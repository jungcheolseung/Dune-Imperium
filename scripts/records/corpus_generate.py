"""Generate a record corpus with the engine on the import path.

A record corpus is a set of AI games one engine played, kept as that
engine's own save-format v1 records, each with an index row of what it did
and a per-step trace of field digests (``dune_imperium.records.corpus``
reads it; ``dune_imperium.records.portable.trace`` has the formats). Run it
like ``old_engine_record.py``: the engine to record on the import path, this
checkout's interpreter and this script::

    PYTHONPATH=<engine checkout>/src <this checkout>/.venv/bin/python \\
        <this checkout>/scripts/records/corpus_generate.py local/records-corpus \\
        --standard

``--standard`` plays the standard plan (``STANDARD_PLAN``, 2,000 games);
``--combo C --mix M --seeds A-B`` plays one range. Seat ``i`` of seed ``s``
is ``make_agent(kind, s * 10 + i)``, so (engine commit, combo, mix, seed)
gives the same bytes again.

- The corpus is ``CORPUS_ROOT/v<codec>-<commit8>`` (``-r<R>`` with
  ``--rounds R``, which cuts every record after round R: for tests and
  trials, never for a real corpus). The commit is the HEAD of the checkout
  ``dune_imperium`` was imported from; a dirty ``src/`` there is refused,
  and so is a commit off master unless ``--branch-ok``.
- Seeds are split into shards of 250 games, ``shards/<combo>.<mix>.<lo>-<hi>``
  with three zstd-10 files (``.records.jsonl.zst``, ``.index.jsonl.zst``,
  ``.trace.bin.zst``, one line or trace per game in the same order) and a
  ``.meta.json`` written last. Games are played in chunks of 25 by
  ``--workers`` processes (default 3) under ``nice``.
- Every record is replayed once: that replay makes its state hash (checked
  against the played game), its index row and its trace.
- A game that raises is listed in its shard's ``failures``, not written.
- ``manifest.json`` is written last, rebuilt from every shard's meta, so a
  rerun keeps finished shards and plays only the missing ones.

The portable modules are loaded from this checkout by path under private
names, and the engine is touched only through the names
tests/unit/records/test_corpus_generate.py allows, so the script also runs
under older engines.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from compression import zstd
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.config import RulesetConfig
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.simulation.coverage import (
    collect_game_coverage,
    normalize_instance_id,
)

HERE = Path(__file__).resolve().parent
PORTABLE = HERE.parents[1] / "src" / "dune_imperium" / "records" / "portable"


def _load(name: str, path: Path) -> ModuleType:
    """Load ``path`` as module ``name``, apart from the engine's packages."""

    loaded = sys.modules.get(name)
    if loaded is not None and getattr(loaded, "__file__", None) == str(path):
        return loaded
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


trace = _load("_corpus_trace", PORTABLE / "trace.py")
record = _load("_corpus_record", HERE / "old_engine_record.py")

CORPUS_FORMAT = 1
SHARD_SIZE = 250
CHUNK_SIZE = 25
ZSTD_LEVEL = 10

