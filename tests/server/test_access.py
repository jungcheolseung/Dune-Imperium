"""Tests for the remote-access vocabulary and session-layer access control
(M14 slice 1, ``docs/multiplayer-design.md`` sections 4.2-4.4, 5, 6)."""

import json
import threading

import pytest

from dune_imperium.server.access import ANONYMOUS, AccessMode, Credentials
from dune_imperium.server.persistence import JsonObject, save_metadata
from dune_imperium.server.sessions import (
    PLAYER_NAME_MAX_LENGTH,
    AdminAccessError,
    GameSessionManager,
    SeatAccessError,
    SeatClaim,
    SeatTakenError,
    SessionError,
    UnknownGameError,
    _public_seat_kind,
)

ALL_AI = ("heuristic", "random", "heuristic", "random")
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


def _remote_manager(
    admin_key: str = "top-secret-key",
) -> tuple[GameSessionManager, Credentials]:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key=admin_key)
    return manager, Credentials(admin_key=admin_key)


# --- manager construction --------------------------------------------------


def test_remote_access_needs_an_admin_key() -> None:
    with pytest.raises(ValueError, match="admin key"):
        GameSessionManager(access=AccessMode.REMOTE)
    with pytest.raises(ValueError, match="admin key"):
        GameSessionManager(access=AccessMode.REMOTE, admin_key="")


def test_open_access_rejects_an_admin_key() -> None:
    with pytest.raises(ValueError, match="admin key"):
        GameSessionManager(access=AccessMode.OPEN, admin_key="secret")


# --- OPEN mode is unchanged -------------------------------------------------


def test_open_mode_claim_and_release_raise_plain_session_error() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])

    with pytest.raises(SessionError) as claim_error:
        manager.claim_seat(game_id, 0, "Alice")
    assert type(claim_error.value) is SessionError

    with pytest.raises(SessionError) as release_error:
        manager.release_seat(game_id, 0)
    assert type(release_error.value) is SessionError


def test_open_mode_admin_login_raises_plain_session_error() -> None:
    manager = GameSessionManager()

    with pytest.raises(SessionError) as excinfo:
        manager.admin_login("whatever")
    assert type(excinfo.value) is SessionError


def test_open_mode_identify_lists_every_human_seat_and_admin_true() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(TWO_HUMANS, game_seed=13)
    game_id = _text(summary["game_id"])

    assert manager.identify(game_id) == {
        "game_id": game_id,
        "access": "open",
        "seats": [0, 1],
        "admin": True,
    }


def test_open_mode_summary_has_the_seed_and_unclaimed_players() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)

    assert summary["access"] == "open"
    assert summary["game_seed"] == 13
    players = _rows(summary["players"])
    assert len(players) == 4
    assert all(entry["claimed"] is False for entry in players)
    assert all(entry["name"] is None for entry in players)


def test_open_mode_seat_operations_need_no_credentials() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])

    assert manager.view(game_id, 0)["player"] == 0
    assert manager.legal_actions(game_id, 0)["seat"] == 0
    assert manager.log(game_id, 0)["seat"] == 0


# --- REMOTE host-only operations --------------------------------------------


def _call_host_operation(
    manager: GameSessionManager, operation: str, game_id: str, credentials: Credentials
) -> object:
    if operation == "create_game":
        return manager.create_game(ALL_AI, game_seed=17, credentials=credentials)
    if operation == "list_games":
        return manager.list_games(credentials=credentials)
    if operation == "delete":
        manager.delete(game_id, credentials=credentials)
        return None
    if operation == "save_game":
        return manager.save_game(game_id, credentials=credentials)
    raise AssertionError(f"unhandled operation {operation!r}")


