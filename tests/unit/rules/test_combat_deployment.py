"""Tests for Combat-space troop deployment during an Agent turn."""

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import resolve_board_effect
from dune_imperium.rules.combat_deployment import (
    apply_combat_deployment,
    legal_combat_deployments,
)


def _instance(card_id: str, copy: int = 0) -> str:
    matches = tuple(
        instance_id
        for instance_id in starting_deck_instance_ids(0)
        if f":{card_id}:" in instance_id
    )
    return matches[copy]


def _imperium_instance(card_id: str, copy: int = 0) -> str:
    matches = tuple(
        instance_id
        for instance_id in imperium_deck_instance_ids(False)
        if f":{card_id}:" in instance_id
    )
    return matches[copy]


def _research_station_state() -> GameState:
    reconnaissance = _instance("reconnaissance")
    deck = (_instance("dagger", 0), _instance("dagger", 1))
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(
            PlayerState(
                player_id=0,
                hand=(reconnaissance,),
                deck=deck,
                resources=Resources(water=2),
            ),
            *(PlayerState(player_id=seat) for seat in range(1, 4)),
        ),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _agent_action_to(state: GameState, space_id: str) -> DomainAction:
    return next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == space_id
    )


def _deployment(state: GameState, count: int) -> DomainAction:
    return next(
        action
        for action in legal_combat_deployments(state, 0)
        if dict(action.arguments)["count"] == count
    )


def test_recruited_troops_and_two_existing_troops_may_deploy() -> None:
    state = _research_station_state()
    state = apply_agent_action(
        state,
        _agent_action_to(state, "research_station"),
    ).state
    state = resolve_board_effect(state).state

    assert tuple(
        dict(action.arguments)["count"]
        for action in legal_combat_deployments(state, 0)
    ) == (0, 1, 2, 3, 4)

    deployed = apply_combat_deployment(state, _deployment(state, 4)).state
    owner = deployed.players[0]
    assert owner.troops_garrison == 1
    assert owner.troops_conflict == 4
    assert owner.combat_strength == 0


def test_zero_deployment_is_legal_and_finishes_the_effect_frame() -> None:
    state = _research_station_state()
    state = apply_agent_action(
        state,
        _agent_action_to(state, "research_station"),
    ).state
    state = resolve_board_effect(state).state

    state = apply_combat_deployment(state, _deployment(state, 0)).state

    decision = state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    assert decision.owner == 1
    assert state.players[0].troops_garrison == 5
    assert state.players[0].troops_conflict == 0


def test_noncombat_or_other_player_has_no_deployment_action() -> None:
    state = _research_station_state()

    assert legal_combat_deployments(state, 0) == ()
    assert legal_combat_deployments(state, 1) == ()


def test_deployment_above_the_legal_limit_is_rejected() -> None:
    state = _research_station_state()
    state = apply_agent_action(
        state,
        _agent_action_to(state, "research_station"),
    ).state
    state = resolve_board_effect(state).state
    invalid = DomainAction(
        action_id="deploy_troops",
        actor=0,
        arguments=(("count", 5),),
    )

    with pytest.raises(ValueError, match="not a legal Combat deployment"):
        apply_combat_deployment(state, invalid)


def test_sardaukar_coordination_deploys_only_troops_recruited_this_turn() -> None:
    coordination = _imperium_instance("sardaukar_coordination")
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(
            PlayerState(player_id=0, hand=(coordination,)),
            *(PlayerState(player_id=seat) for seat in range(1, 4)),
        ),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    state = apply_agent_action(
        state,
        _agent_action_to(state, "gather_support"),
    ).state

    assert tuple(
        dict(action.arguments)["count"]
        for action in legal_combat_deployments(state, 0)
    ) == (0,)

    state = resolve_board_effect(state).state
    assert tuple(
        dict(action.arguments)["count"]
        for action in legal_combat_deployments(state, 0)
    ) == (0, 1, 2)

    deployed = apply_combat_deployment(state, _deployment(state, 2)).state
    assert deployed.players[0].troops_garrison == 3
    assert deployed.players[0].troops_conflict == 2
