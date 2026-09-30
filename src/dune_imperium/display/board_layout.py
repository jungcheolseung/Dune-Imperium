"""Percent-coordinate layout of the Uprising board scan for the browser UI.

The play server can serve one machine-local scan of the printed four-player
board (``assets/board/map.jpg``, or ``DUNE_IMPERIUM_BOARD_IMAGE``)
and the browser draws the live state on top of it: a clickable hotspot per
board space, Agent tokens, Control flags, Spies on observation posts, and
the Conflict and face-up contract cards in their printed slots.
The coordinates below are the only thing that ties the UI to that scan.

Every value is a percentage of the image's width or height, so any scan
with the same framing works regardless of resolution. They were measured
by hand on 2026-09-03 against the owner's square 6012x6005 scan
(Tabletop Simulator export of the retail board) using a 2 % grid overlay;
a differently cropped scan needs a re-measure, not a rules change. The
space and post IDs are the engine's (``content.uprising.board``), and the
tests pin that both tables cover them exactly.

``SPACE_BOXES`` are ``(left, top, width, height)`` of the white frame each
space prints around its picture, the place where the Agent goes, so the
hotspot lights up exactly that frame and not the effect icons beside it.
``POST_POINTS`` are the centres of the observation-post "eye" discs.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final

# Every printed space draws the same white frame around its picture: square
# top-left and bottom-right corners (the Agent icon sits on the top-left one)
# and the other two corners cut at 45 degrees. The boxes run along the
# centre of the white line, found by fitting that outline to the scan and
# taking each edge's brightness centroid (2026-09-21): all 22 printed frames
# are 457 x 354 px of the 6012 x 6005 scan within a pixel, hence one size.
SPACE_BOXES: Final[Mapping[str, tuple[float, float, float, float]]] = (
    MappingProxyType(
        {
            # Emperor
            "sardaukar": (13.49, 7.0, 7.6, 5.9),
            "dutiful_service": (13.5, 17.08, 7.6, 5.9),
            # Spacing Guild
            "heighliner": (13.49, 31.54, 7.6, 5.9),
            "deliver_supplies": (13.51, 41.61, 7.6, 5.9),
            # Bene Gesserit
            "espionage": (13.51, 56.05, 7.6, 5.9),
            "secrets": (13.53, 66.15, 7.6, 5.9),
            # Fremen
            "desert_tactics": (13.5, 80.61, 7.6, 5.9),
            "fremkit": (13.48, 90.76, 7.6, 5.9),
            # Landsraad Council
            "high_council": (30.82, 3.18, 7.6, 5.9),
            "imperial_privilege": (30.89, 13.26, 7.6, 5.9),
            "swordmaster": (51.18, 13.12, 7.6, 5.9),
            "assembly_hall": (65.65, 3.08, 7.6, 5.9),
            "gather_support": (65.62, 13.1, 7.6, 5.9),
            # CHOAM
            "shipping": (85.1, 4.38, 7.6, 5.9),
            "accept_contract": (85.13, 13.11, 7.6, 5.9),
            # Arrakis
            "research_station": (39.67, 33.78, 7.6, 5.9),
            "spice_refinery": (61.06, 31.54, 7.6, 5.9),
            "arrakeen": (77.05, 28.83, 7.6, 5.9),
            "sietch_tabr": (29.78, 46.23, 7.6, 5.9),
            "imperial_basin": (74.47, 45.09, 7.6, 5.9),
            "hagga_basin": (50.25, 50.01, 7.6, 5.9),
            "deep_desert": (31.89, 57.29, 7.6, 5.9),
            # Bloodlines: the frame on Esmar Tuek's tile picture (centres
            # x 36.5..297.5, y 65.5..264.5 of the 550x310 picture), laid at
            # ``LEADER_TILE_BOXES`` below.
            "tuek_sietch": (75.56, 58.71, 7.59, 5.8),
        }
    )
)

# The cut corners of the frame, as percents of its box's width and height:
# the 45 degree cut takes 54 px of the line off each side of the corner.
SPACE_FRAME_CUT: Final = (11.8, 15.3)

# Where a Sardaukar Commander stands on its space, as fractions of the
# space's frame (``SPACE_BOXES``). Setup puts one on each of five spaces
# (six with four players) and says "Leave room on each space for an Agent"
# [Bloodlines p. 3] (docs/rules/bloodlines.md); the setup photo there stands
# each figure on the top-right corner of the frame, the rest of the frame
# left to the Agents, about as tall as the frame. Read off the photo's five
# spaces the base centre lies 0.84-0.94 of the width across and 0.04-0.26 of
# the height down, and the figure is 0.83-1.1 frames tall: placed by hand,
# so the means are used.
COMMANDER_ANCHOR: Final = (0.89, 0.13)
COMMANDER_HEIGHT: Final = 0.95
# The base centre inside the figure's picture (``display.token_images``),
# as fractions of its width and height: the figure leans back over its base.
# ``scripts/cut_commander_token.py`` prints it.
COMMANDER_PICTURE_BASE: Final = (0.434, 0.873)

# A Leader's own space is a tile next to the board that the scan does not
# print, so its picture is drawn in a box of its own. Esmar Tuek's tile
# lies in the empty desert under Imperial Basin, clear of that space's
# Control banner and of the border line (re-placed 2026-09-18). The box has
# the tile picture's shape (550x310) at the printed spaces' scale: their
# picture frames are 7.6 wide.
LEADER_TILE_BOXES: Final[Mapping[str, tuple[float, float, float, float]]] = (
    MappingProxyType({"tuek_sietch": (74.5, 56.8, 16.0, 9.03)})
)

# The Research Station overlay of Immortality ("Draw two cards and
# research" [Immortality pp. 5, 16]) covers the printed space: the box of
# its tile picture (782x425), found by matching the picture's landscape,
# Agent icon and water drops against the print (normalised cross-correlation
# 0.94, 2026-09-18). Its frame (centres x 42.5..424.5, y 82.5..377.5 of
# the picture) lies on the printed one, so the hotspot serves both.
RESEARCH_STATION_OVERLAY_BOX: Final = (38.81, 32.14, 15.58, 8.48)

# The Shield Wall token: "Shield Wall을 Spice Refinery 아래의 표시된 위치에
# 놓는다." [Main p. 4] (docs/rules/setup-and-game-flow.md). The marked
# position is the faint footprint with the rubble between Spice Refinery and
# Imperial Basin, where the white border of the protected region breaks off.
# The box is the token picture's (980x985), turned half round as it lies on
# the board: its left edge is the footprint's (63.27), its white line runs
# on from the border's two ends (the horizontal end at y 49.59, the turn at
# x 63.9) and it hides all of the printed rubble (measured 2026-09-18).
SHIELD_WALL_BOX: Final = (63.27, 42.4, 7.75, 7.8)
SHIELD_WALL_ROTATION: Final = 180

# An observation post is a printed grey disc with an eye, 116 px across the
# scan (1.93 %) with a second ring inside; a Spy stands on it. The points
# are the discs' centres, fitted to both rings (Hough transform on the scan's
# edges, 2026-09-21; the hand-set 2026-09-03 points were up to 0.58 off).
POST_POINTS: Final[Mapping[str, tuple[float, float]]] = MappingProxyType(
    {
        "emperor-sardaukar-dutiful-service": (25.05, 14.92),
        "landsraad-high-council-imperial-privilege-swordmaster": (47.49, 12.11),
        "landsraad-assembly-hall-gather-support": (77.88, 10.91),
        "choam-shipping-accept-contract": (96.06, 11.54),
        "spacing-guild-heighliner-deliver-supplies": (25.05, 39.47),
        "arrakis-research-station-spice-refinery": (54.84, 31.32),
        "arrakis-research-station-sietch-tabr": (38.37, 42.81),
        "arrakis-spice-refinery-arrakeen": (75.3, 26.86),
        "arrakis-imperial-basin": (86.28, 43.01),
        "arrakis-hagga-basin": (62.08, 47.88),
        "arrakis-deep-desert": (43.63, 55.12),
        "bene-gesserit-espionage-secrets": (25.1, 63.96),
        "fremen-desert-tactics-fremkit": (25.02, 88.56),
    }
)
POST_SIZE: Final = 1.93


# Live-state marker coordinates, measured on 2026-09-03 against the same
# scan with a 0.5 % grid overlay.

# Influence tracks: one vertical strip per Faction on the left edge. Levels
# 0..6 run bottom-up; ``INFLUENCE_LEVEL_Y`` holds the Emperor strip's band
# centres and each other Faction's strip is the same drawing shifted down by
# ``INFLUENCE_STRIP_OFFSET_Y``. Seat cubes sit side by side at
# ``INFLUENCE_SEAT_X`` so four cubes on one level stay readable.
INFLUENCE_LEVEL_Y: Final = (23.24, 19.89, 16.15, 12.38, 8.78, 5.76, 2.9)
INFLUENCE_STRIP_OFFSET_Y: Final[Mapping[str, float]] = MappingProxyType(
    {
        "emperor": 0.0,
        "spacing_guild": 24.56,
        "bene_gesserit": 49.08,
        "fremen": 73.72,
    }
)
INFLUENCE_SEAT_X: Final = (4.63, 6.58, 8.52, 10.47)
# An Influence cube is exactly one of the four squares each strip prints
# for Influence 0: 95 px of the 6012 px scan on all sixteen (brightness
# profiles, 2026-09-18), square-cornered. Those squares also fix the row of
# level 0 (their centres), the four columns (the same on every strip within
# 0.04) and the strips' offsets: the old eyeballed offsets were 0.26, 0.38
# and 0.52 short, which the gold bands' dark gaps and the orange line
# confirm. Levels 1..6 are the centres of the chevron bands, averaged over
# the columns (the bands rise about 0.4 towards the middle).
INFLUENCE_CUBE_SIZE: Final = 1.58
# The Alliance token: "Place the four Alliance tokens on the marked areas of
# the Faction's Influence tracks" [Main p. 4]; its first holder "take[s] the
# Alliance token from the track, put[s] it in their supply" [Main p. 7]. The
# marked area is the dashed ring around the Faction emblem at the top of each
# strip: the Emperor strip's centre (the other strips add their offset) and
# the ring's diameter as a percent of the scan's width, from circle fits to
# the dashes and the ring's top and bottom on a 0.5% grid (2026-09-19; the
# old eyeballed point was 1.5 too high).
ALLIANCE_POINT: Final = (7.56, 5.48)
ALLIANCE_TOKEN_SIZE: Final = 6.85

# The Control marker: "place your Control marker on the flag below that space
# (replacing any opponent's marker there)" [Main p. 20]. The flag is the
# swallow-tailed pennant printed under Arrakeen, Spice Refinery and Imperial
# Basin: ``(left, top, width, height)`` of its white outline (left, right
# and tips from pixel runs, the top from a 0.25% grid; 2026-09-19), and the
# depth of the notch between the two tips as a fraction of the height.
CONTROL_FLAG_BOXES: Final[Mapping[str, tuple[float, float, float, float]]] = (
    MappingProxyType(
        {
            "arrakeen": (77.23, 34.8, 3.18, 3.82),
            "spice_refinery": (61.29, 37.5, 3.18, 3.82),
            "imperial_basin": (74.67, 51.05, 3.17, 3.8),
        }
    )
)
CONTROL_FLAG_NOTCH: Final = 0.207

# Bonus spice accumulates "in the spot designated for bonus spice"
# [Main p. 15]: the hexagon with the Maker icon printed on each Maker space.
# The centres of the three hexagons and their common size, ``(width,
# height)`` of the white outline (a regular flat-topped hexagon; pixel runs,
# 2026-09-19). Esmar Tuek's tile prints the same hexagon: its centre lies at
# (413.5, 218.5) of the 550x310 tile picture, laid on the scan at its
# ``LEADER_TILE_BOXES`` box (there it comes out 2.76 x 2.36, the same print
# within a hair). Each hexagon is printed right of the space's frame.
MAKER_SPICE_POINTS: Final[Mapping[str, tuple[float, float]]] = MappingProxyType(
    {
        "imperial_basin": (88.03, 48.18),
        "hagga_basin": (62.1, 54.47),
        "deep_desert": (43.62, 61.85),
        "tuek_sietch": (86.53, 63.16),
    }
)
MAKER_SPICE_SIZE: Final = (2.79, 2.4)

# Victory Point track: the numbered column on the right edge, 0 at the
# bottom and 12 at the top; higher scores share the emblem above 12. The
# values are the centres of the printed cells (re-measured 2026-09-18 from
# the divider diamonds at x 94.25 and 98.75: cell 0 spans y 91.92..97.19 and
# the pitch is 5.275), because a Score marker now fills a quarter of its
# cell instead of being a dot somewhere on it. The emblem's centre is about
# 27.3; the overflow row sits a little higher to stay clear of cell 12.
VICTORY_POINT_X: Final = 96.5
VICTORY_POINT_Y: Final = tuple(round(94.56 - 5.275 * level, 2) for level in range(13))
VICTORY_POINT_OVERFLOW_Y: Final = 27.0
# One cell of the track, (width, height): the diamonds stand 4.5 apart and
# the cells are 5.275 tall. Discs that share a score overlap to stay inside.
VICTORY_POINT_CELL: Final = (4.5, 5.275)

# Combat strength track: two numbered rows along the bottom edge, cells
# 1..10 on the upper row and 11..20 on the lower row (same columns;
# ``STRENGTH_CELL_X[n]`` is the column of printed number n, index 0 is
# unused). A seat's strength token rests in the framed square left of
# "1"/"11" while its strength is 0 (``STRENGTH_ZERO_BOX``, a box like the
# hotspots) and flips to its "+20" face beyond 20.
STRENGTH_CELL_X: Final = tuple(46.3 + index * 4.37 for index in range(11))
STRENGTH_ROW_Y: Final = (93.2, 97.6)
STRENGTH_ZERO_BOX: Final = (38.6, 89.3, 10.0, 9.2)
# A pictured Combat marker (``dune_imperium.display.token_images``) lies in the
# open part of its cell, above the printed number, like the token on the
# table: the centre of that open part per row, and the token's side as a
# percent of the scan's width (a cell's open part is about 3.75 wide and
# 3.35 tall; measured on a 0.5% grid overlay, 2026-09-18). The drawn
# fallback token stays on the number itself (``STRENGTH_ROW_Y``).
STRENGTH_TOKEN_ROW_Y: Final = (91.1, 95.6)
STRENGTH_TOKEN_SIZE: Final = 3.0

# The Conflict area (re-measured 2026-09-06): the four bracketed circles in
# its corners are the garrisons, and the central field between them is
# divided by a cross into four quadrants where deployed units go ("keep
# your deployed units in the quadrant nearest to your garrison"
# [Main p. 10]). Both tables run clockwise from the bottom-left corner for
# seats 0..3: garrison circle centres, then the centre of each seat's
# quadrant (kept toward its outer half, clear of the crossed swords).
GARRISON_POINTS: Final = ((44.9, 83.1), (44.9, 71.8), (85.7, 71.8), (85.7, 83.1))
CONFLICT_QUADRANTS: Final = ((56.5, 83.0), (56.5, 71.8), (74.0, 71.8), (74.0, 83.0))

# The printed quadrants themselves, where each deployed unit stands as a
# piece of its own, as on the table. Measured 2026-09-27 with brightness
# profiles across the printed lines (pixel runs on the 6012 x 6005 scan;
# every line is 3-4 px wide):
# - the garrison rings (``GARRISON_RINGS``): the left pair's right edge
#   runs x 2983-2985 and 2982-2986 on the rows through their centres, the
#   right pair's left edge x 4848-4851 on both;
# - the cross between the quadrants: its vertical line x 3911-3914 on the
#   upper and the lower arm, its horizontal line y 4638-4642 on the left
#   arm and 4639-4642 on the right one;
# - the outline framing the garrisons: its top line y 3992-3995 above the
#   upper pair, its bottom line y 5297-5299 below the lower pair (averaged
#   over the outline's outer columns, x 39.6-41.6 and 88.8-90.8 %).
# The field runs from just right of the left rings (px 2988: 49.7) to just
# left of the right rings (px 4847: 80.62) and from the outline's top line
# (66.5) to its bottom line (88.23); the centre lines of the cross (px
# 3912.5 and 4640) split it into the four quadrants, ``(left, top, width,
# height)`` clockwise from the bottom-left like the tables above.
CONFLICT_CROSS: Final = (65.08, 77.27)
_FIELD_LEFT, _FIELD_RIGHT = 49.7, 80.62
_FIELD_TOP, _FIELD_BOTTOM = 66.5, 88.23


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
# The garrison rings from the same profiles, ``(left, top, width, height)``
# of each ring's outer edge (the half-height ends of the line's runs on the
# row and the column through its centre): x px 2383-2986, 2383-2987,
# 4848-5453, 4848-5453 and y px 4686-5289, 4001-4606, 4001-4606, 4686-5290,
# 603-605 px across both ways. ``GARRISON_POINTS`` (placed by hand) lie
# within 0.25 of their centres.
GARRISON_RINGS: Final = (
    (39.64, 78.04, 10.03, 10.04),
    (39.64, 66.63, 10.05, 10.08),
    (80.64, 66.63, 10.06, 10.08),
    (80.64, 78.04, 10.06, 10.06),
)

# The pieces that stand in a quadrant, ``(width, height)`` in percent of the
# scan's width and height (a square piece is a hair taller in height
# percent, 6012 / 6005). Each is as large as the same piece elsewhere on
# the board:
# - a troop is the same cube as an Influence cube (``INFLUENCE_CUBE_SIZE``,
#   95 px square);
# - an Agent (Duncan Idaho's Into the Fray) is as tall as on a space, 72%
#   of the printed frame (``.agent-token`` in style.css), at the Agent
#   icon's 52:81;
# - a Sardaukar Commander is as tall as on its setup space
#   (``COMMANDER_HEIGHT`` of the frame), at its picture's 130:195;
# - a sandworm is the Icon Guide's grey worm (62:57). Nothing on the board
#   sets its size: 3.6 of the width is a judgment call, about a
#   Commander's width.
# Rows keep ``CONFLICT_UNIT_GAP`` between pieces and ``CONFLICT_UNIT_PADDING``
# inside the box; a crowded quadrant shrinks its pieces down to
# ``CONFLICT_UNIT_MIN_SCALE`` before its rows close up.
_SCAN_WIDTH, _SCAN_HEIGHT = 6012, 6005
_FRAME_HEIGHT = SPACE_BOXES["sardaukar"][3]
AGENT_ON_SPACE_HEIGHT: Final = 0.72
SANDWORM_WIDTH: Final = 3.6


def _piece_by_height(height: float, aspect: float) -> tuple[float, float]:
    """A piece ``height`` percent of the scan's height, ``aspect`` wide/tall."""

    width_px = height / 100 * _SCAN_HEIGHT * aspect
    return (round(width_px / _SCAN_WIDTH * 100, 3), round(height, 3))


