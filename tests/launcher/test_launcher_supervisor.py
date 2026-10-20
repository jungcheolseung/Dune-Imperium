"""Starting, watching and stopping the server child (plan 5.2).

Most tests start the real server, because what they pin only shows in a
real process: that the launcher's closed pipe stops it as gracefully as
Ctrl+C with a stream open, that the admin link it computes is the one the
server prints and accepts, and that a start that cannot listen says why.
The stop ladder runs against ``fake_server.py``.
"""

import http.server
import io
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, cast

import pytest

from dune_imperium.cli import server as server_cli
from dune_imperium.launcher.command import CREATE_NO_WINDOW, LaunchPlan, build_plan
from dune_imperium.launcher.settings import LauncherSettings, with_admin_key
from dune_imperium.launcher.supervisor import (
    KEEP_LOGS,
    ServerProcess,
    StartupCancelled,
    StartupFailed,
    Stopped,
    mask_admin_key,
)

FAKE_SERVER = Path(__file__).with_name("fake_server.py")


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
        return port


def _local_plan(tmp_path: Path, **choices: Any) -> LaunchPlan:
    settings = LauncherSettings(
        port=_free_port(), saves_dir=str(tmp_path / "saves"), **choices
    )
    return build_plan(settings, None)


def _wait_for_line(server: ServerProcess, text: str, timeout: float = 10) -> None:
    deadline = time.monotonic() + timeout
    while not any(text in line for line in server.tail(200)):
        assert time.monotonic() < deadline, f"no line with {text!r}: {server.tail()}"
        time.sleep(0.05)


def _hold_a_stream_open(base: str) -> threading.Event:
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

    def hold() -> None:
        with urllib.request.urlopen(
            f"{base}/games/{game_id}/events", timeout=30
        ) as stream:
            for line in stream:
                if line.startswith(b"event: hello"):
                    greeted.set()
        ended.set()

    threading.Thread(target=hold, daemon=True).start()
    assert greeted.wait(5), "the stream never greeted"
    return ended


def _kill(server: ServerProcess) -> None:
    if server.is_alive():
        server.stop(grace=0.5, term_grace=0.5)


def test_a_local_server_stops_on_its_closed_input_with_a_stream_open(
    tmp_path: Path,
) -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("uvicorn")
    plan = _local_plan(tmp_path)
    server = ServerProcess(plan, log_dir=tmp_path / "logs")
    server.start()
    try:
        info = server.wait_ready()
        assert info["access"] == "open"
        ended = _hold_a_stream_open(plan.room_base)
        stopped = server.stop()
    finally:
        _kill(server)

    assert stopped.how == "stdin"
    assert stopped.exit_code == 0
    assert stopped.port_free
    assert stopped.seconds < 2.0, f"stop took {stopped.seconds:.1f}s"
    assert ended.wait(5), "the browser's stream was not ended"
    assert server.log_path is not None
    log = server.log_path.read_text(encoding="utf-8")
    assert "search AI:" in log and "Traceback" not in log


def test_the_admin_link_is_the_servers_own_and_never_logged(tmp_path: Path) -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("uvicorn")
    settings, key = with_admin_key(
        LauncherSettings(
            mode="remote",
            host="127.0.0.1",
            port=_free_port(),
            saves_dir=str(tmp_path / "saves"),
        )
    )
    plan = build_plan(settings, key)
    server = ServerProcess(plan, log_dir=tmp_path / "logs")
    server.start()
    try:
        info = server.wait_ready()
        _wait_for_line(server, "search AI:")
        tail = server.tail(100)
    finally:
        server.stop()

    # The server took the key from the environment: it answers as to its host.
    assert info["access"] == "remote" and info["admin"] is True
    # The link it printed is the one the launcher computed (masked here).
    assert f"  {mask_admin_key(plan.open_url, key)}" in tail
    # What the launcher says about the search AI is the server's own line.
    arguments = server_cli._build_parser().parse_args(list(plan.server_args))
    _checkpoint, line = server_cli.resolve_search_checkpoint(arguments, plan.env)
    assert line in tail
    assert server.log_path is not None
    assert key not in server.log_path.read_text(encoding="utf-8")


def test_a_start_on_a_busy_port_says_which_port(tmp_path: Path) -> None:
    pytest.importorskip("uvicorn")
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port: int = taken.getsockname()[1]
        plan = build_plan(
            LauncherSettings(port=port, saves_dir=str(tmp_path / "saves")), None
        )
        server = ServerProcess(plan, log_dir=tmp_path / "logs")
        server.start()
        try:
            with pytest.raises(StartupFailed) as failure:
                server.wait_ready()
        finally:
            server.stop(grace=2, term_grace=2)
    assert f"127.0.0.1:{port}" in failure.value.message
    assert failure.value.exit_code == 1


