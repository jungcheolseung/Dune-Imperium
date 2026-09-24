"""Distil search labels into the network (expert iteration).

A LABEL row's target keeps the network's own distribution P0 over the
offered actions and tilts it inside the searched candidates C toward the
candidates the search valued higher::

    s_c  = log P0(c) + m_c / tau          m_c = mean playout value of c
    pi(c) = P0(C) * softmax(s)_c          for c in C
    pi(a) = P0(a)                         for a outside C

so an exact tie leaves P0 unchanged, a confident prior flips only on a clear
margin, and the argmax of pi is always a candidate. ``mode="hard"`` puts
all mass on the search's own choice instead. ``mode="clearhard"`` does that
only on rows where the search is clear -- its choice wins on both halves of
the worlds by a mean margin of at least ``clear_margin`` -- and treats every
other LABEL row as an anchor (target P0, anchor weight). ANCHOR rows target
P0 itself.
The value head is regressed on the game outcome z (winner +1, others
-1/3). The loss is the row-weighted cross-entropy to pi plus
``value_coefficient`` times the value MSE; training starts from the
incumbent, stops early on the held-out objective and keeps its best epoch.
"""

from __future__ import annotations

import math
import random
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import torch
from torch import Tensor

from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.config import RulesetConfig
from dune_imperium.training.checkpoint import load_checkpoint, save_checkpoint
from dune_imperium.training.expert import ANCHOR, LABEL, ExpertData
from dune_imperium.training.network import MASKED_LOGIT, PolicyValueNetwork


@dataclass(frozen=True, slots=True)
class DistillConfig:
    """Target construction and optimisation of one distillation."""

    mode: str = "tilt"
    tau: float = 0.005
    clear_margin: float = 0.01
    anchor_weight: float = 0.5
    value_coefficient: float = 0.5
    learning_rate: float = 1.0e-4
    warmup_steps: int = 100
    minibatch_size: int = 512
    max_epochs: int = 4
    max_grad_norm: float = 1.0
    heldout_modulus: int = 10
    seed: int = 0
    threads: int = 4

    def __post_init__(self) -> None:
        if self.mode not in ("tilt", "hard", "clearhard"):
            raise ValueError("mode is 'tilt', 'hard' or 'clearhard'")
        if self.tau <= 0.0:
            raise ValueError("tau must be positive")


