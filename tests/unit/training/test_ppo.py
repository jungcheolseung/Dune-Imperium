"""The opt-in clipped PPO policy term of the learner."""

import copy
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.cli.train import main as train_main  # noqa: E402
from dune_imperium.training import (  # noqa: E402
    SelfPlayRunner,
    SelfPlaySpec,
    TrainingBatch,
    stack_episodes,
)
from dune_imperium.training.learner import Learner, LearnerConfig  # noqa: E402
from dune_imperium.training.network import PolicyValueNetwork  # noqa: E402
from dune_imperium.training.torch_policy import TorchBatchPolicy  # noqa: E402

_CPU = torch.device("cpu")


def _network_and_batch() -> tuple[PolicyValueNetwork, TrainingBatch]:
    runner = SelfPlayRunner(RulesetConfig(), max_steps=160)
    torch.manual_seed(0)
    network = PolicyValueNetwork(runner.codec.size, hidden=(32,))
    policy = TorchBatchPolicy(network, _CPU, seed=2)
    result = runner.run({"p": policy}, (SelfPlaySpec(game_seed=5, lineup=("p",) * 4),))
    batch = stack_episodes(result.episodes, action_size=runner.codec.size)
    # A truncated game pays nothing; give the steps a signal to learn from.
    returns = batch.returns.copy()
    returns[::2] = 1.0
    returns[1::2] = -1.0 / 3.0
    return network, replace(batch, returns=returns)


def _chosen_log_probabilities(network: PolicyValueNetwork, batch: TrainingBatch) -> Any:
    with torch.no_grad():
        logits, _ = network(
            torch.from_numpy(batch.observations),
            torch.from_numpy(batch.dense_masks(np.arange(batch.actions.shape[0]))),
        )
    actions = torch.from_numpy(batch.actions).unsqueeze(-1)
    return torch.log_softmax(logits, dim=-1).gather(1, actions).squeeze(-1)


def test_the_first_ppo_step_is_the_reinforce_step() -> None:
    # At the collecting policy the ratio is exactly one, where the clipped
    # surrogate has REINFORCE's gradient; one full-batch step must match.
    network, batch = _network_and_batch()
    steps = int(batch.actions.shape[0])
    plain_network = copy.deepcopy(network)
    config = LearnerConfig(minibatch_size=steps, epochs=1)
    Learner(plain_network, _CPU, config, seed=1).update(batch)
    stats = Learner(network, _CPU, replace(config, clip_ratio=0.2), seed=1).update(
        batch
    )

    assert stats.clip_fraction == 0.0
    assert stats.approx_kl == pytest.approx(0.0, abs=1e-6)
    for clipped, plain in zip(
        network.parameters(), plain_network.parameters(), strict=True
    ):
        assert torch.allclose(clipped, plain, atol=1e-6)


def test_clipping_bounds_how_far_several_epochs_move_the_policy() -> None:
    network, batch = _network_and_batch()
    steps = int(batch.actions.shape[0])
    before = _chosen_log_probabilities(network, batch)
    plain_network = copy.deepcopy(network)
    config = LearnerConfig(
        minibatch_size=steps, epochs=12, learning_rate=3.0e-3, entropy_coefficient=0.0
    )
    plain = Learner(plain_network, _CPU, config, seed=1).update(batch)
    clipped = Learner(network, _CPU, replace(config, clip_ratio=0.1), seed=1).update(
        batch
    )

    moved_plain = (
        (_chosen_log_probabilities(plain_network, batch) - before).abs().mean()
    )
    moved_clipped = (_chosen_log_probabilities(network, batch) - before).abs().mean()
    assert float(moved_clipped) < float(moved_plain)
    assert plain.clip_fraction == 0.0 and plain.approx_kl == 0.0
    assert clipped.clip_fraction > 0.0
    assert clipped.minibatches == 12

    with pytest.raises(ValueError, match="clip_ratio"):
        LearnerConfig(clip_ratio=1.0)
    with pytest.raises(ValueError, match="epochs"):
        LearnerConfig(epochs=0)


def test_train_cli_runs_ppo_and_rejects_a_bad_clip(tmp_path: Path) -> None:
    exit_code = train_main(
        [
            "--out",
            str(tmp_path / "ppo"),
            "--iterations",
            "1",
            "--games-per-iteration",
            "1",
            "--hidden",
            "16",
            "--minibatch",
            "256",
            "--clip",
            "0.2",
            "--epochs",
            "2",
        ]
    )
    assert exit_code == 0
    line = json.loads((tmp_path / "ppo" / "training.jsonl").read_text().splitlines()[0])
    assert line["update"]["clip_fraction"] >= 0.0
    assert line["eval_failures"] is None
    with pytest.raises(SystemExit):
        train_main(["--out", str(tmp_path / "bad"), "--clip", "1.5"])
