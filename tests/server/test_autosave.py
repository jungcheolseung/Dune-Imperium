"""Tests for the play server's autosave (M14 slice 5), session layer plus
the store: ``docs/multiplayer-design.md`` section 4.7. This module covers
``GameSessionManager.add_hand_over_listener``, ``server.autosave.Autosaver``,
and ``SaveStore.write_autosave`` directly; ``test_autosave_app.py`` covers
the HTTP wiring in ``server.app``."""

import logging
import threading
from pathlib import Path

import pytest

from dune_imperium.server.access import ANONYMOUS, AccessMode, Credentials
from dune_imperium.server.autosave import AUTOSAVE_NAME_PREFIX, Autosaver
from dune_imperium.server.persistence import SaveStore, UnknownSaveError, save_metadata
from dune_imperium.server.sessions import GameSessionManager, JsonObject

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


class _HandOverRecorder:
    """A hand-over listener that records every game ID it is given."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, game_id: str) -> None:
        self.calls.append(game_id)


def _play_seat0(
    manager: GameSessionManager, summary: JsonObject, requests: int
) -> JsonObject:
    """Play seat 0's first legal action (or confirm) ``requests`` times.

    Assumes seat 0 is the only human seat and stops early once the game
    finishes.
    """

    game_id = _text(summary["game_id"])
    for _ in range(requests):
        if summary["finished"]:
            break
        confirmation = summary["confirmation"]
        if isinstance(confirmation, int):
            summary = manager.confirm_turn(
                game_id, seat=0, revision=_int(summary["revision"])
            )
        else:
            summary = manager.apply_action(
                game_id, seat=0, revision=_int(summary["revision"]), index=0
            )
    return summary


def _play_seat0_to_finish(
    manager: GameSessionManager, summary: JsonObject, budget: int = 5_000
) -> JsonObject:
    summary = _play_seat0(manager, summary, budget)
    assert summary["finished"] is True, "the game did not finish within the budget"
    return summary


def _play_until_confirmation(
    manager: GameSessionManager, summary: JsonObject, seat: int = 0, budget: int = 400
) -> JsonObject:
    """Play ``seat``'s first legal action until its turn end awaits confirmation."""

    game_id = _text(summary["game_id"])
    for _ in range(budget):
        if summary["confirmation"] == seat:
            return summary
        summary = manager.apply_action(
            game_id, seat=seat, revision=_int(summary["revision"]), index=0
        )
    raise AssertionError(f"seat {seat} never paused for a turn-end confirmation")


def _expected_hand_over_after_apply(
    seat: int,
    own_step_index: int,
    document_after: JsonObject,
    summary_after: JsonObject,
) -> bool:
    """Recompute ``_turn_passed`` from public fields alone, for the test's own use.

    Mirrors the invariant in the prompt: not fired while the turn end still
    awaits ``seat``'s confirmation; fired once the game is finished, once
    another player's recorded action follows ``seat``'s own step (an
    auto-advanced AI seat), or once the pending decision belongs to another
    seat outright.
    """

    if summary_after["confirmation"] is not None:
        return False
    if summary_after["finished"] is True:
        return True
    steps = _rows(document_after["steps"])
    if any(
        step.get("type") == "action" and step.get("actor") != seat
        for step in steps[own_step_index:]
    ):
        return True
    decision = summary_after["decision"]
    return isinstance(decision, dict) and decision["owner"] != seat


# --- what fires the hand-over listener, and what does not -------------------


def test_hand_over_listener_fires_exactly_on_turn_hand_overs() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = _text(summary["game_id"])
    recorder = _HandOverRecorder()
    manager.add_hand_over_listener(recorder)

    fired_requests = 0
    quiet_requests = 0
    for _ in range(600):
        if summary["finished"]:
            break
        before_calls = len(recorder.calls)
        confirmation = summary["confirmation"]
        if isinstance(confirmation, int):
            seat = confirmation
            summary = manager.confirm_turn(
                game_id, seat=seat, revision=_int(summary["revision"])
            )
            fired = len(recorder.calls) > before_calls
            assert fired, "confirm_turn must always announce a hand-over"
            fired_requests += 1
        else:
            decision = summary["decision"]
            assert isinstance(decision, dict)
            seat = _int(decision["owner"])
            steps_before = len(_rows(manager.save_document(game_id)["steps"]))
            summary = manager.apply_action(
                game_id, seat=seat, revision=_int(summary["revision"]), index=0
            )
            fired = len(recorder.calls) > before_calls
            expected = _expected_hand_over_after_apply(
                seat, steps_before + 1, manager.save_document(game_id), summary
            )
            assert fired is expected, (seat, fired, expected, summary)
            if fired:
                fired_requests += 1
            else:
                quiet_requests += 1
        assert len(recorder.calls) - before_calls in (0, 1)
        if fired_requests >= 3 and quiet_requests >= 3:
            break
    else:
        raise AssertionError("the game did not finish within the step budget")

    assert fired_requests >= 3
    assert quiet_requests >= 3


