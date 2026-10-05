"""Stable integer encoding for structured Uprising actions."""

from dataclasses import dataclass, field
from numbers import Integral

from dune_imperium.adapters.observation_encoding import MAKER_SPACE_IDS
from dune_imperium.config import RulesetConfig
from dune_imperium.content.arrakeen_scouts import (
    AUCTIONS,
    EVENTS,
    MAX_AUCTION_BID,
    MAX_MERCENARIES_BID,
    MAX_SPECIMEN_TOP_UP,
    SALES,
    scouts_pool,
    subcommittees_for,
)
from dune_imperium.content.bloodlines.sardaukar import SKILLS
from dune_imperium.content.bloodlines.tech import TECH_TILES
from dune_imperium.content.immortality.board import (
    RESEARCH_SPACES_BY_ID,
    RESEARCH_START_ID,
)
from dune_imperium.content.immortality.tleilaxu import (
    tleilaxu_cards_for,
    tleilaxu_deck_instance_ids,
)
from dune_imperium.content.uprising.board import (
    BOARD_SPACES,
    OBSERVATION_POSTS,
    BoardSpace,
    Faction,
)
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.contracts import contract_instance_ids
from dune_imperium.content.uprising.effect_dsl import OnTroopsLostAtConflictEnd
from dune_imperium.content.uprising.imperium import (
    ImperiumCardEntry,
    imperium_cards_for_choam,
    imperium_deck_instance_ids,
)
from dune_imperium.content.uprising.intrigue import (
    intrigue_card_for_instance,
    intrigue_deck_instance_ids,
    navigation_card_instance_ids,
    twisted_intrigue_instance_ids,
)
from dune_imperium.content.uprising.leaders import (
    FEYD_TRACK_START,
    FEYD_TRAINING_TRACK,
    leaders_for_choam,
)
from dune_imperium.content.uprising.objectives import objectives_for_players
from dune_imperium.content.uprising.personal_cards import card_is_graft, card_is_usurp
from dune_imperium.content.uprising.reserve import (
    RESERVE_STACKS,
    ReserveStackDefinition,
)
from dune_imperium.content.uprising.starting_cards import (
    CONTROL_THE_SPICE,
    STARTING_DECK,
    StartingCardEntry,
    starting_deck_entries,
    starting_discard_entries,
)
from dune_imperium.content.uprising.types import (
    BLOODLINES_REVEAL_CHOICE_EFFECTS,
    IMMORTALITY_REVEAL_CHOICE_EFFECTS,
    AgentIcon,
    BattleIcon,
    PersonalCardRevealChoiceEffect,
)
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.rules.agent_effects import AUTOMATIC_AGENT_ICONS
from dune_imperium.rules.board_effects import AUTOMATIC_BOARD_ICONS

# v109 (OQ-068, 2026-09-26 user ruling): every Recall Agent effect, not only
# Imperial Privilege, may recall an Into the Fray Agent from the Conflict --
# Steersman's Recall Agent icon and Twisted Mentat
# (recall_conflict_agent_for_agent_card, Bloodlines catalogs) and the
# Sardaukar II / High Council token Contract reward
# (recall_conflict_agent_for_contract, CHOAM+Bloodlines catalogs).
# v110 (OQ-057 (14)): an Agent-box Spy without a Spy in supply may pass up
# the recall-first when the box resolves [Main pp. 9, 11, 20]
# (decline_agent_card_spy, every catalog), instead of only fizzling at the
# turn's end.
# v111 (2026-09-27): the standard Contract set drops the four Rise of Ix
# tiles (Espionage II, Harvest 3+/4+ with a Contract, Heighliner III) for
# Spice Refinery I and II and the second copies of Espionage I and Harvest
# 3+ [Main p. 16]; the per-Contract templates follow the new instance ids.
# v112: the ``arrakeen_scouts`` option joined ``RulesetConfig``, so every
# state hash changes and old saves need the clean version error -- no
# Scouts templates exist yet.
# v113: the first Scouts templates (Friends Everywhere's choice of Influence
# 4 bonus), only in ``arrakeen_scouts`` catalogs.
# v114: subcommittees (join/decline) and the Scouts effect frame's choices.
# v115: the Scouts events' and sales' turn-order choices and Influence losses.
# v116: missions (take part or pass, collect on a visit).
# v117: Desert Riding's Maker Hooks token at Hagga Basin.
# v118: secret picks (Covert Operation, Offworld Operation).
# v119: auctions (sealed bids, Mercenaries' retreat, Critical Moment).
# v120: the ``go_to_11`` option joined ``RulesetConfig``, so every state
# hash changes and old saves need the clean version error -- no template
# changes.
# v121: Immortality specimen top-ups before a Scouts recruit, mission or
# Mercenaries deployment, and an Agent recalled from the Conflict. (The
# Mercenaries part is superseded by v122: Mercenaries now tops up by itself.)
# v122: Round Start follows the rules order [Main p. 8] [Main p. 20]: the
# Control defense comes before the draw (OQ-072). The same batch of
# Arrakeen Scouts rulings changes replays too: Mercenaries returns its
# specimens by itself, so ``scouts_return_specimens`` is no longer offered
# there (OQ-074 (a)); Critical Moment is not drawn while the Imperium deck
# is short, which changes that draw's options (OQ-087 (b)); Clear the
# Market's CHOAM shuffle mixes the old pair into the whole bank before
# dealing (OQ-083); CHOAM Research skips Bloodlines' Immediate Contract
# (OQ-090); a mandatory event a seat can do only one line of still opens
# its choice frame (OQ-071); Emperor's Schemes reshuffles the Intrigue
# discard when the deck is short (OQ-078). Saves whose game met any of
# these replay differently -- no template change.
# v123: the subcommittee join moves into the turn: choose_subcommittee (no
# arguments, every Scouts catalog) opens the list any time in the turn a
# High Council seat was taken, beside the visit's other effects or in the
# rest of Corrinth City's Reveal turn, and decline_subcommittee is offered
# there too; the old immediate offer is gone (OQ-076 alternative C, user
# ruling 2026-09-30).
# v124: the ``epic_game`` option (Epic Game Mode) joined ``RulesetConfig``;
# its catalogs add Control the Spice's templates and Economic Supremacy's
# ``flip_battle_card``. Catalogs without the option are unchanged. (Built
# as v121 on the epic-game-mode branch; renumbered when it was merged onto
# the line that had meanwhile used v121..v123.)
# v125: every Agent turn ends only through its owner's ``finish_agent_turn``
# (OQ-095, user ruling 2026-09-30): the last effect no longer hands the turn
# over, so a Plot Intrigue, Family Atomics, a specimen return, a Tech flip or
# a Commander recruit stays possible until the press, and what the last
# effect left behind resolves inside the turn. Usurp's borrowed card is
# trashed by the press and its results are the turn's own. An Arrakeen
# Scouts line's spice cost now counts as spice spent this turn, like every
# other spend. Saves replay differently -- no template change. The
# ``turn_closed`` fields (the 4th field of the Skill choice, Navigation play
# and Scouts offer queues, and the frame-context markers) left the state.
# Also in v125 (L2, merged with L1): Desert Power's Reveal choice opens for
# a seat without Maker Hooks too, whose 2 Persuasion now count only from
# ``decline_reveal_sandworm`` (option (B), user ruling 2026-09-30; OQ-069).
# Imperial Privilege's recall and a Contract's Recall Agent reward with no
# target are no longer skipped unasked: the owner confirms them with
# ``resolve_imperial_privilege_without_recall`` (every catalog) and
# ``resolve_contract_without_recall`` (CHOAM catalogs), and the engine hook
# ``skip_impossible_imperial_privilege_recall`` is gone (OQ-023, OQ-068).
# An Immortality research bonus whose arrow cost cannot be paid opens its
# window too, offering only ``decline_research_bonus`` (no template change;
# the ``research_bonus_unavailable`` event is gone).
# A Conflict reward's "choose a Faction" Influence with every eligible
# Faction at the top opens its window too, offering only
# ``resolve_combat_influence_without_faction`` (every catalog; OQ-060); the
# engine no longer drops it unasked. A Conflict reward Spy and Panopticon's
# Spy with nothing to place offer only their declines (no template change;
# unreachable with four players, and the ``tech_reveal_unavailable`` event is
# gone, OQ-044 (b)).
# Holy War's unit loss asks every opponent, even with one (zone, unit) to
# lose or none (OQ-036 (a), user ruling 2026-09-30, which reverses the
# automatic single-option loss and the event-only skip); a seat with no unit
# confirms with ``resolve_unit_loss_without_unit`` (Bloodlines catalogs).
# The windows follow the printed order: every opponent's loss, then every
# opponent's Spy moves (user ruling 2026-10-02).
# Rare sites that skipped without asking now open their windows too. Per
# the user ruling of 2026-09-30 (every automatic skip opens a window):
# Plasteel Blades' extra Skill with nothing to gain offers only
# ``decline_skill`` (OQ-044 (c)); a Navigation card with no usable line
# offers only ``decline_navigation`` (OQ-039 (b)); a card's Tech
# acquisition with no tile left offers only ``decline_tech`` (the
# ``tech_acquisition_unavailable`` event is gone, OQ-057 (9)); a new High
# Council seat's subcommittee offer is always armed, offering only
# ``decline_subcommittee`` when every subcommittee is taken (unreachable
# with four players; the ``scouts_subcommittee_unavailable`` event is
# gone, OQ-076 (c)). Per the user ruling of 2026-10-02 (L2-Q3, confirm
# windows for the old no-window rulings): a bank Commander gained with no
# choosable Skill is confirmed with ``resolve_commander_without_skill``
# (Bloodlines catalogs; OQ-031, OQ-035 (b)), and Imperium Ceremony with
# one Intrigue card left and no discard opens its peek on that card
# (OQ-052). No other template change.
# A Contract icon over a market where nothing can be taken (only the
# Bloodlines Immediate, no Intrigue card to trash) is no longer held
# unasked: the owner confirms it with ``hold_contract_icons``
# (CHOAM+Bloodlines catalogs; OQ-059, user ruling 2026-09-30). Such an icon
# from a Conflict reward is held to the end of its seat's Conflict rewards
# and then fizzles with ``contract_icons_fizzled`` (user ruling 2026-10-02,
# L2-Q2); it no longer reaches a later turn nor vanishes silently.
# Shortfalls with nothing to choose open no window but are logged (user
# ruling 2026-10-02, L2-Q4): an Intrigue draw the Intrigue deck and
# discard cannot cover together logs ``intrigue_draw_short``, and
# Suspensor Suits troops only partly deployed log
# ``suspensor_deployment_unavailable`` too (no template change; the event
# log, and so a replay's hashes, moves).
# v126 (user rulings of 2026-10-02 after v125 was pushed, OQ-059): a Combat
# Intrigue's Contract icons with nothing to take fizzle as the card
# resolves, confirmed by ``resolve_contract_icons_without_contract``
# (CHOAM+Bloodlines catalogs: one template, which shifts every later one),
# and icons held in the Arrakeen Scouts step reopen when an Intrigue card
# arrives and fizzle as the step ends.
# v127: a Combat Intrigue card that leaves a window of its own above the
# Combat Intrigue loop (Reach Agreement's Contract market, Battlefield
# Research's Tech window) still restarts the consecutive passes, and so
# does Harvest Cells laid face up [Main p. 14]; the loop drops a participant
# left without units once that window closes (OQ-003), and a loop that
# empties so now logs combat_intrigue_finished (event id ``...:emptied``;
# the event log, so the state hash, gains it). Saves replay differently --
# no template change.
# v128: with the OQ-007 Leader draft, Epic Game Mode's setup Intrigue card
# is dealt after the last pick instead of before the first, since it is
# drawn once every Leader is known [Rise of Ix p. 10]. Each seat gets the
# same card; the draft-phase states (hands, Intrigue deck, observations)
# and so a draft save's hashes move -- no template change.
# v129 (user ruling 2026-10-03, OQ-016): "When you deploy three or more
# units to the Conflict in a single turn" is a condition for playing
# Distraction and Coercive Negotiation [FAQ p. 2] [Board Guide p. 10], met at
# the turn's deployment peak (designer ruling), not a trigger they wait face
# up for. Distraction's Spy now goes through the Intrigue choice
# (``place_intrigue_spy`` / ``recall_spy_for_intrigue`` /
# ``decline_intrigue_spy`` with the shared-post targets), so
# ``decline_intrigue_trigger``, ``place_trigger_spy`` and
# ``recall_spy_for_trigger`` leave every catalog (-27); Coercive
# Negotiation keeps ``take_trigger_contract``. The player's offer record
# became the turn's deployment peak, so every state hash moves.
# v130 (user ruling 2026-10-04, OQ-021, following the Steam app): over an
# exhausted market Shaddam's Contract icon must take a set-aside Sardaukar
# Contract while one remains -- nobody has taken them, so the two-Solari
# reversion [Main p. 16] waits until they are gone. ``take_exhausted_contract
# _solari`` leaves the CHOAM catalogs (-1). Also v130 (user ruling 2026-10-04,
# OQ-005): an Objective "counts as a Conflict card you've already won"
# [Objective card], so the Endgame Intrigue flips and Grasp Arrakis may take
# it; ``flip_battle_card`` gains one template per Objective of the player
# count in every catalog (+4). Also v130 (user rulings 2026-10-04, OQ-030,
# OQ-049, OQ-050): a recruit or specimen shortfall waits on the seat
# (``PlayerState.ungained_troops``/``ungained_specimens``, so every state
# hash moves) and is made up when troops return to its supply in the same
# turn, and ``return_specimen`` is also offered at Combat Intrigue priority
# and at a supply-less Control defense; replays change, no template does.
# v131 (user rulings 2026-10-04, second batch): the Emperor track's
# Influence-4 Spy owed inside its owner's turn waits as the freely ordered
# action ``place_track_spy`` until placed (OQ-057 (15), following the Steam
# app; +1 template in every catalog); a card discarded straight from a deck
# fires its discard trigger (OQ-013); Interstellar Trade adds +1 Persuasion
# per contract completed later in the Reveal and a trashed card's Reveal
# effects pay nothing late (OQ-028 (c) restored, OQ-022); Call to Arms waits
# for the decision frames the acquired card's own effects opened (OQ-012);
# an Intrigue "trash" goes to the Intrigue discard and ``GameState`` no
# longer has an Intrigue trash zone (OQ-061). Every state hash and many
# replays change.
# v132 (user rulings 2026-10-04, third batch): Litany Against Fear and
# Withdrawn ("At the start of your turn: ...") only as the turn's first
# action -- the owner's turn frame records that its start is over (OQ-095
# (6)); Twisted Intrigue cards stay in the Intrigue discard when it is
# reshuffled (OQ-097). No template change; replays and hashes change.
# v133 (user rulings 2026-10-04, fourth batch): a card or Leader retreat or
# loss no longer gives the basic deployment allowance back (OQ-029; only a
# voluntary withdrawal does); the Usurp-borrowed Row card is not counted as
# in play anywhere (OQ-054, [Immortality p. 14]); a separate-line Intrigue
# must use at least one line before it can be finished (OQ-058); Arrakis
# Revolt's no-effect keep-wall line is withheld under a deployment block
# (OQ-026). No template change; replays and hashes change.
# v134: the final Leader pick waits for finish_leader_draft before setup
# reveals hidden cards, so the play server can undo every pick (OQ-007).
# v135: Tech purchases queue freely ordered acquire icons (OQ-098);
# reward choices move from acquire_tech to resolve_tech_acquire_effect.
# v136 (user ruling 2026-10-05, OQ-100): an Arrakeen Scouts line's later
# rewards may resolve ahead of its pending trash icon (Water Discipline's
# draw); ``scouts_rewards_first`` joins the Scouts catalogs (+1).
ACTION_CODEC_VERSION = 136
MAX_DEPLOYMENT_COUNT = 12
MAX_INTRIGUE_DEPLOYMENT = 4
# Seven Sardaukar Commanders exist [Bloodlines p. 2].
MAX_COMMANDER_DEPLOYMENT = 7


