"""Tests for Combat-space troop deployment during an Agent turn."""

from dataclasses import replace

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
from dune_imperium.rules.board_effects import (
    legal_board_effect_actions,
    resolve_board_effect,
)
from dune_imperium.rules.combat_deployment import (
    apply_agent_turn_finish,
    apply_combat_deployment,
    apply_troop_withdrawal,
    legal_agent_turn_finish_actions,
    legal_combat_deployments,
    legal_troop_withdrawals,
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
                kind="turn",
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


def _resolve_board_icons(state: GameState) -> GameState:
    """Resolve every pending automatic board icon in printed order."""

    for action in legal_board_effect_actions(state, 0):
        state = resolve_board_effect(state, action).state
    return state


def _deployment(state: GameState, count: int) -> DomainAction:
    return next(
        action
        for action in legal_combat_deployments(state, 0)
        if dict(action.arguments)["count"] == count
    )


def _withdrawal(count: int) -> DomainAction:
    return DomainAction(
        action_id="withdraw_troops", actor=0, arguments=(("count", count),)
    )


def _finish() -> DomainAction:
    return DomainAction(action_id="finish_agent_turn", actor=0)


def _counts(actions: tuple[DomainAction, ...]) -> tuple[int, ...]:
    counts = []
    for action in actions:
        count = dict(action.arguments)["count"]
        assert isinstance(count, int)
        counts.append(count)
    return tuple(counts)


def test_recruited_troops_and_two_existing_troops_may_deploy() -> None:
    state = _research_station_state()
    state = apply_agent_action(
        state,
        _agent_action_to(state, "research_station"),
    ).state
    state = _resolve_board_icons(state)

    # Two recruited troops plus two garrison troops [Main p. 10]; deploying
    # nothing is the explicit turn end rather than a count (OQ-029).
    assert _counts(legal_combat_deployments(state, 0)) == (1, 2, 3, 4)
    assert legal_troop_withdrawals(state, 0) == ()
    assert legal_agent_turn_finish_actions(state, 0) == (_finish(),)

    deployed = apply_combat_deployment(state, _deployment(state, 4)).state
    owner = deployed.players[0]
    assert owner.troops_garrison == 1
    assert owner.troops_conflict == 4
    assert owner.combat_strength == 0
    # The limit is reached; the turn stays open until finished.
    assert legal_combat_deployments(deployed, 0) == ()
    assert _counts(legal_troop_withdrawals(deployed, 0)) == (1, 2, 3, 4)
    assert deployed.decision_stack[-1].kind == "agent_effects"


def test_finishing_without_deploying_hands_the_turn_over() -> None:
    state = _research_station_state()
    state = apply_agent_action(
        state,
        _agent_action_to(state, "research_station"),
    ).state
    state = _resolve_board_icons(state)

    state = apply_agent_turn_finish(state, _finish()).state

    decision = state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    assert decision.owner == 1
    assert state.players[0].troops_garrison == 5
    assert state.players[0].troops_conflict == 0


def test_finish_waits_for_the_other_pending_effects() -> None:
    state = _research_station_state()
    state = apply_agent_action(
        state,
        _agent_action_to(state, "research_station"),
    ).state

    # The card icons of Research Station are still pending: no turn end yet,
    # but deploying the two garrison troops is already possible.
    assert legal_agent_turn_finish_actions(state, 0) == ()
    assert _counts(legal_combat_deployments(state, 0)) == (1, 2)
    with pytest.raises(ValueError, match="cannot be finished"):
        apply_agent_turn_finish(state, _finish())


def test_deployed_troops_may_be_withdrawn_after_a_later_draw() -> None:
    # OQ-029: the deployment is adjustable until the turn ends, so a card
    # drawn after deploying may still change the count.
    state = _research_station_state()
    state = apply_agent_action(
        state,
        _agent_action_to(state, "research_station"),
    ).state
    deployed = apply_combat_deployment(state, _deployment(state, 2)).state
    assert deployed.players[0].troops_conflict == 2

    drawn = _resolve_board_icons(deployed)
    assert drawn.players[0].hand != deployed.players[0].hand
    assert _counts(legal_troop_withdrawals(drawn, 0)) == (1, 2)

    back = apply_troop_withdrawal(drawn, _withdrawal(1)).state
    owner = back.players[0]
    assert owner.troops_conflict == 1
    assert owner.troops_garrison == 4
    assert owner.units_deployed_turn == 1
    assert dict(back.decision_stack[-1].context)["combat_troops_deployed"] == 1

    finished = apply_agent_turn_finish(back, _finish()).state
    decision = finished.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    assert decision.owner == 1
    assert finished.players[0].troops_conflict == 1


def test_deployment_may_be_split_and_the_net_limit_holds() -> None:
    # OQ-029: deploy in parts, and later recruits raise the limit; the net
    # total never exceeds recruited troops plus two garrison troops.
    state = _research_station_state()
    state = apply_agent_action(
        state,
        _agent_action_to(state, "research_station"),
    ).state
    first = apply_combat_deployment(state, _deployment(state, 2)).state
    assert legal_combat_deployments(first, 0) == ()

    recruited = _resolve_board_icons(first)
    assert dict(recruited.decision_stack[-1].context)["troops_recruited"] == 2
    assert _counts(legal_combat_deployments(recruited, 0)) == (1, 2)

    second = apply_combat_deployment(recruited, _deployment(recruited, 1)).state
    assert second.players[0].troops_conflict == 3
    withdrawn = apply_troop_withdrawal(second, _withdrawal(3)).state
    assert withdrawn.players[0].troops_conflict == 0
    assert withdrawn.players[0].units_deployed_turn == 0
    # Back to the full net limit of four.
    assert _counts(legal_combat_deployments(withdrawn, 0)) == (1, 2, 3, 4)
    assert legal_troop_withdrawals(withdrawn, 0) == ()


def test_withdrawal_only_covers_this_turns_basic_deployment() -> None:
    state = _research_station_state()
    seasoned = state.players[0]
    state = replace(
        state,
        players=(
            replace(seasoned, troops_conflict=2, troops_supply=7),
            *state.players[1:],
        ),
    )
    state = apply_agent_action(
        state,
        _agent_action_to(state, "research_station"),
    ).state
    state = _resolve_board_icons(state)
    deployed = apply_combat_deployment(state, _deployment(state, 1)).state

    # Troops already in the Conflict from earlier turns stay there.
    assert deployed.players[0].troops_conflict == 3
    assert _counts(legal_troop_withdrawals(deployed, 0)) == (1,)
    invalid = _withdrawal(2)
    with pytest.raises(ValueError, match="not a legal troop withdrawal"):
        apply_troop_withdrawal(deployed, invalid)


def test_withdrawal_stops_at_a_committed_deployment_count() -> None:
    # OQ-029 exception: an effect that consumed the deployment count as its
    # condition keeps that minimum deployed.
    state = _research_station_state()
    state = apply_agent_action(
        state,
        _agent_action_to(state, "research_station"),
    ).state
    state = _resolve_board_icons(state)
    deployed = apply_combat_deployment(state, _deployment(state, 4)).state
    committed = replace(
        deployed,
        players=(
            replace(deployed.players[0], units_deployed_committed=3),
            *deployed.players[1:],
        ),
    )

    assert _counts(legal_troop_withdrawals(committed, 0)) == (1,)
    back = apply_troop_withdrawal(committed, _withdrawal(1)).state
    assert legal_troop_withdrawals(back, 0) == ()
    assert _counts(legal_combat_deployments(back, 0)) == (1,)


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
    state = _resolve_board_icons(state)
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
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    state = apply_agent_action(
        state,
        _agent_action_to(state, "gather_support"),
    ).state

    assert legal_combat_deployments(state, 0) == ()

    state = _resolve_board_icons(state)
    assert _counts(legal_combat_deployments(state, 0)) == (1, 2)

    deployed = apply_combat_deployment(state, _deployment(state, 2)).state
    assert deployed.players[0].troops_garrison == 3
    assert deployed.players[0].troops_conflict == 2
    assert legal_combat_deployments(deployed, 0) == ()
    assert legal_agent_turn_finish_actions(deployed, 0) == (_finish(),)
