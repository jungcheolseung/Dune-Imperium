"""CLI for the evaluation problem set (``evaluation.problem_set``)."""

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from dune_imperium.evaluation.problem_set import (
    DEFAULT_SUITE,
    PROBLEMS,
    answer,
    load_suite,
    mine,
    save_suite,
    suite_note,
    summarize_answers,
    unrestorable,
)
from dune_imperium.evaluation.tournament import tournament_specs


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dune-imperium-problems",
        description=(
            "Mine positions where one family of answers is right from seeded "
            "games, and score agents on them (share answered right, and a "
            "network's mean probability on the right answers)."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    mine_cmd = sub.add_parser("mine", help="play seeded games and keep positions")
    mine_cmd.add_argument("--agents", default="heuristic")
    mine_cmd.add_argument("--games", type=int, default=100)
    mine_cmd.add_argument("--start-seed", type=int, default=0)
    mine_cmd.add_argument("--choam", action="store_true")
    mine_cmd.add_argument("--bloodlines", action="store_true")
    mine_cmd.add_argument("--tech-module", action="store_true")
    mine_cmd.add_argument("--immortality", action="store_true")
    mine_cmd.add_argument("--promo-cards", action="store_true")
    mine_cmd.add_argument(
        "--problems",
        default="",
        help=f"comma-separated subset of {', '.join(PROBLEMS)}",
    )
    mine_cmd.add_argument(
        "--append", action="store_true", help="add to the positions already in --out"
    )
    mine_cmd.add_argument("--workers", type=int, default=1)
    mine_cmd.add_argument(
        "--max-per-problem",
        type=int,
        help="keep only the first N positions of each problem (seed order)",
    )
    mine_cmd.add_argument("--note", help="suite note (kept from --out when appending)")
    mine_cmd.add_argument("--out", type=Path, default=DEFAULT_SUITE)

    score_cmd = sub.add_parser("score", help="answer every position with agents")
    score_cmd.add_argument("--agents", required=True, help="comma-separated kinds")
    score_cmd.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    score_cmd.add_argument("--seed", type=int, default=0)
    score_cmd.add_argument("--json", type=Path, help="write per-position answers")

    check_cmd = sub.add_parser("check", help="restore every position of a suite")
    check_cmd.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    return parser


def _mine(args: argparse.Namespace) -> None:
    specs = tournament_specs(
        agents=tuple(args.agents.split(",")),
        games=args.games,
        rulesets=(args.choam,),
        start_seed=args.start_seed,
        rotate_leaders=True,
        promo_cards=args.promo_cards,
        bloodlines=args.bloodlines,
        tech_module=args.tech_module,
        immortality=args.immortality,
    )
    problems = [p for p in args.problems.split(",") if p] or None
    positions = mine(
        specs, problems, workers=args.workers, max_per_problem=args.max_per_problem
    )
    note = args.note or ""
    if args.append and args.out.exists():
        known = load_suite(args.out)
        ids = {p.position_id for p in known}
        positions = known + [p for p in positions if p.position_id not in ids]
        note = args.note or suite_note(args.out)
    save_suite(args.out, positions, note)
    counts: dict[str, int] = {}
    for position in positions:
        counts[position.problem_id] = counts.get(position.problem_id, 0) + 1
    print(f"{args.out}: {len(positions)} positions {counts}")


def _score(args: argparse.Namespace) -> None:
    positions = load_suite(args.suite)
    report: dict[str, object] = {}
    for kind in args.agents.split(","):
        answers = []
        moved = []
        for position in positions:
            try:
                answers.append(answer(position, kind, args.seed))
            except ValueError as error:
                moved.append(str(error))
        summary = summarize_answers(answers)
        report[kind] = {
            "summary": summary,
            "answers": [asdict(a) for a in answers],
            "moved": moved,
        }
        print(f"## {kind}")
        print(
            "| problem | confidence | positions | right | mean P(right) | unresolved |"
        )
        print("| --- | --- | ---: | ---: | ---: | ---: |")
        for problem_id, row in summary.items():
            p = row["mean_p_right"]
            print(
                f"| {problem_id} | {row['confidence']} | {row['positions']} "
                f"| {row['right']:.2f} | {'' if p is None else f'{p:.2f}'} "
                f"| {row['unresolved']} |"
            )
        if moved:
            print(f"{len(moved)} positions no longer restore; re-mine the suite:")
            for line in moved:
                print(f"- {line}")
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=1) + "\n")


def _check(args: argparse.Namespace) -> None:
    positions = load_suite(args.suite)
    failures = unrestorable(positions)
    print(f"{len(positions) - len(failures)}/{len(positions)} positions restore")
    for line in failures:
        print(f"- {line}")
    if failures:
        raise SystemExit(1)


def main(argv: Sequence[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    if args.command == "mine":
        _mine(args)
    elif args.command == "check":
        _check(args)
    else:
        _score(args)


if __name__ == "__main__":
    main()
