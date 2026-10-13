"""Distil a trained network into a student of another architecture.

Stage P2 of docs/entity-network-plan.md: before spending reinforcement
learning on the ``entity`` network, see whether it learns the same data
better than the MLP does. The teacher (network Y) plays the training
distribution (``Collector``: its own seats plus app_ai opponent games);
every decision it made is kept with

- the teacher's probabilities over the offered actions (temperature 1),
- the game's outcome for the acting seat (winner +1, the others -1/3),
- every seat's final Victory Points, in the observation's relative seat
  order (0 is the acting seat, then the seats after it),

and two students -- ``entity`` and a fresh MLP of the teacher's shape --
learn it with the same loss, data and steps (``train_student``): the
cross-entropy to the teacher's distribution, plus the value regressed on
the outcome, plus (when the student has one) the auxiliary head regressed
on the final Victory Points / 10.

Observations are stored sparse (about 5% of the 4,537 columns are not
zero), the offered actions and the teacher's probabilities in compressed
rows, so a few million decisions fit in a few GB.
"""

from __future__ import annotations

import copy
import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch import Tensor, nn

from dune_imperium.adapters.observation_encoding import OBSERVATION_SIZE
from dune_imperium.training.collect import CollectionResult
from dune_imperium.training.network import MASKED_LOGIT, PolicyValueNetwork

TEACHER_FORMAT = 1
_SEATS = 4
# Final Victory Points are regressed at this scale (a game ends near 10).
VP_SCALE = 10.0