@pytest.mark.parametrize(
    "operation", ["create_game", "list_games", "delete", "save_game"]
)
def test_host_only_session_operations_need_the_admin_key(operation: str) -> None:
    manager, admin = _remote_manager()
    summary = manager.create_game(ALL_AI, game_seed=16, credentials=admin)
    game_id = _text(summary["game_id"])
    wrong = Credentials(admin_key="not-the-key")

    with pytest.raises(AdminAccessError):
        _call_host_operation(manager, operation, game_id, ANONYMOUS)
    with pytest.raises(AdminAccessError):
        _call_host_operation(manager, operation, game_id, wrong)

    result = _call_host_operation(manager, operation, game_id, admin)
    if operation == "create_game":
        assert isinstance(result, dict) and result["game_id"] != game_id
    elif operation == "list_games":
        assert isinstance(result, list) and result
    elif operation == "delete":
        assert result is None
        with pytest.raises(UnknownGameError):
            manager.summary(game_id)
    elif operation == "save_game":
        assert isinstance(result, dict) and result["format"] == "dune-imperium-save"


def test_restore_game_is_host_only_in_remote_mode() -> None:
    manager, admin = _remote_manager()
    summary = manager.create_game(ALL_AI, game_seed=18, credentials=admin)
    document = manager.save_game(_text(summary["game_id"]), credentials=admin)

    with pytest.raises(AdminAccessError):
        manager.restore_game(document, credentials=ANONYMOUS)
    with pytest.raises(AdminAccessError):
        manager.restore_game(document, credentials=Credentials(admin_key="nope"))

    restored = manager.restore_game(document, credentials=admin)
    assert restored["game_id"] != summary["game_id"]


def test_a_seat_token_alone_is_not_admin() -> None:
    manager, admin = _remote_manager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])
    claim = manager.claim_seat(game_id, 0, "P0", credentials=ANONYMOUS)
    seat_only = Credentials(seat_tokens=frozenset({claim.token}))

    assert manager.is_admin(seat_only) is False
    with pytest.raises(AdminAccessError):
        manager.require_admin(seat_only)
    with pytest.raises(AdminAccessError):
        manager.list_games(credentials=seat_only)


# --- REMOTE seed hiding ------------------------------------------------------


def test_remote_summaries_hide_the_seed_until_the_game_finishes() -> None:
    manager, admin = _remote_manager()
    unfinished = manager.create_game(HUMAN_FIRST, game_seed=19, credentials=admin)
    assert unfinished["game_seed"] is None
    assert manager.summary(_text(unfinished["game_id"]))["game_seed"] is None

    finished = manager.create_game(ALL_AI, game_seed=20, credentials=admin)
    assert finished["finished"] is True
    assert finished["game_seed"] == 20


# --- claim -------------------------------------------------------------------


def test_claiming_a_seat_marks_it_in_the_summary() -> None:
    manager, admin = _remote_manager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])

    claim = manager.claim_seat(game_id, 0, "  Alice  ", credentials=ANONYMOUS)

    assert isinstance(claim.token, str) and claim.token
    players = _rows(claim.summary["players"])
    assert players[0]["claimed"] is True
    assert players[0]["name"] == "Alice"
    assert all(entry["claimed"] is False for entry in players if entry["seat"] != 0)


def test_a_strangers_second_claim_is_refused() -> None:
    manager, admin = _remote_manager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])
    manager.claim_seat(game_id, 0, "Alice", credentials=ANONYMOUS)

    with pytest.raises(SeatTakenError):
        manager.claim_seat(game_id, 0, "Bob", credentials=ANONYMOUS)


def test_the_holder_can_reclaim_to_rename_and_keeps_the_token() -> None:
    manager, admin = _remote_manager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])
    first = manager.claim_seat(game_id, 0, "Alice", credentials=ANONYMOUS)
    own = Credentials(seat_tokens=frozenset({first.token}))

    renamed = manager.claim_seat(game_id, 0, "Alicia", credentials=own)

    assert renamed.token == first.token
    assert _rows(renamed.summary["players"])[0]["name"] == "Alicia"


def test_claim_rejects_ai_and_out_of_range_seats() -> None:
    manager, admin = _remote_manager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])

    with pytest.raises(SeatAccessError):
        manager.claim_seat(game_id, 1, "x", credentials=ANONYMOUS)
    with pytest.raises(SeatAccessError):
        manager.claim_seat(game_id, 9, "x", credentials=ANONYMOUS)


def test_claim_on_an_unknown_game_raises_unknown_game_error() -> None:
    manager, _admin = _remote_manager()

    with pytest.raises(UnknownGameError):
        manager.claim_seat("absent", 0, "x", credentials=ANONYMOUS)