# -- targets ---------------------------------------------------------------
def search_choice(candidates: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Position of the search's choice in each row's candidates (-1: none).

    The first candidate with the largest value summed over the worlds, the
    search's own tie rule; padded candidates (-1) never win.
    """

    totals = np.where(candidates[:, None, :] >= 0, values, np.nan).sum(axis=1)
    totals = np.where(candidates >= 0, totals, -np.inf)
    choice = np.argmax(totals, axis=1).astype(np.int64)
    choice[(candidates >= 0).sum(axis=1) < 2] = -1
    return choice


def is_clear(candidates: np.ndarray, values: np.ndarray, margin: float) -> bool:
    """Whether one row's search choice is clear.

    The choice (first largest sum over all worlds) must also win on the
    first half and on the second half of the worlds, and beat the
    runner-up's mean value by at least ``margin``.
    """

    valid = candidates >= 0
    if valid.sum() < 2:
        return False
    table = values[:, valid].astype(np.float64)
    worlds = table.shape[0]
    if worlds < 2:
        return False
    choice = int(np.argmax(table.sum(axis=0)))
    half = worlds // 2
    first = int(np.argmax(table[:half].sum(axis=0)))
    second = int(np.argmax(table[half:].sum(axis=0)))
    means = table.mean(axis=0)
    runner_up = np.max(np.delete(means, choice))
    return first == second == choice and means[choice] - runner_up >= margin


def clear_rows(data: ExpertData, rows: np.ndarray, margin: float) -> np.ndarray:
    """``is_clear`` for each of ``rows`` (False for non-LABEL rows)."""

    return np.asarray(
        [
            data.kind[row] == LABEL
            and is_clear(data.candidates[row], data.values[row], margin)
            for row in rows
        ],
        dtype=bool,
    )


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max()
    weights = np.exp(shifted)
    result: np.ndarray = weights / weights.sum()
    return result


def row_target(
    kind: int,
    legal: np.ndarray,
    prior_logits: np.ndarray,
    candidates: np.ndarray,
    values: np.ndarray,
    config: DistillConfig,
) -> np.ndarray:
    """The target distribution over one row's (ascending) legal actions."""

    prior = _softmax(prior_logits.astype(np.float64))
    if kind != LABEL:
        return prior
    valid = candidates >= 0
    chosen = candidates[valid]
    position = np.searchsorted(legal, chosen)
    if np.any(legal[position] != chosen):
        raise ValueError("a candidate is not in the row's legal set")
    table = values[:, valid].astype(np.float64)
    if config.mode == "clearhard" and not is_clear(
        candidates, values, config.clear_margin
    ):
        return prior
    if config.mode in ("hard", "clearhard"):
        best = int(np.argmax(table.sum(axis=0)))
        target = np.zeros_like(prior)
        target[position[best]] = 1.0
        return target
    mean = table.mean(axis=0)
    mass = prior[position]
    inside = mass.sum()
    scores = np.log(np.maximum(mass, 1e-300)) + mean / config.tau
    tilted = _softmax(scores)
    target = prior.copy()
    target[position] = inside * tilted
    return target


def policy_targets(
    data: ExpertData, rows: np.ndarray, config: DistillConfig
) -> tuple[np.ndarray, np.ndarray]:
    """Targets for ``rows`` as CSR (probabilities, offsets) aligned to legal."""

    pieces: list[np.ndarray] = []
    offsets = np.zeros(len(rows) + 1, dtype=np.int64)
    for position, row in enumerate(rows):
        start, stop = data.legal_offsets[row], data.legal_offsets[row + 1]
        target = row_target(
            int(data.kind[row]),
            data.legal_indices[start:stop],
            data.prior_logits[start:stop],
            data.candidates[row],
            data.values[row],
            config,
        )
        pieces.append(target.astype(np.float32))
        offsets[position + 1] = offsets[position] + len(target)
    flat = np.concatenate(pieces) if pieces else np.zeros(0, dtype=np.float32)
    return flat, offsets


def label_noise(data: ExpertData, rows: np.ndarray) -> dict[str, float]:
    """How much the labels could teach, and how noisy they are.

    ``override``: the search's choice is not the first candidate (the
    network's own pick). ``clear``: the choice wins on worlds {0,1} and on
    {2,3} alike with a mean margin of at least 0.01 over the runner-up.
    """

    label_rows = rows[data.kind[rows] == LABEL]
    if len(label_rows) == 0:
        return {"label_rows": 0.0}
    candidates = data.candidates[label_rows]
    values = data.values[label_rows]
    choice = search_choice(candidates, values)
    worlds = values.shape[1]
    override = float(np.mean(choice > 0))
    ties = gaps = clear = split_flip = 0
    counted = 0
    for index in range(len(label_rows)):
        valid = candidates[index] >= 0
        table = values[index][:, valid].astype(np.float64)
        means = table.mean(axis=0)
        order = np.argsort(-means, kind="stable")
        gap = float(means[order[0]] - means[order[1]])
        ties += int(gap == 0.0)
        gaps += int(gap < 0.005)
        if worlds >= 4:
            half = worlds // 2
            first = int(np.argmax(table[:half].sum(axis=0)))
            second = int(np.argmax(table[half:].sum(axis=0)))
            split_flip += int(first != second)
            clear += int(first == second == choice[index] and gap >= 0.01)
            counted += 1
    total = len(label_rows)
    return {
        "label_rows": float(total),
        "override": override,
        "exact_ties": ties / total,
        "near_ties_lt_0.005": gaps / total,
        "clear": (clear / counted) if counted else float("nan"),
        "half_split_flip": (split_flip / counted) if counted else float("nan"),
    }


# -- the network over legal sets ------------------------------------------
def legal_log_probs(
    network: PolicyValueNetwork, hidden: Tensor, index: Tensor, valid: Tensor
) -> Tensor:
    """Log-probabilities over each row's legal actions ``[B, L]``.

    Reads only the gathered policy-head rows; padded slots get
    ``MASKED_LOGIT`` so they carry no probability.
    """

    weight = network.policy_head.weight[index]
    bias = network.policy_head.bias[index]
    logits = torch.einsum("bh,blh->bl", hidden, weight) + bias
    logits = logits.masked_fill(~valid, MASKED_LOGIT)
    return torch.log_softmax(logits, dim=-1)


@dataclass
class _Padded:
    index: np.ndarray
    valid: np.ndarray
    target: np.ndarray


def _pad(
    data: ExpertData, rows: np.ndarray, targets: np.ndarray, target_offsets: np.ndarray
) -> _Padded:
    lengths = data.legal_offsets[rows + 1] - data.legal_offsets[rows]
    width = int(lengths.max()) if len(rows) else 1
    index = np.zeros((len(rows), width), dtype=np.int64)
    valid = np.zeros((len(rows), width), dtype=bool)
    target = np.zeros((len(rows), width), dtype=np.float32)
    for position, row in enumerate(rows):
        start = data.legal_offsets[row]
        length = int(lengths[position])
        index[position, :length] = data.legal_indices[start : start + length]
        valid[position, :length] = True
        target[position, :length] = targets[
            target_offsets[position] : target_offsets[position + 1]
        ]
    return _Padded(index=index, valid=valid, target=target)


# -- evaluation ------------------------------------------------------------
@dataclass
class HoldoutStats:
    """Held-out behaviour of one network on the labels (see ``evaluate``)."""

    label_rows: int = 0
    anchor_rows: int = 0
    agree_target: float = float("nan")
    agree_search: float = float("nan")
    agree_prior: float = float("nan")
    agree_override: float = float("nan")
    override_rows: int = 0
    label_ce: float = float("nan")
    anchor_agree_clear: float = float("nan")
    anchor_kl: float = float("nan")
    value_mse: float = float("nan")
    explained_variance: float = float("nan")
    objective: float = float("nan")
    prior_max_abs_diff: float = float("nan")
    per_game: dict[str, list[float]] = field(default_factory=dict)


def _forward(
    network: PolicyValueNetwork,
    data: ExpertData,
    rows: np.ndarray,
    padded: _Padded,
    batch: int,
) -> tuple[np.ndarray, np.ndarray]:
    log_probs = np.zeros(padded.index.shape, dtype=np.float32)
    values = np.zeros(len(rows), dtype=np.float32)
    network.eval()
    with torch.no_grad():
        for start in range(0, len(rows), batch):
            part = slice(start, start + batch)
            observations = torch.from_numpy(
                data.observations[rows[part]].astype(np.int32)
            )
            hidden = network.trunk(observations)
            log_probs[part] = legal_log_probs(
                network,
                hidden,
                torch.from_numpy(padded.index[part]),
                torch.from_numpy(padded.valid[part]),
            ).numpy()
            values[part] = network.value_head(hidden).squeeze(-1).numpy()
    return log_probs, values


def evaluate(
    network: PolicyValueNetwork,
    data: ExpertData,
    rows: np.ndarray,
    config: DistillConfig,
    *,
    check_prior: bool = False,
) -> HoldoutStats:
    """Agreement, cross-entropy and value error of ``network`` on ``rows``.

    ``agree_target``: argmax over legal equals the target's argmax, on the
    LABEL rows whose target differs from the prior (all LABEL rows, or with
    ``clearhard`` the clear ones). ``agree_search``: equals the search's
    choice. ``agree_override``: the same on rows where the search overrode
    the network's own pick.
    ``anchor_agree_clear``: on ANCHOR rows whose prior's top two differ by
    at least 0.1 nat, the argmax still equals the prior's. ``anchor_kl``:
    mean KL(P0 || network) on ANCHOR rows. ``prior_max_abs_diff`` (only with
    ``check_prior``): the largest difference between this network's logits
    and the stored prior logits -- the pipeline check when ``network`` is
    the teacher.
    """

    stats = HoldoutStats()
    if len(rows) == 0:
        return stats
    targets, target_offsets = policy_targets(data, rows, config)
    padded = _pad(data, rows, targets, target_offsets)
    log_probs, values = _forward(network, data, rows, padded, config.minibatch_size)
    masked = np.where(padded.valid, log_probs, -np.inf)
    student = masked.argmax(axis=1)
    target_best = np.where(padded.valid, padded.target, -1.0).argmax(axis=1)
    kind = data.kind[rows]
    is_label = kind == LABEL
    # Rows whose target teaches something beyond the prior: every LABEL row,
    # or with clearhard only the clear ones (the rest target the prior).
    taught = (
        is_label & clear_rows(data, rows, config.clear_margin)
        if config.mode == "clearhard"
        else is_label
    )
    is_anchor = kind == ANCHOR
    ce = -(padded.target * np.where(padded.valid, log_probs, 0.0)).sum(axis=1)
    choice = search_choice(data.candidates[rows], data.values[rows])
    search_index = np.full(len(rows), -1, dtype=np.int64)
    prior_best = np.zeros(len(rows), dtype=np.int64)
    prior_clear = np.zeros(len(rows), dtype=bool)
    kl = np.zeros(len(rows), dtype=np.float64)
    for position, row in enumerate(rows):
        start, stop = data.legal_offsets[row], data.legal_offsets[row + 1]
        prior_logits = data.prior_logits[start:stop].astype(np.float64)
        order = np.argsort(-prior_logits, kind="stable")
        prior_best[position] = order[0]
        prior_clear[position] = (
            len(order) > 1 and prior_logits[order[0]] - prior_logits[order[1]] >= 0.1
        )
        if choice[position] >= 0:
            chosen = data.candidates[row, choice[position]]
            search_index[position] = int(
                np.searchsorted(data.legal_indices[start:stop], chosen)
            )
        if is_anchor[position]:
            prior = _softmax(prior_logits)
            length = stop - start
            kl[position] = float(
                np.sum(
                    prior
                    * (np.log(np.maximum(prior, 1e-300)) - log_probs[position, :length])
                )
            )
    z = data.z[rows]
    error = (values - z) ** 2
    games = data.game_seed[rows]
    stats.label_rows = int(is_label.sum())
    stats.anchor_rows = int(is_anchor.sum())
    if stats.label_rows:
        if taught.any():
            stats.agree_target = float(np.mean(student[taught] == target_best[taught]))
        stats.agree_search = float(np.mean(student[is_label] == search_index[is_label]))
        stats.agree_prior = float(np.mean(student[is_label] == prior_best[is_label]))
        overrode = is_label & (search_index != prior_best) & (search_index >= 0)
        stats.override_rows = int(overrode.sum())
        if stats.override_rows:
            stats.agree_override = float(
                np.mean(student[overrode] == search_index[overrode])
            )
        stats.label_ce = float(np.mean(ce[is_label]))
    if stats.anchor_rows:
        clear = is_anchor & prior_clear
        if clear.any():
            stats.anchor_agree_clear = float(
                np.mean(student[clear] == prior_best[clear])
            )
        stats.anchor_kl = float(np.mean(kl[is_anchor]))
    stats.value_mse = float(np.mean(error))
    variance = float(np.var(z))
    stats.explained_variance = (
        1.0 - stats.value_mse / variance if variance > 0 else float("nan")
    )
    weights = _row_weights(data, rows, config)
    stats.objective = float(
        np.sum(weights * ce) / max(np.sum(weights), 1e-12)
        + config.value_coefficient * stats.value_mse
    )
    if check_prior:
        diffs = []
        for position, row in enumerate(rows):
            start, stop = data.legal_offsets[row], data.legal_offsets[row + 1]
            recomputed = _logits_for(
                network, data, row, padded.index[position, : stop - start]
            )
            diffs.append(
                float(np.max(np.abs(recomputed - data.prior_logits[start:stop])))
            )
        stats.prior_max_abs_diff = max(diffs)
    stats.per_game = _per_game(
        games,
        {
            "agree_target": np.where(taught, student == target_best, np.nan),
            "label_rows": is_label.astype(np.float64),
            "value_error": error,
            "anchor_kl": np.where(is_anchor, kl, np.nan),
        },
    )
    return stats


def _logits_for(
    network: PolicyValueNetwork, data: ExpertData, row: int, index: np.ndarray
) -> np.ndarray:
    with torch.no_grad():
        hidden = network.trunk(
            torch.from_numpy(data.observations[row : row + 1].astype(np.int32))
        )
        logits = network.action_logits(hidden, torch.from_numpy(index))
    result: np.ndarray = logits[0].numpy()
    return result


def _per_game(
    games: np.ndarray, columns: Mapping[str, np.ndarray]
) -> dict[str, list[float]]:
    """Per-game means (NaN-aware) for game-clustered comparisons."""

    order = np.unique(games)
    out: dict[str, list[float]] = {"game_seed": [float(g) for g in order]}
    for name, column in columns.items():
        means = []
        for game in order:
            part = column[games == game]
            finite = part[np.isfinite(part)]
            means.append(float(finite.mean()) if finite.size else float("nan"))
        out[name] = means
    return out


def clustered_difference(
    student: HoldoutStats,
    reference: HoldoutStats,
    key: str,
    *,
    draws: int = 4000,
    seed: int = 0,
) -> tuple[float, float, float]:
    """Mean of (student - reference) per game with a game-bootstrap 95% CI."""

    a = np.asarray(student.per_game[key], dtype=np.float64)
    b = np.asarray(reference.per_game[key], dtype=np.float64)
    difference = a - b
    difference = difference[np.isfinite(difference)]
    if difference.size == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, difference.size, size=(draws, difference.size))
    means = difference[picks].mean(axis=1)
    return (
        float(difference.mean()),
        float(np.quantile(means, 0.025)),
        float(np.quantile(means, 0.975)),
    )


