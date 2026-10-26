"""Teacher data and students for the entity network's stage P2.

    uv run python scripts/train/distill_entity.py data \\
        --teacher checkpoints/2026-10-09/readapt-v141/Y/iteration_10881.pt \\
        --out checkpoints/2026-10-13/entity-p2/data --iterations 60
    uv run python scripts/train/distill_entity.py train --arch entity \\
        --data checkpoints/2026-10-13/entity-p2/data \\
        --out checkpoints/2026-10-13/entity-p2/entity

``data`` lets the teacher play the training distribution of the v141+
re-adaptations (every UI option and the Leader draft; 16 of 32 games an
iteration against app_ai Hard at two learner seats) and keeps its
decisions with its distribution over the offered actions, the outcomes
and every seat's final Victory Points (``training.teacher``), one shard an
iteration. Games are seeded from ``--seed`` the way a training run is
(``training.loop``), away from the teacher's own run.

With ``--older`` the teacher is a file of an older codec that cannot answer
the current rows by itself (the stage B retrain, 2026-10-21): it plays and
answers through the whole actions each decision stands for
(``training.older_teacher``, ``training.older_distill``).

``--older --student <checkpoint>`` keeps the older teacher as the labeller
but lets a current-codec student (``entity`` or ``mlp``, e.g. a ``train``
output) play the learner seats, sampling its policy at temperature 1 as
the training collector's learner does (student-position distillation,
DAgger: experiment E5 of the stage B retrain). The shards are the same
format, so ``train`` reads a folder mixing them with teacher-played ones;
``data.json`` and each shard's log line say who played the learner seats.

    uv run python scripts/train/distill_entity.py data --older \
        --teacher <older-codec file> --student <student.pt> \
        --out <folder> --iterations 20 --start 100

``train`` fits one student to every shard in the folder and writes its
best held-out epoch as ``student.pt`` with an ``epochs.jsonl`` log
(docs/entity-network-plan.md section 5, P2). With ``--pack`` the shards are
joined on disk in ``<folder>/packed`` (``pack_teacher_data``) instead of in
memory, for data larger than the machine's memory; the student trains the
same.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import torch

from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.config import RulesetConfig
from dune_imperium.training.checkpoint import load_checkpoint, save_checkpoint
from dune_imperium.training.collect import Collector
from dune_imperium.training.entity_network import (
    DEFAULT_ENTITY_WIDTH,
    DEFAULT_SEAT_WIDTH,
    EntityNetwork,
)
from dune_imperium.training.loop import TrainConfig, _iteration_specs
from dune_imperium.training.network import PolicyValueNetwork
from dune_imperium.training.older_distill import (
    load_student,
    older_shard,
    worker_pool,
)
from dune_imperium.training.older_teacher import load_older_network
from dune_imperium.training.teacher import (
    StudentConfig,
    StudentEpoch,
    add_teacher_values,
    build_teacher_data,
    choice_frequency,
    concatenate,
    load_teacher_data,
    pack_teacher_data,
    save_teacher_data,
    split_rows,
    start_from,
    student_choices,
    teacher_choices,
    train_student,
)


def _play_rules(out: Path, seed: int) -> TrainConfig:
    return TrainConfig(
        out_dir=out,
        games_per_iteration=32,
        workers=4,
        choam_module=True,
        promo_cards=True,
        bloodlines=True,
        tech_module=True,
        immortality=True,
        go_to_11=True,
        epic_game=True,
        arrakeen_scouts=True,
        leader_draft=True,
        opponent="app_ai",
        learner_seats=2,
        opponent_games=16,
        seed=seed,
    )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def make_data(arguments: argparse.Namespace) -> int:
    if arguments.student is not None and not arguments.older:
        print("--student needs --older", file=sys.stderr)
        return 2
    out: Path = arguments.out
    out.mkdir(parents=True, exist_ok=True)
    config = _play_rules(out, arguments.seed)
    if arguments.older:
        return _make_older_data(arguments, config)
    teacher, info = load_checkpoint(arguments.teacher, ruleset=config.ruleset)
    teacher.eval()
    torch.set_num_threads(arguments.threads)
    (out / "data.json").write_text(
        json.dumps(
            {
                "teacher": str(arguments.teacher),
                "teacher_sha256_16": _digest(arguments.teacher),
                "teacher_iteration": info.iteration,
                "ruleset": config.ruleset.identifier,
                "seed": arguments.seed,
                "iterations": [arguments.start, arguments.start + arguments.iterations],
                "games_per_iteration": config.games_per_iteration,
            },
            indent=1,
        )
    )
    with Collector(
        config.ruleset,
        workers=arguments.workers,
        max_steps=config.max_steps,
        opponent=config.opponent,
    ) as collector:
        for iteration in range(arguments.start, arguments.start + arguments.iterations):
            shard = out / f"shard_{iteration:04d}.npz"
            if shard.exists():
                continue
            started = time.perf_counter()
            result = collector.collect(
                teacher,
                torch.device("cpu"),
                _iteration_specs(config, iteration),
                policy_seed=config.seed + 1 + iteration * 1_000,
                opponent_seed=config.seed + 2 + iteration * 1_000,
            )
            data = build_teacher_data(
                result,
                teacher,
                ruleset=config.ruleset.identifier,
                first_game=iteration * config.games_per_iteration,
            )
            save_teacher_data(data, shard)
            truncated = sum(episode.truncated for episode in result.episodes)
            print(
                f"{time.strftime('%H:%M:%S')} shard {iteration}: {data.rows} rows, "
                f"{truncated} truncated, {time.perf_counter() - started:.1f}s",
                flush=True,
            )
    return 0


def _make_older_data(arguments: argparse.Namespace, config: TrainConfig) -> int:
    """``make_data`` with an older-codec teacher (module docstring)."""

    out: Path = arguments.out
    older = load_older_network(arguments.teacher)
    torch.set_num_threads(arguments.threads)
    assert config.opponent is not None
    learner: dict[str, object] = {"learner": "teacher"}
    if arguments.student is not None:
        # Loaded here once as well, so a file that cannot answer the game
        # stops the run before any worker starts.
        _, info = load_student(arguments.student, config.ruleset)
        learner = {
            "learner": "student",
            "student": str(arguments.student),
            "student_sha256_16": _digest(arguments.student),
            "student_arch": info.arch,
            "student_codec": info.action_codec_version,
            "student_iteration": info.iteration,
            "student_untrained_rows": (
                0 if info.migration is None else info.migration.actions_new
            ),
        }
        print(
            f"learner seats: student {arguments.student} ({info.arch}, codec "
            f"v{info.action_codec_version}, {learner['student_untrained_rows']} "
            "untrained rows)",
            flush=True,
        )
    record = {
        "teacher": str(arguments.teacher),
        "teacher_sha256_16": _digest(arguments.teacher),
        "teacher_codec": older.codec_version,
        "older": True,
        **learner,
        "ruleset": config.ruleset.identifier,
        "seed": arguments.seed,
        "iterations": [arguments.start, arguments.start + arguments.iterations],
        "games_per_iteration": config.games_per_iteration,
    }
    (out / "data.json").write_text(json.dumps(record, indent=1))
    # A folder may mix teacher-played and student-played shards (E5): every
    # run is kept here, data.json holding only the latest.
    with (out / "data-runs.jsonl").open("a", encoding="utf-8") as runs:
        runs.write(json.dumps(record) + "\n")
    pool = worker_pool(arguments.workers)
    try:
        for iteration in range(arguments.start, arguments.start + arguments.iterations):
            shard = out / f"shard_{iteration:04d}.npz"
            if shard.exists():
                continue
            started = time.perf_counter()
            data = older_shard(
                pool,
                arguments.teacher,
                config.ruleset,
                _iteration_specs(config, iteration),
                first_game=iteration * config.games_per_iteration,
                workers=arguments.workers,
                opponent=config.opponent,
                seed=config.seed + 1 + iteration * 1_000,
                max_steps=config.max_steps,
                student=arguments.student,
            )
            save_teacher_data(data, shard)
            print(
                f"{time.strftime('%H:%M:%S')} shard {iteration}: {data.rows} rows, "
                f"learner seats played by the {learner['learner']}, "
                f"{time.perf_counter() - started:.1f}s",
                flush=True,
            )
    finally:
        if pool is not None:
            pool.shutdown(wait=True)
    return 0


def add_values(arguments: argparse.Namespace) -> int:
    """Rewrite each shard with the teacher's value of every row (format 2)."""

    torch.set_num_threads(arguments.threads)
    teacher: PolicyValueNetwork | None = None
    for path in sorted(arguments.data.glob("shard_*.npz")):
        data = load_teacher_data(path)
        if not np.isnan(data.values).any():
            continue
        if teacher is None:
            ruleset = RulesetConfig.from_identifier(data.ruleset)
            teacher, _ = load_checkpoint(arguments.teacher, ruleset=ruleset)
        # Written beside the shard, then moved over it: an interrupted run
        # leaves every shard whole.
        scratch = path.with_name(f"{path.stem}.partial.npz")
        save_teacher_data(add_teacher_values(data, teacher), scratch)
        scratch.replace(path)
        print(f"{time.strftime('%H:%M:%S')} {path.name}: {data.rows} rows", flush=True)
    return 0


