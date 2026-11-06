"""Kwisatz Haderach's placements with a graft card in hand, as the play
server lists them for the staged Agent turn (stage P7b of
docs/base-game-and-ix-plan.md).

Kwisatz Haderach sends an Agent "from anywhere" (OQ-139: one not sent yet or
one of the seat's Agents on the board), and on a table with Immortality it
can be grafted (5cef372f): "When grafted to Kwisatz Haderach, you still send
only one Agent on your turn" [FAQ p. 2]. So one space takes it four ways,
which the page's chooser must tell apart (``turn.js``
``placementOptionNode``); ``scripts/e2e/imperium_game.py`` step [8] renders
these very placements.

An original + Immortality game is played to seat 0's first turn, and seat 0
is given Kwisatz Haderach and Ghola in hand and an Agent on Carthag -- the
one change made outside the rules.
"""

import json
from dataclasses import replace
from typing import Any

from dune_imperium.server.sessions import GameSessionManager

KWISATZ = "imperium:kwisatz_haderach:0"
GHOLA = "tleilaxu:ghola:0"
# What the e2e step renders (its KWISATZ_PLACEMENTS): Wealth taken alone or
# grafted, by an Agent not sent yet or the one on Carthag.
WEALTH = [
    {"card_id": KWISATZ, "space_id": "wealth"},
    {"card_id": KWISATZ, "from_space": "carthag", "space_id": "wealth"},
    {"card_id": KWISATZ, "graft": True, "space_id": "wealth"},
    {"card_id": KWISATZ, "from_space": "carthag", "graft": True, "space_id": "wealth"},
]


def _kwisatz_turn() -> tuple[GameSessionManager, str]:
    manager = GameSessionManager()
    summary: Any = manager.create_game(
        ("human",) * 4,
        base_game="imperium",
        immortality=True,
        game_seed=3,
        first_player_seat_zero=True,
    )
    game_id = str(summary["game_id"])
    # Seat 3's Baron Harkonnen chooses his two Factions before round 1.
    for faction in ("emperor", "fremen"):
        listed: Any = manager.legal_actions(game_id, 3)
        row = next(
            row for row in listed["actions"] if row["arguments"] == {"faction": faction}
        )
        summary = manager.apply_action(
            game_id,
            3,
            summary["revision"],
            row["index"],
            undo_count=summary["undo_count"],
        )
        if summary["confirmation"] is not None:
            summary = manager.confirm_turn(
                game_id,
                summary["confirmation"],
                summary["revision"],
                undo_count=summary["undo_count"],
            )
    session = manager._sessions[game_id]
    state = session.state
    assert state.players[0].agent_locations == ()
    state = replace(
        state,
        imperium_row=tuple(card for card in state.imperium_row if card != KWISATZ),
        imperium_deck=tuple(card for card in state.imperium_deck if card != KWISATZ),
        tleilaxu_row=tuple(card for card in state.tleilaxu_row if card != GHOLA),
        tleilaxu_deck=tuple(card for card in state.tleilaxu_deck if card != GHOLA),
    )
    owner = state.players[0]
    seat = replace(
        owner,
        hand=(*owner.hand, KWISATZ, GHOLA),
        agent_locations=("carthag",),
        agents_available=owner.agents_available - 1,
    )
    session.state = replace(state, players=(seat, *state.players[1:]))
    return manager, game_id


def test_one_space_takes_kwisatz_haderach_four_ways() -> None:
    manager, game_id = _kwisatz_turn()
    listed: Any = manager.legal_actions(game_id, 0)
    json.dumps(listed)
    rows = listed["actions"]
    placements = listed["agent_placements"]
    wealth = [
        entry
        for entry in placements
        if entry["arguments"]["card_id"] == KWISATZ
        and entry["arguments"]["space_id"] == "wealth"
    ]
    assert [entry["arguments"] for entry in wealth] == WEALTH
    # Each comes from the card pick of its kind: alone, or grafted.
    picks = [rows[entry["index"]] for entry in wealth]
    assert [pick["action_id"] for pick in picks] == ["choose_agent_card"] * 4
    assert [pick["arguments"] for pick in picks] == [
        {"card_id": KWISATZ},
        {"card_id": KWISATZ},
        {"card_id": KWISATZ, "graft": True},
        {"card_id": KWISATZ, "graft": True},
    ]
