"""What the launcher window does, without the window.

The window calls ``find_addresses``, ``start`` and ``stop``; each runs its
slow part (address lookups, the pre-start checks, the server's start and
stop) on a worker thread and reports through ``emit`` with plain event
objects. The window queues those and applies them on Tk's thread, so this
module never touches Tk and its tests need no display.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

from dune_imperium.launcher.addresses import Discovery, discover
from dune_imperium.launcher.command import (
    LaunchPlan,
    Problem,
    build_plan,
    explain_failure,
    has_errors,
    preflight,
    run_output,
)
from dune_imperium.launcher.settings import (
    LauncherSettings,
    load,
    restore,
    save,
    snapshot,
    with_admin_key,
)
from dune_imperium.launcher.supervisor import (
    ServerProcess,
    StartupCancelled,
    StartupFailed,
    Stopped,
)


class Phase(StrEnum):
    IDLE = "idle"
    CHECKING = "checking"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"


@dataclass(frozen=True)
class AddressesFound:
    discovery: Discovery


@dataclass(frozen=True)
class PhaseChanged:
    phase: Phase


@dataclass(frozen=True)
class ChecksDone:
    problems: tuple[Problem, ...]


@dataclass(frozen=True)
class Started:
    plan: LaunchPlan
    info: dict[str, object]
    log_path: Path | None


@dataclass(frozen=True)
class StartFailed:
    message: str
    tail: tuple[str, ...]
    # The settings of the last start that came up, to offer back.
    last_good: LauncherSettings | None


@dataclass(frozen=True)
class ServerStopped:
    result: Stopped
    # Set when the host did not ask for it: why the server ended.
    unexpected: str | None = None


@dataclass(frozen=True)
class LogLine:
    text: str


Event = (
    AddressesFound
    | PhaseChanged
    | ChecksDone
    | Started
    | StartFailed
    | ServerStopped
    | LogLine
)
Emit = Callable[[Event], None]
ServerFactory = Callable[[LaunchPlan], ServerProcess]


def _run_in_thread(name: str, work: Callable[[], None]) -> None:
    threading.Thread(target=work, name=name, daemon=True).start()


class Controller:
    def __init__(
        self,
        settings_path: Path,
        emit: Emit,
        *,
        server_factory: ServerFactory = ServerProcess,
        discover_addresses: Callable[[], Discovery] = lambda: discover(run_output),
        check_torch: bool = True,
        ready_timeout: float = 30.0,
        spawn: Callable[[str, Callable[[], None]], None] = _run_in_thread,
    ) -> None:
        self.settings_path = settings_path
        loaded = load(settings_path)
        self.settings = loaded.settings
        self.notes = loaded.notes
        self._emit = emit
        self._server_factory = server_factory
        self._discover = discover_addresses
        self._check_torch = check_torch
        self._ready_timeout = ready_timeout
        self._spawn = spawn
        self._lock = threading.Lock()
        self._phase = Phase.IDLE
        self._server: ServerProcess | None = None
        self.plan: LaunchPlan | None = None

    @property
    def phase(self) -> Phase:
        return self._phase

    @property
    def server(self) -> ServerProcess | None:
        return self._server

    def _set_phase(self, phase: Phase) -> None:
        with self._lock:
            self._phase = phase
        self._emit(PhaseChanged(phase))

    def _save(self, settings: LauncherSettings) -> None:
        self.settings = settings
        try:
            save(settings, self.settings_path)
        except OSError as error:
            self._emit(LogLine(f"[launcher] 설정을 저장하지 못했습니다: {error}"))

    def remember(self, settings: LauncherSettings) -> None:
        """Keep what the form shows (the window calls this as it closes)."""

        self._save(settings)

    def find_addresses(self) -> None:
        def work() -> None:
            self._emit(AddressesFound(self._discover()))

        self._spawn("launcher-addresses", work)

    def last_good(self) -> LauncherSettings | None:
        if self.settings.last_good is None:
            return None
        return restore(self.settings, self.settings.last_good)

    def start(self, settings: LauncherSettings) -> bool:
        """Check, then start; ``False`` if something is already going on."""

        with self._lock:
            if self._phase is not Phase.IDLE:
                return False
            self._phase = Phase.CHECKING
        self._emit(PhaseChanged(Phase.CHECKING))
        self._spawn("launcher-start", lambda: self._start(settings))
        return True

    def _start(self, settings: LauncherSettings) -> None:
        settings, admin_key = with_admin_key(settings)
        self._save(settings)
        try:
            plan = build_plan(settings, admin_key)
            problems = preflight(settings, plan, check_torch=self._check_torch)
        except Exception as error:  # a bug must not leave the window stuck
            problems = [Problem("error", f"시작 전 검사가 실패했습니다: {error!r}")]
            plan = None
        self._emit(ChecksDone(tuple(problems)))
        if plan is None or has_errors(problems):
            with self._lock:
                called_off = self._phase is not Phase.CHECKING
                self._phase = Phase.IDLE
            if not called_off:
                self._emit(PhaseChanged(Phase.IDLE))
            return
        with self._lock:
            if self._phase is not Phase.CHECKING:
                return  # called off during the checks
            self.plan = plan
            server = self._server_factory(plan)
            self._server = server
            self._phase = Phase.STARTING
        self._emit(PhaseChanged(Phase.STARTING))
        try:
            server.start()
            info = server.wait_ready(self._ready_timeout)
        except StartupCancelled:
            return  # stop() reports the end
        except StartupFailed as failure:
            server.stop(grace=2.0, term_grace=2.0)
            with self._lock:
                self._server = None
            self._save(replace(self.settings, last_error=failure.message))
            self._emit(
                StartFailed(failure.message, tuple(failure.tail), self.last_good())
            )
            self._set_phase(Phase.IDLE)
            return
        self._save(
            replace(self.settings, last_good=snapshot(settings), last_error=None)
        )
        with self._lock:
            if self._phase is not Phase.STARTING:
                return  # stopped while it came up
            self._phase = Phase.RUNNING
        self._emit(Started(plan, info, server.log_path))
        self._emit(PhaseChanged(Phase.RUNNING))

    def stop(self, then: Callable[[], None] | None = None) -> bool:
        """Stop the server on a worker; ``then`` runs after (on that worker).

        During the checks there is no server yet: the start is called off.
        """

        with self._lock:
            phase = self._phase
            server = self._server
            if phase is Phase.CHECKING:
                self._phase = Phase.IDLE
            elif server is None or phase in (Phase.STOPPING, Phase.IDLE):
                return False
            else:
                self._phase = Phase.STOPPING
        if phase is Phase.CHECKING:
            self._emit(PhaseChanged(Phase.IDLE))
            if then is not None:
                then()
            return True
        assert server is not None
        self._emit(PhaseChanged(Phase.STOPPING))

        def work() -> None:
            result = server.stop()
            with self._lock:
                self._server = None
                self._phase = Phase.IDLE
            self._emit(ServerStopped(result))
            self._emit(PhaseChanged(Phase.IDLE))
            if then is not None:
                then()

        self._spawn("launcher-stop", work)
        return True

    def poll(self) -> None:
        """Pass on the server's new output; notice a server that died.

        The window calls this every tenth of a second on Tk's thread.
        """

        server = self._server
        if server is None:
            return
        while not server.lines.empty():
            self._emit(LogLine(server.lines.get_nowait()))
        if self._phase is not Phase.RUNNING or server.is_alive():
            return
        with self._lock:
            if self._phase is not Phase.RUNNING or self._server is not server:
                return
            self._phase = Phase.STOPPING

        def work() -> None:
            result = server.stop(grace=0.5, term_grace=0.5)
            reason = explain_failure(server.tail(), result.exit_code)
            with self._lock:
                self._server = None
                self._phase = Phase.IDLE
            self._emit(ServerStopped(result, unexpected=reason))
            self._emit(PhaseChanged(Phase.IDLE))

        self._spawn("launcher-died", work)

    def shutdown(self) -> None:
        """Stop the server and wait for it (the launcher is closing)."""

        server = self._server
        if server is not None:
            server.stop()
            with self._lock:
                self._server = None
                self._phase = Phase.IDLE
