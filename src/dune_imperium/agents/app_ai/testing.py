"""Helpers for app_ai tests and probes: real game states and profiles.

Port tests (and scratch probes) build a real ``GameState``, so ``AppContext``
reads exactly what it reads in play, then adjust the fields a formula depends
on with ``with_player``/``with_state`` and evaluate the port on a fresh
``Profile``.
"""

import random
from collections.abc import Callable
from dataclasses import replace

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.context import AppContext
from dune_imperium.agents.app_ai.data.constants import TABLES
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.heuristic_agent import HeuristicAgent
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.engine import UprisingRulesEngine

ENGINE = UprisingRulesEngine()


def play_until(
    predicate: Callable[[GameState, int], bool],
    *,
    choam: bool = True,
    seed: int = 1,
    max_steps: int = 30_000,
    config: RulesetConfig | None = None,
) -> GameState:
    """Play heuristic seats from a fresh game until ``predicate(state, owner)``.

    The predicate sees the state on top of which a player decision waits and
    the deciding seat. Raises if the game ends first. ``config`` (any option
    set: Immortality, Epic, Bloodlines …) overrides ``choam``. The heuristic
    seats only advance test games; app_ai never consults them.
    """

    if config is None:
        config = RulesetConfig(choam_module=choam)
    state = ENGINE.reset(config, seed)
    chance = ChanceResolver(seed=seed)
    agents = [HeuristicAgent(seed=seed * 10 + seat) for seat in range(4)]
    for _ in range(max_steps):
        if state.phase is GamePhase.FINISHED:
            break
        decision = ENGINE.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = ENGINE.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        if predicate(state, decision.owner):
            return state
        actions = ENGINE.legal_actions(state, decision.owner)
        view = ENGINE.observe(state, decision.owner)
        action = agents[decision.owner].choose_action(view, actions)
        state = ENGINE.apply(state, action, legal_actions=actions).state
    raise AssertionError("predicate never held before the game ended")


def first_decision(
    kind: str,
    *,
    choam: bool = True,
    seed: int = 1,
    config: RulesetConfig | None = None,
) -> GameState:
    """The first state whose pending decision is of frame kind ``kind``."""

    return play_until(
        lambda state, owner: state.decision_stack[-1].kind == kind,
        choam=choam,
        seed=seed,
        config=config,
    )


def with_player(state: GameState, seat: int, **changes: object) -> GameState:
    """``state`` with ``replace(players[seat], **changes)``."""

    players = list(state.players)
    players[seat] = replace(players[seat], **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players))


def with_state(state: GameState, **changes: object) -> GameState:
    """``replace(state, **changes)``."""

    return replace(state, **changes)  # type: ignore[arg-type]


def player(state: GameState, seat: int) -> PlayerState:
    return state.players[seat]


def make_profile(
    state: GameState, seat: int | None = None, *, level: int = 2, rng_seed: int = 0
) -> Profile:
    """A fresh ``Profile`` for ``seat`` (default: the seat deciding now)."""

    if seat is None:
        decision = ENGINE.current_decision(state)
        assert isinstance(decision, PlayerDecision)
        seat = decision.owner
    view = ENGINE.observe(state, seat)
    ctx = AppContext(state, seat, view)
    return Profile(ctx, TABLES[level], random.Random(rng_seed))
