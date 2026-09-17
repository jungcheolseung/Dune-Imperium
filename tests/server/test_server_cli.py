"""Tests for the play-server CLI (M14 slices 1 and 3).

Most exercise the pure argument-resolution helpers without starting a server
(``docs/multiplayer-design.md`` sections 4.2-4.4, 5, 6). The last one starts
the real command, because what it pins only shows in a real process: how
long the server takes to stop while an event stream is open (section 4.5).
"""

import json
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from dune_imperium.cli.server import (
    ADMIN_KEY_ENVIRONMENT,
    _build_parser,
    admin_link,
    is_loopback_host,
    main,
    resolve_access,
    resolve_public_url,
)
from dune_imperium.server.access import AccessMode


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("127.0.0.1", True),
        ("localhost", True),
        ("::1", True),
        ("0.0.0.0", False),
        ("100.101.102.103", False),
        ("192.168.0.5", False),
        ("example.com", False),
    ],
)
def test_is_loopback_host(host: str, expected: bool) -> None:
    assert is_loopback_host(host) is expected


# --- resolve_access ----------------------------------------------------


def test_default_arguments_resolve_to_open_access() -> None:
    arguments = _build_parser().parse_args([])

    assert resolve_access(arguments, {}) == (AccessMode.OPEN, None)


def test_a_non_loopback_host_without_remote_is_refused() -> None:
    arguments = _build_parser().parse_args(["--host", "0.0.0.0"])

    with pytest.raises(ValueError, match="--remote"):
        resolve_access(arguments, {})


def test_an_admin_key_without_remote_is_refused() -> None:
    arguments = _build_parser().parse_args(["--admin-key", "x"])

    with pytest.raises(ValueError, match="--remote"):
        resolve_access(arguments, {})


def test_remote_with_an_explicit_admin_key() -> None:
    arguments = _build_parser().parse_args(["--remote", "--admin-key", "x"])

    assert resolve_access(arguments, {}) == (AccessMode.REMOTE, "x")


def test_remote_falls_back_to_the_environment_key() -> None:
    arguments = _build_parser().parse_args(["--remote"])

    access, key = resolve_access(arguments, {ADMIN_KEY_ENVIRONMENT: "env-key"})

    assert (access, key) == (AccessMode.REMOTE, "env-key")


def test_remote_without_a_key_anywhere_mints_a_fresh_random_key() -> None:
    arguments = _build_parser().parse_args(["--remote"])

    _, first = resolve_access(arguments, {})
    _, second = resolve_access(arguments, {})

    assert first and second and first != second


def test_remote_is_allowed_on_a_non_loopback_host() -> None:
    arguments = _build_parser().parse_args(["--remote", "--host", "100.101.102.103"])

    access, key = resolve_access(arguments, {})

    assert access is AccessMode.REMOTE
    assert key


def test_an_explicit_admin_key_wins_over_the_environment() -> None:
    arguments = _build_parser().parse_args(["--remote", "--admin-key", "y"])

    access, key = resolve_access(arguments, {ADMIN_KEY_ENVIRONMENT: "env-key"})

    assert (access, key) == (AccessMode.REMOTE, "y")


# --- resolve_public_url ------------------------------------------------------


def test_the_public_url_is_optional_and_loses_its_trailing_slash() -> None:
    parser = _build_parser()

    assert resolve_public_url(parser.parse_args(["--remote"])) is None
    arguments = parser.parse_args(
        ["--remote", "--public-url", "http://100.101.102.103:8000/"]
    )
    assert resolve_public_url(arguments) == "http://100.101.102.103:8000"


def test_a_public_url_needs_remote_access_and_a_scheme() -> None:
    parser = _build_parser()

    with pytest.raises(ValueError, match="--remote"):
        resolve_public_url(parser.parse_args(["--public-url", "http://x:8000"]))
    with pytest.raises(ValueError, match="http"):
        resolve_public_url(
            parser.parse_args(["--remote", "--public-url", "100.101.102.103:8000"])
        )


# --- admin_link ----------------------------------------------------------


def test_admin_link_swaps_a_wildcard_bind_for_its_loopback_address() -> None:
    assert admin_link("0.0.0.0", 8000, "k") == "http://127.0.0.1:8000/#admin=k"
    assert admin_link("::", 8000, "k") == "http://[::1]:8000/#admin=k"


def test_admin_link_names_the_address_the_server_listens_on() -> None:
    # Bound to one address the server answers nowhere else: 127.0.0.1 would
    # be dead for a Tailscale IP, and equally for an IPv6-only ``::1``.
    assert admin_link("127.0.0.1", 8000, "k") == "http://127.0.0.1:8000/#admin=k"
    assert admin_link("localhost", 8000, "k") == "http://localhost:8000/#admin=k"
    assert (
        admin_link("100.101.102.103", 8000, "k")
        == "http://100.101.102.103:8000/#admin=k"
    )


def test_admin_link_brackets_an_ipv6_host() -> None:
    assert admin_link("::1", 9000, "k") == "http://[::1]:9000/#admin=k"
    assert admin_link("2001:db8::1", 8000, "k") == "http://[2001:db8::1]:8000/#admin=k"


# --- main ------------------------------------------------------------------


def test_main_refuses_a_non_loopback_host_without_remote() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--host", "0.0.0.0"])

    assert excinfo.value.code == 2


# --- shutdown with an open event stream -----------------------------------


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
        return port


def test_the_server_exits_at_once_while_an_event_stream_is_open(
    tmp_path: Path,
) -> None:
    # An event stream never ends by itself and uvicorn waits for open
    # responses, so without ``hub.close()`` on the exit signal the server sat
    # out its whole graceful-shutdown timeout (3 s) and logged an error.
    pytest.importorskip("fastapi")
    pytest.importorskip("uvicorn")
    base = f"http://127.0.0.1:{(port := _free_port())}"
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "dune_imperium.cli.server",
            "--port",
            str(port),
            "--saves-dir",
            str(tmp_path / "saves"),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        deadline = time.monotonic() + 30
        while True:
            try:
                urllib.request.urlopen(f"{base}/catalog", timeout=1).read()
                break
            except OSError:
                assert server.poll() is None, "the server exited during startup"
                assert time.monotonic() < deadline, "the server did not start"
                time.sleep(0.05)
        request = urllib.request.Request(
            f"{base}/games",
            data=json.dumps(
                {"seats": ["human", "heuristic", "heuristic", "heuristic"]}
            ).encode(),
            headers={"content-type": "application/json"},
        )
        game_id = json.load(urllib.request.urlopen(request, timeout=5))["game_id"]

        greeted = threading.Event()
        ended = threading.Event()

        def hold_a_stream_open() -> None:
            with urllib.request.urlopen(
                f"{base}/games/{game_id}/events", timeout=30
            ) as stream:
                for line in stream:
                    if line.startswith(b"event: hello"):
                        greeted.set()
            ended.set()

        threading.Thread(target=hold_a_stream_open, daemon=True).start()
        assert greeted.wait(5), "the stream never greeted"

        asked = time.monotonic()
        server.send_signal(signal.SIGINT)
        code = server.wait(timeout=10)
        took = time.monotonic() - asked
        output = server.stdout.read() if server.stdout is not None else ""
    finally:
        if server.poll() is None:
            server.kill()
            server.wait(timeout=10)

    assert code == 0, output
    assert took < 2.0, f"shutdown took {took:.1f}s with a stream open"
    assert ended.wait(5), "the client's stream was not ended"
    assert "Traceback" not in output
    assert "timeout graceful shutdown exceeded" not in output