def _piece_by_width(width: float, aspect: float) -> tuple[float, float]:
    """A piece ``width`` percent of the scan's width, ``aspect`` wide/tall."""

    height_px = width / 100 * _SCAN_WIDTH / aspect
    return (round(width, 3), round(height_px / _SCAN_HEIGHT * 100, 3))


CONFLICT_UNIT_SIZES: Final[Mapping[str, tuple[float, float]]] = MappingProxyType(
    {
        "troop": _piece_by_width(INFLUENCE_CUBE_SIZE, 1.0),
        "commander": _piece_by_height(_FRAME_HEIGHT * COMMANDER_HEIGHT, 130 / 195),
        "agent": _piece_by_height(_FRAME_HEIGHT * AGENT_ON_SPACE_HEIGHT, 52 / 81),
        "sandworm": _piece_by_width(SANDWORM_WIDTH, 62 / 57),
    }
)
CONFLICT_UNIT_GAP: Final = 0.35
CONFLICT_UNIT_PADDING: Final = 0.5
CONFLICT_UNIT_MIN_SCALE: Final = 0.5

# A garrison holds troops and Sardaukar Commanders, a piece each inside its
# printed ring (``GARRISON_RINGS``), the same pieces as in the Conflict
# (``CONFLICT_UNIT_SIZES``, ``CONFLICT_UNIT_GAP``). The rows are packed
# inside the ring's inner circle: its outer edge less the printed line
# (``GARRISON_UNIT_LINE``, the line is 3-4 px, 0.06) and a padding. The
# padding is the widest that still lays a full garrison of 12 troops as
# three rows of four at full size (4 x 1.58 + 3 x 0.35 wide, the outer rows'
# corners 4.58 from the centre, the inner circle 4.615). A Commander is
# nearly six troops tall, so a garrison with Commanders shrinks: the gap
# shrinks with the pieces, and ``GARRISON_UNIT_MIN_SCALE`` is the smallest
# scale any real garrison needs (12 troops and all 7 Commanders beside a
# Maker Hooks token, 0.35; tests/unit/display/test_board_layout.py).
# The Maker Hooks slot (``MAKER_HOOKS_POINTS``) is printed over the ring's
# outer corner and reaches 1.9 from its centre, so a token lying there takes
# that corner: the pieces keep the padding clear of it (board.js
# ringUnitLayout).
GARRISON_UNIT_LINE: Final = 0.1
GARRISON_UNIT_PADDING: Final = 0.3
GARRISON_UNIT_MIN_SCALE: Final = 0.35

