"""Screen a leaf value network for the search seat without playing a gate.

A value network meant for a search seat's leaves (handoff "학습·AI", E7) is
judged by a search-seat gate: 400 games, about four hours on the Mac mini,
and win shares resolved to about +-6pp. The leaves a searched decision
reads depend only on its playout policy, its worlds and its candidates, not
on the network that rates them (``NetworkSearchAgent``). So
``record_leaves`` plays games with a search seat and keeps, at each searched
decision, the end of every playout -- the searching seat's observation, or
the reward of a game that finished -- and ``screen`` rates those ends with
any value network and asks what the search would have chosen with it.

The reference is a network whose leaves searched best: the v147 play
network's (``search:<student>::flip=0.01::value=<v147>`` won 78.2% of the
2026-10-25 gate cell, against 70.0% for the student's own leaves and 75.0%
for the E7b value network's). A screened network is scored against the
reference on the same decisions by

- ``agreement``: the share of decisions it picks as the reference does,
  with the seat's own rule (``search_pick``: the first candidate unless
  another's summed value beats it by more than ``flip_margin`` a world);
- ``regret``: the reference's mean playout value of its own pick minus
  that of the screened network's pick (0 when they agree);
- ``gap_rmse``: the root mean square error of each candidate's mean value
  minus the first candidate's, against the reference's gaps (what the pick
  compares);
- ``leaf_rmse``: the root mean square error of the open leaves' values.

``paired_difference`` bootstraps a per-decision statistic of two networks
over the same decisions. The screen does not see a network's policy: two
seats with the reference's leaves and different policies (the server seat,
77.5%, and the student with the v147 leaves, 78.2%) look the same to it.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch

from dune_imperium.adapters.observation_encoding import OBSERVATION_SIZE
from dune_imperium.agents import Agent, make_agent
from dune_imperium.agents.network_search_agent import NetworkSearchAgent, SearchResult
from dune_imperium.agents.registry import parse_search_kind
from dune_imperium.config import RulesetConfig
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.observation import PlayerView
from dune_imperium.core.state import GameState
from dune_imperium.evaluation.tournament import MatchSpec
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game
from dune_imperium.training.checkpoint import load_checkpoint
from dune_imperium.training.network import PolicyValueNetwork
from dune_imperium.training.older_teacher import cached_older_network, reads_older_rows

_LEAF_ARRAYS = (
    "shapes",
    "offsets",
    "finished",
    "rewards",
    "recorded",
    "obs_columns",
    "obs_values",
    "obs_offsets",
    "chosen",
    "games",
)


@dataclass(frozen=True, slots=True)
class Leaves:
    """Searched decisions' playout ends, each decision's world by world."""

    shapes: np.ndarray  # int64 [decisions, 2]: worlds, candidates
    offsets: np.ndarray  # int64 [decisions + 1]: the decision's leaves
    finished: np.ndarray  # bool [leaves]: the playout finished the game
    rewards: np.ndarray  # float64 [leaves]: a finished game's reward, else NaN
    recorded: np.ndarray  # float64 [leaves]: the recording seat's value
    obs_columns: np.ndarray  # uint16 [entries]: an open leaf's non-zero column
    obs_values: np.ndarray  # int16 [entries]
    obs_offsets: np.ndarray  # int64 [leaves + 1] (a finished leaf has none)
    chosen: np.ndarray  # int64 [decisions]: the recording seat's pick
    games: np.ndarray  # int64 [decisions]: which recorded match

    @property
    def decisions(self) -> int:
        return int(self.shapes.shape[0])

    def observations(self, leaves: np.ndarray) -> np.ndarray:
        """The dense observations ``int32 [len(leaves), OBSERVATION_SIZE]``."""

        starts = self.obs_offsets[leaves]
        counts = self.obs_offsets[leaves + 1] - starts
        owner = np.repeat(np.arange(leaves.shape[0]), counts)
        first = np.repeat(np.cumsum(counts) - counts, counts)
        index = np.repeat(starts, counts) + np.arange(int(counts.sum())) - first
        dense = np.zeros((leaves.shape[0], OBSERVATION_SIZE), dtype=np.int32)
        dense[owner, self.obs_columns[index].astype(np.int64)] = self.obs_values[index]
        return dense

    def matrix(self, values: np.ndarray, decision: int) -> np.ndarray:
        """``values`` of one decision's leaves as ``[worlds, candidates]``."""

        worlds, candidates = (int(size) for size in self.shapes[decision])
        start, stop = int(self.offsets[decision]), int(self.offsets[decision + 1])
        return values[start:stop].reshape(worlds, candidates)


def save_leaves(leaves: Leaves, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, **{name: getattr(leaves, name) for name in _LEAF_ARRAYS})


