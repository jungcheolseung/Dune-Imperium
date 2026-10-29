"""The Tech Module's Ixian Embassy and its 18 Tech tiles [Bloodlines pp. 6-7].

The module rules live in ``docs/rules/bloodlines.md`` section 5; every tile
face is transcribed from the asset repository (``cards/en/bloodlines/tech/``)
and cited as ``[<name> Tech tile]``. A tile has a spice cost, an optional
acquire effect that pays once when the tile is acquired, and an ability
[Bloodlines p. 7]. The Rival marker only matters in solo play. The acquire
effects are ability records (``tech_abilities.py``, composed A6a) compiled
into the ``acquire_*`` fields below.

Rise of Ix's 18 tiles (stage P4a) are ``TechTile`` entries too
(``content.rise_of_ix.tech``): ``TECH_TILES_BY_ID`` resolves them, while
``TECH_TILES`` and ``TECH_IDS`` stay the Tech Module's.
"""

from dataclasses import dataclass
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
    Reward,
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

    # Rise of Ix's tiles (stage P4a, ``content.rise_of_ix.tech``; the
    # abilities as docs/rules/rise-of-ix.md 4 sums them up). One member per
    # tile; nothing resolves them before stage P4c, and ``has_tech`` finds
    # them only on a seat holding the tile, which no setup deals yet.
    # Artillery -- Reveal Turn: a sword for each revealed card giving swords.
    REVEAL_SWORD_PER_SWORD_CARD = "reveal_sword_per_sword_card"
    # Chaumurky -- Endgame: you win ties [FAQ p. 1].
    ENDGAME_TIE_WIN = "endgame_tie_win"
    # Detonation Devices -- winning with a dreadnought, you may return it to
    # the supply for 1 VP instead of controlling a space (OQ-121).
    DREADNOUGHT_DETONATION = "dreadnought_detonation"
    # Disposal Facility -- Reveal Turn: with 6+ Persuasion gained this turn,
    # you may trash a card in play (OQ-126).
    REVEAL_TRASH_AT_SIX_PERSUASION = "reveal_trash_at_six_persuasion"
    # Flagship -- Flip: 4 Solari -> 3 troops.
    FLIP_SOLARI_FOR_TROOPS = "flip_solari_for_troops"
    # Holoprojectors -- Flip: discard a card -> draw a card.
    FLIP_DISCARD_FOR_CARD = "flip_discard_for_card"
    # Holtzman Engine -- Round Start: draw a card. Endgame: 1 VP with two or
    # more The Spice Must Flow (OQ-123).
    HOLTZMAN_ENGINE = "holtzman_engine"
    # Invasion Ships -- Flip: discard a card -> enemy Agents do not block
    # yours this turn.
    FLIP_DISCARD_IGNORE_BLOCKS = "flip_discard_ignore_blocks"
    # Memocorders -- Endgame: 1 VP with 3+ Influence on all four tracks.
    ENDGAME_INFLUENCE_THREE_VP = "endgame_influence_three_vp"
    # Minimic Film -- Reveal Turn: 1 Persuasion (the line Self-Destroying
    # Messages' REVEAL_PERSUASION prints; a member of its own, one per tile).
    MINIMIC_FILM = "minimic_film"
    # Restricted Ordnance -- Reveal Turn: 4 swords with a High Council seat.
    REVEAL_HIGH_COUNCIL_SWORDS = "reveal_high_council_swords"
    # Shuttle Fleet -- Round Start: 2 Solari (OQ-122).
    ROUND_START_TWO_SOLARI = "round_start_two_solari"
    # Sonic Snoopers -- trash this -> put any number of Intrigue cards on
    # the Intrigue deck's bottom, then draw as many [Rise of Ix p. 10].
    TRASH_CYCLE_INTRIGUE = "trash_cycle_intrigue"
    # Spaceport -- you may put the cards you acquire on top of your deck.
    ACQUIRED_CARDS_ON_DECK = "acquired_cards_on_deck"
    # Spy Satellites -- 3 spice and trash this -> 1 VP. Endgame: 1 VP for
    # each Faction where you have 1 or less Influence.
    SPY_SATELLITES = "spy_satellites"
    # Training Drones -- Flip: a troop.
    FLIP_TROOP = "flip_troop"
    # Troop Transports -- one more troop whenever you recruit from the
    # Shipping track; any of them may deploy to the Conflict.
    SHIPPING_EXTRA_TROOP = "shipping_extra_troop"
    # Windtraps -- when you win a Conflict: 1 water.
    CONFLICT_WIN_WATER = "conflict_win_water"


