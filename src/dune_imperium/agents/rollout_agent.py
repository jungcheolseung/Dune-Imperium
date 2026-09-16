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
decision costs 12 one-round heuristic rollouts.
"""

import random
from dataclasses import dataclass, field

from dune_imperium.agents.determinize import determinize
from dune_imperium.agents.heuristic_agent import (
    HeuristicAgent,
    card_printed_value,
    score_action,
)
from dune_imperium.content.immortality.board import RESEARCH_SPACES_BY_ID
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
# The deck term: a card's printed value (acquisition cost plus its Reveal box
# on the spent-card rubric) at this weight, or, before 2026-09-16 night, 0.5
# per card beyond the starting ten (docs/evaluation/baseline-2026-09-16.md
# section 15).
_CARD_VALUE_WEIGHT = 0.1
_CARD_COUNT_WEIGHT = 0.5


def _research_column(space_id: str) -> int:
    """Columns the research token has advanced; 0 without Immortality."""

    space = RESEARCH_SPACES_BY_ID.get(space_id)
    return 0 if space is None else space.column


def player_value(player: PlayerState, *, deck_by_value: bool = True) -> float:
    """Score one seat's position: Victory Points first, then durable assets.

    With ``deck_by_value`` the deck counts by printed value (a bought 9-cost
    card outweighs a 1-cost one, the starting cards only their Reveal
    boxes); without it every card beyond the starting ten counts the same,
    the 2026-09-16 evening formula the registry pins for the paired A/B.
    """

    influence = player.influence
    zones = (player.deck, player.hand, player.discard_pile, player.in_play)
    if deck_by_value:
        deck = _CARD_VALUE_WEIGHT * sum(
            card_printed_value(instance_id) for zone in zones for instance_id in zone
        )
    else:
        cards = sum(len(zone) for zone in zones)
        deck = _CARD_COUNT_WEIGHT * max(0, cards - _STARTING_DECK_SIZE)
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
        + deck
        + 0.5 * len(player.spy_post_ids)
        + 0.5 * len(player.control_space_ids)
        + 1.0 * len(player.active_contract_ids)
        # Bloodlines: a Sardaukar Commander is a two-strength unit, a Skill
        # a lasting bonus, and a Tech tile a permanent upgrade (a few also
        # score at the end of the game).
        + 1.2 * (player.commanders_garrison + player.commanders_conflict)
        + 0.5 * len(player.skill_ids)
        + 1.0 * len(player.tech_ids)
        # Immortality: a specimen is a troop resting in the Axolotl tanks
        # that buys Tleilaxu cards, and both Bene Tleilax tracks are
        # permanent progress -- the Tleilaxu track scores a Victory Point
        # at spaces 4 and 7, the research track pays a bonus every column
        # and unlocks the genetic markers. An unspent Family Atomics token
        # is one free Imperium Row refresh.
        + 0.5 * player.specimens
        + 0.4 * _research_column(player.research_space)
        + 0.5 * player.tleilaxu_space
        + 0.3 * player.family_atomics
    )


def position_value(
    state: GameState,
    seat: int,
    *,
    opponent_reference: str = "mean",
    deck_by_value: bool = True,
) -> float:
    """Value of ``seat``'s position relative to its opponents.

    A finished game scores by official rank so a win dominates every asset
    difference; otherwise the seat's ``player_value`` minus the opponents'
    reference: their mean (``"mean"``) or the strongest one (``"max"``).
    Both knobs were measured on 2026-09-16 night against three tie-break
    heuristics (docs/evaluation/baseline-2026-09-16.md section 15): the mean
    and the printed-value deck together read a playout with less noise than
    the strongest opponent, whose identity changes from world to world, and
    a card count that prices a Dagger like a 9-cost card.
    """

    if state.phase is GamePhase.FINISHED:
        rank = next(s.rank for s in final_standings(state) if s.player == seat)
        return _WIN_VALUE - _RANK_STEP * (rank - 1)
    own = player_value(state.players[seat], deck_by_value=deck_by_value)
    others = [
        player_value(player, deck_by_value=deck_by_value)
        for player in state.players
        if player.player_id != seat
    ]
    if opponent_reference == "max":
        return own - max(others)
    if opponent_reference == "mean":
        return own - sum(others) / len(others)
    raise ValueError("opponent_reference must be 'max' or 'mean'")


@dataclass(slots=True)
class RolloutAgent:
    """Choose by determinized heuristic rollouts; falls back to the heuristic."""

    seed: int
    # The knobs were re-tuned on 2026-09-16 against the strengthened
    # heuristic (docs/evaluation/baseline-2026-09-16.md section 13): at a
    # fixed budget of playouts per decision the win rate against three
    # heuristics is decided by the number of sampled worlds, not by the
    # width of the candidate set, and a second round of horizon only adds
    # playout noise. The 2026-09-06 defaults (2 worlds, 6 candidates, fresh
    # seeds) stay pinned on the registry's ``rollout_untuned``.
    rollouts: int = 4
    candidates: int = 3
    horizon_rounds: int = 1
    max_rollout_steps: int = 3_000
    # Common random numbers: play every candidate's rollout on one sampled
    # world with the same chance and policy seeds, so the candidates differ
    # only by the action taken and the comparison is not swamped by playout
    # noise.
    paired_playouts: bool = True
    # How a playout's end position is read (section 15): the seat's value
    # against the opponents' mean or the strongest one, with the deck counted
    # by printed value or by card. The 2026-09-16 evening function (max,
    # by card) stays pinned on the registry's ``rollout_count_max``.
    opponent_reference: str = "mean"
    deck_by_value: bool = True
    _rng: random.Random = field(init=False, repr=False)
    _engine: UprisingRulesEngine = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise ValueError("agent seed must not be negative")
        if self.rollouts < 1 or self.candidates < 1 or self.horizon_rounds < 1:
            raise ValueError("rollouts, candidates, and horizon_rounds are positive")
        if self.opponent_reference not in ("max", "mean"):
            raise ValueError("opponent_reference must be 'max' or 'mean'")
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
            shared = (
                (self._rng.randrange(2**31), self._rng.randrange(2**31))
                if self.paired_playouts
                else None
            )
            for index, action in enumerate(candidates):
                branched = self._engine.apply(world, action).state
                totals[index] += self._rollout(branched, seat, horizon, shared)
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

    def _rollout(
        self,
        state: GameState,
        seat: int,
        horizon: int,
        seeds: tuple[int, int] | None = None,
    ) -> float:
        engine = self._engine
        if seeds is None:
            seeds = (self._rng.randrange(2**31), self._rng.randrange(2**31))
        chance = ChanceResolver(seed=seeds[0])
        policy = HeuristicAgent(seed=seeds[1])
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
            state = engine.apply(state, action, legal_actions=actions).state
        return position_value(
            state,
            seat,
            opponent_reference=self.opponent_reference,
            deck_by_value=self.deck_by_value,
        )
