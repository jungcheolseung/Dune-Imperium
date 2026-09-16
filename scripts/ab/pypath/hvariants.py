"""Scratch agent variants for paired A/Bs, registered by the sitecustomize next to it.

Put this directory on ``PYTHONPATH`` (``scripts/ab/cells.py`` does it for you) and
every tournament worker -- Python 3.14 spawns them, so they import this file too --
can name the variants below on the command line next to the committed baselines.

Two kinds of ``HeuristicAgent`` variant, both built on the *current* committed agent
(the board space table, the spent-card price and the within-family tie-breaks stay):

* ``prefer(top, view)`` narrows the top-scoring tie set to a subset *before* the
  seeded draw. It never sees an action outside the tie set, so it cannot change
  which score wins (docs/lessons.md 2026-09-10: tie-breaks are applied after the
  tie set is fixed, never as a term in ``score_action``).
* ``adjust(action, score, view)`` changes one action's score; this *can* reorder
  families and is the kind of change measured as a whole.

``RolloutVariant`` re-weights the rollout's value function (``DEFAULT_WEIGHTS`` is
the committed one) and reads a playout against the opponents' mean or their
strongest seat.

``NullVariant``/``RNull`` must equal ``heuristic``/``rollout`` decision for decision
-- ``scripts/ab/sanity.py`` checks that before a round, and so does
tests/unit/test_ab_tools.py. The variants measured on 2026-09-16
(docs/evaluation/baseline-2026-09-16.md sections 14 and 15) are kept as templates;
the winners were ported into the agents and pinned there.
"""

from __future__ import annotations

from dune_imperium.agents.heuristic_agent import (
    _DECLINE_SCORE,
    _SWITCH_NEUTRAL_ACTIONS,
    UPRISING_SPACE_BONUSES,
    HeuristicAgent,
    TieBreaks,
    _argument,
    card_printed_value,
    cheapest_card_for_the_same_space,
    influence_step_value,
    narrow_family_tie,
    score_action,
)
from dune_imperium.agents.rollout_agent import (
    _RANK_STEP,
    _STARTING_DECK_SIZE,
    _WIN_VALUE,
    RolloutAgent,
    _research_column,
)
from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID, OBSERVATION_POSTS
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.state import GamePhase
from dune_imperium.rules.endgame import final_standings

POSTS_BY_ID = {post.post_id: post for post in OBSERVATION_POSTS}


# ---------------------------------------------------------------- heuristic variants


class VariantAgent(HeuristicAgent):
    """``HeuristicAgent`` with the two hooks; with both defaults it is identical."""

    def adjust(self, action, score, view):
        return score

    def prefer(self, top, view):
        return top

    def choose_action(self, observation, legal_actions):
        if not legal_actions:
            raise ValueError("a heuristic agent requires at least one legal action")
        if any(action.actor != observation.player for action in legal_actions):
            raise ValueError("every legal action must belong to the observing player")
        bonuses = (
            UPRISING_SPACE_BONUSES if self.space_bonuses is None else self.space_bonuses
        )
        scored = tuple(
            self.adjust(
                action, score_action(action, space_bonuses=bonuses), observation
            )
            for action in legal_actions
        )
        if any(a.action_id not in _SWITCH_NEUTRAL_ACTIONS for a in legal_actions):
            scored = tuple(
                min(scored) - 1.0 if a.action_id == "switch_graft_card" else s
                for a, s in zip(legal_actions, scored, strict=True)
            )
        best = max(scored)
        top = tuple(a for a, s in zip(legal_actions, scored, strict=True) if s == best)
        if len(top) > 1 and self.tie_breaks is not None:
            top = narrow_family_tie(top, observation, self.tie_breaks)
        if len(top) > 1:
            narrowed = tuple(self.prefer(top, observation))
            assert narrowed and all(a in top for a in narrowed), "prefer must narrow"
            top = narrowed
        chosen = self._rng.choice(top)
        return cheapest_card_for_the_same_space(chosen, top, self.spent_card_value)


def own(view):
    return view.players[view.player]


def others(view):
    return tuple(p for p in view.players if p.player != view.player)


