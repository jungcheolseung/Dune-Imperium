"""The Control defense with an empty supply, through the play server.

"When a Conflict card is revealed for a space that you already control, you
receive a defensive bonus: you may deploy one troop from your supply to the
Conflict." [Main p. 10] [Main p. 20]; "You may return any of your specimens
to your supply at any time" [Immortality p. 8]. OQ-050 (user ruling
2026-10-04, "앱 구현 방식으로 가자", docs/rules/open-questions.md): "Round
Start에 공개된 Conflict의 위치를 Control하는 좌석이 supply에 troop이 없어도
specimen이 있으면 Control 방어 frame을 열고 ... `return_specimen`을
제시한다. 하나를 돌리면 supply에 troop이 생기므로 반환 제시는 끝나고 방어
배치를 고를 수 있다." The engine side is tests/unit/rules/
test_specimen_return_windows.py; this file pins what the seat is shown and can
do at that frame: the decision, the two rows it is offered (no deploy row
before the return), that taking the specimen back leaves the frame open, and
that the whole answer can be taken back step by step until the turn-end press.
"""

from __future__ import annotations

from dune_imperium.agents.registry import make_agent
from dune_imperium.core import GamePhase
from dune_imperium.rules.frames import FrameKind
from dune_imperium.server.sessions import GameSessionManager, JsonObject

# All four seats are human to the server and played by the table pinned in
# the registry, so the walk does not move when the heuristic is retuned.
# Seed 179 reaches an empty-supply defense first (round 10, seat 1, one
# specimen; 2026-10-18, after the Conflict-end order moved every game -- no
# seed of 0-178 does now; seed 14 until then); the later seeds are only a
# fallback if the engine's games move.
SEEDS = (179, *range(60))


