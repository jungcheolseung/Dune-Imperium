"""The learner's logits over a minibatch's legal union equal the dense head's.

The learner used to compute every catalog logit, mask the illegal ones to
``MASKED_LOGIT`` and take the softmax over the full 33,007-wide head. It now
computes only the columns legal in some row of the minibatch
(``TrainingBatch.local_legal``). A masked logit has probability, entropy
term and gradient exactly zero, so the two must agree up to float summation
order. ``_DenseLearner`` below keeps the old dense computation as the
reference.
"""

import copy
from dataclasses import replace
from typing import Any

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from torch.utils import _pytree as pytree  # noqa: E402
from torch.utils._python_dispatch import TorchDispatchMode  # noqa: E402

from dune_imperium import RulesetConfig  # noqa: E402
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
_FULL = RulesetConfig(
    choam_module=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
)


class _DenseLearner(Learner):
    """The pre-change learner: full-head logits under a dense mask."""

    def _dense(self, batch: TrainingBatch, rows: Any) -> tuple[Any, Any]:
        selected = rows.to("cpu").numpy()
        masks = torch.from_numpy(batch.dense_masks(selected)).to(self.device)
        actions = torch.from_numpy(batch.actions[selected]).to(self.device)
        return masks, actions

    def _behaviour(self, observations: Any, batch: TrainingBatch) -> tuple[Any, Any]:
        values: list[Any] = []
        chosen: list[Any] = []
        rows = torch.arange(observations.shape[0])
        with torch.no_grad():
            for start in range(0, observations.shape[0], self.config.minibatch_size):
                stop = start + self.config.minibatch_size
                masks, actions = self._dense(batch, rows[start:stop])
                logits, value = self.network(observations[start:stop], masks)
                log_probabilities = torch.log_softmax(logits, dim=-1)
                chosen.append(
                    log_probabilities.gather(1, actions.unsqueeze(-1)).squeeze(-1)
                )
                values.append(value)
        return torch.cat(values), torch.cat(chosen)

    def _losses(
        self,
        observations: Any,
        batch: TrainingBatch,
        rows: Any,
        returns: Any,
        advantages: Any,
        old_chosen: Any,
    ) -> tuple[Any, Any, Any, float, float]:
        masks, actions = self._dense(batch, rows)
        logits, values = self.network(observations, masks)
        log_probabilities = torch.log_softmax(logits, dim=-1)
        chosen = log_probabilities.gather(1, actions.unsqueeze(-1)).squeeze(-1)
        clipped = kl = 0.0
        if old_chosen is None or self.config.clip_ratio is None:
            policy_loss = -(chosen * advantages).mean()
        else:
            epsilon = self.config.clip_ratio
            ratio = torch.exp(chosen - old_chosen)
            bounded = ratio.clamp(1.0 - epsilon, 1.0 + epsilon)
            surrogate = torch.minimum(ratio * advantages, bounded * advantages)
            policy_loss = -surrogate.mean()
            with torch.no_grad():
                clipped = float(((ratio - 1.0).abs() > epsilon).float().mean().item())
                kl = float((old_chosen - chosen).mean().item())
        value_loss = torch.nn.functional.mse_loss(values, returns)
        probabilities = log_probabilities.exp()
        entropy = -(probabilities * log_probabilities).sum(dim=-1).mean()
        return policy_loss, value_loss, entropy, clipped, kl


@pytest.fixture(scope="module")
def real() -> tuple[PolicyValueNetwork, TrainingBatch]:
    """A seeded full-expansion self-play batch, collected as training does."""

    runner = SelfPlayRunner(_FULL, max_steps=240, undo_actions=False)
    torch.manual_seed(0)
    network = PolicyValueNetwork(runner.codec.size, hidden=(32,))
    policy = TorchBatchPolicy(network, _CPU, seed=4, sample=True)
    result = runner.run({"p": policy}, (SelfPlaySpec(game_seed=9, lineup=("p",) * 4),))
    batch = stack_episodes(result.episodes, action_size=runner.codec.size)
    # A truncated game pays nothing; give the steps a signal to learn from.
    returns = batch.returns.copy()
    returns[::2] = 1.0
    returns[1::2] = -1.0 / 3.0
    return network, replace(batch, returns=returns)


