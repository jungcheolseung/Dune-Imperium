"""Tests for the play server's snapshot call (M14 slice 2): one lock, one
response replacing the separate summary/view/actions/log reads a refresh
used to make in sequence (``docs/multiplayer-design.md`` section 4.6)."""

import json
from dataclasses import dataclass

import pytest

from dune_imperium.server.access import ANONYMOUS, AccessMode, Credentials
from dune_imperium.server.sessions import (
    GameSessionManager,
    SeatAccessError,
    SessionError,
    UnknownGameError,
)

HUMAN_FIRST = ("human", "heuristic", "heuristic", "heuristic")
TWO_HUMANS = ("human", "human", "heuristic", "heuristic")


def _obj(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _rows(value: object) -> list[dict[str, object]]:
    assert isinstance(value, list)
    return [_obj(item) for item in value]


def _int(value: object) -> int:
    assert isinstance(value, int)
    return value


def _text(value: object) -> str:
    assert isinstance(value, str)
    return value


# --- shape: seatless vs. seated -------------------------------------------


def test_a_snapshot_without_a_seat_is_exactly_summary_and_you() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])

    snapshot = manager.snapshot(game_id)

    assert set(snapshot) == {"summary", "you"}
    assert snapshot["summary"] == manager.summary(game_id)
    assert snapshot["you"] == manager.identify(game_id)
    json.dumps(snapshot)


def test_a_seat_snapshot_has_the_five_keys_and_equals_the_separate_calls() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])
    assert _obj(summary["decision"])["owner"] == 0

    snapshot = manager.snapshot(game_id, 0)

    assert set(snapshot) == {"summary", "you", "view", "actions", "log"}
    assert snapshot["summary"] == manager.summary(game_id)
    assert snapshot["you"] == manager.identify(game_id)
    assert snapshot["view"] == manager.view(game_id, 0)
    assert snapshot["actions"] == manager.legal_actions(game_id, 0)
    log = _obj(snapshot["log"])
    assert _rows(log["entries"]) == _rows(manager.log(game_id, 0, after=0)["entries"])

    revision = _obj(snapshot["summary"])["revision"]
    assert _obj(snapshot["view"])["revision"] == revision
    assert _obj(snapshot["actions"])["revision"] == revision
    json.dumps(snapshot)


# --- actions is None when the seat does not decide ------------------------


def test_actions_are_none_for_a_seat_that_does_not_own_the_decision() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(TWO_HUMANS, game_seed=13)
    game_id = _text(summary["game_id"])
    assert _obj(summary["decision"])["owner"] == 0

    owner_snapshot = manager.snapshot(game_id, 0)
    other_snapshot = manager.snapshot(game_id, 1)

    assert owner_snapshot["actions"] is not None
    assert other_snapshot["actions"] is None


def test_actions_are_none_while_the_seat_awaits_turn_end_confirmation() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = _text(summary["game_id"])

    for _ in range(200):
        if summary["confirmation"] == 0:
            break
        summary = manager.apply_action(
            game_id, seat=0, revision=_int(summary["revision"]), index=0
        )
    else:
        raise AssertionError("seat 0 never paused for a turn-end confirmation")

    snapshot = manager.snapshot(game_id, 0)

    assert snapshot["actions"] is None
    assert _obj(snapshot["summary"])["confirmation"] == 0


# --- incremental log tail ---------------------------------------------------


def test_the_log_tail_after_one_action_matches_a_direct_log_call() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])

    before = manager.snapshot(game_id, 0)
    before_log = _obj(before["log"])
    old_count = _int(before_log["count"])
    old_epoch = _text(before_log["epoch"])
    old_entries = _rows(before_log["entries"])

    manager.apply_action(
        game_id, seat=0, revision=_int(_obj(before["summary"])["revision"]), index=0
    )

    after = manager.snapshot(game_id, 0, log_after=old_count, log_epoch=old_epoch)
    after_log = _obj(after["log"])

    assert after_log["from"] == old_count
    assert _int(after_log["count"]) > old_count
    tail = _rows(after_log["entries"])
    assert tail == _rows(manager.log(game_id, 0, after=old_count)["entries"])
    assert old_entries + tail == _rows(manager.log(game_id, 0)["entries"])


