"""Tests for save documents, the save file store, and replay review."""

import json
from pathlib import Path

import pytest

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.server.persistence import (
    SAVE_FORMAT,
    SAVE_FORMAT_VERSION,
    SaveError,
    SaveStore,
    UnknownSaveError,
)
from dune_imperium.server.sessions import (
    GameSessionManager,
    JsonObject,
    SeatAccessError,
    SessionError,
)

HUMAN_FIRST = ("human", "heuristic", "heuristic", "heuristic")


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


def _texts(value: object) -> list[str]:
    assert isinstance(value, list)
    return [_text(item) for item in value]


def _advance(
    manager: GameSessionManager,
    summary: JsonObject,
    steps: int,
) -> JsonObject:
    """Apply the first legal action of seat 0 ``steps`` times."""

    game_id = _text(summary["game_id"])
    for _ in range(steps):
        if summary["finished"]:
            break
        summary = manager.apply_action(
            game_id, seat=0, revision=_int(summary["revision"]), index=0
        )
    return summary


def _finish(manager: GameSessionManager, summary: JsonObject) -> JsonObject:
    summary = _advance(manager, summary, 2_000)
    assert summary["finished"] is True
    return summary


def _roundtrip(document: object) -> object:
    """Prove the document survives JSON before handing it to a load."""

    return json.loads(json.dumps(document))


@pytest.fixture(scope="module")
def finished_game() -> tuple[GameSessionManager, JsonObject]:
    """One finished human-seat game shared by the read-only tests."""

    manager = GameSessionManager()
    summary = _finish(manager, manager.create_game(HUMAN_FIRST, game_seed=14))
    return manager, summary


def test_save_documents_stamp_current_versions() -> None:
    manager = GameSessionManager()
    summary = _advance(manager, manager.create_game(HUMAN_FIRST, game_seed=31), 3)

    document = manager.save_game(_text(summary["game_id"]), name="테스트 저장")

    assert document["format"] == SAVE_FORMAT
    assert document["format_version"] == SAVE_FORMAT_VERSION
    assert document["action_codec_version"] == ACTION_CODEC_VERSION
    assert _text(document["ruleset_version"])
    assert _text(document["content_version"])
    assert document["name"] == "테스트 저장"
    assert document["seats"] == list(HUMAN_FIRST)
    assert document["game_seed"] == 31
    assert document["finished"] is False
    assert document["source_game_id"] == summary["game_id"]
    assert _text(document["expected_state_hash"])
    steps = _rows(document["steps"])
    # Setup chance resolves inside ``reset``; chance steps only appear once
    # the game hits a reshuffle, so early saves may hold actions only.
    assert {"action"} <= {step["type"] for step in steps} <= {"action", "chance"}
    json.dumps(document)


def test_a_restored_game_continues_like_the_unsaved_session() -> None:
    manager = GameSessionManager()
    original = _advance(manager, manager.create_game(HUMAN_FIRST, game_seed=31), 5)

    document = manager.save_game(_text(original["game_id"]))
    restored = manager.restore_game(_roundtrip(document))

    assert restored["game_id"] != original["game_id"]
    for field in ("revision", "phase", "round_number", "decision", "seats"):
        assert restored[field] == original[field], field

    original_end = _finish(manager, original)
    restored_end = _finish(manager, restored)
    assert restored_end["standings"] == original_end["standings"]
    assert restored_end["revision"] == original_end["revision"]


def test_a_finished_game_can_be_saved_and_restored(
    finished_game: tuple[GameSessionManager, JsonObject],
) -> None:
    manager, summary = finished_game

    document = manager.save_game(_text(summary["game_id"]))
    assert document["finished"] is True
    restored = manager.restore_game(_roundtrip(document))

    assert restored["finished"] is True
    assert restored["standings"] == summary["standings"]


