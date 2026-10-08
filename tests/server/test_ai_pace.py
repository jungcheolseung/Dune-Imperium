"""AI pace: a paced game's AI seats answer on the worker (``server/pacing.py``).

A heuristic or app AI seat answers in milliseconds, so an instant game
plays a whole run of AI decisions inside the request that handed them the
game. A paced game hands each AI decision to the game's worker instead,
which applies it once the tables have had the time to show the public
events before it ("진짜 게임처럼", user, 2026-10-08). Pacing changes when
an answer is applied, never which answer: a paced game reaches the states
an instant one does.
"""

import json

import pytest

from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import canonical_state_hash
from dune_imperium.server import sessions as sessions_module
from dune_imperium.server.access import AccessMode, Credentials
from dune_imperium.server.pacing import (
    BANNER_SECONDS,
    CARD_CUE_SECONDS,
    MAX_WAIT_SECONDS,
    RESULT_SECONDS,
    TURN_BANNER_SECONDS,
    cue_seconds,
)
from dune_imperium.server.persistence import SaveError
from dune_imperium.server.session_log import LoggedStep
from dune_imperium.server.sessions import (
    AdminAccessError,
    GameSessionManager,
    JsonObject,
    SessionError,
)

SEATS = ("human", "heuristic", "heuristic", "heuristic")
SEED = 5  # seat 1 opens the first round, so the AI seats move at once


def _text(value: object) -> str:
    assert isinstance(value, str)
    return value


def _int(value: object) -> int:
    assert isinstance(value, int)
    return value


def _play(manager: GameSessionManager, summary: JsonObject, steps: int) -> JsonObject:
    """Seat 0 confirms its turn ends and otherwise takes legal action 0."""

    game_id = _text(summary["game_id"])
    for _ in range(steps):
        manager.wait_for_ai(game_id)
        summary = manager.summary(game_id)
        if summary["finished"]:
            break
        revision = _int(summary["revision"])
        if summary["confirmation"] == 0:
            summary = manager.confirm_turn(game_id, seat=0, revision=revision)
        else:
            summary = manager.apply_action(game_id, seat=0, revision=revision, index=0)
    manager.wait_for_ai(game_id)
    return manager.summary(game_id)


def test_a_paced_game_answers_its_ai_seats_on_the_worker() -> None:
    manager = GameSessionManager(pace_unit=0.0)
    summary = manager.create_game(SEATS, game_seed=SEED, ai_pace="normal")

    assert summary["ai_pace"] == "normal"
    assert summary["thinking"] == 1
    manager.wait_for_ai(_text(summary["game_id"]))
    assert manager.summary(_text(summary["game_id"]))["thinking"] is None


def test_pacing_changes_when_an_ai_answers_never_which() -> None:
    instant = GameSessionManager()
    paced = GameSessionManager(pace_unit=0.0)
    one = _play(instant, instant.create_game(SEATS, game_seed=SEED), 120)
    two = _play(paced, paced.create_game(SEATS, game_seed=SEED, ai_pace="fast"), 120)

    assert one["round_number"] == two["round_number"]
    states = [
        manager._sessions[_text(summary["game_id"])].state
        for manager, summary in ((instant, one), (paced, two))
    ]
    assert canonical_state_hash(states[0]) == canonical_state_hash(states[1])


def test_a_game_without_a_human_seat_is_never_paced() -> None:
    manager = GameSessionManager(pace_unit=0.0)
    summary = manager.create_game(
        ("heuristic",) * 4, game_seed=SEED, ai_pace="normal"
    )

    assert summary["finished"] is True
    assert summary["thinking"] is None


def test_the_tables_need_time_only_for_public_cues() -> None:
    def event(kind: str, visible_to: tuple[int, ...] | None = None) -> GameEvent:
        return GameEvent(event_id=kind, kind=kind, visible_to=visible_to)

    assert cue_seconds((event("agent_placed"), event("conflict_revealed"))) == (
        pytest.approx(CARD_CUE_SECONDS + BANNER_SECONDS)
    )
    # One result board for the whole standing, however many seats it lists.
    standing = tuple(
        GameEvent(event_id=f"s{seat}", kind="combat_standing") for seat in range(3)
    )
    assert cue_seconds(standing) == pytest.approx(RESULT_SECONDS)
    # A private event never paces anyone: the delay would tell the table.
    assert cue_seconds((event("intrigue_played", visible_to=(2,)),)) == 0
    assert cue_seconds((event("cards_drawn"),)) == 0


def test_an_ai_turn_start_waits_for_the_cues_before_it_and_its_banner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [100.0]
    monkeypatch.setattr(sessions_module, "_monotonic", lambda: now[0])
    manager = GameSessionManager(pace_unit=1.0)
    # The worker is left unstarted: this asks the pace itself.
    monkeypatch.setattr(manager, "_kick_ai", lambda session: None)
    summary = manager.create_game(SEATS, game_seed=SEED, ai_pace="normal")
    session = manager._sessions[_text(summary["game_id"])]

    with session.lock:
        assert session.thinking == 1
        session.cue_clock = 101.0
        ready = sessions_module._pace_ready_locked(session, 1)
        # The cues still on the tables, then seat 1's turn banner.
        assert ready == pytest.approx(101.0 + TURN_BANNER_SECONDS)
        assert session.cue_clock == pytest.approx(ready)
        # The same turn start asked again (a Plot played at it) waits for
        # no second banner.
        assert sessions_module._pace_ready_locked(session, 1) == pytest.approx(ready)
        # Nothing waits longer than the cap, however much piled up.
        session.cue_clock = 1000.0
        assert sessions_module._pace_ready_locked(session, 1) == pytest.approx(
            100.0 + MAX_WAIT_SECONDS
        )


