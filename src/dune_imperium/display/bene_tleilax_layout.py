"""Percent-coordinate layout of the Bene Tleilax board scan (Immortality).

The play server can serve one machine-local scan of the printed Bene
Tleilax board (``assets/board/bene_tleilax.jpg``, or
``DUNE_IMPERIUM_BENE_TLEILAX_IMAGE``) and the browser draws the live state
on top of it: each seat's research token on its hex, the Tleilaxu tokens on
the track, and the bank's spice on the track's fourth space.

Every value is a percentage of the image's width or height, so any scan
with the same framing works regardless of resolution. They were measured
on 2026-09-08 against the owner's 5551x3952 scan with a 5 % grid overlay;
a differently cropped scan needs a re-measure, not a rules change. The
space ids are the engine's (``content.immortality.board``), and the tests
pin that the table covers them exactly.

``RESEARCH_POINTS`` are hex centres (the token is drawn in the dark upper
half, above the printed bonus). ``TRACK_CELLS`` are ``(left, width)`` of the
eight Tleilaxu track spaces inside the top band.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final

# Column centres of the eight hex columns and the start piece on the left
# edge; rows step by 8.8 % (half a hex height).
_COLUMN_X: Final = (4.5, 14.5, 25.5, 36.5, 47.5, 58.5, 69.5, 80.5, 91.7)
_ROW_Y: Final = {1: 35.1, 2: 43.9, 3: 52.7, 4: 61.4, 5: 70.2, 6: 79.0}

RESEARCH_POINTS: Final[Mapping[str, tuple[float, float]]] = MappingProxyType(
    {
        f"c{column}r{row}": (_COLUMN_X[column], _ROW_Y[row])
        for column, rows in (
            (0, (3,)),
            (1, (3,)),
            (2, (2, 4)),
            (3, (1, 3, 5)),
            (4, (2, 4, 6)),
            (5, (1, 3, 5)),
            (6, (2, 4, 6)),
            (7, (1, 3, 5)),
            (8, (2, 4, 6)),
        )
        for row in rows
    }
)
# One hex's footprint (the start piece is a half hex of the same height).
HEX_SIZE: Final = (11.5, 17.5)

# The Tleilaxu track band and its eight spaces, left to right.
TRACK_BAND: Final = (3.0, 19.5)  # (top, height)
TRACK_CELLS: Final[tuple[tuple[float, float], ...]] = (
    (2.7, 13.3),
    (16.5, 10.5),
    (27.0, 10.5),
    (37.5, 10.5),
    (48.0, 22.5),
    (70.5, 10.0),
    (80.5, 7.5),
    (88.0, 10.0),
)
# The setup spice sits on the fourth space's printed "1st / 2" hex.
SPICE_POINT: Final = (65.0, 17.0)


def bene_tleilax_layout() -> dict[str, Any]:
    """Return the overlay layout as plain JSON-ready values."""

    return {
        "research_points": {
            space_id: [x, y] for space_id, (x, y) in RESEARCH_POINTS.items()
        },
        "hex_size": list(HEX_SIZE),
        "track_band": list(TRACK_BAND),
        "track_cells": [[left, width] for left, width in TRACK_CELLS],
        "spice_point": list(SPICE_POINT),
    }
