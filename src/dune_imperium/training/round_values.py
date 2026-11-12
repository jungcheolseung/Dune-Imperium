"""The self-play value's data and fit: round-start positions toward the final result.

docs/entity-self-play-plan.md stage 1 (sections 3.1, 3.2, 4.1). A search seat
reads its value where a playout stops: the first state of the next round
after the Round Start draw (``rollout_agent.past_horizon``), or the finished
game. So the value learns at exactly those states:

- ``collect_rounds`` plays greedy games at a ``TableMix`` table and keeps,
  for every learning seat and every round that begins, the seat's view at
  that state, with the seat's final place, every seat's final Victory Points
  and the seat's Leader.
- ``lambda_targets`` turns one seat's rounds into round-level TD(lambda)
  targets: the last round's target is the graded reward of the final place
  (``pettingzoo_env.graded_reward``), an earlier round's is
  ``(1 - lambda) * V(next round) + lambda * target(next round)``.
- ``fit_round_values`` trains only a value branch (``with_value_branch``)
  and its auxiliary heads toward them, a few times over, recomputing the
  targets with the new value each time (fitted TD(lambda)). Games whose
  seed is a multiple of ``heldout_modulus`` are held out, and each fit keeps
  its epoch with the lowest held-out loss. The policy is frozen, so the file
  plays exactly as the network it started from.
"""

from __future__ import annotations

import copy
import time
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Final

import numpy as np
import torch
from torch import Tensor, nn

from dune_imperium.adapters.observation_encoding import OBSERVATION_SIZE
from dune_imperium.adapters.pettingzoo_env import graded_reward
from dune_imperium.agents.registry import make_agent
from dune_imperium.config import RulesetConfig
from dune_imperium.content.rulesets import content_for
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game
from dune_imperium.training.entity_network import EntityNetwork
from dune_imperium.training.policy import encoded_view
from dune_imperium.training.stored_views import (
    LAYOUT_KEY,
    column_moves,
    layout_entry,
    move_columns,
    recorded_layout,
    stored_layout,
)
from dune_imperium.training.stored_views import (
    observation_column_map as observation_column_map,
)
from dune_imperium.training.stored_views import (
    observation_layout as observation_layout,
)
from dune_imperium.training.table_mix import TABLE_KINDS, TableMix
from dune_imperium.training.teacher import VP_SCALE, gather_rows
from dune_imperium.training.torch_policy import resolve_device

ROUND_FORMAT: Final = 1
_SEATS: Final = 4
_ARRAYS: Final = (
    "obs_columns",
    "obs_values",
    "obs_offsets",
    "games",
    "seats",
    "rounds",
    "ranks",
    "victory_points",
    "tables",
    "leaders",
    "dealt",
)


@dataclass(frozen=True, slots=True)
class RoundData:
    """Round-start views of learning seats, with how their games ended."""

    ruleset: str
    leader_names: tuple[str, ...]
    obs_columns: np.ndarray  # int16 [non-zero values]
    obs_values: np.ndarray  # int16 [non-zero values]
    obs_offsets: np.ndarray  # int64 [rows + 1]
    games: np.ndarray  # int64 [rows]: the game's seed
    seats: np.ndarray  # int8 [rows]: the seat
    rounds: np.ndarray  # int16 [rows]: the round that began
    ranks: np.ndarray  # int8 [rows]: the seat's final place, 1-4
    victory_points: np.ndarray  # int16 [rows, 4]: final VP, the seat first
    tables: np.ndarray  # int8 [rows]: TABLE_KINDS index of the game's table
    leaders: np.ndarray  # int16 [rows]: index into leader_names
    # int8 [rows]: 1 where the game's Leaders were dealt (``TableMix``'s
    # ``dealt_share``), 0 where they were drafted; a shard written before the
    # share existed reads as all drafted.
    dealt: np.ndarray

    @property
    def rows(self) -> int:
        return int(self.games.shape[0])

    def observations(self, rows: np.ndarray) -> np.ndarray:
        """The dense observations ``int32 [len(rows), OBSERVATION_SIZE]``."""

        columns, offsets = gather_rows(self.obs_columns, self.obs_offsets, rows)
        values, _ = gather_rows(self.obs_values, self.obs_offsets, rows)
        dense = np.zeros((rows.shape[0], OBSERVATION_SIZE), dtype=np.int32)
        owner = np.repeat(np.arange(rows.shape[0]), np.diff(offsets))
        dense[owner, columns.astype(np.int64)] = values
        return dense

    def next_rows(self) -> np.ndarray:
        """Each row's next round of the same game and seat, or -1 for the
        seat's last round."""

        order = np.lexsort((self.rounds, self.seats, self.games))
        following = np.full(self.rows, -1, dtype=np.int64)
        same = (self.games[order[1:]] == self.games[order[:-1]]) & (
            self.seats[order[1:]] == self.seats[order[:-1]]
        )
        following[order[:-1][same]] = order[1:][same]
        return following

    def heldout(self, modulus: int) -> np.ndarray:
        """Whether each row's game is held out."""

        mask: np.ndarray = self.games % modulus == 0
        return mask


