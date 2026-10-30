"""Stage 1 of the self-play plan: collect round starts, fit the value branch.

docs/entity-self-play-plan.md sections 3.2, 3.4 and 4.1;
``training.round_values`` holds the method.

    collect  greedy games at the plan's mixed tables (every Uprising option
             and the Leader draft), one shard per block of games; a block
             already written is skipped, so a stopped collection resumes
    fit      one arm (lambda, reward step): a value branch on the starting
             file, fitted to the shards; writes value.pt and fit.json

Example (the pilot's first arm)::

    uv run python scripts/train/round_values.py collect \\
        --learner checkpoints/2026-10-23/e8-quad/quad/student/student.pt \\
        --x checkpoints/play/readapt-v147-4400.pt --out <run>/rounds \\
        --games 5000 --start-seed 8600000 --workers 10
    uv run python scripts/train/round_values.py fit --init <student.pt> \\
        --data <run>/rounds --out <run>/l080-s6 --lam 0.8 --step 0.1666667
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

import numpy as np
import torch

from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.config import RulesetConfig
from dune_imperium.training.checkpoint import load_checkpoint, save_checkpoint
from dune_imperium.training.entity_network import EntityNetwork, with_value_branch
from dune_imperium.training.round_values import (
    CollectSpec,
    FitConfig,
    collect_rounds,
    fit_round_values,
    leader_values,
    load_round_shards,
    save_rounds,
)
from dune_imperium.training.table_mix import (
    DEFAULT_SHARES,
    PastSelves,
    TableMix,
    parse_shares,
)

# The play server's game: every Uprising option and the Leader draft.
PLAY_CONFIG = RulesetConfig(
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


def _single_thread() -> None:
    torch.set_num_threads(1)


def _block(spec: CollectSpec, games: list[tuple[int, int]], path: Path) -> int:
    data = collect_rounds(spec, games)
    save_rounds(data, path)
    return data.rows


def collect(arguments: argparse.Namespace) -> int:
    shares = parse_shares(arguments.mix) if arguments.mix else dict(DEFAULT_SHARES)
    past: tuple[str, ...] = ()
    if arguments.past_dir is not None:
        past = tuple(
            f"checkpoint:{path}" for path in PastSelves(arguments.past_dir).paths()
        )
    spec = CollectSpec(
        config=PLAY_CONFIG,
        learner=f"checkpoint:{arguments.learner}",
        x=f"older:{arguments.x}",
        app=arguments.app,
        past=past,
        mix=TableMix.from_shares(shares),
    )
    out: Path = arguments.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "collect.json").write_text(
        json.dumps(
            {
                "learner": spec.learner,
                "x": spec.x,
                "app": spec.app,
                "past": list(spec.past),
                "shares": shares,
                "cycle": list(spec.mix.cycle),
                "ruleset": PLAY_CONFIG.identifier,
                "games": arguments.games,
                "start_seed": arguments.start_seed,
                "block": arguments.block,
            },
            indent=1,
        )
        + "\n"
    )
    blocks = []
    for first in range(0, arguments.games, arguments.block):
        indices = range(first, min(first + arguments.block, arguments.games))
        path = out / f"rounds-{arguments.start_seed + first:09d}.npz"
        if path.exists():
            continue
        games = [(index, arguments.start_seed + index) for index in indices]
        blocks.append((games, path))
    started = time.perf_counter()
    rows = 0
    with ProcessPoolExecutor(
        max_workers=arguments.workers,
        mp_context=get_context("spawn"),
        initializer=_single_thread,
    ) as pool:
        futures = [pool.submit(_block, spec, games, path) for games, path in blocks]
        for done, future in enumerate(futures, start=1):
            rows += future.result()
            print(
                json.dumps(
                    {
                        "blocks": f"{done}/{len(futures)}",
                        "rows": rows,
                        "seconds": round(time.perf_counter() - started, 1),
                    }
                ),
                flush=True,
            )
    return 0


def fit(arguments: argparse.Namespace) -> int:
    torch.set_num_threads(arguments.threads)
    start, _ = load_checkpoint(arguments.init)
    if not isinstance(start, EntityNetwork):
        raise SystemExit("the fit starts from an entity file")
    network = with_value_branch(
        start, aux_vp=True, aux_rank=True, reward_step=arguments.step
    )
    data = load_round_shards(arguments.data)
    config = FitConfig(
        lam=arguments.lam,
        step=arguments.step,
        fits=arguments.fits,
        epochs=arguments.epochs,
        learning_rate=arguments.learning_rate,
        minibatch=arguments.minibatch,
        vp_weight=arguments.vp_weight,
        rank_weight=arguments.rank_weight,
        seed=arguments.seed,
    )
    out: Path = arguments.out
    out.mkdir(parents=True, exist_ok=True)
    log = (out / "epochs.jsonl").open("w")

    def report(record: dict[str, object]) -> None:
        log.write(json.dumps(record) + "\n")
        log.flush()
        heldout = record["heldout"]
        assert isinstance(heldout, dict)
        print(
            f"fit {record['fit']} epoch {record['epoch']}: train "
            f"{record['train_value_mse']:.4f}, held-out target "
            f"{heldout['target_mse']:.4f}, outcome {heldout['outcome_mse']:.4f} "
            f"(constant {heldout['constant_mse']:.4f}), {record['seconds']}s",
            flush=True,
        )

    fitted, records = fit_round_values(network, data, config, report=report)
    log.close()
    heldout_rows = np.flatnonzero(data.heldout(config.heldout_modulus))
    settings = {
        "lam": config.lam,
        "step": config.step,
        "fits": config.fits,
        "epochs": config.epochs,
        "learning_rate": config.learning_rate,
        "minibatch": config.minibatch,
        "heldout_modulus": config.heldout_modulus,
        "vp_weight": config.vp_weight,
        "rank_weight": config.rank_weight,
        "seed": config.seed,
    }
    summary = {
        "init": str(arguments.init),
        "data": str(arguments.data),
        "rows": data.rows,
        "games": int(np.unique(data.games).size),
        "heldout_rows": int(heldout_rows.size),
        "config": settings,
        "kept": [
            min(
                (record for record in records if record["fit"] == number),
                key=lambda record: record["heldout"]["target_mse"],
            )
            for number in range(1, config.fits + 1)
        ],
        "leaders_start": leader_values(network, data, heldout_rows, config),
        "leaders_fitted": leader_values(fitted, data, heldout_rows, config),
    }
    (out / "fit.json").write_text(json.dumps(summary, indent=1) + "\n")
    save_checkpoint(
        out / "value.pt",
        fitted,
        ruleset=fitted.config.identifier,
        iteration=config.fits,
        metadata={"stage": "self-play stage 1", **settings},
        codec=ActionCodec(fitted.config),
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    gather = commands.add_parser("collect", help="greedy games' round starts")
    gather.add_argument("--learner", type=Path, required=True)
    gather.add_argument("--x", type=Path, required=True)
    gather.add_argument("--app", default="app_ai")
    gather.add_argument("--past-dir", type=Path)
    gather.add_argument("--mix", help="shares, e.g. self=5,past=3,x=1,app=1")
    gather.add_argument("--out", type=Path, required=True)
    gather.add_argument("--games", type=int, required=True)
    gather.add_argument("--start-seed", type=int, required=True)
    gather.add_argument("--block", type=int, default=50)
    gather.add_argument("--workers", type=int, default=4)
    branch = commands.add_parser("fit", help="fit a value branch to the shards")
    branch.add_argument("--init", type=Path, required=True)
    branch.add_argument("--data", type=Path, required=True)
    branch.add_argument("--out", type=Path, required=True)
    branch.add_argument("--lam", type=float, required=True)
    branch.add_argument("--step", type=float, required=True)
    branch.add_argument("--fits", type=int, default=3)
    branch.add_argument("--epochs", type=int, default=6)
    branch.add_argument("--learning-rate", type=float, default=1.0e-4)
    branch.add_argument("--minibatch", type=int, default=512)
    branch.add_argument("--vp-weight", type=float, default=1.0)
    branch.add_argument("--rank-weight", type=float, default=0.1)
    branch.add_argument("--seed", type=int, default=0)
    branch.add_argument("--threads", type=int, default=4)
    arguments = parser.parse_args(argv)
    if arguments.command == "collect":
        return collect(arguments)
    return fit(arguments)


if __name__ == "__main__":
    sys.exit(main())
