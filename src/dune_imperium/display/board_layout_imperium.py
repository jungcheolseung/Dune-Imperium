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
High Council) follow below them, in the shapes of
``display.board_layout.marker_layout``; what Uprising prints and the
original does not (observation posts, Maker Hooks slots, the Shield Wall,
contract slots, Arrakeen Scouts regions) has no entry, and the page draws
none of it here.

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

from dune_imperium.display.board_layout import (
    AGENT_ON_SPACE_HEIGHT,
    COMMANDER_HEIGHT,
    CONFLICT_UNIT_GAP,
    CONFLICT_UNIT_MIN_SCALE,
    CONFLICT_UNIT_PADDING,
    GARRISON_UNIT_LINE,
    GARRISON_UNIT_MIN_SCALE,
    SANDWORM_WIDTH,
)

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

# The tracks, measured 2026-10-29 from the pixels like the spaces (a
# card-implementer agent's fits: edge half-maximum crossings, chevron V-fits
# and circle fits, each good to about 0.5 px unless said otherwise; checked
# here on overlays drawn back from these numbers).

# Influence: one vertical strip per Faction on the left edge, the same
# drawing four times (to 1 px) shifted down by ``INFLUENCE_STRIP_OFFSET_Y``.
# Level 0 is the row of four printed squares at a strip's bottom, levels
# 1..6 the chevron bands above it (taller towards the bottom, not evenly
# spaced): the Emperor strip's band centres, averaged over the four seat
# columns (the bands rise towards the strip's middle, so a column's own
# centre is up to 0.21 off, an eighth of a cube). The offsets come from the
# level-0 squares; the columns from the same squares (the lower strips drift
# up to 0.05 left). A cube is exactly one printed square (79.6 px).
INFLUENCE_LEVEL_Y: Final = (23.61, 20.24, 16.49, 12.63, 9.12, 6.1, 3.34)
INFLUENCE_STRIP_OFFSET_Y: Final[Mapping[str, float]] = MappingProxyType(
    {
        "emperor": 0.0,
        "spacing_guild": 24.6,
        "bene_gesserit": 49.04,
        "fremen": 73.56,
    }
)
INFLUENCE_SEAT_X: Final = (4.43, 6.38, 8.33, 10.28)
INFLUENCE_CUBE_SIZE: Final = 1.59
# "Place the four Alliance tokens on the marked areas of the Faction's
# Influence tracks" [DI p. 4]: the dashed ring around each strip's emblem
# (the Emperor strip's centre, and the dashes' diameter).
ALLIANCE_POINT: Final = (7.4, 5.82)
ALLIANCE_TOKEN_SIZE: Final = 6.84

# The Score track on the right edge, 0 at the bottom to 12 at the top: the
# column's centre, each cell's centre (the cells' chevron dividers; 9-12
# move a few px off the pitch, and 12, with no printed top divider, is one
# pitch tall), and one cell's (width, height).
VICTORY_POINT_X: Final = 96.36
VICTORY_POINT_Y: Final = (
    94.72,
    89.43,
    84.14,
    78.85,
    73.56,
    68.29,
    63.0,
    57.72,
    52.44,
    47.08,
    41.9,
    36.8,
    31.52,
)
VICTORY_POINT_CELL: Final = (4.55, 5.29)

