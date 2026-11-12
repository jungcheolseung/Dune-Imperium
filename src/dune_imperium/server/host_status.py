"""What the admin page shows about the server and its machine (2026-11-06).

The host's page (``GET /admin``, ``static/admin.html``) asks ``GET
/admin/status`` for the server's build and options, the machine's load,
memory and disk, and the server's recent log lines, so that a host who
reaches the server over Tailscale need not ssh in to see how it is doing.

Nothing here touches a game: the page lists games through ``GET /games``,
whose summaries are public fields only. The log keeps each record's
message line alone, never its traceback, so no exception text that might
name a card in somebody's hand reaches the page (the host may still read
the full log on the machine itself; ``docs/multiplayer-design.md`` 3).
And it collects only the play server's own loggers (``COLLECTED_LOGGERS``),
whose lines name games, seats and steps by number: an AI seat's logger may
print an action it proposed, a card of its hand among it (Codex review r1,
2026-11-06). A server line must keep to numbers and ids for that reason.
"""

import logging
import os
import platform
import shutil
import socket
import subprocess
import threading
import time
from collections import deque
from collections.abc import Iterable
from pathlib import Path
from typing import Final

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.adapters.observation_encoding import OBSERVATION_VERSION
from dune_imperium.server.persistence import JsonObject, JsonValue

_REPOSITORY: Final = Path(__file__).parents[3]
# Lines kept for the page, and the most of one line it shows.
RECENT_LINES: Final = 200
_MESSAGE_CHARACTERS: Final = 500
_GIT_SECONDS: Final = 2.0
# uvicorn's (where the server's sign-in and connection lines go too) and the
# play server package's; never the agents', rules' or content's.
COLLECTED_LOGGERS: Final = ("uvicorn.error", "dune_imperium.server")


class RecentLog(logging.Handler):
    """Keep the last lines the server logs, for the admin page.

    The command line attaches it to ``COLLECTED_LOGGERS`` after uvicorn has
    configured its logging, which would otherwise remove it again.
    """

    def __init__(self, capacity: int = RECENT_LINES) -> None:
        super().__init__(level=logging.INFO)
        self._lines: deque[JsonObject] = deque(maxlen=capacity)
        self._guard = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:  # a record whose arguments do not fit its format
            message = str(record.msg)
        line: JsonObject = {
            "time": record.created,
            "level": record.levelname,
            "logger": record.name,
            # The first line only: a message never carries a traceback here.
            "message": message.splitlines()[0][:_MESSAGE_CHARACTERS]
            if message
            else "",
        }
        with self._guard:
            self._lines.append(line)

    def lines(self) -> list[JsonObject]:
        """The kept lines, oldest first."""

        with self._guard:
            return list(self._lines)

    def attach(self, names: Iterable[str]) -> None:
        """Start collecting the lines of these loggers.

        A logger with no handler of its own up to the root is printed by
        ``logging.lastResort`` (warnings to standard error), which stops
        the moment any handler is found. So that the console and a
        service's journal keep those lines, such a logger gets the same
        standard-error handler for real before this one joins it.
        """

        for name in names:
            logger = logging.getLogger(name)
            if self in logger.handlers:
                continue
            if not _has_handlers(logger) and logging.lastResort is not None:
                fallback = logging.StreamHandler()
                fallback.setLevel(logging.lastResort.level)
                logger.addHandler(fallback)
            logger.addHandler(self)


def _has_handlers(logger: logging.Logger) -> bool:
    """Whether a record of ``logger`` reaches some handler (``Logger.handle``)."""

    current: logging.Logger | None = logger
    while current is not None:
        if current.handlers:
            return True
        if not current.propagate:
            return False
        current = current.parent
    return False


def source_commit(repository: Path = _REPOSITORY) -> str | None:
    """The commit the server's checkout is at, or ``None`` if git cannot say."""

    try:
        done = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "--short=8", "HEAD"],
            capture_output=True,
            text=True,
            timeout=_GIT_SECONDS,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    commit = done.stdout.strip()
    return commit if done.returncode == 0 and commit else None


def build_versions() -> JsonObject:
    """The versions a save and an AI seat depend on."""

    return {
        "action_codec": ACTION_CODEC_VERSION,
        "observation": OBSERVATION_VERSION,
        "python": platform.python_version(),
    }


def _meminfo() -> dict[str, int]:
    """``/proc/meminfo`` in bytes (Linux only; empty elsewhere)."""

    try:
        text = Path("/proc/meminfo").read_text()
    except OSError:
        return {}
    values: dict[str, int] = {}
    for line in text.splitlines():
        name, _, rest = line.partition(":")
        parts = rest.split()
        if parts and parts[0].isdigit():
            values[name] = int(parts[0]) * 1024
    return values


def _process_rss() -> int | None:
    """This process's resident memory in bytes, where the system says it."""

    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def _memory_total() -> int | None:
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (AttributeError, ValueError, OSError):
        return None


def machine_status(saves_dir: Path) -> JsonObject:
    """The machine's name, load, memory and the disk the saves live on.

    Every figure is best effort: one the system does not offer is ``None``
    (load on Windows, available memory and resident size off Linux).
    """

    try:
        load: JsonValue = [round(value, 2) for value in os.getloadavg()]
    except (AttributeError, OSError):
        load = None
    meminfo = _meminfo()
    disk_total: int | None = None
    disk_free: int | None = None
    probe = saves_dir
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        usage = shutil.disk_usage(probe)
        disk_total, disk_free = usage.total, usage.free
    except OSError:
        pass
    return {
        "name": socket.gethostname(),
        "system": f"{platform.system()} {platform.release()}",
        "cpus": os.cpu_count(),
        "load": load,
        "memory_total": meminfo.get("MemTotal") or _memory_total(),
        "memory_available": meminfo.get("MemAvailable"),
        "process_rss": _process_rss(),
        "disk_total": disk_total,
        "disk_free": disk_free,
    }


def uptime_seconds(started: float, now: float | None = None) -> int:
    return max(0, int((time.time() if now is None else now) - started))
