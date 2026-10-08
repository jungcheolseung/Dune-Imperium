"""Start, watch and stop the play server as a child process.

docs/server-launcher-plan.md 5.2. The server reads its standard input until
the end (``--exit-when-stdin-closes``) and the launcher holds the write end:

* **stop**: close it, and the server shuts down as on Ctrl+C (exit code 0);
  if it has not ended after ``grace`` seconds, terminate it, then kill it.
  Success is "the process ended and the port is free", never an exit code:
  uvicorn re-raises a signal it stopped on, so a terminated server ends
  with -15 on POSIX.
* **the launcher dies**: the operating system closes the pipe. On macOS the
  server then stops by itself, gracefully. On Windows the server is also in
  a Job Object that kills it when the launcher's last handle to the job
  closes, which happens first: there the server is killed outright. Nothing
  is lost but the turn in progress: the autosave is replaced atomically.

On Windows the ``python.exe`` of a uv virtual environment is a redirector
that runs the base interpreter as its own child, inside its own job; the
process the launcher holds is the redirector. On POSIX the server gets a
session of its own, so a terminal's Ctrl+C or hang-up reaches only the
launcher, which then stops the server the one way.

Server output goes to a queue for the window and to a log file in
``tmp/launcher/``; the admin key is masked in both.
"""

import os
import queue
import re
import subprocess
import sys
import threading
import time
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import IO, Final, Literal

from dune_imperium.launcher.command import (
    LaunchPlan,
    explain_failure,
    no_window_flags,
    whoami,
)
from dune_imperium.paths import PROJECT_ROOT, TMP_DIR

LOG_DIR: Final = TMP_DIR / "launcher"
KEEP_LOGS: Final = 10
_TAIL_LINES: Final = 200
_ADMIN_FRAGMENT: Final = re.compile(r"(#admin=)\S+")


def mask_admin_key(line: str, admin_key: str | None) -> str:
    """The line with the admin key replaced: the literal key first (it may
    sit anywhere), then whatever follows ``#admin=``."""

    if admin_key:
        line = line.replace(admin_key, "…")
    return _ADMIN_FRAGMENT.sub(r"\1…", line)


class StartupFailed(Exception):
    """The server did not come up; ``message`` says why, in Korean."""

    def __init__(self, message: str, tail: Sequence[str], exit_code: int | None):
        super().__init__(message)
        self.message = message
        self.tail = list(tail)
        self.exit_code = exit_code


class StartupCancelled(StartupFailed):
    """The host stopped the server before it came up."""


@dataclass(frozen=True)
class Stopped:
    # How the server ended: by itself before the stop, on the closed input,
    # terminated, or killed.
    how: Literal["already", "stdin", "terminate", "kill"]
    seconds: float
    exit_code: int | None
    port_free: bool


Popen = Callable[..., "subprocess.Popen[str]"]


def _modified(path: Path) -> float:
    """A file's modification time; a file another launcher just removed
    sorts first."""

    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


