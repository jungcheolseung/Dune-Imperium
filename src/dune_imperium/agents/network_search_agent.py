"""Determinized search guided by a trained policy/value network.

``RolloutAgent`` searches with three heuristic parts: the heuristic's
top-scoring candidates, heuristic playouts in every seat, and a hand-made
end-position value that prices a deck by printed card value. Against the
trained network it wins 9.4% of a one-against-three table, because all
three parts model the future with the heuristic's buy-heavy prior, which
the network has learned is wrong for this game
(docs/evaluation/m10-2026-09-22.md sections 3 and 4).

``NetworkSearchAgent`` keeps the determinization -- the honest part, which
re-deals every zone the seat cannot see -- and takes the other three from
the network: the candidates are its highest-logit legal actions, every
seat plays greedy network moves to the end of the round, and the leaf is
its value head. One search seat against three greedy copies of the same
checkpoint wins **58.0%** of 100 matches against a 25% null, mean rank
1.740 (section 12); the same network playing greedy is 25.0% by
construction. A searched decision costs about 2s against 4ms greedy.

Like a checkpoint seat, a search seat enters by file: ``search:<path>``.
"""

import random
from collections.abc import Sequence

import numpy as np
import torch

from dune_imperium.adapters.observation_encoding import encode_player_view
from dune_imperium.agents.determinize import determinize
from dune_imperium.agents.rollout_agent import position_value
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.observation import PlayerView
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.training.policy import without_undo_actions

# The defaults the 100-match cell measured (section 12). Worlds and
# candidates are the cost knobs: a decision plays ``rollouts * candidates``
# playouts, each to the end of the current round.
DEFAULT_ROLLOUTS = 4
DEFAULT_CANDIDATES = 3
DEFAULT_HORIZON_ROUNDS = 1


class NetworkSearchAgent:
    """Search a checkpoint's top actions by determinized network playouts."""

    def __init__(
        self,
        path: str,
        *,
        seed: int,
        rollouts: int = DEFAULT_ROLLOUTS,
        candidates: int = DEFAULT_CANDIDATES,
        horizon_rounds: int = DEFAULT_HORIZON_ROUNDS,
        max_rollout_steps: int = 3_000,
    ) -> None:
        if seed < 0:
            raise ValueError("agent seed must not be negative")
        if rollouts < 1 or candidates < 1 or horizon_rounds < 1:
            raise ValueError("rollouts, candidates, and horizon_rounds are positive")
        from dune_imperium.training.torch_policy import load_network_agent

        # The greedy agent owns the cached network and the catalog, and
        # answers decisions the search cannot branch from.
        self.greedy = load_network_agent(path)
        self.rollouts = rollouts
        self.candidates = candidates
        self.horizon_rounds = horizon_rounds
        self.max_rollout_steps = max_rollout_steps
        self._rng = random.Random(seed)
        self._engine = UprisingRulesEngine()
        self._unmasked = torch.ones(1, self.greedy.codec.size, dtype=torch.int8)

    # -- the network --------------------------------------------------------
    def _logits(
        self, view: PlayerView, legal: Sequence[DomainAction]
    ) -> np.ndarray:
        codec = self.greedy.codec
        index = [codec.encode(action) for action in legal]
        mask = np.zeros(codec.size, dtype=np.int8)
        mask[index] = 1
        observation = np.asarray(encode_player_view(view), dtype=np.int32)
        with torch.no_grad():
            logits, _ = self.greedy.network(
                torch.from_numpy(observation).unsqueeze(0),
                torch.from_numpy(mask).unsqueeze(0),
            )
        scores: np.ndarray = logits[0, index].numpy()
        return scores

    def _leaf_value(self, view: PlayerView) -> float:
        # The value head does not read the mask; an unmasked row is enough.
        observation = np.asarray(encode_player_view(view), dtype=np.int32)
        with torch.no_grad():
            _, value = self.greedy.network(
                torch.from_numpy(observation).unsqueeze(0), self._unmasked
            )
        return float(value[0])

    def _best(
        self, view: PlayerView, legal: Sequence[DomainAction]
    ) -> DomainAction:
        best: DomainAction = legal[int(np.argmax(self._logits(view, legal)))]
        return best

    # -- the agent contract -------------------------------------------------
    def choose_action(
        self,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        """Without a state to branch from, play the network greedily."""

        return self.greedy.choose_action(observation, legal_actions)

    def choose_action_with_state(
        self,
        state: GameState,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        """Search the network's best candidates by determinized playouts."""

        if not legal_actions:
            raise ValueError("a search agent requires at least one legal action")
        offered = without_undo_actions(legal_actions)
        if len(offered) == 1:
            return offered[0]
        order = np.argsort(-self._logits(observation, offered), kind="stable")
        candidates: list[DomainAction] = [
            offered[int(index)] for index in order[: self.candidates]
        ]
        if len(candidates) == 1:
            return candidates[0]
        seat = observation.player
        horizon = state.round_number + self.horizon_rounds
        totals = [0.0 for _ in candidates]
        for _ in range(self.rollouts):
            world = determinize(state, seat, self._rng)
            # Common random numbers: every candidate meets the same world
            # and the same chance stream, so they differ only by the action.
            chance_seed = self._rng.randrange(2**31)
            for index, action in enumerate(candidates):
                branched = self._engine.apply(world, action).state
                totals[index] += self._playout(branched, seat, horizon, chance_seed)
        best = max(totals)
        # Candidates are in the network's own order, so a tie keeps its pick.
        return candidates[totals.index(best)]

    # -- the search ---------------------------------------------------------
    def _playout(
        self, state: GameState, seat: int, horizon: int, chance_seed: int
    ) -> float:
        engine = self._engine
        chance = ChanceResolver(seed=chance_seed)
        for _ in range(self.max_rollout_steps):
            if state.phase is GamePhase.FINISHED or state.round_number >= horizon:
                break
            decision = engine.current_decision(state)
            if isinstance(decision, ChanceDecision):
                state = engine.apply(state, chance.resolve(decision)).state
                continue
            if not isinstance(decision, PlayerDecision):
                break
            actions = engine.legal_actions(state, decision.owner)
            if not actions:
                break
            offered = without_undo_actions(actions)
            action = (
                offered[0]
                if len(offered) == 1
                else self._best(engine.observe(state, decision.owner), offered)
            )
            state = engine.apply(state, action, legal_actions=actions).state
        if state.phase is GamePhase.FINISHED:
            # A finished game is read by official rank, which dominates any
            # asset difference (``position_value``).
            return position_value(state, seat)
        return self._leaf_value(self._engine.observe(state, seat))