def migrate_rounds(data: RoundData, column_map: np.ndarray) -> RoundData:
    """``data``'s views at this tree's columns (``observation_column_map``).

    ``load_rounds`` moves a shard as it loads; this is the copy path of
    ``scripts/train/migrate_rounds.py`` from before shards recorded their
    layout, kept as the reference the loaders are tested against.
    """

    if data.obs_columns.size and int(data.obs_columns.max()) >= column_map.size:
        raise ValueError("the views have columns past the old layout")
    columns = column_map[data.obs_columns.astype(np.int64)]
    return replace(data, obs_columns=columns.astype(data.obs_columns.dtype))


def save_rounds(data: RoundData, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.stem + ".tmp.npz")
    np.savez(
        temporary,
        format=np.asarray(ROUND_FORMAT),
        ruleset=np.asarray(data.ruleset),
        leader_names=np.asarray(data.leader_names, dtype=str),
        **{name: getattr(data, name) for name in _ARRAYS}
        | {LAYOUT_KEY: layout_entry()},
    )
    temporary.replace(path)


def load_rounds(path: Path, *, layout: Mapping[str, Any] | None = None) -> RoundData:
    """A shard with its views at this tree's columns.

    They move by segment name from the layout the shard records, or for a
    shard written before shards recorded one, from ``layout`` or the
    folder's ``observation-layout.json`` (``training.stored_views``).
    """

    with np.load(path) as arrays:
        if int(arrays["format"]) != ROUND_FORMAT:
            raise ValueError(f"round data format {int(arrays['format'])}")
        fields = {name: arrays[name] for name in _ARRAYS if name in arrays}
        fields.setdefault("dealt", np.zeros(arrays["games"].shape[0], np.int8))
        found = stored_layout(path, recorded_layout(arrays), layout=layout)
        fields["obs_columns"] = move_columns(fields["obs_columns"], found, path)
        return RoundData(
            ruleset=str(arrays["ruleset"]),
            leader_names=tuple(str(name) for name in arrays["leader_names"]),
            **fields,
        )


