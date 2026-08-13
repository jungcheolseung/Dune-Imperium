"""Tests for typed automatic board-space effects."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
    canonical_state_hash,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import board_effects_for, resolve_board_effect
from dune_imperium.rules.effects import (
    DrawImperiumCardsEffect,
    DrawIntrigueCardsEffect,
    GainResourcesEffect,
    RecruitTroopsEffect,
)


def _instance(card_id: str) -> str:
    return next(
        instance_id
        for instance_id in starting_deck_instance_ids(0)
        if f":{card_id}:" in instance_id
    )


def _state(card_id: str, resources: Resources | None = None) -> GameState:
    card = _instance(card_id)
    starting_resources = resources or Resources()
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        players=(
            PlayerState(player_id=0, hand=(card,), resources=starting_resources),
            *(PlayerState(player_id=seat) for seat in range(1, 4)),
        ),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _action_to(
    state: GameState,
    space_id: str,
    cost_option: int | None = None,
) -> DomainAction:
    return next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == space_id
        and (
            cost_option is None
            or dict(action.arguments).get("cost_option") == cost_option
        )
    )


def test_first_resource_board_effects_are_typed() -> None:
    state = _state("diplomacy")

    assert board_effects_for(state, "dutiful_service", 0) == (
        GainResourcesEffect(solari=2),
    )
    assert board_effects_for(state, "deliver_supplies", 0) == (
        GainResourcesEffect(water=1),
    )
    assert board_effects_for(state, "spice_refinery", 1) == (
        GainResourcesEffect(solari=4),
    )


def test_dutiful_service_resolves_board_reward_and_keeps_faction_pending() -> None:
    state = _state("diplomacy")
    placed = apply_agent_action(state, _action_to(state, "dutiful_service")).state

    result = resolve_board_effect(placed)
    context = dict(result.state.decision_stack[-1].context)

    assert result.state.players[0].resources.solari == 2
    assert context["pending_board_effect"] is False
    assert context["pending_faction_influence"] is True
    assert result.events[0].kind == "board_effect_resolved"


def test_spice_refinery_reward_depends_on_already_paid_option() -> None:
    state = _state("signet_ring", Resources(spice=1))
    action = _action_to(state, "spice_refinery", cost_option=1)
    placed = apply_agent_action(state, action).state

    resolved = resolve_board_effect(placed).state

    assert resolved.players[0].resources.spice == 0
    assert resolved.players[0].resources.solari == 4


def test_unimplemented_or_already_resolved_board_effect_is_rejected() -> None:
    state = _state("diplomacy")
    placed = apply_agent_action(state, _action_to(state, "desert_tactics")).state
    before = canonical_state_hash(placed)

    with pytest.raises(NotImplementedError, match="desert_tactics"):
        resolve_board_effect(placed)
    assert canonical_state_hash(placed) == before

    dutiful = apply_agent_action(
        state,
        _action_to(state, "dutiful_service"),
    ).state
    resolved = resolve_board_effect(dutiful).state
    with pytest.raises(ValueError, match="no pending"):
        resolve_board_effect(resolved)


def test_draw_and_recruit_board_effects_are_typed() -> None:
    state = _state("diplomacy")

    assert board_effects_for(state, "fremkit", 0) == (
        DrawImperiumCardsEffect(1),
    )
    assert board_effects_for(state, "assembly_hall", 0) == (
        DrawIntrigueCardsEffect(1),
    )
    assert board_effects_for(state, "research_station", 0) == (
        RecruitTroopsEffect(2),
        DrawImperiumCardsEffect(2),
    )


def test_fremkit_draws_a_card_and_leaves_combat_deployment_pending() -> None:
    state = _state("diplomacy")
    drawn = _instance("dagger")
    owner = replace(state.players[0], deck=(drawn,))
    state = replace(state, players=(owner, *state.players[1:]))
    placed = apply_agent_action(state, _action_to(state, "fremkit")).state

    resolved = resolve_board_effect(placed).state
    context = dict(resolved.decision_stack[-1].context)

    assert resolved.players[0].hand == (drawn,)
    assert resolved.players[0].deck == ()
    assert context["pending_board_effect"] is False
    assert context["pending_combat_deployment"] is True


def test_assembly_hall_draws_hidden_intrigue() -> None:
    state = _state("dagger")
    state = replace(state, intrigue_deck=("intrigue:first", "intrigue:second"))
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state

    resolved = resolve_board_effect(placed).state

    assert resolved.players[0].intrigue_cards == ("intrigue:first",)
    assert resolved.intrigue_deck == ("intrigue:second",)


def test_gather_support_recruits_available_troops_and_finishes_turn() -> None:
    state = _state("dagger")
    placed = apply_agent_action(state, _action_to(state, "gather_support", 0)).state

    resolved = resolve_board_effect(placed).state
    owner = resolved.players[0]
    decision = resolved.decision_stack[-1].decision

    assert owner.troops_supply == 7
    assert owner.troops_garrison == 5
    assert isinstance(decision, PlayerDecision)
    assert decision.owner == 1
