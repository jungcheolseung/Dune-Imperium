"""Guild Accord's Heighliner cut as a graft partner, as the play server lists
it for the staged Agent turn (stage P7g, OQ-158).

"Both played cards are considered to have “sent” the Agent, no matter which
card’s icon you use." [Immortality p. 10]: Guild Accord's cut reaches the
graft whose partner it is, and Ghola, which "copies the entire Agent box"
[Immortality p. 14], copies it (OQ-158). The cost is paid as the Agent goes
and the partner is chosen next, so a graft placement on the Heighliner
promises its partner's cut (``partner_discount``) and the partner choice
keeps only the cards that give exactly that much. The server names each such
placement's partners (``graft_partners``, from its dry run) so the page can
say what the placement promises; scripts/e2e/guild_accord.py plays the same
table in the browser (its fixture builds it the same way).

An original + Rise of Ix + Immortality game is given, in its opening state,
Guild Accord, Ghola and Usurp in seat 0's hand and 6 spice -- the one change
made outside the rules -- and played to seat 0's first turn. The server's
undo rebuilds a state by replaying the steps from the engine's ``reset``
(``sessions._state_after``), so that game's ``reset`` returns the edited
opening (as tests/server/test_undo.py's ``_replay_from`` does) and an undo
keeps the three cards.
"""

import json
from dataclasses import replace
from typing import Any

import pytest

from dune_imperium.server.sessions import GameSessionManager

GUILD_ACCORD = "imperium:guild_accord:0"
GHOLA = "tleilaxu:ghola:0"
USURP = "tleilaxu:usurp:0"
HEIGHLINER = "imperium_heighliner"


def _table(monkeypatch: pytest.MonkeyPatch) -> tuple[GameSessionManager, str]:
    manager = GameSessionManager()
    summary: Any = manager.create_game(
        ("human",) * 4,
        base_game="imperium",
        rise_of_ix=True,
        immortality=True,
        game_seed=3,
        first_player_seat_zero=True,
    )
    game_id = str(summary["game_id"])
    session = manager._sessions[game_id]
    assert not session.steps
    state = session.state
    moved = {GUILD_ACCORD, GHOLA, USURP}
    state = replace(
        state,
        imperium_row=tuple(card for card in state.imperium_row if card not in moved),
        imperium_deck=tuple(card for card in state.imperium_deck if card not in moved),
        tleilaxu_row=tuple(card for card in state.tleilaxu_row if card not in moved),
        tleilaxu_deck=tuple(card for card in state.tleilaxu_deck if card not in moved),
    )
    owner = state.players[0]
    seat = replace(
        owner,
        hand=(*owner.hand, GUILD_ACCORD, GHOLA, USURP),
        resources=replace(owner.resources, spice=6),
    )
    opening = replace(state, players=(seat, *state.players[1:]))
    session.state = opening
    monkeypatch.setattr(session.engine, "reset", lambda config, seed: opening)
    for _ in range(10):
        if summary["phase"] == "player_turns":
            break
        seat_index = summary["decision"]["owner"]
        listed: Any = manager.legal_actions(game_id, seat_index)
        summary = manager.apply_action(
            game_id,
            seat_index,
            summary["revision"],
            listed["actions"][0]["index"],
            undo_count=summary["undo_count"],
        )
        if summary["confirmation"] is not None:
            summary = manager.confirm_turn(
                game_id,
                summary["confirmation"],
                summary["revision"],
                undo_count=summary["undo_count"],
            )
    assert summary["phase"] == "player_turns"
    players = session.state.players
    assert {GUILD_ACCORD, GHOLA, USURP} <= set(players[0].hand)
    assert players[0].resources.spice == 6
    return manager, game_id


def _heighliner(listed: Any) -> list[dict[str, Any]]:
    return [
        entry
        for entry in listed["agent_placements"]
        if entry["arguments"]["card_id"] == GUILD_ACCORD
        and entry["arguments"]["space_id"] == HEIGHLINER
    ]


