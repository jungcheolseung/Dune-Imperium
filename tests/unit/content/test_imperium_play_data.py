"""Tests for DIU-bootstrapped Imperium-card play data."""


from tests.support.card_records import acquire_rewards

from dune_imperium.content.core.cards import PersonalCardDefinition
from dune_imperium.content.core.effects import (
    DrawIntrigueCards,
    GainInfluence,
    GainResources,
    PlaceSpy,
    TakeContract,
)
from dune_imperium.content.core.icons import AgentIcon, Faction
from dune_imperium.content.registry.card_abilities import (
    acquisition_ability,
    card_agent_box,
    card_reveal_choices,
    discard_ability,
    reveal_acquisition_ability,
    trash_ability,
)
from dune_imperium.content.registry.imperium import (
    IMPERIUM_CARDS_BY_ID,
    imperium_deck_instance_ids,
)
from dune_imperium.content.registry.personal_cards import personal_card_for_instance
from dune_imperium.display.tokens import reveal_effect_text
from dune_imperium.rules.reveal_lines import reveal_lines


def _reveal_texts(card: PersonalCardDefinition) -> tuple[str, ...]:
    """The card's Reveal record, line by line, as its card text reads."""

    return tuple(reveal_effect_text(line) for line in reveal_lines(card))


def _instance(card_id: str, *, choam_module: bool = False) -> str:
    return next(
        instance_id
        for instance_id in imperium_deck_instance_ids(choam_module)
        if f":{card_id}:" in instance_id
    )


def test_maula_pistol_play_data_matches_the_diu_transcription() -> None:
    card = IMPERIUM_CARDS_BY_ID["maula_pistol"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.FREMEN,)
    assert card.agent_icons == (AgentIcon.CITY, AgentIcon.SPICE_TRADE)
    assert card_agent_box(card) == "draw_personal_card"
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 1
    assert personal_card_for_instance(_instance("maula_pistol")) is card


def test_bene_gesserit_operative_play_data_places_and_counts_spies() -> None:
    card = IMPERIUM_CARDS_BY_ID["bene_gesserit_operative"]

    assert card.play_data_complete is True
    # Purple "BENE GESSERIT" affiliation banner [card face].
    assert card.factions == (Faction.BENE_GESSERIT,)
    assert card.agent_icons == (AgentIcon.BENE_GESSERIT,)
    assert card_agent_box(card) == "place_spy"
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 0
    assert _reveal_texts(card) == ("If you have placed 2 or more Spies: +2 Persuasion",)


def test_reliable_informant_play_data_restricts_its_spy_targets() -> None:
    card = IMPERIUM_CARDS_BY_ID["reliable_informant"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.SPACING_GUILD,)
    assert card.agent_icons == (AgentIcon.SPACING_GUILD,)
    assert card_agent_box(card) == "place_spy"
    # Re-read from the card face 2026-09-26: the third target icon is the
    # blue Fremen sietch badge, not the red Spacing Guild infinity symbol.
    assert card.agent_spy_factions == (
        Faction.EMPEROR,
        Faction.BENE_GESSERIT,
        Faction.FREMEN,
    )
    assert card.reveal_persuasion == 1
    assert _reveal_texts(card) == ("Gain 1 solari",)


def test_truthtrance_play_data_matches_the_diu_transcription() -> None:
    card = IMPERIUM_CARDS_BY_ID["truthtrance"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.BENE_GESSERIT,)
    assert card.agent_icons == (
        AgentIcon.EMPEROR,
        AgentIcon.SPACING_GUILD,
        AgentIcon.BENE_GESSERIT,
        AgentIcon.FREMEN,
    )
    assert card_agent_box(card) is None
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 0


def test_sardaukar_soldier_play_data_includes_its_trash_trigger() -> None:
    card = IMPERIUM_CARDS_BY_ID["sardaukar_soldier"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.EMPEROR,)
    assert card.agent_icons == (AgentIcon.CITY,)
    assert card_agent_box(card) is None
    trash = trash_ability(card.card.card_id)
    assert trash is not None
    assert trash.sections[0].rewards == (DrawIntrigueCards(1),)
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 1


