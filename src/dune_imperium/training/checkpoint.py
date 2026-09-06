"""Checkpoints that pin the observation and action-codec versions.

A saved policy is only meaningful against the encoding it was trained on,
so every checkpoint records ``OBSERVATION_VERSION``, ``ACTION_CODEC_VERSION``,
the ruleset identifier (the catalog size differs between base and CHOAM)
and the network shape, and loading refuses a mismatch instead of silently
producing garbage actions.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.adapters.observation_encoding import (
    OBSERVATION_SIZE,
    OBSERVATION_VERSION,
)
from dune_imperium.training.network import PolicyValueNetwork

CHECKPOINT_FORMAT = 1


@dataclass(frozen=True, slots=True)
class CheckpointInfo:
    """What a checkpoint file says about itself."""

    ruleset: str
    action_size: int
    hidden: tuple[int, ...]
    iteration: int
    metadata: Mapping[str, Any]


def save_checkpoint(
    path: Path,
    network: PolicyValueNetwork,
    *,
    ruleset: str,
    iteration: int,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    """Write the network weights together with the encoding versions."""

    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "format": CHECKPOINT_FORMAT,
        "observation_version": OBSERVATION_VERSION,
        "observation_size": OBSERVATION_SIZE,
        "action_codec_version": ACTION_CODEC_VERSION,
        "ruleset": ruleset,
        "action_size": network.action_size,
        "hidden": list(network.hidden),
        "iteration": iteration,
        "metadata": dict(metadata or {}),
        "state_dict": {
            key: value.detach().cpu() for key, value in network.state_dict().items()
        },
    }
    torch.save(document, path)


def load_checkpoint(path: Path) -> tuple[PolicyValueNetwork, CheckpointInfo]:
    """Rebuild the network on the CPU and verify the encoding versions."""

    document = torch.load(path, map_location="cpu", weights_only=True)
    if document.get("format") != CHECKPOINT_FORMAT:
        raise ValueError(f"unsupported checkpoint format: {document.get('format')!r}")
    if document["observation_version"] != OBSERVATION_VERSION:
        raise ValueError(
            f"checkpoint observation v{document['observation_version']} does not "
            f"match the current v{OBSERVATION_VERSION}"
        )
    if document["action_codec_version"] != ACTION_CODEC_VERSION:
        raise ValueError(
            f"checkpoint codec v{document['action_codec_version']} does not match "
            f"the current v{ACTION_CODEC_VERSION}"
        )
    if document["observation_size"] != OBSERVATION_SIZE:
        raise ValueError("checkpoint observation size does not match the encoder")
    network = PolicyValueNetwork(
        int(document["action_size"]),
        observation_size=int(document["observation_size"]),
        hidden=tuple(int(width) for width in document["hidden"]),
    )
    network.load_state_dict(document["state_dict"])
    network.eval()
    info = CheckpointInfo(
        ruleset=str(document["ruleset"]),
        action_size=network.action_size,
        hidden=network.hidden,
        iteration=int(document["iteration"]),
        metadata=dict(document.get("metadata", {})),
    )
    return network, info
