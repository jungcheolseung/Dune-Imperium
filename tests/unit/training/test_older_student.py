"""A student plays the learner seats while an older teacher labels them (E5).

Student-position distillation for the stage B retrain: the shard keeps the
teacher's distribution and value at every learner decision, but the moves
played -- and so the positions reached -- are the student's.
"""

from collections.abc import Sequence
from dataclasses import fields
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.adapters.action_codec import ActionCodec  # noqa: E402
from dune_imperium.training import older_distill  # noqa: E402
from dune_imperium.training.checkpoint import save_checkpoint  # noqa: E402
from dune_imperium.training.collect import LEARNER  # noqa: E402
from dune_imperium.training.entity_network import EntityNetwork  # noqa: E402
from dune_imperium.training.network import PolicyValueNetwork  # noqa: E402
from dune_imperium.training.older_distill import (  # noqa: E402
    older_shard,
    teacher_rows,
)
from dune_imperium.training.older_teacher import (  # noqa: E402
    NETWORK,
    OlderTeacher,
    OlderTeacherPolicy,
    load_older_network,
)
from dune_imperium.training.policy import (  # noqa: E402
    AgentBatchPolicy,
    PolicyRequest,
)
from dune_imperium.training.selfplay import (  # noqa: E402
    SelfPlayRunner,
    SelfPlaySpec,
)
from dune_imperium.training.teacher import TeacherData  # noqa: E402
from dune_imperium.training.torch_policy import TorchBatchPolicy  # noqa: E402

_RULES = RulesetConfig()
_SPECS = (
    SelfPlaySpec(game_seed=11, lineup=(LEARNER, "heuristic") * 2),
    SelfPlaySpec(game_seed=12, lineup=(LEARNER,) * 4),
)
_SEED = 3
_STEPS = 120


def _mlp(path: Path, seed: int) -> Path:
    """A small current-codec MLP checkpoint (a teacher or a student)."""

    codec = ActionCodec(_RULES)
    torch.manual_seed(seed)
    network = PolicyValueNetwork(codec.size, hidden=(16,))
    save_checkpoint(path, network, ruleset=_RULES.identifier, iteration=1, codec=codec)
    return path


def _highest_row_student(path: Path) -> Path:
    """A student that always plays its decision's highest catalog row.

    Its logits rise by 200 a row, so sampling at temperature 1 leaves every
    other legal row an exactly zero probability.
    """

    codec = ActionCodec(_RULES)
    network = PolicyValueNetwork(codec.size, hidden=(16,))
    with torch.no_grad():
        network.policy_head.weight.zero_()
        network.policy_head.bias.copy_(200.0 * torch.arange(codec.size))
    save_checkpoint(path, network, ruleset=_RULES.identifier, iteration=1, codec=codec)
    return path


def _shard(teacher: Path, student: Path | None, workers: int = 1) -> TeacherData:
    return older_shard(
        None,
        teacher,
        _RULES,
        _SPECS,
        first_game=40,
        workers=workers,
        opponent="heuristic",
        seed=_SEED,
        max_steps=_STEPS,
        student=student,
    )


def _row(data: TeacherData, name: str, row: int) -> np.ndarray:
    start, end = data.legal_offsets[row], data.legal_offsets[row + 1]
    values: np.ndarray = getattr(data, name)[start:end]
    return values