def test_undo_claim_and_release_do_not_fire_the_hand_over_listener() -> None:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key="k")
    admin = Credentials(admin_key="k")
    summary = manager.create_game(HUMAN_FIRST, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])
    recorder = _HandOverRecorder()
    manager.add_hand_over_listener(recorder)

    claim = manager.claim_seat(game_id, 0, "P0", credentials=ANONYMOUS)
    own = Credentials(seat_tokens=frozenset({claim.token}))
    assert recorder.calls == []

    applied = manager.apply_action(
        game_id, 0, revision=_int(summary["revision"]), index=0, credentials=own
    )
    assert _rows(applied["undo"]), "the step must still be undoable for this test"
    calls_after_apply = len(recorder.calls)

    manager.undo(game_id, 0, revision=_int(applied["revision"]), credentials=own)
    assert len(recorder.calls) == calls_after_apply

    manager.release_seat(game_id, 0, credentials=own)
    assert len(recorder.calls) == calls_after_apply


def test_hand_over_between_two_humans_fires_exactly_once() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(TWO_HUMANS, game_seed=13)
    game_id = _text(summary["game_id"])
    recorder = _HandOverRecorder()
    manager.add_hand_over_listener(recorder)

    for _ in range(400):
        assert not recorder.calls, "unexpected hand-over before seat 0 finished"
        confirmation = summary["confirmation"]
        decision = summary["decision"]
        assert isinstance(decision, dict)
        if isinstance(confirmation, int):
            assert confirmation == 0
            summary = manager.confirm_turn(
                game_id, seat=0, revision=_int(summary["revision"])
            )
        else:
            owner = _int(decision["owner"])
            assert owner == 0, "no other human seat should hold the decision yet"
            summary = manager.apply_action(
                game_id, seat=0, revision=_int(summary["revision"]), index=0
            )
        if recorder.calls:
            break
    else:
        raise AssertionError("seat 0 never handed the turn over")

    assert recorder.calls == [game_id]
    new_decision = summary["decision"]
    assert isinstance(new_decision, dict)
    assert new_decision["owner"] == 1
    assert summary["confirmation"] is None


# --- re-entrancy and ordering -------------------------------------------


def test_the_hand_over_listener_may_call_back_into_the_manager() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = _text(summary["game_id"])
    seen: list[JsonObject] = []

    def listener(rung_game_id: str) -> None:
        # A deadlock here would mean the listener still held the session lock.
        seen.append(manager.save_document(rung_game_id))

    manager.add_hand_over_listener(listener)
    summary = _play_until_confirmation(manager, summary, seat=0)

    thread = threading.Thread(
        target=manager.confirm_turn,
        kwargs={"game_id": game_id, "seat": 0, "revision": _int(summary["revision"])},
        daemon=True,
    )
    thread.start()
    thread.join(timeout=5)

    assert not thread.is_alive(), "confirm_turn deadlocked while the listener ran"
    assert len(seen) == 1


def test_the_hand_over_listener_runs_after_the_change_listener() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = _text(summary["game_id"])
    order: list[str] = []
    manager.add_change_listener(lambda gid, payload: order.append("change"))
    manager.add_hand_over_listener(lambda gid: order.append("hand_over"))

    summary = _play_until_confirmation(manager, summary, seat=0)
    order.clear()

    manager.confirm_turn(game_id, seat=0, revision=_int(summary["revision"]))

    assert order == ["change", "hand_over"]