def concatenate_rounds(parts: Sequence[RoundData]) -> RoundData:
    """One table of several shards (Leaders renumbered into one list)."""

    if not parts:
        raise ValueError("no round data to join")
    if len({part.ruleset for part in parts}) != 1:
        raise ValueError("the shards are of different rulesets")
    names = sorted({name for part in parts for name in part.leader_names})
    index = {name: number for number, name in enumerate(names)}
    offsets = [np.zeros(1, dtype=np.int64)]
    base = 0
    for part in parts:
        offsets.append(part.obs_offsets[1:] + base)
        base += int(part.obs_offsets[-1])
    return RoundData(
        ruleset=parts[0].ruleset,
        leader_names=tuple(names),
        obs_columns=np.concatenate([part.obs_columns for part in parts]),
        obs_values=np.concatenate([part.obs_values for part in parts]),
        obs_offsets=np.concatenate(offsets),
        games=np.concatenate([part.games for part in parts]),
        seats=np.concatenate([part.seats for part in parts]),
        rounds=np.concatenate([part.rounds for part in parts]),
        ranks=np.concatenate([part.ranks for part in parts]),
        victory_points=np.concatenate([part.victory_points for part in parts]),
        tables=np.concatenate([part.tables for part in parts]),
        leaders=np.concatenate(
            [
                np.asarray(
                    [index[part.leader_names[number]] for number in part.leaders],
                    dtype=np.int16,
                )
                for part in parts
            ]
        ),
        dealt=np.concatenate([part.dealt for part in parts]),
    )


def load_round_shards(
    directory: Path, *, layout: Mapping[str, Any] | None = None
) -> RoundData:
    """Every shard of ``directory`` as one table, as ``concatenate_rounds``,
    at this tree's columns (``load_rounds``).

    The observations are nearly all of the bytes (about 3 GB for 100,000
    games), so they are copied shard by shard into arrays sized first: the
    peak is the table plus one shard, not twice the table (the main run's
    machine has 16 GB). Every shard's layout is checked before that, so a
    shard that cannot move is refused before anything is read.
    """

    paths = sorted(directory.glob("rounds-*.npz"))
    if not paths:
        raise ValueError(f"no round shards in {directory}")
    names: set[str] = set()
    sizes = []
    rulesets = set()
    for path in paths:
        with np.load(path) as arrays:
            names.update(str(name) for name in arrays["leader_names"])
            sizes.append(int(arrays["obs_offsets"][-1]))
            rulesets.add(str(arrays["ruleset"]))
            found = stored_layout(path, recorded_layout(arrays), layout=layout)
        column_moves(path, found)
    if len(rulesets) != 1:
        raise ValueError("the shards are of different rulesets")
    columns = np.empty(sum(sizes), dtype=np.int16)
    values = np.empty(sum(sizes), dtype=np.int16)
    parts = []
    start = 0
    for path, size in zip(paths, sizes, strict=True):
        part = load_rounds(path, layout=layout)
        columns[start : start + size] = part.obs_columns
        values[start : start + size] = part.obs_values
        start += size
        # The rest is small: keep it, without the shard's observations.
        empty = np.zeros(0, dtype=np.int16)
        parts.append(replace(part, obs_columns=empty, obs_values=empty))
    joined = concatenate_rounds(parts)
    assert tuple(sorted(names)) == joined.leader_names
    return replace(joined, obs_columns=columns, obs_values=values)


# -- collection -----------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class CollectSpec:
    """What a collection plays: the agents of each table kind and the mix."""

    config: RulesetConfig
    learner: str
    x: str
    app: str = "app_ai"
    past: tuple[str, ...] = ()
    mix: TableMix = field(default_factory=lambda: TableMix.from_shares({"self": 1}))


@dataclass
class _Rows:
    observations: list[np.ndarray] = field(default_factory=list)
    games: list[int] = field(default_factory=list)
    seats: list[int] = field(default_factory=list)
    rounds: list[int] = field(default_factory=list)
    ranks: list[int] = field(default_factory=list)
    victory_points: list[list[int]] = field(default_factory=list)
    tables: list[int] = field(default_factory=list)
    leaders: list[str] = field(default_factory=list)
    dealt: list[int] = field(default_factory=list)


def _round_starts(
    engine: UprisingRulesEngine, learners: Sequence[int]
) -> tuple[Callable[[GameState], None], list[tuple[int, int, np.ndarray, str]]]:
    """A runner hook keeping ``(round, seat, view, Leader)`` of each learning
    seat at the first state of every round past its Round Start, the state a
    search playout's leaf is read at (``past_horizon``)."""

    kept: list[tuple[int, int, np.ndarray, str]] = []
    reached = [0]

    def hook(state: GameState) -> None:
        if (
            state.round_number > reached[0]
            and state.phase is not GamePhase.ROUND_START
            and state.phase is not GamePhase.FINISHED
        ):
            reached[0] = state.round_number
            for seat in learners:
                view = engine.observe(state, seat)
                leader = state.players[seat].leader_id or ""
                kept.append((state.round_number, seat, encoded_view(view), leader))

    return hook, kept


