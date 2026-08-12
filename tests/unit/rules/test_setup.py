"""Tests for rules-backed player setup constructors."""

import pytest

from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.objectives import objectives_for_players
from dune_imperium.content.uprising.types import ConflictTier
from dune_imperium.core import ChanceResolver, PlayerState
from dune_imperium.rules.setup import (
    apply_starting_deck_shuffle,
    assign_objectives,
    build_conflict_setup,
    conflict_setup_decisions,
    create_unshuffled_players,
    objective_setup_decision,
    starting_deck_shuffle_decision,
)


def test_four_players_start_with_official_resources_and_components() -> None:
    players = create_unshuffled_players()

    assert tuple(player.player_id for player in players) == (0, 1, 2, 3)
    for player in players:
        assert player.victory_points == 1
        assert player.resources.solari == 0
        assert player.resources.spice == 0
        assert player.resources.water == 1
        assert player.agents_available == 2
        assert player.swordmaster_acquired is False
        assert player.troops_supply == 9
        assert player.troops_garrison == 3
        assert player.troops_conflict == 0
        assert player.spies_supply == 3
        assert player.influence.emperor == 0
        assert player.influence.spacing_guild == 0
        assert player.influence.bene_gesserit == 0
        assert player.influence.fremen == 0
        assert player.combat_strength == 0
        assert len(player.deck) == 10
        assert player.hand == ()


def test_troop_conservation_is_enforced() -> None:
    with pytest.raises(ValueError, match="all 12 troops"):
        PlayerState(player_id=0, troops_supply=8)


def test_agent_conservation_accounts_for_the_swordmaster() -> None:
    with pytest.raises(ValueError, match="active agents"):
        PlayerState(player_id=0, agents_available=3)

    acquired = PlayerState(
        player_id=0,
        agents_available=3,
        swordmaster_acquired=True,
    )
    assert acquired.agents_available == 3


def test_spy_conservation_is_enforced() -> None:
    with pytest.raises(ValueError, match="three spies"):
        PlayerState(player_id=0, spies_supply=2)


def test_conflict_setup_builds_tiered_deck_and_tracks_unused_cards() -> None:
    resolver = ChanceResolver(seed=123)
    outcomes = tuple(
        resolver.resolve(decision) for decision in conflict_setup_decisions()
    )

    setup = build_conflict_setup(outcomes)
    tier_by_id = {conflict.card.card_id: conflict.tier for conflict in CONFLICTS}

    assert len(setup.deck) == 10
    assert len(set(setup.unused)) == 6
    assert tuple(tier_by_id[card_id] for card_id in setup.deck) == (
        ConflictTier.ONE,
        *(ConflictTier.TWO for _ in range(5)),
        *(ConflictTier.THREE for _ in range(4)),
    )
    assert set(setup.deck) | set(setup.unused) == set(tier_by_id)


def test_same_seed_repeats_conflict_setup() -> None:
    decisions = conflict_setup_decisions()

    first = ChanceResolver(seed=99)
    second = ChanceResolver(seed=99)

    assert build_conflict_setup(
        tuple(first.resolve(decision) for decision in decisions)
    ) == build_conflict_setup(tuple(second.resolve(decision) for decision in decisions))


def test_objectives_are_dealt_once_and_determine_first_player() -> None:
    players = create_unshuffled_players()
    resolver = ChanceResolver(seed=321)

    assigned, first_player = assign_objectives(
        players,
        resolver.resolve(objective_setup_decision()),
    )

    dealt = tuple(player.objective_ids[0] for player in assigned)
    expected = {objective.objective_id for objective in objectives_for_players(4)}
    assert set(dealt) == expected
    assert assigned[first_player].objective_ids == ("objective_desert_mouse",)


def test_starting_deck_shuffle_is_a_full_recorded_permutation() -> None:
    player = create_unshuffled_players()[0]
    before = player.deck
    resolver = ChanceResolver(seed=456)

    shuffled = apply_starting_deck_shuffle(
        player,
        resolver.resolve(starting_deck_shuffle_decision(player)),
    )

    assert set(shuffled.deck) == set(before)
    assert len(shuffled.deck) == 10
    assert shuffled.deck != before
