"""Rise of Ix's starting Contracts stay each seat's own in the server's log.

Uprising with Rise of Ix and the CHOAM Module: "give two to each player.
Each player looks at the two they've been given, choosing simultaneously
which contract they want to begin the game with" [Main p. 16]
(docs/rules/choam-module.md, OQ-161 (2): a sealed choice seat by seat). The
live log seals each pick (``SEALED_ACTION_IDS``): another seat sees that the
seat chose and ``(비공개)`` for which, the chooser its own tile, and a
finished game's review everything (OQ-010 ruling 4). The last pick reveals
every choice, so it is a reveal; an earlier one reveals nothing.
"""

import json
from typing import Any

from dune_imperium import RulesetConfig
from dune_imperium.core import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.server.session_log import (
    SEALED_ACTION_IDS,
    LoggedStep,
    log_step,
    reveals_hidden_information,
)
from dune_imperium.server.sessions import GameSessionManager, _log_entry_json

CONFIG = RulesetConfig(rise_of_ix=True, choam_module=True, first_player_seat_zero=True)


def _chooser(state: GameState) -> int:
    decision = state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def _picked(
    engine: UprisingRulesEngine, state: GameState, seat: int, tile: str
) -> tuple[GameState, LoggedStep]:
    action = DomainAction("choose_starting_contract", seat, (("instance_id", tile),))
    result = engine.apply(state, action)
    return result.state, log_step(state, result.state, action, result.events)


def test_another_seat_s_log_hides_each_starting_contract_pick() -> None:
    assert "choose_starting_contract" in SEALED_ACTION_IDS
    engine = UprisingRulesEngine()
    state = engine.reset(CONFIG, 3)
    assert state.phase is GamePhase.SETUP
    pairs = {seat.player_id: seat.starting_contract_ids for seat in state.players}
    for seat in range(4):
        assert _chooser(state) == seat
        tile = pairs[seat][1]
        before = state
        state, entry = _picked(engine, state, seat, tile)
        assert entry.sealed
        own: Any = _log_entry_json(0, entry, seat, finished=False)
        assert own["arguments"] == {"instance_id": tile}
        others = [other for other in range(4) if other != seat]
        if seat < 3:
            assert {
                "kind": "starting_contract_identity",
                "payload": {"contract_id": tile, "player": seat},
            } in own["events"]
            # No other seat learns the pair or the choice before the last.
            assert not entry.reveals
            assert not reveals_hidden_information(before, state, seat)
            for other in others:
                shown: Any = _log_entry_json(0, entry, other, finished=False)
                assert shown["action_id"] == "choose_starting_contract"
                assert shown["arguments"] == {"instance_id": "(비공개)"}
                kinds = [event["kind"] for event in shown["events"]]
                assert "starting_contract_identity" not in kinds
                assert {
                    "kind": "starting_contract_chosen",
                    "payload": {"player": seat},
                } in shown["events"]
                assert not any(card in str(shown) for card in pairs[seat])
        else:
            # The last choice turns every one face up: a reveal for all.
            assert reveals_hidden_information(before, state, seat)
        review: Any = _log_entry_json(0, entry, others[0], finished=True)
        assert review["arguments"] == {"instance_id": tile}
    assert state.phase is not GamePhase.SETUP
    assert all(
        state.players[seat].active_contract_ids == (pairs[seat][1],)
        for seat in range(4)
    )


def _payload(manager: GameSessionManager, game_id: str, seat: int) -> str:
    """Everything the server sends ``seat``: its view, its rows, the log."""

    return json.dumps(
        [
            manager.view(game_id, seat),
            manager.legal_actions(game_id, seat),
            manager.log(game_id, seat),
        ],
        ensure_ascii=False,
    )


def test_the_server_sends_no_seat_another_seat_s_two_or_the_box() -> None:
    """Through the play server, four human seats: before the last choice no
    seat's payload (view, legal rows, log) names another seat's two tiles
    or a tile in the box; its own two it sees. The last choice shows every
    chosen tile to every seat, the box's still to none."""

    manager = GameSessionManager()
    summary = manager.create_game(
        ("human",) * 4,
        rise_of_ix=True,
        choam_module=True,
        first_player_seat_zero=True,
        game_seed=3,
    )
    game_id = str(summary["game_id"])
    state = manager._get(game_id).state
    pairs = {seat.player_id: seat.starting_contract_ids for seat in state.players}
    box = state.contract_box
    for chooser in range(4):
        for seat in range(4):
            shown = _payload(manager, game_id, seat)
            assert all(card in shown for card in pairs[seat])
            assert not any(card in shown for card in box)
            for other in range(4):
                if other != seat:
                    assert not any(card in shown for card in pairs[other]), (
                        chooser,
                        seat,
                        other,
                    )
        rows: Any = manager.legal_actions(game_id, chooser)["actions"]
        index = next(
            row["index"]
            for row in rows
            if row["action_id"] == "choose_starting_contract"
            and row["arguments"]["instance_id"] == pairs[chooser][0]
        )
        current: Any = manager.summary(game_id)
        manager.apply_action(
            game_id,
            chooser,
            current["revision"],
            index,
            undo_count=current["undo_count"],
        )
    final = manager._get(game_id).state
    for seat in range(4):
        shown = _payload(manager, game_id, seat)
        assert all(pairs[other][0] in shown for other in range(4))
        assert not any(card in shown for card in final.contract_box)