def gather_rows(
    values: np.ndarray, offsets: np.ndarray, rows: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Take ``rows`` of a compressed-row array, keeping the order given."""

    starts = offsets[rows]
    counts = offsets[rows + 1] - starts
    new_offsets = np.zeros(rows.shape[0] + 1, dtype=np.int64)
    np.cumsum(counts, out=new_offsets[1:])
    if not new_offsets[-1]:
        return values[:0].copy(), new_offsets
    rank = np.arange(int(new_offsets[-1])) - np.repeat(new_offsets[:-1], counts)
    return values[np.repeat(starts, counts) + rank], new_offsets


@dataclass(frozen=True, slots=True)
class TeacherData:
    """Decisions of the teacher, with its distribution and the outcomes."""

    ruleset: str
    action_size: int
    obs_columns: np.ndarray  # int16 [non-zero values]: observation column
    obs_values: np.ndarray  # int16 [non-zero values]
    obs_offsets: np.ndarray  # int64 [rows + 1]
    legal_indices: np.ndarray  # int32 [offered actions]: catalog indices
    legal_offsets: np.ndarray  # int64 [rows + 1]
    teacher: np.ndarray  # float16 [offered actions]: teacher probability
    actions: np.ndarray  # int32 [rows]: the catalog index played
    returns: np.ndarray  # float32 [rows]: outcome of the acting seat
    victory_points: np.ndarray  # int16 [rows, 4]: final VP, relative seats
    games: np.ndarray  # int32 [rows]: game number (the held-out split)

    @property
    def rows(self) -> int:
        return int(self.actions.shape[0])

    def observations(self, rows: np.ndarray) -> np.ndarray:
        """The dense observations ``int32 [len(rows), OBSERVATION_SIZE]``."""

        columns, offsets = gather_rows(self.obs_columns, self.obs_offsets, rows)
        values, _ = gather_rows(self.obs_values, self.obs_offsets, rows)
        dense = np.zeros((rows.shape[0], OBSERVATION_SIZE), dtype=np.int32)
        owner = np.repeat(np.arange(rows.shape[0]), np.diff(offsets))
        dense[owner, columns.astype(np.int64)] = values
        return dense

    def legal(self, rows: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Padded ``index`` int64, ``valid`` bool and ``target`` float32
        ``[len(rows), width]`` of the offered actions."""

        indices, offsets = gather_rows(self.legal_indices, self.legal_offsets, rows)
        probabilities, _ = gather_rows(self.teacher, self.legal_offsets, rows)
        counts = np.diff(offsets)
        width = max(int(counts.max(initial=0)), 1)
        index = np.zeros((rows.shape[0], width), dtype=np.int64)
        valid = np.zeros((rows.shape[0], width), dtype=bool)
        target = np.zeros((rows.shape[0], width), dtype=np.float32)
        owner = np.repeat(np.arange(rows.shape[0]), counts)
        rank = np.arange(int(offsets[-1])) - np.repeat(offsets[:-1], counts)
        index[owner, rank] = indices
        valid[owner, rank] = True
        target[owner, rank] = probabilities
        return index, valid, target

    def offered(self) -> np.ndarray:
        """How many actions each row offered."""

        counts: np.ndarray = np.diff(self.legal_offsets)
        return counts


def _sparse(observations: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if observations.max(initial=0) > np.iinfo(np.int16).max:
        raise ValueError("observation values exceed the int16 storage range")
    owner, columns = np.nonzero(observations)
    offsets = np.zeros(observations.shape[0] + 1, dtype=np.int64)
    np.cumsum(np.bincount(owner, minlength=observations.shape[0]), out=offsets[1:])
    return (
        columns.astype(np.int16),
        observations[owner, columns].astype(np.int16),
        offsets,
    )


def teacher_probabilities(
    network: PolicyValueNetwork,
    observations: np.ndarray,
    legal_indices: np.ndarray,
    legal_offsets: np.ndarray,
    *,
    chunk: int = 1024,
) -> np.ndarray:
    """The network's probabilities over each row's offered actions (float32,
    aligned with ``legal_indices``)."""

    rows = observations.shape[0]
    out = np.zeros(legal_indices.shape[0], dtype=np.float32)
    network.eval()
    with torch.no_grad():
        for start in range(0, rows, chunk):
            part = np.arange(start, min(start + chunk, rows))
            indices, offsets = gather_rows(legal_indices, legal_offsets, part)
            counts = np.diff(offsets)
            width = max(int(counts.max(initial=0)), 1)
            index = np.zeros((part.shape[0], width), dtype=np.int64)
            valid = np.zeros((part.shape[0], width), dtype=bool)
            owner = np.repeat(np.arange(part.shape[0]), counts)
            rank = np.arange(int(offsets[-1])) - np.repeat(offsets[:-1], counts)
            index[owner, rank] = indices
            valid[owner, rank] = True
            hidden = network.trunk(torch.from_numpy(observations[part]))
            logits = network.row_action_logits(hidden, torch.from_numpy(index))
            logits = logits.masked_fill(~torch.from_numpy(valid), MASKED_LOGIT)
            probabilities = torch.softmax(logits, dim=-1).numpy()
            out[legal_offsets[start] : legal_offsets[part[-1] + 1]] = probabilities[
                owner, rank
            ]
    return out


def build_teacher_data(
    result: CollectionResult,
    network: PolicyValueNetwork,
    *,
    ruleset: str,
    first_game: int,
) -> TeacherData:
    """The teacher's decisions of one collection, numbered from ``first_game``."""

    batch = result.batch
    columns, values, offsets = _sparse(batch.observations)
    victory = np.asarray(
        [episode.victory_points for episode in result.episodes], dtype=np.int16
    )
    seats = batch.seats.astype(np.int64)
    relative = (seats[:, None] + np.arange(_SEATS)[None, :]) % _SEATS
    return TeacherData(
        ruleset=ruleset,
        action_size=batch.action_size,
        obs_columns=columns,
        obs_values=values,
        obs_offsets=offsets,
        legal_indices=batch.legal_indices.astype(np.int32),
        legal_offsets=batch.legal_offsets.astype(np.int64),
        teacher=teacher_probabilities(
            network,
            batch.observations,
            batch.legal_indices,
            batch.legal_offsets,
        ).astype(np.float16),
        actions=batch.actions.astype(np.int32),
        returns=batch.returns.astype(np.float32),
        victory_points=victory[batch.episode_ids][
            np.arange(seats.shape[0])[:, None], relative
        ],
        games=(batch.episode_ids + first_game).astype(np.int32),
    )


_ARRAYS = (
    "obs_columns",
    "obs_values",
    "obs_offsets",
    "legal_indices",
    "legal_offsets",
    "teacher",
    "actions",
    "returns",
    "victory_points",
    "games",
)


def save_teacher_data(data: TeacherData, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        format=np.asarray(TEACHER_FORMAT),
        ruleset=np.asarray(data.ruleset),
        action_size=np.asarray(data.action_size),
        **{name: getattr(data, name) for name in _ARRAYS},
    )


def load_teacher_data(path: Path) -> TeacherData:
    with np.load(path) as arrays:
        if int(arrays["format"]) != TEACHER_FORMAT:
            raise ValueError(f"teacher data format {int(arrays['format'])}")
        return TeacherData(
            ruleset=str(arrays["ruleset"]),
            action_size=int(arrays["action_size"]),
            **{name: arrays[name] for name in _ARRAYS},
        )


def concatenate(parts: Sequence[TeacherData]) -> TeacherData:
    """One data set of ``parts`` in order (one ruleset and catalog)."""

    if not parts:
        raise ValueError("nothing to concatenate")
    if len({(part.ruleset, part.action_size) for part in parts}) != 1:
        raise ValueError("the parts come from different catalogs")

    def offsets(name: str) -> np.ndarray:
        joined = [np.zeros(1, dtype=np.int64)]
        base = 0
        for part in parts:
            values = getattr(part, name)
            joined.append(values[1:] + base)
            base += int(values[-1])
        return np.concatenate(joined)

    plain = {
        name: np.concatenate([getattr(part, name) for part in parts])
        for name in _ARRAYS
        if not name.endswith("_offsets")
    }
    return TeacherData(
        ruleset=parts[0].ruleset,
        action_size=parts[0].action_size,
        obs_offsets=offsets("obs_offsets"),
        legal_offsets=offsets("legal_offsets"),
        **plain,
    )


# -- the student ------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class StudentConfig:
    """How a student learns the teacher data (the same for every student)."""

    learning_rate: float = 3.0e-4
    warmup_steps: int = 200
    minibatch_size: int = 512
    epochs: int = 3
    value_coefficient: float = 0.5
    # The auxiliary Victory Point head's weight; a student without the head
    # ignores it.
    vp_coefficient: float = 0.1
    max_grad_norm: float = 1.0
    heldout_modulus: int = 10
    # Held-out rows scored after each epoch (a fixed sample of the held-out
    # games' rows, the same for every student).
    heldout_rows: int = 50_000
    seed: int = 0
    threads: int = 4

    def __post_init__(self) -> None:
        if self.learning_rate <= 0.0 or self.minibatch_size < 1 or self.epochs < 1:
            raise ValueError("learning rate, minibatch and epochs must be positive")


@dataclass(frozen=True, slots=True)
class StudentScore:
    """A student against the teacher on held-out rows."""

    rows: int
    cross_entropy: float  # to the teacher's distribution
    teacher_entropy: float  # the floor of the cross-entropy
    agreement: float  # top-1 match, rows offering two or more actions
    value_mse: float  # against the outcome
    vp_mse: float | None  # auxiliary head, VP / VP_SCALE


@dataclass(frozen=True, slots=True)
class StudentEpoch:
    epoch: int
    steps: int
    policy_loss: float
    value_loss: float
    vp_loss: float | None
    heldout: StudentScore
    seconds: float


def split_rows(data: TeacherData, modulus: int) -> tuple[np.ndarray, np.ndarray]:
    """Training and held-out rows, split by game (every ``modulus``-th game)."""

    heldout = data.games % modulus == 0
    return np.flatnonzero(~heldout), np.flatnonzero(heldout)


def _vp_head(network: PolicyValueNetwork) -> nn.Module | None:
    head = getattr(network, "vp_head", None)
    return head if isinstance(head, nn.Module) else None


def _losses(
    network: PolicyValueNetwork, data: TeacherData, rows: np.ndarray
) -> tuple[Tensor, Tensor, Tensor | None, Tensor, Tensor]:
    """Policy cross-entropy, value MSE and VP MSE (means over ``rows``), and
    the student's log-probabilities and validity for scoring."""

    observations = torch.from_numpy(data.observations(rows))
    index, valid, target = data.legal(rows)
    valid_t = torch.from_numpy(valid)
    hidden = network.trunk(observations)
    logits = network.row_action_logits(hidden, torch.from_numpy(index))
    log_probs = torch.log_softmax(logits.masked_fill(~valid_t, MASKED_LOGIT), dim=-1)
    policy = -(torch.from_numpy(target) * log_probs.masked_fill(~valid_t, 0.0)).sum(1)
    value = network.value_head(hidden).squeeze(-1)
    value_loss = (value - torch.from_numpy(data.returns[rows])).square()
    head = _vp_head(network)
    vp_loss = None
    if head is not None:
        predicted = head(hidden)
        wanted = torch.from_numpy(data.victory_points[rows].astype(np.float32))
        vp_loss = (predicted - wanted / VP_SCALE).square().mean(dim=1).mean()
    return policy.mean(), value_loss.mean(), vp_loss, log_probs, valid_t


def score_student(
    network: PolicyValueNetwork,
    data: TeacherData,
    rows: np.ndarray,
    *,
    chunk: int = 2048,
) -> StudentScore:
    """``network`` against the teacher on ``rows``."""

    totals = {"ce": 0.0, "entropy": 0.0, "value": 0.0, "vp": 0.0}
    agree = counted = 0
    has_vp = _vp_head(network) is not None
    network.eval()
    with torch.no_grad():
        for start in range(0, rows.shape[0], chunk):
            part = rows[start : start + chunk]
            policy, value, vp, log_probs, valid = _losses(network, data, part)
            _, _, target = data.legal(part)
            teacher = torch.from_numpy(target)
            entropy = -(teacher * torch.log(teacher.clamp(min=1e-12))).sum(1)
            totals["ce"] += float(policy) * part.shape[0]
            totals["entropy"] += float(entropy.sum())
            totals["value"] += float(value) * part.shape[0]
            if vp is not None:
                totals["vp"] += float(vp) * part.shape[0]
            choice = valid.sum(1) > 1
            student_top = log_probs.argmax(1)
            teacher_top = teacher.masked_fill(~valid, -1.0).argmax(1)
            agree += int((student_top == teacher_top)[choice].sum())
            counted += int(choice.sum())
    total = max(rows.shape[0], 1)
    return StudentScore(
        rows=int(rows.shape[0]),
        cross_entropy=totals["ce"] / total,
        teacher_entropy=totals["entropy"] / total,
        agreement=agree / counted if counted else math.nan,
        value_mse=totals["value"] / total,
        vp_mse=totals["vp"] / total if has_vp else None,
    )


def train_student(
    network: PolicyValueNetwork,
    data: TeacherData,
    config: StudentConfig,
    *,
    on_epoch: Callable[[StudentEpoch], None] | None = None,
) -> list[StudentEpoch]:
    """Fit ``network`` to the teacher data; keep the best held-out epoch.

    The network ends holding the weights of the epoch with the lowest
    held-out cross-entropy.
    """

    if data.action_size != network.action_size:
        raise ValueError("the student and the data have different catalogs")
    torch.set_num_threads(config.threads)
    torch.manual_seed(config.seed)
    generator = np.random.default_rng(config.seed)
    train_rows, heldout_rows = split_rows(data, config.heldout_modulus)
    if heldout_rows.shape[0] > config.heldout_rows:
        heldout_rows = np.sort(
            generator.choice(heldout_rows, config.heldout_rows, replace=False)
        )
    optimizer = torch.optim.Adam(network.parameters(), lr=config.learning_rate)
    history: list[StudentEpoch] = []
    best: tuple[float, dict[str, Tensor]] | None = None
    steps = 0
    for epoch in range(1, config.epochs + 1):
        started = time.perf_counter()
        order = generator.permutation(train_rows)
        sums = {"policy": 0.0, "value": 0.0, "vp": 0.0}
        batches = 0
        network.train()
        for start in range(0, order.shape[0], config.minibatch_size):
            rows = np.sort(order[start : start + config.minibatch_size])
            policy, value, vp, _, _ = _losses(network, data, rows)
            loss = policy + config.value_coefficient * value
            if vp is not None:
                loss = loss + config.vp_coefficient * vp
            steps += 1
            rate = config.learning_rate * min(1.0, steps / max(config.warmup_steps, 1))
            for group in optimizer.param_groups:
                group["lr"] = rate
            optimizer.zero_grad()
            loss.backward()  # type: ignore[no-untyped-call]
            nn.utils.clip_grad_norm_(network.parameters(), config.max_grad_norm)
            optimizer.step()
            sums["policy"] += policy.item()
            sums["value"] += value.item()
            if vp is not None:
                sums["vp"] += vp.item()
            batches += 1
        score = score_student(network, data, heldout_rows)
        record = StudentEpoch(
            epoch=epoch,
            steps=steps,
            policy_loss=sums["policy"] / max(batches, 1),
            value_loss=sums["value"] / max(batches, 1),
            vp_loss=sums["vp"] / max(batches, 1) if score.vp_mse is not None else None,
            heldout=score,
            seconds=time.perf_counter() - started,
        )
        history.append(record)
        if on_epoch is not None:
            on_epoch(record)
        if best is None or score.cross_entropy < best[0]:
            best = (score.cross_entropy, copy.deepcopy(network.state_dict()))
    assert best is not None
    network.load_state_dict(best[1])
    network.eval()
    return history
