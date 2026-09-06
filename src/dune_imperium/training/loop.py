"""The M10 training loop: collect self-play, update, checkpoint, evaluate.

Every iteration plays ``games_per_iteration`` seeded games through the
lockstep runner with the learner in every seat (or, with an opponent kind,
the learner rotating through one seat of a table of that baseline), keeps
the learner's own decisions, applies one learner update, appends a JSON
line of statistics, and saves ``latest.pt`` plus a numbered checkpoint.
Every ``eval_every`` iterations the latest checkpoint enters an in-process
tournament against the evaluation opponent so progress is measured with
the same tool as every other baseline. Training seeds start far above the
tournament's default seeds so evaluation never replays a training game.
"""

import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import torch

from dune_imperium.agents.registry import CHECKPOINT_PREFIX, is_agent_kind
from dune_imperium.config import RulesetConfig
from dune_imperium.evaluation import run_tournament, summarize, tournament_specs
from dune_imperium.training.checkpoint import load_checkpoint, save_checkpoint
from dune_imperium.training.collect import Collector
from dune_imperium.training.learner import Learner, LearnerConfig, UpdateStats
from dune_imperium.training.network import DEFAULT_HIDDEN, PolicyValueNetwork
from dune_imperium.training.selfplay import (
    Episode,
    SelfPlayRunner,
    SelfPlaySpec,
    apply_step_penalty,
    select_policy_steps,
)
from dune_imperium.training.torch_policy import resolve_device

LEARNER = "learner"
TRAINING_SEED_BASE = 2_000_000


@dataclass(frozen=True, slots=True)
class TrainConfig:
    out_dir: Path
    iterations: int = 10
    games_per_iteration: int = 32
    seed: int = 0
    device: str = "cpu"
    # Worker processes for collection; 1 collects in-process.
    workers: int = 1
    choam_module: bool = False
    hidden: tuple[int, ...] = DEFAULT_HIDDEN
    learner: LearnerConfig = field(default_factory=LearnerConfig)
    # Baseline kind seated in the three other seats during collection; None
    # means pure self-play with the learner in every seat.
    opponent: str | None = None
    temperature: float = 1.0
    # Learning-side shaping: cost per own decision charged against the
    # terminal reward (see apply_step_penalty); 0 disables it.
    step_penalty: float = 0.0005
    # Decisions per training game before truncation (reward 0). A normal
    # game takes about 650; the cap bounds a policy that learns to loop.
    max_steps: int = 4_000
    eval_every: int = 0
    eval_games: int = 10
    eval_opponent: str = "heuristic"
    resume: Path | None = None

    def __post_init__(self) -> None:
        if self.iterations < 1 or self.games_per_iteration < 1:
            raise ValueError("iterations and games_per_iteration must be positive")
        if self.opponent is not None and not is_agent_kind(self.opponent):
            raise ValueError(f"unknown opponent kind: {self.opponent!r}")
        if self.eval_every and not is_agent_kind(self.eval_opponent):
            raise ValueError(f"unknown evaluation opponent: {self.eval_opponent!r}")
        if self.eval_every < 0 or self.eval_games < 1:
            raise ValueError("eval_every must not be negative; eval_games positive")
        if self.workers < 1:
            raise ValueError("workers must be positive")
        if self.step_penalty < 0.0:
            raise ValueError("step_penalty must not be negative")


@dataclass(frozen=True, slots=True)
class IterationRecord:
    iteration: int
    games: int
    learner_steps: int
    learner_win_rate: float
    learner_mean_reward: float
    mean_rounds: float
    truncated: int
    collect_seconds: float
    update_seconds: float
    decisions_per_second: float
    update: UpdateStats
    eval_win_rate: float | None = None
    eval_mean_rank: float | None = None


@dataclass(frozen=True, slots=True)
class TrainResult:
    records: tuple[IterationRecord, ...]
    latest_checkpoint: Path
    log_path: Path


__all__ = [
    "TrainConfig",
    "IterationRecord",
    "TrainResult",
    "select_policy_steps",
    "train",
]


def _iteration_specs(config: TrainConfig, iteration: int) -> tuple[SelfPlaySpec, ...]:
    players = 4
    first = (
        TRAINING_SEED_BASE
        + config.seed * 1_000_000
        + iteration * config.games_per_iteration
    )
    specs = []
    for offset in range(config.games_per_iteration):
        if config.opponent is None:
            lineup: tuple[str, ...] = (LEARNER,) * players
        else:
            seat = offset % players
            lineup = tuple(
                LEARNER if index == seat else config.opponent
                for index in range(players)
            )
        specs.append(SelfPlaySpec(game_seed=first + offset, lineup=lineup))
    return tuple(specs)