def argmax_subset(top, key):
    values = [key(a) for a in top]
    best = max(values)
    return tuple(a for a, v in zip(top, values, strict=True) if v == best)


def same_family(top):
    families = {a.action_id for a in top}
    return next(iter(families)) if len(families) == 1 else None


class NullVariant(VariantAgent):
    """Framework check: must equal ``heuristic`` decision for decision."""


class SpaceTiebreak(VariantAgent):
    """Among equally ranked spaces prefer the Faction space nearest a threshold.

    Measured 2026-09-16 (section 14(b)): noise on every axis, rejected.
    """

    def prefer(self, top, view):
        if same_family(top) != "agent_turn":
            return top
        if len({_argument(a, "space_id") for a in top}) < 2:
            return top

        def value(action):
            space = BOARD_SPACES_BY_ID.get(_argument(action, "space_id"))
            if space is None or space.faction is None:
                return 0.0
            return influence_step_value(view, space.faction.value)

        return argmax_subset(top, value)


class SpyPost(VariantAgent):
    """Place a Spy on the post whose connected spaces rank highest (rejected: noise)."""

    def prefer(self, top, view):
        family = same_family(top)
        if family is None or not (
            family.startswith("place_") and family.endswith("_spy")
        ):
            return top
        mine = set(own(view).spy_post_ids)

        def value(action):
            post = POSTS_BY_ID.get(_argument(action, "post_id"))
            if post is None:
                return 0.0
            total = sum(
                UPRISING_SPACE_BONUSES.get(s, 0.0) for s in post.connected_space_ids
            )
            return total - (100.0 if post.post_id in mine else 0.0)

        return argmax_subset(top, value)


class TrashDearest(VariantAgent):
    """Template for a ``prefer`` on a family the committed agent already settles.

    The adopted trash tie-break would narrow the set before ``prefer`` sees it, so
    the variant switches that one off and applies the opposite rule; compare it
    against ``heuristic_uniform_ties`` or the live ``heuristic`` as the question
    requires.
    """

    def __post_init__(self):
        super().__post_init__()
        self.tie_breaks = TieBreaks(trash=False)

    def prefer(self, top, view):
        if same_family(top) not in ("trash_agent_card", "discard_agent_card"):
            return top
        return argmax_subset(top, lambda a: card_printed_value(_argument(a, "card_id")))


class IntrigueFirst(VariantAgent):
    """Play Plot Intrigue before placing an Agent (rejected: -5.8 on the full stack)."""

    def adjust(self, action, score, view):
        return 7.5 if action.action_id == "play_intrigue" else score


class DeployHold(VariantAgent):
    """Keep the garrison when everything deployed cannot lead (rejected: -8 to -13)."""

    def adjust(self, action, score, view):
        if action.action_id not in ("deploy_troops", "deploy_commanders"):
            return score
        me = own(view)
        potential = (
            me.combat_strength + 2 * me.troops_garrison + 2 * me.commanders_garrison
        )
        leader = max((p.combat_strength for p in others(view)), default=0)
        return _DECLINE_SCORE - 0.5 if potential < leader else score


VARIANTS = {
    "heuristic_v_null": NullVariant,
    "heuristic_v_space": SpaceTiebreak,
    "heuristic_v_spy": SpyPost,
    "heuristic_v_trash_dearest": TrashDearest,
    "heuristic_v_intrigue": IntrigueFirst,
    "heuristic_v_deploy": DeployHold,
}


def register(registry):
    for name, cls in VARIANTS.items():
        registry.BASELINE_AGENT_FACTORIES[name] = (lambda c: lambda seed: c(seed=seed))(
            cls
        )


# ---------------------------------------------------------------- rollout variants

