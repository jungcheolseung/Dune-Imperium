"""Kept answers of the legal-row path equal fresh ones (2026-11 engine speed).

docs/evaluation/2026-11-engine-speed.md: ``rules.effect_steps`` keeps the
pick, pick-free state and paths of a state, ``rules.agent_turn`` its
placements and ``rules.engine._rules_of`` the rules' actions, with the state
while it lives (``core.memo``, since round 2; the last answer only before),
``rules.agent_effect_frame`` its last box choices,
``rules.engine._advance_automatic`` the last state it stopped at and
``rules.combat_deployment`` its deployment window (round 3). Through
played games of both boards every decision's legal rows, whole actions and
applied step must be the same with the kept answers as after clearing them,
also when two games take turns, as the self-play runner's lockstep games do.
"""

from collections.abc import Iterator

import pytest

from dune_imperium.agents.heuristic_agent import HeuristicAgent
from dune_imperium.config import BaseGame, RulesetConfig
from dune_imperium.core import memo
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.state import GameState
from dune_imperium.rules import agent_effect_frame, combat_deployment
from dune_imperium.rules import engine as rules_engine
from dune_imperium.rules.engine import UprisingRulesEngine

FULL = RulesetConfig(
    choam_module=True,
    leader_draft=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
    epic_game=True,
    arrakeen_scouts=True,
)
IMPERIUM_IX = RulesetConfig(
    base_game=BaseGame.IMPERIUM,
    rise_of_ix=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
    arrakeen_scouts=True,
)


def played_states(config: RulesetConfig, seed: int, steps: int) -> Iterator[GameState]:
    """The states of a seeded heuristic game, every one of its first steps."""

    engine = UprisingRulesEngine()
    chance = ChanceResolver(seed)
    agents = [HeuristicAgent(seed=seed * 10 + seat) for seat in range(4)]
    state = engine.reset(config, seed)
    for _ in range(steps):
        yield state
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        if not isinstance(decision, PlayerDecision):
            return
        legal = engine.legal_actions(state, decision.owner)
        action = agents[decision.owner].choose_action_with_state(
            state, engine.observe(state, decision.owner), legal
        )
        state = engine.apply(state, action, legal_actions=legal).state


def _clear_caches() -> None:
    memo._ANSWERS.clear()
    rules_engine._settled = None
    agent_effect_frame._last_box_choices = None


@pytest.mark.parametrize(("config", "seed"), [(FULL, 7), (IMPERIUM_IX, 8)])
def test_kept_answers_equal_fresh_ones_through_a_game(
    config: RulesetConfig, seed: int
) -> None:
    """Every decision's legal rows, whole actions and applied step are the
    same whether the last answers are kept or cleared first."""

    engine = UprisingRulesEngine()
    for state in played_states(config, seed, 400):
        decision = engine.current_decision(state)
        if not isinstance(decision, PlayerDecision):
            continue
        owner = decision.owner
        warm = engine.legal_actions(state, owner)
        warm_wholes = engine.whole_actions(state, owner)
        warm_after = engine.apply(state, warm[0], legal_actions=warm).state
        _clear_caches()
        assert engine.legal_actions(state, owner) == warm
        _clear_caches()
        assert engine.whole_actions(state, owner) == warm_wholes
        _clear_caches()
        cold_after = engine.apply(state, warm[0]).state
        assert cold_after == warm_after


def test_kept_answers_equal_fresh_ones_when_two_games_take_turns() -> None:
    """Two games asked in turn, as the self-play runner's lockstep games are:
    each game's legal rows, whole actions and step are the same as the
    answers worked out afresh for it alone."""

    engine = UprisingRulesEngine()
    games = [played_states(FULL, 11, 300), played_states(IMPERIUM_IX, 12, 300)]
    for first, second in zip(*games, strict=False):
        asked = []
        for state in (first, second):
            decision = engine.current_decision(state)
            if isinstance(decision, PlayerDecision):
                owner = decision.owner
                legal = engine.legal_actions(state, owner)
                asked.append((state, owner, legal))
        kept = [
            (
                engine.whole_actions(state, owner),
                engine.apply(state, legal[-1], legal_actions=legal).state,
            )
            for state, owner, legal in asked
        ]
        for (state, owner, legal), (wholes, after) in zip(asked, kept, strict=True):
            _clear_caches()
            assert engine.legal_actions(state, owner) == legal
            _clear_caches()
            assert engine.whole_actions(state, owner) == wholes
            _clear_caches()
            assert engine.apply(state, legal[-1]).state == after


@pytest.mark.parametrize(("config", "seed"), [(FULL, 13), (IMPERIUM_IX, 14)])
def test_the_kept_deployment_window_is_the_fresh_one(
    config: RulesetConfig, seed: int
) -> None:
    """``combat_deployment._deployment_context`` keeps its answer with the
    state (round 3): the same as worked out afresh, the same object when
    asked again, and its context cannot be changed by an asker."""

    windows = 0
    for state in played_states(config, seed, 600):
        for player in range(4):
            kept = combat_deployment._deployment_context(state, player)
            assert combat_deployment._deployment_context(state, player) is kept
            assert kept == combat_deployment._find_deployment(state, player)
            if kept is None:
                continue
            windows += 1
            key = next(iter(kept.context))
            with pytest.raises(TypeError):
                kept.context[key] = 0  # type: ignore[index]
    assert windows > 20
