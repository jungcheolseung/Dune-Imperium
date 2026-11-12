"""Expert iteration from the command line.

    uv run python -m dune_imperium.cli.expert collect --teacher P \\
        --start-seed S --games N --workers W --out DIR

``collect`` labels greedy self-play games with the teacher's search and
writes one ``g<seed>.npz`` per game (``training.expert``); it prints one
JSON summary line and exits 2 when more than 5% of the games failed. The
ruleset is chosen with ``--choam --promo-cards --bloodlines --tech-module
--immortality --go-to-11 --epic --arrakeen-scouts --leader-draft``: with none
of them the first collection's set (CHOAM, promos, Bloodlines, Tech Module,
Immortality) is played, with any the given ones exactly. ``--opponent KIND``
seats that agent kind (say ``app_ai``) at two seats of a ``--mixed-share``
of the games; only the teacher's seats label. The search shape defaults to
the shipped one (``--rollouts``, ``--candidates``). ``train`` distils the
labels into a candidate checkpoint (``training.distill``; the slot embedding
of an ``mlp_slots`` network trains at ``--slot-lr-multiplier`` times the
learning rate) and ``metrics`` runs the offline gate G0 of a student against
its reference on the held-out games.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import numpy as np

FAILURE_LIMIT = 0.05


RULESET_FLAGS = (
    ("choam", "choam"),
    ("promo_cards", "promo_cards"),
    ("bloodlines", "bloodlines"),
    ("tech_module", "tech_module"),
    ("immortality", "immortality"),
    ("go_to_11", "go_to_11"),
    ("epic", "epic_game"),
    ("arrakeen_scouts", "arrakeen_scouts"),
    ("leader_draft", "leader_draft"),
)
# What ``collect`` plays when no ruleset flag is given (the first collection).
DEFAULT_RULESET = frozenset(
    {"choam", "promo_cards", "bloodlines", "tech_module", "immortality"}
)


def _ruleset_options(arguments: argparse.Namespace) -> dict[str, bool]:
    """The ``collect_to_directory`` keywords the ruleset flags select."""

    given = {option for flag, option in RULESET_FLAGS if getattr(arguments, flag)}
    chosen = given or DEFAULT_RULESET
    return {option: option in chosen for _, option in RULESET_FLAGS}


def _collect(arguments: argparse.Namespace) -> int:
    from dune_imperium.agents.registry import is_agent_kind
    from dune_imperium.config import RulesetConfig
    from dune_imperium.training.expert import LabelConfig, collect_to_directory

    options = _ruleset_options(arguments)
    try:
        RulesetConfig(
            choam_module=options["choam"],
            promo_cards=options["promo_cards"],
            bloodlines=options["bloodlines"],
            tech_module=options["tech_module"],
            immortality=options["immortality"],
            go_to_11=options["go_to_11"],
            epic_game=options["epic_game"],
            arrakeen_scouts=options["arrakeen_scouts"],
            leader_draft=options["leader_draft"],
        )
    except ValueError as error:
        raise SystemExit(f"collect: {error}") from error
    if arguments.opponent is not None and not is_agent_kind(arguments.opponent):
        raise SystemExit(f"collect: unknown --opponent kind {arguments.opponent!r}")
    if not 0.0 <= arguments.mixed_share <= 1.0:
        raise SystemExit("collect: --mixed-share must lie in [0, 1]")
    config = LabelConfig(
        label_probability=arguments.label_probability,
        anchor_probability=arguments.anchor_probability,
        rollouts=arguments.rollouts,
        candidates=arguments.candidates,
    )
    summary = collect_to_directory(
        arguments.teacher,
        Path(arguments.out),
        start_seed=arguments.start_seed,
        games=arguments.games,
        workers=arguments.workers,
        config=config,
        opponent=arguments.opponent,
        mixed_share=arguments.mixed_share,
        **options,
    )
    print(json.dumps(summary), flush=True)
    attempted = int(summary["games"]) + int(summary["failures"])  # type: ignore[call-overload]
    if attempted and int(summary["failures"]) > FAILURE_LIMIT * attempted:  # type: ignore[call-overload]
        return 2
    return 0


def _shards(directories: Sequence[str]) -> list[Path]:
    from dune_imperium.training.expert import shard_paths

    paths: list[Path] = []
    for directory in directories:
        paths.extend(shard_paths(Path(directory)))
    return paths


def _load_data(current: Sequence[str], previous: Sequence[str]):  # type: ignore[no-untyped-def]
    from dune_imperium.training.expert import read_shards

    now = _shards(current)
    before = _shards(previous)
    if not now:
        raise SystemExit("no shards found in --data")
    weights = [1.0] * len(now) + [0.5] * len(before)
    return read_shards(now + before, weights=weights), len(now), len(before)


def _config(arguments: argparse.Namespace):  # type: ignore[no-untyped-def]
    from dune_imperium.training.distill import DistillConfig

    return DistillConfig(
        mode=arguments.mode,
        tau=arguments.tau,
        max_epochs=arguments.epochs,
        learning_rate=arguments.learning_rate,
        seed=arguments.seed,
        threads=arguments.threads,
        value_coefficient=arguments.value_coefficient,
        slot_lr_multiplier=arguments.slot_lr_multiplier,
    )


def _train(arguments: argparse.Namespace) -> int:
    import time

    from dune_imperium.training.checkpoint import load_checkpoint
    from dune_imperium.training.distill import (
        HoldoutStats,
        distill,
        label_noise,
        save_candidate,
        stats_summary,
    )

    config = _config(arguments)
    started = time.perf_counter()
    data, current, previous = _load_data(arguments.data, arguments.previous)
    load_seconds = time.perf_counter() - started
    network, _ = load_checkpoint(Path(arguments.init))
    noise = label_noise(data, np.arange(data.rows))

    def log(epoch: int, stats: HoldoutStats, seconds: float) -> None:
        line = {"epoch": epoch, "seconds": round(seconds, 1), **stats_summary(stats)}
        print(json.dumps(line), flush=True)

    report = distill(network, data, config, log=log)
    metadata = {
        "expert_iteration": arguments.tag,
        "parent": str(arguments.init),
        "data": [str(d) for d in arguments.data],
        "previous_data": [str(d) for d in arguments.previous],
        "target": f"{config.mode} tau={config.tau}",
        "best_epoch": report.best_epoch,
    }
    save_candidate(
        Path(arguments.out), network, parent=Path(arguments.init), metadata=metadata
    )
    summary = {
        "out": str(arguments.out),
        "rows": data.rows,
        "current_shards": current,
        "previous_shards": previous,
        "train_rows": report.train_rows,
        "heldout_rows": report.heldout_rows,
        "best_epoch": report.best_epoch,
        "epochs_run": len(report.per_epoch),
        "load_seconds": round(load_seconds, 1),
        "train_seconds": round(report.seconds, 1),
        "epoch_seconds": [round(s, 1) for s in report.epoch_seconds],
        "noise": noise,
        "before": stats_summary(report.before),
        "per_epoch": [stats_summary(s) for s in report.per_epoch],
        "train_before": stats_summary(report.train_before),
        "train_after": stats_summary(report.train_after),
        "slot_lr_multiplier": config.slot_lr_multiplier,
        "config": {
            "mode": config.mode,
            "tau": config.tau,
            "epochs": config.max_epochs,
            "slot_lr_multiplier": config.slot_lr_multiplier,
            "learning_rate": config.learning_rate,
        },
    }
    Path(arguments.report).write_text(json.dumps(summary, indent=1))
    print(
        json.dumps(
            {k: summary[k] for k in ("out", "rows", "best_epoch", "train_seconds")}
        ),
        flush=True,
    )
    return 0


def _metrics(arguments: argparse.Namespace) -> int:
    from dune_imperium.training.checkpoint import load_checkpoint
    from dune_imperium.training.distill import (
        clustered_difference,
        evaluate,
        label_noise,
        stats_summary,
    )

    config = _config(arguments)
    data, _, _ = _load_data(arguments.data, [])
    rows = np.flatnonzero(data.heldout(config.heldout_modulus))
    student, _ = load_checkpoint(Path(arguments.student))
    reference, _ = load_checkpoint(Path(arguments.reference))
    s = evaluate(student, data, rows, config)
    r = evaluate(reference, data, rows, config, check_prior=True)
    agree = clustered_difference(s, r, "agree_target")
    mse = clustered_difference(s, r, "value_error")
    checks = {
        "G0a_agree": agree[0] >= 0.01 and agree[1] > 0.0,
        "G0b_anchor": (s.anchor_kl <= 0.05) and (s.anchor_agree_clear >= 0.97),
        "G0c_value": mse[1] <= 0.005,
        "G0d_finite": all(
            np.isfinite(v)
            for v in (s.label_ce, s.value_mse, s.anchor_kl, s.agree_target)
        ),
        "G0e_pipeline": r.prior_max_abs_diff <= 1.0e-4,
    }
    result = {
        "pass": all(checks.values()),
        "checks": checks,
        "agree_target_diff": agree,
        "value_mse_diff": mse,
        "student": stats_summary(s),
        "reference": stats_summary(r),
        "noise": label_noise(data, rows),
        "heldout_rows": int(rows.size),
        "heldout_games": len(s.per_game.get("game_seed", [])),
    }
    Path(arguments.json).write_text(json.dumps(result, indent=1, default=float))
    print(
        json.dumps(
            {"pass": result["pass"], **checks, "agree_diff": agree, "mse_diff": mse},
            default=float,
        ),
        flush=True,
    )
    return 0


def _add_distill_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--data", nargs="+", required=True, help="shard directories")
    parser.add_argument("--mode", choices=("tilt", "hard", "clearhard"), default="tilt")
    parser.add_argument("--tau", type=float, default=0.005)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=1.0e-4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--value-coefficient", type=float, default=0.5)
    parser.add_argument(
        "--slot-lr-multiplier",
        type=float,
        default=1.0,
        help="learning rate of an mlp_slots network's slot embedding, "
        "relative to the rest",
    )


def build_parser() -> argparse.ArgumentParser:
    from dune_imperium.agents.network_search_agent import (
        DEFAULT_CANDIDATES,
        DEFAULT_ROLLOUTS,
    )

    parser = argparse.ArgumentParser(prog="dune_imperium.cli.expert")
    commands = parser.add_subparsers(dest="command", required=True)
    collect = commands.add_parser("collect", help="label greedy self-play games")
    collect.add_argument("--teacher", required=True, help="checkpoint path")
    collect.add_argument("--start-seed", type=int, required=True)
    collect.add_argument("--games", type=int, required=True)
    collect.add_argument("--workers", type=int, default=1)
    collect.add_argument("--out", required=True, help="directory for g<seed>.npz")
    collect.add_argument("--label-probability", type=float, default=0.5)
    collect.add_argument("--anchor-probability", type=float, default=0.25)
    collect.add_argument("--rollouts", type=int, default=DEFAULT_ROLLOUTS)
    collect.add_argument("--candidates", type=int, default=DEFAULT_CANDIDATES)
    rules = collect.add_argument_group(
        "ruleset",
        "none given: CHOAM, promo cards, Bloodlines, Tech Module, Immortality; "
        "any given: exactly the given ones",
    )
    rules.add_argument("--choam", action="store_true", help="the CHOAM module")
    rules.add_argument("--promo-cards", action="store_true", help="promo cards")
    rules.add_argument("--bloodlines", action="store_true", help="Bloodlines")
    rules.add_argument("--tech-module", action="store_true", help="Tech Module")
    rules.add_argument("--immortality", action="store_true", help="Immortality")
    rules.add_argument("--go-to-11", action="store_true", help="the Go to 11 variant")
    rules.add_argument("--epic", action="store_true", help="Epic Game Mode")
    rules.add_argument(
        "--arrakeen-scouts", action="store_true", help="the Arrakeen Scouts module"
    )
    rules.add_argument(
        "--leader-draft", action="store_true", help="the OQ-007 Leader draft"
    )
    collect.add_argument(
        "--opponent",
        default=None,
        metavar="KIND",
        help="agent kind seated beside the teacher at mixed tables (say app_ai)",
    )
    collect.add_argument(
        "--mixed-share",
        type=float,
        default=0.5,
        help="share of the games that are mixed tables (with --opponent)",
    )
    collect.set_defaults(handler=_collect)
    train = commands.add_parser("train", help="distil labels into a candidate")
    train.add_argument("--init", required=True, help="incumbent checkpoint")
    train.add_argument(
        "--previous", nargs="*", default=[], help="older shard dirs (weight 0.5)"
    )
    train.add_argument("--out", required=True)
    train.add_argument("--report", required=True)
    train.add_argument("--tag", default="")
    _add_distill_arguments(train)
    train.set_defaults(handler=_train)
    metrics = commands.add_parser("metrics", help="offline gate G0")
    metrics.add_argument("--student", required=True)
    metrics.add_argument("--reference", required=True)
    metrics.add_argument("--json", required=True)
    _add_distill_arguments(metrics)
    metrics.set_defaults(handler=_metrics)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    handler = arguments.handler
    result: int = handler(arguments)
    return result


if __name__ == "__main__":
    sys.exit(main())
