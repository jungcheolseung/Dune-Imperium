"""Seeded random baseline agent."""

import random
from dataclasses import dataclass, field

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.observation import PlayerView


@dataclass(slots=True)
class RandomAgent:
    """Choose uniformly from the legal actions visible to one player."""

    seed: int
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise ValueError("agent seed must not be negative")
        self._rng = random.Random(self.seed)

    def choose_action(
        self,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        """Return one seeded uniform choice without inspecting hidden state."""

        if not legal_actions:
            raise ValueError("a random agent requires at least one legal action")
        if any(action.actor != observation.player for action in legal_actions):
            raise ValueError("every legal action must belong to the observing player")
        return self._rng.choice(legal_actions)
