"""Save a real game where a seat holding Navigation Chamber picks a placement.

All four seats are human and their moves come from the heuristic, as in
fixtures/tech_acquire_saves.py, except that the first seat offered
Navigation Chamber buys it (a legal action, no edited state). The game is
saved at that seat's next turn choice once

- its legal set has the cut Spice Refinery trade (cost option 1 with the
  spice cut) next to the free option 0 for the same card, so the pick opens
  the chooser, and
- some card and space pair has exactly one placement and it carries a cut
  (a costed space, placed at once).

Navigation Chamber's cut is mandatory (OQ-104): "Board spaces cost you
[1 spice] or [1 Solari] less." [Tech tile face].

Prints {"navigation-chamber": save_id, "seat": seat} as JSON.
"""

import json
import sys
from collections import Counter
from pathlib import Path

from dune_imperium.agents import HeuristicAgent
from dune_imperium.server.persistence import SaveStore
from dune_imperium.server.sessions import GameSessionManager

store = SaveStore(Path(sys.argv[1]))


def ready(actions) -> bool:
    placements = [a for a in actions if a.action_id == "agent_turn"]
    refinery = {}
    for action in placements:
        arguments = dict(action.arguments)
        if arguments["space_id"] == "spice_refinery" and "graft" not in arguments:
            refinery.setdefault(arguments["card_id"], set()).add(
                (arguments.get("cost_option"), arguments.get("discount"))
            )
    if not any(options == {(0, None), (1, "spice")} for options in refinery.values()):
        return False
    pairs = Counter(
        (dict(a.arguments)["card_id"], dict(a.arguments)["space_id"])
        for a in placements
    )
    return any(
        pairs[(dict(a.arguments)["card_id"], dict(a.arguments)["space_id"])] == 1
        and dict(a.arguments).get("discount") is not None
        for a in placements
    )


for seed in range(40):
    manager = GameSessionManager()
    summary = manager.create_game(
        ("human",) * 4, bloodlines=True, tech_module=True, game_seed=seed
    )
    gid = summary["game_id"]
    agents = [HeuristicAgent(seed=20000 + seed * 4 + i) for i in range(4)]
    holder = None
    for _step in range(4000):
        if summary["finished"]:
            break
        if summary["confirmation"] is not None:
            summary = manager.confirm_turn(
                gid, summary["confirmation"], summary["revision"]
            )
            continue
        owner = summary["decision"]["owner"]
        session = manager._get(gid)
        actions = session.engine.legal_actions(session.state, owner)
        if (
            holder == owner
            and session.state.decision_stack[-1].kind == "turn"
            and ready(actions)
        ):
            meta = store.write(manager.save_game(gid, name="navigation-chamber"))
            print(json.dumps({"navigation-chamber": meta["save_id"], "seat": owner}))
            sys.exit(0)
        buy = next(
            (
                a
                for a in actions
                if a.action_id == "acquire_tech"
                and dict(a.arguments).get("tech_id") == "navigation_chamber"
            ),
            None,
        )
        if holder is None and buy is not None:
            chosen = buy
            holder = owner
        else:
            chosen = agents[owner].choose_action(
                session.engine.observe(session.state, owner), actions
            )
        summary = manager.apply_action(
            gid, owner, summary["revision"], actions.index(chosen)
        )
raise RuntimeError("no seat holding Navigation Chamber reached the Spice Refinery")
