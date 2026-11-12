"""Static four-player Uprising board definition.

Space properties come from the official Board Space Guide pp. 1-2. Observation
post edges are transcribed from the official Main Rulebook pp. 4-5 board art and
documented in ``docs/rules/observation-posts.md``.
"""

from typing import Final

from dune_imperium.content.core.board import (
    BoardSpace,
    DynamicCost,
    InfluenceRequirement,
    ObservationPost,
    ResourceCost,
)
from dune_imperium.content.core.icons import AgentIcon, Faction
from dune_imperium.content.core.schema import SourceDocument, SourceRef

FREE: Final = ResourceCost()
GUIDE_P1: Final = (SourceRef(SourceDocument.BOARD_SPACE_GUIDE, (1,)),)
GUIDE_P2: Final = (SourceRef(SourceDocument.BOARD_SPACE_GUIDE, (2,)),)
MAIN_P10: Final = SourceRef(SourceDocument.MAIN_RULEBOOK, (10,))
MAIN_P15: Final = SourceRef(SourceDocument.MAIN_RULEBOOK, (15,))

BOARD_SPACES: Final = (
    BoardSpace(
        "dutiful_service",
        "Dutiful Service",
        AgentIcon.EMPEROR,
        sources=GUIDE_P1,
    ),
    BoardSpace(
        "sardaukar",
        "Sardaukar",
        AgentIcon.EMPEROR,
        cost_options=(ResourceCost(spice=4),),
        sources=GUIDE_P2,
    ),
    BoardSpace(
        "deliver_supplies",
        "Deliver Supplies",
        AgentIcon.SPACING_GUILD,
        sources=GUIDE_P1,
    ),
    BoardSpace(
        "heighliner",
        "Heighliner",
        AgentIcon.SPACING_GUILD,
        combat=True,
        cost_options=(ResourceCost(spice=5),),
        sources=GUIDE_P2,
    ),
    BoardSpace(
        "espionage",
        "Espionage",
        AgentIcon.BENE_GESSERIT,
        cost_options=(ResourceCost(spice=1),),
        sources=GUIDE_P1,
    ),
    BoardSpace("secrets", "Secrets", AgentIcon.BENE_GESSERIT, sources=GUIDE_P2),
    BoardSpace(
        "desert_tactics",
        "Desert Tactics",
        AgentIcon.FREMEN,
        combat=True,
        cost_options=(ResourceCost(water=1),),
        sources=GUIDE_P1,
    ),
    BoardSpace(
        "fremkit",
        "Fremkit",
        AgentIcon.FREMEN,
        combat=True,
        sources=GUIDE_P1,
    ),
    BoardSpace(
        "assembly_hall",
        "Assembly Hall",
        AgentIcon.LANDSRAAD,
        sources=GUIDE_P1,
    ),
    BoardSpace(
        "gather_support",
        "Gather Support",
        AgentIcon.LANDSRAAD,
        cost_options=(FREE, ResourceCost(solari=2)),
        sources=GUIDE_P1,
    ),
    BoardSpace(
        "high_council",
        "High Council",
        AgentIcon.LANDSRAAD,
        cost_options=(ResourceCost(solari=5),),
        sources=GUIDE_P2,
    ),
    BoardSpace(
        "imperial_privilege",
        "Imperial Privilege",
        AgentIcon.LANDSRAAD,
        cost_options=(ResourceCost(solari=3),),
        requirement=InfluenceRequirement(Faction.EMPEROR, 2),
        sources=GUIDE_P2,
    ),
    BoardSpace(
        "swordmaster",
        "Swordmaster",
        AgentIcon.LANDSRAAD,
        cost_options=(ResourceCost(solari=8), ResourceCost(solari=6)),
        dynamic_cost=DynamicCost.SWORDMASTER,
        sources=GUIDE_P2,
    ),
    BoardSpace(
        "arrakeen",
        "Arrakeen",
        AgentIcon.CITY,
        combat=True,
        critical=True,
        sources=(*GUIDE_P1, MAIN_P10),
    ),
    BoardSpace(
        "research_station",
        "Research Station",
        AgentIcon.CITY,
        combat=True,
        cost_options=(ResourceCost(water=2),),
        sources=GUIDE_P2,
    ),
    BoardSpace(
        "sietch_tabr",
        "Sietch Tabr",
        AgentIcon.CITY,
        combat=True,
        requirement=InfluenceRequirement(Faction.FREMEN, 2),
        sources=GUIDE_P2,
    ),
    BoardSpace(
        "spice_refinery",
        "Spice Refinery",
        AgentIcon.CITY,
        combat=True,
        critical=True,
        cost_options=(FREE, ResourceCost(spice=1)),
        sources=(*GUIDE_P2, MAIN_P10),
    ),
    BoardSpace(
        "accept_contract",
        "Accept Contract",
        AgentIcon.SPICE_TRADE,
        sources=GUIDE_P1,
    ),
    BoardSpace(
        "deep_desert",
        "Deep Desert",
        AgentIcon.SPICE_TRADE,
        combat=True,
        maker=True,
        cost_options=(ResourceCost(water=3),),
        sources=(*GUIDE_P1, MAIN_P15),
    ),
    BoardSpace(
        "hagga_basin",
        "Hagga Basin",
        AgentIcon.SPICE_TRADE,
        combat=True,
        maker=True,
        cost_options=(ResourceCost(water=1),),
        sources=(*GUIDE_P2, MAIN_P15),
    ),
    BoardSpace(
        "imperial_basin",
        "Imperial Basin",
        AgentIcon.SPICE_TRADE,
        combat=True,
        maker=True,
        critical=True,
        sources=(*GUIDE_P2, MAIN_P10, MAIN_P15),
    ),
    BoardSpace(
        "shipping",
        "Shipping",
        AgentIcon.SPICE_TRADE,
        cost_options=(ResourceCost(spice=3),),
        requirement=InfluenceRequirement(Faction.SPACING_GUILD, 2),
        sources=GUIDE_P2,
    ),
    # Bloodlines: Esmar Tuek's Maker space, "1 spice OR draw 1 card"
    # (board tile; Dire Wolf design diary image) [Bloodlines p. 12].
    BoardSpace(
        "tuek_sietch",
        "Tuek's Sietch",
        AgentIcon.SPICE_TRADE,
        combat=True,
        maker=True,
        sources=(
            SourceRef(SourceDocument.BLOODLINES_RULEBOOK, (12,)),
            SourceRef(SourceDocument.CARD_FACE, (1,)),
        ),
        required_leader_id="esmar_tuek",
    ),
)


