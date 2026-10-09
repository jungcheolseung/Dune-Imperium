"""CLI for recorded games (``records``): does each save still replay here?

``check`` reads every save in the saves folder, whatever engine wrote it,
keeps one save per game (``records.saves.one_save_per_game``), brings it
onto this engine (``records.migration``) and reports per game:
exact (replays as recorded), migrated (with the bridges it needed), or
diverged (the first recorded step this engine refuses, and what the engine
was waiting for instead). See docs/human-records.md.
"""

import argparse
from collections.abc import Sequence
from pathlib import Path

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import ChanceDecision, Decision
from dune_imperium.core.replay import ReplayStep
from dune_imperium.paths import SAVES_DIR
from dune_imperium.records.migration import MigratedRecord, migrate_record
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return _check(args.saves_dir, every_save=args.every_save)


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
