"""Tech tile vocabulary shared by Bloodlines' Tech Module and Rise of Ix
(docs/content-core-refactor-plan.md 2.4): what a tile prints, and which
abilities Rise of Ix's rules flip, and the tile schema (``TechTile``) with the
check of its acquire record. Each set builds its tiles with their own records
(``acquire_record``, ``ability_records``), so no set reads another's tables
(stage 4 of the plan, 8.3; it had stayed in ``content.bloodlines.tech`` while
its properties read that set's tables, 7.5).
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from dune_imperium.content.core.abilities import (
    Ability,
    AbilityMark,
    AbilityStructure,
    AbilityTiming,
)
from dune_imperium.content.core.effects import (
    DestroyShieldWall,
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    PlaceSpy,
    RecruitTroops,
    Reward,
    TakeContract,
    TrashPersonalCard,
    UseSignetAbility,
)
from dune_imperium.content.core.schema import GameOption, SourceDocument, SourceRef


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


# Rise of Ix's four Flip tiles (docs/rules/rise-of-ix.md 4, "뒤집기" column):
# Flagship, Holoprojectors, Invasion Ships and Training Drones.
IX_FLIP_ABILITIES: Final = frozenset(
    {
        TechAbility.FLIP_SOLARI_FOR_TROOPS,
        TechAbility.FLIP_DISCARD_FOR_CARD,
        TechAbility.FLIP_DISCARD_IGNORE_BLOCKS,
        TechAbility.FLIP_TROOP,
    }
)


# Advanced Data Analysis' prerequisite (``rules.tech`` checks and pays it
# with the purchase).
TRASH_SPY_TO_ACQUIRE: Final = "trash_spy_to_acquire"


def acquire_icons(*rewards: Reward) -> Ability:
    """A tile's acquire icons, one line each."""

    return Ability(
        timing=AbilityTiming.ACQUIRE,
        sections=tuple(EffectSection(rewards=(reward,)) for reward in rewards),
        structure=(
            AbilityStructure.SEPARATE if len(rewards) > 1 else AbilityStructure.SEQUENCE
        ),
    )


@dataclass(frozen=True, slots=True)
class TechTile:
    """One Tech tile: cost and ability, as printed. Its acquire effect is
    its record (``acquire_record``, given by the tile's set: composed A6a),
    read through the
    ``acquire_*`` properties below (cleanup 2e)."""

    tech_id: str
    name: str
    cost: int
    ability: TechAbility
    # The options the tile needs on: "If you are playing without the CHOAM
    # Module, exclude CHOAM Transports" [Bloodlines p. 6].
    requires: frozenset[GameOption] = frozenset()
    # A Rival may acquire the tile in a solo game (marker only).
    rival: bool = False
    sources: tuple[SourceRef, ...] = (
        SourceRef(SourceDocument.BLOODLINES_RULEBOOK, (7,)),
        SourceRef(SourceDocument.CARD_FACE, (1,)),
    )
    # The tile's own records, given by the set that prints it (plan 8.3,
    # stage 4): its acquire effect and its printed ability's lines. They are
    # left out of repr and equality: a tile is its printed identity.
    acquire_record: Ability | None = field(default=None, repr=False, compare=False)
    ability_records: tuple[Ability, ...] = field(
        default=(), repr=False, compare=False
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

        record = self.acquire_record
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

        record = self.acquire_record
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

        record = self.acquire_record
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

        return self.ability in IX_FLIP_ABILITIES or any(
            record.timing is AbilityTiming.FLIP
            # A Rise of Ix tile has no ability record (``content.rise_of_ix.
            # tech``): its flips are the members of ``IX_FLIP_ABILITIES``.
            for record in self.ability_records
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


def check_acquire_record(tech_id: str, ability: Ability | None) -> None:
    """Check the tile's acquire record against what the ``acquire_*``
    properties read; raises ``ValueError`` for a record they cannot read."""

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