def test_each_heighliner_graft_placement_names_its_partners(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, game_id = _table(monkeypatch)
    listed: Any = manager.legal_actions(game_id, 0)
    json.dumps(listed)
    by_promise = {
        (
            entry["arguments"].get("graft", False),
            entry["arguments"].get("partner_discount", 0),
        ): entry
        for entry in _heighliner(listed)
    }
    assert set(by_promise) == {(False, 0), (True, 0), (True, 2)}
    # Alone: no partner to name.
    assert "graft_partners" not in by_promise[False, 0]
    # Grafted with no promise, only a partner that cuts nothing (Usurp);
    # with 2 promised, only Ghola, which copies Guild Accord's cut.
    assert by_promise[True, 0]["graft_partners"] == [USURP]
    assert by_promise[True, 2]["graft_partners"] == [GHOLA]
    # No other space's placement names partners.
    assert not any(
        "graft_partners" in entry
        for entry in listed["agent_placements"]
        if entry["arguments"]["space_id"] != HEIGHLINER
    )


def test_the_promised_placement_offers_ghola_alone_and_pays_two(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, game_id = _table(monkeypatch)
    listed: Any = manager.legal_actions(game_id, 0)
    (promised,) = [
        entry
        for entry in _heighliner(listed)
        if entry["arguments"].get("partner_discount") == 2
    ]
    summary: Any = manager.snapshot(game_id, 0)["summary"]
    summary = manager.apply_action(
        game_id,
        0,
        summary["revision"],
        promised["index"],
        undo_count=summary["undo_count"],
    )
    spaces: Any = manager.legal_actions(game_id, 0)
    # The space pick names neither the card nor the graft (the card pick did).
    wanted = {
        key: value
        for key, value in promised["arguments"].items()
        if key not in ("card_id", "graft")
    }
    (space_row,) = [
        row
        for row in spaces["actions"]
        if row["action_id"] == "place_agent"
        and {key: value for key, value in row["arguments"].items()} == wanted
    ]
    summary = manager.apply_action(
        game_id,
        0,
        summary["revision"],
        space_row["index"],
        undo_count=summary["undo_count"],
    )
    partners: Any = manager.legal_actions(game_id, 0)
    offered = [
        row["arguments"]["card_id"]
        for row in partners["actions"]
        if row["action_id"] == "choose_graft_partner"
    ]
    assert offered == [GHOLA]
    view: Any = manager.snapshot(game_id, 0)["view"]
    # The Heighliner's 6 spice less Guild Accord's own 2 and Ghola's copy of
    # them, 2 more: 2 paid of 6.
    assert view["players"][0]["resources"]["spice"] == 4


def _held_graft_pick(manager: GameSessionManager, game_id: str) -> Any:
    """Seat 0 picks Guild Accord grafted; the space pick waits."""

    listed: Any = manager.legal_actions(game_id, 0)
    (promised,) = [
        entry
        for entry in _heighliner(listed)
        if entry["arguments"].get("partner_discount") == 2
    ]
    summary: Any = manager.snapshot(game_id, 0)["summary"]
    return manager.apply_action(
        game_id,
        0,
        summary["revision"],
        promised["index"],
        undo_count=summary["undo_count"],
    )


def _space_partners(listed: Any) -> dict[int, Any]:
    """Each Heighliner space pick's partners, by the cut it promises."""

    return {
        row["arguments"].get("partner_discount", 0): row.get("graft_partners")
        for row in listed["actions"]
        if row["action_id"] == "place_agent"
        and row["arguments"]["space_id"] == HEIGHLINER
    }


def test_a_held_graft_pick_names_the_space_picks_partners(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The card pick made and the space pick waiting -- as a page reloaded
    # then finds it -- the server lists no placements, so the space picks
    # name their partners themselves, the seat's own rows only.
    manager, game_id = _table(monkeypatch)
    _held_graft_pick(manager, game_id)
    listed: Any = manager.legal_actions(game_id, 0)
    json.dumps(listed)
    assert listed["agent_placements"] is None
    assert _space_partners(listed) == {0: [USURP], 2: [GHOLA]}
    assert not any(
        "graft_partners" in row
        for row in listed["actions"]
        if row["arguments"].get("space_id") != HEIGHLINER
    )
    for seat in (1, 2, 3):
        other: Any = manager.legal_actions(game_id, seat)
        assert not any("graft_partners" in row for row in other["actions"])


def test_an_undone_space_pick_names_its_partners_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, game_id = _table(monkeypatch)
    summary: Any = _held_graft_pick(manager, game_id)
    spaces: Any = manager.legal_actions(game_id, 0)
    (unpromised,) = [
        row
        for row in spaces["actions"]
        if row["action_id"] == "place_agent"
        and row["arguments"]["space_id"] == HEIGHLINER
        and row["arguments"].get("partner_discount", 0) == 0
    ]
    summary = manager.apply_action(
        game_id,
        0,
        summary["revision"],
        unpromised["index"],
        undo_count=summary["undo_count"],
    )
    summary = manager.undo(
        game_id, 0, summary["revision"], undo_count=summary["undo_count"]
    )
    listed: Any = manager.legal_actions(game_id, 0)
    # Back at the space pick with Guild Accord still picked and grafted.
    assert listed["agent_placements"] is None
    assert _space_partners(listed) == {0: [USURP], 2: [GHOLA]}
    (promised,) = [
        row for row in listed["actions"] if row.get("graft_partners") == [GHOLA]
    ]
    summary = manager.apply_action(
        game_id,
        0,
        summary["revision"],
        promised["index"],
        undo_count=summary["undo_count"],
    )
    partners: Any = manager.legal_actions(game_id, 0)
    assert [
        row["arguments"]["card_id"]
        for row in partners["actions"]
        if row["action_id"] == "choose_graft_partner"
    ] == [GHOLA]
    view: Any = manager.snapshot(game_id, 0)["view"]
    assert view["players"][0]["resources"]["spice"] == 4
