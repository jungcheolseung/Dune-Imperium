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
the ``keys`` of one with how many records and occurrences each has,
``pick`` records by key patterns, optionally ``--export``-ing them as save
files ``check --every-save`` reads, and ``check`` its records on this engine
against their traces (``records.corpus.check``): outcomes, divergence
signatures, bridge counts and the verdict of every differing run of steps
around ``--around`` hits and the ``--bridge`` under review. It writes
nothing but the ``--json`` summary.
"""

import argparse
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import ChanceDecision, Decision
from dune_imperium.core.replay import ReplayStep
from dune_imperium.paths import PROJECT_ROOT, SAVES_DIR
from dune_imperium.records.corpus import (
    CORPUS_ROOT,
    DEFAULT_WINDOW,
    MAX_WORKERS,
    CheckReport,
    Corpus,
    CorpusRow,
    DifferingRun,
    check,
    corpora,
    load_migration,
    seatless,
)
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
    checking = actions.add_parser(
        "check", help="compare records with their traces on this engine"
    )
    checking.add_argument("corpus", help="corpus id or folder")
    chosen = checking.add_mutually_exclusive_group()
    chosen.add_argument("--ids", type=Path, metavar="FILE", help="one id per line")
    chosen.add_argument(
        "--has", action="extend", nargs="+", default=[], metavar="PATTERN"
    )
    checking.add_argument("--limit", type=int, help="at most this many records")
    checking.add_argument(
        "--steered", action="store_true", help="include steered and branched games"
    )
    checking.add_argument(
        "--around",
        action="extend",
        nargs="+",
        default=[],
        metavar="PATTERN",
        help="index keys whose hits the verdicts lean on",
    )
    checking.add_argument(
        "--bridge",
        action="extend",
        nargs="+",
        default=[],
        metavar="NAME",
        help="the bridges under review",
    )
    checking.add_argument("--window", type=int, default=DEFAULT_WINDOW)
    checking.add_argument(
        "--control",
        type=int,
        default=0,
        metavar="N",
        help="also check N records without --around hits",
    )
    checking.add_argument(
        "--migration-module",
        type=Path,
        metavar="PATH",
        help="a migration module to use instead of records.migration",
    )
    checking.add_argument(
        "--workers", type=int, default=1, help=f"processes, at most {MAX_WORKERS}"
    )
    checking.add_argument("--json", type=Path, metavar="OUT", help="write a summary")
    for parser in (listing, keys, pick, checking):
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
    try:
        corpus = Corpus.open(args.corpus, args.root)
    except FileNotFoundError as error:
        raise SystemExit(str(error)) from None
    if args.corpus_command == "check":
        return _corpus_check(corpus, args)
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
        print(
            f"wrote {len(paths)} save files to {args.export}, one per record; "
            f"check them with: dune-imperium-records check "
            f"--saves-dir {args.export} --every-save"
        )
    return 0


def _check_rows(corpus: Corpus, args: argparse.Namespace) -> list[CorpusRow]:
    natural = not args.steered
    if args.ids is None:
        rows = corpus.pick(args.has, natural=natural, limit=args.limit)
        total = sum(1 for row in corpus.rows() if row.natural or not natural)
        what = " and ".join(repr(pattern) for pattern in args.has) or "every record"
        print(
            f"{corpus.id}: checking {len(rows)} of {total} records ({what})",
            flush=True,
        )
        return rows
    ids = [
        line.strip()
        for line in args.ids.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    known = {row.id: row for row in corpus.rows()}
    unknown = [record_id for record_id in ids if record_id not in known]
    if unknown:
        raise SystemExit(f"{corpus.id} has no record {', '.join(unknown[:5])}")
    rows = [known[record_id] for record_id in dict.fromkeys(ids)]
    if args.limit is not None:
        rows = rows[: args.limit]
    print(f"{corpus.id}: checking {len(rows)} records from {args.ids}", flush=True)
    return rows


def _corpus_check(corpus: Corpus, args: argparse.Namespace) -> int:
    if not 1 <= args.workers <= MAX_WORKERS:
        raise SystemExit(f"--workers must be 1 to {MAX_WORKERS}")
    if args.migration_module is not None:
        try:
            load_migration(args.migration_module)
        except (OSError, ValueError) as error:
            raise SystemExit(f"--migration-module: {error}") from None
    rows = _check_rows(corpus, args)
    step = max(1, (len(rows) + args.control) // 10)

    def progress(done: int, total: int) -> None:
        if done == total or done // step != (done - 1) // step:
            print(f"  checked {done} of {total}", file=sys.stderr, flush=True)

    report = check(
        corpus,
        rows,
        migration=args.migration_module,
        around=args.around,
        bridge=args.bridge,
        window=args.window,
        controls=args.control,
        workers=args.workers,
        natural=not args.steered,
        progress=progress,
    )
    for line in check_lines(report):
        print(line)
    if report.controls() < args.control:
        print(
            f"only {report.controls()} of the {args.control} control records asked "
            f"for exist: records outside the selection without --around hits"
        )
    if args.json is not None:
        args.json.write_text(
            json.dumps(report.summary(), ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
        )
        print(f"wrote the summary to {args.json}")
    return 0


# Verdict findings listed one by one, per class.
_LISTED_FINDINGS = 12


def check_lines(report: CheckReport) -> list[str]:
    """``corpus check``'s readable report."""

    lines = [
        f"corpus {report.corpus} (codec v{report.corpus_codec}) on this engine "
        f"(codec v{report.engine_codec}), migration {report.migration}",
        f"around: {' '.join(report.around) or '-'}; "
        f"bridges under review: {', '.join(report.bridges) or '-'}; "
        f"window {report.window}",
        "",
    ]
    if report.drift:
        lines.append("schema drift (manifest class_schema against this engine):")
        for qualname, change in report.drift.items():
            if change.get("unmet"):
                lines.append(f"  {qualname}: no checked state held it")
                continue
            removed = ", ".join(change["removed"]) or "-"
            added = ", ".join(change["added"]) or "-"
            lines.append(
                f"  {qualname}: removed {removed} (absent from digests); "
                f"added {added} (left out)"
            )
    else:
        lines.append("schema drift: none")
    drift_fields = report.field_records("drift_fields")
    if drift_fields:
        lines.append("  fields it explains (kept out of outcomes and verdicts):")
        lines.extend(
            f"    {name} in {count} records" for name, count in drift_fields.items()
        )
    reset = report.field_records("reset_fields")
    if reset:
        lines.append(
            "fields that differ already at reset (kept out of outcomes and verdicts):"
        )
        lines.extend(f"  {name} in {count} records" for name, count in reset.items())
    else:
        lines.append("fields that differ already at reset: none")
    unpositioned = report.unpositioned()
    if unpositioned:
        lines.append("--around keys whose rows kept only the first step:")
        lines.extend(
            f"  {key} in {count} records" for key, count in unpositioned.items()
        )

    selected, controls = report.outcomes(), report.outcomes(control=True)
    lines += [
        "",
        f"{'outcome':12s} {'records':>8s}"
        + (f" {'controls':>9s}" if report.controls() else ""),
    ]
    for outcome, count in selected.items():
        lines.append(
            f"{outcome:12s} {count:8d}"
            + (f" {controls[outcome]:9d}" if report.controls() else "")
        )
    lines.append(
        f"{'total':12s} {report.selected():8d}"
        + (f" {report.controls():9d}" if report.controls() else "")
    )
    odd_controls = [
        f"{record.id} {record.outcome}"
        for record in report.records
        if record.control and record.outcome not in ("exact", "equal")
    ]
    if odd_controls:
        lines.append(f"controls not exact or equal: {', '.join(odd_controls)}")

    totals = report.bridge_totals()
    lines.append("")
    lines.append(
        "bridges: "
        + (
            ", ".join(
                f"{name} {steps} steps in {records} records"
                for name, (steps, records) in totals.items()
            )
            or "none fired"
        )
    )
    signatures = report.signatures()
    if signatures:
        lines.append("divergences (pending frame, recorded step, reason):")
        for (frame, step, reason), ids in signatures:
            lines.append(
                f"  {len(ids):5d}  pending {frame} at {step}: {reason}  "
                f"e.g. {', '.join(ids[:3])}"
            )

    verdicts = report.verdicts()
    lines += ["", f"{'verdict':20s} {'items':>6s} {'records':>8s}  fields"]
    for verdict, items in verdicts.items():
        fields: Counter[str] = Counter()
        for _, item in items:
            if isinstance(item, DifferingRun):
                fields.update({seatless(name) for name in item.fields})
        shown = ", ".join(f"{name} {count}" for name, count in fields.most_common(4))
        records = len({record_id for record_id, _ in items})
        lines.append(f"{verdict:20s} {len(items):6d} {records:8d}  {shown}")
    at_hit = report.divergence_hits()
    if at_hit:
        lines.append("diverged-at-hit by pending frame and hit:")
        for (frame, key), ids in at_hit:
            lines.append(
                f"  {len(ids):5d}  pending {frame} after {key}  "
                f"e.g. {', '.join(ids[:3])}"
            )
    for verdict, items in verdicts.items():
        if not items:
            continue
        lines.append(f"{verdict}:")
        for record_id, item in items[:_LISTED_FINDINGS]:
            lines.append(f"  {record_id} {_finding_text(item)}")
        if len(items) > _LISTED_FINDINGS:
            lines.append(f"  ... {len(items) - _LISTED_FINDINGS} more")

    failed = [record for record in report.records if record.outcome == "failed"]
    if failed:
        lines.append("")
        lines.append("failed:")
        lines.extend(f"  {record.id}: {record.error}" for record in failed)
    records = len(report.records)
    lines.append("")
    lines.append(
        f"{records} records in {report.wall_seconds:.1f} s wall, "
        f"{report.cpu_seconds():.1f} s cpu"
        + (f" ({report.cpu_seconds() / records:.2f} s per record)" if records else "")
    )
    return lines


def _finding_text(item: DifferingRun | int) -> str:
    if not isinstance(item, DifferingRun):
        return f"fired before step {item}"
    steps = (
        f"step {item.start}"
        if item.start == item.end
        else f"steps {item.start}-{item.end}"
    )
    hit = "" if item.hit is None else f"; hit {item.hit[1]} at {item.hit[0]}"
    ended = "" if item.ended_by is None else f"; ends where {item.ended_by} fires"
    fields = ", ".join(item.fields[:4]) + (" ..." if len(item.fields) > 4 else "")
    diverged = " (diverged)" if item.diverged else ""
    return f"{steps}{diverged}: {fields or 'no field differs'}{hit}{ended}"


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
