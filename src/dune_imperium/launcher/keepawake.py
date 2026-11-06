"""Keep the host's computer from idle sleep while the server runs (plan 5.11).

macOS: ``caffeinate -i -w <server pid>`` as a separate child. It holds the
assertion only while the server lives, so nothing is left behind if the
launcher dies; the server itself is not wrapped in it, which would put
caffeinate between the launcher and the process it stops.

Windows: ``SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)``,
called on the thread that lives as long as the window (Tk's), released
when the server stops. The display may still turn off.

Elsewhere nothing happens.
"""

import subprocess
import sys
from collections.abc import Callable
from typing import Final

ES_CONTINUOUS: Final = 0x80000000
ES_SYSTEM_REQUIRED: Final = 0x00000001


def _windows_execution_state(flags: int) -> int:
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.SetThreadExecutionState.argtypes = [ctypes.c_uint]
        kernel32.SetThreadExecutionState.restype = ctypes.c_uint
        result: int = kernel32.SetThreadExecutionState(flags)
        return result
    return 0


class KeepAwake:
    def __init__(
        self,
        *,
        platform: str = sys.platform,
        popen: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
        set_execution_state: Callable[[int], int] = _windows_execution_state,
    ) -> None:
        self._platform = platform
        self._popen = popen
        self._set_execution_state = set_execution_state
        self._caffeinate: subprocess.Popen[bytes] | None = None
        self._windows_held = False

    @property
    def holding(self) -> bool:
        return self._windows_held or (
            self._caffeinate is not None and self._caffeinate.poll() is None
        )

    def hold(self, server_pid: int) -> str | None:
        """Keep the machine awake while ``server_pid`` runs; a note if not."""

        self.release()
        if self._platform == "darwin":
            try:
                self._caffeinate = self._popen(
                    ["/usr/bin/caffeinate", "-i", "-w", str(server_pid)],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except OSError as error:
                return f"잠자기 방지를 켜지 못했습니다: {error}"
            return None
        if self._platform == "win32":
            if self._set_execution_state(ES_CONTINUOUS | ES_SYSTEM_REQUIRED) == 0:
                return "잠자기 방지를 켜지 못했습니다(SetThreadExecutionState)"
            self._windows_held = True
            return None
        return None

    def release(self) -> None:
        caffeinate = self._caffeinate
        self._caffeinate = None
        if caffeinate is not None and caffeinate.poll() is None:
            caffeinate.terminate()
            try:
                caffeinate.wait(2.0)
            except subprocess.TimeoutExpired:
                caffeinate.kill()
        if self._windows_held:
            self._set_execution_state(ES_CONTINUOUS)
            self._windows_held = False
