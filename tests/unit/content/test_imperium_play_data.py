"""Tests for DIU-bootstrapped Imperium-card play data."""

import pytest

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.imperium import (
    IMPERIUM_CARDS_BY_ID,
    imperium_deck_instance_ids,
)
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.types import (
    AgentIcon,
    PersonalCardAcquisitionEffect,
    PersonalCardAgentEffect,
    PersonalCardBond,
    PersonalCardDiscardEffect,
    PersonalCardRevealAcquisitionEffect,
    PersonalCardRevealChoiceEffect,
    PersonalCardRevealEffect,
    PersonalCardTrashEffect,
)


def _instance(card_id: str) -> str:
    return next(
        instance_id
        for instance_id in imperium_deck_instance_ids(False)
        if f":{card_id}:" in instance_id
    )


def test_maula_pistol_play_data_matches_the_diu_transcription() -> None:
    card = IMPERIUM_CARDS_BY_ID["maula_pistol"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.FREMEN,)
    assert card.agent_icons == (AgentIcon.CITY, AgentIcon.SPICE_TRADE)
    assert card.agent_effect is PersonalCardAgentEffect.DRAW_PERSONAL_CARD
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 1
    assert personal_card_for_instance(_instance("maula_pistol")) is card


def test_bene_gesserit_operative_play_data_places_and_counts_spies() -> None:
    card = IMPERIUM_CARDS_BY_ID["bene_gesserit_operative"]

    assert card.play_data_complete is True
    assert card.factions == ()
    assert card.agent_icons == (AgentIcon.BENE_GESSERIT,)
    assert card.agent_effect is PersonalCardAgentEffect.PLACE_SPY
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 0
    assert card.reveal_effects == (
        PersonalCardRevealEffect(persuasion=2, minimum_spies_placed=2),
    )


def test_reliable_informant_play_data_restricts_its_spy_targets() -> None:
    card = IMPERIUM_CARDS_BY_ID["reliable_informant"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.SPACING_GUILD,)
    assert card.agent_icons == (AgentIcon.SPACING_GUILD,)
    assert card.agent_effect is PersonalCardAgentEffect.PLACE_SPY
    assert card.agent_spy_factions == (
        Faction.EMPEROR,
        Faction.BENE_GESSERIT,
        Faction.SPACING_GUILD,
    )
    assert card.reveal_persuasion == 1
    assert card.reveal_effects == (PersonalCardRevealEffect(solari=1),)


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
    assert card.agent_effect is None
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 0


def test_sardaukar_soldier_play_data_includes_its_trash_trigger() -> None:
    card = IMPERIUM_CARDS_BY_ID["sardaukar_soldier"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.EMPEROR,)
    assert card.agent_icons == (AgentIcon.CITY,)
    assert card.agent_effect is None
    assert card.trash_effect is PersonalCardTrashEffect.DRAW_INTRIGUE_CARD
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 1


def test_sardaukar_coordination_play_data_deploys_and_counts_emperor_cards() -> None:
    card = IMPERIUM_CARDS_BY_ID["sardaukar_coordination"]

    assert card.play_data_complete is True
    assert card.copies == 2
    assert card.factions == (Faction.EMPEROR,)
    assert card.agent_icons == (AgentIcon.EMPEROR, AgentIcon.LANDSRAAD)
    assert card.allows_recruited_troop_deployment is True
    assert card.reveal_strength == 1
    assert card.reveal_effects == (
        PersonalCardRevealEffect(
            strength=1,
            per_revealed_faction=PersonalCardBond.EMPEROR,
        ),
    )


def test_hidden_missive_play_data_includes_its_conditional_agent_effect() -> None:
    card = IMPERIUM_CARDS_BY_ID["hidden_missive"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.BENE_GESSERIT,)
    assert card.agent_icons == (AgentIcon.LANDSRAAD,)
    assert (
        card.agent_effect
        is PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO
    )
    assert card.trash_effect is None
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 1


def test_desert_survival_play_data_includes_its_optional_trash() -> None:
    card = IMPERIUM_CARDS_BY_ID["desert_survival"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.FREMEN,)
    assert card.agent_icons == (AgentIcon.SPICE_TRADE,)
    assert card.agent_effect is PersonalCardAgentEffect.TRASH_PERSONAL_CARD
    assert card.trash_effect is None
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 1