@dataclass(frozen=True, slots=True)
class TechTile:
    """One Tech tile: cost and ability, as printed. Its acquire effect is
    its record (``TECH_ACQUIRE_ABILITIES``, composed A6a), read through the
    ``acquire_*`` properties below (cleanup 2e)."""

    tech_id: str
    name: str
    cost: int
    ability: TechAbility
    # "If you are playing without the CHOAM Module, exclude CHOAM
    # Transports" [Bloodlines p. 6].
    choam_only: bool = False
    # A Rival may acquire the tile in a solo game (marker only).
    rival: bool = False
    sources: tuple[SourceRef, ...] = (
        SourceRef(SourceDocument.BLOODLINES_RULEBOOK, (7,)),
        SourceRef(SourceDocument.CARD_FACE, (1,)),
    )

    def __post_init__(self) -> None:
        if not self.tech_id or not self.name:
            raise ValueError("Tech tiles require stable IDs and names")
        if self.cost < 0:
            raise ValueError("Tech tile cost must not be negative")

    def _acquire_icons(self) -> tuple[Reward, ...]:
        """The acquire record's icons, one reward per line, paid once when
        the tile is acquired [Bloodlines p. 7]; none for a choice or the
        Spy-trash prerequisite (checked on load, ``_acquire``)."""

        record = TECH_ACQUIRE_ABILITIES.get(self.tech_id)
        if (
            record is None
            or record.hook is not None
            or record.structure is AbilityStructure.ONE_OF
        ):
            return ()
        return tuple(line.rewards[0] for line in record.sections)

    @property
    def acquire_solari(self) -> int:
        return sum(
            icon.solari
            for icon in self._acquire_icons()
            if isinstance(icon, GainResources)
        )

    @property
    def acquire_troops(self) -> int:
        return sum(
            icon.count
            for icon in self._acquire_icons()
            if isinstance(icon, RecruitTroops)
        )

    @property
    def acquire_intrigue(self) -> int:
        return sum(
            icon.count
            for icon in self._acquire_icons()
            if isinstance(icon, DrawIntrigueCards)
        )

    @property
    def acquire_cards(self) -> int:
        return sum(
            icon.count
            for icon in self._acquire_icons()
            if isinstance(icon, DrawPersonalCards)
        )

    @property
    def acquire_victory_points(self) -> int:
        return sum(
            icon.amount
            for icon in self._acquire_icons()
            if isinstance(icon, GainVictoryPoints)
        )

    @property
    def acquire_contracts(self) -> int:
        return sum(
            icon.count
            for icon in self._acquire_icons()
            if isinstance(icon, TakeContract)
        )

    @property
    def acquire_influence_choice(self) -> bool:
        """"Gain one Influence of your choice"."""

        return any(
            isinstance(icon, GainInfluence) and not icon.distinct
            for icon in self._acquire_icons()
        )

    @property
    def acquire_distinct_influence(self) -> bool:
        """Shuttle Fleet's "Choose two:" Influence icons: two different
        Factions, both named before either is paid (OQ-114)."""

        return any(
            isinstance(icon, GainInfluence) and icon.distinct
            for icon in self._acquire_icons()
        )

    @property
    def acquire_water(self) -> int:
        """Windtraps' water: "water 1" on acquiring it [Rise of Ix p. 4]."""

        return sum(
            icon.water
            for icon in self._acquire_icons()
            if isinstance(icon, GainResources)
        )

    @property
    def acquire_intrigue_or_card(self) -> bool:
        """Gene-Locked Vault: an Intrigue card OR a drawn card."""

        record = TECH_ACQUIRE_ABILITIES.get(self.tech_id)
        return record is not None and record.structure is AbilityStructure.ONE_OF

    @property
    def acquire_may_destroy_shield_wall(self) -> bool:
        """The Shield Wall detonation icon: the owner may destroy the wall."""

        return any(
            isinstance(icon, DestroyShieldWall) for icon in self._acquire_icons()
        )

    @property
    def acquire_leader_signet(self) -> bool:
        """The Signet Ring icon: "you use the Signet Ring ability (with the
        corresponding icon) on your Leader" [Main p. 20] (Servo-Receivers)."""

        return any(
            isinstance(icon, UseSignetAbility) for icon in self._acquire_icons()
        )

    @property
    def acquire_may_trash_card(self) -> bool:
        """The trash icon: the owner may trash a card."""

        return any(
            isinstance(icon, TrashPersonalCard) for icon in self._acquire_icons()
        )

    @property
    def acquire_deep_cover_spies(self) -> int:
        """Spy Drones: two Spies with Deep Cover."""

        return sum(isinstance(icon, PlaceSpy) for icon in self._acquire_icons())

    @property
    def acquire_requires_spy_trash(self) -> bool:
        """Advanced Data Analysis: "To acquire this, you must trash one of
        your Spies from the board (return it to the box)"."""

        record = TECH_ACQUIRE_ABILITIES.get(self.tech_id)
        return record is not None and record.hook == TRASH_SPY_TO_ACQUIRE

    @property
    def acquire_effect_keys(self) -> tuple[str, ...]:
        """The independent acquire icons queued after purchase (OQ-098).

        Advanced Data Analysis's Spy trash is a purchase prerequisite,
        rather than a reward to defer [Advanced Data Analysis Tech tile].

        Raises ``NotImplementedError`` for an icon no key below pays: none
        since stage P4c-2a (Windtraps' water is the ``water`` key, Shuttle
        Fleet's two distinct Factions, OQ-114, the ``distinct_influence``
        key); a key that dropped an icon would pay less than the tile prints.
        """

        unpaid = [icon for icon in self._acquire_icons() if not _paid_icon(icon)]
        if unpaid:
            raise NotImplementedError(
                f"{self.tech_id}: no acquire key pays {unpaid!r} until stage P4c"
            )
        counted_icons = (
            "solari",
            "water",
            "troops",
            "intrigue",
            "cards",
            "victory_points",
            "contracts",
        )
        return (
            *(key for key in counted_icons if getattr(self, f"acquire_{key}")),
            *(("influence",) if self.acquire_influence_choice else ()),
            *(("distinct_influence",) if self.acquire_distinct_influence else ()),
            *(("intrigue_or_card",) if self.acquire_intrigue_or_card else ()),
            *(("shield_wall",) if self.acquire_may_destroy_shield_wall else ()),
            *(("signet",) if self.acquire_leader_signet else ()),
            *(("trash",) if self.acquire_may_trash_card else ()),
            *(f"spy_{index}" for index in range(self.acquire_deep_cover_spies)),
        )

    @property
    def flips(self) -> bool:
        """Return whether the ability is used by flipping the tile: the
        tile's record has a Flip line [Bloodlines p. 7] (composed A6b)."""

        return any(
            record.timing is AbilityTiming.FLIP
            for record in TECH_ABILITIES[self.tech_id]
        )


