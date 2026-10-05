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
        "--promo-cards",
        action="store_true",
        help=(
            "shuffle the promo cards into their decks: the three Uprising "
            "promos (Arrakis Revolt, The Beast's Spoils, Pivotal Gambit), "
            "Ruthless Leadership with --bloodlines, and Piter, Genius Advisor "
            "into the Tleilaxu deck with --immortality"
        ),
    )
    parser.add_argument(
        "--bloodlines",
        action="store_true",
        help="play with the Bloodlines expansion (docs/rules/bloodlines.md)",
    )
    parser.add_argument(
        "--tech-module",
        action="store_true",
        help="add the Bloodlines Tech Module (requires --bloodlines)",
    )
    parser.add_argument(
        "--immortality",
        action="store_true",
        help="play with the Immortality expansion (docs/rules/immortality.md)",
    )
    parser.add_argument(
        "--go-to-11",
        action="store_true",
        help="start every Score marker at 0 (requires --immortality)",
    )
    parser.add_argument(
        "--epic",
        action="store_true",
        help="play Rise of Ix's Epic Game Mode (docs/rules/epic-game-mode.md)",
    )
    parser.add_argument(
        "--arrakeen-scouts",
        action="store_true",
        help="play with the Arrakeen Scouts module (docs/rules/arrakeen-scouts.md)",
    )
    parser.add_argument(
        "--leader-draft",
        action="store_true",
        help=(
            "use the OQ-007 six-Leader draft setup, so the learner also learns "
            "the picks (cannot be combined with --rotate-leaders)"
        ),
    )
    parser.add_argument(
        "--rotate-leaders",
        action="store_true",
        help=(
            "deal each training game a random four-Leader roster instead of "
            "the engine's fixed four"
        ),
    )
    parser.add_argument(
        "--hidden",
        default=",".join(str(width) for width in DEFAULT_HIDDEN),
        help="comma-separated hidden widths (default: 512,512)",
    )
    parser.add_argument("--learning-rate", type=float, default=3.0e-4)
    parser.add_argument("--entropy", type=float, default=0.01)
    parser.add_argument("--value-coefficient", type=float, default=0.5)
    parser.add_argument("--minibatch", type=int, default=4096)
    parser.add_argument(
        "--epochs",
        type=int,
        default=1,
        help="passes over each collected batch (default: 1); use several only "
        "with --clip",
    )
    parser.add_argument(
        "--clip",
        type=float,
        default=None,
        help="PPO clip range, e.g. 0.2 (default: off, plain REINFORCE)",
    )
    parser.add_argument(
        "--opponent",
        default=None,
        help=(
            "baseline kind for the other three seats during collection "
            "(default: pure self-play)"
        ),
    )
    parser.add_argument(
        "--learner-seats",
        type=int,
        default=1,
        help=(
            "seats the learner holds at each table when --opponent is set "
            "(1-3, default 1); the rest are the opponent"
        ),
    )
    parser.add_argument(
        "--opponent-games",
        type=int,
        default=None,
        help=(
            "games per iteration seated against --opponent, spread evenly; "
            "the rest are pure self-play (default: every game)"
        ),
    )
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument(
        "--rank-rewards",
        action="store_true",
        help=(
            "pay the finishing order (1, 1/3, -1/3, -1 at four players) "
            "instead of winner-take-all (+1 / -1/3) during collection; the "
            "environment and the tournament's win criterion are unchanged"
        ),
    )
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
    parser.add_argument(
        "--eval-games",
        type=int,
        default=10,
        help="evaluation seeds; each plays the four seat rotations (default: 10)",
    )
    parser.add_argument("--eval-opponent", default="heuristic")
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=1,
        help="keep a numbered checkpoint every N iterations (default: 1); "
        "latest.pt is always rewritten",
    )
    parser.add_argument(
        "--resume", type=Path, default=None, help="checkpoint to continue from"
    )
    parser.add_argument(
        "--retarget",
        action="store_true",
        help=(
            "let --resume load a checkpoint trained on another ruleset: its "
            "policy head moves onto this run's catalog by template identity"
        ),
    )
    return parser


def _print(record: IterationRecord) -> None:
    evaluation = (
        f" eval win {record.eval_win_rate:.1%} rank {record.eval_mean_rank:.2f}"
        if record.eval_win_rate is not None and record.eval_mean_rank is not None
        else ""
    )
    if record.opponent_win_rate is not None:
        evaluation = f" vs opponent {record.opponent_win_rate:.1%}" + evaluation
    if record.eval_failures:
        evaluation += f" ({record.eval_failures} eval matches FAILED)"
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
            promo_cards=arguments.promo_cards,
            bloodlines=arguments.bloodlines,
            tech_module=arguments.tech_module,
            immortality=arguments.immortality,
            go_to_11=arguments.go_to_11,
            epic_game=arguments.epic,
            arrakeen_scouts=arguments.arrakeen_scouts,
            leader_draft=arguments.leader_draft,
            rotate_leaders=arguments.rotate_leaders,
            hidden=hidden,
            learner=LearnerConfig(
                learning_rate=arguments.learning_rate,
                value_coefficient=arguments.value_coefficient,
                entropy_coefficient=arguments.entropy,
                minibatch_size=arguments.minibatch,
                epochs=arguments.epochs,
                clip_ratio=arguments.clip,
            ),
            opponent=arguments.opponent,
            learner_seats=arguments.learner_seats,
            opponent_games=arguments.opponent_games,
            temperature=arguments.temperature,
            rank_rewards=arguments.rank_rewards,
            step_penalty=arguments.step_penalty,
            max_steps=arguments.max_steps,
            eval_every=arguments.eval_every,
            eval_games=arguments.eval_games,
            eval_opponent=arguments.eval_opponent,
            checkpoint_every=arguments.checkpoint_every,
            resume=arguments.resume,
            retarget=arguments.retarget,
        )
    except ValueError as error:
        parser.error(str(error))
    result = train(config, progress=_print)
    print(f"latest checkpoint: {result.latest_checkpoint}; log: {result.log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
