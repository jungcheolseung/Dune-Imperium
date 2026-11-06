"""Dune: Imperium - Uprising content definitions.

Uprising's own data. The shared vocabulary is in ``content.core`` and the
lookups across games in ``content.registry`` (docs/content-core-refactor-plan.md).
"""

from dune_imperium.content.uprising.board import BOARD_SPACES, OBSERVATION_POSTS
from dune_imperium.content.uprising.conflicts import UPRISING_CONFLICTS
from dune_imperium.content.uprising.contracts import STANDARD_CONTRACTS
from dune_imperium.content.uprising.imperium import UPRISING_IMPERIUM_CARDS
from dune_imperium.content.uprising.intrigue import UPRISING_INTRIGUE_CARDS
from dune_imperium.content.uprising.leaders import UPRISING_LEADERS
from dune_imperium.content.uprising.objectives import OBJECTIVES
from dune_imperium.content.uprising.reserve import RESERVE_STACKS

__all__ = [
    "BOARD_SPACES",
    "UPRISING_CONFLICTS",
    "STANDARD_CONTRACTS",
    "UPRISING_IMPERIUM_CARDS",
    "UPRISING_INTRIGUE_CARDS",
    "UPRISING_LEADERS",
    "OBSERVATION_POSTS",
    "OBJECTIVES",
    "RESERVE_STACKS",
]
