"""Structural contract shared by every decision-making agent."""

from typing import Protocol, runtime_checkable

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.observation import PlayerView
from dune_imperium.core.state import GameState


class Agent(Protocol):
    """Anything that picks one legal action from a player-scoped view."""

    def choose_action(
        self,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        """Return exactly one of ``legal_actions`` for the observing player."""
        ...


@runtime_checkable
class StateAgent(Protocol):
    """An agent that branches from the authoritative state to search.

    Runners hand a ``StateAgent`` the full ``GameState`` next to the view so
    it can simulate forward. The contract stays honest by convention: an
    implementation must determinize hidden zones before searching and may
    read nothing the observing seat cannot see (``agents.determinize``).
    """

    def choose_action(
        self,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        """Fallback used when only the view is available."""
        ...

    def choose_action_with_state(
        self,
        state: GameState,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        """Return exactly one of ``legal_actions`` after searching from ``state``."""
        ...
