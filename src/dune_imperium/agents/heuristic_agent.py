"""Simple rule-based heuristic opponent.

``HeuristicAgent`` is the first non-random AI opponent for the M11 human
play interface and is deliberately reused as the starting point of the M9
heuristic baseline. It keeps the exact ``choose_action`` contract of
``RandomAgent``: one ``PlayerView`` plus the legal actions, never hidden
state.

The policy is a static strategy preference over engine-legal actions, not a
rules judgment: the engine alone decides legality and the agent only ranks
what it is offered. Rankings may read printed public card data (acquisition
costs, the Persuasion and swords in a Reveal box) through the content
manifests, exactly as a human reads card text at the table. Unknown action IDs
score 0, so new content degrades to a seeded uniform choice instead of
failing.
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
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
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
UPRISING_SPACE_BONUSES: Final[Mapping[str, float]] = MappingProxyType(
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


# Which board space ranking applies.
#
# The table above prices each space's printed Uprising yield and measured
# +4.9pp and +5.1pp on base+CHOAM against the two-entry ranking it replaced
# (2026-09-10). It was then scoped away from every expansion on one
# all-expansion run that measured -5.6pp. Re-measuring per expansion, with the
# expansions separated instead of stacked, says that -5.6pp was two effects
# cancelling and that only one expansion dislikes the table
# (docs/evaluation/baseline-2026-09-10.md section 15; 4,000 agent-games each):
#
#   Immortality only          +16.0pp   the table is what that ruleset wants
#   Bloodlines only            +3.8pp
#   Bloodlines + Tech Module   -6.6pp, -4.8pp on a second seed block
#   all four expansions        -0.2pp, -0.8pp   the two above cancelling
#
# The Tech Module is the one that punishes it, and the reason is printed on
# the Ixian Embassy: "during a turn in which you send an Agent to a Landsraad
# board space, you may acquire one Tech tile" `[Bloodlines p. 7]`. The Tech
# tile has no board space of its own -- the offer rides on whichever of the
# five Landsraad spaces the Agent named -- and this table ranks the cheap ones
# near the bottom (Assembly Hall 0.50, Gather Support 0.40). So the agent stops
# visiting Landsraad and stops buying tiles: 2.48 -> 1.16 tiles a seat, with
# Commanders 0.62 -> 0.35, over a 30-game all-option probe.
#
# Until a Tech ranking is priced and measured, that one ruleset keeps the
# two-entry table it was measured with and every other ruleset uses the priced
# one.
def space_bonuses_for(observation: PlayerView) -> Mapping[str, float]:
    """Return the board space ranking measured for this view's ruleset.

    The Tech Module is read off the observation, never a config the agent is
    not given: ``tech_stack_sizes`` has one entry per Ixian Embassy stack, and
    the stacks stay on the board once emptied, so the ranking cannot flip
    mid-game.
    """

    tech_module = len(observation.tech_stack_sizes) == 3
    return SPACE_BONUSES_BEFORE_RETUNE if tech_module else UPRISING_SPACE_BONUSES


# Which card an Agent turn spends, once the board space is settled.
#
# "Agent turn에는 낸 card의 Agent box만 처리하고 그 card의 Reveal box는
# 무시한다." `[Main p. 8]` `[Main p. 9]`, and on the Reveal turn "앞선 Agent
# turn에 낸 card의 Reveal box 효과는 얻지 않는다." `[Main p. 12]`
# (``docs/rules/player-turns.md`` lines 60 and 161). So sending the same Agent
# to the same space costs a different amount depending on which hand card
# carries it: the Persuasion and swords printed in the Reveal box that card
# will never open this round.
#
# Both weights come off the rubric the board space table is priced on:
#
#   Persuasion 1  0.20  Assembly Hall is ranked 0.5 and pays "Intrigue 1장
#                       draw" plus "Persuasion 1" `[Board Guide p. 1]`; the
#                       rubric prices an Intrigue at 0.30, leaving 0.20.
#   sword 1       0.09  "Conflict의 troop 하나는 strength 2 ... reveal한 sword
#                       하나는 strength 1" `[Main p. 12]`, and the rubric
#                       prices a recruited troop at 0.18 -- half a troop's
#                       combat contribution, which is what one sword is.
#
# Only the ratio between the two is load-bearing: the tie-break takes an
# argmin, so scaling both weights together changes nothing. They are kept on
# the board rubric anyway, so a later change that does compare a card against a
# space starts from a value that is already comparable to one.
#
# This is applied as a tie-break *inside one space*, never as a term added to
# ``score_action``. Adding it to the score was measured and rejected: at full
# rubric weight it is the size of a space bonus and reorders the spaces instead
# of the cards -- the cheapest card to send (Dagger: no Persuasion, one sword)
# carries only the Landsraad icon, so Dagger placements doubled, Assembly Hall
# and Gather Support absorbed them, the Combat placement share fell
# 50.2% -> 46.5%, and three paired blocks measured -2.2pp, -6.0pp and -8.6pp.
# Scaling it down to fit inside the board table's smallest gap fixed
# base+CHOAM (-0.2pp, +0.2pp) but reproduced the expansion loss *exactly*, to
# the decision count: an expansion ruleset keeps the two-entry table
# (``space_bonuses_for``), so 21 spaces are equal there and any card term at
# all -- at any scale -- picks the space. Only a tie-break that never compares
# two spaces is safe in both. Numbers in
# ``docs/evaluation/baseline-2026-09-10.md`` section 14.
#
# Two limits are deliberate, and both understate the cost rather than invent a
# value. The printed integers are priced but a Reveal box's *effects* are not
# (67 of the 105 Imperium cards that can be sent carry one). And a Graft
# placement names only its own card; the partner is chosen in a later frame
# `[Immortality p. 10]`, so the partner's Reveal box is not counted.
#
# The Agent box a card *pays* is not priced either. That half needs a value for
# each transcribed Agent effect and is a separate measurement; leaving it out
# keeps this change attributable to one term.
@dataclass(frozen=True, slots=True)
class RevealValue:
    """Per-unit price of the Reveal box an Agent turn gives up."""

    persuasion: float
    sword: float


SPENT_CARD_VALUE: Final = RevealValue(persuasion=0.20, sword=0.09)


def reveal_value_forfeited(
    action: DomainAction, weights: RevealValue | None
) -> float:
    """Reveal value the placement's card forfeits, or 0.0 when unpriced."""

    if weights is None or action.action_id != "agent_turn":
        return 0.0
    instance_id = _argument(action, "card_id")
    if not isinstance(instance_id, str):
        return 0.0
    try:
        card = personal_card_for_instance(instance_id)
    except (ValueError, NotImplementedError):
        # New or untranscribed content falls back to the flat ranking rather
        # than failing, exactly as an unknown action ID scores 0.
        return 0.0
    return (
        weights.persuasion * card.reveal_persuasion
        + weights.sword * card.reveal_strength
    )


