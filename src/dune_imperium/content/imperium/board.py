"""The original Dune: Imperium's four-player board (docs/rules/imperium-base.md 8).

Twenty-two spaces [DI pp. 17-18]; costs, troops, resources and Influence
requirements match the Steam app's ``SpaceArchetypes.BaseSet`` (compared
2026-10-22). Arrakeen, Imperial Basin and Secrets print as Uprising's
spaces do (the app shares their definitions) and are Uprising's
definitions here; Heighliner, Hagga Basin, Sietch Tabr, Research Station,
High Council and Swordmaster print differently and take ``imperium_`` ids
(docs/base-game-and-ix-plan.md 4.2 item 7, 15.2). The board prints no
observation post [DI p. 14].
"""

from typing import Final

from dune_imperium.content.schema import SourceDocument, SourceRef
from dune_imperium.content.uprising.board import (
    BOARD_SPACES,
    BoardSpace,
    Faction,
    InfluenceRequirement,
    ResourceCost,
)
from dune_imperium.content.uprising.types import AgentIcon

DI_P10: Final = SourceRef(SourceDocument.IMPERIUM_RULEBOOK, (10,))
DI_P13: Final = SourceRef(SourceDocument.IMPERIUM_RULEBOOK, (13,))
DI_P17: Final = (SourceRef(SourceDocument.IMPERIUM_RULEBOOK, (17,)),)
DI_P18: Final = (SourceRef(SourceDocument.IMPERIUM_RULEBOOK, (18,)),)

_SHARED: Final = {space.space_id: space for space in BOARD_SPACES}

# In the order of the Board Space Guide's Faction, Landsraad, City and Spice
# Trade groups [DI pp. 17-18].
IMPERIUM_BOARD_SPACES: Final[tuple[BoardSpace, ...]] = (
    BoardSpace(
        "conspire",
        "Conspire",
        AgentIcon.EMPEROR,
        cost_options=(ResourceCost(spice=4),),
        sources=DI_P17,
    ),
    BoardSpace("wealth", "Wealth", AgentIcon.EMPEROR, sources=DI_P18),
    BoardSpace(
        "imperium_heighliner",
        "Heighliner",
        AgentIcon.SPACING_GUILD,
        combat=True,
        cost_options=(ResourceCost(spice=6),),
        sources=DI_P17,
    ),
    BoardSpace("foldspace", "Foldspace", AgentIcon.SPACING_GUILD, sources=DI_P17),
    BoardSpace(
        "selective_breeding",
        "Selective Breeding",
        AgentIcon.BENE_GESSERIT,
        cost_options=(ResourceCost(spice=2),),
        sources=DI_P18,
    ),
    _SHARED["secrets"],
    BoardSpace(
        "hardy_warriors",
        "Hardy Warriors",
        AgentIcon.FREMEN,
        combat=True,
        cost_options=(ResourceCost(water=1),),
        sources=DI_P17,
    ),
    BoardSpace(
        "stillsuits",
        "Stillsuits",
        AgentIcon.FREMEN,
        combat=True,
        sources=DI_P18,
    ),
    BoardSpace(
        "hall_of_oratory", "Hall of Oratory", AgentIcon.LANDSRAAD, sources=DI_P17
    ),
    BoardSpace(
        "rally_troops",
        "Rally Troops",
        AgentIcon.LANDSRAAD,
        cost_options=(ResourceCost(solari=4),),
        sources=DI_P18,
    ),
    BoardSpace(
        "mentat",
        "Mentat",
        AgentIcon.LANDSRAAD,
        cost_options=(ResourceCost(solari=2),),
        sources=DI_P18,
    ),
    BoardSpace(
        "imperium_swordmaster",
        "Swordmaster",
        AgentIcon.LANDSRAAD,
        cost_options=(ResourceCost(solari=8),),
        sources=DI_P18,
    ),
    BoardSpace(
        "imperium_high_council",
        "High Council",
        AgentIcon.LANDSRAAD,
        cost_options=(ResourceCost(solari=5),),
        sources=DI_P17,
    ),
    _SHARED["arrakeen"],
    BoardSpace(
        "carthag",
        "Carthag",
        AgentIcon.CITY,
        combat=True,
        critical=True,
        sources=(*DI_P17, DI_P10),
    ),
    BoardSpace(
        "imperium_research_station",
        "Research Station",
        AgentIcon.CITY,
        combat=True,
        cost_options=(ResourceCost(water=2),),
        sources=DI_P18,
    ),
    BoardSpace(
        "imperium_sietch_tabr",
        "Sietch Tabr",
        AgentIcon.CITY,
        combat=True,
        requirement=InfluenceRequirement(Faction.FREMEN, 2),
        sources=DI_P18,
    ),
    _SHARED["imperial_basin"],
    BoardSpace(
        "imperium_hagga_basin",
        "Hagga Basin",
        AgentIcon.SPICE_TRADE,
        combat=True,
        maker=True,
        cost_options=(ResourceCost(water=1),),
        sources=(*DI_P17, DI_P13),
    ),
    BoardSpace(
        "the_great_flat",
        "The Great Flat",
        AgentIcon.SPICE_TRADE,
        combat=True,
        maker=True,
        cost_options=(ResourceCost(water=2),),
        sources=(*DI_P17, DI_P13),
    ),
    BoardSpace(
        "secure_contract", "Secure Contract", AgentIcon.SPICE_TRADE, sources=DI_P18
    ),
    # "Pay 2 to 5 spice" [DI p. 18]: one cost option per amount.
    BoardSpace(
        "sell_melange",
        "Sell Melange",
        AgentIcon.SPICE_TRADE,
        cost_options=tuple(ResourceCost(spice=spice) for spice in (2, 3, 4, 5)),
        sources=DI_P18,
    ),
)

# The spaces only the original game prints (the three shared ones are in
# Uprising's ``BOARD_SPACES`` already).
# Typed: ``content.uprising.board`` reads it while both modules load.
IMPERIUM_ONLY_BOARD_SPACES: Final[tuple[BoardSpace, ...]] = tuple(
    space for space in IMPERIUM_BOARD_SPACES if space.space_id not in _SHARED
)

# The Maker spaces (docs/rules/imperium-base.md 10, [DI p. 13] [FAQ p. 2]), in
# the order the bonus spice ledger keeps them.
IMPERIUM_MAKER_SPACE_IDS: Final = (
    "the_great_flat",
    "imperium_hagga_basin",
    "imperial_basin",
)
