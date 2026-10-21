"""The Agent-turn effect context: read once per frame, a fresh copy per call."""

from dataclasses import replace

import pytest

from dune_imperium.agents.registry import make_agent
from dune_imperium.config import RulesetConfig
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.state import GameState
from dune_imperium.rules import UprisingRulesEngine, effects
from dune_imperium.rules.effects import current_agent_effect_context
from dune_imperium.rules.frames import FrameKind

ENGINE = UprisingRulesEngine()


def _agent_effect_state() -> GameState:
    """The first state of a seeded heuristic game with an Agent-turn effect
    frame on top."""

    config = RulesetConfig()
    state = ENGINE.reset(config, 5)
    chance = ChanceResolver(seed=5)
    agents = [make_agent("heuristic", seed=seat) for seat in range(4)]
    for _ in range(2000):
        if state.decision_stack and state.decision_stack[-1].kind == (
            FrameKind.AGENT_EFFECTS
        ):
            return state
        decision = ENGINE.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = ENGINE.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        actions = ENGINE.legal_actions(state, decision.owner)
        view = ENGINE.observe(state, decision.owner)
        action = agents[decision.owner].choose_action(view, actions)
        state = ENGINE.apply(state, action, legal_actions=actions).state
    raise AssertionError("no Agent-turn effect frame in 2,000 steps")


def test_each_read_of_one_frame_is_a_fresh_equal_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(effects, "_CONTEXTS", {})
    state = _agent_effect_state()

    frame, first = current_agent_effect_context(state)
    first["space_id"] = "changed by a caller"
    again_frame, again = current_agent_effect_context(state)

    assert again_frame is frame is state.decision_stack[-1]
    assert again == dict(frame.context) != first
    assert again is not first
    assert len(effects._CONTEXTS) == 1


def test_a_frame_that_is_not_an_agent_effect_still_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(effects, "_CONTEXTS", {})
    state = _agent_effect_state()
    current_agent_effect_context(state)
    top = state.decision_stack[-1]
    other = replace(
        state,
        decision_stack=(*state.decision_stack[:-1], replace(top, kind=FrameKind.TURN)),
    )

    with pytest.raises(ValueError, match="not an Agent-turn effect"):
        current_agent_effect_context(other)
    with pytest.raises(ValueError, match="no pending Agent-turn effect frame"):
        current_agent_effect_context(replace(state, decision_stack=()))


def test_the_cache_empties_when_full_and_keeps_answering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(effects, "_CONTEXTS", {})
    monkeypatch.setattr(effects, "_CONTEXTS_LIMIT", 2)
    state = _agent_effect_state()
    top = state.decision_stack[-1]
    states = [
        replace(
            state,
            decision_stack=(
                *state.decision_stack[:-1],
                replace(top, frame_id=f"{top.frame_id}-{n}"),
            ),
        )
        for n in range(3)
    ]

    contexts = [current_agent_effect_context(s)[1] for s in states]

    assert contexts == [dict(top.context)] * 3
    assert len(effects._CONTEXTS) == 1
