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
    PersonalCardAgentEffect,
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


def test_untranscribed_imperium_card_still_fails_explicitly() -> None:
    instance_id = _instance("double_agent")

    with pytest.raises(NotImplementedError, match="not transcribed"):
        personal_card_for_instance(instance_id)