class ServerProcess:
    """One run of the server. Not restartable: make a new one per start."""

    def __init__(
        self,
        plan: LaunchPlan,
        *,
        argv: Sequence[str] | None = None,
        log_dir: Path = LOG_DIR,
        popen: Popen = subprocess.Popen,
        platform: str = sys.platform,
    ) -> None:
        self.plan = plan
        self.argv = tuple(argv) if argv is not None else plan.argv
        self.log_dir = log_dir
        self.log_path: Path | None = None
        self.lines: queue.Queue[str] = queue.Queue()
        self._popen = popen
        self._platform = platform
        self._process: subprocess.Popen[str] | None = None
        self._tail: deque[str] = deque(maxlen=_TAIL_LINES)
        self._log: IO[str] | None = None
        self._log_lock = threading.Lock()
        self._reader_started = False
        self._reader_done = threading.Event()
        self._lock = threading.Lock()
        # One stop at a time: the window's stop and its closing can overlap.
        self._stop_lock = threading.Lock()
        self._stopped: Stopped | None = None
        self._stopping = False
        self._job: _Job | None = None

    @property
    def pid(self) -> int | None:
        return None if self._process is None else self._process.pid

    @property
    def stopping(self) -> bool:
        return self._stopping

    def exit_code(self) -> int | None:
        return None if self._process is None else self._process.poll()

    def is_alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def tail(self, count: int = 30) -> list[str]:
        return list(self._tail)[-count:]

    def start(self) -> None:
        if self._process is not None:
            raise RuntimeError("a ServerProcess starts once")
        if self._stopping:
            raise StartupCancelled("시작을 멈췄습니다.", [], None)
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self._open_log()
        except OSError as error:
            raise StartupFailed(
                f"로그 폴더를 만들지 못했습니다: {error}", [], None
            ) from error
        posix = self._platform != "win32"
        try:
            self._process = self._popen(
                list(self.argv),
                cwd=PROJECT_ROOT,
                env=dict(self.plan.env),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=no_window_flags(self._platform),
                # Its own session on POSIX: a terminal's Ctrl+C or hang-up
                # reaches the launcher only, and the server ends the one way,
                # through its closed input (uvicorn has no SIGHUP handler).
                start_new_session=posix,
            )
        except OSError as error:
            self._note(f"could not run {self.argv[0]}: {error}")
            self._finish()
            raise StartupFailed(
                f"서버를 실행하지 못했습니다: {error}", self.tail(), None
            ) from error
        if self._platform == "win32":
            self._job = _Job.for_process(self._process.pid, self._note)
        self._reader_started = True
        threading.Thread(
            target=self._read_output, name="server-output", daemon=True
        ).start()

    def wait_ready(
        self, timeout: float = 30.0, *, interval: float = 0.2
    ) -> dict[str, object]:
        """Wait until this server answers ``/whoami``; return its answer.

        The access it reports has to be the plan's (``open`` or ``remote``):
        another server answering at the same address (a wildcard bind can
        come up beside one on 127.0.0.1 on macOS) is not taken for ours.
        The admin key is sent only to a server that says it is remote, and
        it has to answer as to its host: proof that the admin link the
        launcher shows is the right one.
        """

        process = self._require_process()
        expected = "remote" if self.plan.remote else "open"
        foreign = False
        deadline = time.monotonic() + timeout
        while True:
            code = process.poll()
            if code is not None or self._stopping:
                if code is not None:
                    self._reader_done.wait(2.0)
                tail = self.tail()
                if self._stopping:
                    raise StartupCancelled("시작을 멈췄습니다.", tail, code)
                raise StartupFailed(explain_failure(tail, code), tail, code)
            info = whoami(self.plan.host, self.plan.port)
            if info is not None and info.get("access") != expected:
                foreign = True
            elif info is not None:
                if self.plan.remote:
                    info = whoami(self.plan.host, self.plan.port, self.plan.admin_key)
                if info is not None:
                    if self.plan.remote and info.get("admin") is not True:
                        raise StartupFailed(
                            "서버가 떴지만 관리자 키를 받아들이지 않았습니다.",
                            self.tail(),
                            None,
                        )
                    return info
            if time.monotonic() >= deadline:
                message = (
                    f"포트 {self.plan.port}에서 이 런처가 띄운 서버가 아닌 다른 "
                    "서버가 답합니다. 그 서버를 끄거나 다른 포트를 고르세요."
                    if foreign
                    else f"서버가 {timeout:g}초 안에 응답하지 않았습니다. "
                    "로그를 확인하세요."
                )
                raise StartupFailed(message, self.tail(), None)
            time.sleep(interval)

    def stop(self, *, grace: float = 10.0, term_grace: float = 5.0) -> Stopped:
        """Close the server's input, then escalate; return how it ended.

        Calls overlap when the window is closed while a stop runs: the
        second one waits for the first and returns its result.
        """

        with self._lock:
            self._stopping = True
        with self._stop_lock:
            if self._stopped is not None:
                return self._stopped
            try:
                result = self._stop(grace, term_grace)
            finally:
                self._finish()
            self._stopped = result
            return result

    def _stop(self, grace: float, term_grace: float) -> Stopped:
        process = self._process
        if process is None:
            return Stopped("already", 0.0, None, True)
        begun = time.monotonic()
        how: Literal["already", "stdin", "terminate", "kill"]
        if process.poll() is not None:
            how = "already"
        else:
            self._close_input()
            try:
                process.wait(grace)
                how = "stdin"
            except subprocess.TimeoutExpired:
                self._terminate()
                try:
                    process.wait(term_grace)
                    how = "terminate"
                except subprocess.TimeoutExpired:
                    process.kill()
                    if self._job is not None:
                        self._job.terminate()
                    how = "kill"
                    try:
                        process.wait(10.0)
                    except subprocess.TimeoutExpired:
                        self._note("서버 프로세스가 kill 뒤에도 끝나지 않았습니다")
        seconds = time.monotonic() - begun
        if self._reader_started and not self._reader_done.wait(2.0):
            # Another process still holds the output pipe: a child the
            # server started. Its port may stay taken.
            self._note(
                "서버 출력이 아직 열려 있습니다: "
                "서버가 띄운 프로세스가 남았을 수 있습니다"
            )
        port_free = self._port_released(3.0)
        return Stopped(how, seconds, process.poll(), port_free)

    # --- internals ------------------------------------------------------

    def _require_process(self) -> subprocess.Popen[str]:
        if self._process is None:
            raise RuntimeError("the server was not started")
        return self._process

    def _close_input(self) -> None:
        process = self._require_process()
        with self._lock:
            stream = process.stdin
            if stream is None or stream.closed:
                return
            try:
                stream.close()
            except OSError:
                pass

    def _terminate(self) -> None:
        if self._job is not None:
            # The redirector and the base interpreter together (module doc).
            self._job.terminate()
        else:
            self._require_process().terminate()

    def _port_released(self, timeout: float) -> bool:
        from dune_imperium.cli.server import bind_problem

        deadline = time.monotonic() + timeout
        while True:
            if bind_problem(self.plan.host, self.plan.port) is None:
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.1)

    def _note(self, line: str) -> None:
        """A line of the launcher's own, shown and logged with the server's."""

        self._emit(f"[launcher] {line}")

    def _emit(self, line: str) -> None:
        line = mask_admin_key(line, self.plan.admin_key)
        self._tail.append(line)
        self.lines.put(line)
        with self._log_lock:
            log = self._log
            if log is not None:
                try:
                    log.write(line + "\n")
                    log.flush()
                except (OSError, ValueError):
                    pass

    def _read_output(self) -> None:
        """Pass the server's lines on; close the pipe here, once read.

        Only this thread closes it: closing a pipe another thread is
        blocked reading would wait for that read, which lasts as long as
        any process holds the pipe's other end.
        """

        stream = self._require_process().stdout
        try:
            if stream is not None:
                for raw in stream:
                    self._emit(raw.rstrip("\r\n"))
        except (OSError, ValueError):
            pass
        finally:
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass
            self._reader_done.set()

    def _open_log(self) -> None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = self.log_dir / f"server-{stamp}.log"
        suffix = 1
        while path.exists():
            suffix += 1
            path = self.log_dir / f"server-{stamp}-{suffix}.log"
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        self._log = os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")
        self.log_path = path
        logs = sorted(self.log_dir.glob("server-*.log"), key=_modified)
        for old in logs[:-KEEP_LOGS]:
            try:
                old.unlink()
            except OSError:
                pass

    def _finish(self) -> None:
        if self._job is not None:
            self._job.close()
            self._job = None
        process = self._process
        if process is not None:
            streams = [process.stdin]
            if not self._reader_started:
                streams.append(process.stdout)
            for stream in streams:
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass
        with self._log_lock:
            log = self._log
            self._log = None
            if log is not None:
                try:
                    log.close()
                except OSError:
                    pass


