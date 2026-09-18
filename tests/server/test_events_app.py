"""HTTP-level tests for the play server's doorbell endpoint (M14 slice 3):
Server-Sent Events plus presence, ``docs/multiplayer-design.md`` section
4.5. Starlette's ``TestClient`` buffers a response's whole body, so it
cannot exercise an endless stream; these tests run a real ``uvicorn``
server on a background thread and read it with ``httpx2``."""

import json
import logging
import socket
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from types import TracebackType
from typing import Self
from urllib.parse import urlsplit

import httpx2
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")

import uvicorn  # noqa: E402
from fastapi import FastAPI  # noqa: E402

from dune_imperium.server.access import AccessMode  # noqa: E402
from dune_imperium.server.app import create_app  # noqa: E402
from dune_imperium.server.sessions import GameSessionManager  # noqa: E402

ADMIN_KEY = "top-secret-admin-key"
_DEADLINE = 5.0


def _obj(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _rows(value: object) -> list[dict[str, object]]:
    assert isinstance(value, list)
    return [_obj(item) for item in value]


class LiveServer:
    """Run one app with a real uvicorn server on a background thread.

    Starlette's ``TestClient`` cannot stream an endless response body, so
    the doorbell's Server-Sent Events endpoint needs a real socket.
    """

    def __init__(self, app: FastAPI) -> None:
        self._server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=0,
                log_level="warning",
                timeout_graceful_shutdown=1,
            )
        )
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self.base_url = ""

    def __enter__(self) -> Self:
        self._thread.start()
        deadline = time.monotonic() + 10
        while not self._server.started:
            assert time.monotonic() < deadline, "server did not start"
            time.sleep(0.01)
        port = self._server.servers[0].sockets[0].getsockname()[1]
        self.base_url = f"http://127.0.0.1:{port}"
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=10)
        assert not self._thread.is_alive(), "server did not stop"


def _client(server: LiveServer) -> httpx2.Client:
    """One simulated browser: its own cookie jar, bounded by ``_DEADLINE``."""

    return httpx2.Client(base_url=server.base_url, timeout=httpx2.Timeout(_DEADLINE))


def _create(client: httpx2.Client, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "seats": ["human", "heuristic", "heuristic", "heuristic"],
        "game_seed": 13,
    }
    payload.update(overrides)
    response = client.post("/games", json=payload)
    assert response.status_code == 200, response.text
    summary: dict[str, object] = response.json()
    return summary


def _login_admin(client: httpx2.Client) -> None:
    response = client.post("/auth/admin", json={"key": ADMIN_KEY})
    assert response.status_code == 200, response.text


def _seat_online(client: httpx2.Client, game_id: object, seat: int) -> bool:
    response = client.get(f"/games/{game_id}")
    assert response.status_code == 200, response.text
    players = _rows(response.json()["players"])
    online = next(p for p in players if p["seat"] == seat)["online"]
    assert isinstance(online, bool)
    return online


def _wait_until(predicate: Callable[[], bool], *, deadline: float = _DEADLINE) -> None:
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.02)
    assert predicate(), "condition was not met before the deadline"


def _parse_block(collected: list[str]) -> tuple[str, dict[str, object] | None]:
    if collected[0].startswith(":"):
        return "heartbeat", None
    event = next(
        line.removeprefix("event: ")
        for line in collected
        if line.startswith("event: ")
    )
    data_line = next(line for line in collected if line.startswith("data: "))
    payload = json.loads(data_line.removeprefix("data: "))
    assert isinstance(payload, dict)
    return event, payload


def _read_block(lines: Iterator[str]) -> tuple[str, dict[str, object] | None]:
    """Read one SSE block: its lines through the blank line that ends it."""

    collected: list[str] = []
    for line in lines:
        if line == "":
            return _parse_block(collected)
        collected.append(line)
    raise AssertionError("the stream ended before a complete event was read")


def _read_event(
    lines: Iterator[str], *, deadline: float = _DEADLINE
) -> tuple[str, dict[str, object] | None]:
    """Read blocks until a named event arrives, skipping heartbeat comments."""

    end = time.monotonic() + deadline
    while True:
        event, payload = _read_block(lines)
        if event != "heartbeat":
            return event, payload
        assert time.monotonic() < end, "only heartbeats arrived before the deadline"


