"""Save one finished game that had a human seat, for its final clocks.

Seat 0 is human and confirms every hold or takes its first legal action; the
others play the registry-pinned table heuristic (base game, seed 4). A game
of AI seats only shows no play clock (a watched game), so endgame.py loads
this one to see the frozen totals under the standings (static/clock.js).
The saved clock is set to fixed totals (``CLOCK``) so the page's text can be
checked exactly: the clock is display only, and a load takes it as written.

Prints {"finished": save_id} as JSON.
"""

import json
import sys
from pathlib import Path

from dune_imperium.server.persistence import SaveStore
from dune_imperium.server.sessions import GameSessionManager

SEATS = (
    "human",
    "heuristic_uprising_table",
    "heuristic_uprising_table",
    "heuristic_uprising_table",
)
STEPS = 40_000
CLOCK = {"elapsed_ms": 3_725_000, "seat_ms": [1_234_000, 61_000, 5_500, 999], "known": True}

store = SaveStore(Path(sys.argv[1]))
manager = GameSessionManager()
summary = manager.create_game(SEATS, game_seed=4)
game_id = summary["game_id"]
for _step in range(STEPS):
    if summary["finished"]:
        break
    if isinstance(summary["confirmation"], int):
        summary = manager.confirm_turn(game_id, 0, summary["revision"])
    else:
        summary = manager.apply_action(game_id, 0, summary["revision"], 0)
assert summary["finished"], "the game did not finish"
document = manager.save_game(game_id, name="finished")
document["clock"] = CLOCK
found = {"finished": store.write(document)["save_id"]}
print(json.dumps(found))
