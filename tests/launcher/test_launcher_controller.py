"""The window's logic without the window: phases and events (plan 5.2).

The work that normally runs on worker threads runs inline here (``spawn``
calls it at once), so each test reads as a sequence of events.
"""

import os
import signal
import socket
import sys
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from dune_imperium.launcher.addresses import Discovery
from dune_imperium.launcher.command import LaunchPlan
from dune_imperium.launcher.controller import (
    ChecksDone,
    Controller,
    Event,
    LogLine,
    Phase,
    PhaseChanged,
    ServerStopped,
    Started,
    StartFailed,
)
from dune_imperium.launcher.settings import LauncherSettings, load, save
from dune_imperium.launcher.supervisor import ServerProcess

FAKE_SERVER = Path(__file__).with_name("fake_server.py")


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
        return port


def _inline(name: str, work: Callable[[], None]) -> None:
    work()


def _controller(
    tmp_path: Path,
    events: list[Event],
    *,
    server_factory: Callable[[LaunchPlan], ServerProcess] | None = None,
    spawn: Callable[[str, Callable[[], None]], None] = _inline,
    ready_timeout: float = 30.0,
) -> Controller:
    logs = tmp_path / "logs"
    return Controller(
        tmp_path / "launcher.json",
        events.append,
        server_factory=server_factory
        or (lambda plan: ServerProcess(plan, log_dir=logs)),
        discover_addresses=lambda: Discovery((), None, True),
        check_torch=False,
        ready_timeout=ready_timeout,
        spawn=spawn,
    )


def _phases(events: list[Event]) -> list[Phase]:
    return [event.phase for event in events if isinstance(event, PhaseChanged)]


def _local(tmp_path: Path, port: int | None = None) -> LauncherSettings:
    return LauncherSettings(
        port=port or _free_port(), saves_dir=str(tmp_path / "saves")
    )


def test_a_start_that_fails_its_checks_starts_nothing(tmp_path: Path) -> None:
    events: list[Event] = []
    made: list[LaunchPlan] = []

    def factory(plan: LaunchPlan) -> ServerProcess:
        made.append(plan)
        raise AssertionError("no server for a start that failed its checks")

    controller = _controller(tmp_path, events, server_factory=factory)
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        controller.start(_local(tmp_path, taken.getsockname()[1]))
    [checks] = [event for event in events if isinstance(event, ChecksDone)]
    assert any(problem.level == "error" for problem in checks.problems)
    assert _phases(events) == [Phase.CHECKING, Phase.IDLE]
    assert controller.phase is Phase.IDLE and controller.server is None
    assert made == []


def test_a_server_runs_and_stops_through_the_controller(tmp_path: Path) -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("uvicorn")
    events: list[Event] = []
    controller = _controller(tmp_path, events)
    settings = _local(tmp_path)
    assert controller.start(settings)
    try:
        [started] = [event for event in events if isinstance(event, Started)]
        assert started.plan.open_url == f"http://127.0.0.1:{settings.port}/"
        assert started.info["access"] == "open"
        assert controller.phase is Phase.RUNNING
        # A second start while one runs is refused.
        assert not controller.start(settings)
        controller.poll()
        assert any(isinstance(event, LogLine) for event in events)
        # The settings that came up are kept to be offered back.
        assert load(tmp_path / "launcher.json").settings.last_good is not None
    finally:
        assert controller.stop()
    [stopped] = [event for event in events if isinstance(event, ServerStopped)]
    assert stopped.result.how == "stdin" and stopped.unexpected is None
    assert _phases(events) == [
        Phase.CHECKING,
        Phase.STARTING,
        Phase.RUNNING,
        Phase.STOPPING,
        Phase.IDLE,
    ]
    assert controller.server is None


@pytest.mark.skipif(sys.platform == "win32", reason="kills with SIGKILL")
def test_a_server_that_dies_is_noticed_and_explained(tmp_path: Path) -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("uvicorn")
    events: list[Event] = []
    controller = _controller(tmp_path, events)
    controller.start(_local(tmp_path))
    server = controller.server
    assert server is not None and server.pid is not None
    os.kill(server.pid, signal.SIGKILL)
    deadline = time.monotonic() + 5
    while server.is_alive():
        assert time.monotonic() < deadline, "the killed server is still alive"
        time.sleep(0.05)
    controller.poll()
    [stopped] = [event for event in events if isinstance(event, ServerStopped)]
    assert stopped.unexpected and "종료 코드 -9" in stopped.unexpected
    assert controller.phase is Phase.IDLE


def test_a_start_still_in_its_checks_can_be_called_off(tmp_path: Path) -> None:
    events: list[Event] = []
    waiting: list[Callable[[], None]] = []
    made: list[LaunchPlan] = []

    def factory(plan: LaunchPlan) -> ServerProcess:
        made.append(plan)
        raise AssertionError("called off before any server")

    controller = _controller(
        tmp_path,
        events,
        server_factory=factory,
        spawn=lambda name, work: waiting.append(work),
    )
    assert controller.start(_local(tmp_path))
    assert _phases(events) == [Phase.CHECKING]
    assert controller.stop()
    assert _phases(events) == [Phase.CHECKING, Phase.IDLE]
    for work in waiting:
        work()
    assert made == []
    assert _phases(events)[-1] is Phase.IDLE and controller.server is None


def test_a_server_that_never_answers_is_a_failed_start(tmp_path: Path) -> None:
    events: list[Event] = []
    path = tmp_path / "launcher.json"
    save(LauncherSettings(last_good={"mode": "local", "port": 8123}), path)

    def factory(plan: LaunchPlan) -> ServerProcess:
        return ServerProcess(
            plan,
            argv=[sys.executable, str(FAKE_SERVER), "polite"],
            log_dir=tmp_path / "logs",
        )

    controller = _controller(
        tmp_path, events, server_factory=factory, ready_timeout=0.5
    )
    # The window starts from what the form shows on top of the loaded file.
    controller.start(
        replace(controller.settings, port=_free_port(), saves_dir=str(tmp_path / "s"))
    )
    [failed] = [event for event in events if isinstance(event, StartFailed)]
    assert "응답하지 않았습니다" in failed.message
    assert failed.last_good is not None and failed.last_good.port == 8123
    assert controller.phase is Phase.IDLE and controller.server is None
    assert load(path).settings.last_error == failed.message
