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


@runtime_checkable
class ReplayableAgent(Protocol):
    """An agent that can retrace a recorded decision without recomputing it.

    Loading a saved game replays every recorded step against fresh seeded
    agents, so each AI seat's memory (RNG streams, cycle guards) ends where
    the saved session's did. Regenerating every decision does that but pays
    for it again: a search seat's playouts cost about a second a decision.
    An agent implementing this protocol is told the recorded answer instead
    and only performs the cheap part of its bookkeeping.
    """

    def replay_decision(
        self,
        state: GameState,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
        action: DomainAction,
    ) -> bool:
        """Retrace ``action`` as this agent's own answer to this decision.

        Bring the agent's memory to exactly where it would be had it chosen
        ``action`` here itself (``choose_action_with_state`` with the same
        arguments), without the expensive part. Return ``False`` when
        ``action`` could not have been its choice; the memory is then
        unspecified and the agent must not be used further.
        """
        ...