def _learner_outcomes(episodes: tuple[Episode, ...]) -> tuple[float, float]:
    """Return the learner seats' (win rate, mean reward) over the episodes."""

    rewards: list[float] = []
    wins = 0
    for episode in episodes:
        for seat, name in enumerate(episode.lineup):
            if name != LEARNER:
                continue
            rewards.append(episode.rewards[seat])
            wins += int(episode.ranks[seat] == 1)
    return (wins / len(rewards) if rewards else 0.0, float(np.mean(rewards)))


def _evaluate(config: TrainConfig, checkpoint: Path) -> tuple[float, float]:
    """Tournament win rate and mean rank of the checkpoint vs the opponent."""

    # One checkpoint seat against three opponents (a two-kind lineup would
    # cycle to two checkpoint seats and cap the win rate at 50%).
    specs = tournament_specs(
        agents=(f"{CHECKPOINT_PREFIX}{checkpoint}", *(config.eval_opponent,) * 3),
        games=config.eval_games,
        rulesets=(config.choam_module,),
        rotate_leaders=True,
    )
    summary = summarize(run_tournament(specs))
    entry = next(
        agent for agent in summary.agents if agent.agent.startswith(CHECKPOINT_PREFIX)
    )
    return entry.win_rate, entry.mean_rank


def train(
    config: TrainConfig,
    *,
    progress: Callable[[IterationRecord], None] | None = None,
) -> TrainResult:
    """Run the loop and return every iteration's record."""

    device = resolve_device(config.device)
    ruleset = RulesetConfig(choam_module=config.choam_module)
    codec_size = SelfPlayRunner(ruleset, record=False).codec.size
    start_iteration = 0
    if config.resume is not None:
        network, info = load_checkpoint(config.resume)
        if info.ruleset != ruleset.identifier:
            raise ValueError("resumed checkpoint belongs to a different ruleset")
        start_iteration = info.iteration
    else:
        torch.manual_seed(config.seed)
        network = PolicyValueNetwork(codec_size, hidden=config.hidden)
    learner = Learner(network, device, config.learner, seed=config.seed)
    collector = Collector(
        ruleset,
        workers=config.workers,
        max_steps=config.max_steps,
        temperature=config.temperature,
        opponent=config.opponent,
    )

    config.out_dir.mkdir(parents=True, exist_ok=True)
    log_path = config.out_dir / "training.jsonl"
    latest = config.out_dir / "latest.pt"
    records: list[IterationRecord] = []
    with log_path.open("a") as log, collector:
        for iteration in range(start_iteration, start_iteration + config.iterations):
            result = collector.collect(
                learner.network,
                device,
                _iteration_specs(config, iteration),
                policy_seed=config.seed + 1 + iteration * 1_000,
                opponent_seed=config.seed + 2 + iteration * 1_000,
            )
            collect_seconds = result.duration_seconds
            batch = apply_step_penalty(result.batch, config.step_penalty)
            started = time.perf_counter()
            stats = learner.update(batch)
            update_seconds = time.perf_counter() - started
            win_rate, mean_reward = _learner_outcomes(result.episodes)
            save_checkpoint(
                latest,
                learner.network,
                ruleset=ruleset.identifier,
                iteration=iteration + 1,
                metadata={"config": _config_document(config)},
            )
            save_checkpoint(
                config.out_dir / f"iteration_{iteration + 1:05d}.pt",
                learner.network,
                ruleset=ruleset.identifier,
                iteration=iteration + 1,
            )
            eval_win_rate = eval_mean_rank = None
            if config.eval_every and (iteration + 1) % config.eval_every == 0:
                eval_win_rate, eval_mean_rank = _evaluate(config, latest)
            record = IterationRecord(
                iteration=iteration + 1,
                games=len(result.episodes),
                learner_steps=stats.steps,
                learner_win_rate=win_rate,
                learner_mean_reward=mean_reward,
                mean_rounds=float(np.mean([e.rounds for e in result.episodes])),
                truncated=sum(e.truncated for e in result.episodes),
                collect_seconds=collect_seconds,
                update_seconds=update_seconds,
                decisions_per_second=(
                    result.decisions / collect_seconds if collect_seconds else 0.0
                ),
                update=stats,
                eval_win_rate=eval_win_rate,
                eval_mean_rank=eval_mean_rank,
            )
            records.append(record)
            log.write(json.dumps(asdict(record)) + "\n")
            log.flush()
            if progress is not None:
                progress(record)
    return TrainResult(
        records=tuple(records), latest_checkpoint=latest, log_path=log_path
    )


def _config_document(config: TrainConfig) -> dict[str, object]:
    document = asdict(config)
    document["out_dir"] = str(config.out_dir)
    document["resume"] = None if config.resume is None else str(config.resume)
    document["hidden"] = list(config.hidden)
    return document