def train(arguments: argparse.Namespace) -> int:
    shards = sorted(arguments.data.glob("shard_*.npz"))
    if not shards:
        print(f"no shards in {arguments.data}", file=sys.stderr)
        return 1
    if arguments.pack:
        data = pack_teacher_data(shards, arguments.data / "packed")
    else:
        data = concatenate([load_teacher_data(path) for path in shards])
    ruleset = RulesetConfig.from_identifier(data.ruleset)
    torch.manual_seed(arguments.seed)
    student: PolicyValueNetwork
    if arguments.arch == "entity":
        student = EntityNetwork(
            ruleset,
            aux_vp=arguments.aux_vp,
            own_actions=arguments.own_actions,
            entity_width=arguments.entity_width,
            seat_width=arguments.seat_width,
        )
    else:
        if arguments.aux_vp or arguments.own_actions:
            print("--aux-vp and --own-actions are entity options", file=sys.stderr)
            return 2
        student = PolicyValueNetwork(data.action_size)
    if arguments.init is not None:
        start_from(student, arguments.init, ruleset)
    config = StudentConfig(
        learning_rate=arguments.learning_rate,
        minibatch_size=arguments.minibatch,
        epochs=arguments.epochs,
        value_coefficient=arguments.value_coefficient,
        value_target=arguments.value_target,
        seed=arguments.seed,
        threads=arguments.threads,
        schedule=arguments.schedule,
        keep=arguments.keep,
    )
    out: Path = arguments.out
    out.mkdir(parents=True, exist_ok=True)
    log = out / "epochs.jsonl"
    log.write_text("")
    (out / "student.json").write_text(
        json.dumps(
            {
                "arch": student.arch_spec(),
                "data": str(arguments.data),
                "init": None if arguments.init is None else str(arguments.init),
                "shards": len(shards),
                "rows": data.rows,
                "config": asdict(config),
            },
            indent=1,
        )
    )
    print(f"{data.rows} rows from {len(shards)} shards; {arguments.arch}", flush=True)

    def report(record: StudentEpoch) -> None:
        line = asdict(record)
        with log.open("a") as handle:
            handle.write(json.dumps(line) + "\n")
        score = record.heldout
        print(
            f"{time.strftime('%H:%M:%S')} epoch {record.epoch}: policy "
            f"{record.policy_loss:.4f} value {record.value_loss:.4f} | held-out ce "
            f"{score.cross_entropy:.4f} (teacher {score.teacher_entropy:.4f}) agree "
            f"{score.agreement:.4f} value {score.value_mse:.4f} "
            f"(teacher's {score.teacher_value_mse:.4f}) "
            f"({record.seconds:.0f}s)",
            flush=True,
        )

    train_student(student, data, config, on_epoch=report)
    save_checkpoint(
        out / "student.pt",
        student,
        ruleset=data.ruleset,
        iteration=0,
        metadata={"distilled_from": str(arguments.data)},
        codec=ActionCodec(ruleset),
    )
    return 0


