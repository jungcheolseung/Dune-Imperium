"""Tests for the official ten-card Uprising starting deck."""

from collections import Counter

from dune_imperium.content.uprising.starting_cards import (
    STARTING_CARDS_BY_ID,
    STARTING_DECK,
    StartingCardAgentEffect,
    starting_deck_instance_ids,
)
from dune_imperium.content.uprising.types import AgentIcon


def test_starting_deck_counts_match_main_rulebook_page_three() -> None:
    assert sum(entry.copies for entry in STARTING_DECK) == 10
    assert Counter({entry.card.card_id: entry.copies for entry in STARTING_DECK}) == {
        "convincing_argument": 2,
        "dagger": 2,
        "diplomacy": 1,
        "dune_the_desert_planet": 2,
        "reconnaissance": 1,
        "seek_allies": 1,
        "signet_ring": 1,
    }


def test_card_instances_are_unique_within_and_between_players() -> None:
    decks = tuple(starting_deck_instance_ids(player) for player in range(4))

    assert all(len(deck) == len(set(deck)) == 10 for deck in decks)
    assert len(set().union(*map(set, decks))) == 40


def test_starting_card_agent_icons_match_the_printed_cards() -> None:
    cards = STARTING_CARDS_BY_ID

    assert cards["convincing_argument"].agent_icons == ()
    assert cards["dagger"].agent_icons == (AgentIcon.LANDSRAAD,)
    assert cards["diplomacy"].agent_icons == (
        AgentIcon.EMPEROR,
        AgentIcon.SPACING_GUILD,
        AgentIcon.BENE_GESSERIT,
        AgentIcon.FREMEN,
    )
    assert cards["dune_the_desert_planet"].agent_icons == (
        AgentIcon.SPICE_TRADE,
    )
    assert cards["reconnaissance"].agent_icons == (AgentIcon.CITY,)
    assert cards["seek_allies"].agent_icons == cards["diplomacy"].agent_icons
    assert cards["signet_ring"].agent_icons == (
        AgentIcon.LANDSRAAD,
        AgentIcon.CITY,
        AgentIcon.SPICE_TRADE,
    )


def test_starting_card_basic_effect_metadata_is_typed() -> None:
    cards = STARTING_CARDS_BY_ID

    assert cards["seek_allies"].agent_effect is StartingCardAgentEffect.TRASH_SELF
    assert (
        cards["signet_ring"].agent_effect
        is StartingCardAgentEffect.LEADER_SIGNET
    )
    assert cards["convincing_argument"].reveal_persuasion == 2
    assert cards["dagger"].reveal_strength == 1
    assert all(
        card.reveal_persuasion == 1
        for card_id, card in cards.items()
        if card_id
        in {
            "diplomacy",
            "dune_the_desert_planet",
            "reconnaissance",
            "signet_ring",
        }
    )
