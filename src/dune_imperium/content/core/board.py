"""Board space and observation post schemas shared by every base game's board
(docs/content-core-refactor-plan.md 2.1).
"""

from dataclasses import dataclass
from enum import StrEnum

from dune_imperium.content.core.icons import AgentIcon, Faction
from dune_imperium.content.core.schema import SourceDocument, SourceRef


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
    # A Leader's private board space (Tuek's Sietch): on the table only
    # while that Leader is in play [Bloodlines p. 12].
    required_leader_id: str | None = None

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
