"""Tests for the lockstep self-play runner and batched policies."""

from collections.abc import Sequence

import numpy as np
import pytest

from dune_imperium import RulesetConfig
from dune_imperium.adapters.observation_encoding import OBSERVATION_SIZE
from dune_imperium.cli.selfplay import main as selfplay_main
from dune_imperium.training import (
    UNDO_ACTION_IDS,
    AgentBatchPolicy,
    PolicyRequest,
    RandomBatchPolicy,
    SelfPlayRunner,
    SelfPlaySpec,
    TrainingBatch,
    apply_step_penalty,
    stack_episodes,
    without_undo_actions,
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
            assert step.legal.dtype == np.int32
            assert step.action in step.legal.tolist()
            assert step.legal.shape[0] <= runner.codec.size
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

    batch = stack_episodes(result.episodes, action_size=runner.codec.size)

    total = result.decisions
    assert batch.observations.shape == (total, OBSERVATION_SIZE)
    assert batch.action_size == runner.codec.size
    assert batch.legal_offsets.shape == (total + 1,)
    assert int(batch.legal_offsets[-1]) == batch.legal_indices.shape[0]
    # The compressed form materializes exactly the dense mask it replaced.
    dense = batch.dense_masks(np.arange(total))
    assert dense.shape == (total, runner.codec.size)
    assert dense[np.arange(total), batch.actions] .all()
    assert int(dense.sum()) == batch.legal_indices.shape[0]
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
        stack_episodes((), action_size=runner.codec.size)


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


def test_dense_masks_reproduce_the_mask_the_policy_was_offered() -> None:
    """The compressed legal set must be the dense mask, exactly.

    A dropped or invented legal action is a training-correctness bug, not a
    memory bug: the learner's log-probabilities are computed over this mask,
    so it has to be the set the collecting policy actually chose from.
    """

    runner = SelfPlayRunner(RulesetConfig())
    result = runner.run({"r": RandomBatchPolicy(seed=11)}, _specs("r", (21, 22)))
    batch = stack_episodes(result.episodes, action_size=runner.codec.size)

    steps = [step for episode in result.episodes for step in episode.steps]
    rows = np.arange(len(steps))
    dense = batch.dense_masks(rows)
    for row, step in enumerate(steps):
        expected = np.zeros(runner.codec.size, dtype=np.int8)
        expected[step.legal] = 1
        assert np.array_equal(dense[row], expected)
        # The chosen action is always inside its own mask.
        assert dense[row, batch.actions[row]] == 1

    # Any row order, and any subset, materializes the same rows.
    shuffled = np.asarray([3, 0, len(steps) - 1, 1], dtype=np.int64)
    assert np.array_equal(batch.dense_masks(shuffled), dense[shuffled])
    assert np.array_equal(
        batch.dense_masks(np.zeros(0, dtype=np.int64)),
        np.zeros((0, runner.codec.size), dtype=np.int8),
    )


def test_step_penalty_charges_each_seats_later_decisions() -> None:
    batch = TrainingBatch(
        observations=np.zeros((5, 3), dtype=np.int32),
        legal_indices=np.tile(np.asarray([0, 1], dtype=np.int32), 5),
        legal_offsets=np.arange(6, dtype=np.int64) * 2,
        action_size=2,
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


def test_without_undo_actions_never_empties_the_legal_set() -> None:
    from dune_imperium.core.actions import DomainAction

    deploy = DomainAction("deploy_troops", actor=0, arguments=(("count", 1),))
    finish = DomainAction("finish_agent_turn", actor=0)
    withdraw = DomainAction("withdraw_troops", actor=0, arguments=(("count", 1),))
    commanders = DomainAction(
        "withdraw_commanders", actor=0, arguments=(("count", 1),)
    )

    assert {"withdraw_troops", "withdraw_commanders"} == UNDO_ACTION_IDS
    assert without_undo_actions((deploy, withdraw, finish, commanders)) == (
        deploy,
        finish,
    )
    assert without_undo_actions((deploy, finish)) == (deploy, finish)
    # Nothing else legal: the undo actions stay rather than leaving no move.
    assert without_undo_actions((withdraw, commanders)) == (withdraw, commanders)


class _EagerDeployer:
    """Deploy whenever offered (so a withdrawal becomes legal), else random.

    Records what the runner offered against the engine's own legal set.
    """

    def __init__(self, seed: int) -> None:
        self.inner = RandomBatchPolicy(seed=seed)
        self.offered_undo = 0
        self.engine_had_undo = 0
        self.engine = SelfPlayRunner(RulesetConfig(), record=False)._engine(None)

    def act(self, requests: Sequence[PolicyRequest]) -> Sequence[int]:
        answers = list(self.inner.act(requests))
        for row, request in enumerate(requests):
            full = self.engine.legal_actions(request.state, request.seat)
            assert set(request.legal_actions) <= set(full)
            assert request.mask.sum() == len(request.legal_indices)
            self.engine_had_undo += any(a.action_id in UNDO_ACTION_IDS for a in full)
            self.offered_undo += any(
                a.action_id in UNDO_ACTION_IDS for a in request.legal_actions
            )
            for action, index in zip(
                request.legal_actions, request.legal_indices, strict=True
            ):
                if action.action_id == "deploy_troops":
                    answers[row] = index
                    break
        return tuple(answers)


def test_runner_withholds_undo_actions_from_policies_not_from_the_engine() -> None:
    # OQ-029 (docs/rules/open-questions.md): this turn's basic deployment may
    # be taken back until finish_agent_turn, so deploying makes
    # withdraw_troops legal in the engine. Training withholds that pure-undo
    # action from the policy (docs/rl-environment.md) without changing what
    # the engine accepts.
    withheld = _EagerDeployer(seed=5)
    runner = SelfPlayRunner(RulesetConfig(), max_steps=400, undo_actions=False)
    result = runner.run({"p": withheld}, _specs("p", (11,)))

    assert withheld.engine_had_undo > 0, "the scenario never made a withdrawal legal"
    assert withheld.offered_undo == 0
    undo_indices = [
        index
        for index, template in enumerate(runner.codec.catalog)
        if template.action_id in UNDO_ACTION_IDS
    ]
    assert undo_indices
    for step in result.episodes[0].steps:
        # The recorded mask is the offered set, so a learner stays on-policy.
        assert not set(undo_indices) & set(step.legal.tolist())
        assert step.action in step.legal.tolist()

    # The default runner still offers them (baselines, throughput tools).
    offered = _EagerDeployer(seed=5)
    SelfPlayRunner(RulesetConfig(), max_steps=400).run(
        {"p": offered}, _specs("p", (11,))
    )
    assert offered.offered_undo > 0
