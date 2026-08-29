"""Pure constructors for official four-player setup state."""

from dataclasses import dataclass, replace

from dune_imperium.config import RulesetConfig
from dune_imperium.content.uprising.conflicts import conflicts_by_tier
from dune_imperium.content.uprising.contracts import contract_instance_ids
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.leaders import LEADERS_BY_ID, leaders_for_choam
from dune_imperium.content.uprising.objectives import objectives_for_players
from dune_imperium.content.uprising.reserve import RESERVE_STACKS
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.content.uprising.types import ConflictTier
from dune_imperium.core.chance import (
    ChanceOutcome,
    ChanceReplayError,
    ChanceResolver,
    validate_chance_outcome,
)
from dune_imperium.core.decisions import ChanceDecision
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState


@dataclass(frozen=True, slots=True)
class ConflictSetup:
    """Selected ten-card deck and hidden cards returned to the box."""

    deck: tuple[str, ...]
    unused: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.deck) != 10:
            raise ValueError("the four-player Conflict deck must contain 10 cards")
        if len(self.unused) != 6:
            raise ValueError("six Conflict cards must remain unused")
        if set(self.deck) & set(self.unused):
            raise ValueError("selected and unused Conflict cards must be disjoint")


@dataclass(frozen=True, slots=True)
class SetupResult:
    """A completed setup state and its replayable chance stream."""

    state: GameState
    chance_outcomes: tuple[ChanceOutcome, ...]


def create_unshuffled_players() -> tuple[PlayerState, ...]:
    """Create four players before leader, objective, and shuffle decisions."""

    return tuple(
        PlayerState(
            player_id=player,
            deck=starting_deck_instance_ids(player),
        )
        for player in range(4)
    )


def conflict_setup_decisions() -> tuple[ChanceDecision, ...]:
    """Return tier shuffles in the order prescribed by setup."""

    return tuple(
        ChanceDecision(
            decision_id=f"setup:conflict:tier:{tier.value}",
            prompt=f"Shuffle and select Conflict tier {tier.value}",
            options=tuple(
                conflict.card.card_id for conflict in conflicts_by_tier(tier)
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
) -> ConflictSetup:
    """Build the top-to-bottom deck from the three recorded tier outcomes."""

    decisions = conflict_setup_decisions()
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


def contract_setup_decision() -> ChanceDecision:
    """Return the full shuffle for the 20 standard Contracts."""

    contracts = contract_instance_ids()
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
        tuple(resolver.resolve(decision) for decision in conflict_setup_decisions())
    )
    players, first_player = assign_objectives(
        create_unshuffled_players(),
        resolver.resolve(objective_setup_decision()),
    )
    players = tuple(
        replace(
            player,
            leader_id=leader_id,
            # Double-sided Leaders begin on their printed setup face
            # [Main p. 17]; every other Leader's face is its identity.
            leader_face_id=(
                LEADERS_BY_ID[leader_id].setup_face_id or leader_id
            ),
        )
        for player, leader_id in zip(players, leader_ids, strict=True)
    )

    imperium = resolver.resolve(
        _shuffle_decision(
            "setup:imperium_deck",
            "Shuffle the Imperium deck",
            imperium_deck_instance_ids(config.choam_module),
        )
    ).values
    intrigue = resolver.resolve(
        _shuffle_decision(
            "setup:intrigue_deck",
            "Shuffle the Intrigue deck",
            intrigue_deck_instance_ids(config.choam_module),
        )
    ).values
    contracts = (
        resolver.resolve(contract_setup_decision()).values
        if config.choam_module
        else ()
    )
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
        conflict_deck=conflict.deck,
        unused_conflict_ids=conflict.unused,
        imperium_deck=imperium[5:],
        imperium_row=imperium[:5],
        intrigue_deck=intrigue,
        contract_bank=contracts[2:],
        face_up_contract_ids=contracts[:2],
        reserve_stacks=tuple(
            (stack.card.card_id, stack.copies) for stack in RESERVE_STACKS
        ),
    )
    return SetupResult(state=state, chance_outcomes=resolver.outcomes)


def _validate_leader_selection(
    config: RulesetConfig,
    leader_ids: tuple[str, ...],
) -> None:
    if len(leader_ids) != config.players:
        raise ValueError("setup requires one Leader for each configured player")
    if len(leader_ids) != len(set(leader_ids)):
        raise ValueError("selected Leaders must be unique physical cards")

    available = {leader.leader_id for leader in leaders_for_choam(config.choam_module)}
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
