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
    DREADNOUGHT_ASPECT,
    DREADNOUGHT_WIDTH,
    GARRISON_UNIT_LINE,
    GARRISON_UNIT_MIN_SCALE,
    SANDWORM_WIDTH,
    SCOUTS_GROUP_GAP,
    SCOUTS_MIN_SCALE,
    SCOUTS_PIECE_GAP,
)
from dune_imperium.display.board_layout import (
    SCOUTS_PIECE_SIZES as UPRISING_SCOUTS_PIECE_SIZES,
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
            # Esmar Tuek's own space (stage P7c): the frame on its tile
            # picture, laid in ``LEADER_TILE_BOXES`` below.
            "tuek_sietch": (28.56, 25.41, 7.61, 5.81),
        }
    )
)
# The cut corners as percents of the box's width and height (45.9 px of
# the frame line each way).
SPACE_FRAME_CUT: Final = (12.0, 15.5)
SQUARE_BOTTOM_LEFT: Final = ("arrakeen", "carthag", "imperial_basin")
# Immortality's Research Station overlay covers this board's Research Station
# too ("Research Station overlay를 Research Station 위에 덮는다(Uprising의
# Research Station도)" [Immortality p. 5], docs/rules/immortality.md 2 item 4;
# stage P7b): the box of the tile picture Uprising's scan lays
# (``display.board_layout``, 782 x 425 px), placed by its white frame (line
# centres x 42.5..424.5, y 82.5..377.5 of the picture) on the printed frame of
# ``SPACE_BOXES["imperium_research_station"]`` at that frame's scale (1.000
# by 0.999 picture px per board px). The edge maps of tile and scan correlate
# best one pixel above that (0.90, measured 2026-10-30), inside the frames'
# own measuring error, so the hotspot serves the tile as on Uprising's board.
RESEARCH_STATION_OVERLAY_BOX: Final = (41.84, 36.44, 15.64, 8.5)
# Esmar Tuek's Tuek's Sietch: "During setup, place the Tuek's Sietch board
# space near the game board" [Bloodlines p. 12], the original's too with
# Bloodlines (docs/rules/bloodlines.md 2a, stage P7c). The print has no place
# for it, so the tile picture Uprising's scan lays (550 x 310 px,
# ``display.board_layout``) is drawn in a box of its own on the Heighliner's
# picture beside the Spacing Guild's spaces, clear of every space, flag, track
# and piece (the empty desert left of the Conflict holds its card slot); its
# frame (line centres x 36.5..297.5, y 65.5..264.5 of the picture) is as wide
# as the printed ones (7.61), which gives the hotspot
# ``SPACE_BOXES["tuek_sietch"]``.
LEADER_TILE_BOXES: Final[Mapping[str, tuple[float, float, float, float]]] = (
    MappingProxyType({"tuek_sietch": (27.5, 23.5, 16.04, 9.05)})
)
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
        # The Maker hexagon on Tuek's Sietch's tile: where Uprising's scan
        # finds it on the same picture (0.752, 0.704 of the tile box).
        "tuek_sietch": (39.56, 29.87),
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
        "dreadnought": _piece_by_width(DREADNOUGHT_WIDTH, DREADNOUGHT_ASPECT),
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
_IX_OVERLAYS_AS_MEASURED: Final = {
    "landsraad": (28.56, 1.5, 35.74, 22.62),
    "choam": (62.5, 1.5, 35.74, 22.56),
}
# What the overlay moves or adds, on this picture (the same measurement: the
# overlay's own prints mapped through its box): its five space frames (the
# frame outline's edges matched on the pieces), the Mentat silhouette (the
# board's own silhouette matched, NCC 0.97) and the four High Council chairs
# (each matched, NCC 0.96).
_IX_SPACES_AS_MEASURED: Final = {
    "imperium_high_council": (31.96, 5.44, 7.59, 5.88),
    "mentat": (31.91, 14.97, 7.59, 5.88),
    "imperium_swordmaster": (50.31, 14.96, 7.59, 5.88),
    "interstellar_shipping": (65.44, 6.32, 7.59, 5.88),
    "smuggling": (65.43, 14.84, 7.59, 5.88),
}
# So placed, the CHOAM piece's Smuggling frame lay 0.12 % (6 px) above the
# Landsraad piece's Swordmaster. User decision 2026-10-31: "원판 + 익스도
# 소드마스터-밀수-드레드노트 가 다 같은 높이가 오도록 하자" -- the CHOAM piece
# and the two frames on it go down by that much (its top still above the
# CHOAM panel's edge), the Landsraad piece stays on its panel, and the Ix
# board beside goes down to them (``ix_board_top``).
_IX_CHOAM_DROP: Final = (
    _IX_SPACES_AS_MEASURED["imperium_swordmaster"][1]
    - _IX_SPACES_AS_MEASURED["smuggling"][1]
)
_IX_ON_CHOAM: Final = ("choam", "interstellar_shipping", "smuggling")


