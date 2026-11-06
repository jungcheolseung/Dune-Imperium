"""Rise of Ix on Uprising's board picture (stage P7f,
``display.board_layout_uprising_ix``).

"Unfold only half of the CHOAM board overlay to cover only the top-right
corner of the UPRISING board" [Main p. 18] (docs/rules/rise-of-ix.md 17):
the overlay's CHOAM piece covers the four spaces and two posts of that
corner, prints Interstellar Shipping, Smuggling and the Shipping track at the
print's scale, and the two posts Rise of Ix's boards do not print are drawn
on the piece and on the Ix board.
"""

from tests.support.board_layout import apart, centred

from dune_imperium.content.rise_of_ix.board import IX_OBSERVATION_POSTS
from dune_imperium.content.rulesets import UPRISING_IX_OVERLAID_SPACE_IDS
from dune_imperium.content.uprising.board import OBSERVATION_POSTS
from dune_imperium.display.board_layout import POST_POINTS, POST_SIZE, SPACE_BOXES
from dune_imperium.display.board_layout_imperium import (
    IX_BOARD_PICTURE,
    IX_BOARD_SCOUTS_REGIONS,
    IX_BOARD_SPACE_BOXES,
    IX_CHOAM_FREIGHTER_ON_PIECE,
    IX_FREIGHTER_POINTS,
    IX_NEGOTIATOR_BOX,
    IX_TECH_SLOTS,
)
from dune_imperium.display.board_layout_uprising_ix import (
    IX_BOARD_POST,
    IX_BOARD_POST_ID,
    IX_BOARD_POST_SIZE,
    IX_CHOAM_OVERLAY_BOX,
    IX_CHOAM_PICTURE,
    IX_COVERED_POSTS,
    IX_FREIGHTER_POINTS_UPRISING,
    IX_OVERLAY_POST,
    IX_OVERLAY_POST_ID,
    IX_SCOUTS_REGIONS_UPRISING,
    IX_SPACE_BOXES_UPRISING,
    ix_board_size,
    ix_board_top,
    uprising_ix_layout,
)

# Uprising's scan, 6012 x 6005 px.
ASPECT = 6012 / 6005


def _inside(point: tuple[float, float], box: tuple[float, float, float, float]) -> bool:
    x, y = point
    left, top, width, height = box
    return left <= x <= left + width and top <= y <= top + height


def _covers(outer: tuple[float, float, float, float], inner: tuple[float, ...]) -> bool:
    left, top, width, height = outer
    i_left, i_top, i_width, i_height = inner
    return (
        left <= i_left
        and top <= i_top
        and i_left + i_width <= left + width
        and i_top + i_height <= top + height
    )


def test_the_piece_covers_the_corner_at_the_print_s_scale() -> None:
    left, top, width, height = IX_CHOAM_OVERLAY_BOX
    assert 0 <= left < left + width <= 100 and top + height <= 100
    picture_w, picture_h = IX_CHOAM_PICTURE
    assert abs(width / height * ASPECT - picture_w / picture_h) < 0.01
    # The four covered spaces and the two posts that connect only to them.
    for space_id in UPRISING_IX_OVERLAID_SPACE_IDS:
        assert _covers(IX_CHOAM_OVERLAY_BOX, SPACE_BOXES[space_id]), space_id
    for post_id in IX_COVERED_POSTS:
        assert _inside(POST_POINTS[post_id], IX_CHOAM_OVERLAY_BOX), post_id
    covered = set(UPRISING_IX_OVERLAID_SPACE_IDS)
    for post in OBSERVATION_POSTS:
        only_covered = set(post.connected_space_ids) <= covered
        assert (post.post_id in IX_COVERED_POSTS) == only_covered, post.post_id
    # Every other space and post stays in sight.
    for space_id, box in SPACE_BOXES.items():
        if space_id not in covered:
            assert apart(IX_CHOAM_OVERLAY_BOX, box), space_id
    for post_id, point in POST_POINTS.items():
        if post_id not in IX_COVERED_POSTS:
            assert apart(
                IX_CHOAM_OVERLAY_BOX, centred(point, (POST_SIZE, POST_SIZE))
            ), post_id


