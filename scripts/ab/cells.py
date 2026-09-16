"""Run paired A/B cells of the tournament tool, one ruleset axis at a time.

    uv run python scripts/ab/cells.py --name round1 \\
        --variants heuristic_v_space,heuristic_v_spy --control heuristic_uniform_ties \\
        --axes base,choam,bloodlines,immortality,tech_nochoam,tech_choam,stack_cti \\
        --seeds 0,500 --games 500

    uv run python scripts/ab/cells.py --name rollout1 --lineup single \\
        --variants rollout,rollout_v_vp20 --control heuristic --axes base,cbt --games 50

``mirror`` (default) seats ``variant,control,variant,control`` -- a 2:2 mirror
whose seat, Leader and first-player effects cancel by construction; a true null is
exactly 25.0%. ``single`` seats ``variant,control,control,control`` for search
agents that are too slow to mirror. Each start seed in ``--seeds`` is one block
(the first unsuffixed, then ``_b2``, ``_b3`` ...), and every cell writes
``<name>.json/.md/.out`` under ``<out>/<name>/`` with the tree's HEAD and dirty
files on the first log line -- the control must be a registry-pinned name (never
the live ``heuristic``) and the tree must not change while cells run
(docs/lessons.md 2026-09-16). ``scripts/ab/pair_matrix.py`` summarizes a mirror
round, ``scripts/ab/rollout_table.py`` a single-seat one.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYPATH = Path(__file__).resolve().parent / "pypath"

AXES: dict[str, tuple[str, ...]] = {
    "base": ("--ruleset", "base"),
    "choam": ("--ruleset", "choam"),
    "both": ("--ruleset", "both"),
    "bloodlines": ("--ruleset", "base", "--bloodlines"),
    "immortality": ("--ruleset", "base", "--immortality"),
    "tech_nochoam": ("--ruleset", "base", "--bloodlines", "--tech-module"),
    "tech_choam": ("--ruleset", "choam", "--bloodlines", "--tech-module"),
    "cbt": ("--ruleset", "choam", "--bloodlines", "--tech-module"),
    "stack_cti": (
        "--ruleset",
        "choam",
        "--bloodlines",
        "--tech-module",
        "--immortality",
    ),
    "all_promo": (
        "--ruleset",
        "choam",
        "--bloodlines",
        "--tech-module",
        "--immortality",
        "--promo-cards",
    ),
}


def short_name(kind: str) -> str:
    return kind.removeprefix("heuristic_").removeprefix("rollout_")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--name", required=True, help="round name (output subdirectory)"
    )
    parser.add_argument(
        "--variants", required=True, help="comma-separated registry names"
    )
    parser.add_argument("--control", default="heuristic_uniform_ties")
    parser.add_argument("--axes", default="base,choam")
    parser.add_argument("--seeds", default="0", help="comma-separated start seeds")
    parser.add_argument("--games", type=int, default=500, help="seeds per cell")
    parser.add_argument("--lineup", choices=("mirror", "single"), default="mirror")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--out", type=Path, default=ROOT / "ab-runs")
    args = parser.parse_args()

    out = args.out / args.name
    out.mkdir(parents=True, exist_ok=True)
    log = args.out / f"{args.name}.log"
    head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True
    ).stdout.replace("\n", " ")
    env = dict(os.environ)
    env["PYTHONPATH"] = (
        str(PYPATH) if not env.get("PYTHONPATH") else f"{PYPATH}:{env['PYTHONPATH']}"
    )

    def note(line: str) -> None:
        with log.open("a") as fh:
            fh.write(line + "\n")

    note(f"head={head} dirty={dirty.strip()} start={time.strftime('%F %T')}")
    seeds = [int(s) for s in args.seeds.split(",") if s]
    for variant in args.variants.split(","):
        for index, start in enumerate(seeds):
            suffix = "" if index == 0 else f"_b{index + 1}"
            for axis in args.axes.split(","):
                cell = f"{short_name(variant)}_{axis}{suffix}"
                lineup = (
                    f"{variant},{args.control},{variant},{args.control}"
                    if args.lineup == "mirror"
                    else f"{variant},{args.control},{args.control},{args.control}"
                )
                command = [
                    "uv",
                    "run",
                    "dune-imperium-tournament",
                    "--agents",
                    lineup,
                    *AXES[axis],
                    "--games",
                    str(args.games),
                    "--start-seed",
                    str(start),
                    "--rotate-leaders",
                    "--workers",
                    str(args.workers),
                    "--json",
                    str(out / f"{cell}.json"),
                    "--markdown",
                    str(out / f"{cell}.md"),
                ]
                note(f"cell={cell} start={time.strftime('%T')}")
                with (out / f"{cell}.out").open("w") as fh:
                    code = subprocess.run(
                        command, cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT
                    ).returncode
                note(f"exit={code} cell={cell} end={time.strftime('%T')}")
                if code:
                    print(
                        f"cell {cell} exited {code}; see {out / f'{cell}.out'}",
                        file=sys.stderr,
                    )
    note(f"ALL_DONE end={time.strftime('%F %T')}")
    print(f"done: {out} (log {log})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
