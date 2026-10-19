"""Save two real games at the moment an Intrigue card sits face up.

Plays heuristic seats through GameSessionManager (no edited state) and saves
the first position in which a seat holds one of the wanted cards in its
`intrigue_faceup`: a base-game Call to Arms, and an Immortality game's
Tleilaxu Puppet or Manipulate (kept face up until the owner's Reveal turn
ends). Prints {name: {save_id, owner, card_id, other_faceup}} as JSON.
"""

import json
import sys
from pathlib import Path

from dune_imperium.agents import HeuristicAgent
from dune_imperium.server.persistence import SaveStore
from dune_imperium.server.sessions import GameSessionManager

WANTED = {
    "call_to_arms": ({}, ("call_to_arms",)),
    "reveal_plot": ({"immortality": True}, ("tleilaxu_puppet", "manipulate")),
}
SEEDS = range(60)
STEPS = 3000


def find(name: str, options: dict, wanted: tuple[str, ...], store: SaveStore) -> dict:
    for seed in SEEDS:
        manager = GameSessionManager()
        summary = manager.create_game(("human",) * 4, game_seed=seed, **options)
        gid = summary["game_id"]
        agents = [HeuristicAgent(seed=10000 + seed * 4 + i) for i in range(4)]
        for _step in range(STEPS):
            if summary["finished"]:
                break
            if summary["confirmation"] is not None:
                summary = manager.confirm_turn(
                    gid, summary["confirmation"], summary["revision"]
                )
                continue
            session = manager._get(gid)
            for player in session.state.players:
                for card_id in player.intrigue_faceup:
                    if card_id.split(":")[1] in wanted:
                        meta = store.write(manager.save_game(gid, name=name))
                        return {
                            "save_id": meta["save_id"],
                            "owner": player.player_id,
                            "card_id": card_id,
                            "faceup": {
                                str(p.player_id): list(p.intrigue_faceup)
                                for p in session.state.players
                            },
                        }
            owner = summary["decision"]["owner"]
            actions = session.engine.legal_actions(session.state, owner)
            chosen = agents[owner].choose_action_with_state(
                session.state, session.engine.observe(session.state, owner), actions
            )
            summary = manager.apply_action(
                gid, owner, summary["revision"], actions.index(chosen)
            )
    raise RuntimeError(f"Could not find a face-up {wanted} for {name}")


store = SaveStore(Path(sys.argv[1]))
print(json.dumps({name: find(name, *spec, store) for name, spec in WANTED.items()}))
