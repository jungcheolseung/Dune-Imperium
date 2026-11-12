"""AI seats leave the specimen returns the engine offers since 2026-11-09.

The engine offers a specimen's return in its owner's Conflict reward window
and in the owner's windows outside its own turn where troops can be
recruited ("You may return any of your specimens to your supply at any
time" [Immortality p. 8]; OQ-050, user decisions 2026-11-09). No AI seat
learnt those windows with it, and the heuristic seat answers a Scouts line's
lone collect click without a draw: an extra row there would make it draw and
move every later choice of its seat (found on 2026-11-09, a heuristic game
whose Contract pick 481 moves differed from master's). So every AI seat sees
those windows without it (``agents.window_returns``).
"""

from __future__ import annotations

import random

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents import StateAgent, make_agent
from dune_imperium.agents.window_returns import (
    RETURN_WINDOWS,
    without_window_specimen_return,
)
from dune_imperium.core import ChanceDecision, DomainAction, GameState, PlayerDecision
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.immortality import SPECIMEN_RETURN_WINDOWS
from dune_imperium.rules.scouts_effects import SCOUTS_COLLECT

RETURN = DomainAction("return_specimen", actor=0)
ENGINE = UprisingRulesEngine()
UPRISING_FULL = RulesetConfig(
    choam_module=True,
    leader_draft=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
    go_to_11=True,
    epic_game=True,
    arrakeen_scouts=True,
)


def test_the_filter_covers_every_window_the_return_was_added_to() -> None:
    assert RETURN_WINDOWS == {str(FrameKind.COMBAT_REWARD_ICONS)} | {
        str(kind) for kind in SPECIMEN_RETURN_WINDOWS
    }


@pytest.mark.parametrize("kind", sorted(RETURN_WINDOWS))
def test_the_return_is_left_out_of_every_new_window(kind: str) -> None:
    row = DomainAction("choose_option", actor=0, arguments=(("option", 0),))
    assert without_window_specimen_return((row, RETURN), kind) == (row,)
    # Never no move at all.
    assert without_window_specimen_return((RETURN,), kind) == (RETURN,)


def test_the_windows_that_offered_it_before_keep_it() -> None:
    passed = DomainAction("pass_combat_intrigue", actor=0)
    for kind in (
        "combat_intrigue",
        "control_defense",
        "turn",
        "agent_effects",
        "reveal",
    ):
        assert without_window_specimen_return((passed, RETURN), kind) == (
            passed,
            RETURN,
        )


def _collect_beside_a_return() -> tuple[GameState, int]:
    """A seeded four-heuristic game up to a Scouts line's collect click offered
    beside a specimen's return, outside its seat's turn."""

    seed = 9110046
    state = ENGINE.reset(UPRISING_FULL, seed)
    agents = [
        make_agent("heuristic", seed * 10 + seat, UPRISING_FULL) for seat in range(4)
    ]
    chance = ChanceResolver(seed=seed)
    for _ in range(30_000):
        decision = ENGINE.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = ENGINE.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        owner = decision.owner
        legal = ENGINE.legal_actions(state, owner)
        if [action.action_id for action in legal] == [
            SCOUTS_COLLECT,
            "return_specimen",
        ]:
            return state, owner
        agent = agents[owner]
        view = ENGINE.observe(state, owner)
        action = (
            agent.choose_action_with_state(state, view, legal)
            if isinstance(agent, StateAgent)
            else agent.choose_action(view, legal)
        )
        state = ENGINE.apply(state, action, legal_actions=legal).state
    raise AssertionError("the game never offered a collect beside a return")


COLLECT_STATE, COLLECT_SEAT = _collect_beside_a_return()


def test_the_heuristic_takes_a_lone_collect_without_a_draw() -> None:
    agent = make_agent("heuristic", 7, UPRISING_FULL)
    legal = ENGINE.legal_actions(COLLECT_STATE, COLLECT_SEAT)
    view = ENGINE.observe(COLLECT_STATE, COLLECT_SEAT)
    assert view.decision_kind == str(FrameKind.SCOUTS_EFFECT)
    rng = agent._rng  # type: ignore[attr-defined]
    assert isinstance(rng, random.Random)
    before = rng.getstate()
    chosen = agent.choose_action_with_state(COLLECT_STATE, view, legal)  # type: ignore[attr-defined]
    assert chosen.action_id == SCOUTS_COLLECT
    # Its random stream is the one it had without the return beside it.
    assert rng.getstate() == before


@pytest.mark.parametrize("kind", ["heuristic", "app_ai", "rollout"])
def test_no_ai_seat_returns_a_specimen_in_a_new_window(kind: str) -> None:
    # Over many seeds: a seat given the return beside the collect would take
    # it now and then (app_ai answers an unmirrored Scouts line at random,
    # a rollout weighs both rows), so every seed taking the collect shows
    # the seat is not given it.
    legal = ENGINE.legal_actions(COLLECT_STATE, COLLECT_SEAT)
    view = ENGINE.observe(COLLECT_STATE, COLLECT_SEAT)
    chosen = set()
    for seed in range(24):
        agent = make_agent(kind, seed, UPRISING_FULL)
        action = (
            agent.choose_action_with_state(COLLECT_STATE, view, legal)
            if isinstance(agent, StateAgent)
            else agent.choose_action(view, legal)
        )
        chosen.add(action.action_id)
    assert chosen == {SCOUTS_COLLECT}