@pytest.mark.parametrize("name", ["", " \t "])
def test_claim_rejects_empty_names(name: str) -> None:
    manager, admin = _remote_manager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])

    with pytest.raises(SessionError):
        manager.claim_seat(game_id, 0, name, credentials=ANONYMOUS)


def test_claim_rejects_a_name_over_the_length_limit() -> None:
    manager, admin = _remote_manager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])

    with pytest.raises(SessionError):
        manager.claim_seat(
            game_id, 0, "A" * (PLAYER_NAME_MAX_LENGTH + 1), credentials=ANONYMOUS
        )
    claim = manager.claim_seat(
        game_id, 0, "B" * PLAYER_NAME_MAX_LENGTH, credentials=ANONYMOUS
    )
    assert _rows(claim.summary["players"])[0]["name"] == "B" * PLAYER_NAME_MAX_LENGTH


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("A\x00B", "AB"),
        ("  A   B  ", "A B"),
        ("철수", "철수"),
    ],
)
def test_claim_cleans_the_player_name(raw: str, expected: str) -> None:
    manager, admin = _remote_manager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])

    claim = manager.claim_seat(game_id, 0, raw, credentials=ANONYMOUS)

    assert _rows(claim.summary["players"])[0]["name"] == expected


# --- seat-scoped access ------------------------------------------------------


_SEAT_OPERATIONS = (
    "view",
    "legal_actions",
    "log",
    "apply_action",
    "undo",
    "confirm_turn",
)


def _call_seat_operation(
    manager: GameSessionManager,
    operation: str,
    game_id: str,
    seat: int,
    credentials: Credentials,
) -> object:
    if operation == "view":
        return manager.view(game_id, seat, credentials=credentials)
    if operation == "legal_actions":
        return manager.legal_actions(game_id, seat, credentials=credentials)
    if operation == "log":
        return manager.log(game_id, seat, credentials=credentials)
    if operation == "apply_action":
        return manager.apply_action(
            game_id, seat, revision=0, index=0, credentials=credentials
        )
    if operation == "undo":
        return manager.undo(game_id, seat, revision=0, credentials=credentials)
    if operation == "confirm_turn":
        return manager.confirm_turn(game_id, seat, revision=0, credentials=credentials)
    raise AssertionError(f"unhandled operation {operation!r}")


@pytest.mark.parametrize("operation", _SEAT_OPERATIONS)
def test_seat_scoped_operations_need_the_seats_own_token(operation: str) -> None:
    manager, admin = _remote_manager()
    summary = manager.create_game(TWO_HUMANS, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])
    manager.claim_seat(game_id, 0, "P0", credentials=ANONYMOUS)
    claim1 = manager.claim_seat(game_id, 1, "P1", credentials=ANONYMOUS)
    other_seats_token = Credentials(seat_tokens=frozenset({claim1.token}))

    with pytest.raises(SeatAccessError):
        _call_seat_operation(manager, operation, game_id, 0, ANONYMOUS)
    with pytest.raises(SeatAccessError):
        _call_seat_operation(manager, operation, game_id, 0, other_seats_token)
    with pytest.raises(SeatAccessError):
        _call_seat_operation(manager, operation, game_id, 0, admin)


def test_a_seat_token_unlocks_its_own_operations() -> None:
    manager, admin = _remote_manager()
    summary = manager.create_game(TWO_HUMANS, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])
    claim = manager.claim_seat(game_id, 0, "P0", credentials=ANONYMOUS)
    own = Credentials(seat_tokens=frozenset({claim.token}))

    view = manager.view(game_id, 0, credentials=own)
    assert view["player"] == 0

    actions = manager.legal_actions(game_id, 0, credentials=own)
    assert _rows(actions["actions"])

    log = manager.log(game_id, 0, credentials=own)
    assert log["seat"] == 0

    applied = manager.apply_action(
        game_id, 0, revision=_int(summary["revision"]), index=0, credentials=own
    )
    assert applied["revision"] != summary["revision"]

    # Own token is not blocked by SeatAccessError: the freshly applied step
    # is still in the undo window, so the undo also succeeds outright.
    undone = manager.undo(
        game_id, 0, revision=_int(applied["revision"]), credentials=own
    )
    assert undone["revision"] == summary["revision"]

    # Nothing awaits confirmation right after an undo, so this raises -- the
    # point is only that it is not blocked by SeatAccessError.
    with pytest.raises(SessionError) as excinfo:
        manager.confirm_turn(
            game_id, 0, revision=_int(undone["revision"]), credentials=own
        )
    assert not isinstance(excinfo.value, SeatAccessError)


