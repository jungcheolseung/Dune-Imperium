"""Uprising Conflict identities and tiers used to build the ten-card deck."""

from typing import Final

from dune_imperium.content.core.cards import (
    ConflictDefinition,
    RewardRows,
)
from dune_imperium.content.core.icons import BattleIcon, ConflictTier
from dune_imperium.content.core.schema import (
    CardDefinition,
    GameOption,
    SourceDocument,
    SourceRef,
)
from dune_imperium.content.uprising.conflict_abilities import (
    UPRISING_CONFLICT_REWARD_ABILITIES,
)


def _rewards(conflict_id: str) -> RewardRows:
    """The card's three reward rows: its records (``conflict_abilities``,
    composed A5b) -- Uprising's own, as every card here is Uprising's."""

    first, second, third = UPRISING_CONFLICT_REWARD_ABILITIES[conflict_id]
    return first, second, third


MAIN_P3_P4: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3, 4)),)


def _conflict(
    card_id: int,
    content_id: str,
    name: str,
    tier: ConflictTier,
    *,
    battle_icon: BattleIcon | None = None,
    shield_wall_protected: bool = False,
    reward_rows: RewardRows | None = None,
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
        shield_wall_protected=shield_wall_protected,
        reward_rows=reward_rows,
    )


# Uprising's own Conflict cards; Bloodlines' two are ``content.bloodlines.
# conflicts`` and ``content.registry.conflicts.CONFLICTS`` joins them.
UPRISING_CONFLICTS: Final = (
    _conflict(
        451,
        "skirmish_crysknife",
        "Skirmish (Crysknife)",
        ConflictTier.ONE,
        battle_icon=BattleIcon.CRYSKNIFE,
        reward_rows=_rewards("skirmish_crysknife"),
    ),
    _conflict(
        452,
        "skirmish_ornithopter",
        "Skirmish (Ornithopter)",
        ConflictTier.ONE,
        battle_icon=BattleIcon.ORNITHOPTER,
        reward_rows=_rewards("skirmish_ornithopter"),
    ),
    _conflict(
        453,
        "skirmish_desert_mouse",
        "Skirmish (Desert Mouse)",
        ConflictTier.ONE,
        battle_icon=BattleIcon.DESERT_MOUSE,
        reward_rows=_rewards("skirmish_desert_mouse"),
    ),
    _conflict(
        454,
        "choam_security",
        "CHOAM Security",
        ConflictTier.TWO,
        battle_icon=BattleIcon.CRYSKNIFE,
        reward_rows=_rewards("choam_security"),
    ),
    _conflict(
        455,
        "spice_freighters",
        "Spice Freighters",
        ConflictTier.TWO,
        battle_icon=BattleIcon.CRYSKNIFE,
        reward_rows=_rewards("spice_freighters"),
    ),
    _conflict(
        456,
        "siege_of_arrakeen",
        "Siege of Arrakeen",
        ConflictTier.TWO,
        battle_icon=BattleIcon.ORNITHOPTER,
        shield_wall_protected=True,
        reward_rows=_rewards("siege_of_arrakeen"),
    ),
    _conflict(
        457,
        "seize_spice_refinery",
        "Seize Spice Refinery",
        ConflictTier.TWO,
        battle_icon=BattleIcon.CRYSKNIFE,
        shield_wall_protected=True,
        reward_rows=_rewards("seize_spice_refinery"),
    ),
    _conflict(
        458,
        "test_of_loyalty",
        "Test of Loyalty",
        ConflictTier.TWO,
        battle_icon=BattleIcon.ORNITHOPTER,
        reward_rows=_rewards("test_of_loyalty"),
    ),
    _conflict(
        459,
        "shadow_contest",
        "Shadow Contest",
        ConflictTier.TWO,
        battle_icon=BattleIcon.ORNITHOPTER,
        reward_rows=_rewards("shadow_contest"),
    ),
    _conflict(
        460,
        "secure_imperial_basin",
        "Secure Imperial Basin",
        ConflictTier.TWO,
        battle_icon=BattleIcon.DESERT_MOUSE,
        shield_wall_protected=True,
        reward_rows=_rewards("secure_imperial_basin"),
    ),
    _conflict(
        461,
        "protect_the_sietches",
        "Protect the Sietches",
        ConflictTier.TWO,
        battle_icon=BattleIcon.DESERT_MOUSE,
        reward_rows=_rewards("protect_the_sietches"),
    ),
    _conflict(
        462,
        "trade_dispute",
        "Trade Dispute",
        ConflictTier.TWO,
        battle_icon=BattleIcon.DESERT_MOUSE,
        reward_rows=_rewards("trade_dispute"),
    ),
    _conflict(
        463,
        "propaganda",
        "Propaganda",
        ConflictTier.THREE,
        battle_icon=BattleIcon.WILD,
        reward_rows=_rewards("propaganda"),
    ),
    _conflict(
        464,
        "battle_for_imperial_basin",
        "Battle for Imperial Basin",
        ConflictTier.THREE,
        battle_icon=BattleIcon.ORNITHOPTER,
        shield_wall_protected=True,
        reward_rows=_rewards("battle_for_imperial_basin"),
    ),
    _conflict(
        465,
        "battle_for_arrakeen",
        "Battle for Arrakeen",
        ConflictTier.THREE,
        battle_icon=BattleIcon.CRYSKNIFE,
        shield_wall_protected=True,
        reward_rows=_rewards("battle_for_arrakeen"),
    ),
    _conflict(
        466,
        "battle_for_spice_refinery",
        "Battle for Spice Refinery",
        ConflictTier.THREE,
        battle_icon=BattleIcon.DESERT_MOUSE,
        shield_wall_protected=True,
        reward_rows=_rewards("battle_for_spice_refinery"),
    ),
)

# Economic Supremacy, the fifth Conflict III Epic Game Mode adds; the registry
# deals it after Bloodlines' cards, as the one deck always listed it.
UPRISING_EPIC_CONFLICTS: Final = (
    # Epic Game Mode needs a fifth Conflict III: "In this situation, you
    # should add Economic Supremacy" [Main p. 18] [Rise of Ix p. 10]. Rise of
    # Ix card face: no battle icon, no location; first place 1 VP plus two
    # optional arrows (6 Solari, 4 spice -> 1 VP each).
    ConflictDefinition(
        card=CardDefinition(
            "economic_supremacy",
            "Economic Supremacy",
            (
                SourceRef(SourceDocument.MAIN_RULEBOOK, (18,)),
                SourceRef(SourceDocument.RISE_OF_IX_RULEBOOK, (10,)),
                SourceRef(SourceDocument.CARD_FACE, (1,)),
            ),
            catalog_url=(
                "https://dunecardshub.com/images/"
                "rise-of-ix-conflict-economic-supremacy.webp"
            ),
        ),
        tier=ConflictTier.THREE,
        reward_rows=_rewards("economic_supremacy"),
        requires=frozenset({GameOption.EPIC_GAME}),
    ),
)
