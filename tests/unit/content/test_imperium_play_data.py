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


def test_untranscribed_imperium_card_still_fails_explicitly() -> None:
    instance_id = _instance("double_agent")

    with pytest.raises(NotImplementedError, match="not transcribed"):
        personal_card_for_instance(instance_id)


def test_personal_card_reveal_effect_requires_a_nonnegative_gain() -> None:
    with pytest.raises(ValueError, match="must gain"):
        PersonalCardRevealEffect()
    with pytest.raises(ValueError, match="must gain"):
        PersonalCardRevealEffect(minimum_spies_placed=2)
    with pytest.raises(ValueError, match="must not be negative"):
        PersonalCardRevealEffect(water=-1)
    with pytest.raises(TypeError, match="must use PersonalCardBond"):
        PersonalCardRevealEffect(  # type: ignore[arg-type]
            water=1,
            required_faction_bond="fremen",
        )
    with pytest.raises(ValueError, match="also needs High Council"):
        PersonalCardRevealEffect(persuasion=1, requires_swordmaster=True)