def test_smugglers_harvester_play_data_includes_its_maker_bonus() -> None:
    card = IMPERIUM_CARDS_BY_ID["smuggler_s_harvester"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.SPACING_GUILD,)
    assert card.agent_icons == (AgentIcon.SPICE_TRADE,)
    assert card.agent_effect is PersonalCardAgentEffect.GAIN_SPICE_IF_MAKER_SPACE
    assert card.trash_effect is None
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 0


def test_smugglers_haven_play_data_uses_the_printed_reveal_persuasion() -> None:
    card = IMPERIUM_CARDS_BY_ID["smuggler_s_haven"]

    assert card.play_data_complete is True
    assert card.copies == 1
    assert card.factions == (Faction.SPACING_GUILD,)
    assert card.agent_icons == (AgentIcon.SPACING_GUILD, AgentIcon.SPICE_TRADE)
    assert card.agent_effect is PersonalCardAgentEffect.MAY_PAY_FOUR_SPICE_FOR_VP
    assert card.reveal_persuasion == 1
    assert card.reveal_effects == (
        PersonalCardRevealEffect(
            spice=2,
            requires_spying_on_maker_space=True,
        ),
    )


def test_price_is_no_object_play_data_acquires_with_solari_to_hand() -> None:
    card = IMPERIUM_CARDS_BY_ID["price_is_no_object"]

    assert card.play_data_complete is True
    assert card.copies == 1
    assert card.factions == (Faction.EMPEROR, Faction.BENE_GESSERIT)
    assert card.agent_icons == (AgentIcon.EMPEROR, AgentIcon.BENE_GESSERIT)
    assert card.agent_effect is PersonalCardAgentEffect.ACQUIRE_WITH_SOLARI_TO_HAND
    assert card.acquisition_effect is PersonalCardAcquisitionEffect.GAIN_TWO_SOLARI
    assert card.reveal_persuasion == 2
    assert card.reveal_effects == (PersonalCardRevealEffect(solari=2),)


def test_fedaykin_stilltent_play_data_has_maker_and_reveal_gains() -> None:
    card = IMPERIUM_CARDS_BY_ID["fedaykin_stilltent"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.FREMEN,)
    assert card.agent_icons == (AgentIcon.SPICE_TRADE,)
    assert card.agent_effect is PersonalCardAgentEffect.RECRUIT_ONE_IF_MAKER_SPACE
    assert card.reveal_effects == (PersonalCardRevealEffect(water=1),)
    assert card.reveal_persuasion == 0
    assert card.reveal_strength == 0


def test_northern_watermaster_play_data_has_fremen_bond_gain() -> None:
    card = IMPERIUM_CARDS_BY_ID["northern_watermaster"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.FREMEN,)
    assert card.agent_icons == (AgentIcon.CITY,)
    assert card.agent_effect is PersonalCardAgentEffect.GAIN_WATER
    assert card.reveal_persuasion == 1
    assert card.reveal_effects == (
        PersonalCardRevealEffect(
            spice=2,
            required_faction_bond=PersonalCardBond.FREMEN,
        ),
    )


def test_maker_keeper_play_data_has_independent_influence_rewards() -> None:
    card = IMPERIUM_CARDS_BY_ID["maker_keeper"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.BENE_GESSERIT, Faction.FREMEN)
    assert card.agent_icons == (AgentIcon.CITY, AgentIcon.SPICE_TRADE)
    assert (
        card.agent_effect
        is PersonalCardAgentEffect.GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO
    )
    assert card.reveal_persuasion == 2
    assert card.reveal_strength == 0


def test_southern_elders_play_data_has_two_reveal_effects() -> None:
    card = IMPERIUM_CARDS_BY_ID["southern_elders"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.BENE_GESSERIT, Faction.FREMEN)
    assert card.agent_icons == (AgentIcon.BENE_GESSERIT, AgentIcon.FREMEN)
    assert (
        card.agent_effect
        is PersonalCardAgentEffect.RECRUIT_TWO_IF_BENE_GESSERIT_BOND
    )
    assert card.reveal_effects == (
        PersonalCardRevealEffect(water=1),
        PersonalCardRevealEffect(
            persuasion=2,
            required_faction_bond=PersonalCardBond.FREMEN,
        ),
    )