def test_sardaukar_coordination_play_data_deploys_and_counts_emperor_cards() -> None:
    card = IMPERIUM_CARDS_BY_ID["sardaukar_coordination"]

    assert card.play_data_complete is True
    assert card.copies == 2
    assert card.factions == (Faction.EMPEROR,)
    assert card.agent_icons == (AgentIcon.EMPEROR, AgentIcon.LANDSRAAD)
    assert card.allows_recruited_troop_deployment is True
    # Reveal box: a blue Persuasion diamond "2", then "+[sword] for each
    # Emperor card you revealed (including this one)" [card face]; there is
    # no separate base sword icon.
    assert card.reveal_persuasion == 2
    assert card.reveal_strength == 0
    assert _reveal_texts(card) == ("+1 sword per revealed Emperor card",)


def test_hidden_missive_play_data_includes_its_conditional_agent_effect() -> None:
    card = IMPERIUM_CARDS_BY_ID["hidden_missive"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.BENE_GESSERIT,)
    assert card.agent_icons == (AgentIcon.LANDSRAAD,)
    assert (
        card_agent_box(card)
        == "recruit_one_and_draw_if_bene_gesserit_influence_two"
    )
    assert trash_ability(card.card.card_id) is None
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 1


def test_desert_survival_play_data_includes_its_optional_trash() -> None:
    card = IMPERIUM_CARDS_BY_ID["desert_survival"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.FREMEN,)
    assert card.agent_icons == (AgentIcon.SPICE_TRADE,)
    assert card_agent_box(card) == "trash_personal_card"
    assert trash_ability(card.card.card_id) is None
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 1


def test_smugglers_harvester_play_data_includes_its_maker_bonus() -> None:
    card = IMPERIUM_CARDS_BY_ID["smuggler_s_harvester"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.SPACING_GUILD,)
    assert card.agent_icons == (AgentIcon.SPICE_TRADE,)
    assert card_agent_box(card) == "gain_spice_if_maker_space"
    assert trash_ability(card.card.card_id) is None
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 0


def test_smugglers_haven_play_data_uses_the_printed_reveal_persuasion() -> None:
    card = IMPERIUM_CARDS_BY_ID["smuggler_s_haven"]

    assert card.play_data_complete is True
    assert card.copies == 1
    assert card.factions == (Faction.SPACING_GUILD,)
    assert card.agent_icons == (AgentIcon.SPACING_GUILD, AgentIcon.SPICE_TRADE)
    assert card_agent_box(card) == "may_pay_four_spice_for_vp"
    assert card.reveal_persuasion == 1
    assert _reveal_texts(card) == ("If you are spying on a Maker space: Gain 2 spice",)


def test_price_is_no_object_play_data_acquires_with_solari_to_hand() -> None:
    card = IMPERIUM_CARDS_BY_ID["price_is_no_object"]

    assert card.play_data_complete is True
    assert card.copies == 1
    assert card.factions == (Faction.EMPEROR, Faction.BENE_GESSERIT)
    assert card.agent_icons == (AgentIcon.EMPEROR, AgentIcon.BENE_GESSERIT)
    assert card_agent_box(card) == "acquire_with_solari_to_hand"
    assert acquire_rewards(card.card.card_id) == (GainResources(solari=2),)
    assert card.reveal_persuasion == 2
    assert _reveal_texts(card) == ("Gain 2 solari",)


def test_fedaykin_stilltent_play_data_has_maker_and_reveal_gains() -> None:
    card = IMPERIUM_CARDS_BY_ID["fedaykin_stilltent"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.FREMEN,)
    assert card.agent_icons == (AgentIcon.SPICE_TRADE,)
    assert card_agent_box(card) == "recruit_one_if_maker_space"
    assert _reveal_texts(card) == ("Gain 1 water",)
    assert card.reveal_persuasion == 0
    assert card.reveal_strength == 0


def test_northern_watermaster_play_data_has_fremen_bond_gain() -> None:
    card = IMPERIUM_CARDS_BY_ID["northern_watermaster"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.FREMEN,)
    assert card.agent_icons == (AgentIcon.CITY,)
    assert card_agent_box(card) == "gain_water"
    assert card.reveal_persuasion == 1
    assert _reveal_texts(card) == ("If Fremen Bond: Gain 2 spice",)


