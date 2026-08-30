"""Integration coverage for the full-game runners."""

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents import HeuristicAgent, RandomAgent
from dune_imperium.core import GamePhase, replay_game
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.endgame import final_standings
from dune_imperium.simulation import run_policy_game, run_random_game


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


def test_random_game_delegates_to_the_policy_runner() -> None:
    engine = UprisingRulesEngine()
    config = RulesetConfig()
    agents = tuple(RandomAgent(seed=3014 + seat) for seat in range(config.players))

    baseline = run_random_game(engine, config, game_seed=14, policy_seed=3014)
    explicit = run_policy_game(engine, config, game_seed=14, agents=agents)

    assert explicit.replay.steps == baseline.replay.steps
    assert explicit.replay.expected_state_hash == (
        baseline.replay.expected_state_hash
    )


@pytest.mark.parametrize("choam_module", [False, True])
def test_heuristic_game_runs_to_finished_and_replays(choam_module: bool) -> None:
    engine = UprisingRulesEngine()
    config = RulesetConfig(choam_module=choam_module)
    agents = tuple(HeuristicAgent(seed=3015 + seat) for seat in range(config.players))

    result = run_policy_game(engine, config, game_seed=15, agents=agents)

    assert result.state.phase is GamePhase.FINISHED
    assert [standing.rank for standing in result.standings] == [1, 2, 3, 4]
    replayed = replay_game(engine, result.replay)
    assert replayed.phase is GamePhase.FINISHED


@pytest.mark.parametrize("choam_module", [False, True])
def test_leader_draft_game_runs_to_finished_and_replays(choam_module: bool) -> None:
    engine = UprisingRulesEngine()
    config = RulesetConfig(choam_module=choam_module, leader_draft=True)
    agents = tuple(HeuristicAgent(seed=3016 + seat) for seat in range(config.players))

    result = run_policy_game(engine, config, game_seed=17, agents=agents)

    assert result.state.phase is GamePhase.FINISHED
    leaders = tuple(player.leader_id for player in result.state.players)
    assert all(leader is not None for leader in leaders)
    assert set(leaders) <= set(result.state.leader_draft_pool)
    picks = tuple(
        step
        for step in result.replay.steps
        if hasattr(step, "action_id") and step.action_id == "pick_leader"
    )
    assert len(picks) == 4
    replayed = replay_game(engine, result.replay)
    assert replayed.phase is GamePhase.FINISHED
    assert tuple(player.leader_id for player in replayed.players) == leaders


def test_policy_runner_requires_one_agent_per_seat() -> None:
    engine = UprisingRulesEngine()
    config = RulesetConfig()

    with pytest.raises(ValueError, match="one agent per configured seat"):
        run_policy_game(
            engine,
            config,
            game_seed=16,
            agents=(HeuristicAgent(seed=1),),
        )
