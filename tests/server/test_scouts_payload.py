"""The actions payload's Arrakeen Scouts lines and subcommittee preview.

User request 2026-09-29: the page shows every line of a Scouts choice, the
ones the seat cannot take now greyed out with the reason, and a High Council
step says which subcommittees its seat would let the seat join. Display and
payload only: the legal actions (and so the codec, the observation, the
events and the saves) are unchanged (``display.scouts.scouts_choice_lines``,
``sessions.subcommittee_preview``). Since the 2026-09-30 ruling (OQ-076
alternative C) the seat chooses its subcommittee any time in that turn, so
the preview describes what could be joined once the seat is taken.
"""

import json
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.player import PlayerState, Resources
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.scouts_effects import offer_scouts_choice, offer_secret_reward
from dune_imperium.rules.scouts_secrets import SECRET_ITEM
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
        for action in executable_placements(state, 0)
        if dict(action.arguments)["space_id"] == "high_council"
        and "dagger" in str(dict(action.arguments)["card_id"])
    )
    placed = apply_placement(ENGINE, state, placement).state
    # The payload indexes the seat's whole actions (stage B3).
    legal = ENGINE.whole_actions(placed, 0)
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


def test_the_preview_says_when_nothing_is_joinable_at_once() -> None:
    """OQ-076 alternative C: the seat may still choose later in the turn, so
    open subcommittees nothing can meet yet come with their reasons."""
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

    preview = _obj(serialized["subcommittee_preview"])
    assert preview["joinable"] is False
    lines = {line["subcommittee_id"]: line for line in preview["lines"]}
    assert not any(line["enabled"] for line in lines.values())
    assert lines["oversight"]["reason"] == "Needs 1 Spy on the board (you have 0)"
    assert lines["contingencies"]["code"] == "cost"


def test_the_preview_says_when_every_subcommittee_is_taken() -> None:
    """With every subcommittee taken the offer still opens with only its
    decline (user ruling 2026-09-30, OQ-076 (c)); the preview lists every
    one as claimed by its member, nothing joinable (the page then says none
    is left). It used to be an empty list, read off the lapse event."""
    # A seat joins once, so three other seats can hold a three-strong display.
    claimed = (("readiness", 1), ("oversight", 2), ("relations", 3))
    serialized = _council_step(
        _state(
            5,
            scouts_subcommittees=DISPLAY[:3],
            scouts_subcommittee_members=claimed,
        )
    )

    preview = _obj(serialized["subcommittee_preview"])
    assert preview["joinable"] is False
    lines = preview["lines"]
    assert isinstance(lines, list)
    assert [(line["subcommittee_id"], line["seat"]) for line in lines] == list(
        claimed
    )
    assert all(line["code"] == "claimed" and not line["enabled"] for line in lines)


def test_choosing_a_subcommittee_can_be_taken_back() -> None:
    """Opening the list reveals nothing and hands nothing to chance, so the
    step stays undoable like the visit's other effects."""
    placement = next(
        action
        for action in executable_placements(_state(3), 0)
        if dict(action.arguments)["space_id"] == "high_council"
        and "dagger" in str(dict(action.arguments)["card_id"])
    )
    placed = apply_placement(ENGINE, _state(3), placement).state
    seated = apply_whole(
        ENGINE,
        placed,
        DomainAction(
            action_id="resolve_board_effect",
            actor=0,
            arguments=(("effect", "high_council"),),
        ),
    ).state
    legal = ENGINE.whole_actions(seated, 0)
    rows = {
        action.action_id: _serialize_action(
            legal.index(action),
            action,
            _session(seated),  # type: ignore[arg-type]
        )
        for action in legal
    }
    assert rows["choose_subcommittee"]["undoable"] is True
    # The Agent turn offers no refusal: the unused offer lapses at the turn
    # end (OQ-095 (2), user ruling 2026-10-14; codec v146).
    assert "decline_subcommittee" not in rows
    # Opening the list is not the seat taking its seat: no preview on it.
    assert "subcommittee_preview" not in rows["choose_subcommittee"]
    chosen = apply_whole(
        ENGINE, seated, DomainAction(action_id="choose_subcommittee", actor=0)
    ).state
    join = DomainAction(
        action_id="join_subcommittee",
        actor=0,
        arguments=(("subcommittee_id", "readiness"),),
    )
    joined = _serialize_action(
        ENGINE.whole_actions(chosen, 0).index(join),
        join,
        _session(chosen),  # type: ignore[arg-type]
    )
    assert joined["undoable"] is True


