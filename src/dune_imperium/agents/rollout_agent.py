"""Determinized rollout search over the heuristic policy (M9 baseline).

``RolloutAgent`` is the first search baseline. At every decision with more
than one legal action it keeps the ``candidates`` best actions by the
heuristic ranking, then for each of ``rollouts`` samples a world consistent
with its own knowledge (``determinize``), applies every candidate to that
world, and plays the rest of the current round(s) out with the heuristic
policy in every seat. The candidate with the highest mean position value
at the horizon wins; ties break with the seeded RNG.

The agent needs the authoritative state to branch from, so it implements
the ``StateAgent`` extension of the agent contract. It never reads a hidden
zone directly: every rollout starts from a determinized copy, and the only
thing the real state contributes is what the seat's own view also
contains. Rollouts and rounds are the cost knobs: with the defaults one
decision costs about a dozen one-round heuristic rollouts.
"""

import random
from dataclasses import dataclass, field

from dune_imperium.agents.determinize import determinize
from dune_imperium.agents.heuristic_agent import HeuristicAgent, score_action
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.observation import PlayerView
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.endgame import final_standings

_STARTING_DECK_SIZE = 10
_WIN_VALUE = 100.0
_RANK_STEP = 30.0


def player_value(player: PlayerState) -> float:
    """Score one seat's position: Victory Points first, then durable assets."""

    influence = player.influence
    cards = (
        len(player.deck)
        + len(player.hand)
        + len(player.discard_pile)
        + len(player.in_play)
    )
    return (
        10.0 * player.victory_points
        + 1.5
        * (
            influence.emperor
            + influence.spacing_guild
            + influence.bene_gesserit
            + influence.fremen
        )
        + 1.0 * len(player.alliance_faction_ids)
        + 2.0 * player.swordmaster_acquired
        + 1.5 * player.high_council
        + 0.4 * player.resources.spice
        + 0.25 * player.resources.solari
        + 0.3 * player.resources.water
        + 0.6 * player.troops_garrison
        + 0.4 * player.troops_conflict
        + 0.5 * max(0, cards - _STARTING_DECK_SIZE)
        + 0.5 * len(player.spy_post_ids)
        + 0.5 * len(player.control_space_ids)
        + 1.0 * len(player.active_contract_ids)
    )


def position_value(state: GameState, seat: int) -> float:
    """Value of ``seat``'s position relative to its strongest opponent.

    A finished game scores by official rank so a win dominates every asset
    difference; otherwise the seat's ``player_value`` minus the best
    opponent's, which rewards pulling ahead of the leader rather than
    piling up assets while an opponent runs away.
    """

    if state.phase is GamePhase.FINISHED:
        rank = next(s.rank for s in final_standings(state) if s.player == seat)
        return _WIN_VALUE - _RANK_STEP * (rank - 1)
    own = player_value(state.players[seat])
    others = [
        player_value(player) for player in state.players if player.player_id != seat
    ]
    return own - max(others)


@dataclass(slots=True)
class RolloutAgent:
    """Choose by determinized heuristic rollouts; falls back to the heuristic."""

    seed: int
    rollouts: int = 2
    candidates: int = 6
    horizon_rounds: int = 1
    max_rollout_steps: int = 3_000
    _rng: random.Random = field(init=False, repr=False)
    _engine: UprisingRulesEngine = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise ValueError("agent seed must not be negative")
        if self.rollouts < 1 or self.candidates < 1 or self.horizon_rounds < 1:
            raise ValueError("rollouts, candidates, and horizon_rounds are positive")
        self._rng = random.Random(self.seed)
        self._engine = UprisingRulesEngine()

    def choose_action(
        self,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        """Without a state to branch from, rank like the heuristic."""

        return self._heuristic_choice(observation, legal_actions)

    def choose_action_with_state(
        self,
        state: GameState,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        """Search the candidates by determinized rollouts from ``state``."""

        if not legal_actions:
            raise ValueError("a rollout agent requires at least one legal action")
        if len(legal_actions) == 1:
            return legal_actions[0]
        seat = observation.player
        candidates = self._candidates(legal_actions)
        if len(candidates) == 1:
            return candidates[0]
        horizon = state.round_number + self.horizon_rounds
        totals = [0.0 for _ in candidates]
        for _ in range(self.rollouts):
            world = determinize(state, seat, self._rng)
            for index, action in enumerate(candidates):
                branched = self._engine.apply(world, action).state
                totals[index] += self._rollout(branched, seat, horizon)
        best = max(totals)
        top = tuple(
            action
            for action, total in zip(candidates, totals, strict=True)
            if total == best
        )
        return self._rng.choice(top)

    def _candidates(
        self, legal_actions: tuple[DomainAction, ...]
    ) -> tuple[DomainAction, ...]:
        # Shuffle before the stable sort so equal heuristic scores are cut
        # at random instead of by enumeration order.
        shuffled = list(legal_actions)
        self._rng.shuffle(shuffled)
        ranked = sorted(shuffled, key=score_action, reverse=True)
        return tuple(ranked[: self.candidates])

    def _heuristic_choice(
        self,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        return HeuristicAgent(seed=self._rng.randrange(2**31)).choose_action(
            observation, legal_actions
        )

    def _rollout(self, state: GameState, seat: int, horizon: int) -> float:
        engine = self._engine
        chance = ChanceResolver(seed=self._rng.randrange(2**31))
        policy = HeuristicAgent(seed=self._rng.randrange(2**31))
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
            action = (
                actions[0]
                if len(actions) == 1
                else policy.choose_action(
                    engine.observe(state, decision.owner), actions
                )
            )
            state = engine.apply(state, action).state
        return position_value(state, seat)