def test_a_stale_epoch_after_an_undo_resends_everything_with_the_flag() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])

    applied = manager.apply_action(
        game_id, seat=0, revision=_int(summary["revision"]), index=0
    )
    assert _rows(applied["undo"]), "the step must still be undoable for this test"
    stale = _obj(manager.snapshot(game_id, 0)["log"])
    old_epoch = _text(stale["epoch"])
    old_count = _int(stale["count"])

    manager.undo(game_id, seat=0, revision=_int(applied["revision"]))

    resent = _obj(
        manager.snapshot(game_id, 0, log_after=old_count, log_epoch=old_epoch)["log"]
    )

    assert resent["from"] == 0
    assert resent["epoch"] != old_epoch
    entries = _rows(resent["entries"])
    assert len(entries) == resent["count"] == old_count + 1
    assert entries[-1] == {
        "index": old_count,
        "type": "undo",
        "seat": 0,
        "count": 1,
    }
    assert entries[-2]["type"] == "action" and entries[-2]["undone"] is True


def test_no_epoch_resends_everything_regardless_of_the_cursor() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])
    manager.apply_action(game_id, seat=0, revision=_int(summary["revision"]), index=0)

    snapshot = manager.snapshot(game_id, 0, log_after=3)

    log = _obj(snapshot["log"])
    assert log["from"] == 0
    assert len(_rows(log["entries"])) == log["count"]


def test_the_epoch_differs_by_seat() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(TWO_HUMANS, game_seed=13)
    game_id = _text(summary["game_id"])

    seat0_log = _obj(manager.snapshot(game_id, 0)["log"])
    seat1_log = _obj(manager.snapshot(game_id, 1)["log"])
    assert seat0_log["epoch"] != seat1_log["epoch"]

    cross = _obj(
        manager.snapshot(
            game_id,
            1,
            log_after=_int(seat0_log["count"]),
            log_epoch=_text(seat0_log["epoch"]),
        )["log"]
    )
    assert cross["from"] == 0


# --- cursor and access errors ----------------------------------------------


def test_a_negative_cursor_is_always_a_session_error() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])

    with pytest.raises(SessionError, match="out of range"):
        manager.snapshot(game_id, 0, log_after=-1)
    with pytest.raises(SessionError, match="out of range"):
        manager.snapshot(game_id, 0, log_after=-1, log_epoch="whatever")


def test_a_cursor_past_the_log_with_the_current_epoch_is_a_session_error() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])
    current = _obj(manager.snapshot(game_id, 0)["log"])
    count = _int(current["count"])
    epoch = _text(current["epoch"])

    with pytest.raises(SessionError, match="out of range"):
        manager.snapshot(game_id, 0, log_after=count + 1, log_epoch=epoch)

    exact = _obj(manager.snapshot(game_id, 0, log_after=count, log_epoch=epoch)["log"])
    assert exact["from"] == count
    assert exact["entries"] == []


def test_snapshot_errors_on_an_unknown_game_and_bad_seats() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])

    with pytest.raises(UnknownGameError):
        manager.snapshot("absent")
    with pytest.raises(UnknownGameError):
        manager.snapshot("absent", 0)
    with pytest.raises(SeatAccessError):
        manager.snapshot(game_id, 1)  # an AI seat
    with pytest.raises(SeatAccessError):
        manager.snapshot(game_id, 9)


# --- REMOTE access ----------------------------------------------------------