# The combat strength track along the bottom: cells 1..10 on the upper row
# and 11..20 on the lower one (``STRENGTH_CELL_X[n]`` is printed number n's
# column, a straight 201.54 px pitch; index 0, one pitch left, is unused),
# the red number bands' centres and the open part above each band where a
# token lies. Strength 0 is a ring (3.1 across) on a lighter panel above
# "1" and "2" with a red "0" tab (``STRENGTH_ZERO_BOX``, the panel). The
# panel is too flat for the 2x2 the page lays in Uprising's framed square:
# laid there, two tokens at 0 read as a fan on cell 2. So the page treats
# the ring as a cell of its own (``STRENGTH_ZERO_POINT``, its centre), the
# tokens at 0 fanning on it like those that share a number.
STRENGTH_CELL_X: Final = (
    49.68,
    53.71,
    57.74,
    61.77,
    65.8,
    69.84,
    73.87,
    77.9,
    81.93,
    85.96,
    89.99,
)
STRENGTH_ROW_Y: Final = (93.01, 97.56)
STRENGTH_ZERO_BOX: Final = (51.76, 84.31, 7.92, 4.54)
STRENGTH_ZERO_POINT: Final = (55.65, 86.57)
STRENGTH_TOKEN_ROW_Y: Final = (90.78, 95.34)
STRENGTH_TOKEN_SIZE: Final = 3.0

# The Conflict area: the four printed circles are the garrisons ("Place
# three in one of the four circular garrisons on the game board" [DI p. 5]),
# ``(left, top, width, height)`` of each ring's outer edge (250.2 px
# radius), clockwise from the bottom-left for seats 0..3 as on Uprising's
# board. The Conflict is "the area of the game board in the center of the
# garrisons" [DI p. 10]; unlike Uprising's board, it prints no quadrants for
# the deployed units, only two crossed swords. The page still keeps each
# seat's units apart, in the quarter of the field nearest its garrison. The
# field runs between the ring columns (clear of the outer edge of both rings
# on a side), from the area's printed top line (60.3) to the strength panel
# (84.31); the rings' centres split it (``CONFLICT_CROSS``; the swords
# themselves cross lower, at 74.88).
GARRISON_RINGS: Final = (
    (51.93, 73.15, 10.01, 10.01),
    (51.95, 61.02, 10.01, 10.01),
    (81.39, 61.03, 10.01, 10.01),
    (81.38, 73.16, 10.01, 10.01),
)
CONFLICT_CROSS: Final = (71.66, 72.1)
_FIELD_LEFT, _FIELD_RIGHT = 61.96, 81.38
_FIELD_TOP, _FIELD_BOTTOM = 60.3, 84.31


def _box(
    left: float, top: float, right: float, bottom: float
) -> tuple[float, float, float, float]:
    return (left, top, round(right - left, 2), round(bottom - top, 2))


_CROSS_X, _CROSS_Y = CONFLICT_CROSS
CONFLICT_UNIT_BOXES: Final = (
    _box(_FIELD_LEFT, _CROSS_Y, _CROSS_X, _FIELD_BOTTOM),
    _box(_FIELD_LEFT, _FIELD_TOP, _CROSS_X, _CROSS_Y),
    _box(_CROSS_X, _FIELD_TOP, _FIELD_RIGHT, _CROSS_Y),
    _box(_CROSS_X, _CROSS_Y, _FIELD_RIGHT, _FIELD_BOTTOM),
)
# The pieces, each as large as the same piece elsewhere on this board
# (``display.board_layout`` gives the reasons): a troop is the Influence
# cube, an Agent and a Commander as tall as on a space (a frame is 294.7 px,
# Carthag's), a sandworm 3.6 wide; ``(width, height)`` on the 5000 x 4996
# picture. A quarter of the field is narrower than Uprising's (four troops
# a row), so a Conflict with figures shrinks its pieces sooner.
_PICTURE_WIDTH, _PICTURE_HEIGHT = 5000, 4996
_FRAME_HEIGHT = SPACE_BOXES["carthag"][3]


def _piece_by_height(height: float, aspect: float) -> tuple[float, float]:
    width_px = height / 100 * _PICTURE_HEIGHT * aspect
    return (round(width_px / _PICTURE_WIDTH * 100, 3), round(height, 3))


def _piece_by_width(width: float, aspect: float) -> tuple[float, float]:
    height_px = width / 100 * _PICTURE_WIDTH / aspect
    return (round(width, 3), round(height_px / _PICTURE_HEIGHT * 100, 3))


