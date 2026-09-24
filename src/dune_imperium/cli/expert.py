"""Expert iteration from the command line.

    uv run python -m dune_imperium.cli.expert collect --teacher P \\
        --start-seed S --games N --workers W --out DIR

``collect`` labels greedy self-play games with the teacher's search and
writes one ``g<seed>.npz`` per game (``training.expert``); it prints one
JSON summary line and exits 2 when more than 5% of the games failed.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

FAILURE_LIMIT = 0.05


def _collect(arguments: argparse.Namespace) -> int:
    from dune_imperium.training.expert import LabelConfig, collect_to_directory

    config = LabelConfig(
        label_probability=arguments.label_probability,
        anchor_probability=arguments.anchor_probability,
        rollouts=arguments.rollouts,
        candidates=arguments.candidates,
    )
    summary = collect_to_directory(
        arguments.teacher,
        Path(arguments.out),
        start_seed=arguments.start_seed,
        games=arguments.games,
        workers=arguments.workers,
        config=config,
    )
    print(json.dumps(summary), flush=True)
    attempted = int(summary["games"]) + int(summary["failures"])  # type: ignore[call-overload]
    if attempted and int(summary["failures"]) > FAILURE_LIMIT * attempted:  # type: ignore[call-overload]
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dune_imperium.cli.expert")
    commands = parser.add_subparsers(dest="command", required=True)
    collect = commands.add_parser("collect", help="label greedy self-play games")
    collect.add_argument("--teacher", required=True, help="checkpoint path")
    collect.add_argument("--start-seed", type=int, required=True)
    collect.add_argument("--games", type=int, required=True)
    collect.add_argument("--workers", type=int, default=1)
    collect.add_argument("--out", required=True, help="directory for g<seed>.npz")
    collect.add_argument("--label-probability", type=float, default=0.5)
    collect.add_argument("--anchor-probability", type=float, default=0.25)
    collect.add_argument("--rollouts", type=int, default=4)
    collect.add_argument("--candidates", type=int, default=3)
    collect.set_defaults(handler=_collect)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    handler = arguments.handler
    result: int = handler(arguments)
    return result


if __name__ == "__main__":
    sys.exit(main())
