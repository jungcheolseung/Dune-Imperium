"""Distil a trained network into a student of another architecture.

Stage P2 of docs/entity-network-plan.md: before spending reinforcement
learning on the ``entity`` network, see whether it learns the same data
better than the MLP does. The teacher (network Y) plays the training
distribution (``Collector``: its own seats plus app_ai opponent games);
every decision it made is kept with

- the teacher's probabilities over the offered actions (temperature 1),
- the teacher's value of the position (format 2; ``add_teacher_values``
  fills it in for a format 1 shard),
- the game's outcome for the acting seat (winner +1, the others -1/3),
- every seat's final Victory Points, in the observation's relative seat
  order (0 is the acting seat, then the seats after it),

and two students -- ``entity`` and a fresh MLP of the teacher's shape --
learn it with the same loss, data and steps (``train_student``): the
cross-entropy to the teacher's distribution, plus the value regressed on
the outcome or on the teacher's value (``StudentConfig.value_target``),
plus (when the student has one) the auxiliary head regressed on the final
Victory Points / 10. Regressed on the outcome, every student's value head
memorised its games in P2 round 1 (every decision of a game shares one
target): held-out MSE 0.46 against 0.33 for a constant zero.

Observations are stored sparse (about 5% of the 4,537 columns are not
zero), the offered actions and the teacher's probabilities in compressed
rows, so a few million decisions fit in a few GB.
"""

from __future__ import annotations

import copy
import dataclasses
import json
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

TEACHER_FORMAT = 2
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
    # float32 [rows]: the teacher's value of the position; NaN in a format 1
    # shard until ``add_teacher_values`` fills it in.
    values: np.ndarray

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


def teacher_outputs(
    network: PolicyValueNetwork,
    observations: np.ndarray,
    legal_indices: np.ndarray,
    legal_offsets: np.ndarray,
    *,
    chunk: int = 1024,
) -> tuple[np.ndarray, np.ndarray]:
    """The network's probabilities over each row's offered actions (float32,
    aligned with ``legal_indices``) and its value of each row (float32)."""

    rows = observations.shape[0]
    out = np.zeros(legal_indices.shape[0], dtype=np.float32)
    values = np.zeros(rows, dtype=np.float32)
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
            values[part] = network.value_head(hidden).squeeze(-1).numpy()
    return out, values


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
    probabilities, teacher_values = teacher_outputs(
        network, batch.observations, batch.legal_indices, batch.legal_offsets
    )
    return TeacherData(
        ruleset=ruleset,
        action_size=batch.action_size,
        obs_columns=columns,
        obs_values=values,
        obs_offsets=offsets,
        legal_indices=batch.legal_indices.astype(np.int32),
        legal_offsets=batch.legal_offsets.astype(np.int64),
        teacher=probabilities.astype(np.float16),
        actions=batch.actions.astype(np.int32),
        returns=batch.returns.astype(np.float32),
        victory_points=victory[batch.episode_ids][
            np.arange(seats.shape[0])[:, None], relative
        ],
        games=(batch.episode_ids + first_game).astype(np.int32),
        values=teacher_values,
    )


