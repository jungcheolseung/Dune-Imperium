"""Tests for the network, checkpoints, learner, and training loop (M10)."""

import json
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.adapters.observation_encoding import OBSERVATION_SIZE  # noqa: E402
from dune_imperium.agents import make_agent  # noqa: E402
from dune_imperium.agents.registry import is_agent_kind  # noqa: E402
from dune_imperium.cli.train import main as train_main  # noqa: E402
from dune_imperium.evaluation import MatchSpec, play_match  # noqa: E402
from dune_imperium.training import (  # noqa: E402
    SelfPlayRunner,
    SelfPlaySpec,
    stack_episodes,
)
from dune_imperium.training.checkpoint import (  # noqa: E402
    load_checkpoint,
    save_checkpoint,
)
from dune_imperium.training.learner import Learner, LearnerConfig  # noqa: E402
from dune_imperium.training.loop import (  # noqa: E402
    TrainConfig,
    select_policy_steps,
    train,
)
from dune_imperium.training.network import (  # noqa: E402
    MASKED_LOGIT,
    PolicyValueNetwork,
)
from dune_imperium.training.torch_policy import (  # noqa: E402
    NetworkAgent,
    TorchBatchPolicy,
    resolve_device,
)

_CPU = torch.device("cpu")


def _network(action_size: int) -> PolicyValueNetwork:
    torch.manual_seed(0)
    return PolicyValueNetwork(action_size, hidden=(32,))


def test_network_masks_illegal_actions_to_zero_probability() -> None:
    network = _network(action_size=7)
    observations = torch.randint(0, 5, (3, OBSERVATION_SIZE), dtype=torch.int32)
    masks = torch.zeros(3, 7, dtype=torch.int8)
    masks[0, 2] = 1
    masks[1, [0, 6]] = 1
    masks[2, :] = 1

    logits, values = network(observations, masks)

    assert logits.shape == (3, 7)
    assert values.shape == (3,)
    assert torch.all(logits[masks == 0] <= MASKED_LOGIT)
    probabilities = torch.softmax(logits, dim=-1)
    assert torch.all(probabilities[masks == 0] == 0.0)
    assert probabilities[0, 2].item() == pytest.approx(1.0)
    with pytest.raises(ValueError, match="positive"):
        PolicyValueNetwork(0)


def test_torch_batch_policy_plays_legal_self_play_games() -> None:
    runner = SelfPlayRunner(RulesetConfig())
    network = _network(runner.codec.size)
    sampling = TorchBatchPolicy(network, _CPU, seed=1, sample=True)
    greedy = TorchBatchPolicy(network, _CPU, seed=1, sample=False)
    specs = (
        SelfPlaySpec(game_seed=3, lineup=("s", "g", "s", "g")),
        SelfPlaySpec(game_seed=4, lineup=("g", "s", "g", "s")),
    )

    result = runner.run({"s": sampling, "g": greedy}, specs)

    assert all(not episode.truncated for episode in result.episodes)
    for episode in result.episodes:
        assert all(step.mask[step.action] == 1 for step in episode.steps)
    assert sampling.act(()) == ()
    with pytest.raises(ValueError, match="temperature"):
        TorchBatchPolicy(network, _CPU, seed=1, temperature=0.0)
    assert resolve_device("cpu").type == "cpu"
    assert resolve_device("auto").type in {"cpu", "mps", "cuda"}


def test_checkpoint_round_trip_and_version_guard(tmp_path: Path) -> None:
    network = _network(action_size=11)
    path = tmp_path / "ckpt" / "net.pt"
    save_checkpoint(
        path, network, ruleset="uprising-4p-base", iteration=3, metadata={"k": 1}
    )

    loaded, info = load_checkpoint(path)

    assert info.ruleset == "uprising-4p-base"
    assert info.iteration == 3
    assert info.hidden == (32,)
    assert info.metadata == {"k": 1}
    observations = torch.randint(0, 5, (2, OBSERVATION_SIZE), dtype=torch.int32)
    masks = torch.ones(2, 11, dtype=torch.int8)
    expected, _ = network(observations, masks)
    actual, _ = loaded(observations, masks)
    assert torch.allclose(expected, actual)

    document = torch.load(path, weights_only=True)
    document["action_codec_version"] += 1
    stale = tmp_path / "stale.pt"
    torch.save(document, stale)
    with pytest.raises(ValueError, match="codec"):
        load_checkpoint(stale)


