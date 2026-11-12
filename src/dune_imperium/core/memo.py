"""Kept answers of pure functions of a game state, for as long as it lives.

A decision asks the engine the same question of the same state several
times: its legal rows, the whole actions the deciding seat weighs, the step
it takes (``rules.engine.UprisingRulesEngine._rules_of``,
``rules.effect_steps``, ``rules.agent_turn.executable_placements``). A state
never changes, so the answer for the very same object can be kept.

Keeping only the last answer is not enough when several games are played in
turn: the self-play runner asks every lockstep game for its legal rows, then
every seat chooses, then every game applies its step
(``training.selfplay.SelfPlayRunner.run``), so with one answer kept each
game's later questions find another game's state and the answer is worked
out again (2026-11 engine speed, round 2,
docs/evaluation/2026-11-engine-speed.md). Keeping the last few dozen states'
answers instead held as many old states alive, and a game played alone (a
search seat's playouts, a sweep) then allocated its new states in their
memory, cold, about 5-10% slower. So the answers are kept with their state
instead (``answers_of``): a dict per state, found by the state's identity,
dropped when the state dies (a weak reference's callback). Every lockstep
game's state is alive while the game waits, and nothing outlives its state.
"""

import weakref
from collections.abc import Hashable
from functools import partial
from typing import Any

# id of a state -> (a weak reference to it, its kept answers).
_ANSWERS: dict[int, tuple[weakref.ref[Any], dict[Hashable, Any]]] = {}


def answers_of(state: object) -> dict[Hashable, Any]:
    """The answers kept for ``state`` (an object with a ``__weakref__``
    slot), to read and add to; empty when first asked.

    The entry is found by ``id(state)`` and checked through its weak
    reference to be this very object, so it cannot be another object's that
    was given a dead state's id; the reference's callback drops the entry as
    the state dies."""

    key = id(state)
    kept = _ANSWERS.get(key)
    if kept is not None and kept[0]() is state:
        return kept[1]
    answers: dict[Hashable, Any] = {}
    _ANSWERS[key] = (weakref.ref(state, partial(_forget, key)), answers)
    return answers


def _forget(key: int, reference: weakref.ref[Any]) -> None:
    """Drop the entry of a state that died, unless it is a newer one."""

    kept = _ANSWERS.get(key)
    if kept is not None and kept[0] is reference:
        _ANSWERS.pop(key, None)
