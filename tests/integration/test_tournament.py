"""Tests for the M9 baseline tournament and its report."""

import json
import os
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
    match_rows,
    play_match,
    render_markdown,
    run_tournament,
    summarize,
    summary_to_json,
    tournament_specs,
)
from dune_imperium.evaluation import tournament as tournament_module
from dune_imperium.evaluation.tournament import (
    TournamentReport,
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


def test_tournament_specs_seat_checkpoint_and_search_seats_with_scouts() -> None:
    # Design D6 (user decision 2026-09-30): trained seats may play Arrakeen
    # Scouts; the policy head is moved onto the Scouts catalog when the
    # match builds its agents, so the specs no longer refuse them.
    for kind in ("checkpoint:/nonexistent.pt", "search:/nonexistent.pt"):
        specs = tournament_specs(
            agents=(kind, "random", "random", "random"),
            games=1,
            arrakeen_scouts=True,
        )
        assert all(spec.arrakeen_scouts for spec in specs)
        assert all(spec.config.arrakeen_scouts for spec in specs)
        assert any(spec.seat_agents[0] == kind for spec in specs)


def test_a_checkpoint_seat_plays_a_whole_arrakeen_scouts_match(
    tmp_path: Path,
) -> None:
    torch = pytest.importorskip("torch")
    from dune_imperium.adapters.action_codec import ActionCodec
    from dune_imperium.training.checkpoint import save_checkpoint
    from dune_imperium.training.network import PolicyValueNetwork

    # A file trained without Scouts, as every checkpoint so far is.
    base = RulesetConfig()
    codec = ActionCodec(base)
    torch.manual_seed(0)
    path = tmp_path / "policy.pt"
    save_checkpoint(
        path,
        PolicyValueNetwork(codec.size, hidden=(32,)),
        ruleset=base.identifier,
        iteration=1,
        codec=codec,
    )
    kind = f"checkpoint:{path}"

    result = play_match(
        MatchSpec(
            game_seed=6,
            policy_seed=1,
            seat_agents=(kind, "heuristic", "heuristic", "heuristic"),
            arrakeen_scouts=True,
        )
    )

    assert result.ruleset == "uprising-4p-base+scouts"
    assert result.seats[0].agent == kind
    assert result.seats[0].decisions > 0
    assert result.seats[0].illegal_actions == 0


def test_tournament_specs_rejects_go_to_11_without_immortality() -> None:
    with pytest.raises(ValueError, match="Go to 11 variant requires the Immortality"):
        tournament_specs(agents=("random",), games=1, go_to_11=True)


def test_tournament_specs_forwards_go_to_11() -> None:
    specs = tournament_specs(
        agents=("random",), games=1, immortality=True, go_to_11=True
    )

    assert specs
    assert all(spec.go_to_11 for spec in specs)
    assert all(spec.config.go_to_11 for spec in specs)
    assert all(
        spec.config.identifier == "uprising-4p-base+immortality+go11"
        for spec in specs
    )


def test_go_to_11_match_runs_to_finished() -> None:
    spec = MatchSpec(
        game_seed=3,
        policy_seed=900_003,
        seat_agents=("random", "random", "random", "random"),
        immortality=True,
        go_to_11=True,
    )

    result = play_match(spec)

    assert result.ruleset == "uprising-4p-base+immortality+go11"
    assert result.rounds >= 1
    assert sorted(seat.rank for seat in result.seats) == [1, 2, 3, 4]


def test_tournament_specs_forwards_epic_game() -> None:
    # An independent option (OQ-092): nothing else needs to be on.
    specs = tournament_specs(agents=("random",), games=1, epic_game=True)

    assert specs
    assert all(spec.epic_game for spec in specs)
    assert all(spec.config.epic_game for spec in specs)
    assert all(spec.config.identifier == "uprising-4p-base+epic" for spec in specs)


def test_epic_game_match_runs_to_finished() -> None:
    spec = MatchSpec(
        game_seed=3,
        policy_seed=900_003,
        seat_agents=("random", "random", "random", "random"),
        epic_game=True,
    )

    result = play_match(spec)

    assert result.ruleset == "uprising-4p-base+epic"
    assert result.rounds >= 1
    assert sorted(seat.rank for seat in result.seats) == [1, 2, 3, 4]


def test_tournament_specs_forward_the_leader_draft() -> None:
    specs = tournament_specs(agents=("app_ai", "heuristic"), games=2, leader_draft=True)

    assert specs
    assert all(spec.leader_draft and spec.config.leader_draft for spec in specs)
    # The draft deals its own pool, so no fixed roster rides along.
    assert all(spec.leader_ids is None for spec in specs)
    with pytest.raises(ValueError, match="rotate_leaders cannot be combined"):
        tournament_specs(
            agents=("random",), games=1, leader_draft=True, rotate_leaders=True
        )


def test_a_drafted_match_seats_the_leaders_its_agents_picked() -> None:
    seed = 5
    pool = UprisingRulesEngine().reset(
        RulesetConfig(leader_draft=True), seed
    ).leader_draft_pool
    spec = MatchSpec(
        game_seed=seed,
        policy_seed=900_000 + seed,
        seat_agents=("app_ai", "heuristic", "random", "app_ai_easy"),
        leader_draft=True,
    )

    result = play_match(spec)

    assert result.leader_draft
    # The identifier leaves the draft out; the result carries it instead.
    assert result.ruleset == "uprising-4p-base"
    leaders = [seat.leader_id for seat in result.seats]
    assert len(set(leaders)) == 4
    assert set(leaders) <= set(pool)
    assert sorted(seat.rank for seat in result.seats) == [1, 2, 3, 4]
    assert all(seat.illegal_actions == 0 for seat in result.seats)
    summary = summarize(TournamentReport((result,), (), 0.0))
    assert summary.rulesets == ("uprising-4p-base (leader draft)",)


def test_cli_plays_a_leader_draft_and_marks_its_rows(tmp_path: Path) -> None:
    written = tmp_path / "matches.jsonl"

    exit_code = tournament_main(
        [
            "--agents",
            "app_ai,random",
            "--games",
            "1",
            "--leader-draft",
            "--matches",
            str(written),
        ]
    )

    assert exit_code == 0
    rows = [json.loads(line) for line in written.read_text().splitlines()]
    assert len(rows) == 2
    assert all(row["leader_draft"] for row in rows)
    assert all(len({seat["leader_id"] for seat in row["seats"]}) == 4 for row in rows)


def test_cli_rejects_leader_draft_with_rotated_leaders() -> None:
    with pytest.raises(SystemExit) as excinfo:
        tournament_main(
            [
                "--agents",
                "random",
                "--games",
                "1",
                "--leader-draft",
                "--rotate-leaders",
            ]
        )

    assert excinfo.value.code == 2


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


def test_match_rows_keep_the_pairing_the_summary_collapses(tmp_path: Path) -> None:
    """One row per match, carrying the seed and every seat's rank and VP.

    The summary reports a win rate per agent; a paired comparison needs the
    per-match outcomes, because rotations of one seed share their Leaders,
    decks and first player (tournament module docstring).
    """

    specs = tournament_specs(
        agents=("heuristic", "random"),
        games=2,
        start_seed=11,
        rotate_leaders=True,
    )
    report = run_tournament(specs)
    rows = match_rows(report)

    assert len(rows) == len(report.matches) == 4
    json.dumps(rows)
    seeds = sorted({row["game_seed"] for row in rows})
    assert seeds == [11, 12]
    for row in rows:
        assert row["ruleset"] == "uprising-4p-base"
        assert row["rounds"] > 0
        assert len(row["seats"]) == 4
        # Exactly one winner, and the four ranks are a permutation of 1-4.
        assert sorted(seat["rank"] for seat in row["seats"]) == [1, 2, 3, 4]
        assert {seat["agent"] for seat in row["seats"]} == {"heuristic", "random"}
        assert all(seat["victory_points"] >= 0 for seat in row["seats"])
    # The rows reproduce the summary's win counts exactly.
    summary = summarize(report)
    wins = {agent.agent: agent.wins for agent in summary.agents}
    from_rows: dict[str, int] = {}
    for row in rows:
        for seat in row["seats"]:
            if seat["rank"] == 1:
                from_rows[seat["agent"]] = from_rows.get(seat["agent"], 0) + 1
    assert from_rows == {name: count for name, count in wins.items() if count}

    written = tmp_path / "out" / "matches.jsonl"
    exit_code = tournament_main(
        [
            "--agents",
            "random",
            "--games",
            "1",
            "--start-seed",
            "7",
            "--matches",
            str(written),
        ]
    )
    assert exit_code == 0
    lines = written.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["game_seed"] == 7


def test_cli_rejects_unknown_agents() -> None:
    with pytest.raises(SystemExit):
        tournament_main(["--agents", "oracle", "--games", "1"])


def test_cli_rejects_go_to_11_without_immortality() -> None:
    with pytest.raises(SystemExit) as excinfo:
        tournament_main(["--agents", "random", "--games", "1", "--go-to-11"])

    assert excinfo.value.code == 2


def test_cli_accepts_go_to_11_with_immortality(tmp_path: Path) -> None:
    written = tmp_path / "matches.jsonl"

    exit_code = tournament_main(
        [
            "--agents",
            "random",
            "--games",
            "1",
            "--immortality",
            "--go-to-11",
            "--matches",
            str(written),
        ]
    )

    assert exit_code == 0
    # The match rows record the ruleset the games actually ran under, which
    # catches a --go-to-11 flag the CLI parses but drops before it reaches
    # tournament_specs (the identifier would then lack "+go11").
    lines = written.read_text().splitlines()
    assert lines
    assert all(
        json.loads(line)["ruleset"] == "uprising-4p-base+immortality+go11"
        for line in lines
    )


def test_cli_accepts_epic_alone(tmp_path: Path) -> None:
    written = tmp_path / "matches.jsonl"

    exit_code = tournament_main(
        ["--agents", "random", "--games", "1", "--epic", "--matches", str(written)]
    )

    assert exit_code == 0
    # The match rows record the ruleset the games actually ran under, which
    # catches an --epic flag the CLI parses but drops before it reaches
    # tournament_specs (the identifier would then lack "+epic").
    lines = written.read_text().splitlines()
    assert lines
    assert all(
        json.loads(line)["ruleset"] == "uprising-4p-base+epic" for line in lines
    )


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


def _thread_variables() -> dict[str, str | None]:
    return {name: os.environ.get(name) for name in tournament_module._THREAD_VARIABLES}


def _restore(saved: dict[str, str | None]) -> None:
    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def test_tournament_workers_are_held_to_one_compute_thread() -> None:
    # Eight workers with torch's default 24-thread pool each ran a checkpoint
    # table at 205 ms per decision against 9 ms with one thread each
    # (2026-09-18), so the pool initializer caps every worker.
    saved = _thread_variables()
    try:
        for name in saved:
            os.environ.pop(name, None)
        tournament_module._single_threaded_worker()
        assert _thread_variables() == dict.fromkeys(saved, "1")

        # A thread count the caller exported is respected.
        os.environ["OMP_NUM_THREADS"] = "4"
        os.environ.pop("MKL_NUM_THREADS", None)
        tournament_module._single_threaded_worker()
        assert os.environ["OMP_NUM_THREADS"] == "4"
        assert "MKL_NUM_THREADS" not in os.environ
    finally:
        _restore(saved)


def test_an_already_imported_torch_is_capped_in_a_worker() -> None:
    torch = pytest.importorskip("torch")
    saved = _thread_variables()
    before = torch.get_num_threads()
    try:
        for name in saved:
            os.environ.pop(name, None)
        torch.set_num_threads(max(2, before))
        tournament_module._single_threaded_worker()
        assert torch.get_num_threads() == 1
    finally:
        torch.set_num_threads(before)
        _restore(saved)


def test_run_tournament_plays_across_worker_processes() -> None:
    specs = tournament_specs(agents=("random",), games=2, start_seed=3)
    serial = run_tournament(specs)
    parallel = run_tournament(specs, workers=2)

    assert not parallel.failures

    def outcome(report: TournamentReport) -> list[tuple[int, int, tuple[int, ...]]]:
        return [
            (match.game_seed, match.steps, tuple(seat.rank for seat in match.seats))
            for match in report.matches
        ]

    assert outcome(parallel) == outcome(serial)

