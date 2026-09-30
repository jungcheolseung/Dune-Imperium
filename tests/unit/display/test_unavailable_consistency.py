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
``intrigue_play_block``, ``agent_box_is_waiting``).
``test_the_refactored_providers_offer_what_they_did`` pins that refactor
against copies of the providers as they were before it (2026-09-29): a later
rule change to one of them should update or drop the copy on purpose.
"""

import json
import random
import re
from collections.abc import Callable, Iterator
from typing import Any, cast

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.determinize import determinize
from dune_imperium.content.immortality.board import genetic_markers_reached
from dune_imperium.content.immortality.tleilaxu import (
    RECLAIMED_FORCES,
    tleilaxu_card_for_instance,
)
from dune_imperium.content.uprising.board import Faction
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
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.player import PlayerState
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
    agent_card_effect_is_unavailable,
    legal_agent_card_icon_actions,
    legal_agent_card_influence_actions,
    legal_agent_card_recall_actions,
)
from dune_imperium.rules.board_effects import legal_board_effect_actions
from dune_imperium.rules.combat_deployment import undeployable_troops_this_turn
from dune_imperium.rules.contract_tiles import contract_reveal_is_possible
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
    agent_turn_space_id,
    current_agent_effect_context,
    pending_agent_icons,
)
from dune_imperium.rules.frames import FrameKind, owned_top_frame
from dune_imperium.rules.influence import influence_amount
from dune_imperium.rules.intrigue import PLOT_FRAME_KINDS, legal_intrigue_play_actions
from dune_imperium.rules.leader_abilities import units_deployment_blocked
from dune_imperium.rules.reveal_turn import current_reveal_context
from dune_imperium.rules.tleilaxu_row import (
    RECLAIMED_FORCES_CHOICES,
    legal_tleilaxu_acquisitions,
)

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
        return bool(sections) and all(
            contract_reveal_is_possible(state, reward)
            for section in option.sections
            for reward in section.rewards
            if isinstance(reward, RevealContractsTakeOne)
        )
    return (
        bool(sections)
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
            if option.timing is not timing:
                continue
            if option.turn_start_only and frame.kind != FrameKind.TURN:
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
            waiting = agent_box_is_waiting(state, seat)
            assert waiting == _old_agent_box_waits(state, seat), step
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
