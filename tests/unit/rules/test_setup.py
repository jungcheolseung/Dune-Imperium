"""Tests for rules-backed player setup constructors."""

import pytest

from dune_imperium.core import PlayerState
from dune_imperium.rules.setup import create_unshuffled_players


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
