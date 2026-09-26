"""Tests for the leader-card overlay coordinates behind the browser UI."""

from dune_imperium.content.uprising.leaders import FEYD_TRAINING_TRACK
from dune_imperium.display.leader_layout import (
    CHANI_TACTICS_BOXES,
    FEYD_TRACK_BOXES,
    YRKOON_NAVIGATION_SLOT_BOXES,
    leader_layout,
)


def _inside_image(box: tuple[float, float, float, float]) -> bool:
    left, top, width, height = box
    return 0 <= left < left + width <= 100 and 0 <= top < top + height <= 100


def test_every_feyd_training_track_space_has_exactly_one_box() -> None:
    assert set(FEYD_TRACK_BOXES) == {
        space.space_id for space in FEYD_TRAINING_TRACK
    }


def test_feyd_boxes_stay_inside_the_image() -> None:
    for space_id, box in FEYD_TRACK_BOXES.items():
        assert _inside_image(box), space_id


def test_chani_has_eleven_spaces_left_to_right_without_overlap() -> None:
    assert len(CHANI_TACTICS_BOXES) == 11
    xs = [left for left, _, _, _ in CHANI_TACTICS_BOXES]
    assert xs == sorted(xs)
    for (left, _, width, _), (next_left, _, _, _) in zip(
        CHANI_TACTICS_BOXES, CHANI_TACTICS_BOXES[1:], strict=False
    ):
        assert left + width <= next_left


def test_chani_boxes_stay_inside_the_image() -> None:
    for box in CHANI_TACTICS_BOXES:
        assert _inside_image(box)


def test_yrkoon_has_four_slots_left_to_right_covering_the_strip() -> None:
    assert len(YRKOON_NAVIGATION_SLOT_BOXES) == 4
    xs = [left for left, _, _, _ in YRKOON_NAVIGATION_SLOT_BOXES]
    assert xs == sorted(xs)
    # The four slots are contiguous (unequal widths: narrow, wide, wide,
    # narrow), so each one's right edge is the next one's left edge.
    for (left, _, width, _), (next_left, _, _, _) in zip(
        YRKOON_NAVIGATION_SLOT_BOXES, YRKOON_NAVIGATION_SLOT_BOXES[1:], strict=False
    ):
        assert abs(left + width - next_left) < 0.01


def test_yrkoon_slot_boxes_stay_inside_the_image() -> None:
    for box in YRKOON_NAVIGATION_SLOT_BOXES:
        assert _inside_image(box)


def test_leader_layout_serves_the_same_tables() -> None:
    layout = leader_layout()
    assert layout["feyd_rautha_harkonnen"]["track"] == {
        space_id: list(box) for space_id, box in FEYD_TRACK_BOXES.items()
    }
    assert layout["chani"]["track"] == [
        list(box) for box in CHANI_TACTICS_BOXES
    ]
    assert layout["steersman_y_rkoon"]["navigation_slots"] == [
        list(box) for box in YRKOON_NAVIGATION_SLOT_BOXES
    ]
