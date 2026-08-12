"""Player-scoped, immutable observations."""

from dataclasses import dataclass

from dune_imperium.core.actions import ActionValue
from dune_imperium.core.state import GamePhase


@dataclass(frozen=True, slots=True)
class PlayerView:
    """Information safe to expose to a single player or policy."""

    player: int
    revision: int
    phase: GamePhase
    public_data: tuple[tuple[str, ActionValue], ...] = ()
    private_data: tuple[tuple[str, ActionValue], ...] = ()
