"""The Tech Module's Ixian Embassy and its 18 Tech tiles [Bloodlines pp. 6-7].

The module rules live in ``docs/rules/bloodlines.md`` section 5; every tile
face is transcribed from the asset repository (``cards/en/bloodlines/tech/``)
and cited as ``[<name> Tech tile]``. A tile has a spice cost, an optional
acquire effect that pays once when the tile is acquired, and an ability
[Bloodlines p. 7]. The Rival marker only matters in solo play. The acquire
effects are ability records (``tech_abilities.py``, composed A6a) compiled
into the ``acquire_*`` fields below.
"""

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final

from dune_imperium.content.bloodlines.tech_abilities import (
    TECH_ABILITIES,
    TECH_ACQUIRE_ABILITIES,
    TRASH_SPY_TO_ACQUIRE,
)
from dune_imperium.content.schema import SourceDocument, SourceRef
from dune_imperium.content.uprising.abilities import (
    AbilityMark,
    AbilityStructure,
    AbilityTiming,
)
from dune_imperium.content.uprising.effect_dsl import (
    CommandReached,
    DestroyShieldWall,
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    PlaceSpy,
    RecruitTroops,
    RevealPersuasion,
    RevealSwords,
    TakeContract,
    TrashPersonalCard,
    UseSignetAbility,
)

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
    # The Signet Ring icon: "you use the Signet Ring ability (with the
    # corresponding icon) on your Leader" [Main p. 20] (Servo-Receivers).
    acquire_leader_signet: bool = False
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
    def acquire_effect_keys(self) -> tuple[str, ...]:
        """The independent acquire icons queued after purchase (OQ-098).

        Advanced Data Analysis's Spy trash is a purchase prerequisite,
        rather than a reward to defer [Advanced Data Analysis Tech tile].
        """

        counted_icons = (
            "solari", "troops", "intrigue", "cards", "victory_points", "contracts"
        )
        return (
            *(key for key in counted_icons if getattr(self, f"acquire_{key}")),
            *(("influence",) if self.acquire_influence_choice else ()),
            *(("intrigue_or_card",) if self.acquire_intrigue_or_card else ()),
            *(("shield_wall",) if self.acquire_may_destroy_shield_wall else ()),
            *(("signet",) if self.acquire_leader_signet else ()),
            *(("trash",) if self.acquire_may_trash_card else ()),
            *(f"spy_{index}" for index in range(self.acquire_deep_cover_spies)),
        )

    @property
    def flips(self) -> bool:
        """Return whether the ability is used by flipping the tile."""

        return self.ability in FLIP_ABILITIES


@dataclass(frozen=True, slots=True)
class _AcquireTerms:
    """A tile's acquire fields, compiled from its record (composed A6a)."""

    solari: int = 0
    troops: int = 0
    intrigue: int = 0
    cards: int = 0
    victory_points: int = 0
    contracts: int = 0
    influence_choice: bool = False
    intrigue_or_card: bool = False
    may_destroy_shield_wall: bool = False
    leader_signet: bool = False
    may_trash_card: bool = False
    deep_cover_spies: int = 0
    requires_spy_trash: bool = False


_INTRIGUE_OR_CARD: Final = (
    EffectSection(rewards=(DrawIntrigueCards(1),)),
    EffectSection(rewards=(DrawPersonalCards(1),)),
)


