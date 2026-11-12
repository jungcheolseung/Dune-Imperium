"""Percent-coordinate layout of Rise of Ix on Uprising's board picture.

"Unfold only half of the CHOAM board overlay to cover only the top-right
corner of the UPRISING board" [Main p. 18] (docs/rules/rise-of-ix.md 17,
stage P7f): the overlay's CHOAM piece -- the picture the original board lays
(assets ``board/ix_overlay_choam.png``, 2100 x 1324 px;
``display.board_layout_imperium``) -- covers Assembly Hall, Gather Support,
Shipping and Accept Contract and their two printed observation posts, and
brings Interstellar Shipping, Smuggling and the Shipping track. The Ix board
(``board/ix_board.png``) lies beside the board as on the original game. "the
CHOAM board overlay and Ix board don't have observation posts printed on
them. Play as if there is one observation post on each of those boards"
[Main p. 18]: the page draws those two.

Every value is a percent of Uprising's scan (6012 x 6005 px), in the shapes
of ``display.board_layout_imperium``'s ``ix`` table, or of the Ix board's
own picture where it says so.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final

from dune_imperium.display.board_layout import POST_SIZE, SPACE_BOXES
from dune_imperium.display.board_layout_imperium import (
    IX_BOARD_PICTURE,
    IX_BOARD_SCOUTS_REGIONS,
    IX_BOARD_SPACE_BOXES,
    IX_CHOAM_FREIGHTER_ON_PIECE,
    IX_CHOAM_SCOUTS_ON_PIECE,
    IX_FREIGHTER_DISC_SIZE,
    IX_NEGOTIATOR_BOX,
    IX_NEGOTIATOR_SEATS,
    IX_OVERLAY_BOXES,
    IX_SPACE_BOXES,
    IX_TECH_SLOTS,
)
from dune_imperium.display.board_layout_imperium import (
    SPACE_BOXES as IMPERIUM_SPACE_BOXES,
)

_SCAN_WIDTH, _SCAN_HEIGHT = 6012, 6005
_PIECE_ON_ORIGINAL = IX_OVERLAY_BOXES["choam"]
IX_CHOAM_PICTURE: Final = (2100, 1324)

# The CHOAM piece on this picture. Its scale is the print's: the piece's
# space frames (measured on it for the original board) are as wide as
# Uprising's (7.6 % of the scan), so the piece is 35.79 % wide at its
# picture's proportions. Across, it is placed by eye on a composite
# (2026-10-30): its CHOAM panel's right edge over the board's CHOAM panel's
# in that corner (98.1 %), its Interstellar Shipping and Smuggling frames
# over Assembly Hall's and Gather Support's. Down, Smuggling's frame lies
# where Gather Support's was (user decision 2026-10-31: "smuggling 칸 높이가
# 기존 gather support 칸 높이와 같았으면 좋겠어"). That raises the piece's top
# 0.26 % above the board's; the board's edge stays where it is and the page
# cuts off the piece beyond it ("전체 보드판의 윗면은 고정해두고 초암 덮개
# 윗부분을 자르자", static/board.js), only the piece's blank top margin.
_IX_CHOAM_WIDTH, _IX_CHOAM_HEIGHT = 35.79, 22.59
# How far down the piece Smuggling's frame lies, as a share of its height.
_SMUGGLING_DOWN: Final = (
    IX_SPACE_BOXES["smuggling"][1] - _PIECE_ON_ORIGINAL[1]
) / _PIECE_ON_ORIGINAL[3]
IX_CHOAM_OVERLAY_BOX: Final = (
    62.92,
    round(SPACE_BOXES["gather_support"][1] - _SMUGGLING_DOWN * _IX_CHOAM_HEIGHT, 2),
    _IX_CHOAM_WIDTH,
    _IX_CHOAM_HEIGHT,
)


def _on_piece(x: float, y: float) -> tuple[float, float]:
    """A point in percent of the piece's picture, on this picture."""

    left, top, width, height = IX_CHOAM_OVERLAY_BOX
    return (round(left + x * width / 100, 2), round(top + y * height / 100, 2))