def test_weirding_woman_play_data_has_bond_return_effect() -> None:
    card = IMPERIUM_CARDS_BY_ID["weirding_woman"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.BENE_GESSERIT,)
    assert card.agent_icons == (AgentIcon.CITY, AgentIcon.SPICE_TRADE)
    assert (
        card.agent_effect
        is PersonalCardAgentEffect.RETURN_SELF_IF_BENE_GESSERIT_BOND
    )
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 1


def test_ecological_testing_station_play_data_has_payment_and_bond_gain() -> None:
    card = IMPERIUM_CARDS_BY_ID["ecological_testing_station"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.FREMEN,)
    assert card.agent_icons == (AgentIcon.FREMEN, AgentIcon.CITY)
    assert card.agent_effect is PersonalCardAgentEffect.PAY_TWO_WATER_TO_DRAW_TWO
    assert card.reveal_persuasion == 1
    assert card.reveal_effects == (
        PersonalCardRevealEffect(
            water=1,
            required_faction_bond=PersonalCardBond.FREMEN,
        ),
    )


def test_paracompass_play_data_has_council_and_swordmaster_reveal_gains() -> None:
    card = IMPERIUM_CARDS_BY_ID["paracompass"]

    assert card.play_data_complete is True
    assert card.factions == ()
    assert card.agent_icons == (AgentIcon.CITY,)
    assert card.agent_effect is PersonalCardAgentEffect.GAIN_TWO_SOLARI
    assert card.reveal_effects == (
        PersonalCardRevealEffect(
            persuasion=2,
            requires_high_council=True,
        ),
        PersonalCardRevealEffect(
            persuasion=1,
            requires_high_council=True,
            requires_swordmaster=True,
        ),
    )


def test_overthrow_play_data_covers_acquisition_agent_and_reveal() -> None:
    card = IMPERIUM_CARDS_BY_ID["overthrow"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.EMPEROR,)
    assert card.agent_icons == (
        AgentIcon.EMPEROR,
        AgentIcon.SPACING_GUILD,
        AgentIcon.BENE_GESSERIT,
        AgentIcon.FREMEN,
    )
    assert card.agent_effect is PersonalCardAgentEffect.GAIN_VISITED_FACTION_INFLUENCE
    assert (
        card.acquisition_effect
        is PersonalCardAcquisitionEffect.DRAW_INTRIGUE_CARD
    )
    assert card.reveal_persuasion == 2
    assert card.reveal_strength == 2
    assert card.reveal_effects == (PersonalCardRevealEffect(recruit_troops=1),)


def test_strike_fleet_play_data_covers_spy_acquisition_and_recall_reward() -> None:
    card = IMPERIUM_CARDS_BY_ID["strike_fleet"]

    assert card.play_data_complete is True
    assert card.factions == ()
    assert card.agent_icons == (AgentIcon.SPY,)
    assert (
        card.agent_effect
        is PersonalCardAgentEffect.RECRUIT_THREE_IF_SPY_RECALLED_THIS_TURN
    )
    assert card.acquisition_effect is PersonalCardAcquisitionEffect.PLACE_SPY
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 3


def test_imperial_spymaster_play_data_uses_the_turn_recall_condition() -> None:
    card = IMPERIUM_CARDS_BY_ID["imperial_spymaster"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.EMPEROR,)
    assert card.agent_icons == (AgentIcon.EMPEROR, AgentIcon.SPY)
    assert (
        card.agent_effect
        is PersonalCardAgentEffect.DRAW_INTRIGUE_IF_SPY_RECALLED_THIS_TURN
    )
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 1


def test_spy_network_play_data_has_acquisition_and_reveal_spy_effects() -> None:
    card = IMPERIUM_CARDS_BY_ID["spy_network"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.EMPEROR, Faction.SPACING_GUILD)
    assert card.agent_icons == ()
    assert card.agent_effect is None
    assert card.acquisition_effect is PersonalCardAcquisitionEffect.PLACE_SPY
    assert card.reveal_persuasion == 2
    assert card.reveal_strength == 1
    assert card.reveal_choice_effects == (
        PersonalCardRevealChoiceEffect.RECALL_SPY_TO_DRAW_INTRIGUE_IF_TWO_PLACED,
    )