OBSERVATION_POSTS: Final = (
    ObservationPost(
        "emperor-sardaukar-dutiful-service",
        ("sardaukar", "dutiful_service"),
    ),
    ObservationPost(
        "landsraad-high-council-imperial-privilege-swordmaster",
        ("high_council", "imperial_privilege", "swordmaster"),
    ),
    ObservationPost(
        "landsraad-assembly-hall-gather-support",
        ("assembly_hall", "gather_support"),
    ),
    ObservationPost(
        "choam-shipping-accept-contract",
        ("shipping", "accept_contract"),
    ),
    ObservationPost(
        "spacing-guild-heighliner-deliver-supplies",
        ("heighliner", "deliver_supplies"),
    ),
    ObservationPost(
        "arrakis-research-station-spice-refinery",
        ("research_station", "spice_refinery"),
    ),
    ObservationPost(
        "arrakis-research-station-sietch-tabr",
        ("research_station", "sietch_tabr"),
    ),
    ObservationPost(
        "arrakis-spice-refinery-arrakeen",
        ("spice_refinery", "arrakeen"),
    ),
    ObservationPost("arrakis-imperial-basin", ("imperial_basin",)),
    ObservationPost("arrakis-hagga-basin", ("hagga_basin",)),
    ObservationPost("arrakis-deep-desert", ("deep_desert",)),
    ObservationPost(
        "bene-gesserit-espionage-secrets",
        ("espionage", "secrets"),
    ),
    ObservationPost(
        "fremen-desert-tactics-fremkit",
        ("desert_tactics", "fremkit"),
    ),
)

