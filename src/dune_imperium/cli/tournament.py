"""CLI for the M9 baseline tournament."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from dune_imperium.agents.registry import BASELINE_AGENT_FACTORIES
from dune_imperium.evaluation import (
    render_markdown,
    run_tournament,
    summarize,
    summary_to_json,
    tournament_specs,
)

_RULESETS = {
    "base": (False,),
    "choam": (True,),
    "both": (False, True),
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dune-imperium-tournament",
        description=(
            "Play seeded four-player games between named baseline agents, "
            "rotating the lineup through every seat, and report win rate, "
            "mean rank, VP margin, seat and Leader splits, illegal actions, "
            "and decision time per agent."
        ),
    )
    parser.add_argument(
        "--agents",
        default="heuristic,random",
        help=(
            "comma-separated agent kinds for the table, cycled to four seats "
            f"(choices: {', '.join(sorted(BASELINE_AGENT_FACTORIES))}, or "
            "checkpoint:<path> for a trained policy; default: heuristic,random)"
        ),
    )
    parser.add_argument(
        "--games",
        type=int,
        default=25,
        help="game seeds per selected ruleset; each seed plays every seat "
        "rotation of the lineup (default: 25)",
    )
    parser.add_argument(
        "--ruleset",
        choices=sorted(_RULESETS),
        default="base",
        help="which ruleset(s) to play (default: base)",
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
        default=900_000,
        help="policy seed = offset + game seed (default: 900000)",
    )
    parser.add_argument(
        "--no-rotate-seats",
        action="store_true",
        help="play the lineup in the given seat order only",
    )
    parser.add_argument(
        "--rotate-leaders",
        action="store_true",
        help=(
            "deal each seed a different random four-Leader roster "
            "(same derivation as dune-imperium-sweep --rotate-leaders)"
        ),
    )
    parser.add_argument(
        "--promo-cards",
        action="store_true",
        help=(
            "shuffle the promo Imperium cards into the deck (three Uprising "
            "promos; with --bloodlines also Ruthless Leadership)"
        ),
    )
    parser.add_argument(
        "--bloodlines",
        action="store_true",
        help="play with the Bloodlines expansion",
    )
    parser.add_argument(
        "--tech-module",
        action="store_true",
        help="add the Bloodlines Tech Module (requires --bloodlines)",
    )
    parser.add_argument(
        "--immortality",
        action="store_true",
        help="play with the Immortality expansion",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="worker processes; 1 runs in-process (default: 1)",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=30_000,
        help="per-game step limit before reporting a failure (default: 30000)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="write the summary as JSON to this path",
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=None,
        help="write the Markdown report to this path",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    agents = tuple(kind.strip() for kind in arguments.agents.split(",") if kind.strip())
    try:
        specs = tournament_specs(
            agents=agents,
            games=arguments.games,
            rulesets=_RULESETS[arguments.ruleset],
            start_seed=arguments.start_seed,
            policy_offset=arguments.policy_offset,
            rotate_seats=not arguments.no_rotate_seats,
            rotate_leaders=arguments.rotate_leaders,
            promo_cards=arguments.promo_cards,
            bloodlines=arguments.bloodlines,
            tech_module=arguments.tech_module,
            immortality=arguments.immortality,
            max_steps=arguments.max_steps,
        )
    except ValueError as error:
        parser.error(str(error))
    report = run_tournament(specs, workers=arguments.workers)
    summary = summarize(report)
    markdown = render_markdown(summary)
    print(markdown, end="")
    if arguments.json is not None:
        arguments.json.parent.mkdir(parents=True, exist_ok=True)
        arguments.json.write_text(
            json.dumps(summary_to_json(summary), indent=2, sort_keys=True)
        )
        print(f"summary JSON written to {arguments.json}")
    if arguments.markdown is not None:
        arguments.markdown.parent.mkdir(parents=True, exist_ok=True)
        arguments.markdown.write_text(markdown)
        print(f"Markdown report written to {arguments.markdown}")
    return 1 if report.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
