"""Tests for the board-scan overlay coordinates behind the browser UI."""

import math
from dataclasses import dataclass

from dune_imperium.content.uprising.board import (
    BOARD_SPACES,
    OBSERVATION_POSTS,
    Faction,
)
from dune_imperium.display.board_layout import (
    AGENT_ON_SPACE_HEIGHT,
    COMMANDER_HEIGHT,
    CONFLICT_CROSS,
    CONFLICT_DECK_SLOT,
    CONFLICT_QUADRANTS,
    CONFLICT_SLOT,
    CONFLICT_UNIT_BOXES,
    CONFLICT_UNIT_GAP,
    CONFLICT_UNIT_MIN_SCALE,
    CONFLICT_UNIT_PADDING,
    CONFLICT_UNIT_SIZES,
    CONTROL_FLAG_BOXES,
    FORCE_STEPPER_BAND,
    GARRISON_POINTS,
    GARRISON_RINGS,
    GARRISON_UNIT_LINE,
    GARRISON_UNIT_MIN_SCALE,
    GARRISON_UNIT_PADDING,
    INFLUENCE_CUBE_SIZE,
    LEADER_TILE_BOXES,
    MAKER_HOOKS_POINTS,
    MAKER_HOOKS_SIZE,
    MAKER_HOOKS_TURNS,
    MAKER_SPICE_POINTS,
    MAKER_SPICE_SIZE,
    POST_POINTS,
    POST_SIZE,
    RESEARCH_STATION_OVERLAY_BOX,
    SHIELD_WALL_BOX,
    SHIELD_WALL_ROTATION,
    SPACE_BOXES,
    SPACE_FRAME_CUT,
    STRENGTH_TOKEN_ROW_Y,
    STRENGTH_TOKEN_SIZE,
    STRENGTH_ZERO_BOX,
    marker_layout,
)

Box = tuple[float, float, float, float]


def test_marker_tables_cover_the_printed_tracks() -> None:
    layout = marker_layout()
    influence = layout["influence"]
    assert isinstance(influence, dict)
    assert len(influence["levels"]) == 7
    assert set(influence["offsets"]) == {faction.value for faction in Faction}
    assert len(influence["seat_x"]) == 4
    assert influence["levels"] == sorted(influence["levels"], reverse=True)
    # An Influence cube is exactly a printed Influence 0 square (95 px of
    # the 6012 px scan); neighbouring columns and levels leave room for it.
    cube = influence["cube_size"]
    assert cube == 1.58
    assert round(cube / 100 * 6012) == 95
    seat_x = influence["seat_x"]
    assert all(
        right - left > cube for left, right in zip(seat_x, seat_x[1:], strict=False)
    )
    assert all(
        lower - upper > cube
        for lower, upper in zip(
            influence["levels"], influence["levels"][1:], strict=False
        )
    )
    victory = layout["victory_points"]
    assert isinstance(victory, dict)
    assert len(victory["levels"]) == 13
    assert victory["levels"] == sorted(victory["levels"], reverse=True)
    strength = layout["strength"]
    assert isinstance(strength, dict)
    assert len(strength["cells"]) == 11 and len(strength["rows"]) == 2
    assert len(strength["zero_box"]) == 4
    # A pictured Combat marker lies in the open part of its cell, above the
    # printed number the drawn token sits on, and is narrower than the
    # cells' pitch so neighbouring strengths do not cover each other.
    assert len(strength["token_rows"]) == 2
    assert all(
        token_y < number_y
        for token_y, number_y in zip(
            strength["token_rows"], strength["rows"], strict=True
        )
    )
    assert strength["rows"][0] < strength["token_rows"][1]
    assert 0 < strength["token_size"] < strength["cells"][2] - strength["cells"][1]
    # The common player disc (Score marker, Councilor token) is exactly the
    # printed High Council circle: 176 px of the 6012 px scan. Neighbouring
    # circles do not touch, and one cell of the Score track holds one disc
    # (seats that share a score overlap inside ``cell``).
    disc = layout["disc_size"]
    assert disc == 2.93
    assert round(disc / 100 * 6012) == 176
    council_x = [point[0] for point in layout["council_seats"]]
    assert council_x == sorted(council_x)
    assert all(
        disc < right - left
        for left, right in zip(council_x, council_x[1:], strict=False)
    )
    cell_width, cell_height = victory["cell"]
    assert disc < cell_width and disc < cell_height
    score_pitches = [
        lower - upper
        for lower, upper in zip(victory["levels"], victory["levels"][1:], strict=False)
    ]
    assert all(abs(pitch - cell_height) < 0.02 for pitch in score_pitches)
    assert victory["overflow_y"] < victory["levels"][-1] - disc
    assert len(layout["garrisons"]) == 4
    assert len(layout["conflict_quadrants"]) == 4
    # The units in the Conflict stand in the printed quadrants, one piece
    # per unit (test_conflict_quadrants_hold_the_units_as_pieces).
    units = layout["conflict_units"]
    assert isinstance(units, dict)
    assert units["boxes"] == [list(box) for box in CONFLICT_UNIT_BOXES]
    assert units["cross"] == list(CONFLICT_CROSS)
    assert set(units["sizes"]) == {"troop", "commander", "agent", "sandworm"}
    assert units["sizes"]["troop"][0] == cube
    assert units["gap"] == CONFLICT_UNIT_GAP
    assert units["padding"] == CONFLICT_UNIT_PADDING
    assert units["min_scale"] == CONFLICT_UNIT_MIN_SCALE
    assert len(layout["council_seats"]) == 4
    # Card slots are boxes like the hotspots: the Conflict deck and the
    # current Conflict card, two face-up contracts [Main p. 16].
    assert len(layout["conflict_deck_slot"]) == 4
    assert len(layout["conflict_slot"]) == 4
    assert len(layout["contract_slots"]) == 2

    def inside(value: object) -> bool:
        return isinstance(value, (int, float)) and 0.0 <= value <= 100.0

    for faction_offset in influence["offsets"].values():
        assert all(inside(level + faction_offset) for level in influence["levels"])
    assert all(inside(value) for value in influence["seat_x"])
    assert all(inside(value) for value in victory["levels"])
    assert all(inside(value) for value in strength["cells"])
    assert all(inside(value) for value in strength["token_rows"])
    for table in ("garrisons", "conflict_quadrants", "council_seats"):
        assert all(inside(point[0]) and inside(point[1]) for point in layout[table])
    slots = (
        layout["conflict_deck_slot"],
        layout["conflict_slot"],
        *layout["contract_slots"],
        strength["zero_box"],
    )
    for left, top, width, height in slots:
        assert 0 <= left < left + width <= 100
        assert 0 <= top < top + height <= 100


