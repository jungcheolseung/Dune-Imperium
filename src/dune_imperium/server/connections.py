"""How many connections the play server holds, and for how long a request
may take to arrive (2026-11 security review, finding 1).

uvicorn (with h11) puts no time limit on a request whose head has not
arrived: its keep-alive timer only runs between a response and the next
request, and stops at the first byte of that request. So anyone who reached
the port could open hundreds of connections, send half a request head on
each, and hold them for ever; once the process ran out of file descriptors
no game answered, and every failed ``accept`` logged a line
(``docs/reviews/2026-11-cloud-server-security.md``). ``guarded_h11_protocol``
closes that:

- a request's head and body must arrive within ``request_seconds`` of its
  first byte (of the connection, for its first request), so a half-sent
  request is dropped; an answer that takes long (an AI's turn, a doorbell
  stream) is not limited, since the request has arrived by then;
- at most ``max_connections`` are open at once, and at most
  ``max_per_client`` from one address, so one machine cannot take every
  slot; a connection past either is closed as soon as it is accepted;
- what it closes it reports at most once a minute, with a count.

``raise_open_file_limit`` lifts the process's soft descriptor limit (256 on
macOS, 1024 under systemd) towards its hard limit,
``fitting_max_connections`` keeps the connection cap below what is left,
and ``fitting_backlog`` the listen backlog below what the cap leaves:
asyncio accepts up to a backlog's worth of connections in one go, before
any of them can be refused, so ``accept`` itself never runs out.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Final

from uvicorn.protocols.http.h11_impl import H11Protocol

DEFAULT_MAX_CONNECTIONS: Final = 256
# A browser keeps at most six connections to one server (one of them the
# doorbell stream); this leaves room for a few browsers behind one address.
DEFAULT_MAX_PER_CLIENT: Final = 32
# Every real request is under 64 KiB (``guards.MAX_REQUEST_BODY_BYTES``).
DEFAULT_REQUEST_SECONDS: Final = 10.0
# The soft limit asked for at start, and the descriptors kept for everything
# that is not a client socket (the listening socket, a save being written,
# the interpreter's own files). A connection may hold a second descriptor
# while it sends a picture.
WANTED_OPEN_FILES: Final = 4096
UVICORN_BACKLOG: Final = 2048
_RESERVED_FILES: Final = 128
_NOTICE_SECONDS: Final = 60.0

_log = logging.getLogger("uvicorn.error")


@dataclass(frozen=True, slots=True)
class ConnectionLimits:
    max_connections: int = DEFAULT_MAX_CONNECTIONS
    max_per_client: int = DEFAULT_MAX_PER_CLIENT
    request_seconds: float = DEFAULT_REQUEST_SECONDS

    def __post_init__(self) -> None:
        if self.max_connections < 1 or self.max_per_client < 1:
            raise ValueError("connection limits must be at least 1")
        if self.request_seconds <= 0:
            raise ValueError("the request timeout must be positive")


class _Notices:
    """Say what was closed, at most once a minute per kind, with a count."""

    def __init__(self) -> None:
        self._last: dict[str, float] = {}
        self._held: dict[str, int] = {}

    def say(self, kind: str, message: str) -> None:
        now = time.monotonic()
        last = self._last.get(kind)
        if last is not None and now - last < _NOTICE_SECONDS:
            self._held[kind] = self._held.get(kind, 0) + 1
            return
        held = self._held.pop(kind, 0)
        self._last[kind] = now
        more = f" (and {held} more since the last notice)" if held else ""
        _log.warning("%s%s", message, more)


def guarded_h11_protocol(limits: ConnectionLimits) -> type[H11Protocol]:
    """uvicorn's h11 protocol with ``limits`` (pass it as ``Config(http=...)``)."""

    notices = _Notices()

    class GuardedH11Protocol(H11Protocol):
        _read_deadline: asyncio.TimerHandle | None = None
        # Set once this guard drops the connection: it is gone at the next
        # turn of the loop, so it no longer holds a slot.
        _dropped = False

        def connection_made(self, transport: asyncio.Transport) -> None:  # type: ignore[override]
            super().connection_made(transport)
            client = self.client[0] if self.client else None
            # Only connections this guard dropped are left out: one that is
            # merely closing may wait for ever on a peer that stops reading
            # (asyncio flushes before it closes), and still holds its socket.
            live = [
                other
                for other in self.connections
                if isinstance(other, H11Protocol)
                and not getattr(other, "_dropped", False)
            ]
            if len(live) > limits.max_connections:
                notices.say(
                    "total",
                    f"Refused a connection: {limits.max_connections} are open "
                    "(--max-connections)",
                )
                self._drop()
                return
            if client is not None:
                same = sum(
                    1
                    for other in live
                    if other.client is not None and other.client[0] == client
                )
                if same > limits.max_per_client:
                    notices.say(
                        f"client {client}",
                        f"Refused a connection from {client}: "
                        f"{limits.max_per_client} are open from there "
                        "(--max-connections-per-client)",
                    )
                    self._drop()
                    return
            self._arm()

        def data_received(self, data: bytes) -> None:
            super().data_received(data)
            self._follow()

        def on_response_complete(self) -> None:
            # uvicorn starts a pipelined request from here, without a
            # ``data_received``: it gets its deadline here too.
            before = self.cycle
            super().on_response_complete()
            if self.cycle is not before:
                self._follow()

        def connection_lost(self, exc: Exception | None) -> None:
            self._disarm()
            super().connection_lost(exc)

        def _follow(self) -> None:
            """Run the deadline while a request is arriving, stop it once it has."""

            if self._reading() and self._owns_transport():
                self._arm()
            else:
                self._disarm()

        def _reading(self) -> bool:
            """Whether a request is still arriving: no head yet (or only the
            last response's done), or a body still on its way."""

            cycle = self.cycle
            return cycle is None or cycle.response_complete or cycle.more_body

        def _arm(self) -> None:
            # A deadline already running keeps its time: trickling bytes
            # does not buy more.
            if self._read_deadline is None and not self.transport.is_closing():
                self._read_deadline = self.loop.call_later(
                    limits.request_seconds, self._read_timed_out
                )

        def _disarm(self) -> None:
            if self._read_deadline is not None:
                self._read_deadline.cancel()
                self._read_deadline = None

        def _owns_transport(self) -> bool:
            # A WebSocket upgrade hands the transport to another protocol
            # (none is installed today, but uvicorn would take one).
            return bool(self.transport.get_protocol() is self)

        def _drop(self) -> None:
            """Close at once, unsent output and all: ``close`` would wait for
            a peer that stops reading to take it."""

            self._dropped = True
            self._disarm()
            self.transport.abort()

        def _read_timed_out(self) -> None:
            self._read_deadline = None
            if (
                self._reading()
                and self._owns_transport()
                and not self.transport.is_closing()
            ):
                client = self.client[0] if self.client else "?"
                notices.say(
                    "slow",
                    f"Closed a connection from {client} whose request did not "
                    f"arrive within {limits.request_seconds:g} s "
                    "(--request-timeout)",
                )
                self._drop()

    return GuardedH11Protocol


