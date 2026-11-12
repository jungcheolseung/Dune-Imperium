"""A play server holding two tables for scripts/e2e/guild_accord.py.

Guild Accord's Heighliner cut as a graft partner and Ghola's copy of it
(stage P7g, OQ-158) need three cards in one hand at once, which no searched
game reaches. So this server builds the table itself, as
tests/server/test_guild_accord_placements.py does: an original + Rise of Ix +
Immortality game (four human seats, seed 3, Player 1 first) is given, in its
opening state, Guild Accord, Ghola and Usurp in seat 0's hand and 6 spice --
the one change made outside the rules -- and played through its setup to
seat 0's first turn. The server's undo replays the steps from the engine's
``reset``, so each game's own engine returns that edited opening there and an
undo keeps the three cards. It makes ``--games`` such games (default 4) and
prints ``READY <game id> ...`` once it listens.

Run with the project's interpreter from the repository root:
``python scripts/e2e/fixtures/guild_accord_table.py --port N --saves-dir D``.
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import uvicorn

from dune_imperium.server.app import create_app
from dune_imperium.server.sessions import GameSessionManager

GUILD_ACCORD = "imperium:guild_accord:0"
GHOLA = "tleilaxu:ghola:0"
USURP = "tleilaxu:usurp:0"
HAND = (GUILD_ACCORD, GHOLA, USURP)


def guild_accord_game(manager: GameSessionManager) -> str:
    """Seat 0's first turn with the three cards in hand and 6 spice."""

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
    moved = set(HAND)
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
        hand=(*owner.hand, *HAND),
        resources=replace(owner.resources, spice=6),
    )
    opening = replace(state, players=(seat, *state.players[1:]))
    session.state = opening
    # This game's engine is its own (``create_game``).
    session.engine.reset = lambda config, seed: opening
    for _ in range(10):
        if summary["phase"] == "player_turns":
            break
        acting = summary["decision"]["owner"]
        listed: Any = manager.legal_actions(game_id, acting)
        summary = manager.apply_action(
            game_id,
            acting,
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
    return game_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--saves-dir", type=Path, required=True)
    parser.add_argument("--games", type=int, default=4)
    arguments = parser.parse_args()
    manager = GameSessionManager()
    games = [guild_accord_game(manager) for _ in range(arguments.games)]
    # The private pictures, as scripts/e2e/common.py's servers show them
    # (the play server's default is its own since 2026-11-11):
    # guild_accord.py's check [0] holds back the card's app picture.
    app = create_app(manager=manager, saves_dir=arguments.saves_dir, pictures="assets")
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=arguments.port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", arguments.port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.1)
    print("READY", *games, flush=True)
    try:
        thread.join()
    except KeyboardInterrupt:
        server.should_exit = True
    return 0


if __name__ == "__main__":
    sys.exit(main())