def collect_rounds(spec: CollectSpec, games: Sequence[tuple[int, int]]) -> RoundData:
    """Play ``games`` (``(index, seed)``: the mix position and the game seed)
    and keep their learning seats' round starts.

    A game whose Leaders the mix deals is played without the draft, the
    dealt Leaders in their seats (``UprisingRulesEngine(leader_ids=...)``,
    the forced-Leader path of the tournament); every other option stays.
    """

    drafting = UprisingRulesEngine()
    undrafted = replace(spec.config, leader_draft=False)
    pool = tuple(leader.leader_id for leader in content_for(undrafted).leaders)
    rows = _Rows()
    for index, seed in games:
        table = spec.mix.table(
            index,
            seed,
            learner=spec.learner,
            x=spec.x,
            app=spec.app,
            past=spec.past,
            leader_pool=pool,
        )
        if table.leaders is None:
            engine, config = drafting, spec.config
        else:
            engine, config = UprisingRulesEngine(leader_ids=table.leaders), undrafted
        agents = [
            make_agent(kind, seed * _SEATS + seat, config)
            for seat, kind in enumerate(table.agents)
        ]
        hook, kept = _round_starts(engine, table.learners)
        simulation = run_policy_game(engine, config, seed, agents, on_state=hook)
        places = {standing.player: standing for standing in simulation.standings}
        for round_number, seat, observation, leader in kept:
            rows.observations.append(observation)
            rows.games.append(seed)
            rows.seats.append(seat)
            rows.rounds.append(round_number)
            rows.ranks.append(places[seat].rank)
            rows.victory_points.append(
                [
                    places[(seat + offset) % _SEATS].victory_points
                    for offset in range(_SEATS)
                ]
            )
            rows.tables.append(TABLE_KINDS.index(table.kind))
            rows.leaders.append(leader)
            rows.dealt.append(int(table.leaders is not None))
    return _as_data(spec.config.identifier, rows)


def _as_data(ruleset: str, rows: _Rows) -> RoundData:
    names = tuple(sorted(set(rows.leaders)))
    if rows.observations:
        dense = np.stack(rows.observations)
    else:
        dense = np.zeros((0, OBSERVATION_SIZE), dtype=np.int32)
    if dense.max(initial=0) > np.iinfo(np.int16).max or dense.min(initial=0) < 0:
        raise ValueError("observation values exceed the int16 storage range")
    owner, columns = np.nonzero(dense)
    offsets = np.zeros(dense.shape[0] + 1, dtype=np.int64)
    np.cumsum(np.bincount(owner, minlength=dense.shape[0]), out=offsets[1:])
    return RoundData(
        ruleset=ruleset,
        leader_names=names,
        obs_columns=columns.astype(np.int16),
        obs_values=dense[owner, columns].astype(np.int16),
        obs_offsets=offsets,
        games=np.asarray(rows.games, dtype=np.int64),
        seats=np.asarray(rows.seats, dtype=np.int8),
        rounds=np.asarray(rows.rounds, dtype=np.int16),
        ranks=np.asarray(rows.ranks, dtype=np.int8),
        victory_points=np.asarray(rows.victory_points, dtype=np.int16).reshape(
            -1, _SEATS
        ),
        tables=np.asarray(rows.tables, dtype=np.int8),
        leaders=np.asarray(
            [names.index(leader) for leader in rows.leaders], dtype=np.int16
        ),
        dealt=np.asarray(rows.dealt, dtype=np.int8),
    )


