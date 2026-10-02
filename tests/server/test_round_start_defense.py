"""The Control defense through the play server, in the rules' Round Start order.

"Each round begins by revealing a new Conflict card ... Next, each player
draws five cards from their own deck, forming their hand for the round."
[Main p. 8]; "When a Conflict card is revealed for a space that you already
control, you receive a defensive bonus: you may deploy one troop from your
supply to the Conflict." [Main p. 10] [Main p. 20]. The defense is asked
between the reveal and the draw (user ruling 2026-09-29), so a human
defender answers in Round Start, before any hand is drawn, and the answer
runs straight on into the draw.
"""

from __future__ import annotations

import random

from dune_imperium.core import GamePhase
from dune_imperium.rules.frames import FrameKind
from dune_imperium.server.sessions import GameSessionManager, JsonObject

# The AI seats play the table pinned in the registry, as in
# tests/server/test_turn_end.py, whose seed-0 walk this reuses.
HUMAN_FIRST = (
    "human",
    "heuristic_uprising_table",
    "heuristic_uprising_table",
    "heuristic_uprising_table",
)


def _obj(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _rows(value: object) -> list[dict[str, object]]:
    assert isinstance(value, list)
    return [_obj(item) for item in value]


def _int(value: object) -> int:
    assert isinstance(value, int)
    return value


def test_a_human_defender_answers_before_the_draw_and_cannot_undo_it() -> None:
    # Same walk as test_turn_end's restore test: seed 0 reaches a seat-0
    # Control defense (round 7) under an rng.Random(0).choice policy.
    # (Re-searched 2026-10-01: every Agent turn now waits for its owner's
    # finish_agent_turn (OQ-095), which moved seed 13 off it; 0, 7, 12, 22
    # and 23 of 0-39 reach it.)
    manager = GameSessionManager()
    summary: JsonObject = manager.create_game(HUMAN_FIRST, game_seed=0)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    rng = random.Random(0)

    found = False
    for _ in range(40_000):
        if summary["finished"]:
            break
        held = summary["confirmation"]
        if isinstance(held, int):
            summary = manager.confirm_turn(game_id, held, _int(summary["revision"]))
            continue
        owner = _int(_obj(summary["decision"])["owner"])
        actions = _rows(manager.legal_actions(game_id, owner)["actions"])
        top = session.state.decision_stack[-1] if session.state.decision_stack else None
        if top is not None and top.kind == FrameKind.CONTROL_DEFENSE and owner == 0:
            found = True
            break
        choice = rng.choice(actions)
        summary = manager.apply_action(
            game_id, owner, _int(summary["revision"]), _int(choice["index"])
        )
    assert found, "no seat-0 control_defense decision was reached"

    # At the defense: still Round Start, the Conflict revealed, no hand drawn.
    state = session.state
    assert summary["phase"] == str(GamePhase.ROUND_START)
    assert state.phase is GamePhase.ROUND_START
    assert all(player.hand == () for player in state.players)
    defender = state.players[0]
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert {str(row["action_id"]) for row in actions} == {
        "decline_control_defense",
        "deploy_control_defense",
    }
    # Either answer runs straight on into the draw, which shows each seat its
    # new hand, so neither can be taken back (hidden information).
    assert all(row["undoable"] is False for row in actions)

    (deploy,) = (row for row in actions if row["action_id"] == "deploy_control_defense")
    after = manager.apply_action(
        game_id, 0, _int(summary["revision"]), _int(deploy["index"])
    )

    drawn = session.state
    assert drawn.round_number == state.round_number
    assert drawn.current_conflict_ids == state.current_conflict_ids
    assert drawn.players[0].troops_conflict == defender.troops_conflict + 1
    assert len(drawn.players[0].hand) == min(5, len(defender.deck))
    # The defense is still the defender's own unit: one press ends it.
    assert after["confirmation"] == 0