def test_in_high_places_play_data_has_bond_acquisition_and_reveal_choice() -> None:
    card = IMPERIUM_CARDS_BY_ID["in_high_places"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.BENE_GESSERIT,)
    assert card.agent_icons == (AgentIcon.BENE_GESSERIT, AgentIcon.EMPEROR)
    assert (
        card.agent_effect
        is PersonalCardAgentEffect.GAIN_WATER_IF_BENE_GESSERIT_BOND
    )
    assert card.acquisition_effect is PersonalCardAcquisitionEffect.PLACE_SPY
    assert card.reveal_persuasion == 2
    assert card.reveal_strength == 0
    assert card.reveal_choice_effects == (
        PersonalCardRevealChoiceEffect.MAY_RECALL_TWO_SPIES_FOR_TWO_PERSUASION,
    )


def test_rebel_supplier_play_data_uses_the_turn_recall_condition() -> None:
    card = IMPERIUM_CARDS_BY_ID["rebel_supplier"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.FREMEN,)
    assert card.agent_icons == (AgentIcon.CITY,)
    assert (
        card.agent_effect
        is PersonalCardAgentEffect.RECRUIT_TWO_IF_SPY_RECALLED_THIS_TURN
    )
    assert card.reveal_persuasion == 0
    assert card.reveal_strength == 1
    assert card.reveal_effects == (PersonalCardRevealEffect(spice=1),)


def test_dangerous_rhetoric_play_data_trashes_for_chosen_influence() -> None:
    card = IMPERIUM_CARDS_BY_ID["dangerous_rhetoric"]

    assert card.play_data_complete is True
    assert card.factions == ()
    assert card.agent_icons == (AgentIcon.LANDSRAAD, AgentIcon.SPY)
    assert (
        card.agent_effect
        is PersonalCardAgentEffect.TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE
    )
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 1


def test_public_spectacle_play_data_uses_spy_recall_and_placement() -> None:
    card = IMPERIUM_CARDS_BY_ID["public_spectacle"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.EMPEROR,)
    assert card.agent_icons == (AgentIcon.SPY,)
    assert (
        card.agent_effect
        is PersonalCardAgentEffect.GAIN_CHOSEN_INFLUENCE_IF_SPY_RECALLED_THIS_TURN
    )
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 0
    assert card.reveal_choice_effects == (
        PersonalCardRevealChoiceEffect.PLACE_SPY,
    )


def test_wheels_within_wheels_play_data_reuses_reveal_spy_placement() -> None:
    card = IMPERIUM_CARDS_BY_ID["wheels_within_wheels"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.EMPEROR, Faction.SPACING_GUILD)
    assert card.agent_icons == (AgentIcon.SPY,)
    assert (
        card.agent_effect
        is PersonalCardAgentEffect.GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO
    )
    assert card.reveal_persuasion == 1
    assert card.reveal_choice_effects == (
        PersonalCardRevealChoiceEffect.PLACE_SPY,
    )


def test_unswerving_loyalty_play_data_has_only_reveal_rewards() -> None:
    card = IMPERIUM_CARDS_BY_ID["unswerving_loyalty"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.FREMEN,)
    assert card.agent_icons == ()
    assert card.agent_effect is None
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 0
    assert card.reveal_effects == (
        PersonalCardRevealEffect(recruit_troops=1),
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
    assert card.agent_effect is PersonalCardAgentEffect.RECRUIT_TWO_TROOPS
    assert card.reveal_effects == (
        PersonalCardRevealEffect(
            persuasion=2,
            per_revealed_faction=PersonalCardBond.FREMEN,
        ),
    )


def test_leadership_play_data_scales_with_worms_and_other_sword_cards() -> None:
    card = IMPERIUM_CARDS_BY_ID["leadership"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.FREMEN,)
    assert card.agent_icons == (AgentIcon.FREMEN, AgentIcon.SPICE_TRADE)
    assert (
        card.agent_effect
        is PersonalCardAgentEffect.DRAW_PER_SANDWORM_IN_CONFLICT
    )
    assert card.reveal_persuasion == 2
    assert card.reveal_strength == 1
    assert card.reveal_effects == (
        PersonalCardRevealEffect(strength_per_other_sword_card=1),
    )


def test_shishakli_play_data_has_trash_draw_and_fremen_bond_influence() -> None:
    card = IMPERIUM_CARDS_BY_ID["shishakli"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.FREMEN,)
    assert card.agent_icons == (AgentIcon.CITY, AgentIcon.SPICE_TRADE)
    assert (
        card.agent_effect
        is PersonalCardAgentEffect.TRASH_PERSONAL_CARD_TO_DRAW_ONE
    )
    assert card.reveal_strength == 2
    assert card.reveal_effects == (
        PersonalCardRevealEffect(
            influence=1,
            influence_faction=PersonalCardBond.FREMEN,
            required_faction_bond=PersonalCardBond.FREMEN,
        ),
    )


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
        card.agent_effect
        is PersonalCardAgentEffect.TRASH_PERSONAL_CARD_TO_DRAW_ONE_IF_BENE_GESSERIT_BOND
    )
    assert card.reveal_persuasion == 2
    assert card.reveal_strength == 1


