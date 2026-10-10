"""``records.corpus.check`` and ``dune-imperium-records corpus check``.

The tiny corpus (conftest) was played by this engine, so it checks exact.
The other cases edit a copy of it: a record's trace (a digest altered at a
step, at reset, or a vector dropped where a bridge now runs a step the
recording engine ran inside another), its steps (one taken out, one made
illegal) and its index keys (a synthetic ``around`` hit). Nothing here plays
a game beyond the fixture's four.
"""

import hashlib
import json
import shutil
import struct
from collections.abc import Callable, Mapping
from compression import zstd
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from dune_imperium.cli.records import main
from dune_imperium.records.corpus import (
    Corpus,
    DifferingRun,
    RecordCheck,
    check,
    judge,
    load_migration,
    seatless,
)
from dune_imperium.records.migration import migrate_record, walk
from dune_imperium.records.portable.trace import (
    TraceWriter,
    trace_header,
    trace_payloads,
)
from dune_imperium.rules import UprisingRulesEngine

GARBAGE = b"\xde\xad\xbe\xef"
RECORD = "full.h4.1"

# A migration module with a ``follows`` bridge (records-v142's Imperial
# Privilege draw is the real one): this engine "splits" recorded step AT
# off the step before it, and the bridge runs it right after that step, as
# the recording engine did inside it.
FOLLOWS_MODULE = '''\
"""Test migration: a follows bridge re-adds one split-off step."""

from dataclasses import replace

from dune_imperium.records import migration as base
from dune_imperium.server.persistence import deserialize_step

AT = {at}
STEP = deserialize_step({step!r}, AT)
walk = base.walk


def migrate_record(replay, engine=None):
    steps = list(replay.steps)
    steps.insert(AT, STEP)
    full = base.migrate_record(replace(replay, steps=tuple(steps)), engine)
    migrated = []
    for item in full.steps:
        index = item.recorded_index
        if index == AT:
            migrated.append(base.MigratedStep(item.step, None, "split_follow"))
        elif index is not None and index > AT:
            migrated.append(base.MigratedStep(item.step, index - 1, item.bridge))
        else:
            migrated.append(item)
    return base.MigratedRecord(replay, tuple(migrated), full.state, full.divergence)
'''


def _copy(tiny_corpus: Path, tmp_path: Path) -> Path:
    copy = tmp_path / "root" / tiny_corpus.name
    shutil.copytree(tiny_corpus, copy)
    return copy


def _vectors(corpus: Corpus, record_id: str) -> list[list[bytes]]:
    """The record's trace as one digest vector per point, editable."""

    return [list(vector) for vector in corpus.trace(corpus.row(record_id)).vectors()]


def _steps(corpus: Corpus, record_id: str) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = corpus.document(corpus.row(record_id))["steps"]
    return steps


def _field(corpus: Corpus, name: str) -> int:
    index: int = corpus.manifest["fingerprint_fields"].index(name)
    return index


def _rewrite(
    copy: Path,
    record_id: str,
    *,
    steps: list[dict[str, Any]] | None = None,
    vectors: list[list[bytes]] | None = None,
    keys: Mapping[str, list[Any]] | None = None,
) -> None:
    """Replace a record's steps, trace vectors or (added) index keys."""

    corpus = Corpus.open(copy)
    row = corpus.row(record_id)
    manifest_path = copy / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    (shard,) = [item for item in manifest["shards"] if item["stem"] == row.shard]

    def update(part: str, edit: Callable[[bytes], bytes]) -> None:
        path = corpus.shard_path(row.shard, part)
        data = zstd.compress(edit(zstd.decompress(path.read_bytes())))
        path.write_bytes(data)
        shard["sha256"][part] = hashlib.sha256(data).hexdigest()

    def edit_records(data: bytes) -> bytes:
        lines = data.splitlines()
        document = json.loads(lines[row.line])
        document["steps"] = steps
        lines[row.line] = json.dumps(document, separators=(",", ":")).encode()
        return b"".join(line + b"\n" for line in lines)

    def edit_index(data: bytes) -> bytes:
        rows = [json.loads(line) for line in data.splitlines() if line]
        for item in rows:
            if item["id"] == record_id:
                if steps is not None:
                    item["steps"] = len(steps)
                item["keys"] = {**item["keys"], **(keys or {})}
        return "".join(json.dumps(item) + "\n" for item in rows).encode()

    def edit_trace(data: bytes) -> bytes:
        assert vectors is not None
        field_count, payloads = trace_payloads(data)
        writer = TraceWriter(vectors[0])
        for vector in vectors[1:]:
            writer.step(vector)
        payloads[row.line] = writer.to_bytes()[4:]
        return trace_header(field_count) + b"".join(
            struct.pack("<I", len(payload)) + payload for payload in payloads
        )

    if steps is not None:
        update("records", edit_records)
    if steps is not None or keys is not None:
        update("index", edit_index)
    if vectors is not None:
        update("trace", edit_trace)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def _one(corpus: Corpus, record_id: str = RECORD, **options: Any) -> RecordCheck:
    report = check(corpus, [corpus.row(record_id)], **options)
    (result,) = report.records
    return result


