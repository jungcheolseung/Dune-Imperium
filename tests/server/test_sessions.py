"""Tests for the framework-neutral game sessions of the play server."""

import json

import pytest

from dune_imperium.server.sessions import (
    GameSessionManager,
    SeatAccessError,
    SessionError,
    StaleRevisionError,
    UnknownGameError,
)

ALL_AI = ("heuristic", "random", "heuristic", "random")
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


def test_an_all_ai_game_finishes_during_creation() -> None:
    manager = GameSessionManager()

    summary = manager.create_game(ALL_AI, game_seed=11)

    assert summary["finished"] is True
    assert summary["phase"] == "finished"
    assert summary["decision"] is None
    standings = _rows(summary["standings"])
    assert [entry["rank"] for entry in standings] == [1, 2, 3, 4]
    json.dumps(summary)


def test_the_same_seed_reproduces_an_all_ai_game() -> None:
    manager = GameSessionManager()

    first = manager.create_game(ALL_AI, game_seed=12)
    second = manager.create_game(ALL_AI, game_seed=12)

    assert first["standings"] == second["standings"]
    assert first["revision"] == second["revision"]


def test_a_human_game_pauses_on_the_human_decision() -> None:
    manager = GameSessionManager()

    summary = manager.create_game(HUMAN_FIRST, game_seed=13)

    assert summary["finished"] is False
    decision = _obj(summary["decision"])
    assert decision["owner"] == 0
    assert decision["owner_is_human"] is True
    assert manager.summary(_text(summary["game_id"])) == summary


def test_only_human_seats_expose_views_and_actions() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])

    view = manager.view(game_id, 0)
    assert view["player"] == 0
    assert view["private"] is not None
    json.dumps(view)

    listing = manager.legal_actions(game_id, 0)
    assert listing["revision"] == summary["revision"]
    actions = _rows(listing["actions"])
    assert actions
    assert [entry["index"] for entry in actions] == list(range(len(actions)))
    json.dumps(listing)

    with pytest.raises(SeatAccessError):
        manager.view(game_id, 1)
    with pytest.raises(SeatAccessError):
        manager.legal_actions(game_id, 1)
    with pytest.raises(SeatAccessError):
        manager.view(game_id, 9)


def test_legal_actions_describe_the_board_icon_they_resolve() -> None:
    # Seat 0 opens seed 21 by sending a Dagger to Assembly Hall; the space's
    # single Intrigue icon is then offered with its printed effect text.
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=21)
    game_id = _text(summary["game_id"])
    placements = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert all(entry["detail"] is None for entry in placements)
    assert _obj(placements[0]["arguments"])["space_id"] == "assembly_hall"

    summary = manager.apply_action(
        game_id, seat=0, revision=_int(summary["revision"]), index=0
    )
    actions = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert [
        (entry["action_id"], _obj(entry["arguments"])["effect"], entry["detail"])
        for entry in actions
        if entry["action_id"] == "resolve_board_effect"
    ] == [("resolve_board_effect", "intrigue", "Draw 1 Intrigue card")]


def test_apply_guards_revision_owner_and_index() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])
    revision = _int(summary["revision"])

    with pytest.raises(StaleRevisionError):
        manager.apply_action(game_id, seat=0, revision=revision + 1, index=0)
    with pytest.raises(SessionError, match="out of range"):
        manager.apply_action(game_id, seat=0, revision=revision, index=999)
    with pytest.raises(SeatAccessError):
        manager.apply_action(game_id, seat=1, revision=revision, index=0)

    advanced = manager.apply_action(game_id, seat=0, revision=revision, index=0)
    assert advanced["revision"] != revision
    if not advanced["finished"]:
        assert _obj(advanced["decision"])["owner"] == 0


def test_a_human_game_can_be_played_to_the_end() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=14)
    game_id = _text(summary["game_id"])

    for _ in range(2_000):
        if summary["finished"]:
            break
        summary = manager.apply_action(
            game_id,
            seat=0,
            revision=_int(summary["revision"]),
            index=0,
        )
    assert summary["finished"] is True
    standings = _rows(summary["standings"])
    assert sorted(_int(entry["rank"]) for entry in standings) == [1, 2, 3, 4]


def test_a_leader_draft_game_starts_on_the_pick_frame() -> None:
    manager = GameSessionManager()

    summary = manager.create_game(
        ("human", "human", "human", "human"),
        leader_draft=True,
        game_seed=15,
    )

    decision = _obj(summary["decision"])
    assert decision["kind"] == "leader_draft"
    listing = manager.legal_actions(
        _text(summary["game_id"]), _int(decision["owner"])
    )
    actions = _rows(listing["actions"])
    assert len(actions) == 6
    assert {entry["action_id"] for entry in actions} == {"pick_leader"}


def test_creation_validates_seats_and_seeds() -> None:
    manager = GameSessionManager()

    with pytest.raises(SessionError, match="one seat assignment"):
        manager.create_game(("human", "heuristic"))
    with pytest.raises(SessionError, match="unknown seat assignment"):
        manager.create_game(("human", "alien", "random", "random"))
    with pytest.raises(SessionError, match="not be negative"):
        manager.create_game(ALL_AI, game_seed=-1)


def test_unknown_games_and_deletion() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(ALL_AI, game_seed=16)
    game_id = _text(summary["game_id"])

    assert [entry["game_id"] for entry in manager.list_games()] == [game_id]
    manager.delete(game_id)
    assert manager.list_games() == []
    with pytest.raises(UnknownGameError):
        manager.summary(game_id)
    with pytest.raises(UnknownGameError):
        manager.delete(game_id)
