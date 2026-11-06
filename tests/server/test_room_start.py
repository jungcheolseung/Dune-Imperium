"""A remote room that draws its human seats when a player starts it.

User decision 2026-10-25 (play feedback item 5): after the host creates a
room nobody sees the game until every human seat is taken; then any seated
player (or the host) presses "게임 시작", the people are dealt out to the
human seats at random and the game begins. Who sits where is a table
convention, not a rule: the rules do not seat players and the First Player
comes from the Objectives [Main p. 5] (docs/rules/setup-and-game-flow.md).

Before the start a place in the room reads nothing of any seat (its hand
could be another seat's once the seats are drawn), and the game does not
move: no AI step, no clock.
"""

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from dune_imperium.server.access import AccessMode, Credentials  # noqa: E402
from dune_imperium.server.app import (  # noqa: E402
    ADMIN_COOKIE,
    create_app,
    seat_cookie_name,
)
from dune_imperium.server.sessions import (  # noqa: E402
    GameSessionManager,
    UnknownGameError,
)

ADMIN_KEY = "room-start-admin-key"
SEATS = ["human", "heuristic", "human", "heuristic"]
HUMANS = (0, 2)


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key=ADMIN_KEY)
    return create_app(
        manager,
        saves_dir=tmp_path / "saves",
        card_images_dir=tmp_path / "no-images",
        icons_dir=tmp_path / "no-icons",
        tokens_dir=tmp_path / "no-tokens",
        board_image=tmp_path / "no-map.jpg",
        bene_tleilax_image=tmp_path / "no-bene-tleilax.jpg",
    )


def _host(app: FastAPI) -> TestClient:
    client = TestClient(app)
    assert client.post("/auth/admin", json={"key": ADMIN_KEY}).status_code == 200
    assert ADMIN_COOKIE in client.cookies
    return client


def _room(host: TestClient, seed: int = 21) -> str:
    created = host.post(
        "/games", json={"seats": SEATS, "game_seed": seed, "seats_at_start": True}
    )
    assert created.status_code == 200, created.text
    summary = created.json()
    assert summary["awaiting_start"] is True
    return str(summary["game_id"])


def _join(app: FastAPI, game_id: str, seat: int, name: str) -> TestClient:
    client = TestClient(app)
    claimed = client.post(f"/games/{game_id}/seats/{seat}/claim", json={"name": name})
    assert claimed.status_code == 200, claimed.text
    return client


def _you(client: TestClient, game_id: str) -> list[int]:
    seats: list[int] = client.get(f"/games/{game_id}/snapshot").json()["you"]["seats"]
    return seats


# Seed 1 opens on an AI seat's decision (seat 3 holds the First Player
# Objective), so a game that moved would show its steps.
AI_FIRST_SEED = 1


def test_a_waiting_room_does_not_move_and_shows_no_seat(app: FastAPI) -> None:
    host = _host(app)
    game_id = _room(host, AI_FIRST_SEED)
    ada = _join(app, game_id, 0, "Ada")

    # Nothing has advanced: the AI seat's decision waits, no step, no clock.
    summary = ada.get(f"/games/{game_id}").json()
    assert summary["decision"]["owner"] == 3
    assert summary["revision"] == 0
    assert summary["log_count"] == 0
    assert summary["thinking"] is None
    assert summary["awaiting_start"] is True
    # A place in the room is not a seat: every seat read and act is refused.
    for path in (
        f"/games/{game_id}/snapshot?seat=0",
        f"/games/{game_id}/seats/0/view",
        f"/games/{game_id}/seats/0/actions",
        f"/games/{game_id}/log?seat=0",
        f"/games/{game_id}/vp-ledger",
    ):
        response = ada.get(path)
        assert response.status_code == 409, (path, response.text)
    acted = ada.post(
        f"/games/{game_id}/actions",
        json={"seat": 0, "revision": 0, "index": 0, "undo_count": 0},
    )
    assert acted.status_code == 409, acted.text
    # The seatless snapshot still says who this browser is in the room.
    assert _you(ada, game_id) == [0]

    _join(app, game_id, 2, "Bo")
    started = ada.post(f"/games/{game_id}/start").json()
    # Started, the game moves on to its first human decision.
    assert started["revision"] > 0
    assert started["decision"]["owner"] in HUMANS


def test_the_start_waits_for_every_human_seat(app: FastAPI) -> None:
    host = _host(app)
    game_id = _room(host)
    ada = _join(app, game_id, 0, "Ada")
    stranger = TestClient(app)

    early = ada.post(f"/games/{game_id}/start")
    assert early.status_code == 400
    _join(app, game_id, 2, "Bo")
    # Someone without a place in the room may not start it.
    assert stranger.post(f"/games/{game_id}/start").status_code == 403


