"""Batched policy contract for self-play and the baseline adapters.

A ``BatchPolicy`` answers many pending decisions at once: the self-play
runner gathers one ``PolicyRequest`` per game that waits on a seat this
policy controls and calls ``act`` once per policy per lockstep round, so a
neural policy can run a single forward pass over the whole batch. Each
request carries both the learning-side arrays (the versioned observation
encoding and the fixed-width legal-action mask) and the engine-side objects
(``PlayerView``, legal ``DomainAction`` tuple, and the authoritative state
for ``StateAgent`` search baselines) so rule-based and learned policies
share one interface. The answer is one catalog index per request and must
be a legal one; the runner rejects anything else.
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from dune_imperium.agents import Agent, StateAgent, make_agent
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.observation import PlayerView
from dune_imperium.core.state import GameState


@dataclass(frozen=True, slots=True)
class PolicyRequest:
    """One pending decision of one seat in one self-play game."""

    game: int
    seat: int
    state: GameState
    view: PlayerView
    legal_actions: tuple[DomainAction, ...]
    # Catalog index of every legal action, parallel to ``legal_actions``.
    legal_indices: tuple[int, ...]
    observation: np.ndarray
    mask: np.ndarray


class BatchPolicy(Protocol):
    """Anything that answers a batch of requests with one legal index each."""

    def act(self, requests: Sequence[PolicyRequest]) -> Sequence[int]:
        """Return one catalog index per request, in order."""
        ...


@dataclass(slots=True)
class RandomBatchPolicy:
    """Pick a uniformly random legal index for every request."""

    seed: int
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise ValueError("policy seed must not be negative")
        self._rng = random.Random(self.seed)

    def act(self, requests: Sequence[PolicyRequest]) -> Sequence[int]:
        return tuple(self._rng.choice(request.legal_indices) for request in requests)


class AgentBatchPolicy:
    """Drive seats with a named baseline ``Agent`` (one instance per seat).

    Each (game, seat) pair gets its own agent seeded from ``seed`` so the
    per-seat tie-break streams stay independent and reproducible, matching
    how the tournament seeds its seats. ``StateAgent`` baselines receive the
    request's state and search from it.
    """

    def __init__(self, kind: str, seed: int, *, players: int = 4) -> None:
        if seed < 0:
            raise ValueError("policy seed must not be negative")
        self.kind = kind
        self.seed = seed
        self._players = players
        self._agents: dict[tuple[int, int], Agent] = {}

    def _agent(self, game: int, seat: int) -> Agent:
        key = (game, seat)
        agent = self._agents.get(key)
        if agent is None:
            agent = make_agent(self.kind, self.seed + game * self._players + seat)
            self._agents[key] = agent
        return agent

    def act(self, requests: Sequence[PolicyRequest]) -> Sequence[int]:
        answers: list[int] = []
        for request in requests:
            agent = self._agent(request.game, request.seat)
            action = (
                agent.choose_action_with_state(
                    request.state, request.view, request.legal_actions
                )
                if isinstance(agent, StateAgent)
                else agent.choose_action(request.view, request.legal_actions)
            )
            position = request.legal_actions.index(action)
            answers.append(request.legal_indices[position])
        return tuple(answers)
