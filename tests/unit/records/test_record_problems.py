"""Suites of judged human positions (records.problems)."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from dune_imperium.cli.records import main
from dune_imperium.core.actions import DomainAction
from dune_imperium.records.migration import migrate_record, walk
from dune_imperium.records.problems import (
    HumanProblem,
    Resolved,
    answer,
    build_mistake_suite,
    build_suite,
    load_suite,
    merge_suites,
    resolve,
    save_suite,
    summarize,
)
from dune_imperium.records.saves import SavedGame, human_decisions, read_saved_game
from dune_imperium.rules import UprisingRulesEngine
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
    # The person's move is the one the judge saw: the recorded step as the
    # migration replays it (a recorded placement is this engine's space pick
    # once its card is picked, codec v150).
    judged_moves = {row["step"]: row["human"] for row in judged}
    for problem in loaded.problems:
        recorded = game.parsed.replay.steps[problem.recorded_index]
        assert isinstance(recorded, DomainAction)
        assert _text(problem.person) == judged_moves[problem.recorded_index]
        assert problem.person == recorded or (
            recorded.action_id == "agent_turn"
            and problem.person.action_id == "place_agent"
        )
        assert (problem.right == problem.person) == (problem.family == "human_right")


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


def _game_with_human(tmp_path: Path, seat: int) -> SavedGame:
    document = json.loads((DATA / "v135-app_ai-3.json").read_text(encoding="utf-8"))
    document["seats"] = ["app_ai"] * 4
    document["seats"][seat] = "human"
    path = tmp_path / f"{'b' * 32}.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return read_saved_game(path)


def test_a_person_move_a_bridge_rewrote_is_frozen_in_its_migrated_form(
    tmp_path: Path,
) -> None:
    game = _game_with_human(tmp_path, 3)
    recorded = game.parsed.replay.steps
    # A placement's space pick is rewritten too (codec v150); this test is
    # about the box resolution the cleanup bridges rewrite.
    decision = next(
        decision
        for decision in human_decisions(game)
        if decision.chosen != recorded[decision.recorded_index]
        and decision.chosen.action_id != "place_agent"
    )
    assert decision.chosen.action_id == "resolve_agent_card_effect"
    other = next(
        action
        for action in without_undo_actions(decision.legal_actions)
        if action != decision.chosen
    )
    common = {
        "game": "bbbbbbbb",
        "step": decision.recorded_index,
        "round": decision.state.round_number,
        "seat": 3,
        "human": _text(decision.chosen),
    }
    judged = [
        {**common, "effect_order": True, "values": [[0, 1], [0, 1]], "human_col": 1}
    ]
    confirmed = [
        {
            **common,
            "first": "human",
            "second": "human",
            "mean": 0.1,
            "error": 0.01,
            "p_human": 0.1,
            "net_first": _text(other),
        }
    ]

    suite = build_suite([game], judged, confirmed, "test")

    (problem,) = suite.problems
    assert problem.person == decision.chosen
    position = resolve(suite)[problem.problem_id]
    assert isinstance(position, Resolved)
    assert position.right == decision.chosen


def test_a_position_an_engine_change_moved_does_not_resolve(game: SavedGame) -> None:
    judged, confirmed = _rows(game, ["human", "net"])
    suite = build_suite([game], judged, confirmed, "test")
    first, second = suite.problems
    players = [dict(entry) for entry in first.judged_state["players"]]
    players[0]["victory_points"] = "99"
    moved = replace(first, judged_state={**first.judged_state, "players": players})

    resolved = resolve(replace(suite, problems=(moved, second)))

    assert "differs from the judged one: players[0] victory_points 99 then" in str(
        resolved[first.problem_id]
    )
    assert isinstance(resolved[second.problem_id], Resolved)


def test_the_position_state_keeps_every_seat_field_and_ignores_new_ones(
    game: SavedGame,
) -> None:
    judged, confirmed = _rows(game, ["human"])
    suite = build_suite([game], judged, confirmed, "test")
    (problem,) = suite.problems
    seat = problem.judged_state["players"][0]
    # Every field, card zones by their real names (a misspelt list once
    # left the discard pile, cards in play, Intrigue and Contracts out).
    for name in ("discard_pile", "in_play", "intrigue_cards", "commanders_garrison"):
        assert name in seat
    discard = [*seat["discard_pile"], "imperium:not_a_card:0"]

    def with_seat(**fields: object) -> HumanProblem:
        players = [dict(entry) for entry in problem.judged_state["players"]]
        players[0] = {**players[0], **fields}
        return replace(
            problem, judged_state={**problem.judged_state, "players": players}
        )

    def resolves(changed: HumanProblem) -> object:
        return resolve(replace(suite, problems=(changed,)))[problem.problem_id]

    assert "players[0] discard_pile" in str(resolves(with_seat(discard_pile=discard)))
    assert "players[0] retired_field is gone" in str(
        resolves(with_seat(retired_field=1))
    )
    # A snapshot without a field this engine has still matches.
    players = [dict(entry) for entry in problem.judged_state["players"]]
    del players[0]["memories"]
    older = replace(problem, judged_state={**problem.judged_state, "players": players})
    assert isinstance(resolves(older), Resolved)


def test_the_network_move_goes_through_the_rewrite_bridges(tmp_path: Path) -> None:
    from dune_imperium.records.migration import migrate_record, walk
    from dune_imperium.rules import UprisingRulesEngine

    game = _game_with_human(tmp_path, 0)
    engine = UprisingRulesEngine()
    record = migrate_record(game.parsed.replay, engine)
    # A position where one named card effect is offered and the seat did
    # something else: the network's move, judged in old terms, is the
    # argument-less effect.
    for state, migrated in walk(record, engine):
        step = migrated.step
        if not isinstance(step, DomainAction) or migrated.recorded_index is None:
            continue
        named = [
            action
            for action in engine.legal_actions(state, step.actor)
            if action.action_id == "resolve_agent_card_effect" and action.arguments
        ]
        if len(named) == 1 and step.action_id != "resolve_agent_card_effect":
            break
    else:
        pytest.fail("no position with one named card effect in the record")
    seat = step.actor
    document = json.loads(game.path.read_text(encoding="utf-8"))
    document["seats"] = ["app_ai"] * 4
    document["seats"][seat] = "human"
    game.path.write_text(json.dumps(document), encoding="utf-8")
    game = read_saved_game(game.path)
    common = {
        "game": "bbbbbbbb",
        "step": migrated.recorded_index,
        "round": state.round_number,
        "seat": seat,
        "human": _text(step),
    }
    judged = [
        {**common, "effect_order": True, "values": [[0, 1], [0, 1]], "human_col": 1}
    ]
    confirmed = [
        {
            **common,
            "first": "human",
            "second": "human",
            "mean": 0.1,
            "error": 0.01,
            "p_human": 0.1,
            "net_first": {"id": "resolve_agent_card_effect", "args": {}},
        }
    ]
    suite = build_suite([game], judged, confirmed, "test")

    (position,) = resolve(suite).values()

    assert isinstance(position, Resolved), position
    assert position.wrong == named[0]


def test_a_decision_confirmed_twice_is_refused(game: SavedGame) -> None:
    judged, confirmed = _rows(game, ["human"])

    with pytest.raises(ValueError, match="confirmed twice"):
        build_suite([game], judged, confirmed + confirmed, "test")


def test_untrained_network_rows_give_no_probabilities(tmp_path: Path) -> None:
    torch = pytest.importorskip("torch")
    from dune_imperium.adapters.action_codec import ActionCodec
    from dune_imperium.training.checkpoint import save_checkpoint
    from dune_imperium.training.network import PolicyValueNetwork

    # A file trained without Arrakeen Scouts plays a Scouts game: every
    # Scouts row is untrained, and such a decision goes to its heuristic.
    document = json.loads((DATA / "v135-app_ai-3.json").read_text(encoding="utf-8"))
    document["seats"] = ["human"] * 4
    path = tmp_path / f"{GAME}.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    game = read_saved_game(path)
    without = replace(game.parsed.replay.ruleset, arrakeen_scouts=False)
    codec = ActionCodec(without)
    torch.manual_seed(0)
    network = PolicyValueNetwork(codec.size, hidden=(16,))
    policy = tmp_path / "policy.pt"
    save_checkpoint(
        policy, network, ruleset=without.identifier, iteration=1, codec=codec
    )
    decisions = [
        decision
        for decision in human_decisions(game)
        if len(offered := without_undo_actions(decision.legal_actions)) >= 2
        and all(action.action_id.startswith("scouts_") for action in offered)
    ]
    decision = decisions[0]
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
    judged = [
        {**common, "effect_order": False, "values": [[0, 1], [0, 1]], "human_col": 1}
    ]
    confirmed = [
        {
            **common,
            "first": "human",
            "second": "human",
            "mean": 0.1,
            "error": 0.01,
            "p_human": 0.1,
            "net_first": _text(other),
        }
    ]
    suite = build_suite([game], judged, confirmed, "test")
    (position,) = resolve(suite).values()
    assert isinstance(position, Resolved)

    result = answer(position, f"checkpoint:{policy}")

    assert result.p_right is None and result.rank_right is None


def test_a_later_run_is_appended_and_a_game_is_never_frozen_twice(
    game: SavedGame, tmp_path: Path
) -> None:
    judged, confirmed = _rows(game, ["human", "net"])
    first = build_suite([game], judged[:1], confirmed[:1], "run 1")
    # The same game under another id stands for a later game.
    later_id = "b" * 32
    later_path = tmp_path / f"{later_id}.json"
    later_path.write_text(game.path.read_text(encoding="utf-8"), encoding="utf-8")
    later = read_saved_game(later_path)
    rows = [{**row, "game": later_id[:8]} for row in judged[1:]]
    agreed = [{**row, "game": later_id[:8]} for row in confirmed[1:]]
    second = build_suite([later], rows, agreed, "run 2")

    merged = merge_suites(first, second)

    assert merged.note == "run 1; run 2"
    assert set(merged.records) == {GAME, later_id}
    assert [(p.game, p.family) for p in merged.problems] == [
        (GAME, "human_right"),
        (later_id, "network_right"),
    ]
    with pytest.raises(ValueError, match="games already in the suite: aaaaaaaa"):
        merge_suites(merged, first)


def _ai_choices(
    game: SavedGame, seat: int, count: int
) -> list[tuple[int, DomainAction]]:
    """The recorded index and an unplayed alternative of AI decisions."""

    engine = UprisingRulesEngine()
    found: list[tuple[int, DomainAction]] = []
    for state, migrated in walk(migrate_record(game.parsed.replay, engine), engine):
        step = migrated.step
        if (
            migrated.recorded_index is None
            or not isinstance(step, DomainAction)
            or step.actor != seat
            or step.action_id == "pick_leader"
        ):
            continue
        offered = without_undo_actions(engine.legal_actions(state, seat))
        others = [action for action in offered if action != step]
        if others:
            found.append((migrated.recorded_index, others[0]))
        if len(found) == count:
            break
    return found


def test_an_ai_seat_s_mistakes_are_frozen_and_scored_by_kind(
    game: SavedGame, tmp_path: Path
) -> None:
    """The recorded AI move is the wrong one; the summary keeps each kind."""

    choices = _ai_choices(game, seat=1, count=2)
    picks = [
        {
            "game": GAME[:8],
            "step": index,
            "right": _text(right),
            "kind": kind,
            "evidence": {"why": "test"},
        }
        for (index, right), kind in zip(
            choices, ("first_kind", "second_kind"), strict=True
        )
    ]
    suite = build_mistake_suite([game], picks, note="test")
    path = tmp_path / "mistakes.json"
    save_suite(path, suite)
    loaded = load_suite(path)
    assert [problem.family for problem in loaded.problems] == ["ai_mistake"] * 2
    assert {problem.seat for problem in loaded.problems} == {1}

    positions = resolve(loaded)
    for problem, (_, right) in zip(loaded.problems, choices, strict=True):
        position = positions[problem.problem_id]
        assert isinstance(position, Resolved)
        assert position.right == right
        assert position.wrong == problem.person
        assert position.wrong != right
    answers = [
        answer(position, "heuristic")
        for position in positions.values()
        if isinstance(position, Resolved)
    ]
    summary = summarize(answers)
    assert {"ai_mistake", "ai_mistake/first_kind", "ai_mistake/second_kind"} <= set(
        summary
    )

    with pytest.raises(ValueError, match="right is the recorded move"):
        build_mistake_suite(
            [game],
            [{**picks[0], "right": _text(loaded.problems[0].wrong)}],
            note="test",
        )
    with pytest.raises(ValueError, match="picked twice"):
        build_mistake_suite([game], [picks[0], picks[0]], note="test")