def test_the_pace_is_saved_and_an_older_save_takes_the_servers_default() -> None:
    manager = GameSessionManager(pace_unit=0.0, default_ai_pace="fast")
    summary = _play(
        manager, manager.create_game(SEATS, game_seed=SEED, ai_pace="normal"), 10
    )
    document = manager.save_game(_text(summary["game_id"]))
    assert document["ai_pace"] == "normal"

    restored = manager.restore_game(json.loads(json.dumps(document)))
    assert restored["ai_pace"] == "normal"

    older = {key: value for key, value in document.items() if key != "ai_pace"}
    assert manager.restore_game(older)["ai_pace"] == "fast"

    with pytest.raises(SaveError, match="ai_pace"):
        manager.restore_game({**document, "ai_pace": "slow"})


def test_the_pace_of_a_running_game_can_change() -> None:
    manager = GameSessionManager(pace_unit=0.0)
    summary = manager.create_game(SEATS, game_seed=SEED, ai_pace="normal")
    game_id = _text(summary["game_id"])
    manager.wait_for_ai(game_id)

    assert manager.set_ai_pace(game_id, "instant")["ai_pace"] == "instant"
    summary = _play(manager, manager.summary(game_id), 30)
    assert summary["ai_pace"] == "instant"
    with pytest.raises(SessionError, match="pace"):
        manager.set_ai_pace(game_id, "slow")
    with pytest.raises(SessionError, match="pace"):
        manager.create_game(SEATS, ai_pace="slow")


def test_only_the_host_sets_the_pace_of_a_remote_game() -> None:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key="key")
    host = Credentials(admin_key="key")
    summary = manager.create_game(SEATS, game_seed=SEED, credentials=host)
    game_id = _text(summary["game_id"])

    with pytest.raises(AdminAccessError):
        manager.set_ai_pace(game_id, "fast")
    assert manager.set_ai_pace(game_id, "fast", credentials=host)["ai_pace"] == "fast"


class _Wake:
    """A stand-in for a session's ``pace_wake``: records, never blocks."""

    def __init__(self) -> None:
        self.waits: list[float] = []
        self.sets = 0

    def clear(self) -> None:
        pass

    def set(self) -> None:
        self.sets += 1

    def wait(self, timeout: float) -> bool:
        self.waits.append(timeout)
        return False


def test_the_worker_waits_for_the_tables_and_every_step_adds_its_cues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sessions_module, "_monotonic", lambda: 100.0)
    manager = GameSessionManager(pace_unit=1.0)
    # The worker is driven by hand here, one answer at a time.
    monkeypatch.setattr(manager, "_kick_ai", lambda session: None)
    summary = manager.create_game(SEATS, game_seed=SEED, ai_pace="normal")
    game_id = _text(summary["game_id"])
    session = manager._sessions[game_id]
    wake = _Wake()
    session.pace_wake = wake  # type: ignore[assignment]

    for _ in range(2):
        with session.lock:
            seat = session.thinking
            assert seat is not None
            turn = sessions_module._turn_start_key(session, seat)
            new_turn = turn not in (None, session.paced_turn)
            banner = TURN_BANNER_SECONDS if new_turn else 0
            cap = 100.0 + MAX_WAIT_SECONDS
            ready = min(max(100.0, session.cue_clock) + banner, cap)
            logged = len(session.log)
        assert manager._ai_step(session) is True
        # The answer waited for the cues on the tables and its turn banner...
        assert wake.waits[-1] == pytest.approx(ready - 100.0)
        assert wake.waits[-1] > 0
        # ...and what it logged is on the tables after it.
        with session.lock:
            shown = sum(
                (
                    cue_seconds(entry.events)
                    for entry in session.log[logged:]
                    if isinstance(entry, LoggedStep)
                ),
                0.0,
            )
            assert session.cue_clock == pytest.approx(ready + shown)

    manager.set_ai_pace(game_id, "fast")
    assert wake.sets == 1
    manager.delete(game_id)
    assert wake.sets == 2


def test_a_failing_paced_ai_seat_fails_its_step_and_the_game_still_loads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Only a search seat falls back on another answer (a load retraces it);
    # a paced heuristic seat that fails records nothing, as inside a request.
    def fail(*args: object) -> object:
        raise RuntimeError("the agent failed")

    monkeypatch.setattr(sessions_module, "_choose", fail)
    manager = GameSessionManager(pace_unit=0.0)
    summary = manager.create_game(SEATS, game_seed=SEED, ai_pace="normal")
    game_id = _text(summary["game_id"])
    manager.wait_for_ai(game_id)

    after = manager.summary(game_id)
    assert after["thinking"] is None
    assert after["log_count"] == summary["log_count"]
    decision = after["decision"]
    assert isinstance(decision, dict) and decision["owner"] == 1
    monkeypatch.undo()
    restored = manager.restore_game(manager.save_game(game_id))
    manager.wait_for_ai(_text(restored["game_id"]))
    later = manager.summary(_text(restored["game_id"]))
    assert _int(later["log_count"]) > _int(summary["log_count"])
