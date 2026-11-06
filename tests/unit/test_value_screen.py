"""The offline leaf-value screen for the search seat (``evaluation.value_screen``)."""

from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.adapters.action_codec import ActionCodec  # noqa: E402
from dune_imperium.agents.network_search_agent import (  # noqa: E402
    NetworkSearchAgent,
    SearchResult,
)
from dune_imperium.evaluation import value_screen  # noqa: E402
from dune_imperium.evaluation.tournament import tournament_specs  # noqa: E402
from dune_imperium.evaluation.value_screen import (  # noqa: E402
    Leaves,
    RecordingSearchAgent,
    _as_leaves,
    decision_scores,
    leaf_values,
    load_leaves,
    paired_difference,
    record_leaves,
    save_leaves,
    screen,
    search_pick,
    value_network,
)
from dune_imperium.training.checkpoint import save_checkpoint  # noqa: E402
from dune_imperium.training.network import PolicyValueNetwork  # noqa: E402

_RULES = RulesetConfig()


def test_the_pick_keeps_the_first_candidate_inside_the_flip_margin() -> None:
    values = np.array([[0.10, 0.12, 0.05], [0.10, 0.12, 0.30]])
    # Totals 0.20, 0.24, 0.35: the third leads by 0.075 a world.
    assert search_pick(values, 0.0) == 2
    assert search_pick(values, 0.07) == 2
    assert search_pick(values, 0.08) == 0
    # A tie goes to the first of the tied candidates.
    assert search_pick(np.array([[0.0, 0.2, 0.2]]), 0.0) == 1


def _leaves(matrices: list[np.ndarray], finished: list[np.ndarray]) -> Leaves:
    """Leaves with no observations: every value comes from the matrices."""

    flat = np.concatenate([matrix.ravel() for matrix in matrices])
    done = np.concatenate([mask.ravel() for mask in finished])
    offsets = np.cumsum([0, *(matrix.size for matrix in matrices)])
    return Leaves(
        shapes=np.array([matrix.shape for matrix in matrices], dtype=np.int64),
        offsets=offsets.astype(np.int64),
        finished=done,
        rewards=np.where(done, flat, np.nan),
        recorded=flat,
        obs_columns=np.zeros(0, np.uint16),
        obs_values=np.zeros(0, np.int16),
        obs_offsets=np.zeros(flat.size + 1, np.int64),
        chosen=np.array([search_pick(m, 0.01) for m in matrices], dtype=np.int64),
        games=np.zeros(len(matrices), dtype=np.int64),
    )


def test_a_network_is_scored_by_the_picks_and_gaps_it_shares_with_the_reference() -> (
    None
):
    reference = [
        np.array([[0.2, 0.1], [0.2, 0.1]]),  # the first by 0.1
        np.array([[0.0, 0.3, 0.1], [0.0, 0.3, 0.1]]),  # the second by 0.3
    ]
    mine = [
        np.array([[0.2, 0.1], [0.2, 0.1]]),  # agrees
        np.array([[0.0, 0.1, 0.3], [0.0, 0.1, 0.3]]),  # picks the third
    ]
    leaves = _leaves(reference, [np.zeros(m.shape, bool) for m in reference])
    flat = np.concatenate([matrix.ravel() for matrix in mine])
    scores = decision_scores(leaves, flat, leaves.recorded, flip_margin=0.01)
    assert scores.picks.tolist() == [0, 2]
    assert scores.agree.tolist() == [1.0, 0.0]
    # The reference rates its pick 0.3 and the third candidate 0.1.
    assert scores.regret == pytest.approx([0.0, 0.2])
    # Gaps to the first: (0.1, 0.3) against the reference's (0.3, 0.1).
    assert scores.gap_error == pytest.approx([0.0, 0.04])
    result = screen(scores)
    assert result.agreement == 0.5 and result.regret == pytest.approx(0.1)
    assert result.gap_rmse == pytest.approx(np.sqrt(0.02))
    same = screen(
        decision_scores(leaves, leaves.recorded, leaves.recorded, flip_margin=0.01)
    )
    assert (same.agreement, same.regret, same.gap_rmse, same.leaf_rmse) == (1, 0, 0, 0)


