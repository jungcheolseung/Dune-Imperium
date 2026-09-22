"""The M10 training loop: collect self-play, update, checkpoint, evaluate.

Every iteration plays ``games_per_iteration`` seeded games through the
lockstep runner with the learner in every seat (or, with an opponent kind,
the learner rotating through one seat of a table of that baseline), keeps
the learner's own decisions, applies one learner update, appends a JSON
line of statistics, and saves ``latest.pt`` plus, every ``checkpoint_every``
iterations, a numbered checkpoint (78 MB each for the full-expansion
catalog, so an overnight run keeps one in every few dozen).
Every ``eval_every`` iterations the latest checkpoint enters an in-process
tournament against the evaluation opponent so progress is measured with
the same tool as every other baseline. Training seeds start far above the
tournament's default seeds so evaluation never replays a training game.
"""

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import torch

from dune_imperium.agents.registry import CHECKPOINT_PREFIX, is_agent_kind
from dune_imperium.config import RulesetConfig
from dune_imperium.evaluation import (
    AgentSummary,
    TournamentSummary,
    run_tournament,
    summarize,
    tournament_specs,
)
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
# Where the in-training evaluation's seeds start. Between the tournament
# tool's usual small seeds and TRAINING_SEED_BASE, so a run's evaluation
# games are legible as their own range and never replay a training game.
EVAL_SEED_BASE = 1_000_000


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
    # Shuffle the promo Imperium cards into the deck (see RulesetConfig).
    promo_cards: bool = False
    # Play with the Bloodlines expansion (docs/rules/bloodlines.md).
    bloodlines: bool = False
    # The Bloodlines Tech Module; requires bloodlines.
    tech_module: bool = False
    # Play with the Immortality expansion (docs/rules/immortality.md).
    immortality: bool = False
    hidden: tuple[int, ...] = DEFAULT_HIDDEN
    learner: LearnerConfig = field(default_factory=LearnerConfig)
    # Baseline kind seated in the non-learner seats during collection; None
    # means pure self-play with the learner in every seat.
    opponent: str | None = None
    # Seats the learner holds at each table when ``opponent`` is set (1-3).
    # One learner seat against three frozen ones yields a quarter of the
    # learner rows of self-play per game (measured 6,103 against 24,805 a
    # 32-game iteration, 2026-09-22), so a fixed opponent is cheaper to
    # learn against at two seats each.
    learner_seats: int = 1
    temperature: float = 1.0
    # Pay the finishing order instead of winner-take-all during collection
    # (training.selfplay.rank_reward); a learning-side reward transform.
    rank_rewards: bool = False
    # Learning-side shaping: cost per own decision charged against the
    # terminal reward (see apply_step_penalty); 0 disables it.
    step_penalty: float = 0.0005
    # Decisions per training game before truncation (reward 0). A normal
    # game takes about 650; the cap bounds a policy that learns to loop.
    max_steps: int = 4_000
    eval_every: int = 0
    eval_games: int = 10
    eval_opponent: str = "heuristic"
    # Keep a numbered checkpoint every N iterations; ``latest.pt`` is
    # rewritten every iteration regardless.
    checkpoint_every: int = 1
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
        if self.checkpoint_every < 1:
            raise ValueError("checkpoint_every must be positive")
        if self.workers < 1:
            raise ValueError("workers must be positive")
        if self.step_penalty < 0.0:
            raise ValueError("step_penalty must not be negative")
        if not 1 <= self.learner_seats <= 3:
            raise ValueError("learner_seats must be between 1 and 3")
        if self.learner_seats != 1 and self.opponent is None:
            raise ValueError(
                "learner_seats needs an opponent (self-play seats all four)"
            )


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
    # Evaluation matches that raised instead of finishing. The rates above
    # cover the finished matches only, so a non-zero count is a defect to
    # look at (the messages go to ``eval_failures.log``), not noise.
    eval_failures: int | None = None


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
            learner = _learner_seats(offset, config.learner_seats, players)
            lineup = tuple(
                LEARNER if index in learner else config.opponent
                for index in range(players)
            )
        specs.append(SelfPlaySpec(game_seed=first + offset, lineup=lineup))
    return tuple(specs)


def _learner_seats(offset: int, count: int, players: int) -> frozenset[int]:
    """Which seats the learner holds in the ``offset``-th game of an iteration.

    The learner seats are spread evenly and the pattern rotates with the
    game, so over an iteration every seat position is the learner's equally
    often: one seat walks 0, 1, 2, 3; two seats alternate {0, 2} and {1, 3},
    the interleaved table the 2:2 evaluation mirror also uses.
    """

    step = players // count
    return frozenset((offset + index * step) % players for index in range(count))


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