def _level(
    boxes: Mapping[str, tuple[float, float, float, float]],
) -> Mapping[str, tuple[float, float, float, float]]:
    """The boxes with those on the CHOAM piece moved down with it."""

    return MappingProxyType(
        {
            name: (left, round(top + _IX_CHOAM_DROP, 2), width, height)
            if name in _IX_ON_CHOAM
            else (left, top, width, height)
            for name, (left, top, width, height) in boxes.items()
        }
    )


IX_OVERLAY_BOXES: Final[Mapping[str, tuple[float, float, float, float]]] = _level(
    _IX_OVERLAYS_AS_MEASURED
)
IX_SPACE_BOXES: Final[Mapping[str, tuple[float, float, float, float]]] = _level(
    _IX_SPACES_AS_MEASURED
)
IX_MENTAT_POINT: Final = (45.87, 17.83)
IX_COUNCIL_SEATS: Final = ((43.56, 8.5), (46.84, 8.48), (54.25, 8.52), (57.55, 8.5))


def _on_choam(x: float, y: float) -> tuple[float, float]:
    """A point in percent of the CHOAM piece's picture, on this picture."""

    left, top, width, height = IX_OVERLAY_BOXES["choam"]
    return (round(left + x * width / 100, 2), round(top + y * height / 100, 2))


# The Freighters' discs on the CHOAM piece's Shipping track, bottom step
# (where each seat's disc starts [Rise of Ix p. 3]) to the top, one column
# per seat. Measured 2026-10-29 on the piece's picture by brightness
# profiles across the track outlines, checked drawn over it: the four
# columns divide the bands' common inside evenly, and each disc sits at its
# band's middle at that column, so a row follows the printed chevron. The
# columns are 2.57 % of this picture apart, so the disc is drawn smaller
# than the board's other seat discs.
_FREIGHTER_COLUMNS = (52.62, 59.82, 67.01, 74.21)
_FREIGHTER_ROWS = (
    (82.84, 82.84, 82.84, 82.84),
    (63.16, 61.97, 61.98, 63.16),
    (40.58, 38.18, 38.17, 40.55),
    (16.94, 15.73, 15.72, 16.92),
)
# The same discs in percent of the piece's own picture, for a board it lies
# on elsewhere (Uprising's, ``display.board_layout_uprising_ix``).
IX_CHOAM_FREIGHTER_ON_PIECE: Final = tuple(
    tuple(zip(_FREIGHTER_COLUMNS, row, strict=True)) for row in _FREIGHTER_ROWS
)
IX_FREIGHTER_POINTS: Final = tuple(
    tuple(_on_choam(x, y) for x, y in row) for row in IX_CHOAM_FREIGHTER_ON_PIECE
)
IX_FREIGHTER_DISC_SIZE: Final = 2.3

