"""Tests for the lockstep self-play runner and batched policies."""

from collections.abc import Sequence

import numpy as np
import pytest

from dune_imperium import RulesetConfig
from dune_imperium.adapters.observation_encoding import OBSERVATION_SIZE
from dune_imperium.cli.selfplay import main as selfplay_main
from dune_imperium.training import (
    AgentBatchPolicy,
    PolicyRequest,
    RandomBatchPolicy,
    SelfPlayRunner,
    SelfPlaySpec,
    TrainingBatch,
    apply_step_penalty,
    stack_episodes,
)


def _specs(policy: str, seeds: Sequence[int]) -> tuple[SelfPlaySpec, ...]:
    return tuple(SelfPlaySpec(game_seed=seed, lineup=(policy,) * 4) for seed in seeds)


def test_random_self_play_finishes_games_with_zero_sum_rewards() -> None:
    runner = SelfPlayRunner(RulesetConfig())
    result = runner.run({"r": RandomBatchPolicy(seed=5)}, _specs("r", (1, 2, 3)))

    assert [episode.game_seed for episode in result.episodes] == [1, 2, 3]
    assert result.decisions == sum(e.decisions for e in result.episodes)
    for episode in result.episodes:
        assert not episode.truncated
        assert episode.ruleset == "uprising-4p-base"
        assert episode.rounds >= 1
        assert sorted(episode.ranks) == [1, 2, 3, 4]
        assert episode.rewards.count(1.0) == 1
        assert sum(episode.rewards) == pytest.approx(0.0)
        assert episode.rewards[episode.ranks.index(1)] == 1.0
        assert len(episode.steps) == episode.decisions
        for step in episode.steps:
            assert step.observation.shape == (OBSERVATION_SIZE,)
            assert step.observation.dtype == np.int32
            assert step.mask.shape == (runner.codec.size,)
            assert step.mask[step.action] == 1
            assert 0 <= step.seat < 4

    # The same seeds and policy seed reproduce the same episodes.
    again = SelfPlayRunner(RulesetConfig()).run(
        {"r": RandomBatchPolicy(seed=5)}, _specs("r", (1, 2, 3))
    )
    assert [(e.ranks, e.decisions) for e in again.episodes] == [
        (e.ranks, e.decisions) for e in result.episodes
    ]


def test_stack_episodes_returns_the_acting_seats_reward() -> None:
    runner = SelfPlayRunner(RulesetConfig())
    result = runner.run({"r": RandomBatchPolicy(seed=1)}, _specs("r", (7, 8)))

    batch = stack_episodes(result.episodes)

    total = result.decisions
    assert batch.observations.shape == (total, OBSERVATION_SIZE)
    assert batch.masks.shape == (total, runner.codec.size)
    assert batch.actions.shape == (total,)
    assert batch.seats.shape == (total,)
    assert batch.returns.shape == (total,)
    assert batch.episode_ids.shape == (total,)
    assert set(batch.episode_ids.tolist()) == {0, 1}
    first = result.episodes[0]
    for step, seat, value in zip(
        first.steps,
        batch.seats[: first.decisions],
        batch.returns[: first.decisions],
        strict=True,
    ):
        assert seat == step.seat
        assert value == pytest.approx(first.rewards[step.seat])
    with pytest.raises(ValueError, match="no recorded steps"):
        stack_episodes(())


class _CountingPolicy:
    def __init__(self, inner: RandomBatchPolicy) -> None:
        self.inner = inner
        self.calls = 0
        self.seats: set[int] = set()
        self.largest_batch = 0

    def act(self, requests: Sequence[PolicyRequest]) -> Sequence[int]:
        self.calls += 1
        self.largest_batch = max(self.largest_batch, len(requests))
        self.seats.update(request.seat for request in requests)
        for request in requests:
            assert request.legal_actions
            assert len(request.legal_indices) == len(request.legal_actions)
            assert request.mask.sum() == len(request.legal_indices)
        return self.inner.act(requests)


def test_lineups_route_each_seat_to_its_policy_and_batch_across_games() -> None:
    odd = _CountingPolicy(RandomBatchPolicy(seed=1))
    even = _CountingPolicy(RandomBatchPolicy(seed=2))
    specs = tuple(
        SelfPlaySpec(game_seed=seed, lineup=("even", "odd", "even", "odd"))
        for seed in range(4)
    )

    result = SelfPlayRunner(RulesetConfig(), record=False).run(
        {"odd": odd, "even": even}, specs
    )

    assert odd.seats == {1, 3}
    assert even.seats == {0, 2}
    assert odd.largest_batch > 1
    assert all(episode.steps == () for episode in result.episodes)
    assert all(not episode.truncated for episode in result.episodes)