def test_a_paired_difference_resamples_the_same_decisions() -> None:
    first = np.array([1.0, 1.0, 0.0, 1.0])
    second = np.array([1.0, 0.0, 0.0, 0.0])
    mean, low, high = paired_difference(first, second, draws=2000, seed=1)
    assert mean == 0.5 and 0.0 <= low <= mean <= high <= 1.0
    with pytest.raises(ValueError, match="same decisions"):
        paired_difference(first, second[:3])


def _checkpoint(tmp_path: Path) -> str:
    torch.manual_seed(0)
    network = PolicyValueNetwork(ActionCodec(_RULES).size, hidden=(16,))
    path = tmp_path / "policy.pt"
    save_checkpoint(path, network, ruleset=_RULES.identifier, iteration=1)
    return str(path)


def _first_searches(
    spec: object, kind: str, monkeypatch: pytest.MonkeyPatch, *, record: bool
) -> tuple[list[SearchResult], RecordingSearchAgent | None]:
    """The search seat's first eight searched decisions of ``spec``, played
    by the recorder or by a plain seat of the same seed and options."""

    results: list[SearchResult] = []
    searched = NetworkSearchAgent.search_with_state

    def stop_after_eight(agent, state, observation, legal):  # type: ignore[no-untyped-def]
        result = searched(agent, state, observation, legal)
        if result.searched:
            results.append(result)
            if len(results) == 8:
                raise _Enough(agent)
        return result

    monkeypatch.setattr(NetworkSearchAgent, "search_with_state", stop_after_eight)
    if not record:
        monkeypatch.setattr(value_screen, "RecordingSearchAgent", NetworkSearchAgent)
    with pytest.raises(_Enough) as stopped:
        record_leaves(spec, kind)  # type: ignore[arg-type]
    monkeypatch.undo()
    agent = stopped.value.agent
    return results, agent if isinstance(agent, RecordingSearchAgent) else None


def test_recorded_leaves_rate_back_to_the_seat_s_own_values_and_choices(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _checkpoint(tmp_path)
    kind = f"search:{path}::flip=0.01"
    spec = tournament_specs(
        agents=(kind, "heuristic", "heuristic", "heuristic"), games=1, start_seed=3
    )[0]
    results, recorder = _first_searches(spec, kind, monkeypatch, record=True)
    # The eighth stopped the game before the recorder kept it.
    assert recorder is not None
    assert [result for result, _ in recorder.searched] == results[:7]
    # Recording changes nothing: a plain seat searches the same.
    plain, _ = _first_searches(spec, kind, monkeypatch, record=False)
    assert plain == results

    leaves = _as_leaves(recorder.searched, [0] * len(recorder.searched))
    assert leaves.decisions == 7
    # Every playout end is kept, world by world, with the seat's own value.
    for decision, (result, _) in enumerate(recorder.searched):
        matrix = leaves.matrix(leaves.recorded, decision)
        assert matrix.tolist() == [list(row) for row in result.values]
        assert search_pick(matrix, 0.01) == leaves.chosen[decision]
        assert result.candidates[int(leaves.chosen[decision])] == result.chosen
    assert (~leaves.finished).all()
    rated = leaf_values(value_network(path, _RULES), leaves)
    assert np.allclose(rated, leaves.recorded, rtol=0, atol=1e-5)

    save_leaves(leaves, tmp_path / "a.npz")
    save_leaves(leaves, tmp_path / "b.npz")
    both = load_leaves([tmp_path / "a.npz", tmp_path / "b.npz"])
    assert both.decisions == 14 and both.games.tolist() == [0] * 7 + [1] * 7
    every = np.arange(int(both.offsets[-1]))
    half = int(leaves.offsets[-1])
    assert np.array_equal(
        both.observations(every[half:]), leaves.observations(every[:half])
    )
    assert np.array_equal(both.recorded[half:], leaves.recorded)


class _Enough(Exception):
    def __init__(self, agent: RecordingSearchAgent) -> None:
        super().__init__("enough decisions")
        self.agent = agent


def test_the_recorder_refuses_sequential_halving(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="every candidate in every world"):
        RecordingSearchAgent(_checkpoint(tmp_path), seed=0, halving=2, config=_RULES)