def raise_open_file_limit(wanted: int = WANTED_OPEN_FILES) -> int | None:
    """Raise the soft limit on open files towards ``wanted``, within the
    hard limit; return the soft limit now in force, or ``None`` where there
    is none to read (Windows) or it is unlimited."""

    try:
        import resource
    except ImportError:
        return None
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    target = wanted if hard == resource.RLIM_INFINITY else min(wanted, hard)
    if soft != resource.RLIM_INFINITY and soft < target:
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (target, hard))
        except OSError, ValueError:
            pass
        soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
    return None if soft == resource.RLIM_INFINITY else int(soft)


def fitting_max_connections(requested: int, open_files: int | None) -> int:
    """The most connections that fit in ``open_files`` descriptors, at most
    ``requested``: two for each (a socket and a file it may be sending), past
    a reserve for everything else."""

    if open_files is None:
        return requested
    return max(1, min(requested, (open_files - _RESERVED_FILES) // 2))


def fitting_backlog(open_files: int | None, max_connections: int) -> int:
    """The listen backlog (uvicorn's default 2048) that fits in what
    ``max_connections`` leave of ``open_files``: asyncio accepts up to that
    many at one wake-up, and a refused one closes only on the next, so half
    the room goes to the burst and half to those still closing."""

    if open_files is None:
        return UVICORN_BACKLOG
    room = open_files - _RESERVED_FILES - 2 * max_connections
    return max(16, min(UVICORN_BACKLOG, room // 2))