def _acquire(tech_id: str) -> _AcquireTerms:
    """The ``TechTile`` acquire fields its record says; raises ``ValueError``
    for a record those fields cannot hold."""

    ability = TECH_ACQUIRE_ABILITIES.get(tech_id)
    if ability is None:
        return _AcquireTerms()
    if (
        ability.timing is not AbilityTiming.ACQUIRE
        or ability.mark is not AbilityMark.MANDATORY
        or ability.requirement is not None
        or ability.trigger is not None
    ):
        raise ValueError(f"{tech_id}: not an acquire effect a tile prints")
    if ability.hook is not None:
        if ability.hook != TRASH_SPY_TO_ACQUIRE or ability.sections:
            raise ValueError(f"{tech_id}: unknown acquire hook {ability.hook!r}")
        return _AcquireTerms(requires_spy_trash=True)
    if ability.structure is AbilityStructure.ONE_OF:
        if ability.sections != _INTRIGUE_OR_CARD:
            raise ValueError(f"{tech_id}: no acquire field holds this choice")
        return _AcquireTerms(intrigue_or_card=True)
    terms = _AcquireTerms()

    def once(current: int | bool, name: str) -> None:
        if current:
            raise ValueError(f"{tech_id}: acquire {name} printed twice")

    for line in ability.sections:
        if line.condition is not None or line.costs or len(line.rewards) != 1:
            raise ValueError(f"{tech_id}: an acquire icon is one free reward")
        match line.rewards[0]:
            case GainResources(solari=solari, spice=0, water=0):
                once(terms.solari, "Solari")
                terms = replace(terms, solari=solari)
            case RecruitTroops(count=count):
                once(terms.troops, "troops")
                terms = replace(terms, troops=count)
            case DrawIntrigueCards(count=count):
                once(terms.intrigue, "Intrigue")
                terms = replace(terms, intrigue=count)
            case DrawPersonalCards(count=count):
                once(terms.cards, "cards")
                terms = replace(terms, cards=count)
            case GainVictoryPoints(amount=amount):
                once(terms.victory_points, "VP")
                terms = replace(terms, victory_points=amount)
            case TakeContract(count=count):
                once(terms.contracts, "Contracts")
                terms = replace(terms, contracts=count)
            case GainInfluence() as gain if gain == GainInfluence():
                once(terms.influence_choice, "Influence")
                terms = replace(terms, influence_choice=True)
            case DestroyShieldWall():
                once(terms.may_destroy_shield_wall, "Shield Wall")
                terms = replace(terms, may_destroy_shield_wall=True)
            case UseSignetAbility():
                once(terms.leader_signet, "Signet")
                terms = replace(terms, leader_signet=True)
            case TrashPersonalCard() as trash if trash == TrashPersonalCard():
                once(terms.may_trash_card, "trash")
                terms = replace(terms, may_trash_card=True)
            case PlaceSpy() as spy if spy == PlaceSpy(shared_post=True):
                terms = replace(terms, deep_cover_spies=terms.deep_cover_spies + 1)
            case other:
                raise ValueError(f"{tech_id}: no acquire field holds {other!r}")
    return terms


def _tile(
    tech_id: str,
    name: str,
    cost: int,
    ability: TechAbility,
    *,
    choam_only: bool = False,
    rival: bool = False,
) -> TechTile:
    """One tile, its acquire fields compiled from its record."""

    terms = _acquire(tech_id)
    return TechTile(
        tech_id,
        name,
        cost,
        ability,
        choam_only=choam_only,
        rival=rival,
        acquire_solari=terms.solari,
        acquire_troops=terms.troops,
        acquire_intrigue=terms.intrigue,
        acquire_cards=terms.cards,
        acquire_victory_points=terms.victory_points,
        acquire_contracts=terms.contracts,
        acquire_influence_choice=terms.influence_choice,
        acquire_intrigue_or_card=terms.intrigue_or_card,
        acquire_may_destroy_shield_wall=terms.may_destroy_shield_wall,
        acquire_leader_signet=terms.leader_signet,
        acquire_may_trash_card=terms.may_trash_card,
        acquire_deep_cover_spies=terms.deep_cover_spies,
        acquire_requires_spy_trash=terms.requires_spy_trash,
    )


TECH_TILES: Final[tuple[TechTile, ...]] = (
    _tile(
        "advanced_data_analysis",
        "Advanced Data Analysis",
        3,
        TechAbility.FLIP_DRAW_INTRIGUE,
    ),
    _tile(
        "choam_transports",
        "CHOAM Transports",
        6,
        TechAbility.CONTRACT_COMPLETION_DRAW,
        choam_only=True,
    ),
    _tile(
        "delivery_bay",
        "Delivery Bay",
        3,
        TechAbility.COMMAND_TWO_SOLARI,
        rival=True,
    ),
    _tile(
        "forbidden_weapons",
        "Forbidden Weapons",
        2,
        TechAbility.FORBIDDEN_WEAPONS,
    ),
    _tile(
        "gene_locked_vault",
        "Gene-Locked Vault",
        2,
        TechAbility.INTRIGUE_STEAL_PROTECTION,
        rival=True,
    ),
    _tile(
        "glowglobes",
        "Glowglobes",
        2,
        TechAbility.PEEK_TOP_CARD,
        rival=True,
    ),
    _tile(
        "navigation_chamber",
        "Navigation Chamber",
        5,
        TechAbility.SPACE_DISCOUNT,
    ),
    _tile(
        "ornithopter_fleet",
        "Ornithopter Fleet",
        4,
        TechAbility.ORNITHOPTER_ICONS,
        rival=True,
    ),
    _tile("panopticon", "Panopticon", 5, TechAbility.PANOPTICON, rival=True),
    _tile(
        "planetary_array",
        "Planetary Array",
        2,
        TechAbility.CONFLICT_WIN_DRAW,
    ),
    _tile(
        "plasteel_blades",
        "Plasteel Blades",
        3,
        TechAbility.PLASTEEL_BLADES,
    ),
    _tile(
        "rapid_dropships",
        "Rapid Dropships",
        4,
        TechAbility.FLIP_COMBAT_ICON,
        rival=True,
    ),
    _tile(
        "sardaukar_high_command",
        "Sardaukar High Command",
        7,
        TechAbility.COMMANDER_DISCOUNT,
        rival=True,
    ),
    _tile(
        "self_destroying_messages",
        "Self-Destroying Messages",
        4,
        TechAbility.REVEAL_PERSUASION,
        rival=True,
    ),
    # The acquire box prints the brown-gold Signet Ring icon, not Forbidden
    # Weapons' red-and-tan Shield Wall detonation [Servo-Receivers Tech tile].
    _tile(
        "servo_receivers",
        "Servo-Receivers",
        2,
        TechAbility.SIGNET_FACTION_ICONS,
        rival=True,
    ),
    _tile(
        "spy_drones",
        "Spy Drones",
        5,
        TechAbility.FLIP_SOLARI_AND_TRASH,
        rival=True,
    ),
    _tile(
        "suspensor_suits",
        "Suspensor Suits",
        3,
        TechAbility.INTRIGUE_DRAW_TROOP,
    ),
    _tile(
        "training_depot",
        "Training Depot",
        1,
        TechAbility.COMMAND_TWO_STRENGTH,
        rival=True,
    ),
)
TECH_TILES_BY_ID: Final = {tile.tech_id: tile for tile in TECH_TILES}
TECH_IDS: Final = tuple(tile.tech_id for tile in TECH_TILES)
if set(TECH_ABILITIES) != set(TECH_IDS):
    raise ValueError("every Tech tile prints one ability record set")
