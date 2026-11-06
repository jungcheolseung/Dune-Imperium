"""Probes of what a trained network reads (docs/entity-network-plan.md section 4).

Cheap yardsticks for broad changes to the network, next to the problem
suites (``records.problems``):

- **Value sensitivity.** The value head's change when one thing changes in
  the observing seat's own view: 3 more spice or Solari, 1 more water, 2
  troops moved from supply to garrison, 1 more Victory Point, the Family
  Atomics token spent. The search scores sibling positions with this head,
  so it tells them apart only as far as these differences show. Measured
  2026-10-13 against outcomes, the token is worth about 1.2pp of win share
  (0.016 on the head's scale, a win 1 and a loss -1/3), which the trained
  networks read as about a tenth of that.
- **Row reading.** How much the value and the policy over the offered moves
  change when the view's Imperium Row is swapped for another position's.
  The MLP reads a Row card's identity as a magnitude, so it should barely
  move (docs/entity-network-plan.md section 1).
- **Family Atomics timing.** The round in which four greedy copies of a
  network spend the token: the trained networks did in round 1 in every game,
  the app AI's rule in its own Reveal turns across the game.

Positions come from games of four app_ai seats, so every network is probed
on the same views.
"""

from collections.abc import Callable, Iterable, Sequence
from copy import replace
from dataclasses import dataclass
from statistics import fmean, stdev

import numpy as np
import torch

from dune_imperium.adapters.observation_encoding import encode_player_view
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.app_ai.family_atomics import FAMILY_ATOMICS_ACTION
from dune_imperium.agents.registry import make_agent
from dune_imperium.config import RulesetConfig
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.observation import PlayerView, PublicPlayerView
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game
from dune_imperium.training.policy import without_undo_actions
from dune_imperium.training.torch_policy import NetworkAgent

_BATCH = 256


@dataclass(frozen=True, slots=True)
class ProbePosition:
    """One decision of an app_ai game: the view and the moves offered."""

    state: GameState
    view: PlayerView
    offered: tuple[DomainAction, ...]


@dataclass(frozen=True, slots=True)
class Estimate:
    mean: float
    error: float
    count: int


def sample_positions(
    config: RulesetConfig, seeds: Iterable[int], every: int = 10
) -> list[ProbePosition]:
    """Every ``every``-th decision offering a choice, in app_ai games."""

    engine = UprisingRulesEngine()
    positions: list[ProbePosition] = []
    for seed in seeds:
        state = engine.reset(config, seed)
        chance = ChanceResolver(seed=seed)
        agents = [AppAIAgent(seed * 10 + seat) for seat in range(config.players)]
        count = 0
        while state.phase is not GamePhase.FINISHED:
            decision = engine.current_decision(state)
            if isinstance(decision, ChanceDecision):
                state = engine.apply(state, chance.resolve(decision)).state
                continue
            assert isinstance(decision, PlayerDecision)
            seat = decision.owner
            legal = engine.legal_actions(state, seat)
            view = engine.observe(state, seat)
            offered = without_undo_actions(legal)
            count += 1
            if count % every == 0 and len(offered) >= 2:
                positions.append(ProbePosition(state, view, offered))
            choice = agents[seat].choose_action_with_state(state, view, legal)
            state = engine.apply(state, choice, legal_actions=legal).state
    return positions


def _encode(views: Sequence[PlayerView]) -> torch.Tensor:
    return torch.from_numpy(
        np.stack(
            [np.asarray(encode_player_view(view), dtype=np.int32) for view in views]
        )
    )


def values(agent: NetworkAgent, views: Sequence[PlayerView]) -> np.ndarray:
    """The value head on each view."""

    network = agent.network
    network.eval()
    parts = []
    with torch.no_grad():
        for start in range(0, len(views), _BATCH):
            parts.append(network.values(_encode(views[start : start + _BATCH])).numpy())
    return np.concatenate(parts) if parts else np.zeros(0)


def policy(
    agent: NetworkAgent, view: PlayerView, offered: Sequence[DomainAction]
) -> np.ndarray:
    """The network's probabilities over ``offered``."""

    network = agent.network
    index = torch.tensor([agent.codec.encode(action) for action in offered])
    with torch.no_grad():
        logits = network.action_logits(network.trunk(_encode([view])), index)[0]
    probabilities: np.ndarray = torch.softmax(logits, dim=0).numpy()
    return probabilities


def _own(view: PlayerView) -> PublicPlayerView:
    return next(player for player in view.players if player.player == view.player)


def _with_own(view: PlayerView, player: PublicPlayerView) -> PlayerView:
    players = tuple(player if p.player == view.player else p for p in view.players)
    return replace(view, players=players)


def _resource(name: str, amount: int) -> Callable[[PlayerView], PlayerView | None]:
    def change(view: PlayerView) -> PlayerView | None:
        own = _own(view)
        resources = replace(
            own.resources, **{name: getattr(own.resources, name) + amount}
        )
        return _with_own(view, replace(own, resources=resources))

    return change


def _garrison(view: PlayerView) -> PlayerView | None:
    own = _own(view)
    if own.troops_supply < 2:
        return None
    return _with_own(
        view,
        replace(
            own,
            troops_supply=own.troops_supply - 2,
            troops_garrison=own.troops_garrison + 2,
        ),
    )


