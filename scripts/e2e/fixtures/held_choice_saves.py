"""Save three real games at a seat-0 choice outside its turns.

Seat 0 is human and the others play the registry-pinned table heuristic.
Seat 0 plays ``random.Random(seed).choice`` over its legal actions and every
hold is confirmed at once: the walk of tests/server/test_round_start_defense.py
and tests/server/test_turn_end.py (``_walk_to_held_end_before_chance``), base
game, no edited state.

- ``held-spy-post`` (seed 0, round 4): a Conflict reward Spy whose every post
  is marked ``sent_by_turn_end`` (the next round opens without a reshuffle,
  so the step runs straight into the next Conflict reveal and draw);
- ``held-defense`` (seed 0, round 7, the same walk): seat 0's Control
  defense in Round Start, both answers marked ``sent_by_turn_end``;
- ``held-reward-spy`` (seed 19, round 4): a Conflict reward Spy whose posts
  can be taken back, saved right before seat 0 places it; placing it holds
  the seat's unit end before the next round's reshuffle (a chance outcome).

Prints {name: save_id} as JSON.
"""

import json
import random
import sys
from pathlib import Path

from dune_imperium.core import ChanceDecision
from dune_imperium.server.persistence import SaveStore
from dune_imperium.server.sessions import GameSessionManager

SEATS = (
    "human",
    "heuristic_uprising_table",
    "heuristic_uprising_table",
    "heuristic_uprising_table",
)
SPY_POST = "place_combat_reward_spy"
STEPS = 40_000

store = SaveStore(Path(sys.argv[1]))
found: dict[str, str] = {}


def start(seed: int):
    manager = GameSessionManager()
    summary = manager.create_game(SEATS, game_seed=seed)
    return manager, summary["game_id"], summary, random.Random(seed)


def seat_0_decision(manager, gid, summary):
    """Confirm every hold; return the summary at seat 0's next decision."""

    while isinstance(summary["confirmation"], int) and not summary["finished"]:
        seat = summary["confirmation"]
        summary = manager.confirm_turn(gid, seat, summary["revision"])
    if not summary["finished"]:
        assert summary["decision"]["owner"] == 0, summary["decision"]
    return summary


# Seed 0: the reward Spy sent with the press, then the Control defense.
manager, gid, summary, rng = start(0)
for _step in range(STEPS):
    summary = seat_0_decision(manager, gid, summary)
    if summary["finished"]:
        break
    kind = summary["decision"]["kind"]
    actions = manager.legal_actions(gid, 0)["actions"]
    posts = [a for a in actions if a["action_id"] == SPY_POST]
    if (
        "held-spy-post" not in found
        and kind == "combat_reward_spy"
        and posts
        and all(a["sent_by_turn_end"] for a in posts)
    ):
        found["held-spy-post"] = store.write(
            manager.save_game(gid, name="held-spy-post")
        )["save_id"]
    if kind == "control_defense":
        if len(actions) == 2 and all(a["sent_by_turn_end"] for a in actions):
            found["held-defense"] = store.write(
                manager.save_game(gid, name="held-defense")
            )["save_id"]
        break
    choice = rng.choice(actions)
    summary = manager.apply_action(gid, 0, summary["revision"], choice["index"])

# Seed 19: the reward Spy held before the next round's reshuffle. The game
# is saved before each candidate placement and kept once the policy's own
# placement left the hold before a chance outcome.
manager, gid, summary, rng = start(19)
session = manager._get(gid)
for _step in range(STEPS):
    summary = seat_0_decision(manager, gid, summary)
    if summary["finished"]:
        break
    actions = manager.legal_actions(gid, 0)["actions"]
    posts = [a for a in actions if a["action_id"] == SPY_POST]
    document = None
    if (
        summary["decision"]["kind"] == "combat_reward_spy"
        and posts
        and all(a["undoable"] and not a["sent_by_turn_end"] for a in posts)
    ):
        document = manager.save_game(gid, name="held-reward-spy")
    choice = rng.choice(actions)
    summary = manager.apply_action(gid, 0, summary["revision"], choice["index"])
    if (
        document is not None
        and choice["action_id"] == SPY_POST
        and summary["confirmation"] == 0
        and summary["decision"] is None
        and isinstance(session.engine.current_decision(session.state), ChanceDecision)
    ):
        found["held-reward-spy"] = store.write(document)["save_id"]
        break

missing = {"held-defense", "held-reward-spy", "held-spy-post"} - set(found)
if missing:
    raise RuntimeError(f"Could not find every fixture: {sorted(missing)} ({found})")
print(json.dumps(found))