def test_control_flags_lie_under_the_controllable_spaces() -> None:
    # "place your Control marker on the flag below that space" [Main p. 20]:
    # one printed pennant per space a Conflict can give control of, hanging
    # from the bottom line of that space's frame and no wider than it.
    assert set(CONTROL_FLAG_BOXES) == {
        space.space_id for space in BOARD_SPACES if space.critical
    }
    for space_id, (left, top, width, height) in CONTROL_FLAG_BOXES.items():
        space_left, space_top, space_width, space_height = SPACE_BOXES[space_id]
        assert space_left <= left < left + width <= space_left + space_width
        assert 0.0 <= top - (space_top + space_height) <= 0.15
        # All three flags are the same print: 3.17-3.18 wide, 3.8 tall.
        assert 3.1 < width < 3.25 and 3.7 < height < 3.9
    layout = marker_layout()["control_flags"]
    assert layout["boxes"] == {
        space_id: list(box) for space_id, box in CONTROL_FLAG_BOXES.items()
    }
    assert 0 < layout["notch"] < 0.5


def test_bonus_spice_lies_on_each_printed_maker_hexagon() -> None:
    # Bonus spice goes "in the spot designated for bonus spice" [Main p. 15]:
    # the hexagon with the Maker icon, printed among the Maker space's effect
    # icons right of its frame and within the frame's height. Esmar Tuek's
    # tile is a picture laid on the scan and prints the same hexagon.
    assert set(MAKER_SPICE_POINTS) == {
        space.space_id for space in BOARD_SPACES if space.maker
    }
    width, height = MAKER_SPICE_SIZE
    # A regular flat-topped hexagon: its height is sqrt(3)/2 of its width.
    assert abs(height / width - 3**0.5 / 2) < 0.01
    for space_id, (x, y) in MAKER_SPICE_POINTS.items():
        left, top, box_width, box_height = SPACE_BOXES[space_id]
        assert left + box_width < x - width / 2 < left + box_width + 5
        assert top < y - height / 2 and y + height / 2 < top + box_height


def test_maker_hooks_slots_flank_the_garrisons() -> None:
    # "Place it on your garrison" [Main p. 20]: every garrison prints a slot
    # for the token on its outer side. The four slots mirror each other like
    # the garrisons do, and the token picture (644x449, the handle along its
    # bottom edge) is turned a quarter so its handle lies on the slot's outer
    # edge: clockwise for the left garrisons, the other way for the right
    # ones, mirrored for the two whose hook points away from the Conflict's
    # horizontal axis.
    assert len(MAKER_HOOKS_POINTS) == len(GARRISON_POINTS) == 4
    width, height = MAKER_HOOKS_SIZE
    assert abs(width / height - 449 / 644) < 0.005
    for (x, y), (garrison_x, garrison_y) in zip(
        MAKER_HOOKS_POINTS, GARRISON_POINTS, strict=True
    ):
        assert (x < garrison_x) == (garrison_x < 60)
        assert 2.5 < abs(x - garrison_x) < 5.5 and abs(y - garrison_y) < 3.5
    lower_left, upper_left, upper_right, lower_right = MAKER_HOOKS_POINTS
    assert lower_left[0] == upper_left[0] and upper_right[0] == lower_right[0]
    assert lower_left[1] == lower_right[1] and upper_left[1] == upper_right[1]
    assert MAKER_HOOKS_TURNS == ((90, False), (90, True), (-90, False), (-90, True))
    layout = marker_layout()["maker_hooks"]
    assert layout["size"] == [width, height]
    assert layout["turns"][1] == {"rotation": 90, "mirrored": True}


def _apart(first: Box, second: Box) -> bool:
    """Two boxes that do not overlap (touching edges allowed)."""

    epsilon = 1e-9
    return (
        first[0] + first[2] <= second[0] + epsilon
        or second[0] + second[2] <= first[0] + epsilon
        or first[1] + first[3] <= second[1] + epsilon
        or second[1] + second[3] <= first[1] + epsilon
    )


