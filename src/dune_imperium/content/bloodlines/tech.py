"""The Tech Module's Ixian Embassy and its 18 Tech tiles [Bloodlines pp. 6-7].

The module rules live in ``docs/rules/bloodlines.md`` section 5; every tile
face is transcribed from the asset repository (``cards/en/bloodlines/tech/``)
and cited as ``[<name> Tech tile]``. A tile has a spice cost, an optional
acquire effect that pays once when the tile is acquired, and an ability
[Bloodlines p. 7]. The Rival marker only matters in solo play. The acquire
effects are ability records (``tech_abilities.py``, composed A6a) each tile
carries and reads through ``TechTile``'s ``acquire_*`` properties
(``content.core.tech``).

Rise of Ix's 18 tiles (stage P4a) are ``TechTile`` entries too
(``content.rise_of_ix.tech``, with their records in
``content.rise_of_ix.tech_abilities``): ``TECH_TILES_BY_ID`` resolves them,
while ``TECH_TILES`` and ``TECH_IDS`` stay the Tech Module's.
"""

from typing import Final

from dune_imperium.content.bloodlines.tech_abilities import (
    TECH_ABILITIES,
    TECH_ACQUIRE_ABILITIES,
)
from dune_imperium.content.core.abilities import (
    AbilityMark,
    AbilityTiming,
)
from dune_imperium.content.core.effects import (
    CommandReached,
    EffectSection,
    GainResources,
    RevealPersuasion,
    RevealSwords,
)
from dune_imperium.content.core.schema import GameOption
from dune_imperium.content.core.tech import (
    TechAbility,
    TechTile,
    check_acquire_record,
)

# "Divide them into three stacks of 6 tiles" [Bloodlines p. 6].
TECH_STACKS: Final = 3
# "If you have a High Council seat, each Tech tile costs you 1 less spice"
# [Bloodlines p. 7] [Ixian Embassy board].
HIGH_COUNCIL_TECH_DISCOUNT: Final = 1
# The Tech Discount icon: "a single Tech tile at a discount of 1 spice"
# [Bloodlines pp. 7, 12].
TECH_DISCOUNT_ICON: Final = 1


def _acquire(tech_id: str) -> None:
    """Check a Tech Module tile's acquire record (``check_acquire_record``)."""

    check_acquire_record(tech_id, TECH_ACQUIRE_ABILITIES.get(tech_id))


def _tile(
    tech_id: str,
    name: str,
    cost: int,
    ability: TechAbility,
    *,
    requires: frozenset[GameOption] = frozenset(),
    rival: bool = False,
) -> TechTile:
    """One tile, its acquire record checked."""

    _acquire(tech_id)
    return TechTile(
        tech_id,
        name,
        cost,
        ability,
        requires=requires,
        rival=rival,
        acquire_record=TECH_ACQUIRE_ABILITIES.get(tech_id),
        ability_records=TECH_ABILITIES.get(tech_id, ()),
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
        requires=frozenset({GameOption.CHOAM_MODULE}),
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

    return tuple(
        tile
        for tile in TECH_TILES
        if choam_module or GameOption.CHOAM_MODULE not in tile.requires
    )


# "If you are playing with the original DUNE: IMPERIUM rather than UPRISING,
# exclude Advanced Data Analysis, Forbidden Weapons, Ornithopter Fleet,
# Panopticon, and Spy Drones." [Bloodlines p. 6] (docs/rules/bloodlines.md 5).
ORIGINAL_GAME_LEFT_OUT_TECH_IDS: Final = frozenset(
    {
        "advanced_data_analysis",
        "forbidden_weapons",
        "ornithopter_fleet",
        "panopticon",
        "spy_drones",
    }
)


# "Rise of Ix의 Tech 타일만 쓸 때(Ix의 다른 구성물 없이): Detonation Devices와
# Troop Transports를 빼고 나머지 16장을 Bloodlines 타일과 섞는다" [Bloodlines
# p. 7] (docs/rules/rise-of-ix.md 10a): the two need the Ix board (a
# dreadnought's win, the Shipping track). The Leaders-and-Tech mode leaves
# them out too (OQ-165, user 2026-11-01).
IX_TILES_LEFT_OUT_WITHOUT_IX_BOARD: Final = frozenset(
    {"detonation_devices", "troop_transports"}
)

