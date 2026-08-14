"""Integration coverage for the concrete Uprising rules dispatcher."""

from dune_imperium import RulesetConfig
from dune_imperium.core import (
    GamePhase,
    PlayerDecision,
    canonical_state_hash,
    replay_game,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.simulation import run_random_round


def test_agent_effect_resolution_cannot_start_a_second_agent_turn() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=2)
    decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    first_player = decision.owner
    agent_action = next(
        action
        for action in engine.legal_actions(state, first_player)
        if action.action_id == "agent_turn"
    )

    state = engine.apply(state, agent_action).state
    effect_action_ids = {
        action.action_id for action in engine.legal_actions(state, first_player)
    }

    assert "agent_turn" not in effect_action_ids
    assert "reveal_turn" not in effect_action_ids
    assert state.players[first_player].agents_available == 1


def test_reveal_resolution_cannot_start_another_turn() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=2)
    decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    reveal = next(
        action
        for action in engine.legal_actions(state, decision.owner)
        if action.action_id == "reveal_turn"
    )

    state = engine.apply(state, reveal).state
    reveal_action_ids = {
        action.action_id for action in engine.legal_actions(state, decision.owner)
    }

    assert "agent_turn" not in reveal_action_ids
    assert "reveal_turn" not in reveal_action_ids
    assert "finish_reveal" in reveal_action_ids


def test_assembly_hall_is_playable_and_draws_intrigue() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=2)
    decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    assembly_hall = next(
        action
        for action in engine.legal_actions(state, decision.owner)
        if dict(action.arguments).get("space_id") == "assembly_hall"
    )
    intrigue_card = state.intrigue_deck[0]

    state = engine.apply(state, assembly_hall).state
    resolve = engine.legal_actions(state, decision.owner)
    assert tuple(action.action_id for action in resolve) == ("resolve_board_effect",)
    state = engine.apply(state, resolve[0]).state

    assert intrigue_card in state.players[decision.owner].intrigue_cards


def test_four_seeded_random_players_finish_one_round() -> None:
    result = run_random_round(
        UprisingRulesEngine(),
        RulesetConfig(),
        game_seed=0,
        policy_seed=1000,
    )
    state = result.state

    assert state.phase is GamePhase.ROUND_START
    assert state.round_number == 1
    assert not state.decision_stack
    assert all(not player.has_revealed for player in state.players)
    assert all(player.agents_available == 2 for player in state.players)
    assert all(player.combat_strength == 0 for player in state.players)
    event_kinds = {event.kind for event in state.event_log}
    assert {
        "agent_placed",
        "reveal_finished",
        "combat_cleaned_up",
        "agents_recalled",
    } <= event_kinds


def test_same_game_and_policy_seeds_reproduce_the_round() -> None:
    engine = UprisingRulesEngine()
    first = run_random_round(engine, RulesetConfig(), 7, 2007)
    second = run_random_round(engine, RulesetConfig(), 7, 2007)

    assert canonical_state_hash(first.state) == canonical_state_hash(second.state)
    assert first.replay.steps == second.replay.steps
    assert replay_game(engine, first.replay) == first.state


def test_every_advertised_action_stays_in_the_supported_vertical_slice() -> None:
    for game_seed in range(4):
        result = run_random_round(
            UprisingRulesEngine(),
            RulesetConfig(),
            game_seed,
            policy_seed=3000 + game_seed,
        )
        assert result.state.phase is GamePhase.ROUND_START
