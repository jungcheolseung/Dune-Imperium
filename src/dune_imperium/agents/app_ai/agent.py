"""``AppAIAgent``: our port of the Steam app's computer opponent.

The Steam "Dune: Imperium" app (4.1.2.1808) decides with
``worm.canis.ai.WormAIProfile``: a one-step utility argmax over the choices
the engine offers, valued by hand-tuned per-card data and 437 constants,
with no search (``analysis/ai/ai-policy-report-ko.md`` in the assets
checkout). This agent reproduces that policy inside our engine: each decision
window is translated into the app prompt it corresponds to, answered with
the ported value functions, and mapped back to one of our legal actions.

Difficulty is the app's: level 0 Easy, 1 Medium, 2 Hard (the constant table
is the only difference). A window not mirrored yet falls back to
``HeuristicAgent`` and is counted in ``fallbacks`` so coverage stays visible.

The agent is a ``StateAgent`` because the app reads the open turn's context,
the Reveal's Persuasion and deck multisets that ``PlayerView`` lacks; every
read goes through ``AppContext``, which allows only what the seat may know.
"""

import random
from collections import Counter

from dune_imperium.agents.app_ai.context import AppContext
from dune_imperium.agents.app_ai.data.constants import TABLES
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.windows import DecisionRun, Memory, handler_for
from dune_imperium.agents.heuristic_agent import HeuristicAgent
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.observation import PlayerView
from dune_imperium.core.state import GameState

LEVEL_NAMES = {0: "easy", 1: "medium", 2: "hard"}


class AppAIAgent:
    """The app AI at one difficulty level, seeded for replayable games."""

    def __init__(self, seed: int, level: int = 2) -> None:
        if seed < 0:
            raise ValueError("agent seed must not be negative")
        if level not in TABLES:
            raise ValueError(f"unknown app AI level {level}")
        self.seed = seed
        self.level = level
        self._rng = random.Random(seed)
        self._fallback = HeuristicAgent(seed=seed)
        self.memory = Memory()
        # Decisions answered by the fallback, by decision kind.
        self.fallbacks: Counter[str] = Counter()
        # Decisions answered by the app mirror, by decision kind.
        self.mirrored: Counter[str] = Counter()

    def choose_action(
        self, observation: PlayerView, legal_actions: tuple[DomainAction, ...]
    ) -> DomainAction:
        """View-only fallback: without the state the app cannot be mirrored."""

        self.fallbacks[f"view-only:{observation.decision_kind}"] += 1
        return self._fallback.choose_action(observation, legal_actions)

    def choose_action_with_state(
        self,
        state: GameState,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        """The app AI's answer to the decision on top of ``state``."""

        if not legal_actions:
            raise ValueError("app_ai requires at least one legal action")
        kind = observation.decision_kind
        if len(legal_actions) == 1:
            return legal_actions[0]
        handler = handler_for(kind)
        action: DomainAction | None = None
        if handler is not None:
            ctx = AppContext(state, observation.player, observation)
            profile = Profile(ctx, TABLES[self.level], self._rng)
            run = DecisionRun(ctx, profile, legal_actions, self._rng, self.memory)
            action = handler(run)
        if action is None:
            self.fallbacks[str(kind)] += 1
            return self._fallback.choose_action(observation, legal_actions)
        if action not in legal_actions:
            raise ValueError(f"app_ai chose an illegal action {action!r} in {kind}")
        self.mirrored[str(kind)] += 1
        return action
