"""Policy-gradient update over a self-play batch (REINFORCE with a baseline).

The first learner is deliberately simple: one on-policy pass over the
collected steps, where the advantage of a step is the acting seat's
terminal reward minus the value head's prediction, normalized over the
batch. The loss combines the policy gradient, the value regression toward
the terminal reward, and an entropy bonus that keeps the masked
distribution from collapsing early. PPO-style clipping can replace the
policy term later without changing the data contract.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import torch
from torch import Tensor

from dune_imperium.training.network import PolicyValueNetwork
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


@dataclass(frozen=True, slots=True)
class UpdateStats:
    steps: int
    minibatches: int
    policy_loss: float
    value_loss: float
    entropy: float
    mean_return: float
    explained_variance: float


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
        if self.config.minibatch_size < 1 or self.config.epochs < 1:
            raise ValueError("minibatch_size and epochs must be positive")
        self.optimizer = torch.optim.Adam(
            self.network.parameters(), lr=self.config.learning_rate
        )
        self._generator = torch.Generator().manual_seed(seed)

    def optimizer_state(self) -> dict[str, Any]:
        """Return the optimizer state for a checkpoint."""

        return dict(self.optimizer.state_dict())

    def restore_optimizer(self, state: Mapping[str, Any]) -> None:
        """Continue from a checkpoint's optimizer state (moments, step count)."""

        self.optimizer.load_state_dict(dict(state))

    def update(self, batch: TrainingBatch) -> UpdateStats:
        """Run ``epochs`` passes of minibatch policy-gradient steps."""

        steps = int(batch.actions.shape[0])
        if steps == 0:
            raise ValueError("cannot update on an empty batch")
        observations = torch.from_numpy(batch.observations).to(self.device)
        masks = torch.from_numpy(batch.masks).to(self.device)
        actions = torch.from_numpy(batch.actions).to(self.device)
        returns = torch.from_numpy(batch.returns).to(self.device)

        self.network.train()
        advantages = returns - self._values(observations, masks)
        if self.config.normalize_advantages and steps > 1:
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        policy_total = value_total = entropy_total = 0.0
        minibatches = 0
        for _ in range(self.config.epochs):
            order = torch.randperm(steps, generator=self._generator).to(self.device)
            for start in range(0, steps, self.config.minibatch_size):
                index = order[start : start + self.config.minibatch_size]
                policy_loss, value_loss, entropy = self._losses(
                    observations[index],
                    masks[index],
                    actions[index],
                    returns[index],
                    advantages[index],
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
                minibatches += 1

        fitted = self._values(observations, masks)
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
        )

    def _values(self, observations: Tensor, masks: Tensor) -> Tensor:
        """Value predictions over the whole batch, one minibatch at a time.

        A single pass over every step would materialize the full logit
        matrix (steps x actions in float32), which is gigabytes for a large
        iteration; chunking keeps the peak at one minibatch.
        """

        chunks: list[Tensor] = []
        with torch.no_grad():
            for start in range(0, observations.shape[0], self.config.minibatch_size):
                stop = start + self.config.minibatch_size
                _, values = self.network(observations[start:stop], masks[start:stop])
                chunks.append(values)
        return torch.cat(chunks)

    def _losses(
        self,
        observations: Tensor,
        masks: Tensor,
        actions: Tensor,
        returns: Tensor,
        advantages: Tensor,
    ) -> tuple[Tensor, Tensor, Tensor]:
        logits, values = self.network(observations, masks)
        log_probabilities = torch.log_softmax(logits, dim=-1)
        chosen = log_probabilities.gather(1, actions.unsqueeze(-1)).squeeze(-1)
        policy_loss = -(chosen * advantages).mean()
        value_loss = torch.nn.functional.mse_loss(values, returns)
        probabilities = log_probabilities.exp()
        # Masked actions have probability exactly zero; 0 * (-1e9) stays 0.
        entropy = -(probabilities * log_probabilities).sum(dim=-1).mean()
        return policy_loss, value_loss, entropy


def _explained_variance(predicted: np.ndarray, target: np.ndarray) -> float:
    variance = float(np.var(target))
    if variance == 0.0:
        return 0.0
    return 1.0 - float(np.var(target - predicted)) / variance