def _split(corpus: Corpus, tmp_path: Path) -> tuple[Path, int]:
    """Make RECORD a record of an engine that ran step ``at`` inside the one
    before it; return a migration module whose follows bridge splits it off
    again, and ``at``."""

    steps = _steps(corpus, RECORD)
    vectors = _vectors(corpus, RECORD)
    at = next(
        index
        for index, step in enumerate(steps)
        if index > 40
        and step["type"] == "action"
        and vectors[index] != vectors[index + 1]
    )
    module = tmp_path / "follows_migration.py"
    module.write_text(FOLLOWS_MODULE.format(at=at, step=steps[at]), encoding="utf-8")
    _rewrite(
        corpus.path,
        RECORD,
        steps=steps[:at] + steps[at + 1 :],
        vectors=vectors[:at] + vectors[at + 1 :],
    )
    return module, at


def test_the_tiny_corpus_checks_exact(
    tiny_corpus: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    corpus = Corpus.open(tiny_corpus)
    report = check(corpus, corpus.pick(), around=["draws:*"])
    assert report.outcomes() == {
        "exact": 4,
        "equal": 0,
        "transient": 0,
        "persistent": 0,
        "diverged": 0,
        "failed": 0,
    }
    assert all(not record.runs and not record.reset_fields for record in report.records)
    assert report.drift == {} and report.bridge_totals() == {}
    assert sum(record.hits for record in report.records) > 0

    root = ["--root", str(tiny_corpus.parent)]
    assert main(["corpus", "check", tiny_corpus.name, *root]) == 0
    out = capsys.readouterr().out
    assert "checking 4 of 4 records (every record)" in out
    assert "\nexact               4\n" in out
    assert "schema drift: none" in out
    assert "fields that differ already at reset: none" in out


def test_an_altered_digest_differs_at_its_step_and_names_the_field(
    tiny_corpus: Path, tmp_path: Path
) -> None:
    copy = _copy(tiny_corpus, tmp_path)
    corpus = Corpus.open(copy)
    name = "players[1].hand"
    field = _field(corpus, name)
    vectors = _vectors(corpus, RECORD)
    final = len(vectors) - 1
    step = 30

    transient = [list(vector) for vector in vectors]
    transient[step][field] = GARBAGE
    _rewrite(copy, RECORD, vectors=transient)
    result = _one(Corpus.open(copy))
    assert result.outcome == "transient"
    assert result.runs == (DifferingRun(step, step, (name,), "collateral"),)

    persistent = [list(vector) for vector in vectors]
    for vector in persistent[step:]:
        vector[field] = GARBAGE
    _rewrite(copy, RECORD, vectors=persistent)
    result = _one(Corpus.open(copy))
    assert result.outcome == "persistent"
    assert result.runs == (DifferingRun(step, final, (name,), "collateral"),)


def test_a_field_that_differs_at_reset_is_listed_and_kept_out(
    tiny_corpus: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    copy = _copy(tiny_corpus, tmp_path)
    corpus = Corpus.open(copy)
    name = "players[2].deck"
    field = _field(corpus, name)
    vectors = _vectors(corpus, RECORD)
    vectors[0][field] = GARBAGE
    # Later differences of that field stay out too.
    vectors[20][field] = GARBAGE
    _rewrite(copy, RECORD, vectors=vectors)
    report = check(Corpus.open(copy), Corpus.open(copy).pick())
    result = next(record for record in report.records if record.id == RECORD)
    assert result.reset_fields == (name,)
    assert result.outcome == "exact" and result.runs == ()
    assert report.field_records("reset_fields") == {"players[*].deck": 1}
    assert all(not items for items in report.verdicts().values())

    assert main(["corpus", "check", str(copy)]) == 0
    out = capsys.readouterr().out
    assert (
        "fields that differ already at reset (kept out of outcomes and verdicts):\n"
        "  players[*].deck in 1 records\n"
    ) in out


def test_schema_drift_is_listed_and_explains_its_fields(
    tiny_corpus: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    copy = _copy(tiny_corpus, tmp_path)
    manifest_path = copy / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    # The recording engine had a Resources field this one removed, and
    # called PlayerState's ``memories`` ``recollections``.
    manifest["class_schema"]["Resources"].append("ghost")
    player = manifest["class_schema"]["PlayerState"]
    player[player.index("memories")] = "recollections"
    manifest["fingerprint_fields"] = [
        name.replace(".memories", ".recollections")
        for name in manifest["fingerprint_fields"]
    ]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    corpus = Corpus.open(copy)

    report = check(corpus, [corpus.row(RECORD)])
    (result,) = report.records
    assert report.drift == {
        "PlayerState": {"removed": ["recollections"], "added": ["memories"]},
        "Resources": {"removed": ["ghost"], "added": []},
    }
    assert result.outcome == "exact" and result.runs == ()
    assert result.reset_fields == ()
    assert set(result.drift_fields) == {
        f"players[{seat}].{name}"
        for seat in range(4)
        for name in ("recollections", "resources")
    }

    assert main(["corpus", "check", str(copy), "--ids", _ids(tmp_path, RECORD)]) == 0
    out = capsys.readouterr().out
    assert (
        "  Resources: removed ghost (absent from digests); added - (left out)\n" in out
    )
    assert "    players[*].resources in 1 records\n" in out


def _ids(tmp_path: Path, *ids: str) -> str:
    path = tmp_path / "ids.txt"
    path.write_text("".join(f"{record_id}\n" for record_id in ids), encoding="utf-8")
    return str(path)


def test_an_answer_bridge_is_compared_after_it_ran(
    tiny_corpus: Path, tmp_path: Path
) -> None:
    """Pauses taken out of a record (an engine before OQ-103) come back as
    the pause bridge; before recorded step i, after the bridge, the state
    matches, right after recorded step i - 1 it would not."""

    copy = _copy(tiny_corpus, tmp_path)
    corpus = Corpus.open(copy)
    steps = _steps(corpus, RECORD)
    vectors = _vectors(corpus, RECORD)
    pauses = [
        index
        for index, step in enumerate(steps)
        if step["type"] == "chance" and step["decision_id"].endswith(":pause")
    ]
    assert pauses and pauses[-1] < len(steps) - 1
    _rewrite(
        copy,
        RECORD,
        steps=[step for index, step in enumerate(steps) if index not in pauses],
        vectors=[vector for index, vector in enumerate(vectors) if index not in pauses],
    )
    corpus = Corpus.open(copy)
    result = _one(corpus, bridge="pause")
    assert result.outcome == "equal" and result.runs == ()
    assert result.bridges == {"pause": len(pauses)}
    assert len(result.firings) == len(pauses)

    assert _after_step_differences(corpus) > 0


def _after_step_differences(corpus: Corpus) -> int:
    """Points where the state right after the previous recorded step (before
    any bridged step) differs from the trace."""

    engine = UprisingRulesEngine()
    row = corpus.row(RECORD)
    trace = corpus.trace(row)
    fingerprint = corpus.fingerprint()
    record = migrate_record(corpus.replay(row), engine)
    differences = 0
    after_recorded = None
    for state, migrated in walk(record, engine):
        if migrated.recorded_index is None:
            if after_recorded is None:
                after_recorded = state
            continue
        if after_recorded is not None:
            expected = trace.before(migrated.recorded_index)
            differences += fingerprint(after_recorded) != expected
            after_recorded = None
    return differences


def test_a_follows_bridge_is_compared_after_it_ran(
    tiny_corpus: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    copy = _copy(tiny_corpus, tmp_path)
    corpus = Corpus.open(copy)
    vectors = _vectors(corpus, RECORD)
    module, at = _split(corpus, tmp_path)
    corpus = Corpus.open(copy)

    result = _one(corpus, migration=module, bridge="split_follow")
    assert result.outcome == "equal" and result.runs == ()
    assert result.bridges == {"split_follow": 1} and result.firings == (at,)
    # Right after recorded step at - 1 the state is the one the recording
    # engine never had; the trace holds the state after both.
    engine = UprisingRulesEngine()
    record = load_migration(module).migrate_record(corpus.replay(corpus.row(RECORD)))
    states = [state for state, _ in load_migration(module).walk(record, engine)]
    fingerprint = corpus.fingerprint()
    assert fingerprint(states[at]) == tuple(vectors[at]) != tuple(vectors[at + 1])
    assert fingerprint(states[at + 1]) == tuple(vectors[at + 1])

    # The default migration does not split the step off, so the record no
    # longer fits this engine.
    assert _one(corpus).outcome not in ("exact", "equal")

    argv = ["corpus", "check", str(copy), "--ids", _ids(tmp_path, RECORD)]
    assert main([*argv, "--migration-module", str(module)]) == 0
    out = capsys.readouterr().out
    assert f"migration {module}" in out
    assert "bridges: split_follow 1 steps in 1 records" in out
    assert "\nequal               1\n" in out


def test_verdicts_lean_on_hits_and_bridge_firings(
    tiny_corpus: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    copy = _copy(tiny_corpus, tmp_path)
    corpus = Corpus.open(copy)
    module, at = _split(corpus, tmp_path)
    corpus = Corpus.open(copy)
    vectors = _vectors(corpus, RECORD)
    name = "players[0].intrigue_cards"
    field = _field(corpus, name)
    for vector in vectors[at - 2 : at]:
        vector[field] = GARBAGE
    near, far = at - 5, at - 30
    _rewrite(
        copy,
        RECORD,
        vectors=vectors,
        keys={"draws:card@near": [1, near, [near]], "draws:card@far": [1, far, [far]]},
    )
    corpus = Corpus.open(copy)
    options: dict[str, Any] = {"migration": module, "bridge": "split_follow"}

    bridged = DifferingRun(
        at - 2,
        at - 1,
        (name,),
        "bridged-window",
        (near, "draws:card@near"),
        ended_by="split_follow",
    )

    result = _one(corpus, around=["draws:card@near"], **options)
    assert result.outcome == "transient"
    assert result.runs == (bridged,)
    assert result.lone_firings == ()

    result = _one(corpus, around=["draws:card@far"], **options)
    assert result.runs == (
        DifferingRun(at - 2, at - 1, (name,), "collateral", ended_by="split_follow"),
    )
    assert result.lone_firings == (at,)

    # Without its bridge under review, the run in the hit's window is
    # unbridged; the bridge that ended it is still named.
    other: dict[str, Any] = {"migration": module, "around": ["draws:card@near"]}
    result = _one(corpus, bridge="pause", **other)
    assert result.runs == (replace(bridged, verdict="differs-unbridged"),)
    assert result.firings == ()
    # Several bridges may be under review.
    result = _one(corpus, bridge=["pause", "split_follow"], **other)
    assert result.runs == (bridged,) and result.firings == (at,)

    argv = ["corpus", "check", str(copy), "--migration-module", str(module)]
    argv += ["--around", "draws:card@near", "--bridge", "pause", "split_follow"]
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert "bridges under review: pause, split_follow; window 16" in out
    assert (
        f"  {RECORD} steps {at - 2}-{at - 1}: {name}; hit draws:card@near at "
        f"{near}; ends where split_follow fires\n"
    ) in out


def test_a_divergence_after_a_hit_is_diverged_at_hit(
    tiny_corpus: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    copy = _copy(tiny_corpus, tmp_path)
    corpus = Corpus.open(copy)
    record_id = "full.h4.2"
    steps = _steps(corpus, record_id)
    at = next(
        index
        for index, step in enumerate(steps)
        if index > 30 and step["type"] == "action"
    )
    steps[at] = {**steps[at], "actor": (steps[at]["actor"] + 1) % 4}
    _rewrite(
        copy, record_id, steps=steps, keys={"draws:card@near": [1, at - 1, [at - 1]]}
    )
    corpus = Corpus.open(copy)

    report = check(corpus, [corpus.row(record_id)], around=["draws:card@near"])
    (result,) = report.records
    assert result.outcome == "diverged"
    assert result.runs == (
        DifferingRun(
            at, at, (), "diverged-at-hit", (at - 1, "draws:card@near"), diverged=True
        ),
    )
    assert result.divergence is not None and result.divergence.index == at
    assert result.divergence.signature[1:] == (
        steps[at]["action_id"],
        "action actor does not own the current decision",
    )
    assert report.signatures() == [(result.divergence.signature, [f"{record_id}@{at}"])]
    assert report.divergence_hits() == [
        ((result.divergence.signature[0], "draws:card@near"), [f"{record_id}@{at}"])
    ]

    frame = result.divergence.signature[0]

    result = _one(corpus, record_id, around=["nothing:*"])
    assert [run.verdict for run in result.runs] == ["collateral"]

    assert main(["corpus", "check", str(copy), "--around", "draws:card@near"]) == 0
    out = capsys.readouterr().out
    assert f"pending {frame} at {steps[at]['action_id']}: " in out
    assert f"pending {frame} after draws:card@near  e.g. {record_id}@{at}" in out
    assert f"e.g. {record_id}@{at}" in out
    assert (
        f"  {record_id} step {at} (diverged): no field differs; hit draws:card@near"
        in out
    )

    # The state this engine stopped in is compared with the trace too.
    vectors = _vectors(corpus, record_id)
    name = "players[3].spies_supply"
    vectors[at][_field(corpus, name)] = GARBAGE
    _rewrite(copy, record_id, vectors=vectors)
    result = _one(Corpus.open(copy), record_id, around=["draws:card@near"])
    assert result.runs == (
        DifferingRun(
            at, at, (name,), "diverged-at-hit", (at - 1, "draws:card@near"), True
        ),
    )


@pytest.mark.parametrize(
    ("differences", "hits", "firings", "divergence", "verdicts", "lone"),
    [
        # A run starting window steps after a hit, ended by the firing.
        ({20: {"a"}, 21: {"a"}}, [(4, "k")], [22], None, ["bridged-window"], []),
        # One step too late for the window.
        ({20: {"a"}}, [(3, "k")], [21], None, ["collateral"], [21]),
        # A hit at the run's own first step changed nothing before it (the
        # firing after it has its hit).
        ({20: {"a"}}, [(20, "k")], [21], None, ["collateral"], []),
        # The run ends a step before the firing: something else ended it.
        ({20: {"a"}}, [(19, "k")], [22], None, ["differs-unbridged"], []),
        # A firing inside the run does not end it.
        (
            {20: {"a"}, 21: {"a"}, 22: {"a"}},
            [(19, "k")],
            [21],
            None,
            ["differs-unbridged"],
            [],
        ),
        # Two runs, two hits.
        (
            {5: {"a"}, 30: {"b"}},
            [(4, "k"), (29, "k")],
            [6],
            None,
            ["bridged-window", "differs-unbridged"],
            [],
        ),
        # A divergence with the state still equal, right after a hit ...
        ({}, [(9, "k")], [], 10, ["diverged-at-hit"], []),
        # ... at the hit's own step ...
        ({}, [(10, "k")], [], 10, ["diverged-at-hit"], []),
        # ... at the end of a run that started in a hit's window ...
        ({30: {"a"}, 31: {"a"}}, [(14, "k")], [], 31, ["diverged-at-hit"], []),
        # ... and with no hit near it.
        ({}, [(1, "k")], [], 40, ["collateral"], []),
        # A run before a divergence keeps its own verdict.
        ({8: {"a"}}, [(7, "k")], [9], 12, ["bridged-window", "diverged-at-hit"], []),
        # A firing exactly window steps after a hit has its hit; one more
        # step, and it has none ...
        ({}, [(4, "k")], [20], None, [], []),
        ({}, [(4, "k")], [21], None, [], [21]),
        # (a firing that ends a bridged-window run has its run's hit: the
        # first case's is 18 steps after it); a hit at the firing's own
        # recorded step comes after it.
        ({}, [(21, "k")], [21], None, [], [21]),
    ],
)
def test_judge(
    differences: dict[int, set[str]],
    hits: list[tuple[int, str]],
    firings: list[int],
    divergence: int | None,
    verdicts: list[str],
    lone: list[int],
) -> None:
    runs, lone_firings = judge(
        differences, hits=hits, firings=firings, divergence=divergence, window=16
    )
    assert [run.verdict for run in runs] == verdicts
    assert list(lone_firings) == lone


def test_judge_names_fields_and_the_hit() -> None:
    (run,), _ = judge(
        {7: {"players[1].hand"}, 8: {"players[1].deck", "players[1].hand"}},
        hits=[(2, "x"), (5, "draws:card@y")],
        firings=[9],
    )
    assert run == DifferingRun(
        7,
        8,
        ("players[1].deck", "players[1].hand"),
        "bridged-window",
        (5, "draws:card@y"),
    )
    # A divergence leans on the hit before the refused step, and on the
    # refused step's own hit only when no earlier one is near.
    (run,), _ = judge({}, hits=[(9, "before"), (10, "own")], divergence=10)
    assert (run.verdict, run.hit) == ("diverged-at-hit", (9, "before"))
    (run,), _ = judge({}, hits=[(1, "old"), (40, "own")], divergence=40)
    assert (run.verdict, run.hit) == ("diverged-at-hit", (40, "own"))
    # The bridges that fired where a run ends are named, reviewed or not.
    (run,), _ = judge({4: {"a"}}, ending={5: "pause, split"})
    assert (run.verdict, run.ended_by) == ("collateral", "pause, split")
    assert seatless("players[1].hand") == "players[*].hand"
    assert seatless("round_number") == "round_number"


def test_controls_leave_out_records_with_hits(
    tiny_corpus: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    corpus = Corpus.open(tiny_corpus)
    scouts = "chance_kinds:round:scouts:*"
    report = check(corpus, [corpus.row(RECORD)], around=[scouts], controls=3)
    controls = [record.id for record in report.records if record.control]
    # full.h4.2 and no-tech.rhra.1 meet the Arrakeen Scouts too.
    assert controls == ["base.h4.1"]
    assert report.outcomes(control=True)["exact"] == 1
    assert report.selected() == 1 and report.controls() == 1

    argv = ["corpus", "check", str(tiny_corpus), "--has", scouts, "--around", scouts]
    assert main([*argv, "--control", "2"]) == 0
    out = capsys.readouterr().out
    assert f"checking 3 of 4 records ('{scouts}')" in out
    assert "\nexact               3         1\n" in out
    assert "only 1 of the 2 control records asked for exist" in out


def test_a_record_that_cannot_be_checked_fails_alone(
    tiny_corpus: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    copy = _copy(tiny_corpus, tmp_path)
    corpus = Corpus.open(copy)
    _rewrite(copy, RECORD, vectors=_vectors(corpus, RECORD)[:-1])
    out_json = tmp_path / "out" / "check.json"
    out_json.parent.mkdir()
    before = sorted(path for path in tmp_path.rglob("*"))
    assert main(["corpus", "check", str(copy), "--json", str(out_json)]) == 0
    out = capsys.readouterr().out
    assert f"  {RECORD}: ValueError: the trace has " in out
    assert "\nexact               3\n" in out and "\nfailed              1\n" in out
    # Only the summary is written.
    assert sorted(path for path in tmp_path.rglob("*")) == sorted([*before, out_json])
    summary = json.loads(out_json.read_text(encoding="utf-8"))
    assert summary["outcomes"]["failed"] == 1 and summary["records"] == 4
    assert summary["failed"][0]["id"] == RECORD


def test_workers_give_the_same_report(tiny_corpus: Path) -> None:
    corpus = Corpus.open(tiny_corpus)
    rows = corpus.pick()
    one = check(corpus, rows, around=["draws:*"])
    two = check(corpus, rows, around=["draws:*"], workers=2)
    strip = [
        (record.id, record.outcome, record.hits, record.runs) for record in one.records
    ]
    assert strip == [
        (record.id, record.outcome, record.hits, record.runs) for record in two.records
    ]
    assert two.drift == one.drift == {}
    with pytest.raises(ValueError, match="workers must be 1 to 4"):
        check(corpus, rows, workers=5)


def test_a_migration_module_is_loaded_from_its_path(tmp_path: Path) -> None:
    module = tmp_path / "proposed.py"
    module.write_text(
        "from dune_imperium.records.migration import walk\n"
        "def migrate_record(replay, engine=None):\n"
        "    raise RuntimeError('proposed')\n",
        encoding="utf-8",
    )
    loaded = load_migration(module)
    assert loaded is load_migration(module)
    with pytest.raises(RuntimeError, match="proposed"):
        loaded.migrate_record(None)
    incomplete = tmp_path / "incomplete.py"
    incomplete.write_text("walk = None\n", encoding="utf-8")
    with pytest.raises(ValueError, match="has no migrate_record"):
        load_migration(incomplete)
