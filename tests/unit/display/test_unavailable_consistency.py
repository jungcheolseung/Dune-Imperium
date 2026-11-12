"""The greyed-out choices never disagree with the engine, and never leak.

``display.unavailable`` shows what a seat's decision offers that it cannot
take now (user request 2026-09-29). Over seeded random games in every
ruleset these tests check, at every decision:

- no greyed-out row is a legal action, and no dimmed card is named by one
  (a disagreement may only ever hide a row, never grey out a legal move);
- every reason is a specific one, never the generic ``NOT_NOW`` fallback,
  in both languages, with no Hangul in the English;
- the rows read nothing hidden from the seat: re-dealing every zone it
  cannot see (``agents.determinize``) gives the same legal list and the
  same rows.

The engine's providers were refactored to expose the block predicates the
rows read (``AcquireBlock``, ``option_unplayable_reason``,
``intrigue_play_block``, ``agent_box_is_waiting``, and on 2026-10-02
``reveal_sandworm_block``, ``imperial_privilege_recall_targets``,
``contract_recall_targets``, ``research_bonus_block``,
``combat_reward_influence_block`` and ``unit_loss_block``; then
``skill_choice_block``, ``agent_card_recall_targets``,
``agent_icon_block`` and ``contract_take_block``).
``test_the_refactored_providers_offer_what_they_did`` pins that refactor
against copies of the providers as they were before it (2026-09-29): a later
rule change to one of them should update or drop the copy on purpose.
``combat_reward_payment_block`` and ``combat_reward_spy_recall_block``
(2026-10-14, a Conflict reward's resource or Spies payment) are pinned by
copies of the providers here too, over the seeded games and a sweep of every
optional arrow (``test_the_conflict_reward_payment_blocks_are_the_old_comparisons``).
``board_effects.maker_sandworm_block`` and ``desert_riding_block``
(2026-10-14, a Maker space's sandworm and Desert Riding token) likewise, over
the seeded games and a sweep of the Maker spaces
(``test_the_maker_space_blocks_are_the_old_conditions``).
``board_effects.sietch_tabr_wall_block`` (2026-10-14, Sietch Tabr's
detonation) likewise (``test_the_sietch_tabr_block_is_the_old_condition``).
``leader_abilities.leader_reveal_block`` (2026-10-14, Lady Amber's and
Feyd-Rautha's Reveal abilities) likewise, over the seeded games and a sweep
(``test_the_leader_reveal_block_is_the_old_condition``).
The Faction pickers of an Intrigue choice, an Agent box and a Reveal
choice, Controlled's paid draw and the capped and Tleilaxu acquisitions
(2026-11-10, ``faction_gain_block``, ``faction_loss_block``,
``influence_gain_block``, ``peek_draw_block``, ``capped_reserve_block``,
``capped_imperium_block``) are pinned by copies of their filters over the
seeded games made poorer and richer
(``test_the_choice_blocks_are_the_old_filters``).
``combat.conflict_end_trigger_block`` (2026-10-09, the Conflict-end
window's Harvest Cells) has no copy here: the window tests of
``tests/unit/rules/test_immortality_intrigue.py`` pin what it offers.
``test_recall_targets_never_grow_while_the_recall_waits`` pins what the
recall confirms (2026-10-02) rely on: a recall's targets never come back
while it waits.
"""

import itertools
import json
import random
import re
from collections.abc import Callable, Iterator
from dataclasses import replace
from functools import partial
from typing import Any, cast

import pytest
from tests.unit.display.test_unavailable import (
    HARVEST_CELLS,
    _conflict_end_window,
    _leader_reveal,
    _maker_visit,
    _play_conflict_end,
    _sietch_tabr_visit,
    reward_window,
)

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import PlacementMemory, apply_whole
from dune_imperium.agents.determinize import determinize
from dune_imperium.agents.engine_order import engine_order_answer
from dune_imperium.config import BaseGame
from dune_imperium.content.bloodlines.sardaukar import skill_for_instance
from dune_imperium.content.core.board import ResourceCost
from dune_imperium.content.core.card_effects import REVEAL_CHOICE_KEYS
from dune_imperium.content.core.effects import (
    AcquireCardUpTo,
    AcquireTech,
    AcquireTleilaxuCard,
    DestroyShieldWall,
    DiscardFromHand,
    EffectSection,
    FlipBattleCard,
    FlipFaceUpConflictCard,
    GainInfluence,
    GiveIntrigueToOpponent,
    IntrigueOption,
    IntrigueTiming,
    LoseInfluence,
    LoseTroops,
    OnConflictWon,
    OnTroopsLostAtConflictEnd,
    PayResources,
    PeekTopCard,
    PlaceSpy,
    RecallSpy,
    RetreatTroops,
    RevealContractsTakeOne,
    TakeContract,
    TakeHighCouncilSeat,
    TrashDiscardPileCard,
    TrashIntrigueCard,
)
from dune_imperium.content.core.icons import Faction
from dune_imperium.content.immortality.board import (
    ResearchBonus,
    genetic_markers_reached,
)
from dune_imperium.content.immortality.tleilaxu import (
    RECLAIMED_FORCES,
    tleilaxu_card_for_instance,
)
from dune_imperium.content.registry.board import BOARD_SPACES_BY_ID
from dune_imperium.content.registry.card_abilities import (
    AGENT_BOX_KEYS,
    acquisition_ability,
    card_agent_box,
)
from dune_imperium.content.registry.contracts import contract_for_instance
from dune_imperium.content.registry.imperium import imperium_card_for_instance
from dune_imperium.content.registry.intrigue import INTRIGUE_CARDS_BY_INSTANCE
from dune_imperium.content.registry.personal_cards import personal_card_for_instance
from dune_imperium.content.registry.reserve import RESERVE_STACKS_BY_ID
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.board import OBSERVATION_POSTS
from dune_imperium.content.uprising.leaders import FEYD_TRACK_BY_ID, FeydTrackReward
from dune_imperium.content.uprising.reveal_choice_abilities import (
    reveal_choice_ability,
)
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.player import Influence, PlayerState, Resources
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.display import unavailable
from dune_imperium.display.unavailable import NOT_NOW_CODE, unavailable_choices
from dune_imperium.rules import (
    UprisingRulesEngine,
    agent_effect_frame,
    agent_turn,
    leader_abilities,
    tech,
)
from dune_imperium.rules.ability_executor import (
    acquires_to_hand,
    current_piece,
    piece_blocked_rows,
    piece_rows,
)
from dune_imperium.rules.acquisition import (
    acquirable_imperium_instance_ids,
    acquirable_reserve_card_ids,
    agent_card_acquisition_block,
    capped_imperium_candidates,
    capped_reserve_block,
    deck_top_offered,
    legal_imperium_acquisitions,
    legal_manipulated_acquisitions,
    legal_reserve_acquisitions,
    reserve_cost,
)
from dune_imperium.rules.action_shapes import Source, Target, Verb, template_id
from dune_imperium.rules.agent_box_abilities import (
    box_ability,
    either_box,
    either_choice_block,
    either_rows,
)
from dune_imperium.rules.agent_effect_frame import agent_box_is_waiting
from dune_imperium.rules.agent_effects import (
    AGENT_ICON_CARDS,
    AGENT_ICON_INTRIGUE,
    AGENT_ICON_RECALL,
    AGENT_ICON_SOLARI,
    AGENT_ICON_SPICE,
    AGENT_ICON_TROOPS,
    AGENT_ICON_WATER,
    AUTOMATIC_AGENT_ICONS,
    agent_card_cost_block,
    agent_card_effect_is_unavailable,
    agent_card_trash_block,
    agent_icon_condition_holds,
    box_has_optional_icon,
    box_in_progress,
    box_is_optional,
    box_refusal_needed,
    legal_agent_card_boost_actions,
    legal_agent_card_icon_actions,
    legal_agent_card_icon_choice_actions,
    legal_agent_card_influence_actions,
    legal_agent_card_recall_actions,
    legal_agent_card_trash_actions,
    legal_opponent_card_discard_actions,
)
from dune_imperium.rules.agent_turn import placement_cost_block, space_option_blocks
from dune_imperium.rules.board_effects import (
    BOARD_ICON_IMPERIAL_PRIVILEGE,
    BOARD_ICON_IMPERIAL_PRIVILEGE_INTRIGUE,
    BOARD_ICON_MAKER,
    BOARD_ICON_SIETCH_TABR,
    desert_riding_block,
    desert_riding_offered_at,
    desert_tactics_block,
    imperial_privilege_recall_targets,
    imperial_privilege_trade_block,
    legal_board_effect_actions,
    legal_desert_tactics_actions,
    legal_imperial_privilege_actions,
    legal_maker_space_actions,
    legal_sietch_tabr_actions,
    maker_sandworm_block,
    sietch_tabr_wall_block,
)
from dune_imperium.rules.card_bonds import counted_in_play, has_faction_bond
from dune_imperium.rules.combat import (
    combat_reward_payment_block,
    combat_reward_spy_recall_block,
    legal_combat_reward_influence_actions,
    legal_combat_reward_optional_payment_actions,
    legal_combat_reward_spy_actions,
    legal_combat_reward_spy_recall_actions,
    legal_distinct_combat_reward_influence_actions,
)
from dune_imperium.rules.contract_tiles import contract_reveal_is_possible
from dune_imperium.rules.contracts import (
    contract_recall_targets,
    legal_contract_actions,
    legal_contract_recall_actions,
)
from dune_imperium.rules.effect_interpreter import (
    applicable_sections,
    can_afford,
    condition_holds,
    face_up_conflict_card_ids,
    factions_where_opponent_leads,
    flippable_battle_card_ids,
    influence_gain_candidates,
    option_is_playable,
    pay_cost,
    resource_cost,
    reward_can_change_something,
    section_block,
    section_is_usable,
    spy_placement_possible,
    trashable_discard_pile_ids,
)
from dune_imperium.rules.effects import (
    BOARD_ICON_COMMANDER,
    BOARD_ICON_TECH,
    OptionalBlockKind,
    active_agent_card,
    board_icon_is_pending,
    current_agent_effect_context,
    faction_gain_block,
    faction_loss_block,
    is_grafted,
    mandatory_board_icons_pending,
    other_grafted_card_id,
    pending_agent_icons,
    pending_board_icons,
    recallable_conflict_agents,
    spice_gained_this_turn,
    turn_agent_in_conflict,
)
from dune_imperium.rules.frames import (
    FrameKind,
    owned_top_frame,
    replace_player,
    turn_start_is_open,
)
from dune_imperium.rules.graft_boxes import (
    active_box,
    is_grafted_turn,
    other_box_state,
    state_with_active_box,
    tagged,
)
from dune_imperium.rules.immortality import legal_research_bonus_actions
from dune_imperium.rules.influence import (
    MAX_INFLUENCE,
    alliance_recipients_after_influence_loss,
    influence_amount,
    influence_can_rise,
)
from dune_imperium.rules.intrigue import (
    PLOT_FRAME_KINDS,
    current_intrigue_choice_entry,
    intrigue_lines_used,
    legal_intrigue_play_actions,
    unusable_intrigue_lines,
)
from dune_imperium.rules.leader_abilities import (
    EMPEROR_POST_IDS,
    FACTION_POST_IDS,
    LANDSRAAD_POST_IDS,
    leader_board_repeat_block,
    leader_reveal_block,
    legal_leader_board_repeat_actions,
    legal_leader_reveal_actions,
    prudent_diplomacy_factions,
    shaddam_payment_block,
    signet_optional_block,
    units_deployment_blocked,
)
from dune_imperium.rules.owed_draws import immediate_owed_draw_actions
from dune_imperium.rules.planetologist import replaces_sandworms
from dune_imperium.rules.reveal_turn import (
    contract_reveal_vp_block,
    current_reveal_context,
    printed_or_choice,
    printed_or_line_block,
    reveal_sandworm_block,
    tech_reveal_pending,
)
from dune_imperium.rules.sardaukar import (
    PLASTEEL_BLADES_CARD_ID,
    commander_cost,
    legal_sardaukar_commander_actions,
    legal_skill_choice_actions,
    sardaukar_commander_block,
)
from dune_imperium.rules.scouts_missions import desert_riding_token
from dune_imperium.rules.shield_wall import current_conflict_is_shield_wall_protected
from dune_imperium.rules.spies import legal_gather_intelligence_actions
from dune_imperium.rules.tech import (
    landsraad_tech_block,
    legal_tech_acquisition_actions,
)
from dune_imperium.rules.tleilaxu_row import (
    RECLAIMED_FORCES_CHOICES,
    deck_top_is_allowed,
    legal_tleilaxu_acquisitions,
    reclaimed_forces_block,
)
from dune_imperium.rules.unit_loss import legal_unit_loss_actions, unit_loss_options

ENGINE = UprisingRulesEngine()
HANGUL = re.compile(r"[가-힣]")
CONFIGS = [
    RulesetConfig(),
    RulesetConfig(choam_module=True),
    RulesetConfig(choam_module=True, bloodlines=True, tech_module=True),
    RulesetConfig(choam_module=True, immortality=True),
    RulesetConfig(
        choam_module=True,
        bloodlines=True,
        tech_module=True,
        immortality=True,
        promo_cards=True,
        arrakeen_scouts=True,
    ),
    RulesetConfig(epic_game=True),
    RulesetConfig(choam_module=True, epic_game=True, arrakeen_scouts=True),
]
IDS = [
    "base",
    "choam",
    "bloodlines-tech",
    "immortality",
    "everything-scouts",
    "epic",
    "epic-choam-scouts",
]


Decided = tuple[GameState, int, tuple[DomainAction, ...]]

# The checks below walk the same seeded games (seeds 0 and 1 of every
# ruleset, five tests each; seed 2 once more): a walk is deterministic and
# its states are frozen, so each game of the default walk is walked once
# while this module's tests run and its decisions are handed to every test
# that asks again. The module's teardown lets them go (about 120 MiB for
# the 14 games).
_WALKED: dict[tuple[RulesetConfig, int], tuple[Decided, ...]] = {}


@pytest.fixture(autouse=True, scope="module")
def _forget_the_walked_games() -> Iterator[None]:
    yield
    _WALKED.clear()


def _decisions(
    config: RulesetConfig, seed: int, *, windows_in_any_order: bool = False
) -> Iterator[Decided]:
    """Every player decision of a seeded random game, with its legal list
    (``_walk``; the default walk's decisions are kept, ``_WALKED``)."""

    if windows_in_any_order:
        return _walk(config, seed, windows_in_any_order=True)
    key = (config, seed)
    if key not in _WALKED:
        _WALKED[key] = tuple(_walk(config, seed, windows_in_any_order=False))
    return iter(_WALKED[key])


