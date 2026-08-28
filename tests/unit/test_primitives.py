"""Validation tests for serializable engine primitives."""

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.core import DecisionFrame, DomainAction, GameState, PlayerDecision
from dune_imperium.core.state import canonical_state_hash


def test_action_arguments_require_a_canonical_order() -> None:
    with pytest.raises(ValueError, match="sorted"):
        DomainAction(
            action_id="choose",
            actor=0,
            arguments=(("z", 1), ("a", 2)),
        )


def test_decision_stack_is_last_in_first_out() -> None:
    first = DecisionFrame("test", "first", PlayerDecision(0, "First"))
    second = DecisionFrame("test", "second", PlayerDecision(1, "Second"))
    state = GameState(config=RulesetConfig(), seed=1)

    stacked = state.push_decision(first).push_decision(second)

    assert stacked.decision_stack[-1] == second
    assert stacked.pop_decision().decision_stack[-1] == first
    assert state.decision_stack == ()


def test_state_hash_changes_with_replay_relevant_state() -> None:
    state = GameState(config=RulesetConfig(), seed=1)

    assert canonical_state_hash(state) != canonical_state_hash(
        GameState(config=RulesetConfig(), seed=2)
    )


def test_decision_frame_requires_kind() -> None:
    with pytest.raises(ValueError, match="frame kind"):
        DecisionFrame("", "frame", PlayerDecision(0, "Prompt"))