# Rise of Ix's own board (assets ``board/ix_board.png``, 2100x2132), drawn
# beside this one at the print's scale: its space frames are 449.6 px wide
# against this picture's 379.5 px, so 1.18 of its pixels to one of ours.
# Its values are percent of its own picture, measured 2026-10-29 like the
# rest (brightness profiles across each white frame and plate edge, checked
# drawn over it): the two space frames, the three translucent plates the
# Tech stacks lie on (the tiles' own 1.53 proportions) and the Negotiators'
# shield, with a spot per seat in one row across it.
IX_BOARD_SCALE: Final = 1.18
IX_BOARD_PICTURE: Final = (2100, 2132)
IX_BOARD_SPACE_BOXES: Final[Mapping[str, tuple[float, float, float, float]]] = (
    MappingProxyType(
        {
            "tech_negotiation": (9.29, 11.03, 21.41, 16.28),
            "dreadnought": (9.17, 37.33, 21.43, 16.29),
        }
    )
)
IX_TECH_SLOTS: Final = (
    (55.93, 3.78, 37.02, 23.92),
    (55.8, 33.5, 37.07, 23.92),
    (55.72, 63.25, 37.09, 23.91),
)
IX_NEGOTIATOR_BOX: Final = (33.18, 64.11, 18.37, 22.24)
IX_NEGOTIATOR_SEATS: Final = (
    (35.48, 74.11),
    (40.07, 74.11),
    (44.66, 74.11),
    (49.26, 74.11),
)


def ix_board_size() -> tuple[float, float]:
    """The Ix board's width and height in percent of this picture's."""

    width, height = IX_BOARD_PICTURE
    return (
        round(100 * width / IX_BOARD_SCALE / _PICTURE_WIDTH, 2),
        round(100 * height / IX_BOARD_SCALE / _PICTURE_HEIGHT, 2),
    )


def ix_board_top() -> float:
    """The Ix board's top in percent of this picture's height, beside it.

    Its Dreadnought frame lies level with the Swordmaster's and Smuggling's
    (user decision 2026-10-31, ``IX_OVERLAY_BOXES``): 1.46 % below this
    board's top, which also brings Tech Negotiation level with the High
    Council (5.45 % and 5.44 %).
    """

    height = ix_board_size()[1]
    dreadnought = IX_BOARD_SPACE_BOXES["dreadnought"][1] * height / 100
    return round(IX_SPACE_BOXES["imperium_swordmaster"][1] - dreadnought, 2)