def test_maker_keeper_play_data_has_independent_influence_rewards() -> None:
    card = IMPERIUM_CARDS_BY_ID["maker_keeper"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.BENE_GESSERIT, Faction.FREMEN)
    # Re-read from the card face 2026-09-26: only one Agent icon box (the
    # blue City circle) sits above the Agent box; there is no Spice Trade
    # triangle (BGG marks only Purple Access for this card).
    assert card.agent_icons == (AgentIcon.CITY,)
    assert (
        card_agent_box(card)
        == "gain_by_bene_gesserit_and_fremen_influence_two"
    )
    assert card.reveal_persuasion == 2
    assert card.reveal_strength == 0


def test_southern_elders_play_data_has_two_reveal_effects() -> None:
    card = IMPERIUM_CARDS_BY_ID["southern_elders"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.BENE_GESSERIT, Faction.FREMEN)
    assert card.agent_icons == (AgentIcon.BENE_GESSERIT, AgentIcon.FREMEN)
    assert (
        card_agent_box(card)
        == "recruit_two_if_bene_gesserit_bond"
    )
    assert _reveal_texts(card) == (
        "Gain 1 water",
        "If Fremen Bond: +2 Persuasion",
    )


def test_weirding_woman_play_data_has_bond_return_effect() -> None:
    card = IMPERIUM_CARDS_BY_ID["weirding_woman"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.BENE_GESSERIT,)
    assert card.agent_icons == (AgentIcon.CITY, AgentIcon.SPICE_TRADE)
    assert (
        card_agent_box(card)
        == "return_self_if_bene_gesserit_bond"
    )
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 1


def test_ecological_testing_station_play_data_has_payment_and_bond_gain() -> None:
    card = IMPERIUM_CARDS_BY_ID["ecological_testing_station"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.FREMEN,)
    assert card.agent_icons == (AgentIcon.FREMEN, AgentIcon.CITY)
    assert card_agent_box(card) == "pay_two_water_to_draw_two"
    assert card.reveal_persuasion == 1
    assert _reveal_texts(card) == ("If Fremen Bond: Gain 1 water",)


def test_paracompass_play_data_has_council_and_swordmaster_reveal_gains() -> None:
    card = IMPERIUM_CARDS_BY_ID["paracompass"]

    assert card.play_data_complete is True
    assert card.factions == ()
    assert card.agent_icons == (AgentIcon.CITY,)
    assert card_agent_box(card) == "gain_two_solari"
    assert _reveal_texts(card) == (
        "If High Council: +2 Persuasion",
        "If High Council and Swordmaster: +1 Persuasion",
    )


def test_overthrow_play_data_covers_acquisition_agent_and_reveal() -> None:
    card = IMPERIUM_CARDS_BY_ID["overthrow"]

    assert card.play_data_complete is True
    # No affiliation banner under the title [card face]; the BGG inventory
    # row also leaves every affiliation column blank. The four Faction
    # symbols on the left edge are Agent icons, not affiliation.
    assert card.factions == ()
    assert card.agent_icons == (
        AgentIcon.EMPEROR,
        AgentIcon.SPACING_GUILD,
        AgentIcon.BENE_GESSERIT,
        AgentIcon.FREMEN,
    )
    assert card_agent_box(card) == "gain_visited_faction_influence"
    assert (
        acquire_rewards(card.card.card_id) == (DrawIntrigueCards(1),)
    )
    assert card.reveal_persuasion == 2
    assert card.reveal_strength == 2
    assert _reveal_texts(card) == ("Recruit 1 troop",)


def test_strike_fleet_play_data_covers_spy_acquisition_and_recall_reward() -> None:
    card = IMPERIUM_CARDS_BY_ID["strike_fleet"]

    assert card.play_data_complete is True
    assert card.factions == ()
    assert card.agent_icons == (AgentIcon.SPY,)
    assert (
        card_agent_box(card)
        == "recruit_three_if_spy_recalled_this_turn"
    )
    assert acquire_rewards(card.card.card_id) == (PlaceSpy(),)
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 3


def test_imperial_spymaster_play_data_uses_the_turn_recall_condition() -> None:
    card = IMPERIUM_CARDS_BY_ID["imperial_spymaster"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.EMPEROR,)
    assert card.agent_icons == (AgentIcon.EMPEROR, AgentIcon.SPY)
    assert (
        card_agent_box(card)
        == "draw_intrigue_if_spy_recalled_this_turn"
    )
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 1


