"""Which Tailscale account a peer belongs to: the host's own devices sign in.

User decision 2026-11-06: a remote server bound to its Tailscale address may
let the host's own devices become the admin without the admin link (which
otherwise had to be fetched over ssh for every new browser). The friends who
play come over the same tailnet, by machine sharing, so the network alone
says nothing; what tells them apart is the account a device belongs to,
which the local ``tailscaled`` knows for every peer (``tailscale whois``).

This module only asks that question. The HTTP layer asks it once, in
``POST /auth/tailscale``, about the address the connection really came
from, and the session layer judges the answer
(``GameSessionManager.tailnet_admin_login``), which then hands out the same
signed admin cookie as a login with the key. Every other request still
proves itself with that cookie: a cross-site page on the host's device can
make the browser send the sign-in, but it can neither read the answer nor
send the ``SameSite=Strict`` cookie on with its own requests.
"""

import ipaddress
import json
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Final, Protocol

# The addresses tailscaled hands out (tailscale.com/kb/1015/100.x-addresses):
# the CGNAT range and the Tailscale ULA prefix.
TAILSCALE_NETWORKS: Final = (
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("fd7a:115c:a1e0::/48"),
)
# Where the macOS app keeps its command line when ``tailscale`` is not on PATH.
_MACOS_APP_CLI: Final = Path("/Applications/Tailscale.app/Contents/MacOS/Tailscale")
_WHOIS_SECONDS: Final = 3.0
# How long an answer is kept: a page load asks once, and a guest who reloads
# a hundred times still starts one ``tailscale`` process a minute.
_CACHE_SECONDS: Final = 60.0
# A failed lookup (tailscaled restarting) is asked again sooner.
_FAILURE_SECONDS: Final = 10.0
_MAX_CACHED: Final = 256
# The most ``tailscale`` processes running at once, whatever the addresses.
_MAX_RUNNING: Final = 4


def is_tailscale_address(host: str) -> bool:
    """Return whether ``host`` is an address literal tailscaled hands out."""

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(address in network for network in TAILSCALE_NETWORKS)


def login_problem(login: str) -> str | None:
    """Say why ``login`` cannot name a Tailscale account, or ``None``.

    Every account's login name has an ``@`` (``name@gmail.com``,
    ``name@github``); tagged devices answer ``tagged-devices``, which has
    none and so can never be allowed by accident.
    """

    if not login or "@" not in login or any(c.isspace() for c in login):
        return (
            f"{login!r} is not a Tailscale login name (it looks like "
            "name@example.com; see 'tailscale whois' or the admin console)"
        )
    return None


def find_tailscale_cli(named: str | None = None) -> str | None:
    """Return the ``tailscale`` command to run, or ``None`` if there is none."""

    if named:
        return shutil.which(named) or (named if Path(named).is_file() else None)
    found = shutil.which("tailscale")
    if found is None and sys.platform == "darwin" and _MACOS_APP_CLI.is_file():
        return str(_MACOS_APP_CLI)
    return found


class PeerIdentity(Protocol):
    """What the play server asks about a peer (tests answer it themselves)."""

    def login_of(self, address: str) -> str | None:
        """The login name of the account ``address``'s device belongs to."""
        ...


class Runner(Protocol):
    def __call__(
        self, command: Sequence[str], *, timeout: float
    ) -> subprocess.CompletedProcess[bytes]: ...


def _run(
    command: Sequence[str], *, timeout: float
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        list(command),
        capture_output=True,
        timeout=timeout,
        check=False,
        stdin=subprocess.DEVNULL,
    )


class TailscaleWhois:
    """Ask the local tailscaled, through its command line, who a peer is.

    ``login_of`` answers ``None`` for anything it cannot vouch for: an
    address outside Tailscale's ranges (the command is not even run), a
    peer tailscaled does not know, a tagged device (its identity is its
    tags, not the user who tagged it), a command that fails, hangs or
    answers something unexpected. The answers are kept a minute per
    address, and a failure ten seconds, under a bounded table.

    Lookups of one address at once share one run (Codex review r1,
    2026-11-06: a guest's 32 parallel sign-ins would otherwise start 32
    processes), and at most four run at a time; past that a lookup answers
    ``None`` rather than queue.
    """

    def __init__(
        self,
        command: Sequence[str],
        *,
        runner: Runner = _run,
        clock: Callable[[], float] = time.monotonic,
        timeout: float = _WHOIS_SECONDS,
    ) -> None:
        if not command:
            raise ValueError("the tailscale command is empty")
        self._command = tuple(command)
        self._runner = runner
        self._clock = clock
        self._timeout = timeout
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[float, str | None]] = {}
        self._pending: dict[str, threading.Event] = {}
        self._running = threading.BoundedSemaphore(_MAX_RUNNING)

    def login_of(self, address: str) -> str | None:
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError:
            return None
        if not any(parsed in network for network in TAILSCALE_NETWORKS):
            return None
        key = str(parsed)
        with self._lock:
            cached = self._fresh(key)
            if cached is not None:
                return cached[1]
            running = self._pending.get(key)
            if running is None:
                done = self._pending[key] = threading.Event()
        if running is not None:
            # Another request is asking about this address: wait for it.
            running.wait(self._timeout + 1)
            with self._lock:
                cached = self._fresh(key)
            return cached[1] if cached is not None else None
        try:
            if not self._running.acquire(blocking=False):
                return None
            try:
                login, failed = self._ask(key)
            finally:
                self._running.release()
            self._store(key, login, failed)
            return login
        finally:
            with self._lock:
                del self._pending[key]
            done.set()

    def _fresh(self, key: str) -> tuple[float, str | None] | None:
        """The cached answer for ``key`` if it has not expired (lock held)."""

        cached = self._cache.get(key)
        return cached if cached is not None and cached[0] > self._clock() else None

    def _store(self, key: str, login: str | None, failed: bool) -> None:
        now = self._clock()
        expires = now + (_FAILURE_SECONDS if failed else _CACHE_SECONDS)
        with self._lock:
            if len(self._cache) >= _MAX_CACHED:
                self._cache = {k: v for k, v in self._cache.items() if v[0] > now}
                if len(self._cache) >= _MAX_CACHED:
                    self._cache.clear()
            self._cache[key] = (expires, login)

    def _ask(self, address: str) -> tuple[str | None, bool]:
        """The login for ``address`` and whether the lookup itself failed."""

        try:
            # ``address`` is a parsed IP literal, so it can never read as an
            # option of the command.
            done = self._runner(
                (*self._command, "whois", "--json", address), timeout=self._timeout
            )
        except (OSError, subprocess.SubprocessError):
            return None, True
        if done.returncode != 0:
            # tailscaled answers an unknown peer with an error too; either
            # way there is no account to vouch for.
            return None, True
        try:
            answer = json.loads(done.stdout)
        except (ValueError, UnicodeDecodeError):
            return None, True
        if not isinstance(answer, dict):
            return None, True
        node = answer.get("Node")
        profile = answer.get("UserProfile")
        if not isinstance(node, dict) or not isinstance(profile, dict):
            return None, True
        if node.get("Tags"):
            # A tagged device belongs to its tags, whoever tagged it
            # (tailscale's own web client refuses tagged sources too).
            return None, False
        login = profile.get("LoginName")
        if not isinstance(login, str) or login_problem(login) is not None:
            return None, False
        return login, False