# -- targets --------------------------------------------------------------------
def outcome_rewards(data: RoundData, step: float) -> np.ndarray:
    """Each row's graded reward of its seat's final place."""

    table = np.asarray([0.0] + [graded_reward(rank, step) for rank in (1, 2, 3, 4)])
    rewards: np.ndarray = table[data.ranks.astype(np.int64)].astype(np.float32)
    return rewards


def lambda_targets(
    following: np.ndarray, values: np.ndarray, rewards: np.ndarray, lam: float
) -> np.ndarray:
    """Round-level TD(lambda) targets (module docstring).

    ``following`` is ``RoundData.next_rows``; ``values`` the value of every
    row, ``rewards`` its seat's final reward. A row whose next round is
    ``-1`` (the seat's last round start) is followed by the end of the game.
    """

    if not 0.0 <= lam <= 1.0:
        raise ValueError("lambda is between 0 and 1")
    targets = np.full(following.shape[0], np.nan, dtype=np.float64)
    last = following < 0
    targets[last] = rewards[last]
    pending = np.flatnonzero(~last)
    # Fill backwards one round at a time: a row is ready once its next is.
    while pending.size:
        nxt = following[pending]
        ready = ~np.isnan(targets[nxt])
        if not ready.any():
            raise ValueError("the rounds of a seat do not end")
        rows, nxt = pending[ready], nxt[ready]
        targets[rows] = (1.0 - lam) * values[nxt] + lam * targets[nxt]
        pending = pending[~ready]
    return targets.astype(np.float32)


# -- the fit ----------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class FitConfig:
    """One arm of the stage-1 fit (docs/entity-self-play-plan.md 3.2, 4.1)."""

    lam: float
    step: float
    fits: int = 3
    epochs: int = 6
    learning_rate: float = 1.0e-4
    minibatch: int = 512
    heldout_modulus: int = 20
    vp_weight: float = 1.0
    rank_weight: float = 0.1
    seed: int = 0
    chunk: int = 4096
    # Where the network trains (``cpu`` or ``mps``); the targets, the split
    # and the order stay NumPy on the CPU, and the fitted copy comes back on
    # the CPU.
    device: str = "cpu"

    def __post_init__(self) -> None:
        if self.fits < 1 or self.epochs < 1 or self.minibatch < 1:
            raise ValueError("fits, epochs and the minibatch are positive")
        if self.heldout_modulus < 2:
            raise ValueError("the held-out modulus is at least 2")


def _branch_parameters(network: EntityNetwork) -> list[nn.Parameter]:
    if network.value_body is None:
        raise ValueError("the fit trains a value branch (with_value_branch)")
    heads: list[nn.Module] = [network.value_body, network.value_head]
    heads += [head for head in (network.vp_head, network.rank_head) if head is not None]
    if network.value_twin is not None:
        heads.append(network.value_twin)  # E3: the value's own encoders train too
    return [parameter for head in heads for parameter in head.parameters()]


def predict_values(
    network: EntityNetwork, data: RoundData, rows: np.ndarray, chunk: int = 4096
) -> np.ndarray:
    """The network's value of ``rows``."""

    out = np.zeros(rows.shape[0], dtype=np.float32)
    device = _device_of(network)
    network.eval()
    with torch.no_grad():
        for start in range(0, rows.shape[0], chunk):
            part = rows[start : start + chunk]
            batch = torch.from_numpy(data.observations(part)).to(device)
            out[start : start + part.shape[0]] = network.values(batch).cpu().numpy()
    return out


def _device_of(network: EntityNetwork) -> torch.device:
    return next(network.parameters()).device


