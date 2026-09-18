"""CLI for checkpoint files: inspect, stamp for migration, migrate (``train`` extra)."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from dune_imperium.training.checkpoint import (
    load_checkpoint,
    save_checkpoint,
    stamp_checkpoint,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dune-imperium-checkpoint",
        description=(
            "Inspect training checkpoints, stamp format-1 files with their "
            "action catalog so a later codec change can migrate them, or write "
            "a checkpoint migrated to the current encodings."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="print what each file says")
    inspect.add_argument("paths", type=Path, nargs="+")
    stamp = commands.add_parser(
        "stamp",
        help=(
            "rewrite files written under the current versions with their "
            "template list and observation layout (in place)"
        ),
    )
    stamp.add_argument("paths", type=Path, nargs="+")
    migrate = commands.add_parser(
        "migrate",
        help="load a file (migrating it to the current versions) and save it anew",
    )
    migrate.add_argument("source", type=Path)
    migrate.add_argument("target", type=Path)
    return parser


def _describe(path: Path) -> str:
    _, info = load_checkpoint(path)
    migration = ""
    if info.migration is not None:
        migration = f"; migrated on load: {info.migration.describe()}"
    return (
        f"{path}: format {info.format}, codec v{info.action_codec_version}, "
        f"observation v{info.observation_version}, ruleset {info.ruleset}, "
        f"iteration {info.iteration}, actions {info.action_size}, hidden "
        f"{list(info.hidden)}, optimizer {'yes' if info.optimizer_state else 'no'}, "
        f"migratable {'yes' if info.migratable else 'no'}{migration}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    try:
        if arguments.command == "inspect":
            for path in arguments.paths:
                print(_describe(path))
        elif arguments.command == "stamp":
            for path in arguments.paths:
                stamp_checkpoint(path)
                print(f"stamped {_describe(path)}")
        else:
            network, info = load_checkpoint(arguments.source)
            if info.migration is None:
                print(f"{arguments.source} already matches the current versions")
            else:
                print(f"{arguments.source}: {info.migration.describe()}")
            # The migrated file is written without a codec: its template list
            # is re-derived by ``stamp`` if ever needed, and the optimizer
            # moments travel with it.
            save_checkpoint(
                arguments.target,
                network,
                ruleset=info.ruleset,
                iteration=info.iteration,
                metadata=info.metadata,
                optimizer_state=info.optimizer_state,
            )
            stamp_checkpoint(arguments.target)
            print(f"wrote {_describe(arguments.target)}")
    except (ValueError, OSError) as error:
        print(f"error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
