"""Immortality's personal cards' Agent boxes (Imperium and Tleilaxu), by card id.

docs/content-core-refactor-plan.md 8.3 (stage 4, step 3): each value is
the box's key -- the stable string its display text and record are found
by (``content.registry.card_abilities.agent_box_key``).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.core.abilities import (
    Ability,
    AbilityMark,
    AbilityStructure,
    AbilityTiming,
)
from dune_imperium.content.core.agent_boxes import (
    agent_box,
    box_line,
    icon_box,
    pay_box,
)
from dune_imperium.content.core.effects import (
    AcquireCardUpTo,
    AdvanceTleilaxu,
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    FactionBond,
    GainedSpiceThisTurn,
    GainInfluence,
    GainResources,
    GainSolariPerPartnerAgentIcon,
    GainVictoryPoints,
    GenerateSpecimens,
    GeneticMarkersAtLeast,
    Grafted,
    GraftedTrash,
    GraftedWithFaction,
    GrantCombatDeployment,
    HasAlliance,
    InfluenceAtLeast,
    LookAtIntrigueKeepOne,
    LoseTroops,
    PayResources,
    RecallAgent,
    RecruitTroops,
    Research,
    ReturnOtherGraftedCardAtRevealStart,
    ReturnThisCardToHand,
    SpendSpecimens,
    TrashCard,
    TrashPersonalCard,
)
from dune_imperium.content.core.icons import (
    Faction,
)

_BG = Faction.BENE_GESSERIT
_BG_BOND = FactionBond(_BG)
_GUILD_TWO = InfluenceAtLeast(Faction.SPACING_GUILD, 2)


IMMORTALITY_AGENT_BOXES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "bene_tleilax_lab": "generate_specimen",
        "bene_tleilax_researcher": "research",
        "clandestine_meeting": "gain_bene_gesserit_influence_and_intrigue",
        "corrupt_smuggler": "gain_two_spice_if_grafted",
        "dissecting_kit": "may_trash_other_grafted_for_specimen",
        "for_humanity": "gain_chosen_influence",
        "high_priority_travel": (
            "draw_one_or_combat_icon_if_spacing_guild_influence_two"
        ),
        "imperium_ceremony": "peek_two_intrigue_keep_one",
        "interstellar_conspiracy": (
            "gain_spice_and_chosen_influence_if_grafted_with_emperor_or_guild"
        ),
        "keys_to_power": "gain_two_spice_if_emperor_influence_two",
        "lisan_al_gaib": "gain_fremen_influence_if_bene_gesserit_bond",
        "long_reach": "gain_two_distinct_chosen_influence",
        "occupation": "draw_one_and_combat_icon",
        "organ_merchants": "may_pay_specimen_for_four_solari",
        "planned_coupling": "draw_personal_card",
        "replacement_eyes": "trash_personal_card_to_draw_one",
        "sardaukar_quartermaster": "recruit_one_and_draw_one_if_grafted",
        "show_of_strength": "draw_two_cards",
        "stillsuit_manufacturer": "gain_water_and_return_self_if_fremen_alliance",
        "throne_room_politics": "recruit_one_and_may_trash",
        "tleilaxu_master": "may_acquire_card_up_to_six_if_one_marker",
        "tleilaxu_surgeon": "may_pay_two_specimens_for_two_tleilaxu",
        "beguiling_pheromones": "trash_grafted_card_for_visited_faction_influence",
        "chairdog": "return_other_grafted_to_hand_at_reveal_start",
        "contaminator": "advance_tleilaxu",
        "corrino_genes": "advance_tleilaxu_if_grafted",
        "face_dancer": "draw_personal_card",
        "from_the_tanks": "recruit_two_troops",
        "guild_impersonator": "gain_spacing_guild_influence_if_gained_spice_this_turn",
        "industrial_espionage": "draw_one_and_research_and_specimen_if_grafted",
        "scientific_breakthrough": "research_and_may_trash_self_for_vp_if_two_markers",
        "slig_farmer": (
            "gain_solari_per_partner_icon_and_may_pay_five_solari_for_tleilaxu"
        ),
        "stitched_horror": "choose_two_of_water_troop_trash_tleilaxu",
        "subject_x_137": "advance_tleilaxu_if_one_marker",
        "tleilaxu_infiltrator": "draw_one_and_intrigue_if_two_markers",
        "twisted_mentat": "may_recall_agent_sent_this_turn",
        "unnatural_reflexes": "draw_two_if_one_marker",
        "piter_genius_advisor": "may_lose_troop_to_draw_two_and_research",
    }
)


# The cards whose greyed Agent icons are real under a printed condition, judged
# when the card is played: Long Reach "If you have another Bene Gesserit card
# in play", Show of Strength "If you have more deployed troops than each
# opponent" [card faces]. Each value is the condition's key.
IMMORTALITY_ICON_CONDITIONS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "long_reach": "bene_gesserit_bond",
        "show_of_strength": "more_deployed_troops_than_each_opponent",
    }
)


# The Agent-box records only this set's cards print, by box key.
IMMORTALITY_AGENT_BOX_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        "gain_two_spice_if_grafted": agent_box(
            GainResources(spice=2), condition=Grafted()
        ),
        "gain_two_spice_if_emperor_influence_two": agent_box(
            GainResources(spice=2), condition=InfluenceAtLeast(Faction.EMPEROR, 2)
        ),
        # Throne Room Politics: "troop 1 + 검은 trash 아이콘" -- each icon
        # resolves on its own, in the owner's order (OQ-027 card Agent box
        # extension 3, "원칙대로 아이콘마다 나누자"; printed-effects audit P-2,
        # user 2026-11-09); the black trash icon is optional [FAQ p. 3].
        "recruit_one_and_may_trash": icon_box(
            ("troops", box_line(RecruitTroops(1))),
            ("trash", box_line(TrashPersonalCard())),
        ),
        "draw_two_if_one_marker": agent_box(
            DrawPersonalCards(2), condition=GeneticMarkersAtLeast(1)
        ),
        "advance_tleilaxu": agent_box(AdvanceTleilaxu(1)),
        "advance_tleilaxu_if_one_marker": agent_box(
            AdvanceTleilaxu(1), condition=GeneticMarkersAtLeast(1)
        ),
        "advance_tleilaxu_if_grafted": agent_box(
            AdvanceTleilaxu(1), condition=Grafted()
        ),
        "generate_specimen": agent_box(GenerateSpecimens(1)),
        "peek_two_intrigue_keep_one": agent_box(LookAtIntrigueKeepOne(2)),
        # Guild Impersonator: "If you gained spice this turn: [Spacing
        # Guild Influence]".
        "gain_spacing_guild_influence_if_gained_spice_this_turn": agent_box(
            GainInfluence(factions=(Faction.SPACING_GUILD,)),
            condition=GainedSpiceThisTurn(1),
        ),
        # Tleilaxu Master: "If 1 genetic marker: You may acquire a card
        # costing 6 or less, If 2 genetic markers: put it in your hand",
        # both judged when the box resolves (OQ-028).
        "may_acquire_card_up_to_six_if_one_marker": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                box_line(
                    AcquireCardUpTo(6, to_hand_if=GeneticMarkersAtLeast(2)),
                    condition=GeneticMarkersAtLeast(1),
                ),
            ),
            mark=AbilityMark.OPTIONAL,
        ),
        # --- Unit-loss arrow, payment hook (composed effects, A3f) -----------
        # Piter, Genius Advisor: "You may lose 1 troop -> Draw 2 cards,
        # Research", the rewards armed as icons once the troop (or a
        # Sardaukar Commander, OQ-105) is lost (OQ-106).
        "may_lose_troop_to_draw_two_and_research": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                EffectSection(rewards=(DrawPersonalCards(2),), costs=(LoseTroops(),)),
                box_line(Research()),
            ),
            mark=AbilityMark.OPTIONAL,
            armed_icons=("cards", "research"),
        ),
        # High Priority Travel: "If you have 2 or more Spacing Guild
        # Influence: Choose one: Draw 1 card / Combat".
        "draw_one_or_combat_icon_if_spacing_guild_influence_two": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                box_line(DrawPersonalCards(1), condition=_GUILD_TWO),
                box_line(GrantCombatDeployment(), condition=_GUILD_TWO),
            ),
            structure=AbilityStructure.ONE_OF,
        ),
        # Interstellar Conspiracy: "Gain 1 spice, If grafted with an Emperor
        # or Spacing Guild card: Gain 1 Influence with a chosen Faction" --
        # each icon resolves on its own, in the owner's order (OQ-027, user
        # decision 2026-10-18 "원칙대로 아이콘마다 나누자"; engine audit
        # 2026-10-22, P4): the spice may come first, to pay for another
        # effect before the Faction is chosen.
        "gain_spice_and_chosen_influence_if_grafted_with_emperor_or_guild": icon_box(
            ("spice", box_line(GainResources(spice=1))),
            (
                "influence",
                box_line(
                    GainInfluence(),
                    condition=GraftedWithFaction(
                        (Faction.EMPEROR, Faction.SPACING_GUILD)
                    ),
                ),
            ),
        ),
        # Clandestine Meeting: "[Bene Gesserit Influence] [Intrigue card]"
        # -- the Influence answered by its one-Faction row (cleanup-2d-5,
        # user decision 2026-10-18: "원칙대로 아이콘마다 나누자").
        "gain_bene_gesserit_influence_and_intrigue": icon_box(
            ("influence", box_line(GainInfluence(factions=(_BG,)))),
            ("intrigue", box_line(DrawIntrigueCards(1))),
        ),
        # Occupation: "[draw 1] [Combat]" [Immortality p. 16] -- the Combat
        # icon answered by ``take_agent_card_combat_icon`` (cleanup-2d-5).
        "draw_one_and_combat_icon": icon_box(
            ("cards", box_line(DrawPersonalCards(1))),
            ("combat", box_line(GrantCombatDeployment())),
        ),
        # Twisted Mentat: "You may recall the Agent you sent this turn" (an
        # optional icon, ``agent_effects.OPTIONAL_AGENT_ICONS``).
        "may_recall_agent_sent_this_turn": icon_box(
            ("recall", box_line(RecallAgent(sent_this_turn=True, optional=True))),
        ),
        # Organ Merchants.
        "may_pay_specimen_for_four_solari": pay_box(
            SpendSpecimens(1), GainResources(solari=4)
        ),
        # Tleilaxu Surgeon.
        "may_pay_two_specimens_for_two_tleilaxu": pay_box(
            SpendSpecimens(2), AdvanceTleilaxu(2)
        ),
        # Chairdog: "At the start of your Reveal turn, return the other
        # grafted card from play to your hand" -- noted at the graft; the box
        # waits while that card is out of play.
        "return_other_grafted_to_hand_at_reveal_start": agent_box(
            ReturnOtherGraftedCardAtRevealStart()
        ),
        # Lisan al Gaib: the Fremen Influence, the Bond judged when the box
        # resolves (a grafted partner may give it).
        "gain_fremen_influence_if_bene_gesserit_bond": agent_box(
            GainInfluence(factions=(Faction.FREMEN,)), condition=_BG_BOND
        ),
        # Long Reach: "Choose two Factions: Gain 1 Influence with each" --
        # both named before either is paid (a target choice, cleanup-2d).
        "gain_two_distinct_chosen_influence": agent_box(
            GainInfluence(times=2, distinct=True)
        ),
        # Dissecting Kit: "You may trash the other grafted card -> Generate
        # 1 specimen" (cleanup-2d).
        "may_trash_other_grafted_for_specimen": pay_box(
            TrashCard(grafted=GraftedTrash.OTHER), GenerateSpecimens(1)
        ),
        # Scientific Breakthrough: "Research, If 2 genetic markers: You may
        # trash this card -> Gain 1 VP" -- the trash line judged once the
        # Research has settled.
        "research_and_may_trash_self_for_vp_if_two_markers": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                box_line(Research()),
                EffectSection(
                    rewards=(GainVictoryPoints(1),),
                    condition=GeneticMarkersAtLeast(2),
                    costs=(TrashCard(this_card=True),),
                ),
            ),
            structure=AbilityStructure.SEPARATE,
            hook="scientific_breakthrough",
        ),
        # Slig Farmer: "Gain 1 solari per Agent icon on the other grafted
        # card, You may pay 5 solari -> Advance the Tleilaxu track" -- two
        # printed effects, each its own step in the owner's order (OQ-027:
        # "You may carry out all these effects in any order." [Main p. 9]):
        # the Solari, mandatory, and the arrow, optional [FAQ p. 3], which
        # the Solari may pay (OQ-058) and the turn's end lapses unused
        # (OQ-095 (2)). Until 2026-11-08 the payment row paid both and the
        # plain row closed the box (a carried-over cleanup-2d hook).
        "gain_solari_per_partner_icon_and_may_pay_five_solari_for_tleilaxu": icon_box(
            ("solari", box_line(GainSolariPerPartnerAgentIcon())),
            (
                "tleilaxu",
                EffectSection(
                    rewards=(AdvanceTleilaxu(1),),
                    costs=(PayResources(solari=5),),
                ),
            ),
        ),
        # Stitched Horror: "Choose two: Gain 1 water / Recruit 1 troop /
        # Trash a card / Advance the Tleilaxu track" -- both named before
        # either is paid (cleanup-2d).
        "choose_two_of_water_troop_trash_tleilaxu": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                box_line(GainResources(water=1)),
                box_line(RecruitTroops(1)),
                box_line(TrashPersonalCard()),
                box_line(AdvanceTleilaxu(1)),
            ),
            structure=AbilityStructure.CHOOSE_TWO,
        ),
        # Beguiling Pheromones: "If you sent an Agent to a Faction space this
        # turn: Trash one of the grafted cards, Gain 1 Influence with that
        # Faction".
        # Its "If you sent an Agent to a Faction space this turn" is the
        # visited Faction's gain (no Faction, nothing offered; cleanup-2d).
        "trash_grafted_card_for_visited_faction_influence": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                EffectSection(
                    rewards=(GainInfluence(visited_space=True),),
                    costs=(TrashCard(grafted=GraftedTrash.EITHER),),
                ),
            ),
        ),
        # Tleilaxu Infiltrator (its "Enemy Agents don't block your Agent
        # this turn" is a placement rule, ``agent_turn``).
        "draw_one_and_intrigue_if_two_markers": icon_box(
            ("cards", box_line(DrawPersonalCards(1))),
            (
                "intrigue",
                box_line(DrawIntrigueCards(1), condition=GeneticMarkersAtLeast(2)),
            ),
        ),
        # Sardaukar Quartermaster: "If grafted: troop, draw a card".
        "recruit_one_and_draw_one_if_grafted": icon_box(
            ("troops", box_line(RecruitTroops(1), condition=Grafted())),
            ("cards", box_line(DrawPersonalCards(1), condition=Grafted())),
        ),
        # Industrial Espionage: "[draw 1]" and, on its own line, "If
        # grafted: [Research] [specimen]".
        "draw_one_and_research_and_specimen_if_grafted": icon_box(
            ("cards", box_line(DrawPersonalCards(1))),
            (
                "research",
                box_line(Research(), GenerateSpecimens(1), condition=Grafted()),
            ),
        ),
        # Stillsuit Manufacturer: "[water] —AND— [Fremen] Alliance: Return
        # this card from play to your hand."
        "gain_water_and_return_self_if_fremen_alliance": icon_box(
            ("water", box_line(GainResources(water=1))),
            (
                "return_self",
                box_line(
                    ReturnThisCardToHand(),
                    condition=HasAlliance(Faction.FREMEN),
                ),
            ),
        ),
    }
)
