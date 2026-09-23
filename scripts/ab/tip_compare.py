"""Compare tip-census outputs column by column with seed-cluster bootstrap CIs.

Each argument is a ``tip_census.py`` output directory, optionally narrowed to
one agent kind of a mixed table with ``dir::kind``. Arm B minus arm A is
printed per numeric seat column. A tally column is flattened to ``col[key]``
(a seat without that key counts 0), and a column that is sometimes None also
gets ``has:col``, the share of seats where it applies; its own mean is over
those seats only. The rotations of one seed are one game family, so the
bootstrap resamples seeds, not seats; two arms read from the same directory
are resampled with the same seeds (paired), arms from different directories
independently.

    uv run python scripts/ab/tip_compare.py ab-runs/tips/heuristic-train \\
        ab-runs/tips/5081-train
    uv run python scripts/ab/tip_compare.py \\
        "ab-runs/tips/5081-vs-heuristic-train::heuristic" \\
        "ab-runs/tips/5081-vs-heuristic-train::checkpoint:<path>"

``--winners`` keeps winning seats only. ``--split-winners`` takes one arm and
compares its other seats (A) with its winners (B), resampling seeds jointly.
A difference is marked ``*`` when its 95% interval excludes 0; with about 150
columns, several are marked by chance alone, so read a marked column as a
lead, not a finding.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

SKIP = {"seat", "kind", "leader"}


def flatten(seat: dict[str, Any]) -> dict[str, float | None]:
    """Numeric seat columns; tallies as ``col[key]``; None stays None."""

    out: dict[str, float | None] = {}
    for name, value in seat.items():
        if name in SKIP or isinstance(value, (str, list)):
            continue
        if isinstance(value, dict):
            for key, count in value.items():
                out[f"{name}[{key}]"] = float(count)
        else:
            out[name] = None if value is None else float(value)
    return out


def load_arm(
    arg: str, winners: bool | None = None
) -> list[tuple[int, dict[str, float | None]]]:
    """Read ``dir`` or ``dir::kind`` into (seed, flattened seat) rows.

    ``winners`` True keeps winning seats only, False the other seats only.
    """

    directory, _, kind = arg.partition("::")
    rows = []
    with (Path(directory) / "rows.jsonl").open() as fh:
        for line in fh:
            game = json.loads(line)
            for seat in game["seats"]:
                if kind and seat["kind"] != kind:
                    continue
                if winners is not None and bool(seat["win"]) != winners:
                    continue
                rows.append((int(game["seed"]), flatten(seat)))
    if not rows:
        raise SystemExit(f"no seats in {arg}")
    return rows


def _columns(
    rows: Sequence[tuple[int, dict[str, float | None]]], names: Sequence[str]
) -> dict[str, list[tuple[int, float]]]:
    """Per column, the (seed, value) pairs that count toward its mean."""

    out: dict[str, list[tuple[int, float]]] = {name: [] for name in names}
    for seed, seat in rows:
        for name in names:
            if name.startswith("has:"):
                base = name[4:]
                if base in seat:
                    out[name].append((seed, 0.0 if seat[base] is None else 1.0))
            elif "[" in name:
                # A tally key a seat never hit is a 0 for that seat.
                value = seat.get(name)
                out[name].append((seed, 0.0 if value is None else value))
            else:
                value = seat.get(name)
                if value is not None:
                    out[name].append((seed, value))
    return out


def _sums(
    pairs: Sequence[tuple[int, float]], index: dict[int, int]
) -> tuple[np.ndarray, np.ndarray]:
    sums = np.zeros(len(index))
    counts = np.zeros(len(index))
    for seed, value in pairs:
        sums[index[seed]] += value
        counts[index[seed]] += 1
    return sums, counts


def compare(
    a_rows: Sequence[tuple[int, dict[str, float | None]]],
    b_rows: Sequence[tuple[int, dict[str, float | None]]],
    paired: bool,
    resamples: int = 2000,
    rng_seed: int = 7,
) -> list[dict[str, Any]]:
    """Per column: both means, B - A, and a 95% seed-cluster bootstrap CI."""

    plain = sorted({n for _, seat in (*a_rows, *b_rows) for n in seat})
    maybe_none = sorted(
        {n for _, seat in (*a_rows, *b_rows) for n, v in seat.items() if v is None}
    )
    names = sorted([*plain, *(f"has:{n}" for n in maybe_none)])
    cols_a = _columns(a_rows, names)
    cols_b = _columns(b_rows, names)
    seeds_a = sorted({seed for seed, _ in a_rows})
    seeds_b = sorted({seed for seed, _ in b_rows})
    index_a = {seed: i for i, seed in enumerate(seeds_a)}
    index_b = {seed: i for i, seed in enumerate(seeds_b)}
    rng = np.random.default_rng(rng_seed)
    draw_a = rng.integers(0, len(seeds_a), size=(resamples, len(seeds_a)))
    if paired:
        if seeds_a != seeds_b:
            raise ValueError("paired arms must cover the same seeds")
        draw_b = draw_a
    else:
        draw_b = rng.integers(0, len(seeds_b), size=(resamples, len(seeds_b)))
    rows = []
    for name in names:
        sa, na = _sums(cols_a[name], index_a)
        sb, nb = _sums(cols_b[name], index_b)
        mean_a = sa.sum() / na.sum() if na.sum() else None
        mean_b = sb.sum() / nb.sum() if nb.sum() else None
        low = high = None
        if mean_a is not None and mean_b is not None:
            with np.errstate(invalid="ignore", divide="ignore"):
                boot = sb[draw_b].sum(1) / nb[draw_b].sum(1) - sa[draw_a].sum(1) / na[
                    draw_a
                ].sum(1)
            boot = boot[np.isfinite(boot)]
            if boot.size:
                low, high = (float(q) for q in np.quantile(boot, [0.025, 0.975]))
        rows.append(
            {
                "column": name,
                "a": mean_a,
                "b": mean_b,
                "n_a": int(na.sum()),
                "n_b": int(nb.sum()),
                "diff": None if mean_a is None or mean_b is None else mean_b - mean_a,
                "low": low,
                "high": high,
            }
        )
    return rows


def _fmt(value: float | None) -> str:
    return "" if value is None else f"{value:.2f}"


def markdown(rows: Sequence[dict[str, Any]], label_a: str, label_b: str) -> str:
    lines = [
        f"| column | A: {label_a} | B: {label_b} | B - A [95% CI] |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        excluded = row["low"] is not None and (row["low"] > 0 or row["high"] < 0)
        interval = (
            f" [{_fmt(row['low'])}, {_fmt(row['high'])}]"
            if row["low"] is not None
            else ""
        )
        lines.append(
            f"| {row['column']} | {_fmt(row['a'])} (n={row['n_a']}) "
            f"| {_fmt(row['b'])} (n={row['n_b']}) "
            f"| {_fmt(row['diff'])}{interval}{' *' if excluded else ''} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("a", help="census dir, or dir::kind")
    ap.add_argument("b", nargs="?", help="census dir, or dir::kind")
    ap.add_argument("--winners", action="store_true", help="winning seats only")
    ap.add_argument(
        "--split-winners",
        action="store_true",
        help="compare arm a's other seats (A) with its winners (B)",
    )
    ap.add_argument("--columns", default="", help="comma-separated name prefixes")
    ap.add_argument("--resamples", type=int, default=2000)
    args = ap.parse_args(argv)
    if args.split_winners:
        a_rows = load_arm(args.a, winners=False)
        b_rows = load_arm(args.a, winners=True)
        labels = (f"{args.a} (others)", f"{args.a} (winners)")
        # Every seed has a winner and at least one other seat, so both arms
        # cover the same seeds.
        paired = True
    else:
        if args.b is None:
            ap.error("two arms are needed without --split-winners")
        only = True if args.winners else None
        a_rows = load_arm(args.a, only)
        b_rows = load_arm(args.b, only)
        labels = (args.a, args.b)
        paired = args.a.partition("::")[0] == args.b.partition("::")[0]
    rows = compare(a_rows, b_rows, paired=paired, resamples=args.resamples)
    prefixes = tuple(p for p in args.columns.split(",") if p)
    if prefixes:
        rows = [
            r for r in rows if r["column"].removeprefix("has:").startswith(prefixes)
        ]
    print(markdown(rows, *labels))


if __name__ == "__main__":
    main()
