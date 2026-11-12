"""English text for personal-card enum tokens and automatic Reveal effects.

Wording follows the same shared display contract as ``effect_dsl_text`` and
``structs``: short imperative fragments, no trailing period, resources
lowercase, game terms capitalized as printed. Card-specific wording is
sourced from ``docs/implementation-audits/personal-cards.md`` (per-card,
image-verified behaviour) first, ``docs/card-data-sources.md`` second, and
the enum member name only as a last resort.

Each box kind has one exported ``Mapping`` here, keyed as the engine finds
the box: by ``PersonalCard*Effect`` member for the Agent and Reveal-choice
boxes and the icon conditions, by card id for the acquire, trash, discard,
turn-start and Reveal-acquisition boxes (docs/content-core-refactor-plan.md
8.3). A regression test asserts full coverage (``set(map) == set(EnumClass)``,
or the keys of the box's records), so a box without matching text fails that
test instead of rendering a ``KeyError`` at display time. ``PersonalCardBond``
(a Faction affiliation) has no card-facing members of its own, so it stays a
private lookup used only by :func:`reveal_effect_text`, which renders one
line of a card's Reveal record (``rules.reveal_lines.RevealLine``).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from dune_imperium.content.core.effects import (
    AdvanceTleilaxu,
    AgentOnSpaceWithIcon,
    CommandersInConflictAtLeast,
    CommandReached,
    DeployFromSupply,
    DrawIntrigueCards,
    FactionBond,
    GainInfluence,
    GainResources,
    GarrisonedUnitsAtLeast,
    GenerateSpecimens,
    GeneticMarkersAtLeast,
    GrantCombatDeployment,
    HasAlliance,
    HasHighCouncil,
    HasSwordmaster,
    InfluenceAtLeast,
    RecruitTroops,
    Research,
    ReserveCostDiscount,
    RevealCountKind,
    RevealPersuasion,
    RevealSwords,
    SpiesPlacedAtLeast,
    SpyingOnMakerSpace,
    TrashThisCard,
)
from dune_imperium.content.core.icons import AgentIcon, Faction, PersonalCardBond
from dune_imperium.content.registry.reserve import RESERVE_STACKS_BY_ID
from dune_imperium.display.effect_dsl_text import condition_text, reward_text
from dune_imperium.rules.reveal_lines import RevealLine

_BOND_NAMES: dict[PersonalCardBond, str] = {
    PersonalCardBond.EMPEROR: "Emperor",
    PersonalCardBond.SPACING_GUILD: "Spacing Guild",
    PersonalCardBond.BENE_GESSERIT: "Bene Gesserit",
    PersonalCardBond.FREMEN: "Fremen",
}


def _bond_name(bond: PersonalCardBond) -> str:
    return _BOND_NAMES[bond]


def _faction_name(faction: Faction) -> str:
    return _bond_name(PersonalCardBond(faction.value))


def _plural(count: int, noun: str) -> str:
    return noun if count == 1 else f"{noun}s"


# Agent-box effects, by box key. None of the keys is a "no effect"
# sentinel today (a card with no Agent-box text simply has no key in its
# set's Agent box table), so every value below is non-empty; the empty-
# string convention noted in the module docstring is reserved for a future
# sentinel key rather than exercised now.
AGENT_EFFECT_TEXT: Final[Mapping[str, str]] = MappingProxyType(
    {
        "gain_two_visited_faction_influence_and_trash_self": (
            "Gain 2 Influence with the visited Faction, Trash this card"
        ),
        "look_at_top_three": (
            "If you have 3 or more cards in your deck: Look at the top 3 cards, "
            "Draw 1, Discard 1, Trash 1"
        ),
        "trash_self": "Trash this card",
        "trash_personal_card": "You may trash a card",
        "trash_personal_card_to_draw_one": (
            "You may trash a card → Draw 1 card"
        ),
        # Rise of Ix's Shai-Hulud (stage P4d): "[Trash a card] -> [2 troops]".
        "trash_personal_card_to_recruit_two": (
            "You may trash a card → Recruit 2 troops"
        ),
        # Tread in Darkness: two icons side by side with no arrow between
        # them (OQ-058) — the draw always happens, even if the trash is
        # declined (agent_effects.py), unlike Shishakli's real arrow above.
        "trash_personal_card_to_draw_one_if_bene_gesserit_bond": (
            "If Bene Gesserit Bond: You may trash a card, Draw 1 card"
        ),
        (
            "may_trash_intrigue_for_intrigue_and_two_spice_if_bene_gesserit_alliance"
        ): (
            "If Bene Gesserit Alliance: You may trash an Intrigue card → "
            "Draw 1 Intrigue card, Gain 2 spice"
        ),
        # "Gain two Influence instead of one" [card face]: the visited
        # space's single Influence becomes 2, not 1 + 1 more.
        "trash_self_and_emperor_from_hand_for_extra_influence": (
            "You may trash this card and an Emperor card from your hand → "
            "Gain 2 Influence instead of 1 Influence with the visited Faction"
        ),
        "trash_self_and_gain_chosen_influence": (
            "Trash this card, Gain 1 Influence with a chosen Faction"
        ),
        "gain_chosen_influence_if_spy_recalled_this_turn": (
            "If you recalled a Spy this turn: Gain 1 Influence with a chosen Faction"
        ),
        # Per task instruction: this member always resolves through the
        # owner's Leader's Signet Ring ability data rather than typed text.
        "leader_signet": "Your Leader's Signet Ring ability",
        "pay_two_water_to_draw_two": (
            "You may pay 2 water → Draw 2 cards"
        ),
        "may_pay_four_spice_for_vp": (
            "You may pay 4 spice → Gain 1 VP"
        ),
        # Rise of Ix's Sayyadina (stage P4d).
        "may_pay_three_water_for_vp": (
            "You may pay 3 water → Gain 1 VP"
        ),
        # Rise of Ix's Local Fence (stage P4d): two arrows printed with -OR-.
        (
            "may_pay_two_spice_for_five_solari_or_five_solari_for_four_spice"
        ): (
            "Choose one: You may pay 2 spice → Gain 5 solari / "
            "You may pay 5 solari → Gain 4 spice"
        ),
        "may_discard_two_and_pay_five_solari_for_vp": (
            "You may discard 2 cards and pay 5 solari → Gain 1 VP"
        ),
        (
            "may_trash_intrigue_and_pay_two_spice_for_vp_if_spacing_guild_alliance"
        ): (
            "If Spacing Guild Alliance: You may trash an Intrigue card and "
            "pay 2 spice → Gain 1 VP"
        ),
        "acquire_with_solari_to_hand": (
            "You may acquire an Imperium Row or Reserve card to your hand, "
            "paying its cost in solari"
        ),
        "take_contract": "Take 1 face-up Contract",
        "may_discard_to_take_contract": (
            "You may discard a card → Take 1 face-up Contract"
        ),
        "draw_per_two_completed_contracts_up_to_two": (
            "If you have completed 2 or more Contracts: Draw 1 card, "
            "If you have completed 4 or more Contracts: Draw 1 more card"
        ),
        "gain_chosen_influence": (
            "Gain 1 Influence with a chosen Faction"
        ),
        "draw_one_and_recall_agent": (
            "Draw 1 card, Recall 1 Agent"
        ),
        # The original game's Foldspace (Reserve).
        "draw_one_and_trash_self": "Draw 1 card, Trash this card",
        "draw_personal_card": "Draw 1 card",
        "draw_per_sandworm_in_conflict": (
            "Draw 1 card per sandworm in the Conflict"
        ),
        "discard_to_draw_one_or_two_if_spacing_guild": (
            "You may discard a card → Draw 1 card "
            "(2 if the discarded card has Spacing Guild affiliation)"
        ),
        # No arrow on the card face: the discard is no cost (engine audit
        # 2026-10-22, P6).
        "discard_one_draw_two_if_spacing_guild": (
            "Discard a card. If you discarded a Spacing Guild card: Draw 2 cards"
        ),
        "may_discard_to_draw_intrigue_and_personal_card": (
            "You may discard a card → Draw 1 Intrigue card, Draw 1 card"
        ),
        "may_discard_to_draw_one_and_intrigue_if_spacing_guild": (
            "You may discard a card → Draw 1 card (also Draw 1 Intrigue card "
            "if the discarded card has Spacing Guild affiliation)"
        ),
        "each_opponent_discards_personal_card": (
            "Each opponent discards a card"
        ),
        "gain_spice_if_maker_space": (
            "If you are at a Maker space: Gain 1 spice"
        ),
        "gain_two_spice_if_maker_space": (
            "If you are at a Maker space: Gain 2 spice"
        ),
        "gain_two_solari": "Gain 2 solari",
        # Rise of Ix's Bounty Hunter (stage P4d): "If used to send an Agent to
        # a board space with an enemy Agent: [2 Solari]".
        "gain_two_solari_if_enemy_agent_on_space": (
            "If used to send an Agent to a board space with an enemy Agent: "
            "Gain 2 solari"
        ),
        "gain_one_spice": "Gain 1 spice",
        "place_spy": "Place a Spy",
        "place_spy_on_visited_space_may_share": (
            "Place a Spy on a post connected to the space you sent an Agent to "
            "this turn (may share a post with another player's Spy)"
        ),
        "recruit_three_if_spy_recalled_this_turn": (
            "If you recalled a Spy this turn: Recruit 3 troops"
        ),
        "recruit_two_if_spy_recalled_this_turn": (
            "If you recalled a Spy this turn: Recruit 2 troops"
        ),
        "draw_intrigue_if_spy_recalled_this_turn": (
            "If you recalled a Spy this turn: Draw 1 Intrigue card"
        ),
        "draw_intrigue_if_three_units_in_conflict": (
            "If you have 3 or more units in the Conflict: Draw 1 Intrigue card"
        ),
        "draw_one_and_place_spy_if_bene_gesserit_bond": (
            "If Bene Gesserit Bond: Draw 1 card, Place a Spy"
        ),
        # The printed words [Overthrow card] (OQ-128: it replaces the
        # space's 1, as Treacherous Maneuver's does).
        "gain_visited_faction_influence": (
            "Gain 2 Influence instead of 1 Influence with the visited Faction"
        ),
        "gain_water": "Gain 1 water",
        # Immortality (card faces).
        "research": "Research (advance your research token)",
        "advance_tleilaxu": (
            "Tleilaxu (advance your Tleilaxu token)"
        ),
        "advance_tleilaxu_if_one_marker": (
            "If you have reached one genetic marker: Tleilaxu "
            "(advance your Tleilaxu token)"
        ),
        "advance_tleilaxu_if_grafted": (
            "If grafted: Tleilaxu (advance your Tleilaxu token)"
        ),
        "draw_two_if_one_marker": (
            "If you have reached one genetic marker: Draw 2 cards"
        ),
        "draw_one_and_intrigue_if_two_markers": (
            "Enemy Agents don't block your Agent this turn. Draw 1 card, "
            "If you have reached two genetic markers: Draw 1 Intrigue card"
        ),
        "may_recall_agent_sent_this_turn": (
            "You may recall the Agent you sent this turn"
        ),
        # Rise of Ix's Landing Rights (stage P4d): the Freighter icon.
        "may_move_freighter": (
            "You may move your Freighter up one space or recall it"
        ),
        # Rise of Ix's Embedded Agent: two Freighter icons behind "another
        # Bene Gesserit card in play", the original game's Bond words.
        "may_move_freighter_twice_if_bene_gesserit_bond": (
            "If Bene Gesserit Bond: You may move your Freighter up one space or "
            "recall it, You may move your Freighter up one space or recall it"
        ),
        # Rise of Ix's Weirding Way (stage P4d).
        "may_take_another_turn": (
            "You may take another turn immediately after this one"
        ),
        # Rise of Ix's Ixian Engineer (stage P4d): the Acquire Tech icon.
        "may_acquire_tech": "You may acquire a Tech tile",
        # Rise of Ix's Appropriate (stage P4d).
        (
            "may_acquire_tech_with_spice_or_solari_if_emperor_influence_two"
        ): (
            "If you have 2 or more Emperor Influence: You may acquire a Tech "
            "tile, using Solari instead of spice for this purchase if you like"
        ),
        "generate_specimen": "Generate 1 specimen",
        "gain_bene_gesserit_influence_and_intrigue": (
            "Gain 1 Bene Gesserit Influence, Draw 1 Intrigue card"
        ),
        "gain_two_spice_if_grafted": "If grafted: Gain 2 spice",
        "gain_two_spice_if_emperor_influence_two": (
            "If you have 2 or more Emperor Influence: Gain 2 spice"
        ),
        "gain_fremen_influence_if_bene_gesserit_bond": (
            "If Bene Gesserit Bond: Gain 1 Fremen Influence"
        ),
        "draw_one_and_combat_icon": (
            "Draw 1 card, Combat (deploy as though at a Combat space)"
        ),
        "recruit_one_and_draw_one_if_grafted": (
            "If grafted: Recruit 1 troop, Draw 1 card"
        ),
        "draw_two_cards": "Draw 2 cards",
        "gain_water_and_return_self_if_fremen_alliance": (
            "Gain 1 water, Fremen Alliance: return this card from play to your hand"
        ),
        "recruit_one_and_may_trash": (
            "Recruit 1 troop, You may trash a card"
        ),
        "gain_two_distinct_chosen_influence": (
            "Choose two Factions: Gain 1 Influence with each"
        ),
        "may_pay_specimen_for_four_solari": (
            "You may spend 1 specimen → Gain 4 solari"
        ),
        "may_trash_other_grafted_for_specimen": (
            "You may trash the other grafted card → Generate 1 specimen"
        ),
        (
            "draw_one_or_combat_icon_if_spacing_guild_influence_two"
        ): (
            "If you have 2 or more Spacing Guild Influence: "
            "Choose one: Draw 1 card / Combat (deploy as though at a Combat space)"
        ),
        "peek_two_intrigue_keep_one": (
            "Look at the top 2 Intrigue cards, keep 1 and put the other back on top"
        ),
        (
            "gain_spice_and_chosen_influence_if_grafted_with_emperor_or_guild"
        ): (
            "Gain 1 spice, If grafted with an Emperor or Spacing Guild card: "
            "Gain 1 Influence with a chosen Faction"
        ),
        "may_acquire_card_up_to_six_if_one_marker": (
            "If 1 genetic marker: You may acquire a card costing 6 or less, "
            "If 2 genetic markers: put it in your hand"
        ),
        "may_pay_two_specimens_for_two_tleilaxu": (
            "You may spend 2 specimens → Advance the Tleilaxu track twice"
        ),
        "draw_one_and_research_and_specimen_if_grafted": (
            "Draw 1 card, If grafted: Research, Generate 1 specimen"
        ),
        "research_and_may_trash_self_for_vp_if_two_markers": (
            "Research, If 2 genetic markers: You may trash this card → Gain 1 VP"
        ),
        (
            "gain_spacing_guild_influence_if_gained_spice_this_turn"
        ): "If you gained spice this turn: Gain 1 Spacing Guild Influence",
        (
            "gain_solari_per_partner_icon_and_may_pay_five_solari_for_tleilaxu"
        ): (
            "Gain 1 solari per Agent icon on the other grafted card, "
            "You may pay 5 solari → Advance the Tleilaxu track"
        ),
        "choose_two_of_water_troop_trash_tleilaxu": (
            "Choose two: Gain 1 water / Recruit 1 troop / Trash a card / "
            "Advance the Tleilaxu track"
        ),
        (
            "trash_grafted_card_for_visited_faction_influence"
        ): (
            "If you sent an Agent to a Faction space this turn: "
            "Trash one of the grafted cards, Gain 1 Influence with that Faction"
        ),
        "may_lose_troop_to_draw_two_and_research": (
            "You may lose 1 troop → Draw 2 cards, Research"
        ),
        "return_other_grafted_to_hand_at_reveal_start": (
            "At the start of your Reveal turn, "
            "return the other grafted card from play to your hand"
        ),
        # Control the Spice (Epic Game Mode starting card): the black-X
        # trash stays optional after the arrow is paid [FAQ p. 3], as on
        # Arrakis Revolt's "You may remove the Shield Wall" above.
        "may_pay_spice_to_trash_and_recruit": (
            "You may pay 1 spice → You may trash a card, Recruit 1 troop"
        ),
        "gain_by_bene_gesserit_and_fremen_influence_two": (
            "If you have 2 or more Bene Gesserit Influence: Gain 1 water, "
            "If you have 2 or more Fremen Influence: Gain 1 spice"
        ),
        (
            "gain_by_emperor_spacing_guild_and_fremen_influence_two"
        ): (
            "If you have 2 or more Emperor Influence: Gain 2 solari, "
            "If you have 2 or more Spacing Guild Influence: Draw 1 card, "
            "If you have 2 or more Fremen Influence: Gain 1 water"
        ),
        "gain_by_emperor_and_spacing_guild_influence_two": (
            "If you have 2 or more Emperor Influence: Gain 2 solari, "
            "If you have 2 or more Spacing Guild Influence: Gain 1 spice"
        ),
        # Uprising promo cards (card faces; OQ-024 to OQ-026).
        (
            "may_pay_two_spice_for_shield_wall_and_sandworm_if_maker_hooks"
        ): (
            "If Maker Hooks: You may pay 2 spice → You may remove the Shield Wall,"
            " Summon 1 sandworm"
        ),
        "gain_rewards_per_face_up_battle_icon": (
            "Gain rewards for your face-up battle icons: Crysknife: You may trash"
            " a card, Desert Mouse: Gain 1 spice, Ornithopter: Recruit 1 troop"
        ),
        "may_trash_self_for_troop_and_first_place_influence": (
            "You may trash this card → Recruit 1 troop and add 1 Influence of"
            " your choice to this Conflict's first-place reward"
        ),
        "recruit_one_if_maker_space": (
            "If you are at a Maker space: Recruit 1 troop"
        ),
        "recruit_two_troops": "Recruit 2 troops",
        "recruit_two_if_bene_gesserit_bond": (
            "If Bene Gesserit Bond: Recruit 2 troops"
        ),
        "return_self_if_bene_gesserit_bond": (
            "If Bene Gesserit Bond: Return this card to your hand"
        ),
        "draw_if_bene_gesserit_influence_two": (
            "If you have 2 or more Bene Gesserit Influence: Draw 1 card"
        ),
        "recruit_one_and_draw_if_bene_gesserit_influence_two": (
            "If you have 2 or more Bene Gesserit Influence: Recruit 1 troop, "
            "Draw 1 card"
        ),
        # Bloodlines
        "draw_intrigue_card": "Draw 1 Intrigue card",
        "recruit_one_if_emperor_influence_two": (
            "If you have 2 or more Emperor Influence: Recruit 1 troop"
        ),
        "may_discard_to_draw_one": (
            "You may discard a card → Draw 1 card"
        ),
        # Rise of Ix's Court Intrigue (stage P4d).
        "may_put_intrigue_on_bottom_to_draw_intrigue": (
            "You may put an Intrigue card on the bottom of the Intrigue deck → "
            "Draw 1 Intrigue card"
        ),
        # Rise of Ix's Guild Chief Administrator (stage P4d).
        "may_discard_to_trash_a_card": (
            "You may discard a card → You may trash a card"
        ),
        "draw_intrigue_if_sandworm_in_conflict": (
            "If you have 1 or more sandworms in the Conflict: Draw 1 Intrigue card"
        ),
        "draw_one_if_gained_two_spice_this_turn": (
            "If you gained 2 or more spice this turn: Draw 1 card"
        ),
        (
            "recruit_one_and_draw_one_if_gained_two_spice_this_turn"
        ): "If you gained 2 or more spice this turn: Recruit 1 troop, Draw 1 card",
        "take_contract_if_spy_recalled_this_turn": (
            "If you recalled a Spy this turn: Take a Contract"
        ),
        "draw_intrigue_if_contract_completed_this_turn": (
            "If you completed a Contract this turn: Draw 1 Intrigue card"
        ),
        "may_trash_hand_card_for_emperor_rewards": (
            "You may trash a card from your hand. If you trash an Emperor card: "
            "Draw 1 Intrigue card, Recruit 1 troop, Combat"
        ),
        "force_opponent_troop_retreat": (
            "Force an enemy troop to retreat"
        ),
        # Rise of Ix's Desert Ambush (stage P4d).
        "may_force_enemy_unit_retreat_for_each_troop_deployed": (
            "For each troop you deploy this turn, you may force an enemy unit "
            "to retreat"
        ),
        "may_trash_two_cards_if_commander_in_conflict": (
            "If you have one or more Sardaukar Commanders in the Conflict: "
            "You may trash a card, You may trash a card"
        ),
        "may_discard_for_deep_cover_spy": (
            "You may discard a card → Place a Spy with Deep Cover; "
            "if you discarded a Spacing Guild card: Gain 2 spice"
        ),
        "may_discard_for_water": (
            "You may discard a card → Gain 1 water"
        ),
        # Rise of Ix's Satellite Ban (stage P4d): "[Discard] -> [1 spice] [1 water]".
        "may_discard_for_one_spice_and_one_water": (
            "You may discard a card → Gain 1 spice, Gain 1 water"
        ),
        # Rise of Ix's Spice Trader (stage P4d): "[Fremen] 2 Influence: [Discard]
        # -> [2 spice]".
        "may_discard_for_two_spice_if_fremen_influence_two": (
            "If you have 2 or more Fremen Influence: "
            "You may discard a card → Gain 2 spice"
        ),
        # Rise of Ix's Imperial Bashar (stage P4d): "[Troop] -OR- [Trash a card]".
        "recruit_one_or_may_trash_a_card": (
            "Choose one: Recruit 1 troop / You may trash a card"
        ),
        # Rise of Ix's Esmar Tuek (stage P4d): "[1 spice] -> [Spacing Guild
        # Influence] [draw 1 card]".
        (
            "may_pay_one_spice_for_spacing_guild_influence_and_draw_one"
        ): "You may pay 1 spice → Gain 1 Spacing Guild Influence, Draw 1 card",
        # Rise of Ix's Ix-Guild Compact (stage P4d): "[Discard] [Discard] ->
        # [Dreadnought]".
        "may_discard_two_for_dreadnought": (
            "You may discard two cards → Commission a dreadnought"
        ),
        # Rise of Ix's In The Shadows (stage P4d): "[Bene Gesserit] 2
        # Influence: [Discard] -> Choose one: [Emperor] [Spacing Guild]
        # [Fremen] Influence".
        (
            "may_discard_for_chosen_influence_if_bene_gesserit_influence_two"
        ): (
            "If you have 2 or more Bene Gesserit Influence: You may discard a "
            "card → Choose one: Gain 1 Emperor Influence / Gain 1 Spacing Guild "
            "Influence / Gain 1 Fremen Influence"
        ),
        "complete_one_contract": "Complete one of your contracts",
        "each_opponent_loses_troop_and_moves_spy": (
            "Each opponent loses one troop. Each opponent spying on the board "
            "space where you sent an Agent this turn must move that Spy"
        ),
        "boost_next_bene_gesserit_card_this_round": (
            "The next Bene Gesserit card you play this round has all Agent icons "
            "and, added to its Agent box: Draw 1 card"
        ),
        "draw_one_or_bene_gesserit_influence_if_bond": (
            "Choose one: Draw 1 card / If Bene Gesserit Bond: "
            "Gain 1 Bene Gesserit Influence"
        ),
        "chosen_influence_or_two_troops_both_if_bond": (
            "Choose one: Gain 1 Influence with a chosen Faction / Recruit 2 troops; "
            "if Bene Gesserit Bond: get both"
        ),
        # The original game's Imperium cards (stage P3).
        "recruit_one_troop": "Recruit 1 troop",
        (
            "may_pay_two_spice_for_spacing_guild_influence_and_three_solari"
        ): "You may pay 2 spice → Gain 1 Spacing Guild Influence, Gain 3 solari",
        "each_opponent_loses_garrison_troop": (
            "Each opponent loses one garrisoned troop"
        ),
        "gain_one_solari": "Gain 1 solari",
        "gain_three_solari": "Gain 3 solari",
        "may_pay_one_water_for_troop_and_draw_one": (
            "You may pay 1 water → Recruit 1 troop, Draw 1 card"
        ),
        "may_pay_two_spice_for_three_troops": (
            "You may pay 2 spice → Recruit 3 troops"
        ),
        "draw_two_if_spacing_guild_influence_two": (
            "If you have 2 or more Spacing Guild Influence: Draw 2 cards"
        ),
        "gain_two_spice": "Gain 2 spice",
        "gain_spacing_guild_influence_or_two_spice": (
            "Choose one: Gain 1 Spacing Guild Influence / Gain 2 spice"
        ),
        "draw_one_or_bene_gesserit_card_from_discard": (
            "Choose one: Draw 1 card / Draw a Bene Gesserit card from your "
            "discard pile"
        ),
        "block_chosen_space_for_opponents_next_agent": (
            "Choose any board space. Opponents can't send their next Agents "
            "there this round"
        ),
        "recruit_two_and_draw_one": (
            "Recruit 2 troops, Draw 1 card"
        ),
        "may_trash_self_to_draw_intrigue": (
            "You may trash this card → Draw 1 Intrigue card"
        ),
        "gain_chosen_influence_if_bene_gesserit_bond": (
            "If Bene Gesserit Bond: Gain 1 Influence with a chosen Faction"
        ),
        "may_trash_and_gain_two_spice_if_bene_gesserit_bond": (
            "You may trash a card, If Bene Gesserit Bond: Gain 2 spice"
        ),
        "each_opponent_discards_two_if_bene_gesserit_bond": (
            "If Bene Gesserit Bond: Each opponent discards 2 cards"
        ),
        "double_base_harvest_spice": (
            "Double the base (not bonus) spice you harvest with this Agent"
        ),
        "double_bonus_harvest_spice": (
            "Double the bonus spice you harvest with this Agent"
        ),
        "draw_two_if_bene_gesserit_bond": (
            "If Bene Gesserit Bond: Draw 2 cards"
        ),
        "each_opponent_discards_or_loses_deployed_troop": (
            "Each opponent chooses: Discard a card -OR- Lose a deployed troop"
        ),
        "may_pay_two_solari_for_chosen_influence": (
            "You may pay 2 solari → Choose one: Gain 1 Spacing Guild Influence / "
            "Gain 1 Bene Gesserit Influence / Gain 1 Fremen Influence"
        ),
        (
            "may_lose_influence_and_pay_two_spice_for_two_influence"
        ): (
            "You may lose 1 Influence with a chosen Faction and pay 2 spice → "
            "Gain 2 Influence with one chosen Faction"
        ),
    }
)

# Turn-start alternatives, printed in a red box in place of an Agent box
# (Litany Against Fear).
TURN_START_EFFECT_TEXT: Final[Mapping[str, str]] = (
    MappingProxyType(
        {
            "litany_against_fear": (
                "Put this card into play → Draw 1 card and pass your turn"
            ),
        }
    )
)

TRASH_EFFECT_TEXT: Final[Mapping[str, str]] = MappingProxyType(
    {
        "sardaukar_soldier": "Draw 1 Intrigue card",
        "eliminate_allies": "Recruit 2 troops",
        "sardaukar_standard": (
            "Acquire and recruit the Sardaukar Commander in the bank"
        ),
        "replacement_eyes": (
            "Tleilaxu (advance your Tleilaxu token)"
        ),
        "assassination_mission": "Gain 4 solari",
    }
)

# The printed condition that turns a card's greyed Agent icons on; ``cards``
# appends ", this has <icons>" from the entry's ``agent_icons``. Long Reach:
# "If you have another Bene Gesserit card in play, this has [Landsraad],
# [City], and [Spice Trade]."; Show of Strength: "If you have more deployed
# troops than each opponent, this has [Landsraad] and [Spice Trade]." [card
# faces].
ICON_CONDITION_TEXT: Final[Mapping[str, str]] = (
    MappingProxyType(
        {
            "bene_gesserit_bond": (
                "If you have another Bene Gesserit card in play"
            ),
            "more_deployed_troops_than_each_opponent": (
                "If you have more deployed troops than each opponent"
            ),
        }
    )
)

DISCARD_EFFECT_TEXT: Final[Mapping[str, str]] = MappingProxyType(
    {
        "spacing_guild_s_favor": "Gain 2 spice",
        "corrupt_bureaucrat": "Gain 3 solari",
    }
)

ACQUISITION_EFFECT_TEXT: Final[Mapping[str, str]] = (
    MappingProxyType(
        {
            "overthrow": "Draw 1 Intrigue card",
            "price_is_no_object": "Gain 2 solari",
            "corrino_genes": "Gain 2 solari",
            "guild_spy": "Place a Spy",
            "in_high_places": "Place a Spy",
            "spy_network": "Place a Spy",
            "strike_fleet": "Place a Spy",
            "subversive_advisor": "Place a Spy",
            "intelligence_training": "Place a Spy",
            "steersman": "Gain 1 Spacing Guild Influence",
            "interstellar_trade": "Take 1 face-up Contract",
            "mercantile_affairs": "Take 1 face-up Contract",
            "arrakis_revolt": "Recruit 1 troop",
            "negotiated_withdrawal": "Recruit 1 troop",
            "imperial_throneship": "Gain 1 Emperor Influence",
            "liet_kynes_card": "Gain 1 Emperor Influence",
            "possible_futures": "Gain 1 water",
            "chani_card": "Gain 1 water",
            "water_peddler": "Gain 1 water",
            "spiritual_fervor": "Research (advance your research token)",
            "subject_x_137": "Tleilaxu (advance your Tleilaxu token)",
            "lisan_al_gaib": "Gain 1 spice",
            "occupation": "Recruit 3 troops",
            "choam_directorship": (
                "Gain 1 Emperor Influence, Gain 1 Spacing Guild Influence, "
                "Gain 1 Bene Gesserit Influence, Gain 1 Fremen Influence"
            ),
            "lady_jessica_card": "Gain 1 Influence (choose any Faction)",
            "shai_hulud": "Trash a card",
            "full_scale_assault": "Commission a dreadnought",
            "appropriate": "Move your Freighter up one space or recall it",
        }
    )
)

# The one transcribed member is specific to The Spice Must Flow (see the
# enum member name and Guild Spy's audit entry); ``cards.py`` supplies that
# card-specific condition as the display prefix, so this text is only the
# reward.
REVEAL_ACQUISITION_EFFECT_TEXT: Final[
    Mapping[str, str]
] = MappingProxyType(
    {
        "guild_spy": (
            "Gain 1 Influence with each Faction you are spying on"
        ),
    }
)

# Reveal-turn choice effects. Persuasion and strength gains use the "+N"
# shorthand (matching reveal_effect_text below) because these are all
# alternate outcomes of the same printed Reveal box, not Agent-box gains.
REVEAL_CHOICE_EFFECT_TEXT: Final[Mapping[str, str]] = (
    MappingProxyType(
        {
            "recall_spy_to_draw_intrigue_if_two_placed": (
                "If you have placed 2 or more Spies: "
                "You may recall a Spy → Draw 1 Intrigue card"
            ),
            "may_recall_two_spies_for_three_persuasion": (
                "You may recall 2 Spies → +3 Persuasion"
            ),
            "place_spy": "Place a Spy",
            "place_two_spies": "Place 2 Spies",
            "gain_chosen_influence_if_two_tech": (
                "If you have 2 or more Tech tiles: "
                "Gain 1 Influence with a chosen Faction"
            ),
            # Rise of Ix's Ixian Engineer (stage P4d): CHOAM Demands' arrow with
            # a Victory Point.
            (
                "may_trash_self_for_victory_point_if_three_tech_tiles"
            ): (
                "If you have 3 or more Tech tiles: Trash this card → Gain 1 VP"
            ),
            # Rise of Ix's Ix-Guild Compact (stage P4d): two Tech Negotiation
            # icons, the second of them alone once the first is resolved.
            "may_place_two_negotiators": (
                "You may place a troop from your supply on the Ix board as a "
                "Negotiator, twice"
            ),
            "may_place_negotiator": (
                "You may place a troop from your supply on the Ix board as a "
                "Negotiator"
            ),
            # Rise of Ix's promo Boundless Ambition (stage P4d): the effect DSL's
            # words for its acquisition (``effect_dsl_text``).
            "acquire_card_up_to_five": (
                "Acquire a card costing 5 or less"
            ),
            # Rise of Ix's Web of Power (stage P4d): the wild Influence icon.
            "gain_chosen_influence": (
                "Gain 1 Influence with a chosen Faction"
            ),
            "place_spy_or_gain_two_strength": (
                "Choose one: Place a Spy / +2 swords"
            ),
            "may_lose_influence_to_gain_influence": (
                "You may lose 1 Influence with a chosen Faction → "
                "Gain 1 Influence with a chosen Faction"
            ),
            "may_pay_three_spice_for_influence": (
                "You may pay 3 spice → Gain 1 Influence with a chosen Faction"
            ),
            "may_trash_other_emperor_for_three_strength": (
                "You may trash another Emperor card in play → +3 swords"
            ),
            "may_retreat_two_troops_for_four_strength": (
                "You may retreat 2 troops → +4 swords"
            ),
            (
                "may_lose_influence_for_vp_if_bene_gesserit_alliance"
            ): (
                "Bene Gesserit Alliance: You may lose 2 Influence with one Faction "
                "→ Gain 1 VP"
            ),
            "may_deploy_or_retreat_one_troop": (
                "You may deploy or retreat 1 troop"
            ),
            (
                "may_deploy_or_retreat_one_troop_if_fremen_bond"
            ): "Fremen Bond: You may deploy or retreat 1 troop",
            "may_lose_two_troops_for_two_specimens": (
                "You may lose 2 troops → Generate 2 specimens"
            ),
            # The original game's Imperium cards (stage P3).
            "may_deploy_one_troop": (
                "You may deploy 1 troop from your garrison to the Conflict"
            ),
            "choose_two_persuasion_or_two_strength": (
                "Choose one: 2 Persuasion / 2 swords"
            ),
            "may_deploy_up_to_three_troops": (
                "You may deploy up to 3 troops from your garrison to the Conflict"
            ),
            "may_retreat_up_to_two_troops": (
                "You may retreat up to 2 troops"
            ),
            # Rise of Ix's Guild Chief Administrator (stage P4d).
            "may_move_freighter": (
                "You may move your Freighter up one space or recall it"
            ),
            # Rise of Ix's Negotiated Withdrawal (stage P4d).
            "may_retreat_three_units_for_influence": (
                "You may retreat 3 of your units → Gain 1 Influence with a "
                "chosen Faction"
            ),
            "may_retreat_any_number_of_troops": (
                "You may retreat any number of troops"
            ),
            (
                "may_trash_self_to_move_any_number_of_troops"
            ): (
                "Trash this card → Deploy or retreat any number of your troops "
                "from or to your garrison"
            ),
            "may_pay_six_solari_for_victory_point": (
                "You may pay 6 solari → Gain 1 Victory Point"
            ),
            (
                "may_pay_three_solari_for_two_troops_and_deploy"
            ): (
                "You may pay 3 solari → Recruit 2 troops, "
                "you may deploy these troops to the Conflict"
            ),
            (
                "may_pay_three_spice_for_victory_point_if_spacing_guild_alliance"
            ): (
                "Spacing Guild Alliance: You may pay 3 spice → Gain 1 Victory Point"
            ),
            "gain_five_solari_or_take_high_council": (
                "Choose one: Gain 5 solari / "
                "Pay 5 solari → Take the High Council seat"
            ),
            "may_pay_water_for_sandworm": (
                "Choose one: Keep the Persuasion / "
                "If Maker Hooks: Pay 1 water → Summon and deploy a sandworm"
            ),
            (
                "keep_spice_or_trash_self_for_vp_if_four_contracts"
            ): (
                "If you have completed 4 or more Contracts: "
                "Choose one: Keep the spice / Trash this card → Gain 1 VP"
            ),
            # Bloodlines
            "command_may_trash_card": (
                "Command (6+ Persuasion): You may trash a card"
            ),
            "command_place_spy": (
                "Command (6+ Persuasion): Place a Spy"
            ),
            "command_gain_chosen_influence": (
                "Command (6+ Persuasion): Gain 1 Influence with a chosen Faction"
            ),
            "may_retreat_two_troops_for_two_persuasion": (
                "You may retreat 2 troops → +2 Persuasion"
            ),
            "may_trash_self_for_combat_icon": (
                "Trash this card → Combat (deploy as though at a Combat space)"
            ),
            "may_recall_spy_for_three_strength": (
                "You may recall a Spy → +3 swords"
            ),
            (
                "may_trash_self_for_four_influence_if_four_contracts"
            ): (
                "If you have completed 4+ contracts: Trash this card → "
                "Gain 1 Influence with each Faction"
            ),
            "persuasion_or_contract": (
                "Choose one: 1 Persuasion / Contract"
            ),
            "command_may_trash_self_to_acquire_row_card": (
                "Command (6+ Persuasion): Trash this card → "
                "Acquire a card from the Imperium Row"
            ),
        }
    )
)

# What a line of a Reveal record may hold (``content.uprising.reveal_abilities``
# checks every record against the same sets); the renderers here and in
# ``tokens_ko`` read each of them.
HANDLED_REVEAL_CONDITIONS: Final[frozenset[type]] = frozenset(
    {
        FactionBond,
        HasHighCouncil,
        HasSwordmaster,
        SpiesPlacedAtLeast,
        SpyingOnMakerSpace,
        CommandersInConflictAtLeast,
        GeneticMarkersAtLeast,
        GarrisonedUnitsAtLeast,
        CommandReached,
        InfluenceAtLeast,
        HasAlliance,
        AgentOnSpaceWithIcon,
    }
)
HANDLED_REVEAL_REWARDS: Final[frozenset[type]] = frozenset(
    {
        RevealPersuasion,
        RevealSwords,
        GainResources,
        DrawIntrigueCards,
        RecruitTroops,
        GainInfluence,
        TrashThisCard,
        GrantCombatDeployment,
        GenerateSpecimens,
        AdvanceTleilaxu,
        Research,
        ReserveCostDiscount,
        DeployFromSupply,
    }
)


@dataclass(frozen=True, slots=True)
class RevealLineConditions:
    """A Reveal line's conditions, as the card text names them."""

    bond: Faction | None = None
    high_council: bool = False
    swordmaster: bool = False
    spies: int = 0
    maker: bool = False
    commander: bool = False
    markers: int = 0
    garrison: int = 0
    command: bool = False
    # "Fremen Influence 2" (Worm Riders): a Faction and the Influence it needs.
    influence: tuple[Faction, int] | None = None
    # "Fremen Alliance" (Worm Riders).
    alliance: Faction | None = None
    # "If you have an Agent on an [Emperor] board space" (Imperial Shock
    # Trooper): the board space's icon.
    agent_on_space: AgentIcon | None = None