@pytest.mark.parametrize(
    ("mode", "how"),
    [
        ("polite", "stdin"),
        ("stubborn", "terminate"),
        pytest.param(
            "deaf",
            "kill",
            marks=pytest.mark.skipif(
                sys.platform == "win32", reason="SIGTERM cannot be ignored there"
            ),
        ),
    ],
)
def test_the_stop_ladder_goes_as_far_as_it_has_to(
    tmp_path: Path, mode: str, how: str
) -> None:
    plan = _local_plan(tmp_path)
    server = ServerProcess(
        plan, argv=[sys.executable, str(FAKE_SERVER), mode], log_dir=tmp_path
    )
    server.start()
    try:
        _wait_for_line(server, "fake server up")
        stopped = server.stop(grace=0.5, term_grace=0.5)
    finally:
        _kill(server)
    assert stopped.how == how
    assert not server.is_alive()


def test_a_server_that_never_answers_times_out_with_words(tmp_path: Path) -> None:
    plan = _local_plan(tmp_path)
    server = ServerProcess(
        plan, argv=[sys.executable, str(FAKE_SERVER), "polite"], log_dir=tmp_path
    )
    server.start()
    try:
        with pytest.raises(StartupFailed) as failure:
            server.wait_ready(timeout=0.5)
    finally:
        server.stop()
    assert "응답하지 않았습니다" in failure.value.message


def test_stopping_during_the_start_cancels_the_wait(tmp_path: Path) -> None:
    plan = _local_plan(tmp_path)
    server = ServerProcess(
        plan, argv=[sys.executable, str(FAKE_SERVER), "polite"], log_dir=tmp_path
    )
    server.start()
    _wait_for_line(server, "fake server up")
    stopper = threading.Timer(0.3, server.stop)
    stopper.start()
    try:
        with pytest.raises(StartupCancelled):
            server.wait_ready(timeout=10)
    finally:
        stopper.join(10)
        _kill(server)


def test_a_missing_interpreter_is_a_failed_start(tmp_path: Path) -> None:
    plan = _local_plan(tmp_path)
    server = ServerProcess(plan, argv=[str(tmp_path / "no-python")], log_dir=tmp_path)
    with pytest.raises(StartupFailed) as failure:
        server.start()
    assert "실행하지 못했습니다" in failure.value.message


def test_only_the_last_logs_are_kept(tmp_path: Path) -> None:
    for number in range(KEEP_LOGS + 3):
        old = tmp_path / f"server-old-{number:02d}.log"
        old.write_text("old\n", encoding="utf-8")
        os.utime(old, (1_000_000 + number, 1_000_000 + number))
    plan = _local_plan(tmp_path)
    server = ServerProcess(
        plan, argv=[sys.executable, str(FAKE_SERVER), "polite"], log_dir=tmp_path
    )
    server.start()
    server.stop()
    logs = sorted(path.name for path in tmp_path.glob("server-*.log"))
    assert len(logs) == KEEP_LOGS
    assert "server-old-00.log" not in logs
    assert server.log_path is not None and server.log_path.name in logs


def test_the_admin_key_is_masked_in_every_line() -> None:
    assert (
        mask_admin_key("  http://127.0.0.1:8000/#admin=abc123", None)
        == "  http://127.0.0.1:8000/#admin=…"
    )
    assert mask_admin_key("key=abc123 again", "abc123") == "key=… again"


class _FinishedProcess:
    pid = 4242
    returncode = 0
    stdin = None
    stdout = io.StringIO("")

    def poll(self) -> int:
        return 0

    def wait(self, timeout: float | None = None) -> int:
        return 0


def test_the_server_gets_a_pipe_and_no_console_window_on_windows(
    tmp_path: Path,
) -> None:
    seen: dict[str, Any] = {}

    def fake_popen(argv: list[str], **options: Any) -> subprocess.Popen[str]:
        seen.update(options)
        return cast("subprocess.Popen[str]", _FinishedProcess())

    plan = _local_plan(tmp_path)
    server = ServerProcess(plan, popen=fake_popen, platform="win32", log_dir=tmp_path)
    server.start()
    server.stop()
    assert seen["creationflags"] == CREATE_NO_WINDOW
    assert seen["stdin"] == subprocess.PIPE
    assert seen["env"] == dict(plan.env)


# --- review fixes (2026-10-09) -----------------------------------------------


