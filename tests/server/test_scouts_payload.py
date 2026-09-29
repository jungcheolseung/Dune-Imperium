"""The actions payload's Arrakeen Scouts lines and subcommittee preview.

User request 2026-09-29: the page shows every line of a Scouts choice, the
ones the seat cannot take now greyed out with the reason, and a High Council
step says which subcommittees its seat would let the seat join. Display and
payload only: the legal actions (and so the codec, the observation, the
events and the saves) are unchanged (``display.scouts.scouts_choice_lines``,
``sessions.subcommittee_preview``).
"""

import json
from types import SimpleNamespace
from typing import Any

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.player import PlayerState, Resources
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.scouts_effects import offer_scouts_choice
from dune_imperium.server.sessions import GameSessionManager, _serialize_action

ENGINE = UprisingRulesEngine()
HUMAN_FIRST = ("human", "heuristic", "heuristic", "heuristic")
DISPLAY = ("readiness", "oversight", "relations", "appropriations", "leverage")


def _obj(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return value


def _state(spice: int, **fields: Any) -> GameState:
    owner = PlayerState(
        player_id=0,
        hand=starting_deck_instance_ids(0),
        resources=Resources(solari=5, spice=spice, water=1),
    )
    values: dict[str, Any] = {
        "config": RulesetConfig(arrakeen_scouts=True),
        "seed": 1,
        "phase": GamePhase.PLAYER_TURNS,
        "round_number": 2,
        "first_player": 0,
        "players": (owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        "scouts_subcommittees": DISPLAY,
        "decision_stack": (
            DecisionFrame(
                kind="turn",
                frame_id="round:2:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    }
    values.update(fields)
    return GameState(**values)


def _session(state: GameState) -> SimpleNamespace:
    return SimpleNamespace(
        engine=ENGINE, state=state, game_id="test", awaiting_confirmation=None
    )


def _council_step(state: GameState) -> dict[str, Any]:
    """Send the Dagger to the High Council; serialize its seat's icon."""

    placement = next(
        action
        for action in ENGINE.legal_actions(state, 0)
        if action.action_id == "agent_turn"
        and dict(action.arguments)["space_id"] == "high_council"
        and "dagger" in str(dict(action.arguments)["card_id"])
    )
    placed = ENGINE.apply(state, placement).state
    legal = ENGINE.legal_actions(placed, 0)
    council = DomainAction(
        action_id="resolve_board_effect",
        actor=0,
        arguments=(("effect", "high_council"),),
    )
    assert council in legal
    return _serialize_action(
        legal.index(council),
        council,
        _session(placed),  # type: ignore[arg-type]
    )


def test_scouts_lines_is_null_outside_a_scouts_choice() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = str(summary["game_id"])

    payload = manager.legal_actions(game_id, 0)

    assert payload["actions"]
    assert payload["scouts_lines"] is None
    assert _obj(manager.snapshot(game_id, 0)["actions"])["scouts_lines"] is None


def test_scouts_lines_number_the_enabled_line_by_its_row() -> None:
    offered = offer_scouts_choice(
        _state(2), 0, "unravel_the_future", source="round:2:scouts"
    ).state
    payload = GameSessionManager()._legal_actions_locked(
        _session(offered),  # type: ignore[arg-type]
        0,
    )
    json.dumps(payload)

    lines = _obj(payload["scouts_lines"])
    assert lines["frame"] == "scouts_choice"
    rows = payload["actions"]
    assert isinstance(rows, list)
    cheap, dear = lines["lines"]
    row = _obj(rows[cheap["action_index"]])
    assert row["action_id"] == "scouts_choose_option"
    assert row["arguments"] == {"option": 0}
    assert dear["action_index"] is None
    assert dear["reason"] == "Needs 3 spice (you have 2)"
    # The row list itself is the engine's: pass and the one payable line.
    assert [_obj(item)["action_id"] for item in rows] == [
        "scouts_pass",
        "scouts_choose_option",
    ]


def test_the_high_council_step_previews_the_subcommittee_offer() -> None:
    serialized = _council_step(
        _state(1, scouts_subcommittee_members=(("readiness", 2),))
    )
    json.dumps(serialized)

    preview = _obj(serialized["subcommittee_preview"])
    assert preview["joinable"] is True
    lines = {line["subcommittee_id"]: line for line in preview["lines"]}
    assert list(lines) == list(DISPLAY)
    assert all(line["action_index"] is None for line in lines.values())
    assert lines["readiness"]["code"] == "claimed" and lines["readiness"]["seat"] == 2
    assert lines["appropriations"]["enabled"]
    assert not lines["relations"]["enabled"]
    assert lines["relations"]["reason"] == "Needs 2 spice (you have 1)"
    assert lines["oversight"]["reason"] == "Needs 1 Spy on the board (you have 0)"


def test_the_preview_follows_the_seats_resources() -> None:
    """Two more spice before the icon: Relations lights up in the preview."""

    lines = {
        line["subcommittee_id"]: line
        for line in _obj(_council_step(_state(3))["subcommittee_preview"])["lines"]
    }
    assert lines["relations"]["enabled"] and lines["relations"]["reason"] is None


def test_the_preview_says_when_the_offer_would_lapse() -> None:
    # Three other seats hold three; Oversight needs a Spy on the board and
    # Contingencies an Intrigue card, and the seat has neither.
    claimed = (("readiness", 1), ("relations", 2), ("appropriations", 3))
    serialized = _council_step(
        _state(
            5,
            scouts_subcommittees=(*DISPLAY[:4], "contingencies"),
            scouts_subcommittee_members=claimed,
        )
    )

    assert serialized["subcommittee_preview"] == {"joinable": False, "lines": []}


def test_a_step_without_a_council_seat_has_no_preview() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13, arrakeen_scouts=True)
    rows = manager.legal_actions(str(summary["game_id"]), 0)["actions"]
    assert isinstance(rows, list) and rows
    assert all("subcommittee_preview" not in _obj(row) for row in rows)
