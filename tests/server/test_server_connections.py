"""The play server's connection limits against a real uvicorn (2026-11
security review, finding 1; ``server.connections``).

Each test serves a tiny ASGI app with ``guarded_h11_protocol`` on a
loopback port in a thread, and talks to it over plain sockets, the way the
review's ``probe_conns.py`` held half-sent requests open.
"""

import asyncio
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

uvicorn = pytest.importorskip("uvicorn")

from starlette.types import Receive, Scope, Send  # noqa: E402
from uvicorn import Server  # noqa: E402

from dune_imperium.cli import server as server_cli  # noqa: E402
from dune_imperium.server.connections import (  # noqa: E402
    DEFAULT_MAX_CONNECTIONS,
    DEFAULT_MAX_PER_CLIENT,
    DEFAULT_REQUEST_SECONDS,
    ConnectionLimits,
    fitting_backlog,
    fitting_max_connections,
    guarded_h11_protocol,
    raise_open_file_limit,
)

# Long enough for a loaded machine to send a request; short for the tests.
_DEADLINE = 1.0


async def _app(scope: Scope, receive: Receive, send: Send) -> None:
    """Answer ``/slow`` after 1.5 s, ``/echo`` with the body it read, ``/big``
    with 16 MiB, and anything else at once."""

    if scope["type"] != "http":
        return
    body = b""
    # ``/big`` answers 16 MiB without reading the body, as the play server's
    # picture routes do.
    more = scope["path"] != "/big"
    while more:
        message = await receive()
        if message["type"] == "http.disconnect":
            return
        body += message.get("body", b"")
        more = message.get("more_body", False)
    if scope["path"] == "/slow":
        await asyncio.sleep(_DEADLINE * 1.5)
    reply = body if scope["path"] == "/echo" else b"ok"
    if scope["path"] == "/big":
        reply = b"x" * (16 << 20)
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-length", str(len(reply)).encode())],
        }
    )
    await send({"type": "http.response.body", "body": reply})


@contextmanager
def _serving(limits: ConnectionLimits) -> Iterator[int]:
    with _serving_with_state(limits) as (port, _server):
        yield port


