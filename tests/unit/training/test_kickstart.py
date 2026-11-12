"""Kickstarting: a decaying KL(teacher || student) term in the RL loop (E6)."""

import copy
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.adapters.action_codec import ActionCodec  # noqa: E402
from dune_imperium.cli.train import main as train_main  # noqa: E402
from dune_imperium.core.actions import DomainAction  # noqa: E402
from dune_imperium.training import SelfPlaySpec, TrainingBatch  # noqa: E402
from dune_imperium.training.checkpoint import (  # noqa: E402
    load_checkpoint,
    save_checkpoint,
)
from dune_imperium.training.collect import LEARNER, Collector  # noqa: E402
from dune_imperium.training.kickstart import (  # noqa: E402
    kickstart_weight,
    teacher_column,
)
from dune_imperium.training.learner import Learner, LearnerConfig  # noqa: E402
from dune_imperium.training.loop import TrainConfig  # noqa: E402
from dune_imperium.training.network import PolicyValueNetwork  # noqa: E402
from dune_imperium.training.older_teacher import (  # noqa: E402
    NETWORK,
    OlderTeacher,
    TeacherAnswer,
)

_CPU = torch.device("cpu")
_RULES = RulesetConfig()
_WIDTH = 64  # the synthetic rows' observation width
_ARRAYS = (
    "observations",
    "legal_indices",
    "legal_offsets",
    "actions",
    "seats",
    "returns",
    "episode_ids",
)


def test_the_weight_falls_linearly_from_its_start_to_zero_and_stays_there() -> None:
    weights = [kickstart_weight(1.0, 4, step) for step in range(7)]
    assert weights == [1.0, 0.75, 0.5, 0.25, 0.0, 0.0, 0.0]
    assert kickstart_weight(2.0, 400, 0) == 2.0
    assert kickstart_weight(2.0, 400, 200) == pytest.approx(1.0)
    assert kickstart_weight(2.0, 400, 399) == pytest.approx(0.005)
    assert kickstart_weight(2.0, 400, 400) == 0.0
    assert kickstart_weight(0.0, 400, 0) == 0.0
    with pytest.raises(ValueError, match="negative"):
        kickstart_weight(-1.0, 4, 0)


def _synthetic() -> tuple[PolicyValueNetwork, TrainingBatch]:
    """Rows of very different legal-set sizes, some sharing no action."""

    legal = [
        [3],
        [0, 1, 2],
        [10, 11, 12, 13, 14, 15, 16],
        [40, 41],
        [1, 12, 49],
        [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31],
        [3, 49],
        [45],
    ]
    actions = [3, 2, 14, 41, 1, 20, 49, 45]
    rng = np.random.default_rng(3)
    steps = len(legal)
    offsets = np.zeros(steps + 1, dtype=np.int64)
    np.cumsum([len(row) for row in legal], out=offsets[1:])
    batch = TrainingBatch(
        observations=rng.integers(0, 6, size=(steps, _WIDTH)).astype(np.int32),
        legal_indices=np.concatenate([np.asarray(row) for row in legal]).astype(
            np.int32
        ),
        legal_offsets=offsets,
        action_size=50,
        actions=np.asarray(actions, dtype=np.int64),
        seats=(np.arange(steps) % 4).astype(np.int8),
        returns=np.asarray([1, -1 / 3, -1 / 3, -1 / 3] * 2, dtype=np.float32),
        episode_ids=np.zeros(steps, dtype=np.int32),
    )
    torch.manual_seed(1)
    network = PolicyValueNetwork(50, observation_size=_WIDTH, hidden=(16,))
    with torch.no_grad():
        # Spread the head so the softmax is far from uniform.
        network.policy_head.bias.normal_(0.0, 2.0)
    return network, batch


def _random_teacher(batch: TrainingBatch, seed: int) -> np.ndarray:
    """A distribution over every row's legal actions, unrelated to the net."""

    rng = np.random.default_rng(seed)
    column = np.zeros(batch.legal_indices.shape[0], dtype=np.float32)
    for row in range(batch.actions.shape[0]):
        start, end = batch.legal_offsets[row], batch.legal_offsets[row + 1]
        column[start:end] = rng.dirichlet(np.full(end - start, 0.5))
    return column


def _rows(batch: TrainingBatch) -> np.ndarray:
    return np.repeat(np.arange(batch.actions.shape[0]), np.diff(batch.legal_offsets))


