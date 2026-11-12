"""Every Conflict card's reward rows, across every game.

The original game's cards share the table (one id, one printing;
docs/base-game-and-ix-plan.md 4.2 item 7), then Rise of Ix's three
(``content.rise_of_ix.conflict_abilities``), then Uprising's, then
Bloodlines' two (``content.bloodlines.conflict_abilities``). Merged here
from ``content.uprising.conflict_abilities``
(docs/content-core-refactor-plan.md 2B).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.bloodlines.conflict_abilities import (
    BLOODLINES_CONFLICT_REWARD_ABILITIES,
)
from dune_imperium.content.core.abilities import Ability
from dune_imperium.content.imperium.conflict_abilities import (
    IMPERIUM_CONFLICT_REWARD_ABILITIES,
)
from dune_imperium.content.rise_of_ix.conflict_abilities import (
    IX_CONFLICT_REWARD_ABILITIES,
)
from dune_imperium.content.uprising.conflict_abilities import (
    UPRISING_CONFLICT_REWARD_ABILITIES,
)

CONFLICT_REWARD_ABILITIES: Final[Mapping[str, tuple[Ability, Ability, Ability]]] = (
    MappingProxyType(
        {
            **IMPERIUM_CONFLICT_REWARD_ABILITIES,
            **IX_CONFLICT_REWARD_ABILITIES,
            **UPRISING_CONFLICT_REWARD_ABILITIES,
            **BLOODLINES_CONFLICT_REWARD_ABILITIES,
        }
    )
)
