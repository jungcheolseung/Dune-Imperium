"""Masked policy/value network over the versioned observation encoding.

The network reads the flat integer observation (``OBSERVATION_SIZE`` values:
slot indices, counts, resources, flags), compresses it with ``log1p`` so
counts and resource totals stay on a comparable scale, and feeds a small
MLP whose two heads produce one logit per catalog action and one state
value. Illegal actions are masked to a large negative logit, so their
probability under softmax is exactly zero and a policy can never sample
them. Seats are egocentric in the encoding, so one network serves every
seat.
"""

from collections.abc import Sequence

import torch
from torch import Tensor, nn

from dune_imperium.adapters.observation_encoding import OBSERVATION_SIZE

MASKED_LOGIT = -1.0e9
DEFAULT_HIDDEN: tuple[int, ...] = (512, 512)


class PolicyValueNetwork(nn.Module):
    """MLP with a masked action head and a scalar value head."""

    def __init__(
        self,
        action_size: int,
        *,
        observation_size: int = OBSERVATION_SIZE,
        hidden: Sequence[int] = DEFAULT_HIDDEN,
    ) -> None:
        super().__init__()
        if action_size < 1 or observation_size < 1:
            raise ValueError("action and observation sizes must be positive")
        if not hidden or any(width < 1 for width in hidden):
            raise ValueError("hidden widths must be positive")
        self.action_size = action_size
        self.observation_size = observation_size
        self.hidden = tuple(hidden)
        layers: list[nn.Module] = []
        width = observation_size
        for next_width in hidden:
            layers.append(nn.Linear(width, next_width))
            layers.append(nn.ReLU())
            width = next_width
        self.body = nn.Sequential(*layers)
        self.policy_head = nn.Linear(width, action_size)
        self.value_head = nn.Linear(width, 1)

    def forward(self, observations: Tensor, masks: Tensor) -> tuple[Tensor, Tensor]:
        """Return masked action logits ``[B, A]`` and values ``[B]``."""

        features = torch.log1p(observations.to(torch.float32).clamp(min=0.0))
        hidden = self.body(features)
        logits = self.policy_head(hidden).masked_fill(masks == 0, MASKED_LOGIT)
        values = self.value_head(hidden).squeeze(-1)
        return logits, values