# --- release -----------------------------------------------------------------


def test_release_by_holder_frees_the_seat_for_reclaiming() -> None:
    manager, admin = _remote_manager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])
    claim = manager.claim_seat(game_id, 0, "P0", credentials=ANONYMOUS)
    own = Credentials(seat_tokens=frozenset({claim.token}))

    released = manager.release_seat(game_id, 0, credentials=own)
    assert _rows(released["players"])[0]["claimed"] is False

    with pytest.raises(SeatAccessError):
        manager.view(game_id, 0, credentials=own)

    reclaimed = manager.claim_seat(game_id, 0, "P0-again", credentials=ANONYMOUS)
    assert reclaimed.token != claim.token


def test_admin_may_release_another_players_seat() -> None:
    manager, admin = _remote_manager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])
    claim = manager.claim_seat(game_id, 0, "P0", credentials=ANONYMOUS)
    own = Credentials(seat_tokens=frozenset({claim.token}))

    released = manager.release_seat(game_id, 0, credentials=admin)
    assert _rows(released["players"])[0]["claimed"] is False
    with pytest.raises(SeatAccessError):
        manager.view(game_id, 0, credentials=own)


def test_a_stranger_may_not_release_someone_elses_seat() -> None:
    manager, admin = _remote_manager()
    summary = manager.create_game(TWO_HUMANS, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])
    manager.claim_seat(game_id, 0, "P0", credentials=ANONYMOUS)
    neighbour = manager.claim_seat(game_id, 1, "P1", credentials=ANONYMOUS)

    with pytest.raises(SeatAccessError):
        manager.release_seat(game_id, 0, credentials=ANONYMOUS)
    # Holding another seat of the same game proves nothing about this one.
    other_seat = Credentials(seat_tokens=frozenset({neighbour.token}))
    with pytest.raises(SeatAccessError):
        manager.release_seat(game_id, 0, credentials=other_seat)
    assert _rows(manager.summary(game_id)["players"])[0]["claimed"] is True


def test_another_seats_token_does_not_take_over_a_claimed_seat() -> None:
    manager, admin = _remote_manager()
    summary = manager.create_game(TWO_HUMANS, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])
    manager.claim_seat(game_id, 0, "P0", credentials=ANONYMOUS)
    neighbour = manager.claim_seat(game_id, 1, "P1", credentials=ANONYMOUS)

    with pytest.raises(SeatTakenError):
        manager.claim_seat(
            game_id,
            0,
            "P1 again",
            credentials=Credentials(seat_tokens=frozenset({neighbour.token})),
        )
    assert _rows(manager.summary(game_id)["players"])[0]["name"] == "P0"


def test_no_summary_ever_carries_a_seat_token() -> None:
    manager, admin = _remote_manager()
    summary = manager.create_game(TWO_HUMANS, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])
    claim = manager.claim_seat(game_id, 0, "P0", credentials=ANONYMOUS)

    for payload in (
        claim.summary,
        manager.summary(game_id),
        manager.identify(
            game_id, credentials=Credentials(seat_tokens=frozenset({claim.token}))
        ),
        manager.list_games(credentials=admin),
    ):
        assert claim.token not in json.dumps(payload)


def test_admin_releasing_an_unclaimed_seat_is_a_no_op() -> None:
    manager, admin = _remote_manager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])

    released = manager.release_seat(game_id, 0, credentials=admin)
    assert _rows(released["players"])[0]["claimed"] is False


# --- identify ------------------------------------------------------------


