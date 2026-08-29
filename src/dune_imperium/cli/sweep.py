"""CLI for the M7 random full-game verification sweep."""

import argparse
from collections.abc import Sequence

from dune_imperium.simulation.sweep import run_sweep, sweep_specs

_RULESETS = {
    "base": (False,),
    "choam": (True,),
    "both": (False, True),
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dune-imperium-sweep",
        description=(
            "Play seeded random four-player games to FINISHED while checking "
            "card conservation, deadlocks, observation privacy, and replays."
        ),
    )
    parser.add_argument(
        "--games",
        type=int,
        default=100,
        help="games per selected ruleset (default: 100)",
    )
    parser.add_argument(
        "--ruleset",
        choices=sorted(_RULESETS),
        default="both",
        help="which ruleset(s) to sweep (default: both)",
    )
    parser.add_argument(
        "--start-seed",
        type=int,
        default=0,
        help="first game seed; seeds run contiguously (default: 0)",
    )
    parser.add_argument(
        "--policy-offset",
        type=int,
        default=700_000,
        help="policy seed = offset + game seed (default: 700000)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="worker processes; 1 runs in-process (default: 1)",
    )
    parser.add_argument(
        "--privacy-interval",
        type=int,
        default=25,
        help=(
            "check observation privacy every N player decisions; "
            "0 disables the check (default: 25)"
        ),
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=30_000,
        help="per-game step limit before reporting a deadlock (default: 30000)",
    )
    parser.add_argument(
        "--skip-replay",
        action="store_true",
        help="skip the per-game replay verification",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    specs = sweep_specs(
        games=arguments.games,
        rulesets=_RULESETS[arguments.ruleset],
        start_seed=arguments.start_seed,
        policy_offset=arguments.policy_offset,
        max_steps=arguments.max_steps,
        privacy_interval=arguments.privacy_interval,
        verify_replay=not arguments.skip_replay,
    )
    report = run_sweep(specs, workers=arguments.workers)

    games_per_second = (
        len(report.games) / report.duration_seconds if report.duration_seconds else 0.0
    )
    steps_per_second = (
        report.total_steps / report.duration_seconds
        if report.duration_seconds
        else 0.0
    )
    print(
        f"{len(report.games)}/{len(specs)} games finished in "
        f"{report.duration_seconds:.1f}s "
        f"({games_per_second:.1f} games/s, {steps_per_second:,.0f} steps/s)"
    )
    if report.games:
        rounds = sorted(game.rounds for game in report.games)
        print(
            f"rounds: min {rounds[0]} / median {rounds[len(rounds) // 2]} / "
            f"max {rounds[-1]}; total steps {report.total_steps}"
        )
    for failure in report.failures:
        print(
            f"FAIL {failure.ruleset} seed={failure.game_seed} "
            f"policy={failure.policy_seed}: {failure.error}"
        )
    if report.failures:
        print(f"{len(report.failures)} failure(s)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
