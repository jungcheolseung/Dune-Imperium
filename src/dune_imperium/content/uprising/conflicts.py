"""Uprising Conflict identities and tiers used to build the ten-card deck."""

from dataclasses import dataclass
from typing import Final

from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.types import BattleIcon, ConflictTier


@dataclass(frozen=True, slots=True)
class ConflictReward:
    """One printed reward row; zero values mean that icon is absent."""

    solari: int = 0
    spice: int = 0
    water: int = 0
    intrigue: int = 0
    troops: int = 0
    place_spies: int = 0
    contracts: int = 0
    trash_cards: int = 0
    victory_points: int = 0
    choose_influence: int = 0
    choose_distinct_influence: int = 0
    faction_influence: int = 0
    influence_faction: Faction | None = None
    control_space_id: str | None = None
    optional_spice_cost: int = 0
    optional_solari_cost: int = 0
    optional_recall_spies: int = 0
    optional_victory_points: int = 0

    def __post_init__(self) -> None:
        values = (
            self.solari,
            self.spice,
            self.water,
            self.intrigue,
            self.troops,
            self.place_spies,
            self.contracts,
            self.trash_cards,
            self.victory_points,
            self.choose_influence,
            self.choose_distinct_influence,
            self.faction_influence,
            self.optional_spice_cost,
            self.optional_solari_cost,
            self.optional_recall_spies,
            self.optional_victory_points,
        )
        if min(values) < 0:
            raise ValueError("Conflict reward quantities must not be negative")
        if (self.faction_influence > 0) != (self.influence_faction is not None):
            raise ValueError("fixed Influence requires both a faction and amount")
        optional_costs = (
            self.optional_spice_cost,
            self.optional_solari_cost,
            self.optional_recall_spies,
        )
        if sum(cost > 0 for cost in optional_costs) > 1:
            raise ValueError("an optional Conflict reward requires one cost type")
        if any(optional_costs) != (self.optional_victory_points > 0):
            raise ValueError("optional Conflict rewards require a cost and reward")
        if self.control_space_id == "":
            raise ValueError("control space ID must not be empty")
        if max(values) == 0 and self.control_space_id is None:
            raise ValueError("a Conflict reward row must contain a reward")


@dataclass(frozen=True, slots=True)
class ConflictDefinition:
    """Conflict identity, battle icon, and optional transcribed reward rows."""

    card: CardDefinition
    tier: ConflictTier
    battle_icon: BattleIcon | None = None
    shield_wall_protected: bool = False
    rewards: tuple[ConflictReward, ConflictReward, ConflictReward] | None = None


MAIN_P3_P4: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3, 4)),)


