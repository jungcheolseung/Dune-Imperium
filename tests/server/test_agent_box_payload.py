"""The actions payload's Agent boxes: ``agent_boxes`` and each row's ``box``.

Plan stage 4 (docs/graft-boxes-plan.md 4.11; user request 2026-10-11, "그냥
선택지에 카드 효과가 바로 보여지는게 낫지 않나? 접합했을 때도 왜 다른 접합한
카드 효과 보기를 또 눌러야 그렇게 되게 한거야."): a grafted Agent turn offers
both cards' boxes from the start (codec v143), and the decision panel sets
each box's rows under a header naming its card. The server says which box a
row is and which boxes the turn has; display only, so the legal rows stay
exactly the engine's and a failure leaves the keys out.
"""

import json
import logging
from types import SimpleNamespace
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_placement
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.player import PlayerState, Resources
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.server import sessions
from dune_imperium.server.sessions import GameSessionManager, JsonObject

ENGINE = UprisingRulesEngine()
SEEK_ALLIES = "player:0:starter:seek_allies:0"
FACE_DANCER = "tleilaxu:face_dancer:0"
GHOLA = "tleilaxu:ghola:0"
HORROR = "tleilaxu:stitched_horror:0"


def _obj(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return value


def _rows(value: object) -> list[dict[str, Any]]:
    assert isinstance(value, list)
    return [_obj(item) for item in value]


def _turn(hand: tuple[str, ...]) -> GameState:
    seat = PlayerState(
        player_id=0, hand=hand, resources=Resources(solari=4, spice=2, water=2)
    )
    imperium = imperium_deck_instance_ids(True)
    return GameState(
        config=RulesetConfig(immortality=True, choam_module=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=("choam_security",),
        intrigue_deck=intrigue_deck_instance_ids(False)[:6],
        imperium_row=imperium[:5],
        imperium_deck=imperium[5:20],
        players=(seat, *(PlayerState(player_id=other) for other in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _graft(card: str, partner: str, space: str = "dutiful_service") -> GameState:
    state = _turn((card, partner))
    place = next(
        action
        for action in executable_placements(state, 0)
        if dict(action.arguments).get("card_id") == card
        and dict(action.arguments).get("space_id") == space
        and dict(action.arguments).get("graft") is True
        and "infiltrate_post_id" not in dict(action.arguments)
    )
    placed = apply_placement(ENGINE, state, place).state
    choice = DomainAction(
        action_id="choose_graft_partner", actor=0, arguments=(("card_id", partner),)
    )
    return ENGINE.apply(placed, choice).state


def _payload(state: GameState, seat: int = 0) -> JsonObject:
    session = SimpleNamespace(
        engine=ENGINE, state=state, game_id="test", awaiting_confirmation=None
    )
    return GameSessionManager()._legal_actions_locked(
        session,  # type: ignore[arg-type]
        seat,
    )


def test_a_grafted_turn_names_both_boxes_and_each_row_s_box() -> None:
    state = _graft(FACE_DANCER, SEEK_ALLIES)
    payload = _payload(state)
    json.dumps(payload)

    assert payload["agent_boxes"] == [
        {
            "box": 0,
            "card_id": FACE_DANCER,
            "name": "Face Dancer",
            "name_ko": "얼굴의 춤꾼",
            "locked": False,
        },
        {
            "box": 1,
            "card_id": SEEK_ALLIES,
            "name": "Seek Allies",
            "name_ko": "동맹 물색",
            "locked": False,
        },
    ]
    rows = _rows(payload["actions"])
    boxed = {
        (row["action_id"], json.dumps(row["arguments"])): row["box"]
        for row in rows
        if "box" in row
    }
    assert boxed == {
        ("resolve_agent_card_effect", "{}"): 0,
        ("resolve_agent_card_effect", '{"box": 1}'): 1,
    }
    # Each box row still leads with its card for the log and the banners.
    assert {row["detail_title"] for row in rows if "box" in row} == {
        "Face Dancer",
        "Seek Allies",
    }
    # Every other row (the space's effects, deployments...) has no box.
    assert any("box" not in row for row in rows)


def test_a_box_held_back_by_the_other_box_s_choice_is_locked() -> None:
    """Stitched Horror's "Choose two" after its first pick (OQ-057 (4)):
    only its own rows are offered, and the other box says it waits."""

    state = _graft(HORROR, GHOLA, "arrakeen")
    first = next(
        action
        for action in ENGINE.legal_actions(state, 0)
        if action.action_id == "choose_agent_card_reward"
        and ("box", 1) in action.arguments
    )
    picked = ENGINE.apply(state, first).state
    payload = _payload(picked)

    boxes = [
        (entry["box"], entry["name"], entry["locked"])
        for entry in _rows(payload["agent_boxes"])
    ]
    assert boxes == [(0, "Stitched Horror", True), (1, "Ghola", False)]
    assert {row.get("box") for row in _rows(payload["actions"])} == {1, None}


def test_a_waiting_box_s_greyed_row_names_its_box() -> None:
    """Beguiling Pheromones' box waits for a Faction space (OQ-057 (1)):
    its greyed row carries box 1, beside the legal rows of no box."""

    state = _graft(
        "player:0:starter:dagger:0",
        "tleilaxu:beguiling_pheromones:0",
        "assembly_hall",
    )
    payload = _payload(state)

    rows = _rows(_obj(payload["unavailable"])["rows"])
    waiting = [row for row in rows if row["key"].startswith("waiting:agent_box:")]
    assert [row["box"] for row in waiting] == [1]
    assert waiting[0]["action"]["detail_title"] == "Beguiling Pheromones"
    assert all("box" not in row for row in _rows(payload["actions"]))


def test_any_other_decision_has_no_boxes() -> None:
    payload = _payload(_turn((SEEK_ALLIES,)))
    assert payload["agent_boxes"] is None
    assert payload["actions"]
    assert all("box" not in row for row in _rows(payload["actions"]))
    # Nor does a seat that does not decide.
    other = _payload(_graft(FACE_DANCER, SEEK_ALLIES), 1)
    assert other["agent_boxes"] is None and other["actions"] == []


def test_a_failing_box_read_still_serves_the_legal_actions(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    state = _graft(FACE_DANCER, SEEK_ALLIES)
    expected = [
        {key: value for key, value in row.items() if key != "box"}
        for row in _rows(_payload(state)["actions"])
    ]

    def broken(*_: object) -> None:
        raise RuntimeError("no box")

    monkeypatch.setattr(sessions, "agent_box_headers", broken)
    with caplog.at_level(logging.ERROR, logger=sessions.__name__):
        payload = _payload(state)

    assert payload["agent_boxes"] is None
    assert payload["actions"] == expected and expected
    assert any(
        record.exc_info and "Agent-box groups failed" in record.getMessage()
        for record in caplog.records
    )