def _piece_box(
    box_on_original: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    """A box the original board's layout measured on the piece, here."""

    p_left, p_top, p_width, p_height = _PIECE_ON_ORIGINAL
    left, top, width, height = box_on_original
    x, y = _on_piece(100 * (left - p_left) / p_width, 100 * (top - p_top) / p_height)
    return (
        x,
        y,
        round(width / p_width * IX_CHOAM_OVERLAY_BOX[2], 2),
        round(height / p_height * IX_CHOAM_OVERLAY_BOX[3], 2),
    )


# The piece's two spaces, the frames the original layout matched on it.
IX_SPACE_BOXES_UPRISING: Final[Mapping[str, tuple[float, float, float, float]]] = (
    MappingProxyType(
        {
            space: _piece_box(IX_SPACE_BOXES[space])
            for space in ("interstellar_shipping", "smuggling")
        }
    )
)
# The Freighters' discs on the piece's Shipping track (each seat's column,
# bottom step first), the original layout's points on the piece.
IX_FREIGHTER_POINTS_UPRISING: Final = tuple(
    tuple(_on_piece(x, y) for x, y in row) for row in IX_CHOAM_FREIGHTER_ON_PIECE
)
# The piece's observation post, drawn by the page: on the edge of the
# spaces' panel between Interstellar Shipping and Smuggling, where Uprising
# prints its posts between two spaces (41.5 %, 52 % of the piece).
IX_OVERLAY_POST: Final = _on_piece(41.5, 52.0)
# The posts that connect only to the covered spaces: under the piece, out of
# play (``content.rulesets``, OQ-159).
IX_COVERED_POSTS: Final = (
    "landsraad-assembly-hall-gather-support",
    "choam-shipping-accept-contract",
)
IX_OVERLAY_POST_ID: Final = "choam-interstellar-shipping-smuggling"
IX_BOARD_POST_ID: Final = "landsraad-tech-negotiation-dreadnought"
# Where Arrakeen Scouts' Rise of Ix missions leave their pieces (stage P7f-2):
# Secret Stash's spice and Stowaways' troops on Smuggling, in the empty strip
# of its panel right of the printed coin and Negotiator icons (38.5-45.5 %
# across, 58-92 % down the piece, ``IX_CHOAM_SCOUTS_ON_PIECE``), as
# ``display.board_layout``'s ``SCOUTS_SPACE_REGIONS``: (left, top, width,
# height, from_bottom).
IX_SCOUTS_REGIONS_UPRISING: Final[
    Mapping[str, tuple[tuple[float, float, float, float, bool], ...]]
] = MappingProxyType(
    {
        space_id: tuple(
            (
                *_on_piece(x, y),
                round(width * IX_CHOAM_OVERLAY_BOX[2] / 100, 2),
                round(height * IX_CHOAM_OVERLAY_BOX[3] / 100, 2),
                from_bottom,
            )
            for x, y, width, height, from_bottom in regions
        )
        for space_id, regions in IX_CHOAM_SCOUTS_ON_PIECE.items()
    }
)

# The Ix board beside this picture at the print's scale: its frames are
# 449.6 px wide (``display.board_layout_imperium``) against this scan's 457,
# so 0.984 of its pixels to one of ours. Its post, in percent of its own
# picture: in the gap between Tech Negotiation and Dreadnought, right of
# their frames; as wide as Uprising's printed post discs.
_IX_BOARD_SCALE: Final = 449.6 / (SPACE_BOXES["shipping"][2] / 100 * _SCAN_WIDTH)
IX_BOARD_POST: Final = (34.0, 32.3)
# Armed Escort's dreadnoughts and spice on Dreadnought are in percent of the
# Ix board's picture (``board_layout_imperium.IX_BOARD_SCOUTS_REGIONS``).
IX_BOARD_POST_SIZE: Final = round(
    POST_SIZE * _SCAN_WIDTH * _IX_BOARD_SCALE / IX_BOARD_PICTURE[0], 2
)


def ix_board_size() -> tuple[float, float]:
    """The Ix board's width and height in percent of this picture's."""

    width, height = IX_BOARD_PICTURE
    return (
        round(100 * width / _IX_BOARD_SCALE / _SCAN_WIDTH, 2),
        round(100 * height / _IX_BOARD_SCALE / _SCAN_HEIGHT, 2),
    )


def ix_board_top() -> float:
    """The Ix board's top in percent of this picture's height, beside it.

    Its Dreadnought frame lies level with Smuggling's and where Gather
    Support's was, as the CHOAM piece is placed (user decision 2026-10-31:
    "동일한 원칙으로 드레드노트 칸도 걔네랑 높이 맞출 수 있어?"). That raises
    its top 0.37 % above this board's; this board's edge stays where it is
    and the page cuts the Ix board's picture off there (static/board.js),
    only its dark edge (the picture's first 22 of 2132 px; its printed
    border starts below 26).
    """

    height = ix_board_size()[1]
    dreadnought = IX_BOARD_SPACE_BOXES["dreadnought"][1] * height / 100
    return round(SPACE_BOXES["gather_support"][1] - dreadnought, 2)


def _regions(
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


def uprising_ix_layout() -> dict[str, Any]:
    """The layout as plain JSON-ready values (``server.catalog`` "ix")."""

    # The disc keeps its size against the frames: the original's 2.3 % of a
    # picture whose frames are 7.59 % wide.
    disc = round(
        IX_FREIGHTER_DISC_SIZE
        * SPACE_BOXES["shipping"][2]
        / IMPERIUM_SPACE_BOXES["carthag"][2],
        2,
    )
    return {
        "overlays": {"choam": list(IX_CHOAM_OVERLAY_BOX)},
        "space_boxes": {
            space: list(box) for space, box in IX_SPACE_BOXES_UPRISING.items()
        },
        "freighter": {
            "steps": [
                [list(point) for point in row] for row in IX_FREIGHTER_POINTS_UPRISING
            ],
            "disc_size": disc,
        },
        "posts": {IX_OVERLAY_POST_ID: list(IX_OVERLAY_POST)},
        "covered_posts": list(IX_COVERED_POSTS),
        "scouts_regions": _regions(IX_SCOUTS_REGIONS_UPRISING),
        "board": {
            "size": list(ix_board_size()),
            "top": ix_board_top(),
            "space_boxes": {
                space: list(box) for space, box in IX_BOARD_SPACE_BOXES.items()
            },
            "tech_slots": [list(box) for box in IX_TECH_SLOTS],
            "negotiator_box": list(IX_NEGOTIATOR_BOX),
            "negotiator_seats": [list(point) for point in IX_NEGOTIATOR_SEATS],
            "posts": {IX_BOARD_POST_ID: list(IX_BOARD_POST)},
            "post_size": IX_BOARD_POST_SIZE,
            "scouts_regions": _regions(IX_BOARD_SCOUTS_REGIONS),
        },
    }
