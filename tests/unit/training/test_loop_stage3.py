"""The training loop's stage-3 options (docs/entity-self-play-plan.md 4.3).

The user's mix with past copies and dealt Leaders, the graded reward, a fixed
critic, round-level targets and a frozen value, end to end on a tiny run.
"""

import json
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.adapters.action_codec import ActionCodec  # noqa: E402
from dune_imperium.training import loop as loop_module  # noqa: E402
from dune_imperium.training.checkpoint import (  # noqa: E402
    load_checkpoint,
    save_checkpoint,
)
from dune_imperium.training.collect import (  # noqa: E402
    LEARNER,
    CollectionResult,
    RoundStarts,
)
from dune_imperium.training.learner import LearnerConfig  # noqa: E402
from dune_imperium.training.loop import (  # noqa: E402
    TrainConfig,
    round_start_baselines,
    round_targets,
    train,
)
from dune_imperium.training.network import PolicyValueNetwork  # noqa: E402
from dune_imperium.training.selfplay import Episode, TrainingBatch  # noqa: E402

UNUSED = Path("unused")


def _mixed(**kwargs: object) -> TrainConfig:
    options: dict[str, object] = {
        "out_dir": UNUSED,
        "games_per_iteration": 10,
        "mix": "self=5,past=3,x=1,app=1",
        "x_opponent": "heuristic",
        "leader_draft": True,
    }
    options.update(kwargs)
    return TrainConfig(**options)  # type: ignore[arg-type]


def test_mixed_iterations_follow_the_user_s_shares() -> None:
    config = _mixed()
    specs = loop_module._iteration_specs(config, 0)
    # No past copies yet: their games seat the learner four times.
    kinds = [
        "self"
        if set(spec.lineup) == {LEARNER}
        else (set(spec.lineup) - {LEARNER}).pop()
        for spec in specs
    ]
    assert kinds.count("self") == 8
    assert kinds.count("heuristic") == 1 and kinds.count("app_ai") == 1
    past = ("checkpoint:a.pt", "checkpoint:b.pt")
    with_past = loop_module._iteration_specs(config, 1, past)
    seated = {name for spec in with_past for name in spec.lineup}
    assert seated & set(past)
    assert all(spec.leader_ids is None for spec in with_past)
    # The cycle carries on across iterations: the same seeds by game index.
    assert [spec.game_seed for spec in with_past] == [
        spec.game_seed + 10 for spec in specs
    ]