def test_restoring_rejects_stale_or_tampered_documents(
    finished_game: tuple[GameSessionManager, JsonObject],
) -> None:
    manager, summary = finished_game
    document = manager.save_game(_text(summary["game_id"]))

    stale = {**document, "action_codec_version": ACTION_CODEC_VERSION - 1}
    with pytest.raises(SaveError, match="action_codec_version"):
        manager.restore_game(_roundtrip(stale))

    with pytest.raises(SaveError, match="not a dune-imperium save"):
        manager.restore_game(_roundtrip({**document, "format": "other"}))

    with pytest.raises(SaveError, match="state hash"):
        manager.restore_game(
            _roundtrip({**document, "expected_state_hash": "tampered"})
        )

    steps = _rows(document["steps"])
    tampered_index = next(
        index
        for index, step in enumerate(steps)
        if step["type"] == "chance" and len(_texts(step["values"])) >= 2
    )
    values = _texts(steps[tampered_index]["values"])
    values[0], values[1] = values[1], values[0]
    tampered_steps: list[object] = list(steps)
    tampered_steps[tampered_index] = {**steps[tampered_index], "values": values}
    with pytest.raises(SaveError, match=f"save step {tampered_index} "):
        manager.restore_game(
            _roundtrip({**document, "steps": tampered_steps})
        )

    bad_seats = {**document, "seats": ["human", "alien", "random", "random"]}
    with pytest.raises(SessionError, match="unknown seat assignment"):
        manager.restore_game(_roundtrip(bad_seats))


def test_the_save_store_lists_reads_and_deletes(tmp_path: Path) -> None:
    store = SaveStore(tmp_path / "saves")
    assert store.list() == []

    manager = GameSessionManager()
    summary = _advance(manager, manager.create_game(HUMAN_FIRST, game_seed=31), 1)
    document = manager.save_game(_text(summary["game_id"]), name="슬롯 1")

    metadata = store.write(document)
    save_id = _text(metadata["save_id"])
    assert "steps" not in metadata
    assert metadata["name"] == "슬롯 1"
    assert _int(metadata["step_count"]) > 0
    assert store.list() == [metadata]

    stored = store.read(save_id)
    assert _rows(stored["steps"])
    restored = manager.restore_game(stored)
    assert restored["revision"] == summary["revision"]

    (tmp_path / "saves" / ("f" * 32 + ".json")).write_text("{", encoding="utf-8")
    listing = store.list()
    assert len(listing) == 2
    assert any(entry.get("error") for entry in listing)

    store.delete(save_id)
    with pytest.raises(UnknownSaveError):
        store.read(save_id)
    with pytest.raises(UnknownSaveError):
        store.delete(save_id)
    with pytest.raises(UnknownSaveError):
        store.read("../outside")


def test_review_replays_a_finished_game_for_a_human_seat(
    finished_game: tuple[GameSessionManager, JsonObject],
) -> None:
    manager, summary = finished_game
    game_id = _text(summary["game_id"])

    review = manager.review(game_id, 0)
    steps = _rows(review["steps"])
    assert review["step_count"] == len(steps)
    assert steps

    kinds = {step["type"] for step in steps}
    assert kinds == {"action", "chance"}
    for step in steps:
        if step["type"] == "chance":
            assert "values" not in step
            assert _text(step["decision_id"])
        elif step["actor"] == 0:
            assert _text(step["action_id"])
        else:
            assert set(step) == {"type", "actor"}
    assert any(step["type"] == "action" and step["actor"] == 0 for step in steps)
    assert any(step["type"] == "action" and step["actor"] != 0 for step in steps)

    final = manager.review_state(game_id, 0, len(steps))
    assert final["phase"] == "finished"
    assert final["view"] == manager.view(game_id, 0)
    start = manager.review_state(game_id, 0, 0)
    assert start["view"] != final["view"]
    json.dumps(review)
    json.dumps(final)

    with pytest.raises(SessionError, match="out of range"):
        manager.review_state(game_id, 0, len(steps) + 1)
    with pytest.raises(SessionError, match="out of range"):
        manager.review_state(game_id, 0, -1)
    with pytest.raises(SeatAccessError):
        manager.review(game_id, 1)
    with pytest.raises(SeatAccessError):
        manager.review_state(game_id, 1, 0)


def test_review_requires_a_finished_game() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])

    with pytest.raises(SessionError, match="finishes"):
        manager.review(game_id, 0)
    with pytest.raises(SessionError, match="finishes"):
        manager.review_state(game_id, 0, 0)