def _parse_all_blocks(
    raw_lines: list[str],
) -> list[tuple[str, dict[str, object] | None]]:
    """Split a fully-collected line list into its SSE blocks."""

    blocks: list[tuple[str, dict[str, object] | None]] = []
    current: list[str] = []
    for line in raw_lines:
        if line == "":
            if current:
                blocks.append(_parse_block(current))
                current = []
            continue
        current.append(line)
    if current:
        blocks.append(_parse_block(current))
    return blocks


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    # The image locations are pinned to nonexistent paths so the tests
    # behave identically with or without the machine-local caches. The fast
    # heartbeat makes an idle stream produce a line at least every 50 ms.
    return create_app(
        saves_dir=tmp_path / "saves",
        card_images_dir=tmp_path / "no-images",
        icons_dir=tmp_path / "no-icons",
        tokens_dir=tmp_path / "no-tokens",
        board_image=tmp_path / "no-map.jpg",
        bene_tleilax_image=tmp_path / "no-bene-tleilax.jpg",
        heartbeat_seconds=0.05,
    )


@pytest.fixture
def remote_app(tmp_path: Path) -> FastAPI:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key=ADMIN_KEY)
    return create_app(
        manager,
        saves_dir=tmp_path / "saves",
        card_images_dir=tmp_path / "no-images",
        icons_dir=tmp_path / "no-icons",
        tokens_dir=tmp_path / "no-tokens",
        board_image=tmp_path / "no-map.jpg",
        bene_tleilax_image=tmp_path / "no-bene-tleilax.jpg",
        heartbeat_seconds=0.05,
    )


# --- unknown game ------------------------------------------------------------


def test_an_unknown_games_event_stream_is_404(app: FastAPI) -> None:
    with LiveServer(app) as server, _client(server) as client:
        response = client.get("/games/absent/events")

        assert response.status_code == 404
        assert isinstance(response.json(), dict)


# --- headers -------------------------------------------------------------


def test_the_streams_headers(app: FastAPI) -> None:
    with LiveServer(app) as server, _client(server) as client:
        summary = _create(client)
        game_id = summary["game_id"]

        with client.stream("GET", f"/games/{game_id}/events") as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            assert response.headers["cache-control"] == "no-cache"
            assert response.headers["x-accel-buffering"] == "no"
            assert "content-encoding" not in response.headers


# --- a client that leaves before the first byte -----------------------------


def test_a_stream_closed_before_its_first_byte_is_not_a_server_error(
    app: FastAPI,
) -> None:
    # A page that reopens its doorbell (after a seat claim, M14 slice 4)
    # closes an EventSource it has only just asked for. Behind Starlette's
    # ``BaseHTTPMiddleware`` every such request made uvicorn log "Exception
    # in ASGI application" (RuntimeError: No response returned.) -- measured
    # 4 out of 4 with a socket closed within a millisecond of the request.
    records: list[logging.LogRecord] = []

    class Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    collector = Collect(level=logging.ERROR)
    with LiveServer(app) as server, _client(server) as client:
        # uvicorn configures its loggers when the server starts, and they
        # do not propagate to the root logger that ``caplog`` listens on.
        uvicorn_errors = logging.getLogger("uvicorn.error")
        uvicorn_errors.addHandler(collector)
        try:
            game_id = _create(client)["game_id"]
            address = urlsplit(server.base_url)
            assert address.hostname is not None and address.port is not None
            request = (
                f"GET /games/{game_id}/events HTTP/1.1\r\n"
                f"Host: {address.netloc}\r\n"
                "Accept: text/event-stream\r\n\r\n"
            ).encode()
            for _ in range(4):
                with socket.create_connection((address.hostname, address.port)) as raw:
                    raw.sendall(request)
            # The server is still healthy, and a stream opened now greets.
            with client.stream("GET", f"/games/{game_id}/events") as response:
                lines = response.iter_lines()
                event, _payload = _read_event(lines)
                assert event == "hello"
            # Nobody who left that early was ever counted as present.
            assert _seat_online(client, game_id, 0) is False
        finally:
            uvicorn_errors.removeHandler(collector)

    assert [record.getMessage() for record in records] == []


# --- hello ---------------------------------------------------------------


def test_the_first_event_is_hello_with_the_eight_keys(app: FastAPI) -> None:
    with LiveServer(app) as server, _client(server) as client:
        summary = _create(client)
        game_id = summary["game_id"]

        with client.stream("GET", f"/games/{game_id}/events") as response:
            lines = response.iter_lines()
            event, payload = _read_block(lines)

            assert event == "hello"
            assert payload is not None
            assert set(payload) == {
                "seq",
                "revision",
                "undo_count",
                "log_count",
                "decision_owner",
                "confirmation",
                "finished",
                "players",
            }


# --- change on another client's action ---------------------------------------