def test_a_step_without_a_council_seat_has_no_preview() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13, arrakeen_scouts=True)
    rows = manager.legal_actions(str(summary["game_id"]), 0)["actions"]
    assert isinstance(rows, list) and rows
    assert all("subcommittee_preview" not in _obj(row) for row in rows)


def _scouts_session(**fields: Any) -> tuple[GameSessionManager, str, Any]:
    """A four-human Scouts game whose round 4 step resolves ``fields``."""

    manager = GameSessionManager()
    game_id = str(
        manager.create_game(("human",) * 4, game_seed=21, arrakeen_scouts=True)[
            "game_id"
        ]
    )
    session = manager._get(game_id)
    values: dict[str, Any] = {
        "round_number": 4,
        "first_player": 0,
        "decision_stack": (),
        "scouts_opening": True,
        "scouts_tasks": (),
    }
    values.update(fields)
    session.state = replace(session.state, **values)
    return manager, game_id, session


def test_view_names_the_scouts_item_being_resolved() -> None:
    """Feedback item 8: the decision panel names the item a Scouts decision
    belongs to, for the deciding seat and the waiting ones. It reads the
    public view.scouts_item (and the seat's own scouts_lines.item_id),
    which is empty once the step has opened the round's first turn."""
    manager, game_id, session = _scouts_session(
        scouts_item="private_stock", scouts_revealed=((4, "private_stock"),)
    )
    session.state = offer_scouts_choice(
        session.state, 0, "private_stock", source="round:4:scouts:private_stock:0"
    ).state

    for seat in (0, 1):
        assert manager.view(game_id, seat)["scouts_item"] == "private_stock"
    own = _obj(manager.legal_actions(game_id, 0)["scouts_lines"])
    assert own["frame"] == "scouts_choice" and own["item_id"] == "private_stock"
    assert manager.legal_actions(game_id, 1)["scouts_lines"] is None

    # The seat's choice is the item's last task: the step clears its cursor
    # and opens the First Player's turn.
    choice = ENGINE.legal_actions(session.state, 0)[0]
    session.state = ENGINE.apply(session.state, choice).state
    assert _obj(manager.summary(game_id)["decision"])["kind"] == "turn"
    for seat in (0, 1):
        assert manager.view(game_id, seat)["scouts_item"] == ""


def test_a_revealed_secret_line_names_its_event() -> None:
    """While due secret picks resolve, the step's cursor is "secrets"
    (rules/scouts_secrets.py SECRET_ITEM); a pick's line with a cost is the
    seat's own choice, and its scouts_lines name the pick's event."""
    manager, game_id, session = _scouts_session(
        scouts_item=SECRET_ITEM, scouts_revealed=((4, "private_stock"),)
    )
    # Covert Operation's third line: discard a card to recruit three troops.
    session.state = offer_secret_reward(
        session.state, 0, "covert_operation", 2, source="round:4:scouts:secret:0"
    ).state

    assert manager.view(game_id, 0)["scouts_item"] == SECRET_ITEM
    assert manager.view(game_id, 1)["scouts_item"] == SECRET_ITEM
    own = _obj(manager.legal_actions(game_id, 0)["scouts_lines"])
    assert own["frame"] == "scouts_choice"
    assert own["item_id"] == "covert_operation"