def _branch_losses(
    network: EntityNetwork,
    data: RoundData,
    rows: np.ndarray,
    targets: np.ndarray,
) -> tuple[Tensor, Tensor, Tensor | None, Tensor | None]:
    """The value MSE to ``targets[rows]`` and the auxiliary losses, means over
    ``rows``; the shared encoders run without gradient (the value's own twin
    of them, docs/value-model-plan.md E3, with it)."""

    assert network.value_body is not None
    device = _device_of(network)
    observations = torch.from_numpy(data.observations(rows)).to(device)
    if network.value_twin is None:
        with torch.no_grad():
            torso = network.torso_input(observations)
    else:
        torso = network.value_twin.torso_input(observations)
    hidden = network.value_body(torso)
    value = network.value_head(hidden).squeeze(-1)
    value_loss = (value - torch.from_numpy(targets[rows]).to(device)).square().mean()
    vp_loss = rank_loss = None
    if network.vp_head is not None:
        wanted = torch.from_numpy(data.victory_points[rows].astype(np.float32))
        wanted = wanted.to(device)
        vp_loss = (network.vp_head(hidden) - wanted / VP_SCALE).square().mean()
    if network.rank_head is not None:
        places = torch.from_numpy(data.ranks[rows].astype(np.int64) - 1).to(device)
        rank_loss = nn.functional.cross_entropy(network.rank_head(hidden), places)
    return value_loss, value, vp_loss, rank_loss


def score_values(
    network: EntityNetwork,
    data: RoundData,
    rows: np.ndarray,
    targets: np.ndarray,
    rewards: np.ndarray,
    config: FitConfig,
) -> dict[str, Any]:
    """Held-out losses: MSE to the TD targets and to the final reward, overall
    and by round, and the auxiliary losses."""

    predicted = predict_values(network, data, rows, config.chunk)
    target_error = np.square(predicted - targets[rows])
    outcome_error = np.square(predicted - rewards[rows])
    by_round: dict[str, dict[str, float]] = {}
    for round_number in sorted(set(data.rounds[rows].tolist())):
        mask = data.rounds[rows] == round_number
        by_round[str(round_number)] = {
            "rows": int(mask.sum()),
            "target_mse": float(target_error[mask].mean()),
            "outcome_mse": float(outcome_error[mask].mean()),
            "constant_mse": float(np.square(rewards[rows][mask]).mean()),
        }
    totals = {"vp": 0.0, "rank": 0.0}
    network.eval()
    with torch.no_grad():
        for start in range(0, rows.shape[0], config.chunk):
            part = rows[start : start + config.chunk]
            _, _, vp_loss, rank_loss = _branch_losses(network, data, part, targets)
            if vp_loss is not None:
                totals["vp"] += float(vp_loss) * part.shape[0]
            if rank_loss is not None:
                totals["rank"] += float(rank_loss) * part.shape[0]
    count = max(rows.shape[0], 1)
    return {
        "rows": int(rows.shape[0]),
        "target_mse": float(target_error.mean()),
        "outcome_mse": float(outcome_error.mean()),
        # Always answering 0 (the table's mean reward): the floor to beat.
        "constant_mse": float(np.square(rewards[rows]).mean()),
        "vp_mse": totals["vp"] / count if network.vp_head is not None else None,
        "rank_ce": totals["rank"] / count if network.rank_head is not None else None,
        "by_round": by_round,
    }


def leader_values(
    network: EntityNetwork, data: RoundData, rows: np.ndarray, config: FitConfig
) -> dict[str, dict[str, float]]:
    """The draft diagnostic (plan 3.5): each Leader's mean value at the start
    of round 1 (where the Leader pick's leaf is read) and round 2, and its
    seats' win share, over ``rows``."""

    out: dict[str, dict[str, float]] = {}
    sums: dict[tuple[int, int], list[float]] = defaultdict(list)
    for round_number in (1, 2):
        picked = rows[data.rounds[rows] == round_number]
        values = predict_values(network, data, picked, config.chunk)
        for leader, value in zip(data.leaders[picked], values, strict=True):
            sums[(int(leader), round_number)].append(float(value))
    first = rows[data.rounds[rows] == 1]
    for number, name in enumerate(data.leader_names):
        seats = first[data.leaders[first] == number]
        if not seats.size:
            continue
        out[name] = {
            "seats": int(seats.size),
            "win": float((data.ranks[seats] == 1).mean()),
            "value_round_1": float(np.mean(sums[(number, 1)])),
            "value_round_2": float(np.mean(sums[(number, 2)]))
            if sums[(number, 2)]
            else float("nan"),
        }
    return out


