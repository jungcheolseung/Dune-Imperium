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
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final

from dune_imperium.content.immortality.board import (
    RESEARCH_SPACES_BY_ID,
    ResearchBonus,
)
from dune_imperium.content.immortality.tleilaxu import tleilaxu_card_for_instance
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
    "complete_contract_by_card": 8.0,
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
    # Reveal choice reordering never changes what the rule-based agent
    # would gain; it resolves choices in card order and finishes.
    "defer_reveal_choice": -5.0,
    "resume_reveal_choice": -5.0,
    # Deploy everything the engine allows, then close the turn. Taking
    # troops back (OQ-029) ranks below every decline and pass so the agent
    # never cycles withdraw/deploy instead of settling a pending choice.
    "finish_agent_turn": 0.5,
    # Reveal gains are always taken; the order rarely matters to the rules
    # agent, so it takes them before shopping.
    "recruit_reveal_troops": 4.0,
    "draw_reveal_intrigue": 4.0,
    # Immortality: take the Reveal's specimens, answer research choices,
    # and prefer the paid research bonus; returning specimens is a last
    # resort so the heuristic does not undo its own tanks.
    "generate_reveal_specimens": 4.0,
    "advance_reveal_tleilaxu": 4.0,
    "advance_reveal_research": 4.0,
    "pay_agent_card_specimen": 2.0,
    "choose_research_space": 3.0,
    "choose_research_influence": 3.0,
    "pay_research_bonus": 2.5,
    "trash_for_research_bonus": 1.0,
    "decline_research_bonus": 0.5,
    "use_family_atomics": 0.3,
    # Strictly below ``_DECLINE_SCORE``: at -2.0 this tied with every
    # decline, so the agent emptied its own tanks instead of declining a
    # Tech tile or a Commander (12-game probe, all options on).
    "return_specimen": -2.5,
    # A Tleilaxu card costs specimens instead of Persuasion, so it is
    # ranked the way Imperium cards are: a base plus the printed cost,
    # plus ``_TLEILAXU_BONUSES``. Reclaimed Forces is the fallback use of
    # three specimens and scores by the option chosen.
    "acquire_tleilaxu": 2.5,
    "acquire_reclaimed_forces": 1.0,
    # Graft: the partner is mandatory once a grafted placement was chosen.
    # Switching to the other card's box ranks below every box resolution
    # and decline, or the agent would switch back and forth forever
    # (2026-09-08 all-option soak, seeds 3 and 6).
    "choose_graft_partner": 4.0,
    "switch_graft_card": 0.2,
    "decline_agent_card_recall": 0.5,
    "acquire_intrigue_tleilaxu": 2.5,
    "decline_intrigue_tleilaxu": 0.5,
    # Slice 5b-2 cards: two specimens for two track steps is a bargain, a
    # kept Intrigue is a draw, a Victory Point outranks one Influence,
    # and the Surgeon's troop sacrifice ranks below keeping the troops.
    "pay_agent_card_two_specimens": 2.5,
    "trash_grafted_card_for_specimen": 0.8,
    "take_agent_card_combat_icon": 1.5,
    "keep_peeked_intrigue": 2.0,
    "acquire_reserve_by_card": 2.0,
    "lose_reveal_influence_for_vp": 3.0,
    "decline_reveal_influence_loss": 0.5,
    "deploy_reveal_card_troop": 2.0,
    "retreat_reveal_card_troop": 0.2,
    "decline_reveal_troop_move": 0.5,
    "lose_reveal_troops_for_specimens": 0.4,
    "decline_reveal_troop_sacrifice": 0.6,
    # Tleilaxu deck boxes: a Victory Point for a card, five Solari for a
    # track step, and Piter's troop for two cards are all worth taking;
    # trashing a grafted card for one Influence is not.
    "trash_agent_card_self_for_vp": 3.0,
    "pay_agent_card_five_solari_for_tleilaxu": 2.2,
    "trash_grafted_card_for_influence": 0.3,
    "lose_agent_card_troop": 1.2,
    "choose_agent_card_reward": 2.0,
    "gain_reveal_resources": 4.0,
    "gain_reveal_faction_influence": 4.0,
    # An Intrigue card's separate printed lines are used one at a time and
    # paid when used (OQ-058). Using a line ranks with the other paid arrow
    # effects and finishing the card with the other frame closers, or the
    # two tie at zero and the agent abandons half the lines it played the
    # card for (12-game probe, all options on).
    "use_intrigue_effect": 2.5,
    "finish_intrigue_effects": 0.5,
    # Delivery Logistics' "1 Persuasion OR a contract" and the Bloodlines
    # Immediate's contract: a contract is a Victory Point path, so both
    # rank with ``take_contract`` rather than at zero.
    "take_reveal_contract": 2.0,
    "take_trigger_contract": 2.0,
    "gain_reveal_persuasion": 1.0,
    "withdraw_troops": -10.0,
    # Bloodlines: a Sardaukar Commander is a 2-strength unit for 2 Solari
    # plus a Skill; buying one from the board outranks a plain recruit.
    "acquire_sardaukar_commander": 3.0,
    "recruit_sardaukar_commander": 1.5,
    "trash_skill_for_strength": 1.0,
    "withdraw_commanders": -10.0,
    # Tech Module: a tile is a permanent upgrade; buying outranks most
    # minor picks and never blocks a turn (the decline still ranks lowest).
    "acquire_tech": 2.5,
    # Flips are free once per round; Forbidden Weapons' swords beat losing
    # all spice, and Plasteel Blades' extra Skill is worth the tile.
    "flip_tech": 1.5,
    "choose_tech_strength": 1.0,
    "choose_tech_trash": -1.0,
    "choose_secret_project": 1.0,
    "gain_leader_signet_spice": 1.5,
    "trash_leader_tech": 0.5,
}

