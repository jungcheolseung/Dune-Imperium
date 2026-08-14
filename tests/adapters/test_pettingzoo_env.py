"""PettingZoo API and information-boundary tests."""

import numpy as np
from pettingzoo.test import api_test, seed_test  # type: ignore[import-untyped]

from dune_imperium.adapters.pettingzoo_env import env


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