# -- training --------------------------------------------------------------
def _row_weights(
    data: ExpertData, rows: np.ndarray, config: DistillConfig
) -> np.ndarray:
    kind = data.kind[rows]
    anchored = kind == ANCHOR
    if config.mode == "clearhard":
        # Unclear LABEL rows are trained as anchors.
        anchored = anchored | (
            (kind == LABEL) & ~clear_rows(data, rows, config.clear_margin)
        )
    base = np.where(anchored, config.anchor_weight, 1.0)
    weights: np.ndarray = (base * data.weight[rows]).astype(np.float32)
    return weights


@dataclass
class DistillReport:
    before: HoldoutStats
    per_epoch: list[HoldoutStats]
    best_epoch: int
    train_rows: int
    heldout_rows: int
    seconds: float
    epoch_seconds: list[float]


def distill(
    network: PolicyValueNetwork,
    data: ExpertData,
    config: DistillConfig,
    *,
    log: Callable[[int, HoldoutStats, float], None] | None = None,
) -> DistillReport:
    """Train ``network`` in place on the non-held-out rows; keep the best epoch.

    ``best_epoch`` 0 means no epoch improved the held-out objective and the
    incoming weights were kept.
    """

    started = time.perf_counter()
    torch.set_num_threads(config.threads)
    torch.manual_seed(config.seed)
    generator = random.Random(config.seed)
    heldout = data.heldout(config.heldout_modulus)
    train_rows = np.flatnonzero(~heldout)
    test_rows = np.flatnonzero(heldout)
    targets, target_offsets = policy_targets(data, train_rows, config)
    padded = _pad(data, train_rows, targets, target_offsets)
    weights = _row_weights(data, train_rows, config)
    before = evaluate(network, data, test_rows, config)
    best_objective = before.objective
    best_state = {k: v.clone() for k, v in network.state_dict().items()}
    best_epoch = 0
    optimizer = torch.optim.Adam(network.parameters(), lr=config.learning_rate)
    step = 0
    per_epoch: list[HoldoutStats] = []
    epoch_seconds: list[float] = []
    for epoch in range(1, config.max_epochs + 1):
        epoch_started = time.perf_counter()
        order = list(range(len(train_rows)))
        generator.shuffle(order)
        network.train()
        for start in range(0, len(order), config.minibatch_size):
            batch = np.asarray(order[start : start + config.minibatch_size])
            rows = train_rows[batch]
            observations = torch.from_numpy(data.observations[rows].astype(np.int32))
            hidden = network.trunk(observations)
            log_probs = legal_log_probs(
                network,
                hidden,
                torch.from_numpy(padded.index[batch]),
                torch.from_numpy(padded.valid[batch]),
            )
            target = torch.from_numpy(padded.target[batch])
            valid = torch.from_numpy(padded.valid[batch])
            ce = -(target * log_probs.masked_fill(~valid, 0.0)).sum(dim=1)
            weight = torch.from_numpy(weights[batch])
            policy_loss = (weight * ce).sum() / weight.sum().clamp(min=1e-12)
            value = network.value_head(hidden).squeeze(-1)
            value_loss = torch.nn.functional.mse_loss(
                value, torch.from_numpy(data.z[rows])
            )
            loss = policy_loss + config.value_coefficient * value_loss
            if not torch.isfinite(loss):
                raise FloatingPointError(
                    f"non-finite loss at epoch {epoch}, step {step}"
                )
            for group in optimizer.param_groups:
                group["lr"] = config.learning_rate * min(
                    1.0, (step + 1) / config.warmup_steps
                )
            optimizer.zero_grad()
            loss.backward()  # type: ignore[no-untyped-call]
            torch.nn.utils.clip_grad_norm_(network.parameters(), config.max_grad_norm)
            optimizer.step()
            step += 1
        stats = evaluate(network, data, test_rows, config)
        per_epoch.append(stats)
        epoch_seconds.append(time.perf_counter() - epoch_started)
        if log is not None:
            log(epoch, stats, epoch_seconds[-1])
        if math.isfinite(stats.objective) and stats.objective < best_objective:
            best_objective = stats.objective
            best_state = {k: v.clone() for k, v in network.state_dict().items()}
            best_epoch = epoch
        else:
            break
    network.load_state_dict(best_state)
    network.eval()
    return DistillReport(
        before=before,
        per_epoch=per_epoch,
        best_epoch=best_epoch,
        train_rows=len(train_rows),
        heldout_rows=len(test_rows),
        seconds=time.perf_counter() - started,
        epoch_seconds=epoch_seconds,
    )