def test_remote_seat_snapshot_needs_the_seats_own_token() -> None:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key="k")
    admin = Credentials(admin_key="k")
    summary = manager.create_game(TWO_HUMANS, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])
    claim0 = manager.claim_seat(game_id, 0, "P0", credentials=ANONYMOUS)
    claim1 = manager.claim_seat(game_id, 1, "P1", credentials=ANONYMOUS)
    own0 = Credentials(seat_tokens=frozenset({claim0.token}))
    own1 = Credentials(seat_tokens=frozenset({claim1.token}))

    with pytest.raises(SeatAccessError):
        manager.snapshot(game_id, 0, credentials=ANONYMOUS)
    with pytest.raises(SeatAccessError):
        manager.snapshot(game_id, 0, credentials=own1)
    with pytest.raises(SeatAccessError):
        manager.snapshot(game_id, 0, credentials=admin)

    mine0 = manager.snapshot(game_id, 0, credentials=own0)
    assert _obj(mine0["you"])["seats"] == [0]
    mine1 = manager.snapshot(game_id, 1, credentials=own1)
    assert _obj(mine1["you"])["seats"] == [1]


def test_remote_seatless_snapshot_needs_no_credentials() -> None:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key="k")
    admin = Credentials(admin_key="k")
    summary = manager.create_game(TWO_HUMANS, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])

    snapshot = manager.snapshot(game_id, credentials=ANONYMOUS)

    assert snapshot["you"] == {
        "game_id": game_id,
        "access": "remote",
        "seats": [],
        "admin": False,
    }
    assert _obj(snapshot["summary"])["game_seed"] is None


# --- the point of the slice: an incremental download budget ----------------


@dataclass(frozen=True)
class PlayedGame:
    """One finished human-seat game, played entirely through the snapshot
    call the way a real remote client would, plus what that cost."""

    manager: GameSessionManager
    game_id: str
    incremental_total: int
    full_total: int
    mid_log: tuple[int, str]


@pytest.fixture(scope="module")
def played_game() -> PlayedGame:
    """Play one game to the end, snapshotting before every seat-0 decision.

    Each request reuses the previous response's cursor and epoch, the way a
    real client would refresh; the whole finished game takes a few seconds,
    so it is shared by the finish-epoch and download-budget tests below
    instead of being played twice.
    """

    manager = GameSessionManager()
    created = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = _text(created["game_id"])

    cursor = 0
    epoch: str | None = None
    incremental_total = 0
    full_total = 0
    received: list[dict[str, object]] = []
    mid_log: tuple[int, str] | None = None

    for _ in range(2_000):
        snapshot = manager.snapshot(game_id, 0, log_after=cursor, log_epoch=epoch)
        log = _obj(snapshot["log"])
        incremental_total += len(json.dumps(log))
        full_total += len(json.dumps(manager.log(game_id, 0)))
        start = _int(log["from"])
        entries = _rows(log["entries"])
        received = entries if start == 0 else received + entries
        cursor = _int(log["count"])
        epoch = _text(log["epoch"])
        if mid_log is None and cursor > 0:
            mid_log = (cursor, epoch)

        current = _obj(snapshot["summary"])
        if current["finished"]:
            break
        if current["confirmation"] == 0:
            manager.confirm_turn(game_id, seat=0, revision=_int(current["revision"]))
        else:
            manager.apply_action(
                game_id, seat=0, revision=_int(current["revision"]), index=0
            )
    else:
        raise AssertionError("the game never finished")

    assert received == _rows(manager.log(game_id, 0)["entries"])
    assert mid_log is not None
    return PlayedGame(
        manager=manager,
        game_id=game_id,
        incremental_total=incremental_total,
        full_total=full_total,
        mid_log=mid_log,
    )


def test_finishing_the_game_changes_the_epoch(played_game: PlayedGame) -> None:
    old_count, old_epoch = played_game.mid_log

    resent = played_game.manager.snapshot(
        played_game.game_id, 0, log_after=old_count, log_epoch=old_epoch
    )
    log = _obj(resent["log"])

    assert log["from"] == 0
    assert log["epoch"] != old_epoch
    assert resent["actions"] is None
    assert _obj(resent["summary"])["finished"] is True
    assert "disclosure" in _obj(resent["view"])


def test_the_incremental_log_download_stays_well_under_the_full_log_cost(
    played_game: PlayedGame,
) -> None:
    final_full = len(json.dumps(played_game.manager.log(played_game.game_id, 0)))

    assert played_game.incremental_total < played_game.full_total / 10
    assert played_game.incremental_total < 3 * final_full
