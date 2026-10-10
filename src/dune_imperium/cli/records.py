"""CLI for recorded games (``records``): does each save still replay here?

``check`` reads every save in the saves folder, whatever engine wrote it,
keeps one save per game (``records.saves.one_save_per_game``), brings it
onto this engine (``records.migration``) and reports per game:
exact (replays as recorded), migrated (with the bridges it needed), or
diverged (the first recorded step this engine refuses, and what the engine
was waiting for instead). See docs/human-records.md.

``problems`` checks or scores a suite of judged human positions
(``records.problems``): ``check`` resolves every position on this engine,
``score`` asks agents for them.

``corpus`` reads a record corpus (``records.corpus``): ``list`` the corpora,
the ``keys`` of one with how many records and occurrences each has, and
``pick`` records by key patterns, optionally ``--export``-ing them as save
files ``check --every-save`` reads.
"""

import argparse
import json
import subprocess
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import ChanceDecision, Decision
from dune_imperium.core.replay import ReplayStep
from dune_imperium.paths import PROJECT_ROOT, SAVES_DIR
from dune_imperium.records.corpus import CORPUS_ROOT, Corpus, corpora
from dune_imperium.records.migration import MigratedRecord, migrate_record
from dune_imperium.records.problems import (
    DEFAULT_SUITE,
    Resolved,
    answer,
    load_suite,
    resolve,
    summarize,
)
from dune_imperium.records.saves import SavedGame, one_save_per_game, read_saved_game
from dune_imperium.rules import UprisingRulesEngine


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dune-imperium-records",
        description="Check that saved games still replay on this engine.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="replay every save on this engine")
    check.add_argument("--saves-dir", type=Path, default=SAVES_DIR)
    check.add_argument(
        "--every-save",
        action="store_true",
        help="check every save, not only the longest save of each game",
    )
    problems = sub.add_parser("problems", help="a suite of judged human positions")
    problems.add_argument("action", choices=("check", "score"))
    problems.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    problems.add_argument(
        "--agents", default="", help="comma-separated agent kinds (score)"
    )
    problems.add_argument("--seed", type=int, default=0)
    problems.add_argument("--json", type=Path, help="write every answer here")
    _add_corpus_parser(sub)
    return parser


