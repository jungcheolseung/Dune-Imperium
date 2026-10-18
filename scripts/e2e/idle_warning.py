"""E2E of the idle warning (session.js watchIdle, 2026-10-19).

"플레이어가 15초 이상 아무 행동을 하지 않는 상태면 경고음을 재생하게 하고
싶어" (user, 2026-10-19): while a decision or a turn-end press waits on a seat
this screen plays, every 15 seconds without a step sound the idle warning
(sounds.js SOUNDS.idle), again until a step ("15초에 울리고 또 15초 흐르면
또 울려야해", the same day). The page's playSound is wrapped to record each
call and its time: a browser may refuse to play audio before a gesture, and
the call is what this script checks.

One local game, seat 0 human and three heuristic seats, a fixed seed:

[A] the human seat's decision on screen: no warning 14 seconds in, one at
    about 15 seconds, a second at about 30 seconds;
[B] a step starts the wait again: no new warning 14 seconds after the seat's
    next decision arrived, one more at about 15 seconds;
[C] nothing is armed while the decision belongs to another seat or while a
    review is on screen (the summary edited in the page, then put back).

About 55 seconds, nearly all of it waiting.
"""

from __future__ import annotations

import shutil
import time

from common import LAPTOP_VIEWPORT, SERVER_LOG_COPY, Check, chrome, open_context, server
from log_follow import take_step
from open_mode import create_game, settled

check = Check()

WRAP_JS = """() => {
  window.__sounds = [];
  const real = playSound;
  window.playSound = (name) => {
    window.__sounds.push({ name, at: performance.now() });
    real(name);
  };
}"""

IDLE_JS = """(since) => window.__sounds
  .filter((s) => s.name === 'idle' && s.at >= since)
  .map((s) => s.at - since)"""

MINE_JS = """() => !state.busy && refreshFlight === null && isMyTurn(state.summary)
  && (state.summary.confirmation === state.viewSeat
      || Boolean(state.actions && state.actions.actions.length))"""


def wait_mine(page, timeout: float = 60.0) -> float:
    """Wait until the human seat must act; return the page's clock then."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if page.evaluate(MINE_JS):
            return float(page.evaluate("performance.now()"))
        time.sleep(0.05)
    raise AssertionError("the human seat never got a decision")


def idle_after(page, since: float) -> list[float]:
    result: list[float] = page.evaluate(IDLE_JS, since)
    return result


def sleep_until(page, since: float, seconds: float) -> None:
    left = since + seconds * 1000 - float(page.evaluate("performance.now()"))
    if left > 0:
        time.sleep(left / 1000)


def first_wait(page) -> None:
    print("[A] a decision left alone")
    since = wait_mine(page)
    sleep_until(page, since, 14)
    check.ok(idle_after(page, since) == [], "[A] no warning 14 seconds in")
    sleep_until(page, since, 16)
    warned = idle_after(page, since)
    check.ok(
        len(warned) == 1 and 14_000 <= warned[0] <= 15_500,
        "[A] one warning at about 15 seconds",
        warned,
    )
    sleep_until(page, since, 29)
    check.ok(
        len(idle_after(page, since)) == 1,
        "[A] still only one 29 seconds in",
        idle_after(page, since),
    )
    sleep_until(page, since, 31)
    warned = idle_after(page, since)
    check.ok(
        len(warned) == 2 and 29_000 <= warned[1] <= 30_500,
        "[A] a second warning at about 30 seconds",
        warned,
    )


def after_a_step(page) -> None:
    print("[B] a step starts the wait again")
    take_step(page)
    since = wait_mine(page)
    sleep_until(page, since, 14)
    check.ok(
        idle_after(page, since) == [],
        "[B] no new warning 14 seconds after the next decision arrived",
    )
    sleep_until(page, since, 16)
    warned = idle_after(page, since)
    check.ok(
        len(warned) == 1 and 14_000 <= warned[0] <= 15_500,
        "[B] one more warning at about 15 seconds",
        warned,
    )


def nothing_armed(page) -> None:
    print("[C] another seat's decision, a review")
    other = page.evaluate(
        """() => {
          const real = state.summary;
          state.summary = { ...real, confirmation: null,
                            decision: { ...real.decision, owner: 1 } };
          watchIdle();
          const armed = idleTimer !== null || idleKey !== '';
          state.summary = real;
          watchIdle();
          return { armed, rearmed: idleTimer !== null && idleKey !== '' };
        }"""
    )
    check.ok(not other["armed"], "[C] another seat's decision arms nothing", other)
    check.ok(other["rearmed"], "[C] the seat's own decision arms the wait again", other)
    review = page.evaluate(
        """() => {
          state.review = { seat: state.viewSeat };
          watchIdle();
          const armed = idleTimer !== null || idleKey !== '';
          state.review = null;
          watchIdle();
          return armed;
        }"""
    )
    check.ok(not review, "[C] a review arms nothing")


def main() -> None:
    with server() as (base, log_path), chrome() as browser:
        try:
            _, page, rec = open_context(browser, "idle", LAPTOP_VIEWPORT)
            create_game(page, base, humans=(0,), seed=7)
            assert settled(page, 20)
            page.evaluate(WRAP_JS)
            first_wait(page)
            after_a_step(page)
            nothing_armed(page)
            failed = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
            check.ok(not failed, "no failed requests", failed[:5])
            check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
            if check.failed:
                rec.dump()
        finally:
            shutil.copy(log_path, SERVER_LOG_COPY)
        errors = [
            line
            for line in log_path.read_text().splitlines()
            if "ERROR" in line or "Traceback" in line
        ]
        check.ok(not errors, f"no server errors (see {SERVER_LOG_COPY})", errors[:3])
    check.finish()


if __name__ == "__main__":
    main()
