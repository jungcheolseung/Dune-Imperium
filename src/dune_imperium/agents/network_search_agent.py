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
construction. That cell paid about 2s per searched decision; reading only
the legal rows of the policy head takes a single-threaded decision from
0.53s to 0.14s with the same choices.

By default the seat leaves one kind of decision to the greedy network:
ordering an Agent turn's effects (``search_effect_order``). Over 300 new
matches paired deal for deal with the full search, both guarded, that seat
wins 61.7% against 64.3% -- a difference of -2.7pp [-10.0, +5.0], mean
rank +0.06 [-0.08, +0.20] -- at 18s instead of 45s a match (section 13).

Like greedy play, the search keeps a cycle guard (``_Taken``), both for its
own decisions and inside every playout. Without one a search seat stalled a
tournament match on ``switch_graft_card``: the network ranked the switch
first, so the switch playouts looped to ``max_rollout_steps``, and the value
head rated that stalled mid-turn position above finishing the turn, so the
seat switched forever (docs/evaluation/m10-2026-09-22.md section 13).

Like a checkpoint seat, a search seat enters by file: ``search:<path>``.
"""

import random
from collections.abc import Sequence

import numpy as np
import torch

from dune_imperium.adapters.observation_encoding import encode_player_view
from dune_imperium.adapters.pettingzoo_env import LOSER_REWARD, WINNER_REWARD
from dune_imperium.agents.determinize import determinize
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.observation import PlayerView
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.endgame import final_standings
from dune_imperium.rules.frames import FrameKind
from dune_imperium.training.policy import without_undo_actions

# The worlds, candidates and horizon the 100-match cell measured (section
# 12). Worlds and candidates are the cost knobs: a decision plays
# ``rollouts * candidates`` playouts, each to the end of the current round.
# One world, and two worlds on top of the effect-ordering switch below, both
# lost measurably against these defaults (section 13).
DEFAULT_ROLLOUTS = 4
DEFAULT_CANDIDATES = 3
DEFAULT_HORIZON_ROUNDS = 1
# Ordering an Agent turn's effects is half of all searched decisions and
# 63% of the search time, yet the search overrides the network there least
# (10% against 22.6% overall), and leaving it to the network cost nothing
# measurable (docs/evaluation/m10-2026-09-22.md section 13).
DEFAULT_SEARCH_EFFECT_ORDER = False


class _Taken:
    """Moves a seat already made at an identical decision this round.

    The greedy ``NetworkAgent`` keeps the same guard (``torch_policy``):
    reversible pairs such as ``defer_reveal_choice``/``resume_reveal_choice``
    return a seat to an identical observation and legal set, and an argmax
    -- or a search that keeps preferring the same move there -- never
    finishes the turn. The key is the observation *and* the legal set, so
    two different decisions that happen to share an observation never mask
    each other; only a true repeat is steered to an untried move. Such
    repeats are common inside playouts: rerunning 100 matches with the guard
    changed 38 of them and took the slowest from 487s to 70s, at the same
    strength (section 13).
    """

    def __init__(self) -> None:
        self._round = -1
        self._taken: dict[tuple[object, ...], set[DomainAction]] = {}
        self.breaks = 0

    def untried(
        self,
        round_number: int,
        seat: int,
        encoded: np.ndarray,
        offered: Sequence[DomainAction],
    ) -> tuple[tuple[object, ...], Sequence[DomainAction]]:
        """Return the decision's key and its moves not yet made here.

        Every move is returned again once all of them have been made.
        """

        if round_number != self._round:
            self._round = round_number
            self._taken.clear()
        key = (seat, encoded.tobytes(), tuple(offered))
        taken = self._taken.get(key)
        if not taken:
            return key, offered
        fresh = [action for action in offered if action not in taken]
        if not fresh:
            return key, offered
        self.breaks += 1
        return key, fresh

    def record(self, key: tuple[object, ...], action: DomainAction) -> None:
        self._taken.setdefault(key, set()).add(action)


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
        search_effect_order: bool = DEFAULT_SEARCH_EFFECT_ORDER,
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
        self.search_effect_order = search_effect_order
        self._rng = random.Random(seed)
        self._engine = UprisingRulesEngine()
        self._taken = _Taken()

    # -- the network --------------------------------------------------------
    # Both read the trunk and then only the head rows they need: the policy
    # head holds one row per catalog action (about 33,000) and was 85% of a
    # full forward pass, while a decision offers a handful of actions. The
    # legal logits match the full pass to float rounding (3.8e-6 at most
    # over 1,695 decisions, never a different argmax) at a sixth of the cost.
    @staticmethod
    def _encode(view: PlayerView) -> np.ndarray:
        return np.asarray(encode_player_view(view), dtype=np.int32)

    def _hidden(self, encoded: np.ndarray) -> torch.Tensor:
        return self.greedy.network.trunk(torch.from_numpy(encoded).unsqueeze(0))

    def _scores(
        self, encoded: np.ndarray, legal: Sequence[DomainAction]
    ) -> np.ndarray:
        codec = self.greedy.codec
        index = torch.tensor([codec.encode(action) for action in legal])
        with torch.no_grad():
            logits = self.greedy.network.action_logits(self._hidden(encoded), index)
        scores: np.ndarray = logits[0].numpy()
        return scores

    def _logits(
        self, view: PlayerView, legal: Sequence[DomainAction]
    ) -> np.ndarray:
        return self._scores(self._encode(view), legal)

    def _leaf_value(self, view: PlayerView) -> float:
        with torch.no_grad():
            value = self.greedy.network.value_head(self._hidden(self._encode(view)))
        return float(value[0, 0])

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
        if not self.search_effect_order and orders_agent_effects(state):
            return self.greedy.choose_action(observation, legal_actions)
        offered = without_undo_actions(legal_actions)
        if len(offered) == 1:
            return offered[0]
        seat = observation.player
        encoded = self._encode(observation)
        key, fresh = self._taken.untried(state.round_number, seat, encoded, offered)
        order = np.argsort(-self._scores(encoded, fresh), kind="stable")
        candidates: list[DomainAction] = [
            fresh[int(index)] for index in order[: self.candidates]
        ]
        chosen = self._search(state, seat, candidates)
        self._taken.record(key, chosen)
        return chosen

    # -- the search ---------------------------------------------------------
    def _search(
        self, state: GameState, seat: int, candidates: list[DomainAction]
    ) -> DomainAction:
        if len(candidates) == 1:
            return candidates[0]
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

    def _playout(
        self, state: GameState, seat: int, horizon: int, chance_seed: int
    ) -> float:
        engine = self._engine
        chance = ChanceResolver(seed=chance_seed)
        # Greedy playouts need the same guard as greedy play: without it a
        # reversible pair runs every playout to ``max_rollout_steps``.
        taken = _Taken()
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
            if len(offered) == 1:
                action = offered[0]
            else:
                owner = decision.owner
                encoded = self._encode(engine.observe(state, owner))
                round_number = state.round_number
                key, fresh = taken.untried(round_number, owner, encoded, offered)
                action = fresh[int(np.argmax(self._scores(encoded, fresh)))]
                taken.record(key, action)
            state = engine.apply(state, action, legal_actions=actions).state
        if state.phase is GamePhase.FINISHED:
            return finished_reward(state, seat)
        return self._leaf_value(self._engine.observe(state, seat))


def finished_reward(state: GameState, seat: int) -> float:
    """Read a playout that finished the game on the value head's scale.

    The value head is trained toward the winner's reward and the losers'
    (``WINNER_REWARD`` / ``LOSER_REWARD``), so a finished playout must be read
    the same way. It used to be read by ``position_value``'s rank ladder
    (100/70/40/10), which put every finished playout above every unfinished
    one: a candidate that ended the game in fourth place outscored one that
    played on. Over 1,400 new one-against-three matches paired deal for deal,
    reading it as a reward wins +5.2pp [+3.4, +7.1] more, and the shipped seat
    had ended the game earlier in 170 pairs against 50 the other way
    (docs/evaluation/m10-2026-09-22.md section 14).
    """

    rank = next(s.rank for s in final_standings(state) if s.player == seat)
    return WINNER_REWARD if rank == 1 else LOSER_REWARD


def orders_agent_effects(state: GameState) -> bool:
    """Whether the pending decision picks the next effect of an Agent turn.

    Read from the decision frame's kind rather than its prompt: the
    ``AGENT_EFFECTS`` frame owns exactly the "Choose the next Agent-turn
    effect to resolve" decisions (3,055 of 3,055 agreed over four games).
    """

    return (
        bool(state.decision_stack)
        and state.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    )
