"""Extract the official rulebook's game icons into transparent PNGs.

Crops every icon in ``dune_imperium.display.icons.RULEBOOK_ICON_SOURCES`` out
of the pinned "Uprising Main Rulebook" PDF (``scripts/official-rule-sources.json``
key ``main``) using PyMuPDF, keys out the beige page background with Pillow,
and writes one transparent PNG per icon name into a local directory
(default: the gitignored ``assets/icons``).

This script depends on ``pymupdf`` and ``pillow``, which are not project
dependencies. Run it with ``uv run --with``:

    uv run --with pymupdf --with pillow scripts/extract_rulebook_icons.py

The icons are copyrighted Dire Wolf Digital artwork extracted for
machine-local UI use; the output directory is gitignored and must never be
committed, the same policy as the Dune Cards Hub card image cache
(``scripts/fetch_card_images.py``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import urllib.request
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING

from dune_imperium.display.icons import RULEBOOK_ICON_SOURCES, icon_filename

if TYPE_CHECKING:
    from PIL.Image import Image  # type: ignore[import-not-found]

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEST = REPOSITORY_ROOT / "assets" / "icons"
SOURCES_PATH = REPOSITORY_ROOT / "scripts" / "official-rule-sources.json"
SOURCE_KEY = "main"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="extract_rulebook_icons",
        description=(
            "Extract game icons from the official Uprising Main Rulebook PDF"
            " into transparent PNGs."
        ),
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST,
        help=f"target directory (default: {DEFAULT_DEST})",
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=None,
        help="use an existing local copy instead of downloading",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite PNGs that already exist",
    )
    parser.add_argument(
        "--tolerance",
        type=int,
        default=48,
        help="background colour distance tolerance (default: 48)",
    )
    return parser


def _verify_sha256(path: Path, expected: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise SystemExit(
            f"sha256 mismatch for {path}: expected {expected}, got {digest}."
            " The icon xrefs in dune_imperium.display.icons are pinned to"
            " the exact file version recorded in"
            f" {SOURCES_PATH.relative_to(REPOSITORY_ROOT)}; a different file"
            " cannot be trusted to have the same image xrefs."
        )


def _resolve_pdf(pdf_argument: Path | None, tmp_dir: Path) -> Path:
    sources = json.loads(SOURCES_PATH.read_text())
    entry = sources[SOURCE_KEY]
    expected_sha256 = entry["sha256"]

    if pdf_argument is not None:
        _verify_sha256(pdf_argument, expected_sha256)
        return pdf_argument

    url = entry["url"]
    destination = tmp_dir / "main-rulebook.pdf"
    print(f"downloading {url} ...")
    urllib.request.urlretrieve(url, destination)  # noqa: S310
    _verify_sha256(destination, expected_sha256)
    return destination


def _background_colour(
    image: Image,
) -> tuple[int, int, int]:
    width, height = image.size
    corners = [
        image.getpixel((0, 0)),
        image.getpixel((width - 1, 0)),
        image.getpixel((0, height - 1)),
        image.getpixel((width - 1, height - 1)),
    ]
    r = sum(c[0] for c in corners) / 4
    g = sum(c[1] for c in corners) / 4
    b = sum(c[2] for c in corners) / 4
    return (round(r), round(g), round(b))


def _key_out_background(
    image: Image, background: tuple[int, int, int], tolerance: int
) -> Image:
    width, height = image.size
    pixels = image.load()
    tolerance_squared = tolerance * tolerance
    bg_r, bg_g, bg_b = background

    def close_to_background(x: int, y: int) -> bool:
        r, g, b, _a = pixels[x, y]
        distance_squared = (r - bg_r) ** 2 + (g - bg_g) ** 2 + (b - bg_b) ** 2
        return bool(distance_squared <= tolerance_squared)

    visited = [[False] * width for _ in range(height)]
    queue: deque[tuple[int, int]] = deque()

    def enqueue_if_matching(x: int, y: int) -> None:
        if visited[y][x]:
            return
        if not close_to_background(x, y):
            return
        visited[y][x] = True
        queue.append((x, y))

    for x in range(width):
        enqueue_if_matching(x, 0)
        enqueue_if_matching(x, height - 1)
    for y in range(height):
        enqueue_if_matching(0, y)
        enqueue_if_matching(width - 1, y)

    while queue:
        x, y = queue.popleft()
        r, g, b, _a = pixels[x, y]
        pixels[x, y] = (r, g, b, 0)
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height and not visited[ny][nx]:
                enqueue_if_matching(nx, ny)

    return image


def _crop_to_content(image: Image) -> Image:
    from PIL import Image as PILImage  # type: ignore[import-not-found]

    bbox = image.getbbox()
    if bbox is None:
        return image
    left, top, right, bottom = bbox
    cropped = image.crop((left, top, right, bottom))
    width, height = cropped.size
    padded = PILImage.new("RGBA", (width + 2, height + 2), (0, 0, 0, 0))
    padded.paste(cropped, (1, 1))
    return padded


def _extract_icon(
    doc: object,
    name: str,
    page: int,
    xref: int,
    dest: Path,
    tolerance: int,
) -> str | None:
    import pymupdf  # type: ignore[import-not-found]
    from PIL import Image

    page_object = doc[page - 1]  # type: ignore[index]
    present_xrefs = {info["xref"] for info in page_object.get_image_info(xrefs=True)}
    if xref not in present_xrefs:
        return (
            f"xref {xref} not found on page {page} of the rulebook"
            f" (icon {name!r})"
        )

    pixmap = pymupdf.Pixmap(doc, xref)
    if pixmap.n - pixmap.alpha >= 4:
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pixmap)

    import io

    image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGBA")
    background = _background_colour(image)
    image = _key_out_background(image, background, tolerance)
    image = _crop_to_content(image)
    image.save(dest / icon_filename(name))
    return None


def main(argv: list[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)

    try:
        import pymupdf  # noqa: F401  # type: ignore[import-not-found]
    except ImportError:
        print(
            "pymupdf is required; run with"
            " `uv run --with pymupdf --with pillow"
            " scripts/extract_rulebook_icons.py`",
            file=sys.stderr,
        )
        return 1
    try:
        import PIL  # noqa: F401
    except ImportError:
        print(
            "pillow is required; run with"
            " `uv run --with pymupdf --with pillow"
            " scripts/extract_rulebook_icons.py`",
            file=sys.stderr,
        )
        return 1

    arguments.dest.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    written = 0
    kept = 0

    with tempfile.TemporaryDirectory() as tmp_dir_name:
        pdf_path = _resolve_pdf(arguments.pdf, Path(tmp_dir_name))
        doc = pymupdf.open(pdf_path)
        try:
            for name, (page, xref) in RULEBOOK_ICON_SOURCES.items():
                target = arguments.dest / icon_filename(name)
                if target.is_file() and not arguments.force:
                    kept += 1
                    print(f"kept    {name}")
                    continue
                error = _extract_icon(
                    doc, name, page, xref, arguments.dest, arguments.tolerance
                )
                if error is not None:
                    failures.append(f"{name}: {error}")
                    print(f"FAIL {name}: {error}", file=sys.stderr)
                else:
                    written += 1
                    print(f"written {name}")
        finally:
            doc.close()

    total = len(RULEBOOK_ICON_SOURCES)
    print(
        f"done: {written} written, {kept} kept, {len(failures)} failed,"
        f" {total} total -> {arguments.dest}"
    )
    if failures:
        print("Some icons failed to extract.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