def test_another_server_on_the_port_is_not_taken_for_ours(tmp_path: Path) -> None:
    # A wildcard bind can come up beside a server on 127.0.0.1 (macOS); that
    # one then answers the launcher. Its /whoami says "open", and it never
    # gets the admin cookie.
    cookies: list[str | None] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - the http.server name
            cookies.append(self.headers.get("Cookie"))
            body = json.dumps({"access": "open", "admin": True}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            pass

    other = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=other.serve_forever, daemon=True).start()
    port: int = other.server_address[1]
    settings, key = with_admin_key(
        LauncherSettings(mode="remote", host="0.0.0.0", port=port)
    )
    plan = build_plan(settings, key)
    server = ServerProcess(
        plan, argv=[sys.executable, str(FAKE_SERVER), "polite"], log_dir=tmp_path
    )
    server.start()
    try:
        with pytest.raises(StartupFailed) as failure:
            server.wait_ready(timeout=1.0)
    finally:
        server.stop()
        other.shutdown()
        other.server_close()
    assert "다른" in failure.value.message and str(port) in failure.value.message
    assert cookies and all(cookie is None for cookie in cookies)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX kill of the leftover")
def test_a_child_holding_the_output_pipe_does_not_hang_the_stop(
    tmp_path: Path,
) -> None:
    plan = _local_plan(tmp_path)
    server = ServerProcess(
        plan, argv=[sys.executable, str(FAKE_SERVER), "grandchild"], log_dir=tmp_path
    )
    server.start()
    _wait_for_line(server, "fake server up")
    [line] = [line for line in server.tail() if line.startswith("grandchild ")]
    leftover = int(line.split()[1])
    try:
        stopped = server.stop(grace=1.0, term_grace=1.0)
        assert stopped.how == "stdin"
        assert stopped.seconds < 3.0
        assert any("출력이 아직 열려" in line for line in server.tail())
    finally:
        if sys.platform != "win32":
            os.kill(leftover, signal.SIGKILL)


def test_two_stops_at_once_share_one_result(tmp_path: Path) -> None:
    plan = _local_plan(tmp_path)
    server = ServerProcess(
        plan, argv=[sys.executable, str(FAKE_SERVER), "polite"], log_dir=tmp_path
    )
    server.start()
    _wait_for_line(server, "fake server up")
    results: list[object] = []
    stoppers = [
        threading.Thread(target=lambda: results.append(server.stop())) for _ in range(2)
    ]
    for stopper in stoppers:
        stopper.start()
    for stopper in stoppers:
        stopper.join(30)
    assert len(results) == 2 and results[0] is results[1]


@pytest.mark.parametrize(
    ("platform", "own_session"), [("darwin", True), ("win32", False)]
)
def test_the_server_gets_its_own_session_on_posix(
    tmp_path: Path, platform: str, own_session: bool
) -> None:
    seen: dict[str, Any] = {}

    def fake_popen(argv: list[str], **options: Any) -> subprocess.Popen[str]:
        seen.update(options)
        return cast("subprocess.Popen[str]", _FinishedProcess())

    server = ServerProcess(
        _local_plan(tmp_path), popen=fake_popen, platform=platform, log_dir=tmp_path
    )
    server.start()
    server.stop()
    assert seen["start_new_session"] is own_session


def test_a_stop_before_the_start_cancels_it(tmp_path: Path) -> None:
    server = ServerProcess(_local_plan(tmp_path), log_dir=tmp_path)
    server.stop()
    with pytest.raises(StartupCancelled):
        server.start()


def test_a_stop_during_the_popen_stops_what_the_popen_made(tmp_path: Path) -> None:
    # The controller publishes the server before start() runs; a stop that
    # came in between the cancel check and the Popen used to find no
    # process, report "already", and leave the new server running.
    entered = threading.Event()
    release = threading.Event()

    def slow_popen(argv: list[str], **options: Any) -> subprocess.Popen[str]:
        entered.set()
        assert release.wait(10)
        return subprocess.Popen(argv, **options)

    plan = _local_plan(tmp_path)
    server = ServerProcess(
        plan,
        argv=[sys.executable, str(FAKE_SERVER), "polite"],
        popen=slow_popen,
        log_dir=tmp_path,
    )
    starter = threading.Thread(target=server.start)
    starter.start()
    assert entered.wait(10)
    results: list[Stopped] = []
    stopper = threading.Thread(target=lambda: results.append(server.stop()))
    stopper.start()
    stopper.join(0.5)
    assert stopper.is_alive(), "the stop did not wait for the Popen"
    release.set()
    starter.join(10)
    stopper.join(30)
    [stopped] = results
    assert stopped.how != "already"
    assert not server.is_alive()
    with pytest.raises(StartupCancelled):
        server.wait_ready(timeout=1)
