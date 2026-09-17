"""HTTP-level tests for the play server's snapshot endpoint and its gzip
compression (M14 slice 2, needs the ``ui`` extra), ``docs/multiplayer-
design.md`` section 4.6."""

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from dune_imperium.server.access import AccessMode  # noqa: E402
from dune_imperium.server.app import create_app  # noqa: E402
from dune_imperium.server.sessions import GameSessionManager  # noqa: E402

ADMIN_KEY = "top-secret-admin-key"


def _obj(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _int(value: object) -> int:
    assert isinstance(value, int)
    return value


def _text(value: object) -> str:
    assert isinstance(value, str)
    return value


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    # The image locations are pinned to nonexistent paths so the tests
    # behave identically with or without the machine-local caches.
    return TestClient(
        create_app(
            saves_dir=tmp_path / "saves",
            card_images_dir=tmp_path / "no-images",
            icons_dir=tmp_path / "no-icons",
            board_image=tmp_path / "no-map.jpg",
            bene_tleilax_image=tmp_path / "no-bene-tleilax.jpg",
        )
    )


def _create(client: TestClient, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "seats": ["human", "heuristic", "heuristic", "heuristic"],
        "game_seed": 13,
    }
    payload.update(overrides)
    response = client.post("/games", json=payload)
    assert response.status_code == 200, response.text
    summary: dict[str, object] = response.json()
    return summary


# --- shape and errors --------------------------------------------------


def test_a_seat_snapshot_over_http_has_the_five_keys(client: TestClient) -> None:
    summary = _create(client)
    game_id = summary["game_id"]

    response = client.get(f"/games/{game_id}/snapshot", params={"seat": 0})

    assert response.status_code == 200, response.text
    assert set(response.json()) == {"summary", "you", "view", "actions", "log"}


def test_a_seatless_snapshot_over_http_is_summary_and_you(client: TestClient) -> None:
    summary = _create(client)
    game_id = summary["game_id"]

    response = client.get(f"/games/{game_id}/snapshot")

    assert response.status_code == 200, response.text
    assert set(response.json()) == {"summary", "you"}


def test_snapshot_errors_map_to_the_conventional_http_status_codes(
    client: TestClient,
) -> None:
    summary = _create(client)
    game_id = summary["game_id"]

    ai_seat = client.get(f"/games/{game_id}/snapshot", params={"seat": 2})
    assert ai_seat.status_code == 403

    unknown_game = client.get("/games/absent/snapshot")
    assert unknown_game.status_code == 404

    negative_cursor = client.get(
        f"/games/{game_id}/snapshot", params={"seat": 0, "log_after": -1}
    )
    assert negative_cursor.status_code == 400

    current = _obj(
        client.get(f"/games/{game_id}/snapshot", params={"seat": 0}).json()["log"]
    )
    too_far = client.get(
        f"/games/{game_id}/snapshot",
        params={
            "seat": 0,
            "log_after": _int(current["count"]) + 1,
            "log_epoch": _text(current["epoch"]),
        },
    )
    assert too_far.status_code == 400


# --- incremental flow ----------------------------------------------------


def test_the_incremental_flow_over_http(client: TestClient) -> None:
    summary = _create(client)
    game_id = summary["game_id"]

    before = client.get(f"/games/{game_id}/snapshot", params={"seat": 0})
    assert before.status_code == 200, before.text
    before_log = _obj(before.json()["log"])
    old_count = _int(before_log["count"])
    old_epoch = _text(before_log["epoch"])

    applied = client.post(
        f"/games/{game_id}/actions",
        json={"seat": 0, "revision": summary["revision"], "index": 0},
    )
    assert applied.status_code == 200, applied.text

    after = client.get(
        f"/games/{game_id}/snapshot",
        params={"seat": 0, "log_after": old_count, "log_epoch": old_epoch},
    )
    assert after.status_code == 200, after.text
    after_log = _obj(after.json()["log"])
    assert after_log["from"] == old_count

    full = client.get(f"/games/{game_id}/log", params={"seat": 0, "after": old_count})
    assert full.status_code == 200, full.text
    assert after_log["entries"] == full.json()["entries"]


# --- REMOTE access over HTTP ----------------------------------------------


@pytest.fixture
def remote_app(tmp_path: Path) -> FastAPI:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key=ADMIN_KEY)
    return create_app(
        manager,
        saves_dir=tmp_path / "saves",
        card_images_dir=tmp_path / "no-images",
        icons_dir=tmp_path / "no-icons",
        board_image=tmp_path / "no-map.jpg",
        bene_tleilax_image=tmp_path / "no-bene-tleilax.jpg",
    )


