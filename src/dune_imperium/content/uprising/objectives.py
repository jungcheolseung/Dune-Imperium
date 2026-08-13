"""Objective cards for battle icons and first-player randomization."""

from dataclasses import dataclass
from typing import Final

from dune_imperium.content.schema import SourceDocument, SourceRef
from dune_imperium.content.uprising.types import BattleIcon


@dataclass(frozen=True, slots=True)
class ObjectiveDefinition:
    """One physical Objective card."""

    objective_id: str
    battle_icon: BattleIcon
    marked_player_counts: tuple[int, ...] = ()
    grants_first_player: bool = False
    sources: tuple[SourceRef, ...] = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3, 5)),)
    reference_url: str = (
        "https://news.direwolfdigital.com/"
        "dune-imperium-uprising-design-diary-2-sandworms-conflicts-and-the-shield-wall/"
    )

    def __post_init__(self) -> None:
        if not self.objective_id:
            raise ValueError("objective_id must not be empty")
        if any(players < 1 for players in self.marked_player_counts):
            raise ValueError("marked player counts must be positive")
        if not self.sources:
            raise ValueError("objectives require official source references")

    def supports(self, players: int) -> bool:
        """Return whether this card remains in setup for ``players``."""

        return not self.marked_player_counts or players in self.marked_player_counts


OBJECTIVES: Final = (
    ObjectiveDefinition(
        "objective_desert_mouse_4_6p",
        BattleIcon.DESERT_MOUSE,
        marked_player_counts=(4, 6),
    ),
    ObjectiveDefinition(
        "objective_desert_mouse",
        BattleIcon.DESERT_MOUSE,
        grants_first_player=True,
    ),
    ObjectiveDefinition(
        "objective_crysknife_1",
        BattleIcon.CRYSKNIFE,
    ),
    ObjectiveDefinition(
        "objective_crysknife_2",
        BattleIcon.CRYSKNIFE,
    ),
    ObjectiveDefinition(
        "objective_ornithopter_1_3p",
        BattleIcon.ORNITHOPTER,
        marked_player_counts=(1, 2, 3),
    ),
)

OBJECTIVES_BY_ID: Final = {
    objective.objective_id: objective for objective in OBJECTIVES
}


def objectives_for_players(players: int) -> tuple[ObjectiveDefinition, ...]:
    """Filter Objective cards using their printed player-count marks."""

    if players != 4:
        raise ValueError("only four-player Objective setup is currently supported")
    return tuple(objective for objective in OBJECTIVES if objective.supports(players))