# The Maker Hooks token: "Take a Maker Hooks token from the bank, if you
# don't already have one. Place it on your garrison" [Main p. 20]. Every
# garrison prints a slot in the token's shape on its outer side, a faint
# outline with the hook drawn in it (it takes a contrast stretch to see):
# the centre of each seat's slot, the slot's ``(width, height)`` and how the
# token picture (``token_images.MAKER_HOOKS_TOKEN``: the handle along its
# bottom edge, the hook at the right) is turned and mirrored to lie in it.
# The outer edge, the top of the upper slots and the bottom of the lower ones
# are the peaks of brightness profiles; the slots are as long as the picture
# is when it is as wide as they are (4.88 x 449/644 = 3.4), so the picture
# covers the print exactly (2026-09-19).
MAKER_HOOKS_POINTS: Final = (
    (41.02, 85.77),
    (41.02, 68.92),
    (89.31, 68.92),
    (89.31, 85.77),
)
MAKER_HOOKS_SIZE: Final = (3.4, 4.88)
# (rotation in degrees, mirrored before turning) per seat.
MAKER_HOOKS_TURNS: Final = ((90, False), (90, True), (-90, False), (-90, True))

# Where the seat to move sends and takes back its units on the board (the
# same count rows as the action panel): plain desert just above the
# Conflict, where nothing is printed and no piece stands, ``(left, top,
# width, height)``. Measured 2026-09-27 with brightness profiles on the
# 6012 x 6005 scan:
# - left: Deep Desert's icon panel (its effect icons and bonus-spice
#   hexagon) ends in a double border line at x px 2909 and 2918-2919
#   (48.39 and 48.55 %) on the rows 58-63 %;
# - top: Hagga Basin's icon panel ends in a double border line at y px 3390
#   and 3400-3401 (56.45 and 56.63 %) across x 52-66 %;
# - right: Esmar Tuek's tile (``LEADER_TILE_BOXES``) starts at 74.5;
# - bottom: the Conflict area's shaded panel, which holds the garrison
#   rings and the field, starts with a straight edge at y px 3930-3932
#   (65.46 %) all the way across x 46-80 %.
# Inside, the scan prints only map art: the three-line track that runs from
# under Hagga Basin's panel (x 67, y 56.7) down to the Conflict (x 59.5-60,
# y 62-65.3) with a dotted strip beside it, and a faint thin contour line
# near the left edge. The band keeps 0.15-0.2 off each of those edges.
FORCE_STEPPER_BAND: Final = (48.7, 56.8, 25.6, 8.5)