def test_a_dealt_share_deals_four_leaders() -> None:
    config = _mixed(games_per_iteration=40, dealt_share=0.5)
    specs = loop_module._iteration_specs(config, 0)
    dealt = [spec for spec in specs if spec.leader_ids is not None]
    assert 8 <= len(dealt) <= 32
    assert all(len(set(spec.leader_ids or ())) == 4 for spec in dealt)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"opponent": "random"},
        {"x_opponent": None},
        {"mix": None, "dealt_share": 0.2},
        {"reward_step": 0.1, "rank_rewards": True},
        {"round_targets": True},
        {"round_baseline": True},
        {"lam": 1.5},
        {"past_every": 0},
    ],
)
def test_invalid_stage_three_mixes_are_refused(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _mixed(**kwargs)
    with pytest.raises(ValueError, match="not both"):
        TrainConfig(out_dir=UNUSED, init=Path("a.pt"), resume=Path("b.pt"))


def _result(
    rounds: list[int],
    start_rounds: list[int],
    reward: float,
    after_starts: list[int] | None = None,
) -> CollectionResult:
    """One learner seat (seat 0) of one episode with these step and start rounds."""

    steps = len(rounds)
    episode = Episode(
        game_seed=1,
        ruleset="r",
        lineup=(LEARNER, "x", "x", "x"),
        rewards=(reward, 0.0, 0.0, 0.0),
        ranks=(1, 2, 3, 4),
        victory_points=(0, 0, 0, 0),
        rounds=max(start_rounds),
        decisions=steps,
        truncated=False,
        steps=(),
    )
    batch = TrainingBatch(
        observations=np.zeros((steps, 1), dtype=np.int32),
        legal_indices=np.zeros(steps, dtype=np.int32),
        legal_offsets=np.arange(steps + 1, dtype=np.int64),
        action_size=1,
        actions=np.zeros(steps, dtype=np.int64),
        seats=np.zeros(steps, dtype=np.int8),
        returns=np.zeros(steps, dtype=np.float32),
        episode_ids=np.zeros(steps, dtype=np.int32),
        rounds=np.asarray(rounds, dtype=np.int16),
        after_starts=None
        if after_starts is None
        else np.asarray(after_starts, dtype=np.int16),
    )
    starts = RoundStarts(
        observations=np.zeros((len(start_rounds), 1), dtype=np.int32),
        episode_ids=np.zeros(len(start_rounds), dtype=np.int32),
        seats=np.zeros(len(start_rounds), dtype=np.int8),
        rounds=np.asarray(start_rounds, dtype=np.int16),
    )
    return CollectionResult(
        episodes=(episode,),
        batch=batch,
        decisions=steps,
        duration_seconds=0.0,
        round_starts=starts,
    )


def test_round_targets_by_hand() -> None:
    # Starts of rounds 1, 2, 3 (stored out of order) with values 0.1, 0.4, 0.6;
    # the seat's reward 1.0; steps in the draft (round 0) and rounds 1, 2, 3.
    result = _result([0, 1, 2, 3], start_rounds=[3, 1, 2], reward=1.0)
    values = np.asarray([0.6, 0.1, 0.4], dtype=np.float32)
    targets = round_targets(result, values, 0.5)
    # G_3 = 1; G_2 = 0.5 * 0.6 + 0.5 * 1 = 0.8; G_1 = 0.5 * 0.4 + 0.5 * 0.8 = 0.6.
    # Round 0 aims at start 1: 0.5 * 0.1 + 0.5 * 0.6; round 1 at start 2:
    # 0.5 * 0.4 + 0.5 * 0.8; round 2 at start 3: 0.5 * 0.6 + 0.5 * 1; round 3
    # ends the game: the reward.
    assert targets.tolist() == pytest.approx([0.35, 0.6, 0.8, 1.0])
    assert round_targets(result, values, 1.0).tolist() == pytest.approx([1.0] * 4)
    assert round_targets(result, values, 0.0).tolist() == pytest.approx(
        [0.1, 0.4, 0.6, 1.0]
    )


def test_round_start_baselines_by_hand() -> None:
    # Starts of rounds 1, 2, 3 (stored out of order) with values 0.1, 0.4, 0.6;
    # steps in the draft, round 1, a Round Start phase of round 2 (before
    # start 2) and rounds 2 and 3.
    result = _result(
        [0, 1, 2, 2, 3],
        start_rounds=[3, 1, 2],
        reward=1.0,
        after_starts=[0, 1, 1, 2, 3],
    )
    values = np.asarray([0.6, 0.1, 0.4], dtype=np.float32)
    assert round_start_baselines(result, values).tolist() == pytest.approx(
        [0.0, 0.1, 0.1, 0.4, 0.6]
    )
    with pytest.raises(ValueError, match="round-start baselines"):
        round_start_baselines(_result([0, 1], start_rounds=[1], reward=1.0), values[:1])


@pytest.mark.parametrize("round_baseline", [False, True])
def test_a_mixed_run_with_a_fixed_critic(tmp_path: Path, round_baseline: bool) -> None:
    config = RulesetConfig(leader_draft=True)
    torch.manual_seed(0)
    start = PolicyValueNetwork(ActionCodec(config).size, hidden=(16,))
    start_path = tmp_path / "start.pt"
    save_checkpoint(
        start_path,
        start,
        ruleset=config.identifier,
        iteration=7,
        codec=ActionCodec(config),
    )
    result = train(
        TrainConfig(
            out_dir=tmp_path / "run",
            iterations=2,
            games_per_iteration=3,
            seed=1,
            hidden=(16,),
            leader_draft=True,
            learner=LearnerConfig(minibatch_size=512, value_coefficient=0.0),
            init=start_path,
            mix="self=1,past=1,x=1",
            x_opponent="heuristic",
            dealt_share=0.5,
            reward_step=1 / 6,
            critic=start_path,
            round_targets=True,
            round_baseline=round_baseline,
            freeze_value=True,
            past_every=1,
            past_keep=1,
        )
    )
    assert len(result.records) == 2
    lines = [json.loads(line) for line in result.log_path.read_text().splitlines()]
    assert [line["iteration"] for line in lines] == [1, 2]
    assert all(line["table_win_rates"] for line in lines)
    # One past copy kept (past_every 1, past_keep 1); the second iteration
    # could seat it.
    copies = sorted((tmp_path / "run" / "past").iterdir())
    assert [path.name for path in copies] == ["past-000002.pt"]
    trained, info = load_checkpoint(result.latest_checkpoint)
    assert info.iteration == 2
    # The value head was frozen; the policy moved.
    assert torch.equal(trained.value_head.weight, start.value_head.weight)
    assert not torch.equal(trained.policy_head.weight, start.policy_head.weight)


def test_the_cli_forwards_the_stage_three_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dune_imperium.cli.train import main as train_main

    seen: list[TrainConfig] = []

    def capture(config: TrainConfig, **_: object) -> object:
        seen.append(config)
        raise SystemExit(0)

    monkeypatch.setattr("dune_imperium.cli.train.train", capture)
    with pytest.raises(SystemExit):
        train_main(
            [
                "--out",
                str(tmp_path),
                "--leader-draft",
                "--init",
                str(tmp_path / "s.pt"),
                "--mix",
                "self=5,past=3,x=1,app=1",
                "--x-opponent",
                "heuristic",
                "--past-every",
                "50",
                "--past-keep",
                "4",
                "--dealt-share",
                "0.2",
                "--reward-step",
                "0.1666667",
                "--critic",
                str(tmp_path / "s.pt"),
                "--round-targets",
                "--lam",
                "0.8",
                "--freeze-value",
                "--round-baseline",
            ]
        )
    (config,) = seen
    assert config.init == config.critic == tmp_path / "s.pt"
    assert config.mix == "self=5,past=3,x=1,app=1" and config.x_opponent == "heuristic"
    assert (config.past_every, config.past_keep, config.dealt_share) == (50, 4, 0.2)
    assert config.reward_step == pytest.approx(1 / 6, abs=1e-6)
    assert config.round_targets and config.lam == 0.8 and config.freeze_value
    assert config.round_baseline