CONFLICT_UNIT_SIZES: Final[Mapping[str, tuple[float, float]]] = MappingProxyType(
    {
        "troop": _piece_by_width(INFLUENCE_CUBE_SIZE, 1.0),
        "commander": _piece_by_height(_FRAME_HEIGHT * COMMANDER_HEIGHT, 130 / 195),
        "agent": _piece_by_height(_FRAME_HEIGHT * AGENT_ON_SPACE_HEIGHT, 52 / 81),
        "sandworm": _piece_by_width(SANDWORM_WIDTH, 62 / 57),
    }
)
# The packing constants are Uprising's, except the garrison's padding: on
# these slightly smaller rings 0.3 lays a full garrison of 12 troops in four
# rows, 0.29 in the intended three rows of four.
GARRISON_UNIT_PADDING: Final = 0.29

# Where the seat to move sends and takes back its units on the board: plain
# desert above the Conflict, between Hagga Basin's panel and the Conflict
# area's top line (60.29), centred over the field. Nothing larger is free
# near the Conflict, so it is lower than Uprising's (8.5); only map art (a
# road and a dotted strip) runs through it.
FORCE_STEPPER_BAND: Final = (58.0, 54.54, 27.4, 5.54)

# The four High Council chairs, left to right (a "2" diamond stands between
# the second and third), and the player disc: the chair circle's outer
# diameter (147.5 px), as a percent of the picture's width.
COUNCIL_SEATS: Final = ((42.04, 6.32), (45.33, 6.32), (52.75, 6.3), (56.04, 6.3))
SEAT_DISC_SIZE: Final = 2.95

# Two faint portrait slots under the Great Flat: the Conflict deck lies in
# the left one (the setup picture [DI p. 4] B), and each round's Conflict
# card is placed "face up in the space next to the Conflict Deck" [DI p. 8].
CONFLICT_DECK_SLOT: Final = (30.35, 68.98, 8.62, 13.4)
CONFLICT_SLOT: Final = (40.56, 68.98, 8.68, 13.4)

# Rise of Ix's CHOAM board overlay, which covers the original board's
# Landsraad and CHOAM sections [Rise of Ix p. 3] (docs/rules/rise-of-ix.md 3),
# in its two pictures (assets ``board/ix_overlay_landsraad.png`` and
# ``board/ix_overlay_choam.png``, 2100 px wide), as ``(left, top, width,
# height)`` boxes on this picture. Measured 2026-10-29: the scale from the
# three spaces the Landsraad piece reprints (High Council, Mentat,
# Swordmaster), each found in it by template matching the board's own frame
# (NCC 0.95-0.97, one scale for all three: 1.175 overlay px per board px);
# the overlay rearranges them, so the pieces are placed against the
# sections' outer edges instead: the Landsraad piece's top-left on the
# board's Landsraad panel (28.72%, 1.68%, less the piece's border), the
# CHOAM piece's top-right on the CHOAM panel's (98.06%); they meet with the
# CHOAM piece over the other's dark margin. The panels' edges are where
# their olive and rust tints start (colour profiles).
IX_OVERLAY_BOXES: Final[Mapping[str, tuple[float, float, float, float]]] = (
    MappingProxyType(
        {
            "landsraad": (28.56, 1.5, 35.74, 22.62),
            "choam": (62.5, 1.5, 35.74, 22.56),
        }
    )
)
# What the overlay moves or adds, on this picture (the same measurement: the
# overlay's own prints mapped through its box): its five space frames (the
# frame outline's edges matched on the pieces), the Mentat silhouette (the
# board's own silhouette matched, NCC 0.97) and the four High Council chairs
# (each matched, NCC 0.96).
IX_SPACE_BOXES: Final[Mapping[str, tuple[float, float, float, float]]] = (
    MappingProxyType(
        {
            "imperium_high_council": (31.96, 5.44, 7.59, 5.88),
            "mentat": (31.91, 14.97, 7.59, 5.88),
            "imperium_swordmaster": (50.31, 14.96, 7.59, 5.88),
            "interstellar_shipping": (65.44, 6.32, 7.59, 5.88),
            "smuggling": (65.43, 14.84, 7.59, 5.88),
        }
    )
)
IX_MENTAT_POINT: Final = (45.87, 17.83)
IX_COUNCIL_SEATS: Final = ((43.56, 8.5), (46.84, 8.48), (54.25, 8.52), (57.55, 8.5))


