"""Browser E2E harness for the play server (see README.md in this folder).

Spawns the play server of this checkout, opens cookie-separated browser
contexts and records every request, console line and page error with a
monotonic timestamp, so that a hang can be read off the timeline.

Playwright is deliberately not a project dependency: run these scripts with
a scratch environment that has it (README.md).
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(os.environ.get("E2E_REPO", Path(__file__).resolve().parents[2]))
SERVER_LOG_COPY = Path(tempfile.gettempdir()) / "dune-e2e-server-last.log"
T0 = time.monotonic()


def now() -> float:
    return round(time.monotonic() - T0, 3)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def server(*extra: str):
    port = free_port()
    saves = tempfile.mkdtemp(prefix="dune-e2e-saves-")
    log = open(Path(saves) / "server.log", "w")
    command = [
        str(REPO / ".venv/bin/dune-imperium-server"),
        "--port",
        str(port),
        "--saves-dir",
        saves,
        *extra,
    ]
    process = subprocess.Popen(command, cwd=REPO, stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            if process.poll() is not None:
                raise RuntimeError(Path(saves, "server.log").read_text()) from None
            time.sleep(0.1)
    try:
        yield base, Path(saves) / "server.log"
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        log.close()


class Recorder:
    """Per-context timeline of requests, console lines and page errors."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.events: list[tuple[float, str, str]] = []
        self.js_errors: list[str] = []
        self.requests: list[tuple[float, str, str, int | None]] = []

    def attach(self, page) -> None:
        page.on("console", lambda m: self._console(m))
        page.on("pageerror", lambda e: self._pageerror(e))
        page.on(
            "request",
            lambda r: self.events.append((now(), "req", f"{r.method} {short(r.url)}")),
        )
        page.on("response", lambda r: self._response(r))
        page.on(
            "requestfailed",
            lambda r: self.events.append(
                (now(), "reqfail", f"{r.method} {short(r.url)} {r.failure}")
            ),
        )

    def _console(self, message) -> None:
        self.events.append((now(), "console." + message.type, message.text))
        if message.type == "error":
            self.js_errors.append(message.text)

    def _pageerror(self, error) -> None:
        self.events.append((now(), "pageerror", str(error)))
        self.js_errors.append(str(error))

    def _response(self, response) -> None:
        request = response.request
        self.events.append(
            (now(), "res", f"{response.status} {request.method} {short(response.url)}")
        )
        self.requests.append(
            (now(), request.method, short(response.url), response.status)
        )

    def count(self, method: str, fragment: str, since: float = 0.0) -> int:
        return sum(
            1
            for at, verb, url, _ in self.requests
            if at >= since and verb == method and fragment in url
        )

    def dump(self, since: float = 0.0, limit: int = 80) -> None:
        rows = [row for row in self.events if row[0] >= since]
        print(f"--- timeline of {self.name} ({len(rows)} events, last {limit}) ---")
        for at, kind, text in rows[-limit:]:
            print(f"  {at:8.3f} {kind:14s} {text}")


def short(url: str) -> str:
    return url.split("://", 1)[-1].split("/", 1)[-1] if "://" in url else url


STATE_JS = (
    """() => ({
  busy: state.busy,
  gameId: state.gameId,
  viewSeat: state.viewSeat,
  mine: state.me ? state.me.seats : null,
  rev: state.summary ? state.summary.revision : null,
  undo: state.summary ? state.summary.undo_count : null,
  logCount: state.summary ? state.summary.log_count : null,
  owner: state.summary && state.summary.decision ? state.summary.decision.owner : null,
  kind: state.summary && state.summary.decision ? state.summary.decision.kind : null,
  confirmation: state.summary ? state.summary.confirmation : null,
  finished: state.summary ? state.summary.finished : null,
  nActions: state.actions ? state.actions.actions.length : null,
  actionsRev: state.actions ? state.actions.revision : null,
  logLen: state.log ? state.log.entries.length : null,
  flight: refreshFlight !== null,
  screen: ["setup-screen","landing-screen","lobby-screen","game-screen"].filter("""
    """(id) => !document.getElementById(id).hidden),
  error: document.getElementById("game-error").hidden ? null"""
    """ : document.getElementById("game-error").textContent,
  title: document.title,
})"""
)


def client_state(page) -> dict:
    return page.evaluate(STATE_JS)


class Check:
    def __init__(self) -> None:
        self.failed: list[str] = []
        self.passed = 0

    def ok(self, condition: bool, label: str, detail: object = "") -> bool:
        if condition:
            self.passed += 1
            print(f"  ok   {label}")
        else:
            self.failed.append(label)
            print(f"  FAIL {label} {detail}")
        return bool(condition)

    def finish(self) -> None:
        print(f"\n{self.passed} passed, {len(self.failed)} failed")
        for label in self.failed:
            print(f"  FAILED: {label}")
        sys.exit(1 if self.failed else 0)


def launch_options() -> dict[str, object]:
    """System Chrome by default; `E2E_CHROMIUM` names another executable
    (e.g. a cached `chromium_headless_shell` on a box without Chrome)."""

    executable = os.environ.get("E2E_CHROMIUM")
    if executable:
        return {"executable_path": executable, "headless": True}
    return {"channel": "chrome", "headless": True}


@contextmanager
def chrome():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**launch_options())
        try:
            yield browser
        finally:
            browser.close()


def open_context(browser, name: str):
    context = browser.new_context(viewport={"width": 1600, "height": 1000})
    page = context.new_page()
    recorder = Recorder(name)
    recorder.attach(page)
    page.set_default_timeout(15000)
    return context, page, recorder
