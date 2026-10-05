import json
import sys
from pathlib import Path

from dune_imperium.agents import HeuristicAgent
from dune_imperium.server.persistence import SaveStore
from dune_imperium.server.sessions import GameSessionManager

store = SaveStore(Path(sys.argv[1]))
found = {}
for seed in range(30):
    manager = GameSessionManager()
    summary = manager.create_game(
        ("human",) * 4, bloodlines=True, tech_module=True, game_seed=seed
    )
    gid = summary["game_id"]
    agents = [HeuristicAgent(seed=10000 + seed * 4 + i) for i in range(4)]
    for _step in range(1800):
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
        for tech_id in ("glowglobes", "navigation_chamber"):
            if tech_id in found:
                continue
            if session.state.decision_stack[-1].kind != "agent_effects":
                continue
            action = next(
                (
                    a
                    for a in actions
                    if a.action_id == "acquire_tech"
                    and dict(a.arguments).get("tech_id") == tech_id
                ),
                None,
            )
            others = [
                a
                for a in actions
                if a.action_id
                in (
                    "resolve_board_effect",
                    "resolve_agent_card_effect",
                    "resolve_faction_influence",
                )
            ]
            if action and others:
                meta = store.write(manager.save_game(gid, name=tech_id))
                found[tech_id] = meta["save_id"]
        if len(found) == 2:
            print(json.dumps(found))
            sys.exit(0)
        chosen = agents[owner].choose_action(
            session.engine.observe(session.state, owner), actions
        )
        summary = manager.apply_action(
            gid, owner, summary["revision"], actions.index(chosen)
        )
raise RuntimeError(f"Could not find both fixtures: {found}")
