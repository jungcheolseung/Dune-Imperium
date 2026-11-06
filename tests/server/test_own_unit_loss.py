"""A loss a seat chose to pay is its own unit on the server (cloud engine
review finding 4).

The original game's Fremen Exchange: "Holy War(OQ-036 (a))처럼 잃는 좌석이
zone(garrison/Conflict)과 유닛 종류 ... 를 고른다" (OQ-163), so its troop line
opens the opponents' unit-loss window for the seat itself
(``unit_loss.own_unit_loss_frame``). The server read that window by kind as an
answer inside another seat's unit (``turn_end.INTERRUPT_KINDS``): the seat's
own unit outside the turns (``own_unit_outside_turns``) was false, and a chance
outcome right after the click would have closed its undo window
(``sessions._action_is_undoable``). The engine now marks the window as the
seat's own (``unit_loss.OWN_LOSS_KEY``), and the server treats it as the
seat's unit: undoable, held until its turn end, like the OQ-164 collect
clicks ("드러내는 것이 없는 "받기"는 무를 수 있고, 서버가 그 좌석의 "턴 종료"까지
붙든다", OQ-164).
"""

from dataclasses import replace

from tests.unit.rules import test_scouts_original_mechanisms as mechanisms

from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.state import GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.unit_loss import frame_is_own_loss, opponent_unit_loss_frames
from dune_imperium.server.sessions import GameSessionManager, _action_is_undoable
from dune_imperium.server.turn_end import (
    answers_another_unit,
    own_unit_outside_turns,
    unit_seat,
)

# Four people: the original game seats no Uprising table AI.
HUMANS = ("human",) * 4
_ENGINE = UprisingRulesEngine()


def _rows(value: object) -> list[dict[str, object]]:
    assert isinstance(value, list)
    return [row for row in value if isinstance(row, dict)]


def _fremen_exchange_window() -> tuple[GameSessionManager, str, GameState]:
    """An original game's round-5 Scouts step with Fremen Exchange drawn:
    seat 0 (the First Player, two garrison troops) took the troop line, so
    its own loss window is open (the rules tests' position, served by a
    session of the same ruleset)."""

    state = mechanisms._exchange(mechanisms._units(troops_garrison=2))
    state = mechanisms._act(state, "scouts_choose_option", option=0)
    assert state.decision_stack[-1].kind == FrameKind.OPPONENT_UNIT_LOSS
    manager = GameSessionManager()
    summary = manager.create_game(
        HUMANS,
        game_seed=0,
        base_game="imperium",
        arrakeen_scouts=True,
        first_player_seat_zero=True,
    )
    game_id = str(summary["game_id"])
    assert manager._get(game_id).state.config == state.config
    manager._get(game_id).state = state
    return manager, game_id, state


def test_the_engine_marks_a_loss_the_seat_chose_as_its_own() -> None:
    _, _, state = _fremen_exchange_window()
    assert frame_is_own_loss(state.decision_stack[-1])
    # Holy War's loss is another seat's effect: never marked.
    holy_war = opponent_unit_loss_frames(state, 1, source="test", printer="test")
    pushed = holy_war.state.decision_stack[len(state.decision_stack) :]
    assert [frame.kind for frame in pushed] == [FrameKind.OPPONENT_UNIT_LOSS] * 3
    assert not any(frame_is_own_loss(frame) for frame in pushed)


def test_the_server_reads_the_own_loss_window_as_the_seats_own_unit() -> None:
    _, _, state = _fremen_exchange_window()
    assert unit_seat(state) == 0
    assert not answers_another_unit(state, 0)
    assert own_unit_outside_turns(state, 0)
    # An opponent's loss window above it is still an answer.
    answer = replace(
        state,
        decision_stack=(
            *state.decision_stack,
            DecisionFrame(
                kind=FrameKind.OPPONENT_UNIT_LOSS,
                frame_id="test:unit_loss:1",
                decision=PlayerDecision(owner=1, prompt="Choose a unit to lose"),
                context=(("player", 1), ("printer", "test"), ("source", "test")),
            ),
        ),
    )
    assert answers_another_unit(answer, 1)
    assert not own_unit_outside_turns(answer, 1)


def test_the_loss_click_is_undoable_and_held_until_the_turn_end() -> None:
    manager, game_id, _ = _fremen_exchange_window()
    summary = manager.summary(game_id)
    rows = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert [row["action_id"] for row in rows] == ["lose_unit"]
    assert rows[0]["undoable"] is True
    assert rows[0]["sent_by_turn_end"] is False
    index = rows[0]["index"]
    revision = summary["revision"]
    assert isinstance(index, int) and isinstance(revision, int)
    summary = manager.apply_action(game_id, seat=0, revision=revision, index=index)
    assert manager._get(game_id).state.players[0].troops_garrison == 1
    held = [row for row in _rows(summary["undo"]) if row["seat"] == 0]
    assert held == [{"seat": 0, "steps": 1}]


def test_a_chance_right_after_the_loss_click_leaves_it_undoable() -> None:
    """No item follows Fremen Exchange in a Scouts step today (events end
    rounds 4 to 7, docs/rules/arrakeen-scouts.md 3), so the outcome is made
    by hand: a chance pending after the click comes after the seat's unit and
    waits behind its press (``turn_end.unit_over``), so the click stays
    undoable. Read as an answer inside another seat's unit it was not."""

    manager, game_id, state = _fremen_exchange_window()
    session = manager._get(game_id)
    click = DomainAction(
        action_id="lose_unit", actor=0, arguments=(("zone", "garrison"),)
    )
    after = apply_whole(_ENGINE, state, click)
    draw = DecisionFrame(
        kind=FrameKind.SCOUTS_DRAW,
        frame_id="test:draw",
        decision=ChanceDecision(
            decision_id="test:draw", prompt="Draw a Scouts item", options=("a", "b")
        ),
    )
    pending = replace(after.state, decision_stack=(draw,))
    outcome = RuleResult(state=pending, events=after.events)
    assert _action_is_undoable(session, click, outcome)