def save_candidate(
    path: Path,
    network: PolicyValueNetwork,
    *,
    parent: Path,
    metadata: Mapping[str, object],
) -> None:
    """Write a candidate that ``checkpoint:`` and ``search:`` seats load.

    Keeps the parent's ruleset and iteration, writes the catalog templates,
    and reloads the file to check the weights came back unchanged.
    """

    _, info = load_checkpoint(parent)
    config = RulesetConfig.from_identifier(info.ruleset)
    codec = ActionCodec(config)
    if network.action_size != codec.size:
        raise ValueError("network does not match the parent's catalog")
    save_checkpoint(
        path,
        network,
        ruleset=info.ruleset,
        iteration=info.iteration,
        metadata=dict(metadata),
        optimizer_state=None,
        codec=codec,
    )
    reloaded, _ = load_checkpoint(path)
    for (name, a), (_, b) in zip(
        network.state_dict().items(), reloaded.state_dict().items(), strict=True
    ):
        if not torch.equal(a.cpu(), b.cpu()):
            raise ValueError(f"reloaded candidate differs in {name}")


def stats_summary(stats: HoldoutStats) -> dict[str, float | int]:
    """The scalar fields of ``stats`` (per-game lists dropped)."""

    raw = asdict(stats)
    raw.pop("per_game", None)
    return {key: value for key, value in raw.items()}
