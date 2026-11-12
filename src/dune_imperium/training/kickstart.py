"""Kickstarting: a decaying pull toward a teacher in the RL loop (E6).

Kickstarting (Schmitt et al. 2018, "Kickstarting Deep Reinforcement
Learning") adds ``beta * KL(teacher || student)`` over each learner step's
legal actions to the policy-gradient loss and lowers ``beta`` to zero, so
the student starts out pulled toward the teacher and is left to the reward
later; the paper's students passed their teachers with a decaying weight
and stayed at the teacher's level with a constant one. Here (the handoff's
E6, "모델 구조 점검 뒤 다음 순서" item 5) the teacher is a network of an
older codec read through ``training.older_teacher``, and the student is
what ``dune-imperium-train`` trains.

``kickstart_weight`` is the schedule: ``beta0`` at the run's first trained
iteration, falling linearly to 0 after ``iterations`` of them, then 0.
During an iteration whose weight is positive, the collector wraps the
learner's policy in a ``TeacherRecordingPolicy``: the learner still
chooses every action (the teacher only answers alongside, so the games are
the same as without it), and the teacher's distribution over each request's
legal actions -- the ones the learner was offered, after the undo and
Family Atomics restrictions -- is kept. ``teacher_column`` lines those
answers up with the learner's recorded steps into
``TrainingBatch.teacher``, which the learner reads (``learner``). An
iteration with weight 0 builds no teacher and asks it nothing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace

import numpy as np

from dune_imperium.training.older_teacher import OlderTeacher
from dune_imperium.training.policy import BatchPolicy, PolicyRequest
from dune_imperium.training.selfplay import TrainingBatch

# Each game's learner decisions in order: the legal catalog indices offered
# and the teacher's probability of each.
TeacherAnswers = dict[int, list[tuple[np.ndarray, np.ndarray]]]


def kickstart_weight(initial: float, iterations: int, trained: int) -> float:
    """The weight of the run's ``trained``-th iteration (0 for its first).

    ``initial`` at ``trained == 0``, falling linearly to 0 at
    ``trained == iterations`` and staying there.
    """

    if initial < 0.0 or iterations < 0 or trained < 0:
        raise ValueError("kickstart weight, iterations and step must not be negative")
    if initial == 0.0 or trained >= iterations:
        return 0.0
    return initial * (1.0 - trained / iterations)


@dataclass(slots=True)
class TeacherRecordingPolicy:
    """The learner's policy, with the teacher's answer to each request kept.

    ``policy`` chooses every action; the teacher is asked the same requests
    afterwards and changes nothing about the game. ``answers[game]`` lists
    that game's requests in order, as the runner records them as steps.
    """

    policy: BatchPolicy
    teacher: OlderTeacher
    answers: TeacherAnswers = field(default_factory=dict)

    def act(self, requests: Sequence[PolicyRequest]) -> Sequence[int]:
        chosen = self.policy.act(requests)
        for request in requests:
            answer = self.teacher.answer(
                request.state,
                request.seat,
                request.view,
                request.legal_actions,
                request.observation,
                key=(request.game, request.seat),
            )
            self.answers.setdefault(request.game, []).append(
                (
                    np.asarray(request.legal_indices, dtype=np.int32),
                    answer.probabilities.astype(np.float32),
                )
            )
        return chosen


def teacher_column(batch: TrainingBatch, answers: TeacherAnswers) -> np.ndarray:
    """The teacher's probabilities parallel to ``batch.legal_indices``.

    ``batch`` holds the recorded steps of the policy that ``answers`` was
    kept for (``select_policy_steps``), episode by episode in the order the
    games were given, each episode's steps in the order they were taken.
    Every step must be the next answer of its game, offering the same legal
    indices in the same order, and every answer must be used.
    """

    column = np.zeros(batch.legal_indices.shape[0], dtype=np.float32)
    taken: dict[int, int] = {}
    for row, game in enumerate(batch.episode_ids.tolist()):
        position = taken.get(game, 0)
        game_answers = answers.get(game, [])
        if position >= len(game_answers):
            raise ValueError(f"game {game}: a recorded step has no teacher answer")
        legal, probabilities = game_answers[position]
        taken[game] = position + 1
        start, end = int(batch.legal_offsets[row]), int(batch.legal_offsets[row + 1])
        if not np.array_equal(batch.legal_indices[start:end], legal):
            raise ValueError(f"game {game}: a recorded step is not the answered one")
        column[start:end] = probabilities
    for game, game_answers in answers.items():
        if taken.get(game, 0) != len(game_answers):
            raise ValueError(f"game {game}: teacher answers and steps differ in number")
    return column


def with_teacher(batch: TrainingBatch, answers: TeacherAnswers) -> TrainingBatch:
    """``batch`` carrying the teacher's probabilities (``teacher_column``)."""

    return replace(batch, teacher=teacher_column(batch, answers))