def test_smuggling_lies_where_gather_support_was() -> None:
    """User decision 2026-10-31: "smuggling 칸 높이가 기존 gather support 칸
    높이와 같았으면 좋겠어". The piece then reaches above the board's top
    edge, which stays where it is: the page cuts the piece off there
    ("전체 보드판의 윗면은 고정해두고 초암 덮개 윗부분을 자르자"), and only its
    blank top margin goes (the picture's first 15 of 1324 px are its dark
    edge; the printed panel starts below 40)."""

    smuggling = IX_SPACE_BOXES_UPRISING["smuggling"]
    assert smuggling[1] == SPACE_BOXES["gather_support"][1]
    left, top, width, height = IX_CHOAM_OVERLAY_BOX
    cut = -top / height * IX_CHOAM_PICTURE[1]
    assert 0 < cut < 20
    # Nothing the piece carries lies in the cut-off part.
    disc = uprising_ix_layout()["freighter"]["disc_size"]
    for row in IX_FREIGHTER_POINTS_UPRISING:
        for _, y in row:
            assert y - disc / 2 > 0
    for box in IX_SPACE_BOXES_UPRISING.values():
        assert box[1] > 0
    assert IX_OVERLAY_POST[1] - POST_SIZE / 2 > 0
    for regions in IX_SCOUTS_REGIONS_UPRISING.values():
        for region in regions:
            assert region[1] > 0


def test_the_ix_board_s_dreadnought_lies_level_with_smuggling() -> None:
    """User decision 2026-10-31: "동일한 원칙으로 드레드노트 칸도 걔네랑 높이
    맞출 수 있어?" -- the Ix board beside is raised until its Dreadnought
    frame lies where Gather Support's was, level with Smuggling's. Its
    picture is cut off at this board's top edge, which stays where it is:
    only its dark edge goes (the first 22 of 2132 px; its printed border
    starts below 26), and nothing on it lies there."""

    _, height = ix_board_size()
    top = ix_board_top()
    assert uprising_ix_layout()["board"]["top"] == top
    dreadnought = top + IX_BOARD_SPACE_BOXES["dreadnought"][1] * height / 100
    assert abs(dreadnought - SPACE_BOXES["gather_support"][1]) < 0.01
    assert abs(dreadnought - IX_SPACE_BOXES_UPRISING["smuggling"][1]) < 0.01
    # The cut part, in percent of the Ix board's picture.
    cut = -top / height * 100
    assert 0 < cut / 100 * IX_BOARD_PICTURE[1] < 25
    for box in (*IX_BOARD_SPACE_BOXES.values(), *IX_TECH_SLOTS, IX_NEGOTIATOR_BOX):
        assert box[1] > cut
    assert IX_BOARD_POST[1] - IX_BOARD_POST_SIZE > cut
    for regions in IX_BOARD_SCOUTS_REGIONS.values():
        for region in regions:
            assert region[1] > cut