def test_spy_network_play_data_has_acquisition_and_reveal_spy_effects() -> None:
    card = IMPERIUM_CARDS_BY_ID["spy_network"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.EMPEROR, Faction.SPACING_GUILD)
    assert card.agent_icons == ()
    assert card_agent_box(card) is None
    assert acquire_rewards(card.card.card_id) == (PlaceSpy(),)
    assert card.reveal_persuasion == 2
    assert card.reveal_strength == 1
    assert card_reveal_choices(card) == (
        "recall_spy_to_draw_intrigue_if_two_placed",
    )


def test_in_high_places_play_data_has_bond_acquisition_and_reveal_choice() -> None:
    card = IMPERIUM_CARDS_BY_ID["in_high_places"]

    assert card.play_data_complete is True
    # Two affiliation bands under the title: grey "EMPEROR" above purple
    # "BENE GESSERIT" [card face].
    assert card.factions == (Faction.EMPEROR, Faction.BENE_GESSERIT)
    assert card.agent_icons == (AgentIcon.BENE_GESSERIT, AgentIcon.EMPEROR)
    # "If you have another Bene Gesserit card in play: [draw 1 card] [Spy]"
    # and "[recall Spy] [recall Spy] -> +3 Persuasion" [In High Places card]
    # (BGG inventory: "Draw 1 card, +1 Spy", "Recall 2 Spies -> +3
    # Persuasion"); once transcribed as one water and +2 Persuasion.
    assert (
        card_agent_box(card)
        == "draw_one_and_place_spy_if_bene_gesserit_bond"
    )
    assert acquire_rewards(card.card.card_id) == (PlaceSpy(),)
    assert card.reveal_persuasion == 2
    assert card.reveal_strength == 0
    assert card_reveal_choices(card) == (
        "may_recall_two_spies_for_three_persuasion",
    )


def test_rebel_supplier_play_data_uses_the_turn_recall_condition() -> None:
    card = IMPERIUM_CARDS_BY_ID["rebel_supplier"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.FREMEN,)
    assert card.agent_icons == (AgentIcon.CITY,)
    assert (
        card_agent_box(card)
        == "recruit_two_if_spy_recalled_this_turn"
    )
    assert card.reveal_persuasion == 0
    assert card.reveal_strength == 1
    assert _reveal_texts(card) == ("Gain 1 spice",)


def test_dangerous_rhetoric_play_data_trashes_for_chosen_influence() -> None:
    card = IMPERIUM_CARDS_BY_ID["dangerous_rhetoric"]

    assert card.play_data_complete is True
    assert card.factions == ()
    assert card.agent_icons == (AgentIcon.LANDSRAAD, AgentIcon.SPY)
    assert (
        card_agent_box(card)
        == "trash_self_and_gain_chosen_influence"
    )
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 1


def test_public_spectacle_play_data_uses_spy_recall_and_placement() -> None:
    card = IMPERIUM_CARDS_BY_ID["public_spectacle"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.EMPEROR,)
    assert card.agent_icons == (AgentIcon.SPY,)
    assert (
        card_agent_box(card)
        == "gain_chosen_influence_if_spy_recalled_this_turn"
    )
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 0
    assert card_reveal_choices(card) == (
        "place_spy",
    )


def test_wheels_within_wheels_play_data_reuses_reveal_spy_placement() -> None:
    card = IMPERIUM_CARDS_BY_ID["wheels_within_wheels"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.EMPEROR, Faction.SPACING_GUILD)
    assert card.agent_icons == (AgentIcon.SPY,)
    assert (
        card_agent_box(card)
        == "gain_by_emperor_and_spacing_guild_influence_two"
    )
    assert card.reveal_persuasion == 1
    assert card_reveal_choices(card) == (
        "place_spy",
    )


def test_unswerving_loyalty_play_data_has_reveal_rewards_and_bond_move() -> None:
    card = IMPERIUM_CARDS_BY_ID["unswerving_loyalty"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.FREMEN,)
    assert card.agent_icons == ()
    assert card_agent_box(card) is None
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 0
    assert _reveal_texts(card) == ("Recruit 1 troop",)
    # "Fremen Bond : You may deploy or retreat one of your troops."
    # [Unswerving Loyalty card]; the line was missing from the transcription.
    assert card_reveal_choices(card) == (
        "may_deploy_or_retreat_one_troop_if_fremen_bond",
    )