# The four High Council seats, left to right: the centres of the printed
# circles (diameter 2.91; re-measured 2026-09-18 from the white rings).
COUNCIL_SEATS: Final = ((42.18, 5.22), (46.0, 5.22), (49.83, 5.22), (53.64, 5.22))

# The player disc: one common round token in the seat's colour, used for the
# Score marker and the Councilor token here and for the research and
# Tleilaxu track tokens on the Bene Tleilax board. Its diameter is exactly
# the printed High Council circle's (the white ring's outer diameter,
# 176 px of the 6012 px scan on all four circles; measured 2026-09-18), as
# a percent of the scan's width.
SEAT_DISC_SIZE: Final = 2.93

# Printed card slots, ``(left, top, width, height)`` like ``SPACE_BOXES``
# (measured 2026-09-06). Two faint portrait frames stand under Deep Desert,
# between the Fremen strip and the Conflict area, above the strength
# legend: the upper one holds the face-down Conflict deck and the lower one
# the current round's Conflict card. The two face-up CHOAM contracts sit in
# the pair of slots under the Landsraad Council (the left one carries the
# "contract = 2 Solari" legend) [Main p. 16].
CONFLICT_DECK_SLOT: Final = (29.1, 65.7, 8.4, 12.9)
CONFLICT_SLOT: Final = (29.1, 79.5, 8.4, 12.8)
CONTRACT_SLOTS: Final = ((29.1, 21.5, 10.5, 6.5), (40.3, 21.5, 10.6, 6.5))


