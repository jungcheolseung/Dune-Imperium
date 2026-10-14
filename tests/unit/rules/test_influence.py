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


def _faction_race(faction: Faction, holder: int, *rivals: int) -> GameState:
    """Seat 0 holds ``faction``'s Alliance at ``holder`` Influence; the rivals
    sit in seats 1.. at the given Influence."""

    base = tuple(PlayerState(player_id=seat) for seat in range(4))
    seats = [
        replace(
            base[0],
            influence=Influence(**{faction.value: holder}),
            alliance_faction_ids=(faction.value,),
            victory_points=2,
        )
    ]
    for seat, amount in enumerate(rivals, start=1):
        seats.append(
            replace(
                base[seat],
                influence=Influence(**{faction.value: amount}),
                victory_points=1,
            )
        )
    seats.extend(base[len(seats) :])
    return GameState(config=RulesetConfig(), seed=1, players=tuple(seats))


def test_a_multi_space_loss_is_resolved_one_space_at_a_time() -> None:
    # OQ-014 (reinforced 2026-10-07): "Guild 6인 보유자가 5인 상대를 두고
    # 2를 잃으면(Opportunism, For Humanity) 4로 끝나 token을 지킨다. 한 칸씩
    # 읽으면 6→5에서 동률이 되고 5→4에서 상대가 token을 가져간다. 엔진은
    # 한 칸씩 처리하며 ... 이 읽기를 유지한다." The FAQ rule it applies to
    # each space: "You were previously tied for Influence with another player;
    # the player you were tied with now takes the Alliance token."
    # [FAQ p. 1] (reading the loss one space at a time is a project
    # convention, not an official rule).
    state = _faction_race(Faction.SPACING_GUILD, 6, 5)

    result = lose_faction_influence(
        state, 0, Faction.SPACING_GUILD, 2, event_prefix="test:loss"
    )

    holder, rival = result.state.players[:2]
    assert holder.influence.spacing_guild == 4
    # Read as one loss the holder would still hold the token at 4; the second
    # space starts from the 5-5 tie, so the rival takes it.
    assert holder.alliance_faction_ids == ()
    assert holder.victory_points == 1
    assert rival.influence.spacing_guild == 5
    assert rival.alliance_faction_ids == (Faction.SPACING_GUILD.value,)
    assert rival.victory_points == 2
    assert [(event.event_id, event.kind) for event in result.events] == [
        ("test:loss:influence", "influence_lost"),
        ("test:loss:alliance:1", "alliance_transferred"),
    ]
    assert dict(result.events[0].payload)["amount"] == 2
    assert dict(result.events[1].payload) == {
        "faction": Faction.SPACING_GUILD.value,
        "from_player": 0,
        "to_player": 1,
    }

    # The loss is exactly two single-space losses in a row, and after the
    # first the holder has reached the tie but still holds the token.
    first = lose_faction_influence(
        state, 0, Faction.SPACING_GUILD, 1, event_prefix="test:one"
    )
    assert first.state.players[0].influence.spacing_guild == 5
    assert first.state.players[0].alliance_faction_ids == (
        Faction.SPACING_GUILD.value,
    )
    assert [event.kind for event in first.events] == ["influence_lost"]
    second = lose_faction_influence(
        first.state, 0, Faction.SPACING_GUILD, 1, event_prefix="test:two"
    )
    assert second.state.players == result.state.players


def test_a_multi_space_loss_that_ends_tied_does_not_hand_the_alliance_over() -> None:
    # The same one-space reading (OQ-014): the FAQ's "previously tied" is
    # judged before each space, so landing on the rival's Influence at the
    # end of the loss is not a transfer [FAQ p. 1]. A Guild holder on 6 with a
    # rival on 4 loses 2: 6→5 has no tie behind it and 5→4 still has none, so
    # the holder keeps the token at 4 (above "fallen to 3 Influence or
    # lower" [FAQ p. 1]); only the next loss, starting from the tie, passes it.
    state = _faction_race(Faction.SPACING_GUILD, 6, 4)

    result = lose_faction_influence(
        state, 0, Faction.SPACING_GUILD, 2, event_prefix="test:loss"
    )

    holder, rival = result.state.players[:2]
    assert holder.influence.spacing_guild == 4
    assert holder.alliance_faction_ids == (Faction.SPACING_GUILD.value,)
    assert holder.victory_points == 2
    assert rival.alliance_faction_ids == ()
    assert [event.kind for event in result.events] == ["influence_lost"]

    next_loss = lose_faction_influence(
        result.state, 0, Faction.SPACING_GUILD, 1, event_prefix="test:next"
    )
    assert next_loss.state.players[1].alliance_faction_ids == (
        Faction.SPACING_GUILD.value,
    )


