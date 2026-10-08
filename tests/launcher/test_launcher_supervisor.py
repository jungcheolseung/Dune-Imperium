"""Starting, watching and stopping the server child (plan 5.2).

Most tests start the real server, because what they pin only shows in a
real process: that the launcher's closed pipe stops it as gracefully as
Ctrl+C with a stream open, that the admin link it computes is the one the
server prints and accepts, and that a start that cannot listen says why.
The stop ladder runs against ``fake_server.py``.
"""

import io
import json
import os
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
    PID_FILE_NAME,
    ServerProcess,
    StartupCancelled,
    StartupFailed,
    mask_admin_key,
    read_pid_file,
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
        record = read_pid_file(tmp_path / "logs")
        assert record is not None and record["pid"] == server.pid
        ended = _hold_a_stream_open(plan.room_base)
        stopped = server.stop()
    finally:
        _kill(server)

    assert stopped.how == "stdin"
    assert stopped.exit_code == 0
    assert stopped.port_free
    assert stopped.seconds < 2.0, f"stop took {stopped.seconds:.1f}s"
    assert ended.wait(5), "the browser's stream was not ended"
    assert not (tmp_path / "logs" / PID_FILE_NAME).exists()
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
