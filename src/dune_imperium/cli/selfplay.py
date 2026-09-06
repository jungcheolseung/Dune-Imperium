"""CLI for a lockstep self-play run: a throughput probe and data smoke test."""

import argparse
from collections.abc import Sequence

from dune_imperium.agents.registry import BASELINE_AGENT_FACTORIES
from dune_imperium.config import RulesetConfig
from dune_imperium.training import (
    AgentBatchPolicy,
    BatchPolicy,
    RandomBatchPolicy,
    SelfPlayRunner,
    SelfPlaySpec,
    stack_episodes,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dune-imperium-selfplay",
        description=(
            "Run seeded games in lockstep with batched policy inference and "
            "report episodes, decisions, rewards, and throughput."
        ),
    )
    parser.add_argument(
        "--games",
        type=int,
        default=8,
        help="games run in lockstep (default: 8)",
    )
    parser.add_argument(
        "--policy",
        default="random-batch",
        help=(
            "policy for every seat: random-batch (mask sampling) or a named "
            f"baseline ({', '.join(sorted(BASELINE_AGENT_FACTORIES))}); "
            "default: random-batch"
        ),
    )
    parser.add_argument(
        "--choam",
        action="store_true",
        help="use the CHOAM ruleset",
    )
    parser.add_argument(
        "--start-seed",
        type=int,
        default=0,
        help="first game seed; seeds run contiguously (default: 0)",
    )
    parser.add_argument(
        "--policy-seed",
        type=int,
        default=1_000_000,
        help="seed of the policy (default: 1000000)",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=30_000,
        help="per-game decision limit before truncation (default: 30000)",
    )
    parser.add_argument(
        "--no-record",
        action="store_true",
        help="skip trajectory recording (throughput only)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    policy: BatchPolicy
    if arguments.policy == "random-batch":
        policy = RandomBatchPolicy(seed=arguments.policy_seed)
    elif arguments.policy in BASELINE_AGENT_FACTORIES:
        policy = AgentBatchPolicy(arguments.policy, arguments.policy_seed)
    else:
        parser.error(f"unknown policy: {arguments.policy!r}")
    config = RulesetConfig(choam_module=arguments.choam)
    runner = SelfPlayRunner(
        config, max_steps=arguments.max_steps, record=not arguments.no_record
    )
    specs = tuple(
        SelfPlaySpec(game_seed=seed, lineup=(arguments.policy,) * config.players)
        for seed in range(arguments.start_seed, arguments.start_seed + arguments.games)
    )
    result = runner.run({arguments.policy: policy}, specs)
    episodes = result.episodes
    finished = sum(not episode.truncated for episode in episodes)
    per_second = (
        result.decisions / result.duration_seconds if result.duration_seconds else 0.0
    )
    print(
        f"{finished}/{len(episodes)} games finished in {result.duration_seconds:.1f}s; "
        f"{result.decisions} decisions ({per_second:,.0f} decisions/s); "
        f"mean rounds {sum(e.rounds for e in episodes) / len(episodes):.1f}"
    )
    winners = [episode.rewards.index(max(episode.rewards)) for episode in episodes]
    print(
        "winning seats: "
        + ", ".join(
            f"seat {seat}: {winners.count(seat)}" for seat in range(config.players)
        )
    )
    if not arguments.no_record:
        batch = stack_episodes(episodes)
        print(
            f"batch: observations {batch.observations.shape} masks {batch.masks.shape} "
            f"mean return {float(batch.returns.mean()):+.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