def test_identify_in_remote_mode_reports_only_proven_seats() -> None:
    manager, admin = _remote_manager()
    summary = manager.create_game(TWO_HUMANS, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])
    claim0 = manager.claim_seat(game_id, 0, "P0", credentials=ANONYMOUS)
    claim1 = manager.claim_seat(game_id, 1, "P1", credentials=ANONYMOUS)

    none = manager.identify(game_id, credentials=ANONYMOUS)
    assert none["seats"] == [] and none["admin"] is False

    only0 = Credentials(seat_tokens=frozenset({claim0.token}))
    assert manager.identify(game_id, credentials=only0)["seats"] == [0]

    both = Credentials(seat_tokens=frozenset({claim0.token, claim1.token}))
    assert manager.identify(game_id, credentials=both)["seats"] == [0, 1]

    foreign_summary = manager.create_game(HUMAN_FIRST, game_seed=14, credentials=admin)
    foreign_claim = manager.claim_seat(
        _text(foreign_summary["game_id"]), 0, "F", credentials=ANONYMOUS
    )
    foreign = Credentials(seat_tokens=frozenset({foreign_claim.token}))
    assert manager.identify(game_id, credentials=foreign)["seats"] == []

    assert manager.identify(game_id, credentials=admin)["admin"] is True


# --- restore -------------------------------------------------------------


def test_restoring_a_remote_game_clears_seat_claims() -> None:
    manager, admin = _remote_manager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])
    claim = manager.claim_seat(game_id, 0, "P0", credentials=ANONYMOUS)
    own = Credentials(seat_tokens=frozenset({claim.token}))

    document = manager.save_game(game_id, credentials=admin)
    restored = manager.restore_game(document, credentials=admin)

    assert restored["game_id"] != game_id
    players = _rows(restored["players"])
    assert all(entry["claimed"] is False for entry in players)
    assert all(entry["name"] is None for entry in players)

    with pytest.raises(SeatAccessError):
        manager.view(_text(restored["game_id"]), 0, credentials=own)


# --- claim race ------------------------------------------------------------


def test_a_claim_race_has_exactly_one_winner() -> None:
    manager, admin = _remote_manager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13, credentials=admin)
    game_id = _text(summary["game_id"])
    barrier = threading.Barrier(8)
    results: dict[int, SeatClaim | SeatTakenError] = {}

    def attempt(index: int) -> None:
        barrier.wait()
        try:
            results[index] = manager.claim_seat(
                game_id, 0, "racer", credentials=ANONYMOUS
            )
        except SeatTakenError as error:
            results[index] = error

    threads = [threading.Thread(target=attempt, args=(index,)) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    wins = [value for value in results.values() if isinstance(value, SeatClaim)]
    losses = [value for value in results.values() if isinstance(value, SeatTakenError)]
    assert len(results) == 8
    assert len(wins) == 1
    assert len(losses) == 7


# --- _public_seat_kind -------------------------------------------------------


def test_public_seat_kind_hides_a_checkpoint_path_when_asked() -> None:
    assert (
        _public_seat_kind("checkpoint:/a/b/champion.pt", hide_path=True)
        == "checkpoint:champion.pt"
    )
    assert (
        _public_seat_kind("checkpoint:C:\\m\\c.pt", hide_path=True)
        == "checkpoint:c.pt"
    )
    assert (
        _public_seat_kind("checkpoint:/a/b/champion.pt", hide_path=False)
        == "checkpoint:/a/b/champion.pt"
    )
    assert _public_seat_kind("heuristic", hide_path=True) == "heuristic"
    assert _public_seat_kind("heuristic", hide_path=False) == "heuristic"


# --- save_metadata ------------------------------------------------------


def test_save_metadata_hides_the_seed_of_an_unfinished_document_when_asked() -> None:
    unfinished: JsonObject = {"game_seed": 42, "finished": False, "steps": []}
    finished: JsonObject = {"game_seed": 42, "finished": True, "steps": []}

    assert save_metadata(unfinished, hide_unfinished_seed=True)["game_seed"] is None
    assert save_metadata(finished, hide_unfinished_seed=True)["game_seed"] == 42
    assert save_metadata(unfinished)["game_seed"] == 42
