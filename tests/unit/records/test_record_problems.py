"""Suites of judged human positions (records.problems)."""

import json
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path

import pytest

from dune_imperium.cli.records import main
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.replay import ReplayStep
from dune_imperium.core.state import GameState
from dune_imperium.records.migration import migrate_record, walk
from dune_imperium.records.problems import (
    HumanProblem,
    Resolved,
    Suite,
    answer,
    build_mistake_suite,
    build_suite,
    load_suite,
    merge_suites,
    position_state,
    resolve,
    save_suite,
    summarize,
)
from dune_imperium.records.saves import SavedGame, human_decisions, read_saved_game
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import (
    CARD_PICK_ACTION,
    agent_card_pick_actions,
    executable_placements,
)
from dune_imperium.rules.effect_steps import (
    STEP_SPECS,
    TARGET_SPECS,
    first_step,
    path_of,
)
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
        # The leader draft's pick is the window's target row (stage B3d-2a).
        and decision.chosen.action_id != "choose_leader"
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
    # once its card is picked, codec v150; a recorded whole action is the last
    # of its effect and target steps, stage B3, and a window opened for one
    # effect shows its whole action by its target rows, stage B3d-2a).
    judged_moves = {row["step"]: row["human"] for row in judged}
    migrated = {
        step.recorded_index: step.step
        for step in migrate_record(game.parsed.replay).steps
        if step.recorded_index is not None
    }
    for problem in loaded.problems:
        recorded = game.parsed.replay.steps[problem.recorded_index]
        assert isinstance(recorded, DomainAction)
        assert _text(problem.person) == judged_moves[problem.recorded_index]
        assert problem.person == migrated[problem.recorded_index]
        assert problem.person == recorded or (
            recorded.action_id == "agent_turn"
            or recorded.action_id in STEP_SPECS
            or recorded.action_id in TARGET_SPECS
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
    # A placement's space pick and every whole action's last step are
    # rewritten too (codec v150); this test is about the box resolution the
    # cleanup bridge rewrites: step 134, seat 3's Signet Ring resolved with no
    # icon named (``agent_card_effect_named``), which is its solari icon here.
    assert recorded[134] == DomainAction("resolve_agent_card_effect", 3)
    decision = next(
        decision
        for decision in human_decisions(game)
        if decision.recorded_index == 134
    )
    assert decision.chosen == DomainAction(
        "gain",
        3,
        (
            ("icon", "solari"),
            ("printed", "lady_amber_metulli"),
            ("source", "leader"),
        ),
    )
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
    # argument-less effect (a whole action here; the rows it stands for are
    # what the position offers, stage B3).
    for state, migrated in walk(record, engine):
        step = migrated.step
        if not isinstance(step, DomainAction) or migrated.recorded_index is None:
            continue
        named = [
            action
            for action in engine.whole_actions(state, step.actor)
            if action.action_id == "resolve_agent_card_effect" and action.arguments
        ]
        if len(named) == 1 and step not in (path_of(state, named[0]) or ()):
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
    assert position.wrong == first_step(state, named[0])


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
    # A row is untrained when the Scouts catalog holds its template and the
    # file's catalog does not. Since stage B3d-2b the Scouts windows share
    # generic target rows (``choose_count``, ``choose_option``) with other
    # effects, so only a decision whose every row is Scouts-only (a mission
    # or subcommittee window with its decline) is handed to the heuristic.
    scouts_codec = ActionCodec(game.parsed.replay.ruleset)
    held = set(codec.catalog)
    decisions = [
        decision
        for decision in human_decisions(game)
        if len(offered := without_undo_actions(decision.legal_actions)) >= 2
        and all(
            scouts_codec.catalog[scouts_codec.encode(action)] not in held
            for action in offered
        )
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
            or step.action_id == "choose_leader"
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


def _effect_problem(
    tmp_path: Path, same_effect: bool
) -> tuple[Resolved | str, GameState, tuple[DomainAction, ...], DomainAction]:
    """A problem at a recorded whole action with a target (stage B3: the
    migration takes it as its effect step and then its target step), the
    network's move another effect (``same_effect`` False) or the same effect
    with another target. Returns the resolution, the state before the
    effect step, the person's steps and the network's whole action."""

    from dune_imperium.records.migration import migrate_record, walk
    from dune_imperium.rules import UprisingRulesEngine

    for seat in range(4):
        game = _game_with_human(tmp_path, seat)
        engine = UprisingRulesEngine()
        record = migrate_record(game.parsed.replay, engine)
        base: GameState | None = None
        mine: list[DomainAction] = []
        for state, migrated in walk(record, engine):
            step = migrated.step
            if not isinstance(step, DomainAction):
                continue
            if migrated.recorded_index is None and migrated.bridge == "effect_step":
                base = state if not mine else base
                mine.append(step)
                continue
            if (
                migrated.bridge != "effect_last_step"
                or base is None
                or step.actor != seat
            ):
                base, mine = None, []
                continue
            mine.append(step)
            wholes = engine.whole_actions(base, seat)
            for whole in wholes:
                path = path_of(base, whole) or (whole,)
                if path == tuple(mine) or len(path) < 2 and same_effect:
                    continue
                if (path[0] == mine[0]) != same_effect:
                    continue
                assert migrated.recorded_index is not None
                recorded = game.parsed.replay.steps[migrated.recorded_index]
                assert isinstance(recorded, DomainAction)
                common = {
                    "game": "bbbbbbbb",
                    "step": migrated.recorded_index,
                    "round": state.round_number,
                    "seat": seat,
                    "human": _text(recorded),
                }
                judged = [
                    {
                        **common,
                        "effect_order": True,
                        "values": [[0, 1], [0, 1]],
                        "human_col": 1,
                    }
                ]
                confirmed = [
                    {
                        **common,
                        "first": "human",
                        "second": "human",
                        "mean": 0.1,
                        "error": 0.01,
                        "p_human": 0.1,
                        "net_first": _text(whole),
                    }
                ]
                suite = build_suite([game], judged, confirmed, "test")
                (position,) = resolve(suite).values()
                return position, base, tuple(mine), whole
            base, mine = None, []
    pytest.fail("no whole action with a target in the record")


def test_a_problem_at_another_effect_is_asked_before_the_effect_step(
    tmp_path: Path,
) -> None:
    # Stage B3: the person's whole action is its effect and then its target;
    # the network resolving another effect parts from it at the effect, so
    # the position is the decision before the person picked theirs.
    position, base, mine, whole = _effect_problem(tmp_path, same_effect=False)

    assert isinstance(position, Resolved), position
    assert position.state == base
    assert position.right == mine[0]
    assert position.wrong == first_step(base, whole)


def test_a_problem_at_another_target_is_asked_at_the_target_step(
    tmp_path: Path,
) -> None:
    # The same effect with another target parts at the target: asked once the
    # person's effect is picked.
    position, base, mine, whole = _effect_problem(tmp_path, same_effect=True)

    assert isinstance(position, Resolved), position
    assert position.state != base
    assert position.right == mine[-1]
    path = path_of(base, whole)
    assert path is not None and position.wrong == path[len(mine) - 1]


def test_a_problem_at_a_named_reveal_choice_is_asked_before_its_effect_step(
    tmp_path: Path,
) -> None:
    # Stage B3b-2: a record before codec v147 names a Reveal choice's card
    # (``reveal_source_by_order``) and this engine takes the named whole
    # action as its effect steps; the step that ends it stays the
    # ``effect_last_step`` bridge's, so a problem there is asked where the
    # two moves part, before the person picked the effect. Step 830 of this
    # v141 record: seat 2's Calculus of Power trash, beside Shrouded
    # Counsel's.
    from dune_imperium.records.migration import migrate_record, walk
    from dune_imperium.rules import UprisingRulesEngine

    document = json.loads(
        (DATA / "v141-no-immortality-no-go_to_11-heuristic-1211.json").read_text(
            encoding="utf-8"
        )
    )
    document["seats"] = ["heuristic"] * 4
    document["seats"][2] = "human"
    path = tmp_path / f"{'c' * 32}.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    game = read_saved_game(path)
    engine = UprisingRulesEngine()
    record = migrate_record(game.parsed.replay, engine)
    base: GameState | None = None
    mine: list[DomainAction] = []
    for state, migrated in walk(record, engine):
        step = migrated.step
        if migrated.recorded_index is None and migrated.bridge == "effect_step":
            if not mine:
                base = state
            assert isinstance(step, DomainAction)
            mine.append(step)
            continue
        if migrated.recorded_index == 830:
            assert migrated.bridge == "effect_last_step"
            assert migrated.named_by == "reveal_source_by_order"
            assert isinstance(step, DomainAction)
            mine.append(step)
            break
        base, mine = None, []
    assert base is not None and len(mine) == 2
    other = next(
        whole
        for whole in engine.whole_actions(base, 2)
        if whole.action_id == "acquire_reserve"
    )
    recorded = game.parsed.replay.steps[830]
    assert isinstance(recorded, DomainAction)
    common = {
        "game": "c" * 8,
        "step": 830,
        "round": base.round_number,
        "seat": 2,
        "human": _text(recorded),
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
    (position,) = resolve(suite).values()

    assert isinstance(position, Resolved), position
    assert position.state == base
    assert position.right == mine[0]
    assert position.wrong == first_step(base, other)


def _turn_effect_problem(
    tmp_path: Path, network: Callable[[GameState, int], DomainAction]
) -> tuple[Resolved | str, GameState, tuple[DomainAction, ...], DomainAction]:
    """A problem at a whole action the migration takes as steps (a Plot
    Intrigue card: its effect, its card, its option) at a turn where this
    engine also offers the card picks; the network's move is ``network`` of
    the state before the first step and the seat. Returns the resolution,
    that state, the person's steps and the network's move."""

    for seat in range(4):
        game = _game_with_human(tmp_path, seat)
        engine = UprisingRulesEngine()
        record = migrate_record(game.parsed.replay, engine)
        base: GameState | None = None
        mine: list[DomainAction] = []
        for state, migrated in walk(record, engine):
            step = migrated.step
            if not isinstance(step, DomainAction):
                continue
            if migrated.recorded_index is None and migrated.bridge == "effect_step":
                base = state if not mine else base
                mine.append(step)
                continue
            if (
                migrated.bridge != "effect_last_step"
                or base is None
                or step.actor != seat
                or not any(
                    action.action_id == CARD_PICK_ACTION
                    for action in engine.legal_actions(base, seat)
                )
            ):
                base, mine = None, []
                continue
            mine.append(step)
            move = network(base, seat)
            assert migrated.recorded_index is not None
            recorded = game.parsed.replay.steps[migrated.recorded_index]
            assert isinstance(recorded, DomainAction)
            common = {
                "game": "bbbbbbbb",
                "step": migrated.recorded_index,
                "round": state.round_number,
                "seat": seat,
                "human": _text(recorded),
            }
            judged = [
                {
                    **common,
                    "effect_order": True,
                    "values": [[0, 1], [0, 1]],
                    "human_col": 1,
                }
            ]
            confirmed = [
                {
                    **common,
                    "first": "human",
                    "second": "human",
                    "mean": 0.1,
                    "error": 0.01,
                    "p_human": 0.1,
                    "net_first": _text(move),
                }
            ]
            suite = build_suite([game], judged, confirmed, "test")
            (position,) = resolve(suite).values()
            return position, base, tuple(mine), move
    pytest.fail("no whole action taken as steps beside the card picks")


def test_a_placement_against_steps_is_asked_before_the_first_step(
    tmp_path: Path,
) -> None:
    # Codec v150: the person's Plot card is three steps and the network's
    # placement a card pick; the two part at the first step, where the card
    # picks are offered beside it. At the last step only the Plot's option
    # was offered, so the card pick was "not legal" (the Insider Information
    # AI mistakes, found by the Reveal totals cleanup's gate, 2026-10-21).
    position, base, mine, placement = _turn_effect_problem(
        tmp_path, lambda state, seat: executable_placements(state, seat)[0]
    )

    assert isinstance(position, Resolved), position
    assert position.state == base
    assert position.right == mine[0]
    assert (position.wrong,) == agent_card_pick_actions(placement.actor, (placement,))


@pytest.mark.parametrize(
    ("refusal", "reason"),
    [
        ("decline_optional_trash", "turn_row_refusal"),
        ("decline_tech", "optional_refusal"),
    ],
)
def test_a_refusal_this_engine_no_longer_has_is_reported_not_raised(
    tmp_path: Path, refusal: str, reason: str
) -> None:
    # Since codec v149 an in-turn optional trash has no refusal, and since
    # v146 an Agent turn's optional effect (the turn's end lapses it), so a
    # network's refusal names a window this state is not in. It used to stop
    # the whole check with a ValueError, then read "not legal"; it is
    # reported as having no counterpart (c3adefb4:471, fb716981:607).
    position, _, _, _ = _turn_effect_problem(
        tmp_path, lambda state, seat: DomainAction(refusal, seat)
    )

    assert position == (
        f"the network's move {refusal} has no counterpart on this engine ({reason})"
    )


def _record_game(tmp_path: Path, name: str, letter: str) -> SavedGame:
    path = tmp_path / f"{letter * 32}.json"
    path.write_text((DATA / name).read_text(encoding="utf-8"), encoding="utf-8")
    return read_saved_game(path)


def _states(game: SavedGame, engine: UprisingRulesEngine) -> dict[int, GameState]:
    """The state each recorded step was migrated from, by its index."""

    record = migrate_record(game.parsed.replay, engine)
    return {
        migrated.recorded_index: state
        for state, migrated in walk(record, engine)
        if migrated.recorded_index is not None
    }


def _move(steps: Sequence[ReplayStep], index: int) -> DomainAction:
    step = steps[index]
    assert isinstance(step, DomainAction)
    return step


def _hand_problem(
    game: SavedGame,
    index: int,
    state: GameState,
    right: DomainAction,
    wrong: DomainAction,
) -> HumanProblem:
    """A ``human_right`` problem at recorded step ``index``, judged at
    ``state``: built by hand, as ``build_suite`` finds no position at a
    step this engine drops."""

    return HumanProblem(
        problem_id=f"{game.game_id[:8]}:{index}",
        game=game.game_id,
        recorded_index=index,
        seat=right.actor,
        round_number=state.round_number,
        kind="effect_order",
        family="human_right",
        right=right,
        wrong=wrong,
        evidence={},
        judged_state=position_state(state),
    )


def _suite(game: SavedGame, *problems: HumanProblem) -> Suite:
    record = json.loads(game.path.read_text(encoding="utf-8"))
    return Suite(note="test", records={game.game_id: record}, problems=problems)


def test_a_person_s_refusals_and_turn_end_are_asked_at_the_turn_end(
    tmp_path: Path,
) -> None:
    # Before codec v146 an Agent turn's optional effect had a refusal; this
    # engine lapses the effect at the turn's end and the migration drops the
    # refusal (OQ-095 (2)). A person who refused and then ended the turn
    # made one decision here, ending the turn, in the state the refusal was
    # judged in (885ed2f0:578 and :756); so did one who refused two effects
    # in a row. A network's refusal has no single move here.
    engine = UprisingRulesEngine()
    game = _record_game(tmp_path, "v135-app_ai-3.json", "b")
    steps = game.parsed.replay.steps
    before = _states(game, engine)
    refusal, finish = _move(steps, 42), _move(steps, 43)
    assert (refusal.action_id, finish.action_id) == (
        "decline_sardaukar_commander",
        "finish_agent_turn",
    )
    assert [_move(steps, index).action_id for index in (121, 122, 123)] == [
        "decline_tech",
        "decline_sardaukar_commander",
        "finish_agent_turn",
    ]
    seat = refusal.actor
    asked = {42: (before[43], finish), 121: (before[123], _move(steps, 123))}
    other = {
        index: next(
            action for action in engine.whole_actions(state, seat) if action != end
        )
        for index, (state, end) in asked.items()
    }
    problems = (
        _hand_problem(game, 42, before[43], refusal, other[42]),
        # The network's refusal against the person's turn end itself.
        _hand_problem(game, 43, before[43], finish, refusal),
        _hand_problem(game, 121, before[123], _move(steps, 121), other[121]),
    )

    resolved = resolve(_suite(game, *problems), engine)

    for index, (state, end) in asked.items():
        position = resolved[f"{game.game_id[:8]}:{index}"]
        assert isinstance(position, Resolved), position
        assert position.state == state
        assert position.right == end
        assert position.wrong == (
            other[index]
            if other[index] in position.legal
            else first_step(state, other[index])
        )
    assert resolved[problems[1].problem_id] == (
        "the network's move decline_sardaukar_commander has no counterpart on "
        "this engine (optional_refusal)"
    )


def test_a_person_s_refusal_before_another_move_has_no_counterpart(
    tmp_path: Path,
) -> None:
    # A refusal followed by another move left the effect and played on; here
    # the effect stays pending through that move, and no move stands for the
    # refusal.
    engine = UprisingRulesEngine()
    game = _record_game(tmp_path, "v141-random-3038.json", "c")
    steps = game.parsed.replay.steps
    refusal, following = _move(steps, 42), _move(steps, 43)
    assert (refusal.action_id, following.action_id) == (
        "decline_sardaukar_commander",
        "use_family_atomics",
    )
    state = _states(game, engine)[43]
    other = next(
        action
        for action in engine.whole_actions(state, refusal.actor)
        if action != following
    )

    (position,) = resolve(
        _suite(game, _hand_problem(game, 42, state, refusal, other)), engine
    ).values()

    assert position == (
        "the person's move at step 42 has no counterpart on this engine "
        "(optional_refusal)"
    )


def test_a_refusal_this_engine_still_offers_is_asked(tmp_path: Path) -> None:
    # Outside its owner's turn an optional trash keeps its window and its
    # refusal (codec v149, cleanup-2b): Water Discipline, a Scouts card, has a
    # seat trash a card while others draw. A network's
    # ``decline_optional_trash`` there is asked as a move of this engine.
    engine = UprisingRulesEngine()
    game = _record_game(tmp_path, "v141-app_ai-1009.json", "d")
    trash = _move(game.parsed.replay.steps, 259)
    assert trash.action_id == "trash_optional_card"
    state = _states(game, engine)[259]
    decline = DomainAction("decline_optional_trash", trash.actor)

    (position,) = resolve(
        _suite(game, _hand_problem(game, 259, state, trash, decline)), engine
    ).values()

    assert isinstance(position, Resolved), position
    assert position.wrong in position.legal
    assert position.wrong.action_id == "decline"
