"""Pure constructors for official four-player setup state."""

from dataclasses import dataclass, replace
from typing import Final

from dune_imperium.config import RulesetConfig
from dune_imperium.content.bloodlines.sardaukar import (
    COMMANDER_BANK_AT_SETUP,
    COMMANDER_SETUP_SPACE_IDS,
    SKILL_FACE_UP,
    skill_tile_instance_ids,
)
from dune_imperium.content.bloodlines.tech import TECH_STACKS, tech_tiles_for
from dune_imperium.content.immortality.board import (
    RESEARCH_START_ID,
    TLEILAXU_ROW_SIZE,
    TLEILAXU_SETUP_SPICE,
)
from dune_imperium.content.immortality.tleilaxu import tleilaxu_deck_instance_ids
from dune_imperium.content.uprising.conflicts import conflicts_by_tier
from dune_imperium.content.uprising.contracts import contract_instance_ids
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import (
    intrigue_deck_instance_ids,
    navigation_card_instance_ids,
    twisted_intrigue_instance_ids,
)
from dune_imperium.content.uprising.leaders import LEADERS_BY_ID, leaders_for_choam
from dune_imperium.content.uprising.objectives import objectives_for_players
from dune_imperium.content.uprising.reserve import RESERVE_STACKS
from dune_imperium.content.uprising.starting_cards import (
    starting_card_for_instance,
    starting_deck_instance_ids,
)
from dune_imperium.content.uprising.types import ConflictTier
from dune_imperium.core.chance import (
    ChanceOutcome,
    ChanceReplayError,
    ChanceResolver,
    validate_chance_outcome,
)
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.navigation import assign_navigation_deck
from dune_imperium.rules.tactics import TACTICS_TRACK_START
from dune_imperium.rules.tech import assign_secret_project


@dataclass(frozen=True, slots=True)
class ConflictSetup:
    """Selected ten-card deck and hidden cards returned to the box."""

    deck: tuple[str, ...]
    unused: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.deck) != 10:
            raise ValueError("the four-player Conflict deck must contain 10 cards")
        if len(self.unused) not in (6, 8):
            # 16 retail cards, or 18 with the two Bloodlines cards.
            raise ValueError(
                "six (eight with Bloodlines) Conflict cards must remain unused"
            )
        if set(self.deck) & set(self.unused):
            raise ValueError("selected and unused Conflict cards must be disjoint")


@dataclass(frozen=True, slots=True)
class SetupResult:
    """A completed setup state and its replayable chance stream."""

    state: GameState
    chance_outcomes: tuple[ChanceOutcome, ...]


def create_unshuffled_players(
    *, immortality: bool = False
) -> tuple[PlayerState, ...]:
    """Create four players before leader, objective, and shuffle decisions.

    With Immortality the two Dune, the Desert Planet become Experimentation
    [Immortality p. 5]; the Bene Tleilax tokens and Family Atomics are
    placed by ``_with_immortality``.
    """

    return tuple(
        PlayerState(
            player_id=player,
            deck=starting_deck_instance_ids(player, immortality=immortality),
        )
        for player in range(4)
    )


def conflict_setup_decisions(*, bloodlines: bool = False) -> tuple[ChanceDecision, ...]:
    """Return tier shuffles in the order prescribed by setup.

    Bloodlines adds its two Conflict cards to the pools the tiers are drawn
    from; the deck keeps its 1/5/4 shape [Bloodlines p. 3].
    """

    return tuple(
        ChanceDecision(
            decision_id=f"setup:conflict:tier:{tier.value}",
            prompt=f"Shuffle and select Conflict tier {tier.value}",
            options=tuple(
                conflict.card.card_id
                for conflict in conflicts_by_tier(tier, bloodlines=bloodlines)
            ),
            count=count,
        )
        for tier, count in (
            (ConflictTier.THREE, 4),
            (ConflictTier.TWO, 5),
            (ConflictTier.ONE, 1),
        )
    )


