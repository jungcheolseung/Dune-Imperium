"""Percent-coordinate layout of the original Dune: Imperium board picture.

The play server can serve the original game's printed board
(``assets/board/imperium.jpg``, the English board of Tabletop Simulator mod
2354919205, 5000x4996 px; the assets README has its source) and the
browser draws an original game's live state over it the way
``display.board_layout`` does for the Uprising scan: a clickable hotspot
per board space, Agent tokens, Control markers and Maker bonus spice
(docs/base-game-and-ix-plan.md 18, stage P5b). Every value is a percentage
of the picture's width or height, in the same shapes and units as the
Uprising tables, so the page reads either board through one accessor
(``static/core.js`` ``boardLayout``).

``SPACE_BOXES`` are keyed by the engine's ids of the original board's 22
spaces (``content.imperium.board``), the three it shares with Uprising
(Arrakeen, Imperial Basin, Secrets) included: a space has its own box on
each board. The tracks (Influence, Score, strength, the Conflict and the
High Council) are not measured yet; until they are, the page keeps the
seats' counts in their panels (``static/panels.js`` ``textBoardStats``).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final

SPACE_BOXES: Final[Mapping[str, tuple[float, float, float, float]]] = (
    MappingProxyType({})
)
SPACE_FRAME_CUT: Final = (11.8, 15.3)
CONTROL_FLAG_BOXES: Final[Mapping[str, tuple[float, float, float, float]]] = (
    MappingProxyType({})
)
CONTROL_FLAG_NOTCH: Final = 0.2
MAKER_SPICE_POINTS: Final[Mapping[str, tuple[float, float]]] = MappingProxyType({})
MAKER_SPICE_SIZE: Final = (2.8, 2.4)
MENTAT_POINT: Final[tuple[float, float] | None] = None
MENTAT_HEIGHT: Final = 0.0


def imperium_board_layout() -> dict[str, Any]:
    """Return the layout as plain JSON-ready values (``server.catalog``)."""

    return {
        "space_boxes": {space: list(box) for space, box in SPACE_BOXES.items()},
        "space_frame": {"cut": list(SPACE_FRAME_CUT)},
        "tracks": {
            "control_flags": {
                "boxes": {
                    space: list(box) for space, box in CONTROL_FLAG_BOXES.items()
                },
                "notch": CONTROL_FLAG_NOTCH,
            },
            "maker_spice": {
                "points": {
                    space: list(point) for space, point in MAKER_SPICE_POINTS.items()
                },
                "size": list(MAKER_SPICE_SIZE),
            },
        },
        "mentat": (
            None
            if MENTAT_POINT is None
            else {"point": list(MENTAT_POINT), "height": MENTAT_HEIGHT}
        ),
    }
