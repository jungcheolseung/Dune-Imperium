"""Convert kept records to this engine's codec, once at each codec bump.

User decision 2026-10-28 (docs/human-records.md): instead of keeping a
bridge for every codec a record has crossed, every kept record -- the
people's saves, the human problem suites, the tests' records -- is
converted to the current action codec once, its original is archived where
no code reads it, and ``records.migration`` keeps at most the one bridge
from the previous codec to the current one.

A save converts through ``migrate_record``: its steps become the migrated
steps (the bridged ones included, a rewritten one in its new form) and it
is stamped with this engine's versions and the state hash they reach, so
the play server's strict ``parse_save_document`` takes it and the record
replays here exactly. A record that ends in a ``Divergence`` keeps its
steps up to the divergence and is no longer finished. The converted
session log is the live steps alone: an undone step was taken on the
recording engine and has no counterpart here (records never read the undo
history; the archived original keeps it). The turn-end fields that count
recorded steps (``sealed_steps``, ``open_units``) move with the steps.

A suite converts by resolving its problems on this engine
(``records.problems.resolve``) and freezing each position where its record,
converted, now asks it: the problem's recorded index becomes that converted
step's and its two moves are the ones resolved there, so the converted
suite resolves without any bridge. A problem whose position was reached
with other seat fields than it was judged with is re-captured at the
position this engine reaches only when every differing field is one named
in ``recapture`` (a rule change the user decided, such as OQ-145's
``hand_public``); any other such problem is left out and reported.
"""