def load_leaves(paths: Sequence[Path]) -> Leaves:
    """The leaves of several files, as one set (their games numbered on)."""

    parts = []
    for path in paths:
        with np.load(path) as arrays:
            parts.append({name: arrays[name] for name in _LEAF_ARRAYS})
    if not parts:
        raise ValueError("no leaves to load")
    joined: dict[str, Any] = {}
    for name in _LEAF_ARRAYS:
        if name in ("offsets", "obs_offsets"):
            pieces, base = [np.zeros(1, dtype=np.int64)], 0
            for part in parts:
                pieces.append(part[name][1:] + base)
                base += int(part[name][-1])
            joined[name] = np.concatenate(pieces)
        elif name == "games":
            pieces, base = [], 0
            for part in parts:
                pieces.append(part[name] + base)
                base += int(part[name].max(initial=-1)) + 1
            joined[name] = np.concatenate(pieces)
        else:
            joined[name] = np.concatenate([part[name] for part in parts])
    return Leaves(**joined)


class RecordingSearchAgent(NetworkSearchAgent):
    """A search seat that keeps every searched decision's playout ends.

    It searches exactly as its parent: it only remembers each playout's
    last observation of the seat (``_leaf_value``'s view) or that the
    playout finished the game. Sequential halving plays uneven worlds, so
    it is refused.
    """

    def __init__(self, path: str, **options: Any) -> None:
        if options.get("halving"):
            raise ValueError("the leaf recorder needs every candidate in every world")
        super().__init__(path, **options)
        self.searched: list[tuple[SearchResult, list[np.ndarray | None]]] = []
        self._ends: list[np.ndarray | None] = []
        self._leaf: np.ndarray | None = None

    def search_with_state(
        self,
        state: GameState,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> SearchResult:
        self._ends = []
        result = super().search_with_state(state, observation, legal_actions)
        if result.searched:
            worlds, candidates = len(result.values), len(result.candidates)
            if len(self._ends) != worlds * candidates:
                raise RuntimeError("a searched decision's playouts went unrecorded")
            self.searched.append((result, self._ends))
        return result

    def _playout(
        self, state: GameState, seat: int, horizon: int, chance_seed: int
    ) -> float:
        self._leaf = None
        value = super()._playout(state, seat, horizon, chance_seed)
        self._ends.append(self._leaf)
        return value

    def _leaf_value(self, view: PlayerView) -> float:
        value = super()._leaf_value(view)
        self._leaf = self._encode(view)
        return value


def _as_leaves(
    searched: Sequence[tuple[SearchResult, list[np.ndarray | None]]],
    games: Sequence[int],
) -> Leaves:
    shapes, offsets, finished, rewards, recorded = [], [0], [], [], []
    columns, values, obs_offsets = [], [], [0]
    chosen = []
    for result, ends in searched:
        shapes.append((len(result.values), len(result.candidates)))
        offsets.append(offsets[-1] + len(ends))
        chosen.append(result.candidates.index(result.chosen))
        flat = [value for row in result.values for value in row]
        for end, value in zip(ends, flat, strict=True):
            recorded.append(value)
            finished.append(end is None)
            rewards.append(value if end is None else np.nan)
            if end is not None:
                nonzero = np.flatnonzero(end)
                columns.append(nonzero.astype(np.uint16))
                values.append(end[nonzero].astype(np.int16))
                obs_offsets.append(obs_offsets[-1] + nonzero.shape[0])
            else:
                obs_offsets.append(obs_offsets[-1])
    return Leaves(
        shapes=np.asarray(shapes, dtype=np.int64).reshape(-1, 2),
        offsets=np.asarray(offsets, dtype=np.int64),
        finished=np.asarray(finished, dtype=bool),
        rewards=np.asarray(rewards, dtype=np.float64),
        recorded=np.asarray(recorded, dtype=np.float64),
        obs_columns=np.concatenate(columns) if columns else np.zeros(0, np.uint16),
        obs_values=np.concatenate(values) if values else np.zeros(0, np.int16),
        obs_offsets=np.asarray(obs_offsets, dtype=np.int64),
        chosen=np.asarray(chosen, dtype=np.int64),
        games=np.asarray(games, dtype=np.int64),
    )


def record_leaves(spec: MatchSpec, kind: str, *, game: int = 0) -> Leaves:
    """Play ``spec`` and keep the leaves of its ``kind`` seat's searched
    decisions (the seat ``kind`` names, a ``search:`` seat; its seed and
    options as ``make_agent`` would give them)."""

    if kind not in spec.seat_agents:
        raise ValueError(f"{kind!r} has no seat in the match")
    config = spec.config
    path, options = parse_search_kind(kind)
    agents: list[Agent] = []
    recorder: RecordingSearchAgent | None = None
    for seat, seat_kind in enumerate(spec.seat_agents):
        seed = spec.policy_seed + seat
        if seat_kind == kind and recorder is None:
            recorder = RecordingSearchAgent(path, seed=seed, config=config, **options)
            agents.append(recorder)
        else:
            agents.append(make_agent(seat_kind, seed, config))
    engine = (
        UprisingRulesEngine(leader_ids=spec.leader_ids)
        if spec.leader_ids is not None
        else UprisingRulesEngine()
    )
    run_policy_game(engine, config, spec.game_seed, agents, max_steps=spec.max_steps)
    assert recorder is not None
    return _as_leaves(recorder.searched, [game] * len(recorder.searched))


def value_network(path: str, config: RulesetConfig) -> PolicyValueNetwork:
    """A file's network for its value head (an older codec's MLP read
    through ``older_teacher``, as a search seat reads its leaves)."""

    if reads_older_rows(path):
        return cached_older_network(path).network
    network, _ = load_checkpoint(Path(path), ruleset=config)
    network.eval()
    return network


def leaf_values(
    network: PolicyValueNetwork, leaves: Leaves, *, chunk: int = 512
) -> np.ndarray:
    """``network``'s value of every open leaf; a finished one keeps its
    reward. Batched, so a value may differ from the seat's own reading in
    the last bits."""

    values = leaves.rewards.copy()
    open_leaves = np.flatnonzero(~leaves.finished)
    with torch.no_grad():
        for start in range(0, open_leaves.shape[0], chunk):
            part = open_leaves[start : start + chunk]
            batch = torch.from_numpy(leaves.observations(part))
            read = network.value_head(network.trunk(batch)).squeeze(-1)
            values[part] = read.numpy()
    return values


def search_pick(matrix: np.ndarray, flip_margin: float) -> int:
    """The seat's choice from ``[worlds, candidates]`` playout values: the
    first candidate with the largest summed value, kept on the first while
    the best beats it by no more than ``flip_margin`` a world
    (``NetworkSearchAgent._pick`` with every candidate in every world)."""

    totals = [sum(float(value) for value in column) for column in matrix.T]
    best = totals.index(max(totals))
    worlds = matrix.shape[0]
    if best and flip_margin and (totals[best] - totals[0]) / worlds <= flip_margin:
        return 0
    return best


@dataclass(frozen=True, slots=True)
class DecisionScores:
    """Per-decision statistics of a screened network against the reference."""

    picks: np.ndarray  # int64 [decisions]
    agree: np.ndarray  # float64 [decisions]: 1 when the pick is the reference's
    regret: np.ndarray  # float64 [decisions]
    gap_error: np.ndarray  # float64 [decisions]: mean squared gap error
    leaf_error: np.ndarray  # float64 [decisions]: mean squared open-leaf error


@dataclass(frozen=True, slots=True)
class ScreenScore:
    decisions: int
    agreement: float
    regret: float
    gap_rmse: float
    leaf_rmse: float


def decision_scores(
    leaves: Leaves,
    values: np.ndarray,
    reference: np.ndarray,
    *,
    flip_margin: float,
) -> DecisionScores:
    """``values`` (a screened network's leaf values) against ``reference``."""

    picks, agree, regret, gap_error, leaf_error = [], [], [], [], []
    for decision in range(leaves.decisions):
        mine = leaves.matrix(values, decision)
        theirs = leaves.matrix(reference, decision)
        pick = search_pick(mine, flip_margin)
        wanted = search_pick(theirs, flip_margin)
        means = theirs.mean(axis=0)
        picks.append(pick)
        agree.append(float(pick == wanted))
        regret.append(float(means[wanted] - means[pick]))
        gaps = mine.mean(axis=0) - mine.mean(axis=0)[0]
        wanted_gaps = means - means[0]
        gap_error.append(float(np.mean(np.square(gaps[1:] - wanted_gaps[1:]))))
        start, stop = int(leaves.offsets[decision]), int(leaves.offsets[decision + 1])
        open_leaves = ~leaves.finished[start:stop]
        error = values[start:stop][open_leaves] - reference[start:stop][open_leaves]
        leaf_error.append(float(np.mean(np.square(error))) if error.size else 0.0)
    return DecisionScores(
        picks=np.asarray(picks, dtype=np.int64),
        agree=np.asarray(agree),
        regret=np.asarray(regret),
        gap_error=np.asarray(gap_error),
        leaf_error=np.asarray(leaf_error),
    )


def screen(scores: DecisionScores) -> ScreenScore:
    return ScreenScore(
        decisions=int(scores.agree.shape[0]),
        agreement=float(scores.agree.mean()),
        regret=float(scores.regret.mean()),
        gap_rmse=float(np.sqrt(scores.gap_error.mean())),
        leaf_rmse=float(np.sqrt(scores.leaf_error.mean())),
    )


def paired_difference(
    first: np.ndarray,
    second: np.ndarray,
    *,
    draws: int = 4000,
    seed: int = 0,
    level: float = 0.95,
) -> tuple[float, float, float]:
    """Mean of ``first - second`` over the same decisions and its bootstrap
    interval (decisions resampled with replacement)."""

    if first.shape != second.shape or not first.size:
        raise ValueError("a paired difference needs the same decisions")
    difference = first - second
    generator = np.random.default_rng(seed)
    samples = generator.integers(0, difference.shape[0], (draws, difference.shape[0]))
    means = difference[samples].mean(axis=1)
    tail = (1.0 - level) / 2.0
    low, high = np.quantile(means, [tail, 1.0 - tail])
    return float(difference.mean()), float(low), float(high)
