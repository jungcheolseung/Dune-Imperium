"""Probe what trained networks read, and score them on the problem suites.

    uv run python scripts/ab/network_probes.py X=checkpoints/play/mix-v139-10081.pt \\
        Y=checkpoints/2026-10-09/readapt-v141/Y/iteration_10881.pt

Prints, per network: the value head's sensitivity to single changes in the
observing seat's view, how much value and policy move when the Imperium Row is
swapped, where four greedy copies spend Family Atomics, and the answers on
the human problem suite and the AI mistake suite when they exist
(``evaluation.network_probes``, ``records.problems``,
docs/entity-network-plan.md section 4). Every network meets the same
positions (app_ai games, the play rules).
"""

import argparse
from pathlib import Path

from dune_imperium.config import RulesetConfig
from dune_imperium.evaluation.network_probes import (
    atomics_timing,
    row_sensitivity,
    sample_positions,
    value_sensitivity,
)
from dune_imperium.records.problems import (
    AI_MISTAKES_SUITE,
    DEFAULT_SUITE,
    Resolved,
    answer,
    load_suite,
    resolve,
    summarize,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.training.torch_policy import load_network_agent

PLAY_RULES = RulesetConfig(
    choam_module=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
    go_to_11=True,
    epic_game=True,
    arrakeen_scouts=True,
    leader_draft=True,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("networks", nargs="+", help="name=checkpoint path")
    parser.add_argument("--games", type=int, default=20, help="app_ai games to probe")
    parser.add_argument("--every", type=int, default=10)
    parser.add_argument("--atomics-games", type=int, default=20)
    parser.add_argument("--seed", type=int, default=8_100_000)
    parser.add_argument(
        "--suite",
        type=Path,
        action="append",
        help="problem suites to score (default: the human and AI mistake suites)",
    )
    arguments = parser.parse_args()

    seeds = range(arguments.seed, arguments.seed + arguments.games)
    positions = sample_positions(PLAY_RULES, seeds, every=arguments.every)
    print(f"{len(positions)} positions from {arguments.games} app_ai games")
    engine = UprisingRulesEngine()
    suites = [
        path
        for path in (arguments.suite or [DEFAULT_SUITE, AI_MISTAKES_SUITE])
        if path.exists()
    ]
    resolved = {
        path: [
            position
            for position in resolve(load_suite(path), engine).values()
            if isinstance(position, Resolved)
        ]
        for path in suites
    }

    for spec in arguments.networks:
        name, path = spec.split("=", 1)
        agent = load_network_agent(path, PLAY_RULES, seed=0)
        print(f"\n## {name} ({Path(path).name})")
        print("value change (changed - base, head scale; a win 1, a loss -1/3):")
        for change, estimate in value_sensitivity(agent, positions).items():
            print(
                f"  {change:<24} {estimate.mean:+.4f} "
                f"(SE {estimate.error:.4f}, n={estimate.count})"
            )
        row = row_sensitivity(agent, positions)
        print(
            f"row swapped: |value change| {row['value'].mean:.4f}, "
            f"policy total variation {row['policy'].mean:.3f} (n={row['policy'].count})"
        )
        timing = atomics_timing(
            f"checkpoint:{path}",
            PLAY_RULES,
            range(arguments.seed, arguments.seed + arguments.atomics_games),
        )
        print(
            f"family atomics: spent by {timing.spent}/{timing.seats} seats, "
            f"in round 1 by {timing.round_one}, in a Reveal turn by {timing.in_reveal}"
        )
        for suite_path, positions_of_suite in resolved.items():
            answers = [
                answer(position, f"checkpoint:{path}", 0, engine)
                for position in positions_of_suite
            ]
            for family, row_summary in summarize(answers).items():
                if "/" in family:
                    continue
                print(
                    f"{suite_path.name} {family:<14} n={row_summary['n']:3d} "
                    f"right {row_summary['right']:.0%} wrong {row_summary['wrong']:.0%}"
                )


if __name__ == "__main__":
    main()