# The committed value function (docs/evaluation/baseline-2026-09-16.md section 15).
DEFAULT_WEIGHTS = {
    "vp": 10.0,
    "influence": 1.5,
    "alliance": 1.0,
    "swordmaster": 2.0,
    "council": 1.5,
    "spice": 0.4,
    "solari": 0.25,
    "water": 0.3,
    "garrison": 0.6,
    "conflict": 0.4,
    "card": 0.0,  # per card beyond the starting ten (the pre-2026-09-16 deck term)
    "card_cost": 0.1,  # per point of printed value in the deck (card_printed_value)
    "spy": 0.5,
    "control": 0.5,
    "contract": 1.0,
    "commander": 1.2,
    "skill": 0.5,
    "tech": 1.0,
    "specimen": 0.5,
    "research": 0.4,
    "tleilaxu": 0.5,
    "atomics": 0.3,
    "threshold": 0.0,  # per track one step below 2 or 4
}


def weighted_player_value(player, w):
    influence = player.influence
    levels = (
        influence.emperor,
        influence.spacing_guild,
        influence.bene_gesserit,
        influence.fremen,
    )
    zones = (player.deck, player.hand, player.discard_pile, player.in_play)
    cards = sum(len(zone) for zone in zones)
    value = (
        w["vp"] * player.victory_points
        + w["influence"] * sum(levels)
        + w["alliance"] * len(player.alliance_faction_ids)
        + w["swordmaster"] * player.swordmaster_acquired
        + w["council"] * player.high_council
        + w["spice"] * player.resources.spice
        + w["solari"] * player.resources.solari
        + w["water"] * player.resources.water
        + w["garrison"] * player.troops_garrison
        + w["conflict"] * player.troops_conflict
        + w["card"] * max(0, cards - _STARTING_DECK_SIZE)
        + w["spy"] * len(player.spy_post_ids)
        + w["control"] * len(player.control_space_ids)
        + w["contract"] * len(player.active_contract_ids)
        + w["commander"] * (player.commanders_garrison + player.commanders_conflict)
        + w["skill"] * len(player.skill_ids)
        + w["tech"] * len(player.tech_ids)
        + w["specimen"] * player.specimens
        + w["research"] * _research_column(player.research_space)
        + w["tleilaxu"] * player.tleilaxu_space
        + w["atomics"] * player.family_atomics
    )
    if w["card_cost"]:
        value += w["card_cost"] * sum(
            card_printed_value(instance_id) for zone in zones for instance_id in zone
        )
    if w["threshold"]:
        value += w["threshold"] * sum(1 for level in levels if level in (1, 3))
    return value


class RolloutVariant(RolloutAgent):
    weights = DEFAULT_WEIGHTS
    mode = "mean"  # "mean": against the opponents' mean; "max": the strongest opponent

    def _value(self, state, seat):
        if state.phase is GamePhase.FINISHED:
            rank = next(s.rank for s in final_standings(state) if s.player == seat)
            return _WIN_VALUE - _RANK_STEP * (rank - 1)
        own_value = weighted_player_value(state.players[seat], self.weights)
        rest = [
            weighted_player_value(p, self.weights)
            for p in state.players
            if p.player_id != seat
        ]
        return own_value - (max(rest) if self.mode == "max" else sum(rest) / len(rest))

    def _rollout(self, state, seat, horizon, seeds=None):
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
        return self._value(state, seat)


def rollout_variant(name, mode="mean", **overrides):
    """A ``RolloutVariant`` subclass with ``DEFAULT_WEIGHTS`` plus ``overrides``."""

    return type(
        name,
        (RolloutVariant,),
        {"weights": {**DEFAULT_WEIGHTS, **overrides}, "mode": mode},
    )


ROLLOUT_VARIANTS = {
    "rollout_v_null": rollout_variant("RNull"),
    "rollout_v_count_max": rollout_variant(
        "RCountMax", mode="max", card=0.5, card_cost=0.0
    ),
    "rollout_v_vp20": rollout_variant("RVp20", vp=20.0),
    "rollout_v_threshold": rollout_variant("RThreshold", threshold=1.0),
    "rollout_v_spice08": rollout_variant("RSpice", spice=0.8),
    "rollout_v_garrison03": rollout_variant("RGarrison", garrison=0.3),
}


def register_rollout(registry):
    for name, cls in ROLLOUT_VARIANTS.items():
        registry.BASELINE_AGENT_FACTORIES[name] = (lambda c: lambda seed: c(seed=seed))(
            cls
        )