_RARE = 20
_BINS = ((0, 0), (1, _RARE), (_RARE + 1, 200), (201, None))


def _bootstrap(
    games: np.ndarray, left: np.ndarray, right: np.ndarray, *, draws: int = 2_000
) -> tuple[float, float, float]:
    """Mean of ``left - right`` and its 95% interval, resampling games."""

    numbers, owner = np.unique(games, return_inverse=True)
    counts = np.bincount(owner, minlength=numbers.shape[0]).astype(np.float64)
    gap = np.bincount(owner, weights=left - right, minlength=numbers.shape[0])
    generator = np.random.default_rng(0)
    picks = generator.integers(0, numbers.shape[0], size=(draws, numbers.shape[0]))
    sampled = gap[picks].sum(axis=1) / np.maximum(counts[picks].sum(axis=1), 1.0)
    low, high = np.percentile(sampled, [2.5, 97.5])
    return float(gap.sum() / max(counts.sum(), 1.0)), float(low), float(high)


def _bins(seen: np.ndarray) -> list[tuple[str, np.ndarray]]:
    named = []
    for low, high in _BINS:
        top = high if high is not None else int(seen.max(initial=0))
        named.append(
            (
                f"{low}-{high if high is not None else 'max'}",
                (seen >= low) & (seen <= top),
            )
        )
    return named