def _admin_client(app: FastAPI) -> TestClient:
    """A fresh browser logged in as the host."""

    client = TestClient(app)
    response = client.post("/auth/admin", json={"key": ADMIN_KEY})
    assert response.status_code == 200, response.text
    return client


def test_remote_snapshot_access_is_scoped_per_browser(remote_app: FastAPI) -> None:
    admin = _admin_client(remote_app)
    summary = _create(
        admin, seats=["human", "human", "heuristic", "heuristic"], game_seed=13
    )
    game_id = summary["game_id"]

    player0 = TestClient(remote_app)
    claimed0 = player0.post(f"/games/{game_id}/seats/0/claim", json={"name": "P0"})
    assert claimed0.status_code == 200, claimed0.text
    player1 = TestClient(remote_app)
    claimed1 = player1.post(f"/games/{game_id}/seats/1/claim", json={"name": "P1"})
    assert claimed1.status_code == 200, claimed1.text

    own = player0.get(f"/games/{game_id}/snapshot", params={"seat": 0})
    assert own.status_code == 200, own.text

    # Another player's cookie does not open seat 0.
    other_player = player1.get(f"/games/{game_id}/snapshot", params={"seat": 0})
    assert other_player.status_code == 403

    # A cookie-less client is refused a seat but may still read the
    # seatless snapshot: knowing the game id is the room ticket.
    stranger = TestClient(remote_app)
    assert (
        stranger.get(f"/games/{game_id}/snapshot", params={"seat": 0}).status_code
        == 403
    )
    seatless = stranger.get(f"/games/{game_id}/snapshot")
    assert seatless.status_code == 200, seatless.text
    you = _obj(seatless.json()["you"])
    assert you["seats"] == []
    assert you["admin"] is False

    # The host plays too and must not reach a seat through the admin cookie.
    admin_only = admin.get(f"/games/{game_id}/snapshot", params={"seat": 0})
    assert admin_only.status_code == 403


# --- gzip ------------------------------------------------------------------


def test_large_json_responses_are_gzipped(client: TestClient) -> None:
    summary = _create(client)
    game_id = summary["game_id"]

    seat_snapshot = client.get(f"/games/{game_id}/snapshot", params={"seat": 0})
    assert seat_snapshot.status_code == 200, seat_snapshot.text
    assert seat_snapshot.headers.get("content-encoding") == "gzip"
    # The test client decodes transparently: the body is still the same JSON.
    assert set(seat_snapshot.json()) == {"summary", "you", "view", "actions", "log"}

    script = client.get("/static/app.js")
    assert script.status_code == 200
    assert script.headers.get("content-encoding") == "gzip"

    catalog = client.get("/catalog")
    assert catalog.status_code == 200
    assert catalog.headers.get("content-encoding") == "gzip"


def test_small_json_responses_are_not_gzipped(client: TestClient) -> None:
    summary = _create(client)
    game_id = summary["game_id"]

    # ``/me`` stays a few hundred bytes; a summary hovers around the 1024-byte
    # threshold and would make this test depend on unrelated summary fields.
    me = client.get(f"/games/{game_id}/me")
    assert me.status_code == 200, me.text
    assert len(me.content) < 512
    assert "content-encoding" not in me.headers


def test_a_jpeg_board_image_is_not_gzipped_even_though_it_is_large(
    tmp_path: Path,
) -> None:
    board = tmp_path / "map.jpg"
    board.write_bytes(b"\xff\xd8" + b"x" * 5000)
    client = TestClient(
        create_app(
            saves_dir=tmp_path / "saves",
            card_images_dir=tmp_path / "no-images",
            icons_dir=tmp_path / "no-icons",
            board_image=board,
            bene_tleilax_image=tmp_path / "no-bene-tleilax.jpg",
        )
    )

    response = client.get("/board-image")

    assert response.status_code == 200
    assert len(response.content) >= 1024
    assert "content-encoding" not in response.headers
