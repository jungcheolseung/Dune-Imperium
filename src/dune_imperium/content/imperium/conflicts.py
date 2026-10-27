"""The original game's 18 Conflict cards (docs/rules/imperium-base.md 3, 10).

Conflict I 4, II 10, III 4 [DI p. 3]; the deck takes one I, five II and four
III [DI p. 4]. The cards print no battle icon and no Shield Wall, and stay
face up on the board after Combat instead of going to the winner [DI pp. 8,
12]. Names repeated from Uprising but printed with other rewards take
``imperium_`` ids (docs/base-game-and-ix-plan.md 4.2 item 7, 15.2).
"""

from typing import Final

from dune_imperium.content.imperium.conflict_abilities import (
    IMPERIUM_CONFLICT_REWARD_ABILITIES,
)
from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.uprising.conflicts import ConflictDefinition
from dune_imperium.content.uprising.types import ConflictTier

_SOURCES: Final = (SourceRef(SourceDocument.IMPERIUM_RULEBOOK, (3, 4, 12)),)


def _conflict(content_id: str, name: str, tier: ConflictTier) -> ConflictDefinition:
    first, second, third = IMPERIUM_CONFLICT_REWARD_ABILITIES[content_id]
    return ConflictDefinition(
        card=CardDefinition(content_id, name, _SOURCES),
        tier=tier,
        reward_rows=(first, second, third),
    )


# Typed: ``content.uprising.conflicts`` reads it while both modules load.
IMPERIUM_CONFLICTS: Final[tuple[ConflictDefinition, ...]] = (
    _conflict("skirmish_a", "Skirmish", ConflictTier.ONE),
    _conflict("skirmish_b", "Skirmish", ConflictTier.ONE),
    _conflict("skirmish_c", "Skirmish", ConflictTier.ONE),
    _conflict("skirmish_d", "Skirmish", ConflictTier.ONE),
    _conflict("cloak_and_dagger", "Cloak and Dagger", ConflictTier.TWO),
    _conflict("desert_power_conflict", "Desert Power", ConflictTier.TWO),
    _conflict("guild_bank_raid", "Guild Bank Raid", ConflictTier.TWO),
    _conflict("machinations", "Machinations", ConflictTier.TWO),
    _conflict("raid_stockpiles", "Raid Stockpiles", ConflictTier.TWO),
    _conflict(
        "imperium_secure_imperial_basin", "Secure Imperial Basin", ConflictTier.TWO
    ),
    _conflict("imperium_siege_of_arrakeen", "Siege of Arrakeen", ConflictTier.TWO),
    _conflict("siege_of_carthag", "Siege of Carthag", ConflictTier.TWO),
    _conflict("sort_through_the_chaos", "Sort Through the Chaos", ConflictTier.TWO),
    _conflict("terrible_purpose", "Terrible Purpose", ConflictTier.TWO),
    _conflict(
        "imperium_battle_for_arrakeen", "Battle for Arrakeen", ConflictTier.THREE
    ),
    _conflict("battle_for_carthag", "Battle for Carthag", ConflictTier.THREE),
    _conflict(
        "imperium_battle_for_imperial_basin",
        "Battle for Imperial Basin",
        ConflictTier.THREE,
    ),
    _conflict("grand_vision", "Grand Vision", ConflictTier.THREE),
)
