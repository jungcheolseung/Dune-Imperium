"""What the play server refuses before a request reaches a game.

The 2026-11 security review (``docs/reviews/2026-11-cloud-server-security.md``)
found no gap in who may do what, only in how much a client may make the
server hold or say. The guards here close the HTTP-level findings:

- ``LimitRequestBody`` (finding 2): a body larger than any real request is
  refused before it is read into memory.
- ``NoStorePrivateResponses`` (finding 4): a seat's hand, its legal actions
  and the host's listings are not kept in a browser's disk cache.
- ``AllowedHosts`` (finding 9): a page that renamed itself to the server's
  address (DNS rebinding) is refused.
- ``LoginThrottle`` (finding 3b): an address that keeps guessing the admin
  key is held off.
- ``validation_error_response`` (finding 6): an invalid body gets a 422 that
  never echoes its input, so ``Infinity`` or a lone surrogate cannot turn it
  into a 500.

Connection-level limits (finding 1) live in ``server.connections``: they
need uvicorn, which only the command line starts.
"""

import ipaddress
import json
import threading
import time
from collections import deque
from collections.abc import Callable, Iterable
from typing import Final

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# The largest body a client sends is POST /games: the setup screen's options
# with every expansion on and four seats, 0.6 KB; a ``checkpoint:<path>``
# seat of the longest path an OS allows (4 KB each) stays under 17 KB. Any
# action, undo, claim, save or load body is under 0.1 KB.
MAX_REQUEST_BODY_BYTES: Final = 64 * 1024
# Paths whose answers are a seat's or the host's own: hands, legal actions,
# logs, the game and save listings, who is asking, the admin page's status.
_PRIVATE_PREFIXES: Final = ("/games", "/saves", "/whoami", "/auth/", "/admin/")


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", ()):
        if key == name:
            text: str = value.decode("latin-1")
            return text
    return None


