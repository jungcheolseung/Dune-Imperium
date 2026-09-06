"""Network-backed policies: the batched self-play policy and the tournament agent.

``TorchBatchPolicy`` implements ``BatchPolicy`` for data collection: one
forward pass per batch, then a seeded sample from the masked distribution
(or the greedy action for evaluation). ``NetworkAgent`` wraps a checkpoint
in the plain ``Agent`` contract so a trained policy enters tournaments by
name: ``checkpoint:<path>`` resolves through ``agents.registry.make_agent``,
which lets tournament worker processes load the file themselves.

Both modes use a cycle guard: several legal actions are reversible
(deploy/withdraw troops under OQ-029, defer/resume a Reveal choice), so a
deterministic argmax that prefers the reversing pair never finishes the
turn, and a sampling policy that learns to like the pair inflates every
game with loops that carry no information about the outcome.
``_CycleGuard`` remembers which actions were already taken at an identical
observation within the current round (the observation carries no revision
counter, so a reversed move reproduces the same bytes) and masks them out
on the next visit, so play always makes progress.
"""

import os
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

import numpy as np
import torch

from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.adapters.observation_encoding import encode_player_view
from dune_imperium.config import RulesetConfig
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.observation import PlayerView
from dune_imperium.training.checkpoint import load_checkpoint
from dune_imperium.training.network import MASKED_LOGIT, PolicyValueNetwork
from dune_imperium.training.policy import PolicyRequest


class _CycleGuard:
    """Mask actions already taken at an identical observation this round."""

    def __init__(self) -> None:
        self._round = -1
        self._taken: dict[bytes, set[int]] = {}

    def restrict(
        self, round_number: int, observation: np.ndarray, logits: torch.Tensor
    ) -> torch.Tensor:
        """Mask the actions already taken at this observation this round.

        Returns the logits unchanged when every legal action was already
        taken here, so a decision never loses its whole legal set.
        """

        if round_number != self._round:
            self._round = round_number
            self._taken.clear()
        taken = self._taken.get(observation.tobytes())
        if not taken:
            return logits
        candidate = logits.clone()
        candidate[list(taken)] = MASKED_LOGIT
        if bool((candidate > MASKED_LOGIT / 2).any()):
            return candidate
        return logits

    def record(self, observation: np.ndarray, index: int) -> None:
        self._taken.setdefault(observation.tobytes(), set()).add(index)

    def greedy(
        self, round_number: int, observation: np.ndarray, logits: torch.Tensor
    ) -> int:
        """Return the argmax over legal actions not yet taken here."""

        index = int(self.restrict(round_number, observation, logits).argmax().item())
        self.record(observation, index)
        return index


def resolve_device(name: str) -> torch.device:
    """Map ``cpu`` / ``mps`` / ``cuda`` / ``auto`` to an available device."""

    if name == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")
    device = torch.device(name)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise ValueError("cuda requested but not available")
    if device.type == "mps" and not torch.backends.mps.is_available():
        raise ValueError("mps requested but not available")
    return device


class TorchBatchPolicy:
    """Answer self-play requests with one masked forward pass per batch."""

    def __init__(
        self,
        network: PolicyValueNetwork,
        device: torch.device,
        *,
        seed: int,
        sample: bool = True,
        temperature: float = 1.0,
    ) -> None:
        if seed < 0:
            raise ValueError("policy seed must not be negative")
        if temperature <= 0.0:
            raise ValueError("temperature must be positive")
        self.network = network
        self.device = device
        self.sample = sample
        self.temperature = temperature
        self._generator = torch.Generator().manual_seed(seed)
        self._guards: dict[tuple[int, int], _CycleGuard] = {}

    def act(self, requests: Sequence[PolicyRequest]) -> Sequence[int]:
        if not requests:
            return ()
        observations = torch.from_numpy(
            np.stack([request.observation for request in requests])
        ).to(self.device)
        masks = torch.from_numpy(np.stack([request.mask for request in requests])).to(
            self.device
        )
        self.network.eval()
        with torch.no_grad():
            logits, _ = self.network(observations, masks)
        logits = logits.to("cpu")
        answers: list[int] = []
        if self.sample:
            # The guard applies to sampling too: an action already taken at
            # this exact observation this round is a reversal loop, which
            # costs collection time and teaches nothing about the outcome.
            restricted = torch.stack(
                [
                    self._guard(request).restrict(
                        request.view.round_number, request.observation, logits[row]
                    )
                    for row, request in enumerate(requests)
                ]
            )
            probabilities = torch.softmax(restricted / self.temperature, dim=-1)
            chosen = torch.multinomial(probabilities, 1, generator=self._generator)
            for request, index in zip(
                requests, chosen.squeeze(-1).tolist(), strict=True
            ):
                self._guard(request).record(request.observation, int(index))
                answers.append(int(index))
            return tuple(answers)
        for row, request in enumerate(requests):
            answers.append(
                self._guard(request).greedy(
                    request.view.round_number, request.observation, logits[row]
                )
            )
        return tuple(answers)

    def _guard(self, request: PolicyRequest) -> _CycleGuard:
        return self._guards.setdefault((request.game, request.seat), _CycleGuard())


class NetworkAgent:
    """Greedy single-decision agent over a policy network (tournament use)."""

    def __init__(self, network: PolicyValueNetwork, config: RulesetConfig) -> None:
        self.network = network
        self.codec = ActionCodec(config)
        if self.codec.size != network.action_size:
            raise ValueError(
                f"network action size {network.action_size} does not match the "
                f"{config.identifier} catalog ({self.codec.size})"
            )
        self.network.eval()
        self._guard = _CycleGuard()

    def choose_action(
        self,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        if not legal_actions:
            raise ValueError("a network agent requires at least one legal action")
        legal_indices = tuple(self.codec.encode(action) for action in legal_actions)
        mask = np.zeros(self.codec.size, dtype=np.int8)
        mask[list(legal_indices)] = 1
        encoded = np.asarray(encode_player_view(observation), dtype=np.int32)
        with torch.no_grad():
            logits, _ = self.network(
                torch.from_numpy(encoded).unsqueeze(0),
                torch.from_numpy(mask).unsqueeze(0),
            )
        index = self._guard.greedy(observation.round_number, encoded, logits[0])
        return legal_actions[legal_indices.index(index)]


@lru_cache(maxsize=8)
def _cached_network(path: str, modified: float) -> tuple[PolicyValueNetwork, str]:
    del modified  # part of the cache key so a rewritten file reloads
    network, info = load_checkpoint(Path(path))
    return network, info.ruleset


def load_network_agent(path: str) -> NetworkAgent:
    """Build a greedy agent from a checkpoint file, cached per process."""

    resolved = str(Path(path).expanduser())
    network, ruleset = _cached_network(resolved, os.path.getmtime(resolved))
    config = RulesetConfig(
        choam_module="choam" in ruleset, promo_cards="+promo" in ruleset
    )
    return NetworkAgent(network, config)
