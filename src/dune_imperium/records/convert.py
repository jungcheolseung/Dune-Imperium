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
steps up to the divergence and is no longer finished. The converted session
log is the live steps alone: an undone step was taken on the recording
engine, which the server would replay it on when it loads the log (records
never read the undo history; the archived original keeps it). Only a save
of this engine whose steps stay as they were keeps its log. The
turn-end fields that count recorded steps (``sealed_steps``,
``open_units``) move with the steps.

A conversion never hides a damaged input (``ConversionError``). A save
already stamped with this engine's versions must reach its own recorded
state hash: the new hash may replace an older engine's only. And every
recorded step must be in the converted record -- up to the divergence of
one that diverges -- or be one the migration dropped by name
(``dropped_steps``, reported with the conversion), so no tail is cut
silently.

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
    position_state,
    resolve,
    suite_from_document,
    suite_text,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.server.persistence import parse_save_document, serialize_step

# Where a converted save says what it was converted from.
CONVERTED_FROM: Final = "converted_from"
# The version stamps a save of this engine has (``parse_save_document``).
_VERSION_FIELDS: Final = ("ruleset_version", "content_version", "action_codec_version")


class ConversionError(ValueError):
    """A record that cannot be converted without hiding what is wrong with it."""


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
    _check_input(document, original, record, stamped)
    converted: dict[str, Any] = dict(document)
    converted.update(
        steps=[serialize_step(step) for step in steps],
        expected_state_hash=stamped.expected_state_hash,
        ruleset_version=stamped.ruleset_version,
        content_version=stamped.content_version,
        action_codec_version=stamped.action_codec_version,
    )
    if "log" in document and not (
        _current(document, stamped) and steps == original.steps
    ):
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


def _current(document: Mapping[str, Any], stamped: GameReplay) -> bool:
    """Whether ``document`` is stamped with this engine's versions."""

    return all(document.get(name) == getattr(stamped, name) for name in _VERSION_FIELDS)


def _check_input(
    document: Mapping[str, Any],
    original: GameReplay,
    record: MigratedRecord,
    stamped: GameReplay,
) -> None:
    """Raise ``ConversionError`` when converting would hide a damaged input."""

    if _current(document, stamped):
        # This engine's own save: it replays to its recorded state or it is
        # damaged (a step cut or changed), never "converted".
        if stamped.expected_state_hash != original.expected_state_hash:
            divergence = record.divergence
            where = (
                ""
                if divergence is None
                else f", stopping at step {divergence.recorded_index}: "
                f"{divergence.reason}"
            )
            raise ConversionError(
                f"a save of this engine (codec v{ACTION_CODEC_VERSION}) does not "
                f"reach its recorded state hash{where}"
            )
    divergence = record.divergence
    reached = len(original.steps) if divergence is None else divergence.recorded_index
    kept = {
        migrated.recorded_index
        for migrated in record.steps
        if migrated.recorded_index is not None
    }
    lost = sorted(set(range(reached)) - kept - set(dropped_steps(record)))
    if lost:
        raise ConversionError(
            f"the converted record lacks recorded steps {lost[:5]}"
            + (" ..." if len(lost) > 5 else "")
            + f" of the {reached} it reached"
        )


def dropped_steps(record: MigratedRecord) -> dict[int, str]:
    """The recorded steps the migration dropped by name, each with its reason.

    A bridge may find a recorded step with no counterpart here (the bridges
    of codecs v143-v154 dropped the old graft switch, refusals the turn's
    end lapses now, and a few more); a migration module that does so lists
    them as ``MigratedRecord.dropped``, and they are reported with the
    conversion. This one has none."""

    return dict(getattr(record, "dropped", ()))


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

# The archive's own files, outside ``originals/`` and ``converted/``, which
# mirror the inputs' paths under the root: no input path can name them.
MANIFESTS: Final = Path("manifests")
SWAP_PLAN: Final = Path("swap-plan.md")


def _digest(data: bytes) -> dict[str, Any]:
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