def build_conflict_setup(
    outcomes: tuple[ChanceOutcome, ...],
    *,
    bloodlines: bool = False,
) -> ConflictSetup:
    """Build the top-to-bottom deck from the three recorded tier outcomes."""

    decisions = conflict_setup_decisions(bloodlines=bloodlines)
    if len(outcomes) != len(decisions):
        raise ValueError("Conflict setup requires one outcome for each tier")

    by_id = {outcome.decision_id: outcome for outcome in outcomes}
    if len(by_id) != len(outcomes):
        raise ValueError("Conflict setup outcomes must have unique decision IDs")
    selected: dict[ConflictTier, tuple[str, ...]] = {}
    unused: list[str] = []
    for decision, tier in zip(
        decisions,
        (ConflictTier.THREE, ConflictTier.TWO, ConflictTier.ONE),
        strict=True,
    ):
        try:
            outcome = by_id[decision.decision_id]
        except KeyError as error:
            raise ValueError("Conflict setup outcome is missing a tier") from error
        validate_chance_outcome(decision, outcome)
        selected[tier] = outcome.values
        unused.extend(
            option for option in decision.options if option not in outcome.values
        )

    return ConflictSetup(
        deck=(
            *selected[ConflictTier.ONE],
            *selected[ConflictTier.TWO],
            *selected[ConflictTier.THREE],
        ),
        unused=tuple(unused),
    )


def objective_setup_decision() -> ChanceDecision:
    """Return the ordered four-card deal for a four-player game."""

    return ChanceDecision(
        decision_id="setup:objectives",
        prompt="Shuffle and deal the four-player Objective cards",
        options=tuple(
            objective.objective_id for objective in objectives_for_players(4)
        ),
        count=4,
    )


SARDAUKAR_CONTRACT_IDS: Final = ("contract:sardaukar_i", "contract:sardaukar_ii")


def contract_setup_decision(
    set_aside_ids: tuple[str, ...] = (),
) -> ChanceDecision:
    """Return the setup shuffle for the standard Contracts.

    When Shaddam Corrino IV is in play, both Sardaukar Contracts are set
    aside before the shuffle [Shaddam Corrino IV card] and are excluded from
    the shuffled pool.
    """

    contracts = tuple(
        instance_id
        for instance_id in contract_instance_ids()
        if instance_id not in set_aside_ids
    )
    return _shuffle_decision(
        "setup:contracts",
        "Shuffle the standard Contracts",
        contracts,
    )


def assign_objectives(
    players: tuple[PlayerState, ...],
    outcome: ChanceOutcome,
) -> tuple[tuple[PlayerState, ...], int]:
    """Deal one Objective per seat and return the First Player seat."""

    if len(players) != 4 or tuple(player.player_id for player in players) != tuple(
        range(4)
    ):
        raise ValueError("Objective setup requires players in seat order 0 through 3")
    decision = objective_setup_decision()
    validate_chance_outcome(decision, outcome)

    definitions = {
        objective.objective_id: objective for objective in objectives_for_players(4)
    }
    assigned = tuple(
        replace(player, objective_ids=(objective_id,))
        for player, objective_id in zip(players, outcome.values, strict=True)
    )
    first_players = tuple(
        player.player_id
        for player in assigned
        if definitions[player.objective_ids[0]].grants_first_player
    )
    if len(first_players) != 1:
        raise RuntimeError("four-player Objectives must identify one First Player")
    return assigned, first_players[0]


def starting_deck_shuffle_decision(player: PlayerState) -> ChanceDecision:
    """Return the chance decision that orders one starting deck."""

    return ChanceDecision(
        decision_id=f"setup:player:{player.player_id}:starting_deck",
        prompt=f"Shuffle player {player.player_id}'s starting deck",
        options=player.deck,
        count=len(player.deck),
    )


def apply_starting_deck_shuffle(
    player: PlayerState,
    outcome: ChanceOutcome,
) -> PlayerState:
    """Apply a recorded full-deck permutation to one player."""

    validate_chance_outcome(starting_deck_shuffle_decision(player), outcome)
    return replace(player, deck=outcome.values)


def skill_stack_decision() -> ChanceDecision:
    """Shuffle the 14 Skill tiles face down [Bloodlines p. 3]."""

    return _shuffle_decision(
        "setup:skill_stack",
        "Shuffle the Sardaukar Commander Skills",
        skill_tile_instance_ids(),
    )


@dataclass(frozen=True, slots=True)
class BloodlinesSetup:
    """Bloodlines state fields fixed at setup [Bloodlines p. 3]."""

    skill_face_up: tuple[str, ...]
    skill_stack: tuple[str, ...]
    twisted_deck: tuple[str, ...] = ()
    navigation_deck: tuple[str, ...] = ()
    # Tech Module: the three Ixian Embassy stacks, top first.
    tech_stacks: tuple[tuple[str, ...], ...] = ()