# The abilities used by flipping the tile [Bloodlines p. 7] (composed A6b).
FLIP_ABILITIES: Final = frozenset(
    tile.ability
    for tile in TECH_TILES
    if any(
        record.timing is AbilityTiming.FLIP for record in TECH_ABILITIES[tile.tech_id]
    )
)


@dataclass(frozen=True, slots=True)
class TechRevealGain:
    """A tile's automatic Reveal Turn line, compiled from its record
    (composed A6b): ``command`` for "Command (6+):" [Bloodlines p. 5]."""

    tech_id: str
    ability: TechAbility
    command: bool
    persuasion: int = 0
    solari: int = 0
    swords: int = 0


def _reveal_gain(tile: TechTile) -> TechRevealGain | None:
    """The tile's automatic Reveal Turn line; raises ``ValueError`` for a
    record the Reveal cannot pay."""

    records = tuple(
        record
        for record in TECH_ABILITIES[tile.tech_id]
        if record.timing is AbilityTiming.REVEAL and record.hook is None
    )
    if not records:
        return None
    (record,) = records
    if (
        record.mark is not AbilityMark.AUTOMATIC
        or record.requirement is not None
        or len(record.sections) != 1
    ):
        raise ValueError(f"{tile.tech_id}: not an automatic Reveal line")
    (line,) = record.sections
    command = line.condition == CommandReached()
    if (line.condition is not None and not command) or line.costs:
        raise ValueError(f"{tile.tech_id}: the Reveal checks no such condition")
    match line.rewards:
        case (RevealPersuasion(amount=amount, per=None),) if not command:
            # Command opens on the other Persuasion and adds none itself.
            return TechRevealGain(
                tile.tech_id, tile.ability, command, persuasion=amount
            )
        case (GainResources(solari=solari, spice=0, water=0),) if command:
            return TechRevealGain(tile.tech_id, tile.ability, command, solari=solari)
        case (RevealSwords(amount=amount, per=None),) if command:
            return TechRevealGain(tile.tech_id, tile.ability, command, swords=amount)
    raise ValueError(f"{tile.tech_id}: the Reveal pays no such line")


TECH_REVEAL_GAINS: Final = tuple(
    gain for tile in TECH_TILES if (gain := _reveal_gain(tile)) is not None
)
TECH_REVEAL_GAINS_BY_ID: Final = {gain.tech_id: gain for gain in TECH_REVEAL_GAINS}


def tech_tiles_for(choam_module: bool) -> tuple[TechTile, ...]:
    """Return the tiles shuffled into the three stacks for this setup.

    CHOAM Transports joins only when the CHOAM Module is in play
    [Bloodlines pp. 2, 6].
    """

    return tuple(tile for tile in TECH_TILES if choam_module or not tile.choam_only)


def has_tech(tech_ids: tuple[str, ...], ability: TechAbility) -> bool:
    """Return whether one of ``tech_ids`` prints ``ability``."""

    return any(TECH_TILES_BY_ID[tech_id].ability is ability for tech_id in tech_ids)
