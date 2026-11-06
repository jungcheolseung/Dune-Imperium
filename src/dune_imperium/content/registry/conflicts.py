"""Every Conflict card any game prints, by id.

The original game's and Rise of Ix's cards follow Uprising's (one id, one
printing; docs/base-game-and-ix-plan.md 4.2 item 7). Moved from
``content.uprising.conflicts`` (docs/content-core-refactor-plan.md 2B).
"""

from typing import Final

from dune_imperium.content.bloodlines.conflicts import BLOODLINES_CONFLICTS
from dune_imperium.content.core.cards import ConflictDefinition
from dune_imperium.content.core.icons import ConflictTier
from dune_imperium.content.core.schema import GameOption
from dune_imperium.content.imperium.conflicts import IMPERIUM_CONFLICTS
from dune_imperium.content.rise_of_ix.conflicts import IX_CONFLICTS
from dune_imperium.content.uprising.conflicts import (
    UPRISING_CONFLICTS,
    UPRISING_EPIC_CONFLICTS,
)

# The Uprising-format Conflict deck: Uprising's cards, Bloodlines' two, then
# Economic Supremacy for Epic Game Mode (each dealt only with its option,
# ``conflicts_by_tier``).
CONFLICTS: Final = (
    *UPRISING_CONFLICTS,
    *BLOODLINES_CONFLICTS,
    *UPRISING_EPIC_CONFLICTS,
)

CONFLICTS_BY_ID: Final = {
    conflict.card.card_id: conflict
    for conflict in (*CONFLICTS, *IMPERIUM_CONFLICTS, *IX_CONFLICTS)
}


def conflicts_by_tier(
    tier: ConflictTier, *, bloodlines: bool = False, epic_game: bool = False
) -> tuple[ConflictDefinition, ...]:
    """Return the physical Conflict cards with the requested back in the pool."""

    return tuple(
        conflict
        for conflict in CONFLICTS
        if conflict.tier is tier
        and (bloodlines or GameOption.BLOODLINES not in conflict.requires)
        and (epic_game or GameOption.EPIC_GAME not in conflict.requires)
    )