def _centred(point: tuple[float, float], size: tuple[float, float]) -> Box:
    (x, y), (width, height) = point, size
    return (x - width / 2, y - height / 2, width, height)


def test_conflict_quadrants_hold_the_units_as_pieces() -> None:
    # "keep your deployed units in the quadrant nearest to your garrison"
    # [Main p. 10]: every deployed unit stands in its seat's printed
    # quadrant as a piece of its own. The four quadrants fill the field
    # between the garrison rings and meet at the printed cross; nothing else
    # printed or laid on the board lies in them.
    assert len(CONFLICT_UNIT_BOXES) == 4
    cross_x, cross_y = CONFLICT_CROSS
    for seat, box in enumerate(CONFLICT_UNIT_BOXES):
        left, top, width, height = box
        assert 0 <= left < left + width <= 100 and 0 <= top < top + height <= 100
        x, y = CONFLICT_QUADRANTS[seat]
        assert left < x < left + width and top < y < top + height, seat
        # Seats run clockwise from the bottom-left, each quadrant touching
        # the cross with its inner corner.
        right_side = seat in (2, 3)
        lower = seat in (0, 3)
        assert abs((left if right_side else left + width) - cross_x) < 1e-9, seat
        assert abs((top if lower else top + height) - cross_y) < 1e-9, seat
        # Clear of every garrison ring (a circle inside its box) and of the
        # other pieces around the field.
        for ring in GARRISON_RINGS:
            assert _apart(box, ring), (seat, ring)
        for point in MAKER_HOOKS_POINTS:
            assert _apart(box, _centred(point, MAKER_HOOKS_SIZE)), (seat, point)
        for slot in (STRENGTH_ZERO_BOX, CONFLICT_SLOT, CONFLICT_DECK_SLOT):
            assert _apart(box, slot), (seat, slot)
        assert _apart(box, LEADER_TILE_BOXES["tuek_sietch"]), seat
        assert top + height < STRENGTH_TOKEN_ROW_Y[0] - STRENGTH_TOKEN_SIZE / 2
    for index, first in enumerate(CONFLICT_UNIT_BOXES):
        for second in CONFLICT_UNIT_BOXES[index + 1 :]:
            assert _apart(first, second)
    # The rings are the garrisons: each ring holds its seat's garrison point
    # and is 603-605 px across both ways.
    for (x, y), (left, top, width, height) in zip(
        GARRISON_POINTS, GARRISON_RINGS, strict=True
    ):
        assert abs(x - (left + width / 2)) < 0.3 and abs(y - (top + height / 2)) < 0.3
        assert 603 <= round(width / 100 * 6012) <= 605
        assert 603 <= round(height / 100 * 6005) <= 605

    # Each piece is as large as the same piece elsewhere on the board: a
    # troop is the Influence cube, an Agent and a Commander are as tall as
    # on a space; all keep their pictures' shapes on the 6012 x 6005 scan.
    frame_height = SPACE_BOXES["sardaukar"][3]
    troop = CONFLICT_UNIT_SIZES["troop"]
    agent, commander = CONFLICT_UNIT_SIZES["agent"], CONFLICT_UNIT_SIZES["commander"]
    assert troop[0] == INFLUENCE_CUBE_SIZE
    assert abs(agent[1] - frame_height * AGENT_ON_SPACE_HEIGHT) < 1e-3
    assert abs(commander[1] - frame_height * COMMANDER_HEIGHT) < 1e-3

    def shape(size: tuple[float, float]) -> float:
        return size[0] * 6012 / (size[1] * 6005)

    assert abs(shape(troop) - 1) < 0.005
    assert abs(shape(agent) - 52 / 81) < 0.005
    assert abs(shape(commander) - 130 / 195) < 0.005
    assert abs(shape(CONFLICT_UNIT_SIZES["sandworm"]) - 62 / 57) < 0.005

    # At full size one quadrant holds a full Conflict of troops (12) and one
    # of each figure, laid out as the client does (board.js
    # conflictUnitLayout): rows of troops from the outer edge, then the
    # figures in a row of their own, with the gap between pieces and rows
    # and the padding inside the box.
    gap, padding = CONFLICT_UNIT_GAP, CONFLICT_UNIT_PADDING
    figures = [commander, agent, CONFLICT_UNIT_SIZES["sandworm"]]
    for _, _, width, height in CONFLICT_UNIT_BOXES:
        inner_width, inner_height = width - 2 * padding, height - 2 * padding
        per_row = int((inner_width + gap) // (troop[0] + gap))
        troop_rows = -(-12 // per_row)
        assert sum(w for w, _ in figures) + gap * (len(figures) - 1) <= inner_width
        depth = troop_rows * troop[1] + gap * troop_rows + max(h for _, h in figures)
        assert depth <= inner_height, (width, height, depth)
    assert 0 < CONFLICT_UNIT_MIN_SCALE < 1


@dataclass
class _Row:
    kind: str
    w: float
    h: float
    top: float = 0.0
    span: tuple[float, float] | None = None
    capacity: int = 0
    count: int = 0


def _row_splits(rows: int, parts: int) -> list[list[int]]:
    if parts == 1:
        return [[rows]]
    return [
        [first, *rest]
        for first in range(1, rows - parts + 2)
        for rest in _row_splits(rows - first, parts - 1)
    ]


def _ring_unit_layout(
    counts: dict[str, int], ring: Box, avoid: tuple[Box, ...] = ()
) -> tuple[float, list[tuple[str, Box]]]:
    """The garrison's pieces as the client lays them (board.js ringUnitLayout).

    Rows inside the ring's inner circle, troops then Commanders, in the
    fewest rows that hold them, a kind's units shared evenly among its rows;
    the block centred, or moved just clear of a box to avoid, or else the rows
    that box cuts narrowed; every piece and gap shrinks in 0.05 steps down to
    ``GARRISON_UNIT_MIN_SCALE``. Returns the scale and each piece's box, or
    no pieces when nothing fits there (the client then closes the rows up).
    """

    left, top, width, height = ring
    inset = GARRISON_UNIT_LINE + GARRISON_UNIT_PADDING
    cx, cy = left + width / 2, top + height / 2
    rx, ry = width / 2 - inset, height / 2 - inset
    kinds = [kind for kind in ("troop", "commander") if counts.get(kind)]
    total = sum(counts[kind] for kind in kinds)
    pad = GARRISON_UNIT_PADDING
    blocks = [
        (bl - pad, bt - pad, bl + bw + pad, bt + bh + pad) for bl, bt, bw, bh in avoid
    ]

    def free_span(
        row_top: float, row_bottom: float
    ) -> tuple[tuple[float, float] | None, bool]:
        edge = max(abs(row_top - cy), abs(row_bottom - cy))
        if edge >= ry:
            return None, False
        half = rx * math.sqrt(1 - (edge / ry) ** 2)
        spans = [(cx - half, cx + half)]
        cut = False
        for bx0, by0, bx1, by1 in blocks:
            if by1 <= row_top or by0 >= row_bottom:
                continue
            rest = []
            for a, b in spans:
                if bx1 <= a or bx0 >= b:
                    rest.append((a, b))
                    continue
                cut = True
                if bx0 > a:
                    rest.append((a, bx0))
                if bx1 < b:
                    rest.append((bx1, b))
            spans = rest
        best = None
        for span in spans:
            if best is None or span[1] - span[0] > best[1] - best[0]:
                best = span
        return best, cut

    def fill(rows: list[_Row]) -> bool:
        for kind in kinds:
            own = [row for row in rows if row.kind == kind]
            room = sum(row.capacity for row in own)
            if any(row.capacity < 1 for row in own) or room < counts[kind]:
                return False
            for _ in range(counts[kind]):
                pick = min(
                    (row for row in own if row.count < row.capacity),
                    key=lambda row: row.count,
                )
                pick.count += 1
        return True

    def arrange(split: list[int], scale: float) -> list[_Row] | None:
        between = CONFLICT_UNIT_GAP * scale
        sized = [
            (
                kind,
                CONFLICT_UNIT_SIZES[kind][0] * scale,
                CONFLICT_UNIT_SIZES[kind][1] * scale,
            )
            for kind, count in zip(kinds, split, strict=True)
            for _ in range(count)
        ]
        depth = sum(h for _, _, h in sized) + between * (len(sized) - 1)
        if depth > 2 * ry + 1e-9:
            return None
        shifts = [0.0]
        for _, by0, _, by1 in blocks:
            for shift in (by0 - (cy + depth / 2), by1 - (cy - depth / 2)):
                if abs(shift) > 1e-9 and abs(shift) + depth / 2 <= ry + 1e-9:
                    shifts.append(shift)
        shifts.sort(key=abs)
        narrowed = None
        for shift in shifts:
            row_top = cy + shift - depth / 2
            cut = False
            rows = []
            for kind, w, h in sized:
                span, cuts = free_span(row_top, row_top + h)
                cut = cut or cuts
                room = span[1] - span[0] if span else 0.0
                capacity = (
                    math.floor((room + between + 1e-9) / (w + between)) if span else 0
                )
                rows.append(_Row(kind, w, h, row_top, span, capacity))
                row_top += h + between
            if not fill(rows):
                continue
            if not cut:
                return rows
            narrowed = narrowed or rows
        return narrowed

    scale = 1.0
    while True:
        for count in range(len(kinds), total + 1):
            for split in _row_splits(count, len(kinds)):
                arranged = arrange(split, scale)
                if arranged is None:
                    continue
                between = CONFLICT_UNIT_GAP * scale
                pieces = []
                for row in arranged:
                    assert row.span is not None
                    length = row.count * row.w + (row.count - 1) * between
                    start = max(row.span[0], min(cx - length / 2, row.span[1] - length))
                    for index in range(row.count):
                        x = start + index * (row.w + between)
                        pieces.append((row.kind, (x, row.top, row.w, row.h)))
                return scale, pieces
        if scale <= GARRISON_UNIT_MIN_SCALE + 1e-9:
            return scale, []
        scale = max(GARRISON_UNIT_MIN_SCALE, round(scale - 0.05, 2))


def test_garrison_rings_hold_their_units_as_pieces() -> None:
    # Every unit in a garrison stands in its seat's printed ring as a piece
    # of its own, the same pieces as in the Conflict: troops, and Bloodlines'
    # Sardaukar Commanders (up to 7 exist). The client gets the rings and the
    # packing's constants in one table.
    units = marker_layout()["garrison_units"]
    assert isinstance(units, dict)
    assert units["rings"] == [list(ring) for ring in GARRISON_RINGS]
    assert units["sizes"] == {
        kind: list(CONFLICT_UNIT_SIZES[kind]) for kind in ("troop", "commander")
    }
    assert units["gap"] == CONFLICT_UNIT_GAP
    assert units["line"] == GARRISON_UNIT_LINE
    assert units["padding"] == GARRISON_UNIT_PADDING
    assert units["min_scale"] == GARRISON_UNIT_MIN_SCALE
    # The printed line is 3-4 px (0.06), so the packing keeps inside it.
    assert 0.06 <= GARRISON_UNIT_LINE < GARRISON_UNIT_PADDING
    for (x, y), (left, top, width, height) in zip(
        GARRISON_POINTS, GARRISON_RINGS, strict=True
    ):
        assert left < x < left + width and top < y < top + height
        assert abs(x - (left + width / 2)) < 0.3 and abs(y - (top + height / 2)) < 0.3

    hooks = [_centred(point, MAKER_HOOKS_SIZE) for point in MAKER_HOOKS_POINTS]
    for seat, ring in enumerate(GARRISON_RINGS):
        # The setup garrison (3 troops [Main p. 4]) is one row at full size
        # on the ring's centre, and a full one (12) is three rows of four.
        scale, pieces = _ring_unit_layout({"troop": 3}, ring)
        left, top, width, height = ring
        centre_x, centre_y = left + width / 2, top + height / 2
        assert scale == 1 and len({box[1] for _, box in pieces}) == 1
        assert abs(pieces[0][1][1] + pieces[0][1][3] / 2 - centre_y) < 1e-9
        scale, pieces = _ring_unit_layout({"troop": 12}, ring)
        rows: dict[float, int] = {}
        for _, box in pieces:
            rows[round(box[1], 6)] = rows.get(round(box[1], 6), 0) + 1
        assert scale == 1 and sorted(rows.values()) == [4, 4, 4], rows
        # The Maker Hooks slot is printed over the ring's outer corner and
        # reaches into the circle, so a token lying there takes that corner.
        slot = hooks[seat]
        slot_right_of_centre = slot[0] > centre_x
        near_x = slot[0] if slot_right_of_centre else slot[0] + slot[2]
        assert abs(near_x - centre_x) < 2.5

    # Every garrison a game can hold (0-12 troops, 0-7 Commanders) fits in
    # every ring, beside a Maker Hooks token or not, at no less than the
    # smallest scale; the most crowded one needs exactly that scale. Every
    # piece stands inside the inner circle, off the token by the padding and
    # off every other piece.
    inset = GARRISON_UNIT_LINE + GARRISON_UNIT_PADDING
    scales = []
    for seat, ring in enumerate(GARRISON_RINGS):
        left, top, width, height = ring
        centre_x, centre_y = left + width / 2, top + height / 2
        rx, ry = width / 2 - inset, height / 2 - inset
        for avoid in ((), (hooks[seat],)):
            for troops in range(13):
                for commanders in range(8):
                    if not troops and not commanders:
                        continue
                    counts = {"troop": troops, "commander": commanders}
                    scale, pieces = _ring_unit_layout(counts, ring, avoid)
                    assert pieces, (seat, bool(avoid), counts)
                    scales.append(scale)
                    kinds = [kind for kind, _ in pieces]
                    assert kinds.count("troop") == troops
                    assert kinds.count("commander") == commanders
                    boxes = [box for _, box in pieces]
                    for bl, bt, bw, bh in boxes:
                        for corner_x, corner_y in (
                            (bl, bt),
                            (bl + bw, bt),
                            (bl, bt + bh),
                            (bl + bw, bt + bh),
                        ):
                            reach = ((corner_x - centre_x) / rx) ** 2 + (
                                (corner_y - centre_y) / ry
                            ) ** 2
                            assert reach <= 1 + 1e-9, (seat, counts)
                        for slot in avoid:
                            grown = (
                                slot[0] - GARRISON_UNIT_PADDING + 1e-9,
                                slot[1] - GARRISON_UNIT_PADDING + 1e-9,
                                slot[2] + 2 * GARRISON_UNIT_PADDING - 2e-9,
                                slot[3] + 2 * GARRISON_UNIT_PADDING - 2e-9,
                            )
                            assert _apart((bl, bt, bw, bh), grown), (seat, counts)
                    for index, first in enumerate(boxes):
                        for second in boxes[index + 1 :]:
                            assert _apart(first, second), (seat, counts)
    assert min(scales) == GARRISON_UNIT_MIN_SCALE


def test_the_board_stepper_band_is_plain_desert_above_the_conflict() -> None:
    # The board's copy of the count rows (deploy / withdraw units) stands in
    # the plain desert just above the Conflict: inside the scan, clear of
    # every space, its effect icons' bonus-spice hexagon, Esmar Tuek's tile,
    # the Conflict field, the garrison rings and the Maker Hooks slots.
    band = FORCE_STEPPER_BAND
    left, top, width, height = band
    assert 0 <= left < left + width <= 100 and 0 <= top < top + height <= 100
    assert marker_layout()["force_stepper_band"] == list(band)
    for space_id, box in SPACE_BOXES.items():
        assert _apart(band, box), space_id
    for space_id, point in MAKER_SPICE_POINTS.items():
        assert _apart(band, _centred(point, MAKER_SPICE_SIZE)), space_id
    for space_id, box in LEADER_TILE_BOXES.items():
        assert _apart(band, box), space_id
    for space_id, box in CONTROL_FLAG_BOXES.items():
        assert _apart(band, box), space_id
    for post_id, point in POST_POINTS.items():
        assert _apart(band, _centred(point, (POST_SIZE, POST_SIZE))), post_id
    for box in (*GARRISON_RINGS, *CONFLICT_UNIT_BOXES):
        assert _apart(band, box), box
    for point in MAKER_HOOKS_POINTS:
        assert _apart(band, _centred(point, MAKER_HOOKS_SIZE)), point
    for box in (SHIELD_WALL_BOX, CONFLICT_SLOT, CONFLICT_DECK_SLOT, STRENGTH_ZERO_BOX):
        assert _apart(band, box), box
    # Between Deep Desert and Esmar Tuek's tile, under Hagga Basin's icons
    # and above the Conflict area's shaded panel (65.46) and its rings.
    deep_desert_x, _ = MAKER_SPICE_POINTS["deep_desert"]
    hagga_x, hagga_y = MAKER_SPICE_POINTS["hagga_basin"]
    assert deep_desert_x + MAKER_SPICE_SIZE[0] / 2 < left
    assert hagga_y + MAKER_SPICE_SIZE[1] / 2 < top
    assert left < hagga_x < left + width
    assert left + width < LEADER_TILE_BOXES["tuek_sietch"][0]
    assert top + height < 65.46 < min(ring[1] for ring in GARRISON_RINGS)
    # Room for the rows: about a quarter of the board wide.
    assert width > 25 and height > 8


def test_the_alliance_token_covers_the_ring_printed_for_it() -> None:
    # "Place the four Alliance tokens on the marked areas of the Faction's
    # Influence tracks" [Main p. 4]: the dashed ring at the top of a strip,
    # 6.85 across, over Influence levels 4 to 6 and inside the strip.
    influence = marker_layout()["influence"]
    x, y = influence["alliance"]
    size = influence["alliance_size"]
    assert size == 6.85
    assert influence["seat_x"][0] - 1 < x - size / 2
    assert x + size / 2 < influence["seat_x"][-1] + 1
    assert influence["levels"][6] - 1 < y - size / 2 + 0.2
    assert y + size / 2 < influence["levels"][3]


def test_every_board_space_has_exactly_one_hotspot_box() -> None:
    assert set(SPACE_BOXES) == {space.space_id for space in BOARD_SPACES}


def test_hotspots_are_the_one_frame_every_space_prints() -> None:
    # The hotspot is the white frame around a space's picture, not the
    # effect icons beside it, so every printed space's box is the same size
    # (457 x 354 px of the 6012 x 6005 scan) and so is the frame on a
    # Leader's tile within a few pixels.
    printed = {
        space_id: box
        for space_id, box in SPACE_BOXES.items()
        if space_id not in LEADER_TILE_BOXES
    }
    assert len(printed) == 22
    assert {(width, height) for _, _, width, height in printed.values()} == {
        (7.6, 5.9)
    }
    for space_id in LEADER_TILE_BOXES:
        _, _, width, height = SPACE_BOXES[space_id]
        assert abs(width - 7.6) < 0.05 and abs(height - 5.9) < 0.15
    # Two corners are cut at 45 degrees, 54 px along each side.
    cut_x, cut_y = SPACE_FRAME_CUT
    assert abs(cut_x / 100 * 7.6 / 100 * 6012 - 54) < 1
    assert abs(cut_y / 100 * 5.9 / 100 * 6005 - 54) < 1


def test_every_observation_post_has_a_point() -> None:
    assert set(POST_POINTS) == {post.post_id for post in OBSERVATION_POSTS}


def test_posts_are_printed_discs_clear_of_the_spaces() -> None:
    # A Spy stands on the post's printed disc, 116 px of the 6012 px scan:
    # the disc lies off every space's frame, so a Spy never covers a place
    # an Agent goes.
    assert round(POST_SIZE / 100 * 6012) == 116
    radius = POST_SIZE / 2
    for post_id, (x, y) in POST_POINTS.items():
        for space_id, (left, top, width, height) in SPACE_BOXES.items():
            nearest_x = min(max(x, left), left + width)
            nearest_y = min(max(y, top), top + height)
            gap = ((x - nearest_x) ** 2 + (y - nearest_y) ** 2) ** 0.5
            assert gap > radius, (post_id, space_id)


def test_boxes_and_points_stay_inside_the_image() -> None:
    for space_id, (left, top, width, height) in SPACE_BOXES.items():
        assert 0 <= left < left + width <= 100, space_id
        assert 0 <= top < top + height <= 100, space_id
        assert width >= 5 and height >= 5, space_id
    for post_id, (x, y) in POST_POINTS.items():
        assert 0 <= x <= 100 and 0 <= y <= 100, post_id


def test_hotspot_boxes_do_not_overlap() -> None:
    boxes = list(SPACE_BOXES.items())
    for index, (first_id, first) in enumerate(boxes):
        for second_id, second in boxes[index + 1 :]:
            separated = (
                first[0] + first[2] <= second[0]
                or second[0] + second[2] <= first[0]
                or first[1] + first[3] <= second[1]
                or second[1] + second[3] <= first[1]
            )
            assert separated, (first_id, second_id)


def test_pieces_laid_on_the_scan_keep_their_pictures_shape() -> None:
    # Boxes are percents of a 6012 x 6005 scan, so a picture's shape is its
    # box's width over height times the scan's.
    scan_aspect = 6012 / 6005

    def box_aspect(box: tuple[float, float, float, float]) -> float:
        _, _, width, height = box
        return width / height * scan_aspect

    # The Shield Wall token (980 x 985) lies half turned on its marked
    # position between Spice Refinery and Imperial Basin [Main p. 4].
    assert abs(box_aspect(SHIELD_WALL_BOX) - 980 / 985) < 0.01
    assert SHIELD_WALL_ROTATION == 180
    wall_left, wall_top, wall_width, wall_height = SHIELD_WALL_BOX
    refinery = SPACE_BOXES["spice_refinery"]
    basin = SPACE_BOXES["imperial_basin"]
    assert wall_top > refinery[1] + refinery[3]  # below Spice Refinery
    assert wall_left + wall_width < basin[0]  # left of Imperial Basin
    assert refinery[0] < wall_left + wall_width / 2 < basin[0]

    def frame_in(
        tile: tuple[float, float, float, float],
        picture: tuple[int, int],
        frame: tuple[float, float, float, float],
    ) -> tuple[float, float, float, float]:
        # A frame measured in a tile picture's pixels (line centres, left,
        # top, right, bottom), in percent of the scan once laid at ``tile``.
        left, top, width, height = tile
        x_scale, y_scale = width / picture[0], height / picture[1]
        return (
            left + frame[0] * x_scale,
            top + frame[1] * y_scale,
            (frame[2] - frame[0]) * x_scale,
            (frame[3] - frame[1]) * y_scale,
        )

    def close(
        first: tuple[float, float, float, float],
        second: tuple[float, float, float, float],
    ) -> bool:
        return all(abs(a - b) < 0.05 for a, b in zip(first, second, strict=True))

    # Immortality's Research Station overlay (782 x 425) covers the printed
    # space, and its frame lies on the printed one, so the hotspot is both.
    assert abs(box_aspect(RESEARCH_STATION_OVERLAY_BOX) - 782 / 425) < 0.01
    overlay_frame = frame_in(
        RESEARCH_STATION_OVERLAY_BOX, (782, 425), (42.5, 82.5, 424.5, 377.5)
    )
    assert close(overlay_frame, SPACE_BOXES["research_station"])

    # Tuek's Sietch has no print: its tile picture (550 x 310) is drawn in
    # its own box, clear of Imperial Basin above it, and the hotspot is the
    # frame on that picture.
    assert set(LEADER_TILE_BOXES) == {
        space.space_id for space in BOARD_SPACES if space.required_leader_id
    }
    tuek = LEADER_TILE_BOXES["tuek_sietch"]
    assert abs(box_aspect(tuek) - 550 / 310) < 0.01
    assert tuek[1] > basin[1] + basin[3]
    tuek_frame = frame_in(tuek, (550, 310), (36.5, 65.5, 297.5, 264.5))
    assert close(tuek_frame, SPACE_BOXES["tuek_sietch"])



# --- Arrakeen Scouts mission pieces -------------------------------------------------


def _meets(first: Box, second: Box) -> bool:
    return not (
        first[0] + first[2] <= second[0]
        or second[0] + second[2] <= first[0]
        or first[1] + first[3] <= second[1]
        or second[1] + second[3] <= first[1]
    )


def _commander_box(space_id: str) -> Box:
    # The figure commanderPiece draws on the frame's top-right corner
    # [Bloodlines p. 3]: COMMANDER_HEIGHT frames tall at its picture's
    # 130:195, its base (COMMANDER_PICTURE_BASE) on COMMANDER_ANCHOR.
    from dune_imperium.display.board_layout import (
        COMMANDER_ANCHOR,
        COMMANDER_PICTURE_BASE,
    )

    left, top, width, height = SPACE_BOXES[space_id]
    tall = height * COMMANDER_HEIGHT
    wide = tall * 130 / 195
    x = left + width * COMMANDER_ANCHOR[0]
    y = top + height * COMMANDER_ANCHOR[1]
    return (
        x - wide * COMMANDER_PICTURE_BASE[0],
        y - tall * COMMANDER_PICTURE_BASE[1],
        wide,
        tall,
    )


def test_every_scouts_mission_space_has_regions_for_its_pieces() -> None:
    # A mission's pieces stay on its space until claimed
    # (docs/rules/arrakeen-scouts.md 5): every space a mission names has
    # free parts of the scan to lie in, and nothing else does.
    from dune_imperium.content.arrakeen_scouts import MISSIONS
    from dune_imperium.display.board_layout import SCOUTS_SPACE_REGIONS

    spaces = {mission.space_id for mission in MISSIONS if mission.space_id}
    assert set(SCOUTS_SPACE_REGIONS) == spaces
    served = marker_layout()["scouts"]
    assert set(served["regions"]) == spaces
    for space_id, regions in served["regions"].items():
        assert regions, space_id
        for region in regions:
            assert len(region["box"]) == 4 and isinstance(region["from_bottom"], bool)


def test_scouts_regions_lie_on_free_print() -> None:
    # Each region is plain panel or map art: inside the scan, off every
    # frame (the Agents' place) and every other piece's printed place, and
    # off the other regions.
    from dune_imperium.display.board_layout import SCOUTS_SPACE_REGIONS

    radius = POST_SIZE / 2
    taken: list[tuple[str, Box]] = [
        *((f"frame {space_id}", box) for space_id, box in SPACE_BOXES.items()),
        *(
            (f"post {post_id}", (x - radius, y - radius, POST_SIZE, POST_SIZE))
            for post_id, (x, y) in POST_POINTS.items()
        ),
        *((f"flag {space_id}", box) for space_id, box in CONTROL_FLAG_BOXES.items()),
        *(
            (
                f"bonus spice {space_id}",
                (
                    x - MAKER_SPICE_SIZE[0] / 2,
                    y - MAKER_SPICE_SIZE[1] / 2,
                    MAKER_SPICE_SIZE[0],
                    MAKER_SPICE_SIZE[1],
                ),
            )
            for space_id, (x, y) in MAKER_SPICE_POINTS.items()
        ),
        *((f"garrison {seat}", ring) for seat, ring in enumerate(GARRISON_RINGS)),
        *((f"tile {space_id}", box) for space_id, box in LEADER_TILE_BOXES.items()),
        ("research overlay", RESEARCH_STATION_OVERLAY_BOX),
        ("shield wall", SHIELD_WALL_BOX),
        ("stepper band", FORCE_STEPPER_BAND),
        ("conflict deck", CONFLICT_DECK_SLOT),
        ("conflict", CONFLICT_SLOT),
    ]
    # The face-up Contracts are drawn 1.2 times their slot (board.js
    # CONTRACT_SLOT_SCALE), centred on it.
    from dune_imperium.display.board_layout import CONTRACT_SLOTS

    for index, (left, top, width, height) in enumerate(CONTRACT_SLOTS):
        taken.append(
            (
                f"contract {index}",
                (left - width * 0.1, top - height * 0.1, width * 1.2, height * 1.2),
            )
        )
    regions = [
        (space_id, region[:4])
        for space_id, entries in SCOUTS_SPACE_REGIONS.items()
        for region in entries
    ]
    for space_id, box in regions:
        left, top, width, height = box
        assert 0 <= left and left + width <= 100 and 0 <= top and top + height <= 100
        for name, other in taken:
            assert not _meets(box, other), (space_id, box, name)
    for index, (first_id, first) in enumerate(regions):
        for second_id, second in regions[index + 1 :]:
            assert not _meets(first, second), (first_id, second_id)


def test_scouts_regions_keep_room_beside_a_commander() -> None:
    # A Sardaukar Commander stands on three mission spaces' frames until
    # acquired [Bloodlines p. 3]; the client keeps the parts of a region
    # left and right of its figure (board.js scoutsRegionsClear), and every
    # space still has room there for a seat's piece at full size.
    from dune_imperium.content.bloodlines import COMMANDER_SETUP_SPACE_IDS
    from dune_imperium.display.board_layout import (
        SCOUTS_PIECE_SIZES,
        SCOUTS_SPACE_REGIONS,
    )

    cube = SCOUTS_PIECE_SIZES["troop"]
    shared = set(COMMANDER_SETUP_SPACE_IDS) & set(SCOUTS_SPACE_REGIONS)
    assert shared == {"sardaukar", "deliver_supplies", "gather_support"}
    for space_id in shared:
        figure = _commander_box(space_id)
        parts: list[Box] = []
        for left, top, width, height, _ in SCOUTS_SPACE_REGIONS[space_id]:
            box = (left, top, width, height)
            if not _meets(box, figure):
                parts.append(box)
                continue
            parts.append((left, top, figure[0] - 0.2 - left, height))
            right = figure[0] + figure[2] + 0.2
            parts.append((right, top, left + width - right, height))
        assert any(
            width >= cube[0] and height >= cube[1] for _, _, width, height in parts
        ), space_id


def test_scouts_pieces_are_the_size_of_the_board_print() -> None:
    from dune_imperium.display.board_layout import (
        SCOUTS_CARD_SCALE,
        SCOUTS_MIN_SCALE,
        SCOUTS_PIECE_SIZES,
    )

    sizes = SCOUTS_PIECE_SIZES
    # A troop is the Influence cube, 95 px of the 6012 px scan.
    assert sizes["troop"][0] == INFLUENCE_CUBE_SIZE
    assert round(sizes["troop"][0] / 100 * 6012) == 95
    # The printed icons: Hagga Basin's spice hexagon (99 x 100 px), Gather
    # Support's Solari coin (94 px) and Deliver Supplies' drop (88 x 153).
    assert (round(sizes["spice"][0] * 60.12), round(sizes["spice"][1] * 60.05)) == (
        99,
        100,
    )
    assert round(sizes["solari"][0] * 60.12) == 94
    assert (round(sizes["water"][0] * 60.12), round(sizes["water"][1] * 60.05)) == (
        88,
        153,
    )
    # The Control marker is the flag it lies on under a controlled space;
    # the Maker Hooks token lies flat, as long as its garrison slot is tall.
    marker_width, marker_height = sizes["marker"]
    assert all(
        abs(box[2] - marker_width) < 0.02 and abs(box[3] - marker_height) < 0.03
        for box in CONTROL_FLAG_BOXES.values()
    )
    assert sizes["maker_hooks"] == (MAKER_HOOKS_SIZE[1], MAKER_HOOKS_SIZE[0])
    # Face-down piles are a card back at a third of the card.
    assert SCOUTS_CARD_SCALE == 1 / 3
    assert sizes["intrigue"] == (2.8, 4.27)
    assert sizes["contract"] == (3.5, 2.17)
    assert 0 < SCOUTS_MIN_SCALE < 1