# Module combinations, as ``--without`` lists: config.py's rules hold (Tech
# needs Bloodlines, Go to 11 needs Immortality). Prison Planet is drawn only
# without Immortality (content/arrakeen_scouts/missions.py).
COMBOS: dict[str, tuple[str, ...]] = {
    "full": (),
    "no-immortality": ("immortality", "go_to_11"),
    "no-tech": ("tech_module",),
    "no-bloodlines": ("bloodlines", "tech_module"),
    "no-scouts-epic": ("arrakeen_scouts", "epic_game"),
    "base": (
        "promo_cards",
        "bloodlines",
        "tech_module",
        "immortality",
        "go_to_11",
        "epic_game",
        "arrakeen_scouts",
    ),
}
# Seat mixes. Random seats reach declines the AIs never take.
MIXES: dict[str, tuple[str, ...]] = {
    "h4": ("heuristic",) * 4,
    "ha": ("heuristic", "app_ai", "heuristic", "app_ai"),
    "rhra": ("random", "heuristic", "random", "app_ai"),
    "a4": ("app_ai",) * 4,
}
# (combo, mix, games): 2,000 natural games, seeds 1..games each.
STANDARD_PLAN: tuple[tuple[str, str, int], ...] = (
    ("full", "h4", 500),
    ("full", "ha", 200),
    ("full", "rhra", 200),
    ("full", "a4", 100),
    ("no-immortality", "h4", 250),
    ("no-immortality", "ha", 100),
    ("no-immortality", "rhra", 50),
    ("no-tech", "h4", 150),
    ("no-bloodlines", "h4", 100),
    ("no-bloodlines", "rhra", 50),
    ("no-scouts-epic", "h4", 150),
    ("base", "h4", 100),
    ("base", "rhra", 50),
)
# The engine trees a corpus names (``git rev-parse <commit>:<path>``).
ENGINE_TREES = {
    "core": "src/dune_imperium/core",
    "rules": "src/dune_imperium/rules",
    "content": "src/dune_imperium/content",
    "adapters": "src/dune_imperium/adapters",
    "config.py": "src/dune_imperium/config.py",
}
AGENTS_TREE = "src/dune_imperium/agents"


@dataclass(frozen=True)
class EngineIdentity:
    """The engine checkout that plays a corpus."""

    commit: str
    on_master: bool
    engine_trees: dict[str, str]
    agents_tree: str


@dataclass(frozen=True)
class Request:
    """One requested seed range."""

    combo: str
    mix: str
    lo: int
    hi: int


@dataclass(frozen=True)
class ShardSpec:
    combo: str
    mix: str
    lo: int
    hi: int

    @property
    def stem(self) -> str:
        return f"{self.combo}.{self.mix}.{self.lo}-{self.hi}"


