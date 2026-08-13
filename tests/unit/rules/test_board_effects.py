"""Tests for typed automatic board-space effects."""

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
from dune_imperium.rules.effects import GainResourcesEffect


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
    placed = apply_agent_action(state, _action_to(state, "fremkit")).state
    before = canonical_state_hash(placed)

    with pytest.raises(NotImplementedError, match="fremkit"):
        resolve_board_effect(placed)
    assert canonical_state_hash(placed) == before

    dutiful = apply_agent_action(
        state,
        _action_to(state, "dutiful_service"),
    ).state
    resolved = resolve_board_effect(dutiful).state
    with pytest.raises(ValueError, match="no pending"):
        resolve_board_effect(resolved)