def imperium_board_layout() -> dict[str, Any]:
    """Return the layout as plain JSON-ready values (``server.catalog``)."""

    return {
        "space_boxes": {space: list(box) for space, box in SPACE_BOXES.items()},
        "space_frame": {
            "cut": list(SPACE_FRAME_CUT),
            "square_bottom_left": list(SQUARE_BOTTOM_LEFT),
        },
        "tracks": {
            "influence": {
                "levels": list(INFLUENCE_LEVEL_Y),
                "offsets": dict(INFLUENCE_STRIP_OFFSET_Y),
                "seat_x": list(INFLUENCE_SEAT_X),
                "cube_size": INFLUENCE_CUBE_SIZE,
                "alliance": list(ALLIANCE_POINT),
                "alliance_size": ALLIANCE_TOKEN_SIZE,
            },
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
            "victory_points": {
                "x": VICTORY_POINT_X,
                "levels": list(VICTORY_POINT_Y),
                "cell": list(VICTORY_POINT_CELL),
            },
            "strength": {
                "cells": list(STRENGTH_CELL_X),
                "rows": list(STRENGTH_ROW_Y),
                "zero_box": list(STRENGTH_ZERO_BOX),
                "zero_point": list(STRENGTH_ZERO_POINT),
                "token_rows": list(STRENGTH_TOKEN_ROW_Y),
                "token_size": STRENGTH_TOKEN_SIZE,
            },
            "conflict_units": {
                "boxes": [list(box) for box in CONFLICT_UNIT_BOXES],
                "cross": list(CONFLICT_CROSS),
                "sizes": {
                    kind: list(size) for kind, size in CONFLICT_UNIT_SIZES.items()
                },
                "gap": CONFLICT_UNIT_GAP,
                "padding": CONFLICT_UNIT_PADDING,
                "min_scale": CONFLICT_UNIT_MIN_SCALE,
            },
            "garrison_units": {
                "rings": [list(ring) for ring in GARRISON_RINGS],
                "sizes": {
                    kind: list(CONFLICT_UNIT_SIZES[kind])
                    for kind in ("troop", "commander")
                },
                "gap": CONFLICT_UNIT_GAP,
                "line": GARRISON_UNIT_LINE,
                "padding": GARRISON_UNIT_PADDING,
                "min_scale": GARRISON_UNIT_MIN_SCALE,
            },
            "force_stepper_band": list(FORCE_STEPPER_BAND),
            "council_seats": [list(point) for point in COUNCIL_SEATS],
            "disc_size": SEAT_DISC_SIZE,
            "conflict_deck_slot": list(CONFLICT_DECK_SLOT),
            "conflict_slot": list(CONFLICT_SLOT),
        },
        # Rise of Ix's overlay and what it moves (the page uses these on an
        # original + Ix table).
        "ix": {
            "overlays": {name: list(box) for name, box in IX_OVERLAY_BOXES.items()},
            "space_boxes": {
                space: list(box) for space, box in IX_SPACE_BOXES.items()
            },
            "mentat": {"point": list(IX_MENTAT_POINT), "height": MENTAT_HEIGHT},
            "council_seats": [list(point) for point in IX_COUNCIL_SEATS],
        },
        "mentat": (
            None
            if MENTAT_POINT is None
            else {"point": list(MENTAT_POINT), "height": MENTAT_HEIGHT}
        ),
    }
