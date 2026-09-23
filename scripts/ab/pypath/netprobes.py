"""Network probes: a trained policy with one decision family overridden (scratch).

A probe keeps the checkpoint's network and changes only the named decisions,
so an A/B against the plain checkpoint (2:2 mirror, ``--matches``,
``scripts/ab/paired.py``) measures that family alone. Registry kinds are
factories of a seed, so the checkpoint comes from ``DUNE_PROBE_CKPT``;
``sitecustomize.py`` registers the probes only when it is set.

    DUNE_PROBE_CKPT=checkpoints/2026-09-22/exploit/champion-5081.pt \\
    PYTHONPATH=scripts/ab/pypath uv run dune-imperium-tournament \\
        --agents net_faction_early2,checkpoint:$DUNE_PROBE_CKPT ...

``net_faction_early<cap>`` tests the players' tip "buy one or two early
Faction-access cards" (community tip C1.6, the owner's thin-strong-deck H-deck
by function rather than cost; docs/player-tips-for-training.md 7.7-7.8): in
rounds 1-3, a Reveal-turn buy decision that offers a card with a Faction Agent
icon takes one -- the network's highest-logit such card -- until the seat has
bought ``cap`` of them (its own voluntary Faction buys count). Every other
decision is the network's.
"""

from __future__ import annotations

import os
from collections.abc import Sequence

import numpy as np
import torch

from dune_imperium.adapters.observation_encoding import encode_player_view
from dune_imperium.content.uprising.imperium import imperium_card_for_instance
from dune_imperium.content.uprising.reserve import RESERVE_STACKS_BY_ID
from dune_imperium.content.uprising.types import AgentIcon
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.observation import PlayerView
from dune_imperium.training.torch_policy import NetworkAgent, load_network_agent

FACTION_ICONS = frozenset(
    (
        AgentIcon.EMPEROR,
        AgentIcon.SPACING_GUILD,
        AgentIcon.BENE_GESSERIT,
        AgentIcon.FREMEN,
    )
)


def is_faction_buy(action: DomainAction) -> bool:
    """A Reveal-turn buy of a card that prints a Faction Agent icon."""

    arguments = dict(action.arguments)
    if action.action_id in ("acquire_imperium", "acquire_manipulated_imperium"):
        card = imperium_card_for_instance(str(arguments["instance_id"]))
    elif action.action_id == "acquire_reserve":
        card = RESERVE_STACKS_BY_ID[str(arguments["card_id"])]
    else:
        return False
    return bool(FACTION_ICONS & set(card.agent_icons))


def network_logits(
    agent: NetworkAgent, view: PlayerView, legal: Sequence[DomainAction]
) -> np.ndarray:
    """The network's logits for ``legal`` (same forward pass as greedy play)."""

    index = [agent.codec.encode(action) for action in legal]
    mask = np.zeros(agent.codec.size, dtype=np.int8)
    mask[index] = 1
    observation = np.asarray(encode_player_view(view), dtype=np.int32)
    with torch.no_grad():
        logits, _ = agent.network(
            torch.from_numpy(observation).unsqueeze(0),
            torch.from_numpy(mask).unsqueeze(0),
        )
    scores: np.ndarray = logits[0, index].numpy()
    return scores


class FactionEarlyBuy:
    """The checkpoint, but it buys up to ``cap`` Faction cards in rounds 1-3."""

    def __init__(self, path: str, cap: int, last_round: int = 3) -> None:
        self.inner = load_network_agent(path)
        self.cap = cap
        self.last_round = last_round
        self.faction_buys = 0
        self.forced = 0

    def choose_action(
        self, observation: PlayerView, legal_actions: tuple[DomainAction, ...]
    ) -> DomainAction:
        choice = self.inner.choose_action(observation, legal_actions)
        if is_faction_buy(choice):
            self.faction_buys += 1
            return choice
        if observation.round_number > self.last_round or self.faction_buys >= self.cap:
            return choice
        targets = [action for action in legal_actions if is_faction_buy(action)]
        if not targets:
            return choice
        scores = network_logits(self.inner, observation, targets)
        self.faction_buys += 1
        self.forced += 1
        return targets[int(np.argmax(scores))]


PROBES = {
    "net_faction_early1": lambda path, seed: FactionEarlyBuy(path, cap=1),
    "net_faction_early2": lambda path, seed: FactionEarlyBuy(path, cap=2),
}


def register(registry) -> None:  # type: ignore[no-untyped-def]
    path = os.environ.get("DUNE_PROBE_CKPT")
    if not path:
        return
    for name, factory in PROBES.items():
        registry.BASELINE_AGENT_FACTORIES[name] = (
            lambda f: lambda seed: f(path, seed)
        )(factory)