def test_the_piece_prints_its_spaces_track_and_post_on_it() -> None:
    assert set(IX_SPACE_BOXES_UPRISING) == {"interstellar_shipping", "smuggling"}
    for space_id, box in IX_SPACE_BOXES_UPRISING.items():
        assert _covers(IX_CHOAM_OVERLAY_BOX, box), space_id
        # As large as the board's printed frames.
        assert abs(box[2] - SPACE_BOXES["shipping"][2]) < 0.05, space_id
        assert abs(box[3] - SPACE_BOXES["shipping"][3]) < 0.05, space_id
    shipping = IX_SPACE_BOXES_UPRISING["interstellar_shipping"]
    smuggling = IX_SPACE_BOXES_UPRISING["smuggling"]
    assert apart(shipping, smuggling) and shipping[1] < smuggling[1]
    # The Shipping track: four steps of four seat columns, bottom step first,
    # each disc on the piece, as on the original board.
    assert len(IX_FREIGHTER_POINTS_UPRISING) == len(IX_FREIGHTER_POINTS) == 4
    assert len(IX_CHOAM_FREIGHTER_ON_PIECE) == 4
    for row in IX_FREIGHTER_POINTS_UPRISING:
        assert len(row) == 4
        for point in row:
            assert _inside(point, IX_CHOAM_OVERLAY_BOX)
    bottom, *_, top = IX_FREIGHTER_POINTS_UPRISING
    assert all(low[1] > high[1] for low, high in zip(bottom, top, strict=True))
    # Its post, between its two spaces and clear of their frames.
    assert _inside(IX_OVERLAY_POST, IX_CHOAM_OVERLAY_BOX)
    post = centred(IX_OVERLAY_POST, (POST_SIZE, POST_SIZE))
    assert apart(post, shipping) and apart(post, smuggling)
    assert shipping[1] + shipping[3] < IX_OVERLAY_POST[1] < smuggling[1]


def test_the_ix_board_carries_the_other_post() -> None:
    assert {post.post_id for post in IX_OBSERVATION_POSTS} == {
        IX_OVERLAY_POST_ID,
        IX_BOARD_POST_ID,
    }
    tech = IX_BOARD_SPACE_BOXES["tech_negotiation"]
    dreadnought = IX_BOARD_SPACE_BOXES["dreadnought"]
    x, y = IX_BOARD_POST
    assert tech[1] + tech[3] < y < dreadnought[1]
    assert x > max(tech[0] + tech[2], dreadnought[0] + dreadnought[2])
    width, height = ix_board_size()
    assert 30 < width < 40 and 30 < height < 40
    layout = uprising_ix_layout()
    board = layout["board"]
    assert board["posts"] == {IX_BOARD_POST_ID: list(IX_BOARD_POST)}
    # The drawn disc is as wide as the scan's printed ones.
    assert abs(board["post_size"] * width / 100 - POST_SIZE) < 0.02
    assert layout["posts"] == {IX_OVERLAY_POST_ID: list(IX_OVERLAY_POST)}
    assert layout["covered_posts"] == list(IX_COVERED_POSTS)


def test_rise_of_ix_missions_leave_their_pieces_on_their_own_boards() -> None:
    # Arrakeen Scouts' Rise of Ix missions (stage P7f-2): Secret Stash and
    # Stowaways on Smuggling, on the piece beside its frame; Armed Escort on
    # Dreadnought, on the Ix board beside its frame and below its panel.
    from dune_imperium.content.arrakeen_scouts import MISSIONS

    ix_spaces = {
        mission.space_id
        for mission in MISSIONS
        if mission.rise_of_ix_only and mission.space_id
    }
    assert ix_spaces == set(IX_SCOUTS_REGIONS_UPRISING) | set(IX_BOARD_SCOUTS_REGIONS)
    smuggling = IX_SPACE_BOXES_UPRISING["smuggling"]
    for left, top, width, height, _ in IX_SCOUTS_REGIONS_UPRISING["smuggling"]:
        region = (left, top, width, height)
        assert _covers(IX_CHOAM_OVERLAY_BOX, region)
        assert apart(region, smuggling)
        assert left > smuggling[0] + smuggling[2]
    dreadnought = IX_BOARD_SPACE_BOXES["dreadnought"]
    for left, top, width, height, _ in IX_BOARD_SCOUTS_REGIONS["dreadnought"]:
        region = (left, top, width, height)
        assert 0 <= left < left + width <= 100 and 0 <= top < top + height <= 100
        assert apart(region, dreadnought)
    layout = uprising_ix_layout()
    assert set(layout["scouts_regions"]) == {"smuggling"}
    assert set(layout["board"]["scouts_regions"]) == {"dreadnought"}