def test_space_time_folding_play_data_has_conditional_discard_draw() -> None:
    card = IMPERIUM_CARDS_BY_ID["space_time_folding"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.SPACING_GUILD,)
    assert card.agent_icons == (AgentIcon.SPACING_GUILD,)
    assert (
        card.agent_effect
        is PersonalCardAgentEffect.DISCARD_TO_DRAW_ONE_OR_TWO_IF_SPACING_GUILD
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
        card.agent_effect
        is PersonalCardAgentEffect.DISCARD_ONE_DRAW_TWO_IF_SPACING_GUILD
    )
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 0


def test_captured_mentat_play_data_has_discard_and_influence_choices() -> None:
    card = IMPERIUM_CARDS_BY_ID["captured_mentat"]

    assert card.play_data_complete is True
    assert card.factions == ()
    assert card.agent_icons == (AgentIcon.LANDSRAAD, AgentIcon.SPICE_TRADE)
    assert (
        card.agent_effect
        is PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_INTRIGUE_AND_PERSONAL_CARD
    )
    assert card.reveal_persuasion == 1
    assert card.reveal_choice_effects == (
        PersonalCardRevealChoiceEffect.MAY_LOSE_INFLUENCE_TO_GAIN_INFLUENCE,
    )


def test_spacing_guilds_favor_play_data_has_discard_and_reveal_payments() -> None:
    card = IMPERIUM_CARDS_BY_ID["spacing_guild_s_favor"]

    assert card.play_data_complete is True
    assert card.copies == 2
    assert card.factions == (Faction.SPACING_GUILD,)
    assert card.agent_icons == (AgentIcon.SPACING_GUILD, AgentIcon.SPICE_TRADE)
    assert card.agent_effect is PersonalCardAgentEffect.DRAW_PERSONAL_CARD
    assert card.discard_effect is PersonalCardDiscardEffect.GAIN_TWO_SPICE
    assert card.reveal_persuasion == 2
    assert card.reveal_choice_effects == (
        PersonalCardRevealChoiceEffect.MAY_PAY_THREE_SPICE_FOR_INFLUENCE,
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
        card.agent_effect
        is PersonalCardAgentEffect.PLACE_SPY_ALLOW_SHARED_IF_SPYING_ON_VISITED_SPACE
    )
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 1


def test_guild_spy_play_data_has_discard_acquisition_and_reveal_triggers() -> None:
    card = IMPERIUM_CARDS_BY_ID["guild_spy"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.SPACING_GUILD,)
    assert card.agent_icons == (AgentIcon.SPY,)
    assert (
        card.agent_effect
        is PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_ONE_AND_INTRIGUE_IF_SPACING_GUILD
    )
    assert card.acquisition_effect is PersonalCardAcquisitionEffect.PLACE_SPY
    assert card.reveal_persuasion == 2
    assert (
        card.reveal_acquisition_effect
        is (
            PersonalCardRevealAcquisitionEffect.GAIN_INFLUENCE_FOR_EACH_SPIED_FACTION_ON_SPICE_MUST_FLOW
        )
    )


def test_covert_operation_play_data_forces_each_opponent_to_discard() -> None:
    card = IMPERIUM_CARDS_BY_ID["covert_operation"]

    assert card.play_data_complete is True
    assert card.factions == ()
    assert card.agent_icons == (AgentIcon.SPY,)
    assert (
        card.agent_effect
        is PersonalCardAgentEffect.EACH_OPPONENT_DISCARDS_PERSONAL_CARD
    )
    assert card.reveal_persuasion == 2
    assert card.reveal_strength == 0


