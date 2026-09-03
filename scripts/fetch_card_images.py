"""Fill gaps in a card-image checkout from the sources its manifest records.

The private ``Dune-Imperium-assets`` repository holds the card scans and
``cards/manifest.json`` (see ``dune_imperium.display.images``). Every
manifest entry records where its file came from (Dune Cards Hub URL and
sha256), so a checkout that is missing files — a fresh clone that only
took the manifest, or a newly added entry — can be completed with:

    uv run scripts/fetch_card_images.py            # assets/cards
    uv run scripts/fetch_card_images.py --dest ../Dune-Imperium-assets/cards

Files are written to ``<dest>/en/<path>`` and verified against the
manifest's sha256; existing files are kept unless ``--force`` is given.
The images are machine-local reference material per ``AGENTS.md``: never
commit them to this repository, and treat Dune Cards Hub as a visual
reference, not a rules authority. Direct requests without browser-like
headers get HTTP 403, hence the User-Agent and Referer below.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEST = REPOSITORY_ROOT / "assets" / "cards"
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
            "Download the card images a manifest records but the checkout lacks."
        ),
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST,
        help=f"cards directory holding manifest.json (default: {DEFAULT_DEST})",
    )
    parser.add_argument(
        "--set",
        dest="sets",
        action="append",
        help="only entries of this set (repeatable; default: every set)",
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


def _fetch(url: str, expected_sha256: str) -> bytes:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        payload: bytes = response.read()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected_sha256:
        raise ValueError(f"sha256 mismatch: expected {expected_sha256}, got {digest}")
    return payload


def main(argv: list[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    manifest_path = arguments.dest / "manifest.json"
    if not manifest_path.is_file():
        print(f"no manifest at {manifest_path}", file=sys.stderr)
        return 1
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Several entries may share one file (the Uprising starting deck reuses
    # the base-game scans), so work per path.
    targets: dict[str, dict[str, str]] = {}
    for entry in document["entries"]:
        if arguments.sets and entry["set"] not in arguments.sets:
            continue
        targets.setdefault(entry["path"], entry["source"])

    if arguments.dry_run:
        for relative, source in sorted(targets.items()):
            present = (arguments.dest / "en" / relative).is_file()
            marker = "have" if present and not arguments.force else "need"
            print(f"{marker}  {relative}  <- {source['url']}")
        return 0

    downloaded = 0
    skipped = 0
    failures: list[str] = []
    for relative, source in sorted(targets.items()):
        target = arguments.dest / "en" / relative
        if target.is_file() and not arguments.force:
            skipped += 1
            continue
        try:
            payload = _fetch(source["url"], source["sha256"])
        except (urllib.error.URLError, ValueError, TimeoutError) as error:
            failures.append(f"{relative}: {error}")
            print(f"FAIL {relative}: {error}", file=sys.stderr)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            downloaded += 1
            print(f"ok   {relative}")
        time.sleep(arguments.delay)

    print(
        f"done: {downloaded} downloaded, {skipped} already present,"
        f" {len(failures)} failed, {len(targets)} total -> {arguments.dest}"
    )
    if failures:
        print("Some files failed; rerun to retry only the gaps.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
