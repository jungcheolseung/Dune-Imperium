"""``AppAIAgent``: our port of the Steam app's computer opponent.

The Steam "Dune: Imperium" app (4.1.2.1808) decides with
``worm.canis.ai.WormAIProfile``: a one-step utility argmax over the choices
the engine offers, valued by hand-tuned per-card data and 437 constants,
with no search (``analysis/ai/ai-policy-report-ko.md`` in the assets
checkout). This agent reproduces that policy inside our engine: each decision
window is translated into the app prompt it corresponds to, answered with
the ported value functions, and mapped back to one of our legal actions.

Difficulty is the app's: level 0 Easy, 1 Medium, 2 Hard (the constant table
is the only difference). Every decision is the app's (no heuristic is ever
mixed in, user decision 2026-10-05): a decision no window mirrors is answered
the way the app answers a forced prompt it cannot value
(``PlayerEntity::DefaultRandomChoice``, a uniformly random legal action) and
is counted in ``fallbacks``; the coverage census requires that count to be 0.

A live game must never stall on an app_ai bug (user decision 2026-10-05, for
the play UI): a window that raises, or that answers with an action outside
the legal set, is answered the same way, counted in ``fallbacks`` under
``error:<decision kind>`` and logged with the decision kind. The answer
comes from the agent's own seeded RNG, so a save restore, which asks a fresh
agent every AI step again, regenerates the same step. Every fallback logs a
warning (or, for an error, an error) on this module's logger.

The agent is a ``StateAgent`` because the app reads the open turn's context,
the Reveal's Persuasion and deck multisets that ``PlayerView`` lacks; every
read goes through ``AppContext``, which allows only what the seat may know.

Concurrent games (the play server's threadpool) each hold their own agents.
The package keeps no module-level state that a decision writes and a later
decision reads: per-decision caches live on the ``Profile``, cross-decision
memory on the agent, and module-level values are either built at import or
pure ``functools.cache`` lookups of immutable values; ``abilities.UNPORTED``
is a diagnostic counter updated under a lock
(``tests/unit/agents/app_ai/test_app_ai_concurrency.py``).
"""

import logging
import random
from collections import Counter
from typing import Final

from dune_imperium.agents.app_ai.choice import default_random_choice
from dune_imperium.agents.app_ai.context import AppContext
from dune_imperium.agents.app_ai.data.constants import TABLES
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.windows import DecisionRun, Memory, handler_for
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.observation import PlayerView
from dune_imperium.core.state import GameState

LEVEL_NAMES = {0: "easy", 1: "medium", 2: "hard"}
#: The ``fallbacks`` key prefix of a decision a window failed on.
ERROR_PREFIX: Final = "error:"

_LOGGER: Final = logging.getLogger(__name__)


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
        self.memory = Memory()
        # Decisions answered at random, by decision kind: no window mirrors
        # them (``<kind>``, ``view-only:<kind>``) or the window failed
        # (``error:<kind>``).
        self.fallbacks: Counter[str] = Counter()
        # Decisions answered by the app mirror, by decision kind.
        self.mirrored: Counter[str] = Counter()

    def choose_action(
        self, observation: PlayerView, legal_actions: tuple[DomainAction, ...]
    ) -> DomainAction:
        """View-only call: without the state the app cannot be mirrored."""

        key = f"view-only:{observation.decision_kind}"
        _LOGGER.warning(
            "%s answered a %s decision at random: no state was given",
            self._name(observation.player),
            observation.decision_kind,
        )
        return self._random_answer(key, legal_actions)

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
        action: DomainAction | None = None
        try:
            handler = handler_for(kind)
            if handler is not None:
                ctx = AppContext(state, observation.player, observation)
                profile = Profile(ctx, TABLES[self.level], self._rng)
                run = DecisionRun(ctx, profile, legal_actions, self._rng, self.memory)
                action = handler(run)
        except Exception:
            # The window may have drawn from the RNG and written memory
            # before it failed; it does so identically on a restore's replay.
            _LOGGER.exception(
                "%s failed on a %s decision (round %s); answering at random",
                self._name(observation.player),
                kind,
                state.round_number,
            )
            return self._random_answer(f"{ERROR_PREFIX}{kind}", legal_actions)
        if action is None:
            _LOGGER.warning(
                "%s answered an unmirrored %s decision at random",
                self._name(observation.player),
                kind,
            )
            return self._random_answer(str(kind), legal_actions)
        if action not in legal_actions:
            _LOGGER.error(
                "%s chose an illegal action %r in a %s decision (round %s); "
                "answering at random",
                self._name(observation.player),
                action,
                kind,
                state.round_number,
            )
            return self._random_answer(f"{ERROR_PREFIX}{kind}", legal_actions)
        self.mirrored[str(kind)] += 1
        return action

    def _random_answer(
        self, key: str, legal_actions: tuple[DomainAction, ...]
    ) -> DomainAction:
        """``DefaultRandomChoice`` from the agent's own RNG, counted under ``key``.

        Deterministic given the agent's history, so a restored game asks a
        fresh agent the same questions and gets the same answers.
        """

        self.fallbacks[key] += 1
        return default_random_choice(legal_actions, self._rng)

    def _name(self, seat: int) -> str:
        return f"app_ai {LEVEL_NAMES.get(self.level, self.level)} seat {seat}"