def _student_log_probabilities(
    network: PolicyValueNetwork, batch: TrainingBatch
) -> Any:
    """The dense masked log-softmax: the reference the learner must match."""

    steps = batch.actions.shape[0]
    with torch.no_grad():
        logits, _ = network(
            torch.from_numpy(batch.observations),
            torch.from_numpy(batch.dense_masks(np.arange(steps))),
        )
    return torch.log_softmax(logits.double(), dim=-1)


def _reference_kl(network: PolicyValueNetwork, batch: TrainingBatch) -> float:
    assert batch.teacher is not None
    teacher = np.zeros((batch.actions.shape[0], batch.action_size))
    np.add.at(teacher, (_rows(batch), batch.legal_indices), batch.teacher)
    target = torch.from_numpy(teacher)
    log_probabilities = _student_log_probabilities(network, batch)
    per_row = torch.special.xlogy(target, target) - target * log_probabilities
    return float(per_row.sum(dim=-1).mean())


def _same_weights(left: PolicyValueNetwork, right: PolicyValueNetwork) -> bool:
    return all(
        torch.equal(a, b)
        for a, b in zip(
            left.state_dict().values(), right.state_dict().values(), strict=True
        )
    )


@pytest.mark.parametrize(("clip_ratio", "epochs"), [(None, 1), (0.2, 3)])
def test_without_weight_or_teacher_rows_an_update_is_the_plain_one(
    clip_ratio: float | None, epochs: int
) -> None:
    network, batch = _synthetic()
    taught = replace(batch, teacher=_random_teacher(batch, 0))
    config = LearnerConfig(minibatch_size=3, epochs=epochs, clip_ratio=clip_ratio)
    plain = Learner(copy.deepcopy(network), _CPU, config, seed=2)
    unweighted = Learner(copy.deepcopy(network), _CPU, config, seed=2)
    untaught = Learner(copy.deepcopy(network), _CPU, config, seed=2)
    for _ in range(2):  # the second update starts from moved Adam moments
        expected = plain.update(batch)
        assert unweighted.update(taught, kickstart_weight=0.0) == expected
        assert untaught.update(batch, kickstart_weight=0.7) == expected
        assert expected.kickstart_weight == 0.0 and expected.kickstart_kl == 0.0
        assert _same_weights(unweighted.network, plain.network)
        assert _same_weights(untaught.network, plain.network)
    with pytest.raises(ValueError, match="negative"):
        plain.update(batch, kickstart_weight=-0.1)


def test_a_teacher_that_is_the_student_costs_nothing_and_pulls_nowhere() -> None:
    network, batch = _synthetic()
    probabilities = _student_log_probabilities(network, batch).exp()
    own = probabilities[_rows(batch), batch.legal_indices].numpy()
    batch = replace(batch, teacher=own.astype(np.float32))
    steps = int(batch.actions.shape[0])
    learner = Learner(copy.deepcopy(network), _CPU, LearnerConfig(minibatch_size=steps))
    rows = torch.arange(steps)
    observations = torch.from_numpy(batch.observations)
    zeros = torch.zeros(steps)
    *_, distance = learner._terms(
        observations, batch, rows, zeros, zeros, None, teacher=True
    )
    assert distance is not None
    assert abs(float(distance.item())) < 1e-6
    distance.backward()  # type: ignore[no-untyped-call]
    for name, parameter in learner.network.named_parameters():
        if name.startswith("value_head"):
            assert parameter.grad is None  # the term reads the policy only
            continue
        assert parameter.grad is not None
        assert float(parameter.grad.abs().max()) < 1e-5, name
    stats = learner.update(batch, kickstart_weight=1.0)
    assert stats.kickstart_weight == 1.0
    assert abs(stats.kickstart_kl) < 1e-6


def test_a_positive_weight_pulls_the_student_toward_the_teacher() -> None:
    network, batch = _synthetic()
    batch = replace(batch, teacher=_random_teacher(batch, 1))
    steps = int(batch.actions.shape[0])
    config = LearnerConfig(learning_rate=1e-2, minibatch_size=steps)
    before = _reference_kl(network, batch)
    assert before > 0.1

    pulled = Learner(copy.deepcopy(network), _CPU, config, seed=3)
    stats = pulled.update(batch, kickstart_weight=5.0)
    free = Learner(copy.deepcopy(network), _CPU, config, seed=3)
    free.update(batch)

    # One minibatch: the logged term is the KL of the weights before the step.
    assert stats.kickstart_weight == 5.0
    assert stats.kickstart_kl == pytest.approx(before, rel=1e-5)
    after = _reference_kl(pulled.network, batch)
    assert after < before
    assert after < _reference_kl(free.network, batch)