def test_a_multi_space_loss_returns_the_token_and_then_the_friendship_vp() -> None:
    # OQ-014's one-space reading applied to the other FAQ case: "If you have
    # fallen to 3 Influence or lower." [FAQ p. 1] The token goes back to the
    # board in the space that reaches 3 (nobody else has 4) and the
    # friendship Victory Point goes in the later space that falls below 2
    # [Main pp. 7, 17] -- each exactly once, in its own space.
    state = _faction_race(Faction.FREMEN, 4)
    assert state.players[0].victory_points == 2

    result = lose_faction_influence(
        state, 0, Faction.FREMEN, 3, event_prefix="test:loss"
    )

    holder = result.state.players[0]
    assert holder.influence.fremen == 1
    assert holder.alliance_faction_ids == ()
    assert holder.victory_points == 0
    assert [(event.event_id, event.kind) for event in result.events] == [
        ("test:loss:influence", "influence_lost"),
        ("test:loss:alliance:0", "alliance_lost"),
    ]
    assert dict(result.events[0].payload)["amount"] == 3

    # Stopping at 2 loses the token but not yet the friendship point.
    stopped = lose_faction_influence(
        state, 0, Faction.FREMEN, 2, event_prefix="test:stop"
    ).state.players[0]
    assert stopped.influence.fremen == 2
    assert stopped.alliance_faction_ids == ()
    assert stopped.victory_points == 1


def test_a_multi_space_loss_never_picks_an_alliance_recipient_for_the_owner() -> None:
    # OQ-014 / uprising-systems.md: when the space about to be lost starts
    # tied with several players, "the player you were tied with now takes the
    # Alliance token" [FAQ p. 1] and, with more than one, "기존 보유자가 받을
    # 한 명을 정한다" (uprising-systems.md, Alliance) -- the engine must ask
    # instead of picking. A holder on 5 with two rivals on 4 keeps the token
    # in the first space (nobody is tied at 5, and 4 is not "3 or lower");
    # the second space starts from a three-way tie, so the whole two-space
    # call refuses to choose for the owner, and the caller walks the spaces
    # one at a time, naming the recipient on the space that needs one.
    state = _faction_race(Faction.BENE_GESSERIT, 5, 4, 4)
    with pytest.raises(ValueError, match="requires an Alliance recipient"):
        lose_faction_influence(
            state, 0, Faction.BENE_GESSERIT, 2, event_prefix="test:loss"
        )
    with pytest.raises(ValueError, match="one-step loss"):
        lose_faction_influence(
            state,
            0,
            Faction.BENE_GESSERIT,
            2,
            event_prefix="test:loss",
            alliance_recipient=2,
        )

    first = lose_faction_influence(
        state, 0, Faction.BENE_GESSERIT, 1, event_prefix="test:one"
    ).state
    assert first.players[0].influence.bene_gesserit == 4
    assert first.players[0].alliance_faction_ids == (Faction.BENE_GESSERIT.value,)
    assert alliance_recipients_after_influence_loss(
        first, 0, Faction.BENE_GESSERIT
    ) == (1, 2)

    second = lose_faction_influence(
        first,
        0,
        Faction.BENE_GESSERIT,
        1,
        event_prefix="test:two",
        alliance_recipient=2,
    ).state
    assert second.players[0].influence.bene_gesserit == 3
    assert second.players[0].alliance_faction_ids == ()
    assert second.players[1].alliance_faction_ids == ()
    assert second.players[2].alliance_faction_ids == (Faction.BENE_GESSERIT.value,)
    assert second.players[2].victory_points == 2