def test_stilgar_play_data_counts_revealed_fremen_cards() -> None:
    card = IMPERIUM_CARDS_BY_ID["stilgar_the_devoted"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.FREMEN,)
    assert card.agent_icons == (
        AgentIcon.FREMEN,
        AgentIcon.CITY,
        AgentIcon.SPICE_TRADE,
    )
    assert card_agent_box(card) == "recruit_two_troops"
    # "for each Fremen card you have in play (including this one)"
    # [Stilgar, The Devoted card]: Agent-turn cards count too [Main p. 20]
    # [FAQ p. 2 Liet Kynes], not only the revealed ones.
    assert _reveal_texts(card) == ("+2 Persuasion per Fremen card in play",)


def test_leadership_play_data_scales_with_worms_and_other_sword_cards() -> None:
    card = IMPERIUM_CARDS_BY_ID["leadership"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.FREMEN,)
    assert card.agent_icons == (AgentIcon.FREMEN, AgentIcon.SPICE_TRADE)
    assert (
        card_agent_box(card)
        == "draw_per_sandworm_in_conflict"
    )
    assert card.reveal_persuasion == 2
    assert card.reveal_strength == 1
    assert _reveal_texts(card) == ("+1 sword per other revealed sword card",)


def test_shishakli_play_data_has_trash_draw_and_fremen_bond_influence() -> None:
    card = IMPERIUM_CARDS_BY_ID["shishakli"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.FREMEN,)
    assert card.agent_icons == (AgentIcon.CITY, AgentIcon.SPICE_TRADE)
    assert (
        card_agent_box(card)
        == "trash_personal_card_to_draw_one"
    )
    assert card.reveal_strength == 2
    assert _reveal_texts(card) == ("If Fremen Bond: Gain 1 Fremen Influence",)


def test_tread_in_darkness_play_data_has_bond_trash_draw() -> None:
    card = IMPERIUM_CARDS_BY_ID["tread_in_darkness"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.BENE_GESSERIT,)
    assert card.agent_icons == (
        AgentIcon.LANDSRAAD,
        AgentIcon.CITY,
        AgentIcon.SPICE_TRADE,
    )
    assert (
        card_agent_box(card)
        == "trash_personal_card_to_draw_one_if_bene_gesserit_bond"
    )
    assert card.reveal_persuasion == 2
    assert card.reveal_strength == 1


def test_space_time_folding_play_data_has_conditional_discard_draw() -> None:
    card = IMPERIUM_CARDS_BY_ID["space_time_folding"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.SPACING_GUILD,)
    assert card.agent_icons == (AgentIcon.SPACING_GUILD,)
    assert (
        card_agent_box(card)
        == "discard_to_draw_one_or_two_if_spacing_guild"
    )
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 0


def test_guild_envoy_play_data_has_mandatory_conditional_discard_draw() -> None:
    card = IMPERIUM_CARDS_BY_ID["guild_envoy"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.SPACING_GUILD,)
    assert card.agent_icons == (
        AgentIcon.EMPEROR,
        AgentIcon.SPACING_GUILD,
        AgentIcon.BENE_GESSERIT,
        AgentIcon.FREMEN,
    )
    assert (
        card_agent_box(card)
        == "discard_one_draw_two_if_spacing_guild"
    )
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 0


def test_captured_mentat_play_data_has_discard_and_influence_choices() -> None:
    card = IMPERIUM_CARDS_BY_ID["captured_mentat"]

    assert card.play_data_complete is True
    assert card.factions == ()
    assert card.agent_icons == (AgentIcon.LANDSRAAD, AgentIcon.SPICE_TRADE)
    assert (
        card_agent_box(card)
        == "may_discard_to_draw_intrigue_and_personal_card"
    )
    assert card.reveal_persuasion == 1
    assert card_reveal_choices(card) == (
        "may_lose_influence_to_gain_influence",
    )


def test_spacing_guilds_favor_play_data_has_discard_and_reveal_payments() -> None:
    card = IMPERIUM_CARDS_BY_ID["spacing_guild_s_favor"]

    assert card.play_data_complete is True
    assert card.copies == 2
    assert card.factions == (Faction.SPACING_GUILD,)
    assert card.agent_icons == (AgentIcon.SPACING_GUILD, AgentIcon.SPICE_TRADE)
    assert card_agent_box(card) == "draw_personal_card"
    discard = discard_ability(card.card.card_id)
    assert discard is not None
    assert discard.sections[0].rewards == (GainResources(spice=2),)
    assert card.reveal_persuasion == 2
    assert card_reveal_choices(card) == (
        "may_pay_three_spice_for_influence",
    )