def judge(arguments: argparse.Namespace) -> int:
    shards = sorted(arguments.data.glob("shard_*.npz"))
    data = concatenate([load_teacher_data(path) for path in shards])
    train_rows, heldout = split_rows(data, StudentConfig().heldout_modulus)
    heldout = heldout[data.offered()[heldout] > 1]
    teacher = teacher_choices(data, heldout)
    seen = choice_frequency(data, train_rows, teacher)
    games = data.games[heldout]
    print(f"held-out rows offering a choice: {heldout.shape[0]}")
    print(f"held-out games: {np.unique(games).shape[0]}")
    for name, inside in _bins(seen):
        print(f"  teacher's choice seen {name} times in training: {int(inside.sum())}")
    correct: dict[str, np.ndarray] = {}
    for entry in arguments.students:
        name, _, path = entry.partition("=")
        network, _ = load_checkpoint(Path(path))
        correct[name] = student_choices(network, data, heldout) == teacher
    rare = seen <= _RARE
    for name, right in correct.items():
        parts = [f"{name}: agreement {right.mean():.4f}"]
        for label, inside in _bins(seen):
            if inside.any():
                parts.append(f"[{label}] {right[inside].mean():.4f}")
        print("  ".join(parts))
    control = correct[arguments.control].astype(np.float64)
    for name, right in correct.items():
        if name == arguments.control:
            continue
        whole = _bootstrap(games, right.astype(np.float64), control)
        few = _bootstrap(games[rare], right[rare].astype(np.float64), control[rare])
        print(
            f"{name} - {arguments.control}: agreement {whole[0]:+.4f} "
            f"[{whole[1]:+.4f}, {whole[2]:+.4f}]; rare (seen <= {_RARE}, "
            f"{int(rare.sum())} rows) {few[0]:+.4f} [{few[1]:+.4f}, {few[2]:+.4f}]"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    data = commands.add_parser("data", help="keep the teacher's decisions")
    data.add_argument("--teacher", type=Path, required=True)
    data.add_argument("--out", type=Path, required=True)
    data.add_argument("--iterations", type=int, required=True)
    data.add_argument("--start", type=int, default=0)
    data.add_argument("--seed", type=int, default=11)
    data.add_argument("--workers", type=int, default=4)
    data.add_argument("--threads", type=int, default=4)
    data.add_argument(
        "--older",
        action="store_true",
        help="the teacher is an older codec's file (training.older_teacher)",
    )
    data.add_argument(
        "--student",
        type=Path,
        help="with --older: this current-codec checkpoint plays the learner "
        "seats (sampled at temperature 1) and the teacher only labels them",
    )
    data.set_defaults(run=make_data)
    student = commands.add_parser("train", help="fit one student to the shards")
    student.add_argument("--data", type=Path, required=True)
    student.add_argument(
        "--pack",
        action="store_true",
        help="join the shards on disk in <data>/packed and read rows from there",
    )
    student.add_argument("--out", type=Path, required=True)
    student.add_argument("--arch", choices=("entity", "mlp"), required=True)
    student.add_argument("--aux-vp", action="store_true")
    student.add_argument("--own-actions", action="store_true")
    student.add_argument(
        "--value-target", choices=("outcome", "teacher"), default="outcome"
    )
    student.add_argument(
        "--value-coefficient",
        type=float,
        default=StudentConfig().value_coefficient,
        help="the value loss's weight against the policy cross-entropy",
    )
    student.add_argument(
        "--init",
        type=Path,
        help="start from this student checkpoint's weights (same architecture)",
    )
    student.add_argument("--entity-width", type=int, default=DEFAULT_ENTITY_WIDTH)
    student.add_argument("--seat-width", type=int, default=DEFAULT_SEAT_WIDTH)
    student.add_argument("--epochs", type=int, default=3)
    student.add_argument("--learning-rate", type=float, default=3.0e-4)
    student.add_argument(
        "--schedule", choices=("constant", "cosine"), default="constant"
    )
    student.add_argument(
        "--keep",
        choices=("cross_entropy", "teacher_value", "last"),
        default=StudentConfig().keep,
        help="the epoch saved: lowest held-out cross-entropy or teacher-value "
        "error, or the last",
    )
    student.add_argument("--minibatch", type=int, default=512)
    student.add_argument("--seed", type=int, default=0)
    student.add_argument("--threads", type=int, default=4)
    student.set_defaults(run=train)
    values = commands.add_parser("values", help="add the teacher's values to shards")
    values.add_argument("--teacher", type=Path, required=True)
    values.add_argument("--data", type=Path, required=True)
    values.add_argument("--threads", type=int, default=4)
    values.set_defaults(run=add_values)
    verdict = commands.add_parser("judge", help="students against the teacher")
    verdict.add_argument("--data", type=Path, required=True)
    verdict.add_argument("--control", required=True, help="name of the control")
    verdict.add_argument("students", nargs="+", help="name=student.pt")
    verdict.set_defaults(run=judge)
    arguments = parser.parse_args(argv)
    result: int = arguments.run(arguments)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
