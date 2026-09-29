"""The actions payload's ``unavailable``: what the seat cannot take now.

User request 2026-09-29: every choice the seat cannot take right now is
shown greyed out with the reason, for the whole game
(``display.unavailable.unavailable_choices``). Display and payload only: the
legal actions (and so the codec, the observation, the events and the saves)
are exactly what they were, a greyed-out row carries no index and no dry-run
preview, and only the seat that owns the decision gets one.
"""

import json
import logging
import re
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.server import sessions
from dune_imperium.server.sessions import GameSessionManager, JsonObject

ENGINE = UprisingRulesEngine()
HANGUL = re.compile(r"[가-힣]")
TWO_HUMANS = ("human", "human", "heuristic", "heuristic")


def _obj(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return value


def _rows(value: object) -> list[dict[str, Any]]:
    assert isinstance(value, list)
    return [_obj(item) for item in value]


def _int(value: object) -> int:
    assert isinstance(value, int)
    return value


def _reveal_state() -> GameState:
    """Seat 0 in its Reveal with 2 Persuasion, an Intrigue card it cannot
    pay for, and a Row of 3-Persuasion cards beside a Reserve it can buy."""

    owner = PlayerState(player_id=0, intrigue_cards=("intrigue:imperium_politics:0",))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        imperium_row=imperium_deck_instance_ids(False)[:5],
        reserve_stacks=(("prepare_the_way", 8), ("the_spice_must_flow", 10)),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    revealed = ENGINE.apply(state, DomainAction(action_id="reveal_turn", actor=0))
    frame = revealed.state.decision_stack[-1]
    context = {**dict(frame.context), "persuasion": 2}
    return replace(
        revealed.state,
        decision_stack=(
            *revealed.state.decision_stack[:-1],
            replace(frame, context=tuple(sorted(context.items()))),
        ),
    )


def _payload(state: GameState, seat: int = 0) -> JsonObject:
    session = SimpleNamespace(
        engine=ENGINE, state=state, game_id="test", awaiting_confirmation=None
    )
    return GameSessionManager()._legal_actions_locked(
        session,  # type: ignore[arg-type]
        seat,
    )


def test_the_payload_greys_out_the_reveal_shop_and_the_intrigue_card() -> None:
    payload = _payload(_reveal_state())
    json.dumps(payload)

    info = _obj(payload["unavailable"])
    assert info["frame"] == "reveal"
    rows = info["rows"]
    assert {row["surface"] for row in rows} == {"acquire", "intrigue"}
    legal = [(row["action_id"], row["arguments"]) for row in _rows(payload["actions"])]
    assert ("acquire_reserve", {"card_id": "prepare_the_way"}) in legal
    for row in rows:
        action = row["action"]
        # Described like a legal row, without its index or dry-run previews.
        assert set(action) == {"action_id", "arguments", "detail", "detail_ko"}
        assert (action["action_id"], action["arguments"]) not in legal
        assert row["reason"] and row["reason_ko"]
        assert not HANGUL.search(row["reason"])
    intrigue = next(row for row in rows if row["surface"] == "intrigue")
    assert intrigue["reason"] == "Needs 1 solari (you have 0)"
    assert info["refs"]["intrigue:imperium_politics:0"]["code"] == "cost"
    assert info["refs"]["the_spice_must_flow"]["reason"] == (
        "Needs 9 Persuasion (you have 2)"
    )


def test_the_legal_actions_are_the_same_with_or_without_the_greyed_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _reveal_state()
    with_rows = _payload(state)
    monkeypatch.setattr(sessions, "unavailable_choices", lambda *_: None)
    without = _payload(state)

    assert with_rows["unavailable"] is not None
    assert without["unavailable"] is None
    assert with_rows["actions"] == without["actions"]
    assert with_rows["scouts_lines"] == without["scouts_lines"] is None


def test_a_failing_greyed_out_payload_still_serves_the_legal_actions(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The rows are display only: an error working them out is logged and
    the key is None, and the seat still gets its whole legal list."""

    state = _reveal_state()
    expected = _payload(state)["actions"]

    def broken(*_: object) -> None:
        raise RuntimeError("no reason for this block")

    monkeypatch.setattr(sessions, "unavailable_choices", broken)
    with caplog.at_level(logging.ERROR, logger=sessions.__name__):
        payload = _payload(state)

    assert payload["unavailable"] is None
    assert payload["actions"] == expected and expected
    assert any(
        record.exc_info and "greyed-out choices failed" in record.getMessage()
        for record in caplog.records
    )


def test_only_the_deciding_seat_gets_greyed_rows() -> None:
    state = _reveal_state()

    assert _payload(state, 0)["unavailable"] is not None
    other = _payload(state, 1)
    assert other["actions"] == [] and other["unavailable"] is None


def test_a_live_game_sends_the_key_only_to_the_seat_to_move() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(TWO_HUMANS, game_seed=13)
    game_id = str(summary["game_id"])
    owner = _int(_obj(summary["decision"])["owner"])
    other = 1 - owner

    payload = manager.legal_actions(game_id, owner)
    assert "unavailable" in payload
    assert (
        _obj(manager.snapshot(game_id, owner)["actions"])["unavailable"]
        == (payload["unavailable"])
    )
    assert manager.legal_actions(game_id, other)["unavailable"] is None
    assert manager.snapshot(game_id, other)["actions"] is None


def test_a_live_reveal_greys_out_what_the_seat_cannot_buy() -> None:
    """Seat 0 plays its first legal action until its first Reveal: the Row
    and the Reserve cards it cannot afford come greyed out with the reason,
    the table cards they name are dimmed, and none of them is a legal row."""

    manager = GameSessionManager()
    summary = manager.create_game(
        ("human", "heuristic", "heuristic", "heuristic"), game_seed=5
    )
    game_id = str(summary["game_id"])
    for _ in range(400):
        assert not summary["finished"]
        held = summary["confirmation"]
        if isinstance(held, int):
            summary = manager.confirm_turn(game_id, held, _int(summary["revision"]))
            continue
        decision = _obj(summary["decision"])
        payload = manager.legal_actions(game_id, 0)
        if decision.get("kind") == "reveal" and payload["unavailable"]:
            break
        summary = manager.apply_action(game_id, 0, _int(summary["revision"]), 0)
    else:
        raise AssertionError("seat 0 never reached a Reveal with greyed-out cards")

    info = _obj(payload["unavailable"])
    json.dumps(info)
    acquire = [row for row in info["rows"] if row["surface"] == "acquire"]
    assert acquire
    legal = {
        (row["action_id"], json.dumps(row["arguments"], sort_keys=True))
        for row in _rows(payload["actions"])
    }
    for row in acquire:
        action = row["action"]
        assert (
            action["action_id"],
            json.dumps(action["arguments"], sort_keys=True),
        ) not in legal
        assert row["code"] in {"cost", "empty"}
        assert row["refs"] and row["refs"][0] in info["refs"]
    persuasion = decision["persuasion"]
    assert any(row["reason"].endswith(f"(you have {persuasion})") for row in acquire)
