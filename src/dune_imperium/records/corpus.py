"""Read a record corpus: index rows, picks, records and their traces.

A record corpus is a set of AI games one engine played, written by that
engine itself (``scripts/records/corpus_generate.py``, run with the engine
on the import path). It lets a review of an engine change start from games
an older engine already played instead of playing new ones. This module only
reads the files; it never imports the old engine's code.

Layout, under ``CORPUS_ROOT`` (git-ignored ``local/records-corpus``)::

    v<codec>-<commit8>/                 the engine that played: codec, commit
      manifest.json                     written last; a shard it omits is ignored
      shards/<combo>.<mix>.<lo>-<hi>.records.jsonl.zst   save-format v1 records
      shards/<same stem>.index.jsonl.zst                 one index row per record
      shards/<same stem>.trace.bin.zst                   one trace per record
      shards/<same stem>.meta.json                       the generator's own

Each record line is a save document ``dune-imperium-records check`` reads,
plus a ``corpus`` entry; each index row lists what the game did as
``"dimension:key" -> [count, first_step, positions]``
(``records.portable.trace.step_keys``); each trace holds the digests of the
fields every recorded step changed (``records.portable.trace``).

``check`` replays records on *this* engine through ``records.migration``
and compares the state before every recorded step with the trace, so a
review of an engine change needs only the new engine (docs/human-records.md).
"""

