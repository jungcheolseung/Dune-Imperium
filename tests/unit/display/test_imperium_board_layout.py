"""Tests for the original Dune: Imperium board picture's overlay coordinates.

The page draws an original game's tracks with the same code as Uprising's
(board.js ``renderTrackMarkers``), so the tables come in Uprising's shapes
and hold the same pieces; these tests check that, and that the measured
places stay apart from each other on the picture.
"""

from typing import Any

from tests.support.board_layout import apart, centred, ring_unit_layout

from dune_imperium.display.board_layout import (
    AGENT_ON_SPACE_HEIGHT,
    COMMANDER_HEIGHT,
    marker_layout,
)
from dune_imperium.display.board_layout_imperium import (
    CONFLICT_CROSS,
    CONFLICT_DECK_SLOT,
    CONFLICT_SLOT,
    CONFLICT_UNIT_BOXES,
    CONFLICT_UNIT_SIZES,
    CONTROL_FLAG_BOXES,
    COUNCIL_SEATS,
    FORCE_STEPPER_BAND,
    GARRISON_RINGS,
    INFLUENCE_CUBE_SIZE,
    IX_OVERLAY_BOXES,
    MAKER_SPICE_POINTS,
    MAKER_SPICE_SIZE,
    SEAT_DISC_SIZE,
    SPACE_BOXES,
    STRENGTH_CELL_X,
    STRENGTH_TOKEN_ROW_Y,
    STRENGTH_TOKEN_SIZE,
    STRENGTH_ZERO_BOX,
    STRENGTH_ZERO_POINT,
    VICTORY_POINT_CELL,
    VICTORY_POINT_Y,
    imperium_board_layout,
)

Box = tuple[float, float, float, float]

# The original board picture, 5000 x 4996 px.
ASPECT = 5000 / 4996


def _tracks() -> dict[str, Any]:
    tracks = imperium_board_layout()["tracks"]
    assert isinstance(tracks, dict)
    return tracks


