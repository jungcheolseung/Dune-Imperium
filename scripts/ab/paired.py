"""Paired comparison of two agents over one tournament's match rows.

    uv run dune-imperium-tournament --matches runs/ab.jsonl --games 200 \\
        --start-seed 1000 --agents checkpoint:A,checkpoint:B,checkpoint:A,checkpoint:B
    uv run python scripts/ab/paired.py runs/ab.jsonl --a checkpoint:A --b checkpoint:B

The tournament report gives each agent a win rate over its own matches, and
comparing two of those rows treats them as independent samples. They are not:
every rotation of a seed shares its Leaders, decks and first player, so the two
agents meet inside the same games and their per-match outcomes move together.
This reads the per-match rows instead and reports the *difference*, with a
confidence interval bootstrapped over **seeds** rather than matches -- rotations
of one seed are the same game dealt differently, so they are one cluster, and
treating them as independent understates the interval.

Three statistics per agent, all already present in a row: the win share (which
seat took rank 1), the mean rank of the agent's seats, and the VP margin (a
seat's Victory Points minus the mean of the other seats'). Rank and margin are
ordinal/continuous rather than binary, so for the same number of games they
resolve a smaller difference than the win rate does.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path


def per_match(row: dict, name: str) -> dict[str, float] | None:
    """Return one agent's outcome in one match, or None if it is not seated."""

    seats = [seat for seat in row["seats"] if seat["agent"] == name]
    if not seats:
        return None
    others = {seat["seat"]: seat for seat in row["seats"]}
    margins = []
    for seat in seats:
        rest = [o["victory_points"] for s, o in others.items() if s != seat["seat"]]
        margins.append(seat["victory_points"] - statistics.fmean(rest))
    return {
        "win": float(any(seat["rank"] == 1 for seat in seats)),
        "rank": statistics.fmean([seat["rank"] for seat in seats]),
        "margin": statistics.fmean(margins),
        "vp": statistics.fmean([seat["victory_points"] for seat in seats]),
    }


def bootstrap(
    clusters: list[list[float]], draws: int, seed: int
) -> tuple[float, float]:
    """Percentile interval of the mean, resampling whole clusters."""

    rng = random.Random(seed)
    size = len(clusters)
    means = []
    for _ in range(draws):
        picked = [clusters[rng.randrange(size)] for _ in range(size)]
        flat = [value for cluster in picked for value in cluster]
        means.append(statistics.fmean(flat))
    means.sort()
    return means[int(0.025 * draws)], means[int(0.975 * draws)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("rows", type=Path, help="match rows written by --matches")
    parser.add_argument("--a", required=True, help="agent name, the experiment")
    parser.add_argument("--b", required=True, help="agent name, the control")
    parser.add_argument("--draws", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=0)
    arguments = parser.parse_args()

    by_seed: dict[int, list[tuple[dict, dict]]] = defaultdict(list)
    matches = 0
    for line in arguments.rows.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        first = per_match(row, arguments.a)
        second = per_match(row, arguments.b)
        if first is None or second is None:
            continue
        by_seed[row["game_seed"]].append((first, second))
        matches += 1

    if not matches:
        parser.error(f"no match seats both {arguments.a!r} and {arguments.b!r}")

    print(f"{matches} matches over {len(by_seed)} seeds (clustered by seed)")
    print(f"  A = {arguments.a}")
    print(f"  B = {arguments.b}")
    print()
    header = f"{'statistic':>10} {'A':>9} {'B':>9} {'A-B':>9} {'95% CI of A-B':>22}"
    print(header)
    print("-" * len(header))
    for key, better in (("win", "higher"), ("rank", "lower"), ("margin", "higher")):
        clusters = [
            [first[key] - second[key] for first, second in pairs]
            for pairs in by_seed.values()
        ]
        flat = [value for cluster in clusters for value in cluster]
        low, high = bootstrap(clusters, arguments.draws, arguments.seed)
        a_mean = statistics.fmean(
            [first[key] for pairs in by_seed.values() for first, _ in pairs]
        )
        b_mean = statistics.fmean(
            [second[key] for pairs in by_seed.values() for _, second in pairs]
        )
        resolved = "  resolved" if low > 0.0 or high < 0.0 else "  inside noise"
        print(
            f"{key:>10} ({better:>6}) {a_mean:8.3f} {b_mean:8.3f} "
            f"{statistics.fmean(flat):+8.3f} [{low:+7.3f}, {high:+7.3f}]{resolved}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
