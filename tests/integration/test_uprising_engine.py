"""Integration coverage for the concrete Uprising rules dispatcher."""

from dune_imperium import RulesetConfig
from dune_imperium.core import (
    GamePhase,
    canonical_state_hash,
    replay_game,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.simulation import run_random_round


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