def test_local_rows_carry_the_teacher_over_the_same_columns() -> None:
    _, batch = _synthetic()
    with pytest.raises(ValueError, match="teacher"):
        batch.local_legal(np.arange(3), teacher=True)
    teacher = _random_teacher(batch, 2)
    batch = replace(batch, teacher=teacher)
    picked = [5, 0, 4, 1]
    rows = np.asarray(picked, dtype=np.int64)
    legal = batch.local_legal(rows, teacher=True)
    assert legal.teacher is not None
    assert legal.teacher.shape == legal.mask.shape
    assert not legal.teacher[~legal.mask].any()
    assert legal.teacher.sum(axis=1) == pytest.approx(np.ones(rows.shape[0]))
    for position, row in enumerate(picked):
        start = int(batch.legal_offsets[row])
        end = int(batch.legal_offsets[row + 1])
        columns = np.searchsorted(legal.catalog, batch.legal_indices[start:end])
        assert legal.teacher[position, columns] == pytest.approx(teacher[start:end])
    assert batch.local_legal(rows).teacher is None


def test_teacher_answers_line_up_with_the_recorded_steps() -> None:
    _, batch = _synthetic()
    batch = replace(batch, episode_ids=np.asarray([0, 0, 1, 0, 1, 1, 2, 2], np.int32))
    teacher = _random_teacher(batch, 3)
    answers: dict[int, list[tuple[np.ndarray, np.ndarray]]] = {}
    for row, game in enumerate(batch.episode_ids.tolist()):
        start, end = batch.legal_offsets[row], batch.legal_offsets[row + 1]
        answers.setdefault(game, []).append(
            (batch.legal_indices[start:end].copy(), teacher[start:end].copy())
        )
    assert np.array_equal(teacher_column(batch, answers), teacher)

    shuffled = {game: list(reversed(rows)) for game, rows in answers.items()}
    with pytest.raises(ValueError, match="not the answered one"):
        teacher_column(batch, shuffled)
    extra = {**answers, 0: [*answers[0], answers[0][0]]}
    with pytest.raises(ValueError, match="differ in number"):
        teacher_column(batch, extra)
    with pytest.raises(ValueError, match="no teacher answer"):
        teacher_column(batch, {game: rows for game, rows in answers.items() if game})


def _teacher_file(tmp_path: Path) -> Path:
    """A tiny current-codec MLP: ``load_older_network`` reads any MLP file."""

    codec = ActionCodec(_RULES)
    torch.manual_seed(7)
    network = PolicyValueNetwork(codec.size, hidden=(16,))
    path = tmp_path / "teacher.pt"
    save_checkpoint(path, network, ruleset=_RULES.identifier, iteration=1, codec=codec)
    return path


def _student() -> PolicyValueNetwork:
    torch.manual_seed(0)
    return PolicyValueNetwork(ActionCodec(_RULES).size, hidden=(16,)).eval()


_SPECS = (
    SelfPlaySpec(game_seed=11, lineup=(LEARNER, "heuristic") * 2),
    SelfPlaySpec(game_seed=12, lineup=(LEARNER,) * 4),
)


def test_a_kickstarted_collection_keeps_the_teacher_answer_of_each_learner_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    codec = ActionCodec(_RULES)
    asked: list[object] = []

    def by_index(
        self: OlderTeacher,
        state: object,
        player: int,
        view: object,
        legal_actions: tuple[DomainAction, ...],
        observation: object = None,
        *,
        key: object = None,
    ) -> TeacherAnswer:
        # A distribution that names each legal action's catalog index, so a
        # row that lines up with another step's legal set cannot pass.
        asked.append(key)
        weights = np.asarray([codec.encode(a) + 1 for a in legal_actions], float)
        return TeacherAnswer(
            probabilities=weights / weights.sum(), value=0.0, source=NETWORK
        )

    monkeypatch.setattr(OlderTeacher, "answer", by_index)
    student = _student()
    with Collector(
        _RULES,
        max_steps=60,
        opponent="heuristic",
        kickstart_teacher=_teacher_file(tmp_path),
    ) as collector:
        taught = collector.collect(
            student, _CPU, _SPECS, policy_seed=4, opponent_seed=5, teacher=True
        ).batch
        assert len(asked) == taught.actions.shape[0]
        assert set(asked) <= {
            (0, 0),
            (0, 2),
            (1, 0),
            (1, 1),
            (1, 2),
            (1, 3),
        }

        def refuse(*_: object, **__: object) -> TeacherAnswer:
            raise AssertionError("the teacher was asked with kickstarting off")

        monkeypatch.setattr(OlderTeacher, "answer", refuse)
        monkeypatch.setattr(
            "dune_imperium.training.collect.cached_older_network", refuse
        )
        plain = collector.collect(
            student, _CPU, _SPECS, policy_seed=4, opponent_seed=5
        ).batch

    assert plain.teacher is None
    assert taught.teacher is not None
    # The teacher answers beside the learner: the games are the same.
    for name in _ARRAYS:
        assert np.array_equal(getattr(taught, name), getattr(plain, name)), name
    assert set(taught.episode_ids.tolist()) == {0, 1}
    for row in range(taught.actions.shape[0]):
        start, end = taught.legal_offsets[row], taught.legal_offsets[row + 1]
        weights = taught.legal_indices[start:end].astype(np.float64) + 1.0
        assert taught.teacher[start:end] == pytest.approx(weights / weights.sum())
    with pytest.raises(ValueError, match="kickstart teacher"):
        Collector(_RULES).collect(
            student, _CPU, _SPECS[1:], policy_seed=4, opponent_seed=5, teacher=True
        )