class _Job:
    """A Windows Job Object that kills its processes when it is closed."""

    def __init__(self, handle: int) -> None:
        self._handle: int | None = handle

    @staticmethod
    def for_process(pid: int, note: Callable[[str], None]) -> _Job | None:
        if sys.platform == "win32":
            handle = _win32_job_for(pid)
            if handle is None:
                note(
                    "Job Object를 만들지 못했습니다: "
                    "런처가 죽으면 서버가 남을 수 있습니다"
                )
                return None
            return _Job(handle)
        return None

    def terminate(self) -> None:
        if sys.platform == "win32" and self._handle is not None:
            _win32_terminate_job(self._handle)

    def close(self) -> None:
        if sys.platform == "win32" and self._handle is not None:
            _win32_close(self._handle)
        self._handle = None


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION: Final = 9
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: Final = 0x2000
    _PROCESS_SET_QUOTA: Final = 0x0100
    _PROCESS_TERMINATE: Final = 0x0001

    class _IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class _BasicLimits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimits),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    _kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    _kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    _kernel32.SetInformationJobObject.restype = wintypes.BOOL
    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    _kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _kernel32.TerminateJobObject.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL

    def _win32_job_for(pid: int) -> int | None:
        job = _kernel32.CreateJobObjectW(None, None)
        if not job:
            return None
        limits = _ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        configured = _kernel32.SetInformationJobObject(
            job,
            _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        )
        process = _kernel32.OpenProcess(
            _PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, pid
        )
        assigned = bool(
            configured and process and _kernel32.AssignProcessToJobObject(job, process)
        )
        if process:
            _kernel32.CloseHandle(process)
        if not assigned:
            _kernel32.CloseHandle(job)
            return None
        handle: int = job
        return handle

    def _win32_terminate_job(handle: int) -> None:
        _kernel32.TerminateJobObject(handle, 1)

    def _win32_close(handle: int) -> None:
        _kernel32.CloseHandle(handle)