def cheapest_card_for_the_same_space(
    chosen: DomainAction,
    tied: tuple[DomainAction, ...],
    weights: RevealValue | None,
) -> DomainAction:
    """Re-spend ``chosen``'s placement on its cheapest tied hand card.

    ``chosen`` already fixes the board space -- it was drawn from ``tied`` by
    the seeded tie-break, so the space distribution is untouched. Only the card
    carrying the Agent there is reconsidered, among the tied placements that
    name the same space. Anything but an ``agent_turn`` is returned unchanged.
    """

    if weights is None or chosen.action_id != "agent_turn":
        return chosen
    space_id = _argument(chosen, "space_id")
    same_space = tuple(
        action
        for action in tied
        if action.action_id == "agent_turn"
        and _argument(action, "space_id") == space_id
    )
    if len(same_space) < 2:
        return chosen
    priced = tuple(
        (reveal_value_forfeited(action, weights), action) for action in same_space
    )
    cheapest = min(cost for cost, _ in priced)
    if reveal_value_forfeited(chosen, weights) == cheapest:
        # The draw already spends one of the cheapest cards; leave it alone so
        # everything else it settled stays settled.
        return chosen
    winners = tuple(action for cost, action in priced if cost == cheapest)
    # Swap the card and nothing else. One card reaches one space once per cost
    # option, once more per Navigation Chamber discount, and again for a Graft
    # or an Infiltrate, and every one of those forfeits the same Reveal box --
    # so taking the first cheapest would quietly move the cost option the draw
    # made, drop a discount that costs nothing to keep (97 of 6,198 separating
    # swaps over a 40-game all-option probe, and 777 with several cost
    # options), or spend a Spy on an Infiltrate the draw did not ask for.
    terms = _placement_terms(chosen)
    return next(
        (action for action in winners if _placement_terms(action) == terms),
        winners[0],
    )


def _placement_terms(action: DomainAction) -> tuple[tuple[str, ActionValue], ...]:
    """Everything an ``agent_turn`` settles except which card pays for it."""

    return tuple((key, value) for key, value in action.arguments if key != "card_id")


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
    space_bonuses: Mapping[str, float] = UPRISING_SPACE_BONUSES,
) -> float:
    """Rank one engine-legal action; higher is preferred.

    ``space_bonuses`` is the board space preference to rank ``agent_turn``
    with. Passing an earlier table reproduces an earlier ranking, which is how
    the registry offers a paired A/B opponent from the committed tree. Which
    card an ``agent_turn`` spends is not scored here; it is settled after the
    tie-break by ``cheapest_card_for_the_same_space``.
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
    # How the Reveal box a placement forfeits is priced, or None to leave every
    # card the same price. The registry pins None on one variant for the same
    # reason.
    spent_card_value: RevealValue | None = SPENT_CARD_VALUE
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
        chosen = self._rng.choice(top)
        # The draw settles the board space; the card carrying the Agent there
        # is then the cheapest Reveal box among the placements that reach it.
        return cheapest_card_for_the_same_space(chosen, top, self.spent_card_value)