def _conflict(
    card_id: int,
    content_id: str,
    name: str,
    tier: ConflictTier,
    *,
    battle_icon: BattleIcon | None = None,
    shield_wall_protected: bool = False,
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
        shield_wall_protected=shield_wall_protected,
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
    _conflict(
        454,
        "choam_security",
        "CHOAM Security",
        ConflictTier.TWO,
        battle_icon=BattleIcon.CRYSKNIFE,
        rewards=(
            ConflictReward(
                troops=1,
                contracts=1,
                faction_influence=1,
                influence_faction=Faction.SPACING_GUILD,
            ),
            ConflictReward(solari=2, water=1, troops=2),
            ConflictReward(intrigue=1, troops=1),
        ),
    ),
    _conflict(
        455,
        "spice_freighters",
        "Spice Freighters",
        ConflictTier.TWO,
        battle_icon=BattleIcon.CRYSKNIFE,
        rewards=(
            ConflictReward(
                choose_influence=1,
                optional_spice_cost=3,
                optional_victory_points=1,
            ),
            ConflictReward(spice=1, water=1, troops=1),
            ConflictReward(spice=1, troops=1),
        ),
    ),
    _conflict(
        456,
        "siege_of_arrakeen",
        "Siege of Arrakeen",
        ConflictTier.TWO,
        battle_icon=BattleIcon.ORNITHOPTER,
        shield_wall_protected=True,
        rewards=(
            ConflictReward(
                solari=2,
                troops=2,
                control_space_id="arrakeen",
            ),
            ConflictReward(solari=4, troops=1),
            ConflictReward(solari=3),
        ),
    ),
    _conflict(
        457,
        "seize_spice_refinery",
        "Seize Spice Refinery",
        ConflictTier.TWO,
        battle_icon=BattleIcon.CRYSKNIFE,
        shield_wall_protected=True,
        rewards=(
            ConflictReward(
                spice=2,
                place_spies=1,
                control_space_id="spice_refinery",
            ),
            ConflictReward(spice=1, intrigue=1, troops=1),
            ConflictReward(spice=2),
        ),
    ),
    _conflict(
        458,
        "test_of_loyalty",
        "Test of Loyalty",
        ConflictTier.TWO,
        battle_icon=BattleIcon.ORNITHOPTER,
        rewards=(
            ConflictReward(
                solari=2,
                place_spies=1,
                faction_influence=1,
                influence_faction=Faction.EMPEROR,
            ),
            ConflictReward(solari=4, troops=1),
            ConflictReward(solari=3),
        ),
    ),
    _conflict(
        459,
        "shadow_contest",
        "Shadow Contest",
        ConflictTier.TWO,
        battle_icon=BattleIcon.ORNITHOPTER,
        rewards=(
            ConflictReward(
                intrigue=1,
                faction_influence=1,
                influence_faction=Faction.BENE_GESSERIT,
            ),
            ConflictReward(spice=1, intrigue=1, troops=1),
            ConflictReward(spice=1, troops=1),
        ),
    ),
    _conflict(
        460,
        "secure_imperial_basin",
        "Secure Imperial Basin",
        ConflictTier.TWO,
        battle_icon=BattleIcon.DESERT_MOUSE,
        shield_wall_protected=True,
        rewards=(
            ConflictReward(
                spice=2,
                troops=1,
                control_space_id="imperial_basin",
            ),
            ConflictReward(water=2, troops=1),
            ConflictReward(water=1, troops=1),
        ),
    ),
    _conflict(
        461,
        "protect_the_sietches",
        "Protect the Sietches",
        ConflictTier.TWO,
        battle_icon=BattleIcon.DESERT_MOUSE,
        rewards=(
            ConflictReward(
                water=1,
                troops=1,
                faction_influence=1,
                influence_faction=Faction.FREMEN,
            ),
            ConflictReward(spice=3, troops=1),
            ConflictReward(spice=2),
        ),
    ),
    _conflict(
        462,
        "trade_dispute",
        "Trade Dispute",
        ConflictTier.TWO,
        battle_icon=BattleIcon.DESERT_MOUSE,
        rewards=(
            ConflictReward(water=1, contracts=1, trash_cards=1),
            ConflictReward(spice=1, water=1, trash_cards=1),
            ConflictReward(water=1, troops=1),
        ),
    ),
    _conflict(
        463,
        "propaganda",
        "Propaganda",
        ConflictTier.THREE,
        battle_icon=BattleIcon.WILD,
        rewards=(
            ConflictReward(choose_distinct_influence=2),
            ConflictReward(spice=3, intrigue=1),
            ConflictReward(spice=3),
        ),
    ),
    _conflict(
        464,
        "battle_for_imperial_basin",
        "Battle for Imperial Basin",
        ConflictTier.THREE,
        battle_icon=BattleIcon.ORNITHOPTER,
        shield_wall_protected=True,
        rewards=(
            ConflictReward(
                victory_points=1,
                control_space_id="imperial_basin",
                optional_spice_cost=4,
                optional_victory_points=1,
            ),
            ConflictReward(spice=5),
            ConflictReward(spice=3),
        ),
    ),
    _conflict(
        465,
        "battle_for_arrakeen",
        "Battle for Arrakeen",
        ConflictTier.THREE,
        battle_icon=BattleIcon.CRYSKNIFE,
        shield_wall_protected=True,
        rewards=(
            ConflictReward(
                victory_points=1,
                control_space_id="arrakeen",
                optional_recall_spies=2,
                optional_victory_points=1,
            ),
            ConflictReward(solari=3, spice=1, intrigue=1),
            ConflictReward(solari=2, spice=2),
        ),
    ),
    _conflict(
        466,
        "battle_for_spice_refinery",
        "Battle for Spice Refinery",
        ConflictTier.THREE,
        battle_icon=BattleIcon.DESERT_MOUSE,
        shield_wall_protected=True,
        rewards=(
            ConflictReward(
                victory_points=1,
                control_space_id="spice_refinery",
                optional_solari_cost=6,
                optional_victory_points=1,
            ),
            ConflictReward(spice=3, intrigue=1),
            ConflictReward(spice=3),
        ),
    ),
)


def conflicts_by_tier(tier: ConflictTier) -> tuple[ConflictDefinition, ...]:
    """Return all physical Conflict cards with the requested back."""

    return tuple(conflict for conflict in CONFLICTS if conflict.tier is tier)


CONFLICTS_BY_ID: Final = {
    conflict.card.card_id: conflict for conflict in CONFLICTS
}