import fnmatch
import hashlib
import importlib.util
import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from compression import zstd
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field, replace
from multiprocessing import get_context
from pathlib import Path
from types import ModuleType
from typing import Any, Final

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.replay import GameReplay, ReplayStep
from dune_imperium.paths import LOCAL_DIR
from dune_imperium.records import migration as records_migration
from dune_imperium.records.portable.trace import (
    Digests,
    Fingerprint,
    TraceReader,
    canonical,
    chance_family,
    trace_payloads,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.server.persistence import parse_save_document

CORPUS_ROOT: Final = LOCAL_DIR / "records-corpus"
MANIFEST: Final = "manifest.json"
SUFFIXES: Final = {
    "records": ".records.jsonl.zst",
    "index": ".index.jsonl.zst",
    "trace": ".trace.bin.zst",
}
# Decompressed shard files kept in memory at once.
_CACHED_FILES: Final = 6


@dataclass(frozen=True, slots=True)
class CorpusRow:
    """One record's index row."""

    id: str
    shard: str
    line: int
    combo: str
    ruleset: str
    mix: str
    seats: tuple[str, ...]
    steer: str | None
    branch_of: str | None
    seed: int
    steps: int
    rounds: int
    finished: bool
    final_hash: str
    keys: Mapping[str, Sequence[Any]] = field(compare=False, repr=False)
    errors: Mapping[str, int] = field(default_factory=dict, compare=False)
    # Rounds the record was cut after (``corpus_generate.py --rounds``).
    cut_rounds: int | None = None

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> CorpusRow:
        return cls(
            id=data["id"],
            shard=data["shard"],
            line=data["line"],
            combo=data["combo"],
            ruleset=data["ruleset"],
            mix=data["mix"],
            seats=tuple(data["seats"]),
            steer=data.get("steer"),
            branch_of=data.get("branch_of"),
            seed=data["seed"],
            steps=data["steps"],
            rounds=data["rounds"],
            finished=data["finished"],
            final_hash=data["final_hash"],
            keys=data["keys"],
            errors=data.get("errors") or {},
            cut_rounds=data.get("cut_rounds"),
        )

    @property
    def natural(self) -> bool:
        """Whether the game was played without steering or branching."""

        return self.steer is None and self.branch_of is None

    def count(self, key: str) -> int:
        entry = self.keys.get(key)
        return 0 if entry is None else int(entry[0])

    def first_step(self, key: str) -> int | None:
        entry = self.keys.get(key)
        return None if entry is None or len(entry) < 2 else int(entry[1])

    def positions(self, key: str) -> tuple[int, ...] | None:
        """Every step the key occurred at, when the row kept them."""

        entry = self.keys.get(key)
        return None if entry is None or len(entry) < 3 else tuple(entry[2])

    def matching(self, pattern: str, *, min_count: int = 1) -> list[str]:
        """The row's keys matching the fnmatch ``pattern``, counted enough."""

        match = _matcher(pattern)
        return [
            key
            for key, entry in self.keys.items()
            if match(key) and int(entry[0]) >= min_count
        ]


def _matcher(pattern: str) -> Callable[[str], object]:
    if pattern == "*":
        return lambda key: True
    return re.compile(fnmatch.translate(pattern)).match


class Corpus:
    """One record corpus folder."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.manifest: dict[str, Any] = json.loads(
            (path / MANIFEST).read_text(encoding="utf-8")
        )
        self._shards: dict[str, dict[str, Any]] = {
            shard["stem"]: shard for shard in self.manifest["shards"]
        }
        self._rows: tuple[CorpusRow, ...] | None = None
        self._files: dict[tuple[str, str], bytes] = {}
        self._lines: dict[str, list[bytes]] = {}
        self._traces: dict[str, tuple[int, list[bytes]]] = {}

    @classmethod
    def open(cls, id_or_path: str | Path, root: Path = CORPUS_ROOT) -> Corpus:
        """A corpus by folder path, or by id under ``root``."""

        for candidate in (Path(id_or_path), root / str(id_or_path)):
            if (candidate / MANIFEST).is_file():
                return cls(candidate)
        raise FileNotFoundError(f"no record corpus {str(id_or_path)!r} in {root}")

    @property
    def id(self) -> str:
        return str(self.manifest.get("id") or self.path.name)

    def __repr__(self) -> str:
        return f"Corpus({str(self.path)!r})"

    def shard_path(self, stem: str, part: str) -> Path:
        return self.path / "shards" / f"{stem}{SUFFIXES[part]}"

    def size(self) -> int:
        """Bytes on disk."""

        return sum(
            path.stat().st_size for path in self.path.rglob("*") if path.is_file()
        )

    def _read(self, stem: str, part: str) -> bytes:
        """One shard file, checked against the manifest and decompressed."""

        shard = self._shards.get(stem)
        if shard is None:
            raise KeyError(f"{self.id} has no shard {stem!r}")
        path = self.shard_path(stem, part)
        compressed = path.read_bytes()
        if hashlib.sha256(compressed).hexdigest() != shard["sha256"][part]:
            raise ValueError(f"{path} does not match the manifest's sha256")
        return zstd.decompress(compressed)

    def _file(self, stem: str, part: str) -> bytes:
        cached = self._files.get((stem, part))
        if cached is not None:
            return cached
        data = self._read(stem, part)
        if len(self._files) >= _CACHED_FILES:
            self._files.pop(next(iter(self._files)))
        self._files[(stem, part)] = data
        return data

    def rows(self) -> tuple[CorpusRow, ...]:
        """Every record's row, shard by shard in manifest order."""

        if self._rows is None:
            rows: list[CorpusRow] = []
            for stem in self._shards:
                data = self._read(stem, "index")
                rows.extend(
                    CorpusRow.from_json(json.loads(line))
                    for line in data.splitlines()
                    if line
                )
            self._rows = tuple(rows)
        return self._rows

    def row(self, record_id: str) -> CorpusRow:
        for row in self.rows():
            if row.id == record_id:
                return row
        raise KeyError(f"{self.id} has no record {record_id!r}")

    def pick(
        self,
        has: Iterable[str] = (),
        without: Iterable[str] = (),
        *,
        combo: str | None = None,
        mix: str | None = None,
        natural: bool = True,
        min_count: int = 1,
        limit: int | None = None,
        seed: int = 0,
    ) -> list[CorpusRow]:
        """Rows whose keys match every ``has`` pattern and no ``without`` one.

        Patterns are fnmatch patterns over keys; a ``has`` key must be
        counted at least ``min_count`` times. ``natural`` leaves steered and
        branched records out. The rows come round-robin over the
        (combo, mix) groups in sorted order, each group by seed (shuffled
        by ``seed`` when it is not 0), so a ``limit`` spreads over groups.
        """

        wanted = [_matcher(pattern) for pattern in has]
        unwanted = [_matcher(pattern) for pattern in without]
        groups: dict[tuple[str, str], list[CorpusRow]] = defaultdict(list)
        for row in self.rows():
            if (combo is not None and row.combo != combo) or (
                mix is not None and row.mix != mix
            ):
                continue
            if natural and not row.natural:
                continue
            if any(any(match(key) for key in row.keys) for match in unwanted):
                continue
            if not all(
                any(
                    match(key) and int(entry[0]) >= min_count
                    for key, entry in row.keys.items()
                )
                for match in wanted
            ):
                continue
            groups[(row.combo, row.mix)].append(row)
        queues = []
        rng = random.Random(seed)
        for group in sorted(groups):
            queue = sorted(groups[group], key=lambda row: row.seed)
            if seed:
                rng.shuffle(queue)
            queues.append(queue)
        picked: list[CorpusRow] = []
        depth = 0
        while any(depth < len(queue) for queue in queues):
            for queue in queues:
                if depth < len(queue):
                    if limit is not None and len(picked) >= limit:
                        return picked
                    picked.append(queue[depth])
            depth += 1
        return picked

    def key_counts(
        self, pattern: str = "*", *, natural: bool = False
    ) -> dict[str, tuple[int, int]]:
        """``{key: (records, count)}`` over the keys matching ``pattern``."""

        match = _matcher(pattern)
        records: dict[str, int] = defaultdict(int)
        counts: dict[str, int] = defaultdict(int)
        for row in self.rows():
            if natural and not row.natural:
                continue
            for key, entry in row.keys.items():
                if match(key):
                    records[key] += 1
                    counts[key] += int(entry[0])
        return {key: (records[key], counts[key]) for key in sorted(records)}

    def document(self, row: CorpusRow) -> dict[str, Any]:
        """The record's save document."""

        lines = self._lines.get(row.shard)
        if lines is None:
            lines = self._file(row.shard, "records").splitlines()
            self._lines = {row.shard: lines}
        document: dict[str, Any] = json.loads(lines[row.line])
        if document.get("corpus", {}).get("id") != row.id:
            raise ValueError(f"{row.shard} line {row.line} is not {row.id}")
        return document

    def replay(self, row: CorpusRow) -> GameReplay:
        """The record as a replay with its own version stamps.

        ``records.migration.migrate_record`` takes it as it takes a saved
        game (``records.saves.read_saved_game``).
        """

        return parse_save_document(self.document(row), check_versions=False).replay

    def trace(self, row: CorpusRow) -> TraceReader:
        """The record's trace."""

        payloads = self._traces.get(row.shard)
        if payloads is None:
            payloads = trace_payloads(self._file(row.shard, "trace"))
            self._traces = {row.shard: payloads}
        field_count, records = payloads
        return TraceReader(records[row.line], field_count)

    def fingerprint(self) -> Fingerprint:
        """A ``Fingerprint`` over this corpus's fields and classes.

        Fields and nested fields a newer engine adds are left out, so its
        states digest comparably to the trace.
        """

        return Fingerprint(
            names=self.manifest["fingerprint_fields"],
            schema=self.manifest["class_schema"],
            unordered=self.manifest["unordered_zones"],
        )

    def export(self, rows: Iterable[CorpusRow], out_dir: Path) -> list[Path]:
        """Write each row's record as ``<id>.json``, a save file
        ``dune-imperium-records check --saves-dir`` reads.

        Each file is one record; ``--every-save`` checks every one even
        where records share a ruleset, seed and seats (a steered or
        branched record beside its natural one). The document gains the
        row's ``finished``, as a play server save carries it.
        """

        out_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for row in rows:
            path = out_dir / f"{row.id}.json"
            document = {**self.document(row), "finished": row.finished}
            path.write_text(
                json.dumps(document, separators=(",", ":")), encoding="utf-8"
            )
            paths.append(path)
        return paths

    def games(self) -> dict[tuple[str, str], int]:
        """Games per (combo, mix), from the manifest."""

        games: dict[tuple[str, str], int] = defaultdict(int)
        for shard in self.manifest["shards"]:
            games[(shard["combo"], shard["mix"])] += shard["games"]
        return dict(sorted(games.items()))


def corpora(root: Path = CORPUS_ROOT) -> list[Corpus]:
    """Every corpus under ``root``, by name."""

    if not root.is_dir():
        return []
    return [
        Corpus(path) for path in sorted(root.iterdir()) if (path / MANIFEST).is_file()
    ]


# --- check: a corpus on this engine -------------------------------------------
#
# ``check`` replays each record on this engine through a migration module
# (``records.migration`` or one loaded by path, to review a proposed one
# before it is merged): ``migrate_record``, then ``walk``. At every migrated
# step with a ``recorded_index`` i it digests the state before that step --
# after any bridged steps in front of it -- with the corpus's own field list
# and class schema (``Corpus.fingerprint``: fields a newer engine adds are
# left out, nested classes keep their old fields) and compares the digests
# with the trace's ``before(i)``; then the final state with ``final()``, or,
# for a record this engine refuses, the state it stopped in with
# ``before(divergence)``. It never compares the state right after a
# recorded step: a bridge that answers a question the recording engine did
# not ask, or that adds a part of the recorded step this engine splits off
# (a ``follows`` bridge), restores the recorded state only once it has run.
#
# Each record's outcome is one of ``OUTCOMES``: exact (no bridge, every
# digest equal), equal (bridges fired, every digest equal), transient
# (differs, then equal again by the end), persistent (the final state
# differs), diverged (this engine refused a recorded step that no bridge
# reached) and failed (an exception; reported, and the check goes on).
#
# Every run of consecutive differing compared points gets one of
# ``VERDICTS`` against the nearest preceding ``around`` hit (an index key's
# recorded step, from the corpus row) and the firings of the ``bridge`` under
# review (``judge``). Fields that differ already in the reset state, and
# fields the schema drift explains (a field this engine removed or renamed,
# at the top or in a nested class: ``schema_drift``), are reported once and
# kept out of the outcomes and verdicts.

OUTCOMES: Final = ("exact", "equal", "transient", "persistent", "diverged", "failed")
VERDICTS: Final = (
    "bridged-window",
    "diverged-at-hit",
    "differs-unbridged",
    "collateral",
    "bridge-without-hit",
)
DEFAULT_WINDOW: Final = 16
MAX_WORKERS: Final = 4
# Records per worker task.
_CHECK_CHUNK: Final = 10
# Divergence reasons are grouped by this many characters, digits blanked.
_REASON_PREFIX: Final = 60
_SEAT: Final = re.compile(r"^players\[(?P<seat>\d+)\]\.(?P<attr>.+)$")
_MISSING: Final = object()


@dataclass(frozen=True, slots=True)
class DifferingRun:
    """Consecutive compared points whose digests differ from the trace.

    ``start`` and ``end`` are recorded step indices: the point ``i`` is the
    state before recorded step ``i`` (``steps`` is the final state). A run
    that ends where the record diverged has ``diverged`` set; its
    ``fields`` may be empty when the state still matched there.
    """

    start: int
    end: int
    fields: tuple[str, ...]
    verdict: str
    # The ``around`` hit the verdict leans on: (recorded step, key).
    hit: tuple[int, str] | None = None
    diverged: bool = False


@dataclass(frozen=True, slots=True)
class DivergenceCheck:
    """Where this engine refused a recorded step, grouped by ``signature``."""

    index: int
    # (pending frame kind, recorded step, reason prefix).
    signature: tuple[str, str, str]


@dataclass(frozen=True, slots=True)
class RecordCheck:
    """One record compared with its trace on this engine."""

    id: str
    outcome: str
    steps: int
    control: bool = False
    # Steps each bridge answered or rewrote.
    bridges: Mapping[str, int] = field(default_factory=dict)
    runs: tuple[DifferingRun, ...] = ()
    # Where the reviewed bridge fired: before which recorded step (or the
    # end point), once per firing.
    firings: tuple[int, ...] = ()
    # Those of ``firings`` without an ``around`` hit in the window before.
    lone_firings: tuple[int, ...] = ()
    divergence: DivergenceCheck | None = None
    # Fields that differ already in the reset state.
    reset_fields: tuple[str, ...] = ()
    # Fields whose difference the schema drift explains.
    drift_fields: tuple[str, ...] = ()
    # ``around`` hits, and the hit keys whose row kept no positions (only
    # their first step is used).
    hits: int = 0
    unpositioned: tuple[str, ...] = ()
    error: str | None = None
    seconds: float = 0.0


def judge(
    differences: Mapping[int, Iterable[str]],
    *,
    hits: Iterable[tuple[int, str]] = (),
    firings: Iterable[int] = (),
    divergence: int | None = None,
    window: int = DEFAULT_WINDOW,
) -> tuple[tuple[DifferingRun, ...], tuple[int, ...]]:
    """The verdict of every differing run, and the firings without a hit.

    ``differences`` maps each differing compared point (a recorded step
    index; the state before it) to its fields; ``hits`` are the recorded
    steps of ``around`` keys (a hit at ``h`` changed the state seen at
    ``h + 1``); ``firings`` the points the reviewed bridge fired before;
    ``divergence`` the recorded step this engine refused. Verdicts:

    - ``diverged-at-hit``: the run that ends where the record diverged
      (one is made, without fields, when the state still matched there),
      with a hit at or before the divergence and no earlier than ``window``
      steps before the run starts;
    - ``bridged-window``: the run starts at most ``window`` steps after a
      hit and ends right where the bridge fires, the firing being the step
      that makes the state equal again;
    - ``differs-unbridged``: the run starts in a hit's window, but no
      firing ends it (it lasts to the end, or something else ends it);
    - ``collateral``: no hit in the window before the run, or before the
      divergence;
    - ``bridge-without-hit`` (the second result): a firing with no hit in
      the ``window`` steps before it that does not end a ``bridged-window``
      run either (a held draw may be taken more than ``window`` steps after
      its hit, at the seat's turn end).
    """

    hit_list = sorted(hits)
    firing_points = sorted(firings)
    fired = set(firing_points)
    groups: list[list[int]] = []
    for index in sorted(differences):
        if groups and index == groups[-1][-1] + 1:
            groups[-1].append(index)
        else:
            groups.append([index])
    if divergence is not None and not (groups and groups[-1][-1] == divergence):
        groups.append([divergence])
    runs = []
    for group in groups:
        start, end = group[0], group[-1]
        fields = tuple(sorted({name for i in group for name in differences.get(i, ())}))
        if divergence is not None and end == divergence:
            hit = _nearest(hit_list, divergence)
            leans = hit is not None and hit[0] >= start - window
            verdict = "diverged-at-hit" if leans else "collateral"
        else:
            hit = _nearest(hit_list, start - 1)
            leans = hit is not None and start - hit[0] <= window
            if not leans:
                verdict = "collateral"
            elif end + 1 in fired:
                verdict = "bridged-window"
            else:
                verdict = "differs-unbridged"
        runs.append(
            DifferingRun(
                start,
                end,
                fields,
                verdict,
                hit if leans else None,
                diverged=divergence is not None and end == divergence,
            )
        )
    ending = {run.end + 1 for run in runs if run.verdict == "bridged-window"}
    lone = []
    for point in firing_points:
        hit = _nearest(hit_list, point - 1)
        if (hit is None or point - hit[0] > window) and point not in ending:
            lone.append(point)
    return tuple(runs), tuple(lone)


def _nearest(hits: Sequence[tuple[int, str]], at: int) -> tuple[int, str] | None:
    """The last hit at or before recorded step ``at``."""

    found = None
    for hit in hits:
        if hit[0] > at:
            break
        found = hit
    return found


def row_hits(
    row: CorpusRow, patterns: Sequence[str]
) -> tuple[list[tuple[int, str]], list[str]]:
    """``row``'s hits of ``patterns`` as (recorded step, key), sorted.

    A key whose row kept no positions (counted more than
    ``portable.trace.POSITION_LIMIT`` times outside the full-position
    dimensions) gives its first step only; such keys come second.
    """

    hits: set[tuple[int, str]] = set()
    unpositioned: set[str] = set()
    matchers = [_matcher(pattern) for pattern in patterns]
    for key, entry in row.keys.items():
        if not any(match(key) for match in matchers):
            continue
        positions = row.positions(key)
        if positions is None:
            first = row.first_step(key)
            if first is None:
                continue
            positions = (first,)
            if int(entry[0]) > 1:
                unpositioned.add(key)
        hits.update((position, key) for position in positions)
    return sorted(hits), sorted(unpositioned)


def schema_drift(
    old: Mapping[str, Sequence[str]], current: Mapping[str, Sequence[str]]
) -> dict[str, dict[str, Any]]:
    """The classes whose fields changed from ``old`` to ``current``.

    ``{qualname: {"removed": [...], "added": [...]}}``, and
    ``{qualname: {"unmet": True}}`` for a class of ``old`` that no checked
    state held on this engine (renamed, removed, or only absent from these
    records). A removed field digests as absent; an added one is left out of
    the digests.
    """

    drift: dict[str, dict[str, Any]] = {}
    for qualname, names in sorted(old.items()):
        now = current.get(qualname)
        if now is None:
            drift[qualname] = {"unmet": True}
            continue
        removed = [name for name in names if name not in now]
        added = [name for name in now if name not in names]
        if removed or added:
            drift[qualname] = {"removed": removed, "added": added}
    return drift


def seatless(name: str) -> str:
    """A field name with its seat replaced by ``*`` (``players[*].hand``)."""

    match = _SEAT.match(name)
    return name if match is None else f"players[*].{match.group('attr')}"


def load_migration(path: Path) -> ModuleType:
    """A migration module (``records.migration``'s interface) loaded from ``path``.

    It is imported under a private name, so it may sit anywhere, e.g. a
    branch's proposed ``records/migration.py`` reviewed before merging; it
    runs on this checkout's engine.
    """

    path = path.resolve()
    digest = hashlib.sha1(str(path).encode()).hexdigest()[:12]
    name = f"_corpus_migration_{digest}"
    loaded = sys.modules.get(name)
    if loaded is not None:
        return loaded
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"{path} is not a Python module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise
    missing = [name for name in ("migrate_record", "walk") if not hasattr(module, name)]
    if missing:
        del sys.modules[name]
        raise ValueError(f"{path} has no {', '.join(missing)}")
    return module


def _field_value(state: Any, name: str) -> Any:
    match = _SEAT.match(name)
    if match is None:
        return getattr(state, name, _MISSING)
    players = getattr(state, "players", ())
    seat = int(match.group("seat"))
    if seat >= len(players):
        return _MISSING
    return getattr(players[seat], match.group("attr"), _MISSING)


class _Comparison:
    """One record's digests against its trace, point by point."""

    def __init__(self, fingerprint: Fingerprint, schema: Mapping[str, Sequence[str]]):
        assert fingerprint.names is not None
        self.fingerprint = fingerprint
        self.names = fingerprint.names
        self.schema = schema
        self.excluded: set[int] = set()
        self.reset_fields: list[str] = []
        self.drift_fields: set[str] = set()
        self.differences: dict[int, frozenset[str]] = {}
        self.last = -1
        self._started = False
        self._drifted_values: dict[int, tuple[object, bool]] = {}

    def reset(self, state: Any, expected: Digests) -> None:
        """Compare the reset state once; its differing fields are left out."""

        if self._started:
            return
        self._started = True
        for index in self._differing(self.fingerprint(state), expected):
            self.excluded.add(index)
            if self._drifted(state, index):
                self.drift_fields.add(self.names[index])
            else:
                self.reset_fields.append(self.names[index])

    def point(self, index: int, state: Any, expected: Digests) -> None:
        """Compare the state at recorded point ``index``."""

        self.last = index
        digests = self.fingerprint(state)
        if digests == expected:
            return
        fields = set()
        for field_index in self._differing(digests, expected):
            if field_index in self.excluded:
                continue
            if self._drifted(state, field_index):
                self.excluded.add(field_index)
                self.drift_fields.add(self.names[field_index])
                continue
            fields.add(self.names[field_index])
        if fields:
            self.differences[index] = frozenset(fields)

    @staticmethod
    def _differing(digests: Digests, expected: Digests) -> list[int]:
        if len(digests) != len(expected):
            raise ValueError("the trace and the corpus field list differ in length")
        return [
            index
            for index, (new, old) in enumerate(zip(digests, expected, strict=True))
            if new != old
        ]

    def _drifted(self, state: Any, index: int) -> bool:
        """Whether the schema drift explains field ``index``'s difference."""

        value = _field_value(state, self.names[index])
        if value is _MISSING:
            return True
        current = self.fingerprint.class_schema
        drifting = {
            qualname
            for qualname, names in self.schema.items()
            if qualname in current
            and any(name not in current[qualname] for name in names)
        }
        if not drifting:
            return False
        hit = self._drifted_values.get(id(value))
        if hit is not None and hit[0] is value:
            return hit[1]
        seen: dict[str, list[str]] = {}
        canonical(value, None, seen)
        drifted = any(qualname in drifting for qualname in seen)
        self._drifted_values[id(value)] = (value, drifted)
        return drifted


def _step_name(step: ReplayStep) -> str:
    if isinstance(step, DomainAction):
        return step.action_id
    return f"chance {chance_family(step.decision_id)}"


def _signature(record: Any) -> tuple[str, str, str]:
    divergence = record.divergence
    stack = getattr(record.state, "decision_stack", ())
    if divergence.pending is None or not stack:
        frame = "none"
    else:
        kind = stack[-1].kind
        frame = str(getattr(kind, "value", kind))
    reason = re.sub(r"\d+", "#", str(divergence.reason))[:_REASON_PREFIX]
    return frame, _step_name(divergence.step), reason


class _Checker:
    """Checks records of one corpus on one engine and migration module."""

    def __init__(
        self,
        corpus: Corpus,
        engine: UprisingRulesEngine,
        migration: ModuleType,
        *,
        around: Sequence[str],
        bridge: str | None,
        window: int,
    ) -> None:
        self.corpus = corpus
        self.engine = engine
        self.migration = migration
        self.around = tuple(around)
        self.bridge = bridge
        self.window = window
        self.schema: Mapping[str, Sequence[str]] = corpus.manifest["class_schema"]
        self.rows = {row.id: row for row in corpus.rows()}
        # This engine's classes as the digests met them.
        self.classes: dict[str, list[str]] = {}

    def run(self, row: CorpusRow, *, control: bool = False) -> RecordCheck:
        started = time.process_time()
        try:
            result = self._check(row, control)
        except Exception as error:  # noqa: BLE001 - one record's failure is a finding
            result = RecordCheck(
                row.id,
                "failed",
                row.steps,
                control=control,
                error=f"{type(error).__name__}: {error}",
            )
        return replace(result, seconds=time.process_time() - started)

    def _check(self, row: CorpusRow, control: bool) -> RecordCheck:
        replay = self.corpus.replay(row)
        trace = self.corpus.trace(row)
        if trace.steps != len(replay.steps):
            raise ValueError(
                f"the trace has {trace.steps} steps, the record {len(replay.steps)}"
            )
        record = self.migration.migrate_record(replay, self.engine)
        fingerprint = self.corpus.fingerprint()
        comparison = _Comparison(fingerprint, self.schema)
        firings: list[int] = []
        waiting = 0
        for state, migrated in self.migration.walk(record, self.engine):
            comparison.reset(state, trace.reset)
            if self.bridge is not None and migrated.bridge == self.bridge:
                waiting += 1
            index = migrated.recorded_index
            if index is None:
                continue
            firings.extend([index] * waiting)
            waiting = 0
            comparison.point(index, state, trace.before(index))
        comparison.reset(record.state, trace.reset)
        divergence = record.divergence
        end = trace.steps if divergence is None else divergence.recorded_index
        if end <= comparison.last:
            raise ValueError(f"the migration ends at step {end}, already compared")
        firings.extend([end] * waiting)
        comparison.point(end, record.state, trace.before(end))
        for qualname, names in fingerprint.class_schema.items():
            self.classes.setdefault(qualname, names)

        hits, unpositioned = row_hits(row, self.around)
        runs, lone = judge(
            comparison.differences,
            hits=hits,
            firings=firings,
            divergence=None if divergence is None else end,
            window=self.window,
        )
        bridges = dict(sorted(record.bridge_counts().items()))
        if divergence is not None:
            outcome = "diverged"
        elif comparison.differences:
            outcome = "persistent" if end in comparison.differences else "transient"
        else:
            outcome = "equal" if bridges else "exact"
        return RecordCheck(
            row.id,
            outcome,
            row.steps,
            control=control,
            bridges=bridges,
            runs=runs,
            firings=tuple(firings),
            lone_firings=lone,
            divergence=(
                None if divergence is None else DivergenceCheck(end, _signature(record))
            ),
            reset_fields=tuple(comparison.reset_fields),
            drift_fields=tuple(sorted(comparison.drift_fields)),
            hits=len(hits),
            unpositioned=tuple(unpositioned),
        )


_WORKER: _Checker | None = None


def _start_worker(
    corpus_path: Path, migration_path: Path | None, settings: dict[str, Any]
) -> None:
    global _WORKER
    os.nice(10)
    migration = (
        records_migration if migration_path is None else load_migration(migration_path)
    )
    _WORKER = _Checker(
        Corpus(corpus_path), UprisingRulesEngine(), migration, **settings
    )


def _check_chunk(
    task: Sequence[tuple[str, bool]],
) -> tuple[list[RecordCheck], dict[str, list[str]]]:
    checker = _WORKER
    assert checker is not None, "the worker was not started"
    results = [
        checker.run(checker.rows[record_id], control=control)
        for record_id, control in task
    ]
    return results, checker.classes


@dataclass(frozen=True, slots=True)
class CheckReport:
    """What ``check`` found over a corpus's records."""

    corpus: str
    corpus_codec: int
    engine_codec: int
    migration: str
    around: tuple[str, ...]
    bridge: str | None
    window: int
    records: tuple[RecordCheck, ...]
    # Manifest ``class_schema`` against this engine's classes (``schema_drift``).
    drift: Mapping[str, Mapping[str, Any]]
    wall_seconds: float

    def outcomes(self, *, control: bool = False) -> dict[str, int]:
        counts = dict.fromkeys(OUTCOMES, 0)
        for record in self.records:
            if record.control == control:
                counts[record.outcome] += 1
        return counts

    def selected(self) -> int:
        return sum(1 for record in self.records if not record.control)

    def controls(self) -> int:
        return sum(1 for record in self.records if record.control)

    def cpu_seconds(self) -> float:
        return sum(record.seconds for record in self.records)

    def bridge_totals(self) -> dict[str, tuple[int, int]]:
        """``{bridge: (steps, records)}``."""

        steps: Counter[str] = Counter()
        records: Counter[str] = Counter()
        for record in self.records:
            for name, count in record.bridges.items():
                steps[name] += count
                records[name] += 1
        return {name: (steps[name], records[name]) for name in sorted(steps)}

    def signatures(self) -> list[tuple[tuple[str, str, str], list[str]]]:
        """Divergence signatures, most records first, with every ``id@step``."""

        groups: dict[tuple[str, str, str], list[str]] = defaultdict(list)
        for record in self.records:
            if record.divergence is not None:
                groups[record.divergence.signature].append(
                    f"{record.id}@{record.divergence.index}"
                )
        return sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))

    def verdicts(self) -> dict[str, list[tuple[str, DifferingRun | int]]]:
        """Every verdict's items: (record id, run), or (id, firing point)."""

        items: dict[str, list[tuple[str, DifferingRun | int]]] = {
            verdict: [] for verdict in VERDICTS
        }
        for record in self.records:
            for run in record.runs:
                items[run.verdict].append((record.id, run))
            for point in record.lone_firings:
                items["bridge-without-hit"].append((record.id, point))
        return items

    def field_records(self, attribute: str) -> dict[str, int]:
        """Records per seatless field of ``reset_fields`` or ``drift_fields``."""

        counts: Counter[str] = Counter()
        for record in self.records:
            counts.update({seatless(name) for name in getattr(record, attribute)})
        return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))

    def unpositioned(self) -> dict[str, int]:
        counts: Counter[str] = Counter()
        for record in self.records:
            counts.update(record.unpositioned)
        return dict(sorted(counts.items()))

    def summary(self, *, examples: int = 20, findings: int = 200) -> dict[str, Any]:
        """The report as JSON data: counts, examples and capped finding lists."""

        verdicts: dict[str, Any] = {}
        listed: list[dict[str, Any]] = []
        for verdict, items in self.verdicts().items():
            fields: Counter[str] = Counter()
            entries = []
            for record_id, item in items:
                if isinstance(item, DifferingRun):
                    fields.update({seatless(name) for name in item.fields})
                    entry = {
                        "id": record_id,
                        "start": item.start,
                        "end": item.end,
                        "fields": list(item.fields),
                        "hit": None if item.hit is None else list(item.hit),
                    }
                else:
                    entry = {"id": record_id, "firing": item}
                entries.append(entry)
            verdicts[verdict] = {
                "count": len(items),
                "records": len({record_id for record_id, _ in items}),
                "fields": dict(fields.most_common()),
                "examples": entries[:examples],
            }
            if verdict != "bridged-window":
                listed.extend({"verdict": verdict, **entry} for entry in entries)
        return {
            "corpus": self.corpus,
            "corpus_codec": self.corpus_codec,
            "engine_codec": self.engine_codec,
            "migration": self.migration,
            "around": list(self.around),
            "bridge": self.bridge,
            "window": self.window,
            "records": self.selected(),
            "controls": self.controls(),
            "outcomes": self.outcomes(),
            "control_outcomes": self.outcomes(control=True),
            "controls_not_exact_or_equal": [
                f"{record.id} {record.outcome}"
                for record in self.records
                if record.control and record.outcome not in ("exact", "equal")
            ],
            "bridges": {
                name: {"steps": steps, "records": records}
                for name, (steps, records) in self.bridge_totals().items()
            },
            "schema_drift": self.drift,
            "reset_fields": self.field_records("reset_fields"),
            "drift_fields": self.field_records("drift_fields"),
            "unpositioned_hit_keys": self.unpositioned(),
            "divergences": [
                {
                    "pending": signature[0],
                    "recorded": signature[1],
                    "reason": signature[2],
                    "records": len(ids),
                    "examples": ids[:3],
                }
                for signature, ids in self.signatures()
            ],
            "verdicts": verdicts,
            "findings": listed[:findings],
            "findings_total": len(listed),
            "failed": [
                {"id": record.id, "error": record.error}
                for record in self.records
                if record.outcome == "failed"
            ][:findings],
            "wall_seconds": round(self.wall_seconds, 1),
            "cpu_seconds": round(self.cpu_seconds(), 1),
        }