def test_learner_update_changes_parameters_and_reports_finite_stats() -> None:
    runner = SelfPlayRunner(RulesetConfig())
    network = _network(runner.codec.size)
    policy = TorchBatchPolicy(network, _CPU, seed=2)
    result = runner.run({"p": policy}, (SelfPlaySpec(game_seed=5, lineup=("p",) * 4),))
    batch = stack_episodes(result.episodes)
    learner = Learner(network, _CPU, LearnerConfig(minibatch_size=256, epochs=2))
    before = [parameter.detach().clone() for parameter in network.parameters()]

    stats = learner.update(batch)

    assert stats.steps == batch.actions.shape[0]
    assert stats.minibatches == 2 * ((stats.steps + 255) // 256)
    assert np.isfinite(stats.policy_loss)
    assert np.isfinite(stats.value_loss)
    assert stats.entropy > 0.0
    assert stats.mean_return == pytest.approx(float(batch.returns.mean()))
    assert any(
        not torch.equal(old, new)
        for old, new in zip(before, network.parameters(), strict=True)
    )


def test_checkpoint_agents_enter_tournaments_by_path(tmp_path: Path) -> None:
    config = RulesetConfig()
    runner = SelfPlayRunner(config)
    network = _network(runner.codec.size)
    path = tmp_path / "policy.pt"
    save_checkpoint(path, network, ruleset=config.identifier, iteration=1)
    kind = f"checkpoint:{path}"
    assert is_agent_kind(kind)
    assert not is_agent_kind("checkpoint:")
    assert isinstance(make_agent(kind, 0), NetworkAgent)

    result = play_match(
        MatchSpec(
            game_seed=6,
            policy_seed=1,
            seat_agents=(kind, "heuristic", "heuristic", "heuristic"),
        )
    )

    assert result.seats[0].agent == kind
    assert result.seats[0].decisions > 0
    assert result.seats[0].illegal_actions == 0
    with pytest.raises(ValueError, match="catalog"):
        NetworkAgent(network, RulesetConfig(choam_module=True))


def test_train_loop_writes_log_checkpoints_and_evaluates(tmp_path: Path) -> None:
    config = TrainConfig(
        out_dir=tmp_path / "run",
        iterations=2,
        games_per_iteration=2,
        seed=1,
        hidden=(32,),
        learner=LearnerConfig(minibatch_size=512),
        opponent="heuristic",
        eval_every=2,
        eval_games=1,
    )

    result = train(config)

    assert len(result.records) == 2
    first, second = result.records
    assert first.iteration == 1 and second.iteration == 2
    assert first.games == 2
    assert first.learner_steps > 0
    assert first.eval_win_rate is None
    assert second.eval_win_rate is not None
    assert 0.0 <= second.eval_win_rate <= 1.0
    assert second.eval_mean_rank is not None and 1.0 <= second.eval_mean_rank <= 4.0
    assert (tmp_path / "run" / "latest.pt").exists()
    assert (tmp_path / "run" / "iteration_00002.pt").exists()
    lines = result.log_path.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["iteration"] == 2

    # Resuming continues the iteration count from the checkpoint.
    resumed = train(
        TrainConfig(
            out_dir=tmp_path / "run",
            iterations=1,
            games_per_iteration=1,
            seed=1,
            hidden=(32,),
            resume=result.latest_checkpoint,
        )
    )
    assert resumed.records[0].iteration == 3
    with pytest.raises(ValueError, match="unknown opponent"):
        TrainConfig(out_dir=tmp_path, opponent="oracle")


def test_select_policy_steps_keeps_only_the_named_seats() -> None:
    runner = SelfPlayRunner(RulesetConfig(), max_steps=40)
    network = _network(runner.codec.size)
    policy = TorchBatchPolicy(network, _CPU, seed=3)
    result = runner.run(
        {"learner": policy, "other": TorchBatchPolicy(network, _CPU, seed=4)},
        (SelfPlaySpec(game_seed=7, lineup=("learner", "other", "other", "other")),),
    )
    batch = select_policy_steps(result.episodes, "learner")
    assert batch.actions.shape[0] > 0
    assert set(batch.seats.tolist()) == {0}
    with pytest.raises(ValueError, match="no steps"):
        select_policy_steps(result.episodes, "nobody")


def test_train_cli_smoke(tmp_path: Path) -> None:
    exit_code = train_main(
        [
            "--out",
            str(tmp_path / "cli"),
            "--iterations",
            "1",
            "--games-per-iteration",
            "1",
            "--hidden",
            "16",
            "--minibatch",
            "256",
        ]
    )
    assert exit_code == 0
    assert (tmp_path / "cli" / "latest.pt").exists()
    with pytest.raises(SystemExit):
        train_main(["--out", str(tmp_path), "--opponent", "oracle"])