# Arrakeen Scouts' mission pieces on this picture (stage P8e), in the shapes
# of ``display.board_layout``'s ``SCOUTS_SPACE_REGIONS``: ``(left, top,
# width, height, from_bottom)`` boxes of free print where the pieces a
# mission leaves on a space lie until claimed (docs/rules/arrakeen-scouts.md
# 5, 9a), measured 2026-10-31 on percent-gridded crops of the scan. As on
# Uprising they are bands of a space's own panel or plain map beside it,
# off every frame, icon and printed place:
# - Conspire, the Heighliner and Selective Breeding: the band under the
#   frame, down to the next space's name (15.3, 40.0, 64.5); Selective
#   Breeding also the Bene Gesserit panel's head above its name (51.0-54.2);
# - Foldspace: the band under the frame to the panel's foot (49.4), and the
#   strip right of its Foldspace card icon (x 24.6) to the panel's edge;
# - Mentat and Rally Troops: the plain map under the Landsraad panel (its
#   foot 19.0), above the Spacing Guild's ship (23.5), each under its own
#   space; Rally Troops is covered with Rise of Ix, and the Mentat then
#   lies on the overlay (``IX_SCOUTS_REGIONS``);
# - Research Station: the desert left of its panel under the ship's nose
#   (x 38.9-41.65; Secrets in the Desert's face-down pile stands there), the
#   plain map above the panel right of the dotted route (x 47.2, y
#   33.9-36.3) and the strip under the panel left of Hagga Basin's name
#   (45.1-46.4), all clear of Immortality's overlay tile
#   (``RESEARCH_STATION_OVERLAY_BOX``).
SCOUTS_SPACE_REGIONS: Final[
    Mapping[str, tuple[tuple[float, float, float, float, bool], ...]]
] = MappingProxyType(
    {
        "conspire": ((13.2, 13.45, 13.0, 1.7, False),),
        "imperium_heighliner": ((13.2, 37.95, 13.0, 1.85, False),),
        "foldspace": ((13.2, 48.05, 13.0, 1.35, False), (24.75, 42.1, 1.55, 5.7, True)),
        "selective_breeding": (
            (13.2, 62.45, 13.0, 1.9, False),
            (13.2, 51.2, 13.0, 2.6, True),
        ),
        "mentat": ((30.6, 19.3, 16.8, 3.0, False),),
        "rally_troops": ((48.6, 19.3, 14.4, 3.0, False),),
        "imperium_research_station": (
            (38.9, 38.2, 2.75, 6.3, True),
            (47.2, 33.9, 10.3, 2.4, True),
            (42.3, 45.1, 10.0, 1.3, False),
        ),
    }
)
# Where Rise of Ix's missions leave pieces on its own prints (stage P7f-2):
# Secret Stash's spice and Stowaways' troops on Smuggling, in the empty strip
# of its panel right of the printed coin and Negotiator icons, in percent of
# the CHOAM piece's picture; Armed Escort's dreadnoughts and spice on
# Dreadnought, in percent of the Ix board's picture -- the panel's strip
# right of its printed dreadnought and Tech icons, then the plain planet
# below the panel, above the Negotiators' shield.
IX_CHOAM_SCOUTS_ON_PIECE: Final[
    Mapping[str, tuple[tuple[float, float, float, float, bool], ...]]
] = MappingProxyType({"smuggling": ((38.5, 58.0, 7.0, 34.0, True),)})
IX_BOARD_SCOUTS_REGIONS: Final[
    Mapping[str, tuple[tuple[float, float, float, float, bool], ...]]
] = MappingProxyType(
    {
        "dreadnought": (
            (45.2, 37.5, 6.0, 15.5, True),
            (12.0, 57.6, 36.0, 5.6, False),
        ),
    }
)


def _on_choam_region(
    region: tuple[float, float, float, float, bool],
) -> tuple[float, float, float, float, bool]:
    """A region in percent of the CHOAM piece's picture, on this picture."""

    x, y, width, height, from_bottom = region
    _, _, piece_width, piece_height = IX_OVERLAY_BOXES["choam"]
    return (
        *_on_choam(x, y),
        round(width * piece_width / 100, 2),
        round(height * piece_height / 100, 2),
        from_bottom,
    )


