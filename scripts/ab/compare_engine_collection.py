"""Alternate two source trees through the real self-play Collector.

Each cell loads the same checkpoint, configuration and seeds in a fresh
process. Only Collector.collect is timed; array and episode fingerprints
must match before reporting a comparison. Parallel cells include pool startup
and transport, so their timings cover cold collection rather than a warmed
training pool. Redirect JSONL output into the repository's ignored tmp/.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def worker(args: argparse.Namespace) -> dict[str, object]:
    import numpy as np
    import torch

    from dune_imperium.config import RulesetConfig
    from dune_imperium.training.checkpoint import load_checkpoint
    from dune_imperium.training.collect import LEARNER, Collector
    from dune_imperium.training.selfplay import SelfPlaySpec

    torch.set_num_threads(1)
    config = RulesetConfig(
        choam_module=args.ruleset != "base",
        promo_cards=args.ruleset == "full",
        bloodlines=args.ruleset == "full",
        tech_module=args.ruleset == "full",
        immortality=args.ruleset == "full",
        arrakeen_scouts=args.ruleset == "full",
    )
    network, info = load_checkpoint(args.checkpoint, ruleset=config)
    iteration = info.iteration
    del info
    specs = []
    for game in range(args.games):
        lineup = (LEARNER,) * 4
        if args.mode == "app" or args.mode == "mixed" and game % 2:
            lineup = tuple(
                LEARNER if seat == game % 4 else "app_ai" for seat in range(4)
            )
        specs.append(SelfPlaySpec(args.seed + game, lineup))
    with Collector(
        config,
        workers=args.workers,
        max_steps=4000,
        opponent=None if args.mode == "selfplay" else "app_ai",
    ) as collector:
        cpu_started = time.process_time()
        result = collector.collect(
            network,
            torch.device("cpu"),
            specs,
            policy_seed=731,
            opponent_seed=500_000,
        )
        coordinator_cpu = time.process_time() - cpu_started
    digest = hashlib.sha256()
    for name in (
        "observations", "legal_indices", "legal_offsets", "actions", "seats",
        "returns", "episode_ids",
    ):
        array = np.asarray(getattr(result.batch, name))
        digest.update(repr((name, array.shape, str(array.dtype))).encode())
        digest.update(array.tobytes())
    summaries = [
        (e.game_seed, e.lineup, e.rewards, e.ranks, e.victory_points, e.rounds,
         e.decisions, e.truncated)
        for e in result.episodes
    ]
    digest.update(repr(summaries).encode())
    return {
        "ruleset": config.identifier,
        "checkpoint_iteration": iteration,
        "mode": args.mode,
        "workers": args.workers,
        "games": args.games,
        "decisions": result.decisions,
        "learner_rows": result.batch.actions.shape[0],
        "truncated": sum(e.truncated for e in result.episodes),
        "wall_seconds": result.duration_seconds,
        # With workers > 1 this excludes the workers' CPU; never interpret
        # it as total engine core-seconds or a wall-time contribution.
        "coordinator_cpu_seconds": coordinator_cpu,
        "fingerprint": digest.hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-root", type=Path)
    parser.add_argument("--candidate-root", type=Path, default=Path.cwd())
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--ruleset", choices=("base", "choam", "full"), default="full")
    parser.add_argument("--mode", choices=("selfplay", "app", "mixed"), default="mixed")
    parser.add_argument("--games", type=int, default=8)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=2_000_300)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if min(args.games, args.workers, args.repeats) < 1:
        parser.error("games, workers and repeats must be positive")
    if args.worker:
        print(json.dumps(worker(args)))
        return
    if args.baseline_root is None:
        parser.error("--baseline-root is required")
    common = [
        sys.executable, str(Path(__file__).resolve()), "--worker",
        "--checkpoint", str(args.checkpoint.resolve()),
        "--ruleset", args.ruleset, "--mode", args.mode,
        "--games", str(args.games), "--workers", str(args.workers),
        "--seed", str(args.seed),
    ]
    roots = {"baseline": args.baseline_root, "candidate": args.candidate_root}
    expected = None
    for repeat in range(args.repeats):
        order = ("baseline", "candidate") if repeat % 2 == 0 else (
            "candidate", "baseline"
        )
        for label in order:
            root = roots[label].resolve()
            env = {**os.environ, "PYTHONPATH": str(root / "src")}
            completed = subprocess.run(
                common, env=env, capture_output=True, text=True
            )
            if completed.returncode:
                raise RuntimeError(completed.stderr or completed.stdout)
            row = json.loads(completed.stdout)
            signature = (row["fingerprint"], row["decisions"], row["truncated"])
            if expected is None:
                expected = signature
            if signature != expected:
                raise RuntimeError(f"{label}: collection changed, comparison rejected")
            row.update(source=label, repeat=repeat)
            print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