class LimitRequestBody:
    """Refuse a request body over ``max_bytes`` with 413, before reading it.

    A declared ``Content-Length`` over the limit is answered at once, and
    the connection closed so the rest is never read. A chunked body is
    counted as it arrives and refused as soon as it passes the limit, so at
    most one chunk past the limit is ever held. Pure ASGI like
    ``app._RevalidateUIFiles``, for the same reason.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_REQUEST_BODY_BYTES) -> None:
        self._app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        declared = _header(scope, b"content-length")
        if declared is not None and declared.strip().isdigit():
            if int(declared) > self._max_bytes:
                response = JSONResponse(
                    {"detail": "request body too large"},
                    status_code=413,
                    headers={"Connection": "close"},
                )
                await response(scope, receive, send)
                return
        received = 0

        async def counting_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self._max_bytes:
                    # FastAPI passes an HTTPException from body reading on
                    # unchanged (fastapi/routing.py), so this is the 413.
                    raise HTTPException(
                        413, "request body too large", headers={"Connection": "close"}
                    )
            return message

        await self._app(scope, counting_receive, send)


class NoStorePrivateResponses:
    """Mark every answer under ``_PRIVATE_PREFIXES`` ``Cache-Control: no-store``.

    A browser may keep a validator-less 200 on disk; on a borrowed or shared
    computer that would leave a seat's hand behind. A response that already
    says how to cache (the doorbell stream's ``no-cache``) keeps its own.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope["path"] if scope["type"] == "http" else None
        if path is None or not path.startswith(_PRIVATE_PREFIXES):
            await self._app(scope, receive, send)
            return

        async def send_no_store(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                if "cache-control" not in headers:
                    headers["Cache-Control"] = "no-store"
            await send(message)

        await self._app(scope, receive, send_no_store)


def _host_name(value: str) -> str:
    """The host part of a ``Host`` header, lower case, without port or dot."""

    text = value.strip().lower()
    if text.startswith("["):
        end = text.find("]")
        return text[1:end] if end > 0 else text
    if text.count(":") == 1:
        text = text.split(":", 1)[0]
    return text.rstrip(".")


def host_allowed(
    value: str | None, names: Iterable[str], machine: str | None = None
) -> bool:
    """Return whether a request's ``Host`` header names this server.

    DNS rebinding needs a name the attacker's DNS answers, so an address
    literal (any IP, IPv4 or IPv6) is always this server, and so is a
    request without the header (no browser sends one). A name has to be
    one of ``names``, or, for a Tailscale MagicDNS name, this ``machine``
    in any tailnet (``<machine>.<tailnet>.ts.net``, a domain only
    Tailscale's DNS answers).
    """

    if not value:
        return True
    host = _host_name(value)
    try:
        ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        pass
    else:
        return True
    if host in names:
        return True
    labels = host.split(".")
    return (
        machine is not None
        and len(labels) == 4
        and labels[0] == machine
        and labels[2:] == ["ts", "net"]
    )


class AllowedHosts:
    """Answer 400 to a request whose ``Host`` is not this server (``host_allowed``)."""

    def __init__(
        self, app: ASGIApp, names: Iterable[str], machine: str | None = None
    ) -> None:
        self._app = app
        self._names = frozenset(name.lower().rstrip(".") for name in names)
        self._machine = machine.lower() if machine else None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket") and not host_allowed(
            _header(scope, b"host"), self._names, self._machine
        ):
            response = JSONResponse({"detail": "invalid host header"}, status_code=400)
            await response(scope, receive, send)
            return
        await self._app(scope, receive, send)


class LoginThrottle:
    """Hold off an address after ``failures`` wrong admin keys in ``window``.

    Generated keys and the 16-character minimum already make guessing
    hopeless; this keeps a short key a host chose from being tried at
    hundreds a second. Every attempt counts when it starts (``attempt``), so
    logins sent all at once cannot pass the check together, and a right key
    clears its address (``succeeded``). Called from the login route's worker
    threads, hence the lock; the table forgets idle addresses and never
    holds more than ``max_addresses``.
    """

    def __init__(
        self,
        failures: int = 5,
        window: float = 60.0,
        *,
        clock: Callable[[], float] = time.monotonic,
        max_addresses: int = 1024,
    ) -> None:
        if failures < 1 or window <= 0:
            raise ValueError("a login throttle needs a positive limit and window")
        self._failures = failures
        self._window = window
        self._clock = clock
        self._max_addresses = max_addresses
        self._lock = threading.Lock()
        self._recent: dict[str, deque[float]] = {}

    def _current(self, address: str, now: float) -> deque[float] | None:
        recent = self._recent.get(address)
        if recent is None:
            return None
        while recent and recent[0] <= now - self._window:
            recent.popleft()
        if not recent:
            del self._recent[address]
            return None
        return recent

    def attempt(self, address: str) -> float | None:
        """Count one login attempt from ``address`` as a failure until it
        succeeds; return instead the seconds it must wait, if it is held off
        (that refusal is not counted)."""

        with self._lock:
            now = self._clock()
            recent = self._current(address, now)
            if recent is not None and len(recent) >= self._failures:
                return max(recent[0] + self._window - now, 0.0)
            if recent is None:
                if len(self._recent) >= self._max_addresses:
                    for stale in list(self._recent):
                        self._current(stale, now)
                    while len(self._recent) >= self._max_addresses:
                        del self._recent[next(iter(self._recent))]
                recent = self._recent.setdefault(address, deque())
            recent.append(now)
            return None

    def failures(self, address: str) -> int:
        """The attempts ``address`` has made in the window without the key."""

        with self._lock:
            recent = self._current(address, self._clock())
            return 0 if recent is None else len(recent)

    def succeeded(self, address: str) -> None:
        """Forget ``address``'s attempts: it knew the key."""

        with self._lock:
            self._recent.pop(address, None)


async def validation_error_response(request: Request, error: Exception) -> Response:
    """FastAPI's 422 without the ``input`` it echoes (review finding 6).

    The default answer repeats the whole offending value, so a body of
    megabytes comes back as megabytes, and a value JSON cannot render
    (``Infinity``, a lone surrogate) fails the answer itself with a 500 and
    a traceback. ``loc``, ``msg`` and ``type`` are all a client needs; the
    ASCII-escaped dump renders any text.
    """

    assert isinstance(error, RequestValidationError)
    detail = [
        {
            "loc": [
                part if isinstance(part, int) else str(part)
                for part in entry.get("loc", ())
            ],
            "msg": str(entry.get("msg", "")),
            "type": str(entry.get("type", "")),
        }
        for entry in error.errors()
    ]
    return Response(
        json.dumps({"detail": detail}),
        status_code=422,
        media_type="application/json",
    )
