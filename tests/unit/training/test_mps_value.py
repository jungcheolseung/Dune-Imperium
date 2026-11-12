"""The entity network and the round-value fit on Apple's GPU (MPS).

docs/evaluation/2026-11-mps-value.md: the value fit can run on ``mps`` and
gives the CPU's numbers within the tolerances that document fixed before
any measurement (section 2 A and C); the default stays the CPU, and a fit
made on the GPU comes back, saves and reloads on the CPU. The MPS tests skip
where PyTorch reports no MPS device (another OS, or a sandbox that hides it).
"""

import copy
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.adapters.action_codec import ActionCodec  # noqa: E402
from dune_imperium.training.checkpoint import (  # noqa: E402
    load_checkpoint,
    save_checkpoint,
)
from dune_imperium.training.entity_network import (  # noqa: E402
    EntityNetwork,
    with_value_branch,
)
from dune_imperium.training.round_values import (  # noqa: E402
    CollectSpec,
    FitConfig,
    RoundData,
    _branch_losses,
    _branch_parameters,
    collect_rounds,
    fit_round_values,
    lambda_targets,
    outcome_rewards,
    predict_values,
)

_CONFIG = RulesetConfig()
_MPS = torch.backends.mps.is_available()
needs_mps = pytest.mark.skipif(
    not _MPS, reason="PyTorch reports no MPS device here (not Apple silicon, or hidden)"
)

# Fixed before any measurement (docs/evaluation/2026-11-mps-value.md 2).
VALUE_TOLERANCE = 1e-4
LOGIT_TOLERANCE = 1e-3
GRADIENT_TENSOR_TOLERANCE = 1e-3
GRADIENT_TOTAL_TOLERANCE = 1e-4
LOSS_STEP_TOLERANCE = 1e-4


@pytest.fixture(scope="module")
def collected() -> RoundData:
    spec = CollectSpec(config=_CONFIG, learner="heuristic", x="heuristic")
    return collect_rounds(spec, [(0, 20), (1, 21)])


def _e3_like(seed: int = 0) -> EntityNetwork:
    """A small network with E3's shape: a value branch with its own encoders."""

    torch.manual_seed(seed)
    start = EntityNetwork(
        _CONFIG, hidden=(32,), entity_width=16, seat_width=32, action_width=16
    ).eval()
    with torch.no_grad():
        for parameter in start.entity_own.values():
            parameter.normal_(0.0, 0.5)
        start.action_bias.normal_(0.0, 0.5)
    return with_value_branch(
        start, aux_vp=True, aux_rank=True, reward_step=1 / 6, value_encoders=True
    ).eval()


def test_the_fit_stays_on_the_cpu_by_default(collected: RoundData) -> None:
    config = FitConfig(lam=0.8, step=1 / 6, fits=1, epochs=1, minibatch=16, chunk=64)
    assert config.device == "cpu"
    fitted, _ = fit_round_values(_e3_like(), collected, config)
    assert {parameter.device.type for parameter in fitted.parameters()} == {"cpu"}


@pytest.mark.skipif(_MPS, reason="checks the refusal where MPS is missing")
def test_asking_for_mps_without_it_is_refused(collected: RoundData) -> None:
    config = FitConfig(lam=0.8, step=1 / 6, fits=1, epochs=1, device="mps")
    with pytest.raises(ValueError, match="mps"):
        fit_round_values(_e3_like(), collected, config)


@needs_mps
def test_values_and_logits_match_the_cpu(collected: RoundData) -> None:
    network = _e3_like()
    gpu = copy.deepcopy(network).to("mps")
    rows = np.arange(collected.rows)
    cpu_values = predict_values(network, collected, rows, chunk=32)
    gpu_values = predict_values(gpu, collected, rows, chunk=32)
    assert np.isfinite(gpu_values).all()
    assert np.abs(gpu_values - cpu_values).max() <= VALUE_TOLERANCE
    observations = torch.from_numpy(collected.observations(rows[:16]))
    masks = torch.ones(16, network.action_size, dtype=torch.bool)
    with torch.no_grad():
        cpu_logits, _ = network(observations, masks)
        gpu_logits, _ = gpu(observations.to("mps"), masks.to("mps"))
    gpu_logits = gpu_logits.cpu()
    assert torch.isfinite(gpu_logits).all()
    assert (gpu_logits - cpu_logits).abs().max().item() <= LOGIT_TOLERANCE


