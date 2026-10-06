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

from dune_imperium.cli import server as server_cli
from dune_imperium.cli.server import (
    ADMIN_KEY_ENVIRONMENT,
    SEARCH_CHECKPOINT_ENVIRONMENT,
    _build_parser,
    admin_link,
    bind_problem,
    is_loopback_host,
    main,
    resolve_access,
    resolve_autosave,
    resolve_public_url,
    resolve_search_checkpoint,
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


# --- resolve_search_checkpoint ------------------------------------------------


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty home directory, and a default network path in an empty
    stand-in checkout, so the project's own ``checkpoints/play/search.pt``
    stays out."""

    directory = tmp_path / "home"
    directory.mkdir()
    monkeypatch.setenv("HOME", str(directory))
    monkeypatch.setattr(
        server_cli,
        "DEFAULT_SEARCH_CHECKPOINT",
        tmp_path / "project" / "checkpoints" / "play" / "search.pt",
    )
    return directory


def _network(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not read before a game seats it")
    return path


def test_no_search_checkpoint_anywhere_leaves_the_search_ai_off(home: Path) -> None:
    arguments = _build_parser().parse_args([])

    assert resolve_search_checkpoint(arguments, {}) == (
        None,
        "search AI: off (no checkpoint; --search-checkpoint or "
        f"{server_cli.DEFAULT_SEARCH_CHECKPOINT})",
    )


def test_the_flag_names_the_search_checkpoint_resolved(
    home: Path, tmp_path: Path
) -> None:
    # A symlink is followed now: saves name the file it pointed at on start.
    real = _network(tmp_path / "checkpoints" / "l3-8081.pt").resolve()
    link = tmp_path / "search-link.pt"
    link.symlink_to(real)
    arguments = _build_parser().parse_args(["--search-checkpoint", str(link)])

    assert resolve_search_checkpoint(arguments, {}) == (real, f"search AI: {real}")


def test_the_flag_expands_the_home_directory(home: Path) -> None:
    real = _network(home / "nets" / "search.pt").resolve()
    arguments = _build_parser().parse_args(["--search-checkpoint", "~/nets/search.pt"])

    assert resolve_search_checkpoint(arguments, {})[0] == real


def test_the_environment_names_the_search_checkpoint_without_the_flag(
    home: Path, tmp_path: Path
) -> None:
    from_environment = _network(tmp_path / "env.pt").resolve()
    from_flag = _network(tmp_path / "flag.pt").resolve()
    environment = {SEARCH_CHECKPOINT_ENVIRONMENT: str(from_environment)}
    parser = _build_parser()

    assert resolve_search_checkpoint(parser.parse_args([]), environment)[0] == (
        from_environment
    )
    flagged = parser.parse_args(["--search-checkpoint", str(from_flag)])
    assert resolve_search_checkpoint(flagged, environment)[0] == from_flag


def test_the_default_search_checkpoint_is_found_in_the_project_checkout(
    home: Path,
) -> None:
    default = server_cli.DEFAULT_SEARCH_CHECKPOINT
    real = _network(default.parent / "l3-8081.pt").resolve()
    default.symlink_to(real.name)
    arguments = _build_parser().parse_args([])

    assert resolve_search_checkpoint(arguments, {}) == (real, f"search AI: {real}")
    # Nothing is looked for in the home directory any more.
    assert not (home / ".dune-imperium").exists()


def test_the_project_keeps_its_local_files_inside_the_checkout() -> None:
    """User decision 2026-10-06: no project file outside the project.

    The defaults name folders of the checkout the package runs from, both
    git-ignored there.
    """

    from dune_imperium.paths import PROJECT_ROOT, SAVES_DIR, SEARCH_CHECKPOINT
    from dune_imperium.server.persistence import default_saves_directory

    assert (PROJECT_ROOT / "pyproject.toml").is_file()
    assert default_saves_directory() == SAVES_DIR == PROJECT_ROOT / "saves"
    assert server_cli.DEFAULT_SEARCH_CHECKPOINT == SEARCH_CHECKPOINT
    assert SEARCH_CHECKPOINT == PROJECT_ROOT / "checkpoints" / "play" / "search.pt"
    paths = ["saves/x.json", "checkpoints/play/search.pt"]
    ignored = subprocess.run(
        ["git", "check-ignore", *paths],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ignored.stdout.split() == paths


def test_a_named_search_checkpoint_that_is_missing_is_reported(
    home: Path, tmp_path: Path
) -> None:
    missing = tmp_path / "missing.pt"
    arguments = _build_parser().parse_args(["--search-checkpoint", str(missing)])

    checkpoint, line = resolve_search_checkpoint(arguments, {})

    assert checkpoint is None
    assert line == f"search AI: off (no file at {missing.resolve()})"


def test_the_search_ai_is_off_without_torch(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = _network(tmp_path / "search.pt")
    monkeypatch.setattr(
        server_cli, "find_spec", lambda name: None if name == "torch" else object()
    )
    arguments = _build_parser().parse_args(["--search-checkpoint", str(real)])

    assert resolve_search_checkpoint(arguments, {}) == (
        None,
        "search AI: off (torch not installed: uv sync --extra train)",
    )


@pytest.mark.parametrize("configured", [True, False])
def test_main_prints_the_search_ai_line_at_startup(
    configured: bool,
    home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    uvicorn = pytest.importorskip("uvicorn")
    pytest.importorskip("fastapi")
    # Everything but serving: the server returns as soon as it would start.
    monkeypatch.setattr(uvicorn.Server, "run", lambda self, *args, **kwargs: None)
    monkeypatch.delenv(SEARCH_CHECKPOINT_ENVIRONMENT, raising=False)
    real = _network(tmp_path / "search.pt").resolve()
    flag = ["--search-checkpoint", str(real)] if configured else []

    code = main(
        ["--port", str(_free_port()), "--saves-dir", str(tmp_path / "saves"), *flag]
    )

    output = capsys.readouterr().out
    assert code == 0
    search_lines = [line for line in output.splitlines() if "search AI" in line]
    expected = f"search AI: {real}" if configured else "search AI: off (no checkpoint;"
    assert len(search_lines) == 1, output
    assert search_lines[0].startswith(expected), output


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


# --- an address the server cannot listen on ----------------------------------


def test_a_free_loopback_port_is_no_bind_problem() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]

    assert bind_problem("127.0.0.1", port) is None


def test_a_port_somebody_listens_on_is_a_bind_problem() -> None:
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port: int = taken.getsockname()[1]

        problem = bind_problem("127.0.0.1", port)

    assert problem is not None
    assert f"127.0.0.1:{port}" in problem
    # The hint about Tailscale is for addresses, not for a busy port.
    assert "Tailscale" not in problem


def test_an_address_this_machine_does_not_have_is_refused_before_any_link(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # 192.0.2.0/24 is reserved for documentation (RFC 5737): no interface has
    # it, which is what a Tailscale address looks like while Tailscale is off.
    # uvicorn reports the failed bind among its own log lines, after the CLI
    # had already printed an admin link for a server that never came up.
    code = main(["--remote", "--host", "192.0.2.1", "--port", "8000"])

    captured = capsys.readouterr()
    assert code == 1
    assert "#admin=" not in captured.out
    assert "192.0.2.1:8000" in captured.err
    assert "Tailscale" in captured.err


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


def _finish_index(client: httpx2.Client, game_id: object) -> int:
    """Return the index of seat 0's ``finish_agent_turn`` press."""

    response = client.get(f"/games/{game_id}/seats/0/actions")
    assert response.status_code == 200, response.text
    actions: list[dict[str, object]] = response.json()["actions"]
    indexes = [
        action["index"]
        for action in actions
        if action["action_id"] == "finish_agent_turn"
    ]
    assert len(indexes) == 1, "a ready Agent turn offers exactly one end press"
    index = indexes[0]
    assert isinstance(index, int)
    return index


def _play_seat0_until_two_hand_overs(
    client: httpx2.Client, game_id: object
) -> dict[str, object]:
    """Play seat 0 until it has handed its turn over twice.

    The first is its held Leader pick (the game is a Leader draft), handed
    over by the confirm press. An Agent turn is never held: it ends with its
    owner's own ``finish_agent_turn`` (OQ-095), pressed here once the summary
    says nothing mandatory is left (``turn_end_ready``); that press is the
    second hand-over.
    """

    response = client.get(f"/games/{game_id}")
    assert response.status_code == 200, response.text
    summary: dict[str, object] = response.json()
    hand_overs = 0
    for _ in range(400):
        if hand_overs >= 2:
            return summary
        if summary.get("confirmation") == 0:
            response = client.post(
                f"/games/{game_id}/confirm",
                json={"seat": 0, "revision": summary["revision"]},
            )
            assert response.status_code == 200, response.text
            summary = response.json()
            hand_overs += 1
            continue
        decision = summary["decision"]
        assert isinstance(decision, dict)
        ready = decision.get("turn_end_ready") is True
        index = _finish_index(client, game_id) if ready else 0
        response = client.post(
            f"/games/{game_id}/actions",
            json={"seat": 0, "revision": summary["revision"], "index": index},
        )
        assert response.status_code == 200, response.text
        summary = response.json()
        if ready:
            hand_overs += 1
    raise AssertionError("seat 0 never handed its turn over twice")


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
                # A Leader pick is still held for the confirm press, an
                # Agent turn never is (OQ-095).
                "leader_draft": True,
            },
        )
        assert created.status_code == 200, created.text
        game_id = created.json()["game_id"]

        claimed = client.post(f"/games/{game_id}/seats/0/claim", json={"name": "Host"})
        assert claimed.status_code == 200, claimed.text

        summary = _play_seat0_until_two_hand_overs(client, game_id)
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