def test_double_agent_play_data_has_conditional_shared_spy_placement() -> None:
    card = IMPERIUM_CARDS_BY_ID["double_agent"]

    assert card.play_data_complete is True
    assert card.copies == 2
    assert card.factions == (Faction.EMPEROR, Faction.SPACING_GUILD)
    assert card.agent_icons == (
        AgentIcon.LANDSRAAD,
        AgentIcon.CITY,
        AgentIcon.SPICE_TRADE,
    )
    assert (
        card_agent_box(card)
        == "place_spy_on_visited_space_may_share"
    )
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 1


def test_guild_spy_play_data_has_discard_acquisition_and_reveal_triggers() -> None:
    card = IMPERIUM_CARDS_BY_ID["guild_spy"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.SPACING_GUILD,)
    assert card.agent_icons == (AgentIcon.SPY,)
    assert (
        card_agent_box(card)
        == "may_discard_to_draw_one_and_intrigue_if_spacing_guild"
    )
    assert acquire_rewards(card.card.card_id) == (PlaceSpy(),)
    assert card.reveal_persuasion == 2
    guild_spy = reveal_acquisition_ability(card.card.card_id)
    assert guild_spy is not None and guild_spy.hook == "guild_spy"


def test_covert_operation_play_data_forces_each_opponent_to_discard() -> None:
    card = IMPERIUM_CARDS_BY_ID["covert_operation"]

    assert card.play_data_complete is True
    assert card.factions == ()
    assert card.agent_icons == (AgentIcon.SPY,)
    assert (
        card_agent_box(card)
        == "each_opponent_discards_personal_card"
    )
    # The Reveal box prints two Spy icons and no Persuasion diamond
    # [Covert Operation card] (BGG inventory: "+2 Spies"); it was once
    # transcribed as two Persuasion.
    assert card.reveal_persuasion == 0
    assert card.reveal_strength == 0
    assert card_reveal_choices(card) == (
        "place_two_spies",
    )


def test_calculus_of_power_play_data_trashes_self_or_another_emperor() -> None:
    card = IMPERIUM_CARDS_BY_ID["calculus_of_power"]

    assert card.play_data_complete is True
    assert card.copies == 2
    assert card.factions == (Faction.EMPEROR,)
    # Re-read from the card face 2026-09-26: the top icon is a solid blue
    # circle (City), not the green Landsraad pentagon.
    assert card.agent_icons == (AgentIcon.CITY, AgentIcon.SPY)
    # The plain trash icon, not "trash this card" (bug fixed 2026-09-09).
    assert card_agent_box(card) == "trash_personal_card"
    assert card.reveal_persuasion == 2
    assert card_reveal_choices(card) == (
        "may_trash_other_emperor_for_three_strength",
    )


def test_branching_path_play_data_has_alliance_trash_reward() -> None:
    card = IMPERIUM_CARDS_BY_ID["branching_path"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.BENE_GESSERIT,)
    # Re-read from the card face 2026-09-19: the second icon is City (the
    # blue circle), not Landsraad.
    assert card.agent_icons == (AgentIcon.BENE_GESSERIT, AgentIcon.CITY)
    assert (
        card_agent_box(card)
        == (
            "may_trash_intrigue_for_intrigue_and_two_spice_if_bene_gesserit_alliance"
        )
    )
    assert card.reveal_persuasion == 2
    assert card.reveal_strength == 0


def test_treacherous_maneuver_play_data_matches_the_card() -> None:
    card = IMPERIUM_CARDS_BY_ID["treacherous_maneuver"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.EMPEROR,)
    assert card.agent_icons == (
        AgentIcon.EMPEROR,
        AgentIcon.SPACING_GUILD,
        AgentIcon.BENE_GESSERIT,
        AgentIcon.FREMEN,
    )
    assert (
        card_agent_box(card)
        == "trash_self_and_emperor_from_hand_for_extra_influence"
    )
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 0
    assert _reveal_texts(card) == ("Draw 1 Intrigue card",)


