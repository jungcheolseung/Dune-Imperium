"""Save a real Immortality game at a Control defense with an empty supply.

All four seats are human and their moves come from the registry-pinned table
heuristic (``heuristic_uprising_table``, so a retune of ``heuristic`` does not
move the walk), as in tests/server/test_empty_supply_defense.py, whose walk
this is: base game plus Immortality, no edited state. The game is saved at
the first Round Start Control defense whose defender has no troop in its
supply but a specimen -- the frame OQ-050 opens so that a specimen can be
returned "at any time" [Immortality p. 8] for the one defending troop
[Main pp. 10, 20]. A walk of seeds 0-39 finds seed 14 first (round 9, seat 0,
one specimen, Spice Refinery; seed 30 also does, with seat 2).

Prints {"defense-specimen": save_id, "seat": defender, "specimens": count} as
JSON.
"""

import json
import sys
from pathlib import Path

from dune_imperium.agents.registry import make_agent
from dune_imperium.rules.frames import FrameKind
from dune_imperium.server.persistence import SaveStore
from dune_imperium.server.sessions import GameSessionManager

STEPS = 20_000

store = SaveStore(Path(sys.argv[1]))

for seed in range(60):
    manager = GameSessionManager()
    summary = manager.create_game(("human",) * 4, immortality=True, game_seed=seed)
    gid = summary["game_id"]
    session = manager._get(gid)
    agents = [
        make_agent("heuristic_uprising_table", 20000 + seed * 4 + seat)
        for seat in range(4)
    ]
    for _step in range(STEPS):
        if summary["finished"]:
            break
        if summary["confirmation"] is not None:
            summary = manager.confirm_turn(
                gid, summary["confirmation"], summary["revision"]
            )
            continue
        owner = summary["decision"]["owner"]
        state = session.state
        top = state.decision_stack[-1] if state.decision_stack else None
        if top is not None and top.kind == FrameKind.CONTROL_DEFENSE:
            defender = state.players[owner]
            if defender.troops_supply == 0 and defender.specimens > 0:
                meta = store.write(manager.save_game(gid, name="defense-specimen"))
                print(
                    json.dumps(
                        {
                            "defense-specimen": meta["save_id"],
                            "seat": owner,
                            "specimens": defender.specimens,
                        }
                    )
                )
                sys.exit(0)
        actions = session.engine.legal_actions(state, owner)
        chosen = agents[owner].choose_action(
            session.engine.observe(state, owner), actions
        )
        summary = manager.apply_action(
            gid, owner, summary["revision"], actions.index(chosen)
        )
raise RuntimeError("no seat was asked to defend with an empty supply and a specimen")
