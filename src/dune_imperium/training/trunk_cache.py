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
weights it was read with, and it holds at most one decision's observations:
about a thousand, 10.7 KB each as keys, in a default decision, and never more
than ``LIMIT`` (a decision whose playouts ran long reads the rest afresh).
Outside a decision every call reads the trunk afresh.

An observation is keyed by its dtype and ``bytes_key`` of its bytes
(``observation_keys``, 2026-11-11 engine speed, seat stage): equal exactly
when the dtype and the bytes are, as the bytes themselves were, at a
quarter of their 42.7 KB. A search seat hands its playout steps' views in as
``EncodedObservation``s (``hidden_of``, ``hidden_batch_of``): their keys are
the encoder's bytes, and the int32 arrays are built only for the trunks
read afresh.
"""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager

import numpy as np
import torch
from torch import Tensor

from dune_imperium.training.network import PolicyValueNetwork
from dune_imperium.training.observation_keys import EncodedObservation, stacked

# Entries one decision keeps at most: about 44 MB of keys. A default
# decision kept 1,058 at its peak (8 worlds x 5 candidates, horizon 1).
LIMIT = 4096

# A kept trunk's key: the network's identity, the observation's dtype, and
# its ``bytes_key``.
type _Key = tuple[int, str, str, bytes]


class TrunkCache:
    """``network.trunk`` of observations already seen in a decision, per
    network."""

    __slots__ = ("_depth", "_hidden", "hits", "misses")

    def __init__(self) -> None:
        self._hidden: dict[_Key, Tensor] = {}
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

        return self.hidden_of(network, EncodedObservation.of_array(observation))

    def hidden_of(
        self, network: PolicyValueNetwork, observation: EncodedObservation
    ) -> Tensor:
        """``hidden`` of an encoded observation."""

        if not self._depth:
            with torch.no_grad():
                return network.trunk(torch.from_numpy(observation.array()).unsqueeze(0))
        # The network's identity, not its weights: nothing trains or
        # replaces a search seat's networks while it answers a decision.
        key = (id(network), observation.dtype(), *observation.key())
        found = self._hidden.get(key)
        if found is not None:
            self.hits += 1
            return found
        self.misses += 1
        with torch.no_grad():
            found = network.trunk(torch.from_numpy(observation.array()).unsqueeze(0))
        if len(self._hidden) < LIMIT:
            self._hidden[key] = found
        return found

    def hidden_batch(
        self, network: PolicyValueNetwork, observations: Sequence[np.ndarray]
    ) -> Tensor:
        """``network.trunk`` of several observations, ``[B, H]``, without
        gradient: the ones already read come from the cache, the others in
        one batched pass over each distinct observation (a search seat's
        ``batch_playouts``). A batched pass rounds differently from a batch
        of one (about 1e-6), so a trunk is the same bits only within the
        path that computed it first."""

        return self.hidden_batch_of(
            network, [EncodedObservation.of_array(o) for o in observations]
        )

    def hidden_batch_of(
        self, network: PolicyValueNetwork, observations: Sequence[EncodedObservation]
    ) -> Tensor:
        """``hidden_batch`` of encoded observations."""

        rows: list[Tensor | None] = []
        missing: dict[_Key, list[int]] = {}
        for position, observation in enumerate(observations):
            key = (id(network), observation.dtype(), *observation.key())
            found = self._hidden.get(key) if self._depth else None
            if found is not None:
                self.hits += 1
            else:
                missing.setdefault(key, []).append(position)
            rows.append(found)
        if missing:
            first = [positions[0] for positions in missing.values()]
            batch = torch.from_numpy(stacked([observations[i] for i in first]))
            with torch.no_grad():
                computed = network.trunk(batch)
            for index, (key, positions) in enumerate(missing.items()):
                row = computed[index : index + 1]
                if self._depth:
                    self.misses += 1
                    if len(self._hidden) < LIMIT:
                        self._hidden[key] = row
                for position in positions:
                    rows[position] = row
        filled = [row for row in rows if row is not None]
        assert len(filled) == len(observations)
        return torch.cat(filled)
