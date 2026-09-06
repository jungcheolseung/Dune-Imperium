"""CLI for the M10 training loop (requires the ``train`` extra)."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from dune_imperium.training.learner import LearnerConfig
from dune_imperium.training.loop import IterationRecord, TrainConfig, train
from dune_imperium.training.network import DEFAULT_HIDDEN


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dune-imperium-train",
        description=(
            "Train a masked policy/value network by self-play: collect seeded "
            "games, update, checkpoint, and periodically evaluate against a "
            "baseline with the tournament tool."
        ),
    )
    parser.add_argument("--out", type=Path, required=True, help="output directory")
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--games-per-iteration", type=int, default=32)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--device",
        default="cpu",
        help="cpu, mps, cuda, or auto (default: cpu)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="worker processes for self-play collection (default: 1)",
    )
    parser.add_argument("--choam", action="store_true", help="use the CHOAM ruleset")
    parser.add_argument(
        "--hidden",
        default=",".join(str(width) for width in DEFAULT_HIDDEN),
        help="comma-separated hidden widths (default: 512,512)",
    )
    parser.add_argument("--learning-rate", type=float, default=3.0e-4)
    parser.add_argument("--entropy", type=float, default=0.01)
    parser.add_argument("--value-coefficient", type=float, default=0.5)
    parser.add_argument("--minibatch", type=int, default=4096)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument(
        "--opponent",
        default=None,
        help=(
            "baseline kind for the other three seats during collection "
            "(default: pure self-play)"
        ),
    )
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument(
        "--step-penalty",
        type=float,
        default=0.0005,
        help="learning-side cost per own decision (default: 0.0005; 0 disables)",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=4_000,
        help="decisions per training game before truncation (default: 4000)",
    )
    parser.add_argument(
        "--eval-every",
        type=int,
        default=0,
        help="evaluate the latest checkpoint every N iterations (0: never)",
    )
    parser.add_argument("--eval-games", type=int, default=10)
    parser.add_argument("--eval-opponent", default="heuristic")
    parser.add_argument(
        "--resume", type=Path, default=None, help="checkpoint to continue from"
    )
    return parser


def _print(record: IterationRecord) -> None:
    evaluation = (
        f" eval win {record.eval_win_rate:.1%} rank {record.eval_mean_rank:.2f}"
        if record.eval_win_rate is not None and record.eval_mean_rank is not None
        else ""
    )
    print(
        f"iter {record.iteration}: {record.games} games, {record.learner_steps} "
        f"learner steps, win {record.learner_win_rate:.1%}, reward "
        f"{record.learner_mean_reward:+.3f}, rounds {record.mean_rounds:.1f}, "
        f"policy {record.update.policy_loss:+.4f} value {record.update.value_loss:.4f} "
        f"entropy {record.update.entropy:.3f} "
        f"ev {record.update.explained_variance:+.2f}, "
        f"{record.decisions_per_second:,.0f} dec/s, update {record.update_seconds:.1f}s"
        f"{evaluation}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    try:
        hidden = tuple(int(width) for width in arguments.hidden.split(",") if width)
        config = TrainConfig(
            out_dir=arguments.out,
            iterations=arguments.iterations,
            games_per_iteration=arguments.games_per_iteration,
            seed=arguments.seed,
            device=arguments.device,
            workers=arguments.workers,
            choam_module=arguments.choam,
            hidden=hidden,
            learner=LearnerConfig(
                learning_rate=arguments.learning_rate,
                value_coefficient=arguments.value_coefficient,
                entropy_coefficient=arguments.entropy,
                minibatch_size=arguments.minibatch,
                epochs=arguments.epochs,
            ),
            opponent=arguments.opponent,
            temperature=arguments.temperature,
            step_penalty=arguments.step_penalty,
            max_steps=arguments.max_steps,
            eval_every=arguments.eval_every,
            eval_games=arguments.eval_games,
            eval_opponent=arguments.eval_opponent,
            resume=arguments.resume,
        )
    except ValueError as error:
        parser.error(str(error))
    result = train(config, progress=_print)
    print(f"latest checkpoint: {result.latest_checkpoint}; log: {result.log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
