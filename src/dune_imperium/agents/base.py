"""Structural contract shared by every decision-making agent."""

from typing import Protocol

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.observation import PlayerView


class Agent(Protocol):
    """Anything that picks one legal action from a player-scoped view."""

    def choose_action(
        self,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        """Return exactly one of ``legal_actions`` for the observing player."""
        ...
