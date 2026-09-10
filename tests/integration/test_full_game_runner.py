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


def test_the_seeds_that_deadlocked_on_an_unreachable_market_now_finish() -> None:
    # Bloodlines+Tech tournament seed 110 reached a Contract icon whose market
    # held only the Immediate with no Intrigue card to trash, so nothing was
    # takeable, the market was not empty, and the turn had no legal action
    # (OQ-059). The icon is held to the turn's end and fizzles now.
    from dune_imperium.agents.registry import make_agent
    from dune_imperium.evaluation.tournament import tournament_specs

    specs = [
        spec
        for spec in tournament_specs(
            agents=(
                "heuristic",
                "heuristic_untuned",
                "heuristic",
                "heuristic_untuned",
            ),
            games=500,
            start_seed=0,
            rulesets=(True,),
            rotate_leaders=True,
            bloodlines=True,
            tech_module=True,
        )
        if spec.game_seed == 110
    ]
    assert len(specs) == 2

    for spec in specs:
        assert spec.leader_ids is not None
        engine = UprisingRulesEngine(leader_ids=spec.leader_ids)
        agents = tuple(
            make_agent(kind, spec.policy_seed + seat)
            for seat, kind in enumerate(spec.seat_agents)
        )
        result = run_policy_game(engine, spec.config, spec.game_seed, agents)
        assert result.state.phase is GamePhase.FINISHED
        assert replay_game(engine, result.replay).phase is GamePhase.FINISHED
