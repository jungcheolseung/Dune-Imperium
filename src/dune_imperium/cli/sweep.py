"""CLI for the M7 full-game verification sweep."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from dune_imperium.simulation.coverage import Census, merge_coverage, zero_coverage
from dune_imperium.simulation.sweep import (
    POLICIES,
    GameCheckReport,
    run_sweep,
    sweep_specs,
)

_ChoamModuleByRuleset = {"uprising-4p-base": False, "uprising-4p-choam": True}

_RULESETS = {
    "base": (False,),
    "choam": (True,),
    "both": (False, True),
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dune-imperium-sweep",
        description=(
            "Play seeded four-player games to FINISHED with one baseline "
            "policy while checking card conservation, deadlocks, observation "
            "privacy, and replays."
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
        "--policy",
        choices=sorted(POLICIES),
        default="random",
        help="baseline policy driving every seat (default: random)",
    )
    parser.add_argument(
        "--leader-draft",
        action="store_true",
        help="use the OQ-007 six-Leader draft setup instead of fixed Leaders",
    )
    parser.add_argument(
        "--rotate-leaders",
        action="store_true",
        help=(
            "deal each game a different random four-Leader roster (deterministic "
            "per game seed) instead of the engine's fixed default; rejected "
            "together with --leader-draft"
        ),
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
        "--soundness-interval",
        type=int,
        default=0,
        help=(
            "at every Nth player decision, check that every advertised legal "
            "action applies and round-trips through the action codec; "
            "0 disables the check (default: 0)"
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
    parser.add_argument(
        "--coverage-json",
        type=Path,
        default=None,
        help=(
            "collect a content-coverage census per ruleset and write "
            "{ruleset: {counts, zero}} JSON to this path"
        ),
    )
    return parser


def _write_coverage_report(
    games: tuple[GameCheckReport, ...],
    path: Path,
) -> None:
    """Merge each game's census per ruleset, print zero-coverage, write JSON."""

    merged: dict[str, Census] = {}
    for game in games:
        if game.coverage is None:
            continue
        merged[game.ruleset] = (
            merge_coverage(merged[game.ruleset], game.coverage)
            if game.ruleset in merged
            else game.coverage
        )

    report: dict[str, dict[str, object]] = {}
    for ruleset, counts in sorted(merged.items()):
        zero = zero_coverage(counts, choam_module=_ChoamModuleByRuleset[ruleset])
        report[ruleset] = {"counts": counts, "zero": zero}
        zero_summary = ", ".join(
            f"{dimension}={len(missing)}" for dimension, missing in sorted(zero.items())
        )
        print(
            f"coverage {ruleset}: {len(counts)} dimensions tracked; "
            f"zero counts: {zero_summary}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True))
    print(f"coverage census written to {path}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    if arguments.rotate_leaders and arguments.leader_draft:
        parser.error("--rotate-leaders cannot be combined with --leader-draft")
    specs = sweep_specs(
        games=arguments.games,
        rulesets=_RULESETS[arguments.ruleset],
        start_seed=arguments.start_seed,
        policy_offset=arguments.policy_offset,
        max_steps=arguments.max_steps,
        privacy_interval=arguments.privacy_interval,
        soundness_interval=arguments.soundness_interval,
        verify_replay=not arguments.skip_replay,
        policy=arguments.policy,
        leader_draft=arguments.leader_draft,
        rotate_leaders=arguments.rotate_leaders,
        collect_coverage=arguments.coverage_json is not None,
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
    if arguments.coverage_json is not None:
        _write_coverage_report(report.games, arguments.coverage_json)
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
