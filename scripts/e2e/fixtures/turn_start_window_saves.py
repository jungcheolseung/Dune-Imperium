"""Save one real game at a turn start that offers both turn-start cards.

"At the start of your turn" [Litany Against Fear card] [Withdrawn card]: the
page asks for such a play first and alone (static/turn.js, user decision
2026-10-14), so turn_start_window.py needs a seat whose turn opens with both
plays legal, a Plot it may play instead (a first other action, after which
the plays are greyed out), and that seat's next turn opening with them
again.

Four human seats, Bloodlines and the Leader draft on (Withdrawn is a Twisted
Intrigue card, dealt to Piter De Vries, whom the draft can seat); every seat
plays ``random.Random(SEED).choice`` over its legal actions but never a
turn-start play, and every hold is confirmed at once. Seed 185 is the first
of 0-199 whose walk meets such a turn start: seat 2 in round 6, holding
Litany Against Fear and Withdrawn, with a Plot that leaves it on its turn
frame. The walk saves there, plays that Plot, goes on, and records every
step up to seat 2's next turn start (both plays legal again), so the page
can replay them and must open the window once more.

Prints {"turn-start": {save_id, seat, round, revision, plays, plot, steps,
next_revision, next_plays}} as JSON. ``plays`` and ``next_plays`` are the
turn-start rows as the server lists them ({index, action_id, card_id,
option}); ``plot`` is {index, card_id, undoable}; each step is
["action", seat, index] or ["confirm", seat].
"""

import json
import random
import sys
from pathlib import Path

from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.intrigue import plays_turn_start_option
from dune_imperium.server.persistence import SaveStore
from dune_imperium.server.sessions import GameSessionManager

SEATS = ("human", "human", "human", "human")
SEED = 185
STEPS = 6_000

store = SaveStore(Path(sys.argv[1]))


def turn_start(action) -> bool:
    return action.action_id == "play_turn_start_card" or plays_turn_start_option(
        action
    )


def rows_of(manager, game_id, seat) -> list[dict]:
    return manager.legal_actions(game_id, seat)["actions"]


def plays_of(rows) -> list[dict]:
    return [
        {
            "index": row["index"],
            "action_id": row["action_id"],
            "card_id": row["arguments"]["card_id"],
            "option": row["arguments"].get("option"),
        }
        for row in rows
        if row.get("turn_start") is True
    ]


def back_to_turn(engine, state, seat, action) -> bool:
    """Whether the Plot leaves the seat on its own turn frame at once."""

    after = engine.apply(state, action).state
    top = after.decision_stack[-1] if after.decision_stack else None
    return (
        top is not None
        and top.kind == FrameKind.TURN
        and top.decision.owner == seat
    )


manager = GameSessionManager()
summary = manager.create_game(SEATS, game_seed=SEED, bloodlines=True, leader_draft=True)
game_id = str(summary["game_id"])
session = manager._get(game_id)
rng = random.Random(SEED)
found: dict | None = None
steps: list[list] = []
for _step in range(STEPS):
    if summary["finished"]:
        break
    held = summary["confirmation"]
    if isinstance(held, int):
        if found is not None:
            steps.append(["confirm", held])
        summary = manager.confirm_turn(game_id, held, summary["revision"])
        continue
    owner = summary["decision"]["owner"]
    actions = session.engine.legal_actions(session.state, owner)
    starts = {a.action_id for a in actions if turn_start(a)}
    if found is not None and owner == found["seat"] and starts:
        if summary["revision"] != found["revision"]:
            found["steps"] = steps
            found["next_revision"] = summary["revision"]
            found["next_plays"] = plays_of(rows_of(manager, game_id, owner))
            break
    if found is None and starts == {"play_turn_start_card", "play_intrigue"}:
        plots = [
            index
            for index, action in enumerate(actions)
            if action.action_id == "play_intrigue"
            and not turn_start(action)
            and back_to_turn(session.engine, session.state, owner, action)
        ]
        if plots:
            rows = rows_of(manager, game_id, owner)
            plot = rows[plots[0]]
            document = manager.save_game(game_id, name="turn-start")
            found = {
                "save_id": store.write(document)["save_id"],
                "seat": owner,
                "round": summary["round_number"],
                "revision": summary["revision"],
                "plays": plays_of(rows),
                "plot": {
                    "index": plot["index"],
                    "card_id": plot["arguments"]["card_id"],
                    "undoable": plot["undoable"],
                },
            }
            summary = manager.apply_action(
                game_id, owner, summary["revision"], plots[0]
            )
            continue
    choices = [index for index, action in enumerate(actions) if not turn_start(action)]
    index = rng.choice(choices) if choices else 0
    if found is not None:
        steps.append(["action", owner, index])
    summary = manager.apply_action(game_id, owner, summary["revision"], index)

if found is None or "next_revision" not in found:
    raise RuntimeError(f"Seed {SEED} no longer reaches both turn starts ({found})")
print(json.dumps({"turn-start": found}))
