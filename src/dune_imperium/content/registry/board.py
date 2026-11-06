"""Every board space and observation post any game prints.

One table for both base games (docs/base-game-and-ix-plan.md 4.2 item 7):
the original Dune: Imperium's own spaces follow Uprising's, and Rise of
Ix's four (stage P4a, plan 17.2) follow them. Moved from
``content.uprising.board`` (docs/content-core-refactor-plan.md 2B).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.core.board import BoardSpace, ObservationPost
from dune_imperium.content.imperium.board import (
    IMPERIUM_BOARD_LAYOUT,
    IMPERIUM_ONLY_BOARD_SPACES,
)
from dune_imperium.content.rise_of_ix.board import (
    IX_BOARD_SPACES,
    IX_OBSERVATION_POSTS,
)
from dune_imperium.content.uprising.board import BOARD_SPACES, OBSERVATION_POSTS

BOARD_SPACES_BY_ID: Final[Mapping[str, BoardSpace]] = MappingProxyType(
    {
        space.space_id: space
        for space in (*BOARD_SPACES, *IMPERIUM_ONLY_BOARD_SPACES, *IX_BOARD_SPACES)
    }
)

# Every observation post any game prints, Uprising's then Rise of Ix's two
# (stage P7f, [Main p. 18]): a lookup universe like ``BOARD_SPACES_BY_ID``. A
# game's own posts are ``content_for(config).observation_posts``; code that
# offers a post iterates those, code that reads a Spy's post may read these.
ALL_OBSERVATION_POSTS: Final[tuple[ObservationPost, ...]] = (
    *OBSERVATION_POSTS,
    *IX_OBSERVATION_POSTS,
)

# The original game's board in the Board Space Guide's order [DI pp. 17-18],
# its three spaces printed as Uprising's being Uprising's definitions
# (``content.imperium.board.IMPERIUM_BOARD_LAYOUT``).
IMPERIUM_BOARD_SPACES: Final[tuple[BoardSpace, ...]] = tuple(
    BOARD_SPACES_BY_ID[space] if isinstance(space, str) else space
    for space in IMPERIUM_BOARD_LAYOUT
)
