"""CLI launching the local play server (requires the ``ui`` extra)."""

import argparse
from collections.abc import Sequence
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dune-imperium-server",
        description="Serve the local Dune: Imperium - Uprising play API.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="bind address (default: 127.0.0.1, local only)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="TCP port (default: 8000)",
    )
    parser.add_argument(
        "--saves-dir",
        type=Path,
        default=None,
        help="save-file directory (default: ~/.dune-imperium/saves)",
    )
    parser.add_argument(
        "--card-images-dir",
        type=Path,
        default=None,
        help=(
            "local card-image checkout with manifest.json (default: "
            "DUNE_IMPERIUM_CARD_IMAGE_DIR or the repository's assets/cards)"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    # Imported lazily so the CLI module stays importable without the extra.
    import uvicorn

    from dune_imperium.server.app import create_app

    uvicorn.run(
        create_app(
            saves_dir=arguments.saves_dir,
            card_images_dir=arguments.card_images_dir,
        ),
        host=arguments.host,
        port=arguments.port,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
