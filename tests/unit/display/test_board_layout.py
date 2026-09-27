"""Tests for the board-scan overlay coordinates behind the browser UI."""

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
    GARRISON_POINTS,
    GARRISON_RINGS,
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