import hashlib
import json
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.replay import GameReplay, replay_game
from dune_imperium.core.state import GamePhase, canonical_state_hash
from dune_imperium.records.migration import MigratedRecord, migrate_record, walk
from dune_imperium.records.problems import (
    POSITION_DIFFERS,
    HumanProblem,
    Resolved,
    Suite,
    judged_differences,
    load_suite,
    position_state,
    resolve,
    save_suite,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.server.persistence import parse_save_document, serialize_step

# Where a converted save says what it was converted from.
CONVERTED_FROM: Final = "converted_from"


@dataclass(frozen=True, slots=True)
class ConvertedSave:
    """One save document converted to this engine's codec."""

    document: dict[str, Any]
    record: MigratedRecord
    # The original's action codec and number of steps.
    codec: int
    steps: int


def _first_at(record: MigratedRecord, recorded: int) -> list[int]:
    """For each recorded index 0..``recorded``, where the converted steps of
    that recorded step and every later one begin (the converted step count
    when none is left): a recorded count such as ``sealed_steps`` then
    counts the bridged steps in front of the next recorded step too."""

    end = len(record.steps)
    first = [end] * (recorded + 1)
    for position, migrated in enumerate(record.steps):
        index = migrated.recorded_index
        if index is not None and first[index] == end:
            first[index] = position
    for index in range(recorded - 1, -1, -1):
        first[index] = min(first[index], first[index + 1])
    return first


def convert_save_document(
    document: Mapping[str, Any], engine: UprisingRulesEngine | None = None
) -> ConvertedSave:
    """``document`` (a save of any engine) converted to this engine's codec.

    Every other field stays as it was: the seats, seeds, name, save time,
    pace and clock. ``round_number``, ``phase`` and ``finished`` are read
    off the converted state when the document has them.
    """

    engine = engine or UprisingRulesEngine()
    parsed = parse_save_document(dict(document), check_versions=False)
    original = parsed.replay
    record = migrate_record(original, engine)
    steps = tuple(migrated.step for migrated in record.steps)
    state = record.state
    stamped = GameReplay(
        ruleset=original.ruleset,
        seed=original.seed,
        steps=steps,
        expected_state_hash=canonical_state_hash(state),
        action_codec_version=ACTION_CODEC_VERSION,
    )
    converted: dict[str, Any] = dict(document)
    converted.update(
        steps=[serialize_step(step) for step in steps],
        expected_state_hash=stamped.expected_state_hash,
        ruleset_version=stamped.ruleset_version,
        content_version=stamped.content_version,
        action_codec_version=stamped.action_codec_version,
    )
    if "log" in document:
        converted["log"] = [{**serialize_step(step), "undone": False} for step in steps]
    if "round_number" in document:
        converted["round_number"] = state.round_number
    if "phase" in document:
        converted["phase"] = str(state.phase)
    if "finished" in document:
        converted["finished"] = state.phase is GamePhase.FINISHED
    first = _first_at(record, len(original.steps))
    if isinstance(document.get("sealed_steps"), int):
        converted["sealed_steps"] = first[min(document["sealed_steps"], len(first) - 1)]
    if isinstance(document.get("open_units"), list):
        converted["open_units"] = [
            [seat, first[min(opened, len(first) - 1)]]
            for seat, opened in document["open_units"]
            if first[min(opened, len(first) - 1)] < len(steps)
        ]
    divergence = record.divergence
    converted[CONVERTED_FROM] = {
        "action_codec_version": original.action_codec_version,
        "steps": len(original.steps),
        "expected_state_hash": original.expected_state_hash,
        "divergence": None
        if divergence is None
        else {"recorded_index": divergence.recorded_index, "reason": divergence.reason},
    }
    return ConvertedSave(
        converted, record, original.action_codec_version, len(original.steps)
    )


def verify_converted_save(
    document: Mapping[str, Any], engine: UprisingRulesEngine | None = None
) -> None:
    """Raise unless ``document`` loads as the play server loads a save (its
    versions this build's, ``parse_save_document``) and replays here to its
    state hash with no bridge."""

    engine = engine or UprisingRulesEngine()
    replay = parse_save_document(dict(document)).replay
    replay_game(engine, replay)
    record = migrate_record(replay, engine)
    if not record.exact:
        raise ValueError("the converted record does not replay exactly")


@dataclass(frozen=True, slots=True)
class ConvertedSuite:
    """A suite converted to this engine's codec, with what that took."""

    suite: Suite
    # The problems re-captured at this engine's position, each with the
    # fields that had moved.
    recaptured: tuple[tuple[str, tuple[str, ...]], ...]
    # The problems left out, each with why.
    left_out: tuple[tuple[str, str], ...]


def _person(problem: HumanProblem, position: Resolved) -> DomainAction:
    return position.right if problem.family == "human_right" else position.wrong


def _where(problem: HumanProblem, position: Resolved, record: MigratedRecord) -> int:
    """The converted step that is the person's move at ``position``: the one
    taken from that very state (by its hash), nearest the problem's own
    recorded step."""

    person = _person(problem, position)
    wanted = canonical_state_hash(position.state)
    found = [
        index
        for index, (state, migrated) in enumerate(walk(record))
        if migrated.step == person and canonical_state_hash(state) == wanted
    ]
    if not found:
        raise ValueError(f"{problem.problem_id}: no converted step asks its position")
    near = next(
        (
            index
            for index, migrated in enumerate(record.steps)
            if migrated.recorded_index == problem.recorded_index
        ),
        0,
    )
    return min(found, key=lambda index: abs(index - near))


def convert_suite(
    suite: Suite,
    engine: UprisingRulesEngine | None = None,
    *,
    recapture: frozenset[str] = frozenset(),
) -> ConvertedSuite:
    """``suite`` with its records and problems at this engine's codec.

    The converted suite is checked before it is returned: every problem in
    it resolves to the very position, moves and legal actions it resolved to
    before (``ValueError`` otherwise).
    """

    engine = engine or UprisingRulesEngine()
    first = resolve(suite, engine)
    positions: dict[str, Resolved] = {
        problem_id: item
        for problem_id, item in first.items()
        if isinstance(item, Resolved)
    }
    judged: dict[str, Mapping[str, Any]] = {}
    recaptured: list[tuple[str, tuple[str, ...]]] = []
    left_out: list[tuple[str, str]] = []
    moved = [
        problem
        for problem in suite.problems
        if isinstance(first[problem.problem_id], str)
        and str(first[problem.problem_id]).startswith(POSITION_DIFFERS)
    ]
    again: dict[str, Resolved | str] = (
        resolve(
            replace(
                suite,
                problems=tuple(replace(item, judged_state={}) for item in moved),
            ),
            engine,
        )
        if recapture and moved
        else {}
    )
    for problem in suite.problems:
        item = first[problem.problem_id]
        if isinstance(item, Resolved):
            judged[problem.problem_id] = problem.judged_state
            continue
        retaken = again.get(problem.problem_id)
        fields = (
            judged_differences(problem.judged_state, retaken.state)
            if isinstance(retaken, Resolved)
            else ()
        )
        if (
            isinstance(retaken, Resolved)
            and fields
            and all(field.rsplit(".", 1)[-1] in recapture for field in fields)
        ):
            positions[problem.problem_id] = retaken
            judged[problem.problem_id] = position_state(retaken.state)
            recaptured.append((problem.problem_id, fields))
            continue
        left_out.append((problem.problem_id, str(item)))
    records: dict[str, Mapping[str, Any]] = {}
    migrated: dict[str, MigratedRecord] = {}
    for game, record_document in suite.records.items():
        converted = convert_save_document(record_document, engine)
        records[game] = {key: converted.document[key] for key in record_document}
        migrated[game] = converted.record
    problems = tuple(
        replace(
            problem,
            recorded_index=_where(
                problem, positions[problem.problem_id], migrated[problem.game]
            ),
            right=positions[problem.problem_id].right,
            wrong=positions[problem.problem_id].wrong,
            judged_state=judged[problem.problem_id],
        )
        for problem in suite.problems
        if problem.problem_id in positions
    )
    converted_suite = Suite(
        note=suite.note,
        records={game: records[game] for game in suite.records},
        problems=tuple(
            sorted(problems, key=lambda item: (item.game, item.recorded_index))
        ),
    )
    _check_same_positions(converted_suite, positions, engine)
    return ConvertedSuite(converted_suite, tuple(recaptured), tuple(left_out))


def _check_same_positions(
    suite: Suite, positions: Mapping[str, Resolved], engine: UprisingRulesEngine
) -> None:
    after = resolve(suite, engine)
    for problem in suite.problems:
        before = positions[problem.problem_id]
        now = after[problem.problem_id]
        if not isinstance(now, Resolved):
            raise ValueError(f"{problem.problem_id} no longer resolves: {now}")
        if canonical_state_hash(now.state) != canonical_state_hash(before.state) or (
            now.right,
            now.wrong,
            now.legal,
        ) != (before.right, before.wrong, before.legal):
            raise ValueError(f"{problem.problem_id} resolves to another position")


# --- files -------------------------------------------------------------------


def _digest(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


def _relative(path: Path, root: Path) -> Path:
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError:
        raise ValueError(f"{path} is not inside {root}") from None


@dataclass(frozen=True, slots=True)
class ConvertedFile:
    """One file converted into an archive folder."""

    # The file's path under the project root, and where its original copy
    # and its converted file are under the archive folder.
    path: Path
    original: Path
    converted: Path
    kind: str
    # A line per save or suite for the report.
    summary: str


def convert_files(
    saves: Sequence[Path],
    suites: Sequence[Path],
    out: Path,
    *,
    root: Path,
    recapture: frozenset[str] = frozenset(),
    engine: UprisingRulesEngine | None = None,
) -> list[ConvertedFile]:
    """Archive and convert ``saves`` and ``suites`` into ``out``.

    ``out/originals/<path>`` is a byte copy of each file and
    ``out/converted/<path>`` its conversion, ``<path>`` being the file's
    path under ``root``; each folder has a ``manifest.json`` (path, sha256,
    size, codec, and for a converted file its original's sha256 and what
    the conversion did), and ``out/swap-plan.md`` lists the copies that
    would put the converted files in place. Nothing under ``root`` is
    written. ``out`` must not exist yet.
    """

    engine = engine or UprisingRulesEngine()
    if out.exists():
        raise FileExistsError(f"{out} already exists")
    # Every input reads before anything is written.
    for path in saves:
        _relative(path, root)
        parse_save_document(
            json.loads(path.read_text(encoding="utf-8")), check_versions=False
        )
    for path in suites:
        _relative(path, root)
        load_suite(path)
    out.mkdir(parents=True)
    originals: list[dict[str, Any]] = []
    converted_entries: list[dict[str, Any]] = []
    done: list[ConvertedFile] = []
    for kind, paths in (("save", saves), ("suite", suites)):
        for path in paths:
            relative = _relative(path, root)
            original = out / "originals" / relative
            converted = out / "converted" / relative
            original.parent.mkdir(parents=True, exist_ok=True)
            converted.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, original)
            if _digest(original) != _digest(path):
                raise OSError(f"the copy of {path} differs from it")
            document = json.loads(original.read_text(encoding="utf-8"))
            if kind == "save":
                entry, summary = _convert_save_file(document, converted, engine)
                codecs: Any = document.get("action_codec_version")
            else:
                entry, summary = _convert_suite_file(
                    original, converted, engine, recapture
                )
                codecs = sorted(
                    {
                        record["action_codec_version"]
                        for record in document["records"].values()
                    }
                )
            originals.append(
                {
                    "path": str(relative),
                    "kind": kind,
                    **_digest(original),
                    "codec": codecs,
                }
            )
            converted_entries.append(
                {
                    "path": str(relative),
                    "kind": kind,
                    **_digest(converted),
                    "codec": ACTION_CODEC_VERSION,
                    "original_sha256": _digest(original)["sha256"],
                    **entry,
                }
            )
            done.append(
                ConvertedFile(
                    relative,
                    original.relative_to(out),
                    converted.relative_to(out),
                    kind,
                    summary,
                )
            )
    for folder, entries in (("originals", originals), ("converted", converted_entries)):
        (out / folder).mkdir(exist_ok=True)
        (out / folder / "manifest.json").write_text(
            json.dumps(
                {"root": str(root), "files": entries}, ensure_ascii=False, indent=1
            )
            + "\n",
            encoding="utf-8",
        )
    (out / "swap-plan.md").write_text(_swap_plan(done, out, root), encoding="utf-8")
    return done


def _convert_save_file(
    document: dict[str, Any], target: Path, engine: UprisingRulesEngine
) -> tuple[dict[str, Any], str]:
    converted = convert_save_document(document, engine)
    verify_converted_save(converted.document, engine)
    # Written as the play server writes a save (``SaveStore``).
    target.write_text(
        json.dumps(converted.document, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    record = converted.record
    divergence = record.divergence
    outcome = (
        "exact"
        if record.exact
        else "migrated"
        if divergence is None
        else f"diverged at step {divergence.recorded_index}: {divergence.reason}"
    )
    bridges = dict(sorted(record.bridge_counts().items()))
    entry = {
        "outcome": outcome,
        "steps": [converted.steps, len(record.steps)],
        "bridges": bridges,
    }
    summary = (
        f"v{converted.codec} {converted.steps} steps -> "
        f"v{ACTION_CODEC_VERSION} {len(record.steps)} steps, {outcome}"
    )
    return entry, summary


def _convert_suite_file(
    source: Path, target: Path, engine: UprisingRulesEngine, recapture: frozenset[str]
) -> tuple[dict[str, Any], str]:
    suite = load_suite(source)
    converted = convert_suite(suite, engine, recapture=recapture)
    save_suite(target, converted.suite)
    entry = {
        "problems": [len(suite.problems), len(converted.suite.problems)],
        "recaptured": {
            problem_id: list(fields) for problem_id, fields in converted.recaptured
        },
        "left_out": dict(converted.left_out),
    }
    summary = (
        f"{len(suite.problems)} problems -> {len(converted.suite.problems)} "
        f"({len(converted.recaptured)} re-captured, "
        f"{len(converted.left_out)} left out)"
    )
    return entry, summary


def _swap_plan(done: Sequence[ConvertedFile], out: Path, root: Path) -> str:
    try:
        archive = str(out.resolve().relative_to(root.resolve()))
    except ValueError:
        archive = str(out)
    lines = [
        f"# Putting the converted records in place (codec v{ACTION_CODEC_VERSION})",
        "",
        f"Each file under `{archive}/converted/` replaces the file of the same path",
        f"under `{root}`; its original stays in `{archive}/originals/` (both",
        "`manifest.json` files have the sha256 of every file). Check the converted",
        "files first (docs/human-records.md), then, from that folder:",
        "",
        "```bash",
        f"cd '{root}'",
    ]
    lines += [f"cp '{archive}/{item.converted}' '{item.path}'" for item in done]
    lines += [
        "```",
        "",
        "| file | kind | conversion |",
        "|---|---|---|",
    ]
    lines += [f"| `{item.path}` | {item.kind} | {item.summary} |" for item in done]
    return "\n".join(lines) + "\n"