# The synthetic rows' observation width. It is fixed rather than
# OBSERVATION_SIZE so that an observation layout change does not redraw the
# random rows and weights: at v30's 4,529 columns one row's PPO ratio drew
# 179 and amplified float32 noise past the gradient tolerance (OQ-061).
_SYNTHETIC_WIDTH = 64


def _synthetic() -> tuple[PolicyValueNetwork, TrainingBatch]:
    """Rows of very different legal-set sizes, some sharing no action."""

    legal = [
        [3],  # a single legal action
        [0, 1, 2],
        [10, 11, 12, 13, 14, 15, 16],
        [40, 41],  # shares nothing with any other row
        [1, 12, 49],
        [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31],
        [3, 49],
        [45],  # single, and shared with no one
    ]
    actions = [3, 2, 14, 41, 1, 20, 49, 45]
    rng = np.random.default_rng(3)
    steps = len(legal)
    offsets = np.zeros(steps + 1, dtype=np.int64)
    np.cumsum([len(row) for row in legal], out=offsets[1:])
    batch = TrainingBatch(
        observations=rng.integers(0, 6, size=(steps, _SYNTHETIC_WIDTH)).astype(
            np.int32
        ),
        legal_indices=np.concatenate([np.asarray(row) for row in legal]).astype(
            np.int32
        ),
        legal_offsets=offsets,
        action_size=50,
        actions=np.asarray(actions, dtype=np.int64),
        seats=(np.arange(steps) % 4).astype(np.int8),
        returns=np.asarray([1, -1 / 3, -1 / 3, -1 / 3] * 2, dtype=np.float32),
        episode_ids=np.zeros(steps, dtype=np.int32),
    )
    torch.manual_seed(1)
    network = PolicyValueNetwork(
        50, observation_size=_SYNTHETIC_WIDTH, hidden=(16,)
    )
    with torch.no_grad():
        # Spread the head so the softmax is far from uniform.
        network.policy_head.bias.normal_(0.0, 2.0)
    return network, batch


def _losses_and_gradients(
    learner: Learner,
    batch: TrainingBatch,
    rows: Any,
    advantages: Any,
    old_chosen: Any,
) -> tuple[list[float], dict[str, Any]]:
    observations = torch.from_numpy(batch.observations)
    returns = torch.from_numpy(batch.returns)
    learner.network.zero_grad(set_to_none=True)
    policy, value, entropy, clipped, kl = learner._losses(
        observations[rows],
        batch,
        rows,
        returns[rows],
        advantages[rows],
        None if old_chosen is None else old_chosen[rows],
    )
    (policy + 0.5 * value - 0.01 * entropy).backward()  # type: ignore[no-untyped-call]
    gradients: dict[str, Any] = {}
    for name, parameter in learner.network.named_parameters():
        assert parameter.grad is not None
        gradients[name] = parameter.grad.clone()
    return [policy.item(), value.item(), entropy.item(), clipped, kl], gradients