def test_calculus_of_power_play_data_trashes_self_or_another_emperor() -> None:
    card = IMPERIUM_CARDS_BY_ID["calculus_of_power"]

    assert card.play_data_complete is True
    assert card.copies == 2
    assert card.factions == (Faction.EMPEROR,)
    assert card.agent_icons == (AgentIcon.LANDSRAAD, AgentIcon.SPY)
    assert card.agent_effect is PersonalCardAgentEffect.TRASH_SELF
    assert card.reveal_persuasion == 2
    assert card.reveal_choice_effects == (
        PersonalCardRevealChoiceEffect.MAY_TRASH_OTHER_EMPEROR_FOR_THREE_STRENGTH,
    )


def test_branching_path_play_data_has_alliance_trash_reward() -> None:
    card = IMPERIUM_CARDS_BY_ID["branching_path"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.BENE_GESSERIT,)
    assert card.agent_icons == (AgentIcon.BENE_GESSERIT, AgentIcon.LANDSRAAD)
    assert (
        card.agent_effect
        is (
            PersonalCardAgentEffect.MAY_TRASH_FOR_INTRIGUE_AND_TWO_TROOPS_IF_BENE_GESSERIT_ALLIANCE
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
        card.agent_effect
        is PersonalCardAgentEffect.TRASH_SELF_AND_EMPEROR_FROM_HAND_FOR_EXTRA_INFLUENCE
    )
    assert card.reveal_persuasion == 1
    assert card.reveal_strength == 0
    assert card.reveal_effects == (PersonalCardRevealEffect(draw_intrigue=1),)


def test_chani_clever_tactician_play_data_matches_the_card() -> None:
    card = IMPERIUM_CARDS_BY_ID["chani_clever_tactician"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.FREMEN,)
    assert card.agent_icons == (
        AgentIcon.SPACING_GUILD,
        AgentIcon.CITY,
        AgentIcon.SPICE_TRADE,
    )
    assert (
        card.agent_effect
        is PersonalCardAgentEffect.DRAW_INTRIGUE_IF_THREE_UNITS_IN_CONFLICT
    )
    assert card.reveal_persuasion == 0
    assert card.reveal_strength == 0
    assert card.reveal_effects == (
        PersonalCardRevealEffect(
            persuasion=2,
            required_faction_bond=PersonalCardBond.FREMEN,
        ),
    )
    assert card.reveal_choice_effects == (
        PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_FOUR_STRENGTH,
    )


def test_undercover_asset_play_data_is_complete() -> None:
    card = IMPERIUM_CARDS_BY_ID["undercover_asset"]

    assert card.play_data_complete is True
    assert card.factions == (Faction.EMPEROR, Faction.SPACING_GUILD)
    assert card.agent_icons == (
        AgentIcon.LANDSRAAD,
        AgentIcon.CITY,
        AgentIcon.SPICE_TRADE,
        AgentIcon.SPY,
    )
    assert card.ignores_influence_requirements is True
    assert card.reveal_persuasion == 0
    assert card.reveal_strength == 0
    assert card.reveal_choice_effects == (
        PersonalCardRevealChoiceEffect.PLACE_SPY_OR_GAIN_TWO_STRENGTH,
    )


def test_untranscribed_imperium_card_still_fails_explicitly() -> None:
    instance_id = _instance("corrinth_city")

    with pytest.raises(NotImplementedError, match="not transcribed"):
        personal_card_for_instance(instance_id)


def test_personal_card_reveal_effect_requires_a_nonnegative_gain() -> None:
    with pytest.raises(ValueError, match="must gain"):
        PersonalCardRevealEffect()
    with pytest.raises(ValueError, match="must gain"):
        PersonalCardRevealEffect(minimum_spies_placed=2)
    with pytest.raises(ValueError, match="must not be negative"):
        PersonalCardRevealEffect(water=-1)
    with pytest.raises(ValueError, match="must not be negative"):
        PersonalCardRevealEffect(draw_intrigue=-1)
    with pytest.raises(TypeError, match="must use PersonalCardBond"):
        PersonalCardRevealEffect(
            water=1,
            required_faction_bond="fremen",  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="also needs High Council"):
        PersonalCardRevealEffect(persuasion=1, requires_swordmaster=True)
    with pytest.raises(ValueError, match="requires Persuasion or strength"):
        PersonalCardRevealEffect(
            water=1,
            per_revealed_faction=PersonalCardBond.FREMEN,
        )
    with pytest.raises(ValueError, match="must be paired"):
        PersonalCardRevealEffect(influence=1)
