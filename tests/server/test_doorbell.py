"""Tests for the play server's doorbell (M14 slice 3): a change listener on
``GameSessionManager`` plus presence, ``docs/multiplayer-design.md`` section
4.5. This module covers the session layer only; ``test_events.py`` covers
the hub that fans a change out to Server-Sent Events streams, and
``test_events_app.py`` covers the HTTP endpoint built from both."""

import threading

import pytest

from dune_imperium.server.access import ANONYMOUS, AccessMode, Credentials
from dune_imperium.server.sessions import (
    GameSessionManager,
    JsonObject,
    UnknownGameError,
)

ALL_AI = ("heuristic", "random", "heuristic", "random")
HUMAN_FIRST = ("human", "heuristic", "heuristic", "heuristic")
TWO_HUMANS = ("human", "human", "heuristic", "heuristic")

_DOORBELL_KEYS = {
    "seq",
    "revision",
    "undo_count",
    "log_count",
    "decision_owner",
    "confirmation",
    "finished",
    "players",
}


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


class _Recorder:
    """A change listener that records every ring it is given."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, JsonObject | None]] = []

    def __call__(self, game_id: str, payload: JsonObject | None) -> None:
        self.calls.append((game_id, payload))


def _assert_mirrors_summary(bell: JsonObject, summary: JsonObject) -> None:
    assert set(bell) == _DOORBELL_KEYS
    decision = summary["decision"]
    owner = _obj(decision)["owner"] if isinstance(decision, dict) else None
    assert bell["decision_owner"] == owner
    assert bell["revision"] == summary["revision"]
    assert bell["undo_count"] == summary["undo_count"]
    assert bell["log_count"] == summary["log_count"]
    assert bell["confirmation"] == summary["confirmation"]
    assert bell["finished"] == summary["finished"]
    assert bell["players"] == summary["players"]
    assert isinstance(bell["seq"], int)


# --- doorbell payload shape --------------------------------------------------


def test_doorbell_payload_mirrors_an_unfinished_summary() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])
    assert summary["finished"] is False

    bell = manager.doorbell(game_id)

    _assert_mirrors_summary(bell, manager.summary(game_id))


def test_doorbell_payload_for_a_finished_all_ai_game_has_no_decision_owner() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(ALL_AI, game_seed=11)
    game_id = _text(summary["game_id"])
    assert summary["finished"] is True

    bell = manager.doorbell(game_id)

    _assert_mirrors_summary(bell, manager.summary(game_id))
    assert bell["decision_owner"] is None
    assert bell["finished"] is True


def test_doorbell_on_an_unknown_game_raises() -> None:
    manager = GameSessionManager()

    with pytest.raises(UnknownGameError):
        manager.doorbell("absent")


# --- what rings, and what does not -------------------------------------------


def test_create_game_summary_snapshot_doorbell_and_view_do_not_ring() -> None:
    manager = GameSessionManager()
    recorder = _Recorder()
    manager.add_change_listener(recorder)

    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])
    manager.summary(game_id)
    manager.snapshot(game_id)
    manager.snapshot(game_id, 0)
    manager.doorbell(game_id)
    manager.view(game_id, 0)

    assert recorder.calls == []


def test_apply_action_rings_once_with_the_new_revision() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])
    recorder = _Recorder()
    manager.add_change_listener(recorder)

    applied = manager.apply_action(
        game_id, seat=0, revision=_int(summary["revision"]), index=0
    )

    assert len(recorder.calls) == 1
    rung_game_id, payload = recorder.calls[0]
    assert rung_game_id == game_id
    bell = _obj(payload)
    assert bell["revision"] == applied["revision"]
    assert isinstance(bell["seq"], int)


def test_undo_rings_once_with_the_rolled_back_revision() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])
    applied = manager.apply_action(
        game_id, seat=0, revision=_int(summary["revision"]), index=0
    )
    assert _rows(applied["undo"]), "the step must still be undoable for this test"
    recorder = _Recorder()
    manager.add_change_listener(recorder)

    undone = manager.undo(game_id, seat=0, revision=_int(applied["revision"]))

    assert len(recorder.calls) == 1
    bell = _obj(recorder.calls[0][1])
    assert bell["revision"] == undone["revision"]
    assert bell["undo_count"] == undone["undo_count"]


def test_confirm_turn_rings_once_with_the_lifted_confirmation() -> None:
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
    recorder = _Recorder()
    manager.add_change_listener(recorder)

    confirmed = manager.confirm_turn(
        game_id, seat=0, revision=_int(summary["revision"])
    )

    assert len(recorder.calls) == 1
    bell = _obj(recorder.calls[0][1])
    assert bell["revision"] == confirmed["revision"]
    assert bell["confirmation"] == confirmed["confirmation"]


def test_claim_seat_rings_once_and_the_payload_shows_the_claim() -> None:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key="k")
    admin = Credentials(admin_key="k")
    summary = manager.create_game(TWO_HUMANS, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])
    recorder = _Recorder()
    manager.add_change_listener(recorder)

    manager.claim_seat(game_id, 0, "P0", credentials=ANONYMOUS)

    assert len(recorder.calls) == 1
    players = _rows(_obj(recorder.calls[0][1])["players"])
    seat0 = next(p for p in players if p["seat"] == 0)
    assert seat0["claimed"] is True
    assert seat0["name"] == "P0"


def test_reclaiming_with_the_same_token_to_rename_rings_once() -> None:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key="k")
    admin = Credentials(admin_key="k")
    summary = manager.create_game(TWO_HUMANS, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])
    claim = manager.claim_seat(game_id, 0, "P0", credentials=ANONYMOUS)
    own = Credentials(seat_tokens=frozenset({claim.token}))
    recorder = _Recorder()
    manager.add_change_listener(recorder)

    renamed = manager.claim_seat(game_id, 0, "P0-renamed", credentials=own)

    assert renamed.token == claim.token
    assert len(recorder.calls) == 1
    players = _rows(_obj(recorder.calls[0][1])["players"])
    seat0 = next(p for p in players if p["seat"] == 0)
    assert seat0["name"] == "P0-renamed"


def test_release_seat_rings_once_and_the_payload_shows_it_unclaimed() -> None:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key="k")
    admin = Credentials(admin_key="k")
    summary = manager.create_game(TWO_HUMANS, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])
    claim = manager.claim_seat(game_id, 0, "P0", credentials=ANONYMOUS)
    own = Credentials(seat_tokens=frozenset({claim.token}))
    recorder = _Recorder()
    manager.add_change_listener(recorder)

    manager.release_seat(game_id, 0, credentials=own)

    assert len(recorder.calls) == 1
    players = _rows(_obj(recorder.calls[0][1])["players"])
    seat0 = next(p for p in players if p["seat"] == 0)
    assert seat0["claimed"] is False


def test_delete_rings_none() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])
    recorder = _Recorder()
    manager.add_change_listener(recorder)

    manager.delete(game_id)

    assert recorder.calls == [(game_id, None)]


def test_seq_strictly_increases_across_a_sequence_of_rings() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = _text(summary["game_id"])
    recorder = _Recorder()
    manager.add_change_listener(recorder)

    for _ in range(200):
        if summary["confirmation"] == 0:
            break
        summary = manager.apply_action(
            game_id, seat=0, revision=_int(summary["revision"]), index=0
        )
    else:
        raise AssertionError("seat 0 never paused for a turn-end confirmation")
    manager.confirm_turn(game_id, seat=0, revision=_int(summary["revision"]))

    seqs = [_int(_obj(payload)["seq"]) for _, payload in recorder.calls]
    assert len(seqs) >= 2
    assert all(
        later > earlier for earlier, later in zip(seqs, seqs[1:], strict=False)
    )


# --- the listener runs outside the session lock ------------------------------


def test_the_listener_runs_outside_the_session_lock() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])
    seen_summaries: list[JsonObject] = []
    seen_payloads: list[JsonObject] = []

    def listener(rung_game_id: str, payload: JsonObject | None) -> None:
        assert payload is not None
        seen_payloads.append(payload)
        # A deadlock here would mean the listener still held the session lock.
        seen_summaries.append(manager.summary(rung_game_id))

    manager.add_change_listener(listener)

    thread = threading.Thread(
        target=manager.apply_action,
        kwargs={
            "game_id": game_id,
            "seat": 0,
            "revision": _int(summary["revision"]),
            "index": 0,
        },
        daemon=True,
    )
    thread.start()
    thread.join(timeout=5)

    assert not thread.is_alive(), "apply_action deadlocked while the listener ran"
    assert len(seen_summaries) == 1
    assert seen_summaries[0]["revision"] == seen_payloads[0]["revision"]


def test_two_listeners_both_get_every_ring() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])
    first = _Recorder()
    second = _Recorder()
    manager.add_change_listener(first)
    manager.add_change_listener(second)

    manager.apply_action(game_id, seat=0, revision=_int(summary["revision"]), index=0)

    assert len(first.calls) == 1
    assert len(second.calls) == 1
    assert first.calls == second.calls


# --- presence: online defaults ------------------------------------------------


def test_summaries_carry_online_false_for_every_player_with_no_connections() -> None:
    open_manager = GameSessionManager()
    open_summary = open_manager.create_game(TWO_HUMANS, game_seed=13)
    remote_manager = GameSessionManager(access=AccessMode.REMOTE, admin_key="k")
    remote_summary = remote_manager.create_game(
        TWO_HUMANS, game_seed=13, credentials=Credentials(admin_key="k")
    )

    for manager, summary in (
        (open_manager, open_summary),
        (remote_manager, remote_summary),
    ):
        game_id = _text(summary["game_id"])
        players = _rows(manager.summary(game_id)["players"])
        assert len(players) == 4
        assert all(player["online"] is False for player in players)


# --- OPEN presence -------------------------------------------------------------


def test_open_presence_connect_and_disconnect() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(TWO_HUMANS, game_seed=13)
    game_id = _text(summary["game_id"])
    recorder = _Recorder()
    manager.add_change_listener(recorder)

    first_id = manager.connect(game_id)
    assert len(recorder.calls) == 1
    online = {
        p["seat"] for p in _rows(manager.summary(game_id)["players"]) if p["online"]
    }
    # Both human seats light up; neither AI seat (2, 3) ever does.
    assert online == {0, 1}

    second_id = manager.connect(game_id)
    assert len(recorder.calls) == 1  # already online: no new ring

    manager.disconnect(game_id, first_id)
    assert len(recorder.calls) == 1  # still online via the second connection
    online = {
        p["seat"] for p in _rows(manager.summary(game_id)["players"]) if p["online"]
    }
    assert online == {0, 1}

    manager.disconnect(game_id, second_id)
    assert len(recorder.calls) == 2
    players = _rows(manager.summary(game_id)["players"])
    assert all(not p["online"] for p in players)

    # Unknown connection IDs and unknown games are tolerated.
    manager.disconnect(game_id, 999_999)
    manager.disconnect("absent-game", first_id)
    assert len(recorder.calls) == 2


# --- REMOTE presence -----------------------------------------------------------


def test_remote_presence_own_token_lights_only_its_seat() -> None:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key="k")
    admin = Credentials(admin_key="k")
    summary = manager.create_game(TWO_HUMANS, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])
    claim0 = manager.claim_seat(game_id, 0, "P0", credentials=ANONYMOUS)
    manager.claim_seat(game_id, 1, "P1", credentials=ANONYMOUS)
    own0 = Credentials(seat_tokens=frozenset({claim0.token}))
    recorder = _Recorder()
    manager.add_change_listener(recorder)

    manager.connect(game_id, credentials=own0)

    assert len(recorder.calls) == 1
    online = {
        p["seat"]: p["online"] for p in _rows(manager.summary(game_id)["players"])
    }
    assert online[0] is True
    assert online[1] is False


def test_remote_presence_anonymous_connection_lights_nothing() -> None:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key="k")
    admin = Credentials(admin_key="k")
    summary = manager.create_game(TWO_HUMANS, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])
    manager.claim_seat(game_id, 0, "P0", credentials=ANONYMOUS)
    recorder = _Recorder()
    manager.add_change_listener(recorder)

    manager.connect(game_id, credentials=ANONYMOUS)

    assert recorder.calls == []
    players = _rows(manager.summary(game_id)["players"])
    assert all(p["online"] is False for p in players)


def test_remote_presence_admin_key_alone_lights_nothing() -> None:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key="k")
    admin = Credentials(admin_key="k")
    summary = manager.create_game(TWO_HUMANS, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])
    manager.claim_seat(game_id, 0, "P0", credentials=ANONYMOUS)
    recorder = _Recorder()
    manager.add_change_listener(recorder)

    manager.connect(game_id, credentials=admin)

    assert recorder.calls == []
    players = _rows(manager.summary(game_id)["players"])
    assert all(p["online"] is False for p in players)


def test_remote_presence_release_rings_and_turns_the_seat_offline() -> None:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key="k")
    admin = Credentials(admin_key="k")
    summary = manager.create_game(TWO_HUMANS, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])
    claim0 = manager.claim_seat(game_id, 0, "P0", credentials=ANONYMOUS)
    own0 = Credentials(seat_tokens=frozenset({claim0.token}))
    manager.connect(game_id, credentials=own0)
    recorder = _Recorder()
    manager.add_change_listener(recorder)

    manager.release_seat(game_id, 0, credentials=own0)

    assert len(recorder.calls) == 1
    players = _rows(manager.summary(game_id)["players"])
    seat0 = next(p for p in players if p["seat"] == 0)
    assert seat0["online"] is False
    assert seat0["claimed"] is False


def test_remote_presence_reclaim_stays_online_past_the_old_connection() -> None:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key="k")
    admin = Credentials(admin_key="k")
    summary = manager.create_game(TWO_HUMANS, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])
    claim0 = manager.claim_seat(game_id, 0, "P0", credentials=ANONYMOUS)
    own0 = Credentials(seat_tokens=frozenset({claim0.token}))
    old_connection = manager.connect(game_id, credentials=own0)
    manager.release_seat(game_id, 0, credentials=own0)

    reclaimed = manager.claim_seat(game_id, 0, "P0-again", credentials=ANONYMOUS)
    new_own = Credentials(seat_tokens=frozenset({reclaimed.token}))
    manager.connect(game_id, credentials=new_own)
    players = _rows(manager.summary(game_id)["players"])
    assert next(p for p in players if p["seat"] == 0)["online"] is True
    recorder = _Recorder()
    manager.add_change_listener(recorder)

    manager.disconnect(game_id, old_connection)

    assert recorder.calls == []  # nothing changed: seat 0 was already online
    players = _rows(manager.summary(game_id)["players"])
    assert next(p for p in players if p["seat"] == 0)["online"] is True
