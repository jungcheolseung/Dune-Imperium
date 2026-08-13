"""Uprising Conflict identities and tiers used to build the ten-card deck."""

from dataclasses import dataclass
from typing import Final

from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.uprising.types import BattleIcon, ConflictTier


@dataclass(frozen=True, slots=True)
class ConflictReward:
    """One printed reward row; zero values mean that icon is absent."""

    solari: int = 0
    spice: int = 0
    intrigue: int = 0
    choose_influence: int = 0

    def __post_init__(self) -> None:
        values = (self.solari, self.spice, self.intrigue, self.choose_influence)
        if min(values) < 0:
            raise ValueError("Conflict reward quantities must not be negative")
        if max(values) == 0:
            raise ValueError("a Conflict reward row must contain a reward")


@dataclass(frozen=True, slots=True)
class ConflictDefinition:
    """Conflict identity, battle icon, and optional transcribed reward rows."""

    card: CardDefinition
    tier: ConflictTier
    battle_icon: BattleIcon | None = None
    rewards: tuple[ConflictReward, ConflictReward, ConflictReward] | None = None


MAIN_P3_P4: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3, 4)),)


def _conflict(
    card_id: int,
    content_id: str,
    name: str,
    tier: ConflictTier,
    *,
    battle_icon: BattleIcon | None = None,
    rewards: tuple[ConflictReward, ConflictReward, ConflictReward] | None = None,
) -> ConflictDefinition:
    slug = f"uprising-{content_id.replace('_', '-')}"
    return ConflictDefinition(
        card=CardDefinition(
            content_id,
            name,
            MAIN_P3_P4,
            catalog_url=f"https://dunecardshub.com/cards/{card_id}/{slug}",
        ),
        tier=tier,
        battle_icon=battle_icon,
        rewards=rewards,
    )


CONFLICTS: Final = (
    _conflict(
        451,
        "skirmish_crysknife",
        "Skirmish (Crysknife)",
        ConflictTier.ONE,
        battle_icon=BattleIcon.CRYSKNIFE,
        rewards=(
            ConflictReward(choose_influence=1),
            ConflictReward(spice=1, intrigue=1),
            ConflictReward(spice=1),
        ),
    ),
    _conflict(
        452,
        "skirmish_ornithopter",
        "Skirmish (Ornithopter)",
        ConflictTier.ONE,
        battle_icon=BattleIcon.ORNITHOPTER,
        rewards=(
            ConflictReward(solari=1, intrigue=1),
            ConflictReward(solari=2, intrigue=1),
            ConflictReward(intrigue=1),
        ),
    ),
    _conflict(
        453,
        "skirmish_desert_mouse",
        "Skirmish (Desert Mouse)",
        ConflictTier.ONE,
        battle_icon=BattleIcon.DESERT_MOUSE,
        rewards=(
            ConflictReward(solari=2),
            ConflictReward(solari=3),
            ConflictReward(solari=2),
        ),
    ),
    _conflict(454, "choam_security", "CHOAM Security", ConflictTier.TWO),
    _conflict(455, "spice_freighters", "Spice Freighters", ConflictTier.TWO),
    _conflict(456, "siege_of_arrakeen", "Siege of Arrakeen", ConflictTier.TWO),
    _conflict(
        457,
        "seize_spice_refinery",
        "Seize Spice Refinery",
        ConflictTier.TWO,
    ),
    _conflict(458, "test_of_loyalty", "Test of Loyalty", ConflictTier.TWO),
    _conflict(459, "shadow_contest", "Shadow Contest", ConflictTier.TWO),
    _conflict(
        460,
        "secure_imperial_basin",
        "Secure Imperial Basin",
        ConflictTier.TWO,
    ),
    _conflict(
        461,
        "protect_the_sietches",
        "Protect the Sietches",
        ConflictTier.TWO,
    ),
    _conflict(462, "trade_dispute", "Trade Dispute", ConflictTier.TWO),
    _conflict(463, "propaganda", "Propaganda", ConflictTier.THREE),
    _conflict(
        464,
        "battle_for_imperial_basin",
        "Battle for Imperial Basin",
        ConflictTier.THREE,
    ),
    _conflict(
        465,
        "battle_for_arrakeen",
        "Battle for Arrakeen",
        ConflictTier.THREE,
    ),
    _conflict(
        466,
        "battle_for_spice_refinery",
        "Battle for Spice Refinery",
        ConflictTier.THREE,
    ),
)


def conflicts_by_tier(tier: ConflictTier) -> tuple[ConflictDefinition, ...]:
    """Return all physical Conflict cards with the requested back."""

    return tuple(conflict for conflict in CONFLICTS if conflict.tier is tier)


CONFLICTS_BY_ID: Final = {
    conflict.card.card_id: conflict for conflict in CONFLICTS
}
