"""Bloodlines' two Conflict cards (``bloodlines``).

Moved from ``content.uprising.conflicts`` (docs/content-core-refactor-plan.md
8.3, user decision 2026-11-04); ``content.registry.conflicts`` deals them after
Uprising's own cards.
"""

from typing import Final

from dune_imperium.content.bloodlines.conflict_abilities import (
    BLOODLINES_CONFLICT_REWARD_ABILITIES,
)
from dune_imperium.content.core.cards import ConflictDefinition, RewardRows
from dune_imperium.content.core.icons import BattleIcon, ConflictTier
from dune_imperium.content.core.schema import (
    CardDefinition,
    GameOption,
    SourceDocument,
    SourceRef,
)

BLOODLINES_P3: Final = (
    SourceRef(SourceDocument.BLOODLINES_RULEBOOK, (2, 3)),
    SourceRef(SourceDocument.CARD_FACE, (1,)),
)


def _rewards(conflict_id: str) -> RewardRows:
    first, second, third = BLOODLINES_CONFLICT_REWARD_ABILITIES[conflict_id]
    return first, second, third


BLOODLINES_CONFLICTS: Final = (
    # Bloodlines adds one Conflict I and one Conflict II, both with a wild
    # battle icon [Bloodlines pp. 2-3]; rewards transcribed from the card
    # faces (asset repository ``cards/en/bloodlines/conflict/``).
    ConflictDefinition(
        card=CardDefinition(
            "skirmish_wild",
            "Skirmish (Wild)",
            BLOODLINES_P3,
            catalog_url="https://dunecardshub.com/images/bloodlines-conflict-skirmish.webp",
        ),
        tier=ConflictTier.ONE,
        battle_icon=BattleIcon.WILD,
        reward_rows=_rewards("skirmish_wild"),
        requires=frozenset({GameOption.BLOODLINES}),
    ),
    ConflictDefinition(
        card=CardDefinition(
            "storms_in_the_south",
            "Storms in the South",
            BLOODLINES_P3,
            catalog_url=(
                "https://dunecardshub.com/images/"
                "bloodlines-conflict-storms-in-the-south.webp"
            ),
        ),
        tier=ConflictTier.TWO,
        battle_icon=BattleIcon.WILD,
        reward_rows=_rewards("storms_in_the_south"),
        requires=frozenset({GameOption.BLOODLINES}),
    ),
)