def test_a_student_shard_keeps_the_teachers_answer_at_every_learner_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    teacher_path = _mlp(tmp_path / "teacher.pt", seed=0)
    student_path = _mlp(tmp_path / "student.pt", seed=1)
    seen: list[tuple[PolicyRequest, int]] = []
    networks: list[PolicyValueNetwork] = []

    class Recording(TorchBatchPolicy):
        def act(self, requests: Sequence[PolicyRequest]) -> Sequence[int]:
            chosen = super().act(requests)
            seen.extend(zip(requests, chosen, strict=True))
            networks.append(self.network)
            return chosen

    monkeypatch.setattr(older_distill, "TorchBatchPolicy", Recording)
    data = _shard(teacher_path, student_path)

    # The student sampled the file it was given.
    saved = torch.load(student_path, weights_only=True)["state_dict"]
    assert torch.equal(networks[0].policy_head.weight, saved["policy_head.weight"])
    assert data.rows == len(seen) > 0
    # The teacher's answers again, asked in the order the run asked them (a
    # fallback heuristic per seat keeps its own stream).
    fresh = OlderTeacher(load_older_network(teacher_path), seed=_SEED)
    answers = [
        fresh.answer(
            request.state,
            request.seat,
            request.view,
            request.legal_actions,
            request.observation,
            key=(request.game, request.seat),
        )
        for request, _ in seen
    ]
    # The shard is in game order, each game's decisions in play order.
    order = sorted(range(len(seen)), key=lambda index: seen[index][0].game)
    for row, index in enumerate(order):
        request, chosen = seen[index]
        answer = answers[index]
        assert data.games[row] == 40 + request.game
        assert _row(data, "legal_indices", row).tolist() == list(request.legal_indices)
        assert _row(data, "teacher", row).astype(np.float64) == pytest.approx(
            answer.probabilities, abs=1e-3
        )
        assert data.values[row] == pytest.approx(answer.value, abs=1e-6)
        assert data.actions[row] == chosen  # the student's move
    assert any(answer.source == NETWORK for answer in answers)


def test_the_student_not_the_teacher_plays_the_learner_seats(
    tmp_path: Path,
) -> None:
    teacher_path = _mlp(tmp_path / "teacher.pt", seed=0)
    student_path = _highest_row_student(tmp_path / "student.pt")
    data = _shard(teacher_path, student_path, workers=2)
    highest = [_row(data, "legal_indices", row).max() for row in range(data.rows)]
    assert data.rows > 0
    assert set(np.unique(data.games).tolist()) == {40, 41}
    assert (data.actions == np.asarray(highest)).all()
    sums = np.add.reduceat(data.teacher.astype(np.float64), data.legal_offsets[:-1])
    assert sums == pytest.approx(np.ones(data.rows), abs=2e-3)
    assert np.isfinite(data.values).all()
    # The teacher, playing the same games itself, does not always pick so.
    played = _shard(teacher_path, None, workers=2)
    highest = [_row(played, "legal_indices", row).max() for row in range(played.rows)]
    assert not (played.actions == np.asarray(highest)).all()


def test_without_a_student_the_teacher_plays_as_before(tmp_path: Path) -> None:
    teacher_path = _mlp(tmp_path / "teacher.pt", seed=0)
    # The shard as ``play_job`` built it before a student could play.
    policy = OlderTeacherPolicy(
        OlderTeacher(load_older_network(teacher_path), seed=_SEED), _SEED
    )
    runner = SelfPlayRunner(_RULES, max_steps=_STEPS, record=True, undo_actions=False)
    opponent = AgentBatchPolicy("heuristic", _SEED + 1)
    result = runner.run({LEARNER: policy, "heuristic": opponent}, _SPECS)
    before = teacher_rows(
        result.episodes,
        policy.answers,
        ruleset=_RULES.identifier,
        action_size=ActionCodec(_RULES).size,
        games=(40, 41),
    )
    data = _shard(teacher_path, None)
    assert (data.ruleset, data.action_size) == (before.ruleset, before.action_size)
    for field in fields(TeacherData):
        if field.name in ("ruleset", "action_size"):
            continue
        mine, theirs = getattr(data, field.name), getattr(before, field.name)
        assert mine.dtype == theirs.dtype, field.name
        assert mine.tobytes() == theirs.tobytes(), field.name


def test_an_entity_student_plays_its_seats(tmp_path: Path) -> None:
    teacher_path = _mlp(tmp_path / "teacher.pt", seed=0)
    torch.manual_seed(2)
    student = EntityNetwork(
        _RULES, hidden=(8,), entity_width=8, seat_width=8, action_width=8
    )
    student_path = tmp_path / "entity.pt"
    save_checkpoint(
        student_path,
        student,
        ruleset=_RULES.identifier,
        iteration=1,
        codec=ActionCodec(_RULES),
    )
    data = older_shard(
        None,
        teacher_path,
        _RULES,
        _SPECS[:1],
        first_game=0,
        workers=1,
        opponent="heuristic",
        seed=_SEED,
        max_steps=40,
        student=student_path,
    )
    assert data.rows > 0
    index, valid, _ = data.legal(np.arange(data.rows))
    assert ((index == data.actions[:, None]) & valid).any(axis=1).all()