def test_starting_deals_the_people_to_the_human_seats_at_random(app: FastAPI) -> None:
    deals: set[tuple[int, int]] = set()
    for seed in range(12):
        host = _host(app)
        game_id = _room(host, seed)
        ada = _join(app, game_id, 0, "Ada")
        bo = _join(app, game_id, 2, "Bo")

        started = bo.post(f"/games/{game_id}/start")
        assert started.status_code == 200, started.text
        summary = started.json()
        assert summary["awaiting_start"] is False
        ada_seat, bo_seat = _you(ada, game_id), _you(bo, game_id)
        assert sorted(ada_seat + bo_seat) == list(HUMANS)
        # Each name went with its player.
        names = {info["seat"]: info["name"] for info in summary["players"]}
        assert names[ada_seat[0]] == "Ada" and names[bo_seat[0]] == "Bo"
        # The seats are the players' now: each reads its own and no other.
        mine = ada.get(f"/games/{game_id}/snapshot?seat={ada_seat[0]}")
        assert mine.status_code == 200, mine.text
        theirs = ada.get(f"/games/{game_id}/snapshot?seat={bo_seat[0]}")
        assert theirs.status_code == 403
        assert ada.post(f"/games/{game_id}/start").status_code == 400
        deals.add((ada_seat[0], bo_seat[0]))
    assert deals == {(0, 2), (2, 0)}


def test_the_host_may_start_and_an_open_server_never_waits(
    app: FastAPI, tmp_path: Path
) -> None:
    host = _host(app)
    game_id = _room(host)
    _join(app, game_id, 0, "Ada")
    _join(app, game_id, 2, "Bo")
    assert host.post(f"/games/{game_id}/start").status_code == 200

    open_app = create_app(
        GameSessionManager(),
        saves_dir=tmp_path / "open-saves",
        card_images_dir=tmp_path / "no-images",
        icons_dir=tmp_path / "no-icons",
        tokens_dir=tmp_path / "no-tokens",
        board_image=tmp_path / "no-map.jpg",
        bene_tleilax_image=tmp_path / "no-bene-tleilax.jpg",
    )
    refused = TestClient(open_app).post(
        "/games", json={"seats": SEATS, "game_seed": 3, "seats_at_start": True}
    )
    assert refused.status_code == 400


def test_a_room_without_waiting_is_as_before(app: FastAPI) -> None:
    host = _host(app)
    created = host.post("/games", json={"seats": SEATS, "game_seed": 21})
    summary = created.json()
    assert summary["awaiting_start"] is False
    game_id = str(summary["game_id"])
    ada = _join(app, game_id, 0, "Ada")
    assert ada.get(f"/games/{game_id}/snapshot?seat=0").status_code == 200
    assert ada.post(f"/games/{game_id}/start").status_code == 400


def test_a_later_claim_never_overwrites_a_drawn_seats_cookie(app: FastAPI) -> None:
    # Review finding (2026-10-25): a cookie keeps the name of the place it
    # was claimed for. Ada, claimed at place 0 and drawn to seat 2, claims
    # the freed seat 0 too: the claim must not overwrite the cookie that
    # still carries seat 2's token, or Ada is locked out of seat 2.
    for seed in range(40):
        host = _host(app)
        game_id = _room(host, seed)
        ada = _join(app, game_id, 0, "Ada")
        bo = _join(app, game_id, 2, "Bo")
        assert bo.post(f"/games/{game_id}/start").status_code == 200
        if host.get(f"/games/{game_id}").json()["players"][0]["name"] == "Bo":
            break
    else:
        pytest.fail("no seed drew Ada away from her place")
    # Bo leaves seat 0; Ada, who has asked for nothing since the start,
    # claims it.
    assert host.post(f"/games/{game_id}/seats/0/release").status_code == 200
    claimed = ada.post(f"/games/{game_id}/seats/0/claim", json={"name": "Ada"})
    assert claimed.status_code == 200, claimed.text
    assert sorted(_you(ada, game_id)) == [0, 2]
    for seat in (0, 2):
        response = ada.get(f"/games/{game_id}/snapshot?seat={seat}")
        assert response.status_code == 200, (seat, response.text)


def test_a_snapshot_names_each_cookie_after_its_drawn_seat(app: FastAPI) -> None:
    for seed in range(40):
        host = _host(app)
        game_id = _room(host, seed)
        ada = _join(app, game_id, 0, "Ada")
        _join(app, game_id, 2, "Bo")
        assert host.post(f"/games/{game_id}/start").status_code == 200
        if _you(ada, game_id) == [2]:
            break
    else:
        pytest.fail("no seed drew Ada away from her place")
    names = {cookie.name for cookie in ada.cookies.jar}
    assert seat_cookie_name(game_id, 2) in names
    assert seat_cookie_name(game_id, 0) not in names


def test_a_waiting_room_is_not_saved_and_a_deleted_one_never_starts(
    app: FastAPI,
) -> None:
    host = _host(app)
    game_id = _room(host)
    # A save keeps no wait: its load would start without drawing the seats.
    assert host.post(f"/games/{game_id}/save", json={}).status_code == 409

    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key=ADMIN_KEY)
    admin = Credentials(seat_tokens=frozenset(), admin_key=ADMIN_KEY)
    summary = manager.create_game(
        tuple(SEATS), game_seed=1, seats_at_start=True, credentials=admin
    )
    room = str(summary["game_id"])
    manager.claim_seat(room, 0, "Ada")
    manager.claim_seat(room, 2, "Bo")
    # A delete that won the lock first: the start finds the game closed.
    session = manager._get(room)
    session.closed = True
    with pytest.raises(UnknownGameError):
        manager.start_game(room, credentials=admin)
    assert session.awaiting_start is True