def _victory_point(view: PlayerView) -> PlayerView | None:
    own = _own(view)
    return _with_own(view, replace(own, victory_points=own.victory_points + 1))


def _atomics_spent(view: PlayerView) -> PlayerView | None:
    own = _own(view)
    if not own.family_atomics:
        return None
    return _with_own(view, replace(own, family_atomics=False))


# Each change, and whether it should raise the value (the token spent should
# lower it).
VALUE_CHANGES: dict[str, Callable[[PlayerView], PlayerView | None]] = {
    "spice +3": _resource("spice", 3),
    "solari +3": _resource("solari", 3),
    "water +1": _resource("water", 1),
    "troops to garrison +2": _garrison,
    "victory point +1": _victory_point,
    "family atomics spent": _atomics_spent,
}


def _estimate(differences: Sequence[float]) -> Estimate:
    if not differences:
        return Estimate(0.0, 0.0, 0)
    count = len(differences)
    error = stdev(differences) / count**0.5 if count > 1 else 0.0
    return Estimate(fmean(differences), error, len(differences))


def value_sensitivity(
    agent: NetworkAgent, positions: Sequence[ProbePosition]
) -> dict[str, Estimate]:
    """Mean value change (changed minus base) for every ``VALUE_CHANGES`` entry."""

    report: dict[str, Estimate] = {}
    for name, change in VALUE_CHANGES.items():
        pairs = [
            (position.view, changed)
            for position in positions
            if (changed := change(position.view)) is not None
        ]
        if not pairs:
            report[name] = _estimate([])
            continue
        base = values(agent, [view for view, _ in pairs])
        moved = values(agent, [view for _, view in pairs])
        report[name] = _estimate([float(x) for x in moved - base])
    return report


def row_sensitivity(
    agent: NetworkAgent, positions: Sequence[ProbePosition]
) -> dict[str, Estimate]:
    """Value and policy change when each view's Imperium Row is swapped.

    Every view with a full Row takes the Row of the view half the list away
    (another game or round), skipping a swap that leaves the Row unchanged.
    ``value`` is the mean absolute value change, ``policy`` the mean total
    variation distance between the policies over the offered moves.
    """

    full = [p for p in positions if len(p.view.imperium_row) == 5]
    value_moves: list[float] = []
    policy_moves: list[float] = []
    for index, position in enumerate(full):
        other = full[(index + len(full) // 2) % len(full)].view.imperium_row
        if other == position.view.imperium_row:
            continue
        swapped = replace(position.view, imperium_row=other)
        base, moved = values(agent, [position.view, swapped])
        value_moves.append(abs(float(moved - base)))
        before = policy(agent, position.view, position.offered)
        after = policy(agent, swapped, position.offered)
        policy_moves.append(0.5 * float(np.abs(before - after).sum()))
    return {"value": _estimate(value_moves), "policy": _estimate(policy_moves)}


@dataclass(frozen=True, slots=True)
class AtomicsTiming:
    seats: int
    spent: int
    round_one: int
    in_reveal: int
    rounds: tuple[int, ...]


class _Watch:
    """A seat that notes the round in which it spends Family Atomics."""

    def __init__(self, inner: object, notes: list[tuple[int, bool]]) -> None:
        self.inner, self.notes = inner, notes

    def choose_action(
        self, observation: PlayerView, legal_actions: tuple[DomainAction, ...]
    ) -> DomainAction:
        action: DomainAction = self.inner.choose_action(observation, legal_actions)  # type: ignore[attr-defined]
        return self._note(observation, legal_actions, action)

    def choose_action_with_state(
        self,
        state: GameState,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        inner = self.inner
        if hasattr(inner, "choose_action_with_state"):
            action: DomainAction = inner.choose_action_with_state(
                state, observation, legal_actions
            )
        else:
            action = inner.choose_action(observation, legal_actions)  # type: ignore[attr-defined]
        return self._note(observation, legal_actions, action)

    def _note(
        self,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
        action: DomainAction,
    ) -> DomainAction:
        if action.action_id == FAMILY_ATOMICS_ACTION:
            offered = {candidate.action_id for candidate in legal_actions}
            in_reveal = bool({"finish_reveal", "acquire_imperium"} & offered)
            self.notes.append((observation.round_number, in_reveal))
        return action


def atomics_timing(
    kind: str, config: RulesetConfig, seeds: Iterable[int]
) -> AtomicsTiming:
    """Where four ``kind`` seats spend Family Atomics, over one game a seed."""

    notes: list[tuple[int, bool]] = []
    seats = 0
    engine = UprisingRulesEngine()
    for seed in seeds:
        agents = [
            _Watch(make_agent(kind, seed * 10 + seat, config), notes)
            for seat in range(config.players)
        ]
        run_policy_game(engine, config, seed, agents)
        seats += config.players
    rounds = tuple(sorted(round_number for round_number, _ in notes))
    return AtomicsTiming(
        seats=seats,
        spent=len(notes),
        round_one=sum(1 for round_number in rounds if round_number == 1),
        in_reveal=sum(1 for _, in_reveal in notes if in_reveal),
        rounds=rounds,
    )
