"""``core.memo.answers_of``: answers kept with a game state while it lives
(2026-11 engine speed, round 2)."""

import copy
import gc
import pickle
from dataclasses import fields

from dune_imperium.config import RulesetConfig
from dune_imperium.core import memo
from dune_imperium.core.state import GameState
from dune_imperium.rules.engine import UprisingRulesEngine


def _state(seed: int) -> GameState:
    return UprisingRulesEngine().reset(RulesetConfig(), seed)


def test_answers_are_kept_for_the_very_same_state() -> None:
    state = _state(1)
    answers = memo.answers_of(state)
    answers["question"] = "answer"
    assert memo.answers_of(state) is answers
    # An equal state that is another object has answers of its own.
    other = copy.replace(state)
    assert other == state
    assert other is not state
    assert memo.answers_of(other) == {}


def test_answers_leave_with_their_state() -> None:
    state = _state(2)
    memo.answers_of(state)["question"] = "answer"
    key = id(state)
    assert key in memo._ANSWERS
    del state
    gc.collect()
    assert key not in memo._ANSWERS


def test_a_dead_state_s_late_callback_keeps_a_newer_entry() -> None:
    state = _state(3)
    memo.answers_of(state)
    key = id(state)
    reference = memo._ANSWERS[key][0]
    newer = memo._ANSWERS[key] = (memo._ANSWERS[key][0].__class__(state), {})
    memo._forget(key, reference)
    assert memo._ANSWERS[key] is newer
    memo._ANSWERS.pop(key)


def test_the_weak_reference_slot_is_no_field_of_the_state() -> None:
    state = _state(4)
    names = tuple(field.name for field in fields(GameState))
    assert "__weakref__" not in names
    assert "__weakref__" in GameState.__slots__
    copied = pickle.loads(pickle.dumps(state))
    assert copied == state
    assert copy.deepcopy(state) == state