@dataclass(frozen=True, slots=True)
class ActionTemplate:
    """Actor-neutral action stored at one stable catalog index."""

    action_id: str
    arguments: tuple[tuple[str, ActionValue], ...] = ()

    def __post_init__(self) -> None:
        DomainAction(self.action_id, actor=0, arguments=self.arguments)


@dataclass(frozen=True, slots=True)
class ActionCodec:
    """Encode, decode, and mask actions for one ruleset configuration."""

    config: RulesetConfig
    catalog: tuple[ActionTemplate, ...] = field(init=False)
    _indices: dict[ActionTemplate, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        catalog = _build_catalog(self.config)
        indices = {template: index for index, template in enumerate(catalog)}
        if len(indices) != len(catalog):
            raise RuntimeError("action catalog contains duplicate templates")
        object.__setattr__(self, "catalog", catalog)
        object.__setattr__(self, "_indices", indices)

    @property
    def size(self) -> int:
        """Return the fixed discrete action-space size."""

        return len(self.catalog)

    def encode(self, action: DomainAction) -> int:
        """Return the integer ID for one structured action."""

        if not 0 <= action.actor < self.config.players:
            raise ValueError("action actor must identify a configured player")
        template = ActionTemplate(
            action_id=action.action_id,
            arguments=_normalize_arguments(action.arguments, action.actor),
        )
        try:
            return self._indices[template]
        except KeyError as error:
            raise ValueError("action is not present in this codec version") from error

    def decode(self, action_index: int, actor: int) -> DomainAction:
        """Reconstruct an actor-owned structured action from an integer ID."""

        if isinstance(action_index, bool) or not isinstance(action_index, Integral):
            raise TypeError("action index must be an integer")
        index = int(action_index)
        if not 0 <= index < self.size:
            raise ValueError("action index is outside the catalog")
        if not 0 <= actor < self.config.players:
            raise ValueError("action actor must identify a configured player")
        template = self.catalog[index]
        return DomainAction(
            action_id=template.action_id,
            actor=actor,
            arguments=_denormalize_arguments(template.arguments, actor),
        )

    def legal_action_mask(
        self,
        legal_actions: tuple[DomainAction, ...],
    ) -> tuple[int, ...]:
        """Return a fixed-width binary mask for the supplied legal actions."""

        mask = [0] * self.size
        for action in legal_actions:
            mask[self.encode(action)] = 1
        return tuple(mask)


def _build_catalog(config: RulesetConfig) -> tuple[ActionTemplate, ...]:
    # The OQ-007 Leader draft picks are part of every catalog so the
    # leader_draft ruleset option never changes the action space; the mask
    # simply keeps them illegal outside a draft setup.
    templates: list[ActionTemplate] = [
        ActionTemplate(
            action_id="pick_leader",
            arguments=(("leader_id", leader.leader_id),),
        )
        for leader in leaders_for_choam(
            config.choam_module,
            bloodlines=config.bloodlines,
            tech_module=config.tech_module,
        )
    ]
    templates.extend(
        ActionTemplate(action_id=action_id)
        for action_id in (
            "finish_leader_draft",
            "decline_combat_reward",
            "decline_combat_reward_spy",
            "decline_combat_reward_trash",
            # A Conflict reward Influence choice with every eligible Faction
            # at the top is confirmed (OQ-060).
            "resolve_combat_influence_without_faction",
            "decline_agent_card_trash",
            "decline_agent_card_payment",
            "decline_corrinth_city_payment",
            "decline_agent_card_intrigue_payment",
            "decline_agent_card_discard",
            "decline_agent_card_acquisition",
            "decline_control_defense",
            "decline_leader_board_repeat",
            "decline_leader_card_trash",
            "decline_leader_signet_payment",
            # A Leader's Spy may pass up the recall-first without a Spy in
            # supply [Main pp. 11, 20].
            "decline_leader_spy_placement",
            "decline_other_memories",
            "decline_gather_intelligence",
            "decline_reveal_spy_recall",
            "decline_reveal_influence_exchange",
            "decline_reveal_card_trash",
            "skip_intrigue_acquisition",
            "finish_intrigue_effects",
            "decline_reveal_sandworm",
            "decline_reveal_spice_influence",
            "decline_reveal_troop_retreat",
            # Unswerving Loyalty's Fremen Bond troop move [Unswerving Loyalty
            # card], shared with Shadout Mapes (Immortality).
            "decline_reveal_troop_move",
            "deploy_reveal_card_troop",
            "retreat_reveal_card_troop",
            "defer_reveal_choice",
            "deploy_control_defense",
            # Reveal troop recruits and Intrigue draws in the owner's order
            # (OQ-045, codec v92).
            "draw_reveal_intrigue",
            "finish_reveal",
            "recruit_reveal_troops",
            "gain_five_reveal_solari",
            "gain_leader_signet_troop",
            "gain_two_reveal_strength",
            "pass_combat_intrigue",
            "pass_endgame_intrigue",
            "pay_agent_card_water",
            "pay_agent_card_spice",
            "pay_agent_card_spice_for_sandworm",
            "pay_agent_card_spice_for_sandworm_and_shield_wall",
            "pay_leader_board_repeat",
            "pay_leader_signet_solari",
            "pay_leader_signet_spice",
            "pay_reveal_water_for_sandworm",
            "take_high_council_from_reveal",
            "pay_combat_reward",
            "resolve_agent_card_effect",
            "resolve_desert_tactics_without_trash",
            "resolve_espionage_without_spy",
            # The generic Spy placement frame's way out when nothing can be
            # placed (every ruleset since the Emperor track's Spy uses it).
            "decline_spy_placement",
            # The owner's waiting Emperor track Spy, opened in any order
            # inside its own turn (user ruling 2026-10-04).
            "place_track_spy",
            # An acquisition-bonus Spy may pass up the recall-first without a
            # Spy in supply [Main pp. 11, 20] (OQ-057 (14)).
            "decline_acquisition_spy",
            # So may an Agent-box Spy, when the box resolves (codec v110).
            "decline_agent_card_spy",
            "resolve_faction_influence",
            "retreat_leader_troop",
            "reveal_turn",
            "retreat_two_troops_for_reveal",
            "take_sietch_tabr_supplies",
            "take_sietch_tabr_water",
            "take_sietch_tabr_water_and_destroy_wall",
            "use_other_memories",
        )
    )
    # One board-effect resolution per printed automatic icon (OQ-027).
    templates.extend(
        ActionTemplate(
            action_id="resolve_board_effect",
            arguments=(("effect", key),),
        )
        for key in AUTOMATIC_BOARD_ICONS
    )
    # One Agent-box resolution per printed automatic icon of a multi-icon
    # card (OQ-027); single-effect boxes keep the argument-less template.
    templates.extend(
        ActionTemplate(
            action_id="resolve_agent_card_effect",
            arguments=(("effect", key),),
        )
        for key in AUTOMATIC_AGENT_ICONS
    )
    # Bringing back one kind of deferred Reveal choice [Main p. 12].
    templates.extend(
        ActionTemplate(
            action_id="resume_reveal_choice",
            arguments=(("effect", effect.value),),
        )
        for effect in PersonalCardRevealChoiceEffect
        if (config.bloodlines or effect not in BLOODLINES_REVEAL_CHOICE_EFFECTS)
        and (config.immortality or effect not in IMMORTALITY_REVEAL_CHOICE_EFFECTS)
    )
    if config.choam_module:
        templates.extend(
            ActionTemplate(action_id=action_id)
            for action_id in (
                "keep_contract_reveal_spice",
                "trash_contract_reveal_for_vp",
                # A Contract Spy may pass up the recall-first without a Spy
                # in supply [Main pp. 11, 20].
                "decline_contract_spy",
                # A Contract recall reward with no target is confirmed.
                "resolve_contract_without_recall",
            )
        )
    templates.extend(_agent_turn_templates(config))
    templates.extend(_endgame_wild_templates(config))
    templates.extend(_reveal_resource_templates())
    # Basic Combat deployment is adjustable until the explicit turn end
    # (OQ-029): add, withdraw, finish.
    templates.extend(
        ActionTemplate(
            action_id="deploy_troops",
            arguments=(("count", count),),
        )
        for count in range(1, MAX_DEPLOYMENT_COUNT + 1)
    )
    templates.extend(
        ActionTemplate(
            action_id="withdraw_troops",
            arguments=(("count", count),),
        )
        for count in range(1, MAX_DEPLOYMENT_COUNT + 1)
    )
    templates.append(ActionTemplate(action_id="finish_agent_turn"))
    if config.bloodlines:
        templates.extend(_bloodlines_templates(config))
        # Unswerving Loyalty (every ruleset) and Shadout Mapes (Immortality)
        # may move a Sardaukar Commander: it "is a 'troop'" [Bloodlines p. 4].
        templates.extend(
            ActionTemplate(action_id=action_id, arguments=(("commanders", 1),))
            for action_id in ("deploy_reveal_card_troop", "retreat_reveal_card_troop")
        )
    if config.tech_module:
        templates.extend(_tech_templates(config))
    if config.immortality:
        templates.extend(_immortality_templates(config))
    if config.arrakeen_scouts:
        templates.extend(_scouts_templates(config))
    if config.epic_game and not (
        config.bloodlines or config.immortality or config.arrakeen_scouts
    ):
        # Control the Spice's paid trash opens the generic optional-trash
        # frame, which only the Bloodlines, Immortality and Scouts catalogs
        # hold otherwise; it pays with the shared ``pay_agent_card_spice``.
        templates.append(ActionTemplate(action_id="decline_optional_trash"))
        templates.extend(_trash_templates(config, "trash_optional_card"))
    templates.extend(
        ActionTemplate(
            action_id="recall_agent_for_agent_card",
            arguments=(("space_id", space.space_id),),
        )
        for space in catalog_spaces(config)
    )
    templates.extend(
        ActionTemplate(
            action_id="recall_agent_for_imperial_privilege",
            arguments=(("space_id", space.space_id),),
        )
        for space in catalog_spaces(config)
    )
    templates.extend(
        ActionTemplate(
            action_id="acquire_reserve",
            arguments=(("card_id", stack.card.card_id),),
        )
        for stack in RESERVE_STACKS
    )
    imperium_instances = imperium_deck_instance_ids(
        config.choam_module,
        config.promo_cards,
        bloodlines=config.bloodlines,
        tech_module=config.tech_module,
        immortality=config.immortality,
    )
    intrigue_instances = intrigue_deck_instance_ids(
        config.choam_module,
        bloodlines=config.bloodlines,
        tech_module=config.tech_module,
        immortality=config.immortality,
    )
    if config.bloodlines:
        # Piter De Vries' Twisted Intrigue cards are held and played like
        # any Intrigue card once dealt.
        intrigue_instances = (*intrigue_instances, *twisted_intrigue_instance_ids())
    templates.extend(
        ActionTemplate(
            action_id="acquire_imperium",
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in imperium_instances
    )
    if config.bloodlines:
        # Engineered Miracle's Command acquisition from the Imperium Row.
        templates.extend(
            ActionTemplate(
                action_id="command_acquire_row_card",
                arguments=(("instance_id", instance_id),),
            )
            for instance_id in imperium_instances
        )
        # Litany Against Fear's turn-start play from the hand.
        templates.extend(
            ActionTemplate(
                action_id="play_turn_start_card",
                arguments=(("card_id", instance_id),),
            )
            for instance_id in imperium_instances
            if instance_id.startswith("imperium:litany_against_fear:")
        )
        if config.choam_module:
            # CHOAM Demands completes any active Contract; Coercive
            # Negotiation takes one of the bank's revealed Contracts.
            templates.extend(
                ActionTemplate(
                    action_id=action_id,
                    arguments=(("instance_id", instance_id),),
                )
                for action_id in ("complete_contract_by_card", "take_trigger_contract")
                for instance_id in contract_instance_ids(bloodlines=config.bloodlines)
            )
    if config.choam_module:
        for action_id in ("take_contract", "complete_contract"):
            templates.extend(
                ActionTemplate(
                    action_id=action_id,
                    arguments=(("instance_id", instance_id),),
                )
                for instance_id in contract_instance_ids(bloodlines=config.bloodlines)
            )
        templates.extend(
            ActionTemplate(
                action_id="recall_agent_for_contract",
                arguments=(("space_id", space.space_id),),
            )
            for space in catalog_spaces(config)
        )
    templates.extend(
        ActionTemplate(
            action_id="pay_agent_card_intrigue_and_spice",
            arguments=(("intrigue_card_id", instance_id),),
        )
        for instance_id in intrigue_instances
    )
    # v106: Branching Path trashes an Intrigue card from hand for a Bene
    # Gesserit Alliance reward (Intrigue card, 2 spice) instead of trashing a
    # personal card for 2 troops (card-face re-transcription, 2026-09-19).
    templates.extend(
        ActionTemplate(
            action_id="trash_intrigue_for_agent_card",
            arguments=(("intrigue_card_id", instance_id),),
        )
        for instance_id in intrigue_instances
    )
    # v106: Imperial Privilege trashes the Intrigue card, as its printed icon
    # says (OQ-061); the action was ``discard_intrigue_for_imperial_privilege``.
    # The id stays a trash, though since the OQ-061 user ruling of 2026-10-04
    # the trashed card lands on the shared Intrigue discard.
    templates.extend(
        ActionTemplate(
            action_id="trash_intrigue_for_imperial_privilege",
            arguments=(("card_id", instance_id),),
        )
        for instance_id in intrigue_instances
    )
    templates.extend(
        ActionTemplate(
            action_id="play_intrigue",
            arguments=(("card_id", instance_id), ("option", option)),
        )
        for instance_id in intrigue_instances
        for option in range(len(intrigue_card_for_instance(instance_id).options))
    )
    # Separate printed lines (OQ-058): one template per line index.
    line_count = max(
        len(option.sections)
        for instance_id in intrigue_instances
        for option in intrigue_card_for_instance(instance_id).options
        if option.separate
    )
    templates.extend(
        ActionTemplate(action_id="use_intrigue_effect", arguments=(("section", index),))
        for index in range(line_count)
    )
    templates.extend(
        ActionTemplate(
            action_id="choose_intrigue_faction",
            arguments=(("faction", faction.value),),
        )
        for faction in Faction
    )
    templates.extend(
        ActionTemplate(
            action_id="choose_intrigue_faction",
            arguments=(("alliance_recipient", recipient), ("faction", faction.value)),
        )
        for faction in Faction
        for recipient in range(config.players)
    )
    templates.extend(_trash_templates(config, "choose_intrigue_discard"))
    templates.extend(
        ActionTemplate(action_id=action_id)
        for action_id in (
            "detonate_shield_wall",
            "keep_shield_wall",
            "decline_intrigue_trash",
            "decline_intrigue_spy",
            "decline_imperial_privilege_intrigue",
            # Imperial Privilege's recall with no target is confirmed.
            "resolve_imperial_privilege_without_recall",
            "resolve_intrigue_rewards",
        )
    )
    templates.extend(_trash_templates(config, "trash_intrigue_card"))
    templates.extend(
        ActionTemplate(
            action_id="deploy_intrigue_troops", arguments=(("count", count),)
        )
        for count in range(1, MAX_INTRIGUE_DEPLOYMENT + 1)
    )
    templates.extend(
        ActionTemplate(
            action_id="retreat_intrigue_troops", arguments=(("count", count),)
        )
        for count in range(1, MAX_DEPLOYMENT_COUNT + 1)
    )
    templates.extend(
        ActionTemplate(
            action_id="acquire_intrigue_imperium",
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in imperium_instances
    )
    templates.extend(
        ActionTemplate(
            action_id="acquire_intrigue_reserve",
            arguments=(("card_id", stack.card.card_id),),
        )
        for stack in RESERVE_STACKS
    )
    templates.extend(
        ActionTemplate(
            action_id="flip_battle_card",
            arguments=(("card_id", conflict.card.card_id),),
        )
        for conflict in CONFLICTS
        if (config.bloodlines or not conflict.bloodlines_only)
        and (config.epic_game or not conflict.epic_only)
    )
    # An Objective "counts as a Conflict card you've already won" [Objective
    # card], so the flip effects may take it too (OQ-005, codec v130).
    templates.extend(
        ActionTemplate(
            action_id="flip_battle_card",
            arguments=(("card_id", objective.objective_id),),
        )
        for objective in objectives_for_players(config.players)
    )
    for action_id in ("manipulate_imperium_row", "acquire_manipulated_imperium"):
        templates.extend(
            ActionTemplate(
                action_id=action_id,
                arguments=(("instance_id", instance_id),),
            )
            for instance_id in imperium_instances
        )
    templates.extend(
        ActionTemplate(
            action_id="acquire_imperium_with_solari",
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in imperium_instances
    )
    templates.extend(
        ActionTemplate(
            action_id="acquire_reserve_with_solari",
            arguments=(("card_id", stack.card.card_id),),
        )
        for stack in RESERVE_STACKS
    )
    for space_id in ("deep_desert", "hagga_basin", "imperial_basin"):
        templates.append(
            ActionTemplate(
                action_id="harvest_maker_spice",
                arguments=(("space_id", space_id),),
            )
        )
    for space_id in ("deep_desert", "hagga_basin"):
        templates.append(
            ActionTemplate(
                action_id="summon_maker_sandworms",
                arguments=(("space_id", space_id),),
            )
        )
    post_ids = tuple(post.post_id for post in OBSERVATION_POSTS)
    templates.extend(
        ActionTemplate(
            action_id="gather_intelligence",
            arguments=(("post_id", post_id),),
        )
        for post_id in post_ids
    )
    for action_id in (
        "place_acquisition_spy",
        "place_agent_card_spy",
        "place_intrigue_spy",
        "place_leader_spy",
        "recall_spy_for_intrigue",
        "recall_spy_for_leader",
        "recall_spy_for_leader_placement",
        "place_reveal_spy",
        "recall_spy_for_acquisition",
        "recall_spy_for_agent_card",
        "recall_spy_for_espionage",
        "recall_spy_for_reveal",
        "recall_spy_for_reveal_placement",
        "resolve_espionage_place_spy",
        # v107: the generic placement frame serves the Emperor track's
        # Influence 4 Spy [Main p. 7] in every ruleset, not only Bloodlines.
        "place_spy_on_space",
        "recall_spy_for_placement",
        *(("move_spy",) if config.bloodlines else ()),
        *(
            ("place_contract_spy", "recall_spy_for_contract")
            if config.choam_module
            else ()
        ),
    ):
        templates.extend(
            ActionTemplate(
                action_id=action_id,
                arguments=(("post_id", post_id),),
            )
            for post_id in post_ids
        )
    for action_id in (
        "place_combat_reward_spy",
        # Without a Spy in supply a Conflict reward Spy may recall one first
        # [Main pp. 11, 20].
        "recall_spy_for_combat_reward",
    ):
        templates.extend(
            ActionTemplate(
                action_id=action_id,
                arguments=(("post_id", post_id),),
            )
            for post_id in post_ids
        )
    templates.extend(
        ActionTemplate(
            action_id="recall_spies_for_reveal",
            arguments=(
                ("first_post_id", first_post_id),
                ("second_post_id", second_post_id),
            ),
        )
        for index, first_post_id in enumerate(post_ids)
        for second_post_id in post_ids[index + 1 :]
    )
    templates.extend(
        ActionTemplate(
            action_id="recall_spies_for_combat_reward",
            arguments=(
                ("first_post_id", first_post_id),
                ("second_post_id", second_post_id),
            ),
        )
        for first_post_id in post_ids
        for second_post_id in post_ids
        if first_post_id != second_post_id
    )
    for action_id in (
        "choose_agent_card_influence",
        "choose_combat_reward_influence",
        "choose_distinct_combat_reward_influence",
        "choose_leader_signet_influence",
        "choose_shipping_influence",
    ):
        templates.extend(
            ActionTemplate(
                action_id=action_id,
                arguments=(("faction", faction.value),),
            )
            for faction in Faction
        )
    templates.extend(
        ActionTemplate(
            action_id="exchange_reveal_influence",
            arguments=(
                ("gained_faction", gained_faction.value),
                ("lost_faction", lost_faction.value),
            ),
        )
        for lost_faction in Faction
        for gained_faction in Faction
    )
    templates.extend(
        ActionTemplate(
            action_id="exchange_reveal_influence",
            arguments=(
                ("alliance_recipient", recipient),
                ("gained_faction", gained_faction.value),
                ("lost_faction", lost_faction.value),
            ),
        )
        for lost_faction in Faction
        for gained_faction in Faction
        for recipient in range(config.players)
    )
    templates.extend(
        ActionTemplate(
            action_id="pay_reveal_spice_influence",
            arguments=(("faction", faction.value),),
        )
        for faction in Faction
    )
    templates.extend(
        ActionTemplate(
            action_id="advance_feyd_track",
            arguments=(("space_id", space.space_id),),
        )
        for space in FEYD_TRAINING_TRACK
        if space.space_id != FEYD_TRACK_START
    )
    templates.extend(
        ActionTemplate(
            action_id="acquire_leader_imperium",
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in imperium_instances
    )
    templates.extend(
        ActionTemplate(
            action_id="acquire_leader_reserve",
            arguments=(("card_id", stack.card.card_id),),
        )
        for stack in RESERVE_STACKS
    )
    templates.extend(_trash_templates(config, "trash_leader_card"))
    templates.extend(_trash_templates(config, "trash_agent_card"))
    templates.extend(_trash_templates(config, "select_long_live_fighters_draw"))
    templates.extend(_trash_templates(config, "select_long_live_fighters_discard"))
    templates.extend(_trash_templates(config, "discard_agent_card"))
    templates.extend(_trash_templates(config, "discard_opponent_card"))
    templates.extend(_trash_templates(config, "trash_reveal_card"))
    templates.extend(_trash_templates(config, "trash_combat_reward_card"))
    templates.extend(_trash_templates(config, "trash_card_for_desert_tactics"))
    templates.extend(_trash_templates(config, "select_corrinth_city_discard"))
    templates.extend(_trash_templates(config, "pay_corrinth_city"))
    return tuple(sorted(templates, key=_template_sort_key))


def _bloodlines_templates(config: RulesetConfig) -> tuple[ActionTemplate, ...]:
    """Sardaukar Commander choices [Bloodlines p. 4] (``rules.sardaukar``)."""

    templates: list[ActionTemplate] = [
        ActionTemplate(action_id=action_id)
        for action_id in (
            "decline_sardaukar_commander",
            "recruit_sardaukar_commander",
            # Bought without a Skill when none is choosable (OQ-031).
            "acquire_sardaukar_commander",
            # False Orders / Holy War: no empty post off the Agent's space,
            # so the forced-to-move Spy is lost [FAQ p. 2] (OQ-065).
            "lose_moved_spy",
            # Holy War: an opponent with no unit to lose confirms it
            # (OQ-036 (a), user ruling 2026-09-30).
            "resolve_unit_loss_without_unit",
            # A bank Commander with no choosable Skill is confirmed
            # (OQ-031, OQ-035 (b), user ruling 2026-10-02).
            "resolve_commander_without_skill",
        )
    ]
    for action_id in (
        "acquire_sardaukar_commander",
        "trash_skill_for_strength",
        "choose_skill",
    ):
        templates.extend(
            ActionTemplate(
                action_id=action_id,
                arguments=(("skill_id", skill.skill_id),),
            )
            for skill in SKILLS
        )
    for action_id in ("deploy_commanders", "withdraw_commanders"):
        templates.extend(
            ActionTemplate(action_id=action_id, arguments=(("count", count),))
            for count in range(1, MAX_COMMANDER_DEPLOYMENT + 1)
        )
    # Commanders are troops for retreats and garrison deployments
    # [Bloodlines p. 4]: the ``commanders`` share of a unit count. A Commander
    # is its own component, not one of the twelve troops, so a seat's units in
    # the Conflict reach MAX_DEPLOYMENT_COUNT + MAX_COMMANDER_DEPLOYMENT and
    # Tactical Option's unbounded "retreat any number" offers every one of
    # them; stopping the count at the troop total left the engine able to
    # offer a retreat this codec could not encode (2026-09-10).
    templates.extend(
        ActionTemplate(
            action_id="retreat_intrigue_troops",
            arguments=(("commanders", share), ("count", count)),
        )
        for count in range(1, MAX_DEPLOYMENT_COUNT + MAX_COMMANDER_DEPLOYMENT + 1)
        for share in range(
            max(1, count - MAX_DEPLOYMENT_COUNT),
            min(count, MAX_COMMANDER_DEPLOYMENT) + 1,
        )
    )
    templates.extend(
        ActionTemplate(
            action_id="deploy_intrigue_troops",
            arguments=(("commanders", share), ("count", count)),
        )
        for count in range(1, MAX_INTRIGUE_DEPLOYMENT + 1)
        for share in range(1, count + 1)
    )
    templates.extend(
        ActionTemplate(
            action_id="retreat_two_troops_for_reveal",
            arguments=(("commanders", share),),
        )
        for share in (1, 2)
    )
    templates.append(ActionTemplate(action_id="retreat_leader_commander"))
    # Disruption Tactics: one enemy unit (troop or Commander) to retreat.
    for seat in range(4):
        templates.append(
            ActionTemplate(
                action_id="retreat_opponent_troop", arguments=(("player", seat),)
            )
        )
        templates.append(
            ActionTemplate(
                action_id="retreat_opponent_troop",
                arguments=(("commanders", 1), ("player", seat)),
            )
        )
    templates.append(ActionTemplate(action_id="decline_command_acquisition"))
    templates.append(ActionTemplate(action_id="gain_reveal_persuasion"))
    templates.append(ActionTemplate(action_id="take_reveal_contract"))
    templates.extend(
        ActionTemplate(action_id=action_id)
        for action_id in (
            # Bloodlines Leaders: Duncan Idaho, Chani, Liet Kynes, Esmar Tuek.
            "deploy_leader_agent",
            "recall_conflict_agent_for_imperial_privilege",
            # Steersman's Recall Agent icon and Twisted Mentat may likewise
            # recall an Into the Fray Agent from the Conflict (OQ-068).
            "recall_conflict_agent_for_agent_card",
            "pay_leader_signet_water",
            "decline_optional_trash",
            "take_tuek_sietch_spice",
            "take_tuek_sietch_card",
            "place_leader_bonus_spice",
            # Twisted Intrigue (Piter De Vries).
            "put_back_top_card",
            "discard_top_card",
            "draw_top_card_for_solari",
        )
    )
    templates.extend(
        ActionTemplate(action_id="lose_intrigue_troop", arguments=arguments)
        for zone in ("garrison", "conflict")
        for arguments in ((("zone", zone),), (("commanders", 1), ("zone", zone)))
    )
    # Steersman Y'rkoon: the four Navigation picks and the played option.
    templates.extend(
        ActionTemplate(
            action_id="place_navigation_card", arguments=(("card_id", card_id),)
        )
        for card_id in navigation_card_instance_ids()
    )
    templates.extend(
        ActionTemplate(action_id="play_navigation", arguments=(("option", option),))
        for option in range(2)
    )
    # An arrow cost is optional [Main p. 20]: Navigation card 10 may be
    # declined (spent without effect).
    templates.append(ActionTemplate(action_id="decline_navigation"))
    twisted = twisted_intrigue_instance_ids()
    all_intrigue = (
        *intrigue_deck_instance_ids(
            config.choam_module,
            bloodlines=True,
            tech_module=config.tech_module,
            # Immortality Intrigue can be given or trashed too (soak seed
            # 5038 found Gruesome Sacrifice missing from give_intrigue_card).
            immortality=config.immortality,
        ),
        *twisted,
    )
    templates.extend(
        ActionTemplate(
            action_id="trash_intrigue_hand_card", arguments=(("card_id", card_id),)
        )
        for card_id in all_intrigue
    )
    if config.choam_module:
        # The Bloodlines Immediate Contract trashes a hand Intrigue card.
        templates.extend(
            ActionTemplate(
                action_id="trash_intrigue_for_contract",
                arguments=(("card_id", card_id),),
            )
            for card_id in all_intrigue
        )
        # Sardaukar II and the High Council token's Recall Agent reward may
        # likewise recall an Into the Fray Agent from the Conflict (OQ-068).
        templates.append(
            ActionTemplate(action_id="recall_conflict_agent_for_contract")
        )
        # A market whose only token is the Immediate, with no Intrigue card
        # to trash: the owner confirms its Contract icons are held (OQ-059).
        templates.append(ActionTemplate(action_id="hold_contract_icons"))
        templates.append(
            ActionTemplate(action_id="resolve_contract_icons_without_contract")
        )
    templates.extend(
        ActionTemplate(
            action_id="give_intrigue_card",
            arguments=(("card_id", card_id), ("player", seat)),
        )
        for card_id in all_intrigue
        for seat in range(config.players)
    )
    templates.extend(
        ActionTemplate(
            action_id="take_leader_bonus_spice", arguments=(("space_id", space_id),)
        )
        for space_id in MAKER_SPACE_IDS
    )
    templates.extend(_trash_templates(config, "trash_optional_card"))
    # Fedaykin Maneuver retreats any number, Commanders included: ``count``
    # is troops plus Commanders (Commanders are troops [Bloodlines p. 4]), so
    # it reaches MAX_DEPLOYMENT_COUNT + MAX_COMMANDER_DEPLOYMENT with the
    # Commander share bounded like ``retreat_intrigue_troops`` above. v105:
    # the share branch stopped at MAX_DEPLOYMENT_COUNT, so a 12-troop Conflict
    # with one Commander offered ``count 13`` that had no template (found by a
    # trained policy in greedy play, 2026-09-18).
    templates.extend(
        ActionTemplate(action_id="retreat_leader_troops", arguments=(("count", count),))
        for count in range(1, MAX_DEPLOYMENT_COUNT + 1)
    )
    templates.extend(
        ActionTemplate(
            action_id="retreat_leader_troops",
            arguments=(("commanders", share), ("count", count)),
        )
        for count in range(1, MAX_DEPLOYMENT_COUNT + MAX_COMMANDER_DEPLOYMENT + 1)
        for share in range(
            max(1, count - MAX_DEPLOYMENT_COUNT),
            min(count, MAX_COMMANDER_DEPLOYMENT) + 1,
        )
    )
    # The loser picks the zone and the unit kind (OQ-036); ``commanders``
    # marks a Sardaukar Commander like the retreat argument does.
    templates.extend(
        ActionTemplate(action_id="lose_unit", arguments=arguments)
        for zone in ("garrison", "conflict")
        for arguments in (
            (("zone", zone),),
            (("commanders", 1), ("zone", zone)),
        )
    )
    # "Gain one Influence of your choice" as a Reveal choice (Pointing the Way).
    templates.extend(
        ActionTemplate(
            action_id="gain_reveal_influence",
            arguments=(("faction", faction.value),),
        )
        for faction in Faction
    )
    return tuple(templates)


def _scouts_templates(config: RulesetConfig) -> tuple[ActionTemplate, ...]:
    """Arrakeen Scouts actions (docs/rules/arrakeen-scouts.md), all here so
    the other catalogs never grow with them (design 4.9)."""

    templates: list[ActionTemplate] = [
        # Friends Everywhere: take any Faction's Influence 4 bonus.
        *(
            ActionTemplate(
                action_id="choose_four_bonus", arguments=(("faction", faction.value),)
            )
            for faction in Faction
        ),
        # Subcommittees: open the list during the turn (OQ-076), join one,
        # or decline the chance.
        ActionTemplate(action_id="choose_subcommittee"),
        ActionTemplate(action_id="decline_subcommittee"),
        *(
            ActionTemplate(
                action_id="join_subcommittee",
                arguments=(("subcommittee_id", entry.subcommittee_id),),
            )
            for entry in subcommittees_for(
                scouts_pool(immortality=config.immortality),
                choam=config.choam_module,
            )
        ),
        # A seat's line: the choices of the Scouts effect frame.
        *_trash_templates(config, "scouts_discard"),
        *_trash_templates(config, "scouts_trash_card"),
        *(
            ActionTemplate(
                action_id="scouts_trash_intrigue", arguments=(("card_id", card_id),)
            )
            for card_id in _held_intrigue_instance_ids(config)
        ),
        *(
            ActionTemplate(
                action_id="scouts_recall_spy", arguments=(("post_id", post.post_id),)
            )
            for post in OBSERVATION_POSTS
        ),
        *(
            ActionTemplate(
                action_id="scouts_choose_faction",
                arguments=(("faction", faction.value),),
            )
            for faction in Faction
        ),
        *(
            ActionTemplate(
                action_id="scouts_recall_agent",
                arguments=(("space_id", space_id),),
            )
            for space_id in (
                *(space.space_id for space in catalog_spaces(config)),
                "conflict",  # an Into the Fray Agent (OQ-075 (D))
            )
        ),
        # Immortality: specimens returned to the supply first (0 = none).
        *(
            ActionTemplate(
                action_id="scouts_return_specimens", arguments=(("count", n),)
            )
            for n in range(MAX_SPECIMEN_TOP_UP + 1 if config.immortality else 0)
        ),
        # Influence losses (Crackdown and the like, Political Equilibrium),
        # with the Alliance recipient when several opponents tie.
        *(
            ActionTemplate(
                action_id="scouts_lose_influence",
                arguments=(("faction", faction.value),),
            )
            for faction in Faction
        ),
        *(
            ActionTemplate(
                action_id="scouts_lose_influence_to",
                arguments=(
                    ("alliance_recipient", recipient),
                    ("faction", faction.value),
                ),
            )
            for recipient in range(config.players)
            for faction in Faction
        ),
        # The trash icon (Oversight, Water Discipline) opens the generic
        # optional-trash frame, which only the Bloodlines and Immortality
        # catalogs hold otherwise; the line's later rewards may resolve
        # before it (OQ-100).
        ActionTemplate(action_id="scouts_rewards_first"),
        *(
            (
                ActionTemplate(action_id="decline_optional_trash"),
                *_trash_templates(config, "trash_optional_card"),
            )
            if not config.bloodlines and not config.immortality
            else ()
        ),
        # Missions: take part (CHOAM Escort: recruit or a face-up Contract of
        # the seat's) or pass, and collect on a visit (Imperial Reserve's
        # pick of spice or Solari).
        ActionTemplate(action_id="scouts_decline_mission"),
        *(
            ActionTemplate(action_id="scouts_join_mission", arguments=(("target", t),))
            for t in (
                "",
                *(
                    ("recruit", *contract_instance_ids(bloodlines=config.bloodlines))
                    if config.choam_module
                    else ()
                ),
            )
        ),
        *(
            ActionTemplate(
                action_id="scouts_collect_mission", arguments=(("choice", choice),)
            )
            for choice in ("", "solari", "spice")
        ),
        # Desert Riding: Hagga Basin's Maker Hooks token instead of its spice.
        ActionTemplate(
            action_id="take_desert_riding_hooks",
            arguments=(("space_id", "hagga_basin"),),
        ),
        # A secret pick among an event's four lines.
        *(
            ActionTemplate(action_id="scouts_secret_pick", arguments=(("pick", i),))
            for i in range(4)
        ),
        # Auctions: a sealed bid and its confirmation, Mercenaries' retreat,
        # Critical Moment's call (0 a pass) and the purchase by card slot.
        ActionTemplate(action_id="confirm_scouts_bid"),
        *(
            ActionTemplate(action_id="scouts_bid", arguments=(("count", n),))
            for n in range(MAX_AUCTION_BID + 1)
        ),
        *(
            ActionTemplate(action_id="scouts_retreat", arguments=(("count", n),))
            for n in range(MAX_MERCENARIES_BID + 1)
        ),
        *(
            ActionTemplate(action_id="scouts_call", arguments=(("count", n),))
            for n in range(MAX_AUCTION_BID + 1)
        ),
        ActionTemplate(action_id="scouts_decline_card"),
        *(
            ActionTemplate(action_id="scouts_take_card", arguments=(("slot", slot),))
            for slot in range(max(auction.revealed_cards for auction in AUCTIONS))
        ),
        # One seat's turn-order pick of an event's or sale's line, or a pass.
        ActionTemplate(action_id="scouts_pass"),
        *(
            ActionTemplate(action_id="scouts_choose_option", arguments=(("option", i),))
            for i in range(_MAX_SCOUTS_OPTIONS)
        ),
    ]
    return tuple(templates)


# The most lines any Scouts event or sale offers, counting a revealed secret
# pick's line, which is taken or left by its index (Covert Operation's
# third line).
_MAX_SCOUTS_OPTIONS = max(
    len(options)
    for options in (
        *(event.options for event in EVENTS),
        *(event.secret_choices for event in EVENTS),
        *(sale.options for sale in SALES),
    )
)


def _held_intrigue_instance_ids(config: RulesetConfig) -> tuple[str, ...]:
    """Every Intrigue card a seat can hold in this ruleset."""

    held = intrigue_deck_instance_ids(
        config.choam_module,
        bloodlines=config.bloodlines,
        tech_module=config.tech_module,
        immortality=config.immortality,
    )
    if config.bloodlines:
        # Piter De Vries' Twisted Intrigue cards are held once dealt.
        held = (*held, *twisted_intrigue_instance_ids())
    return held


def _immortality_templates(config: RulesetConfig) -> tuple[ActionTemplate, ...]:
    """Bene Tleilax board choices [Immortality pp. 6-8, 12] (``rules.immortality``)."""

    templates: list[ActionTemplate] = [
        ActionTemplate(action_id=action_id)
        for action_id in (
            "decline_research_bonus",
            # Harvest Cells gained as a Combat reward, played before the
            # cleanup (OQ-057).
            "decline_conflict_end_intrigue",
            "pay_research_bonus",
            "return_specimen",
            "use_family_atomics",
            "generate_reveal_specimens",
            "advance_reveal_tleilaxu",
            "advance_reveal_research",
            "pay_agent_card_specimen",
            # Tleilaxu Surgeon, Dissecting Kit, High Priority Travel.
            "pay_agent_card_two_specimens",
            "trash_grafted_card_for_specimen",
            "take_agent_card_combat_icon",
            # Scientific Breakthrough, Slig Farmer.
            "trash_agent_card_self_for_vp",
            "pay_agent_card_five_solari_for_tleilaxu",
            # For Humanity and Tleilaxu Surgeon Reveal choices (Shadout
            # Mapes' troop move is in every catalog, for Unswerving Loyalty).
            "decline_reveal_influence_loss",
            "decline_reveal_troop_sacrifice",
        )
    ]
    templates.extend(
        ActionTemplate(
            action_id="lose_reveal_troops_for_specimens", arguments=(("zones", zones),)
        )
        for zones in ("garrison,garrison", "garrison,conflict", "conflict,conflict")
    )
    # Piter's troop cost, Stitched Horror's picks, Beguiling Pheromones'
    # grafted-card trash.
    templates.extend(
        ActionTemplate(action_id="lose_agent_card_troop", arguments=(("zone", zone),))
        for zone in ("garrison", "conflict")
    )
    templates.extend(
        ActionTemplate(
            action_id="choose_agent_card_reward", arguments=(("reward", reward),)
        )
        for reward in ("water", "troop", "trash", "tleilaxu")
    )
    templates.extend(
        ActionTemplate(
            action_id="trash_grafted_card_for_influence",
            arguments=(("card_id", card_id),),
        )
        for card_id in _personal_card_instance_ids(config)
    )
    templates.extend(
        ActionTemplate(
            action_id="lose_reveal_influence_for_vp",
            arguments=(("faction", faction.value),),
        )
        for faction in Faction
    )
    templates.extend(
        ActionTemplate(
            action_id="lose_reveal_influence_for_vp",
            arguments=(("alliance_recipient", recipient), ("faction", faction.value)),
        )
        for faction in Faction
        for recipient in range(config.players)
    )
    # Imperium Ceremony's keep-one choice over any Intrigue card.
    peekable = intrigue_deck_instance_ids(
        config.choam_module,
        bloodlines=config.bloodlines,
        tech_module=config.tech_module,
        immortality=True,
    )
    if config.bloodlines:
        peekable = (*peekable, *twisted_intrigue_instance_ids())
    templates.extend(
        ActionTemplate(
            action_id="keep_peeked_intrigue", arguments=(("instance_id", instance_id),)
        )
        for instance_id in peekable
    )
    # Tleilaxu Master's free acquisition of a card costing 6 or less.
    templates.extend(
        ActionTemplate(
            action_id="acquire_reserve_by_card",
            arguments=(("card_id", stack.card.card_id),),
        )
        for stack in RESERVE_STACKS
    )
    templates.extend(
        ActionTemplate(
            action_id="acquire_imperium_by_card",
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in imperium_deck_instance_ids(
            config.choam_module,
            config.promo_cards,
            bloodlines=config.bloodlines,
            tech_module=config.tech_module,
            immortality=True,
        )
    )
    templates.extend(
        ActionTemplate(
            action_id="choose_research_space", arguments=(("space_id", space_id),)
        )
        for space_id in RESEARCH_SPACES_BY_ID
        if space_id != RESEARCH_START_ID
    )
    templates.extend(
        ActionTemplate(
            action_id="choose_research_influence",
            arguments=(("faction", faction.value),),
        )
        for faction in Faction
    )
    # v106: c7r3's arrow cost trashes an Intrigue card from hand ("Trash an
    # Intrigue card" [Immortality p. 16]); the peekable set above is every
    # Intrigue card a seat of this ruleset can hold.
    templates.extend(
        ActionTemplate(
            action_id="trash_intrigue_for_research_bonus",
            arguments=(("card_id", instance_id),),
        )
        for instance_id in peekable
    )
    if not config.bloodlines:
        # The trash-and-specimen research spaces open the generic optional
        # trash frame, and Gruesome Sacrifice's troop loss the unit-loss
        # choice; Bloodlines catalogs already hold both.
        templates.append(ActionTemplate(action_id="decline_optional_trash"))
        templates.extend(_trash_templates(config, "trash_optional_card"))
        templates.extend(
            ActionTemplate(action_id="lose_intrigue_troop", arguments=(("zone", zone),))
            for zone in ("garrison", "conflict")
        )
    # The Tleilaxu Row: each deck card to the discard pile or, past the
    # first genetic marker, on top of the deck; Reclaimed Forces' two
    # effects [Immortality pp. 6, 9].
    for instance_id in tleilaxu_deck_instance_ids(config.promo_cards):
        templates.append(
            ActionTemplate(
                action_id="acquire_tleilaxu", arguments=(("instance_id", instance_id),)
            )
        )
        templates.append(
            ActionTemplate(
                action_id="acquire_tleilaxu",
                arguments=(("instance_id", instance_id), ("to_deck_top", True)),
            )
        )
    templates.extend(
        ActionTemplate(
            action_id="acquire_reclaimed_forces", arguments=(("choice", choice),)
        )
        for choice in ("troops", "tleilaxu")
    )
    # Graft [Immortality p. 10]: the partner choice over every personal
    # card, the box switch, and Twisted Mentat's recall decline.
    templates.extend(
        ActionTemplate(
            action_id="choose_graft_partner", arguments=(("card_id", card_id),)
        )
        for card_id in _personal_card_instance_ids(config)
    )
    templates.append(ActionTemplate(action_id="switch_graft_card"))
    templates.append(ActionTemplate(action_id="decline_agent_card_recall"))
    # Harvest Cells' offer: a Row card (to the discard pile or the deck
    # top) or the decline.
    for instance_id in tleilaxu_deck_instance_ids(config.promo_cards):
        templates.append(
            ActionTemplate(
                action_id="acquire_intrigue_tleilaxu",
                arguments=(("instance_id", instance_id),),
            )
        )
        templates.append(
            ActionTemplate(
                action_id="acquire_intrigue_tleilaxu",
                arguments=(("instance_id", instance_id), ("to_deck_top", True)),
            )
        )
    templates.append(ActionTemplate(action_id="decline_intrigue_tleilaxu"))
    templates.extend(
        ActionTemplate(
            action_id="play_conflict_end_intrigue",
            arguments=(("card_id", instance_id),),
        )
        for instance_id in intrigue_deck_instance_ids(
            config.choam_module,
            bloodlines=config.bloodlines,
            tech_module=config.tech_module,
            immortality=True,
        )
        if any(
            isinstance(option.trigger, OnTroopsLostAtConflictEnd)
            for option in intrigue_card_for_instance(instance_id).options
        )
    )
    return tuple(templates)


def _tech_templates(config: RulesetConfig) -> tuple[ActionTemplate, ...]:
    """Tech Module choices [Bloodlines pp. 6-7] (``rules.tech``)."""

    templates: list[ActionTemplate] = [ActionTemplate(action_id="decline_tech")]
    for tile in TECH_TILES:
        base: tuple[tuple[str, ActionValue], ...] = (("tech_id", tile.tech_id),)
        variants: list[tuple[tuple[str, ActionValue], ...]] = []
        if tile.acquire_requires_spy_trash:
            # Advanced Data Analysis: the Spy trashed from the board.
            variants.extend(
                (("post_id", post.post_id), *base) for post in OBSERVATION_POSTS
            )
        else:
            variants.append(base)
        templates.extend(
            ActionTemplate(action_id="acquire_tech", arguments=arguments)
            for arguments in variants
        )
        for effect in tile.acquire_effect_keys:
            effect_base = (("effect", effect), *base)
            if effect == "influence":
                rewards = tuple(
                    tuple(sorted((*effect_base, ("faction", faction.value))))
                    for faction in Faction
                )
            elif effect == "intrigue_or_card":
                rewards = tuple(
                    tuple(sorted((*effect_base, ("choice", choice))))
                    for choice in ("card", "intrigue")
                )
            elif effect == "shield_wall":
                rewards = (
                    effect_base,
                    tuple(sorted((*effect_base, ("destroy_shield_wall", True)))),
                )
            else:
                rewards = (effect_base,)
            templates.extend(
                ActionTemplate(action_id="resolve_tech_acquire_effect", arguments=args)
                for args in rewards
            )
        if tile.flips:
            templates.append(ActionTemplate(action_id="flip_tech", arguments=base))
    # Forbidden Weapons' Reveal choice: swords with an Influence loss (and
    # the Alliance recipient when several opponents tie), or the trash.
    templates.append(ActionTemplate(action_id="choose_tech_strength"))
    templates.extend(
        ActionTemplate(
            action_id="choose_tech_strength", arguments=(("faction", faction.value),)
        )
        for faction in Faction
    )
    templates.extend(
        ActionTemplate(
            action_id="choose_tech_strength",
            arguments=(("alliance_recipient", seat), ("faction", faction.value)),
        )
        for faction in Faction
        for seat in range(config.players)
    )
    templates.append(ActionTemplate(action_id="choose_tech_trash"))
    # Panopticon's Reveal-turn Spy, taken in the owner's order.
    templates.append(ActionTemplate(action_id="place_tech_spy"))
    # Plasteel Blades' optional trash for an extra Skill.
    templates.append(ActionTemplate(action_id="decline_skill"))
    # Kota Odax of Ix: the Secret Project pick and Reverse Engineering.
    templates.extend(
        ActionTemplate(action_id=action_id, arguments=(("tech_id", tile.tech_id),))
        for action_id in ("choose_secret_project", "trash_leader_tech")
        for tile in TECH_TILES
    )
    templates.append(ActionTemplate(action_id="gain_leader_signet_spice"))
    return tuple(templates)


def _reveal_resource_templates() -> tuple[ActionTemplate, ...]:
    """One ``gain_reveal_resources`` per distinct printed Reveal resource bundle.

    Reveal resource gains are the owner's own actions (OQ-045, codec v93);
    a bundle is the solari/spice/water of one printed Reveal effect, a
    Skill's Reveal bonus, or Delivery Bay's Command Solari.
    """

    bundles: set[tuple[int, int, int]] = set()
    cards: tuple[
        StartingCardEntry | ReserveStackDefinition | ImperiumCardEntry, ...
    ] = (
        *STARTING_DECK,
        CONTROL_THE_SPICE,
        *RESERVE_STACKS,
        *imperium_cards_for_choam(
            True, True, bloodlines=True, tech_module=True, immortality=True
        ),
    )
    for card in cards:
        for effect in card.reveal_effects:
            if effect.solari or effect.spice or effect.water:
                bundles.add((effect.solari, effect.spice, effect.water))
    for skill in SKILLS:
        if skill.reveal_spice:
            bundles.add((0, skill.reveal_spice, 0))
    bundles.add((2, 0, 0))  # Delivery Bay
    return (
        *(
            ActionTemplate(
                action_id="gain_reveal_resources",
                arguments=(("solari", solari), ("spice", spice), ("water", water)),
            )
            for solari, spice, water in sorted(bundles)
        ),
        # Fixed-Faction Reveal Influence, one per Faction (codec v94).
        *(
            ActionTemplate(
                action_id="gain_reveal_faction_influence",
                arguments=(("faction", faction.value),),
            )
            for faction in Faction
        ),
    )


def _agent_turn_templates(config: RulesetConfig) -> tuple[ActionTemplate, ...]:
    # Emperor's Invitation (Bloodlines) can give any card the Emperor icon
    # for a turn, so the option's catalogs also hold every card's Emperor
    # placements.
    granted: tuple[AgentIcon, ...] = (AgentIcon.EMPEROR,) if config.bloodlines else ()
    # Gaius Helen Mohiam gives every card the Spy icon, Urgent Shigawire
    # gives the next Bene Gesserit card "all Agent icons" and Delivery
    # Logistics borrows its Contracts' icons, so the option's catalogs hold
    # every card's placement on every space.
    every_icon = tuple(AgentIcon) if config.bloodlines else ()
    if config.bloodlines:
        granted = every_icon
    templates: list[ActionTemplate] = []
    for starting_card in _starting_entries(config):
        templates.extend(
            _agent_turn_templates_for_card(
                "starter",
                starting_card,
                granted,
                catalog_spaces(config),
                space_discounts=config.tech_module,
                graft=config.immortality,
            )
        )
    for reserve_card in RESERVE_STACKS:
        templates.extend(
            _agent_turn_templates_for_card(
                "reserve",
                reserve_card,
                granted,
                catalog_spaces(config),
                space_discounts=config.tech_module,
                graft=config.immortality,
            )
        )
    for imperium_card in imperium_cards_for_choam(
        config.choam_module,
        config.promo_cards,
        bloodlines=config.bloodlines,
        tech_module=config.tech_module,
        immortality=config.immortality,
    ):
        if imperium_card.play_data_complete:
            card_granted = (
                every_icon
                if config.bloodlines
                and (
                    Faction.BENE_GESSERIT in imperium_card.factions
                    or imperium_card.agent_icons_from_contracts
                )
                else granted
            )
            templates.extend(
                _agent_turn_templates_for_card(
                    "imperium",
                    imperium_card,
                    card_granted,
                    catalog_spaces(config),
                    space_discounts=config.tech_module,
                    graft=config.immortality,
                )
            )
    if config.immortality:
        for tleilaxu_card in tleilaxu_cards_for(config.promo_cards):
            templates.extend(
                _agent_turn_templates_for_card(
                    "tleilaxu",
                    tleilaxu_card,
                    granted,
                    catalog_spaces(config),
                    space_discounts=config.tech_module,
                    graft=config.immortality,
                )
            )
    return tuple(templates)


def catalog_spaces(config: RulesetConfig) -> tuple[BoardSpace, ...]:
    """Board spaces a catalog holds: Leader-only spaces need Bloodlines."""

    return tuple(
        space
        for space in BOARD_SPACES
        if space.required_leader_id is None or config.bloodlines
    )


def _agent_turn_templates_for_card(
    prefix: str,
    card: StartingCardEntry | ReserveStackDefinition | ImperiumCardEntry,
    granted_icons: tuple[AgentIcon, ...] = (),
    spaces: tuple[BoardSpace, ...] = BOARD_SPACES,
    *,
    space_discounts: bool = False,
    graft: bool = False,
) -> tuple[ActionTemplate, ...]:
    templates: list[ActionTemplate] = []
    # Immortality: a Graft card is only ever played grafted; any other card
    # may also be played grafted (the partner is chosen next), and Blank
    # Slate grafted has the four Faction icons [card face].
    if not graft:
        graft_variants: tuple[bool, ...] = (False,)
    elif card_is_graft(card):
        graft_variants = (True,)
    else:
        graft_variants = (False, True)
    grafted_icons: tuple[AgentIcon, ...] = (
        (
            AgentIcon.EMPEROR,
            AgentIcon.SPACING_GUILD,
            AgentIcon.BENE_GESSERIT,
            AgentIcon.FREMEN,
        )
        if card.card.card_id == "blank_slate"
        else ()
    )
    for copy in range(card.copies):
        card_id = f"{prefix}:{card.card.card_id}:{copy}"
        for space in spaces:
            for grafted in graft_variants:
                templates.extend(
                    _placement_templates(
                        card,
                        card_id,
                        space,
                        (*granted_icons, *(grafted_icons if grafted else ())),
                        space_discounts=space_discounts,
                        grafted=grafted,
                    )
                )
    return tuple(templates)


def _placement_templates(
    card: StartingCardEntry | ReserveStackDefinition | ImperiumCardEntry,
    card_id: str,
    space: BoardSpace,
    granted_icons: tuple[AgentIcon, ...],
    *,
    space_discounts: bool,
    grafted: bool,
) -> tuple[ActionTemplate, ...]:
    templates: list[ActionTemplate] = []
    if (
        space.agent_icon not in card.agent_icons
        and space.agent_icon not in granted_icons
        and AgentIcon.SPY not in card.agent_icons
        # Usurp reaches any space on a Row card's icons [card face].
        and not (grafted and card_is_usurp(card))
    ):
        return ()
    cost_options: tuple[int | None, ...] = (
        tuple(range(len(space.cost_options)))
        if space.dynamic_cost is None and len(space.cost_options) > 1
        else (None,)
    )
    # Navigation Chamber (Tech Module): one spice or one Solari off.
    discounts: tuple[str | None, ...] = (None,)
    if space_discounts:
        discounts = (
            None,
            *(
                kind
                for kind in ("spice", "solari")
                if any(
                    getattr(option, kind) > 0 for option in space.cost_options
                )
            ),
        )
    infiltration_post_ids: tuple[str | None, ...] = (
        None,
        *(
            post.post_id
            for post in OBSERVATION_POSTS
            if space.space_id in post.connected_space_ids
        ),
    )
    for cost_option in cost_options:
        for discount in discounts:
            for infiltrate_post_id in infiltration_post_ids:
                arguments: list[tuple[str, ActionValue]] = [
                    ("card_id", card_id)
                ]
                if cost_option is not None:
                    arguments.append(("cost_option", cost_option))
                if discount is not None:
                    arguments.append(("discount", discount))
                if grafted:
                    arguments.append(("graft", True))
                if infiltrate_post_id is not None:
                    arguments.append(
                        ("infiltrate_post_id", infiltrate_post_id)
                    )
                arguments.append(("space_id", space.space_id))
                templates.append(
                    ActionTemplate(
                        action_id="agent_turn",
                        arguments=tuple(arguments),
                    )
                )
    return tuple(templates)


def _endgame_wild_templates(
    config: RulesetConfig,
) -> tuple[ActionTemplate, ...]:
    battle_cards = (
        *(
            (conflict.card.card_id, conflict.battle_icon)
            for conflict in CONFLICTS
            if (config.bloodlines or not conflict.bloodlines_only)
            and (config.epic_game or not conflict.epic_only)
        ),
        *(
            (objective.objective_id, objective.battle_icon)
            for objective in objectives_for_players(config.players)
        ),
    )
    wild_card_ids = tuple(
        card_id for card_id, icon in battle_cards if icon is BattleIcon.WILD
    )
    matching_card_ids = tuple(
        card_id for card_id, icon in battle_cards if icon not in (None, BattleIcon.WILD)
    )
    templates = [
        ActionTemplate(
            action_id="match_endgame_wild_icon",
            arguments=(
                ("matching_card_id", matching_card_id),
                ("wild_card_id", wild_card_id),
            ),
        )
        for wild_card_id in wild_card_ids
        for matching_card_id in matching_card_ids
    ]
    # Wild-with-wild pairs [Bloodlines p. 5], once each in sorted order.
    sorted_wild = sorted(wild_card_ids)
    templates.extend(
        ActionTemplate(
            action_id="match_endgame_wild_icon",
            arguments=(("matching_card_id", second), ("wild_card_id", first)),
        )
        for index, first in enumerate(sorted_wild)
        for second in sorted_wild[index + 1 :]
    )
    return tuple(templates)


def _trash_templates(
    config: RulesetConfig,
    action_id: str,
) -> tuple[ActionTemplate, ...]:
    return tuple(
        ActionTemplate(
            action_id=action_id,
            arguments=(("card_id", card_id),),
        )
        for card_id in _personal_card_instance_ids(config)
    )


def _starting_entries(config: RulesetConfig) -> tuple[StartingCardEntry, ...]:
    """Every starting card a seat owns: its deck and, in Epic Game Mode with
    Immortality, the Control the Spice that starts in the discard pile."""

    return (
        *starting_deck_entries(
            immortality=config.immortality, epic_game=config.epic_game
        ),
        *starting_discard_entries(
            immortality=config.immortality, epic_game=config.epic_game
        ),
    )


def _personal_card_instance_ids(config: RulesetConfig) -> tuple[str, ...]:
    card_ids = [
        f"starter:{card.card.card_id}:{copy}"
        for card in _starting_entries(config)
        for copy in range(card.copies)
    ]
    card_ids.extend(
        imperium_deck_instance_ids(
            config.choam_module,
            config.promo_cards,
            bloodlines=config.bloodlines,
            tech_module=config.tech_module,
            immortality=config.immortality,
        )
    )
    card_ids.extend(
        f"reserve:{stack.card.card_id}:{copy}"
        for stack in RESERVE_STACKS
        for copy in range(stack.copies)
    )
    if config.immortality:
        card_ids.extend(tleilaxu_deck_instance_ids(config.promo_cards))
    return tuple(card_ids)


def _normalize_arguments(
    arguments: tuple[tuple[str, ActionValue], ...],
    actor: int,
) -> tuple[tuple[str, ActionValue], ...]:
    prefix = f"player:{actor}:starter:"
    return tuple(
        (key, f"starter:{value.removeprefix(prefix)}")
        if isinstance(value, str) and value.startswith(prefix)
        else (key, value)
        for key, value in arguments
    )


def _denormalize_arguments(
    arguments: tuple[tuple[str, ActionValue], ...],
    actor: int,
) -> tuple[tuple[str, ActionValue], ...]:
    return tuple(
        (key, f"player:{actor}:{value}")
        if isinstance(value, str) and value.startswith("starter:")
        else (key, value)
        for key, value in arguments
    )


def _template_sort_key(template: ActionTemplate) -> tuple[str, str]:
    return template.action_id, repr(template.arguments)
