"""Policy-gradient update over a self-play batch: REINFORCE or clipped PPO.

The advantage of a step is the acting seat's terminal reward minus the
value head's prediction before the update, normalized over the batch. The
loss combines the policy term, the value regression toward the terminal
reward, and an entropy bonus that keeps the masked distribution from
collapsing early.

Without ``clip_ratio`` the policy term is plain REINFORCE, which is only
on-policy for one pass over the batch. With ``clip_ratio`` it is PPO's
clipped surrogate: the probability ratio between the policy being trained
and the policy that collected the batch replaces the log-probability, and
a step stops contributing once its ratio leaves ``1 +- clip_ratio`` in
the direction its advantage pushes. That bounds how far one update moves
the policy and makes several ``epochs`` over the same batch sound. The
collecting policy's log-probabilities need no transport: collection runs
on the very weights the learner holds when ``update`` starts, with the
same masks, so they are recomputed here before the first gradient step.

Each minibatch computes logits only for the catalog actions legal in at
least one of its rows (``TrainingBatch.local_legal``), not for the whole
33,007-action head. That is exact, not an approximation: under the dense
mask every other action had logit ``MASKED_LOGIT``, hence probability,
entropy term and gradient exactly zero, and a head row no row can play gets
a zero gradient either way. Losses and gradients agree with the dense
computation up to float summation order.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import torch
from torch import Tensor

from dune_imperium.training.network import MASKED_LOGIT, PolicyValueNetwork
from dune_imperium.training.selfplay import TrainingBatch


@dataclass(frozen=True, slots=True)
class LearnerConfig:
    learning_rate: float = 3.0e-4
    value_coefficient: float = 0.5
    entropy_coefficient: float = 0.01
    minibatch_size: int = 4096
    epochs: int = 1
    max_grad_norm: float = 1.0
    normalize_advantages: bool = True
    # PPO clip range; None keeps the REINFORCE policy term.
    clip_ratio: float | None = None

    def __post_init__(self) -> None:
        if self.minibatch_size < 1 or self.epochs < 1:
            raise ValueError("minibatch_size and epochs must be positive")
        if self.clip_ratio is not None and not 0.0 < self.clip_ratio < 1.0:
            raise ValueError("clip_ratio must lie strictly between 0 and 1")


@dataclass(frozen=True, slots=True)
class UpdateStats:
    steps: int
    minibatches: int
    policy_loss: float
    value_loss: float
    entropy: float
    mean_return: float
    explained_variance: float
    # PPO diagnostics over every minibatch step (0.0 without clipping): the
    # share of steps whose ratio left the clip range, and the mean
    # old-minus-new log-probability of the chosen actions.
    clip_fraction: float = 0.0
    approx_kl: float = 0.0


class Learner:
    """Own the optimizer and apply one update per collected batch."""

    def __init__(
        self,
        network: PolicyValueNetwork,
        device: torch.device,
        config: LearnerConfig | None = None,
        *,
        seed: int = 0,
    ) -> None:
        self.network = network.to(device)
        self.device = device
        self.config = config or LearnerConfig()
        self.optimizer = torch.optim.Adam(
            self.network.parameters(), lr=self.config.learning_rate
        )
        self._generator = torch.Generator().manual_seed(seed)

    def optimizer_state(self) -> dict[str, Any]:
        """Return the optimizer state for a checkpoint."""

        return dict(self.optimizer.state_dict())

    def restore_optimizer(self, state: Mapping[str, Any]) -> None:
        """Continue from a checkpoint's optimizer state (moments, step count).

        The state also carries the learning rate it was saved with, and
        ``load_state_dict`` puts it back. The configured rate has to win:
        resuming with another ``--learning-rate`` is how a run lowers it, and
        it used to keep the checkpoint's rate without a word.
        """

        self.optimizer.load_state_dict(dict(state))
        for group in self.optimizer.param_groups:
            group["lr"] = self.config.learning_rate

    def update(self, batch: TrainingBatch) -> UpdateStats:
        """Run ``epochs`` passes of minibatch policy-gradient steps."""

        steps = int(batch.actions.shape[0])
        if steps == 0:
            raise ValueError("cannot update on an empty batch")
        observations = torch.from_numpy(batch.observations).to(self.device)
        returns = torch.from_numpy(batch.returns).to(self.device)

        self.network.train()
        values, behaviour = self._behaviour(observations, batch)
        advantages = returns - values
        old_chosen = behaviour if self.config.clip_ratio is not None else None
        if self.config.normalize_advantages and steps > 1:
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        policy_total = value_total = entropy_total = 0.0
        clipped_total = kl_total = 0.0
        minibatches = 0
        for _ in range(self.config.epochs):
            order = torch.randperm(steps, generator=self._generator).to(self.device)
            for start in range(0, steps, self.config.minibatch_size):
                index = order[start : start + self.config.minibatch_size]
                policy_loss, value_loss, entropy, clipped, kl = self._losses(
                    observations[index],
                    batch,
                    index,
                    returns[index],
                    advantages[index],
                    None if old_chosen is None else old_chosen[index],
                )
                loss = (
                    policy_loss
                    + self.config.value_coefficient * value_loss
                    - self.config.entropy_coefficient * entropy
                )
                self.optimizer.zero_grad(set_to_none=True)
                loss.backward()  # type: ignore[no-untyped-call]
                torch.nn.utils.clip_grad_norm_(
                    self.network.parameters(), self.config.max_grad_norm
                )
                self.optimizer.step()
                policy_total += float(policy_loss.item())
                value_total += float(value_loss.item())
                entropy_total += float(entropy.item())
                clipped_total += clipped
                kl_total += kl
                minibatches += 1

        fitted, _ = self._behaviour(observations, batch)
        return UpdateStats(
            steps=steps,
            minibatches=minibatches,
            policy_loss=policy_total / minibatches,
            value_loss=value_total / minibatches,
            entropy=entropy_total / minibatches,
            mean_return=float(np.mean(batch.returns)),
            explained_variance=_explained_variance(
                fitted.to("cpu").numpy(), batch.returns
            ),
            clip_fraction=clipped_total / minibatches,
            approx_kl=kl_total / minibatches,
        )

    def _local_logits(
        self, observations: Tensor, batch: TrainingBatch, rows: Tensor
    ) -> tuple[Tensor, Tensor, Tensor]:
        """Masked logits over the minibatch's legal union, chosen positions, values.

        The logits are ``[rows, K]`` over ``batch.local_legal(rows).catalog``
        instead of ``[rows, action_size]``; no dense mask is built.
        """

        legal = batch.local_legal(rows.to("cpu").numpy())
        catalog = torch.from_numpy(legal.catalog).to(self.device)
        mask = torch.from_numpy(legal.mask).to(self.device)
        hidden = self.network.trunk(observations)
        logits = self.network.action_logits(hidden, catalog).masked_fill(
            ~mask, MASKED_LOGIT
        )
        values = self.network.value_head(hidden).squeeze(-1)
        return logits, torch.from_numpy(legal.chosen).to(self.device), values

    def _behaviour(
        self, observations: Tensor, batch: TrainingBatch
    ) -> tuple[Tensor, Tensor]:
        """Values and chosen-action log-probabilities of the current weights.

        Called before the first gradient step these are the collecting
        policy's. The pass is chunked by minibatch so each chunk's logits
        cover only that chunk's legal union.
        """

        values: list[Tensor] = []
        chosen: list[Tensor] = []
        rows = torch.arange(observations.shape[0])
        with torch.no_grad():
            for start in range(0, observations.shape[0], self.config.minibatch_size):
                stop = start + self.config.minibatch_size
                logits, positions, value = self._local_logits(
                    observations[start:stop], batch, rows[start:stop]
                )
                log_probabilities = torch.log_softmax(logits, dim=-1)
                chosen.append(
                    log_probabilities.gather(1, positions.unsqueeze(-1)).squeeze(-1)
                )
                values.append(value)
        return torch.cat(values), torch.cat(chosen)

    def _losses(
        self,
        observations: Tensor,
        batch: TrainingBatch,
        rows: Tensor,
        returns: Tensor,
        advantages: Tensor,
        old_chosen: Tensor | None,
    ) -> tuple[Tensor, Tensor, Tensor, float, float]:
        logits, positions, values = self._local_logits(observations, batch, rows)
        log_probabilities = torch.log_softmax(logits, dim=-1)
        chosen = log_probabilities.gather(1, positions.unsqueeze(-1)).squeeze(-1)
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
        # Masked actions have probability exactly zero; 0 * (-1e9) stays 0.
        entropy = -(probabilities * log_probabilities).sum(dim=-1).mean()
        return policy_loss, value_loss, entropy, clipped, kl


def _explained_variance(predicted: np.ndarray, target: np.ndarray) -> float:
    variance = float(np.var(target))
    if variance == 0.0:
        return 0.0
    return 1.0 - float(np.var(target - predicted)) / variance
