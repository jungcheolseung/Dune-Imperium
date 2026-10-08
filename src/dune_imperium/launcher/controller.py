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
    list_games,
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
    pid: int | None = None


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


@dataclass(frozen=True)
class GamesListed:
    games: tuple[dict[str, object], ...]


Event = (
    AddressesFound
    | PhaseChanged
    | ChecksDone
    | Started
    | StartFailed
    | ServerStopped
    | LogLine
    | GamesListed
)
Emit = Callable[[Event], None]
ServerFactory = Callable[[LaunchPlan], ServerProcess]


def _run_in_thread(name: str, work: Callable[[], None]) -> None:
    threading.Thread(target=work, name=name, daemon=True).start()


class Controller:
    """The launcher's state, changed only under ``_lock``.

    Every start gets a generation number. A start called off during its
    checks keeps running on its worker until the checks end, but by then
    its generation is stale and it changes nothing: a second start made in
    the meantime is not overwritten by the first one's result.
    """

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
        # Read-modify-write of the settings, from the window and the workers.
        self._save_lock = threading.Lock()
        self._phase = Phase.IDLE
        self._generation = 0
        self._server: ServerProcess | None = None
        # Run once the stop under way has ended (a close during a stop).
        self._after_stop: list[Callable[[], None]] = []
        self.plan: LaunchPlan | None = None

    @property
    def phase(self) -> Phase:
        return self._phase

    @property
    def server(self) -> ServerProcess | None:
        return self._server

    def _update(self, change: Callable[[LauncherSettings], LauncherSettings]) -> None:
        """Change the settings and write them, one change at a time."""

        with self._save_lock:
            self.settings = change(self.settings)
            try:
                save(self.settings, self.settings_path)
            except OSError as error:
                self._emit(LogLine(f"[launcher] 설정을 저장하지 못했습니다: {error}"))

    def remember(self, settings: LauncherSettings) -> None:
        """Keep what the form shows (the window calls this as it closes).

        The form carries the hidden fields it was given; the ones a worker
        may have changed since (the last good start, the last error) are
        taken from the current settings.
        """

        self._update(
            lambda current: replace(
                settings,
                last_good=current.last_good,
                last_error=current.last_error,
                admin_key=settings.admin_key or current.admin_key,
            )
        )

    def renew_admin_key(self) -> None:
        self._update(lambda current: replace(current, admin_key=None))

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
            self._generation += 1
            generation = self._generation
        self._emit(PhaseChanged(Phase.CHECKING))
        self._spawn("launcher-start", lambda: self._start(settings, generation))
        return True

    def _current(self, generation: int) -> bool:
        return generation == self._generation

    def _start(self, settings: LauncherSettings, generation: int) -> None:
        settings, admin_key = with_admin_key(settings)
        with self._lock:
            if not self._current(generation):
                return
        self._update(lambda current: replace(settings, last_good=current.last_good))
        try:
            plan = build_plan(settings, admin_key)
            problems = preflight(settings, plan, check_torch=self._check_torch)
        except Exception as error:  # a bug must not leave the window stuck
            problems = [Problem("error", f"시작 전 검사가 실패했습니다: {error!r}")]
            plan = None
        failed = plan is None or has_errors(problems)
        with self._lock:
            if not self._current(generation) or self._phase is not Phase.CHECKING:
                return  # called off during the checks; later state is not ours
            self._emit(ChecksDone(tuple(problems)))
            if failed or plan is None:
                self._phase = Phase.IDLE
                self._emit(PhaseChanged(Phase.IDLE))
                return
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
            message, tail = failure.message, tuple(failure.tail)
            server.stop(grace=2.0, term_grace=2.0)
            with self._lock:
                if self._server is not server:
                    return
                self._pass_on_lines(server)
                self._server = None
                self._phase = Phase.IDLE
            self._update(lambda current: replace(current, last_error=message))
            self._emit(StartFailed(message, tail, self.last_good()))
            self._emit(PhaseChanged(Phase.IDLE))
            return
        with self._lock:
            if self._server is not server or self._phase is not Phase.STARTING:
                return  # stopped while it came up
            self._phase = Phase.RUNNING
        self._update(
            lambda current: replace(
                current, last_good=snapshot(settings), last_error=None
            )
        )
        self._emit(Started(plan, info, server.log_path, server.pid))
        self._emit(PhaseChanged(Phase.RUNNING))

    def stop(self, then: Callable[[], None] | None = None) -> bool:
        """Stop the server on a worker; ``then`` runs after (on that worker).

        During the checks there is no server yet: the start is called off.
        During a stop already under way ``then`` waits for that one.
        """

        with self._lock:
            phase = self._phase
            server = self._server
            if phase is Phase.STOPPING:
                if then is not None:
                    self._after_stop.append(then)
                return True
            if phase is Phase.CHECKING:
                self._phase = Phase.IDLE
                self._generation += 1
            elif server is None or phase is Phase.IDLE:
                return False
            else:
                self._phase = Phase.STOPPING
                if then is not None:
                    self._after_stop.append(then)
        if phase is Phase.CHECKING:
            self._emit(PhaseChanged(Phase.IDLE))
            if then is not None:
                then()
            return True
        assert server is not None
        self._emit(PhaseChanged(Phase.STOPPING))
        self._spawn("launcher-stop", lambda: self._stop_worker(server, None))
        return True

    def _stop_worker(self, server: ServerProcess, why: str | None) -> None:
        """Stop ``server`` and report it, whatever goes wrong on the way."""

        result: Stopped | None = None
        reason = why
        try:
            if why is None:
                result = server.stop()
            else:
                result = server.stop(grace=0.5, term_grace=0.5)
                reason = explain_failure(server.tail(), result.exit_code)
        except Exception as error:  # a bug must not leave the window stuck
            reason = f"서버를 끄다가 오류가 났습니다: {error!r}"
        finally:
            with self._lock:
                self._pass_on_lines(server)
                if self._server is server:
                    self._server = None
                    self._phase = Phase.IDLE
                waiting, self._after_stop = self._after_stop, []
            stopped = result or Stopped("already", 0.0, server.exit_code(), False)
            self._emit(ServerStopped(stopped, unexpected=reason))
            self._emit(PhaseChanged(Phase.IDLE))
            for then in waiting:
                then()

    def _pass_on_lines(self, server: ServerProcess) -> None:
        """The server's last lines and the launcher's notes on the stop,
        which ``poll`` can no longer reach once the server is dropped."""

        while not server.lines.empty():
            self._emit(LogLine(server.lines.get_nowait()))

    def refresh_games(self) -> None:
        """List the server's games on a worker (the window asks every 3 s)."""

        plan = self.plan
        if plan is None or self._phase is not Phase.RUNNING:
            return

        def work() -> None:
            games = list_games(plan.host, plan.port, plan.admin_key)
            if games is not None and self._phase is Phase.RUNNING:
                self._emit(GamesListed(tuple(games)))

        self._spawn("launcher-games", work)

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
        self._emit(PhaseChanged(Phase.STOPPING))
        self._spawn("launcher-died", lambda: self._stop_worker(server, "died"))

    def shutdown(self) -> None:
        """Stop the server and wait for it (the launcher is closing)."""

        server = self._server
        if server is not None:
            server.stop()
            with self._lock:
                if self._server is server:
                    self._server = None
                    self._phase = Phase.IDLE
