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
from dune_imperium.launcher.command import LaunchPlan, build_plan
from dune_imperium.launcher.controller import (
    ChecksDone,
    Controller,
    Event,
    GamesListed,
    LogLine,
    Phase,
    PhaseChanged,
    ServerStopped,
    Started,
    StartFailed,
)
from dune_imperium.launcher.settings import LauncherSettings, load, save
from dune_imperium.launcher.supervisor import ServerProcess, Stopped

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
    if sys.platform != "win32":
        os.kill(server.pid, signal.SIGKILL)
    deadline = time.monotonic() + 5
    while server.is_alive():
        assert time.monotonic() < deadline, "the killed server is still alive"
        time.sleep(0.05)
    controller.poll()
    [stopped] = [event for event in events if isinstance(event, ServerStopped)]
    assert stopped.unexpected and "종료 코드 -9" in stopped.unexpected
    assert controller.phase is Phase.IDLE
    # The window hears at once that the server is going.
    assert _phases(events)[-2:] == [Phase.STOPPING, Phase.IDLE]


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


def _create_game(base: str, key: str | None = None) -> str:
    import json
    import urllib.request

    request = urllib.request.Request(
        f"{base}/games",
        data=json.dumps(
            {"seats": ["human", "heuristic", "heuristic", "heuristic"]}
        ).encode(),
        headers={"content-type": "application/json"},
    )
    if key is not None:
        request.add_header("Cookie", f"dune_admin={key}")
    game_id: str = json.load(urllib.request.urlopen(request, timeout=10))["game_id"]
    return game_id


def test_the_host_sees_the_open_games_of_a_remote_server(tmp_path: Path) -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("uvicorn")
    from dune_imperium.launcher.command import list_games

    events: list[Event] = []
    controller = _controller(tmp_path, events)
    controller.start(
        LauncherSettings(
            mode="remote",
            host="127.0.0.1",
            port=_free_port(),
            saves_dir=str(tmp_path / "saves"),
        )
    )
    plan = controller.plan
    try:
        assert plan is not None and plan.admin_key is not None
        game_id = _create_game(plan.room_base, plan.admin_key)
        controller.refresh_games()
        [listed] = [event for event in events if isinstance(event, GamesListed)]
        assert [game["game_id"] for game in listed.games] == [game_id]
        # Only the host may list a remote server's games.
        assert list_games(plan.host, plan.port) is None
    finally:
        controller.stop()


# --- review fixes (2026-10-09, stages 3-5) -----------------------------------


def _polite(tmp_path: Path, made: list[int]) -> Callable[[LaunchPlan], ServerProcess]:
    def factory(plan: LaunchPlan) -> ServerProcess:
        made.append(plan.port)
        return ServerProcess(
            plan,
            argv=[sys.executable, str(FAKE_SERVER), "polite"],
            log_dir=tmp_path / "logs",
        )

    return factory


def test_a_start_called_off_cannot_take_over_the_next_one(tmp_path: Path) -> None:
    # [시작] on port A, [중지] during the checks, [시작] on port B: A's checks
    # end later, and must change nothing (no server on A, no problem list).
    events: list[Event] = []
    waiting: list[Callable[[], None]] = []
    made: list[int] = []
    controller = _controller(
        tmp_path,
        events,
        server_factory=_polite(tmp_path, made),
        spawn=lambda name, work: waiting.append(work),
        ready_timeout=0.3,
    )
    first, second = _local(tmp_path), _local(tmp_path)
    assert controller.start(first)
    assert controller.stop()
    assert controller.start(second)
    called_off, current = waiting
    called_off()
    assert made == [] and not any(isinstance(e, ChecksDone) for e in events)
    assert _phases(events)[-1] is Phase.CHECKING
    current()
    assert made == [second.port]


