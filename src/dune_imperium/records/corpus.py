"""Read a record corpus: index rows, picks, records and their traces.

A record corpus is a set of AI games one engine played, written by that
engine itself (``scripts/records/corpus_generate.py``, run with the engine
on the import path). It lets a review of an engine change start from games
an older engine already played instead of playing new ones. This module only
reads the files; it never imports the old engine's code.

Layout, under ``CORPUS_ROOT`` (git-ignored ``local/records-corpus``)::

    v141-<commit8>/                     <codec>-<commit of the engine that played>
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
"""

import fnmatch
import hashlib
import json
import random
import re
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from compression import zstd
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from dune_imperium.core.replay import GameReplay
from dune_imperium.paths import LOCAL_DIR
from dune_imperium.records.portable.trace import (
    Fingerprint,
    TraceReader,
    trace_payloads,
)
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
        ``dune-imperium-records check --saves-dir`` reads (use
        ``--every-save``: records of one combo share a seed)."""

        out_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for row in rows:
            path = out_dir / f"{row.id}.json"
            path.write_text(
                json.dumps(self.document(row), separators=(",", ":")),
                encoding="utf-8",
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
