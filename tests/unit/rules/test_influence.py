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


def _at_three(faction: Faction) -> GameState:
    return GameState(
        config=RulesetConfig(),
        seed=1,
        players=(
            PlayerState(player_id=0, influence=Influence(**{faction.value: 3})),
            *(PlayerState(player_id=seat) for seat in range(1, 4)),
        ),
        intrigue_deck=("intrigue:ambush:1", "intrigue:bribery:1"),
    )


def test_track_bonuses_match_the_printed_board() -> None:
    # "When you reach 4 Influence, you earn the bonus shown on that space of
    # the track." [Main p. 7] The Influence 4 band of each strip prints (the
    # board scan read against the rulebook icons, 2026-09-19): the Spy icon
    # (Emperor), a 3 on the Solari coin (Spacing Guild), an Intrigue card
    # (Bene Gesserit), a water drop (Fremen). The earlier transcription gave
    # the Emperor two troops and the Guild three water (docs/lessons.md).
    gained = {
        faction: gain_faction_influence(
            _at_three(faction), 0, faction, 1, event_prefix="test:influence"
        )
        for faction in Faction
    }
    before = _at_three(Faction.EMPEROR).players[0]

    guild = gained[Faction.SPACING_GUILD].state.players[0]
    assert guild.resources.solari == before.resources.solari + 3
    assert guild.resources.water == before.resources.water

    fremen = gained[Faction.FREMEN].state.players[0]
    assert fremen.resources.water == before.resources.water + 1

    sisterhood = gained[Faction.BENE_GESSERIT].state
    assert sisterhood.players[0].intrigue_cards == ("intrigue:ambush:1",)
    assert sisterhood.intrigue_deck == ("intrigue:bribery:1",)

    # The Emperor's Spy is a placement decision: it is queued for the engine
    # and recruits nothing.
    emperor = gained[Faction.EMPEROR].state
    assert emperor.pending_track_spies == ((0, "test:influence:track_bonus:0"),)
    assert emperor.players[0].troops_garrison == before.troops_garrison
    assert emperor.players[0].spies_supply == before.spies_supply
    assert all(
        result.state.pending_track_spies == ()
        for faction, result in gained.items()
        if faction is not Faction.EMPEROR
    )

    for faction, result in gained.items():
        assert result.state.players[0].alliance_faction_ids == (faction.value,)
        bonus = next(
            dict(event.payload)
            for event in result.events
            if event.kind == "influence_track_bonus_gained"
        )
        assert bonus["faction"] == faction.value
    payloads = {
        faction: {
            key: value
            for event in result.events
            if event.kind == "influence_track_bonus_gained"
            for key, value in event.payload
            if key not in ("faction", "player")
        }
        for faction, result in gained.items()
    }
    assert payloads == {
        Faction.EMPEROR: {"spy": 1},
        Faction.SPACING_GUILD: {"solari": 3},
        Faction.BENE_GESSERIT: {"intrigue": 1},
        Faction.FREMEN: {"water": 1},
    }


def test_reaching_four_again_after_a_drop_pays_the_track_bonus_again() -> None:
    # "4 아래로 내려가도 보너스를 반환하지 않으며, 다시 4에 도달하면 같은
    # 보너스를 다시 받을 수 있다." [Main pp. 4, 7 board artwork]
    # (docs/rules/uprising-systems.md). The Alliance is lost at 3 and taken
    # back at 4, but the bonus is paid on every reach, not once a game.
    reached = gain_faction_influence(
        _at_three(Faction.SPACING_GUILD),
        0,
        Faction.SPACING_GUILD,
        1,
        event_prefix="test:reach",
    )
    dropped = lose_faction_influence(
        reached.state, 0, Faction.SPACING_GUILD, 1, event_prefix="test:drop"
    )
    kept = dropped.state.players[0]
    assert kept.alliance_faction_ids == ()
    assert kept.resources.solari == 3

    again = gain_faction_influence(
        dropped.state, 0, Faction.SPACING_GUILD, 1, event_prefix="test:again"
    )

    player = again.state.players[0]
    assert player.resources.solari == 6
    assert player.alliance_faction_ids == (Faction.SPACING_GUILD.value,)
    assert [e.kind for e in again.events].count("influence_track_bonus_gained") == 1


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
