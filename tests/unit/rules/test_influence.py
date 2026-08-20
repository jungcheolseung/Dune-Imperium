"""Tests for shared Faction Influence and Alliance transitions."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.board import Faction
from dune_imperium.core import GameState, Influence, PlayerState
from dune_imperium.rules.influence import (
    alliance_recipients_after_influence_loss,
    gain_faction_influence,
    lose_faction_influence,
)


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


def test_losing_influence_below_two_removes_friendship_vp() -> None:
    owner = PlayerState(
        player_id=0,
        influence=Influence(fremen=2),
        victory_points=1,
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
    )

    result = lose_faction_influence(
        state,
        0,
        Faction.FREMEN,
        1,
        event_prefix="test:influence",
    )

    assert result.state.players[0].influence.fremen == 1
    assert result.state.players[0].victory_points == 0
    assert result.events[0].kind == "influence_lost"


def test_losing_influence_transfers_alliance_to_previously_tied_player() -> None:
    players = tuple(PlayerState(player_id=seat) for seat in range(4))
    holder = replace(
        players[0],
        influence=Influence(emperor=5),
        alliance_faction_ids=(Faction.EMPEROR.value,),
        victory_points=2,
    )
    tied = replace(players[1], influence=Influence(emperor=5), victory_points=1)
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        players=(holder, tied, *players[2:]),
    )

    result = lose_faction_influence(
        state,
        0,
        Faction.EMPEROR,
        1,
        event_prefix="test:influence",
    )

    assert result.state.players[0].alliance_faction_ids == ()
    assert result.state.players[0].victory_points == 1
    assert result.state.players[1].alliance_faction_ids == (Faction.EMPEROR.value,)
    assert result.state.players[1].victory_points == 2
    assert result.events[-1].kind == "alliance_transferred"


def test_losing_influence_below_four_returns_unclaimed_alliance() -> None:
    players = tuple(PlayerState(player_id=seat) for seat in range(4))
    holder = replace(
        players[0],
        influence=Influence(spacing_guild=4),
        alliance_faction_ids=(Faction.SPACING_GUILD.value,),
        victory_points=2,
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        players=(holder, *players[1:]),
    )

    result = lose_faction_influence(
        state,
        0,
        Faction.SPACING_GUILD,
        1,
        event_prefix="test:influence",
    )

    assert result.state.players[0].alliance_faction_ids == ()
    assert result.state.players[0].victory_points == 1
    assert result.events[-1].kind == "alliance_lost"


def test_losing_influence_requires_choice_between_alliance_recipients() -> None:
    players = tuple(PlayerState(player_id=seat) for seat in range(4))
    holder = replace(
        players[0],
        influence=Influence(bene_gesserit=4),
        alliance_faction_ids=(Faction.BENE_GESSERIT.value,),
        victory_points=2,
    )
    first = replace(players[1], influence=Influence(bene_gesserit=4))
    second = replace(players[2], influence=Influence(bene_gesserit=4))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        players=(holder, first, second, players[3]),
    )

    assert alliance_recipients_after_influence_loss(
        state,
        0,
        Faction.BENE_GESSERIT,
    ) == (1, 2)
    with pytest.raises(ValueError, match="requires an Alliance recipient"):
        lose_faction_influence(
            state,
            0,
            Faction.BENE_GESSERIT,
            1,
            event_prefix="test:influence",
        )

    result = lose_faction_influence(
        state,
        0,
        Faction.BENE_GESSERIT,
        1,
        event_prefix="test:influence",
        alliance_recipient=2,
    ).state

    assert result.players[0].alliance_faction_ids == ()
    assert result.players[2].alliance_faction_ids == (Faction.BENE_GESSERIT.value,)