# Arrakeen Scouts mission pieces (docs/rules/arrakeen-scouts.md 5): the bank
# goods a mission puts on a space, the troops seats park there and the
# face-down cards a mission lays there stay until claimed [Scouts help]. The
# companion app says only which space they go on, and the board prints no
# place for them, so each space names the free parts of its printed panel
# where they lie: ``(left, top, width, height, from_bottom)`` boxes, tried
# in order, their rows filled from the bottom edge (the one against the
# space's name) when ``from_bottom`` holds, else from the top edge. Every box
# is plain panel or map art, measured on a 0.5 % grid of the 6012 x 6005
# scan (2026-09-30), clear of the frame (the Agents' place), the printed
# icons, the space's name, the connector lines and the posts. A Sardaukar
# Commander standing on the frame's corner (``COMMANDER_ANCHOR``) rises over
# two of them (on Sardaukar over x 18.6-22.4, y 2.9-8.5; on Deliver Supplies
# over x 18.7-22.4, y 37.5-43.1): while it stands there the client keeps
# the parts of a box left and right of it (board.js scoutsRegionsClear).
# - Sardaukar: the Emperor panel's head (its top line 1.3, its inner edge
#   26.3), right of the name (x 18.2, down to the Intrigue icon at 6.6) and
#   above it (the name from y 5.0);
# - Deliver Supplies: the band between Heighliner's frame (37.44) and the
#   name (39.6), left of the connector line (21.1); then under the water
#   drop (45.85) down to the Spacing Guild panel's bottom line (48.6);
# - Espionage and Desert Tactics: the Bene Gesserit and Fremen panels' heads
#   above the name (panel tops 50.3 and 74.9, names from 54.1 and 78.5);
# - Imperial Privilege: right of the two card icons (44.2), under the
#   connector to the post (13.1) and above the panel's bottom (19.4);
# - Gather Support: the plain map under the Landsraad panel (its bottom line
#   19.5), above the dotted line at 22.5, to the CHOAM column (81);
# - Research Station: the desert under its panel (40.62, also the bottom of
#   Immortality's overlay tile ``RESEARCH_STATION_OVERLAY_BOX``), right of
#   Sietch Tabr's panel (46.0) and left of the Shield Wall's lines (60);
# - Hagga Basin (Desert Riding's Maker Hooks token, "beside Hagga Basin"):
#   the desert above its name (48.3), clear of that box and of the post.
SCOUTS_SPACE_REGIONS: Final[
    Mapping[str, tuple[tuple[float, float, float, float, bool], ...]]
] = MappingProxyType(
    {
        "sardaukar": ((18.2, 1.7, 7.9, 4.8, True), (13.2, 1.7, 4.8, 3.1, True)),
        "deliver_supplies": (
            (13.4, 37.7, 7.5, 1.75, True),
            (22.6, 46.1, 3.6, 2.2, False),
        ),
        "espionage": ((13.2, 50.7, 12.9, 3.2, True),),
        "desert_tactics": ((13.2, 75.3, 12.9, 3.0, True),),
        "imperial_privilege": ((44.3, 13.4, 2.5, 5.9, False),),
        "gather_support": ((65.4, 19.75, 15.3, 2.6, False),),
        "research_station": ((46.5, 40.9, 8.0, 3.0, False),),
        "hagga_basin": ((50.5, 44.3, 8.5, 3.8, True),),
    }
)
# The pieces, ``(width, height)`` in percent of the scan. Bank goods are the
# size of the icons the board prints for them (pixel runs of the grey rims,
# 2026-09-30): the spice hexagon of Hagga Basin's "2" (x 58.87-60.52,
# y 50.53-52.19), the Solari coin of Gather Support's "2" (x 73.97-75.53,
# y 16.3-17.88) and Deliver Supplies' water drop (x 22.88-24.35,
# y 43.3-45.85). A troop is the Influence cube; the Control marker (Prison
# Planet) is the printed flag it lies on under a controlled space
# (``CONTROL_FLAG_BOXES``); the Maker Hooks token lies flat as in its
# garrison slot (``MAKER_HOOKS_SIZE``, turned back). A face-down pile is a
# card back at a third of the card: an Intrigue card is the Conflict card's
# size (``CONFLICT_SLOT``), a Contract its printed slot (``CONTRACT_SLOTS``);
# the board has no place for them and a whole card would hide the space.
SCOUTS_CARD_SCALE: Final = 1 / 3
SCOUTS_PIECE_SIZES: Final[Mapping[str, tuple[float, float]]] = MappingProxyType(
    {
        "troop": _piece_by_width(INFLUENCE_CUBE_SIZE, 1.0),
        "spice": (1.65, 1.66),
        "solari": _piece_by_width(1.57, 1.0),
        "water": (1.47, 2.55),
        "marker": (3.18, 3.82),
        "maker_hooks": (MAKER_HOOKS_SIZE[1], MAKER_HOOKS_SIZE[0]),
        "intrigue": (
            round(CONFLICT_SLOT[2] * SCOUTS_CARD_SCALE, 2),
            round(CONFLICT_SLOT[3] * SCOUTS_CARD_SCALE, 2),
        ),
        "contract": (
            round(CONTRACT_SLOTS[0][2] * SCOUTS_CARD_SCALE, 2),
            round(CONTRACT_SLOTS[0][3] * SCOUTS_CARD_SCALE, 2),
        ),
    }
)
# Pieces of one seat (or the bank's goods of one mission) stand
# ``SCOUTS_PIECE_GAP`` apart, groups ``SCOUTS_GROUP_GAP`` apart; a crowded
# space shrinks its pieces in steps of 0.05 down to ``SCOUTS_MIN_SCALE``
# before its rows close up, like the Conflict quadrants.
SCOUTS_PIECE_GAP: Final = 0.2
SCOUTS_GROUP_GAP: Final = 0.5
SCOUTS_MIN_SCALE: Final = 0.5