def test_chani_clever_tactician_play_data_matches_the_card() -> None:
    card = IMPERIUM_CARDS_BY_ID["chani_clever_tactician"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.FREMEN,)
    # Re-read from the card face 2026-09-26: the first icon is the blue
    # Fremen sietch badge, not the red Spacing Guild infinity symbol.
    assert card.agent_icons == (
        AgentIcon.FREMEN,
        AgentIcon.CITY,
        AgentIcon.SPICE_TRADE,
    )
    assert (
        card_agent_box(card)
        == "draw_intrigue_if_three_units_in_conflict"
    )
    assert card.reveal_persuasion == 0
    assert card.reveal_strength == 0
    assert _reveal_texts(card) == ("If Fremen Bond: +2 Persuasion",)
    assert card_reveal_choices(card) == (
        "may_retreat_two_troops_for_four_strength",
    )


def test_steersman_play_data_matches_the_card() -> None:
    card = IMPERIUM_CARDS_BY_ID["steersman"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.SPACING_GUILD,)
    assert card.agent_icons == (
        AgentIcon.SPACING_GUILD,
        AgentIcon.LANDSRAAD,
        AgentIcon.CITY,
        AgentIcon.SPICE_TRADE,
    )
    assert card_agent_box(card) == "draw_one_and_recall_agent"
    assert acquire_rewards(card.card.card_id) == (
        GainInfluence(factions=(Faction.SPACING_GUILD,)),
    )
    assert card.reveal_persuasion == 2
    assert card.reveal_strength == 0
    assert _reveal_texts(card) == ("Gain 2 spice",)


def test_junction_headquarters_play_data_matches_the_card() -> None:
    card = IMPERIUM_CARDS_BY_ID["junction_headquarters"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.SPACING_GUILD,)
    assert card.agent_icons == (
        AgentIcon.LANDSRAAD,
        AgentIcon.CITY,
        AgentIcon.SPICE_TRADE,
    )
    assert (
        card_agent_box(card)
        == (
            "may_trash_intrigue_and_pay_two_spice_for_vp_if_spacing_guild_alliance"
        )
    )
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 0
    assert _reveal_texts(card) == ("Gain 1 water, Recruit 1 troop",)


def test_undercover_asset_play_data_is_complete() -> None:
    card = IMPERIUM_CARDS_BY_ID["undercover_asset"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.EMPEROR, Faction.SPACING_GUILD)
    # Re-read from the card face 2026-09-26: only three Agent icon boxes
    # (Landsraad, City, Spice Trade) sit on the left edge; there is no Spy
    # eye box. The Korean scan (assets/cards/ko/uprising/imperium/Undercover
    # Asset.webp) shows the same three boxes and confirms this reading; only
    # the BGG inventory sheet's "Spy Access" mark was the slip.
    assert card.agent_icons == (
        AgentIcon.LANDSRAAD,
        AgentIcon.CITY,
        AgentIcon.SPICE_TRADE,
    )
    assert card.ignores_influence_requirements is True
    assert card.reveal_persuasion == 0
    assert card.reveal_strength == 0
    assert card_reveal_choices(card) == (
        "place_spy_or_gain_two_strength",
    )


def test_corrinth_city_play_data_is_complete() -> None:
    card = IMPERIUM_CARDS_BY_ID["corrinth_city"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.EMPEROR,)
    assert card.agent_icons == (AgentIcon.EMPEROR, AgentIcon.LANDSRAAD)
    assert (
        card_agent_box(card)
        == "may_discard_two_and_pay_five_solari_for_vp"
    )
    assert card.reveal_persuasion == 0
    assert card.reveal_strength == 0
    assert card_reveal_choices(card) == (
        "gain_five_solari_or_take_high_council",
    )


def test_desert_power_play_data_covers_maker_spice_and_sandworm_choice() -> None:
    card = IMPERIUM_CARDS_BY_ID["desert_power"]

    assert card.play_data_complete is True
    assert card.acquisition_cost == 6
    assert card.factions == (Faction.FREMEN,)
    assert card.agent_icons == (AgentIcon.SPICE_TRADE,)
    assert (
        card_agent_box(card)
        == "gain_two_spice_if_maker_space"
    )
    assert card.reveal_persuasion == 2
    assert card.reveal_strength == 0
    assert card_reveal_choices(card) == (
        "may_pay_water_for_sandworm",
    )


