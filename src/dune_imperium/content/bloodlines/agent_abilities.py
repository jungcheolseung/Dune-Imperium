"""Bloodlines' personal cards' Agent boxes, by card id.

docs/content-core-refactor-plan.md 8.3 (stage 4, step 3): each value is
the box's key -- the stable string its display text and record are found
by (``content.registry.card_abilities.agent_box_key``).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.core.abilities import (
    Ability,
    AbilityStructure,
    AbilityTiming,
)
from dune_imperium.content.core.agent_boxes import (
    agent_box,
    box_line,
    discard_box,
    icon_box,
    trash_box,
)
from dune_imperium.content.core.effects import (
    BoostNextBeneGesseritCard,
    CommandersInConflictAtLeast,
    CompleteContract,
    ContractCompletedThisTurn,
    DiscardedCardHasFaction,
    DrawIntrigueCards,
    DrawPersonalCards,
    EachOpponentLosesTroop,
    EffectSection,
    FactionBond,
    ForceEnemyRetreat,
    GainedSpiceThisTurn,
    GainInfluence,
    GainResources,
    GrantCombatDeployment,
    InfluenceAtLeast,
    OpponentsMoveSpiesFromVisitedSpace,
    PlaceSpy,
    RecruitTroops,
    SandwormsInConflictAtLeast,
    SpyRecalledThisTurn,
    TakeContract,
    TrashCard,
    TrashedCardHasFaction,
    TrashPersonalCard,
)
from dune_imperium.content.core.icons import (
    Faction,
)

_BG = Faction.BENE_GESSERIT
_BG_BOND = FactionBond(_BG)
_TWO_SPICE = GainedSpiceThisTurn(2)
_GUILD_DISCARD = DiscardedCardHasFaction(Faction.SPACING_GUILD)
_COMMANDER_IN_CONFLICT = CommandersInConflictAtLeast(1)
_EMPEROR_TRASH = TrashedCardHasFaction(Faction.EMPEROR)


BLOODLINES_AGENT_BOXES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "ruthless_leadership": "may_trash_two_cards_if_commander_in_conflict",
        "arrakis_observer": "may_discard_for_deep_cover_spy",
        "choam_demands": "complete_one_contract",
        "command_center": "recruit_one_if_emperor_influence_two",
        "corrupt_bureaucrat": "take_contract_if_spy_recalled_this_turn",
        "disruption_tactics": "force_opponent_troop_retreat",
        "eliminate_allies": "trash_personal_card",
        "elite_forces": "may_trash_hand_card_for_emperor_rewards",
        "engineered_miracle": "may_discard_for_water",
        "fremen_war_name": "recruit_one_and_draw_one_if_gained_two_spice_this_turn",
        "holy_war": "each_opponent_loses_troop_and_moves_spy",
        "i_believe": "may_discard_to_draw_one",
        "imperial_throneship": "draw_intrigue_card",
        "ixian_ambassador": "gain_one_spice",
        "mercantile_affairs": "draw_intrigue_if_contract_completed_this_turn",
        "pointing_the_way": "draw_intrigue_if_sandworm_in_conflict",
        "possible_futures": "chosen_influence_or_two_troops_both_if_bond",
        "quash_rebellion": "gain_two_solari",
        "sandwalk": "draw_one_if_gained_two_spice_this_turn",
        "shrouded_counsel": "draw_intrigue_card",
        "southern_faith": "draw_one_or_bene_gesserit_influence_if_bond",
        "urgent_shigawire": "boost_next_bene_gesserit_card_this_round",
    }
)


# The Agent-box records only this set's cards print, by box key.
BLOODLINES_AGENT_BOX_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        "gain_one_spice": agent_box(GainResources(spice=1)),
        "boost_next_bene_gesserit_card_this_round": agent_box(
            BoostNextBeneGesseritCard()
        ),
        "recruit_one_if_emperor_influence_two": agent_box(
            RecruitTroops(1), condition=InfluenceAtLeast(Faction.EMPEROR, 2)
        ),
        "draw_one_if_gained_two_spice_this_turn": agent_box(
            DrawPersonalCards(1), condition=_TWO_SPICE
        ),
        "draw_intrigue_if_sandworm_in_conflict": agent_box(
            DrawIntrigueCards(1), condition=SandwormsInConflictAtLeast(1)
        ),
        "draw_intrigue_if_contract_completed_this_turn": agent_box(
            DrawIntrigueCards(1), condition=ContractCompletedThisTurn()
        ),
        "take_contract_if_spy_recalled_this_turn": agent_box(
            TakeContract(1), condition=SpyRecalledThisTurn()
        ),
        # Disruption Tactics.
        "force_opponent_troop_retreat": agent_box(ForceEnemyRetreat()),
        # CHOAM Demands.
        "complete_one_contract": agent_box(CompleteContract()),
        # Engineered Miracle.
        "may_discard_for_water": discard_box(box_line(GainResources(water=1))),
        # Arrakis Observer: "You may discard a card -> Place a Spy with Deep
        # Cover; if you discarded a Spacing Guild card: Gain 2 spice" -- the
        # spice comes with the discard, the Spy is the box's next step.
        "may_discard_for_deep_cover_spy": discard_box(
            box_line(PlaceSpy(shared_post=True)),
            box_line(GainResources(spice=2), condition=_GUILD_DISCARD),
        ),
        # Ruthless Leadership: "If you have one or more Sardaukar Commanders
        # in the Conflict: You may trash a card, You may trash a card", the
        # condition judged at each trash (OQ-028).
        "may_trash_two_cards_if_commander_in_conflict": trash_box(
            box_line(TrashPersonalCard(), condition=_COMMANDER_IN_CONFLICT),
            box_line(TrashPersonalCard(), condition=_COMMANDER_IN_CONFLICT),
        ),
        # Elite Forces: "You may trash a card from your hand. If you trash an
        # Emperor card: Draw 1 Intrigue card, Recruit 1 troop, Combat" -- the
        # draw and the troop armed as icons, the Combat paid with the trash.
        "may_trash_hand_card_for_emperor_rewards": trash_box(
            EffectSection(
                rewards=(DrawIntrigueCards(1),),
                condition=_EMPEROR_TRASH,
                costs=(TrashCard(hand_only=True),),
            ),
            box_line(RecruitTroops(1), condition=_EMPEROR_TRASH),
            box_line(GrantCombatDeployment(), condition=_EMPEROR_TRASH),
            armed=("intrigue", "troops"),
        ),
        # --- A plain line beside a choice line (composed effects, A3f) ------
        # Southern Faith: "Choose one: Draw 1 card / If Bene Gesserit Bond:
        # Gain 1 Bene Gesserit Influence".
        "draw_one_or_bene_gesserit_influence_if_bond": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                box_line(DrawPersonalCards(1)),
                box_line(GainInfluence(factions=(_BG,)), condition=_BG_BOND),
            ),
            structure=AbilityStructure.ONE_OF,
        ),
        # Possible Futures: "Choose one: Gain 1 Influence with a chosen
        # Faction / Recruit 2 troops; if Bene Gesserit Bond: get both" -- the
        # Bond turns the choice into both, named apart, so the flow stays code
        # (``agent_effects`` hook ``possible_futures``).
        "chosen_influence_or_two_troops_both_if_bond": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(box_line(GainInfluence()), box_line(RecruitTroops(2))),
            structure=AbilityStructure.ONE_OF,
            hook="possible_futures",
        ),
        # Holy War: "Each opponent loses one troop. Each opponent spying on
        # the board space where you sent an Agent this turn must move that
        # Spy" -- every loss first, then the Spy moves (OQ-036).
        "each_opponent_loses_troop_and_moves_spy": agent_box(
            EachOpponentLosesTroop(), OpponentsMoveSpiesFromVisitedSpace()
        ),
        # Fremen War Name: "If you gained [2 spice] or more this turn:".
        "recruit_one_and_draw_one_if_gained_two_spice_this_turn": icon_box(
            ("troops", box_line(RecruitTroops(1), condition=_TWO_SPICE)),
            ("cards", box_line(DrawPersonalCards(1), condition=_TWO_SPICE)),
        ),
    }
)
