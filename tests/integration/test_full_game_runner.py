"""Integration coverage for the full-game random runner."""

from dune_imperium import RulesetConfig
from dune_imperium.core import GamePhase, replay_game
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.endgame import final_standings
from dune_imperium.simulation import run_random_game


def test_random_game_runs_to_finished_and_replays() -> None:
    engine = UprisingRulesEngine()
    result = run_random_game(
        engine,
        RulesetConfig(),
        game_seed=11,
        policy_seed=3011,
    )

    assert result.state.phase is GamePhase.FINISHED
    assert [standing.rank for standing in result.standings] == [1, 2, 3, 4]
    assert result.standings == final_standings(result.state)
    winner = result.standings[0]
    assert winner.victory_points == max(
        player.victory_points for player in result.state.players
    )

    replayed = replay_game(engine, result.replay)
    assert replayed.phase is GamePhase.FINISHED


def test_same_game_and_policy_seeds_reproduce_the_game() -> None:
    engine = UprisingRulesEngine()
    first = run_random_game(engine, RulesetConfig(), 12, 3012)
    second = run_random_game(engine, RulesetConfig(), 12, 3012)

    assert first.replay.expected_state_hash == second.replay.expected_state_hash
    assert first.replay.steps == second.replay.steps
    assert first.standings == second.standings


def test_choam_random_game_runs_to_finished_and_replays() -> None:
    engine = UprisingRulesEngine()
    config = RulesetConfig(choam_module=True)
    result = run_random_game(engine, config, game_seed=13, policy_seed=3013)

    assert result.state.phase is GamePhase.FINISHED
    assert result.replay.ruleset == config
    replay_game(engine, result.replay)