def add_teacher_values(
    data: TeacherData, network: PolicyValueNetwork, *, chunk: int = 2048
) -> TeacherData:
    """``data`` with ``network``'s value of every row."""

    values = np.zeros(data.rows, dtype=np.float32)
    network.eval()
    with torch.no_grad():
        for start in range(0, data.rows, chunk):
            part = np.arange(start, min(start + chunk, data.rows))
            hidden = network.trunk(torch.from_numpy(data.observations(part)))
            values[part] = network.value_head(hidden).squeeze(-1).numpy()
    return dataclasses.replace(data, values=values)


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
    "values",
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
        version = int(arrays["format"])
        if version not in (1, TEACHER_FORMAT):
            raise ValueError(f"teacher data format {version}")
        fields = {name: arrays[name] for name in _ARRAYS if name in arrays}
        if version == 1:
            fields["values"] = np.full(
                arrays["actions"].shape[0], np.nan, dtype=np.float32
            )
        return TeacherData(
            ruleset=str(arrays["ruleset"]),
            action_size=int(arrays["action_size"]),
            **fields,
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


PACK_MANIFEST = "manifest.json"
_PACK_FORMAT = 1
# Which count each array's length follows: decisions (an offsets array has
# one more), observation values or offered actions.
_PACK_COUNTS = {
    "obs_columns": "obs",
    "obs_values": "obs",
    "legal_indices": "legal",
    "teacher": "legal",
}


def _pack_entries(shards: Sequence[Path]) -> list[dict[str, object]]:
    return [
        {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "modified_ns": path.stat().st_mtime_ns,
        }
        for path in shards
    ]


def _open_pack(directory: Path, manifest: dict[str, object]) -> TeacherData:
    arrays = {
        name: np.load(directory / f"{name}.npy", mmap_mode="r") for name in _ARRAYS
    }
    return TeacherData(
        ruleset=str(manifest["ruleset"]),
        action_size=int(str(manifest["action_size"])),
        **arrays,
    )


def pack_teacher_data(shards: Sequence[Path], directory: Path) -> TeacherData:
    """``concatenate`` of the ``shards``, kept on disk in ``directory``.

    Every array is written there one shard at a time and read back as a
    read-only memory map, so building it holds one shard rather than the
    parts and their join (twice the data set: on 2026-10-23 twice the mixed
    distillation data, 5.2M rows, took the 16 GB machine to its limit), and
    training reads in only the rows of each minibatch. The arrays equal
    ``concatenate``'s element for element, so a student trains the same.
    A pack whose manifest names the same shards in the same order (resolved
    path, size, modification time) is reused; any other is rebuilt. The
    manifest is written last, so an interrupted pack is never reused.
    """

    if not shards:
        raise ValueError("nothing to pack")
    entries = _pack_entries(shards)
    manifest_path = directory / PACK_MANIFEST
    if manifest_path.exists():
        stored = json.loads(manifest_path.read_text())
        if stored.get("format") == _PACK_FORMAT and stored.get("shards") == entries:
            return _open_pack(directory, stored)
        manifest_path.unlink()
    directory.mkdir(parents=True, exist_ok=True)

    counts: list[dict[str, int]] = []
    catalogs: set[tuple[str, int]] = set()
    for path in shards:
        with np.load(path) as arrays:
            obs_offsets = arrays["obs_offsets"]
            counts.append(
                {
                    "row": int(obs_offsets.shape[0]) - 1,
                    "obs": int(obs_offsets[-1]),
                    "legal": int(arrays["legal_offsets"][-1]),
                }
            )
            catalogs.add((str(arrays["ruleset"]), int(arrays["action_size"])))
    if len(catalogs) != 1:
        raise ValueError("the shards come from different catalogs")
    ruleset, action_size = catalogs.pop()
    totals = {key: sum(count[key] for count in counts) for key in counts[0]}

    outputs: dict[str, np.ndarray] = {}
    base = dict.fromkeys(totals, 0)
    for path, count in zip(shards, counts, strict=True):
        part = load_teacher_data(path)
        for name in _ARRAYS:
            values = getattr(part, name)
            offsets = name.endswith("_offsets")
            key = _PACK_COUNTS.get(name, "row")
            if name not in outputs:
                outputs[name] = np.lib.format.open_memmap(
                    directory / f"{name}.npy",
                    mode="w+",
                    dtype=values.dtype,
                    shape=(totals[key] + offsets, *values.shape[1:]),
                )
            out = outputs[name]
            if out.dtype != values.dtype or out.shape[1:] != values.shape[1:]:
                raise ValueError(f"{path}: {name} is {values.dtype} {values.shape}")
            if offsets:
                # Each shard's offsets start at 0; shift them past the rows
                # (observation values or offered actions) packed before it.
                into = "obs" if name == "obs_offsets" else "legal"
                row = base["row"]
                out[row + 1 : row + count["row"] + 1] = values[1:] + base[into]
                out[0] = 0
            else:
                out[base[key] : base[key] + count[key]] = values
        for key in base:
            base[key] += count[key]
    for out in outputs.values():
        out.flush()  # type: ignore[attr-defined]
    del outputs
    manifest: dict[str, object] = {
        "format": _PACK_FORMAT,
        "ruleset": ruleset,
        "action_size": action_size,
        "rows": totals["row"],
        "shards": entries,
    }
    manifest_path.write_text(json.dumps(manifest, indent=1) + "\n")
    return _open_pack(directory, manifest)


# -- the student ------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class StudentConfig:
    """How a student learns the teacher data (the same for every student)."""

    learning_rate: float = 3.0e-4
    warmup_steps: int = 200
    minibatch_size: int = 512
    epochs: int = 3
    value_coefficient: float = 0.5
    # What the value head is regressed on: "outcome" (the game's result for
    # the acting seat) or "teacher" (the teacher's value of the position).
    value_target: str = "outcome"
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
    # "constant" keeps the learning rate after the warm-up; "cosine" takes
    # it down to zero over every step of every epoch (the stage B retrain's
    # student plateaued at a constant 1e-3, 2026-10-21).
    schedule: str = "constant"

    def __post_init__(self) -> None:
        if self.learning_rate <= 0.0 or self.minibatch_size < 1 or self.epochs < 1:
            raise ValueError("learning rate, minibatch and epochs must be positive")
        if self.value_target not in ("outcome", "teacher"):
            raise ValueError("value_target is 'outcome' or 'teacher'")
        if self.schedule not in ("constant", "cosine"):
            raise ValueError("schedule is 'constant' or 'cosine'")


@dataclass(frozen=True, slots=True)
class StudentScore:
    """A student against the teacher on held-out rows."""

    rows: int
    cross_entropy: float  # to the teacher's distribution
    teacher_entropy: float  # the floor of the cross-entropy
    agreement: float  # top-1 match, rows offering two or more actions
    value_mse: float  # against the outcome
    vp_mse: float | None  # auxiliary head, VP / VP_SCALE
    # Against the teacher's value (NaN when the data has none).
    teacher_value_mse: float = math.nan


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


def _value_targets(data: TeacherData, value_target: str) -> np.ndarray:
    if value_target == "outcome":
        return data.returns
    if np.isnan(data.values).any():
        raise ValueError("the data has no teacher values (add_teacher_values)")
    return data.values


def _losses(
    network: PolicyValueNetwork,
    data: TeacherData,
    rows: np.ndarray,
    targets: np.ndarray,
) -> tuple[Tensor, Tensor, Tensor | None, Tensor, Tensor, Tensor]:
    """Policy cross-entropy, value MSE against ``targets[rows]`` and VP MSE
    (means over ``rows``), the student's log-probabilities and validity for
    scoring, and its values."""

    observations = torch.from_numpy(data.observations(rows))
    index, valid, target = data.legal(rows)
    valid_t = torch.from_numpy(valid)
    hidden = network.trunk(observations)
    logits = network.row_action_logits(hidden, torch.from_numpy(index))
    log_probs = torch.log_softmax(logits.masked_fill(~valid_t, MASKED_LOGIT), dim=-1)
    policy = -(torch.from_numpy(target) * log_probs.masked_fill(~valid_t, 0.0)).sum(1)
    value = network.value_head(hidden).squeeze(-1)
    value_loss = (value - torch.from_numpy(targets[rows])).square()
    head = _vp_head(network)
    vp_loss = None
    if head is not None:
        predicted = head(hidden)
        wanted = torch.from_numpy(data.victory_points[rows].astype(np.float32))
        vp_loss = (predicted - wanted / VP_SCALE).square().mean(dim=1).mean()
    return policy.mean(), value_loss.mean(), vp_loss, log_probs, valid_t, value


def score_student(
    network: PolicyValueNetwork,
    data: TeacherData,
    rows: np.ndarray,
    *,
    chunk: int = 2048,
) -> StudentScore:
    """``network`` against the teacher on ``rows``."""

    totals = {"ce": 0.0, "entropy": 0.0, "value": 0.0, "vp": 0.0, "teacher": 0.0}
    agree = counted = 0
    has_vp = _vp_head(network) is not None
    network.eval()
    with torch.no_grad():
        for start in range(0, rows.shape[0], chunk):
            part = rows[start : start + chunk]
            policy, value, vp, log_probs, valid, predicted = _losses(
                network, data, part, data.returns
            )
            gap = predicted.numpy() - data.values[part]
            totals["teacher"] += float(np.square(gap).sum())
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
        teacher_value_mse=totals["teacher"] / total,
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
    targets = _value_targets(data, config.value_target)
    train_rows, heldout_rows = split_rows(data, config.heldout_modulus)
    if heldout_rows.shape[0] > config.heldout_rows:
        heldout_rows = np.sort(
            generator.choice(heldout_rows, config.heldout_rows, replace=False)
        )
    optimizer = torch.optim.Adam(network.parameters(), lr=config.learning_rate)
    batches_per_epoch = -(-train_rows.shape[0] // config.minibatch_size)
    total_steps = max(batches_per_epoch * config.epochs, 1)
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
            policy, value, vp, _, _, _ = _losses(network, data, rows, targets)
            loss = policy + config.value_coefficient * value
            if vp is not None:
                loss = loss + config.vp_coefficient * vp
            steps += 1
            rate = config.learning_rate * min(1.0, steps / max(config.warmup_steps, 1))
            if config.schedule == "cosine":
                rate *= 0.5 * (1.0 + math.cos(math.pi * min(steps / total_steps, 1.0)))
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


# -- judging ------------------------------------------------------------------
def teacher_choices(data: TeacherData, rows: np.ndarray) -> np.ndarray:
    """The catalog index of the teacher's most probable action on each row."""

    index, valid, target = data.legal(rows)
    target = np.where(valid, target, -1.0)
    chosen: np.ndarray = index[np.arange(rows.shape[0]), target.argmax(axis=1)]
    return chosen


def student_choices(
    network: PolicyValueNetwork,
    data: TeacherData,
    rows: np.ndarray,
    *,
    chunk: int = 2048,
) -> np.ndarray:
    """The catalog index of the student's most probable action on each row."""

    out = np.zeros(rows.shape[0], dtype=np.int64)
    network.eval()
    with torch.no_grad():
        for start in range(0, rows.shape[0], chunk):
            part = rows[start : start + chunk]
            index, valid, _ = data.legal(part)
            hidden = network.trunk(torch.from_numpy(data.observations(part)))
            logits = network.row_action_logits(hidden, torch.from_numpy(index))
            logits = logits.masked_fill(~torch.from_numpy(valid), MASKED_LOGIT)
            best = logits.argmax(dim=1).numpy()
            out[start : start + part.shape[0]] = index[np.arange(part.shape[0]), best]
    return out


def choice_frequency(
    data: TeacherData, train_rows: np.ndarray, choices: np.ndarray
) -> np.ndarray:
    """How often each of ``choices`` was the teacher's choice on ``train_rows``
    that offered two or more actions."""

    offered = data.offered()[train_rows] > 1
    seen = np.bincount(
        teacher_choices(data, train_rows[offered]), minlength=data.action_size
    )
    counts: np.ndarray = seen[choices]
    return counts