@needs_mps
def test_the_value_s_encoders_get_the_cpu_s_gradients(collected: RoundData) -> None:
    network = _e3_like()
    rows = np.arange(min(64, collected.rows))
    targets = np.linspace(-0.5, 0.5, collected.rows).astype(np.float32)
    gradients = []
    for device in ("cpu", "mps"):
        copied = copy.deepcopy(network).to(device).train()
        parameters = _branch_parameters(copied)
        value_loss, _, vp_loss, rank_loss = _branch_losses(
            copied, collected, rows, targets
        )
        assert vp_loss is not None and rank_loss is not None
        loss = value_loss + vp_loss + 0.1 * rank_loss
        loss.backward()  # type: ignore[no-untyped-call]
        gradients.append(
            [
                torch.zeros_like(p).cpu() if p.grad is None else p.grad.detach().cpu()
                for p in parameters
            ]
        )
    cpu, gpu = gradients
    assert any(gradient.abs().sum() > 0 for gradient in cpu)
    for want, got in zip(cpu, gpu, strict=True):
        assert torch.isfinite(got).all()
        norm = want.norm().item()
        if norm == 0.0:
            assert got.abs().max().item() == 0.0
        else:
            assert (got - want).norm().item() / norm <= GRADIENT_TENSOR_TOLERANCE
    want_all = torch.cat([gradient.flatten() for gradient in cpu])
    got_all = torch.cat([gradient.flatten() for gradient in gpu])
    total = (got_all - want_all).norm().item() / want_all.norm().item()
    assert total <= GRADIENT_TOTAL_TOLERANCE


@needs_mps
def test_an_mps_fit_follows_the_cpu_and_keeps_the_policy(
    collected: RoundData,
) -> None:
    network = _e3_like()
    records = {}
    fitted = {}
    for device in ("cpu", "mps"):
        config = FitConfig(
            lam=0.8, step=1 / 6, fits=1, epochs=2, minibatch=16, chunk=64, device=device
        )
        fitted[device], records[device] = fit_round_values(network, collected, config)
    for want, got in zip(records["cpu"], records["mps"], strict=True):
        cpu_loss, gpu_loss = want["train_value_mse"], got["train_value_mse"]
        assert abs(gpu_loss - cpu_loss) <= LOSS_STEP_TOLERANCE * abs(cpu_loss)
    branch = {id(parameter) for parameter in _branch_parameters(network)}
    names = {
        name
        for name, parameter in network.named_parameters()
        if id(parameter) not in branch
    }
    assert names
    for device in ("cpu", "mps"):
        state = fitted[device].state_dict()
        assert {tensor.device.type for tensor in state.values()} == {"cpu"}
        for name in names:
            assert torch.equal(state[name], network.state_dict()[name]), (device, name)


@needs_mps
def test_an_mps_fit_saves_and_reloads_on_the_cpu(
    tmp_path: Path, collected: RoundData
) -> None:
    config = FitConfig(
        lam=0.8, step=1 / 6, fits=1, epochs=1, minibatch=16, chunk=64, device="mps"
    )
    fitted, _ = fit_round_values(_e3_like(), collected, config)
    path = tmp_path / "value.pt"
    save_checkpoint(
        path,
        fitted,
        ruleset=fitted.config.identifier,
        iteration=1,
        codec=ActionCodec(fitted.config),
    )
    loaded, _ = load_checkpoint(path, ruleset=_CONFIG)
    assert isinstance(loaded, EntityNetwork)
    for name, tensor in fitted.state_dict().items():
        assert torch.equal(loaded.state_dict()[name], tensor), name
    rows = np.arange(collected.rows)
    np.testing.assert_array_equal(
        predict_values(loaded, collected, rows), predict_values(fitted, collected, rows)
    )


@needs_mps
def test_lambda_targets_from_mps_values_match_the_cpu_s(collected: RoundData) -> None:
    # The fit builds each fit's targets from the network's own values; with
    # the values within tolerance the NumPy targets are too.
    network = _e3_like()
    rows = np.arange(collected.rows)
    following = collected.next_rows()
    rewards = outcome_rewards(collected, 1 / 6)
    cpu = lambda_targets(
        following, predict_values(network, collected, rows), rewards, 0.8
    )
    gpu_network = copy.deepcopy(network).to("mps")
    gpu = lambda_targets(
        following, predict_values(gpu_network, collected, rows), rewards, 0.8
    )
    assert np.abs(gpu - cpu).max() <= VALUE_TOLERANCE
