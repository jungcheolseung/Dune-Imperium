"""Tests for the leader-card overlay coordinates behind the browser UI."""

import json
import struct
from pathlib import Path

import pytest

from dune_imperium.content.uprising.leaders import FEYD_TRAINING_TRACK
from dune_imperium.display.leader_layout import (
    CHANI_TACTICS_BOXES,
    FEYD_TRACK_BOXES,
    YRKOON_NAVIGATION_SLOT_BOXES,
    leader_layout,
)

APP_CARDS_DIR = Path(__file__).resolve().parents[3] / "assets" / "cards" / "app"
LEADER_SOURCES = APP_CARDS_DIR / "leader_sources.json"


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


def _webp_size(path: Path) -> tuple[int, int]:
    """Canvas size from a WebP header (VP8X, VP8 or VP8L), without Pillow."""
    data = path.read_bytes()[:30]
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP", path
    chunk = data[12:16]
    if chunk == b"VP8X":
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return width, height
    if chunk == b"VP8 ":
        width, height = struct.unpack("<HH", data[26:30])
        return width & 0x3FFF, height & 0x3FFF
    assert chunk == b"VP8L", (path, chunk)
    bits = int.from_bytes(data[21:25], "little")
    return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1


@pytest.mark.skipif(
    not LEADER_SOURCES.is_file(),
    reason="no leader faces drawn from the app in the assets checkout",
)
def test_app_leader_faces_keep_the_scan_geometry() -> None:
    """The leader faces scripts/dwgr/app_leaders.py draws keep the scans'
    1460x1020, and Feyd's Training track is drawn at FEYD_TRACK_BOXES: a
    change to the boxes needs the face re-rendered (``render --ids
    feyd_rautha_harkonnen``) so the play UI's token still lands on it."""
    faces = json.loads(LEADER_SOURCES.read_text())["faces"]
    for face_id, source in faces.items():
        assert source["size"] == [1460, 1020], face_id
        for language in source["sha256"]:
            path = APP_CARDS_DIR / language / source["path"]
            assert _webp_size(path) == (1460, 1020), path
    assert faces["feyd_rautha_harkonnen"]["track_boxes"] == {
        space_id: list(box) for space_id, box in FEYD_TRACK_BOXES.items()
    }
