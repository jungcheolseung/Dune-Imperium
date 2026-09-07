"""The Tech Module's Ixian Embassy and its 18 Tech tiles [Bloodlines pp. 6-7].

The module rules live in ``docs/rules/bloodlines.md`` section 5; every tile
face is transcribed from the asset repository (``cards/en/bloodlines/tech/``)
and cited as ``[<name> Tech tile]``. A tile has a spice cost, an optional
acquire effect that pays once when the tile is acquired, and an ability
[Bloodlines p. 7]. The Rival marker only matters in solo play.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from dune_imperium.content.schema import SourceDocument, SourceRef

# "Divide them into three stacks of 6 tiles" [Bloodlines p. 6].
TECH_STACKS: Final = 3
# "If you have a High Council seat, each Tech tile costs you 1 less spice"
# [Bloodlines p. 7] [Ixian Embassy board].
HIGH_COUNCIL_TECH_DISCOUNT: Final = 1
# The Tech Discount icon: "a single Tech tile at a discount of 1 spice"
# [Bloodlines pp. 7, 12].
TECH_DISCOUNT_ICON: Final = 1


class TechAbility(StrEnum):
    """The printed ability of one Tech tile (resolved in ``rules.tech``)."""

    # Flip: draw an Intrigue card.
    FLIP_DRAW_INTRIGUE = "flip_draw_intrigue"
    # When you complete a contract: draw a card. Endgame: 1 VP with four or
    # more completed contracts.
    CONTRACT_COMPLETION_DRAW = "contract_completion_draw"
    # Reveal Turn: Command (6+): 2 Solari.
    COMMAND_TWO_SOLARI = "command_two_solari"
    # Reveal Turn: you must choose 3 swords and lose one Influence, or lose
    # all your spice and trash the tile.
    FORBIDDEN_WEAPONS = "forbidden_weapons"
    # Your Intrigue cards can't be stolen unless you have five or more.
    INTRIGUE_STEAL_PROTECTION = "intrigue_steal_protection"
    # You may look at the top card of your deck at any time.
    PEEK_TOP_CARD = "peek_top_card"
    # Board spaces cost you 1 spice or 1 Solari less.
    SPACE_DISCOUNT = "space_discount"
    # All of your battle icons are Ornithopter.
    ORNITHOPTER_ICONS = "ornithopter_icons"
    # Reveal Turn: a Spy and a troop. Endgame: 1 Influence with each Faction
    # where you have 1 or less.
    PANOPTICON = "panopticon"
    # When you win a Conflict: draw a card.
    CONFLICT_WIN_DRAW = "conflict_win_draw"
    # Whenever you recruit a Sardaukar Commander: trash this -> gain an
    # additional Skill.
    PLASTEEL_BLADES = "plasteel_blades"
    # Agent Turn: Flip -> the Combat icon.
    FLIP_COMBAT_ICON = "flip_combat_icon"
    # Recruiting a Sardaukar Commander (acquiring included) costs 1 less.
    COMMANDER_DISCOUNT = "commander_discount"
    # Reveal Turn: 1 Persuasion.
    REVEAL_PERSUASION = "reveal_persuasion"
    # Your Signet Ring has the four Faction Agent icons.
    SIGNET_FACTION_ICONS = "signet_faction_icons"
    # Flip -> 1 Solari, and if you recalled a Spy this turn: trash a card.
    FLIP_SOLARI_AND_TRASH = "flip_solari_and_trash"
    # For each Intrigue card you draw or steal during your turn: a troop,
    # deployed to the Conflict.
    INTRIGUE_DRAW_TROOP = "intrigue_draw_troop"
    # Reveal Turn: Command (6+): 2 swords.
    COMMAND_TWO_STRENGTH = "command_two_strength"


FLIP_ABILITIES: Final = frozenset(
    {
        TechAbility.FLIP_DRAW_INTRIGUE,
        TechAbility.FLIP_COMBAT_ICON,
        TechAbility.FLIP_SOLARI_AND_TRASH,
    }
)


@dataclass(frozen=True, slots=True)
class TechTile:
    """One Tech tile: cost, acquire effect and ability, as printed."""

    tech_id: str
    name: str
    cost: int
    ability: TechAbility
    # "If you are playing without the CHOAM Module, exclude CHOAM
    # Transports" [Bloodlines p. 6].
    choam_only: bool = False
    # A Rival may acquire the tile in a solo game (marker only).
    rival: bool = False
    # Acquire effects, paid once when the tile is acquired [Bloodlines p. 7].
    acquire_solari: int = 0
    acquire_troops: int = 0
    acquire_intrigue: int = 0
    acquire_cards: int = 0
    acquire_victory_points: int = 0
    acquire_contracts: int = 0
    # "Gain one Influence of your choice".
    acquire_influence_choice: bool = False
    # Gene-Locked Vault: an Intrigue card OR a drawn card.
    acquire_intrigue_or_card: bool = False
    # The Shield Wall detonation icon: the owner may destroy the wall.
    acquire_may_destroy_shield_wall: bool = False
    # The trash icon: the owner may trash a card.
    acquire_may_trash_card: bool = False
    # Spy Drones: two Spies with Deep Cover.
    acquire_deep_cover_spies: int = 0
    # Advanced Data Analysis: "To acquire this, you must trash one of your
    # Spies from the board (return it to the box)".
    acquire_requires_spy_trash: bool = False
    sources: tuple[SourceRef, ...] = (
        SourceRef(SourceDocument.BLOODLINES_RULEBOOK, (7,)),
        SourceRef(SourceDocument.CARD_FACE, (1,)),
    )

    def __post_init__(self) -> None:
        if not self.tech_id or not self.name:
            raise ValueError("Tech tiles require stable IDs and names")
        if self.cost < 0:
            raise ValueError("Tech tile cost must not be negative")
        if (
            min(
                self.acquire_solari,
                self.acquire_troops,
                self.acquire_intrigue,
                self.acquire_cards,
                self.acquire_victory_points,
                self.acquire_contracts,
                self.acquire_deep_cover_spies,
            )
            < 0
        ):
            raise ValueError("Tech tile acquire effects must not be negative")

    @property
    def flips(self) -> bool:
        """Return whether the ability is used by flipping the tile."""

        return self.ability in FLIP_ABILITIES


TECH_TILES: Final[tuple[TechTile, ...]] = (
    TechTile(
        "advanced_data_analysis",
        "Advanced Data Analysis",
        3,
        TechAbility.FLIP_DRAW_INTRIGUE,
        acquire_requires_spy_trash=True,
    ),
    TechTile(
        "choam_transports",
        "CHOAM Transports",
        6,
        TechAbility.CONTRACT_COMPLETION_DRAW,
        choam_only=True,
        acquire_contracts=1,
    ),
    TechTile(
        "delivery_bay",
        "Delivery Bay",
        3,
        TechAbility.COMMAND_TWO_SOLARI,
        rival=True,
        acquire_cards=1,
    ),
    TechTile(
        "forbidden_weapons",
        "Forbidden Weapons",
        2,
        TechAbility.FORBIDDEN_WEAPONS,
        acquire_may_destroy_shield_wall=True,
        acquire_troops=1,
    ),
    TechTile(
        "gene_locked_vault",
        "Gene-Locked Vault",
        2,
        TechAbility.INTRIGUE_STEAL_PROTECTION,
        rival=True,
        acquire_intrigue_or_card=True,
    ),
    TechTile(
        "glowglobes",
        "Glowglobes",
        2,
        TechAbility.PEEK_TOP_CARD,
        rival=True,
        acquire_influence_choice=True,
    ),
    TechTile(
        "navigation_chamber",
        "Navigation Chamber",
        5,
        TechAbility.SPACE_DISCOUNT,
        acquire_influence_choice=True,
    ),
    TechTile(
        "ornithopter_fleet",
        "Ornithopter Fleet",
        4,
        TechAbility.ORNITHOPTER_ICONS,
        rival=True,
        acquire_troops=2,
    ),
    TechTile("panopticon", "Panopticon", 5, TechAbility.PANOPTICON, rival=True),
    TechTile(
        "planetary_array",
        "Planetary Array",
        2,
        TechAbility.CONFLICT_WIN_DRAW,
        acquire_may_trash_card=True,
    ),
    TechTile(
        "plasteel_blades",
        "Plasteel Blades",
        3,
        TechAbility.PLASTEEL_BLADES,
        acquire_solari=4,
    ),
    TechTile(
        "rapid_dropships",
        "Rapid Dropships",
        4,
        TechAbility.FLIP_COMBAT_ICON,
        rival=True,
        acquire_troops=2,
    ),
    TechTile(
        "sardaukar_high_command",
        "Sardaukar High Command",
        7,
        TechAbility.COMMANDER_DISCOUNT,
        rival=True,
        acquire_victory_points=1,
    ),
    TechTile(
        "self_destroying_messages",
        "Self-Destroying Messages",
        4,
        TechAbility.REVEAL_PERSUASION,
        rival=True,
        acquire_intrigue=2,
    ),
    TechTile(
        "servo_receivers",
        "Servo-Receivers",
        2,
        TechAbility.SIGNET_FACTION_ICONS,
        rival=True,
        acquire_may_destroy_shield_wall=True,
    ),
    TechTile(
        "spy_drones",
        "Spy Drones",
        5,
        TechAbility.FLIP_SOLARI_AND_TRASH,
        rival=True,
        acquire_deep_cover_spies=2,
    ),
    TechTile(
        "suspensor_suits",
        "Suspensor Suits",
        3,
        TechAbility.INTRIGUE_DRAW_TROOP,
    ),
    TechTile(
        "training_depot",
        "Training Depot",
        1,
        TechAbility.COMMAND_TWO_STRENGTH,
        rival=True,
    ),
)
TECH_TILES_BY_ID: Final = {tile.tech_id: tile for tile in TECH_TILES}
TECH_IDS: Final = tuple(tile.tech_id for tile in TECH_TILES)


def tech_tiles_for(choam_module: bool) -> tuple[TechTile, ...]:
    """Return the tiles shuffled into the three stacks for this setup.

    CHOAM Transports joins only when the CHOAM Module is in play
    [Bloodlines pp. 2, 6].
    """

    return tuple(tile for tile in TECH_TILES if choam_module or not tile.choam_only)


def has_tech(tech_ids: tuple[str, ...], ability: TechAbility) -> bool:
    """Return whether one of ``tech_ids`` prints ``ability``."""

    return any(TECH_TILES_BY_ID[tech_id].ability is ability for tech_id in tech_ids)
