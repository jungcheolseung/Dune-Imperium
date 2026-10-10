"""The play clock: game time and each seat's time holding control.

"게임 ui에 플레이한 시간이 기록되면 좋겠어. 이 게임 시작부터 시간이 얼마나
흘렀는지랑, 각 플레이어가 자기 차례에 시간을 얼마나 썼는지" and "ai 좌석도
구분 없이 시간 세자" (user, 2026-10-10, every recommendation accepted). A
seat's clock runs while it holds control, a chess clock: its own decisions,
its answers inside another seat's turn, the time before its turn-end press;
nobody's while a chance outcome or a stalled AI decision waits. Undo never
refunds time. The game time runs while the game is loaded and unfinished,
and a load continues from the saved totals. ``server/play_clock.py``.

Every test stands in its own monotonic clock (``sessions._monotonic``), so
the charges are exact.
"""

import json
import threading
from collections.abc import Callable
from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
)
from dune_imperium.records.problems import _RECORD_FIELDS
from dune_imperium.server import sessions as sessions_module
from dune_imperium.server.pacing import MAX_WAIT_SECONDS, TURN_BANNER_SECONDS
from dune_imperium.server.persistence import parse_save_document, read_saved_clock
from dune_imperium.server.play_clock import PlayClock
from dune_imperium.server.sessions import GameSessionManager, JsonObject

# Seats that follow a fixed table (see tests/server/test_turn_end.py), so the
# seeds below keep their shapes when the baseline heuristic is retuned.
HUMAN_FIRST = (
    "human",
    "heuristic_uprising_table",
    "heuristic_uprising_table",
    "heuristic_uprising_table",
)
FOUR_HUMANS = ("human",) * 4


class _Clock:
    """A monotonic clock the test moves by hand."""

    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    stand_in = _Clock()
    monkeypatch.setattr(sessions_module, "_monotonic", stand_in)
    return stand_in


def _obj(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _int(value: object) -> int:
    assert isinstance(value, int) and not isinstance(value, bool)
    return value


def _text(value: object) -> str:
    assert isinstance(value, str)
    return value


def _clock_of(summary: JsonObject) -> dict[str, object]:
    return _obj(summary["clock"])


def _seat_ms(summary: JsonObject) -> list[int]:
    values = _clock_of(summary)["seat_ms"]
    assert isinstance(values, list)
    return [_int(value) for value in values]


def _owner(summary: JsonObject) -> int:
    return _int(_obj(summary["decision"])["owner"])


# --- the holder and the totals ------------------------------------------


def test_a_new_game_starts_at_zero_with_the_first_decider_holding(
    clock: _Clock,
) -> None:
    manager = GameSessionManager()
    summary = manager.create_game(FOUR_HUMANS, game_seed=3)

    assert _clock_of(summary) == {
        "elapsed_ms": 0,
        "seat_ms": [0, 0, 0, 0],
        "running": _owner(summary),
        "spell_ms": 0,
        "narration": [],
        "counting": True,
        "known": True,
    }


def test_a_human_step_charges_its_seat_and_the_summary_waits_for_a_change(
    clock: _Clock,
) -> None:
    manager = GameSessionManager()
    summary = manager.create_game(FOUR_HUMANS, game_seed=3)
    game_id = _text(summary["game_id"])
    seat = _owner(summary)

    clock.advance(5.0)
    # Between changes the summary is the same, however long the wait.
    assert manager.summary(game_id) == summary

    after = manager.apply_action(game_id, seat, _int(summary["revision"]), 0)

    held = _clock_of(after)
    assert held["elapsed_ms"] == 5000
    assert _seat_ms(after)[seat] == 5000
    assert sum(_seat_ms(after)) == 5000
    # An Agent sent: the same seat goes on with its turn, its spell too.
    assert held["running"] == seat
    assert held["spell_ms"] == 5000
    clock.advance(1.0)
    assert manager.summary(game_id) == after


def test_the_snapshot_says_how_long_ago_the_clock_was_settled(clock: _Clock) -> None:
    manager = GameSessionManager()
    summary = manager.create_game(FOUR_HUMANS, game_seed=3)
    game_id = _text(summary["game_id"])
    seat = _owner(summary)

    clock.advance(2.5)
    snapshot = manager.snapshot(game_id, seat)
    seatless = manager.snapshot(game_id)

    assert snapshot["clock_age_ms"] == 2500
    assert seatless["clock_age_ms"] == 2500
    assert snapshot["summary"] == summary
    # The doorbell carries no clock: a ring compares only what changed.
    assert "clock" not in manager.doorbell(game_id)


def test_a_held_turn_end_stays_on_its_seat_until_the_press(clock: _Clock) -> None:
    # Seed 1 with the Leader draft: seat 0 picks before AI seats, and its
    # pick is held for the press (test_turn_end's
    # test_a_non_last_leader_pick_holds_before_the_next_picker).
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, leader_draft=True, game_seed=1)
    game_id = _text(summary["game_id"])
    assert _owner(summary) == 0

    clock.advance(3.0)
    summary = manager.apply_action(game_id, 0, _int(summary["revision"]), 0)

    assert summary["confirmation"] == 0
    assert _owner(summary) != 0
    held = _clock_of(summary)
    # The next picker is named, but the clock stays with the seat that must
    # press, its spell going on (the client's isMyTurn reads it the same).
    assert held["running"] == 0
    assert held["spell_ms"] == 3000

    clock.advance(4.0)
    summary = manager.confirm_turn(game_id, 0, _int(summary["revision"]))

    assert summary["confirmation"] is None
    assert _seat_ms(summary) == [7000, 0, 0, 0]
    # The AI picks ran inside the press and handed round 1 back to seat 0:
    # a new spell, as every hand-over starts one.
    assert _clock_of(summary)["running"] == 0
    assert _clock_of(summary)["spell_ms"] == 0
    assert _clock_of(summary)["elapsed_ms"] == 7000


