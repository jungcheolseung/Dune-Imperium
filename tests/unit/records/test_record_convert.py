"""Records converted to this engine's codec (records.convert).

At each codec bump every kept record is converted once (user decision
2026-10-28, docs/human-records.md). The older record here is a game of this
engine with its pauses taken out and an older codec stamped on it: the
``pause`` bridge, open to every record, brings it back step for step, so its
conversion must be the game as played here.
"""

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from tests.support.records import (
    older_steps,
    pause_indices,
    played_steps,
    save_document,
)

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.cli.records import main
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.replay import ReplayStep
from dune_imperium.records import convert
from dune_imperium.records.convert import (
    CONVERTED_FROM,
    ConversionError,
    convert_files,
    convert_save_document,
    convert_suite,
    verify_converted_save,
)
from dune_imperium.records.migration import MigratedRecord, migrate_record, walk
from dune_imperium.records.problems import (
    POSITION_DIFFERS,
    HumanProblem,
    Resolved,
    Suite,
    load_suite,
    position_state,
    resolve,
    save_suite,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.server.persistence import deserialize_step, parse_save_document
from dune_imperium.server.sessions import GameSessionManager

ENGINE = UprisingRulesEngine()
SEED = 3
OLDER = ACTION_CODEC_VERSION - 1


@pytest.fixture(scope="module")
def played() -> tuple[ReplayStep, ...]:
    """Two rounds of a heuristic game with every module on, ending on a step
    an older engine recorded too (a pause after the last recorded step has
    no recorded step to bring it back)."""

    steps = played_steps(SEED, rounds=2)
    pauses = set(pause_indices(SEED, steps))
    while len(steps) - 1 in pauses:
        steps = steps[:-1]
    return steps


@pytest.fixture(scope="module")
def older(played: tuple[ReplayStep, ...]) -> tuple[ReplayStep, ...]:
    steps = older_steps(SEED, played)
    assert len(played) - len(steps) >= 4
    return steps


def _steps(document: dict[str, Any]) -> list[ReplayStep]:
    return [
        deserialize_step(item, index) for index, item in enumerate(document["steps"])
    ]


def _older_save(
    played: tuple[ReplayStep, ...], older: tuple[ReplayStep, ...], **extra: Any
) -> dict[str, Any]:
    return save_document(SEED, older, codec=OLDER, reached=played, **extra)


def test_an_older_save_converts_to_the_game_as_this_engine_plays_it(
    played: tuple[ReplayStep, ...], older: tuple[ReplayStep, ...]
) -> None:
    pauses = pause_indices(SEED, played)
    # The seat's unit opened at the older record's step 30; the undo log
    # took back one of its steps.
    log = [
        *_older_save(played, older)["log"],
        {
            "type": "action",
            "action_id": "pass_combat_intrigue",
            "actor": 1,
            "arguments": {},
            "undone": True,
        },
        {"type": "undo", "seat": 1, "count": 1},
    ]
    document = _older_save(
        played,
        older,
        log=log,
        sealed_steps=len(older) - 10,
        open_units=[[0, 30]],
        name="옛 판",
    )

    converted = convert_save_document(document, ENGINE)

    result = converted.document
    assert _steps(result) == list(played)
    assert result["action_codec_version"] == ACTION_CODEC_VERSION
    assert converted.record.bridge_counts() == {"pause": len(pauses)}
    # The play server's load takes it, and it replays here as recorded.
    parse_save_document(result)
    verify_converted_save(result, ENGINE)
    assert migrate_record(parse_save_document(result).replay, ENGINE).exact
    # The live steps alone, with what the converted steps moved.
    assert result["log"] == [{**item, "undone": False} for item in result["steps"]]
    moved = [index for index in range(len(played)) if index not in pauses]
    assert result["open_units"] == [[0, moved[30]]]
    assert result["sealed_steps"] == moved[len(older) - 10]
    assert result[CONVERTED_FROM] == {
        "action_codec_version": OLDER,
        "steps": len(older),
        "expected_state_hash": document["expected_state_hash"],
        "divergence": None,
    }
    # Everything else is as it was.
    for key in ("name", "saved_at", "seats", "game_seed", "policy_seed", "ruleset"):
        assert result[key] == document[key]
    assert document["action_codec_version"] == OLDER  # the input is untouched


def test_a_record_that_diverges_keeps_its_steps_up_to_the_divergence(
    played: tuple[ReplayStep, ...], older: tuple[ReplayStep, ...]
) -> None:
    broken = list(older)
    at = next(
        index
        for index, step in enumerate(broken)
        if isinstance(step, DomainAction) and index > 100
    )
    step = broken[at]
    assert isinstance(step, DomainAction)
    broken[at] = replace(step, arguments=(("nowhere", 1),))
    document = _older_save(played, tuple(broken), finished=True)

    converted = convert_save_document(document, ENGINE)

    divergence = converted.record.divergence
    assert divergence is not None and divergence.recorded_index == at
    result = converted.document
    assert _steps(result) == [migrated.step for migrated in converted.record.steps]
    assert _steps(result) == list(played[: len(_steps(result))])
    assert result["finished"] is False
    assert result[CONVERTED_FROM]["divergence"]["recorded_index"] == at
    verify_converted_save(result, ENGINE)


def _older_record(
    played: tuple[ReplayStep, ...], older: tuple[ReplayStep, ...]
) -> MigratedRecord:
    document = _older_save(played, older)
    return migrate_record(parse_save_document(document, check_versions=False).replay)


def _problem(
    record: MigratedRecord, index: int, *, family: str = "human_right"
) -> HumanProblem:
    """A problem at the older record's step ``index``, judged where this
    engine asks it."""

    state, migrated = next(
        (state, migrated)
        for state, migrated in walk(record)
        if migrated.recorded_index == index
    )
    person = migrated.step
    assert isinstance(person, DomainAction)
    other = next(
        action
        for action in ENGINE.legal_actions(state, person.actor)
        if action != person
    )
    return HumanProblem(
        problem_id=f"game:{index}",
        game="game",
        recorded_index=index,
        seat=person.actor,
        round_number=state.round_number,
        kind=person.action_id,
        family=family,
        right=person if family == "human_right" else other,
        wrong=other if family == "human_right" else person,
        evidence={"note": "test"},
        judged_state=position_state(state),
    )


def _choices(record: MigratedRecord, start: int, count: int) -> list[int]:
    """Recorded indexes of ``count`` decisions with a choice from ``start``."""

    found = []
    for state, migrated in walk(record):
        step = migrated.step
        if (
            migrated.recorded_index is not None
            and migrated.recorded_index >= start
            and isinstance(step, DomainAction)
            and len(ENGINE.legal_actions(state, step.actor)) >= 2
        ):
            found.append(migrated.recorded_index)
        if len(found) == count:
            return found
    raise AssertionError("not enough choices")


def _suite(
    played: tuple[ReplayStep, ...],
    older: tuple[ReplayStep, ...],
    *problems: HumanProblem,
) -> Suite:
    document = save_document(SEED, older, codec=OLDER, reached=played)
    record = {
        "format": "dune-imperium-save",
        "format_version": 1,
        **{
            key: document[key]
            for key in (
                "ruleset",
                "game_seed",
                "policy_seed",
                "seats",
                "steps",
                "expected_state_hash",
                "ruleset_version",
                "content_version",
                "action_codec_version",
                "name",
                "saved_at",
                "source_game_id",
                "finished",
            )
        },
    }
    return Suite(note="test", records={"game": record}, problems=problems)


def test_a_suite_converts_each_problem_to_the_step_its_record_now_asks(
    played: tuple[ReplayStep, ...], older: tuple[ReplayStep, ...]
) -> None:
    record = _older_record(played, older)
    first, second = _choices(record, 150, 2)
    suite = _suite(
        played,
        older,
        _problem(record, first),
        _problem(record, second, family="network_right"),
    )
    before = resolve(suite, ENGINE)

    converted = convert_suite(suite, ENGINE)

    assert not converted.recaptured and not converted.left_out
    stored = converted.suite.records["game"]
    assert stored["action_codec_version"] == ACTION_CODEC_VERSION
    assert stored["format_version"] == 1 and "log" not in stored
    assert _steps(dict(stored)) == list(played)
    pauses = pause_indices(SEED, played)
    moved = [index for index in range(len(played)) if index not in pauses]
    after = resolve(converted.suite, ENGINE)
    for problem in converted.suite.problems:
        original = next(
            item for item in suite.problems if item.problem_id == problem.problem_id
        )
        assert problem.recorded_index == moved[original.recorded_index]
        assert problem.judged_state == original.judged_state
        then, now = before[problem.problem_id], after[problem.problem_id]
        assert isinstance(then, Resolved) and isinstance(now, Resolved)
        assert (now.right, now.wrong, now.legal) == (then.right, then.wrong, then.legal)
        assert (problem.right, problem.wrong) == (then.right, then.wrong)


def test_a_judged_field_named_for_recapture_is_taken_again_and_others_left_out(
    played: tuple[ReplayStep, ...], older: tuple[ReplayStep, ...]
) -> None:
    record = _older_record(played, older)
    first, second, third = _choices(record, 120, 3)
    named, other, kept = (
        _problem(record, first),
        _problem(record, second),
        _problem(record, third),
    )

    def moved(problem: HumanProblem, field: str, value: object) -> HumanProblem:
        judged = json.loads(json.dumps(problem.judged_state))
        judged["players"][problem.seat][field] = value
        return replace(problem, judged_state=judged)

    suite = _suite(
        played,
        older,
        moved(named, "hand_public", ["imperium:not_a_card:0"]),
        moved(other, "solari", 99),
        kept,
    )

    converted = convert_suite(suite, ENGINE, recapture=frozenset({"hand_public"}))

    assert converted.recaptured == (
        (named.problem_id, (f"players[{named.seat}].hand_public",)),
    )
    assert [problem_id for problem_id, _ in converted.left_out] == [other.problem_id]
    assert converted.left_out[0][1].startswith(POSITION_DIFFERS)
    ids = {problem.problem_id for problem in converted.suite.problems}
    assert ids == {named.problem_id, kept.problem_id}
    retaken = next(
        item for item in converted.suite.problems if item.problem_id == named.problem_id
    )
    assert retaken.judged_state == named.judged_state
    assert all(isinstance(item, Resolved) for item in resolve(converted.suite).values())

    # Without the field named nothing is re-captured.
    plain = convert_suite(suite, ENGINE)
    assert not plain.recaptured
    assert {problem_id for problem_id, _ in plain.left_out} == {
        named.problem_id,
        other.problem_id,
    }


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_convert_archives_and_converts_without_writing_outside_its_folder(
    played: tuple[ReplayStep, ...],
    older: tuple[ReplayStep, ...],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "project"
    saves = root / "saves"
    saves.mkdir(parents=True)
    old_save = saves / f"{'a' * 32}.json"
    old_save.write_text(json.dumps(_older_save(played, older)), encoding="utf-8")
    new_save = saves / f"{'b' * 32}.json"
    new_save.write_text(json.dumps(save_document(SEED, played)), encoding="utf-8")
    suite_path = root / "local" / "records" / "suite.json"
    record = _older_record(played, older)
    (first,) = _choices(record, 150, 1)
    save_suite(suite_path, _suite(played, older, _problem(record, first)))
    inputs = {path: _sha(path) for path in (old_save, new_save, suite_path)}
    out = root / "local" / "records-archive" / "today"

    assert (
        main(
            [
                "convert",
                "--out",
                str(out),
                "--saves-dir",
                str(saves),
                "--suite",
                str(suite_path),
                "--root",
                str(root),
            ]
        )
        == 0
    )

    assert {path: _sha(path) for path in inputs} == inputs
    printed = capsys.readouterr().out
    assert f"saves/{'a' * 32}.json: v{OLDER} {len(older)} steps -> " in printed
    assert "1 problems -> 1 (0 re-captured, 0 left out)" in printed
    originals = json.loads((out / "manifests" / "originals.json").read_text())
    converted = json.loads((out / "manifests" / "converted.json").read_text())
    for entry in originals["files"]:
        copy = out / "originals" / entry["path"]
        assert _sha(copy) == entry["sha256"] == inputs[root / entry["path"]]
        assert copy.stat().st_size == entry["size"]
    assert [entry["codec"] for entry in originals["files"]] == [
        OLDER,
        ACTION_CODEC_VERSION,
        [OLDER],
    ]
    for entry in converted["files"]:
        assert _sha(out / "converted" / entry["path"]) == entry["sha256"]
        assert entry["original_sha256"] == inputs[root / entry["path"]]
        assert entry["codec"] == ACTION_CODEC_VERSION
    outcomes = [entry.get("outcome") for entry in converted["files"]]
    assert outcomes == ["migrated", "exact", None]
    assert (
        len(load_suite(out / "converted" / "local" / "records" / "suite.json").problems)
        == 1
    )
    plan = (out / "swap-plan.md").read_text()
    assert f"converted/saves/{'a' * 32}.json' 'saves/{'a' * 32}.json'" in plan
    assert "manifests/originals.json" in plan
    # The mirrors hold the inputs and nothing else.
    for mirror in ("originals", "converted"):
        assert sorted(
            str(path.relative_to(out / mirror))
            for path in (out / mirror).rglob("*")
            if path.is_file()
        ) == sorted(str(path.relative_to(root)) for path in inputs)

    with pytest.raises(SystemExit, match="already exists"):
        main(
            [
                "convert",
                "--out",
                str(out),
                "--saves-dir",
                str(saves),
                "--root",
                str(root),
                "--suite",
                str(suite_path),
            ]
        )


def test_a_converted_save_loads_on_the_play_server(
    played: tuple[ReplayStep, ...], older: tuple[ReplayStep, ...]
) -> None:
    document = _older_save(played, older)
    with pytest.raises(ValueError, match="action_codec_version"):
        GameSessionManager().restore_game(document)

    converted = convert_save_document(document, ENGINE).document
    summary = GameSessionManager().restore_game(json.loads(json.dumps(converted)))

    # The load replays every converted step, its log with no undo, and plays
    # on to the next person's decision.
    assert summary["undo_count"] == 0
    assert isinstance(summary["log_count"], int)
    assert isinstance(summary["round_number"], int)
    assert summary["log_count"] >= len(converted["steps"])
    assert summary["round_number"] >= converted["round_number"]


@pytest.mark.parametrize("damage", ["truncated", "hash"])
def test_a_save_of_this_engine_that_misses_its_own_hash_is_refused(
    played: tuple[ReplayStep, ...], damage: str
) -> None:
    # A save stamped with this engine's versions replays here as recorded or
    # it is damaged; its conversion must not stamp a new hash over that.
    document = save_document(SEED, played)
    if damage == "truncated":
        document["steps"] = document["steps"][:-25]
    else:
        document["expected_state_hash"] = "0" * 64

    with pytest.raises(ConversionError, match="does not reach its recorded state"):
        convert_save_document(document, ENGINE)


def test_a_save_of_this_engine_converts_to_itself(
    played: tuple[ReplayStep, ...],
) -> None:
    log = [
        *save_document(SEED, played)["log"],
        {
            "type": "action",
            "action_id": "pass_combat_intrigue",
            "actor": 1,
            "arguments": {},
            "undone": True,
        },
        {"type": "undo", "seat": 1, "count": 1},
    ]
    document = save_document(SEED, played, log=log)

    result = convert_save_document(document, ENGINE).document

    # Same steps, same hash, and the undo history kept: nothing changed.
    assert {key: value for key, value in result.items() if key != CONVERTED_FROM} == (
        document
    )


def test_a_conversion_that_loses_recorded_steps_fails(
    played: tuple[ReplayStep, ...],
    older: tuple[ReplayStep, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A migration that ended early without a divergence would cut the tail
    # off silently (an older save's hash cannot be rebuilt to catch it).
    real = migrate_record

    def cut(replay: Any, engine: Any = None) -> MigratedRecord:
        record = real(replay, engine)
        return replace(record, steps=record.steps[:-10], walked=None)

    monkeypatch.setattr(convert, "migrate_record", cut)

    with pytest.raises(ConversionError, match="lacks recorded steps"):
        convert_save_document(_older_save(played, older), ENGINE)


def test_a_record_that_fails_leaves_no_archive(
    played: tuple[ReplayStep, ...], older: tuple[ReplayStep, ...], tmp_path: Path
) -> None:
    root = tmp_path / "project"
    (root / "saves").mkdir(parents=True)
    good = root / "saves" / f"{'a' * 32}.json"
    good.write_text(json.dumps(_older_save(played, older)), encoding="utf-8")
    bad = root / "saves" / f"{'b' * 32}.json"
    damaged = save_document(SEED, played)
    damaged["steps"] = damaged["steps"][:-25]
    bad.write_text(json.dumps(damaged), encoding="utf-8")
    out = root / "archive"

    with pytest.raises(ConversionError, match=f"saves/{'b' * 32}.json: "):
        convert_files([good, bad], [], out, root=root, engine=ENGINE)
    assert not out.exists()
    with pytest.raises(ValueError, match="given twice"):
        convert_files([good, good], [], out, root=root, engine=ENGINE)
    assert not out.exists()


def test_inputs_named_like_the_archive_s_own_files_keep_their_bytes(
    played: tuple[ReplayStep, ...], older: tuple[ReplayStep, ...], tmp_path: Path
) -> None:
    # The archive's manifests and plan stand outside the two mirrors, so an
    # input named ``manifest.json`` (or anything else) keeps its copy and its
    # conversion (review finding 2026-10-29).
    root = tmp_path / "project"
    root.mkdir()
    named = [root / "manifest.json", root / "manifests" / "originals.json"]
    for path in named:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_older_save(played, older)), encoding="utf-8")
    sha = {path: _sha(path) for path in named}
    out = root / "archive"

    convert_files(named, [], out, root=root, engine=ENGINE)

    for path in named:
        relative = path.relative_to(root)
        assert _sha(out / "originals" / relative) == sha[path]
        document = json.loads((out / "converted" / relative).read_text())
        verify_converted_save(document, ENGINE)
    originals = json.loads((out / "manifests" / "originals.json").read_text())
    assert [entry["path"] for entry in originals["files"]] == [
        "manifest.json",
        "manifests/originals.json",
    ]
    assert {path.name for path in out.iterdir()} == {
        "originals",
        "converted",
        "manifests",
        "swap-plan.md",
    }
