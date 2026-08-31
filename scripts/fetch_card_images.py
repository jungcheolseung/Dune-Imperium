"""Download the Uprising card images the browser UI can display.

Fetches exactly the file set enumerated by
``dune_imperium.display.images.required_images()`` (166 files as of
2026-08-31) from Dune Cards Hub into the gitignored local cache
``downloads/dunecardshub/cards/`` — the directory the play server mounts at
``/card-images``. Existing files are kept unless ``--force`` is given, so
reruns only fill gaps.

Run inside the project environment (the script imports the package):

    uv run scripts/fetch_card_images.py

Images are a machine-local convenience per ``AGENTS.md`` and
``docs/implementation-plan.md``: they are never committed to the repository,
and Dune Cards Hub is a card/visual reference, not a rules authority. The
server degrades to text-only when the cache is absent, so this script is
optional. Direct requests without browser-like headers get HTTP 403, hence
the User-Agent and Referer below.
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from dune_imperium.display.images import required_images

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEST = REPOSITORY_ROOT / "downloads" / "dunecardshub" / "cards"
BASE_URL = "https://dunecardshub.com/images/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Referer": "https://dunecardshub.com/uprising",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fetch_card_images",
        description=(
            "Download the Dune Cards Hub images the local play UI can show."
        ),
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST,
        help=f"target directory (default: {DEFAULT_DEST})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.4,
        help="seconds to wait between downloads (default: 0.4)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-download files that already exist",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list what would be downloaded without fetching anything",
    )
    return parser


def _fetch(filename: str) -> bytes:
    request = urllib.request.Request(BASE_URL + filename, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        payload: bytes = response.read()
    if payload[:4] != b"RIFF" or payload[8:12] != b"WEBP":
        raise ValueError("response is not a WebP image")
    return payload


def main(argv: list[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    entries = required_images()

    if arguments.dry_run:
        for kind, content_id, filename in entries:
            present = (arguments.dest / filename).is_file()
            marker = "have" if present and not arguments.force else "need"
            print(f"{marker}  {kind}:{content_id}  {filename}")
        return 0

    arguments.dest.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    skipped = 0
    failures: list[str] = []
    for kind, content_id, filename in entries:
        target = arguments.dest / filename
        if target.is_file() and not arguments.force:
            skipped += 1
            continue
        try:
            payload = _fetch(filename)
        except (urllib.error.URLError, ValueError, TimeoutError) as error:
            failures.append(f"{kind}:{content_id} ({filename}): {error}")
            print(f"FAIL {filename}: {error}", file=sys.stderr)
        else:
            target.write_bytes(payload)
            downloaded += 1
            print(f"ok   {filename}")
        time.sleep(arguments.delay)

    print(
        f"done: {downloaded} downloaded, {skipped} already present,"
        f" {len(failures)} failed, {len(entries)} total -> {arguments.dest}"
    )
    if failures:
        print(
            "Some files failed; rerun to retry only the gaps.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
