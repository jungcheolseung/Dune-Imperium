"""Trunk outputs a search decision has already computed.

A searched decision plays ``rollouts * candidates`` playouts, and every
playout step reads a network's trunk on the deciding seat's observation.
About 14% of those observations repeat one already read in the same
decision (the first 12 to 15 searched decisions of gate match 0, for the
play network and for the v151 entity student alike; ai-speedup,
2026-10-27): a seat's own steps right after the candidate look the same in
every world, as its view does not depend on how the hidden zones were
dealt. The trunk is a pure function of the weights and the observation, so
handing back the tensor computed the first time gives every head the same
bits it would read from a second pass, and every playout the same moves
and values.

``TrunkCache.hidden`` returns ``network.trunk`` of a batch of one, exactly
as the callers computed it: a ``[1, H]`` tensor (older-codec callers index
row 0, as they did). It keeps what it computes only inside ``decision()``,
which a search seat wraps around each decision it answers; the cache is
emptied when the decision begins and ends, so an entry never outlives the
weights it was read with, and it holds at most one decision's observations
(about a thousand, 23 KB each as keys). Outside a decision every call reads
the trunk afresh.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import numpy as np
import torch
from torch import Tensor

from dune_imperium.training.network import PolicyValueNetwork


class TrunkCache:
    """``network.trunk`` of observations already seen in a decision, per
    network."""

    __slots__ = ("_depth", "_hidden", "hits", "misses")

    def __init__(self) -> None:
        self._hidden: dict[tuple[int, bytes], Tensor] = {}
        self._depth = 0
        self.hits = 0
        self.misses = 0

    def __len__(self) -> int:
        return len(self._hidden)

    @contextmanager
    def decision(self) -> Iterator[None]:
        """Keep trunks for the duration of one decision (nested uses share
        the outermost one)."""

        if not self._depth:
            self._hidden.clear()
        self._depth += 1
        try:
            yield
        finally:
            self._depth -= 1
            if not self._depth:
                self._hidden.clear()

    def hidden(self, network: PolicyValueNetwork, observation: np.ndarray) -> Tensor:
        """``network.trunk`` of the one observation, ``[1, H]``, without
        gradient; inside a decision, computed once per network and
        observation."""

        if not self._depth:
            with torch.no_grad():
                return network.trunk(torch.from_numpy(observation).unsqueeze(0))
        # The network's identity, not its weights: nothing trains or
        # replaces a search seat's networks while it answers a decision.
        key = (id(network), observation.tobytes())
        found = self._hidden.get(key)
        if found is not None:
            self.hits += 1
            return found
        self.misses += 1
        with torch.no_grad():
            found = network.trunk(torch.from_numpy(observation).unsqueeze(0))
        self._hidden[key] = found
        return found
