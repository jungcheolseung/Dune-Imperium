"""Percent-coordinate layout of printed leader-card state for the browser UI.

Feyd-Rautha Harkonnen's Training track and Chani's Tactics track hold a
per-player token printed on the leader card itself, and Steersman Y'rkoon's
Navigation cards sit face down in four numbered slots along its top edge.
The browser draws each seat's live state on top of the leader-card image the
same way ``display.board_layout`` draws the shared board scan: the image
becomes a stage and the token or slot is positioned in percent of it.

Every value is a percentage of the leader-card image's width or height,
``(left, top, width, height)`` in the same order as
``board_layout.SPACE_BOXES``. They were measured by hand on 2026-09-25
against the owner's English leader scans (``cards/en/{uprising,
bloodlines}/leader/*.webp``, 1460 px wide: Feyd-Rautha Harkonnen
1460x1020, Chani and Steersman Y'rkoon 1460x1022) using fine-pixel grid
overlays, cross-checked with brightness-profile scans for Chani's uniform
row and Y'rkoon's slot dividers, and confirmed by drawing the boxes back
onto the card and viewing the result (overlay screenshots kept at
``…/scratchpad/leaders/overlays/{feyd,chani,yrkoon}_overlay.png``). Feyd's
Korean scan is the same 1460x1020; the Bloodlines Korean scans (Chani,
Y'rkoon) are 1460x1020, 2 px shorter than their English counterparts, but
applying the English boxes unchanged still lands on the same printed
spaces on all three Korean scans (``…_ko_overlay.png``), so one table
drives both languages. A differently cropped scan needs a re-measure, not
a rules change, exactly as ``board_layout`` notes for the shared board.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final

# Feyd-Rautha Harkonnen's Training track (``FEYD_TRAINING_TRACK``,
# ``content.uprising.leaders``): the branching path of printed icons lower
# right of the card art, one box per named space the Feyd token can stand on
# ("Move your Feyd token one space to the right on your Training track"
# [Main p. 17]). ``start``'s box is the plain square left of the first fork;
# the others are the white rounded-rectangle icon each space prints.
FEYD_TRACK_BOXES: Final[Mapping[str, tuple[float, float, float, float]]] = (
    MappingProxyType(
        {
            "start": (41.1, 63.4, 6.7, 10.0),
            "paid_trash": (48.2, 58.9, 15.6, 9.0),
            "first_spy": (48.2, 69.2, 15.6, 8.8),
            "mid_trash": (65.5, 63.5, 5.9, 10.5),
            "late_trash": (72.8, 58.9, 15.0, 9.0),
            "second_spy": (72.8, 69.2, 8.7, 8.8),
            "double_spice": (81.8, 69.2, 6.0, 8.8),
            "final": (88.9, 57.4, 10.5, 21.9),
        }
    )
)

# Chani's Tactics track (``tactics_track_space``, ``core.player``): eleven
# equal-width spaces in one horizontal strip below the card art, index 0..10
# left to right for the token's printed space 1..11
# [Bloodlines p. 12]. Space 0 prints "6P" and space 2 "1-4P" (this game's
# four-player start, ``rules.tactics.TACTICS_TRACK_START``) — printed
# player-count starting markers, not rewards. Space 5 pays one spice
# (``rules.tactics.TACTICS_SPICE_SPACE``, the orange hex) and space 10 pays
# water and resets the token.
CHANI_TACTICS_BOXES: Final[tuple[tuple[float, float, float, float], ...]] = (
    (10.3, 65.7, 6.7, 9.2),
    (18.5, 65.7, 6.6, 9.2),
    (26.4, 65.7, 6.6, 9.2),
    (34.5, 65.7, 6.6, 9.2),
    (42.4, 65.7, 6.6, 9.2),
    (50.3, 65.7, 6.5, 9.2),
    (58.3, 65.7, 6.6, 9.2),
    (66.2, 65.7, 6.6, 9.2),
    (74.1, 65.7, 6.6, 9.2),
    (82.1, 65.7, 6.6, 9.2),
    (90.0, 65.7, 6.6, 9.2),
)

# Steersman Y'rkoon's four Navigation-card slots (``rules.navigation.
# NAVIGATION_SLOTS``), the numbered strip along the top edge where the
# face-down cards are placed "above" the leader card, in order
# ("Choose four to place face down above, in order" [card face]). The
# printed slots are not equal width: 1 and 4 are narrow, 2 and 3 wide.
YRKOON_NAVIGATION_SLOT_BOXES: Final[tuple[tuple[float, float, float, float], ...]] = (
    (2.2, 2.6, 17.3, 6.0),
    (19.5, 2.6, 30.8, 6.0),
    (50.3, 2.6, 30.7, 6.0),
    (81.0, 2.6, 17.4, 6.0),
)


def leader_layout() -> dict[str, dict[str, Any]]:
    """Return every leader-card overlay table, keyed by leader id.

    Only leaders with printed on-card state carry an entry; every other
    leader (including the pair with no on-card state, Jessica's flip and
    the leaders that only touch board/hand resources) has none.
    """

    return {
        "feyd_rautha_harkonnen": {
            "track": {
                space_id: list(box) for space_id, box in FEYD_TRACK_BOXES.items()
            },
        },
        "chani": {
            "track": [list(box) for box in CHANI_TACTICS_BOXES],
        },
        "steersman_y_rkoon": {
            "navigation_slots": [
                list(box) for box in YRKOON_NAVIGATION_SLOT_BOXES
            ],
        },
    }
