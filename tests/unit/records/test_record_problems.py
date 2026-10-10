"""Suites of judged human positions (records.problems)."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from dune_imperium.cli.records import main
from dune_imperium.core.actions import DomainAction
from dune_imperium.records.problems import (
    Resolved,
    answer,
    build_suite,
    load_suite,
    resolve,
    save_suite,
    summarize,
)
from dune_imperium.records.saves import SavedGame, human_decisions, read_saved_game
from dune_imperium.server.persistence import serialize_step
from dune_imperium.training.policy import without_undo_actions

DATA = Path(__file__).parent / "data"
GAME = "a" * 32


def _text(action: DomainAction) -> dict[str, object]:
    return {"id": action.action_id, "args": dict(action.arguments)}


@pytest.fixture
def game(tmp_path: Path) -> SavedGame:
    """An old-engine record read as a game a person played at seat 0."""

    document = json.loads((DATA / "v135-app_ai-3.json").read_text(encoding="utf-8"))
    document["seats"] = ["human", "app_ai", "app_ai", "app_ai"]
    document["log"] = [{"type": "undo", "seat": 0, "count": 1}]
    path = tmp_path / f"{GAME}.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return read_saved_game(path)


def _rows(
    game: SavedGame, verdicts: list[str]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Judge and confirm rows for the person's first decisions with a choice."""

    judged: list[dict[str, object]] = []
    confirmed: list[dict[str, object]] = []
    decisions = (
        decision
        for decision in human_decisions(game)
        if len(without_undo_actions(decision.legal_actions)) >= 2
        and decision.chosen.action_id != "pick_leader"
    )
    for verdict, decision in zip(verdicts, decisions, strict=False):
        other = next(
            action
            for action in without_undo_actions(decision.legal_actions)
            if action != decision.chosen
        )
        common = {
            "game": GAME[:8],
            "step": decision.recorded_index,
            "round": decision.state.round_number,
            "seat": decision.seat,
            "human": _text(decision.chosen),
        }
        judged.append(
            {
                **common,
                "effect_order": False,
                "values": [[0.0, 0.2], [0.1, 0.2], [0.0, 0.3]],
                "human_col": 1,
            }
        )
        sign = 1 if verdict == "human" else -1
        confirmed.append(
            {
                **common,
                "first": verdict,
                "second": verdict,
                "mean": 0.1 * sign,
                "error": 0.01,
                "p_human": 0.05,
                "net_first": _text(other),
            }
        )
    return judged, confirmed


def test_a_suite_keeps_the_agreed_positions_and_their_record(
    game: SavedGame, tmp_path: Path
) -> None:
    judged, confirmed = _rows(game, ["human", "net", "human"])
    confirmed.append({**confirmed[0], "second": "none"})  # disagreement: left out

    suite = build_suite([game], judged, confirmed, "test")
    path = tmp_path / "suite.json"
    save_suite(path, suite)
    loaded = load_suite(path)

    assert loaded == suite
    assert [p.family for p in loaded.problems] == [
        "human_right",
        "network_right",
        "human_right",
    ]
    record = loaded.records[GAME]
    assert "log" not in record and record["format_version"] == 1
    for problem in loaded.problems:
        recorded = game.parsed.replay.steps[problem.recorded_index]
        assert problem.person == recorded
        assert (problem.right == recorded) == (problem.family == "human_right")


def test_every_position_resolves_on_this_engine(game: SavedGame) -> None:
    judged, confirmed = _rows(game, ["human", "net", "human", "net"])
    suite = build_suite([game], judged, confirmed, "test")

    resolved = resolve(suite)

    assert set(resolved) == {problem.problem_id for problem in suite.problems}
    for problem in suite.problems:
        position = resolved[problem.problem_id]
        assert isinstance(position, Resolved), position
        assert position.right in position.legal and position.wrong in position.legal
        assert position.state.round_number == problem.round_number


def test_a_position_past_a_divergence_or_with_a_lost_move_is_named(
    game: SavedGame,
) -> None:
    judged, confirmed = _rows(game, ["human", "human", "human"])
    suite = build_suite([game], judged, confirmed, "test")
    first, second, third = suite.problems
    record = dict(suite.records[GAME])
    steps = list(record["steps"])
    # The record stops at the second position's own step.
    steps[second.recorded_index] = serialize_step(
        DomainAction(
            action_id="agent_turn",
            actor=0,
            arguments=(("card_id", "nothing"), ("space_id", "nowhere")),
        )
    )
    record["steps"] = steps
    lost = DomainAction(action_id="agent_turn", actor=0, arguments=(("x", 1),))
    broken = replace(
        suite,
        records={GAME: record},
        problems=(replace(first, wrong=lost), second, third),
    )

    resolved = resolve(broken)

    assert "is not legal" in str(resolved[first.problem_id])
    assert "the record stops at step" in str(resolved[second.problem_id])
    assert "the record stops at step" in str(resolved[third.problem_id])


def test_agents_answer_and_the_summary_splits_the_families(game: SavedGame) -> None:
    judged, confirmed = _rows(game, ["human", "net", "human", "net"])
    suite = build_suite([game], judged, confirmed, "test")
    positions = [p for p in resolve(suite).values() if isinstance(p, Resolved)]

    answers = [answer(position, "heuristic") for position in positions]

    assert {item.outcome for item in answers} <= {"right", "wrong", "neither"}
    assert all(item.p_right is None for item in answers)
    summary = summarize(answers)
    assert summary["human_right"]["n"] == 2
    assert summary["network_right"]["n"] == 2
    groups = [name for name in summary if name.startswith("human_right/")]
    assert groups and sum(summary[name]["n"] for name in groups) == 2


def test_a_network_is_scored_by_its_probabilities(
    game: SavedGame, tmp_path: Path
) -> None:
    torch = pytest.importorskip("torch")
    from dune_imperium.adapters.action_codec import ActionCodec
    from dune_imperium.training.checkpoint import save_checkpoint
    from dune_imperium.training.network import PolicyValueNetwork

    config = game.parsed.replay.ruleset
    torch.manual_seed(0)
    network = PolicyValueNetwork(ActionCodec(config).size, hidden=(16,))
    path = tmp_path / "policy.pt"
    save_checkpoint(path, network, ruleset=config.identifier, iteration=1)
    judged, confirmed = _rows(game, ["human", "net"])
    suite = build_suite([game], judged, confirmed, "test")

    for position in resolve(suite).values():
        assert isinstance(position, Resolved)
        result = answer(position, f"checkpoint:{path}")
        assert result.p_right is not None and result.p_wrong is not None
        assert 0.0 < result.p_right + result.p_wrong <= 1.0 + 1e-9
        assert result.pair_share is not None and 0.0 < result.pair_share < 1.0
        assert result.rank_right is not None and result.rank_right >= 1
        # A network's choice is its first: the right move is chosen exactly
        # when it ranks first.
        assert (result.outcome == "right") == (result.rank_right == 1)


def test_the_cli_checks_and_scores_a_suite(
    game: SavedGame, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    judged, confirmed = _rows(game, ["human", "net"])
    path = tmp_path / "suite.json"
    save_suite(path, build_suite([game], judged, confirmed, "test"))

    assert main(["problems", "check", "--suite", str(path)]) == 0
    answers = tmp_path / "answers.json"
    assert (
        main(
            [
                "problems",
                "score",
                "--suite",
                str(path),
                "--agents",
                "random",
                "--json",
                str(answers),
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "2 problems (human_right, network_right), 2 resolve" in out
    assert "## random" in out
    report = json.loads(answers.read_text(encoding="utf-8"))
    assert len(report["random"]["answers"]) == 2