def _evaluate(
    config: TrainConfig, checkpoint: Path, iteration: int
) -> tuple[float, float, tuple[str, ...]]:
    """Win rate and mean rank of the checkpoint vs the opponent, plus failures.

    ``eval_games`` counts seeds; every seed plays the four seat rotations,
    so the sample is four times that many matches.

    Each evaluation takes its own block of seeds. Leaving ``start_seed`` at
    the default replayed seeds 0..eval_games-1 at every evaluation of every
    run, so a whole run's series was one small fixed sample measured over
    and over: on 2026-09-21 a 1,000-iteration run read 24.5% against its
    own starting checkpoint across ten evaluations of the same 25 seeds,
    while 350 fresh seeds put the same checkpoint at 32.4% against a 25%
    null. Averaging those ten did not help, because they were the same
    games. Disjoint blocks cost the comparability of two consecutive
    readings and buy an unbiased series; the instrument that decides
    anything is the post-hoc tournament, not this tripwire.
    """

    # One checkpoint seat against three opponents (a two-kind lineup would
    # cycle to two checkpoint seats and cap the win rate at 50%).
    tested = f"{CHECKPOINT_PREFIX}{checkpoint}"
    specs = tournament_specs(
        agents=(tested, *(config.eval_opponent,) * 3),
        games=config.eval_games,
        rulesets=(config.choam_module,),
        start_seed=EVAL_SEED_BASE + iteration * config.eval_games,
        rotate_leaders=True,
        promo_cards=config.promo_cards,
        bloodlines=config.bloodlines,
        tech_module=config.tech_module,
        immortality=config.immortality,
    )
    # Collection is finished by the time an evaluation runs, so the same
    # worker budget is free; leaving this at the default of one process
    # played the whole evaluation in the training process (about 95s for 200
    # matches on a 4-core run against about 48s across four).
    summary = summarize(run_tournament(specs, workers=config.workers))
    entry = evaluated_entry(summary, tested)
    return entry.win_rate, entry.mean_rank, summary.failure_messages


def evaluated_entry(summary: TournamentSummary, tested: str) -> AgentSummary:
    """Return the summary row of the checkpoint under test, by its exact name.

    This used to take the first row whose name started with ``checkpoint:``.
    With the default opponent (``heuristic``) that was the only one, but a
    checkpoint opponent starts with the same prefix, and ``summarize`` sorts
    rows by name, so whichever path sorted first won: an older opponent
    directory sorted before the run's own and the evaluation read the
    OPPONENT's row. That row holds three seats, so it reported
    (1 - true win rate) / 3 -- identical at parity, and falling as the tested
    checkpoint got stronger. Measured on 2026-09-22: the evaluation logged
    21.3% at iteration 4000 where the same checkpoint, opponent and seeds
    replayed through the tournament CLI read 36.0%, and (100 - 36.0) / 3 is
    21.3.
    """

    matches = [agent for agent in summary.agents if agent.agent == tested]
    if len(matches) != 1:
        raise ValueError(f"no single summary row for the tested agent {tested!r}")
    return matches[0]


def train(
    config: TrainConfig,
    *,
    progress: Callable[[IterationRecord], None] | None = None,
) -> TrainResult:
    """Run the loop and return every iteration's record."""

    device = resolve_device(config.device)
    ruleset = RulesetConfig(
        choam_module=config.choam_module,
        promo_cards=config.promo_cards,
        bloodlines=config.bloodlines,
        tech_module=config.tech_module,
        immortality=config.immortality,
    )
    codec = SelfPlayRunner(ruleset, record=False).codec
    codec_size = codec.size
    start_iteration = 0
    resumed_optimizer: Mapping[str, Any] | None = None
    if config.resume is not None:
        network, info = load_checkpoint(config.resume)
        if info.ruleset != ruleset.identifier:
            raise ValueError("resumed checkpoint belongs to a different ruleset")
        if info.migration is not None:
            print(f"migrated {config.resume}: {info.migration.describe()}")
        start_iteration = info.iteration
        resumed_optimizer = info.optimizer_state
    else:
        torch.manual_seed(config.seed)
        network = PolicyValueNetwork(codec_size, hidden=config.hidden)
    learner = Learner(network, device, config.learner, seed=config.seed)
    if resumed_optimizer is not None:
        learner.restore_optimizer(resumed_optimizer)
    collector = Collector(
        ruleset,
        workers=config.workers,
        max_steps=config.max_steps,
        temperature=config.temperature,
        rank_rewards=config.rank_rewards,
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
                optimizer_state=learner.optimizer_state(),
                codec=codec,
            )
            if (iteration + 1) % config.checkpoint_every == 0:
                save_checkpoint(
                    config.out_dir / f"iteration_{iteration + 1:05d}.pt",
                    learner.network,
                    ruleset=ruleset.identifier,
                    iteration=iteration + 1,
                    codec=codec,
                )
            eval_win_rate = eval_mean_rank = None
            eval_failures: int | None = None
            if config.eval_every and (iteration + 1) % config.eval_every == 0:
                eval_win_rate, eval_mean_rank, failures = _evaluate(
                    config, latest, iteration + 1
                )
                eval_failures = len(failures)
                if failures:
                    with (config.out_dir / "eval_failures.log").open("a") as handle:
                        for message in failures:
                            handle.write(f"iteration {iteration + 1}: {message}\n")
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
                eval_failures=eval_failures,
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