@contextmanager
def _serving_with_state(
    limits: ConnectionLimits,
) -> Iterator[tuple[int, Server]]:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
    config = uvicorn.Config(
        _app,
        host="127.0.0.1",
        port=port,
        http=guarded_h11_protocol(limits),
        lifespan="off",
        log_level="warning",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "the server did not start"
        time.sleep(0.01)
    try:
        yield port, server
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def _connect(port: int) -> socket.socket:
    return socket.create_connection(("127.0.0.1", port), timeout=5)


def _closed_by_server(sock: socket.socket, within: float) -> bool:
    """Whether the server closes ``sock`` within ``within`` seconds."""

    sock.settimeout(within)
    try:
        return sock.recv(1024) == b""
    except TimeoutError:
        return False
    except ConnectionResetError:
        return True


def _get(port: int, path: str = "/") -> bytes:
    """The answer to ``GET path``; empty if the server closed the connection
    (a refused connection may also be reset, having unread data)."""

    data = b""
    with _connect(port) as sock:
        try:
            sock.sendall(f"GET {path} HTTP/1.1\r\nHost: x\r\n\r\n".encode())
            while b"\r\n\r\n" not in data or not data.endswith(b"ok"):
                chunk = sock.recv(1024)
                if not chunk:
                    break
                data += chunk
        except (ConnectionResetError, BrokenPipeError):
            pass
    return data


def test_a_half_sent_request_head_is_dropped() -> None:
    with _serving(ConnectionLimits(request_seconds=_DEADLINE)) as port:
        sock = _connect(port)
        sock.sendall(b"GET /whoami HTTP/1.1\r\nHost: x\r\n")  # no blank line
        started = time.monotonic()
        assert _closed_by_server(sock, within=_DEADLINE * 4)
        assert time.monotonic() - started >= _DEADLINE * 0.8
        sock.close()


def test_a_connection_that_never_speaks_is_dropped() -> None:
    with _serving(ConnectionLimits(request_seconds=_DEADLINE)) as port:
        sock = _connect(port)
        assert _closed_by_server(sock, within=_DEADLINE * 4)
        sock.close()


def test_trickling_bytes_buys_no_time() -> None:
    with _serving(ConnectionLimits(request_seconds=_DEADLINE)) as port:
        sock = _connect(port)
        started = time.monotonic()
        closed = False
        for byte in b"GET / HTTP/1.1\r\nHost: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx":
            try:
                sock.sendall(bytes([byte]))
            except OSError:
                closed = True
                break
            if _closed_by_server(sock, within=0.1):
                closed = True
                break
        assert closed
        assert time.monotonic() - started < _DEADLINE * 3
        sock.close()


def test_a_body_that_stops_arriving_is_dropped_too() -> None:
    with _serving(ConnectionLimits(request_seconds=_DEADLINE)) as port:
        sock = _connect(port)
        sock.sendall(
            b"POST /echo HTTP/1.1\r\nHost: x\r\nContent-Length: 100\r\n\r\n0123456789"
        )
        assert _closed_by_server(sock, within=_DEADLINE * 4)
        sock.close()


def test_a_pipelined_request_gets_its_own_deadline() -> None:
    # Codex review of this branch (2026-11-03): uvicorn starts a request
    # that waited behind another from on_response_complete, not from
    # data_received, so it had no deadline at all.
    with _serving(ConnectionLimits(request_seconds=_DEADLINE)) as port:
        sock = _connect(port)
        sock.sendall(
            b"GET / HTTP/1.1\r\nHost: x\r\n\r\n"
            b"POST /echo HTTP/1.1\r\nHost: x\r\nContent-Length: 10\r\n\r\n{"
        )
        sock.settimeout(_DEADLINE * 4)
        data = b""
        try:
            while True:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                data += chunk
        except ConnectionResetError:
            pass
        assert data.startswith(b"HTTP/1.1 200")  # the first was answered
        assert data.count(b"HTTP/1.1") == 1  # and the second dropped
        sock.close()


def test_a_dropped_connection_is_gone_even_if_its_peer_stops_reading() -> None:
    # Codex review of this branch (2026-11-03): ``close`` waits for a peer
    # that reads nothing to take the unsent answer, and the guard had stopped
    # counting it. Dropping aborts: the socket and its task go at once.
    limits = ConnectionLimits(max_per_client=2, request_seconds=_DEADLINE)
    with _serving_with_state(limits) as (port, server):
        stalled = []
        for _ in range(2):
            sock = socket.socket()
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
            sock.connect(("127.0.0.1", port))
            # A body the GET never reads keeps the request "arriving".
            sock.sendall(b"GET /big HTTP/1.1\r\nHost: x\r\nContent-Length: 2\r\n\r\n{")
            stalled.append(sock)
        time.sleep(_DEADLINE * 2.5)
        assert len(server.server_state.connections) == 0
        assert len(server.server_state.tasks) == 0
        assert _get(port).startswith(b"HTTP/1.1 200")
        for sock in stalled:
            sock.close()


def test_an_answer_may_take_longer_than_the_request_deadline() -> None:
    # An AI's turn or a doorbell stream: the request has arrived, so the
    # deadline is off until the next one starts.
    with _serving(ConnectionLimits(request_seconds=_DEADLINE)) as port:
        with _connect(port) as sock:
            sock.sendall(b"GET /slow HTTP/1.1\r\nHost: x\r\n\r\n")
            sock.settimeout(_DEADLINE * 5)
            data = b""
            while not data.endswith(b"ok"):
                chunk = sock.recv(1024)
                assert chunk, "the server closed a request that had arrived"
                data += chunk
            assert data.startswith(b"HTTP/1.1 200")
            # The same connection carries the next request, and a body.
            sock.sendall(
                b"POST /echo HTTP/1.1\r\nHost: x\r\nContent-Length: 2\r\n\r\nok"
            )
            data = b""
            while not data.endswith(b"ok"):
                chunk = sock.recv(1024)
                assert chunk
                data += chunk
            assert data.startswith(b"HTTP/1.1 200")


def test_one_address_cannot_hold_every_connection() -> None:
    limits = ConnectionLimits(max_per_client=4, request_seconds=_DEADLINE * 3)
    with _serving(limits) as port:
        held = [_connect(port) for _ in range(4)]
        for sock in held:
            sock.sendall(b"GET / HTTP/1.1\r\nHost: x\r\n")
        time.sleep(0.2)
        extra = _connect(port)
        # One past the cap is closed at once, the held ones are not.
        assert _closed_by_server(extra, within=1.0)
        assert not any(_closed_by_server(sock, within=0.05) for sock in held)
        extra.close()
        for sock in held:
            sock.close()
        time.sleep(0.2)
        assert _get(port).startswith(b"HTTP/1.1 200")


def test_the_server_never_holds_more_than_its_cap() -> None:
    limits = ConnectionLimits(
        max_connections=6, max_per_client=100, request_seconds=_DEADLINE * 3
    )
    with _serving(limits) as port:
        held = [_connect(port) for _ in range(6)]
        time.sleep(0.2)
        extra = _connect(port)
        assert _closed_by_server(extra, within=1.0)
        extra.close()
        for sock in held:
            sock.close()


def test_honest_requests_come_back_once_the_half_sent_ones_are_dropped() -> None:
    # The review's attack in small: the address's slots all hold half-sent
    # heads, a request is turned away, and after the deadline it is served.
    limits = ConnectionLimits(max_per_client=8, request_seconds=_DEADLINE)
    with _serving(limits) as port:
        attackers = [_connect(port) for _ in range(8)]
        for sock in attackers:
            sock.sendall(b"GET / HTTP/1.1\r\nHost: x\r\n")
        time.sleep(0.2)
        assert _get(port) == b""  # refused while they hold every slot
        time.sleep(_DEADLINE * 2)
        assert _get(port).startswith(b"HTTP/1.1 200")
        assert all(_closed_by_server(sock, within=0.5) for sock in attackers)
        for sock in attackers:
            sock.close()


def test_the_cap_fits_the_open_file_limit() -> None:
    assert fitting_max_connections(256, None) == 256
    assert fitting_max_connections(256, 4096) == 256
    assert fitting_max_connections(256, 1024) == 256
    assert fitting_max_connections(256, 256) == 64
    assert fitting_max_connections(256, 100) == 1


def test_the_backlog_leaves_room_for_a_burst_of_refusals() -> None:
    assert fitting_backlog(None, 256) == 2048
    assert fitting_backlog(4096, 256) == 1728
    assert fitting_backlog(1 << 20, 256) == 2048
    # 256 open files: 64 connections take what the reserve leaves, so the
    # burst gets the floor of 16.
    assert fitting_backlog(256, fitting_max_connections(256, 256)) == 16
    assert fitting_backlog(200, 1) == 35  # (200 - 128 - 2) / 2
    assert fitting_backlog(130, 1) == 16


def test_the_open_file_limit_is_raised_not_lowered() -> None:
    resource = pytest.importorskip("resource")
    before, _ = resource.getrlimit(resource.RLIMIT_NOFILE)

    after = raise_open_file_limit(wanted=64)

    current, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
    assert current == before
    assert after is None or after == current


def test_the_command_lines_defaults_are_the_guards_own() -> None:
    arguments = server_cli._build_parser().parse_args([])

    assert arguments.max_connections == DEFAULT_MAX_CONNECTIONS
    assert arguments.max_connections_per_client == DEFAULT_MAX_PER_CLIENT
    assert arguments.request_timeout == DEFAULT_REQUEST_SECONDS
    assert ConnectionLimits() == ConnectionLimits(
        DEFAULT_MAX_CONNECTIONS, DEFAULT_MAX_PER_CLIENT, DEFAULT_REQUEST_SECONDS
    )
