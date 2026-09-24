"""Expert-iteration data: greedy self-play labelled by the search.

Every seat plays the incumbent network greedily (the same ``NetworkAgent``
and cycle guard as a ``checkpoint:`` seat), so the states come from the
student's own play. At a sample of the decisions the search could have
searched, the teacher -- a ``NetworkSearchAgent`` on the same checkpoint --
evaluates its candidates in determinized worlds and the row records those
values next to the network's own logits; the search never chooses the move.
Agent-effect ordering, which the shipped search leaves to the network, is
sampled as ANCHOR rows that keep the network's own distribution there.

A labelled game is written as one ``.npz`` file, so a game that stalls or
fails costs only itself. ``read_shards`` stacks many files into one
``ExpertData`` with CSR legal sets for ``training.distill``.
"""

from __future__ import annotations

import json
import os
import random
import time
from collections.abc import Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

import numpy as np
import torch

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.adapters.observation_encoding import (
    OBSERVATION_SIZE,
    OBSERVATION_VERSION,
    encode_player_view,
)
from dune_imperium.adapters.pettingzoo_env import LOSER_REWARD, WINNER_REWARD
from dune_imperium.agents.network_search_agent import (
    DEFAULT_CANDIDATES,
    DEFAULT_HORIZON_ROUNDS,
    DEFAULT_ROLLOUTS,
    NetworkSearchAgent,
    _Taken,
    orders_agent_effects,
)
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.observation import PlayerView
from dune_imperium.core.state import GameState
from dune_imperium.evaluation.tournament import (
    MatchSpec,
    _single_threaded_worker,
    tournament_specs,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game
from dune_imperium.training.policy import without_undo_actions
from dune_imperium.training.torch_policy import load_network_agent

EXPERT_FORMAT: Final = 1
LABEL: Final = 0
ANCHOR: Final = 1
# A greedy full-expansion game takes 675-874 steps; the RL collector's cap.
# A game that loops fails at the cap instead of stalling its worker.
COLLECTION_MAX_STEPS: Final = 4_000
OBSERVATION_LIMIT: Final = 255


@dataclass(frozen=True, slots=True)
class LabelConfig:
    """How often decisions are labelled, and the teacher's search knobs."""

    label_probability: float = 0.5
    anchor_probability: float = 0.25
    rollouts: int = DEFAULT_ROLLOUTS
    candidates: int = DEFAULT_CANDIDATES
    horizon_rounds: int = DEFAULT_HORIZON_ROUNDS

    def __post_init__(self) -> None:
        for name in ("label_probability", "anchor_probability"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must lie in [0, 1]")
        if self.rollouts < 1 or self.candidates < 2 or self.horizon_rounds < 1:
            raise ValueError("rollouts >= 1, candidates >= 2, horizon_rounds >= 1")


@dataclass(frozen=True, slots=True)
class LabelRow:
    """One labelled (or anchor) decision of one seat.

    ``legal`` holds the catalog indices of the offered actions (undo actions
    removed) in ascending order and ``prior_logits`` the network's logits in
    that same order. ``candidates`` are catalog indices in the teacher's
    ranking, padded with -1 to K; ``values[world][candidate]`` is padded with
    NaN. ANCHOR rows carry no candidates.
    """

    kind: int
    seat: int
    round_number: int
    decision_index: int
    observation: np.ndarray
    legal: np.ndarray
    prior_logits: np.ndarray
    candidates: np.ndarray
    values: np.ndarray
    played: int


class LabellingAgent:
    """A greedy network seat that records search labels as it plays."""

    def __init__(self, teacher: str, *, seed: int, config: LabelConfig) -> None:
        if seed < 0:
            raise ValueError("agent seed must not be negative")
        self.config = config
        self.player = load_network_agent(teacher)
        self.codec = self.player.codec
        self.network = self.player.network
        self.search = NetworkSearchAgent(
            teacher,
            seed=seed,
            rollouts=config.rollouts,
            candidates=config.candidates,
            horizon_rounds=config.horizon_rounds,
        )
        self._taken = _Taken()
        self._coin = random.Random(seed ^ 0x5EED)
        self.rows: list[LabelRow] = []
        self.decisions = 0
        self.guard_skips = 0
        self.played_is_first = 0

    def choose_action(
        self, observation: PlayerView, legal_actions: tuple[DomainAction, ...]
    ) -> DomainAction:
        """Without a state there is nothing to search: play greedily."""

        self.decisions += 1
        return self.player.choose_action(observation, legal_actions)

    def choose_action_with_state(
        self,
        state: GameState,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        played = self.player.choose_action(observation, legal_actions)
        decision_index = self.decisions
        self.decisions += 1
        offered = without_undo_actions(legal_actions)
        if len(offered) < 2:
            return played
        encoded = np.asarray(encode_player_view(observation), dtype=np.int32)
        seat = observation.player
        if orders_agent_effects(state):
            if self._coin.random() < self.config.anchor_probability:
                self.rows.append(
                    self._row(
                        ANCHOR, state, seat, decision_index, encoded, offered
                    )._replace_played(self.codec.encode(played))
                )
            return played
        key, fresh = self._taken.untried(state.round_number, seat, encoded, offered)
        self._taken.record(key, played)
        if len(fresh) < len(offered):
            # The guard steered this decision away from a repeat; the search
            # would rank a different set than the one the player chose from.
            self.guard_skips += 1
            return played
        if self._coin.random() >= self.config.label_probability:
            return played
        ranked = self.search.candidate_order(observation, offered)
        candidates = ranked[: self.config.candidates]
        values = self.search.evaluate_candidates(state, seat, candidates)
        self.played_is_first += int(candidates[0] == played)
        row = self._row(LABEL, state, seat, decision_index, encoded, offered)
        width = self.config.candidates
        padded = np.full(width, -1, dtype=np.int32)
        padded[: len(candidates)] = [self.codec.encode(a) for a in candidates]
        table = np.full((self.config.rollouts, width), np.nan, dtype=np.float32)
        table[:, : len(candidates)] = np.asarray(values, dtype=np.float32)
        self.rows.append(
            LabelRow(
                kind=LABEL,
                seat=seat,
                round_number=row.round_number,
                decision_index=decision_index,
                observation=row.observation,
                legal=row.legal,
                prior_logits=row.prior_logits,
                candidates=padded,
                values=table,
                played=self.codec.encode(played),
            )
        )
        return played

    def _row(
        self,
        kind: int,
        state: GameState,
        seat: int,
        decision_index: int,
        encoded: np.ndarray,
        offered: Sequence[DomainAction],
    ) -> _PartialRow:
        if int(encoded.max()) > OBSERVATION_LIMIT:
            raise ValueError(
                f"observation value {int(encoded.max())} does not fit uint8"
            )
        observation = np.clip(encoded, 0, OBSERVATION_LIMIT).astype(np.uint8)
        index = np.asarray([self.codec.encode(a) for a in offered], dtype=np.int64)
        order = np.argsort(index, kind="stable")
        legal = index[order]
        with torch.no_grad():
            hidden = self.network.trunk(torch.from_numpy(encoded).unsqueeze(0))
            logits = self.network.action_logits(hidden, torch.from_numpy(legal))
        return _PartialRow(
            kind=kind,
            seat=seat,
            round_number=state.round_number,
            decision_index=decision_index,
            observation=observation,
            legal=legal.astype(np.int32),
            prior_logits=logits[0].numpy().astype(np.float32),
            width=self.config.candidates,
            worlds=self.config.rollouts,
        )


@dataclass(frozen=True, slots=True)
class _PartialRow:
    kind: int
    seat: int
    round_number: int
    decision_index: int
    observation: np.ndarray
    legal: np.ndarray
    prior_logits: np.ndarray
    width: int
    worlds: int

    def _replace_played(self, played: int) -> LabelRow:
        return LabelRow(
            kind=self.kind,
            seat=self.seat,
            round_number=self.round_number,
            decision_index=self.decision_index,
            observation=self.observation,
            legal=self.legal,
            prior_logits=self.prior_logits,
            candidates=np.full(self.width, -1, dtype=np.int32),
            values=np.full((self.worlds, self.width), np.nan, dtype=np.float32),
            played=played,
        )


@dataclass(frozen=True, slots=True)
class LabelledGame:
    """One finished game: its rows and every seat's outcome."""

    game_seed: int
    rows: tuple[LabelRow, ...]
    rewards: tuple[float, ...]
    ranks: tuple[int, ...]
    victory_points: tuple[int, ...]
    leader_ids: tuple[str, ...]
    rounds: int
    decisions: tuple[int, ...]
    seconds: float
    guard_skips: int
    played_is_first: int


def collection_specs(
    teacher: str, *, start_seed: int, games: int
) -> tuple[MatchSpec, ...]:
    """All-expansion specs with rotating Leaders, one per game seed."""

    return tournament_specs(
        agents=(f"checkpoint:{teacher}",) * 4,
        games=games,
        rulesets=(True,),
        start_seed=start_seed,
        rotate_seats=False,
        rotate_leaders=True,
        promo_cards=True,
        bloodlines=True,
        tech_module=True,
        immortality=True,
        max_steps=COLLECTION_MAX_STEPS,
    )


def label_game(spec: MatchSpec, teacher: str, config: LabelConfig) -> LabelledGame:
    """Play one spec with four labelling seats and return its rows."""

    started = time.perf_counter()
    engine = (
        UprisingRulesEngine(leader_ids=spec.leader_ids)
        if spec.leader_ids is not None
        else UprisingRulesEngine()
    )
    agents = [
        LabellingAgent(teacher, seed=spec.policy_seed + seat, config=config)
        for seat in range(spec.config.players)
    ]
    simulation = run_policy_game(
        engine, spec.config, spec.game_seed, agents, max_steps=spec.max_steps
    )
    ranks = {standing.player: standing for standing in simulation.standings}
    players = spec.config.players
    rewards = tuple(
        WINNER_REWARD if ranks[seat].rank == 1 else LOSER_REWARD
        for seat in range(players)
    )
    rows = tuple(row for agent in agents for row in agent.rows)
    return LabelledGame(
        game_seed=spec.game_seed,
        rows=rows,
        rewards=rewards,
        ranks=tuple(ranks[seat].rank for seat in range(players)),
        victory_points=tuple(ranks[seat].victory_points for seat in range(players)),
        leader_ids=tuple(p.leader_id or "" for p in simulation.state.players),
        rounds=simulation.state.round_number,
        decisions=tuple(agent.decisions for agent in agents),
        seconds=time.perf_counter() - started,
        guard_skips=sum(agent.guard_skips for agent in agents),
        played_is_first=sum(agent.played_is_first for agent in agents),
    )


def game_arrays(game: LabelledGame) -> dict[str, np.ndarray]:
    """Flatten a game into the arrays of one shard file (CSR legal sets)."""

    rows = game.rows
    count = len(rows)
    lengths = np.asarray([len(row.legal) for row in rows], dtype=np.int64)
    offsets = np.zeros(count + 1, dtype=np.int64)
    np.cumsum(lengths, out=offsets[1:])
    width = rows[0].candidates.shape[0] if rows else 0
    worlds = rows[0].values.shape[0] if rows else 0
    return {
        "kind": np.asarray([r.kind for r in rows], dtype=np.int8),
        "seat": np.asarray([r.seat for r in rows], dtype=np.int8),
        "round": np.asarray([r.round_number for r in rows], dtype=np.int16),
        "decision_index": np.asarray([r.decision_index for r in rows], dtype=np.int32),
        "observations": (
            np.stack([r.observation for r in rows])
            if rows
            else np.zeros((0, OBSERVATION_SIZE), dtype=np.uint8)
        ),
        "legal_indices": (
            np.concatenate([r.legal for r in rows]).astype(np.int32)
            if rows
            else np.zeros(0, dtype=np.int32)
        ),
        "legal_offsets": offsets,
        "prior_logits": (
            np.concatenate([r.prior_logits for r in rows]).astype(np.float32)
            if rows
            else np.zeros(0, dtype=np.float32)
        ),
        "candidates": (
            np.stack([r.candidates for r in rows])
            if rows
            else np.zeros((0, width), dtype=np.int32)
        ),
        "values": (
            np.stack([r.values for r in rows])
            if rows
            else np.zeros((0, worlds, width), dtype=np.float32)
        ),
        "played": np.asarray([r.played for r in rows], dtype=np.int32),
        "z": np.asarray([game.rewards[r.seat] for r in rows], dtype=np.float32),
        "seat_decisions": np.asarray(
            [game.decisions[r.seat] for r in rows], dtype=np.int32
        ),
        "g_rewards": np.asarray(game.rewards, dtype=np.float32),
        "g_ranks": np.asarray(game.ranks, dtype=np.int8),
        "g_vp": np.asarray(game.victory_points, dtype=np.int16),
        "g_decisions": np.asarray(game.decisions, dtype=np.int32),
    }


def validate_game(game: LabelledGame, action_size: int) -> None:
    """Refuse a game whose rows break the invariants distillation relies on."""

    if sum(reward == WINNER_REWARD for reward in game.rewards) != 1:
        raise ValueError(f"game {game.game_seed}: not exactly one winner")
    for row in game.rows:
        legal = row.legal
        if len(legal) < 2 or np.any(np.diff(legal) <= 0):
            raise ValueError(f"game {game.game_seed}: legal set not ascending")
        if legal[0] < 0 or legal[-1] >= action_size:
            raise ValueError(f"game {game.game_seed}: legal index out of range")
        if row.prior_logits.shape != legal.shape or not np.all(
            np.isfinite(row.prior_logits)
        ):
            raise ValueError(f"game {game.game_seed}: prior logits misaligned")
        if row.played not in set(legal.tolist()):
            raise ValueError(f"game {game.game_seed}: played action not offered")
        valid = row.candidates >= 0
        if row.kind == LABEL:
            if valid.sum() < 2 or not set(row.candidates[valid].tolist()) <= set(
                legal.tolist()
            ):
                raise ValueError(f"game {game.game_seed}: bad candidates")
            if not np.all(np.isfinite(row.values[:, valid])):
                raise ValueError(f"game {game.game_seed}: non-finite values")
        elif valid.any():
            raise ValueError(f"game {game.game_seed}: anchor row with candidates")


def write_game(path: Path, game: LabelledGame, meta: Mapping[str, object]) -> None:
    """Write one game's shard atomically (``.tmp`` then rename)."""

    arrays = game_arrays(game)
    header = dict(meta)
    header.update(
        {
            "format": EXPERT_FORMAT,
            "game_seed": game.game_seed,
            "leader_ids": list(game.leader_ids),
            "rounds": game.rounds,
            "seconds": game.seconds,
            "guard_skips": game.guard_skips,
            "played_is_first": game.played_is_first,
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp.npz")
    arrays["meta_json"] = np.asarray(json.dumps(header))
    np.savez_compressed(temporary, allow_pickle=False, **arrays)
    os.replace(temporary, path)


def run_meta(
    teacher: str, config: LabelConfig, action_size: int, ruleset: str
) -> dict[str, object]:
    """The header every shard of a collection shares."""

    return {
        "teacher": str(teacher),
        "ruleset": ruleset,
        "observation_version": OBSERVATION_VERSION,
        "observation_size": OBSERVATION_SIZE,
        "action_codec_version": ACTION_CODEC_VERSION,
        "action_size": action_size,
        "label_config": asdict(config),
    }


def _label_one(
    item: tuple[MatchSpec, str, LabelConfig],
) -> LabelledGame | tuple[int, str]:
    spec, teacher, config = item
    try:
        return label_game(spec, teacher, config)
    except Exception as error:  # noqa: BLE001 - a failed game is recorded, not fatal
        return (spec.game_seed, f"{type(error).__name__}: {error}")


def collect_to_directory(
    teacher: str,
    out: Path,
    *,
    start_seed: int,
    games: int,
    workers: int,
    config: LabelConfig,
) -> dict[str, object]:
    """Label ``games`` seeds and write each finished game as ``g<seed>.npz``.

    Seeds whose file already exists are skipped, so a killed collection can
    be rerun over the same range. Returns a summary for the caller to log.
    """

    agent = load_network_agent(teacher)
    action_size = agent.codec.size
    specs = [
        spec
        for spec in collection_specs(teacher, start_seed=start_seed, games=games)
        if not (out / f"g{spec.game_seed}.npz").exists()
    ]
    ruleset = specs[0].config.identifier if specs else ""
    meta = run_meta(teacher, config, action_size, ruleset)
    started = time.perf_counter()
    written: list[LabelledGame] = []
    failures: list[tuple[int, str]] = []

    def keep(result: LabelledGame | tuple[int, str]) -> None:
        if isinstance(result, tuple):
            failures.append(result)
            return
        try:
            validate_game(result, action_size)
        except ValueError as error:
            failures.append((result.game_seed, str(error)))
            return
        write_game(out / f"g{result.game_seed}.npz", result, meta)
        written.append(result)

    items = [(spec, teacher, config) for spec in specs]
    if workers > 1 and len(items) > 1:
        with ProcessPoolExecutor(
            max_workers=workers, initializer=_single_threaded_worker
        ) as pool:
            futures = [pool.submit(_label_one, item) for item in items]
            for future in as_completed(futures):
                keep(future.result())
    else:
        for item in items:
            keep(_label_one(item))
    labels = sum(1 for g in written for r in g.rows if r.kind == LABEL)
    anchors = sum(1 for g in written for r in g.rows if r.kind == ANCHOR)
    first = sum(g.played_is_first for g in written)
    leaders = {leader for g in written for leader in g.leader_ids}
    return {
        "games": len(written),
        "skipped_existing": games - len(specs),
        "failures": len(failures),
        "failure_messages": [f"{seed}: {message}" for seed, message in failures[:10]],
        "labels": labels,
        "anchors": anchors,
        "played_eq_cand0": (first / labels) if labels else None,
        "guard_skips": sum(g.guard_skips for g in written),
        "distinct_leaders": len(leaders),
        "wall_seconds": time.perf_counter() - started,
        "s_per_game": (
            sum(g.seconds for g in written) / len(written) if written else None
        ),
    }


@dataclass(frozen=True)
class ExpertData:
    """Many shards stacked; legal sets and prior logits are CSR-aligned."""

    observations: np.ndarray
    legal_indices: np.ndarray
    legal_offsets: np.ndarray
    prior_logits: np.ndarray
    kind: np.ndarray
    seat: np.ndarray
    round: np.ndarray
    decision_index: np.ndarray
    seat_decisions: np.ndarray
    candidates: np.ndarray
    values: np.ndarray
    played: np.ndarray
    z: np.ndarray
    weight: np.ndarray
    game_seed: np.ndarray
    action_size: int
    teachers: tuple[str, ...] = field(default=())

    @property
    def rows(self) -> int:
        return int(self.kind.shape[0])

    def heldout(self, modulus: int = 10) -> np.ndarray:
        """Rows of games whose seed is divisible by ``modulus`` (never trained)."""

        mask: np.ndarray = (self.game_seed % modulus) == 0
        return mask


def read_shards(
    paths: Sequence[Path], *, weights: Sequence[float] | None = None
) -> ExpertData:
    """Stack game shards into one ``ExpertData``.

    Refuses mixed formats, versions, rulesets or search shapes, and
    duplicate game seeds (the same seed replays the same game).
    """

    if not paths:
        raise ValueError("no shards to read")
    if weights is not None and len(weights) != len(paths):
        raise ValueError("one weight per shard")
    loaded = []
    keys: dict[str, object] | None = None
    shape: tuple[tuple[int, ...], tuple[int, ...]] | None = None
    seeds: set[int] = set()
    for position, path in enumerate(paths):
        with np.load(path, allow_pickle=False) as handle:
            meta = json.loads(str(handle["meta_json"]))
            arrays = {key: handle[key] for key in handle.files if key != "meta_json"}
        if meta.get("format") != EXPERT_FORMAT:
            raise ValueError(f"{path}: unsupported format {meta.get('format')}")
        these = {
            name: meta[name]
            for name in (
                "ruleset",
                "observation_version",
                "observation_size",
                "action_codec_version",
                "action_size",
            )
        }
        if keys is None:
            keys = these
        elif these != keys:
            raise ValueError(f"{path}: {these} differs from {keys}")
        if arrays["kind"].size:
            this_shape = (
                tuple(arrays["values"].shape[1:]),
                tuple(arrays["candidates"].shape[1:]),
            )
            if shape is None:
                shape = this_shape
            elif this_shape != shape:
                raise ValueError(
                    f"{path}: search shape {this_shape} differs from {shape}"
                )
        seed = int(meta["game_seed"])
        if seed in seeds:
            raise ValueError(f"{path}: duplicate game seed {seed}")
        seeds.add(seed)
        weight = 1.0 if weights is None else float(weights[position])
        loaded.append((arrays, seed, weight, str(meta.get("teacher", ""))))
    assert keys is not None
    total_rows = sum(a["kind"].shape[0] for a, _, _, _ in loaded)
    total_legal = sum(a["legal_indices"].shape[0] for a, _, _, _ in loaded)
    worlds, width = shape[0] if shape is not None else (0, 0)
    observations = np.empty((total_rows, OBSERVATION_SIZE), dtype=np.uint8)
    legal_indices = np.empty(total_legal, dtype=np.int32)
    prior_logits = np.empty(total_legal, dtype=np.float32)
    legal_offsets = np.zeros(total_rows + 1, dtype=np.int64)
    columns: dict[str, list[np.ndarray]] = {
        name: []
        for name in (
            "kind",
            "seat",
            "round",
            "decision_index",
            "seat_decisions",
            "candidates",
            "values",
            "played",
            "z",
        )
    }
    weight_parts: list[np.ndarray] = []
    seed_parts: list[np.ndarray] = []
    row_at = legal_at = 0
    for arrays, seed, weight, _ in loaded:
        count = arrays["kind"].shape[0]
        length = arrays["legal_indices"].shape[0]
        observations[row_at : row_at + count] = arrays["observations"]
        legal_indices[legal_at : legal_at + length] = arrays["legal_indices"]
        prior_logits[legal_at : legal_at + length] = arrays["prior_logits"]
        legal_offsets[row_at + 1 : row_at + count + 1] = (
            arrays["legal_offsets"][1:] + legal_at
        )
        for name, parts in columns.items():
            parts.append(arrays[name])
        weight_parts.append(np.full(count, weight, dtype=np.float32))
        seed_parts.append(np.full(count, seed, dtype=np.int64))
        row_at += count
        legal_at += length
    stacked = {
        name: (np.concatenate(parts) if parts else np.zeros(0))
        for name, parts in columns.items()
    }
    return ExpertData(
        observations=observations,
        legal_indices=legal_indices,
        legal_offsets=legal_offsets,
        prior_logits=prior_logits,
        kind=stacked["kind"].astype(np.int8),
        seat=stacked["seat"].astype(np.int8),
        round=stacked["round"].astype(np.int16),
        decision_index=stacked["decision_index"].astype(np.int32),
        seat_decisions=stacked["seat_decisions"].astype(np.int32),
        candidates=(stacked["candidates"].astype(np.int32).reshape(total_rows, width)),
        values=stacked["values"].astype(np.float32).reshape(total_rows, worlds, width),
        played=stacked["played"].astype(np.int32),
        z=stacked["z"].astype(np.float32),
        weight=np.concatenate(weight_parts)
        if weight_parts
        else np.zeros(0, np.float32),
        game_seed=np.concatenate(seed_parts) if seed_parts else np.zeros(0, np.int64),
        action_size=int(str(keys["action_size"])),
        teachers=tuple(sorted({teacher for _, _, _, teacher in loaded})),
    )
