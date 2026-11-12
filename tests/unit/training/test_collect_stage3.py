"""The collector's stage-3 additions (docs/entity-self-play-plan.md 4.3).

Several opponent kinds in one collection, the graded reward, each step's
round, and the learner seats' round starts, serial and over workers.
"""

from collections import defaultdict

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.adapters.action_codec import ActionCodec  # noqa: E402
from dune_imperium.adapters.pettingzoo_env import graded_reward  # noqa: E402
from dune_imperium.training.collect import (  # noqa: E402
    LEARNER,
    CollectionResult,
    Collector,
)
from dune_imperium.training.network import PolicyValueNetwork  # noqa: E402
from dune_imperium.training.selfplay import SelfPlaySpec  # noqa: E402

_CONFIG = RulesetConfig()
_SPECS = (
    SelfPlaySpec(game_seed=61, lineup=(LEARNER,) * 4),
    SelfPlaySpec(game_seed=62, lineup=(LEARNER, "heuristic", LEARNER, "random")),
    SelfPlaySpec(game_seed=63, lineup=("random", LEARNER, "heuristic", LEARNER)),
)


def _network() -> PolicyValueNetwork:
    torch.manual_seed(0)
    return PolicyValueNetwork(ActionCodec(_CONFIG).size, hidden=(16,)).eval()


def _check(result: CollectionResult) -> None:
    episodes = result.episodes
    batch = result.batch
    assert batch.rounds is not None and batch.rounds.shape == batch.actions.shape
    after = batch.after_starts
    assert after is not None and after.shape == batch.actions.shape
    assert bool(np.all((after <= batch.rounds) & (after >= batch.rounds - 1)))
    for row, (episode_id, seat) in enumerate(
        zip(batch.episode_ids.tolist(), batch.seats.tolist(), strict=True)
    ):
        episode = episodes[episode_id]
        assert episode.lineup[seat] == LEARNER
        assert batch.returns[row] == pytest.approx(
            graded_reward(episode.ranks[seat], 1 / 6)
        )
    starts = result.round_starts
    assert starts is not None
    by_seat: dict[tuple[int, int], list[int]] = defaultdict(list)
    for episode_id, seat, round_number in zip(
        starts.episode_ids.tolist(),
        starts.seats.tolist(),
        starts.rounds.tolist(),
        strict=True,
    ):
        assert episodes[episode_id].lineup[seat] == LEARNER
        by_seat[(episode_id, seat)].append(round_number)
    learner_seats = {
        (index, seat)
        for index, episode in enumerate(episodes)
        for seat, name in enumerate(episode.lineup)
        if name == LEARNER
    }
    assert set(by_seat) == learner_seats
    for (episode_id, _), rounds in by_seat.items():
        assert rounds == list(range(1, len(rounds) + 1))
        assert max(rounds) <= episodes[episode_id].rounds
        # A decision's round never runs past the seat's last round start.
        mine = batch.rounds[batch.episode_ids == episode_id]
        assert int(mine.max()) <= max(rounds)
    assert starts.observations.shape[0] == starts.seats.shape[0]
    assert starts.observations.dtype == np.int32


@pytest.mark.parametrize("workers", [1, 2])
def test_a_mixed_collection_returns_rounds_and_round_starts(workers: int) -> None:
    with Collector(
        _CONFIG, workers=workers, reward_step=1 / 6, record_round_starts=True
    ) as collector:
        result = collector.collect(
            _network(),
            torch.device("cpu"),
            _SPECS,
            policy_seed=5,
            opponent_seed=6,
            opponents=("heuristic", "random"),
        )
    assert sorted(episode.game_seed for episode in result.episodes) == [61, 62, 63]
    _check(result)
    if workers > 1:
        assert all(episode.round_starts == () for episode in result.episodes)


def test_without_round_starts_nothing_extra_is_kept() -> None:
    with Collector(_CONFIG) as collector:
        result = collector.collect(
            _network(),
            torch.device("cpu"),
            _SPECS[:1],
            policy_seed=5,
            opponent_seed=6,
        )
    assert result.round_starts is None
    assert all(episode.round_starts == () for episode in result.episodes)


def test_the_atomics_rule_names_every_network_opponent() -> None:
    collector = Collector(_CONFIG, family_atomics="app", opponent="checkpoint:a.pt")
    assert collector._atomics_rule(("checkpoint:b.pt", "app_ai")) == frozenset(
        {LEARNER, "checkpoint:a.pt", "checkpoint:b.pt"}
    )
    assert Collector(_CONFIG)._atomics_rule(("checkpoint:b.pt",)) == frozenset()