def test_undo_refunds_no_time(clock: _Clock) -> None:
    manager = GameSessionManager()
    summary = manager.create_game(FOUR_HUMANS, game_seed=3)
    game_id = _text(summary["game_id"])
    seat = _owner(summary)
    revision = _int(summary["revision"])

    clock.advance(3.0)
    summary = manager.apply_action(game_id, seat, revision, 0)
    clock.advance(2.0)
    summary = manager.undo(game_id, seat, _int(summary["revision"]))

    assert _int(summary["revision"]) == revision
    assert _seat_ms(summary)[seat] == 5000
    assert _clock_of(summary)["running"] == seat
    assert _clock_of(summary)["elapsed_ms"] == 5000


# --- answers inside another seat's turn -----------------------------------

_HOLY_WAR = "imperium:holy_war:0"


def _holy_war_for_four_humans(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[GameSessionManager, str]:
    """Human seat 0 has sent Holy War to Assembly Hall and resolved its
    Agent box; every opponent is human and holds three garrison troops (the
    setup of test_turn_end's ``_holy_war_game``). The game starts from that
    position, so an undo rebuilds onto it."""

    owner = PlayerState(
        player_id=0, hand=(_HOLY_WAR,), deck=starting_deck_instance_ids(0)[:4]
    )
    state = GameState(
        config=RulesetConfig(bloodlines=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False)[:3],
        players=(
            owner,
            PlayerState(player_id=1),
            PlayerState(player_id=2),
            PlayerState(player_id=3),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    manager = GameSessionManager()
    summary = manager.create_game(FOUR_HUMANS, game_seed=0, bloodlines=True)
    game_id = _text(summary["game_id"])
    session = manager._get(game_id)
    monkeypatch.setattr(session.engine, "reset", lambda config, seed: state)
    session.state = state
    session.steps.clear()
    session.log.clear()
    session.open_units.clear()
    session.undo_floor = 0
    actions = manager.legal_actions(game_id, 0)["actions"]
    assert isinstance(actions, list)
    send = next(
        _obj(a)
        for a in actions
        if _obj(a)["action_id"] == "agent_turn"
        and _obj(_obj(a)["arguments"]).get("card_id") == _HOLY_WAR
        and _obj(_obj(a)["arguments"]).get("space_id") == "assembly_hall"
    )
    summary = manager.apply_action(game_id, 0, 0, _int(send["index"]))
    for action_id in ("resolve_board_effect", "resolve_agent_card_effect"):
        actions = manager.legal_actions(game_id, 0)["actions"]
        assert isinstance(actions, list)
        row = next(_obj(a) for a in actions if _obj(a)["action_id"] == action_id)
        summary = manager.apply_action(
            game_id, 0, _int(summary["revision"]), _int(row["index"])
        )
    return manager, game_id


def test_an_answer_inside_another_seats_turn_is_the_answering_seats_time(
    monkeypatch: pytest.MonkeyPatch, clock: _Clock
) -> None:
    manager, game_id = _holy_war_for_four_humans(monkeypatch)
    summary = manager.summary(game_id)
    assert _obj(summary["decision"])["kind"] == "opponent_unit_loss"
    assert _owner(summary) == 1
    start = _seat_ms(summary)
    assert _clock_of(summary)["running"] == 1

    clock.advance(2.0)
    summary = manager.apply_action(game_id, 1, _int(summary["revision"]), 0)

    assert _owner(summary) == 2
    assert _seat_ms(summary)[1] - start[1] == 2000
    assert _seat_ms(summary)[0] == start[0]
    assert _clock_of(summary)["running"] == 2

    # Seat 1 takes its answer back while seat 2 holds control: control moves
    # back to seat 1, seat 2 keeps the second it spent, seat 1 its two.
    rows = summary["undo"]
    assert isinstance(rows, list)
    window = {_int(_obj(row)["seat"]): _int(_obj(row)["steps"]) for row in rows}
    assert window.get(1) == 1
    clock.advance(1.0)
    summary = manager.undo(game_id, 1, _int(summary["revision"]))

    assert _owner(summary) == 1
    assert _clock_of(summary)["running"] == 1
    assert _seat_ms(summary)[1] - start[1] == 2000
    assert _seat_ms(summary)[2] - start[2] == 1000


# --- AI seats -------------------------------------------------------------


class _Wait(threading.Event):
    """A pace wait that passes at once, moving the stand-in clock instead."""

    def __init__(self, clock: _Clock) -> None:
        super().__init__()
        self._clock = clock

    def wait(self, timeout: float | None = None) -> bool:
        if timeout:
            self._clock.advance(timeout)
        return True


def _paced(
    monkeypatch: pytest.MonkeyPatch, clock: _Clock, seed: int = 5
) -> tuple[GameSessionManager, str]:
    """A paced game whose worker the test drives step by step (seed 5: AI
    seat 1 opens the first round)."""

    manager = GameSessionManager(pace_unit=1.0)
    monkeypatch.setattr(manager, "_kick_ai", lambda session: None)
    summary = manager.create_game(
        ("human", "heuristic", "heuristic", "heuristic"),
        game_seed=seed,
        ai_pace="normal",
    )
    game_id = _text(summary["game_id"])
    manager._get(game_id).pace_wake = _Wait(clock)
    return manager, game_id


def test_a_thinking_seat_holds_control_its_pace_wait_included(
    monkeypatch: pytest.MonkeyPatch, clock: _Clock
) -> None:
    manager, game_id = _paced(monkeypatch, clock)
    session = manager._get(game_id)
    summary = manager.summary(game_id)
    assert summary["thinking"] == 1
    assert _clock_of(summary)["running"] == 1

    clock.advance(0.5)
    asked = clock.now
    assert manager._ai_step(session) is True

    # Thinking, then waiting at its turn start for its banner (the stand-in
    # pace wait moved the clock): all of it seat 1's.
    wait = clock.now - asked
    assert wait == pytest.approx(TURN_BANNER_SECONDS)
    summary = manager.summary(game_id)
    assert _seat_ms(summary)[1] == pytest.approx(500 + 1000 * wait, abs=1)
    assert sum(_seat_ms(summary)) == _seat_ms(summary)[1]


def test_a_failed_worker_step_stops_every_seat_clock(
    monkeypatch: pytest.MonkeyPatch, clock: _Clock
) -> None:
    manager, game_id = _paced(monkeypatch, clock)
    session = manager._get(game_id)
    clock.advance(1.0)

    manager._end_failed_ai_step(session)

    summary = manager.summary(game_id)
    stalled = _clock_of(summary)
    assert summary["thinking"] is None and _owner(summary) == 1
    assert stalled["running"] is None
    assert _seat_ms(summary)[1] == 1000
    clock.advance(30.0)
    manager.connect(game_id)  # a change, so the clock settles
    later = manager.summary(game_id)
    # Nobody's clock runs while nothing answers; the game time still does.
    assert _seat_ms(later) == _seat_ms(summary)
    assert _clock_of(later)["elapsed_ms"] == 31_000


def test_the_tables_narration_of_an_ai_step_is_that_seats_time(
    monkeypatch: pytest.MonkeyPatch, clock: _Clock
) -> None:
    # A paced game: once the worker applies the last AI answer before seat
    # 0's decision, the tables still show it for its cue length (cue_clock);
    # seat 0's clock starts only after that, and the wait is the AI seat's.
    # The worker waits for every cue before the next answer, so only the
    # last answer's own cues are left when seat 0 takes over; an Agent
    # turn's last step (its end) shows none, so every step here shows two
    # seconds of them.
    monkeypatch.setattr(
        sessions_module, "cue_seconds", lambda events: 2.0 if events else 0.0
    )
    manager, game_id = _paced(monkeypatch, clock)
    session = manager._get(game_id)
    for _ in range(300):
        summary = manager.summary(game_id)
        if summary["thinking"] is None:
            break
        manager._ai_step(session)
    else:
        raise AssertionError("the AI seats never handed over")
    assert _owner(summary) == 0
    held = _clock_of(summary)
    assert held["running"] == 0
    narration = held["narration"]
    assert isinstance(narration, list) and narration, "an Agent card's cue"
    pieces = [(_int(seat), _int(ms)) for seat, ms in narration]
    assert all(seat != 0 for seat, _ in pieces)
    total = sum(ms for _, ms in pieces)
    assert total == pytest.approx(1000 * (session.cue_clock - clock.now), abs=2)
    assert total <= 1000 * MAX_WAIT_SECONDS

    before = _seat_ms(summary)
    clock.advance(total / 1000 + 3.0)
    summary = manager.apply_action(game_id, 0, _int(summary["revision"]), 0)

    gained = [after - was for after, was in zip(_seat_ms(summary), before, strict=True)]
    assert gained[0] == pytest.approx(3000, abs=2)
    for seat, ms in pieces:
        assert gained[seat] >= ms - 2


def test_an_instant_game_narrates_its_ai_run_before_the_humans_clock(
    clock: _Clock,
) -> None:
    # Instant: the AI seats answer inside the human's request and the
    # browser narrates them afterwards, at full cue length (effects.js
    # cueScale), each AI seat's turn banner included.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=5)
    game_id = _text(summary["game_id"])
    held = _clock_of(summary)
    # The AI moves before the first human decision were never narrated: a
    # page that opens the game takes them as its baseline.
    assert held["narration"] == []
    assert held["running"] == 0
    session = manager._get(game_id)
    for _ in range(40):
        clock.advance(1.0)
        before = _seat_ms(summary)
        if summary["confirmation"] == 0:
            summary = manager.confirm_turn(game_id, 0, _int(summary["revision"]))
        else:
            summary = manager.apply_action(game_id, 0, _int(summary["revision"]), 0)
        # Each second before the step was seat 0's, or narration still due.
        assert sum(_seat_ms(summary)) - sum(before) == pytest.approx(1000, abs=2)
        narration = _clock_of(summary)["narration"]
        assert isinstance(narration, list)
        if narration and _clock_of(summary)["running"] == 0:
            break
    else:
        raise AssertionError("no AI run was narrated before seat 0")
    pieces = [(_int(seat), _int(ms)) for seat, ms in narration]
    assert {seat for seat, _ in pieces} <= {1, 2, 3}
    assert sum(ms for _, ms in pieces) == pytest.approx(
        1000 * (session.narration_clock - clock.now), abs=len(pieces)
    )

    # Seat 0 acts a second in, while the tables still show the first AI
    # seat's turn: that second was the AI seat's, and the rest of the
    # narration is dropped, since seat 0 was plainly not waiting for it.
    first_seat, first_ms = pieces[0]
    assert first_ms > 1000
    before = _seat_ms(summary)
    acted = clock.now + 1.0
    clock.advance(1.0)
    if summary["confirmation"] == 0:
        summary = manager.confirm_turn(game_id, 0, _int(summary["revision"]))
    else:
        summary = manager.apply_action(game_id, 0, _int(summary["revision"]), 0)
    gained = [after - was for after, was in zip(_seat_ms(summary), before, strict=True)]
    assert gained[first_seat] == 1000
    assert sum(gained) == 1000
    assert all(start >= acted for _, start, _ in session.clock.narration)


# --- finish, un-finish, save and load -----------------------------------


def test_a_finished_game_stops_the_clock_and_an_undo_that_unfinishes_resumes_it(
    monkeypatch: pytest.MonkeyPatch, clock: _Clock
) -> None:
    # The stand-in finished state below has no Endgame to rank.
    monkeypatch.setattr(sessions_module, "final_standings", lambda state: ())
    manager = GameSessionManager()
    summary = manager.create_game(FOUR_HUMANS, game_seed=3)
    game_id = _text(summary["game_id"])
    seat = _owner(summary)
    session = manager._get(game_id)
    clock.advance(1.0)
    summary = manager.apply_action(game_id, seat, _int(summary["revision"]), 0)

    # Stand in a finished state for that step, as if it ended the game.
    live = session.state
    session.state = replace(live, phase=GamePhase.FINISHED)
    clock.advance(2.0)
    connection = manager.connect(game_id)
    finished = manager.summary(game_id)
    assert finished["finished"] is True
    assert _clock_of(finished)["running"] is None
    assert _clock_of(finished)["counting"] is False
    assert _clock_of(finished)["elapsed_ms"] == 3000

    clock.advance(10.0)
    manager.disconnect(game_id, connection)
    assert _clock_of(manager.summary(game_id))["elapsed_ms"] == 3000
    assert _seat_ms(manager.summary(game_id))[seat] == 3000

    summary = manager.undo(game_id, seat, _int(finished["revision"]))
    assert summary["finished"] is False
    assert _clock_of(summary)["counting"] is True
    assert _clock_of(summary)["running"] == seat
    clock.advance(4.0)
    manager.connect(game_id)
    assert _clock_of(manager.summary(game_id))["elapsed_ms"] == 7000


def test_a_save_carries_the_clock_and_a_load_continues_it(clock: _Clock) -> None:
    manager = GameSessionManager()
    summary = manager.create_game(FOUR_HUMANS, game_seed=3)
    game_id = _text(summary["game_id"])
    seat = _owner(summary)
    clock.advance(3.0)
    summary = manager.apply_action(game_id, seat, _int(summary["revision"]), 0)
    clock.advance(2.0)

    document = manager.save_document(game_id)

    # Folded in at the save, the running interval included; the summary is
    # untouched (no change happened).
    expected = [0, 0, 0, 0]
    expected[seat] = 5000
    assert document["clock"] == {"elapsed_ms": 5000, "seat_ms": expected, "known": True}
    assert manager.summary(game_id) == summary
    # The replay of a load counts nothing: the time it takes is no one's.
    clock.advance(100.0)
    restored = manager.restore_game(json.loads(json.dumps(document)))
    assert _clock_of(restored)["seat_ms"] == expected
    assert _clock_of(restored)["elapsed_ms"] == 5000
    assert _clock_of(restored)["known"] is True
    assert _clock_of(restored)["running"] == seat
    clock.advance(1.5)
    again = manager.save_document(_text(restored["game_id"]))
    expected[seat] = 6500
    assert _obj(again["clock"])["seat_ms"] == expected


@pytest.mark.parametrize(
    "damage",
    [
        pytest.param(lambda document: document.pop("clock"), id="absent"),
        pytest.param(
            lambda document: document.update(clock={"elapsed_ms": -1}), id="malformed"
        ),
        pytest.param(
            lambda document: document.update(
                clock={"elapsed_ms": 5, "seat_ms": [1, 2], "known": True}
            ),
            id="wrong_seats",
        ),
        pytest.param(
            # Too large to become seconds at all: still no reason to refuse.
            lambda document: document.update(
                clock={"elapsed_ms": 10**400, "seat_ms": [0, 0, 0, 0], "known": True}
            ),
            id="huge",
        ),
    ],
)
def test_a_save_without_a_usable_clock_loads_and_counts_from_the_load(
    clock: _Clock, damage: Callable[[JsonObject], object]
) -> None:
    manager = GameSessionManager()
    summary = manager.create_game(FOUR_HUMANS, game_seed=3)
    game_id = _text(summary["game_id"])
    clock.advance(3.0)
    document = manager.save_document(game_id)
    damage(document)

    restored = manager.restore_game(document)

    loaded = _clock_of(restored)
    assert loaded["known"] is False
    assert loaded["elapsed_ms"] == 0 and _seat_ms(restored) == [0, 0, 0, 0]
    # It saves as unknown in turn, so a later load still says so.
    clock.advance(2.0)
    again = manager.save_document(_text(restored["game_id"]))
    assert _obj(again["clock"])["known"] is False
    assert _obj(again["clock"])["elapsed_ms"] == 2000


def test_the_clock_stays_out_of_records(clock: _Clock) -> None:
    # Timing is never record data (decision 7, 2026-10-10): the parser the
    # records read saves with ignores it, and a problem suite copies a fixed
    # list of save fields.
    manager = GameSessionManager()
    summary = manager.create_game(FOUR_HUMANS, game_seed=3)
    clock.advance(3.0)
    document = manager.save_document(_text(summary["game_id"]))
    assert "clock" in document

    parsed = parse_save_document(document, check_versions=False)

    assert "clock" not in _RECORD_FIELDS
    assert not hasattr(parsed, "clock")
    assert read_saved_clock(document, 4) is not None


# --- the clock itself -----------------------------------------------------


def test_narration_pieces_are_charged_in_order_then_the_holder_runs() -> None:
    clock = PlayClock(seats=4)
    clock.start(10.0, holder=2, grace=False, counting=True)
    clock.narrate(1, 10.0, 12.0)
    clock.narrate(3, 11.0, 13.0)  # queued after seat 1's
    clock.settle(10.5, holder=0, grace=True, counting=True)

    payload = clock.payload()
    assert payload["running"] == 0
    assert payload["narration"] == [[1, 1500], [3, 1000]]
    # Seat 2 held the first half second; then seat 1's segment, seat 3's,
    # and seat 0's own second.
    assert clock.totals(14.0) == (4.0, (1.0, 1.5, 0.5, 1.0))

    clock.settle(14.0, holder=1, grace=False, counting=True)
    assert clock.seat_seconds == [1.0, 1.5, 0.5, 1.0]
    assert clock.payload()["narration"] == []
    assert clock.spell == 0.0


def test_a_gap_between_narration_segments_is_the_holders() -> None:
    clock = PlayClock(seats=4)
    clock.start(0.0, holder=0, grace=True, counting=True)
    clock.narrate(1, 0.0, 1.0)
    clock.narrate(2, 3.0, 4.0)

    assert clock.payload()["narration"] == [[1, 1000], [0, 2000], [2, 1000]]
    elapsed, seats = clock.totals(6.0)
    assert elapsed == 6.0
    assert seats == (4.0, 1.0, 1.0, 0.0)


def test_a_chance_step_extends_only_a_pending_ai_segment() -> None:
    clock = PlayClock(seats=4)
    clock.start(0.0, holder=0, grace=True, counting=True)
    clock.extend_narration(0.0, 1.0)
    assert clock.narration == []
    clock.narrate(3, 0.0, 2.0)
    clock.extend_narration(2.0, 3.6)
    assert clock.narration == [(3, 0.0, 3.6)]
    clock.extend_narration(5.0, 6.0)  # after it ended: nobody's grace
    assert clock.narration == [(3, 0.0, 3.6)]
