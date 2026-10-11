"""Save a real game at a grafted Agent turn offering both cards' boxes.

Plan stage 4 (docs/graft-boxes-plan.md 4.11): a grafted Agent turn offers
both cards' Agent boxes from the start (codec v143), and the decision panel
sets each box's rows under a header naming its card. The save rests on the
turn owner's decision right where both boxes offer rows, and one of its
rows starts a bundled selection (a "Choose two" first pick, an arrow's
cost; plan 4.3) that holds the other box back, so the e2e can show the
held box's header with its note.

Four human seats, Immortality on, Leader draft off; every seat plays
``random.Random(seed).randrange`` over its engine legal actions and every
hold is confirmed at once (the walk of turn_card_trash_saves.py). The seeds
are tried in order, so a rule change that moves a game only moves the case
to a later seed; seed 4 reaches Long Reach grafted to Planned Coupling in
round 10 when this was written.

The expectations are read off the engine and the display helpers here
(``agent_box_headers``, ``agent_box_of_rows``), the same ones the server
serializes; the script checks the page against the payload it is served.

Prints {"graft-boxes": {save_id, seed, seat, boxes, box_one_index,
lock_index, locked_box}} as JSON: ``boxes`` is the headers (box, card_id,
name, name_ko); ``box_one_index`` a box 1 row that holds nothing back;
``lock_index`` the row that holds ``locked_box`` back.
"""

import json
import random
import sys
from pathlib import Path

from dune_imperium.display.actions import agent_box_headers, agent_box_of_rows
from dune_imperium.server.persistence import SaveStore
from dune_imperium.server.sessions import GameSessionManager

SEATS = ("human", "human", "human", "human")
SEEDS = range(0, 40)
STEPS = 6_000
NAME = "graft-boxes"

store = SaveStore(Path(sys.argv[1]))


def locked_after(engine, state, owner, action) -> int | None:
    """The box ``action`` holds back once taken, if it does."""

    result = engine.apply(state, action).state
    headers = agent_box_headers(result, owner) or []
    return next((entry["box"] for entry in headers if entry["locked"]), None)


def graft_case(engine, state, owner) -> dict[str, object] | None:
    headers = agent_box_headers(state, owner)
    if not headers or len(headers) != 2 or any(e["locked"] for e in headers):
        return None
    actions = engine.legal_actions(state, owner)
    boxes = agent_box_of_rows(state, owner, actions)
    if 0 not in boxes or 1 not in boxes:
        return None
    lock_index = locked_box = box_one_index = None
    for index, (action, box) in enumerate(zip(actions, boxes, strict=True)):
        if box is None:
            continue
        held = locked_after(engine, state, owner, action)
        if held is not None and lock_index is None:
            lock_index, locked_box = index, held
        if held is None and box == 1 and box_one_index is None:
            box_one_index = index
    if lock_index is None or box_one_index is None:
        return None
    return {
        "seat": owner,
        "boxes": [
            {key: entry[key] for key in ("box", "card_id", "name", "name_ko")}
            for entry in headers
        ],
        "box_one_index": box_one_index,
        "lock_index": lock_index,
        "locked_box": locked_box,
    }


def walk(seed: int) -> dict[str, object] | None:
    manager = GameSessionManager()
    summary = manager.create_game(
        SEATS, game_seed=seed, immortality=True, leader_draft=False
    )
    gid = str(summary["game_id"])
    session = manager._get(gid)
    rng = random.Random(seed)
    for _step in range(STEPS):
        if summary["finished"]:
            return None
        held = summary["confirmation"]
        if isinstance(held, int):
            summary = manager.confirm_turn(gid, held, summary["revision"])
            continue
        owner = summary["decision"]["owner"]
        actions = session.engine.legal_actions(session.state, owner)
        case = graft_case(session.engine, session.state, owner)
        if case is not None:
            saved = store.write(manager.save_game(gid, name=NAME))
            return {"save_id": saved["save_id"], "seed": seed, **case}
        summary = manager.apply_action(
            gid, owner, summary["revision"], rng.randrange(len(actions))
        )
    return None


for seed in SEEDS:
    found = walk(seed)
    if found is not None:
        print(json.dumps({NAME: found}))
        sys.exit(0)
raise RuntimeError(f"no grafted turn with a bundled selection in seeds {SEEDS}")
