"""Command-line audit for the development-only DIU Imperium source."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from dune_imperium.content.diu import DiuDataError, audit_diu_imperium


def build_parser() -> argparse.ArgumentParser:
    """Build the DIU audit command-line parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Validate and normalize a DIU imperium.JSON against the local "
            "typed content identities without creating a runtime dependency."
        )
    )
    parser.add_argument("source", type=Path, help="path to DIU/data/imperium.JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Audit one explicitly supplied DIU source and print a stable summary."""

    args = build_parser().parse_args(argv)
    try:
        audit = audit_diu_imperium(args.source)
    except DiuDataError as error:
        print(f"DIU audit failed: {error}")
        return 2

    groups = Counter(card.group.value for card in audit.cards)
    print(f"source: {audit.source_path}")
    print(f"matched cards: {len(audit.cards)}")
    print(
        "groups: "
        + ", ".join(f"{group}={groups[group]}" for group in sorted(groups))
    )
    print(
        "copy mismatches ignored: "
        f"{len(audit.copy_mismatches)} (local manifest remains authoritative)"
    )
    print("effect types:")
    for effect_type, count in audit.effect_type_counts:
        print(f"  {effect_type}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