def fit_round_values(
    network: EntityNetwork,
    data: RoundData,
    config: FitConfig,
    *,
    report: Callable[[dict[str, Any]], None] | None = None,
    initial_values: np.ndarray | None = None,
) -> tuple[EntityNetwork, list[dict[str, Any]]]:
    """Fit ``network``'s value branch to ``data`` (module docstring).

    Returns the fitted network (a copy) and one record per epoch. Only the
    branch and its auxiliary heads train; the policy's weights stay the
    file's bit for bit.

    ``initial_values`` (one per row) build the first fit's targets instead
    of the network's own values: a branch that starts fresh (another size,
    docs/value-model-plan.md E2) has none worth bootstrapping from, so it
    takes the starting file's, as a copied branch would.
    """

    # Move the copy first, then take its parameters for the optimizer.
    network = copy.deepcopy(network).to(resolve_device(config.device))
    parameters = _branch_parameters(network)
    branch = {id(parameter) for parameter in parameters}
    for parameter in network.parameters():
        parameter.requires_grad_(id(parameter) in branch)
    heldout = data.heldout(config.heldout_modulus)
    train_rows = np.flatnonzero(~heldout)
    held_rows = np.flatnonzero(heldout)
    if not train_rows.size or not held_rows.size:
        raise ValueError("the fit needs both training and held-out games")
    following = data.next_rows()
    rewards = outcome_rewards(data, config.step)
    every = np.arange(data.rows)
    generator = np.random.default_rng(config.seed)
    torch.manual_seed(config.seed)
    optimizer = torch.optim.Adam(parameters, lr=config.learning_rate)
    records: list[dict[str, Any]] = []
    if initial_values is not None and initial_values.shape != (data.rows,):
        raise ValueError("initial_values needs one value per row")
    for fit in range(1, config.fits + 1):
        if fit == 1 and initial_values is not None:
            values = initial_values
        else:
            values = predict_values(network, data, every, config.chunk)
        targets = lambda_targets(following, values, rewards, config.lam)
        best: tuple[float, dict[str, Tensor]] | None = None
        for epoch in range(1, config.epochs + 1):
            started = time.perf_counter()
            network.train()
            order = generator.permutation(train_rows)
            total = 0.0
            for start in range(0, order.shape[0], config.minibatch):
                part = order[start : start + config.minibatch]
                value_loss, _, vp_loss, rank_loss = _branch_losses(
                    network, data, part, targets
                )
                loss = value_loss
                if vp_loss is not None:
                    loss = loss + config.vp_weight * vp_loss
                if rank_loss is not None:
                    loss = loss + config.rank_weight * rank_loss
                if not torch.isfinite(loss):
                    raise FloatingPointError(f"non-finite loss in fit {fit}")
                optimizer.zero_grad(set_to_none=True)
                loss.backward()  # type: ignore[no-untyped-call]
                nn.utils.clip_grad_norm_(parameters, 1.0)
                optimizer.step()
                total += float(value_loss.detach()) * part.shape[0]
            score = score_values(network, data, held_rows, targets, rewards, config)
            record = {
                "fit": fit,
                "epoch": epoch,
                "train_value_mse": total / order.shape[0],
                "heldout": score,
                "seconds": round(time.perf_counter() - started, 1),
            }
            records.append(record)
            if report is not None:
                report(record)
            if best is None or score["target_mse"] < best[0]:
                best = (
                    score["target_mse"],
                    {
                        key: value.detach().clone()
                        for key, value in network.state_dict().items()
                    },
                )
        assert best is not None
        network.load_state_dict(best[1])
    for parameter in network.parameters():
        parameter.requires_grad_(True)
    return network.cpu().eval(), records
