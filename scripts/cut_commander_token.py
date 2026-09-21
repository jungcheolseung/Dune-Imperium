#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "numpy",
#   "pillow",
#   "pypdfium2",
#   "scipy",
# ]
# ///
"""Cut the Sardaukar Commander figure out of the official Bloodlines rulebook.

The board UI stands a Commander on each space that still holds one, as the
rulebook's setup photo does [Bloodlines p. 3]. Its picture is the figure on
the components page [Bloodlines p. 2]: two JPEG tiles (the figure and its
base) over a flat beige ground, with the drop shadow baked in around them.
This stacks the tiles and keys the ground out:

- the shadow is the ground darkened, the same hue at a lower level, so a
  pixel belongs to the ground or its shadow when it lies on the ground
  colour's line through black; the figure is a pinker grey and leaves it;
- the blade is beige like the ground, so it is found as a bright ridge
  across the shadow it cuts and kept in a band that narrows to the tip.

Usage (the PDF from ``scripts/prepare_official_rules.py --source bloodlines``,
which pins its sha256)::

    scripts/cut_commander_token.py [--pdf PATH] [--out PATH]

The output is copyrighted artwork and belongs in the private assets checkout
(``assets/tokens/sardaukar_commander.png``), never in this repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw
from PIL import Image
from scipy import ndimage

REPO = Path(__file__).resolve().parents[1]
SOURCES = REPO / "scripts" / "official-rule-sources.json"
DEFAULT_PDF = (
    Path(tempfile.gettempdir()) / "dune-imperium-official-rules" / "di-bloodlines.pdf"
)
DEFAULT_OUT = REPO / "assets" / "tokens" / "sardaukar_commander.png"

# The figure on p. 2 sits in this box (PDF points, left/bottom/right/top);
# inside it are the soft shadow (154x219) and the two figure tiles (130 wide).
PAGE_INDEX = 1
FIGURE_BOX = (460.0, 650.0, 545.0, 765.0)
TILE_WIDTH = 130
GROUND = np.array([231.0, 219.0, 202.0])


def figure_tiles(pdf_path: Path) -> np.ndarray:
    """The figure's two tiles from p. 2, stacked top to bottom (RGB, float)."""

    page = pdfium.PdfDocument(str(pdf_path))[PAGE_INDEX]
    tiles = []
    images = page.get_objects(filter=(pdfium_raw.FPDF_PAGEOBJ_IMAGE,), max_depth=5)
    for image in images:
        left, bottom, right, top = image.get_bounds()
        inside = (
            left >= FIGURE_BOX[0]
            and bottom >= FIGURE_BOX[1]
            and right <= FIGURE_BOX[2]
            and top <= FIGURE_BOX[3]
        )
        picture = image.get_bitmap(render=False).to_pil().convert("RGB")
        if inside and picture.width == TILE_WIDTH:
            tiles.append((top, np.asarray(picture).astype(float)))
    if len(tiles) != 2:
        raise SystemExit(f"expected the two figure tiles on p. 2, found {len(tiles)}")
    tiles.sort(key=lambda tile: -tile[0])
    return np.vstack([tiles[0][1], tiles[1][1]])


def cut(figure: np.ndarray) -> Image.Image:
    """Key the ground and its shadow out of the stacked figure."""

    height, width = figure.shape[:2]
    level = (figure @ GROUND) / (GROUND @ GROUND)
    off_hue = ndimage.gaussian_filter(
        np.sqrt(((figure - level[..., None] * GROUND) ** 2).sum(-1)), 0.8
    )
    from_ground = np.sqrt(((figure - GROUND) ** 2).sum(-1))
    lum = ndimage.gaussian_filter(figure.mean(-1), 0.6)

    # The blade: a bright ridge near the line from the hands to the tip.
    xs, ys = [], []
    for x in range(55, width):
        guess = 0.284 * x + 27.1
        score, y = max(
            (lum[y, x] - (lum[y - 3, x] + lum[y + 3, x]) / 2, y)
            for y in range(int(guess) - 6, int(guess) + 7)
            if 3 <= y < height - 3
        )
        if score > 4:
            xs.append(x)
            ys.append(y)
    ridge = ndimage.median_filter(np.array(ys, float), 7)
    centre = np.interp(np.arange(width), xs, ridge, left=np.nan, right=np.nan)
    rows, cols = np.mgrid[0:height, 0:width]
    taper = np.clip((cols - 55) / (width - 55), 0, 1)
    band = ~np.isnan(centre[cols]) & (
        np.abs(rows - np.nan_to_num(centre[cols])) <= 2.6 - 1.4 * taper
    )
    blade = band & (lum > ndimage.minimum_filter(lum, size=(9, 1)) + 6)

    # The figure: grow from clearly off-hue pixels into weaker ones.
    strong = off_hue > 4.5
    weak = (off_hue > 3.5) & (from_ground > 14)
    body = ndimage.binary_propagation(strong & weak, mask=weak | strong)
    body = ndimage.binary_opening(body & (from_ground > 10), iterations=1)
    labels, count = ndimage.label(body)
    sizes = ndimage.sum(body, labels, range(1, count + 1))
    body = labels == 1 + int(np.argmax(sizes))
    body = ndimage.binary_fill_holes(ndimage.binary_closing(body, iterations=2))
    body = ndimage.binary_erosion(body, iterations=1) | blade

    alpha = ndimage.gaussian_filter(body.astype(float), 0.6)
    weight = alpha[..., None]
    colour = np.where(
        weight > 0.05,
        (figure - (1 - weight) * GROUND) / np.maximum(weight, 0.05),
        0,
    )
    rgba = np.dstack([np.clip(colour, 0, 255), alpha * 255]).astype("uint8")
    return Image.fromarray(rgba, "RGBA")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    arguments = parser.parse_args()

    pinned = json.loads(SOURCES.read_text())["bloodlines"]["sha256"]
    actual = hashlib.sha256(arguments.pdf.read_bytes()).hexdigest()
    if actual != pinned:
        raise SystemExit(f"{arguments.pdf} is not the pinned rulebook ({actual})")

    picture = cut(figure_tiles(arguments.pdf))
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    picture.save(arguments.out, optimize=True)
    alpha = np.asarray(picture.getchannel("A")).astype(float) / 255
    rows, cols = np.nonzero(alpha > 0.5)
    low = rows > alpha.shape[0] * 0.78
    print(f"{arguments.out}: {picture.width}x{picture.height}")
    print(
        "base centre (fraction of the picture):",
        round(float(cols[low].mean()) / alpha.shape[1], 3),
        round(float(rows[low].mean()) / alpha.shape[0], 3),
    )


if __name__ == "__main__":
    main()