def _walk(
    config: RulesetConfig, seed: int, *, windows_in_any_order: bool
) -> Iterator[Decided]:
    """Every player decision of a seeded random game, with its legal list.

    A Conflict or Contract reward window (stage B2, OQ-112) is yielded like any
    decision, so every check below meets its rows; the walk answers it in the
    older engine's fixed order and draws nothing for it, so a seed plays the
    game it played before the windows existed. ``windows_in_any_order`` draws
    its answer like any other (its own games, for the checks that want the
    windows' rows answered in every order)."""

    state = ENGINE.reset(config, seed)
    resolver = ChanceResolver(seed=seed)
    rng = random.Random(seed)
    memory = PlacementMemory()
    while state.phase is not GamePhase.FINISHED:
        decision = ENGINE.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = apply_whole(ENGINE, state, resolver.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        legal = ENGINE.whole_actions(state, decision.owner)
        yield state, decision.owner, legal
        action = (
            None
            if windows_in_any_order
            else engine_order_answer(state, decision.owner, legal)
        )
        if action is None:
            # One draw per placement, as when it was one action (stage B1).
            action = memory.choose(state, decision.owner, legal, rng.choice)
        state = apply_whole(ENGINE, state, action).state


def _is_legal(row: dict[str, Any], legal: tuple[DomainAction, ...]) -> bool:
    action = row["action"]
    return any(
        candidate.action_id == action["action_id"]
        and dict(candidate.arguments) == action["arguments"]
        for candidate in legal
    )


_SIBLING_KEYS = (
    "choice:agent_card_influence:",
    "choice:agent_card_influence_loss:",
    "choice:reveal_faction:",
)


def _check_greyed_out_rows(
    config: RulesetConfig,
    seeds: range,
    *,
    windows_in_any_order: bool = False,
) -> tuple[set[str], set[str], int]:
    """The greyed-out rows' invariants at every decision of the seeded games:
    (the surfaces met, the row keys met, the decisions with rows)."""

    surfaces: set[str] = set()
    keys: set[str] = set()
    checked = 0
    for seed in seeds:
        rng = random.Random(1000 + seed)
        for state, seat, legal in _decisions(
            config, seed, windows_in_any_order=windows_in_any_order
        ):
            found = cast(dict[str, Any] | None, unavailable_choices(state, seat, legal))
            if found is not None:
                json.dumps(found)
                named = {
                    value
                    for action in legal
                    for _, value in action.arguments
                    if isinstance(value, str)
                }
                for row in found["rows"]:
                    surfaces.add(row["surface"])
                    keys.add(row["key"])
                    assert not _is_legal(row, legal), row
                    if row["key"].startswith(_SIBLING_KEYS):
                        # A Faction withheld by an Agent box's or a Reveal
                        # choice's picker shows only beside one it offers
                        # (the display tests meet each; a seeded game may
                        # not).
                        assert any(
                            action.action_id == row["action"]["action_id"]
                            for action in legal
                        ), row
                    assert row["code"] != NOT_NOW_CODE, row
                    assert row["reason"] and row["reason_ko"], row
                    assert not HANGUL.search(row["reason"]), row
                for ref, why in found["refs"].items():
                    assert ref not in named, ref
                    assert why["code"] != NOT_NOW_CODE, (ref, why)
                    assert not HANGUL.search(why["reason"]), why
                checked += 1
            # Nothing hidden from the seat changes what it is shown.
            hidden = determinize(state, seat, rng)
            hidden_legal = ENGINE.whole_actions(hidden, seat)
            assert hidden_legal == legal
            assert unavailable_choices(hidden, seat, hidden_legal) == found
    return surfaces, keys, checked


@pytest.mark.parametrize("config", CONFIGS, ids=IDS)
def test_greyed_out_rows_hold_with_the_reward_windows_answered_in_any_order(
    config: RulesetConfig,
) -> None:
    """Stage B2 (OQ-112): a Conflict or Contract reward's rows resolve in any
    order. The seeded games of the test below answer a window in the older
    engine's order; here one game per ruleset draws its answer like any other
    decision, so the rows, and the choices behind them, are met in the other
    orders too (the same invariants at every decision, the windows' own
    included)."""

    _, _, checked = _check_greyed_out_rows(
        config, range(1), windows_in_any_order=True
    )
    assert checked > 0


@pytest.mark.parametrize("config", CONFIGS, ids=IDS)
def test_greyed_out_rows_are_never_legal_and_never_leak(
    config: RulesetConfig,
) -> None:
    surfaces, keys, checked = _check_greyed_out_rows(config, range(2))
    assert checked > 0
    assert "acquire" in surfaces and "intrigue" in surfaces
    if config == RulesetConfig():
        # Plan 4 rows 8, 13, 15 and 17 turn up in every few games: a Maker
        # space's sandworm, Sietch Tabr's detonation, an Influence cost's
        # Faction, a Leader Reveal ability (row 1 is rarer; the display
        # tests pin it).
        for wanted in (
            "summon_maker_sandworms",
            "take_sietch_tabr_water_and_destroy_wall",
            "leader_reveal",
            # Plan 4 row 15: an Intrigue's Influence cost names a Faction
            # the seat has none with (Opportunism in seed 1).
            "intrigue_choice:choose_intrigue_faction",
        ):
            assert any(wanted in key for key in keys), (wanted, sorted(keys))


def test_a_harvest_cells_that_changes_nothing_in_its_window_reads_nothing_hidden() -> (
    None
):
    """The Conflict-end window opens on public facts for every seat
    (OQ-103), and a held Harvest Cells that could change nothing is offered
    like any other (OQ-113 (C), user ruling 2026-10-24; until then it greyed
    out, ``display.unavailable._conflict_end_trigger``). The seeded games
    above seldom meet it, so the two windows of
    ``test_harvest_cells_window_offers_a_copy_that_would_change_nothing``
    are re-dealt here: for the deciding seat the legal actions and the (no)
    greyed rows stay the same; for any other seat, re-dealing the deciding
    seat's hand shows nothing."""

    first, second = HARVEST_CELLS
    lone = _conflict_end_window(first)
    mixed = {"troops_garrison": 10, "troops_conflict": 2, "commanders_conflict": 1}
    # The first copy resolves at its play; its acquisition choice answered,
    # the window is back with the second copy offered.
    resolved = apply_whole(ENGINE, 
        _conflict_end_window(first, second, **mixed), _play_conflict_end(first)
    ).state
    played = apply_whole(ENGINE, 
        resolved, DomainAction(action_id="decline_intrigue_tleilaxu", actor=0)
    ).state
    assert played.decision_stack[-1].kind == FrameKind.CONFLICT_END_TRIGGER
    rng = random.Random(7)
    for state in (lone, played):
        legal = ENGINE.whole_actions(state, 0)
        found = unavailable_choices(state, 0, legal)
        assert found is None
        assert any(action.action_id == "play_conflict_end_intrigue" for action in legal)
        for _ in range(20):
            hidden = determinize(state, 0, rng)
            hidden_legal = ENGINE.whole_actions(hidden, 0)
            assert hidden_legal == legal
            assert unavailable_choices(hidden, 0, hidden_legal) == found
        for seat in range(1, 4):
            other = determinize(state, seat, rng)
            assert other.decision_stack[-1] == state.decision_stack[-1]
            assert ENGINE.whole_actions(other, seat) == ()
            assert unavailable_choices(other, seat, ()) is None


# --- The providers before the refactor (2026-09-29) --------------------------


def _old_revealer_persuasion(state: GameState, player: int) -> int | None:
    try:
        context = current_reveal_context(state)
    except ValueError:
        return None
    owner = context["turn_owner"]
    persuasion = context["persuasion"]
    assert isinstance(owner, int) and isinstance(persuasion, int)
    return persuasion if owner == player else None


def _old_reserve(state: GameState, player: int) -> tuple[DomainAction, ...]:
    persuasion = _old_revealer_persuasion(state, player)
    if persuasion is None:
        return ()
    return tuple(
        DomainAction(
            action_id="acquire_reserve",
            actor=player,
            arguments=(("card_id", card_id),),
        )
        for card_id, count in state.reserve_stacks
        if count > 0 and reserve_cost(state, card_id) <= persuasion
    )


def _old_imperium(state: GameState, player: int) -> tuple[DomainAction, ...]:
    persuasion = _old_revealer_persuasion(state, player)
    if persuasion is None:
        return ()
    actions: list[DomainAction] = []
    for instance_id in state.imperium_row:
        cost = imperium_card_for_instance(instance_id).acquisition_cost
        if cost is not None and cost <= persuasion:
            actions.append(
                DomainAction(
                    action_id="acquire_imperium",
                    actor=player,
                    arguments=(("instance_id", instance_id),),
                )
            )
    return tuple(actions)


def _old_manipulated(state: GameState, player: int) -> tuple[DomainAction, ...]:
    owner = state.players[player]
    if not owner.imperium_set_aside:
        return ()
    persuasion = _old_revealer_persuasion(state, player)
    if persuasion is None:
        return ()
    actions: list[DomainAction] = []
    for instance_id in owner.imperium_set_aside:
        definition = imperium_card_for_instance(instance_id)
        printed = definition.acquisition_cost
        if printed is None or max(printed - 1, 0) > persuasion:
            continue
        if (
            definition.has_acquisition_bonus
            and acquisition_ability(definition.card.card_id) is None
        ):
            continue
        actions.append(
            DomainAction(
                action_id="acquire_manipulated_imperium",
                actor=player,
                arguments=(("instance_id", instance_id),),
            )
        )
    return tuple(actions)


def _old_tleilaxu(state: GameState, player: int) -> tuple[DomainAction, ...]:
    if not state.config.immortality:
        return ()
    if owned_top_frame(state, FrameKind.REVEAL, player) is None:
        return ()
    owner = state.players[player]
    deck_top_allowed = genetic_markers_reached(owner.research_space) >= 1
    actions: list[DomainAction] = []
    for instance_id in state.tleilaxu_row:
        if tleilaxu_card_for_instance(instance_id).specimen_cost > owner.specimens:
            continue
        actions.append(
            DomainAction(
                action_id="acquire_tleilaxu",
                actor=player,
                arguments=(("instance_id", instance_id),),
            )
        )
        if deck_top_allowed:
            actions.append(
                DomainAction(
                    action_id="acquire_tleilaxu",
                    actor=player,
                    arguments=(("instance_id", instance_id), ("to_deck_top", True)),
                )
            )
    if owner.specimens >= RECLAIMED_FORCES.specimen_cost:
        actions.extend(
            DomainAction(
                action_id="acquire_reclaimed_forces",
                actor=player,
                arguments=(("choice", choice),),
            )
            for choice in RECLAIMED_FORCES_CHOICES
        )
    return tuple(actions)


def _old_choice_costs_feasible(
    player: PlayerState, sections: tuple[EffectSection, ...]
) -> bool:
    influence_needed = discards_needed = recalls_needed = retreats_needed = 0
    losses_needed = conflict_losses_needed = intrigue_needed = 0
    for section in sections:
        for cost in section.costs:
            match cost:
                case LoseInfluence(count=count):
                    influence_needed += count
                case DiscardFromHand(count=count):
                    discards_needed += count
                case LoseTroops(count=count, from_conflict=from_conflict):
                    losses_needed += count
                    if from_conflict:
                        conflict_losses_needed += count
                case GiveIntrigueToOpponent() | TrashIntrigueCard():
                    intrigue_needed += 1
                case RecallSpy(count=count):
                    recalls_needed += count
                case RetreatTroops(minimum=minimum):
                    retreats_needed += minimum
                case FlipBattleCard(icon=icon) if not flippable_battle_card_ids(
                    player, icon
                ):
                    return False
                case FlipFaceUpConflictCard(count=count) if (
                    len(face_up_conflict_card_ids(player)) < count
                ):
                    return False
                case TrashDiscardPileCard(minimum_cost=minimum_cost) if (
                    not trashable_discard_pile_ids(player, minimum_cost)
                ):
                    return False
                case _:
                    pass
    total_influence = sum(
        influence_amount(player.influence, faction) for faction in Faction
    )
    in_conflict = player.troops_conflict + player.commanders_conflict
    units = player.troops_garrison + player.commanders_garrison + in_conflict
    return (
        total_influence >= influence_needed
        and len(player.hand) >= discards_needed
        and len(player.spy_post_ids) >= recalls_needed
        and in_conflict >= retreats_needed
        and units >= losses_needed
        and in_conflict >= conflict_losses_needed
        and (intrigue_needed == 0 or len(player.intrigue_cards) >= intrigue_needed + 1)
    )


def _old_choice_rewards_feasible(
    state: GameState, player: int, sections: tuple[EffectSection, ...]
) -> bool:
    for section in sections:
        for reward in section.rewards:
            match reward:
                # Updated on purpose 2026-10-06: "Deploy up to N troops" may
                # deploy zero, so DeployFromGarrison no longer gates a play
                # [FAQ p. 2] (OQ-057 (6)).
                # Updated on purpose 2026-10-24 (user ruling, OQ-113 (C)): a
                # Spy placement gates only a line with a cost (Go to Ground,
                # Sleeper Unit); Special Mission's, Distraction's and
                # Navigation card 2's are played and fizzle. Tactical
                # Option's "any number" retreat (minimum 0) no longer needs a
                # unit in the Conflict either (a rule change made after the
                # copy).
                case PlaceSpy() if section.costs and not spy_placement_possible(
                    state, player, reward
                ):
                    return False
                case TakeContract() if not state.config.choam_module:
                    return False
                # Updated on purpose 2026-10-24 (user ruling, OQ-113 (C)): an
                # empty Imperium Row's set-aside, an empty deck's peek, an
                # empty hand's mandatory trash and False Orders before the
                # turn's Agent is sent are cost-free lines, played and
                # fizzling, so none of them gates a play any more -- a rule
                # change made after the copy.
                case GainInfluence(where_opponent_leads=True) if not (
                    factions_where_opponent_leads(state, player)
                ):
                    return False
                case GainInfluence() as gain if (
                    gain.different_from_trigger or gain.minimum_own
                ) and not influence_gain_candidates(state, player, gain):
                    return False
                # A cost line for Influence no cube can take (OQ-060,
                # OQ-071, 2026-10-06): a rule change made on purpose after
                # the copy.
                case GainInfluence() if _old_influence_line_buys_nothing(
                    state, player, section
                ):
                    return False
                case _:
                    pass
    return True


def _old_influence_line_buys_nothing(
    state: GameState, player: int, section: EffectSection
) -> bool:
    if not section.costs:
        return False
    loses = any(isinstance(cost, LoseInfluence) for cost in section.costs)
    return all(
        isinstance(reward, GainInfluence)
        and not (loses and reward.factions is None)
        and not influence_gain_candidates(state, player, reward)
        for reward in section.rewards
    )


def _old_any_effect(
    state: GameState, player: int, sections: tuple[EffectSection, ...]
) -> bool:
    # Updated on purpose 2026-10-06 (user ruling) and again 2026-10-24
    # (OQ-113 (C), "비용을 낸 것만 보장"): a line with a cost needs a reward
    # that can change something now, judged after its own resource cost
    # (``reward_can_change_something``), while a line without a cost is played
    # even when every reward fizzles -- rule changes made after the copy.
    # Updated on purpose 2026-10-30 (stage P4d, OQ-113 (C): "Tech 획득은 그
    # 타일 값(spice)을 내고 타일을 받는다"): a line whose reward is an Acquire
    # Tech is a line with a cost too (Rise of Ix's Machine Culture).
    owner = state.players[player]
    for section in sections:
        if not section.costs and not any(
            isinstance(reward, AcquireTech) for reward in section.rewards
        ):
            continue
        cost = resource_cost((section,))
        after = pay_cost(owner, cost) if can_afford(owner, cost) else owner
        if not any(
            reward_can_change_something(state, player, reward, section, after)
            for reward in section.rewards
            if state.shield_wall_present or not isinstance(reward, DestroyShieldWall)
        ):
            return False
    return True


def _old_section_is_usable(
    state: GameState, player: int, section: EffectSection
) -> bool:
    owner = state.players[player]
    if section.condition is not None and not condition_holds(
        state, player, section.condition
    ):
        return False
    # Updated on purpose 2026-10-24 (OQ-113 (C)): a line of the Shield Wall's
    # detonation alone still applies once the wall is gone and fizzles.
    sections = (section,)
    return (
        can_afford(owner, resource_cost(sections))
        and _old_choice_costs_feasible(owner, sections)
        and _old_choice_rewards_feasible(state, player, sections)
        and _old_any_effect(state, player, sections)
    )


def _old_option_is_playable(
    state: GameState, player: int, option: IntrigueOption
) -> bool:
    owner = state.players[player]
    if option.separate and option.trigger is None:
        return any(
            _old_section_is_usable(state, player, section)
            for section in option.sections
        )
    sections = applicable_sections(state, player, option)
    if option.trigger is not None and not isinstance(option.trigger, OnConflictWon):
        # Updated on purpose 2026-10-24 (user ruling, OQ-113 (C)): a
        # triggered option is played whenever a section applies, even when
        # its firing can change nothing (Call to Arms' troop, a Reveal turn
        # with nothing left to acquire) -- a rule change made after the copy.
        return bool(sections)
    # Updated on purpose 2026-10-28 (stage P3c, OQ-121 decision 6): a winning
    # Intrigue ("When you win a Conflict:", the original game's To the
    # Victor... and Demand Respect) is played from the hand in the sole
    # winner's window, so it meets the cost and the live reward like any
    # other played card; only a card waiting face up skips them.
    # Updated on purpose 2026-10-03 (codec v129, OQ-016): Coercive
    # Negotiation is no longer a face-up trigger but a Plot whose condition
    # is this turn's deployment, so its Contract-bank check (OQ-064) moved
    # from the trigger branch to the ordinary one.
    return (
        bool(sections)
        and all(
            contract_reveal_is_possible(state, reward)
            for section in sections
            for reward in section.rewards
            if isinstance(reward, RevealContractsTakeOne)
        )
        and can_afford(owner, resource_cost(sections))
        and _old_choice_costs_feasible(owner, sections)
        and _old_choice_rewards_feasible(state, player, sections)
        and _old_any_effect(state, player, sections)
    )


def _old_intrigue_plays(state: GameState, player: int) -> tuple[DomainAction, ...]:
    frame = state.decision_stack[-1] if state.decision_stack else None
    if (
        frame is None
        or not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
    ):
        return ()
    if state.phase is GamePhase.PLAYER_TURNS and frame.kind in PLOT_FRAME_KINDS:
        timing = IntrigueTiming.PLOT
    elif state.phase is GamePhase.COMBAT and frame.kind == FrameKind.COMBAT_INTRIGUE:
        timing = IntrigueTiming.COMBAT
    elif state.phase is GamePhase.ENDGAME and frame.kind == FrameKind.ENDGAME_INTRIGUE:
        timing = IntrigueTiming.ENDGAME
    else:
        return ()
    actions: list[DomainAction] = []
    for card_id in state.players[player].intrigue_cards:
        entry = INTRIGUE_CARDS_BY_INSTANCE.get(card_id)
        if entry is None or not entry.play_data_complete:
            continue
        for index, option in enumerate(entry.options):
            # Harvest Cells only in the Conflict-end window (user ruling
            # 2026-10-06, OQ-057 (11)): a rule change made on purpose after
            # the copy.
            if isinstance(option.trigger, OnTroopsLostAtConflictEnd):
                continue
            # A winning Intrigue only in the sole winner's reward window
            # (stage P3c, OQ-121 decision 6): a rule change made on purpose
            # after the copy, whose rounds are the only Combat window it knew.
            if isinstance(option.trigger, OnConflictWon):
                continue
            if option.timing is not timing:
                continue
            if option.turn_start_only and frame.kind != FrameKind.TURN:
                continue
            # Only the turn's first action (OQ-095 (6), user ruling
            # 2026-10-04): a rule change made on purpose after the copy.
            if option.turn_start_only and not turn_start_is_open(state, player):
                continue
            if _old_option_is_playable(state, player, option):
                actions.append(
                    DomainAction(
                        action_id="play_intrigue",
                        actor=player,
                        arguments=(("card_id", card_id), ("option", index)),
                    )
                )
    return tuple(actions)


def _pending_groups(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """``agent_effect_frame._pending_group_actions`` for the seat's own frame."""

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    return agent_effect_frame._pending_group_actions(state, player, context)


def _old_box_rows(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """The rows of the Agent box in ``card_id``, as the provider offered them."""

    _, context = current_agent_effect_context(state)
    actions: list[DomainAction] = []
    if context["pending_agent_effect"] is True and pending_agent_icons(context):
        actions.extend(legal_agent_card_icon_actions(state, player))
        actions.extend(legal_agent_card_recall_actions(state, player))
        actions.extend(legal_agent_card_influence_actions(state, player))
        # 2026-10-06: Tread in Darkness's trash became a choice icon.
        actions.extend(legal_agent_card_trash_actions(state, player))
        # 2026-10-18 (cleanup-2d-5): an icon box's Combat, Spy, Freighter and
        # Tech icons became rows of their own; the 2026-11-01 payout clicks
        # (OQ-164) moved a seeded random game onto a Spy icon beside a draw.
        actions.extend(legal_agent_card_icon_choice_actions(state, player))
    elif context["pending_agent_effect"] is True:
        choice_actions = tuple(
            action
            for provider in agent_effect_frame._AGENT_CARD_CHOICE_PROVIDERS
            for action in provider(state, player)
        )
        if choice_actions:
            actions.extend(choice_actions)
        elif not box_is_optional(state) and not agent_card_effect_is_unavailable(
            state
        ):
            # 2026-10-14: an optional box resolves only through its choices.
            actions.append(
                DomainAction(action_id="resolve_agent_card_effect", actor=player)
            )
    if (
        box_is_optional(state) or box_has_optional_icon(state)
    ) and not box_refusal_needed(state):
        # 2026-10-14 (OQ-095 (2), user ruling): an optional box offers no
        # refusal; the turn's end lapses it. The refusal stays only as the
        # way to the other grafted box during a bundled selection. Later
        # the same day an optional icon's refusal went beside a mandatory
        # icon too (Tread in Darkness's trash beside its draw).
        actions = [
            action
            for action in actions
            if action.action_id not in agent_effect_frame._REFUSALS
        ]
    return tuple(actions)


def _old_pending_groups(state: GameState, player: int) -> tuple[DomainAction, ...]:
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    actions: list[DomainAction] = list(_old_box_rows(state, player))
    if is_grafted_turn(context):
        # 2026-10-12: a grafted turn offers both boxes' rows from the start,
        # box 1's tagged ``box=1`` (codec v143, docs/graft-boxes-plan.md);
        # the other box waits while the active one is part way through a
        # bundled selection (plan 4.3).
        current = active_box(context)
        other = (
            ()
            if box_in_progress(state)
            else _old_box_rows(other_box_state(state), player)
        )
        zero, one = (actions, other) if current == 0 else (other, actions)
        actions = [*zero, *(tagged(action, 1) for action in one)]
    # 2026-10-10: Urgent Shigawire's added draw became its own step (OQ-106).
    actions.extend(legal_agent_card_boost_actions(state, player))
    actions.extend(legal_board_effect_actions(state, player))
    if context["pending_faction_influence"] is True:
        actions.append(
            DomainAction(action_id="resolve_faction_influence", actor=player)
        )
    return tuple(actions)


def _old_agent_box_waits(state: GameState, player: int) -> bool:
    """The page's own copy of the withheld-box test, before it read
    ``agent_box_is_waiting`` (the seat is always the frame's owner here)."""

    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return False
    if context.get("pending_agent_effect") is not True or pending_agent_icons(context):
        return False
    if any(
        provider(state, player)
        for provider in agent_effect_frame._AGENT_CARD_CHOICE_PROVIDERS
    ):
        return False
    return agent_card_effect_is_unavailable(state)


def _old_can_summon_reveal_sandworm(state: GameState, player: int) -> bool:
    """``reveal_turn._can_summon_reveal_sandworm`` before it became
    ``reveal_sandworm_block`` (2026-10-02, Desert Power option (B))."""

    owner = state.players[player]
    return (
        owner.maker_hooks
        and owner.resources.water >= 1
        and bool(state.current_conflict_ids)
        and (
            replaces_sandworms(owner)
            or not current_conflict_is_shield_wall_protected(state)
        )
    )


def _old_imperial_privilege(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """``board_effects.legal_imperial_privilege_actions`` before the recall
    confirm (2026-10-02, user ruling 2026-09-30): with no target it offered
    nothing, and the engine skipped the recall unasked.

    Since the user ruling of 2026-10-14 (OQ-095 (2)) the optional Intrigue
    trade is its own icon, offered beside the recall with no refusal (it
    gated the recall before, with its decline)."""

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("space_id") != "imperial_privilege":
        return ()
    owner = state.players[player]
    trades = (
        tuple(
            DomainAction(
                action_id="trash_intrigue_for_imperial_privilege",
                actor=player,
                arguments=(("card_id", card_id),),
            )
            for card_id in owner.intrigue_cards
        )
        if board_icon_is_pending(context, BOARD_ICON_IMPERIAL_PRIVILEGE_INTRIGUE)
        else ()
    )
    if not board_icon_is_pending(context, BOARD_ICON_IMPERIAL_PRIVILEGE):
        return trades
    conflict = recallable_conflict_agents(
        owner,
        sent_this_turn=turn_agent_in_conflict(owner, context, "imperial_privilege"),
    )
    return (
        *trades,
        *(
            DomainAction(
                action_id="recall_agent_for_imperial_privilege",
                actor=player,
                arguments=(("space_id", space_id),),
            )
            for space_id in owner.agent_locations
            if space_id != "imperial_privilege"
        ),
        *(
            (
                DomainAction(
                    action_id="recall_conflict_agent_for_imperial_privilege",
                    actor=player,
                ),
            )
            if conflict
            else ()
        ),
    )


def _old_contract_recall(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """``contracts.legal_contract_recall_actions`` before the recall confirm
    (2026-10-02): with no target the frame never opened."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.CONTRACT_REWARD_RECALL:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    context = dict(frame.context)
    excluded = context.get("excluded_space_id")
    owner = state.players[player]
    return (
        *(
            DomainAction(
                action_id="recall_agent_for_contract",
                actor=player,
                arguments=(("space_id", space_id),),
            )
            for space_id in owner.agent_locations
            if space_id != excluded
        ),
        *(
            (
                DomainAction(
                    action_id="recall_conflict_agent_for_contract", actor=player
                ),
            )
            if recallable_conflict_agents(
                owner,
                sent_this_turn=context.get("turn_agent_in_conflict") is True,
            )
            > 0
            else ()
        ),
    )


def _research_bonus_window(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """``legal_research_bonus_actions`` in the window alone: since
    cleanup-2b it also offers the bonuses waiting on the owner's turn, which
    the old copy never saw."""

    if owned_top_frame(state, FrameKind.RESEARCH_BONUS, player) is None:
        return ()
    return legal_research_bonus_actions(state, player)


def _old_research_bonus(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """``immortality.legal_research_bonus_actions`` before it read
    ``research_bonus_block`` (2026-10-02). The window it answers for now
    also opens when the arrow's cost cannot be paid; it then offered, and
    still offers, only the decline."""

    frame = owned_top_frame(state, FrameKind.RESEARCH_BONUS, player)
    if frame is None:
        return ()
    bonus = ResearchBonus(str(dict(frame.context)["bonus"]))
    owner = state.players[player]
    if bonus in (
        ResearchBonus.TRASH_AND_SPECIMEN,
        ResearchBonus.TLEILAXU_AND_SPECIMEN,
    ):
        # A research pair's window outside its owner's turn (composed-effects
        # plan 5, rule decision 5) came after this copy, which never offered
        # it: nothing old to compare. The seeded walks first reached one when
        # Forbidden Weapons' Shield Wall row changed (audit F-1, 2026-11-09).
        return _research_bonus_window(state, player)
    if bonus is ResearchBonus.INFLUENCE_ANY:
        return tuple(
            DomainAction(
                action_id="choose_research_influence",
                actor=player,
                arguments=(("faction", faction.value),),
            )
            for faction in Faction
        )
    decline = DomainAction(action_id="decline_research_bonus", actor=player)
    if bonus is ResearchBonus.TRASH_INTRIGUE_FOR_CARD_AND_INTRIGUE:
        return (
            decline,
            *(
                DomainAction(
                    action_id="trash_intrigue_for_research_bonus",
                    actor=player,
                    arguments=(("card_id", card_id),),
                )
                for card_id in owner.intrigue_cards
            ),
        )
    assert bonus is ResearchBonus.SEVEN_SOLARI_FOR_TWO_TLEILAXU
    if owner.resources.solari < 7:
        return (decline,)
    return (decline, DomainAction(action_id="pay_research_bonus", actor=player))


# The recall providers gained a confirm where the old copy offered nothing:
# (new provider, old copy, target function, confirm action id).
_RECALLS: list[
    tuple[
        Callable[[GameState, int], tuple[DomainAction, ...]],
        Callable[[GameState, int], tuple[DomainAction, ...]],
        Callable[[GameState, int], tuple[str, ...] | None],
        str,
    ]
] = [
    (
        legal_imperial_privilege_actions,
        _old_imperial_privilege,
        imperial_privilege_recall_targets,
        "resolve_imperial_privilege_without_recall",
    ),
    (
        legal_contract_recall_actions,
        _old_contract_recall,
        contract_recall_targets,
        "resolve_contract_without_recall",
    ),
]


def _old_combat_reward_influence(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """``combat.legal_combat_reward_influence_actions`` before the confirm
    without a Faction (2026-10-02, user ruling 2026-09-30): with every
    Faction at the top it offered nothing, and the engine dropped the
    choice unasked (OQ-060)."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.COMBAT_REWARD_INFLUENCE:
        return ()
    decision = frame.decision
    if not isinstance(decision, PlayerDecision) or decision.owner != player:
        return ()
    influence = state.players[player].influence
    return tuple(
        DomainAction(
            action_id="choose_combat_reward_influence",
            actor=player,
            arguments=(("faction", faction.value),),
        )
        for faction in Faction
        if influence_amount(influence, faction) < 6
    )


def _old_distinct_combat_reward_influence(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """``combat.legal_distinct_combat_reward_influence_actions`` before the
    confirm without a Faction (2026-10-02)."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.COMBAT_REWARD_DISTINCT_INFLUENCE:
        return ()
    decision = frame.decision
    if not isinstance(decision, PlayerDecision) or decision.owner != player:
        return ()
    chosen_mask = dict(frame.context)["chosen_mask"]
    assert isinstance(chosen_mask, int)
    influence = state.players[player].influence
    return tuple(
        DomainAction(
            action_id="choose_distinct_combat_reward_influence",
            actor=player,
            arguments=(("faction", faction.value),),
        )
        for index, faction in enumerate(Faction)
        if not chosen_mask & (1 << index) and influence_amount(influence, faction) < 6
    )


def _old_combat_reward_spy(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """``combat.legal_combat_reward_spy_actions`` before it offered the
    decline alone (2026-10-02): with nothing to place or recall it offered
    nothing, and the engine dropped the Spy unasked."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.COMBAT_REWARD_SPY:
        return ()
    decision = frame.decision
    if not isinstance(decision, PlayerDecision) or decision.owner != player:
        return ()
    owner = state.players[player]
    if dict(frame.context).get("deep_cover") is True:
        occupied = set(owner.spy_post_ids)
    else:
        occupied = {
            post_id for seat in state.players for post_id in seat.spy_post_ids
        }
    targets = tuple(
        post.post_id for post in OBSERVATION_POSTS if post.post_id not in occupied
    )
    if targets and owner.spies_supply > 0:
        return tuple(
            DomainAction(
                action_id="place_combat_reward_spy",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in targets
        )
    if targets and owner.spy_post_ids:
        return (
            DomainAction(action_id="decline_combat_reward_spy", actor=player),
            *(
                DomainAction(
                    action_id="recall_spy_for_combat_reward",
                    actor=player,
                    arguments=(("post_id", post_id),),
                )
                for post_id in owner.spy_post_ids
            ),
        )
    return ()


def _old_combat_reward_payment(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """``combat.legal_combat_reward_optional_payment_actions`` before
    ``combat_reward_payment_block`` (2026-10-14): the resource comparison
    was inline."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.COMBAT_REWARD_OPTIONAL:
        return ()
    decision = frame.decision
    if not isinstance(decision, PlayerDecision) or decision.owner != player:
        return ()
    context = dict(frame.context)
    cost = context["cost"]
    resource = context.get("resource")
    assert isinstance(cost, int) and resource in ("solari", "spice")
    actions = [DomainAction(action_id="decline_combat_reward", actor=player)]
    if getattr(state.players[player].resources, resource) >= cost:
        actions.append(DomainAction(action_id="pay_combat_reward", actor=player))
    return tuple(actions)


def _old_combat_reward_spy_recall(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """``combat.legal_combat_reward_spy_recall_actions`` before
    ``combat_reward_spy_recall_block`` (2026-10-14): every pair of placed
    Spies, which is none with fewer than two."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.COMBAT_REWARD_SPY_RECALL:
        return ()
    decision = frame.decision
    if not isinstance(decision, PlayerDecision) or decision.owner != player:
        return ()
    count = dict(frame.context)["spy_count"]
    posts = state.players[player].spy_post_ids
    actions = [DomainAction(action_id="decline_combat_reward", actor=player)]
    assert count == 2
    actions.extend(
        DomainAction(
            action_id="recall_spies_for_combat_reward",
            actor=player,
            arguments=(
                ("first_post_id", posts[first]),
                ("second_post_id", posts[second]),
            ),
        )
        for first in range(len(posts))
        for second in range(first + 1, len(posts))
    )
    return tuple(actions)


def _old_maker_space(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """``board_effects.legal_maker_space_actions`` before
    ``maker_sandworm_block`` and ``desert_riding_block`` (2026-10-14): the
    Maker Hooks, Conflict, Shield Wall and deployment conditions were inline."""

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    space_id = context.get("space_id")
    if space_id not in (
        "deep_desert",
        "hagga_basin",
        "imperial_basin",
    ) or not board_icon_is_pending(context, BOARD_ICON_MAKER):
        return ()
    actions = [
        DomainAction(
            action_id="harvest_maker_spice",
            actor=player,
            arguments=(("space_id", space_id),),
        )
    ]
    owner = state.players[player]
    if (
        space_id == "hagga_basin"
        and not owner.maker_hooks
        and desert_riding_token(state) is not None
    ):
        actions.append(
            DomainAction(
                action_id="take_desert_riding_hooks",
                actor=player,
                arguments=(("space_id", space_id),),
            )
        )
    if (
        space_id != "imperial_basin"
        and owner.maker_hooks
        and state.current_conflict_ids
        and (
            replaces_sandworms(owner)
            or not current_conflict_is_shield_wall_protected(state)
        )
        and not units_deployment_blocked(state, player)
    ):
        actions.append(
            DomainAction(
                action_id="summon_maker_sandworms",
                actor=player,
                arguments=(("space_id", space_id),),
            )
        )
    return tuple(actions)


def _old_sietch_tabr(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """``board_effects.legal_sietch_tabr_actions`` before
    ``sietch_tabr_wall_block`` (2026-10-14): the Shield Wall test was inline."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("space_id") != "sietch_tabr" or not board_icon_is_pending(
        context, BOARD_ICON_SIETCH_TABR
    ):
        return ()
    actions = [
        DomainAction(action_id="take_sietch_tabr_supplies", actor=player),
        DomainAction(action_id="take_sietch_tabr_water", actor=player),
    ]
    if state.shield_wall_present:
        actions.append(
            DomainAction(
                action_id="take_sietch_tabr_water_and_destroy_wall",
                actor=player,
            )
        )
    return tuple(actions)


def _old_leader_reveal(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """``leader_abilities.legal_leader_reveal_actions`` before
    ``leader_reveal_block`` (2026-10-14): each ability's prerequisite was
    inline in its leader's branch."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    frame = owned_top_frame(state, FrameKind.REVEAL, player)
    if frame is None:
        return ()
    if dict(frame.context).get("leader_reveal_ability_used") is True:
        return ()
    owner = state.players[player]
    if owner.leader_id == "lady_amber_metulli" and (
        owner.troops_conflict >= 1 or owner.commanders_conflict >= 1
    ):
        return (
            *(
                (DomainAction(action_id="retreat_leader_troop", actor=player),)
                if owner.troops_conflict >= 1
                else ()
            ),
            *(
                (DomainAction(action_id="retreat_leader_commander", actor=player),)
                if owner.commanders_conflict >= 1
                else ()
            ),
        )
    if owner.leader_id == "feyd_rautha_harkonnen" and owner.spy_post_ids:
        return tuple(
            DomainAction(
                action_id="recall_spy_for_leader",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in owner.spy_post_ids
        )
    return ()


def _old_loss_options(state: GameState, player: int) -> tuple[tuple[str, bool], ...]:
    """``unit_loss._loss_options`` before it became ``unit_loss_options``
    over ``unit_loss_block`` (2026-10-02)."""

    owner = state.players[player]
    options: list[tuple[str, bool]] = []
    if owner.troops_garrison > 0:
        options.append(("garrison", False))
    if owner.commanders_garrison > 0:
        options.append(("garrison", True))
    if owner.troops_conflict > 0:
        options.append(("conflict", False))
    if owner.commanders_conflict > 0:
        options.append(("conflict", True))
    return tuple(options)


def _old_unit_loss(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """``unit_loss.legal_unit_loss_actions`` before the confirm with no unit
    (2026-10-02, user ruling 2026-09-30): the window opened only with two
    options or more, and with none it would have offered nothing."""

    frame = owned_top_frame(state, FrameKind.OPPONENT_UNIT_LOSS, player)
    if frame is None:
        return ()
    return tuple(
        DomainAction(
            action_id="lose_unit",
            actor=player,
            arguments=(
                *((("commanders", 1),) if commander else ()),
                ("zone", zone),
            ),
        )
        for zone, commander in _old_loss_options(state, player)
    )


def _old_opponent_card_discard(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """``agent_effects.legal_opponent_card_discard_actions`` before the confirm
    with an empty hand (codec v155, OQ-138): an empty hand was never asked,
    and its window would have offered nothing."""

    if not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if (
        not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
        or "covert_operation_card_id" not in context
    ):
        return ()
    return tuple(
        DomainAction(
            action_id="discard_opponent_card",
            actor=player,
            arguments=(("card_id", card_id),),
        )
        for card_id in state.players[player].hand
    )


def _old_eligible_skills(state: GameState, owner: PlayerState) -> tuple[str, ...]:
    """``sardaukar.eligible_face_up_skill_ids`` before ``skill_choice_block``
    (2026-10-02)."""

    held = {skill_for_instance(instance).skill_id for instance in owner.skill_ids}
    seen: list[str] = []
    for instance_id in state.skill_face_up:
        skill_id = skill_for_instance(instance_id).skill_id
        if skill_id in held or skill_id in seen:
            continue
        seen.append(skill_id)
    return tuple(seen)


def _old_skill_choice(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """``sardaukar.legal_skill_choice_actions`` before the confirm with no
    choosable Skill (2026-10-02, user ruling L2-Q3 (1)): a bank Commander's
    frame then offered nothing (it never opened)."""

    frame = owned_top_frame(state, FrameKind.SKILL_CHOICE, player)
    if frame is None:
        return ()
    plasteel = dict(frame.context).get("card_id") == PLASTEEL_BLADES_CARD_ID
    return (
        *((DomainAction(action_id="decline_skill", actor=player),) if plasteel else ()),
        *(
            DomainAction(
                action_id="choose_skill",
                actor=player,
                arguments=(("skill_id", skill_id),),
            )
            for skill_id in _old_eligible_skills(state, state.players[player])
        ),
    )


def _old_contract_market(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """``contracts.legal_contract_actions`` before ``contract_take_block``
    and the hold confirm (2026-10-02, user ruling 2026-09-30): with nothing
    takeable in a non-empty market it offered nothing, and the engine held
    the icons unasked (OQ-059). Updated on purpose 2026-10-04 (OQ-021): Shaddam
    no longer chooses two Solari over an exhausted market."""

    frame = owned_top_frame(state, FrameKind.CONTRACT_MARKET, player)
    if frame is None:
        return ()
    set_aside = (
        state.sardaukar_contract_ids
        if state.players[player].leader_id == "shaddam_corrino_iv"
        else ()
    )
    holds_intrigue = bool(state.players[player].intrigue_cards)
    return (
        *(
            DomainAction(
                action_id="take_contract",
                actor=player,
                arguments=(("instance_id", instance_id),),
            )
            for instance_id in (*state.face_up_contract_ids, *set_aside)
            if holds_intrigue
            or not contract_for_instance(instance_id).requires_intrigue_trash
        ),
    )


def _old_agent_card_recall(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """``agent_effects.legal_agent_card_recall_actions`` before
    ``agent_card_recall_targets`` (2026-10-02)."""

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("pending_agent_effect") is not True:
        return ()
    if AGENT_ICON_RECALL not in pending_agent_icons(context):
        return ()
    turn_space_id = str(context["space_id"])
    owner = state.players[player]
    if (
        card_agent_box(active_agent_card(context))
        == "may_recall_agent_sent_this_turn"
    ):
        return (
            DomainAction(action_id="decline_agent_card_recall", actor=player),
            *(
                DomainAction(
                    action_id="recall_agent_for_agent_card",
                    actor=player,
                    arguments=(("space_id", space_id),),
                )
                for space_id in owner.agent_locations
                if space_id == turn_space_id
            ),
            *(
                (
                    DomainAction(
                        action_id="recall_conflict_agent_for_agent_card",
                        actor=player,
                    ),
                )
                if turn_agent_in_conflict(owner, context, turn_space_id)
                and owner.agent_in_conflict > 0
                else ()
            ),
        )
    return (
        *(
            DomainAction(
                action_id="recall_agent_for_agent_card",
                actor=player,
                arguments=(("space_id", space_id),),
            )
            for space_id in owner.agent_locations
            if space_id != turn_space_id
        ),
        *(
            (
                DomainAction(
                    action_id="recall_conflict_agent_for_agent_card",
                    actor=player,
                ),
            )
            if recallable_conflict_agents(
                owner,
                sent_this_turn=turn_agent_in_conflict(owner, context, turn_space_id),
            )
            > 0
            else ()
        ),
    )


_BRANCHING_PATH = (
    "may_trash_intrigue_for_intrigue_and_two_spice_if_bene_gesserit_alliance"
)


def _old_icon_condition_holds(
    owner: PlayerState,
    context: dict[str, Any],
    effect: str | None,
    key: str,
) -> bool:
    """``agent_effects.agent_icon_condition_holds`` before ``agent_icon_block``
    (2026-10-02), with the rule changes made on purpose since then."""

    # 2026-10-06 (Steam app comparison): Cargo Runner's two printed lines
    # became two icons, judged at two and four completed contracts.
    if effect == "draw_per_two_completed_contracts_up_to_two":
        if key == "cards":
            return len(owner.completed_contract_ids) >= 2
        if key == "cards_second":
            return len(owner.completed_contract_ids) >= 4
    # 2026-10-30 (Rise of Ix, stage P4d): Web of Power's three icons, each
    # judged at 2 Influence with its own Faction.
    web_of_power = (
        "gain_by_emperor_spacing_guild_and_fremen_influence_two"
    )
    if effect is web_of_power:
        if key == "solari":
            return owner.influence.emperor >= 2
        if key == "cards":
            return owner.influence.spacing_guild >= 2
        if key == "water":
            return owner.influence.fremen >= 2
    # 2026-10-28 (the original game, stage P3): Smuggler's Thopter's two draw
    # icons, each judged at 2 Spacing Guild Influence.
    if (
        effect == "draw_two_if_spacing_guild_influence_two"
        and key in ("cards", "cards_second")
    ):
        return owner.influence.spacing_guild >= 2
    # 2026-10-28 (the original game's promo Jessica of Arrakis, stage P3): two
    # draw icons, each judging the Bene Gesserit Bond.
    if (
        effect == "draw_two_if_bene_gesserit_bond"
        and key in ("cards", "cards_second")
    ):
        card_id = context.get("card_id")
        return has_faction_bond(
            counted_in_play(owner),
            card_id if isinstance(card_id, str) else "",
            Faction.BENE_GESSERIT,
        )
    if key == "cards_second":
        return False
    # Stillsuit Manufacturer's water and its Fremen Alliance return.
    stillsuit = (
        effect == "gain_water_and_return_self_if_fremen_alliance"
    )
    if stillsuit and key == "water":
        return True
    if key == "return_self":
        return (
            stillsuit
            and context.get("card_id") in counted_in_play(owner)
            and Faction.FREMEN.value in owner.alliance_faction_ids
        )
    # Lady Amber Metulli's Fill Coffers: the Signet Ring's Solari, and its
    # spice with any Alliance.
    if (
        effect == "leader_signet"
        and owner.leader_id == "lady_amber_metulli"
    ):
        if key == "solari":
            return True
        if key == "spice":
            return bool(owner.alliance_faction_ids)
    # 2026-10-25 (engine audit 2026-10-22, P4; OQ-027 extension 3, user
    # decision 2026-10-18 "원칙대로 아이콘마다 나누자"): Interstellar
    # Conspiracy's two lines became two icons, the spice always and the
    # Influence when grafted with an Emperor or Spacing Guild card.
    conspiracy = (
        "gain_spice_and_chosen_influence_if_grafted_with_emperor_or_guild"  # noqa: E501
    )
    if effect is conspiracy:
        if key == "spice":
            return True
        if key == "influence":
            partner = context.get("graft_card_id")
            return bool(partner) and bool(
                {Faction.EMPEROR, Faction.SPACING_GUILD}
                & set(personal_card_for_instance(str(partner)).factions)
            )
    # 2026-11-08 (OQ-027 card Agent box extension 4): Slig Farmer's Solari
    # line became an icon of its own, unconditioned, beside its arrow.
    if (
        effect == "gain_solari_per_partner_icon_and_may_pay_five_solari_for_tleilaxu"
        and key == "solari"
    ):
        return True
    # Industrial Espionage's grafted Research line became its own icon.
    # 2026-10-10: Piter, Genius Advisor's reward Research too, armed after
    # its troop cost with no condition (OQ-106).
    if key == "research":
        if effect == "may_lose_troop_to_draw_two_and_research":
            return True
        return (
            effect
            == "draw_one_and_research_and_specimen_if_grafted"
            and is_grafted(context)
        )
    # Tread in Darkness's draw became its own icon, judging the Bond; so did
    # In High Places' (cleanup-2d-5, user decision 2026-10-18).
    if (
        effect
        in (
            "trash_personal_card_to_draw_one_if_bene_gesserit_bond",
            "draw_one_and_place_spy_if_bene_gesserit_bond",
        )
        and key == "cards"
    ):
        card_id = context.get("card_id")
        return has_faction_bond(
            counted_in_play(owner),
            card_id if isinstance(card_id, str) else "",
            Faction.BENE_GESSERIT,
        )
    if key in (AGENT_ICON_CARDS, AGENT_ICON_TROOPS):
        if effect == (
            "recruit_one_and_draw_if_bene_gesserit_influence_two"
        ):
            return owner.influence.bene_gesserit >= 2
        if effect == (
            "recruit_one_and_draw_one_if_gained_two_spice_this_turn"
        ):
            return spice_gained_this_turn(owner) >= 2
        if effect == "recruit_one_and_draw_one_if_grafted":
            return is_grafted(context)
        return True
    if key == AGENT_ICON_INTRIGUE:
        return (
            effect != "draw_one_and_intrigue_if_two_markers"
            or genetic_markers_reached(owner.research_space) >= 2
        )
    maker_keeper = (
        effect == "gain_by_bene_gesserit_and_fremen_influence_two"
    )
    wheels = (
        effect
        == "gain_by_emperor_and_spacing_guild_influence_two"
    )
    if key == AGENT_ICON_SOLARI:
        # Spice Smugglers' armed 3 Solari (OQ-148, 2026-10-29) is offered as
        # it waits; the old copy knew only Wheels Within Wheels.
        smugglers = (
            "may_pay_two_spice_for_spacing_guild_influence_and_three_solari"
        )
        if effect is smugglers:
            return True
        return wheels and owner.influence.emperor >= 2
    if key == AGENT_ICON_SPICE:
        return (
            effect == _BRANCHING_PATH
            or (maker_keeper and owner.influence.fremen >= 2)
            or (wheels and owner.influence.spacing_guild >= 2)
        )
    if key == AGENT_ICON_WATER:
        return maker_keeper and owner.influence.bene_gesserit >= 2
    return True


def _old_agent_card_icons(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """``agent_effects.legal_agent_card_icon_actions`` over the old condition."""

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("pending_agent_effect") is not True:
        return ()
    owner = state.players[player]
    effect = card_agent_box(active_agent_card(context))
    return tuple(
        DomainAction(
            action_id="resolve_agent_card_effect",
            actor=player,
            arguments=(("effect", key),),
        )
        for key in pending_agent_icons(context)
        if key in AUTOMATIC_AGENT_ICONS
        and _old_icon_condition_holds(owner, context, effect, key)
    )


def test_the_agent_icon_condition_is_what_it_was() -> None:
    """``agent_icon_condition_holds`` (now ``agent_icon_block`` is None) gives
    the old answer for every Agent-box effect, icon key and owner state that
    reaches a printed threshold: each Faction's Influence and the genetic
    markers below, at and above two, spice gained this turn, grafted or
    not."""

    from dune_imperium.content.immortality.board import RESEARCH_SPACES

    spaces = tuple(space.space_id for space in RESEARCH_SPACES)
    researches = (*spaces[:: max(1, len(spaces) // 6)], spaces[-1])
    compared = 0
    for effect in (None, *sorted(AGENT_BOX_KEYS)):
        for key in (*AUTOMATIC_AGENT_ICONS, AGENT_ICON_RECALL, "influence"):
            for level in range(4):
                for gained in range(4):
                    for research in researches:
                        owner = PlayerState(
                            player_id=0,
                            influence=Influence(
                                emperor=level,
                                spacing_guild=(level + 1) % 4,
                                bene_gesserit=(level + 2) % 4,
                                fremen=(level + 3) % 4,
                            ),
                            resources=Resources(spice=gained),
                            research_space=research,
                        )
                        for grafted in (False, True):
                            # A Spacing Guild partner (Keys to Power): only
                            # Interstellar Conspiracy reads its Factions.
                            context: dict[str, Any] = (
                                {"graft_card_id": "imperium:keys_to_power:0"}
                                if grafted
                                else {}
                            )
                            assert agent_icon_condition_holds(
                                owner, context, effect, key
                            ) == _old_icon_condition_holds(
                                owner, context, effect, key
                            ), (effect, key, level, gained, research, grafted)
                            compared += 1
    assert compared > 0


# Providers that gained a confirm where the old copy offered nothing at all:
# (new provider, old copy, the frame kind, the confirm's action id).
_CONFIRMS: list[
    tuple[
        Callable[[GameState, int], tuple[DomainAction, ...]],
        Callable[[GameState, int], tuple[DomainAction, ...]],
        FrameKind,
        str,
    ]
] = [
    (
        legal_combat_reward_influence_actions,
        _old_combat_reward_influence,
        FrameKind.COMBAT_REWARD_INFLUENCE,
        "resolve_combat_influence_without_faction",
    ),
    (
        legal_distinct_combat_reward_influence_actions,
        _old_distinct_combat_reward_influence,
        FrameKind.COMBAT_REWARD_DISTINCT_INFLUENCE,
        "resolve_combat_influence_without_faction",
    ),
    (
        legal_combat_reward_spy_actions,
        _old_combat_reward_spy,
        FrameKind.COMBAT_REWARD_SPY,
        "decline_combat_reward_spy",
    ),
    (
        legal_unit_loss_actions,
        _old_unit_loss,
        FrameKind.OPPONENT_UNIT_LOSS,
        "resolve_unit_loss_without_unit",
    ),
    (
        legal_opponent_card_discard_actions,
        _old_opponent_card_discard,
        FrameKind.OPPONENT_CARD_DISCARD,
        "resolve_opponent_discard_without_card",
    ),
    (
        legal_skill_choice_actions,
        _old_skill_choice,
        FrameKind.SKILL_CHOICE,
        "resolve_commander_without_skill",
    ),
    (
        legal_contract_actions,
        _old_contract_market,
        FrameKind.CONTRACT_MARKET,
        "hold_contract_icons",
    ),
]


_PAIRS: list[
    tuple[
        Callable[[GameState, int], tuple[DomainAction, ...]],
        Callable[[GameState, int], tuple[DomainAction, ...]],
    ]
] = [
    (legal_reserve_acquisitions, _old_reserve),
    (legal_imperium_acquisitions, _old_imperium),
    (legal_manipulated_acquisitions, _old_manipulated),
    (legal_tleilaxu_acquisitions, _old_tleilaxu),
    (legal_intrigue_play_actions, _old_intrigue_plays),
    (_pending_groups, _old_pending_groups),
    (_research_bonus_window, _old_research_bonus),
    (legal_agent_card_recall_actions, _old_agent_card_recall),
    (legal_agent_card_icon_actions, _old_agent_card_icons),
    (legal_combat_reward_optional_payment_actions, _old_combat_reward_payment),
    (legal_combat_reward_spy_recall_actions, _old_combat_reward_spy_recall),
    (legal_maker_space_actions, _old_maker_space),
    (legal_sietch_tabr_actions, _old_sietch_tabr),
    (legal_leader_reveal_actions, _old_leader_reveal),
]
_OPTIONS = tuple(
    option
    for entry in {
        entry.card.card_id: entry for entry in INTRIGUE_CARDS_BY_INSTANCE.values()
    }.values()
    for option in entry.options
)


@pytest.mark.parametrize("config", CONFIGS, ids=IDS)
def test_the_refactored_providers_offer_what_they_did(config: RulesetConfig) -> None:
    """Every refactored provider, on every decision of two seeded games,
    offers exactly what its pre-refactor copy offers; and every Intrigue
    option's playability, on every 10th decision, is the old answer."""

    compared = boxes = 0
    for seed in range(2):
        for step, (state, seat, _) in enumerate(_decisions(config, seed)):
            for new, old in _PAIRS:
                assert new(state, seat) == old(state, seat), (new.__name__, step)
            # A recall offers what it did, and the confirm exactly where the
            # old provider offered nothing for want of a target.
            for new, old, targets, confirm in _RECALLS:
                expected = old(state, seat)
                if targets(state, seat) == ():
                    # Nothing to recall; Imperial Privilege's trade stays
                    # beside the confirm (2026-10-14).
                    assert not any(
                        action.action_id.startswith("recall_") for action in expected
                    )
                    expected = (
                        *expected,
                        DomainAction(action_id=confirm, actor=seat),
                    )
                assert new(state, seat) == expected, (new.__name__, step)
            # A provider that gained a confirm offers what it did, and the
            # confirm exactly where its own frame, the seat's, offered nothing.
            for new, old, kind, confirm in _CONFIRMS:
                expected = old(state, seat)
                if expected == () and owned_top_frame(state, kind, seat):
                    expected = (DomainAction(action_id=confirm, actor=seat),)
                assert new(state, seat) == expected, (new.__name__, step)
            # Panopticon's Spy is offered and holds the Reveal without the
            # old gate (2026-10-02); the gate never failed in a real game.
            panopticon = owned_top_frame(state, FrameKind.REVEAL, seat)
            if panopticon is not None and "panopticon" in tech_reveal_pending(
                dict(panopticon.context)
            ):
                owner = state.players[seat]
                assert owner.spies_supply > 0 or owner.spy_post_ids, step
            waiting = agent_box_is_waiting(state, seat)
            assert waiting == _old_agent_box_waits(state, seat), step
            for player in range(state.config.players):
                assert (
                    reveal_sandworm_block(state, player) is None
                ) == _old_can_summon_reveal_sandworm(state, player), step
                assert unit_loss_options(state, player) == _old_loss_options(
                    state, player
                ), step
            boxes += waiting
            if step % 10 == 0:
                for option in _OPTIONS:
                    assert option_is_playable(
                        state, seat, option
                    ) == _old_option_is_playable(state, seat, option)
                    for section in option.sections:
                        assert section_is_usable(
                            state, seat, section
                        ) == _old_section_is_usable(state, seat, section)
                compared += 1
    assert compared > 0
    assert boxes > 0  # a withheld Agent box was met (75-149 per ruleset)


_PRIVILEGE_RECALLS = frozenset(
    {
        "recall_agent_for_imperial_privilege",
        "recall_conflict_agent_for_imperial_privilege",
        "resolve_imperial_privilege_without_recall",
    }
)


def _privilege_choice(
    state: GameState,
    owner: int,
    rng: random.Random,
    delayed: list[int],
    shown: tuple[DomainAction, ...],
) -> DomainAction:
    """One draw of ``_privilege_decisions`` over ``shown`` (the legal list,
    an Agent turn's step shown as its placements: stage B1)."""

    choices = [
        action
        for action in shown
        if action.action_id == "agent_turn"
        and dict(action.arguments).get("space_id") == "imperial_privilege"
    ]
    waiting = imperial_privilege_recall_targets(state, owner)
    if not choices and waiting is not None:
        later = [a for a in shown if a.action_id not in _PRIVILEGE_RECALLS]
        if later and delayed[0] < 4:
            choices = later
            delayed[0] += 1
    else:
        delayed[0] = 0
    return rng.choice(choices or shown)


def _privilege_decisions(
    config: RulesetConfig, seed: int
) -> Iterator[tuple[GameState, int, tuple[DomainAction, ...]]]:
    """Every player decision of a seeded random game whose seats send an
    Agent to Imperial Privilege whenever they may, and leave its recall (or
    the confirm) for up to four other choices first (effects, Plot Intrigue
    cards, troops), so a visit's recall is asked about again after other
    things happen."""

    state = ENGINE.reset(config, seed)
    resolver = ChanceResolver(seed=seed)
    rng = random.Random(seed)
    memory = PlacementMemory()
    delayed = [0]
    while state.phase is not GamePhase.FINISHED:
        decision = ENGINE.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = apply_whole(ENGINE, state, resolver.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        legal = ENGINE.whole_actions(state, decision.owner)
        yield state, decision.owner, legal
        # One draw per placement, as when it was one action (stage B1).
        action = memory.choose(
            state,
            decision.owner,
            legal,
            partial(_privilege_choice, state, decision.owner, rng, delayed),
        )
        state = apply_whole(ENGINE, state, action).state


@pytest.mark.parametrize("config", CONFIGS, ids=IDS)
def test_recall_targets_never_grow_while_the_recall_waits(
    config: RulesetConfig,
) -> None:
    """The recall confirms are offered as soon as a recall has no target
    (user ruling 2026-09-30, "결정 창 없이 자동으로 넘어가는 곳도 모두 결정
    창을 연다"). That gives up nothing only because the targets cannot come
    back while the recall waits, as ``imperial_privilege_recall_targets``
    and ``contract_recall_targets`` say; nothing else would fail if a later
    effect broke it. Over three seeded games per ruleset that go to
    Imperial Privilege whenever they may:

    - within one Imperial Privilege visit (its Agent-effect frame and played
      card), every answer is a subset of the one before it, whatever other
      effects, Plot Intrigue cards or windows above came between; an empty
      answer, where the confirm is offered, stays empty;
    - a Contract recall's frame is the only thing its owner may act on (no
      Plot Intrigue above it), and its answer at the decision is still the
      one it was opened with (its prompt is fixed when it is pushed);
    - neither answers for a seat that is not deciding.
    """

    visits: dict[tuple[int, str, str], frozenset[str]] = {}
    compared = after_empty = 0
    for seed in range(3):
        for step, (state, seat, legal) in enumerate(_privilege_decisions(config, seed)):
            top = state.decision_stack[-1]
            for player in range(state.config.players):
                if player != seat:
                    assert imperial_privilege_recall_targets(state, player) is None
                    assert contract_recall_targets(state, player) is None
            privilege = imperial_privilege_recall_targets(state, seat)
            if privilege is not None:
                key = (seed, top.frame_id, str(dict(top.context)["card_id"]))
                if key in visits:
                    assert set(privilege) <= visits[key], (key, privilege, step)
                    compared += 1
                    after_empty += not visits[key]
                visits[key] = frozenset(privilege)
            recall = contract_recall_targets(state, seat)
            if recall is not None:
                assert legal == legal_contract_recall_actions(state, seat), step
                assert isinstance(top.decision, PlayerDecision)
                opened_empty = top.decision.prompt == "No other Agent to recall"
                assert opened_empty == (recall == ()), (top.frame_id, recall, step)
    # 6-14 visits per ruleset, asked again 3-9 times, 2-7 of them after the
    # confirm was already offered.
    assert visits and compared > 0 and after_empty > 0


# --- Optional effects of the Agent turn that offer nothing (2026-10-14) ------
#
# User ruling 2026-10-14 (OQ-095 (2)): an optional effect of the owner's
# Agent turn offers no refusal, and the turn's end lapses it, so one that
# cannot be used now offers no row at all. ``display.unavailable`` greys
# each out with the block its provider gates it on.


def _silent_optional_effects(
    state: GameState, seat: int, legal: tuple[DomainAction, ...]
) -> set[str]:
    """The row keys (without their surface) of every optional effect of the
    seat's own Agent turn that is pending and offers nothing in ``legal``.

    Read from the legal list itself, not from the block functions the page
    uses: an optional Agent box with no row of its own (each box judged
    with itself active, as the frame offers it), Imperial Privilege's
    Intrigue trade, Desert Tactics' trash, the visit's Sardaukar Commander
    and Acquire Tech, Reverend Mother's repeat and a new High Council
    seat's subcommittee. A step the seat must take before anything else
    -- Gather Intelligence, or a held draw that comes at once
    (``frames.draw_is_immediate``, OQ-106: the Bene Gesserit Influence 4
    Intrigue card) -- offers nothing else on purpose and is left out.
    """

    top = state.decision_stack[-1]
    if (
        top.kind != FrameKind.AGENT_EFFECTS
        or not isinstance(top.decision, PlayerDecision)
        or top.decision.owner != seat
        or legal_gather_intelligence_actions(state, seat)
        or immediate_owed_draw_actions(state, seat)
    ):
        return set()
    _, context = current_agent_effect_context(state)
    if context.get("finishing") is True:
        return set()
    ids = {action.action_id for action in legal}
    silent: set[str] = set()
    grafted = is_grafted_turn(context)
    locked = grafted and box_in_progress(state)
    for box in (0, 1) if grafted else (0,):
        view = state_with_active_box(state, box)
        _, view_context = current_agent_effect_context(view)
        if (
            (locked and box != active_box(context))
            or view_context.get("pending_agent_effect") is not True
            or pending_agent_icons(view_context)
            or not box_is_optional(view)
        ):
            continue
        offered = agent_effect_frame.agent_box_rows(state, seat)[box]
        if not offered:
            key = f"optional_box:{view_context['card_id']}"
            silent.add(f"{key}:box1" if box == 1 else key)
    icons = set(pending_board_icons(context))
    for icon, key, action_id in (
        (
            BOARD_ICON_IMPERIAL_PRIVILEGE_INTRIGUE,
            "imperial_privilege_intrigue",
            "trash_intrigue_for_imperial_privilege",
        ),
        ("trash", "desert_tactics_trash", "trash_card_for_desert_tactics"),
        (BOARD_ICON_COMMANDER, "sardaukar_commander", "acquire_sardaukar_commander"),
        (BOARD_ICON_TECH, "landsraad_tech", "acquire_tech"),
        ("scouts_subcommittee", "choose_subcommittee", "choose_subcommittee"),
    ):
        if icon in icons and action_id not in ids:
            silent.add(key)
    if (
        context.get("pending_leader_board_repeat") is True
        and "pay_leader_board_repeat" not in ids
    ):
        silent.add("leader_board_repeat")
    return silent


@pytest.mark.parametrize("config", CONFIGS, ids=IDS)
def test_every_optional_effect_that_offers_nothing_is_greyed_out(
    config: RulesetConfig,
) -> None:
    """At every decision of two seeded games per ruleset, each optional
    effect of the seat's own Agent turn that is pending but offers nothing
    has its greyed row, under "waiting" or "choice", whose reason says it
    lapses when the turn ends; a "waiting" one says another effect of the
    turn could still enable it. (The rows' legality, their specific
    reasons and that they read nothing hidden are
    ``test_greyed_out_rows_are_never_legal_and_never_leak``'s.)"""

    met: set[str] = set()
    for seed in range(2):
        for step, (state, seat, legal) in enumerate(_decisions(config, seed)):
            silent = _silent_optional_effects(state, seat, legal)
            if not silent:
                continue
            found = cast(dict[str, Any] | None, unavailable_choices(state, seat, legal))
            rows = {
                str(row["key"]).split(":", 1)[1]: row
                for row in (found["rows"] if found is not None else [])
            }
            for key in silent:
                assert key in rows, (key, step, sorted(rows))
                row = rows[key]
                assert row["code"] != NOT_NOW_CODE, row
                if key == "leader_board_repeat" and row["code"] == "timing":
                    # It waits for the space's own effects first.
                    assert row["surface"] == "waiting", row
                    assert "사라짐" in row["reason_ko"], row
                    continue
                if row["surface"] == "waiting":
                    assert "이번 차례의 다른 효과로 채우면 가능" in row["reason_ko"]
                    assert "another effect of this turn" in row["reason"], row
                else:
                    assert row["surface"] == "choice", row
                    assert row["reason_ko"].endswith(
                        "차례가 끝나면 쓰지 않은 채 사라짐"
                    ), row
                assert "lapses" in row["reason"], row
                met.add(key.split(":", 1)[0])
    if config.bloodlines:
        assert {"sardaukar_commander", "landsraad_tech"} <= met, met
    assert met, "an optional effect offering nothing was met"


def _own_effect_context(
    state: GameState, seat: int
) -> dict[str, Any] | None:
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return None
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != seat:
        return None
    return cast(dict[str, Any], context)


@pytest.mark.parametrize("config", CONFIGS, ids=IDS)
def test_the_optional_blocks_agree_with_their_providers(
    config: RulesetConfig,
) -> None:
    """Each visit-level optional effect's block (``display.unavailable``
    reads them) is None exactly when its provider offers it, at every
    decision of two seeded games; and an optional Agent box that offers
    nothing always has a block (``_optional_box_reason`` never falls back
    to the generic reason)."""

    compared = 0
    for seed in range(2):
        for step, (state, seat, _) in enumerate(_decisions(config, seed)):
            context = _own_effect_context(state, seat)
            if context is None:
                continue
            icons = set(pending_board_icons(context))
            if BOARD_ICON_IMPERIAL_PRIVILEGE_INTRIGUE in icons:
                trades = any(
                    action.action_id == "trash_intrigue_for_imperial_privilege"
                    for action in legal_imperial_privilege_actions(state, seat)
                )
                assert (imperial_privilege_trade_block(state, seat) is None) == trades
                compared += 1
            if "trash" in icons and context.get("space_id") == "desert_tactics":
                assert (desert_tactics_block(state, seat) is None) == bool(
                    legal_desert_tactics_actions(state, seat)
                ), step
            if BOARD_ICON_COMMANDER in icons:
                assert (sardaukar_commander_block(state, seat) is None) == bool(
                    legal_sardaukar_commander_actions(state, seat)
                ), step
                compared += 1
            if BOARD_ICON_TECH in icons:
                assert (landsraad_tech_block(state, seat) is None) == bool(
                    legal_tech_acquisition_actions(state, seat)
                ), step
                compared += 1
            if context.get("pending_leader_board_repeat") is True:
                assert (leader_board_repeat_block(state, seat) is None) == bool(
                    legal_leader_board_repeat_actions(state, seat)
                ), step
                compared += 1
            for box in (0, 1) if is_grafted_turn(context) else (0,):
                view = state_with_active_box(state, box)
                if (
                    box_is_optional(view)
                    and not pending_agent_icons(current_agent_effect_context(view)[1])
                    and not agent_effect_frame.active_box_can_act(view, seat)
                ):
                    assert unavailable._optional_box_reason(view, seat) is not None
                    compared += 1
    assert compared > 0


# --- The optional gates before their block functions (2026-10-14) ----------
#
# The providers' inline gates became block functions the page reads
# (``agent_card_cost_block``, ``agent_card_trash_block``,
# ``agent_card_acquisition_block``, ``signet_optional_block``,
# ``sardaukar_commander_block``, ``leader_board_repeat_block``); each
# provider now asks ``block is None``. These copies are the gates as they
# were written inline, so the refactor offers exactly what it did.

_OLD_OPTIONAL_DISCARDS = frozenset(
    {
        "discard_to_draw_one_or_two_if_spacing_guild",
        "may_discard_to_draw_intrigue_and_personal_card",
        "may_discard_to_draw_one_and_intrigue_if_spacing_guild",
        "may_discard_to_take_contract",
        "may_discard_to_draw_one",
        "may_discard_for_deep_cover_spy",
        "may_discard_for_water",
    }
)


def _old_cost_gate(state: GameState, player: int) -> bool:
    """The inline gates ``agent_card_cost_block`` replaced, by the box."""

    _, context = current_agent_effect_context(state)
    owner = state.players[player]
    spice, solari = owner.resources.spice, owner.resources.solari
    effect = card_agent_box(active_agent_card(context))
    if effect == "may_pay_two_spice_for_shield_wall_and_sandworm_if_maker_hooks":
        if not owner.maker_hooks or spice < 2 or not state.current_conflict_ids:
            return True
        worm = not units_deployment_blocked(state, player) and (
            replaces_sandworms(owner)
            or not current_conflict_is_shield_wall_protected(state)
        )
        return not state.shield_wall_present and not worm
    if effect == "may_pay_specimen_for_four_solari":
        return owner.specimens < 1
    if effect == "may_pay_two_specimens_for_two_tleilaxu":
        return owner.specimens < 2
    if effect == "may_trash_other_grafted_for_specimen":
        partner = other_grafted_card_id(context)
        return not partner or partner not in owner.in_play
    if effect == "research_and_may_trash_self_for_vp_if_two_markers":
        return genetic_markers_reached(owner.research_space) < 2
    if effect == "may_lose_troop_to_draw_two_and_research":
        return not any(
            getattr(owner, f"{unit}_{zone}") >= 1
            for zone in ("garrison", "conflict")
            for unit in ("troops", "commanders")
        )
    if effect == "may_pay_spice_to_trash_and_recruit":
        return spice < 1
    if effect == "pay_two_water_to_draw_two":
        return owner.resources.water < 2
    if effect == "may_pay_four_spice_for_vp":
        return spice < 4
    if effect == "may_discard_two_and_pay_five_solari_for_vp":
        return solari < 5 or len(owner.hand) < 2
    if effect == _BRANCHING_PATH:
        return (
            Faction.BENE_GESSERIT.value not in owner.alliance_faction_ids
            or not owner.intrigue_cards
        )
    if (
        effect
        == "may_trash_intrigue_and_pay_two_spice_for_vp_if_spacing_guild_alliance"
    ):
        return (
            Faction.SPACING_GUILD.value not in owner.alliance_faction_ids
            or spice < 2
            or not owner.intrigue_cards
        )
    if effect in _OLD_OPTIONAL_DISCARDS:
        return not owner.hand
    return False


_OLD_TRASH_BOXES = frozenset(
    {
        "trash_personal_card",
        "trash_personal_card_to_draw_one",
        "trash_self_and_emperor_from_hand_for_extra_influence",
        "may_trash_self_for_troop_and_first_place_influence",
        "gain_rewards_per_face_up_battle_icon",
        "may_trash_hand_card_for_emperor_rewards",
        "may_trash_two_cards_if_commander_in_conflict",
    }
)


def _old_trash_targets(state: GameState, player: int) -> tuple[str, ...] | None:
    """``legal_agent_card_trash_actions``' eligible cards as computed
    inline; None for Ruthless Leadership without a Commander in the
    Conflict, whose provider offered nothing at all."""

    _, context = current_agent_effect_context(state)
    owner = state.players[player]
    effect = card_agent_box(active_agent_card(context))
    source_card_id = str(context["card_id"])
    if (
        effect == "may_trash_two_cards_if_commander_in_conflict"
        and owner.commanders_conflict < 1
    ):
        return None
    eligible = (*owner.hand, *owner.discard_pile, *counted_in_play(owner))
    if effect == "may_trash_hand_card_for_emperor_rewards":
        eligible = owner.hand
    if effect == "may_trash_self_for_troop_and_first_place_influence":
        eligible = (source_card_id,) if source_card_id in owner.in_play else ()
    if effect == "trash_self_and_emperor_from_hand_for_extra_influence":
        space_id = context.get("space_id")
        visited = (
            BOARD_SPACES_BY_ID[space_id].faction if isinstance(space_id, str) else None
        )
        eligible = (
            tuple(
                card_id
                for card_id in owner.hand
                if card_id != source_card_id
                and Faction.EMPEROR in personal_card_for_instance(card_id).factions
            )
            if context.get("pending_faction_influence") is True
            and visited is not None
            and influence_amount(owner.influence, visited) <= MAX_INFLUENCE - 2
            else ()
        )
    return eligible


def _old_acquisition_gate(state: GameState, player: int) -> str | None:
    """Tleilaxu Master's marker gate ("marker", offered nothing) and either
    box's empty choice ("nothing", the refusal alone), as written inline."""

    _, context = current_agent_effect_context(state)
    owner = state.players[player]
    effect = card_agent_box(active_agent_card(context))
    if effect == "may_acquire_card_up_to_six_if_one_marker":
        if genetic_markers_reached(owner.research_space) < 1:
            return "marker"
        if acquirable_reserve_card_ids(state, 6) or acquirable_imperium_instance_ids(
            state, 6, player=player
        ):
            return None
        return "nothing"
    if effect == "acquire_with_solari_to_hand":
        solari = owner.resources.solari
        if any(
            count > 0 and reserve_cost(state, card_id) <= solari
            for card_id, count in state.reserve_stacks
        ) or acquirable_imperium_instance_ids(state, solari, player=player):
            return None
        return "nothing"
    return None


def _old_signet_offers_nothing(state: GameState, player: int) -> bool:
    """The optional Signet Ring abilities' inline gates, true where the
    ability offered its refusal alone."""

    context = _own_effect_context(state, player)
    assert context is not None
    owner = state.players[player]
    if owner.leader_id == "lady_jessica":
        return owner.resources.spice < 1
    if owner.leader_id == "staban_tuek":
        post = context.get("staban_bonus_post")
        if not isinstance(post, str):
            return False
        return not (
            (post in LANDSRAAD_POST_IDS and owner.resources.spice >= 1)
            or (post in FACTION_POST_IDS and owner.resources.solari >= 2)
        )
    if owner.leader_id == "princess_irulan":
        return not (
            any(
                imperium_card_for_instance(instance_id).acquisition_cost == 1
                for instance_id in acquirable_imperium_instance_ids(
                    state, 1, player=player
                )
            )
            or any(
                count > 0 and RESERVE_STACKS_BY_ID[card_id].acquisition_cost == 1
                for card_id, count in state.reserve_stacks
            )
            or owner.hand
        )
    if owner.leader_id == "chani":
        return owner.troops_conflict + owner.commanders_conflict < 1 and not (
            owner.influence.fremen >= 2 and owner.resources.water >= 1
        )
    if owner.leader_id == "duncan_idaho":
        space_id = context.get("space_id")
        return not (
            state.current_conflict_ids
            and not units_deployment_blocked(state, player)
            and isinstance(space_id, str)
            and space_id in owner.agent_locations
        )
    if owner.leader_id == "gaius_helen_mohiam":
        if context.get("listeners_paid") is True or context.get("leader_spy_recalled"):
            return False
        spies = leader_abilities._leader_spy_placement_actions(
            state, player, context, LANDSRAAD_POST_IDS, offer_decline=False
        )
        return not spies and owner.resources.spice < 1
    if owner.leader_id == "count_hasimir_fenring":
        if context.get("leader_spy_recalled") is True:
            return False
        spies = leader_abilities._leader_spy_placement_actions(
            state,
            player,
            context,
            EMPEROR_POST_IDS,
            deep_cover=True,
            offer_decline=False,
        )
        return not counted_in_play(owner) and not spies
    if owner.leader_id == "feyd_rautha_harkonnen":
        stage_id = context.get("feyd_track_stage")
        if not isinstance(stage_id, str):
            return False
        reward = FEYD_TRACK_BY_ID[stage_id].reward
        if reward is FeydTrackReward.PAY_SOLARI_TO_TRASH:
            return owner.resources.solari < 1 or not (
                owner.hand or owner.discard_pile or counted_in_play(owner)
            )
        if reward is FeydTrackReward.OPTIONAL_TRASH:
            return not (owner.hand or owner.discard_pile or counted_in_play(owner))
    return False


def _old_commander_gate(state: GameState, player: int) -> bool:
    context = _own_effect_context(state, player)
    assert context is not None
    owner = state.players[player]
    return context.get(
        "space_id"
    ) not in state.sardaukar_commander_space_ids or owner.resources.solari < (
        commander_cost(owner)
    )


def _old_repeat_gate(state: GameState, player: int) -> bool:
    context = _own_effect_context(state, player)
    assert context is not None
    return (
        mandatory_board_icons_pending(context, state.players[player])
        or state.players[player].resources.water < 1
    )


def _optional_states(
    config: RulesetConfig, seed: int
) -> Iterator[tuple[GameState, int, dict[str, Any]]]:
    """Every own Agent-turn decision of a seeded game, with each grafted
    box made active in turn, and its effect-frame context."""

    for state, seat, _ in _decisions(config, seed):
        context = _own_effect_context(state, seat)
        if context is None:
            continue
        for box in (0, 1) if is_grafted_turn(context) else (0,):
            view = state_with_active_box(state, box)
            view_context = _own_effect_context(view, seat)
            assert view_context is not None
            yield view, seat, view_context


@pytest.mark.parametrize("config", CONFIGS, ids=IDS)
def test_the_optional_block_functions_are_the_old_gates(
    config: RulesetConfig,
) -> None:
    """At every own Agent-turn decision of three seeded games (each grafted
    box made active in turn), each block function blocks exactly where the
    gate it replaced did. The seeded games are also run synthetically
    poorer: with no spice, Solari, water, cards in hand or Intrigue cards,
    which is where the gates close."""

    compared = 0
    for seed in range(3):
        for view, seat, context in _optional_states(config, seed):
            owner = view.players[seat]
            poor = replace(
                owner,
                resources=Resources(water=0),
                hand=(),
                intrigue_cards=(),
                # A specimen is a troop out of the supply (12 in all).
                troops_supply=owner.troops_supply + owner.specimens,
                specimens=0,
            )
            poorer = replace(view, players=replace_player(view.players, poor))
            for state in (view, poorer):
                if context.get("pending_agent_effect") is True:
                    assert (agent_card_cost_block(state, seat) is not None) == (
                        _old_cost_gate(state, seat)
                    ), seed
                    effect = card_agent_box(active_agent_card(context))
                    if effect in _OLD_TRASH_BOXES:
                        old = _old_trash_targets(state, seat)
                        block = agent_card_trash_block(state, seat)
                        if old is None:
                            assert block is not None
                            assert block.kind is (
                                OptionalBlockKind.NO_COMMANDER_IN_CONFLICT
                            )
                        else:
                            assert (block is None) == bool(old), seed
                    gate = _old_acquisition_gate(state, seat)
                    acquisition = agent_card_acquisition_block(state, seat)
                    assert (acquisition is None) == (gate is None), seed
                    if gate == "marker":
                        assert acquisition is not None
                        assert acquisition.kind is OptionalBlockKind.GENETIC_MARKERS
                    if effect == "leader_signet":
                        assert (signet_optional_block(state, seat) is not None) == (
                            _old_signet_offers_nothing(state, seat)
                        ), (seed, owner.leader_id)
                    compared += 1
                if state.config.bloodlines and board_icon_is_pending(
                    context, BOARD_ICON_COMMANDER
                ):
                    assert (sardaukar_commander_block(state, seat) is not None) == (
                        _old_commander_gate(state, seat)
                    ), seed
                    compared += 1
                if context.get("pending_leader_board_repeat") is True:
                    assert (leader_board_repeat_block(state, seat) is not None) == (
                        _old_repeat_gate(state, seat)
                    ), seed
                    compared += 1
    assert compared > 0


# --- The Conflict reward payments before their blocks (2026-10-14) -----------
#
# ``combat_reward_payment_block`` and ``combat_reward_spy_recall_block``
# replaced the providers' inline comparisons (a resource against the arrow's
# cost, two Spies on the board); each provider now asks ``block is None``.
# ``_old_combat_reward_payment`` and ``_old_combat_reward_spy_recall`` are the
# comparisons as they were written inline. The seeded games above compare the
# providers wherever one is met (``_PAIRS``); the optional windows are rare
# in a random game, so this sweeps every optional arrow of every Conflict
# over what the seat holds.

_ARROW_CONFLICTS = (
    ("spice_freighters", RulesetConfig()),
    ("battle_for_imperial_basin", RulesetConfig()),
    ("battle_for_arrakeen", RulesetConfig()),
    ("battle_for_spice_refinery", RulesetConfig()),
    ("economic_supremacy", RulesetConfig(epic_game=True)),
)


def test_the_conflict_reward_payment_blocks_are_the_old_comparisons() -> None:
    """Over every optional arrow of every Conflict, with 0-8 of each
    resource and 0-3 Spies on the board, each provider offers what its old
    copy did, the payment exactly where its block is None, and the block
    names what the seat is short of."""

    posts = tuple(post.post_id for post in OBSERVATION_POSTS)
    decline = DomainAction(action_id="decline_combat_reward", actor=0)
    blocked = open_windows = recalls = 0
    for conflict_id, config in _ARROW_CONFLICTS:
        for held in range(9):
            for spies in range(4):
                state = reward_window(
                    conflict_id,
                    config=config,
                    resources=Resources(solari=held, spice=(held + 3) % 9),
                    spies_supply=3 - spies,
                    spy_post_ids=posts[:spies],
                )
                # Economic Supremacy's second arrow follows the first.
                while state.decision_stack[-1].kind in (
                    FrameKind.COMBAT_REWARD_OPTIONAL,
                    FrameKind.COMBAT_REWARD_SPY_RECALL,
                ):
                    frame = state.decision_stack[-1]
                    owner = state.players[0]
                    legal = ENGINE.whole_actions(state, 0)
                    if frame.kind == FrameKind.COMBAT_REWARD_SPY_RECALL:
                        assert legal == _old_combat_reward_spy_recall(state, 0)
                        spy_block = combat_reward_spy_recall_block(frame, owner)
                        assert (spy_block is None) == (spies >= 2)
                        assert (len(legal) > 1) == (spy_block is None)
                        if spy_block is not None:
                            assert (spy_block.needed, spy_block.held) == (2, spies)
                        recalls += 1
                        break
                    assert legal == _old_combat_reward_payment(state, 0)
                    block = combat_reward_payment_block(frame, owner)
                    context = dict(frame.context)
                    resource, cost = str(context["resource"]), int(str(context["cost"]))
                    have = getattr(owner.resources, resource)
                    pay = DomainAction(action_id="pay_combat_reward", actor=0)
                    assert (block is None) == (pay in legal)
                    if block is None:
                        assert have >= cost
                        open_windows += 1
                    else:
                        assert block.kind.value == resource
                        assert (block.needed, block.held) == (cost, have)
                        blocked += 1
                    state = apply_whole(ENGINE, state, decline).state
    assert blocked > 0 and open_windows > 0 and recalls > 0


# --- The Maker spaces before their blocks (2026-10-14) -----------------------
#
# ``maker_sandworm_block`` and ``desert_riding_block`` replaced the inline
# conditions of ``legal_maker_space_actions``; the provider now asks
# ``block is None``. ``_old_maker_space`` is the provider as it was written.


def _expected_sandworm_block(
    hooks: bool, conflict_ids: tuple[str, ...], barred: bool, walled: bool
) -> OptionalBlockKind | None:
    """The first condition that fails, in the block's documented order."""

    if not hooks:
        return OptionalBlockKind.MAKER_HOOKS
    if not conflict_ids:
        return OptionalBlockKind.NO_CONFLICT
    if barred:
        return OptionalBlockKind.DEPLOYMENT_BARRED
    return OptionalBlockKind.SHIELD_WALL if walled else None


def test_the_maker_space_blocks_are_the_old_conditions() -> None:
    """Over every Maker space, with and without Maker Hooks, with no
    Conflict, an unprotected one, a Shield-Wall-protected one with and
    without the Wall, for Arrakis Planetologist, the deployment ban and the
    Desert Riding token, the provider offers what its old copy did, the
    sandworm and the token exactly where their blocks are None (the sandworm
    at the two spaces that print one), and each block names the first
    condition that fails."""

    conflicts = (
        ((), False),
        (("propaganda",), False),
        (("siege_of_arrakeen",), False),
        (("siege_of_arrakeen",), True),
    )
    cases = list(
        itertools.product(
            ("deep_desert", "hagga_basin", "imperial_basin"),
            (False, True),
            conflicts,
            ("atreides", "liet_kynes"),
            (False, True),
            (False, True),
        )
    )
    kinds: set[OptionalBlockKind | None] = set()
    for space_id, hooks, (conflict_ids, wall), leader, barred, token in cases:
        state = _maker_visit(
            space_id,
            owner_fields={"maker_hooks": hooks, "leader_id": leader},
            barred=barred,
            token=token,
            current_conflict_ids=conflict_ids,
            shield_wall_present=wall,
        )
        legal = legal_maker_space_actions(state, 0)
        assert legal == _old_maker_space(state, 0)
        ids = {action.action_id for action in legal}
        sandworm = maker_sandworm_block(state, 0)
        riding = desert_riding_block(state, 0)
        assert ("summon_maker_sandworms" in ids) == (
            space_id in content_for(state.config).sandworm_space_ids
            and sandworm is None
        )
        assert ("take_desert_riding_hooks" in ids) == (
            desert_riding_offered_at(state, space_id) and riding is None
        )
        # The Wall protects only "Siege of Arrakeen"; Liet's sandworms ignore it.
        walled = wall and leader != "liet_kynes"
        expected = _expected_sandworm_block(hooks, conflict_ids, barred, walled)
        assert (sandworm.kind if sandworm else None) is expected
        assert (riding is not None) == hooks
        kinds.add(expected)
        # Only the seat deciding has a Maker choice.
        for seat in range(1, 4):
            assert legal_maker_space_actions(state, seat) == ()
    assert len(cases) == 3 * 2 * 4 * 2 * 2 * 2
    assert kinds == {
        None,
        OptionalBlockKind.MAKER_HOOKS,
        OptionalBlockKind.NO_CONFLICT,
        OptionalBlockKind.DEPLOYMENT_BARRED,
        OptionalBlockKind.SHIELD_WALL,
    }


# --- Sietch Tabr before its block (2026-10-14) -----------------------------


def test_the_sietch_tabr_block_is_the_old_condition() -> None:
    """With the Shield Wall on the board and destroyed, while the choice is
    pending and once it is taken, the provider offers what its old copy did
    and the detonation exactly where ``sietch_tabr_wall_block`` is None."""

    detonate = DomainAction(
        action_id="take_sietch_tabr_water_and_destroy_wall", actor=0
    )
    compared = 0
    for wall in (True, False):
        pending = _sietch_tabr_visit(shield_wall_present=wall)
        taken = apply_whole(ENGINE, 
            pending, DomainAction(action_id="take_sietch_tabr_water", actor=0)
        ).state
        for state in (pending, taken):
            for seat in range(4):
                assert legal_sietch_tabr_actions(state, seat) == _old_sietch_tabr(
                    state, seat
                )
        legal = legal_sietch_tabr_actions(pending, 0)
        assert (detonate in legal) == (sietch_tabr_wall_block(pending) is None) == wall
        assert legal_sietch_tabr_actions(taken, 0) == ()
        compared += 1
    assert compared == 2


# --- The Leader Reveal abilities before their block (2026-10-14) -------------


def test_the_leader_reveal_block_is_the_old_condition() -> None:
    """For Lady Amber, Feyd-Rautha and a Leader without a Reveal-turn
    ability, with 0-1 troops and Commanders in the Conflict and 0-2 Spies on
    the board, before and after the ability is used, the provider offers
    what its old copy did and the ability exactly where
    ``leader_reveal_block`` is None; and nothing is offered, or blocked, for
    a seat that is not revealing."""

    posts = tuple(post.post_id for post in OBSERVATION_POSTS)
    bloodlines = RulesetConfig(bloodlines=True)
    cases = list(
        itertools.product(
            ("lady_amber_metulli", "feyd_rautha_harkonnen", "paul_atreides"),
            (0, 1),
            (0, 1),
            (0, 1, 2),
            (False, True),
        )
    )
    kinds: set[OptionalBlockKind | None] = set()
    for leader, troops, commanders, spies, used in cases:
        state = _leader_reveal(
            leader,
            config=bloodlines,
            troops_garrison=3 - troops,
            troops_conflict=troops,
            commanders_garrison=1 - commanders,
            commanders_conflict=commanders,
            spies_supply=3 - spies,
            spy_post_ids=posts[:spies],
        )
        if used:
            frame = state.decision_stack[-1]
            context = {**dict(frame.context), "leader_reveal_ability_used": True}
            frame = replace(frame, context=tuple(sorted(context.items())))
            state = replace(state, decision_stack=(*state.decision_stack[:-1], frame))
        legal = legal_leader_reveal_actions(state, 0)
        assert legal == _old_leader_reveal(state, 0)
        block = leader_reveal_block(state, 0)
        if used or leader == "paul_atreides":
            assert block is None and legal == ()
        elif leader == "lady_amber_metulli":
            assert (block is None) == (troops + commanders >= 1) == bool(legal)
        else:
            assert (block is None) == (spies >= 1) == bool(legal)
        if block is not None:
            assert block.kind in (
                OptionalBlockKind.NO_UNIT_IN_CONFLICT,
                OptionalBlockKind.SPIES_ON_BOARD,
            )
        kinds.add(block.kind if block else None)
        # Only the revealing seat has a Reveal-turn ability.
        for seat in range(1, 4):
            assert legal_leader_reveal_actions(state, seat) == ()
            assert leader_reveal_block(state, seat) is None
    assert len(cases) == 3 * 2 * 2 * 3 * 2
    assert kinds == {
        None,
        OptionalBlockKind.NO_UNIT_IN_CONFLICT,
        OptionalBlockKind.SPIES_ON_BOARD,
    }


# --- Faction choices and capped acquisitions before their blocks -------------
#
# Unavailable-options plan 4 rows 10, 14 and 15 (2026-11-10, stage 3 batch
# 1): the Faction pickers of an Intrigue choice, an Agent box and a Reveal
# choice, Controlled's paid draw and the capped and Tleilaxu acquisitions
# filter on named block functions (``faction_gain_block``,
# ``faction_loss_block``, ``influence_gain_block``, ``peek_draw_block``,
# ``capped_reserve_block``, ``capped_imperium_block``,
# ``tleilaxu_acquisition_block``), which the page reads for its greyed rows.
# The copies below are the filters as they were written inline before; the
# seeded games, made poorer and richer, and a sweep compare the providers to
# them.


def _old_influence_gain_candidates(
    state: GameState, player: int, gain: GainInfluence
) -> tuple[Faction, ...]:
    owner = state.players[player]
    candidates = gain.factions if gain.factions is not None else tuple(Faction)
    candidates = tuple(f for f in candidates if influence_can_rise(owner, f))
    if gain.where_opponent_leads:
        leading = factions_where_opponent_leads(state, player)
        candidates = tuple(f for f in candidates if f in leading)
    if gain.different_from_trigger:
        candidates = tuple(
            f for f in candidates if f.value != owner.navigation_trigger_faction
        )
    if gain.minimum_own:
        candidates = tuple(
            f
            for f in candidates
            if influence_amount(owner.influence, f) >= gain.minimum_own
        )
    return candidates


def _old_acquirable_reserve_card_ids(
    state: GameState, max_cost: int
) -> tuple[str, ...]:
    return tuple(
        card_id
        for card_id, count in state.reserve_stacks
        if count > 0
        and not RESERVE_STACKS_BY_ID[card_id].icon_only
        and reserve_cost(state, card_id) <= max_cost
    )


def _old_acquirable_imperium_instance_ids(
    state: GameState, max_cost: int, *, player: int | None = None
) -> tuple[str, ...]:
    set_aside = () if player is None else state.players[player].imperium_set_aside
    return tuple(
        instance_id
        for instance_id in (*state.imperium_row, *set_aside)
        if (
            (definition := imperium_card_for_instance(instance_id)).acquisition_cost
            is not None
            and definition.acquisition_cost <= max_cost
            and (
                not definition.has_acquisition_bonus
                or acquisition_ability(definition.card.card_id) is not None
            )
        )
    )


_OLD_PIECES = (
    LoseInfluence,
    GainInfluence,
    PeekTopCard,
    AcquireCardUpTo,
    AcquireTleilaxuCard,
)


def _old_piece_rows(
    state: GameState,
    player: int,
    piece: Any,
    source: Source,
    *,
    chosen: tuple[str, ...] = (),
) -> tuple[DomainAction, ...]:
    """``piece_rows``' five refactored branches as they were written, for a
    stacked Intrigue choice (refusals offered, an empty gain or acquisition
    confirmed)."""

    owner = state.players[player]

    def row(
        verb: Verb,
        target: Target | None = None,
        arguments: tuple[tuple[str, Any], ...] = (),
        *,
        of: Verb | None = None,
        variant: str = "",
    ) -> DomainAction:
        return DomainAction(
            action_id=template_id(verb, source, target, of=of, variant=variant),
            actor=player,
            arguments=arguments,
        )

    rows: list[DomainAction] = []
    match piece:
        case LoseInfluence():
            for faction in Faction:
                if influence_amount(owner.influence, faction) == 0:
                    continue
                recipients = alliance_recipients_after_influence_loss(
                    state, player, faction
                )
                for recipient in tuple(recipients) if len(recipients) > 1 else (None,):
                    arguments: tuple[tuple[str, Any], ...] = (
                        ("faction", faction.value),
                    )
                    if recipient is not None:
                        arguments = (("alliance_recipient", recipient), *arguments)
                    rows.append(row(Verb.LOSE_INFLUENCE, Target.FACTION, arguments))
        case GainInfluence(distinct=distinct) as gain:
            taken = {Faction(value) for value in chosen}
            rows.extend(
                row(Verb.GAIN_INFLUENCE, Target.FACTION, (("faction", faction.value),))
                for faction in _old_influence_gain_candidates(state, player, gain)
                if not (distinct and faction in taken)
            )
            if not rows:
                rows.append(row(Verb.CONFIRM_EMPTY, of=Verb.GAIN_INFLUENCE))
        case AcquireTleilaxuCard():
            deck_top = deck_top_is_allowed(state, player)
            for instance_id in state.tleilaxu_row:
                if tleilaxu_card_for_instance(instance_id).specimen_cost > (
                    owner.specimens
                ):
                    continue
                arguments = (("instance_id", instance_id),)
                rows.append(row(Verb.ACQUIRE, Target.TLEILAXU_CARD, arguments))
                if deck_top:
                    rows.append(
                        row(
                            Verb.ACQUIRE,
                            Target.TLEILAXU_CARD,
                            (*arguments, ("to_deck_top", True)),
                        )
                    )
            rows.extend(
                row(Verb.ACQUIRE, Target.RECLAIMED_FORCES, (("choice", choice),))
                for choice in RECLAIMED_FORCES_CHOICES
                if reclaimed_forces_block(owner, choice) is None
            )
            rows.append(row(Verb.DECLINE, of=Verb.ACQUIRE))
        case PeekTopCard(draw_or_trash=False):
            if owner.deck:
                rows.append(row(Verb.KEEP, variant="deck_top"))
                rows.append(row(Verb.DISCARD, variant="deck_top"))
                if owner.resources.solari >= 1:
                    rows.append(row(Verb.DRAW, variant="deck_top"))
            else:
                rows.append(row(Verb.CONFIRM_EMPTY, of=Verb.KEEP, variant="deck_top"))
        case AcquireCardUpTo(max_cost=max_cost, to_deck_top=forced_top):
            tops = (
                (True,)
                if forced_top
                else (False, True)
                if deck_top_offered(state, player)
                and not acquires_to_hand(state, player, piece)
                else (False,)
            )
            rows.extend(
                row(
                    Verb.ACQUIRE,
                    Target.RESERVE_CARD,
                    (
                        ("card_id", card_id),
                        *((("to_deck_top", True),) if top else ()),
                    ),
                )
                for card_id in _old_acquirable_reserve_card_ids(state, max_cost)
                for top in tops
            )
            rows.extend(
                row(
                    Verb.ACQUIRE,
                    Target.IMPERIUM_CARD,
                    (
                        ("instance_id", instance),
                        *((("to_deck_top", True),) if top else ()),
                    ),
                )
                for instance in _old_acquirable_imperium_instance_ids(
                    state, max_cost, player=player
                )
                for top in tops
            )
            if not rows:
                rows.append(row(Verb.CONFIRM_EMPTY, of=Verb.ACQUIRE))
    return tuple(rows)


# The printed limits of every GainInfluence the content holds, and a few more.
_GAINS = (
    GainInfluence(),
    GainInfluence(times=2, distinct=True),
    GainInfluence(factions=(Faction.EMPEROR, Faction.SPACING_GUILD)),
    GainInfluence(factions=(Faction.BENE_GESSERIT, Faction.FREMEN)),
    GainInfluence(where_opponent_leads=True),
    GainInfluence(different_from_trigger=True, minimum_own=2),
    GainInfluence(different_from_trigger=True),
    GainInfluence(minimum_own=1),
)
_PIECES: tuple[Any, ...] = (
    LoseInfluence(1),
    *_GAINS,
    PeekTopCard(),
    AcquireCardUpTo(max_cost=3),
    AcquireCardUpTo(max_cost=5),
    AcquireCardUpTo(max_cost=3, to_deck_top=True),
    AcquireTleilaxuCard(),
)


def _swept(state: GameState, seat: int) -> Iterator[GameState]:
    """``state`` as it is, then with the seat poorer (nothing to pay, no
    Influence, no specimens) and richer (Influence at the top with two
    Factions, ten Solari, five specimens)."""

    owner = state.players[seat]
    yield state
    poor = replace(
        owner,
        resources=Resources(),
        influence=Influence(),
        troops_supply=owner.troops_supply + owner.specimens,
        specimens=0,
    )
    yield replace(state, players=replace_player(state.players, poor))
    # Specimens only on the Immortality board.
    specimens = 5 if state.config.immortality else owner.specimens
    if owner.troops_supply + owner.specimens >= specimens:
        rich = replace(
            owner,
            resources=Resources(solari=10, spice=owner.resources.spice),
            influence=replace(owner.influence, emperor=MAX_INFLUENCE, fremen=6),
            troops_supply=owner.troops_supply + owner.specimens - specimens,
            specimens=specimens,
        )
        yield replace(state, players=replace_player(state.players, rich))


@pytest.mark.parametrize("config", CONFIGS, ids=IDS)
def test_the_choice_blocks_are_the_old_filters(config: RulesetConfig) -> None:
    """At every decision of two seeded games, as it is and with the seat
    made poorer and richer: ``piece_rows`` for each refactored piece kind
    (and the Intrigue choice the seat is in) offers what its pre-refactor
    copy offers; ``influence_gain_candidates`` for every printed limit, the
    capped acquisitions for every cap and the two Faction blocks are the old
    filters. ``piece_blocked_rows`` names every candidate ``piece_rows``
    withholds and none it offers."""

    compared = 0
    for seed in range(2):
        for state, seat, _ in _decisions(config, seed):
            for view in _swept(state, seat):
                owner = view.players[seat]
                for faction in Faction:
                    assert (faction_gain_block(owner, faction) is None) == (
                        influence_can_rise(owner, faction)
                    )
                    for amount in (1, 2):
                        assert (faction_loss_block(owner, faction, amount) is None) == (
                            influence_amount(owner.influence, faction) >= amount
                        )
                for gain in _GAINS:
                    assert influence_gain_candidates(
                        view, seat, gain
                    ) == _old_influence_gain_candidates(view, seat, gain)
                for cap in range(10):
                    assert acquirable_reserve_card_ids(
                        view, cap
                    ) == _old_acquirable_reserve_card_ids(view, cap)
                    assert acquirable_imperium_instance_ids(
                        view, cap, player=seat
                    ) == _old_acquirable_imperium_instance_ids(view, cap, player=seat)
                entry = current_intrigue_choice_entry(view, seat)
                pieces = (
                    _PIECES
                    if entry is None
                    else (*_PIECES, current_piece(entry))
                )
                for piece in pieces:
                    if not isinstance(piece, _OLD_PIECES) or (
                        isinstance(piece, PeekTopCard) and piece.draw_or_trash
                    ):
                        # Poison Snooper's look was not refactored.
                        continue
                    chosen = entry.chosen if entry is not None else ()
                    new = piece_rows(
                        view,
                        seat,
                        piece,
                        Source.INTRIGUE,
                        refusals=True,
                        chosen=chosen,
                    )
                    assert new == _old_piece_rows(
                        view, seat, piece, Source.INTRIGUE, chosen=chosen
                    ), (seed, piece)
                    blocked = piece_blocked_rows(
                        view, seat, piece, Source.INTRIGUE, chosen=chosen
                    )
                    # A greyed row is its candidate's plain row: no Alliance
                    # recipient, no optional deck-top twin -- but a deck-top
                    # destination the piece forces (Bypass Protocol) stays.
                    dropped = (
                        ("alliance_recipient",)
                        if getattr(piece, "to_deck_top", False)
                        else ("alliance_recipient", "to_deck_top")
                    )
                    plain = {
                        replace(
                            action,
                            arguments=tuple(
                                item
                                for item in action.arguments
                                if item[0] not in dropped
                            ),
                        )
                        for action in new
                    }
                    assert not plain & {action for action, _ in blocked}, piece
                    if getattr(piece, "to_deck_top", False):
                        assert all(
                            dict(action.arguments).get("to_deck_top") is True
                            for action, _ in blocked
                        ), piece
                    # Every candidate is offered or greyed: none drops silently.
                    named = {
                        _named(action)
                        for action in (*new, *(action for action, _ in blocked))
                    }
                    assert _candidates(view, seat, piece) <= named, (seed, piece)
                    compared += 1
    assert compared > 0


def _named(action: DomainAction) -> str:
    """What a choice row names: its Faction, card or choice, else its id."""

    arguments = dict(action.arguments)
    for key in ("faction", "instance_id", "card_id", "choice"):
        value = arguments.get(key)
        if isinstance(value, str):
            return value
    return action.action_id


def _candidates(state: GameState, seat: int, piece: Any) -> set[str]:
    """Everything a refactored piece names, offered or not."""

    match piece:
        case LoseInfluence():
            return {faction.value for faction in Faction}
        case GainInfluence(factions=factions):
            return {faction.value for faction in factions or tuple(Faction)}
        case PeekTopCard() if state.players[seat].deck:
            return {template_id(Verb.DRAW, Source.INTRIGUE, variant="deck_top")}
        case AcquireCardUpTo():
            return {card_id for card_id, _ in state.reserve_stacks} | set(
                capped_imperium_candidates(state, seat)
            )
        case AcquireTleilaxuCard():
            return set(state.tleilaxu_row) | set(RECLAIMED_FORCES_CHOICES)
    return set()


# --- The Tech tile block before it (stage 3 batch 2) --------------------------
#
# Unavailable-options plan 4 row 2 (2026-11-10): ``tech._affordable_
# acquisitions`` (the Tech Module) and ``ix_tech_acquisitions`` (Rise of Ix)
# offer a tile exactly when ``tech_tile_block`` is None. The copies below are
# the filters as they were written inline; a sweep of the seat's spice,
# Solari, Negotiators, Spies, High Council seat and Secret Project, every
# Tech Discount and both payments, and the seeded games, compare them.


def _old_affordable_acquisitions(
    state: GameState, owner: PlayerState, discount: int
) -> tuple[Any, ...]:
    return tuple(
        (tile, variant)
        for tile, secret in tech.tech_candidates(state, owner)
        if owner.resources.spice
        >= tech.tech_cost(owner, tile, discount=discount, secret_project=secret)
        for variant in tech._acquisition_variants(state, owner, tile)
    )


def _old_ix_tech_acquisitions(
    state: GameState, owner: PlayerState, discount: int, payment: str
) -> tuple[Any, ...]:
    held = tech._held_for(owner, payment)
    return tuple(
        (tile, returned, variant)
        for tile, secret in tech.tech_candidates(state, owner)
        for returned in range(
            min(
                owner.negotiators,
                tech.ix_negotiators_useful(
                    tile, discount=discount, secret_project=secret
                ),
            )
            + 1
        )
        if held
        >= tech.ix_tech_cost(
            owner,
            tile,
            discount=discount,
            negotiators=returned,
            secret_project=secret,
        )
        for variant in tech._acquisition_variants(state, owner, tile)
    )


def _tech_filters_agree(state: GameState, seat: int) -> int:
    """Compare the providers' filters with their copies for ``seat`` at
    every Tech Discount and payment; the number of comparisons."""

    owner = state.players[seat]
    compared = 0
    for discount in range(3):
        if state.config.rise_of_ix:
            for payment in (tech.SPICE_PAYMENT, tech.SOLARI_PAYMENT):
                new = tech.ix_tech_acquisitions(state, owner, discount, payment)
                assert new == _old_ix_tech_acquisitions(state, owner, discount, payment)
                offered = {tile.tech_id for tile, _, _ in new}
                for tile, secret in tech.tech_candidates(state, owner):
                    block = tech.tech_tile_block(
                        state,
                        owner,
                        tile,
                        secret=secret,
                        discount=discount,
                        payment=payment,
                    )
                    assert (block is None) == (tile.tech_id in offered), tile
                compared += 1
        elif state.config.tech_module:
            new_pairs = tech._affordable_acquisitions(state, owner, discount)
            assert new_pairs == _old_affordable_acquisitions(state, owner, discount)
            offered = {tile.tech_id for tile, _ in new_pairs}
            for tile, secret in tech.tech_candidates(state, owner):
                block = tech.tech_tile_block(
                    state, owner, tile, secret=secret, discount=discount
                )
                assert (block is None) == (tile.tech_id in offered), tile
            compared += 1
    return compared


_TECH_CONFIGS = (
    RulesetConfig(bloodlines=True, tech_module=True),
    # Rise of Ix's tiles (and Leaders) on the Ixian Embassy, without the rest
    # of Rise of Ix: the Tech Module's provider prices them, the High
    # Council's discount included.
    RulesetConfig(bloodlines=True, tech_module=True, ix_tech_tiles=True),
    RulesetConfig(
        bloodlines=True, tech_module=True, ix_tech_tiles=True, ix_leaders=True
    ),
    RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True),
    RulesetConfig(
        base_game=BaseGame.IMPERIUM, rise_of_ix=True, bloodlines=True, tech_module=True
    ),
)


def test_the_tech_tile_block_is_the_old_filter() -> None:
    """Over a sweep of what the seat holds in each Tech configuration (the
    Tech Module, Rise of Ix's tiles on it, Rise of Ix with and without the
    Module), and the seeded games of the rulesets with Tech tiles, the providers
    offer what their copies offer, and ``tech_tile_block`` is None exactly
    for the tiles they offer."""

    compared = 0
    for config in _TECH_CONFIGS:
        state = ENGINE.reset(config, 0)
        tiles = [tile for stack in state.tech_stacks for tile in stack]
        posts = [post.post_id for post in OBSERVATION_POSTS][:1]
        for start in range(0, len(tiles) - 2, 3):
            stacks = tuple((tile,) for tile in tiles[start : start + 3])
            for spice, solari, negotiators, spies, council, secret in itertools.product(
                (0, 1, 2, 3, 5, 8),
                (0, 3, 6),
                (0, 1, 3) if config.rise_of_ix else (0,),
                (0, 1),
                (False, True),
                # A Secret Project only with the Tech Module (Kota Odax).
                ("", tiles[start - 1] if start and config.tech_module else ""),
            ):
                owner = replace(
                    state.players[0],
                    resources=Resources(spice=spice, solari=solari),
                    negotiators=negotiators,
                    troops_supply=state.players[0].troops_supply - negotiators,
                    spy_post_ids=tuple(posts[:spies]),
                    spies_supply=state.players[0].spies_supply - spies,
                    high_council=council,
                    secret_project_tech_id=secret,
                )
                swept = replace(
                    state,
                    tech_stacks=stacks,
                    players=replace_player(state.players, owner),
                )
                compared += _tech_filters_agree(swept, 0)
    for config in (*CONFIGS, *_TECH_CONFIGS[1:]):  # one game of each extra
        if not (config.tech_module or config.rise_of_ix):
            continue
        for seed in range(1 if config.rise_of_ix else 2):
            for state, seat, _ in _decisions(config, seed):
                compared += _tech_filters_agree(state, seat)
    assert compared > 0


# --- A separate-lines card's lines (stage 3 batch 3, plan 4 row 7) -------------


@pytest.mark.parametrize("config", CONFIGS, ids=IDS)
def test_every_unused_arrow_line_is_offered_or_greyed(config: RulesetConfig) -> None:
    """At every separate-lines card's frame of two seeded games, each unused
    arrow line is either offered (``use_intrigue_effect``) or named by
    ``unusable_intrigue_lines`` with its ``section_block``, never both; the
    block is None exactly for the offered lines (``section_is_usable``, whose
    pre-refactor copy ``test_the_refactored_providers_offer_what_they_did``
    compares)."""

    met = 0
    for seed in range(2):
        for state, seat, legal in _decisions(config, seed):
            unusable = unusable_intrigue_lines(state, seat)
            if unusable is None:
                continue
            option, blocked = unusable
            offered = {
                dict(action.arguments)["section"]
                for action in legal
                if action.action_id == "use_intrigue_effect"
            }
            greyed = {index for index, _ in blocked}
            assert not offered & greyed
            frame = state.decision_stack[-1]
            used = set(intrigue_lines_used(dict(frame.context)))
            arrow = {
                index
                for index, section in enumerate(option.sections)
                if section.costs and index not in used
            }
            assert offered | greyed == arrow, (offered, greyed, arrow)
            for index, block in blocked:
                assert block == section_block(state, seat, option.sections[index])
                assert not section_is_usable(state, seat, option.sections[index])
            met += 1
    assert met > 0


# --- The long tail before its blocks (stage 3 batch 4) -------------------------
#
# Plan 4 rows 11, 5, 4 and 10 (2026-11-10): a printed "-OR-" Reveal line
# (``printed_or_line_block``), Prudent Diplomacy's Factions
# (``prudent_diplomacy_block``), Emperor of the Known Universe's payment
# (``shaddam_payment_block``), Captured Mentat's lost Faction and the Contract
# VP line (``faction_loss_block``, ``contract_reveal_vp_block``), and Price is
# No Object's Reserve cards (``capped_reserve_block``) replaced inline filters.
# The copies below are those filters as they were.


def _old_printed_or_line_open(owner: PlayerState, line: EffectSection) -> bool:
    if line.rewards == (TakeHighCouncilSeat(),):
        if owner.high_council:
            return False
    for cost in line.costs:
        match cost:
            case PayResources(solari=solari, spice=spice, water=water):
                if (
                    owner.resources.solari < solari
                    or owner.resources.spice < spice
                    or owner.resources.water < water
                ):
                    return False
    return True


def _old_prudent_diplomacy_factions(
    state: GameState, player: int
) -> tuple[Faction, ...]:
    owner = state.players[player]
    if owner.resources.spice < 1:
        return ()
    return tuple(
        faction
        for faction in Faction
        if influence_can_rise(owner, faction)
        and any(
            influence_amount(seat.influence, faction)
            > influence_amount(owner.influence, faction)
            for seat in state.players
            if seat.player_id != player
        )
    )


def _old_solari_reserve(state: GameState, solari: int) -> tuple[str, ...]:
    return tuple(
        card_id
        for card_id, count in state.reserve_stacks
        if count > 0
        and not RESERVE_STACKS_BY_ID[card_id].icon_only
        and reserve_cost(state, card_id) <= solari
    )


_PRINTED_OR_LINES = tuple(
    line
    for key in REVEAL_CHOICE_KEYS
    if printed_or_choice(ability := reveal_choice_ability(key))
    for line in cast(Any, ability).sections
)
_LONG_TAIL_CONFIGS = (
    *CONFIGS,
    RulesetConfig(base_game=BaseGame.IMPERIUM),
    RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True),
)


def test_the_long_tail_blocks_are_the_old_filters() -> None:
    """Over the seeded games (the original board's and Rise of Ix's too),
    each seat made poorer and richer, and every printed "-OR-" line: the
    refactored filters keep what their copies kept, and at every either
    Agent box its choice line is offered exactly when
    ``either_choice_block`` is None."""

    assert _PRINTED_OR_LINES
    compared = either = 0
    for config in _LONG_TAIL_CONFIGS:
        seeds = range(2) if config in CONFIGS else range(1)
        for seed in seeds:
            for state, seat, _ in _decisions(config, seed):
                for view in _swept(state, seat):
                    owner = view.players[seat]
                    for line in _PRINTED_OR_LINES:
                        assert (printed_or_line_block(owner, line) is None) == (
                            _old_printed_or_line_open(owner, line)
                        )
                    for player in range(view.config.players):
                        assert prudent_diplomacy_factions(
                            view, player
                        ) == _old_prudent_diplomacy_factions(view, player)
                    for solari in range(12):
                        assert tuple(
                            card_id
                            for card_id, count in view.reserve_stacks
                            if capped_reserve_block(view, card_id, count, solari)
                            is None
                        ) == _old_solari_reserve(view, solari)
                    assert (shaddam_payment_block(owner) is None) == (
                        owner.resources.solari >= 3
                    )
                    either += _either_agrees(view, seat)
                    compared += 1
    assert compared > 0
    assert either > 0, "an either Agent box was met"


def test_the_contract_vp_block_is_the_old_condition() -> None:
    """Delivery Agreement's and Priority Contracts' "trash this card -> 1
    VP" (four completed Contracts, the card still in play): the block is
    None exactly where the old provider's inline test held, below, at and
    above the threshold, the card in play or not; and the Reveal offers
    the line exactly then."""

    effect = "keep_spice_or_trash_self_for_vp_if_four_contracts"
    met = 0
    for name in ("delivery_agreement", "priority_contracts"):
        card = f"imperium:{name}:0"
        for contracts, present in itertools.product(range(6), (True, False)):
            owner = PlayerState(
                player_id=0,
                in_play=(card,) if present else (),
                completed_contract_ids=tuple(f"c{i}" for i in range(contracts)),
            )
            state = ENGINE.reset(RulesetConfig(choam_module=True), 0)
            judged = replace(state, players=replace_player(state.players, owner))
            block = contract_reveal_vp_block(judged, 0, card, effect)
            assert (block is None) == (contracts >= 4 and present), (name, contracts)
            met += 1
    assert met == 24


def _either_agrees(state: GameState, seat: int) -> int:
    """At an own Agent-turn decision with an either box pending, its choice
    line offers a row exactly when ``either_choice_block`` is None."""

    context = _own_effect_context(state, seat)
    if context is None:
        return 0
    met = 0
    for box in (0, 1) if is_grafted_turn(context) else (0,):
        view = state_with_active_box(state, box)
        view_context = _own_effect_context(view, seat)
        assert view_context is not None
        if view_context.get("pending_agent_effect") is not True or pending_agent_icons(
            view_context
        ):
            continue
        ability = box_ability(card_agent_box(active_agent_card(view_context)))
        if ability is None or not either_box(ability):
            continue
        rows = either_rows(view, seat, ability)
        choice = any(
            action.action_id != "resolve_agent_card_effect" for action in rows
        )
        assert choice == (either_choice_block(view, seat, ability) is None), (
            view_context.get("card_id"),
            rows,
        )
        met += 1
    return met


# --- A space's printed cost options (stage 3, plan 4 row 18) -----------------


def test_the_placement_cost_block_is_the_bare_comparison() -> None:
    """``placement_cost_block`` is None exactly where ``_can_afford`` holds,
    over every small cost and holding (the placement hot path keeps the
    bare comparison)."""

    span = range(4)
    for solari, spice, water, cost_solari, cost_spice, cost_water in (
        itertools.product(span, span, span, span, span, span)
    ):
        owner = PlayerState(
            player_id=0,
            resources=Resources(solari=solari, spice=spice, water=water),
        )
        cost = ResourceCost(solari=cost_solari, spice=cost_spice, water=cost_water)
        assert (placement_cost_block(owner, cost) is None) == agent_turn._can_afford(
            owner, cost
        )


@pytest.mark.parametrize("config", CONFIGS, ids=IDS)
def test_a_named_cost_option_is_never_offered_and_every_withheld_one_is_named(
    config: RulesetConfig,
) -> None:
    """At every space pick of two seeded games, a cost option the payload
    names is never offered, and every printed option of an offered space
    the pick withholds is named."""

    met = 0
    for seed in range(2):
        for state, seat, legal in _decisions(config, seed):
            blocked = space_option_blocks(state, seat, legal)
            offered: dict[str, set[int]] = {}
            for action in legal:
                arguments = dict(action.arguments)
                if action.action_id == "place_agent" and isinstance(
                    arguments.get("cost_option"), int
                ):
                    space = str(arguments["space_id"])
                    offered.setdefault(space, set()).add(int(arguments["cost_option"]))
            for space_id, options in blocked.items():
                named = {option for option, _ in options}
                assert not named & offered.get(space_id, set()), space_id
                met += 1
            # A grafted pick too: only the Heighliner's cost depends on the
            # partner, and it prints one (Codex review 2026-11-10).
            if agent_turn.agent_card_pick(state, seat) is not None:
                for space_id, offered_options in offered.items():
                    printed = len(BOARD_SPACES_BY_ID[space_id].cost_options)
                    withheld = {option for option, _ in blocked.get(space_id, ())}
                    assert offered_options | withheld == set(range(printed)), space_id
    assert met > 0
