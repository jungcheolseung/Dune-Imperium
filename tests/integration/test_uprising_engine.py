"""Integration coverage for the concrete Uprising rules dispatcher."""

import random

from dune_imperium import RulesetConfig
from dune_imperium.core import (
    GamePhase,
    GameState,
    PlayerDecision,
    canonical_state_hash,
)
from dune_imperium.rules import UprisingRulesEngine


def _play_one_round(game_seed: int, policy_seed: int) -> GameState:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), game_seed)
    policy_rng = random.Random(policy_seed)

    for _ in range(500):
        if state.phase in (GamePhase.ROUND_START, GamePhase.ENDGAME):
            return state
        decision = engine.current_decision(state)
        assert isinstance(decision, PlayerDecision)
        actions = engine.legal_actions(state, decision.owner)
        assert actions
        state = engine.apply(state, policy_rng.choice(actions)).state
    raise AssertionError("one round did not finish within the transition limit")


def test_four_seeded_random_players_finish_one_round() -> None:
    state = _play_one_round(game_seed=0, policy_seed=1000)

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
    first = _play_one_round(game_seed=7, policy_seed=2007)
    second = _play_one_round(game_seed=7, policy_seed=2007)

    assert canonical_state_hash(first) == canonical_state_hash(second)


def test_every_advertised_action_stays_in_the_supported_vertical_slice() -> None:
    for game_seed in range(4):
        state = _play_one_round(game_seed, policy_seed=3000 + game_seed)
        assert state.phase is GamePhase.ROUND_START
