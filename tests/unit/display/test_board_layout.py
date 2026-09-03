"""Tests for the board-scan overlay coordinates behind the browser UI."""

from dune_imperium.content.uprising.board import BOARD_SPACES, OBSERVATION_POSTS
from dune_imperium.display.board_layout import POST_POINTS, SPACE_BOXES


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