def _git(checkout: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(checkout), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed in {checkout}: {result.stderr}")
    return result.stdout.strip() if result.returncode == 0 else ""


def engine_identity(checkout: Path) -> EngineIdentity:
    """The commit and trees of ``checkout``; refuses a dirty ``src/``."""

    dirty = _git(checkout, "status", "--porcelain", "--", "src")
    if dirty:
        raise SystemExit(
            f"{checkout}/src has uncommitted changes, and a corpus names the "
            f"commit that played it:\n{dirty}"
        )
    commit = _git(checkout, "rev-parse", "HEAD")
    on_master = (
        subprocess.run(
            [
                "git",
                "-C",
                str(checkout),
                "merge-base",
                "--is-ancestor",
                commit,
                "master",
            ],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )
    trees = {
        name: _git(checkout, "rev-parse", f"{commit}:{path}", check=False)
        for name, path in ENGINE_TREES.items()
    }
    agents = _git(checkout, "rev-parse", f"{commit}:{AGENTS_TREE}", check=False)
    return EngineIdentity(commit, on_master, trees, agents)


def portable_tree() -> str:
    """The git tree hash of the portable folder's ``*.py`` files as loaded.

    It equals ``git rev-parse <commit>:src/dune_imperium/records/portable``
    when those files are committed and the folder holds nothing else.
    """

    entries = b""
    for path in sorted(PORTABLE.glob("*.py"), key=lambda item: item.name.encode()):
        data = path.read_bytes()
        blob = hashlib.sha1(b"blob %d\0" % len(data) + data).digest()
        entries += b"100644 " + path.name.encode() + b"\0" + blob
    return hashlib.sha1(b"tree %d\0" % len(entries) + entries).hexdigest()


def corpus_name(commit: str, rounds: int | None = None) -> str:
    cut = "" if rounds is None else f"-r{rounds}"
    return f"v{ACTION_CODEC_VERSION}-{commit[:8]}{cut}"


def combo_config(combo: str) -> Any:
    return RulesetConfig(**record.modules_with(COMBOS[combo]))


def ruleset_name(config: Any) -> str:
    identifier = str(getattr(config, "identifier", ""))
    return identifier + ("+draft" if getattr(config, "leader_draft", False) else "")


@dataclass
class IndexedGame:
    """One played game: its record line, index row and trace."""

    document: dict[str, Any]
    row: dict[str, Any]
    trace: bytes
    fields: tuple[str, ...]
    class_schema: dict[str, list[str]]


def index_game(
    engine: Any,
    combo: str,
    mix: str,
    seed: int,
    *,
    commit: str,
    rounds: int | None = None,
) -> IndexedGame:
    """Play one game and make its record, index row and trace in one replay."""

    config = combo_config(combo)
    seats = list(MIXES[mix])
    fingerprint = trace.Fingerprint()
    keys = trace.KeyIndex()
    writers: list[Any] = []

    def on_step(index: int, before: Any, step: Any, transition: Any) -> None:
        if not writers:
            writers.append(trace.TraceWriter(fingerprint(before)))
        decision = engine.current_decision(before)
        legal = (
            engine.legal_actions(before, decision.owner)
            if isinstance(decision, PlayerDecision)
            else ()
        )
        keys.add(
            index,
            trace.step_keys(
                before, step, transition, legal, normalize=normalize_instance_id
            ),
        )
        writers[0].step(fingerprint(transition.state))

    document, final = record.play_record(
        engine, config, seats, seed, rounds=rounds, commit=commit[:8], on_step=on_step
    )
    if not writers:
        writers.append(trace.TraceWriter(fingerprint(final)))
    record_id = f"{combo}.{mix}.{seed}"
    document["corpus"] = {
        "id": record_id,
        "combo": combo,
        "mix": mix,
        "seat_seeds": [seed * 10 + seat for seat in range(len(seats))],
        "steer": None,
        "branch_of": None,
        "branch_step": None,
    }
    phase = getattr(final.phase, "value", final.phase)
    leaders = [player.leader_id for player in final.players if player.leader_id]
    row = {
        "id": record_id,
        "shard": None,
        "line": None,
        "combo": combo,
        "ruleset": ruleset_name(config),
        "mix": mix,
        "seats": seats,
        "steer": None,
        "branch_of": None,
        "seed": seed,
        "steps": len(document["steps"]),
        "rounds": final.round_number,
        "cut_rounds": rounds,
        "finished": phase == "finished",
        "final_hash": document["expected_state_hash"],
        "errors": {},
        "keys": keys.row_keys(collect_game_coverage(final, ()), leaders),
    }
    assert fingerprint.names is not None
    return IndexedGame(
        document,
        row,
        writers[0].to_bytes(),
        fingerprint.names,
        fingerprint.class_schema,
    )


def play_chunk(task: dict[str, Any]) -> dict[str, Any]:
    """Play a chunk of one shard's seeds (a worker task)."""

    started = time.process_time()
    engine = UprisingRulesEngine()
    games: list[tuple[str, dict[str, Any], bytes]] = []
    failures: list[dict[str, Any]] = []
    fields: list[str] | None = None
    class_schema: dict[str, list[str]] = {}
    versions: dict[str, Any] = {}
    for seed in task["seeds"]:
        try:
            game = index_game(
                engine,
                task["combo"],
                task["mix"],
                seed,
                commit=task["commit"],
                rounds=task["rounds"],
            )
        except Exception as error:  # noqa: BLE001 - a failing game is a finding
            failures.append({"seed": seed, "error": f"{type(error).__name__}: {error}"})
            continue
        if fields is None:
            fields = list(game.fields)
        elif fields != list(game.fields):
            raise RuntimeError(f"seed {seed}: the fingerprint fields changed")
        for name, names in game.class_schema.items():
            class_schema.setdefault(name, names)
        versions = {
            key: game.document[key]
            for key in ("ruleset_version", "content_version", "action_codec_version")
        }
        line = json.dumps(game.document, separators=(",", ":"))
        games.append((line, game.row, game.trace))
    return {
        "stem": task["stem"],
        "first": task["seeds"][0],
        "games": games,
        "failures": failures,
        "fields": fields,
        "class_schema": class_schema,
        "versions": versions,
        "seconds": time.process_time() - started,
    }


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, data: bytes) -> None:
    partial = path.with_name(path.name + ".partial")
    partial.write_bytes(data)
    os.replace(partial, path)


def write_shard(
    shards_dir: Path, spec: ShardSpec, chunks: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    """Write one shard's three files, then its meta; return the meta."""

    chunks = sorted(chunks, key=lambda chunk: chunk["first"])
    lines: list[str] = []
    rows: list[str] = []
    traces: list[bytes] = []
    failures: list[dict[str, Any]] = []
    fields: list[str] | None = None
    class_schema: dict[str, list[str]] = {}
    versions: dict[str, Any] = {}
    for chunk in chunks:
        failures.extend(chunk["failures"])
        if chunk["fields"] is not None:
            if fields is not None and fields != chunk["fields"]:
                raise RuntimeError(f"{spec.stem}: the fingerprint fields changed")
            fields = chunk["fields"]
            versions = chunk["versions"]
        for name, names in chunk["class_schema"].items():
            class_schema.setdefault(name, names)
        for line, row, game_trace in chunk["games"]:
            row["shard"] = spec.stem
            row["line"] = len(lines)
            lines.append(line)
            rows.append(json.dumps(row, separators=(",", ":")))
            traces.append(game_trace)
    blobs = {
        "records": "".join(line + "\n" for line in lines).encode(),
        "index": "".join(row + "\n" for row in rows).encode(),
        "trace": trace.trace_header(len(fields or ())) + b"".join(traces),
    }
    suffixes = {
        "records": ".records.jsonl.zst",
        "index": ".index.jsonl.zst",
        "trace": ".trace.bin.zst",
    }
    sha256 = {}
    for name, blob in blobs.items():
        compressed = zstd.compress(blob, level=ZSTD_LEVEL)
        _write(shards_dir / f"{spec.stem}{suffixes[name]}", compressed)
        sha256[name] = _sha256(compressed)
    meta = {
        "stem": spec.stem,
        "combo": spec.combo,
        "modules": record.modules_with(COMBOS[spec.combo]),
        "mix": spec.mix,
        "seats": list(MIXES[spec.mix]),
        "steer": None,
        "seeds": [spec.lo, spec.hi],
        "games": len(lines),
        "failures": sorted(failures, key=lambda failure: failure["seed"]),
        "seconds": round(sum(chunk["seconds"] for chunk in chunks), 1),
        "sha256": sha256,
        "portable_tree": portable_tree(),
        "fingerprint_fields": fields,
        "class_schema": class_schema,
        "versions": versions,
    }
    _write(
        shards_dir / f"{spec.stem}.meta.json",
        json.dumps(meta, indent=1).encode(),
    )
    return meta


def plan_shards(requests: Sequence[Request]) -> list[ShardSpec]:
    """Split the requested ranges into shards of at most ``SHARD_SIZE``."""

    specs = []
    for request in requests:
        if request.combo not in COMBOS:
            raise SystemExit(f"unknown combo {request.combo!r}; one of {list(COMBOS)}")
        if request.mix not in MIXES:
            raise SystemExit(f"unknown mix {request.mix!r}; one of {list(MIXES)}")
        if not 0 <= request.lo <= request.hi:
            raise SystemExit(f"bad seed range {request.lo}-{request.hi}")
        for lo in range(request.lo, request.hi + 1, SHARD_SIZE):
            hi = min(lo + SHARD_SIZE - 1, request.hi)
            specs.append(ShardSpec(request.combo, request.mix, lo, hi))
    return specs


def read_metas(shards_dir: Path) -> dict[str, dict[str, Any]]:
    """Every finished shard's meta, by stem."""

    metas = {}
    for path in sorted(shards_dir.glob("*.meta.json")):
        meta = json.loads(path.read_text(encoding="utf-8"))
        metas[meta["stem"]] = meta
    return metas


def _check_overlaps(specs: Sequence[ShardSpec], metas: dict[str, Any]) -> None:
    taken = [
        (meta["combo"], meta["mix"], meta["seeds"][0], meta["seeds"][1], stem)
        for stem, meta in metas.items()
    ]
    for spec in specs:
        for combo, mix, lo, hi, stem in taken:
            if stem == spec.stem or (combo, mix) != (spec.combo, spec.mix):
                continue
            if spec.lo <= hi and lo <= spec.hi:
                raise SystemExit(f"seeds of {spec.stem} overlap the shard {stem}")
        taken.append((spec.combo, spec.mix, spec.lo, spec.hi, spec.stem))


def frame_catalog() -> list[str]:
    return [str(getattr(kind, "value", kind)) for kind in FrameKind]


def write_manifest(
    corpus_dir: Path,
    identity: EngineIdentity,
    plan: list[dict[str, Any]],
) -> dict[str, Any]:
    """Rebuild ``manifest.json`` from the shard metas; written last."""

    metas = read_metas(corpus_dir / "shards")
    fields: list[str] | None = None
    class_schema: dict[str, list[str]] = {}
    versions: dict[str, Any] = {}
    shards = []
    for stem, meta in sorted(metas.items()):
        if meta["fingerprint_fields"] is not None:
            if fields is not None and fields != meta["fingerprint_fields"]:
                raise SystemExit(f"{stem}: its fingerprint fields differ from others")
            fields = meta["fingerprint_fields"]
            versions = meta["versions"]
        for name, names in meta["class_schema"].items():
            if class_schema.setdefault(name, names) != names:
                raise SystemExit(f"{stem}: class {name} has other fields")
        shards.append(
            {
                key: meta[key]
                for key in (
                    "stem",
                    "combo",
                    "modules",
                    "mix",
                    "seats",
                    "steer",
                    "seeds",
                    "games",
                    "failures",
                    "seconds",
                    "sha256",
                )
            }
        )
    path = corpus_dir / "manifest.json"
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    manifest = {
        "corpus_format": CORPUS_FORMAT,
        "id": corpus_dir.name,
        "engine_commit": identity.commit,
        "on_master": identity.on_master,
        "engine_trees": identity.engine_trees,
        "agents_tree": identity.agents_tree,
        "portable_tree": portable_tree(),
        "action_codec_version": versions.get(
            "action_codec_version", ACTION_CODEC_VERSION
        ),
        "ruleset_version": versions.get("ruleset_version"),
        "content_version": versions.get("content_version"),
        "games": sum(shard["games"] for shard in shards),
        "fingerprint_fields": fields or [],
        "class_schema": dict(sorted(class_schema.items())),
        "unordered_zones": list(trace.UNORDERED),
        "frame_catalog": frame_catalog(),
        "plan": plan,
        "shards": shards,
        "situation_runs": previous.get("situation_runs", {}),
    }
    _write(path, json.dumps(manifest, indent=1).encode())
    return manifest


def generate(
    root: Path,
    requests: Sequence[Request],
    *,
    identity: EngineIdentity,
    workers: int = 3,
    rounds: int | None = None,
    branch_ok: bool = False,
    log: Callable[[str], None] = print,
) -> Path:
    """Play the missing shards of ``requests`` and rewrite the manifest."""

    if not identity.on_master and not branch_ok:
        raise SystemExit(
            f"{identity.commit[:8]} is not on master; pass --branch-ok to record "
            "a branch engine (the manifest says on_master: false)"
        )
    corpus_dir = root / corpus_name(identity.commit, rounds)
    shards_dir = corpus_dir / "shards"
    shards_dir.mkdir(parents=True, exist_ok=True)
    metas = read_metas(shards_dir)
    tree = portable_tree()
    for stem, meta in metas.items():
        if meta["portable_tree"] != tree:
            raise SystemExit(
                f"{stem} was written by other portable code ({meta['portable_tree']})"
            )
    specs = plan_shards(requests)
    _check_overlaps(specs, metas)
    todo = [spec for spec in specs if spec.stem not in metas]
    log(f"{corpus_dir}: {len(specs) - len(todo)} shards kept, {len(todo)} to play")

    tasks = []
    for spec in todo:
        seeds = list(range(spec.lo, spec.hi + 1))
        for start in range(0, len(seeds), CHUNK_SIZE):
            tasks.append(
                {
                    "stem": spec.stem,
                    "combo": spec.combo,
                    "mix": spec.mix,
                    "seeds": seeds[start : start + CHUNK_SIZE],
                    "rounds": rounds,
                    "commit": identity.commit,
                }
            )
    by_stem = {spec.stem: spec for spec in todo}
    waiting = {
        spec.stem: sum(1 for task in tasks if task["stem"] == spec.stem)
        for spec in todo
    }
    done: dict[str, list[dict[str, Any]]] = {spec.stem: [] for spec in todo}

    def finish(chunk: dict[str, Any]) -> None:
        stem = chunk["stem"]
        done[stem].append(chunk)
        if len(done[stem]) == waiting[stem]:
            meta = write_shard(shards_dir, by_stem[stem], done.pop(stem))
            log(
                f"  {stem}: {meta['games']} games, {len(meta['failures'])} failures, "
                f"{meta['seconds']} CPU s"
            )

    if workers <= 1:
        for task in tasks:
            finish(play_chunk(task))
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures: list[Future[dict[str, Any]]] = [
                pool.submit(play_chunk, task) for task in tasks
            ]
            for future in as_completed(futures):
                finish(future.result())

    previous = corpus_dir / "manifest.json"
    plan = (
        json.loads(previous.read_text(encoding="utf-8"))["plan"]
        if previous.exists()
        else []
    )
    for request in requests:
        entry = {
            "combo": request.combo,
            "mix": request.mix,
            "seeds": [request.lo, request.hi],
            "rounds": rounds,
        }
        if entry not in plan:
            plan.append(entry)
    manifest = write_manifest(corpus_dir, identity, plan)
    log(f"{corpus_dir}/manifest.json: {manifest['games']} games")
    return corpus_dir


def _seed_range(text: str) -> tuple[int, int]:
    lo, _, hi = text.partition("-")
    return int(lo), int(hi or lo)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="corpus_generate.py",
        description="Generate a record corpus with the engine on the import path.",
    )
    parser.add_argument(
        "root", type=Path, help="CORPUS_ROOT, e.g. local/records-corpus"
    )
    parser.add_argument("--standard", action="store_true", help="the 2,000-game plan")
    parser.add_argument("--combo", choices=sorted(COMBOS))
    parser.add_argument("--mix", choices=sorted(MIXES))
    parser.add_argument("--seeds", type=_seed_range, help="A-B")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument(
        "--rounds", type=int, help="cut every record after round R (tests, trials)"
    )
    parser.add_argument(
        "--branch-ok", action="store_true", help="record an engine off master"
    )
    args = parser.parse_args(argv)
    if args.standard:
        if args.combo or args.mix or args.seeds:
            parser.error("--standard takes no --combo, --mix or --seeds")
        requests = [
            Request(combo, mix, 1, games) for combo, mix, games in STANDARD_PLAN
        ]
    elif args.combo and args.mix and args.seeds:
        requests = [Request(args.combo, args.mix, *args.seeds)]
    else:
        parser.error("give --standard, or --combo, --mix and --seeds")
    identity = engine_identity(record.engine_checkout())
    os.nice(10)
    generate(
        args.root,
        requests,
        identity=identity,
        workers=args.workers,
        rounds=args.rounds,
        branch_ok=args.branch_ok,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