# With Rise of Ix (stage P8e): the Mentat's space on the Landsraad piece,
# the band under its frame (20.85) above the piece's foot (24.12) and left
# of the Swordmaster (50.31), and Smuggling on the CHOAM piece where its
# missions leave theirs on Uprising's table too. The Ix board's Dreadnought
# is in its own picture (``IX_BOARD_SCOUTS_REGIONS``).
IX_SCOUTS_REGIONS: Final[
    Mapping[str, tuple[tuple[float, float, float, float, bool], ...]]
] = MappingProxyType(
    {
        "mentat": ((31.0, 21.05, 17.5, 2.6, False),),
        **{
            space_id: tuple(_on_choam_region(region) for region in regions)
            for space_id, regions in IX_CHOAM_SCOUTS_ON_PIECE.items()
        },
    }
)
# The pieces at the print's scale (the two boards' frames are both 7.6 % of
# their scans wide): a troop is this board's Influence cube, the Control
# marker (Sapho Juice) its printed flag (``CONTROL_FLAG_BOXES``), a
# face-down Intrigue card (Secrets in the Desert) a third of its Conflict
# slot, a parked dreadnought two thirds of a deployed one; the bank goods
# are Uprising's icon sizes.
SCOUTS_PIECE_SIZES: Final[Mapping[str, tuple[float, float]]] = MappingProxyType(
    {
        "troop": _piece_by_width(INFLUENCE_CUBE_SIZE, 1.0),
        "spice": UPRISING_SCOUTS_PIECE_SIZES["spice"],
        "solari": UPRISING_SCOUTS_PIECE_SIZES["solari"],
        "water": UPRISING_SCOUTS_PIECE_SIZES["water"],
        "marker": CONTROL_FLAG_BOXES["arrakeen"][2:],
        "intrigue": (round(CONFLICT_SLOT[2] / 3, 2), round(CONFLICT_SLOT[3] / 3, 2)),
        "dreadnought": _piece_by_width(
            round(DREADNOUGHT_WIDTH * 2 / 3, 2), DREADNOUGHT_ASPECT
        ),
        # Genetic Research's parked Sardaukar Commander (OQ-166), Uprising's.
        "commander": UPRISING_SCOUTS_PIECE_SIZES["commander"],
    }
)


def scouts_regions_json(
    table: Mapping[str, tuple[tuple[float, float, float, float, bool], ...]],
) -> dict[str, list[dict[str, Any]]]:
    """Scouts regions in the shape of the catalog's ``tracks.scouts``."""

    return {
        space_id: [
            {"box": [left, top, width, height], "from_bottom": from_bottom}
            for left, top, width, height, from_bottom in regions
        ]
        for space_id, regions in table.items()
    }


def imperium_board_layout() -> dict[str, Any]:
    """Return the layout as plain JSON-ready values (``server.catalog``)."""

    return {
        "space_boxes": {space: list(box) for space, box in SPACE_BOXES.items()},
        # A Leader's own tile laid beside the print (Tuek's Sietch), in the
        # shape of a catalog space's ``tile_box`` on Uprising's scan.
        "tile_boxes": {
            space: list(box) for space, box in LEADER_TILE_BOXES.items()
        },
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
                    for kind in ("troop", "commander", "dreadnought")
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
            "scouts": {
                "regions": scouts_regions_json(SCOUTS_SPACE_REGIONS),
                "sizes": {
                    kind: list(size) for kind, size in SCOUTS_PIECE_SIZES.items()
                },
                "gap": [SCOUTS_PIECE_GAP, SCOUTS_PIECE_GAP],
                "group_gap": [SCOUTS_GROUP_GAP, SCOUTS_GROUP_GAP],
                "min_scale": SCOUTS_MIN_SCALE,
            },
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
            "freighter": {
                "steps": [
                    [list(point) for point in row] for row in IX_FREIGHTER_POINTS
                ],
                "disc_size": IX_FREIGHTER_DISC_SIZE,
            },
            # Arrakeen Scouts' regions in place of the board's own (stage P8e).
            "scouts_regions": scouts_regions_json(IX_SCOUTS_REGIONS),
            # The Ix board beside this one: ``size`` and ``top`` in percent
            # of this picture, everything else in percent of its own.
            "board": {
                "size": list(ix_board_size()),
                "top": ix_board_top(),
                "space_boxes": {
                    space: list(box) for space, box in IX_BOARD_SPACE_BOXES.items()
                },
                "tech_slots": [list(box) for box in IX_TECH_SLOTS],
                "negotiator_box": list(IX_NEGOTIATOR_BOX),
                "negotiator_seats": [list(point) for point in IX_NEGOTIATOR_SEATS],
                "scouts_regions": scouts_regions_json(IX_BOARD_SCOUTS_REGIONS),
            },
        },
        "mentat": (
            None
            if MENTAT_POINT is None
            else {"point": list(MENTAT_POINT), "height": MENTAT_HEIGHT}
        ),
    }
