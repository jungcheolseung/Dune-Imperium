"""Percent-coordinate layout of the original Dune: Imperium board picture.

The play server can serve the original game's printed board
(``assets/board/imperium.jpg``, the English board of Tabletop Simulator mod
2354919205, 5000x4996 px; the assets README has its source) and the
browser draws an original game's live state over it the way
``display.board_layout`` does for the Uprising scan: a clickable hotspot
per board space, Agent tokens, Control markers and Maker bonus spice
(docs/base-game-and-ix-plan.md 18, stage P5b). Every value is a percentage
of the picture's width or height, in the same shapes and units as the
Uprising tables, so the page reads either board through one accessor
(``static/core.js`` ``boardLayout``).

``SPACE_BOXES`` are keyed by the engine's ids of the original board's 22
spaces (``content.imperium.board``), the three it shares with Uprising
(Arrakeen, Imperial Basin, Secrets) included: a space has its own box on
each board. The tracks (Influence, Score, strength, the Conflict and the
High Council) are not measured yet; until they are, the page keeps the
seats' counts in their panels (``static/panels.js`` ``textBoardStats``).

Measured 2026-10-29 from the pixels (a card-implementer agent's fits,
checked here on overlays drawn back from these numbers): each space box
follows the centre line of the white frame around the space's picture,
found from its edges' brightness profiles (straight to 0.03 px rms; each
edge good to about 0.3 px of the 5000-px picture). Twenty-one frames are
one size within a pixel (380.9 x 294.7 px); Sietch Tabr's prints 4.7 px
shorter. The frame is Uprising's shape, its top-right and bottom-left
corners cut at 45 degrees (``SPACE_FRAME_CUT``), except that the three
spaces whose Control flag hangs from that corner print it square
(``SQUARE_BOTTOM_LEFT``). A Control flag box is the centre line of the
banner's outline, top where its side lines start under the frame, bottom
at its tips; a Maker spot is the centre of the inner hexagon printed for
the bonus spice; the Mentat point is the centre of the black silhouette
the Mentat space prints for the piece, and its height the silhouette's.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final

SPACE_BOXES: Final[Mapping[str, tuple[float, float, float, float]]] = (
    MappingProxyType(
        {
            # Emperor
            "conspire": (13.35, 7.32, 7.62, 5.91),
            "wealth": (13.35, 17.43, 7.62, 5.9),
            # Spacing Guild
            "imperium_heighliner": (13.32, 31.88, 7.61, 5.88),
            "foldspace": (13.33, 41.97, 7.61, 5.9),
            # Bene Gesserit
            "selective_breeding": (13.28, 56.34, 7.62, 5.91),
            "secrets": (13.28, 66.44, 7.62, 5.9),
            # Fremen
            "hardy_warriors": (13.27, 80.85, 7.61, 5.88),
            "stillsuits": (13.25, 90.98, 7.61, 5.89),
            # Landsraad
            "imperium_high_council": (31.81, 3.47, 7.62, 5.91),
            "hall_of_oratory": (63.19, 3.46, 7.61, 5.9),
            "mentat": (31.77, 12.16, 7.62, 5.9),
            "rally_troops": (48.61, 12.21, 7.64, 5.9),
            "imperium_swordmaster": (63.1, 12.13, 7.61, 5.89),
            # CHOAM
            "sell_melange": (79.92, 3.53, 7.62, 5.9),
            "secure_contract": (79.92, 12.19, 7.62, 5.9),
            # Arrakis
            "arrakeen": (76.13, 26.22, 7.62, 5.89),
            "carthag": (58.86, 29.48, 7.61, 5.9),
            "imperium_research_station": (42.69, 38.11, 7.64, 5.9),
            "imperium_sietch_tabr": (33.45, 48.92, 7.61, 5.8),
            "imperial_basin": (74.83, 41.36, 7.62, 5.9),
            "imperium_hagga_basin": (55.5, 47.4, 7.62, 5.9),
            "the_great_flat": (29.61, 58.83, 7.6, 5.89),
        }
    )
)
# The cut corners as percents of the box's width and height (45.9 px of
# the frame line each way).
SPACE_FRAME_CUT: Final = (12.0, 15.5)
SQUARE_BOTTOM_LEFT: Final = ("arrakeen", "carthag", "imperial_basin")
CONTROL_FLAG_BOXES: Final[Mapping[str, tuple[float, float, float, float]]] = (
    MappingProxyType(
        {
            "arrakeen": (76.32, 32.31, 3.14, 3.65),
            "carthag": (59.13, 35.58, 3.13, 3.66),
            "imperial_basin": (75.04, 47.45, 3.15, 3.67),
        }
    )
)
# The V notch's depth as a fraction of the flag's height.
CONTROL_FLAG_NOTCH: Final = 0.206
MAKER_SPICE_POINTS: Final[Mapping[str, tuple[float, float]]] = MappingProxyType(
    {
        "the_great_flat": (43.17, 61.73),
        "imperium_hagga_basin": (69.07, 50.4),
        "imperial_basin": (88.41, 44.45),
    }
)
# The hexagon's width (vertex to vertex) and height (flat to flat).
MAKER_SPICE_SIZE: Final = (2.76, 2.39)
MENTAT_POINT: Final[tuple[float, float] | None] = (44.62, 14.99)
MENTAT_HEIGHT: Final = 4.94


def imperium_board_layout() -> dict[str, Any]:
    """Return the layout as plain JSON-ready values (``server.catalog``)."""

    return {
        "space_boxes": {space: list(box) for space, box in SPACE_BOXES.items()},
        "space_frame": {
            "cut": list(SPACE_FRAME_CUT),
            "square_bottom_left": list(SQUARE_BOTTOM_LEFT),
        },
        "tracks": {
            "control_flags": {
                "boxes": {
                    space: list(box) for space, box in CONTROL_FLAG_BOXES.items()
                },
                "notch": CONTROL_FLAG_NOTCH,
            },
            "maker_spice": {
                "points": {
                    space: list(point) for space, point in MAKER_SPICE_POINTS.items()
                },
                "size": list(MAKER_SPICE_SIZE),
            },
        },
        "mentat": (
            None
            if MENTAT_POINT is None
            else {"point": list(MENTAT_POINT), "height": MENTAT_HEIGHT}
        ),
    }
