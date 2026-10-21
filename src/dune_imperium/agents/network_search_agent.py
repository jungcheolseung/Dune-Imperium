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
With five candidates in eight worlds (the default since 2026-09-25) it
wins 76.1% [73.7, 78.7] of 1,000 fresh deals against three greedy 5081,
where three candidates in four worlds won 62.0% of the same deals
(section 16); a searched decision costs about 0.27s.

Like greedy play, the search keeps a cycle guard (``_Taken``), both for its
own decisions and inside every playout. Without one a search seat stalled a
tournament match on the graft switch (``switch_graft_card``, removed in codec
v143 when both grafted boxes came to be offered at once): the network ranked
the switch first, so the switch playouts looped to ``max_rollout_steps``,
and the value head rated that stalled mid-turn position above finishing the
turn, so the seat switched forever (docs/evaluation/m10-2026-09-22.md
section 13).

Like a checkpoint seat, a search seat enters by file: ``search:<path>``.
``search:<policy path>::value=<value path>`` reads the leaves of unfinished
playouts from another file's value head and keeps everything else -- the
shortlist, every playout move, the greedy answers -- on the first file; it
splits a network's policy from its value when two files search differently
(the 2026-10-07 reversal, docs/evaluation/m10-2026-10-07.md section 4).

A decision whose legal actions are all templates the checkpoint was never
trained on (``NetworkAgent.untrained``: an Arrakeen Scouts bid, pick or
mission on a file trained without Scouts) has only tied zero logits, so
there is no shortlist to search. The seat answers it through its greedy
agent, which hands it to a heuristic, and every playout does the same with
a heuristic seeded from the playout's chance seed, so the candidates of one
decision still meet the same answers (docs/arrakeen-scouts-design.md 4.9).

The Family Atomics token is the app AI's to spend (``family_atomics``,
``agents.app_ai.family_atomics``): the network used it on its first Agent
turn in every game, at an effect choice the search leaves to it and where a
search would only compare spending it now with spending it a step later.
Under the app's rule the seat spends it in its own Reveal turn when the
Imperium Row offers poor buys, and keeps it otherwise; every seat of every
playout follows the same rule.