_INTRIGUE_OR_CARD: Final = (
    EffectSection(rewards=(DrawIntrigueCards(1),)),
    EffectSection(rewards=(DrawPersonalCards(1),)),
)


def _paid_icon(icon: Reward) -> bool:
    """Whether a key of ``TechTile.acquire_effect_keys`` pays this acquire
    icon (``rules.tech``): the pieces the ``acquire_*`` properties read."""

    match icon:
        # Solari (the Tech Module's) or water (Windtraps): "water 1"
        # [Rise of Ix p. 4]; no tile prints spice.
        case GainResources(spice=0):
            return True
        case (
            RecruitTroops()
            | DrawIntrigueCards()
            | DrawPersonalCards()
            | GainVictoryPoints()
            | TakeContract()
            | DestroyShieldWall()
            | UseSignetAbility()
        ):
            return True
        case GainInfluence():
            return icon in (GainInfluence(), GainInfluence(times=2, distinct=True))
        case TrashPersonalCard():
            return icon == TrashPersonalCard()
        case PlaceSpy():
            return icon == PlaceSpy(shared_post=True)
    return False


def _acquire(tech_id: str) -> None:
    """Check a Tech Module tile's acquire record (``check_acquire_record``)."""

    check_acquire_record(tech_id)


def check_acquire_record(tech_id: str) -> None:
    """Check the tile's acquire record against what the ``acquire_*``
    properties read; raises ``ValueError`` for a record they cannot read."""

    ability = TECH_ACQUIRE_ABILITIES.get(tech_id)
    if ability is None:
        return
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
        return
    if ability.structure is AbilityStructure.ONE_OF:
        if ability.sections != _INTRIGUE_OR_CARD:
            raise ValueError(f"{tech_id}: no acquire icon holds this choice")
        return
    printed: set[type] = set()
    for line in ability.sections:
        if line.condition is not None or line.costs or len(line.rewards) != 1:
            raise ValueError(f"{tech_id}: an acquire icon is one free reward")
        icon = line.rewards[0]
        if not _paid_icon(icon):
            raise ValueError(f"{tech_id}: no acquire icon holds {icon!r}")
        if isinstance(icon, PlaceSpy):
            # Spy Drones prints two Spies with Deep Cover.
            continue
        if type(icon) in printed:
            raise ValueError(f"{tech_id}: acquire {type(icon).__name__} printed twice")
        printed.add(type(icon))