def test_long_live_the_fighters_play_data_matches_the_card() -> None:
    card = IMPERIUM_CARDS_BY_ID["long_live_the_fighters"]

    assert card.play_data_complete is True
    assert card.copies == 1
    assert card.acquisition_cost == 7
    assert card.factions == (Faction.FREMEN,)
    assert card.agent_icons == (AgentIcon.FREMEN, AgentIcon.CITY)
    assert card_agent_box(card) == "look_at_top_three"
    assert card.reveal_persuasion == 2
    assert card.reveal_strength == 3


def test_subversive_advisor_play_data_matches_the_card() -> None:
    card = IMPERIUM_CARDS_BY_ID["subversive_advisor"]

    assert card.play_data_complete is True
    assert card.copies == 1
    assert card.acquisition_cost == 5
    assert card.factions == ()
    assert card.agent_icons == (AgentIcon.SPY,)
    assert (
        card_agent_box(card)
        == "gain_two_visited_faction_influence_and_trash_self"
    )
    assert acquire_rewards(card.card.card_id) == (PlaceSpy(),)
    # Re-read from the card face 2026-09-26: the Reveal band prints a single
    # blue Persuasion diamond "1", not a Solari coin.
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 0
    assert _reveal_texts(card) == ()


def test_cargo_runner_play_data_scales_draws_with_completed_contracts() -> None:
    card = IMPERIUM_CARDS_BY_ID["cargo_runner"]

    assert card.play_data_complete is True
    assert card.acquisition_cost == 3
    assert card.factions == (Faction.SPACING_GUILD,)
    assert card.agent_icons == (
        AgentIcon.LANDSRAAD,
        AgentIcon.CITY,
        AgentIcon.SPICE_TRADE,
    )
    assert (
        card_agent_box(card)
        == "draw_per_two_completed_contracts_up_to_two"
    )
    assert card.reveal_persuasion == 1
    assert personal_card_for_instance(
        _instance("cargo_runner", choam_module=True)
    ) is card


def test_delivery_agreement_play_data_uses_the_printed_vp_choice() -> None:
    card = IMPERIUM_CARDS_BY_ID["delivery_agreement"]

    assert card.play_data_complete is True
    assert card.acquisition_cost == 5
    assert card.factions == (Faction.SPACING_GUILD,)
    assert card.agent_icons == (AgentIcon.CITY,)
    assert card_agent_box(card) == "may_discard_to_take_contract"
    assert card.reveal_persuasion == 0
    assert _reveal_texts(card) == ("Gain 1 spice",)
    assert card_reveal_choices(card) == (
        "keep_spice_or_trash_self_for_vp_if_four_contracts",
    )


def test_interstellar_trade_play_data_uses_contract_count_and_market() -> None:
    card = IMPERIUM_CARDS_BY_ID["interstellar_trade"]

    assert card.play_data_complete is True
    assert card.acquisition_cost == 7
    assert card.has_acquisition_bonus is True
    assert card.factions == (Faction.SPACING_GUILD,)
    assert card.agent_icons == (
        AgentIcon.LANDSRAAD,
        AgentIcon.CITY,
        AgentIcon.SPICE_TRADE,
    )
    assert card_agent_box(card) == "gain_chosen_influence"
    assert acquire_rewards(card.card.card_id) == (TakeContract(1),)
    assert card.reveal_persuasion == 0
    assert _reveal_texts(card) == ("+1 Persuasion per completed Contract",)


def test_priority_contracts_play_data_has_agent_and_reveal_contract_rewards() -> None:
    card = IMPERIUM_CARDS_BY_ID["priority_contracts"]

    assert card.play_data_complete is True
    assert card.acquisition_cost == 6
    assert card.factions == (Faction.SPACING_GUILD,)
    assert card.agent_icons == (AgentIcon.LANDSRAAD, AgentIcon.SPICE_TRADE)
    assert card_agent_box(card) == "take_contract"
    assert card.reveal_persuasion == 0
    assert _reveal_texts(card) == ("Gain 2 spice",)
    assert card_reveal_choices(card) == (
        "keep_spice_or_trash_self_for_vp_if_four_contracts",
    )


def test_every_acquisition_bonus_has_a_typed_effect() -> None:
    # The dispatcher advertises every Imperium acquisition, so a bonus without
    # a typed effect would raise after the Persuasion was already spent.
    for entry in IMPERIUM_CARDS_BY_ID.values():
        if entry.has_acquisition_bonus:
            card_id = entry.card.card_id
            assert acquisition_ability(card_id) is not None, card_id