def test_parallel_workers_load_the_teacher_and_return_its_rows(
    tmp_path: Path,
) -> None:
    student = _student()
    with Collector(
        _RULES,
        workers=2,
        max_steps=60,
        opponent="heuristic",
        kickstart_teacher=_teacher_file(tmp_path),
    ) as collector:
        taught = collector.collect(
            student, _CPU, _SPECS, policy_seed=4, opponent_seed=5, teacher=True
        ).batch
        plain = collector.collect(
            student, _CPU, _SPECS, policy_seed=4, opponent_seed=5
        ).batch

    assert plain.teacher is None
    assert taught.teacher is not None
    assert taught.teacher.dtype == np.float32
    assert taught.teacher.shape == taught.legal_indices.shape
    for name in _ARRAYS:
        assert np.array_equal(getattr(taught, name), getattr(plain, name)), name
    sums = np.add.reduceat(taught.teacher.astype(np.float64), taught.legal_offsets[:-1])
    assert sums == pytest.approx(np.ones(taught.actions.shape[0]), abs=1e-5)
    assert set(taught.episode_ids.tolist()) == {0, 1}


def test_the_cli_kickstarts_for_the_given_iterations_and_records_it(
    tmp_path: Path,
) -> None:
    teacher = _teacher_file(tmp_path)
    out = tmp_path / "run"
    exit_code = train_main(
        [
            "--out",
            str(out),
            "--iterations",
            "2",
            "--games-per-iteration",
            "1",
            "--hidden",
            "16",
            "--minibatch",
            "256",
            "--max-steps",
            "60",
            "--kickstart-teacher",
            str(teacher),
            "--kickstart-weight",
            "0.5",
            "--kickstart-iterations",
            "1",
        ]
    )
    assert exit_code == 0
    first, second = (
        json.loads(line)["update"]
        for line in (out / "training.jsonl").read_text().splitlines()
    )
    assert first["kickstart_weight"] == 0.5 and first["kickstart_kl"] > 0.0
    assert second["kickstart_weight"] == 0.0 and second["kickstart_kl"] == 0.0
    _, info = load_checkpoint(out / "latest.pt")
    document = info.metadata["config"]
    assert document["kickstart_teacher"] == str(teacher)
    assert document["kickstart_weight"] == 0.5
    assert document["kickstart_iterations"] == 1


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--kickstart-weight", "1"], "needs a kickstart_teacher"),
        (
            ["--kickstart-weight", "1", "--kickstart-teacher", "t.pt"],
            "needs kickstart_iterations",
        ),
        (["--kickstart-teacher", "t.pt"], "positive kickstart_weight"),
        (["--kickstart-iterations", "4"], "positive kickstart_weight"),
        (["--kickstart-weight", "-1"], "negative"),
    ],
)
def test_kickstart_options_that_do_not_fit_together_are_refused(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    arguments: list[str],
    message: str,
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        train_main(["--out", str(tmp_path), *arguments])
    assert excinfo.value.code == 2
    assert message in capsys.readouterr().err
    config = TrainConfig(
        out_dir=tmp_path,
        kickstart_teacher=Path("t.pt"),
        kickstart_weight=1.0,
        kickstart_iterations=400,
    )
    assert config.kickstart_iterations == 400
