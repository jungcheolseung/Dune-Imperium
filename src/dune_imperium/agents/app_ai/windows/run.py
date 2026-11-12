"""What a window handler receives: one decision's inputs and the agent's memory."""

import random
from collections.abc import Callable
from dataclasses import dataclass, field

from dune_imperium.agents.app_ai.context import AppContext
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.core.actions import ActionValue, DomainAction


@dataclass
class Memory:
    """Per-agent memory across decisions.

    ``intents`` keeps an app answer that spans several of our decisions (the
    app answers once where our engine asks step by step): key it by something
    that identifies the app prompt, e.g. ``(round, frame kind, card id)``, and
    drop it once used. ``data`` is free-form per-window state.
    """

    intents: dict[tuple[object, ...], object] = field(default_factory=dict)
    data: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DecisionRun:
    """One decision: honest context, profile, legal actions, RNG and memory."""

    ctx: AppContext
    profile: Profile
    legal: tuple[DomainAction, ...]
    rng: random.Random
    memory: Memory

    def by_id(self, action_id: str) -> tuple[DomainAction, ...]:
        """The legal actions of one action id, in legal order."""

        return tuple(a for a in self.legal if a.action_id == action_id)

    def first(self, action_id: str) -> DomainAction | None:
        """The first legal action of ``action_id``, if any."""

        for action in self.legal:
            if action.action_id == action_id:
                return action
        return None


def arg(action: DomainAction, name: str) -> ActionValue | None:
    """One argument of ``action`` by name."""

    for key, value in action.arguments:
        if key == name:
            return value
    return None


type Handler = Callable[[DecisionRun], DomainAction | None]
"""A window handler: the app-faithful action, or None to fall back."""
