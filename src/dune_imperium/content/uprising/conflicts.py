"""Uprising Conflict identities and tiers used to build the ten-card deck."""

from dataclasses import dataclass
from typing import Final

from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.uprising.types import ConflictTier


@dataclass(frozen=True, slots=True)
class ConflictDefinition:
    """Setup-relevant Conflict metadata; rewards are transcribed later."""

    card: CardDefinition
    tier: ConflictTier


MAIN_P3_P4: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3, 4)),)


def _conflict(
    card_id: int,
    content_id: str,
    name: str,
    tier: ConflictTier,
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
    )


CONFLICTS: Final = (
    _conflict(451, "skirmish_crysknife", "Skirmish (Crysknife)", ConflictTier.ONE),
    _conflict(
        452,
        "skirmish_ornithopter",
        "Skirmish (Ornithopter)",
        ConflictTier.ONE,
    ),
    _conflict(
        453,
        "skirmish_desert_mouse",
        "Skirmish (Desert Mouse)",
        ConflictTier.ONE,
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
