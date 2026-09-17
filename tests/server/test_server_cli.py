"""Tests for the play-server CLI (M14 slices 1, 3 and 5).

Most exercise the pure argument-resolution helpers without starting a server
(``docs/multiplayer-design.md`` sections 4.2-4.4, 5, 6). The last two start
the real command, because what they pin only shows in a real process: how
long the server takes to stop while an event stream is open (section 4.5),
and whether a killed server's autosave survives it (section 4.7).
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

import httpx2
import pytest

from dune_imperium.cli.server import (
    ADMIN_KEY_ENVIRONMENT,
    _build_parser,
    admin_link,
    is_loopback_host,
    main,
    resolve_access,
    resolve_autosave,
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


# --- resolve_autosave ----------------------------------------------------


def test_default_arguments_resolve_autosave_to_false() -> None:
    arguments = _build_parser().parse_args([])

    assert resolve_autosave(arguments) is False


def test_remote_resolves_autosave_to_true() -> None:
    arguments = _build_parser().parse_args(["--remote"])

    assert resolve_autosave(arguments) is True


def test_remote_with_no_autosave_resolves_to_false() -> None:
    arguments = _build_parser().parse_args(["--remote", "--no-autosave"])

    assert resolve_autosave(arguments) is False


def test_no_autosave_without_remote_is_refused() -> None:
    arguments = _build_parser().parse_args(["--no-autosave"])

    with pytest.raises(ValueError, match="--remote"):
        resolve_autosave(arguments)


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


def test_main_refuses_no_autosave_without_remote() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--no-autosave"])

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


# --- crash recovery via the autosave (M14 slice 5) -------------------------


def _wait_for_server(
    client: httpx2.Client, process: subprocess.Popen[str], deadline: float = 20.0
) -> None:
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        assert process.poll() is None, "the server exited during startup"
        try:
            response = client.get("/catalog", timeout=1.0)
        except httpx2.TransportError:
            time.sleep(0.05)
            continue
        if response.status_code == 200:
            return
        time.sleep(0.05)
    raise AssertionError("the server did not start in time")


def _play_seat0_until_two_confirms(
    client: httpx2.Client, game_id: object
) -> dict[str, object]:
    response = client.get(f"/games/{game_id}")
    assert response.status_code == 200, response.text
    summary: dict[str, object] = response.json()
    confirms = 0
    for _ in range(400):
        if confirms >= 2:
            return summary
        if summary.get("confirmation") == 0:
            response = client.post(
                f"/games/{game_id}/confirm",
                json={"seat": 0, "revision": summary["revision"]},
            )
            assert response.status_code == 200, response.text
            summary = response.json()
            confirms += 1
            continue
        response = client.post(
            f"/games/{game_id}/actions",
            json={"seat": 0, "revision": summary["revision"], "index": 0},
        )
        assert response.status_code == 200, response.text
        summary = response.json()
    raise AssertionError("seat 0 never reached two confirmed turn hand-overs")


def _server_process(
    *, admin_key: str, port: int, saves_dir: Path
) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            sys.executable,
            "-u",  # unbuffered: the startup banner must survive a SIGKILL
            "-m",
            "dune_imperium.cli.server",
            "--remote",
            "--admin-key",
            admin_key,
            "--port",
            str(port),
            "--saves-dir",
            str(saves_dir),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def test_a_killed_server_recovers_from_its_autosave(tmp_path: Path) -> None:
    # The autosave (default on for --remote) is the whole point of an
    # otherwise ungraceful death: restart, load it, and only the turn in
    # flight is lost.
    pytest.importorskip("fastapi")
    pytest.importorskip("uvicorn")
    admin_key = "crash-recovery-key"
    saves_dir = tmp_path / "saves"
    first_port = _free_port()
    first = _server_process(admin_key=admin_key, port=first_port, saves_dir=saves_dir)
    first_stdout = first.stdout
    assert first_stdout is not None
    first_output: list[str] = []

    def _drain_first() -> None:
        for line in first_stdout:
            first_output.append(line)

    first_reader = threading.Thread(target=_drain_first, daemon=True)
    first_reader.start()

    second: subprocess.Popen[str] | None = None
    try:
        client = httpx2.Client(
            base_url=f"http://127.0.0.1:{first_port}",
            timeout=httpx2.Timeout(10.0),
        )
        _wait_for_server(client, first)

        login = client.post("/auth/admin", json={"key": admin_key})
        assert login.status_code == 200, login.text

        created = client.post(
            "/games",
            json={
                "seats": ["human", "heuristic", "heuristic", "heuristic"],
                "game_seed": 41,
            },
        )
        assert created.status_code == 200, created.text
        game_id = created.json()["game_id"]

        claimed = client.post(f"/games/{game_id}/seats/0/claim", json={"name": "Host"})
        assert claimed.status_code == 200, claimed.text

        summary = _play_seat0_until_two_confirms(client, game_id)
        round_before_crash = summary["round_number"]

        first.kill()
        first.wait(timeout=10)
        first_reader.join(timeout=5)
        first_text = "".join(first_output)

        save_path = saves_dir / f"{game_id}.json"
        assert save_path.exists(), first_text
        assert list(saves_dir.glob("*.tmp")) == []
        assert "Autosave is on" in first_text, first_text

        second_port = _free_port()
        second = _server_process(
            admin_key=admin_key, port=second_port, saves_dir=saves_dir
        )
        second_client = httpx2.Client(
            base_url=f"http://127.0.0.1:{second_port}",
            timeout=httpx2.Timeout(10.0),
        )
        _wait_for_server(second_client, second)

        second_login = second_client.post("/auth/admin", json={"key": admin_key})
        assert second_login.status_code == 200, second_login.text

        listing = second_client.get("/saves")
        assert listing.status_code == 200, listing.text
        entries: list[dict[str, object]] = listing.json()
        entry = next(e for e in entries if e["save_id"] == game_id)
        assert entry["autosave"] is True
        assert entry["round_number"] == round_before_crash

        loaded = second_client.post(f"/saves/{game_id}/load")
        assert loaded.status_code == 200, loaded.text
        restored: dict[str, object] = loaded.json()
        assert restored["game_id"] != game_id
        assert restored["revision"] == entry["step_count"]
        assert restored["round_number"] == entry["round_number"]

        new_game_id = restored["game_id"]
        claim_new = second_client.post(
            f"/games/{new_game_id}/seats/0/claim", json={"name": "Host2"}
        )
        assert claim_new.status_code == 200, claim_new.text
        one_more = second_client.post(
            f"/games/{new_game_id}/actions",
            json={"seat": 0, "revision": restored["revision"], "index": 0},
        )
        assert one_more.status_code == 200, one_more.text
    finally:
        for process in (first, second):
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=10)