def _add_corpus_parser(
    sub: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    corpus = sub.add_parser("corpus", help="read a record corpus")
    actions = corpus.add_subparsers(dest="corpus_command", required=True)
    listing = actions.add_parser("list", help="every corpus")
    keys = actions.add_parser("keys", help="records and occurrences per key")
    keys.add_argument("corpus", help="corpus id or folder")
    keys.add_argument("pattern", nargs="?", default="*", help="fnmatch pattern")
    keys.add_argument("--natural", action="store_true", help="natural games only")
    pick = actions.add_parser("pick", help="records by key patterns")
    pick.add_argument("corpus", help="corpus id or folder")
    pick.add_argument("--has", action="append", default=[], metavar="PATTERN")
    pick.add_argument(
        "--not", dest="without", action="append", default=[], metavar="PATTERN"
    )
    pick.add_argument("--min-count", type=int, default=1)
    pick.add_argument("--combo")
    pick.add_argument("--mix")
    pick.add_argument(
        "--steered", action="store_true", help="include steered and branched games"
    )
    pick.add_argument("--limit", type=int)
    pick.add_argument("--seed", type=int, default=0, help="shuffle within groups")
    pick.add_argument("--ids-out", type=Path, help="write the picked ids here")
    pick.add_argument("--export", type=Path, metavar="DIR", help="write save files")
    for parser in (listing, keys, pick):
        parser.add_argument("--root", type=Path, default=CORPUS_ROOT)


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "problems":
        return _problems(args)
    if args.command == "corpus":
        return _corpus(args)
    return _check(args.saves_dir, every_save=args.every_save)


# The engine trees a corpus names (scripts/records/corpus_generate.py).
_ENGINE_TREES = {
    "core": "src/dune_imperium/core",
    "rules": "src/dune_imperium/rules",
    "content": "src/dune_imperium/content",
    "adapters": "src/dune_imperium/adapters",
    "config.py": "src/dune_imperium/config.py",
}


def _head_engine_trees() -> dict[str, str] | None:
    """This checkout's engine trees at HEAD, or ``None`` without git."""

    trees = {}
    for name, path in _ENGINE_TREES.items():
        result = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "rev-parse", f"HEAD:{path}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        trees[name] = result.stdout.strip()
    return trees


def _corpus(args: argparse.Namespace) -> int:
    if args.corpus_command == "list":
        found = corpora(args.root)
        print(f"{args.root}: {len(found)} corpora")
        head = _head_engine_trees() if found else None
        for corpus in found:
            manifest = corpus.manifest
            trees = manifest.get("engine_trees")
            match = "?" if head is None else "yes" if trees == head else "no"
            failures = sum(len(shard["failures"]) for shard in manifest["shards"])
            print(
                f"\n{corpus.id}  codec v{manifest['action_codec_version']}, "
                f"commit {str(manifest['engine_commit'])[:8]}, "
                f"{'on master' if manifest['on_master'] else 'off master'}, "
                f"engine trees match HEAD: {match}"
            )
            print(
                f"  {manifest['games']} games, {failures} failures, "
                f"{corpus.size() / 1e6:.1f} MB"
            )
            games = ", ".join(
                f"{combo}.{mix} {count}"
                for (combo, mix), count in corpus.games().items()
            )
            print(f"  {games}")
            runs = manifest.get("situation_runs") or {}
            if runs:
                print(f"  situation runs: {', '.join(sorted(runs))}")
        return 0
    corpus = Corpus.open(args.corpus, args.root)
    if args.corpus_command == "keys":
        counts = corpus.key_counts(args.pattern, natural=args.natural)
        rows = [row for row in corpus.rows() if row.natural or not args.natural]
        print(
            f"{corpus.id}: {len(counts)} keys match {args.pattern!r} "
            f"over {len(rows)} records"
        )
        print(f"{'records':>8} {'count':>8}  key")
        for key, (records, count) in counts.items():
            print(f"{records:8d} {count:8d}  {key}")
        return 0
    natural = not args.steered
    total = sum(1 for row in corpus.rows() if row.natural or not natural)
    picked = corpus.pick(
        args.has,
        args.without,
        combo=args.combo,
        mix=args.mix,
        natural=natural,
        min_count=args.min_count,
        limit=args.limit,
        seed=args.seed,
    )
    matched = len(
        corpus.pick(
            args.has,
            args.without,
            combo=args.combo,
            mix=args.mix,
            natural=natural,
            min_count=args.min_count,
        )
    )
    print(
        f"{corpus.id}: {matched} of {total} records match"
        + (f"; {len(picked)} picked" if len(picked) != matched else "")
    )
    for row in picked:
        hits = []
        for pattern in args.has:
            for key in sorted(row.matching(pattern, min_count=args.min_count)):
                first = row.first_step(key)
                at = "" if first is None else f"@{first}"
                hits.append(f"{key} x{row.count(key)}{at}")
        print(f"  {row.id}  {row.combo} {row.mix} {row.steps} steps  {'  '.join(hits)}")
    if args.ids_out is not None:
        args.ids_out.write_text(
            "".join(f"{row.id}\n" for row in picked), encoding="utf-8"
        )
    if args.export is not None:
        paths = corpus.export(picked, args.export)
        print(f"wrote {len(paths)} save files to {args.export}")
    return 0


def _problems(args: argparse.Namespace) -> int:
    suite = load_suite(args.suite)
    engine = UprisingRulesEngine()
    resolved = resolve(suite, engine)
    positions = [item for item in resolved.values() if isinstance(item, Resolved)]
    families = sorted({problem.family for problem in suite.problems})
    print(
        f"{args.suite}: {len(suite.problems)} problems "
        f"({', '.join(families)}), {len(positions)} resolve on this engine "
        f"(codec v{ACTION_CODEC_VERSION})"
    )
    for problem_id, item in resolved.items():
        if not isinstance(item, Resolved):
            print(f"  unresolved {problem_id}: {item}")
    if args.action == "check":
        return 0 if len(positions) == len(suite.problems) else 1
    kinds = [kind for kind in args.agents.split(",") if kind]
    if not kinds:
        raise SystemExit("score needs --agents")
    report: dict[str, object] = {}
    for kind in kinds:
        answers = [answer(position, kind, args.seed, engine) for position in positions]
        summary = summarize(answers)
        report[kind] = {
            "summary": summary,
            "answers": [asdict(item) for item in answers],
        }
        print(f"\n## {kind}")
        print("group                         n  right  wrong neither  p(right) share")
        for name, row in summary.items():
            p_right = row["mean_p_right"]
            share = row["mean_pair_share"]
            print(
                f"{name:28s} {row['n']:3d} {row['right']:6.0%} {row['wrong']:6.0%}"
                f" {row['neither']:7.0%}"
                f"  {'' if p_right is None else f'{p_right:7.3f}'}"
                f"  {'' if share is None else f'{share:5.3f}'}"
            )
    if args.json is not None:
        args.json.write_text(
            json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    return 0


def _check(directory: Path, *, every_save: bool) -> int:
    games: list[SavedGame] = []
    unreadable: list[str] = []
    for path in sorted(directory.glob("*.json")):
        try:
            games.append(read_saved_game(path))
        except (OSError, ValueError) as error:
            unreadable.append(f"{path.name}: {error}")
    if not every_save:
        games = one_save_per_game(games)

    engine = UprisingRulesEngine()
    counts = {"exact": 0, "migrated": 0, "diverged": 0, "failed": 0}
    print(f"{directory} (this engine: codec v{ACTION_CODEC_VERSION})")
    for game in games:
        print()
        print(_heading(game))
        try:
            record = migrate_record(game.parsed.replay, engine)
        except Exception as error:  # noqa: BLE001 - one game's engine error
            counts["failed"] += 1
            print(f"  failed: the engine raised {type(error).__name__}: {error}")
            continue
        outcome = (
            "exact" if record.exact else "migrated" if record.complete else "diverged"
        )
        counts[outcome] += 1
        for line in _outcome_lines(record, outcome):
            print(f"  {line}")
    for line in unreadable:
        print(f"\nunreadable {line}")
    print(
        f"\n{len(games)} games: {counts['exact']} exact, "
        f"{counts['migrated']} migrated, {counts['diverged']} diverged"
        + (f", {counts['failed']} failed" if counts["failed"] else "")
        + (f", {len(unreadable)} unreadable files" if unreadable else "")
    )
    return 0


def _heading(game: SavedGame) -> str:
    replay = game.parsed.replay
    seats = ", ".join(_seat_name(seat) for seat in game.parsed.seats)
    state = "finished" if game.finished else "unfinished"
    when = (game.saved_at or "?")[:16].replace("T", " ")
    return (
        f"{when}  {game.name or game.path.stem}  [{game.path.name}]\n"
        f"  codec v{replay.action_codec_version}, {len(replay.steps)} steps, "
        f"{state}; seats: {seats}"
    )


def _outcome_lines(record: MigratedRecord, outcome: str) -> list[str]:
    bridges = ", ".join(
        f"{name} {count}" for name, count in sorted(record.bridge_counts().items())
    )
    if outcome == "exact":
        return ["exact: replays as recorded"]
    if outcome == "migrated":
        return [f"migrated: every step applies; bridges: {bridges or 'none'}"]
    divergence = record.divergence
    assert divergence is not None
    total = len(record.replay.steps)
    lines = [
        f"diverged at step {divergence.recorded_index} of {total} "
        f"(round {record.state.round_number}): {_step_text(divergence.step)}",
        f"  this engine refused it: {divergence.reason}",
        f"  this engine waits for: {_decision_text(divergence.pending)}",
    ]
    if bridges:
        lines.append(f"  bridges before it: {bridges}")
    return lines


def _seat_name(seat: str) -> str:
    kind, _, path = seat.partition(":")
    return f"{kind}:{Path(path).name}" if path else seat


def _step_text(step: ReplayStep) -> str:
    if isinstance(step, DomainAction):
        arguments = ", ".join(f"{key}={value}" for key, value in step.arguments)
        return f"seat {step.actor} {step.action_id}({arguments})"
    return f"chance {step.decision_id}"


def _decision_text(decision: Decision | None) -> str:
    if decision is None:
        return "nothing (the game is over)"
    if isinstance(decision, ChanceDecision):
        return f"chance {decision.decision_id}"
    return f"seat {decision.owner}: {decision.prompt}"


if __name__ == "__main__":
    raise SystemExit(main())
