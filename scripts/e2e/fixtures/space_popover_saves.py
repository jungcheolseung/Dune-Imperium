"""Save a real game where a board space's popover has live state to show.

Seat 0 is human and the others play the registry-pinned table heuristic.
Seat 0 plays ``random.Random(seed).choice`` over its legal actions and every
hold is confirmed at once (the walk of fixtures/held_choice_saves.py), base
game, no edited state. The game is saved at seat 0's first turn choice once

- some player has their Swordmaster, so the Swordmaster space costs 6
  Solari, not 8 [Board Guide p. 2], and
- bonus spice lies on Hagga Basin (Makers phase [Main p. 15]).

Prints {"space-popover": save_id} as JSON.
"""

import json
import random
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
SEEDS = range(8)

store = SaveStore(Path(sys.argv[1]))
found: dict[str, str] = {}


def ready(session) -> bool:
    state = session.state
    bonus = dict(state.maker_bonus_spice)
    return (
        any(player.swordmaster_acquired for player in state.players)
        and bonus.get("hagga_basin", 0) >= 1
    )


for seed in SEEDS:
    manager = GameSessionManager()
    summary = manager.create_game(SEATS, game_seed=seed)
    gid = summary["game_id"]
    session = manager._get(gid)
    rng = random.Random(seed)
    for _step in range(STEPS):
        while isinstance(summary["confirmation"], int) and not summary["finished"]:
            summary = manager.confirm_turn(
                gid, summary["confirmation"], summary["revision"]
            )
        if summary["finished"]:
            break
        assert summary["decision"]["owner"] == 0, summary["decision"]
        if summary["decision"]["kind"] == "turn" and ready(session):
            found["space-popover"] = store.write(
                manager.save_game(gid, name="space-popover")
            )["save_id"]
            break
        actions = manager.legal_actions(gid, 0)["actions"]
        choice = rng.choice(actions)
        summary = manager.apply_action(gid, 0, summary["revision"], choice["index"])
    if found:
        break

if not found:
    raise RuntimeError("no game reached a Swordmaster with bonus spice on Hagga Basin")
print(json.dumps(found))