def test_a_raising_hand_over_listener_does_not_fail_the_request(
    caplog: pytest.LogCaptureFixture,
) -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = _text(summary["game_id"])
    good = _HandOverRecorder()

    def bad(rung_game_id: str) -> None:
        raise RuntimeError("boom")

    manager.add_hand_over_listener(bad)
    manager.add_hand_over_listener(good)

    summary = _play_until_confirmation(manager, summary, seat=0)
    with caplog.at_level(logging.ERROR, logger="dune_imperium.server.sessions"):
        result = manager.confirm_turn(
            game_id, seat=0, revision=_int(summary["revision"])
        )

    assert isinstance(result, dict) and "revision" in result
    assert good.calls == [game_id]
    assert any(
        record.levelno == logging.ERROR and game_id in record.getMessage()
        for record in caplog.records
    )

    # A later hand-over still reaches the surviving listener.
    good.calls.clear()
    caplog.clear()
    summary = _play_until_confirmation(manager, manager.summary(game_id), seat=0)
    with caplog.at_level(logging.ERROR, logger="dune_imperium.server.sessions"):
        manager.confirm_turn(game_id, seat=0, revision=_int(summary["revision"]))
    assert good.calls == [game_id]


# --- the game finishing, combined with the Autosaver's 종료 name ------------


def test_finishing_fires_the_listener_and_the_autosaver_names_it_종료(
    tmp_path: Path,
) -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=17)
    game_id = _text(summary["game_id"])
    recorder = _HandOverRecorder()
    manager.add_hand_over_listener(recorder)

    summary = _play_seat0_to_finish(manager, summary)

    assert summary["finished"] is True
    assert recorder.calls, "the finishing request must announce a hand-over"
    assert recorder.calls[-1] == game_id

    saves = SaveStore(tmp_path / "saves")
    Autosaver(manager, saves)(game_id)

    stored = saves.read(game_id)
    assert stored["name"] == f"{AUTOSAVE_NAME_PREFIX} · 종료"
    assert stored["autosave"] is True


# --- SaveStore.write_autosave ---------------------------------------------