A Combat Intrigue that only adds strength is held while the seat alone
leads the Conflict (``hold_combat_lead``): the card-playing step ends only
when every participant passes in a row `[Main p. 14]`, so a leader that
passes is asked again after any opponent plays, and playing first only
spends the card and its cost. The app AI holds them the same way ("sole
first now: hold", ``StrengthIntrigueAbility``). The network had played
Spice is Power, paying 3 spice, at 12 strength against 6, 2 and 0, where
the search rated playing and passing alike. Every seat of every playout
holds the same way.

A loaded save does not search its recorded decisions again: the seat
retraces each one (``replay_decision``, the ``ReplayableAgent`` protocol),
drawing the worlds a search would have drawn without playing them out, so
it resumes with the RNG stream and cycle guard of the seat that was saved.

A file of a codec before the Agent turn became two steps (an MLP before
v150, ``training.older_teacher.reads_older_rows``) reaches only a few rows
of a current catalog -- 84 of 4,311 for the play network -- so the seat
plays it through the older-codec adapter instead (handoff "학습·AI", the
2026-10-21 order, step 0): the search is the same, but a candidate's score
is the adapter's probability of the step (the softmax over the whole
actions behind it, by the file's own head rows), every playout is an
``OlderNetworkAgent`` game seeded from its chance seed (it plays whole
actions, as the file learnt them, and keeps that engine's fixed answers),
the leaves are the file's value head, and a decision the older engine
answered alone (``engine_order_answer``) takes that answer without a search.
"""

import random
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, Protocol

import numpy as np
import torch

from dune_imperium.adapters.observation_encoding import encode_player_view
from dune_imperium.adapters.pettingzoo_env import LOSER_REWARD, WINNER_REWARD
from dune_imperium.agents.app_ai.family_atomics import (
    FAMILY_ATOMICS_ACTION,
    FAMILY_ATOMICS_DECIDERS,
    app_uses_family_atomics,
    without_family_atomics,
)
from dune_imperium.agents.determinize import determinize
from dune_imperium.agents.engine_order import engine_order_answer
from dune_imperium.agents.heuristic_agent import HeuristicAgent
from dune_imperium.agents.rollout_agent import past_horizon
from dune_imperium.config import RulesetConfig
from dune_imperium.content.uprising.effect_dsl import GainCombatStrength, IntrigueTiming
from dune_imperium.content.uprising.intrigue import intrigue_card_for_instance
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.observation import PlayerView
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.effect_steps import first_step
from dune_imperium.rules.endgame import final_standings
from dune_imperium.rules.frames import FrameKind
from dune_imperium.training.policy import without_undo_actions

if TYPE_CHECKING:
    from dune_imperium.training.network import PolicyValueNetwork
    from dune_imperium.training.older_teacher import OlderTeacher
    from dune_imperium.training.torch_policy import NetworkAgent


class _GreedyAnswer(Protocol):
    """The agent that answers the decisions a search seat does not search."""

    def choose_action(
        self, observation: PlayerView, legal_actions: tuple[DomainAction, ...]
    ) -> DomainAction: ...

    def choose_action_with_state(
        self,
        state: GameState,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction: ...


# Worlds and candidates are the cost knobs: a decision plays
# ``rollouts * candidates`` playouts, each to the end of the current round.
# Five candidates in eight worlds beat five in four by +10.0pp [+6.4, +13.7]
# in one-against-three win share over 1,000 fresh deals paired deal for deal
# (mean rank -0.21), and five in four beat three in four by +4.1pp
# [+0.1, +8.1]: against three greedy 5081 the three settings win 76.1%,
# 66.1% and 62.0% of the same deals, at 58s, 31s and 18s a match. Eight
# candidates in four worlds were no better than five; a two-round horizon
# gained nothing at 3.4x the cost; one world, and two worlds with effect
# ordering skipped, lost (docs/evaluation/m10-2026-09-22.md sections 13, 16).
DEFAULT_ROLLOUTS = 8
DEFAULT_CANDIDATES = 5
DEFAULT_HORIZON_ROUNDS = 1
# Ordering an Agent turn's effects is half of all searched decisions and
# 63% of the search time, yet the search overrides the network there least
# (10% against 22.6% overall), and leaving it to the network cost nothing
# measurable (docs/evaluation/m10-2026-09-22.md section 13).
DEFAULT_SEARCH_EFFECT_ORDER = False
# Who decides when to spend the Family Atomics token (FAMILY_ATOMICS_DECIDERS):
# the app AI's rule by default. See the module docstring.
DEFAULT_FAMILY_ATOMICS = "app"
# Hold strength-only Combat Intrigue while alone in the lead (module docstring).
DEFAULT_HOLD_COMBAT_LEAD = True
# Experiments of the 2026-10-21 order (handoff "학습·AI", E1 and E3), off by
# default: a searched decision keeps the network's first candidate unless
# another's mean playout value beats it by more than ``flip_margin``; its
# candidates are ranked by mean value plus ``prior_weight`` times their log
# probability under the network; ``halving`` shortlists that many candidates
# and spends the same playouts (``rollouts * candidates``) by sequential
# halving instead of every candidate in every world. In the 2026-09 labels
# the search overturned the network's first choice in 44% of decisions, and
# in 41% the mean values differed by less than 0.005
# (docs/evaluation/m10-2026-09-22.md section 15).
DEFAULT_FLIP_MARGIN = 0.0
DEFAULT_PRIOR_WEIGHT = 0.0
DEFAULT_HALVING = 0


@dataclass(frozen=True, slots=True)
class SearchResult:
    """One decision of a search seat, with the evidence behind it.

    ``values[world][candidate]`` holds each playout's value on the value
    head's scale; ``candidates`` are in the network's own order, so the
    choice is the first candidate with the largest column sum (the defaults;
    ``flip_margin``, ``prior_weight`` and ``halving`` change it, and under
    ``halving`` a candidate dropped in an early round holds NaN in the worlds
    it never played). A decision
    the seat answered without searching (a single offered action, a single
    untried candidate, or Agent-effect ordering left to the network) has
    ``searched`` false and no candidates or values.
    """

    chosen: DomainAction
    searched: bool
    candidates: tuple[DomainAction, ...] = ()
    values: tuple[tuple[float, ...], ...] = ()

    @property
    def totals(self) -> tuple[float, ...]:
        """Each candidate's value summed over the worlds."""

        return tuple(sum(column) for column in zip(*self.values, strict=True))


@dataclass(frozen=True, slots=True)
class _Shortlist:
    """A decision's candidates for the search, best network logit first,
    with each one's log probability under the network (``priors``)."""

    key: tuple[object, ...]
    candidates: tuple[DomainAction, ...]
    priors: tuple[float, ...] = ()


class _Taken:
    """Moves a seat already made at an identical decision this round.

    The greedy ``NetworkAgent`` keeps the same guard (``torch_policy``):
    reversible pairs (before codec v147, ``defer_reveal_choice`` and
    ``resume_reveal_choice``) return a seat to an identical observation and
    legal set, and an argmax
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
        config: RulesetConfig | None = None,
        value_path: str | None = None,
        family_atomics: str = DEFAULT_FAMILY_ATOMICS,
        hold_combat_lead: bool = DEFAULT_HOLD_COMBAT_LEAD,
        flip_margin: float = DEFAULT_FLIP_MARGIN,
        prior_weight: float = DEFAULT_PRIOR_WEIGHT,
        halving: int = DEFAULT_HALVING,
    ) -> None:
        if seed < 0:
            raise ValueError("agent seed must not be negative")
        if rollouts < 1 or candidates < 1 or horizon_rounds < 1:
            raise ValueError("rollouts, candidates, and horizon_rounds are positive")
        if flip_margin < 0 or prior_weight < 0:
            raise ValueError("flip_margin and prior_weight must not be negative")
        if halving == 1 or halving < 0:
            raise ValueError("halving is 0 (off) or at least 2 candidates")
        if family_atomics not in FAMILY_ATOMICS_DECIDERS:
            raise ValueError(f"family_atomics must be one of {FAMILY_ATOMICS_DECIDERS}")
        from dune_imperium.training.older_teacher import (
            OlderNetworkAgent,
            OlderTeacher,
            cached_older_network,
            reads_older_rows,
        )
        from dune_imperium.training.torch_policy import load_network_agent

        self._network_agent: NetworkAgent | None = None
        self._older: OlderTeacher | None = None
        self.value_network: PolicyValueNetwork
        if reads_older_rows(path):
            # An older codec's file plays through its own rows (module
            # docstring): the adapter answers what is not searched.
            if value_path is not None:
                raise ValueError("an older-codec file searches with its own value head")
            older = cached_older_network(path)
            self._older = OlderTeacher(older, seed=seed)
            self._answerer: _GreedyAnswer = OlderNetworkAgent(older, seed=seed)
            # Every playout plays a fresh one (``_playout``).
            self._walker = OlderNetworkAgent
            self.value_network = older.network
        else:
            # The greedy agent owns the cached network and the catalog (the
            # game's, for ``config``), and answers decisions the search
            # cannot branch from.
            self._network_agent = load_network_agent(path, config, seed=seed)
            self._answerer = self._network_agent
            # The leaves' value head: the same network unless ``value_path``
            # names another file (observation encodings migrate on load, so
            # any file of this observation version reads the same views).
            self.value_network = (
                self._network_agent.network
                if value_path is None
                else load_network_agent(value_path, config, seed=seed).network
            )
        self.rollouts = rollouts
        self.candidates = candidates
        self.horizon_rounds = horizon_rounds
        self.max_rollout_steps = max_rollout_steps
        self.search_effect_order = search_effect_order
        self.family_atomics = family_atomics
        self.hold_combat_lead = hold_combat_lead
        self.flip_margin = flip_margin
        self.prior_weight = prior_weight
        self.halving = halving
        self._rng = random.Random(seed)
        self._engine = UprisingRulesEngine()
        self._taken = _Taken()

    @property
    def greedy(self) -> NetworkAgent:
        """The greedy agent of a current-codec file (its network and catalog).

        A seat of an older codec's file has none: its greedy answers come
        from the older-codec adapter (``older``).
        """

        if self._network_agent is None:
            raise ValueError("an older-codec search seat has no catalog network")
        return self._network_agent

    @property
    def older(self) -> OlderTeacher | None:
        """The older-codec adapter the seat plays through, if any."""

        return self._older

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

    def _family_atomics(
        self,
        state: GameState,
        seat: int,
        offered: tuple[DomainAction, ...],
        observation: PlayerView | None = None,
    ) -> DomainAction | tuple[DomainAction, ...]:
        """Apply the app's Family Atomics rule to ``seat``'s decision.

        Returns the token's action when the rule spends it now, else the
        offer without it; a decision that does not offer it (or a seat that
        leaves the token to the network) keeps its offer. ``observation`` is
        the seat's view when the caller has one; playouts let it be built
        only for the decisions that offer the token.
        """

        if self.family_atomics != "app":
            return offered
        if not any(action.action_id == FAMILY_ATOMICS_ACTION for action in offered):
            return offered
        if observation is None:
            observation = self._engine.observe(state, seat)
        if app_uses_family_atomics(state, observation):
            return next(a for a in offered if a.action_id == FAMILY_ATOMICS_ACTION)
        return without_family_atomics(offered)

    def _untrained_only(self, offered: Sequence[DomainAction]) -> bool:
        """Whether every offered action is a template the file never saw."""

        greedy = self.greedy
        return bool(greedy.untrained) and greedy.untrained_only(
            [greedy.codec.encode(action) for action in offered]
        )

    def _untrained(
        self, state: GameState, seat: int, offered: tuple[DomainAction, ...]
    ) -> bool:
        """Whether the file has nothing to rank a decision's actions by: all
        untrained rows, or (an older codec) no whole action with a row."""

        if self._older is not None:
            return self._older.untrained_only(state, seat, offered)
        return self._untrained_only(offered)

    def _candidate_scores(
        self,
        state: GameState,
        seat: int,
        encoded: np.ndarray,
        legal: tuple[DomainAction, ...],
    ) -> np.ndarray:
        """The scores a decision's candidates are ranked by."""

        if self._older is not None:
            return self._older.row_scores(state, seat, legal, encoded)
        return self._scores(encoded, legal)

    def _forced(
        self, state: GameState, seat: int, offered: tuple[DomainAction, ...]
    ) -> DomainAction | None:
        """An older codec's file keeps that engine's fixed answers to the
        decisions it never asked (``engine_order_answer``)."""

        if self._older is None:
            return None
        return engine_order_answer(state, seat, offered)

    def _leaf_value(self, view: PlayerView) -> float:
        if self._older is not None:
            return self._older.value(self._encode(view))
        network = self.value_network
        encoded = torch.from_numpy(self._encode(view)).unsqueeze(0)
        with torch.no_grad():
            value = network.value_head(network.trunk(encoded))
        return float(value[0, 0])

    # -- the agent contract -------------------------------------------------
    def choose_action(
        self,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        """Without a state to branch from, play the network greedily.

        The app's Family Atomics rule reads the state, so without one the
        seat keeps the token. An older codec's file reads whole actions,
        which need the state, so its seat answers from the view as a
        heuristic does (the play server's fallback after a failed search).
        """

        if self.family_atomics == "app":
            legal_actions = without_family_atomics(legal_actions)
        if self._older is not None:
            return self._older.fallback(None).choose_action(observation, legal_actions)
        return self._answerer.choose_action(observation, legal_actions)

    def choose_action_with_state(
        self,
        state: GameState,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        """Search the network's best candidates by determinized playouts."""

        return self.search_with_state(state, observation, legal_actions).chosen

    def search_with_state(
        self,
        state: GameState,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> SearchResult:
        """Answer a decision and return the candidates and playout values.

        The same decision, RNG use and choice as ``choose_action_with_state``;
        expert iteration reads the values as training targets.
        """

        plan = self._shortlist(state, observation, legal_actions)
        if not isinstance(plan, _Shortlist):
            return SearchResult(chosen=plan, searched=False)
        candidates = plan.candidates
        if len(candidates) == 1:
            result = SearchResult(chosen=candidates[0], searched=False)
        else:
            if self.halving:
                values = self._search_halving(
                    state, observation.player, candidates, plan.priors
                )
            else:
                values = self._search(state, observation.player, candidates)
            chosen = candidates[self._pick(values, plan.priors)]
            result = SearchResult(
                chosen=chosen, searched=True, candidates=candidates, values=values
            )
        self._taken.record(plan.key, result.chosen)
        return result

    def _scores_of(
        self, values: Sequence[Sequence[float]], priors: Sequence[float]
    ) -> list[float]:
        """Each candidate's mean playout value over the worlds it played,
        plus ``prior_weight`` times its log probability (-inf for a
        candidate that played no world)."""

        scores = []
        for index, column in enumerate(zip(*values, strict=True)):
            played = [value for value in column if not np.isnan(value)]
            score = sum(played) / len(played) if played else -np.inf
            if self.prior_weight and priors and np.isfinite(priors[index]):
                score += self.prior_weight * priors[index]
            scores.append(score)
        return scores

    def _pick(
        self, values: Sequence[Sequence[float]], priors: Sequence[float]
    ) -> int:
        """The searched decision's choice among the candidates that played
        the most worlds (all of them, unless ``halving`` dropped some): the
        best score, first on a tie (candidates are in the network's own
        order), kept on the network's first candidate when it is among them
        and the best beats it by no more than ``flip_margin``. With the
        defaults this is the first candidate with the largest column sum."""

        scores = self._scores_of(values, priors)
        played = [
            sum(not np.isnan(value) for value in column)
            for column in zip(*values, strict=True)
        ]
        eligible = [index for index, count in enumerate(played) if count == max(played)]
        best = max(eligible, key=lambda index: (scores[index], -index))
        if (
            best != 0
            and self.flip_margin
            and 0 in eligible
            and scores[best] - scores[0] <= self.flip_margin
        ):
            return 0
        return best

    def replay_decision(
        self,
        state: GameState,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
        action: DomainAction,
    ) -> bool:
        """Retrace a recorded answer without its playouts (``ReplayableAgent``).

        Walks the very branches of ``search_with_state`` (``_shortlist``):
        a decision the greedy network answers is asked of it again, since
        that is cheap and moves its cycle guard and heuristic fallback the
        same way; a searched one draws its worlds (``_worlds``) only to move
        ``_rng`` on as far as the playouts' decision did, and the cycle
        guard records ``action``. An agent that retraces decisions 1..k and
        then answers decision k+1 gives the answer of one that searched all
        of them. Nothing else in the agent remembers a decision: the playouts
        keep their own guards and heuristics, and the greedy agent is only
        asked where ``_shortlist`` asks it.

        Returns ``False`` when ``action`` cannot have been this agent's
        answer: not the greedy network's or the forced choice, or not among
        the candidates the network shortlisted. The values the playouts
        would have produced are not recomputed, so which candidate a
        searched decision chose is taken on trust.
        """

        plan = self._shortlist(state, observation, legal_actions)
        if not isinstance(plan, _Shortlist):
            return plan == action
        if len(plan.candidates) > 1:
            count = self._world_count(len(plan.candidates))
            for _ in self._worlds(state, observation.player, count):
                pass
        self._taken.record(plan.key, action)
        return action in plan.candidates

    def _shortlist(
        self,
        state: GameState,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction | _Shortlist:
        """Answer a decision that needs no playouts, or shortlist its candidates.

        Shared by ``search_with_state`` and ``replay_decision``, so the two
        can never walk different branches. A shortlist carries the cycle
        guard's key for the decision; whoever answers it records the answer
        under that key.
        """

        if not legal_actions:
            raise ValueError("a search agent requires at least one legal action")
        ruled = self._family_atomics(
            state, observation.player, legal_actions, observation
        )
        if isinstance(ruled, DomainAction):
            return ruled
        legal_actions = ruled
        if self.hold_combat_lead:
            legal_actions = holds_combat_lead(state, observation.player, legal_actions)
        forced = self._forced(
            state, observation.player, without_undo_actions(legal_actions)
        )
        if forced is not None:
            return forced
        if not self.search_effect_order and orders_agent_effects(state):
            return self._answerer.choose_action_with_state(
                state, observation, legal_actions
            )
        offered = without_undo_actions(legal_actions)
        if len(offered) == 1:
            return offered[0]
        if self._untrained(state, observation.player, offered):
            return self._answerer.choose_action_with_state(
                state, observation, legal_actions
            )
        encoded = self._encode(observation)
        key, fresh = self._taken.untried(
            state.round_number, observation.player, encoded, offered
        )
        scores = self._candidate_scores(
            state, observation.player, encoded, tuple(fresh)
        )
        order = np.argsort(-scores, kind="stable")
        # A row no whole action reaches (an older codec's file: -inf) is no
        # candidate while any row is reached; a current file's logits are
        # always finite.
        reached = [int(index) for index in order if np.isfinite(scores[index])]
        ranked = reached or [int(index) for index in order]
        # Log probabilities under the network: an older codec's scores are
        # already its log probabilities, a current file's are logits.
        finite = scores[np.isfinite(scores)]
        if self._older is not None or not finite.size:
            priors = scores
        else:
            priors = scores - np.logaddexp.reduce(finite)
        kept = ranked[: self.halving or self.candidates]
        return _Shortlist(
            key=key,
            candidates=tuple(fresh[index] for index in kept),
            priors=tuple(float(priors[index]) for index in kept),
        )

    # -- expert iteration ---------------------------------------------------
    def candidate_order(
        self, observation: PlayerView, actions: Sequence[DomainAction]
    ) -> tuple[DomainAction, ...]:
        """``actions`` in the order the search ranks candidates (stable)."""

        order = np.argsort(-self._logits(observation, actions), kind="stable")
        return tuple(actions[int(index)] for index in order)

    def evaluate_candidates(
        self, state: GameState, seat: int, candidates: tuple[DomainAction, ...]
    ) -> tuple[tuple[float, ...], ...]:
        """Playout values ``values[world][candidate]`` for given candidates.

        The same playouts and RNG use as a searched decision; expert
        iteration labels a greedy player's decisions with it without letting
        the search choose the move.
        """

        return self._search(state, seat, candidates)

    # -- the search ---------------------------------------------------------
    def _search(
        self, state: GameState, seat: int, candidates: tuple[DomainAction, ...]
    ) -> tuple[tuple[float, ...], ...]:
        """Return ``values[world][candidate]`` over the determinized worlds."""

        horizon = state.round_number + self.horizon_rounds
        values: list[tuple[float, ...]] = []
        for world, chance_seed in self._worlds(state, seat):
            values.append(
                tuple(
                    self._playout(
                        self._engine.apply(world, action).state,
                        seat,
                        horizon,
                        chance_seed,
                    )
                    for action in candidates
                )
            )
        return tuple(values)

    def _halving_rounds(self, count: int) -> list[int]:
        """New worlds per round of sequential halving over ``count``
        candidates: the budget ``rollouts * candidates`` split evenly over
        ceil(log2(count)) rounds among the candidates still in, half of
        them kept after each round (Gumbel AlphaZero's schedule). It depends
        only on ``count``, so a retraced decision draws as many worlds."""

        budget = self.rollouts * self.candidates
        rounds = max(1, (count - 1).bit_length())
        remaining, alive, schedule = budget, count, []
        for left in range(rounds, 0, -1):
            new = max(1, remaining // (left * alive))
            schedule.append(new)
            remaining -= new * alive
            alive = max(1, (alive + 1) // 2)
        return schedule

    def _world_count(self, count: int) -> int:
        """How many worlds a searched decision of ``count`` candidates draws."""

        return sum(self._halving_rounds(count)) if self.halving else self.rollouts

    def _search_halving(
        self,
        state: GameState,
        seat: int,
        candidates: tuple[DomainAction, ...],
        priors: Sequence[float],
    ) -> tuple[tuple[float, ...], ...]:
        """``values[world][candidate]`` by sequential halving: every candidate
        still in plays each round's new worlds (the same worlds and chance
        streams for all of them), then the better half by ``_scores_of``
        stays (the first on a tie); a dropped candidate holds NaN in the
        worlds it did not play."""

        horizon = state.round_number + self.horizon_rounds
        alive = list(range(len(candidates)))
        rows: list[list[float]] = []
        worlds = self._worlds(state, seat, self._world_count(len(candidates)))
        for new in self._halving_rounds(len(candidates)):
            for _ in range(new):
                world, chance_seed = next(worlds)
                row = [float("nan")] * len(candidates)
                for index in alive:
                    after = self._engine.apply(world, candidates[index]).state
                    row[index] = self._playout(after, seat, horizon, chance_seed)
                rows.append(row)
            scores = self._scores_of(rows, priors)
            ranked = sorted(alive, key=lambda index: (-scores[index], index))
            alive = sorted(ranked[: max(1, (len(alive) + 1) // 2)])
        return tuple(tuple(row) for row in rows)

    def _worlds(
        self, state: GameState, seat: int, count: int | None = None
    ) -> Iterator[tuple[GameState, int]]:
        """Draw a searched decision's worlds and chance seeds from ``_rng``.

        The only use of ``_rng``: ``_search`` plays the candidates in each
        world, and ``replay_decision`` draws them only to move the stream
        on exactly as far. Playouts never touch ``_rng``, so drawing the
        worlds lazily between them or all at once uses it the same way.
        ``count`` defaults to ``rollouts``.
        """

        for _ in range(self.rollouts if count is None else count):
            world = determinize(state, seat, self._rng)
            # Common random numbers: every candidate meets the same world
            # and the same chance stream, so they differ only by the action.
            chance_seed = self._rng.randrange(2**31)
            yield world, chance_seed

    def _playout(
        self, state: GameState, seat: int, horizon: int, chance_seed: int
    ) -> float:
        engine = self._engine
        chance = ChanceResolver(seed=chance_seed)
        # Greedy playouts need the same guard as greedy play: without it a
        # reversible pair runs every playout to ``max_rollout_steps``.
        taken = _Taken()
        # Seeded per playout, so every candidate meets the same answers.
        fallback: HeuristicAgent | None = None
        # An older codec's file plays the playout as its own greedy seat in
        # every chair: whole actions, that engine's fixed answers, its guard.
        walker: _GreedyAnswer | None = None
        if self._older is not None:
            walker = self._walker(self._older.older, seed=chance_seed)
        for _ in range(self.max_rollout_steps):
            if state.phase is GamePhase.FINISHED or past_horizon(state, horizon):
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
            offered = self._family_atomics(
                state, decision.owner, without_undo_actions(actions)
            )
            if self.hold_combat_lead and not isinstance(offered, DomainAction):
                offered = holds_combat_lead(state, decision.owner, offered)
            if isinstance(offered, DomainAction):
                action = offered
            elif len(offered) == 1:
                action = offered[0]
            elif walker is not None:
                owner = decision.owner
                action = walker.choose_action_with_state(
                    state, engine.observe(state, owner), offered
                )
            elif self._untrained_only(offered):
                if fallback is None:
                    fallback = HeuristicAgent(seed=chance_seed)
                owner = decision.owner
                action = fallback.choose_action_with_state(
                    state, engine.observe(state, owner), offered
                )
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


def holds_combat_lead(
    state: GameState, seat: int, offered: tuple[DomainAction, ...]
) -> tuple[DomainAction, ...]:
    """``offered`` without strength-only Combat Intrigue while ``seat`` alone leads.

    Only at the Combat Intrigue step itself, and only when ``seat``'s
    strength is above every other seat's; a tie or a deficit keeps the
    offer. Never empty: passing is always offered there. The window offers a
    play effect first (stage B3c-1): a row whose every whole action behind
    it plays a strength-only card -- the window's ``play`` row, a card's row,
    an option's row -- is withheld like the whole action itself.
    """

    if not (
        state.decision_stack
        and state.decision_stack[-1].kind == FrameKind.COMBAT_INTRIGUE
    ):
        return offered
    mine = state.players[seat].combat_strength
    if any(
        player.combat_strength >= mine
        for index, player in enumerate(state.players)
        if index != seat
    ):
        return offered
    behind: dict[DomainAction, list[DomainAction]] = {}
    for whole in _RULES.whole_actions(state, seat):
        behind.setdefault(first_step(state, whole), []).append(whole)

    def withheld(action: DomainAction) -> bool:
        if adds_only_strength(action):
            return True
        wholes = behind.get(action, ())
        return bool(wholes) and all(adds_only_strength(whole) for whole in wholes)

    kept = tuple(action for action in offered if not withheld(action))
    return kept or offered


# The rules' whole actions of a decision; any engine instance lists the same.
_RULES = UprisingRulesEngine()


def adds_only_strength(action: DomainAction) -> bool:
    """Whether ``action`` plays a Combat Intrigue whose rewards are all strength.

    Its costs do not matter: holding the card keeps them unpaid too.
    """

    if action.action_id != "play_intrigue":
        return False
    arguments = dict(action.arguments)
    card_id = arguments.get("card_id")
    option = arguments.get("option")
    if not isinstance(card_id, str) or not isinstance(option, int):
        return False
    return _option_adds_only_strength(card_id, option)


@cache
def _option_adds_only_strength(card_id: str, option: int) -> bool:
    options = intrigue_card_for_instance(card_id).options
    if not 0 <= option < len(options):
        return False
    chosen = options[option]
    return (
        chosen.timing is IntrigueTiming.COMBAT
        and chosen.trigger is None
        and all(
            isinstance(reward, GainCombatStrength)
            for section in chosen.sections
            for reward in section.rewards
        )
    )


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
