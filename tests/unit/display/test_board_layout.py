"""Tests for the board-scan overlay coordinates behind the browser UI."""

from dune_imperium.content.uprising.board import (
    BOARD_SPACES,
    OBSERVATION_POSTS,
    Faction,
)
from dune_imperium.display.board_layout import (
    POST_POINTS,
    RESEARCH_STATION_OVERLAY_BOX,
    SHIELD_WALL_BOX,
    SHIELD_WALL_ROTATION,
    SPACE_BOXES,
    marker_layout,
)


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


def test_every_board_space_has_exactly_one_hotspot_box() -> None:
    assert set(SPACE_BOXES) == {space.space_id for space in BOARD_SPACES}


def test_every_observation_post_has_a_point() -> None:
    assert set(POST_POINTS) == {post.post_id for post in OBSERVATION_POSTS}


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

    # Immortality's Research Station overlay (782 x 425) covers the printed
    # space, whose hotspot stays inside it.
    assert abs(box_aspect(RESEARCH_STATION_OVERLAY_BOX) - 782 / 425) < 0.01
    left, top, width, height = RESEARCH_STATION_OVERLAY_BOX
    hot_left, hot_top, hot_width, hot_height = SPACE_BOXES["research_station"]
    assert left <= hot_left and hot_left + hot_width <= left + width
    assert top <= hot_top and hot_top + hot_height <= top + height

    # Tuek's Sietch has no print: its box is its tile picture (550 x 310),
    # clear of Imperial Basin above it.
    tuek = SPACE_BOXES["tuek_sietch"]
    assert abs(box_aspect(tuek) - 550 / 310) < 0.01
    assert tuek[1] > basin[1] + basin[3]

