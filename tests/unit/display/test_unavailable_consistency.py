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
``test_recall_targets_never_grow_while_the_recall_waits`` pins what the
recall confirms (2026-10-02) rely on: a recall's targets never come back
while it waits.
"""

import json
import random
import re
from collections.abc import Callable, Iterator
from typing import Any, cast

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.determinize import determinize
from dune_imperium.content.bloodlines.sardaukar import skill_for_instance
from dune_imperium.content.immortality.board import (
    ResearchBonus,
    genetic_markers_reached,
)
from dune_imperium.content.immortality.tleilaxu import (
    RECLAIMED_FORCES,
    tleilaxu_card_for_instance,
)
from dune_imperium.content.uprising.board import OBSERVATION_POSTS, Faction
from dune_imperium.content.uprising.contracts import contract_for_instance
from dune_imperium.content.uprising.effect_dsl import (
    DeployFromGarrison,
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
    OnTroopsLostAtConflictEnd,
    PeekTopCard,
    PlaceSpy,
    RecallSpy,
    RedirectSpiesOnTurnSpace,
    RetreatTroops,
    RevealContractsTakeOne,
    SetAsideImperiumRowCard,
    TakeContract,
    TrashDiscardPileCard,
    TrashIntrigueCard,
    TrashPersonalCard,
)
from dune_imperium.content.uprising.imperium import imperium_card_for_instance
from dune_imperium.content.uprising.intrigue import INTRIGUE_CARDS_BY_INSTANCE
from dune_imperium.content.uprising.types import PersonalCardAgentEffect
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.player import Influence, PlayerState, Resources
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.display.unavailable import NOT_NOW_CODE, unavailable_choices
from dune_imperium.rules import UprisingRulesEngine, agent_effect_frame
from dune_imperium.rules.acquisition import (
    legal_imperium_acquisitions,
    legal_manipulated_acquisitions,
    legal_reserve_acquisitions,
    reserve_cost,
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
    agent_card_effect_is_unavailable,
    agent_icon_condition_holds,
    legal_agent_card_icon_actions,
    legal_agent_card_influence_actions,
    legal_agent_card_recall_actions,
    legal_agent_card_trash_actions,
    spice_gained_this_turn,
)
from dune_imperium.rules.board_effects import (
    BOARD_ICON_IMPERIAL_PRIVILEGE,
    imperial_privilege_recall_targets,
    legal_board_effect_actions,
    legal_imperial_privilege_actions,
)
from dune_imperium.rules.card_bonds import counted_in_play, has_faction_bond
from dune_imperium.rules.combat import (
    legal_combat_reward_influence_actions,
    legal_combat_reward_spy_actions,
    legal_distinct_combat_reward_influence_actions,
)
from dune_imperium.rules.combat_deployment import undeployable_troops_this_turn
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
    resource_cost,
    section_is_usable,
    spy_placement_possible,
    trashable_discard_pile_ids,
)
from dune_imperium.rules.effects import (
    active_agent_card,
    agent_turn_space_id,
    board_icon_is_pending,
    current_agent_effect_context,
    is_grafted,
    pending_agent_icons,
    recallable_conflict_agents,
    turn_agent_in_conflict,
)
from dune_imperium.rules.frames import FrameKind, owned_top_frame, turn_start_is_open
from dune_imperium.rules.immortality import legal_research_bonus_actions
from dune_imperium.rules.influence import influence_amount
from dune_imperium.rules.intrigue import PLOT_FRAME_KINDS, legal_intrigue_play_actions
from dune_imperium.rules.leader_abilities import units_deployment_blocked
from dune_imperium.rules.planetologist import replaces_sandworms
from dune_imperium.rules.reveal_turn import (
    current_reveal_context,
    reveal_sandworm_block,
    tech_reveal_pending,
)
from dune_imperium.rules.sardaukar import (
    PLASTEEL_BLADES_CARD_ID,
    legal_skill_choice_actions,
)
from dune_imperium.rules.shield_wall import current_conflict_is_shield_wall_protected
from dune_imperium.rules.tleilaxu_row import (
    RECLAIMED_FORCES_CHOICES,
    legal_tleilaxu_acquisitions,
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


def _decisions(
    config: RulesetConfig, seed: int
) -> Iterator[tuple[GameState, int, tuple[DomainAction, ...]]]:
    """Every player decision of a seeded random game, with its legal list."""

    state = ENGINE.reset(config, seed)
    resolver = ChanceResolver(seed=seed)
    rng = random.Random(seed)
    while state.phase is not GamePhase.FINISHED:
        decision = ENGINE.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = ENGINE.apply(state, resolver.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        legal = ENGINE.legal_actions(state, decision.owner)
        yield state, decision.owner, legal
        state = ENGINE.apply(state, rng.choice(legal)).state


def _is_legal(row: dict[str, Any], legal: tuple[DomainAction, ...]) -> bool:
    action = row["action"]
    return any(
        candidate.action_id == action["action_id"]
        and dict(candidate.arguments) == action["arguments"]
        for candidate in legal
    )


@pytest.mark.parametrize("config", CONFIGS, ids=IDS)
def test_greyed_out_rows_are_never_legal_and_never_leak(
    config: RulesetConfig,
) -> None:
    surfaces: set[str] = set()
    checked = 0
    for seed in range(2):
        rng = random.Random(1000 + seed)
        for state, seat, legal in _decisions(config, seed):
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
                    assert not _is_legal(row, legal), row
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
            hidden_legal = ENGINE.legal_actions(hidden, seat)
            assert hidden_legal == legal
            assert unavailable_choices(hidden, seat, hidden_legal) == found
    assert checked > 0
    assert "acquire" in surfaces and "intrigue" in surfaces


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
        if definition.has_acquisition_bonus and definition.acquisition_effect is None:
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
    owner = state.players[player]
    for section in sections:
        for reward in section.rewards:
            match reward:
                case DeployFromGarrison() if (
                    owner.troops_garrison
                    - undeployable_troops_this_turn(state, player)
                    + owner.commanders_garrison
                    < 1
                    or units_deployment_blocked(state, player)
                ):
                    return False
                case PlaceSpy() if not spy_placement_possible(state, player, reward):
                    return False
                case RetreatTroops(minimum=minimum) if (
                    owner.troops_conflict + owner.commanders_conflict < minimum
                ):
                    return False
                case TakeContract() if not state.config.choam_module:
                    return False
                case SetAsideImperiumRowCard() if not state.imperium_row:
                    return False
                case PeekTopCard() if not owner.deck:
                    return False
                case TrashPersonalCard(mandatory=True, hand_only=True) if (
                    not owner.hand
                ):
                    return False
                case GainInfluence(where_opponent_leads=True) if not (
                    factions_where_opponent_leads(state, player)
                ):
                    return False
                case GainInfluence() as gain if (
                    gain.different_from_trigger or gain.minimum_own
                ) and not influence_gain_candidates(state, player, gain):
                    return False
                case RedirectSpiesOnTurnSpace() if (
                    agent_turn_space_id(state, player) is None
                ):
                    return False
                case _:
                    pass
    return True


def _old_section_is_usable(
    state: GameState, player: int, section: EffectSection
) -> bool:
    owner = state.players[player]
    if section.condition is not None and not condition_holds(
        state, player, section.condition
    ):
        return False
    if not state.shield_wall_present and all(
        isinstance(reward, DestroyShieldWall) for reward in section.rewards
    ):
        return False
    sections = (section,)
    return (
        can_afford(owner, resource_cost(sections))
        and _old_choice_costs_feasible(owner, sections)
        and _old_choice_rewards_feasible(state, player, sections)
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
    sections = applicable_sections(
        state, player, option, shield_wall_present=state.shield_wall_present
    )
    if option.trigger is not None:
        return bool(sections)
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


def _old_pending_groups(state: GameState, player: int) -> tuple[DomainAction, ...]:
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    actions: list[DomainAction] = []
    if context["pending_agent_effect"] is True and pending_agent_icons(context):
        actions.extend(legal_agent_card_icon_actions(state, player))
        actions.extend(legal_agent_card_recall_actions(state, player))
        actions.extend(legal_agent_card_influence_actions(state, player))
        # 2026-10-06: Tread in Darkness's trash became a choice icon.
        actions.extend(legal_agent_card_trash_actions(state, player))
    elif context["pending_agent_effect"] is True:
        choice_actions = tuple(
            action
            for provider in agent_effect_frame._AGENT_CARD_CHOICE_PROVIDERS
            for action in provider(state, player)
        )
        if choice_actions:
            actions.extend(choice_actions)
        elif not agent_card_effect_is_unavailable(state):
            actions.append(
                DomainAction(action_id="resolve_agent_card_effect", actor=player)
            )
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
    nothing, and the engine skipped the recall unasked."""

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("space_id") != "imperial_privilege" or not board_icon_is_pending(
        context, BOARD_ICON_IMPERIAL_PRIVILEGE
    ):
        return ()
    owner = state.players[player]
    if context.get("imperial_privilege_intrigue_resolved") is not True:
        return (
            DomainAction(action_id="decline_imperial_privilege_intrigue", actor=player),
            *(
                DomainAction(
                    action_id="trash_intrigue_for_imperial_privilege",
                    actor=player,
                    arguments=(("card_id", card_id),),
                )
                for card_id in owner.intrigue_cards
            ),
        )
    conflict = recallable_conflict_agents(
        owner,
        sent_this_turn=turn_agent_in_conflict(owner, context, "imperial_privilege"),
    )
    return (
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
        active_agent_card(context).agent_effect
        is PersonalCardAgentEffect.MAY_RECALL_AGENT_SENT_THIS_TURN
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
    PersonalCardAgentEffect
    .MAY_TRASH_INTRIGUE_FOR_INTRIGUE_AND_TWO_SPICE_IF_BENE_GESSERIT_ALLIANCE
)