def marker_layout() -> dict[str, Any]:
    """Return every marker table as plain JSON-ready values."""

    return {
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
                space_id: list(box) for space_id, box in CONTROL_FLAG_BOXES.items()
            },
            "notch": CONTROL_FLAG_NOTCH,
        },
        "maker_spice": {
            "points": {
                space_id: list(point)
                for space_id, point in MAKER_SPICE_POINTS.items()
            },
            "size": list(MAKER_SPICE_SIZE),
        },
        "maker_hooks": {
            "points": [list(point) for point in MAKER_HOOKS_POINTS],
            "size": list(MAKER_HOOKS_SIZE),
            "turns": [
                {"rotation": rotation, "mirrored": mirrored}
                for rotation, mirrored in MAKER_HOOKS_TURNS
            ],
        },
        "victory_points": {
            "x": VICTORY_POINT_X,
            "levels": list(VICTORY_POINT_Y),
            "overflow_y": VICTORY_POINT_OVERFLOW_Y,
            "cell": list(VICTORY_POINT_CELL),
        },
        "strength": {
            "cells": list(STRENGTH_CELL_X),
            "rows": list(STRENGTH_ROW_Y),
            "zero_box": list(STRENGTH_ZERO_BOX),
            "token_rows": list(STRENGTH_TOKEN_ROW_Y),
            "token_size": STRENGTH_TOKEN_SIZE,
        },
        "garrisons": [list(point) for point in GARRISON_POINTS],
        "conflict_quadrants": [list(point) for point in CONFLICT_QUADRANTS],
        "conflict_units": {
            "boxes": [list(box) for box in CONFLICT_UNIT_BOXES],
            "cross": list(CONFLICT_CROSS),
            "sizes": {kind: list(size) for kind, size in CONFLICT_UNIT_SIZES.items()},
            "gap": CONFLICT_UNIT_GAP,
            "padding": CONFLICT_UNIT_PADDING,
            "min_scale": CONFLICT_UNIT_MIN_SCALE,
        },
        "garrison_units": {
            "rings": [list(ring) for ring in GARRISON_RINGS],
            "sizes": {
                kind: list(CONFLICT_UNIT_SIZES[kind]) for kind in ("troop", "commander")
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
        "contract_slots": [list(box) for box in CONTRACT_SLOTS],
        "scouts": {
            "regions": {
                space_id: [
                    {"box": [left, top, width, height], "from_bottom": from_bottom}
                    for left, top, width, height, from_bottom in regions
                ]
                for space_id, regions in SCOUTS_SPACE_REGIONS.items()
            },
            "sizes": {kind: list(size) for kind, size in SCOUTS_PIECE_SIZES.items()},
            "gap": [SCOUTS_PIECE_GAP, SCOUTS_PIECE_GAP],
            "group_gap": [SCOUTS_GROUP_GAP, SCOUTS_GROUP_GAP],
            "min_scale": SCOUTS_MIN_SCALE,
        },
    }