def test_a_failed_check_called_off_does_not_end_the_next_start(
    tmp_path: Path,
) -> None:
    events: list[Event] = []
    waiting: list[Callable[[], None]] = []
    made: list[int] = []
    controller = _controller(
        tmp_path,
        events,
        server_factory=_polite(tmp_path, made),
        spawn=lambda name, work: waiting.append(work),
        ready_timeout=0.3,
    )
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        assert controller.start(_local(tmp_path, taken.getsockname()[1]))
        assert controller.stop()
        second = _local(tmp_path)
        assert controller.start(second)
        waiting[0]()  # the busy-port checks fail, for a start called off
    assert _phases(events)[-1] is Phase.CHECKING
    waiting[1]()
    assert made == [second.port]


def _running(
    tmp_path: Path, controller: Controller, server: ServerProcess
) -> None:
    """Put a started fake server into the controller as if it came up."""

    server.start()
    controller._server = server
    controller._phase = Phase.RUNNING


def test_closing_during_a_stop_waits_for_that_stop(tmp_path: Path) -> None:
    events: list[Event] = []
    waiting: list[Callable[[], None]] = []
    controller = _controller(
        tmp_path, events, spawn=lambda name, work: waiting.append(work)
    )
    plan_server = ServerProcess(
        build_plan(_local(tmp_path), None),
        argv=[sys.executable, str(FAKE_SERVER), "polite"],
        log_dir=tmp_path / "logs",
    )
    _running(tmp_path, controller, plan_server)
    closed: list[bool] = []
    assert controller.stop()
    assert controller.stop(then=lambda: closed.append(True))
    assert closed == []
    [work] = waiting
    work()
    assert closed == [True]
    assert controller.phase is Phase.IDLE


def test_a_stop_that_fails_still_returns_the_window_to_idle(tmp_path: Path) -> None:
    class Broken(ServerProcess):
        def stop(self, *, grace: float = 10.0, term_grace: float = 5.0) -> Stopped:
            raise RuntimeError("boom")

    events: list[Event] = []
    waiting: list[Callable[[], None]] = []
    controller = _controller(
        tmp_path, events, spawn=lambda name, work: waiting.append(work)
    )
    broken = Broken(
        build_plan(_local(tmp_path), None),
        argv=[sys.executable, str(FAKE_SERVER), "polite"],
        log_dir=tmp_path / "logs",
    )
    _running(tmp_path, controller, broken)
    try:
        closed: list[bool] = []
        assert controller.stop(then=lambda: closed.append(True))
        waiting[0]()
        [stopped] = [e for e in events if isinstance(e, ServerStopped)]
        assert stopped.unexpected and "오류" in stopped.unexpected
        assert controller.phase is Phase.IDLE and closed == [True]
    finally:
        ServerProcess.stop(broken)


def test_the_last_server_lines_reach_the_window(tmp_path: Path) -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("uvicorn")
    events: list[Event] = []
    controller = _controller(tmp_path, events)
    controller.start(_local(tmp_path))
    controller.stop()
    # The server's shutdown lines arrive after the window stopped polling.
    lines = [e.text for e in events if isinstance(e, LogLine)]
    assert any("Finished server process" in line for line in lines), lines[-5:]


def test_settings_saved_from_two_threads_stay_a_valid_file(tmp_path: Path) -> None:
    import json
    import threading

    events: list[Event] = []
    controller = _controller(tmp_path, events)

    def port(value: int) -> Callable[[LauncherSettings], LauncherSettings]:
        return lambda current: replace(current, port=value)

    def bump(offset: int) -> None:
        for number in range(50):
            controller._update(port(8000 + offset + number))

    threads = [threading.Thread(target=bump, args=(i * 100,)) for i in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    json.loads((tmp_path / "launcher.json").read_text(encoding="utf-8"))
    assert list(tmp_path.glob("launcher.json.*.tmp")) == []


def test_closing_keeps_what_a_worker_saved(tmp_path: Path) -> None:
    events: list[Event] = []
    controller = _controller(tmp_path, events)
    form = controller.settings
    controller._update(lambda current: replace(current, last_good={"port": 8123}))
    controller.remember(replace(form, port=8124))
    kept = load(tmp_path / "launcher.json").settings
    assert kept.port == 8124 and kept.last_good == {"port": 8123}