def tech_tiles_decision(choam_module: bool) -> ChanceDecision:
    """Shuffle the Tech tiles face down [Bloodlines p. 6]."""

    return _shuffle_decision(
        "setup:tech_tiles",
        "Shuffle the Tech tiles",
        tuple(tile.tech_id for tile in tech_tiles_for(choam_module)),
    )


def deal_tech_stacks(shuffled: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    """Divide the shuffled tiles into three stacks, as evenly as possible.

    Eighteen tiles make three stacks of six; without CHOAM Transports the
    seventeen are split 6-6-5 [Bloodlines p. 6].
    """

    base, extra = divmod(len(shuffled), TECH_STACKS)
    stacks: list[tuple[str, ...]] = []
    cursor = 0
    for index in range(TECH_STACKS):
        size = base + (1 if index < extra else 0)
        stacks.append(shuffled[cursor : cursor + size])
        cursor += size
    return tuple(stacks)


def navigation_deck_decision() -> ChanceDecision:
    """Shuffle Steersman Y'rkoon's ten Navigation cards [Steersman Y'rkoon card]."""

    return _shuffle_decision(
        "setup:navigation",
        "Shuffle the Navigation cards",
        navigation_card_instance_ids(),
    )


def twisted_deck_decision() -> ChanceDecision:
    """Shuffle Piter De Vries' twelve Twisted Intrigue cards [Piter De Vries card]."""

    return _shuffle_decision(
        "setup:twisted_intrigue",
        "Shuffle the Twisted Intrigue deck",
        twisted_intrigue_instance_ids(),
    )


def _bloodlines_setup(
    config: RulesetConfig,
    resolver: ChanceResolver,
) -> BloodlinesSetup | None:
    """Deal the Skill tiles when the Bloodlines option is on.

    The shuffled 14-tile stack shows four face up [Bloodlines p. 3]; the
    Commander placement itself is static (``_with_bloodlines``).
    """

    if not config.bloodlines:
        return None
    skills = resolver.resolve(skill_stack_decision()).values
    # The Twisted deck is shuffled whether or not Piter is picked (the
    # draft chooses Leaders later); it waits in ``twisted_deck_stock``.
    twisted = resolver.resolve(twisted_deck_decision()).values
    navigation = resolver.resolve(navigation_deck_decision()).values
    tech_stacks: tuple[tuple[str, ...], ...] = ()
    if config.tech_module:
        tech_stacks = deal_tech_stacks(
            resolver.resolve(tech_tiles_decision(config.choam_module)).values
        )
    return BloodlinesSetup(
        skill_face_up=skills[:SKILL_FACE_UP],
        skill_stack=skills[SKILL_FACE_UP:],
        twisted_deck=twisted,
        navigation_deck=navigation,
        tech_stacks=tech_stacks,
    )


def _with_bloodlines(state: GameState, setup: BloodlinesSetup | None) -> GameState:
    """Place the Commanders and the dealt Skills on a freshly built state.

    Five Commanders go on their printed spaces plus one on Assembly Hall in
    a four-player game, and the last one waits in the bank for Sardaukar
    Standard [Bloodlines p. 3].
    """

    if setup is None:
        return state
    return assign_secret_project(
        assign_navigation_deck(
            assign_twisted_deck(
                replace(
                    state,
                    sardaukar_commander_space_ids=COMMANDER_SETUP_SPACE_IDS,
                sardaukar_commanders_bank=COMMANDER_BANK_AT_SETUP,
                skill_face_up=setup.skill_face_up,
                skill_stack=setup.skill_stack,
                    twisted_deck_stock=setup.twisted_deck,
                    navigation_stock=setup.navigation_deck,
                    tech_stacks=setup.tech_stacks,
                )
            )
        )
    )


def tleilaxu_deck_decision(promo_cards: bool) -> ChanceDecision | None:
    """Shuffle the Tleilaxu deck [Immortality p. 4], or None while it is empty."""

    instance_ids = tleilaxu_deck_instance_ids(promo_cards)
    if not instance_ids:
        return None
    return _shuffle_decision(
        "setup:tleilaxu_deck", "Shuffle the Tleilaxu deck", instance_ids
    )


def _immortality_setup(
    config: RulesetConfig,
    resolver: ChanceResolver,
) -> tuple[str, ...] | None:
    """Shuffle the Tleilaxu deck when the Immortality option is on.

    Resolved after the Bloodlines decisions so the chance stream of every
    earlier option keeps its order.
    """

    if not config.immortality:
        return None
    decision = tleilaxu_deck_decision(config.promo_cards)
    if decision is None:
        return ()
    return resolver.resolve(decision).values


def _with_immortality(state: GameState, deck: tuple[str, ...] | None) -> GameState:
    """Place the Bene Tleilax board pieces on a freshly built state.

    Two spice wait on the Tleilaxu track's fourth space, every token starts
    on the leftmost space, the Tleilaxu Row shows two cards next to the
    fixed Reclaimed Forces, and each player holds a Family Atomics token
    [Immortality pp. 4-5].
    """

    if deck is None:
        return state
    return replace(
        state,
        players=tuple(
            replace(
                player,
                research_space=RESEARCH_START_ID,
                tleilaxu_space=0,
                family_atomics=True,
            )
            for player in state.players
        ),
        tleilaxu_row=deck[:TLEILAXU_ROW_SIZE],
        tleilaxu_deck=deck[TLEILAXU_ROW_SIZE:],
        tleilaxu_track_spice=TLEILAXU_SETUP_SPICE,
    )


def assign_twisted_deck(state: GameState) -> GameState:
    """Hand the shuffled Twisted Intrigue deck to Piter De Vries' seat."""

    if not state.twisted_deck_stock:
        return state
    piter = next(
        (seat for seat in state.players if seat.leader_id == "piter_de_vries"), None
    )
    if piter is None:
        return state
    dealt = replace(piter, twisted_deck=state.twisted_deck_stock)
    return replace(
        state,
        players=tuple(dealt if seat is piter else seat for seat in state.players),
        twisted_deck_stock=(),
    )


def create_initial_state(
    config: RulesetConfig,
    seed: int,
    leader_ids: tuple[str, ...],
    recorded_outcomes: tuple[ChanceOutcome, ...] | None = None,
) -> SetupResult:
    """Build the complete pre-Round-Start state for four selected Leaders.

    Leader choice remains an explicit caller decision because the official rules
    permit either selection or random assignment without defining a draft order.
    Every actual shuffle and deal is routed through the returned chance stream.
    """

    _validate_leader_selection(config, leader_ids)
    resolver = ChanceResolver(seed=seed, recorded=recorded_outcomes)

    conflict = build_conflict_setup(
        tuple(
            resolver.resolve(decision)
            for decision in conflict_setup_decisions(bloodlines=config.bloodlines)
        ),
        bloodlines=config.bloodlines,
    )
    players, first_player = assign_objectives(
        create_unshuffled_players(immortality=config.immortality),
        resolver.resolve(objective_setup_decision()),
    )
    players = tuple(
        replace(
            player,
            leader_id=leader_id,
            # Double-sided Leaders begin on their printed setup face
            # [Main p. 17]; every other Leader's face is its identity.
            leader_face_id=(LEADERS_BY_ID[leader_id].setup_face_id or leader_id),
            # Printed setup rules may remove starting cards (Staban Tuek's
            # Limited Allies); the shuffle decision below then covers the
            # reduced deck.
            deck=tuple(
                instance_id
                for instance_id in player.deck
                if starting_card_for_instance(instance_id).card.card_id
                not in LEADERS_BY_ID[leader_id].removed_starting_card_ids
            ),
            # Strange Form: Steersman Y'rkoon starts with no water.
            resources=replace(
                player.resources, water=LEADERS_BY_ID[leader_id].starting_water
            ),
            # Tactician: the Tactics token starts on the four-player space
            # [Bloodlines p. 12].
            tactics_track_space=(
                TACTICS_TRACK_START
                if LEADERS_BY_ID[leader_id].uses_tactics_track
                else 0
            ),
        )
        for player, leader_id in zip(players, leader_ids, strict=True)
    )

    imperium = resolver.resolve(
        _shuffle_decision(
            "setup:imperium_deck",
            "Shuffle the Imperium deck",
            imperium_deck_instance_ids(
                config.choam_module,
                config.promo_cards,
                bloodlines=config.bloodlines,
                tech_module=config.tech_module,
                immortality=config.immortality,
            ),
        )
    ).values
    intrigue = resolver.resolve(
        _shuffle_decision(
            "setup:intrigue_deck",
            "Shuffle the Intrigue deck",
            intrigue_deck_instance_ids(
                config.choam_module,
                bloodlines=config.bloodlines,
                tech_module=config.tech_module,
                immortality=config.immortality,
            ),
        )
    ).values
    # Sardaukar Commander sets aside both Sardaukar Contracts before the
    # shuffle; only Shaddam can acquire them [Shaddam Corrino IV card].
    sardaukar_set_aside = (
        SARDAUKAR_CONTRACT_IDS
        if config.choam_module and "shaddam_corrino_iv" in leader_ids
        else ()
    )
    contracts = (
        resolver.resolve(contract_setup_decision(sardaukar_set_aside)).values
        if config.choam_module
        else ()
    )
    bloodlines = _bloodlines_setup(config, resolver)
    immortality = _immortality_setup(config, resolver)
    players = tuple(
        apply_starting_deck_shuffle(
            player,
            resolver.resolve(starting_deck_shuffle_decision(player)),
        )
        for player in players
    )

    if recorded_outcomes is not None and not resolver.exhausted:
        raise ChanceReplayError("recorded chance stream has unused outcomes")

    state = GameState(
        config=config,
        seed=seed,
        phase=GamePhase.ROUND_START,
        first_player=first_player,
        players=players,
        maker_bonus_spice=maker_bonus_spice_for(leader_ids),
        conflict_deck=conflict.deck,
        unused_conflict_ids=conflict.unused,
        imperium_deck=imperium[5:],
        imperium_row=imperium[:5],
        intrigue_deck=intrigue,
        contract_bank=contracts[2:],
        face_up_contract_ids=contracts[:2],
        sardaukar_contract_ids=sardaukar_set_aside,
        reserve_stacks=tuple(
            (stack.card.card_id, stack.copies) for stack in RESERVE_STACKS
        ),
    )
    state = _with_immortality(_with_bloodlines(state, bloodlines), immortality)
    return SetupResult(state=state, chance_outcomes=resolver.outcomes)


LEADER_DRAFT_POOL_SIZE: Final = 6


def leader_draft_pool_decision(config: RulesetConfig) -> ChanceDecision:
    """Return the seeded face-up six-Leader deal of the OQ-007 draft."""

    return ChanceDecision(
        decision_id="setup:leader_draft_pool",
        prompt="Deal six face-up Leaders for the draft",
        options=tuple(
            leader.leader_id
            for leader in leaders_for_choam(
                config.choam_module,
                bloodlines=config.bloodlines,
                tech_module=config.tech_module,
            )
        ),
        count=LEADER_DRAFT_POOL_SIZE,
    )


def create_draft_initial_state(
    config: RulesetConfig,
    seed: int,
    recorded_outcomes: tuple[ChanceOutcome, ...] | None = None,
) -> SetupResult:
    """Build the paused pre-pick state of the OQ-007 draft convention.

    Everything independent of the Leader picks resolves eagerly through the
    seeded chance stream: Conflict tiers, Objectives (which fix the First
    Player), the public six-Leader pool, and full-set shuffles of the
    Imperium deck, the Intrigue deck, the standard Contracts, and every
    starting deck. The state then waits in ``GamePhase.SETUP`` on a
    ``leader_draft`` frame owned by the last seat of the round-1 turn order.
    Each pick finalizes its seat — printed starting-card removals filter the
    already-shuffled deck, which leaves the remaining order uniformly random
    — and the final pick deals the Contract market (setting the Sardaukar
    Contracts aside when Shaddam was picked) and hands off to Round Start.
    """

    if not config.leader_draft:
        raise ValueError("the draft setup requires the leader_draft option")
    resolver = ChanceResolver(seed=seed, recorded=recorded_outcomes)

    conflict = build_conflict_setup(
        tuple(
            resolver.resolve(decision)
            for decision in conflict_setup_decisions(bloodlines=config.bloodlines)
        ),
        bloodlines=config.bloodlines,
    )
    players, first_player = assign_objectives(
        create_unshuffled_players(immortality=config.immortality),
        resolver.resolve(objective_setup_decision()),
    )
    pool = resolver.resolve(leader_draft_pool_decision(config)).values
    imperium = resolver.resolve(
        _shuffle_decision(
            "setup:imperium_deck",
            "Shuffle the Imperium deck",
            imperium_deck_instance_ids(
                config.choam_module,
                config.promo_cards,
                bloodlines=config.bloodlines,
                tech_module=config.tech_module,
                immortality=config.immortality,
            ),
        )
    ).values
    intrigue = resolver.resolve(
        _shuffle_decision(
            "setup:intrigue_deck",
            "Shuffle the Intrigue deck",
            intrigue_deck_instance_ids(
                config.choam_module,
                bloodlines=config.bloodlines,
                tech_module=config.tech_module,
                immortality=config.immortality,
            ),
        )
    ).values
    # The full Contract order is drawn now; whether the Sardaukar Contracts
    # leave it is only known after the picks, so the market is dealt then.
    contracts = (
        resolver.resolve(contract_setup_decision()).values
        if config.choam_module
        else ()
    )
    bloodlines = _bloodlines_setup(config, resolver)
    immortality = _immortality_setup(config, resolver)
    players = tuple(
        apply_starting_deck_shuffle(
            player,
            resolver.resolve(starting_deck_shuffle_decision(player)),
        )
        for player in players
    )

    if recorded_outcomes is not None and not resolver.exhausted:
        raise ChanceReplayError("recorded chance stream has unused outcomes")

    last_picker = (first_player + config.players - 1) % config.players
    state = GameState(
        config=config,
        seed=seed,
        phase=GamePhase.SETUP,
        first_player=first_player,
        players=players,
        conflict_deck=conflict.deck,
        unused_conflict_ids=conflict.unused,
        imperium_deck=imperium[5:],
        imperium_row=imperium[:5],
        intrigue_deck=intrigue,
        contract_bank=contracts,
        leader_draft_pool=pool,
        reserve_stacks=tuple(
            (stack.card.card_id, stack.copies) for stack in RESERVE_STACKS
        ),
        decision_stack=(
            DecisionFrame(
                kind=FrameKind.LEADER_DRAFT,
                frame_id="setup:leader_draft",
                decision=PlayerDecision(
                    owner=last_picker,
                    prompt="Pick a Leader from the face-up draft pool",
                ),
            ),
        ),
        event_log=(
            GameEvent(
                event_id="setup:leader_draft:pool",
                kind="leader_draft_pool_revealed",
                payload=(("leader_ids", ",".join(pool)),),
            ),
        ),
    )
    state = _with_immortality(_with_bloodlines(state, bloodlines), immortality)
    return SetupResult(state=state, chance_outcomes=resolver.outcomes)


def maker_bonus_spice_for(leader_ids: tuple[str, ...]) -> tuple[tuple[str, int], ...]:
    """Return the Maker spice ledger, with Tuek's Sietch while Esmar plays."""

    spaces = ["deep_desert", "hagga_basin", "imperial_basin"]
    if "esmar_tuek" in leader_ids:
        # "During setup, place the Tuek's Sietch board space near the game
        # board. It is a Maker board space" [Bloodlines p. 12].
        spaces.append("tuek_sietch")
    return tuple((space_id, 0) for space_id in spaces)


def _validate_leader_selection(
    config: RulesetConfig,
    leader_ids: tuple[str, ...],
) -> None:
    if len(leader_ids) != config.players:
        raise ValueError("setup requires one Leader for each configured player")
    if len(leader_ids) != len(set(leader_ids)):
        raise ValueError("selected Leaders must be unique physical cards")

    available = {
        leader.leader_id
        for leader in leaders_for_choam(
            config.choam_module,
            bloodlines=config.bloodlines,
            tech_module=config.tech_module,
        )
    }
    unavailable = tuple(
        leader_id for leader_id in leader_ids if leader_id not in available
    )
    if unavailable:
        raise ValueError(f"Leader is not available in this ruleset: {unavailable[0]}")


def _shuffle_decision(
    decision_id: str,
    prompt: str,
    cards: tuple[str, ...],
) -> ChanceDecision:
    return ChanceDecision(
        decision_id=decision_id,
        prompt=prompt,
        options=cards,
        count=len(cards),
    )