def _old_icon_condition_holds(
    owner: PlayerState,
    context: dict[str, Any],
    effect: PersonalCardAgentEffect | None,
    key: str,
) -> bool:
    """``agent_effects.agent_icon_condition_holds`` before ``agent_icon_block``
    (2026-10-02), with the rule changes made on purpose since then."""

    # 2026-10-06 (Steam app comparison): Cargo Runner's two printed lines
    # became two icons, judged at two and four completed contracts.
    if effect is PersonalCardAgentEffect.DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO:
        if key == "cards":
            return len(owner.completed_contract_ids) >= 2
        if key == "cards_second":
            return len(owner.completed_contract_ids) >= 4
    if key == "cards_second":
        return False
    # Stillsuit Manufacturer's water and its Fremen Alliance return.
    stillsuit = (
        effect is PersonalCardAgentEffect.GAIN_WATER_AND_RETURN_SELF_IF_FREMEN_ALLIANCE
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
        effect is PersonalCardAgentEffect.LEADER_SIGNET
        and owner.leader_id == "lady_amber_metulli"
    ):
        if key == "solari":
            return True
        if key == "spice":
            return bool(owner.alliance_faction_ids)
    # Industrial Espionage's grafted Research line became its own icon.
    if key == "research":
        return (
            effect
            is PersonalCardAgentEffect.DRAW_ONE_AND_RESEARCH_AND_SPECIMEN_IF_GRAFTED
            and is_grafted(context)
        )
    # Tread in Darkness's draw became its own icon, judging the Bond.
    if (
        effect
        is PersonalCardAgentEffect.TRASH_PERSONAL_CARD_TO_DRAW_ONE_IF_BENE_GESSERIT_BOND
        and key == "cards"
    ):
        card_id = context.get("card_id")
        return has_faction_bond(
            counted_in_play(owner),
            card_id if isinstance(card_id, str) else "",
            Faction.BENE_GESSERIT,
        )
    if key in (AGENT_ICON_CARDS, AGENT_ICON_TROOPS):
        if effect is (
            PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO
        ):
            return owner.influence.bene_gesserit >= 2
        if effect is (
            PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN
        ):
            return spice_gained_this_turn(owner) >= 2
        if effect is PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_ONE_IF_GRAFTED:
            return is_grafted(context)
        return True
    if key == AGENT_ICON_INTRIGUE:
        return (
            effect is not PersonalCardAgentEffect.DRAW_ONE_AND_INTRIGUE_IF_TWO_MARKERS
            or genetic_markers_reached(owner.research_space) >= 2
        )
    maker_keeper = (
        effect is PersonalCardAgentEffect.GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO
    )
    wheels = (
        effect
        is PersonalCardAgentEffect.GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO
    )
    if key == AGENT_ICON_SOLARI:
        return wheels and owner.influence.emperor >= 2
    if key == AGENT_ICON_SPICE:
        return (
            effect is _BRANCHING_PATH
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
    effect = active_agent_card(context).agent_effect
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
    for effect in (None, *PersonalCardAgentEffect):
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
                            context: dict[str, Any] = (
                                {"graft_card_id": "x"} if grafted else {}
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
    (legal_research_bonus_actions, _old_research_bonus),
    (legal_agent_card_recall_actions, _old_agent_card_recall),
    (legal_agent_card_icon_actions, _old_agent_card_icons),
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
                    assert expected == ()
                    expected = (DomainAction(action_id=confirm, actor=seat),)
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
    delayed = 0
    while state.phase is not GamePhase.FINISHED:
        decision = ENGINE.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = ENGINE.apply(state, resolver.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        legal = ENGINE.legal_actions(state, decision.owner)
        yield state, decision.owner, legal
        choices = [
            action
            for action in legal
            if action.action_id == "agent_turn"
            and dict(action.arguments).get("space_id") == "imperial_privilege"
        ]
        waiting = imperial_privilege_recall_targets(state, decision.owner)
        if not choices and waiting is not None:
            later = [a for a in legal if a.action_id not in _PRIVILEGE_RECALLS]
            if later and delayed < 4:
                choices, delayed = later, delayed + 1
        else:
            delayed = 0
        state = ENGINE.apply(state, rng.choice(choices or legal)).state


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