def _obj(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _rows(value: object) -> list[dict[str, object]]:
    assert isinstance(value, list)
    return [_obj(item) for item in value]


def _list(value: object) -> list[object]:
    assert isinstance(value, list)
    return value


def _int(value: object) -> int:
    assert isinstance(value, int)
    return value


def _ids(rows: list[dict[str, object]]) -> list[str]:
    return [str(row["action_id"]) for row in rows]


def _walk_to_empty_supply_defense() -> tuple[GameSessionManager, str, JsonObject, int]:
    """Play an Immortality game until a seat with no troop in its supply but a
    specimen is asked to defend the location it controls."""

    for seed in SEEDS:
        manager = GameSessionManager()
        summary = manager.create_game(("human",) * 4, immortality=True, game_seed=seed)
        game_id = str(summary["game_id"])
        session = manager._get(game_id)
        agents = [
            make_agent("heuristic_uprising_table", 20000 + seed * 4 + seat)
            for seat in range(4)
        ]
        for _ in range(20_000):
            if summary["finished"]:
                break
            held = summary["confirmation"]
            if isinstance(held, int):
                summary = manager.confirm_turn(
                    game_id, held, _int(summary["revision"])
                )
                continue
            owner = _int(_obj(summary["decision"])["owner"])
            state = session.state
            top = state.decision_stack[-1] if state.decision_stack else None
            if top is not None and top.kind == FrameKind.CONTROL_DEFENSE:
                defender = state.players[owner]
                if defender.troops_supply == 0 and defender.specimens > 0:
                    return manager, game_id, summary, owner
            actions = session.engine.legal_actions(state, owner)
            chosen = agents[owner].choose_action(
                session.engine.observe(state, owner), actions
            )
            summary = manager.apply_action(
                game_id, owner, _int(summary["revision"]), actions.index(chosen)
            )
    raise AssertionError("no empty-supply Control defense was reached")


def test_an_empty_supply_defender_returns_a_specimen_for_the_troop() -> None:
    manager, game_id, summary, seat = _walk_to_empty_supply_defense()
    session = manager._get(game_id)
    state = session.state

    # At the frame: Round Start, the Conflict revealed, no hand drawn, and the
    # defender holds the location with nothing in its supply but a specimen.
    defender = state.players[seat]
    assert summary["phase"] == str(GamePhase.ROUND_START)
    assert all(player.hand == () for player in state.players)
    assert defender.troops_supply == 0 and defender.specimens > 0
    assert dict(state.decision_stack[-1].context)["space_id"] in (
        defender.control_space_ids
    )
    decision = _obj(summary["decision"])
    assert decision["kind"] == "control_defense"
    assert decision["owner"] == seat and decision["owner_is_human"] is True
    assert summary["confirmation"] is None

    # The seat is offered declining and returning a specimen; there is no
    # deploy row to press while the supply is empty. Only the defender has a
    # row at all, and neither row is held for the press or carries a warning.
    offered = manager.legal_actions(game_id, seat)
    actions = _rows(offered["actions"])
    assert _ids(actions) == ["decline_control_defense", "return_specimen"]
    assert all(row["undoable"] is True for row in actions)
    assert all(row["sent_by_turn_end"] is False for row in actions)
    assert all(row["warning"] is None for row in actions)
    assert _obj(actions[1])["arguments"] == {}
    for other in range(4):
        if other != seat:
            assert _rows(manager.legal_actions(game_id, other)["actions"]) == []

    # Taking one specimen back fills the supply and leaves the frame open: it
    # is not an answer, so nothing is held and the next offer is the deploy.
    returned = manager.apply_action(
        game_id, seat, _int(summary["revision"]), _int(actions[1]["index"])
    )
    after_return = session.state
    assert returned["confirmation"] is None
    assert _obj(returned["decision"])["kind"] == "control_defense"
    assert _obj(returned["decision"])["owner"] == seat
    assert after_return.decision_stack[-1].kind == FrameKind.CONTROL_DEFENSE
    assert after_return.players[seat].troops_supply == 1
    assert after_return.players[seat].specimens == defender.specimens - 1
    assert all(player.hand == () for player in after_return.players)
    assert returned["undo"] == [{"seat": seat, "steps": 1}]
    actions = _rows(manager.legal_actions(game_id, seat)["actions"])
    # One specimen covers the one defending troop: no second return is offered.
    assert _ids(actions) == ["decline_control_defense", "deploy_control_defense"]
    assert all(row["undoable"] is True for row in actions)
    assert all(row["sent_by_turn_end"] is False for row in actions)

    # Deploying answers the defense: the engine pauses before the draw, so the
    # server holds the answer for the press, with both steps to take back.
    held = manager.apply_action(
        game_id,
        seat,
        _int(returned["revision"]),
        _int(actions[1]["index"]),
        undo_count=_int(returned["undo_count"]),
    )
    assert held["confirmation"] == seat
    assert session.state.decision_stack[-1].kind == FrameKind.PAUSE
    deployed = session.state.players[seat]
    assert deployed.troops_conflict == defender.troops_conflict + 1
    assert deployed.troops_supply == 0
    assert deployed.specimens == defender.specimens - 1
    assert all(player.hand == () for player in session.state.players)
    assert {"seat": seat, "steps": 2} in _list(held["undo"])

    # One step back is the deploy offer again, two is the empty supply.
    back = manager.undo(game_id, seat, _int(held["revision"]), 1)
    assert session.state.players[seat].troops_supply == 1
    assert session.state.decision_stack[-1].kind == FrameKind.CONTROL_DEFENSE
    back = manager.undo(
        game_id, seat, _int(back["revision"]), 1, undo_count=_int(back["undo_count"])
    )
    assert session.state.players[seat] == defender
    assert session.state.decision_stack[-1].kind == FrameKind.CONTROL_DEFENSE
    assert back["confirmation"] is None
    actions = _rows(manager.legal_actions(game_id, seat)["actions"])
    assert _ids(actions) == ["decline_control_defense", "return_specimen"]

    # Declining without returning anything is a complete answer: the supply
    # stays empty, the specimen stays, and the press draws the round's hands.
    held = manager.apply_action(
        game_id,
        seat,
        _int(back["revision"]),
        _int(actions[0]["index"]),
        undo_count=_int(back["undo_count"]),
    )
    assert held["confirmation"] == seat
    after = manager.confirm_turn(
        game_id, seat, _int(held["revision"]), undo_count=_int(held["undo_count"])
    )
    drawn = session.state
    assert after["confirmation"] is None
    assert drawn.round_number == state.round_number
    assert drawn.players[seat].troops_supply == 0
    assert drawn.players[seat].specimens == defender.specimens
    assert drawn.players[seat].troops_conflict == defender.troops_conflict
    assert len(drawn.players[seat].hand) == min(5, len(defender.deck))