_IMPERIUM_ACQUISITIONS: Final = frozenset(
    {
        "acquire_imperium",
        "acquire_imperium_with_solari",
        "acquire_imperium_by_card",
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
_COUNT_DEPLOYMENTS: Final = frozenset(
    {"deploy_troops", "deploy_intrigue_troops", "deploy_commanders"}
)

# Actions that leave a grafted card's box untouched; when only these
# accompany the switch, switching is the way forward.
_SWITCH_NEUTRAL_ACTIONS: Final = frozenset(
    {
        "switch_graft_card",
        "withdraw_troops",
        "withdraw_commanders",
        "deploy_troops",
        "deploy_commanders",
        "return_specimen",
        "use_family_atomics",
        "finish_agent_turn",
    }
)
_ACQUISITION_BASE: Final = 3.0
_SPY_PLACEMENT_SCORE: Final = 3.0
_MINOR_ACTION_SCORE: Final = 1.0
_DECLINE_SCORE: Final = -2.0
_PASS_SCORE: Final = -3.0
_RETREAT_SCORE: Final = -1.0

# Board space preference. Only Swordmaster and High Council were ranked
# before 2026-09-10, so the other 21 spaces tied at ``agent_turn``'s base and
# the agent picked among them almost uniformly -- 1,652 of 15,296 legal-action
# sets in a 20-game all-option probe were ``agent_turn`` argument ties, the
# single largest tie family by an order of magnitude.
#
# The values below are strategy preference, not a rules judgment (see the
# module docstring): each space's printed yield comes from
# ``docs/rules/board-spaces.md`` `[Board Guide pp. 1-2]`, and that yield is
# priced on one rubric and reduced by the printed cost, so the numbers stay
# comparable to each other and to the reward scores in ``_ACTION_SCORES``:
#
#   Influence 1   0.45   (a Victory Point at 2 and an Alliance at 4)
#   sandworm 1    0.45   Maker Hooks 0.35   control location 0.35
#   Intrigue 1    0.30   Spy placement 0.25   water 1 0.22
#   card 1        0.20   troop 1 0.18   spice 1 0.12   Solari 1 0.07
#
# Permanent upgrades stay on top at their established values: a third Agent
# for the rest of the game and a Council seat's standing +2 Persuasion are
# worth more than any one-shot yield, so every priced space lands below them.
#
# Two limits are deliberate. ``score_action`` sees only the action, so a space
# whose yield depends on the ruleset is priced on its base reward -- Dutiful
# Service and Accept Contract pay 2 Solari here rather than a CHOAM contract,
# and Research Station omits the Immortality research advance. And a space
# with several cost options is one value, so Gather Support's two Solari for a
# water and Spice Refinery's spice for two more Solari still tie; that and the
# ``card_id`` half of an ``agent_turn`` tie are the remaining argument ties.
_SPACE_BONUSES: Final[Mapping[str, float]] = MappingProxyType(
    {
        # Permanent upgrades keep their established values.
        "swordmaster": 3.0,
        "high_council": 2.0,
        # Influence plus a big recruit, or Intrigue plus the steal from every
        # opponent holding four or more.
        "sardaukar": 1.0,
        "secrets": 1.0,
        # A second placement this turn, behind Emperor Influence 2.
        "imperial_privilege": 0.9,
        # A control location that also pays spice every round.
        "imperial_basin": 0.85,
        "espionage": 0.8,
        "heighliner": 0.8,
        "arrakeen": 0.75,
        "sietch_tabr": 0.75,
        "deliver_supplies": 0.7,
        "fremkit": 0.65,
        "deep_desert": 0.6,
        "dutiful_service": 0.6,
        "hagga_basin": 0.6,
        "tuek_sietch": 0.55,
        "assembly_hall": 0.5,
        "desert_tactics": 0.5,
        "spice_refinery": 0.5,
        "shipping": 0.45,
        "gather_support": 0.4,
        # Both pay the least once their cost is priced in.
        "accept_contract": 0.35,
        "research_station": 0.35,
    }
)

# The ranking before the 2026-09-10 retune, kept so the registry's
# ``heuristic_untuned`` baseline reproduces it for a paired A/B from the
# committed tree instead of needing a scratch module.
SPACE_BONUSES_BEFORE_RETUNE: Final[Mapping[str, float]] = MappingProxyType(
    {"swordmaster": 3.0, "high_council": 2.0}
)


# Which board space ranking applies. The retuned table above prices each
# space's printed Uprising yield and measured +4.9pp and +5.1pp against the old
# two-entry ranking on base+CHOAM, over two independent 2,000-match blocks
# (2026-09-10, docs/evaluation/baseline-2026-09-10.md). With every expansion on
# the same table measured -5.6pp, and an attempt to overlay the spaces the
# expansions upgrade -- Immortality's revised Research Station
# [Immortality pp. 5, 16], the Landsraad route to a Tech tile
# [Bloodlines pp. 7, 12], the spaces holding a Commander [Bloodlines pp. 4, 12]
# -- measured far worse still at -34pp, because lifting those mostly
# non-Combat spaces pulled the agent out of Conflicts (Combat placements
# 46.1% -> 39.7%, mean VP 8.20 -> 5.73). So the retune is scoped to the
# rulesets it is measured on and an expansion table keeps the ranking it had;
# pricing expansion spaces wants the Combat balance rebuilt with it, not a
# bonus added on top.
def space_bonuses_for(observation: PlayerView) -> Mapping[str, float]:
    """Return the board space ranking measured for this view's ruleset.

    The expansions are read off the observation, never a config the agent is
    not given: a three-entry ``tech_stack_sizes`` means the Tech Module is on,
    a seat's ``research_space`` is set only under Immortality, and a Skill
    stack or a Commander on the board means Bloodlines. Every marker survives
    a late game -- the stacks stay three once emptied, the Research tokens
    never leave the track -- so the ranking cannot flip mid-game.
    """

    expansion = (
        len(observation.tech_stack_sizes) == 3
        or any(seat.research_space for seat in observation.players)
        or bool(observation.skill_stack_size)
        or bool(observation.sardaukar_commander_space_ids)
    )
    return SPACE_BONUSES_BEFORE_RETUNE if expansion else _SPACE_BONUSES


_TECH_BONUSES: Final[dict[str, float]] = {
    "sardaukar_high_command": 2.0,
    "choam_transports": 1.5,
    "panopticon": 1.0,
    "navigation_chamber": 1.0,
    "ornithopter_fleet": 1.0,
    "delivery_bay": 0.5,
    "plasteel_blades": 0.5,
    "spy_drones": 0.5,
    "suspensor_suits": 0.5,
    "training_depot": 0.5,
}

# Tleilaxu cards (Immortality) whose printed box pays back the moment the
# card is bought or scores outright: an acquisition box, a Victory Point,
# or a Reveal box that puts a specimen back in the tanks every round. Every
# other card keeps the cost-scaled score, so a buy still outranks a decline
# whatever the card [Immortality pp. 8-9] [Tleilaxu card faces].
_TLEILAXU_BONUSES: Final[dict[str, float]] = {
    "subject_x_137": 1.0,
    "scientific_breakthrough": 1.0,
    "corrino_genes": 0.5,
    "twisted_mentat": 0.5,
    "usurp": 0.5,
}

# The research track's branch choice is worth what the destination space
# pays. The scale mirrors ``rollout_agent.player_value`` so both baselines
# rank the same step the same way: an Influence is 1.5 there, a specimen
# and a Tleilaxu step 0.5, spice 0.4, Solari 0.25. A Research space is the
# best of all because it "triggers another research icon and immediately
# advances her token again" [Immortality p. 6], a free extra space.
_RESEARCH_BONUS_SCORES: Final[dict[ResearchBonus, float]] = {
    ResearchBonus.RESEARCH: 2.0,
    ResearchBonus.INFLUENCE_ANY: 1.5,
    ResearchBonus.TLEILAXU_AND_SPECIMEN: 1.0,
    ResearchBonus.TRASH_FOR_CARD_AND_INTRIGUE: 1.0,
    ResearchBonus.SEVEN_SOLARI_FOR_TWO_TLEILAXU: 1.0,
    ResearchBonus.SPICE_TWO: 0.8,
    ResearchBonus.TRASH_AND_SPECIMEN: 0.75,
    ResearchBonus.SPECIMEN: 0.5,
    ResearchBonus.TLEILAXU: 0.5,
    ResearchBonus.SPICE_ONE: 0.4,
    ResearchBonus.SOLARI_ONE: 0.25,
    ResearchBonus.NONE: 0.0,
}

# Reclaimed Forces' two options for the same three specimens: "recruit 2
# troops" or "advance the Tleilaxu token 1 space" [Immortality p. 9]. Two
# garrison troops outweigh one track step on the same ``player_value``
# scale (0.6 each against 0.5), so the units are the static default.
_RECLAIMED_FORCES_SCORES: Final[dict[str, float]] = {
    "troops": 0.7,
    "tleilaxu": 0.5,
}

# Putting an acquired Tleilaxu card straight on the deck instead of in the
# discard pile is a free upgrade once the first genetic marker is reached
# [Immortality p. 6]; it draws the card a whole reshuffle sooner.
_TLEILAXU_DECK_TOP_BONUS: Final = 0.5


def score_action(
    action: DomainAction,
    *,
    space_bonuses: Mapping[str, float] = _SPACE_BONUSES,
) -> float:
    """Rank one engine-legal action; higher is preferred.

    ``space_bonuses`` is the board space preference to rank ``agent_turn``
    with. Passing an earlier table reproduces an earlier ranking, which is how
    the registry offers a paired A/B opponent from the committed tree.
    """

    action_id = action.action_id
    if action_id in _COUNT_DEPLOYMENTS:
        count = _argument(action, "count")
        return float(count) if isinstance(count, int) else 0.0
    if action_id in _IMPERIUM_ACQUISITIONS or action_id in _RESERVE_ACQUISITIONS:
        cost = _acquisition_cost(action)
        return _ACQUISITION_BASE + (float(cost) if cost is not None else 0.0)
    if action_id == "agent_turn":
        space_id = _argument(action, "space_id")
        bonus = space_bonuses.get(space_id, 0.0) if isinstance(space_id, str) else 0.0
        return _ACTION_SCORES["agent_turn"] + bonus
    if action_id == "acquire_tech":
        tech_id = _argument(action, "tech_id")
        bonus = _TECH_BONUSES.get(tech_id, 0.0) if isinstance(tech_id, str) else 0.0
        return _ACTION_SCORES["acquire_tech"] + bonus
    if action_id == "acquire_tleilaxu":
        return _ACTION_SCORES["acquire_tleilaxu"] + _tleilaxu_acquisition_bonus(action)
    if action_id == "acquire_reclaimed_forces":
        choice = _argument(action, "choice")
        bonus = (
            _RECLAIMED_FORCES_SCORES.get(choice, 0.0)
            if isinstance(choice, str)
            else 0.0
        )
        return _ACTION_SCORES["acquire_reclaimed_forces"] + bonus
    if action_id == "choose_research_space":
        space_id = _argument(action, "space_id")
        space = (
            RESEARCH_SPACES_BY_ID.get(space_id) if isinstance(space_id, str) else None
        )
        bonus = 0.0 if space is None else _RESEARCH_BONUS_SCORES.get(space.bonus, 0.0)
        return _ACTION_SCORES["choose_research_space"] + bonus
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


def _tleilaxu_acquisition_bonus(action: DomainAction) -> float:
    """Printed specimen cost, card bonus, and deck-top bonus of a buy."""

    instance_id = _argument(action, "instance_id")
    if not isinstance(instance_id, str):
        return 0.0
    try:
        entry = tleilaxu_card_for_instance(instance_id)
    except ValueError:
        return 0.0
    bonus = float(entry.specimen_cost) + _TLEILAXU_BONUSES.get(entry.card.card_id, 0.0)
    if _argument(action, "to_deck_top"):
        bonus += _TLEILAXU_DECK_TOP_BONUS
    return bonus


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
    # A fixed board space ranking, or None to derive one per observation with
    # ``space_bonuses_for``. The registry pins the pre-retune table on one
    # variant so an A/B against the earlier ranking is reproducible from the
    # committed tree.
    space_bonuses: Mapping[str, float] | None = None
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
        bonuses = (
            space_bonuses_for(observation)
            if self.space_bonuses is None
            else self.space_bonuses
        )
        scored = tuple(
            score_action(action, space_bonuses=bonuses) for action in legal_actions
        )
        if any(
            action.action_id not in _SWITCH_NEUTRAL_ACTIONS for action in legal_actions
        ):
            # Switching to the other grafted card only reorders the boxes;
            # whenever the active box (or a decline of it) can be resolved,
            # that comes first, or two boxes whose offers rank below the
            # switch loop forever (Ghola copying Corrinth City or CHOAM
            # Demands, 2026-09-08 seeds 11 and 32).
            scored = tuple(
                min(scored) - 1.0 if action.action_id == "switch_graft_card" else s
                for action, s in zip(legal_actions, scored, strict=True)
            )
        best = max(scored)
        top = tuple(
            action
            for action, score in zip(legal_actions, scored, strict=True)
            if score == best
        )
        return self._rng.choice(top)
