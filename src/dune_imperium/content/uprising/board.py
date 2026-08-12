"""Static four-player Uprising board definition.

Space properties come from the official Board Space Guide pp. 1-2. Observation
post edges are transcribed from the official Main Rulebook pp. 4-5 board art and
documented in ``docs/rules/observation-posts.md``.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from dune_imperium.content.schema import SourceDocument, SourceRef


class AgentIcon(StrEnum):
    """Agent icons printed on cards and board spaces."""

    EMPEROR = "emperor"
    SPACING_GUILD = "spacing_guild"
    BENE_GESSERIT = "bene_gesserit"
    FREMEN = "fremen"
    LANDSRAAD = "landsraad"
    CITY = "city"
    SPICE_TRADE = "spice_trade"
    SPY = "spy"


class Faction(StrEnum):
    """The four influence factions."""

    EMPEROR = "emperor"
    SPACING_GUILD = "spacing_guild"
    BENE_GESSERIT = "bene_gesserit"
    FREMEN = "fremen"


class DynamicCost(StrEnum):
    """Cost selection controlled by board state rather than player choice."""

    SWORDMASTER = "swordmaster"


@dataclass(frozen=True, slots=True)
class ResourceCost:
    """Resources paid before resolving a board space."""

    solari: int = 0
    spice: int = 0
    water: int = 0

    def __post_init__(self) -> None:
        if min(self.solari, self.spice, self.water) < 0:
            raise ValueError("resource costs must not be negative")


@dataclass(frozen=True, slots=True)
class InfluenceRequirement:
    """Faction influence required before entering a space."""

    faction: Faction
    amount: int

    def __post_init__(self) -> None:
        if self.amount < 1:
            raise ValueError("influence requirement must be positive")


@dataclass(frozen=True, slots=True)
class BoardSpace:
    """Rules-relevant static properties of one board space."""

    space_id: str
    name: str
    agent_icon: AgentIcon
    combat: bool = False
    maker: bool = False
    critical: bool = False
    cost_options: tuple[ResourceCost, ...] = ()
    dynamic_cost: DynamicCost | None = None
    requirement: InfluenceRequirement | None = None
    sources: tuple[SourceRef, ...] = ()

    def __post_init__(self) -> None:
        if not self.space_id or not self.name:
            raise ValueError("board spaces require stable IDs and names")
        if not self.sources:
            raise ValueError("board spaces require official source references")
        if self.maker and not self.combat:
            raise ValueError("every Uprising maker space must be a combat space")
        if self.critical and not self.combat:
            raise ValueError("every critical location must be a combat space")
        if self.dynamic_cost is not None and not self.cost_options:
            raise ValueError("dynamic costs require their possible costs")

    @property
    def faction(self) -> Faction | None:
        """Return the faction granted by visiting this icon, if any."""

        try:
            return Faction(self.agent_icon.value)
        except ValueError:
            return None


@dataclass(frozen=True, slots=True)
class ObservationPost:
    """One observation post and its direct board-space edges."""

    post_id: str
    connected_space_ids: tuple[str, ...]
    source: SourceRef = SourceRef(SourceDocument.MAIN_RULEBOOK, (4, 5))

    def __post_init__(self) -> None:
        if not self.post_id:
            raise ValueError("observation post ID must not be empty")
        if not self.connected_space_ids:
            raise ValueError("observation posts require at least one connection")
        if len(self.connected_space_ids) != len(set(self.connected_space_ids)):
            raise ValueError("observation post connections must be unique")


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
)

BOARD_SPACES_BY_ID: Final[Mapping[str, BoardSpace]] = MappingProxyType(
    {space.space_id: space for space in BOARD_SPACES}
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
