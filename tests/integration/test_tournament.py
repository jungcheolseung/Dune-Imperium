"""Tests for the M9 baseline tournament and its report."""

import json
from pathlib import Path

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents import StateAgent, make_agent
from dune_imperium.cli.tournament import main as tournament_main
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.observation import PlayerView
from dune_imperium.evaluation import (
    MatchSpec,
    play_match,
    render_markdown,
    run_tournament,
    summarize,
    summary_to_json,
    tournament_specs,
)
from dune_imperium.evaluation import tournament as tournament_module
from dune_imperium.evaluation.tournament import (
    _MeteredAgent,
    fill_lineup,
    seat_rotations,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.simulation import runner as runner_module


def test_lineup_fill_and_seat_rotations() -> None:
    assert fill_lineup(("heuristic", "random")) == (
        "heuristic",
        "random",
        "heuristic",
        "random",
    )
    assert fill_lineup(("random",)) == ("random",) * 4
    with pytest.raises(ValueError, match="unknown agent kind"):
        fill_lineup(("oracle",))
    with pytest.raises(ValueError, match="between 1 and 4"):
        fill_lineup(("random",) * 5)

    # A mixed table rotates through four seatings; a uniform table has one,
    # and a two-agent alternating table only two distinct rotations.
    assert len(seat_rotations(("heuristic", "random", "random", "random"))) == 4
    assert seat_rotations(("random",) * 4) == (("random",) * 4,)
    assert seat_rotations(("heuristic", "random", "heuristic", "random")) == (
        ("heuristic", "random", "heuristic", "random"),
        ("random", "heuristic", "random", "heuristic"),
    )


def test_tournament_specs_cross_seeds_rulesets_and_rotations() -> None:
    specs = tournament_specs(
        agents=("heuristic", "random", "random", "random"),
        games=2,
        rulesets=(False, True),
        start_seed=10,
        rotate_leaders=True,
    )

    assert len(specs) == 2 * 2 * 4
    seeds = {spec.game_seed for spec in specs}
    assert seeds == {10, 11}
    # The rotations of one seed share every setup input but the seating.
    same_seed = [
        spec for spec in specs if spec.game_seed == 10 and not spec.choam_module
    ]
    assert len(same_seed) == 4
    assert len({spec.policy_seed for spec in same_seed}) == 1
    assert len({spec.leader_ids for spec in same_seed}) == 1
    assert {spec.seat_agents.index("heuristic") for spec in same_seed} == {0, 1, 2, 3}
    assert {spec.config.identifier for spec in specs} == {
        "uprising-4p-base",
        "uprising-4p-choam",
    }
    unrotated = tournament_specs(agents=("random",), games=3, rotate_seats=False)
    assert len(unrotated) == 3
    assert all(spec.leader_ids is None for spec in unrotated)
    with pytest.raises(ValueError, match="at least one game"):
        tournament_specs(agents=("random",), games=0)


def test_play_match_meters_every_seat() -> None:
    spec = MatchSpec(
        game_seed=3,
        policy_seed=900_003,
        seat_agents=("heuristic", "random", "random", "random"),
    )

    result = play_match(spec)

    assert result.ruleset == "uprising-4p-base"
    assert result.rounds >= 1
    assert result.steps > 100
    assert 0 <= result.first_player < 4
    assert sorted(seat.rank for seat in result.seats) == [1, 2, 3, 4]
    assert result.winner.rank == 1
    assert tuple(seat.agent for seat in result.seats) == spec.seat_agents
    assert all(seat.leader_id for seat in result.seats)
    assert all(seat.decisions > 0 for seat in result.seats)
    assert all(seat.illegal_actions == 0 for seat in result.seats)
    assert all(seat.decision_seconds >= 0.0 for seat in result.seats)

    # The same spec reproduces the same standings and decision counts.
    again = play_match(spec)
    assert [(s.rank, s.victory_points, s.decisions) for s in again.seats] == [
        (s.rank, s.victory_points, s.decisions) for s in result.seats
    ]


class _AlwaysIllegal:
    def choose_action(
        self,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        return DomainAction(action_id="not_a_real_action", actor=observation.player)


def test_metered_agent_counts_and_repairs_illegal_choices() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), 1)
    decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    view = engine.observe(state, decision.owner)
    legal = engine.legal_actions(state, decision.owner)

    metered = _MeteredAgent(make_agent("random", 1))
    assert metered.choose_action(view, legal) in legal
    assert metered.decisions == 1
    assert metered.illegal_actions == 0
    assert metered.seconds >= 0.0

    broken = _MeteredAgent(_AlwaysIllegal())
    assert broken.choose_action(view, legal) == legal[0]
    assert broken.illegal_actions == 1
    assert broken.decisions == 1