def _shape(value: object) -> object:
    """A JSON value's structure: dict keys and list lengths, leaves as types."""

    if isinstance(value, dict):
        return {key: _shape(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_shape(item) for item in value]
    return float if isinstance(value, int | float) else type(value)


def test_the_tracks_come_in_uprisings_shapes() -> None:
    # Every table the original board prints has Uprising's keys, list
    # lengths and value types, so the page reads it with the same code;
    # what only Uprising's board prints has no entry at all.
    tracks, uprising = _tracks(), marker_layout()
    printed_on_both = {
        "influence",
        "control_flags",
        "maker_spice",
        "victory_points",
        "strength",
        "conflict_units",
        "garrison_units",
        "force_stepper_band",
        "council_seats",
        "disc_size",
        "conflict_deck_slot",
        "conflict_slot",
    }
    assert set(tracks) == printed_on_both
    assert set(uprising) - set(tracks) >= {
        "maker_hooks",
        "contract_slots",
        "scouts",
    }
    # The original's strength track adds its printed 0 ring (board.js lays
    # the tokens at 0 there, as on a cell, instead of Uprising's 2x2).
    strength = dict(tracks["strength"])
    assert strength.pop("zero_point") == list(STRENGTH_ZERO_POINT)
    tracks = {**tracks, "strength": strength}
    for key in printed_on_both - {"control_flags", "maker_spice"}:
        assert _shape(tracks[key]) == _shape(uprising[key]), key


def test_influence_cubes_sit_on_the_printed_strips() -> None:
    # Levels 0..6 run bottom-up, one cube per seat side by side; a cube is
    # one printed level-0 square and the same piece as a troop.
    influence = _tracks()["influence"]
    levels = influence["levels"]
    assert len(levels) == 7
    assert all(lower > upper for lower, upper in zip(levels, levels[1:], strict=False))
    seat_x = influence["seat_x"]
    pitch = [right - left for left, right in zip(seat_x, seat_x[1:], strict=False)]
    assert all(abs(step - 1.95) < 0.01 for step in pitch)
    assert min(pitch) > INFLUENCE_CUBE_SIZE
    assert CONFLICT_UNIT_SIZES["troop"][0] == INFLUENCE_CUBE_SIZE
    offsets = influence["offsets"]
    assert list(offsets) == ["emperor", "spacing_guild", "bene_gesserit", "fremen"]
    assert offsets["emperor"] == 0
    # The strips follow each other down the left edge without overlapping.
    starts = list(offsets.values())
    for upper, lower in zip(starts, starts[1:], strict=False):
        assert lower - upper > levels[0] - levels[6] + INFLUENCE_CUBE_SIZE
    assert levels[0] + starts[-1] + INFLUENCE_CUBE_SIZE / 2 < 100
    # "Place the four Alliance tokens on the marked areas of the Faction's
    # Influence tracks" [DI p. 4]: the dashed ring over the upper levels,
    # inside the strip.
    x, y = influence["alliance"]
    size = influence["alliance_size"]
    assert seat_x[0] - 1 < x - size / 2 and x + size / 2 < seat_x[-1] + 1
    assert levels[6] - 1 < y - size / 2 and y + size / 2 < levels[3]


def test_score_discs_fit_the_cells_of_the_score_track() -> None:
    # 0 at the bottom to 12 at the top, one disc a cell (cells 9-12 stray
    # up to 0.19 off the pitch where the board prints its orange line).
    assert len(VICTORY_POINT_Y) == 13
    steps = [
        lower - upper
        for lower, upper in zip(VICTORY_POINT_Y, VICTORY_POINT_Y[1:], strict=False)
    ]
    assert all(abs(step - VICTORY_POINT_CELL[1]) < 0.2 for step in steps)
    assert SEAT_DISC_SIZE < VICTORY_POINT_CELL[0]
    assert SEAT_DISC_SIZE * ASPECT < VICTORY_POINT_CELL[1]
    assert VICTORY_POINT_Y[0] + VICTORY_POINT_CELL[1] / 2 < 100


def test_strength_tokens_fit_the_printed_cells() -> None:
    # Index n is printed number n's column (index 0 unused), a straight
    # pitch; a token lies in the open part of its cell, over its row.
    assert len(STRENGTH_CELL_X) == 11
    pitch = STRENGTH_CELL_X[1] - STRENGTH_CELL_X[0]
    for left, right in zip(STRENGTH_CELL_X, STRENGTH_CELL_X[1:], strict=False):
        assert abs(right - left - pitch) < 0.02
    assert STRENGTH_TOKEN_SIZE < pitch
    upper, lower = STRENGTH_TOKEN_ROW_Y
    assert lower - upper > STRENGTH_TOKEN_SIZE
    assert lower + STRENGTH_TOKEN_SIZE * ASPECT / 2 < 100
    # The 0 spot is a printed ring on the panel above "1" and "2", a cell of
    # its own: a token there (fanned with any other at 0, at most 1.1 each
    # way) stays on the panel, off the garrison ring above and off the
    # tokens of the first row below.
    left, top, width, height = STRENGTH_ZERO_BOX
    x, y = STRENGTH_ZERO_POINT
    assert left < STRENGTH_CELL_X[1] < x < STRENGTH_CELL_X[2] < left + width
    assert top < y < top + height
    half = STRENGTH_TOKEN_SIZE / 2
    assert y + 1.1 * 0.35 + half * ASPECT < upper - half * ASPECT
    for ring in GARRISON_RINGS:
        assert apart(STRENGTH_ZERO_BOX, ring), ring
        ring_bottom = ring[1] + ring[3]
        assert ring[0] + ring[2] < x - 1.1 - half or ring_bottom < y - 0.4 - half


def _conflict_rows(
    counts: dict[str, int], width: float, scale: float
) -> list[tuple[float, int]]:
    """board.js ``conflictUnitLayout``'s rows: (height, pieces) each."""

    units = _tracks()["conflict_units"]
    gap, padding, sizes = units["gap"], units["padding"], units["sizes"]
    inner = width - 2 * padding
    rows: list[list[Any]] = []
    for kind in ("troop", "commander", "agent", "sandworm"):
        w, h = (value * scale for value in sizes[kind])
        figure = kind != "troop"
        for _ in range(counts.get(kind, 0)):
            row = rows[-1] if rows else None
            if row is None or row[0] != figure or row[1] + gap + w > inner + 1e-9:
                row = [figure, -gap, 0.0, 0]
                rows.append(row)
            row[1] += gap + w
            row[2] = max(row[2], h)
            row[3] += 1
    return [(height, count) for _, _, height, count in rows]


def _conflict_scale(counts: dict[str, int], box: Box) -> tuple[float, bool]:
    """The scale the client lays a quadrant at, and whether the rows fit."""

    units = _tracks()["conflict_units"]
    gap, padding, min_scale = units["gap"], units["padding"], units["min_scale"]
    _, _, width, height = box
    inner = height - 2 * padding

    def depth(scale: float) -> float:
        rows = _conflict_rows(counts, width, scale)
        return float(sum(h for h, _ in rows) + gap * max(0, len(rows) - 1))

    scale = 1.0
    while depth(scale) > inner + 1e-9 and scale > min_scale + 1e-9:
        scale = max(min_scale, round(scale - 0.05, 2))
    return scale, depth(scale) <= inner + 1e-9


def test_each_seat_has_a_quarter_of_the_conflict_for_its_units() -> None:
    # The Conflict is "the area of the game board in the center of the
    # garrisons" [DI p. 10]; the board prints no quadrants, so the page
    # splits the field between the rings at the rings' centres, clockwise
    # from the bottom-left for seats 0..3 like the garrisons.
    cross_x, cross_y = CONFLICT_CROSS
    for seat, box in enumerate(CONFLICT_UNIT_BOXES):
        left, top, width, height = box
        right_side, lower = seat in (2, 3), seat in (0, 3)
        assert abs((left if right_side else left + width) - cross_x) < 1e-9, seat
        assert abs((top if lower else top + height) - cross_y) < 1e-9, seat
        for ring in GARRISON_RINGS:
            assert apart(box, ring), (seat, ring)
        for other in (STRENGTH_ZERO_BOX, CONFLICT_SLOT, CONFLICT_DECK_SLOT):
            assert apart(box, other), (seat, other)
        for space_id, space in SPACE_BOXES.items():
            assert apart(box, space), (seat, space_id)
    for index, first in enumerate(CONFLICT_UNIT_BOXES):
        for second in CONFLICT_UNIT_BOXES[index + 1 :]:
            assert apart(first, second)
    # The rings' centres split the field: each seat's quarter lies beside
    # its own garrison.
    for seat, (_, top, _, height) in enumerate(GARRISON_RINGS):
        assert abs((top + height / 2) - cross_y) > 5
        quarter = CONFLICT_UNIT_BOXES[seat]
        assert (top + height / 2 < cross_y) == (quarter[1] < cross_y), seat

    # The pieces are those of the rest of this board: a troop is the
    # Influence cube, an Agent and a Commander as tall as on a space, each
    # keeping its picture's shape on the 5000 x 4996 picture.
    frame_height = SPACE_BOXES["carthag"][3]
    sizes = CONFLICT_UNIT_SIZES
    assert abs(sizes["agent"][1] - frame_height * AGENT_ON_SPACE_HEIGHT) < 1e-3
    assert abs(sizes["commander"][1] - frame_height * COMMANDER_HEIGHT) < 1e-3
    for kind, aspect in (
        ("troop", 1.0),
        ("agent", 52 / 81),
        ("commander", 130 / 195),
        ("sandworm", 62 / 57),
    ):
        width, height = sizes[kind]
        assert abs(width * ASPECT / height - aspect) < 0.005, kind

    # A quarter holds a full Conflict of troops (12) at full size, four a
    # row; with an Agent (Bloodlines' Into the Fray) and a Commander beside
    # them it shrinks its pieces but still fits without closing the rows up.
    for box in CONFLICT_UNIT_BOXES:
        assert [count for _, count in _conflict_rows({"troop": 12}, box[2], 1)] == [
            4,
            4,
            4,
        ]
        assert _conflict_scale({"troop": 12}, box) == (1.0, True)
        scale, fits = _conflict_scale(
            {"troop": 12, "commander": 1, "agent": 1, "sandworm": 1}, box
        )
        assert fits and scale >= _tracks()["conflict_units"]["min_scale"], scale


def test_garrison_rings_hold_their_units_as_pieces() -> None:
    # "Place three in one of the four circular garrisons on the game board"
    # [DI p. 5]: the setup garrison is one row at full size on the ring's
    # centre, a full one (12) three rows of four, and every garrison a game
    # can hold (0-12 troops, 0-7 Commanders) fits at no less than the
    # smallest scale.
    units = _tracks()["garrison_units"]
    for ring in GARRISON_RINGS:
        left, top, width, height = ring
        assert abs(width / 100 * 5000 - 500.3) < 1.5
        assert abs(height / 100 * 4996 - 500.3) < 1.5
        scale, pieces = ring_unit_layout({"troop": 3}, ring, units)
        assert scale == 1 and len({box[1] for _, box in pieces}) == 1
        assert abs(pieces[0][1][1] + pieces[0][1][3] / 2 - (top + height / 2)) < 1e-9
        scale, pieces = ring_unit_layout({"troop": 12}, ring, units)
        rows: dict[float, int] = {}
        for _, box in pieces:
            rows[round(box[1], 6)] = rows.get(round(box[1], 6), 0) + 1
        assert scale == 1 and sorted(rows.values()) == [4, 4, 4], rows
        for troops in range(13):
            for commanders in range(8):
                if troops or commanders:
                    counts = {"troop": troops, "commander": commanders}
                    scale, pieces = ring_unit_layout(counts, ring, units)
                    assert pieces and scale >= units["min_scale"], counts


def test_the_board_stepper_band_is_plain_desert_above_the_conflict() -> None:
    band = FORCE_STEPPER_BAND
    left, top, width, height = band
    assert 0 <= left < left + width <= 100 and 0 <= top < top + height <= 100
    for space_id, box in SPACE_BOXES.items():
        assert apart(band, box), space_id
    for space_id, box in CONTROL_FLAG_BOXES.items():
        assert apart(band, box), space_id
    for space_id, point in MAKER_SPICE_POINTS.items():
        assert apart(band, centred(point, MAKER_SPICE_SIZE)), space_id
    for box in (*GARRISON_RINGS, *CONFLICT_UNIT_BOXES, CONFLICT_SLOT):
        assert apart(band, box), box
    # Above the Conflict area, as wide as its field.
    assert top + height < min(box[1] for box in CONFLICT_UNIT_BOXES)
    assert left <= CONFLICT_UNIT_BOXES[0][0]
    assert CONFLICT_UNIT_BOXES[2][0] + CONFLICT_UNIT_BOXES[2][2] <= left + width
    assert height > 5


def test_council_discs_lie_on_the_four_chairs() -> None:
    # Four chairs left to right in the High Council row, beside the space,
    # no two discs touching.
    assert len(COUNCIL_SEATS) == 4
    xs = [x for x, _ in COUNCIL_SEATS]
    assert xs == sorted(xs)
    for first, second in zip(xs, xs[1:], strict=False):
        assert second - first > SEAT_DISC_SIZE
    council = SPACE_BOXES["imperium_high_council"]
    hall = SPACE_BOXES["hall_of_oratory"]
    for point in COUNCIL_SEATS:
        disc = centred(point, (SEAT_DISC_SIZE, SEAT_DISC_SIZE * ASPECT))
        assert council[0] + council[2] < disc[0] and disc[0] + disc[2] < hall[0]
        assert council[1] < point[1] < council[1] + council[3]


def test_the_conflict_cards_lie_in_the_two_printed_slots() -> None:
    # The deck in the left slot (the setup picture [DI p. 4] B), each round's
    # card "face up in the space next to the Conflict Deck" [DI p. 8]: two
    # portrait slots of one size side by side, clear of the spaces.
    deck, revealed = CONFLICT_DECK_SLOT, CONFLICT_SLOT
    assert deck[0] + deck[2] < revealed[0]
    assert deck[1] == revealed[1] and deck[3] == revealed[3]
    assert abs(deck[2] - revealed[2]) < 0.1
    for slot in (deck, revealed):
        assert slot[3] > slot[2]
        for space_id, box in SPACE_BOXES.items():
            assert apart(slot, box), space_id


def test_the_ix_overlay_covers_the_landsraad_and_choam_sections() -> None:
    # Rise of Ix's CHOAM board overlay covers the original Landsraad and
    # CHOAM sections [Rise of Ix p. 3]: its two pieces lie over the spaces
    # those sections print (the four it removes and the three it reprints),
    # inside the picture, side by side at one top.
    landsraad = IX_OVERLAY_BOXES["landsraad"]
    choam = IX_OVERLAY_BOXES["choam"]
    for left, top, width, height in (landsraad, choam):
        assert 0 <= left < left + width <= 100 and 0 <= top < top + height <= 100
    assert landsraad[1] == choam[1]
    assert abs(landsraad[2] - choam[2]) < 0.01
    assert landsraad[0] < choam[0] < landsraad[0] + landsraad[2]
    covered = ("imperium_high_council", "hall_of_oratory", "mentat", "rally_troops",
               "imperium_swordmaster", "sell_melange", "secure_contract")
    for space_id in covered:
        left, top, width, height = SPACE_BOXES[space_id]
        assert any(
            o[0] <= left and left + width <= o[0] + o[2]
            and o[1] <= top and top + height <= o[1] + o[3]
            for o in (landsraad, choam)
        ), space_id
    assert imperium_board_layout()["ix_overlays"] == {
        name: list(box) for name, box in IX_OVERLAY_BOXES.items()
    }