def _tile(
    tech_id: str,
    name: str,
    cost: int,
    ability: TechAbility,
    *,
    choam_only: bool = False,
    rival: bool = False,
) -> TechTile:
    """One tile, its acquire record checked."""

    _acquire(tech_id)
    return TechTile(tech_id, name, cost, ability, choam_only=choam_only, rival=rival)


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
TECH_IDS: Final = tuple(tile.tech_id for tile in TECH_TILES)
if set(TECH_ABILITIES) != set(TECH_IDS):
    raise ValueError("every Tech tile prints one ability record set")


def tech_reveal_line(tech_id: str) -> EffectSection | None:
    """The tile's automatic "Reveal Turn:" line -- the line of its REVEAL
    record without a hook (composed A6b) -- or None; ``command`` lines open
    on "Command (6+):" [Bloodlines p. 5]."""

    records = tuple(
        record
        for record in TECH_ABILITIES[tech_id]
        if record.timing is AbilityTiming.REVEAL and record.hook is None
    )
    if not records:
        return None
    (record,) = records
    (line,) = record.sections
    return line


def _check_reveal_lines() -> None:
    """Every automatic Reveal Turn line is one the Reveal can pay; raises
    ``ValueError`` on load otherwise."""

    for tile in TECH_TILES:
        for record in TECH_ABILITIES[tile.tech_id]:
            if record.timing is not AbilityTiming.REVEAL or record.hook is not None:
                continue
            if (
                record.mark is not AbilityMark.AUTOMATIC
                or record.requirement is not None
                or len(record.sections) != 1
            ):
                raise ValueError(f"{tile.tech_id}: not an automatic Reveal line")
        line = tech_reveal_line(tile.tech_id)
        if line is None:
            continue
        command = line.condition == CommandReached()
        if (line.condition is not None and not command) or line.costs:
            raise ValueError(f"{tile.tech_id}: the Reveal checks no such condition")
        match line.rewards:
            # Command opens on the other Persuasion and adds none itself.
            case (RevealPersuasion(per=None),) if not command:
                pass
            case (GainResources(spice=0, water=0),) if command:
                pass
            case (RevealSwords(per=None),) if command:
                pass
            case _:
                raise ValueError(f"{tile.tech_id}: the Reveal pays no such line")


_check_reveal_lines()


def tech_tiles_for(choam_module: bool) -> tuple[TechTile, ...]:
    """Return the tiles shuffled into the three stacks for this setup.

    CHOAM Transports joins only when the CHOAM Module is in play
    [Bloodlines pp. 2, 6].
    """

    return tuple(tile for tile in TECH_TILES if choam_module or not tile.choam_only)


def has_tech(tech_ids: tuple[str, ...], ability: TechAbility) -> bool:
    """Return whether one of ``tech_ids`` prints ``ability``."""

    return any(TECH_TILES_BY_ID[tech_id].ability is ability for tech_id in tech_ids)


# One lookup by id for the Tech Module's tiles and Rise of Ix's (stage P4a,
# docs/base-game-and-ix-plan.md 17.1), as ``BOARD_SPACES_BY_ID`` is for the
# boards: code that lists the Tech Module's own tiles (its stacks, setup,
# codec, catalog and texts) iterates ``TECH_TILES`` and ``TECH_IDS``. Imported
# last, as Rise of Ix's tiles are built from ``TechTile``.
from dune_imperium.content.rise_of_ix.tech import IX_TECH_TILES  # noqa: E402

TECH_TILES_BY_ID: Final = {
    tile.tech_id: tile for tile in (*TECH_TILES, *IX_TECH_TILES)
}
