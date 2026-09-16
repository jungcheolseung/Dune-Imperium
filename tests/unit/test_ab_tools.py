"""The scratch-variant scaffolding under scripts/ab tracks the committed agents."""

import importlib.util
import sys
from pathlib import Path

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents import HeuristicAgent, RolloutAgent, registry
from dune_imperium.agents.rollout_agent import position_value
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.state import GamePhase
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game

_PYPATH = Path(__file__).resolve().parents[2] / "scripts" / "ab" / "pypath"


@pytest.fixture(scope="module")
def hvariants():
    spec = importlib.util.spec_from_file_location("hvariants", _PYPATH / "hvariants.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["hvariants"] = module
    spec.loader.exec_module(module)
    before = dict(registry.BASELINE_AGENT_FACTORIES)
    module.register(registry)
    module.register_rollout(registry)
    yield module
    registry.BASELINE_AGENT_FACTORIES.clear()
    registry.BASELINE_AGENT_FACTORIES.update(before)
    sys.modules.pop("hvariants", None)


def test_the_null_heuristic_variant_equals_the_committed_agent(hvariants) -> None:
    engine = UprisingRulesEngine()
    for flags in ({}, {"choam_module": True, "bloodlines": True, "immortality": True}):
        config = RulesetConfig(**flags)
        committed = run_policy_game(
            engine, config, 4, [HeuristicAgent(seed=900 + s) for s in range(4)]
        )
        null = run_policy_game(
            engine,
            config,
            4,
            [registry.make_agent("heuristic_v_null", 900 + s) for s in range(4)],
        )
        assert committed.replay.steps == null.replay.steps


def test_the_null_rollout_variant_values_a_position_like_the_committed_agent(
    hvariants,
) -> None:
    # The whole playout loop is the committed one; the value read at the
    # horizon is what a variant changes, so it is compared on real states.
    engine = UprisingRulesEngine()
    config = RulesetConfig(choam_module=True, bloodlines=True, tech_module=True)
    state = engine.reset(config, 6)
    chance = ChanceResolver(seed=6)
    policy = HeuristicAgent(seed=6)
    null = hvariants.ROLLOUT_VARIANTS["rollout_v_null"](seed=1)
    pinned = hvariants.ROLLOUT_VARIANTS["rollout_v_count_max"](seed=1)
    compared = 0
    while state.round_number < 4 and state.phase is not GamePhase.FINISHED:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        for seat in range(4):
            assert null._value(state, seat) == pytest.approx(
                position_value(state, seat)
            )
            assert pinned._value(state, seat) == pytest.approx(
                position_value(
                    state, seat, opponent_reference="max", deck_by_value=False
                )
            )
            compared += 1
        actions = engine.legal_actions(state, decision.owner)
        action = policy.choose_action(engine.observe(state, decision.owner), actions)
        state = engine.apply(state, action, legal_actions=actions).state
    assert compared > 100
    assert isinstance(registry.make_agent("rollout_v_null", 1), RolloutAgent)
