"""Tests for shared Faction Influence and Alliance transitions."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.board import Faction
from dune_imperium.core import GameState, Influence, PlayerState
from dune_imperium.rules.influence import gain_faction_influence


def test_influence_cannot_exceed_the_printed_track() -> None:
    with pytest.raises(ValueError, match="top of its track"):
        Influence(fremen=7)


@pytest.mark.parametrize(
    ("faction", "influence", "expected_water"),
    (
        (Faction.SPACING_GUILD, Influence(spacing_guild=3), 4),
        (Faction.FREMEN, Influence(fremen=3), 2),
    ),
)
def test_resource_track_bonuses_match_the_printed_board(
    faction: Faction,
    influence: Influence,
    expected_water: int,
) -> None:
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        players=(
            PlayerState(player_id=0, influence=influence),
            *(PlayerState(player_id=seat) for seat in range(1, 4)),
        ),
    )

    result = gain_faction_influence(
        state,
        0,
        faction,
        1,
        event_prefix="test:influence",
    ).state

    assert result.players[0].resources.water == expected_water
    assert result.players[0].alliance_faction_ids == (faction.value,)


def test_matching_the_holder_does_not_transfer_an_alliance() -> None:
    players = tuple(PlayerState(player_id=seat) for seat in range(4))
    challenger = replace(players[0], influence=Influence(emperor=3))
    holder = replace(
        players[1],
        influence=Influence(emperor=4),
        alliance_faction_ids=(Faction.EMPEROR.value,),
        victory_points=2,
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        players=(challenger, holder, *players[2:]),
    )

    result = gain_faction_influence(
        state,
        0,
        Faction.EMPEROR,
        1,
        event_prefix="test:influence",
    ).state

    assert result.players[0].influence.emperor == 4
    assert result.players[0].alliance_faction_ids == ()
    assert result.players[0].victory_points == 1
    assert result.players[1].alliance_faction_ids == (Faction.EMPEROR.value,)
    assert result.players[1].victory_points == 2
