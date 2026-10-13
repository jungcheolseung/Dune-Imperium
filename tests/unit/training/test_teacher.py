"""Teacher data and student training (docs/entity-network-plan.md stage P2)."""

from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.adapters.action_codec import ActionCodec  # noqa: E402
from dune_imperium.training.collect import (  # noqa: E402
    LEARNER,
    CollectionResult,
    Collector,
)
from dune_imperium.training.entity_network import EntityNetwork  # noqa: E402
from dune_imperium.training.network import PolicyValueNetwork  # noqa: E402
from dune_imperium.training.selfplay import SelfPlaySpec  # noqa: E402
from dune_imperium.training.teacher import (  # noqa: E402
    VP_SCALE,
    StudentConfig,
    TeacherData,
    build_teacher_data,
    concatenate,
    gather_rows,
    load_teacher_data,
    save_teacher_data,
    score_student,
    split_rows,
    train_student,
)

_RULES = RulesetConfig()


def _teacher() -> PolicyValueNetwork:
    """A small network with a peaked policy (a fresh one is nearly uniform)."""

    torch.manual_seed(0)
    network = PolicyValueNetwork(ActionCodec(_RULES).size, hidden=(16,))
    with torch.no_grad():
        network.policy_head.weight.mul_(30.0)
    return network.eval()


@pytest.fixture(scope="module")
def collected() -> list[tuple[CollectionResult, TeacherData]]:
    """Two collections of two teacher games each, and their teacher data."""

    teacher = _teacher()
    parts = []
    with Collector(_RULES, workers=1) as collector:
        for part in range(2):
            specs = tuple(
                SelfPlaySpec(game_seed=40 + 2 * part + game, lineup=(LEARNER,) * 4)
                for game in range(2)
            )
            result = collector.collect(
                teacher,
                torch.device("cpu"),
                specs,
                policy_seed=part,
                opponent_seed=part,
            )
            data = build_teacher_data(
                result, teacher, ruleset=_RULES.identifier, first_game=2 * part
            )
            parts.append((result, data))
    return parts


def test_gather_rows_takes_rows_in_the_order_given() -> None:
    values = np.arange(10)
    offsets = np.array([0, 3, 3, 7, 10])
    gathered, new_offsets = gather_rows(values, offsets, np.array([3, 1, 0, 2]))
    assert gathered.tolist() == [7, 8, 9, 0, 1, 2, 3, 4, 5, 6]
    assert new_offsets.tolist() == [0, 3, 3, 6, 10]
    empty, empty_offsets = gather_rows(values, offsets, np.array([1]))
    assert empty.shape == (0,) and empty_offsets.tolist() == [0, 0]


def test_teacher_data_keeps_every_decision_with_its_distribution(
    collected: list[tuple[CollectionResult, TeacherData]], tmp_path: Path
) -> None:
    teacher = _teacher()
    result, data = collected[0]
    batch = result.batch
    rows = np.arange(data.rows)
    assert data.rows == batch.observations.shape[0]
    assert np.array_equal(data.observations(rows), batch.observations)
    assert np.array_equal(data.actions, batch.actions)
    # The teacher's distribution over the offered actions.
    index, valid, target = data.legal(rows)
    np.testing.assert_allclose(target.sum(axis=1), 1.0, atol=5e-3)
    sample = np.arange(0, data.rows, max(1, data.rows // 7))
    with torch.no_grad():
        hidden = teacher.trunk(torch.from_numpy(batch.observations[sample]))
        for position, row in enumerate(sample):
            offered = torch.from_numpy(index[row, valid[row]])
            expected = torch.softmax(
                teacher.action_logits(hidden[position : position + 1], offered)[0], 0
            )
            np.testing.assert_allclose(
                target[row, valid[row]], expected.numpy(), atol=2e-3
            )
    # Every seat's final VP, the acting seat first, then the seats after it.
    for row in sample:
        episode = result.episodes[int(batch.episode_ids[row])]
        seat = int(batch.seats[row])
        assert data.victory_points[row].tolist() == [
            episode.victory_points[(seat + k) % 4] for k in range(4)
        ]
        assert data.returns[row] == episode.rewards[seat]
    assert set(data.games.tolist()) == {0, 1}
    assert set(collected[1][1].games.tolist()) == {2, 3}

    save_teacher_data(data, tmp_path / "part.npz")
    loaded = load_teacher_data(tmp_path / "part.npz")
    assert loaded.ruleset == data.ruleset and loaded.action_size == data.action_size
    for name in ("obs_columns", "obs_offsets", "legal_indices", "teacher", "games"):
        assert np.array_equal(getattr(loaded, name), getattr(data, name)), name


def test_concatenated_parts_read_like_the_parts(
    collected: list[tuple[CollectionResult, TeacherData]],
) -> None:
    first, second = (data for _, data in collected)
    joined = concatenate([first, second])
    assert joined.rows == first.rows + second.rows
    tail = np.arange(first.rows, joined.rows)
    own = np.arange(second.rows)
    assert np.array_equal(joined.observations(tail), second.observations(own))
    for left, right in zip(joined.legal(tail), second.legal(own), strict=True):
        assert np.array_equal(left, right)
    assert np.array_equal(joined.victory_points[tail], second.victory_points)
    train, heldout = split_rows(joined, 2)
    assert set(joined.games[heldout].tolist()) == {0, 2}
    assert set(joined.games[train].tolist()) == {1, 3}


@pytest.mark.parametrize("arch", ["entity", "mlp"])
def test_a_student_learns_the_teacher_and_keeps_its_best_epoch(
    collected: list[tuple[CollectionResult, TeacherData]], arch: str
) -> None:
    data = concatenate([part for _, part in collected])
    torch.manual_seed(1)
    student: PolicyValueNetwork
    if arch == "entity":
        student = EntityNetwork(
            _RULES,
            hidden=(32,),
            entity_width=16,
            seat_width=32,
            action_width=16,
            aux_vp=True,
        )
    else:
        student = PolicyValueNetwork(data.action_size, hidden=(32,))
    config = StudentConfig(
        learning_rate=3e-3,
        warmup_steps=5,
        minibatch_size=64,
        epochs=3,
        heldout_modulus=2,
        threads=1,
    )
    train_rows, heldout_rows = split_rows(data, config.heldout_modulus)
    before = score_student(student, data, train_rows)
    history = train_student(student, data, config)
    after = score_student(student, data, train_rows)
    assert [record.epoch for record in history] == [1, 2, 3]
    # The distance to the teacher (cross-entropy above its entropy) halves.
    assert after.teacher_entropy < 0.5 * before.cross_entropy
    distance = after.cross_entropy - after.teacher_entropy
    assert distance < 0.5 * (before.cross_entropy - before.teacher_entropy)
    assert after.agreement > before.agreement
    assert after.value_mse < before.value_mse
    # The network ends holding the best held-out epoch.
    final = score_student(student, data, heldout_rows)
    best = min(record.heldout.cross_entropy for record in history)
    assert final.cross_entropy == pytest.approx(best, rel=1e-5)
    assert 0.0 <= final.agreement <= 1.0
    assert final.teacher_entropy <= final.cross_entropy + 1e-6
    if arch == "entity":
        assert all(record.vp_loss is not None for record in history)
        assert after.vp_mse is not None and before.vp_mse is not None
        assert after.vp_mse < before.vp_mse
        assert np.abs(data.victory_points / VP_SCALE).max() < 3.0
    else:
        assert all(record.vp_loss is None for record in history)
        assert after.vp_mse is None
