"""Masked policy/value network over the versioned observation encoding.

The network reads the flat integer observation (``OBSERVATION_SIZE`` values:
slot indices, counts, resources, flags), compresses it with ``log1p`` so
counts and resource totals stay on a comparable scale, and feeds a small
MLP whose two heads produce one logit per catalog action and one state
value. Illegal actions are masked to a large negative logit, so their
probability under softmax is exactly zero and a policy can never sample
them. Seats are egocentric in the encoding, so one network serves every
seat.

``MlpSlotsNetwork`` (architecture ``mlp_slots``) adds a one-hot path for
the observation's identity columns (``training.slots``) into the first
layer's pre-activation. Its embedding starts at zero, so a widened copy of
a trained MLP computes exactly the same function until it is trained.
"""

from collections.abc import Mapping, Sequence
from typing import Any

import torch
from torch import Tensor, nn

from dune_imperium.adapters.observation_encoding import OBSERVATION_SIZE
from dune_imperium.training.slots import (
    PAD_ROW,
    SLOT_KEYS,
    SLOT_VERSION,
    VALUE_RANGE,
    lookup_tables,
)

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

        hidden = self.trunk(observations)
        logits = self.policy_head(hidden).masked_fill(masks == 0, MASKED_LOGIT)
        values = self.value_head(hidden).squeeze(-1)
        return logits, values

    def trunk(self, observations: Tensor) -> Tensor:
        """Return the hidden features ``[B, H]`` both heads read."""

        features = torch.log1p(observations.to(torch.float32).clamp(min=0.0))
        hidden: Tensor = self.body(features)
        return hidden

    def arch_spec(self) -> dict[str, Any]:
        """The architecture as a plain document (checkpoints, workers)."""

        return {"kind": "mlp", "hidden": list(self.hidden)}

    def action_logits(self, hidden: Tensor, actions: Tensor) -> Tensor:
        """Return unmasked logits ``[B, K]`` of the catalog indices ``actions``.

        The policy head is almost all of the network's weights (one row per
        catalog action), so a caller that needs only a decision's few legal
        actions reads those rows instead of computing every logit.
        """

        return nn.functional.linear(
            hidden, self.policy_head.weight[actions], self.policy_head.bias[actions]
        )


class MlpSlotsNetwork(PolicyValueNetwork):
    """The MLP plus a zero-initialised embedding of the identity columns.

    ``trunk`` adds ``slot_embed`` (one row per ``SLOT_KEYS`` entry, summed
    over an observation's active rows) to the first linear layer's output
    before its activation. ``slot_embed`` is registered after the heads, so
    the parameters the MLP already had keep their optimizer indices and the
    embedding is parameter ``2 * len(hidden) + 4``. The column and row
    tables are non-persistent buffers rebuilt from ``training.slots``; the
    state dict holds weights only.
    """

    def __init__(
        self,
        action_size: int,
        *,
        observation_size: int = OBSERVATION_SIZE,
        hidden: Sequence[int] = DEFAULT_HIDDEN,
    ) -> None:
        super().__init__(action_size, observation_size=observation_size, hidden=hidden)
        if observation_size != OBSERVATION_SIZE:
            raise ValueError("the slot table is defined on the current observation")
        self.slot_embed = nn.EmbeddingBag(
            len(SLOT_KEYS) + 1, self.hidden[0], mode="sum", padding_idx=PAD_ROW
        )
        nn.init.zeros_(self.slot_embed.weight)
        columns, table = lookup_tables()
        self.slot_columns: Tensor
        self.slot_table: Tensor
        self.slot_bases: Tensor
        self.register_buffer("slot_columns", columns, persistent=False)
        self.register_buffer("slot_table", table, persistent=False)
        self.register_buffer(
            "slot_bases",
            torch.arange(columns.shape[0], dtype=torch.long) * VALUE_RANGE,
            persistent=False,
        )

    def arch_spec(self) -> dict[str, Any]:
        return {
            "kind": "mlp_slots",
            "hidden": list(self.hidden),
            "slot_version": SLOT_VERSION,
        }

    def slot_rows(self, observations: Tensor) -> Tensor:
        """Embedding rows ``[B, C]`` of each observation (``PAD_ROW`` when idle)."""

        values = observations.index_select(1, self.slot_columns).long()
        values = values.clamp(0, VALUE_RANGE - 1)
        rows: Tensor = self.slot_table[values + self.slot_bases]
        return rows

    def trunk(self, observations: Tensor) -> Tensor:
        features = torch.log1p(observations.to(torch.float32).clamp(min=0.0))
        hidden: Tensor = self.body[0](features) + self.slot_embed(
            self.slot_rows(observations)
        )
        for layer in list(self.body)[1:]:
            hidden = layer(hidden)
        return hidden


def build_network(arch: Mapping[str, Any], action_size: int) -> PolicyValueNetwork:
    """Build the network an ``arch_spec`` document describes (fresh weights)."""

    kind = arch.get("kind")
    hidden = tuple(int(width) for width in arch["hidden"])
    if kind == "mlp":
        return PolicyValueNetwork(action_size, hidden=hidden)
    if kind == "mlp_slots":
        if arch.get("slot_version") != SLOT_VERSION:
            raise ValueError(
                f"slot table v{arch.get('slot_version')} does not match the "
                f"current v{SLOT_VERSION}"
            )
        return MlpSlotsNetwork(action_size, hidden=hidden)
    raise ValueError(f"unknown network architecture: {kind!r}")
