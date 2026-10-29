"""Rise of Ix's 18 Tech tiles (stage P4a; docs/rules/rise-of-ix.md 4).

docs/base-game-and-ix-plan.md 17.1 and 17.7: 18 tiles [Rise of Ix p. 2]
(docs/rules/rise-of-ix.md 2), acquired with the Acquire Tech icon from the
Ix board's three stacks [Rise of Ix p. 4]. Per D1 (plan 2.4) the names and
spice costs are the Steam app's attribute table
(``TechTileArchetypes.RiseOfIx.*``, the app title and ``SpiceCost``), equal
to docs/rules/rise-of-ix.md 4's table; ``tests/unit/content/
test_rise_of_ix_app_table.py`` reads the table on its own. The ids are the
snake case of the names (plan 17.2): none is a Tech Module tile's or any
other id.

These are stage P4a identity entries, built from the Tech Module's
``TechTile`` (``content.bloodlines.tech``):

- each tile names its ability with a ``TechAbility`` member of its own, and
  has no ability record (``TECH_ABILITIES``): its flips, Reveal and Endgame
  lines and hooks come in stage P4c, and nothing resolves the ability before;
- an acquire effect an existing piece prints is a record of
  ``TECH_ACQUIRE_ABILITIES`` (``content.bloodlines.tech_abilities``), checked
  here as the Tech Module's are. Windtraps' water and Shuttle Fleet's two
  different Factions (OQ-114) have keys of their own since stage P4c-2a
  (``water``, ``distinct_influence``; ``TechTile.acquire_effect_keys``);
- no stack, setup or deck holds them, and setup still refuses Rise of Ix.
  ``content.bloodlines.tech``'s ``TECH_TILES_BY_ID`` resolves them; code that
  lists the Tech Module's own tiles iterates ``TECH_TILES``. The observation
  lists them after the Tech Module's from v39 (``adapters.
  observation_encoding.TECH_IDS``, plan 17.8).

The solo Rival marker is not transcribed: one- and two-player rules are out
of scope (docs/rules/rise-of-ix.md 1), so ``rival`` stays False.
"""

from typing import Final

from dune_imperium.content.bloodlines.tech import (
    TechAbility,
    TechTile,
    check_acquire_record,
)
from dune_imperium.content.schema import SourceDocument, SourceRef

# The component table and the Tech tile rules [Rise of Ix pp. 2, 4]; the
# printed values are the app's (plan 2.4, D1).
IX_TECH_SOURCES: Final = (SourceRef(SourceDocument.RISE_OF_IX_RULEBOOK, (2, 4)),)


def _tile(tech_id: str, name: str, cost: int, ability: TechAbility) -> TechTile:
    """One tile, its acquire record checked."""

    check_acquire_record(tech_id)
    return TechTile(tech_id, name, cost, ability, sources=IX_TECH_SOURCES)


# In the app table's order (alphabetical). Typed: ``content.bloodlines.tech``
# reads it while both modules load.
IX_TECH_TILES: Final[tuple[TechTile, ...]] = (
    _tile("artillery", "Artillery", 1, TechAbility.REVEAL_SWORD_PER_SWORD_CARD),
    _tile("chaumurky", "Chaumurky", 4, TechAbility.ENDGAME_TIE_WIN),
    _tile(
        "detonation_devices",
        "Detonation Devices",
        3,
        TechAbility.DREADNOUGHT_DETONATION,
    ),
    _tile(
        "disposal_facility",
        "Disposal Facility",
        3,
        TechAbility.REVEAL_TRASH_AT_SIX_PERSUASION,
    ),
    _tile("flagship", "Flagship", 8, TechAbility.FLIP_SOLARI_FOR_TROOPS),
    _tile("holoprojectors", "Holoprojectors", 3, TechAbility.FLIP_DISCARD_FOR_CARD),
    _tile("holtzman_engine", "Holtzman Engine", 6, TechAbility.HOLTZMAN_ENGINE),
    _tile(
        "invasion_ships", "Invasion Ships", 5, TechAbility.FLIP_DISCARD_IGNORE_BLOCKS
    ),
    _tile("memocorders", "Memocorders", 2, TechAbility.ENDGAME_INFLUENCE_THREE_VP),
    _tile("minimic_film", "Minimic Film", 2, TechAbility.MINIMIC_FILM),
    _tile(
        "restricted_ordnance",
        "Restricted Ordnance",
        4,
        TechAbility.REVEAL_HIGH_COUNCIL_SWORDS,
    ),
    _tile("shuttle_fleet", "Shuttle Fleet", 6, TechAbility.ROUND_START_TWO_SOLARI),
    _tile("sonic_snoopers", "Sonic Snoopers", 2, TechAbility.TRASH_CYCLE_INTRIGUE),
    _tile("spaceport", "Spaceport", 5, TechAbility.ACQUIRED_CARDS_ON_DECK),
    _tile("spy_satellites", "Spy Satellites", 4, TechAbility.SPY_SATELLITES),
    _tile("training_drones", "Training Drones", 3, TechAbility.FLIP_TROOP),
    _tile(
        "troop_transports", "Troop Transports", 2, TechAbility.SHIPPING_EXTRA_TROOP
    ),
    _tile("windtraps", "Windtraps", 2, TechAbility.CONFLICT_WIN_WATER),
)
IX_TECH_TILES_BY_ID: Final = {tile.tech_id: tile for tile in IX_TECH_TILES}
IX_TECH_IDS: Final = tuple(tile.tech_id for tile in IX_TECH_TILES)