def _assert_same_losses_and_gradients(
    network: PolicyValueNetwork, batch: TrainingBatch, clip_ratio: float | None
) -> None:
    steps = int(batch.actions.shape[0])
    config = LearnerConfig(minibatch_size=steps, clip_ratio=clip_ratio)
    local = Learner(copy.deepcopy(network), _CPU, config)
    dense = _DenseLearner(copy.deepcopy(network), _CPU, config)
    observations = torch.from_numpy(batch.observations)
    old_chosen = None
    if clip_ratio is not None:
        _, old_chosen = dense._behaviour(observations, batch)
        # Move the policy off the collecting one so ratios differ and clip.
        generator = torch.Generator().manual_seed(7)
        with torch.no_grad():
            for learner in (local, dense):
                for parameter in learner.network.parameters():
                    parameter.add_(
                        torch.randn(parameter.shape, generator=generator) * 0.3
                    )
                generator.manual_seed(7)
    generator = torch.Generator().manual_seed(5)
    advantages = torch.randn(steps, generator=generator)
    rows = torch.randperm(steps, generator=generator)

    got, got_gradients = _losses_and_gradients(
        local, batch, rows, advantages, old_chosen
    )
    want, want_gradients = _losses_and_gradients(
        dense, batch, rows, advantages, old_chosen
    )

    assert got == pytest.approx(want, rel=1e-5, abs=1e-6)
    if clip_ratio is not None:
        assert 0.0 < want[3] < 1.0  # some ratios clipped, some not
    for name, expected in want_gradients.items():
        scale = float(expected.abs().max()) or 1.0
        torch.testing.assert_close(
            got_gradients[name], expected, rtol=1e-5, atol=1e-6 * scale, msg=name
        )
    # The head rows no row can play get no gradient in either path.
    unused = np.setdiff1d(np.arange(batch.action_size), batch.legal_indices)
    assert not got_gradients["policy_head.weight"][unused].any()
    assert not got_gradients["policy_head.bias"][unused].any()


@pytest.mark.parametrize("clip_ratio", [None, 0.2])
def test_local_losses_and_gradients_match_the_dense_head_on_self_play(
    real: tuple[PolicyValueNetwork, TrainingBatch], clip_ratio: float | None
) -> None:
    network, batch = real
    _assert_same_losses_and_gradients(network, batch, clip_ratio)


@pytest.mark.parametrize("clip_ratio", [None, 0.2])
def test_local_losses_and_gradients_match_the_dense_head_on_ragged_rows(
    clip_ratio: float | None,
) -> None:
    network, batch = _synthetic()
    _assert_same_losses_and_gradients(network, batch, clip_ratio)


@pytest.mark.parametrize("clip_ratio", [None, 0.2])
def test_one_update_moves_the_weights_as_the_dense_update_does(
    real: tuple[PolicyValueNetwork, TrainingBatch], clip_ratio: float | None
) -> None:
    network, batch = real
    config = LearnerConfig(minibatch_size=64, epochs=2, clip_ratio=clip_ratio)
    local = Learner(copy.deepcopy(network), _CPU, config, seed=3)
    dense = _DenseLearner(copy.deepcopy(network), _CPU, config, seed=3)

    got = local.update(batch)
    want = dense.update(batch)

    assert got.steps == want.steps and got.minibatches == want.minibatches
    for field in (
        "policy_loss",
        "value_loss",
        "entropy",
        "mean_return",
        "explained_variance",
        "clip_fraction",
        "approx_kl",
    ):
        assert getattr(got, field) == pytest.approx(
            getattr(want, field), rel=1e-4, abs=1e-6
        ), field
    for (name, moved), expected in zip(
        local.network.named_parameters(), dense.network.parameters(), strict=True
    ):
        torch.testing.assert_close(moved, expected, rtol=0.0, atol=1e-6, msg=name)
    # And the update did move them.
    assert any(
        not torch.equal(moved, original)
        for moved, original in zip(
            local.network.parameters(), network.parameters(), strict=True
        )
    )


def test_behaviour_matches_the_dense_head(
    real: tuple[PolicyValueNetwork, TrainingBatch],
) -> None:
    network, batch = real
    config = LearnerConfig(minibatch_size=48)
    observations = torch.from_numpy(batch.observations)

    values, chosen = Learner(network, _CPU, config)._behaviour(observations, batch)
    want_values, want_chosen = _DenseLearner(network, _CPU, config)._behaviour(
        observations, batch
    )

    torch.testing.assert_close(values, want_values, rtol=1e-6, atol=1e-6)
    torch.testing.assert_close(chosen, want_chosen, rtol=1e-5, atol=1e-6)
    assert bool((chosen <= 0.0).all())


