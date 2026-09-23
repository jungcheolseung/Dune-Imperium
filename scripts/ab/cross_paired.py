"""Paired comparison of one seat's agent across two tournament cells.

    uv run dune-imperium-tournament --matches runs/a.jsonl --games 25 \\
        --start-seed 62000 --agents A,checkpoint:C,checkpoint:C,checkpoint:C
    uv run dune-imperium-tournament --matches runs/b.jsonl --games 25 \\
        --start-seed 62000 --agents B,checkpoint:C,checkpoint:C,checkpoint:C
    uv run python scripts/ab/cross_paired.py runs/a.jsonl runs/b.jsonl --a A --b B

``paired.py`` compares two agents seated in the same matches. This compares
two agents that each ran a cell of their own against the same opponents on
the same seeds -- the one-against-three cells a search seat is judged in.
A match of cell A is paired with the match of cell B that has the same game
seed and puts the tested agent in the same seat: the same Leaders, decks,
first player and opponents, so the pair differs only by the tested agent
(and whatever the games do differently once its choices diverge). The
difference is bootstrapped over seeds, since the rotations of one seed are
one deal.

Each cell's own share is also reported against the one-against-three null
of 25%, with the same seed-clustered interval.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paired import bootstrap, per_match  # noqa: E402


def cell(path: Path, name: str) -> dict[tuple[int, int], dict[str, float]]:
    """Map (game seed, tested seat) to the tested agent's outcome."""

    outcomes: dict[tuple[int, int], dict[str, float]] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        seats = [seat["seat"] for seat in row["seats"] if seat["agent"] == name]
        if len(seats) != 1:
            continue
        outcome = per_match(row, name)
        assert outcome is not None
        outcomes[(row["game_seed"], seats[0])] = outcome
    return outcomes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("a_rows", type=Path, help="cell A's --matches rows")
    parser.add_argument("b_rows", type=Path, help="cell B's --matches rows")
    parser.add_argument("--a", required=True, help="the tested agent in cell A")
    parser.add_argument("--b", required=True, help="the tested agent in cell B")
    parser.add_argument("--draws", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=0)
    arguments = parser.parse_args()

    first = cell(arguments.a_rows, arguments.a)
    second = cell(arguments.b_rows, arguments.b)
    keys = sorted(first.keys() & second.keys())
    if not keys:
        parser.error("the two cells share no (seed, seat) match")
    by_seed: dict[int, list[tuple[dict, dict]]] = defaultdict(list)
    for key in keys:
        by_seed[key[0]].append((first[key], second[key]))

    print(
        f"{len(keys)} paired matches over {len(by_seed)} seeds "
        f"(A has {len(first)}, B has {len(second)})"
    )
    print(f"  A = {arguments.a}  ({arguments.a_rows})")
    print(f"  B = {arguments.b}  ({arguments.b_rows})")
    print()
    seeds = list(by_seed.values())
    for label, index in (("A", 0), ("B", 1)):
        clusters = [[pair[index]["win"] for pair in pairs] for pairs in seeds]
        low, high = bootstrap(clusters, arguments.draws, arguments.seed)
        share = statistics.fmean([v for c in clusters for v in c])
        interval = f"[{100 * low:.1f}, {100 * high:.1f}]"
        print(f"{label} win share {100 * share:5.1f}%  {interval}")
    print()
    header = f"{'statistic':>10} {'A':>9} {'B':>9} {'A-B':>9} {'95% CI of A-B':>22}"
    print(header)
    print("-" * len(header))
    for key, better in (("win", "higher"), ("rank", "lower"), ("margin", "higher")):
        clusters = [[a[key] - b[key] for a, b in pairs] for pairs in by_seed.values()]
        flat = [value for cluster in clusters for value in cluster]
        low, high = bootstrap(clusters, arguments.draws, arguments.seed)
        a_mean = statistics.fmean([a[key] for pairs in seeds for a, _ in pairs])
        b_mean = statistics.fmean([b[key] for pairs in seeds for _, b in pairs])
        resolved = "  resolved" if low > 0.0 or high < 0.0 else "  inside noise"
        print(
            f"{key:>10} ({better:>6}) {a_mean:8.3f} {b_mean:8.3f} "
            f"{statistics.fmean(flat):+8.3f} [{low:+7.3f}, {high:+7.3f}]{resolved}"
        )
    same = sum(
        a["rank"] == b["rank"] and a["vp"] == b["vp"]
        for pairs in by_seed.values()
        for a, b in pairs
    )
    print(f"\npairs with the same rank and VP in both cells: {same}/{len(keys)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
