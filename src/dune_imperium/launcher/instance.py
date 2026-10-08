"""One launcher per checkout (plan 5.2, "이전 서버·다른 점유자").

The launcher holds an exclusive lock on ``tmp/launcher/launcher.lock`` for
as long as it runs; a second double-click finds it taken and says so. The
operating system drops the lock when the process ends, however it ends,
so no stale record can block a later start (a pid file could: the pid may
belong to another program by then, and on Windows ``os.kill(pid, 0)``
would even terminate it).

A server this launcher started cannot outlive it (its standard input is
the launcher's pipe, and on Windows a Job Object holds it), so there is no
"left-over server of the last run" to adopt: a server already on the port
is someone else's, and the pre-start check says so.
"""

import os
import sys
from pathlib import Path
from typing import IO, Final

from dune_imperium.launcher.supervisor import LOG_DIR

LOCK_FILE: Final = LOG_DIR / "launcher.lock"


class InstanceLock:
    """Hold the launcher lock; ``acquire`` is False while another holds it."""

    def __init__(self, path: Path = LOCK_FILE) -> None:
        self.path = path
        self._handle: IO[bytes] | None = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Kept open until release: the lock lives as long as the handle.
        handle = open(self.path, "a+b")
        try:
            if sys.platform == "win32":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        handle.seek(0)
        handle.truncate()
        handle.write(f"{os.getpid()}\n".encode())
        handle.flush()
        self._handle = handle
        return True

    def release(self) -> None:
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        if sys.platform == "win32":
            # Windows frees a lock left to close() only "eventually"; a
            # double-click right after closing would find it still held.
            import msvcrt

            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        handle.close()