def test_another_clients_action_produces_a_change_event(app: FastAPI) -> None:
    with (
        LiveServer(app) as server,
        _client(server) as watcher,
        _client(server) as actor,
    ):
        summary = _create(watcher)
        game_id = summary["game_id"]

        with watcher.stream("GET", f"/games/{game_id}/events") as response:
            lines = response.iter_lines()
            assert _read_block(lines)[0] == "hello"

            applied = actor.post(
                f"/games/{game_id}/actions",
                json={"seat": 0, "revision": summary["revision"], "index": 0},
            )
            assert applied.status_code == 200, applied.text

            event, payload = _read_event(lines)

            assert event == "change"
            assert payload is not None
            assert payload["revision"] == applied.json()["revision"]


# --- heartbeats ------------------------------------------------------------


def test_an_idle_stream_delivers_heartbeats(app: FastAPI) -> None:
    with LiveServer(app) as server, _client(server) as client:
        summary = _create(client)
        game_id = summary["game_id"]

        with client.stream("GET", f"/games/{game_id}/events") as response:
            lines = response.iter_lines()
            assert _read_block(lines)[0] == "hello"

            assert _read_block(lines)[0] == "heartbeat"


# --- delete ----------------------------------------------------------------


def test_deleting_the_game_closes_the_stream_and_the_reader_ends_itself(
    app: FastAPI,
) -> None:
    with (
        LiveServer(app) as server,
        _client(server) as watcher,
        _client(server) as deleter,
    ):
        summary = _create(watcher)
        game_id = summary["game_id"]
        raw_lines: list[str] = []
        greeted = threading.Event()

        def read_until_the_server_ends_it() -> None:
            with watcher.stream("GET", f"/games/{game_id}/events") as response:
                for line in response.iter_lines():
                    raw_lines.append(line)
                    if not greeted.is_set() and line == "":
                        greeted.set()

        thread = threading.Thread(target=read_until_the_server_ends_it, daemon=True)
        thread.start()
        assert greeted.wait(_DEADLINE), "the stream never greeted"

        deleted = deleter.delete(f"/games/{game_id}")
        assert deleted.status_code == 200, deleted.text

        thread.join(timeout=_DEADLINE)

        assert not thread.is_alive(), "the reader thread did not end by itself"
        blocks = _parse_all_blocks(raw_lines)
        assert blocks[0][0] == "hello"
        assert blocks[-1] == ("closed", {})


# --- OPEN presence over HTTP --------------------------------------------------


def test_open_presence_over_http(app: FastAPI) -> None:
    with (
        LiveServer(app) as server,
        _client(server) as player,
        _client(server) as onlooker,
    ):
        summary = _create(player)
        game_id = summary["game_id"]

        with player.stream("GET", f"/games/{game_id}/events") as response:
            # Bound to a name on purpose: dropping the line iterator closes
            # the connection, and the server rightly takes presence down.
            lines = response.iter_lines()
            assert _read_block(lines)[0] == "hello"

            assert _seat_online(onlooker, game_id, 0) is True

        _wait_until(lambda: _seat_online(onlooker, game_id, 0) is False)


# --- REMOTE presence over HTTP ------------------------------------------------


def test_remote_presence_over_http(remote_app: FastAPI) -> None:
    with (
        LiveServer(remote_app) as server,
        _client(server) as admin,
        _client(server) as player0,
        _client(server) as player1,
        _client(server) as stranger,
    ):
        _login_admin(admin)
        summary = _create(admin, seats=["human", "human", "heuristic", "heuristic"])
        game_id = summary["game_id"]
        claimed0 = player0.post(
            f"/games/{game_id}/seats/0/claim", json={"name": "P0"}
        )
        assert claimed0.status_code == 200, claimed0.text
        claimed1 = player1.post(
            f"/games/{game_id}/seats/1/claim", json={"name": "P1"}
        )
        assert claimed1.status_code == 200, claimed1.text

        # A cookie-less client's stream lights nothing.
        with stranger.stream("GET", f"/games/{game_id}/events") as response:
            lines = response.iter_lines()
            assert _read_block(lines)[0] == "hello"

            assert _seat_online(admin, game_id, 0) is False
            assert _seat_online(admin, game_id, 1) is False

        with player0.stream("GET", f"/games/{game_id}/events") as response:
            lines = response.iter_lines()
            assert _read_block(lines)[0] == "hello"

            assert _seat_online(admin, game_id, 0) is True
            assert _seat_online(admin, game_id, 1) is False

        _wait_until(lambda: _seat_online(admin, game_id, 0) is False)