class _CatalogWideGuard(TorchDispatchMode):  # type: ignore[no-untyped-call]
    """Fail on any op output with an ``action_size`` axis but not head-shaped.

    The policy head's own parameter shapes (``[action_size, width]`` and
    ``[action_size]``) stay allowed: its gradient and the optimizer step are
    catalog-wide by nature. A dense mask ``[rows, action_size]``, full-head
    logits (``policy_head(hidden)`` or ``weight @ hidden.T``) and anything
    derived from them are not.
    """

    def __init__(self, action_size: int, allowed: set[tuple[int, ...]]) -> None:
        super().__init__()  # type: ignore[no-untyped-call]
        self.action_size = action_size
        self.allowed = allowed

    def __torch_dispatch__(
        self, func: Any, types: Any, args: Any = (), kwargs: Any = None
    ) -> Any:
        out = func(*args, **(kwargs or {}))
        for tensor in pytree.tree_leaves(out):
            if not isinstance(tensor, torch.Tensor):
                continue
            shape = tuple(tensor.shape)
            if self.action_size in shape and shape not in self.allowed:
                raise AssertionError(f"{func} produced a catalog-wide {shape}")
        return out


def test_update_never_builds_a_catalog_wide_mask_or_logit_row(
    real: tuple[PolicyValueNetwork, TrainingBatch], monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_: Any, **__: Any) -> Any:
        raise AssertionError("the learner built a catalog-wide mask or logit row")

    monkeypatch.setattr(TrainingBatch, "dense_masks", refuse)
    monkeypatch.setattr(PolicyValueNetwork, "forward", refuse)
    network, batch = real
    head = network.policy_head.weight
    allowed = {tuple(head.shape), (head.shape[0],)}
    # The minibatch must not share a size with the head's width, or a
    # transposed [action_size, rows] product would pass as head-shaped.
    assert 64 != head.shape[1]
    for clip_ratio in (None, 0.2):
        config = LearnerConfig(minibatch_size=64, clip_ratio=clip_ratio)
        learner = Learner(copy.deepcopy(network), _CPU, config)
        with _CatalogWideGuard(batch.action_size, allowed):
            learner.update(batch)


def test_catalog_wide_guard_catches_full_head_logits(
    real: tuple[PolicyValueNetwork, TrainingBatch],
) -> None:
    """The guard above fires on the full-head matmul the learner dropped."""

    network, batch = real
    head = network.policy_head.weight
    observations = torch.from_numpy(batch.observations[:64])
    with (
        _CatalogWideGuard(batch.action_size, {tuple(head.shape), (head.shape[0],)}),
        pytest.raises(AssertionError, match="catalog-wide"),
    ):
        network.policy_head(network.trunk(observations))


def test_local_legal_indexes_each_row_over_the_union() -> None:
    _, batch = _synthetic()
    rows = np.asarray([5, 0, 3, 4], dtype=np.int64)

    legal = batch.local_legal(rows)

    dense = batch.dense_masks(rows).astype(bool)
    assert np.array_equal(legal.catalog, np.flatnonzero(dense.any(axis=0)))
    assert np.array_equal(legal.mask, dense[:, legal.catalog])
    assert np.array_equal(legal.catalog[legal.chosen], batch.actions[rows])

    # Row 3 offers only 40 and 41: 0 is in no row's set, 3 is in row 0's.
    for action in (0, 3):
        illegal = replace(
            batch, actions=np.where(np.arange(8) == 3, action, batch.actions)
        )
        with pytest.raises(ValueError, match="legal set"):
            illegal.local_legal(rows)
    beyond = replace(batch, actions=np.where(np.arange(8) == 3, 49, batch.actions))
    with pytest.raises(ValueError, match="legal set"):
        beyond.local_legal(np.asarray([3], dtype=np.int64))