def control_rows(
    corpus: Corpus,
    rows: Sequence[CorpusRow],
    around: Sequence[str],
    count: int,
    *,
    natural: bool = True,
) -> list[CorpusRow]:
    """``count`` records outside ``rows`` with no key matching ``around``.

    They come round-robin over the corpus's (combo, mix) groups
    (``Corpus.pick``); they should check exact or equal.
    """

    if count <= 0:
        return []
    chosen = {row.id for row in rows}
    candidates = corpus.pick(without=around, natural=natural)
    return [row for row in candidates if row.id not in chosen][:count]


def check(
    corpus: Corpus,
    rows: Sequence[CorpusRow],
    *,
    engine: UprisingRulesEngine | None = None,
    migration: ModuleType | Path | None = None,
    around: Sequence[str] = (),
    bridge: str | None = None,
    window: int = DEFAULT_WINDOW,
    controls: int = 0,
    workers: int = 1,
    natural: bool = True,
    progress: Callable[[int, int], None] | None = None,
) -> CheckReport:
    """Compare ``rows`` (and ``controls`` control records) with their traces.

    ``migration`` is ``records.migration`` by default, or a module or the
    path of one (``load_migration``). ``around`` are index-key patterns
    whose hits the verdicts lean on; ``bridge`` names the bridge under
    review. ``workers`` processes (at most ``MAX_WORKERS``, under ``nice``)
    share the records; with more than one, ``engine`` must be ``None`` and
    a ``migration`` module must have a file. Nothing is written.
    """

    if not 1 <= workers <= MAX_WORKERS:
        raise ValueError(f"workers must be 1 to {MAX_WORKERS}")
    started = time.monotonic()
    if isinstance(migration, Path):
        migration = load_migration(migration)
    module = migration or records_migration
    source = getattr(module, "__file__", None)
    path = None if module is records_migration or source is None else Path(source)
    if workers > 1 and module is not records_migration and path is None:
        raise ValueError("a migration module without a file cannot go to workers")
    settings: dict[str, Any] = {
        "around": tuple(around),
        "bridge": bridge,
        "window": window,
    }
    tasks = [(row.id, False) for row in rows] + [
        (row.id, True)
        for row in control_rows(corpus, rows, around, controls, natural=natural)
    ]
    results: list[RecordCheck] = []
    classes: dict[str, list[str]] = {}
    if workers == 1:
        checker = _Checker(corpus, engine or UprisingRulesEngine(), module, **settings)
        for record_id, control in tasks:
            results.append(checker.run(checker.rows[record_id], control=control))
            if progress is not None:
                progress(len(results), len(tasks))
        classes = checker.classes
    else:
        if engine is not None:
            raise ValueError("an engine object cannot go to worker processes")
        chunks = [
            tasks[start : start + _CHECK_CHUNK]
            for start in range(0, len(tasks), _CHECK_CHUNK)
        ]
        with ProcessPoolExecutor(
            max_workers=workers,
            mp_context=get_context("spawn"),
            initializer=_start_worker,
            initargs=(corpus.path, path, settings),
        ) as pool:
            for chunk_results, chunk_classes in pool.map(_check_chunk, chunks):
                results.extend(chunk_results)
                for qualname, names in chunk_classes.items():
                    classes.setdefault(qualname, names)
                if progress is not None:
                    progress(len(results), len(tasks))
    return CheckReport(
        corpus=corpus.id,
        corpus_codec=int(corpus.manifest["action_codec_version"]),
        engine_codec=ACTION_CODEC_VERSION,
        migration=(
            "records.migration"
            if module is records_migration
            else str(path or module.__name__)
        ),
        around=tuple(around),
        bridge=bridge,
        window=window,
        records=tuple(results),
        drift=schema_drift(corpus.manifest["class_schema"], classes) if classes else {},
        wall_seconds=time.monotonic() - started,
    )
