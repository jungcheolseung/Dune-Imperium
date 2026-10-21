"""Distillation data whose teacher is a network of an older codec.

``scripts/train/distill_entity.py data`` lets a teacher network play the
training distribution and keeps its distribution over each decision's rows
(``training.teacher``). A file of an older codec cannot answer the current
rows by itself (``training.older_teacher``), so here the teacher is an
``OlderTeacher``: it plays the learner seats of the same games
(``loop._iteration_specs``: its own seats against each other and against
the opponent baseline), sampling its distribution at temperature 1 as the
collector's learner does, and the data keeps that distribution and the
file's value of every position. Worker processes each play a share of an
iteration's games and return their rows; the shard is their rows in the
order of the games.

With a student (``older_shard(student=...)``, ``distill_entity.py data
--older --student``) the learner seats are the student's instead: a
checkpoint of the current codec, loaded once per worker process for the
game's ruleset (``load_student``), samples its policy at temperature 1
over the same legal rows (``TorchBatchPolicy``, the collector's learner),
and the teacher still answers every learner decision
(``LabelledStudentPolicy``). The rows are the same ``TeacherData``, so a
student is trained on the positions it reaches itself (student-position
distillation, DAgger) on a mix of such shards and the teacher's own.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from multiprocessing import get_context
from pathlib import Path

import numpy as np
import torch

from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.config import RulesetConfig
from dune_imperium.training.checkpoint import CheckpointInfo, load_checkpoint
from dune_imperium.training.collect import LEARNER
from dune_imperium.training.network import PolicyValueNetwork
from dune_imperium.training.older_teacher import (
    GameAnswers,
    LabelledStudentPolicy,
    OlderTeacher,
    OlderTeacherPolicy,
    cached_older_network,
)
from dune_imperium.training.policy import AgentBatchPolicy
from dune_imperium.training.selfplay import (
    Episode,
    SelfPlayRunner,
    SelfPlaySpec,
    select_policy_steps,
)
from dune_imperium.training.teacher import TeacherData, _sparse, concatenate
from dune_imperium.training.torch_policy import TorchBatchPolicy

_SEATS = 4


@dataclass(frozen=True, slots=True)
class OlderJob:
    """One worker's share of an iteration's games."""

    teacher_path: str
    ruleset: RulesetConfig
    specs: tuple[SelfPlaySpec, ...]
    games: tuple[int, ...]  # each spec's game number in the data
    opponent: str
    policy_seed: int
    opponent_seed: int
    max_steps: int
    # The checkpoint playing the learner seats; None: the teacher plays them.
    student_path: str | None = None


@lru_cache(maxsize=2)
def _cached_student(
    path: str, modified: float, ruleset: RulesetConfig
) -> tuple[PolicyValueNetwork, CheckpointInfo]:
    del modified  # part of the key so a rewritten file reloads
    network, info = load_checkpoint(Path(path), ruleset=ruleset)
    network.eval()
    return network, info


def load_student(
    path: str | Path, ruleset: RulesetConfig
) -> tuple[PolicyValueNetwork, CheckpointInfo]:
    """A student checkpoint answering ``ruleset``'s catalog, loaded once per
    process and file (``load_checkpoint(ruleset=...)``, as a seat of
    another game loads a file)."""

    resolved = str(Path(path).expanduser())
    return _cached_student(resolved, os.path.getmtime(resolved), ruleset)


def teacher_rows(
    episodes: Sequence[Episode],
    answers: GameAnswers,
    *,
    ruleset: str,
    action_size: int,
    games: Sequence[int],
) -> TeacherData:
    """The learner's decisions of ``episodes`` with the teacher's answers.

    ``answers[game]`` holds, in order, each learner decision of that game:
    the legal catalog indices it was offered and the teacher's answer over
    them; they must match the recorded steps one for one.
    """

    batch = select_policy_steps(episodes, LEARNER, action_size=action_size)
    probabilities = np.zeros(batch.legal_indices.shape[0], dtype=np.float32)
    values = np.zeros(batch.actions.shape[0], dtype=np.float32)
    taken = dict.fromkeys(answers, 0)
    for row, episode_id in enumerate(batch.episode_ids.tolist()):
        game_answers = answers[episode_id]
        legal, answer = game_answers[taken[episode_id]]
        taken[episode_id] += 1
        start, end = batch.legal_offsets[row], batch.legal_offsets[row + 1]
        recorded = batch.legal_indices[start:end].tolist()
        if sorted(recorded) != sorted(legal):
            raise ValueError(f"game {episode_id}: a recorded step is not the answer's")
        by_index = dict(zip(legal, answer.probabilities.tolist(), strict=True))
        probabilities[start:end] = [by_index[index] for index in recorded]
        values[row] = answer.value
    for episode_id, count in taken.items():
        if count != len(answers[episode_id]):
            raise ValueError(f"game {episode_id}: answers and steps differ in number")
    columns, observation_values, offsets = _sparse(batch.observations)
    victory = np.asarray([episode.victory_points for episode in episodes], np.int16)
    seats = batch.seats.astype(np.int64)
    relative = (seats[:, None] + np.arange(_SEATS)[None, :]) % _SEATS
    numbers = np.asarray(games, dtype=np.int32)
    return TeacherData(
        ruleset=ruleset,
        action_size=action_size,
        obs_columns=columns,
        obs_values=observation_values,
        obs_offsets=offsets,
        legal_indices=batch.legal_indices.astype(np.int32),
        legal_offsets=batch.legal_offsets.astype(np.int64),
        teacher=probabilities.astype(np.float16),
        actions=batch.actions.astype(np.int32),
        returns=batch.returns.astype(np.float32),
        victory_points=victory[batch.episode_ids][
            np.arange(seats.shape[0])[:, None], relative
        ],
        games=numbers[batch.episode_ids],
        values=values,
    )


def play_job(job: OlderJob) -> TeacherData:
    """Play one share of games and return its teacher rows (a worker)."""

    torch.set_num_threads(1)
    older = cached_older_network(job.teacher_path)
    teacher = OlderTeacher(older, seed=job.policy_seed)
    policy: OlderTeacherPolicy | LabelledStudentPolicy
    if job.student_path is None:
        policy = OlderTeacherPolicy(teacher, job.policy_seed)
    else:
        network, _ = load_student(job.student_path, job.ruleset)
        student = TorchBatchPolicy(
            network,
            torch.device("cpu"),
            seed=job.policy_seed,
            sample=True,
            temperature=1.0,
        )
        policy = LabelledStudentPolicy(teacher, student)
    runner = SelfPlayRunner(
        job.ruleset, max_steps=job.max_steps, record=True, undo_actions=False
    )
    opponent = AgentBatchPolicy(job.opponent, job.opponent_seed)
    result = runner.run({LEARNER: policy, job.opponent: opponent}, job.specs)
    truncated = [
        episode.game_seed for episode in result.episodes if episode.truncated
    ]
    if truncated:
        print(f"truncated games (seeds): {truncated}", flush=True)
    return teacher_rows(
        result.episodes,
        policy.answers,
        ruleset=job.ruleset.identifier,
        action_size=ActionCodec(job.ruleset).size,
        games=job.games,
    )


def older_shard(
    pool: ProcessPoolExecutor | None,
    teacher_path: Path,
    ruleset: RulesetConfig,
    specs: Sequence[SelfPlaySpec],
    *,
    first_game: int,
    workers: int,
    opponent: str,
    seed: int,
    max_steps: int,
    student: Path | None = None,
) -> TeacherData:
    """One iteration's teacher rows, the games split over ``workers``.

    With ``student`` that checkpoint plays the learner seats and the
    teacher only labels them (module docstring).
    """

    shares = [tuple(range(start, len(specs), workers)) for start in range(workers)]
    jobs = [
        OlderJob(
            teacher_path=str(teacher_path),
            ruleset=ruleset,
            specs=tuple(specs[index] for index in share),
            games=tuple(first_game + index for index in share),
            opponent=opponent,
            policy_seed=seed + 7_919 * number,
            opponent_seed=seed + 1 + 7_919 * number,
            max_steps=max_steps,
            student_path=None if student is None else str(student),
        )
        for number, share in enumerate(shares)
        if share
    ]
    if pool is None:
        parts = [play_job(job) for job in jobs]
    else:
        parts = list(pool.map(play_job, jobs))
    data = concatenate(parts)
    order = np.argsort(data.games, kind="stable")
    if np.all(order == np.arange(order.shape[0])):
        return data
    return _rows(data, order)


def _rows(data: TeacherData, rows: np.ndarray) -> TeacherData:
    from dune_imperium.training.teacher import gather_rows

    obs_columns, obs_offsets = gather_rows(data.obs_columns, data.obs_offsets, rows)
    obs_values, _ = gather_rows(data.obs_values, data.obs_offsets, rows)
    legal, legal_offsets = gather_rows(data.legal_indices, data.legal_offsets, rows)
    teacher, _ = gather_rows(data.teacher, data.legal_offsets, rows)
    return TeacherData(
        ruleset=data.ruleset,
        action_size=data.action_size,
        obs_columns=obs_columns,
        obs_values=obs_values,
        obs_offsets=obs_offsets,
        legal_indices=legal,
        legal_offsets=legal_offsets,
        teacher=teacher,
        actions=data.actions[rows],
        returns=data.returns[rows],
        victory_points=data.victory_points[rows],
        games=data.games[rows],
        values=data.values[rows],
    )


def worker_pool(workers: int) -> ProcessPoolExecutor | None:
    """A spawn pool for ``older_shard``, or None to play in-process."""

    if workers <= 1:
        return None
    return ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn"))