def reveal_line_conditions(line: RevealLine) -> RevealLineConditions:
    """Read ``line``'s conditions (each kind printed at most once)."""

    found: dict[str, object] = {}
    for condition in line.conditions:
        match condition:
            case FactionBond(faction=faction):
                found["bond"] = faction
            case HasHighCouncil():
                found["high_council"] = True
            case HasSwordmaster():
                found["swordmaster"] = True
            case SpiesPlacedAtLeast(count=count):
                found["spies"] = count
            case SpyingOnMakerSpace():
                found["maker"] = True
            case CommandersInConflictAtLeast():
                found["commander"] = True
            case GeneticMarkersAtLeast(count=count):
                found["markers"] = count
            case GarrisonedUnitsAtLeast(count=count):
                found["garrison"] = count
            case CommandReached():
                found["command"] = True
            case InfluenceAtLeast(faction=faction, amount=amount):
                found["influence"] = (faction, amount)
            case HasAlliance(faction=faction) if faction is not None:
                found["alliance"] = faction
            case AgentOnSpaceWithIcon(icon=icon):
                found["agent_on_space"] = icon
            case _:
                raise TypeError(f"{condition!r} is not a Reveal line condition")
    return RevealLineConditions(**found)  # type: ignore[arg-type]


def reveal_effect_text(line: RevealLine) -> str:
    """Render one printed Reveal line as ``If <condition>: <gains>``.

    Its conditions come first as an ``If ...:`` prefix (Faction Bond, High
    Council/Swordmaster, minimum placed Spies, spying on a Maker space, ...);
    a count per Faction card (revealed or in play) instead scales whichever
    gain (Persuasion or strength) it accompanies, so it is folded into that
    gain's own text rather than into the prefix. The gains that follow are
    joined with ", " in a fixed order; Persuasion and strength use the "+N"
    shorthand that matches the printed Reveal diamonds, everything else uses
    "Gain N ...".
    """

    held = reveal_line_conditions(line)
    conditions: list[str] = []
    if held.bond is not None:
        conditions.append(f"{_faction_name(held.bond)} Bond")
    if held.swordmaster:
        conditions.append("High Council and Swordmaster")
    elif held.high_council:
        conditions.append("High Council")
    if held.spies:
        noun = "Spy" if held.spies == 1 else "Spies"
        conditions.append(f"you have placed {held.spies} or more {noun}")
    if held.maker:
        conditions.append("you are spying on a Maker space")
    if held.commander:
        conditions.append("you have 1 or more Sardaukar Commanders in the Conflict")
    if held.markers:
        noun = "marker" if held.markers == 1 else "markers"
        conditions.append(f"you have reached {held.markers} genetic {noun}")
    if held.garrison:
        conditions.append(f"you have {held.garrison} or more garrisoned units")
    if held.command:
        conditions.append("Command (6+ Persuasion)")
    if held.influence is not None:
        faction, amount = held.influence
        name = _faction_name(faction)
        conditions.append(f"you have {amount} or more {name} Influence")
    if held.alliance is not None:
        conditions.append(f"you have the {_faction_name(held.alliance)} Alliance")
    if held.agent_on_space is not None:
        # "If you have an Agent on an [Emperor] board space," [Imperial Shock
        # Trooper, Steam app text]: the Canny line's words.
        conditions.append(condition_text(AgentOnSpaceWithIcon(held.agent_on_space)))

    count = line.faction_count
    per_faction = (
        ""
        if count is None or count.faction is None
        else f" per revealed {_faction_name(count.faction)} card"
        if count.kind is RevealCountKind.REVEALED_FACTION_CARD
        else f" per {_faction_name(count.faction)} card in play"
    )

    gains: list[str] = []
    persuasion = line.printed_persuasion
    if persuasion:
        gains.append(f"+{persuasion} Persuasion{per_faction}")
    strength = line.printed_strength
    if strength:
        gains.append(f"+{strength} {_plural(strength, 'sword')}{per_faction}")
    if line.strength_per_other_sword_card:
        n = line.strength_per_other_sword_card
        gains.append(f"+{n} {_plural(n, 'sword')} per other revealed sword card")
    if line.strength_per_dreadnought:
        # Rise of Ix's Full-Scale Assault.
        n = line.strength_per_dreadnought
        gains.append(
            f"+{n} {_plural(n, 'sword')} per dreadnought of yours in the Conflict"
        )
    if line.persuasion_per_completed_contract:
        gains.append(
            f"+{line.persuasion_per_completed_contract} Persuasion "
            "per completed Contract"
        )
    if line.solari:
        gains.append(f"Gain {line.solari} solari")
    if line.spice:
        gains.append(f"Gain {line.spice} spice")
    if line.water:
        gains.append(f"Gain {line.water} water")
    if line.draw_intrigue:
        gains.append(
            f"Draw {line.draw_intrigue} Intrigue {_plural(line.draw_intrigue, 'card')}"
        )
    if line.recruit_troops:
        gains.append(
            f"Recruit {line.recruit_troops} {_plural(line.recruit_troops, 'troop')}"
        )
    if line.supply_deployments:
        # Treachery: Double Cross's words (``effect_dsl_text``).
        gains.append(reward_text(DeployFromSupply(line.supply_deployments)))
    influence = line.influence
    if influence is not None and influence[1]:
        faction, times = influence
        gains.append(f"Gain {times} {_faction_name(faction)} Influence")
    if line.trashes_self:
        gains.append("Trash this card")
    if line.grants_combat_icon:
        gains.append("Combat (deploy as though at a Combat space)")
    if line.specimens:
        gains.append(f"Generate {line.specimens} {_plural(line.specimens, 'specimen')}")
    if line.tleilaxu:
        gains.append("Tleilaxu (advance your Tleilaxu token)")
    if line.research:
        gains.append(
            "Research (advance your research token)"
            if line.research == 1
            else f"Research ×{line.research} (advance your research token twice)"
        )
    for discount in line.reserve_discounts:
        # Guild Bankers: the card's printed sentence (``effect_dsl_text``'s
        # ``ReserveCostDiscount``).
        name = RESERVE_STACKS_BY_ID[discount.card_ids[0]].card.name
        gains.append(
            f"{name} costs {discount.amount} Persuasion less to acquire this turn"
        )

    text = ", ".join(gains)
    if conditions:
        return f"If {' and '.join(conditions)}: {text}"
    return text
