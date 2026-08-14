"""PettingZoo API and information-boundary tests."""

from dataclasses import replace

import numpy as np
from pettingzoo.test import api_test, seed_test  # type: ignore[import-untyped]

from dune_imperium import RulesetConfig
from dune_imperium.adapters.pettingzoo_env import _round_finished, env
from dune_imperium.core import GamePhase
from dune_imperium.rules import UprisingRulesEngine


def test_aec_environment_passes_official_api_test() -> None:
    api_test(env(), num_cycles=500)


def test_aec_environment_is_seed_reproducible() -> None:
    seed_test(env, num_cycles=200)


def test_observation_exposes_only_encoded_view_and_action_mask() -> None:
    environment = env()
    environment.reset(seed=7)

    observation, _, terminated, truncated, info = environment.last()

    assert observation is not None
    assert set(observation) == {"observation", "action_mask"}
    assert isinstance(observation["observation"], np.ndarray)
    assert observation["action_mask"].sum() > 0
    assert terminated is False
    assert truncated is False
    assert info == {}


def test_one_round_environment_stops_after_automatic_next_round_start() -> None:
    state = UprisingRulesEngine().reset(RulesetConfig(), seed=7)

    assert _round_finished(state) is False
    assert _round_finished(replace(state, round_number=2, phase=GamePhase.PLAYER_TURNS))