def test_run_tournament_summary_and_report(tmp_path: Path) -> None:
    specs = tournament_specs(
        agents=("heuristic", "random"),
        games=1,
        start_seed=5,
        rotate_leaders=True,
    )
    report = run_tournament(specs)

    assert not report.failures
    assert len(report.matches) == len(specs) == 2
    summary = summarize(report)
    assert summary.matches == 2
    assert summary.failures == 0
    assert summary.rulesets == ("uprising-4p-base",)
    assert [agent.agent for agent in summary.agents] == ["heuristic", "random"]
    assert sum(agent.games for agent in summary.agents) == 8
    assert sum(agent.wins for agent in summary.agents) == 2
    assert sum(agent.first_player_games for agent in summary.agents) == 2
    for agent in summary.agents:
        assert agent.games == 4
        assert 1.0 <= agent.mean_rank <= 4.0
        assert agent.illegal_actions == 0
        assert agent.decisions > 0
        assert agent.mean_decision_ms >= 0.0
        # Two rotations put each agent in every seat once.
        assert [seat.seat for seat in agent.seats] == [0, 1, 2, 3]
        assert all(seat.games == 1 for seat in agent.seats)
        assert sum(leader.games for leader in agent.leaders) == 4
    # VP margins are zero-sum within a table, so the agents' totals cancel.
    total_margin = sum(agent.mean_vp_margin * agent.games for agent in summary.agents)
    assert abs(total_margin) < 1e-9

    document = summary_to_json(summary)
    json.dumps(document)
    assert document["agents"][0]["win_rate"] == summary.agents[0].win_rate
    markdown = render_markdown(summary)
    assert "| heuristic |" in markdown
    assert "## Leaders" in markdown

    written = tmp_path / "out" / "summary.json"
    report_path = tmp_path / "out" / "report.md"
    exit_code = tournament_main(
        [
            "--agents",
            "random",
            "--games",
            "1",
            "--start-seed",
            "7",
            "--json",
            str(written),
            "--markdown",
            str(report_path),
        ]
    )
    assert exit_code == 0
    loaded = json.loads(written.read_text())
    assert loaded["matches"] == 1
    assert loaded["agents"][0]["agent"] == "random"
    assert report_path.read_text().startswith("# Tournament report")


def test_cli_rejects_unknown_agents() -> None:
    with pytest.raises(SystemExit):
        tournament_main(["--agents", "oracle", "--games", "1"])


class _CountingProtocolCheck(type):
    """Stand in for ``StateAgent`` and count the isinstance() calls."""

    checks: int

    def __instancecheck__(cls, instance: object) -> bool:
        cls.checks += 1
        return isinstance(instance, StateAgent)


def test_the_state_agent_protocol_is_asked_per_seat_not_per_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``StateAgent`` is a runtime-checkable Protocol, so one isinstance()
    against it walks the members through ``inspect.getattr_static`` -- about
    5us. Asking once per decision charged that to every agent's metered
    decision time, which is what the 2026-09-10 baseline saw when heuristic
    (0.005 -> 0.010 ms) and random (0.001 -> 0.006 ms) each gained the same
    +0.005 ms. Seating cannot change mid-game, so the answer is asked once.
    """

    class _Counted(metaclass=_CountingProtocolCheck):
        checks = 0

    monkeypatch.setattr(runner_module, "StateAgent", _Counted)
    monkeypatch.setattr(tournament_module, "StateAgent", _Counted)

    result = play_match(
        MatchSpec(
            game_seed=3,
            policy_seed=900_003,
            seat_agents=("heuristic", "random", "random", "random"),
        )
    )

    decisions = sum(seat.decisions for seat in result.seats)
    assert decisions > 100, "the match must really have made many decisions"
    # Two call sites -- the runner's seating and the metered wrapper -- ask
    # once per seat each, and nothing scales with the decision count.
    assert _Counted.checks == 2 * len(result.seats)
