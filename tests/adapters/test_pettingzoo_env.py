"""PettingZoo API, episode, and information-boundary tests."""

import numpy as np
import pytest
from pettingzoo.test import api_test, seed_test  # type: ignore[import-untyped]

from dune_imperium.adapters.observation_encoding import (
    OBSERVATION_SIZE,
    OBSERVATION_VERSION,
)
from dune_imperium.adapters.pettingzoo_env import (
    LOSER_REWARD,
    WINNER_REWARD,
    DuneImperiumUprisingEnv,
    env,
)


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
    assert observation["observation"].shape == (OBSERVATION_SIZE,)
    assert observation["action_mask"].sum() > 0
    assert terminated is False
    assert truncated is False
    assert info == {"observation_version": OBSERVATION_VERSION}


def _play_episode(
    environment: DuneImperiumUprisingEnv,
    seed: int,
) -> tuple[dict[str, float], dict[str, dict[str, int]], int]:
    environment.reset(seed=seed)
    rng = np.random.default_rng(seed)
    terminal_rewards: dict[str, float] = {}
    infos: dict[str, dict[str, int]] = {}
    steps = 0
    for agent in environment.agent_iter(max_iter=200_000):
        observation, reward, termination, truncation, info = environment.last()
        if termination or truncation:
            terminal_rewards[agent] = reward
            infos[agent] = dict(info)
            environment.step(None)
            continue
        assert observation is not None
        legal = np.flatnonzero(observation["action_mask"])
        assert legal.size > 0
        environment.step(int(rng.choice(legal)))
        steps += 1
    return terminal_rewards, infos, steps


def test_full_game_episode_ends_with_zero_sum_winner_take_all_rewards() -> None:
    environment = env()
    terminal_rewards, infos, steps = _play_episode(environment, seed=3)

    assert set(terminal_rewards) == set(environment.possible_agents)
    assert steps < environment.max_steps
    values = sorted(terminal_rewards.values(), reverse=True)
    assert values[0] == pytest.approx(WINNER_REWARD)
    assert values[1:] == [pytest.approx(LOSER_REWARD)] * 3
    assert sum(terminal_rewards.values()) == pytest.approx(0.0)

    ranks = {agent: info["rank"] for agent, info in infos.items()}
    assert sorted(ranks.values()) == [1, 2, 3, 4]
    winner = next(agent for agent, rank in ranks.items() if rank == 1)
    assert terminal_rewards[winner] == pytest.approx(WINNER_REWARD)
    assert all("victory_points" in info for info in infos.values())


def test_choam_full_game_episode_completes() -> None:
    environment = env(choam_module=True)
    terminal_rewards, infos, _ = _play_episode(environment, seed=4)

    assert sum(terminal_rewards.values()) == pytest.approx(0.0)
    assert sorted(info["rank"] for info in infos.values()) == [1, 2, 3, 4]


def test_step_limit_truncates_without_rewards() -> None:
    environment = env(max_steps=5)
    terminal_rewards, infos, steps = _play_episode(environment, seed=8)

    assert steps == 5
    assert all(reward == 0.0 for reward in terminal_rewards.values())
    assert all("rank" not in info for info in infos.values())
    assert all(environment.truncations.values())