@dataclass(frozen=True, slots=True)
class _Pending:
    """A file converted in memory, before anything is written."""

    source: Path
    relative: Path
    kind: str
    data: bytes
    codec: Any
    text: str
    entry: dict[str, Any]
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
    path under ``root``. The archive's own files stand outside those two
    mirrors: ``out/manifests/originals.json`` and ``converted.json`` (path,
    sha256, size, codec, and for a converted file its original's sha256 and
    what the conversion did) and ``out/swap-plan.md``, the copies that would
    put the converted files in place. Every file is converted and checked
    before anything is written, so a record that fails
    (``ConversionError``) leaves no archive. Nothing under ``root`` is
    written. ``out`` must not exist yet.
    """

    engine = engine or UprisingRulesEngine()
    if out.exists():
        raise FileExistsError(f"{out} already exists")
    pending: list[_Pending] = []
    seen: set[Path] = set()
    for kind, paths in (("save", saves), ("suite", suites)):
        for path in paths:
            relative = _relative(path, root)
            if relative in seen:
                raise ValueError(f"{relative} is given twice")
            seen.add(relative)
            try:
                pending.append(_convert_file(kind, path, relative, engine, recapture))
            except ValueError as error:
                raise ConversionError(f"{relative}: {error}") from error
    originals: list[dict[str, Any]] = []
    converted_entries: list[dict[str, Any]] = []
    done: list[ConvertedFile] = []
    out.mkdir(parents=True)
    for item in pending:
        original = out / "originals" / item.relative
        converted = out / "converted" / item.relative
        original.parent.mkdir(parents=True, exist_ok=True)
        converted.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item.source, original)
        if original.read_bytes() != item.data:
            raise OSError(f"{item.source} changed while it was converted")
        converted.write_text(item.text, encoding="utf-8")
        common = {"path": str(item.relative), "kind": item.kind}
        originals.append({**common, **_digest(item.data), "codec": item.codec})
        converted_entries.append(
            {
                **common,
                **_digest(converted.read_bytes()),
                "codec": ACTION_CODEC_VERSION,
                "original_sha256": _digest(item.data)["sha256"],
                **item.entry,
            }
        )
        done.append(
            ConvertedFile(
                item.relative,
                original.relative_to(out),
                converted.relative_to(out),
                item.kind,
                item.summary,
            )
        )
    (out / MANIFESTS).mkdir()
    for name, entries in (("originals", originals), ("converted", converted_entries)):
        (out / MANIFESTS / f"{name}.json").write_text(
            json.dumps(
                {"root": str(root), "files": entries}, ensure_ascii=False, indent=1
            )
            + "\n",
            encoding="utf-8",
        )
    (out / SWAP_PLAN).write_text(swap_plan(done, out, root), encoding="utf-8")
    return done


def _convert_file(
    kind: str,
    source: Path,
    relative: Path,
    engine: UprisingRulesEngine,
    recapture: frozenset[str],
) -> _Pending:
    data = source.read_bytes()
    document = json.loads(data.decode("utf-8"))
    if kind == "save":
        text, entry, summary = _convert_save_file(document, engine)
        codec: Any = document.get("action_codec_version")
    else:
        text, entry, summary = _convert_suite_file(document, engine, recapture)
        codec = sorted(
            {record["action_codec_version"] for record in document["records"].values()}
        )
    return _Pending(source, relative, kind, data, codec, text, entry, summary)


def _convert_save_file(
    document: dict[str, Any], engine: UprisingRulesEngine
) -> tuple[str, dict[str, Any], str]:
    converted = convert_save_document(document, engine)
    verify_converted_save(converted.document, engine)
    record = converted.record
    divergence = record.divergence
    outcome = (
        "exact"
        if record.exact
        else "migrated"
        if divergence is None
        else f"diverged at step {divergence.recorded_index}: {divergence.reason}"
    )
    entry = {
        "outcome": outcome,
        "steps": [converted.steps, len(record.steps)],
        "bridges": dict(sorted(record.bridge_counts().items())),
        "dropped": {
            str(index): reason
            for index, reason in sorted(dropped_steps(record).items())
        },
    }
    summary = (
        f"v{converted.codec} {converted.steps} steps -> "
        f"v{ACTION_CODEC_VERSION} {len(record.steps)} steps, {outcome}"
    )
    # Written as the play server writes a save (``SaveStore``).
    text = json.dumps(converted.document, ensure_ascii=False, indent=1)
    return text, entry, summary


def _convert_suite_file(
    document: dict[str, Any], engine: UprisingRulesEngine, recapture: frozenset[str]
) -> tuple[str, dict[str, Any], str]:
    suite = suite_from_document(document)
    converted = convert_suite(suite, engine, recapture=recapture)
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
    return suite_text(converted.suite), entry, summary


def swap_plan(done: Sequence[ConvertedFile], out: Path, root: Path) -> str:
    """The copies that put the converted files of the archive ``out`` in
    place under ``root`` (``out/swap-plan.md``)."""

    try:
        archive = str(out.resolve().relative_to(root.resolve()))
    except ValueError:
        archive = str(out)
    lines = [
        f"# Putting the converted records in place (codec v{ACTION_CODEC_VERSION})",
        "",
        f"Each file under `{archive}/converted/` replaces the file of the same path",
        f"under `{root}`; its original stays in `{archive}/originals/`. The",
        f"sha256 of every file is in `{archive}/{MANIFESTS}/originals.json` and",
        f"`{archive}/{MANIFESTS}/converted.json`. Check the converted files first",
        "(docs/human-records.md), then, from that folder:",
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
