"""Simple rule-based heuristic opponent.

``HeuristicAgent`` is the first non-random AI opponent for the M11 human
play interface and is deliberately reused as the starting point of the M9
heuristic baseline. It keeps the exact ``choose_action`` contract of
``RandomAgent``: one ``PlayerView`` plus the legal actions, never hidden
state.

The policy is a static strategy preference over engine-legal actions, not a
rules judgment: the engine alone decides legality and the agent only ranks
what it is offered. Rankings may read printed public card data (acquisition
costs) through the content manifests, exactly as a human reads card text at
the table. Unknown action IDs score 0, so new content degrades to a seeded
uniform choice instead of failing.
"""

import random
from dataclasses import dataclass, field
from typing import Final

from dune_imperium.content.uprising.imperium import imperium_card_for_instance
from dune_imperium.content.uprising.reserve import RESERVE_STACKS_BY_ID
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.observation import PlayerView

# Strategy weights, largest first: direct victory points, then permanent
# upgrades, then cards, units, and resources. Declines and passes sit below
# zero so the agent acts when the engine offers anything to act on. The
# numbers only order the choices inside one legal-action set.
_ACTION_SCORES: Final[dict[str, float]] = {
    # Direct victory points and Objective progress.
    "complete_contract": 8.0,
    "trash_contract_reveal_for_vp": 8.0,
    "flip_battle_card": 7.0,
    "match_endgame_wild_icon": 7.0,
    "take_high_council_from_reveal": 6.0,
    # Keep placing Agents before revealing.
    "agent_turn": 4.0,
    "reveal_turn": 1.0,
    # Combat presence.
    "summon_maker_sandworms": 4.0,
    "deploy_control_defense": 2.0,
    "gain_two_reveal_strength": 2.0,
    # Cards, Intrigue, and Spies.
    "play_intrigue": 3.0,
    "resolve_agent_card_effect": 2.0,
    "resolve_board_effect": 2.0,
    "gather_intelligence": 2.0,
    "resolve_espionage_place_spy": 2.0,
    "advance_feyd_track": 2.0,
    # Influence steps.
    "resolve_faction_influence": 2.0,
    "exchange_reveal_influence": 2.0,
    "pay_reveal_spice_influence": 2.0,
    "choose_agent_card_influence": 2.0,
    "choose_combat_reward_influence": 2.0,
    "choose_distinct_combat_reward_influence": 2.0,
    "choose_leader_signet_influence": 2.0,
    "choose_intrigue_faction": 2.0,
    # Resource pickups.
    "harvest_maker_spice": 2.0,
    "take_sietch_tabr_water": 2.0,
    "take_sietch_tabr_supplies": 2.0,
    "take_sietch_tabr_water_and_destroy_wall": 2.0,
    "gain_five_reveal_solari": 2.0,
    "keep_contract_reveal_spice": 2.0,
    "take_contract": 2.0,
    "gain_leader_signet_troop": 2.0,
    "use_other_memories": 1.0,
}

_IMPERIUM_ACQUISITIONS: Final = frozenset(
    {
        "acquire_imperium",
        "acquire_imperium_with_solari",
        "acquire_intrigue_imperium",
        "acquire_leader_imperium",
        "acquire_manipulated_imperium",
    }
)
_RESERVE_ACQUISITIONS: Final = frozenset(
    {
        "acquire_reserve",
        "acquire_reserve_with_solari",
        "acquire_intrigue_reserve",
        "acquire_leader_reserve",
    }
)
_COUNT_DEPLOYMENTS: Final = frozenset({"deploy_troops", "deploy_intrigue_troops"})

_ACQUISITION_BASE: Final = 3.0
_SPY_PLACEMENT_SCORE: Final = 3.0
_MINOR_ACTION_SCORE: Final = 1.0
_DECLINE_SCORE: Final = -2.0
_PASS_SCORE: Final = -3.0
_RETREAT_SCORE: Final = -1.0

# Board spaces granting permanent upgrades outrank other placements.
_SPACE_BONUSES: Final[dict[str, float]] = {
    "swordmaster": 3.0,
    "high_council": 2.0,
}


def score_action(action: DomainAction) -> float:
    """Rank one engine-legal action; higher is preferred."""

    action_id = action.action_id
    if action_id in _COUNT_DEPLOYMENTS:
        count = _argument(action, "count")
        return float(count) if isinstance(count, int) else 0.0
    if action_id in _IMPERIUM_ACQUISITIONS or action_id in _RESERVE_ACQUISITIONS:
        cost = _acquisition_cost(action)
        return _ACQUISITION_BASE + (float(cost) if cost is not None else 0.0)
    if action_id == "agent_turn":
        space_id = _argument(action, "space_id")
        bonus = _SPACE_BONUSES.get(space_id, 0.0) if isinstance(space_id, str) else 0.0
        return _ACTION_SCORES["agent_turn"] + bonus
    if action_id in _ACTION_SCORES:
        return _ACTION_SCORES[action_id]
    if action_id.startswith("decline_"):
        return _DECLINE_SCORE
    if action_id.startswith("pass_"):
        return _PASS_SCORE
    if action_id.startswith("retreat_"):
        return _RETREAT_SCORE
    if action_id.startswith("place_") and action_id.endswith("_spy"):
        return _SPY_PLACEMENT_SCORE
    if action_id.startswith(("trash_", "pay_", "recall_")):
        return _MINOR_ACTION_SCORE
    return 0.0


def _argument(action: DomainAction, name: str) -> ActionValue | None:
    for key, value in action.arguments:
        if key == name:
            return value
    return None


def _acquisition_cost(action: DomainAction) -> int | None:
    """Printed acquisition cost of the card an acquisition action targets."""

    if action.action_id in _IMPERIUM_ACQUISITIONS:
        instance_id = _argument(action, "instance_id")
        if isinstance(instance_id, str):
            try:
                return imperium_card_for_instance(instance_id).acquisition_cost
            except ValueError:
                return None
        return None
    card_id = _argument(action, "card_id")
    if isinstance(card_id, str):
        entry = RESERVE_STACKS_BY_ID.get(card_id)
        if entry is not None:
            return entry.acquisition_cost
    return None


@dataclass(slots=True)
class HeuristicAgent:
    """Pick a highest-scoring legal action, breaking ties with a seeded RNG."""

    seed: int
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise ValueError("agent seed must not be negative")
        self._rng = random.Random(self.seed)

    def choose_action(
        self,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        """Return one top-ranked action without inspecting hidden state."""

        if not legal_actions:
            raise ValueError("a heuristic agent requires at least one legal action")
        if any(action.actor != observation.player for action in legal_actions):
            raise ValueError("every legal action must belong to the observing player")
        scored = tuple(score_action(action) for action in legal_actions)
        best = max(scored)
        top = tuple(
            action
            for action, score in zip(legal_actions, scored, strict=True)
            if score == best
        )
        return self._rng.choice(top)