def test_truncation_pays_nothing_and_illegal_answers_are_rejected() -> None:
    runner = SelfPlayRunner(RulesetConfig(), max_steps=20)
    result = runner.run({"r": RandomBatchPolicy(seed=3)}, _specs("r", (1,)))
    episode = result.episodes[0]
    assert episode.truncated
    assert episode.decisions == 20
    assert episode.rewards == (0.0, 0.0, 0.0, 0.0)
    assert episode.ranks == (0, 0, 0, 0)

    class _Illegal:
        def act(self, requests: Sequence[PolicyRequest]) -> Sequence[int]:
            return tuple(
                next(i for i in range(len(request.mask)) if request.mask[i] == 0)
                for request in requests
            )

    with pytest.raises(ValueError, match="illegal action index"):
        SelfPlayRunner(RulesetConfig()).run({"x": _Illegal()}, _specs("x", (1,)))
    with pytest.raises(ValueError, match="unknown policy"):
        SelfPlayRunner(RulesetConfig()).run({}, _specs("x", (1,)))
    with pytest.raises(ValueError, match="one policy per seat"):
        SelfPlayRunner(RulesetConfig()).run(
            {"x": _Illegal()}, (SelfPlaySpec(game_seed=1, lineup=("x",)),)
        )


def test_agent_batch_policy_drives_baselines_including_search() -> None:
    heuristic = AgentBatchPolicy("heuristic", 10)
    runner = SelfPlayRunner(RulesetConfig())
    result = runner.run({"h": heuristic}, _specs("h", (4,)))
    episode = result.episodes[0]
    assert not episode.truncated
    assert episode.rewards.count(1.0) == 1

    # A StateAgent baseline receives the state through the request; a short
    # truncated run keeps the rollout search affordable here.
    rollout = AgentBatchPolicy("rollout", 20)
    short = SelfPlayRunner(RulesetConfig(), max_steps=12).run(
        {"rollout": rollout, "h": heuristic},
        (SelfPlaySpec(game_seed=4, lineup=("rollout", "h", "h", "h")),),
    )
    assert short.episodes[0].truncated
    assert short.episodes[0].decisions == 12
    with pytest.raises(ValueError, match="unknown agent kind"):
        AgentBatchPolicy("oracle", 1).act(
            [
                PolicyRequest(
                    game=0,
                    seat=0,
                    state=runner._engine(None).reset(RulesetConfig(), 1),
                    view=runner._engine(None).observe(
                        runner._engine(None).reset(RulesetConfig(), 1), 0
                    ),
                    legal_actions=(),
                    legal_indices=(),
                    observation=np.zeros(OBSERVATION_SIZE, dtype=np.int32),
                    mask=np.zeros(runner.codec.size, dtype=np.int8),
                )
            ]
        )


def test_selfplay_cli_reports_throughput(capsys: pytest.CaptureFixture[str]) -> None:
    assert selfplay_main(["--games", "2", "--policy", "random-batch"]) == 0
    output = capsys.readouterr().out
    assert "2/2 games finished" in output
    assert "decisions/s" in output
    assert "batch: observations" in output
    with pytest.raises(SystemExit):
        selfplay_main(["--policy", "oracle"])


def test_step_penalty_charges_each_seats_later_decisions() -> None:
    batch = TrainingBatch(
        observations=np.zeros((5, 3), dtype=np.int32),
        masks=np.ones((5, 2), dtype=np.int8),
        actions=np.zeros(5, dtype=np.int64),
        seats=np.asarray([0, 1, 0, 0, 1], dtype=np.int8),
        returns=np.asarray([1.0, -1 / 3, 1.0, 1.0, 2.0], dtype=np.float32),
        episode_ids=np.asarray([0, 0, 0, 0, 1], dtype=np.int32),
    )

    shaped = apply_step_penalty(batch, 0.1)

    # Seat 0 of episode 0 decides three times: 2, 1, 0 later decisions.
    assert shaped.returns.tolist() == pytest.approx(
        [1.0 - 0.2, -1 / 3, 1.0 - 0.1, 1.0, 2.0]
    )
    assert shaped.returns.dtype == np.float32
    assert apply_step_penalty(batch, 0.0) is batch
    with pytest.raises(ValueError, match="negative"):
        apply_step_penalty(batch, -0.1)
