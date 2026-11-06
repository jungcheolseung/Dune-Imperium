"""The self-play runner's stage-3 additions (docs/entity-self-play-plan.md 4.3).

The graded reward, each decision's round, every seat's round starts (the
states a search leaf is read at) and dealt Leaders under a drafting ruleset.
"""

from collections.abc import Sequence

import numpy as np
import pytest

from dune_imperium import RulesetConfig
from dune_imperium.adapters.pettingzoo_env import graded_reward
from dune_imperium.content.rulesets import content_for
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.training import (
    RandomBatchPolicy,
    SelfPlayRunner,
    SelfPlaySpec,
    stack_episodes,
)
from dune_imperium.training.policy import encoded_view, without_undo_actions
from dune_imperium.training.selfplay import Episode, apply_step_penalty

_DRAFT = RulesetConfig(leader_draft=True)


def _specs(seeds: Sequence[int]) -> tuple[SelfPlaySpec, ...]:
    return tuple(SelfPlaySpec(game_seed=seed, lineup=("r",) * 4) for seed in seeds)


def test_the_graded_reward_pays_by_place() -> None:
    specs = _specs((31, 32))
    plain = SelfPlayRunner(RulesetConfig()).run({"r": RandomBatchPolicy(seed=3)}, specs)
    graded = SelfPlayRunner(RulesetConfig(), reward_step=1 / 6).run(
        {"r": RandomBatchPolicy(seed=3)}, specs
    )
    assert [e.ranks for e in graded.episodes] == [e.ranks for e in plain.episodes]
    for episode in graded.episodes:
        assert episode.rewards == pytest.approx(
            tuple(graded_reward(rank, 1 / 6) for rank in episode.ranks)
        )
        assert sum(episode.rewards) == pytest.approx(0.0)
    with pytest.raises(ValueError, match="exclusive"):
        SelfPlayRunner(RulesetConfig(), rank_rewards=True, reward_step=0.1)


def _replay(
    config: RulesetConfig,
    episode: Episode,
    leader_ids: tuple[str, ...] | None = None,
    afters: list[int] | None = None,
) -> tuple[list[tuple[int, int, np.ndarray]], list[int], GameState]:
    """Play the episode's recorded actions again; return every seat's view at
    each round start, each decision's round and the first state.

    A decision's round is kept as (its round, the round of the last start
    before it) when ``afters`` is given.
    """

    engine = (
        UprisingRulesEngine(leader_ids=leader_ids)
        if leader_ids is not None
        else UprisingRulesEngine()
    )
    runner = SelfPlayRunner(config)
    state = engine.reset(config, episode.game_seed)
    first = state
    chance = ChanceResolver(seed=episode.game_seed)
    starts: list[tuple[int, int, np.ndarray]] = []
    rounds: list[int] = []
    reached = 0
    steps = iter(episode.steps)
    while state.phase is not GamePhase.FINISHED:
        if state.round_number > reached and state.phase is not GamePhase.ROUND_START:
            reached = state.round_number
            starts.extend(
                (state.round_number, seat, encoded_view(engine.observe(state, seat)))
                for seat in range(4)
            )
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        step = next(steps)
        legal = engine.legal_actions(state, decision.owner)
        offered = without_undo_actions(legal)
        action = next(a for a in offered if runner.codec.encode(a) == step.action)
        rounds.append(state.round_number)
        if afters is not None:
            afters.append(reached)
        state = engine.apply(state, action, legal_actions=legal).state
    return starts, rounds, first


def test_round_starts_are_the_states_a_leaf_is_read_at() -> None:
    runner = SelfPlayRunner(_DRAFT, undo_actions=False, record_round_starts=True)
    (episode,) = runner.run({"r": RandomBatchPolicy(seed=4)}, _specs((41,))).episodes
    assert not episode.truncated
    afters: list[int] = []
    starts, rounds, _ = _replay(_DRAFT, episode, afters=afters)
    assert len(episode.round_starts) == len(starts)
    for kept, (round_number, seat, observation) in zip(
        episode.round_starts, starts, strict=True
    ):
        assert (kept.round_number, kept.seat) == (round_number, seat)
        assert np.array_equal(kept.observation, observation)
    assert [start.round_number for start in episode.round_starts[::4]] == list(
        range(1, len(starts) // 4 + 1)
    )
    assert [step.round_number for step in episode.steps] == rounds
    # Round 0 holds the draft; the batch keeps every step's round.
    assert episode.steps[0].round_number == 0
    batch = stack_episodes([episode], action_size=runner.codec.size)
    assert batch.rounds is not None and batch.rounds.tolist() == rounds
    assert apply_step_penalty(batch, 0.001).rounds is batch.rounds
    # Each step names the last round start before it: 0 in the draft, then
    # its own round, or the round before in a Round Start phase.
    assert [step.after_start for step in episode.steps] == afters
    assert afters[0] == 0 and max(afters) == len(starts) // 4
    assert all(r - 1 <= a <= r for a, r in zip(afters, rounds, strict=True))
    assert batch.after_starts is not None and batch.after_starts.tolist() == afters
    assert apply_step_penalty(batch, 0.001).after_starts is batch.after_starts
    # Off by default.
    plain = SelfPlayRunner(_DRAFT, undo_actions=False).run(
        {"r": RandomBatchPolicy(seed=4)}, _specs((41,))
    )
    assert plain.episodes[0].round_starts == ()
    assert {step.after_start for step in plain.episodes[0].steps} == {0}


def test_dealt_leaders_play_without_the_draft() -> None:
    undrafted = RulesetConfig()
    # The last four of the ruleset's Leaders: not the default four.
    leaders = tuple(leader.leader_id for leader in content_for(undrafted).leaders[-4:])
    spec = SelfPlaySpec(game_seed=43, lineup=("r",) * 4, leader_ids=leaders)
    runner = SelfPlayRunner(_DRAFT, undo_actions=False, record_round_starts=True)
    (episode,) = runner.run({"r": RandomBatchPolicy(seed=5)}, (spec,)).episodes
    _, rounds, first = _replay(undrafted, episode, leader_ids=leaders)
    assert tuple(player.leader_id for player in first.players) == leaders
    # No decision was taken before round 1: there was no draft.
    assert min(rounds) >= 1
    assert episode.round_starts[0].round_number == 1