def test_write_autosave_replaces_the_single_slot_and_rejects_bad_ids(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "saves"
    store = SaveStore(directory)
    game_id = "a" * 32
    document: JsonObject = {
        "game_seed": 1,
        "finished": False,
        "steps": [],
        "round_number": 1,
    }

    first = store.write_autosave(game_id, document)
    assert first["autosave"] is True
    assert first["save_id"] == game_id
    assert [path.name for path in directory.glob("*.json")] == [f"{game_id}.json"]
    assert list(directory.glob("*.tmp")) == []

    second = store.write_autosave(game_id, {**document, "round_number": 2})
    assert second["save_id"] == game_id
    assert [path.name for path in directory.glob("*.json")] == [f"{game_id}.json"]
    assert list(directory.glob("*.tmp")) == []
    assert store.read(game_id)["round_number"] == 2

    normal = store.write(document)
    assert normal["autosave"] is False
    # ``autosave`` is derived metadata (save_metadata), not necessarily a key
    # physically stored on an ordinary document; re-deriving it from what was
    # actually written proves the same thing a fresh listing would show.
    assert save_metadata(store.read(_text(normal["save_id"])))["autosave"] is False

    before = sorted(path.name for path in directory.glob("*.json"))
    with pytest.raises(UnknownSaveError):
        store.write_autosave("../evil", document)
    after = sorted(path.name for path in directory.glob("*.json"))
    assert after == before


def test_write_autosave_hides_the_seed_only_while_unfinished(tmp_path: Path) -> None:
    store = SaveStore(tmp_path / "saves")
    game_id = "b" * 32
    unfinished: JsonObject = {
        "game_seed": 42,
        "finished": False,
        "steps": [],
        "round_number": 1,
    }

    metadata = store.write_autosave(game_id, unfinished, hide_unfinished_seed=True)
    assert metadata["game_seed"] is None

    finished: JsonObject = {**unfinished, "finished": True}
    metadata = store.write_autosave(game_id, finished, hide_unfinished_seed=True)
    assert metadata["game_seed"] == 42

    visible = store.write_autosave(game_id, unfinished, hide_unfinished_seed=False)
    assert visible["game_seed"] == 42


# --- Autosaver ---------------------------------------------------------


def test_autosaver_names_an_unfinished_autosave_by_round(tmp_path: Path) -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = _text(summary["game_id"])
    saves = SaveStore(tmp_path / "saves")
    autosaver = Autosaver(manager, saves)

    autosaver(game_id)

    stored = saves.read(game_id)
    assert stored["name"] == f"{AUTOSAVE_NAME_PREFIX} · R{stored['round_number']}"
    assert stored["autosave"] is True


def test_autosaver_on_an_unknown_game_writes_nothing(tmp_path: Path) -> None:
    manager = GameSessionManager()
    saves = SaveStore(tmp_path / "saves")
    autosaver = Autosaver(manager, saves)

    autosaver("absent")  # declared -> None; mypy already proves it writes nothing else
    assert saves.list() == []


def test_a_store_error_propagates_and_is_swallowed_through_the_listener(
    tmp_path: Path,
) -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = _text(summary["game_id"])
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("occupied", encoding="utf-8")
    saves = SaveStore(blocked)
    autosaver = Autosaver(manager, saves)

    with pytest.raises(OSError):
        autosaver(game_id)

    manager.add_hand_over_listener(autosaver)
    summary = _play_until_confirmation(manager, summary, seat=0)

    result = manager.confirm_turn(game_id, seat=0, revision=_int(summary["revision"]))
    assert isinstance(result, dict) and "revision" in result


def test_autosaver_holds_its_lock_across_build_and_write(tmp_path: Path) -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = _text(summary["game_id"])
    saves = SaveStore(tmp_path / "saves")
    autosaver = Autosaver(manager, saves)

    release_first_write = threading.Event()
    first_write_started = threading.Event()
    calls: list[str] = []

    real_save_document = manager.save_document
    real_write_autosave = saves.write_autosave

    def recording_save_document(gid: str, *, name: str | None = None) -> JsonObject:
        calls.append("save_document")
        return real_save_document(gid, name=name)

    def blocking_write_autosave(
        gid: str, document: JsonObject, *, hide_unfinished_seed: bool = False
    ) -> JsonObject:
        calls.append("write_start")
        first_write_started.set()
        release_first_write.wait(timeout=5)
        result = real_write_autosave(
            gid, document, hide_unfinished_seed=hide_unfinished_seed
        )
        calls.append("write_end")
        return result

    manager.save_document = recording_save_document  # type: ignore[method-assign,assignment]
    saves.write_autosave = blocking_write_autosave  # type: ignore[method-assign,assignment]

    first_thread = threading.Thread(target=autosaver, args=(game_id,), daemon=True)
    first_thread.start()
    assert first_write_started.wait(timeout=5)

    second_thread = threading.Thread(target=autosaver, args=(game_id,), daemon=True)
    second_thread.start()
    second_thread.join(timeout=0.3)
    assert second_thread.is_alive(), "the second autosave must block behind the first"
    assert calls == ["save_document", "write_start"]

    release_first_write.set()
    first_thread.join(timeout=5)
    second_thread.join(timeout=5)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert calls == [
        "save_document",
        "write_start",
        "write_end",
        "save_document",
        "write_start",
        "write_end",
    ]


# --- restoring from an autosave -----------------------------------------


def test_restore_from_an_autosave_continues_the_same_game(tmp_path: Path) -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = _text(summary["game_id"])
    saves = SaveStore(tmp_path / "saves")
    manager.add_hand_over_listener(Autosaver(manager, saves))

    live_hash = ""
    for _ in range(600):
        if summary["finished"]:
            break
        confirmation = summary["confirmation"]
        if isinstance(confirmation, int):
            summary = manager.confirm_turn(
                game_id, seat=0, revision=_int(summary["revision"])
            )
        else:
            summary = manager.apply_action(
                game_id, seat=0, revision=_int(summary["revision"]), index=0
            )
        live_document = manager.save_document(game_id)
        live_hash = _text(live_document["expected_state_hash"])
        listing = saves.list()
        if (
            listing
            and _int(listing[0]["step_count"]) >= 5
            and saves.read(game_id)["expected_state_hash"] == live_hash
        ):
            break
    else:
        raise AssertionError("no autosave lined up with a live state in the budget")

    autosaved_document = saves.read(game_id)
    assert autosaved_document["expected_state_hash"] == live_hash

    restored = manager.restore_game(autosaved_document)
    restored_id = _text(restored["game_id"])
    assert manager.save_document(restored_id)["expected_state_hash"] == live_hash
    assert _int(restored["revision"]) == len(_rows(autosaved_document["steps"]))
    assert restored["round_number"] == autosaved_document["round_number"]

    # Determinism: two independent restores of the same autosave, each
    # played the same next K requests, land on the same state hash.
    copy_a = manager.restore_game(autosaved_document)
    copy_b = manager.restore_game(autosaved_document)
    final_a = _play_seat0(manager, copy_a, 10)
    final_b = _play_seat0(manager, copy_b, 10)
    hash_a = manager.save_document(_text(final_a["game_id"]))["expected_state_hash"]
    hash_b = manager.save_document(_text(final_b["game_id"]))["expected_state_hash"]
    assert hash_a == hash_b
