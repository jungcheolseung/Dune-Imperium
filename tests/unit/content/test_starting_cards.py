"""Tests for the official ten-card Uprising starting deck."""

from collections import Counter

from dune_imperium.content.uprising.starting_cards import (
    STARTING_DECK,
    starting_deck_instance_ids,
)


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
