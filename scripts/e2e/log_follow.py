"""E2E of the live action log's auto-follow (panels.js renderLog, 2026-09-24).

Bug this reproduces: renderLog() decided "following" from the previous
list's scroll position alone (`scrollHeight - scrollTop - clientHeight <
24`). A render always scrolls to the FIRST fresh card, not the end, so when
a fresh batch is taller than the list (the leader draft, a round change)
that scroll lands well short of the end. The next render then reads the
reader as "away from the end" and keeps that stale offset forever -- at
round 7 the log still showed an early leader pick while the newest card sat
thousands of pixels below.

This drives a human seat through several rounds of a full-expansion,
leader-draft game and checks, after every step that added log entries, that
the newest ("fresh") card is actually on screen -- which the leader draft's
own batch (four picks landing in one render) is tall enough to break on the
old client. It then checks the two behaviours the fix must not disturb: a
reader who scrolled up to read an earlier turn keeps their exact place, and
scrolling back to the end resumes following.
"""

from __future__ import annotations

import time

from common import (
    RULE_OPTIONS,
    SERVER_LOG_COPY,
    Check,
    chrome,
    open_context,
    server,
    set_rule_options,
)
from open_mode import settled

check = Check()

# Today's date, like open_mode.py's SEED (20260917) names its own day.
SEED = 20260924
VIEWPORT = {"width": 1440, "height": 900}
# Rounds 1-3 fully played means round_number has reached 4 (rules/phases.py
# increments round_number to 1 when round 1 itself starts; it is 0 during
# the leader draft that precedes it).
MIN_ROUND = 4


def create_game(page, base: str, seed: int = SEED) -> str:
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(
            f"#seat-selects select[data-seat='{seat}']",
            "human" if seat == 0 else "heuristic",
        )
    set_rule_options(page, *RULE_OPTIONS)  # every expansion on
    page.set_checked("#opt-leader-draft", True)
    page.fill("#opt-seed", str(seed))
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    return page.evaluate("state.gameId")


def take_step(page) -> tuple[int, int]:
    """Apply the human seat's next action, or confirm a hold, exactly like
    open_mode.py's own driving loop. Returns the log length before and
    after, so callers can tell whether this step actually added entries."""
    deadline = time.monotonic() + 5.0
    while True:
        assert settled(page, 20)
        if page.evaluate("state.summary.confirmation === state.viewSeat"):
            before = page.evaluate("state.log.entries.length")
            page.evaluate("confirmTurn()")
            break
        if page.evaluate("Boolean(state.actions && state.actions.actions.length)"):
            index = page.evaluate("state.actions.actions[0].index")
            before = page.evaluate("state.log.entries.length")
            page.evaluate(f"applyAction({index})")
            break
        if time.monotonic() > deadline:
            raise AssertionError("no decision reached for the human seat")
        time.sleep(0.02)
    assert settled(page, 20)
    after = page.evaluate("state.log.entries.length")
    return before, after


def log_follow_state(page) -> dict:
    """Whether the newest ('fresh') card is actually inside the visible
    .log-list viewport right now, measured with getBoundingClientRect (not
    by re-deriving it from scroll math, which is exactly what the bug got
    wrong)."""
    return page.evaluate(
        """() => {
            const list = document.querySelector('#action-log .log-list');
            if (!list) return { present: false };
            const first = list.querySelector('.turn-card.fresh');
            if (!first) return { present: false };
            const listRect = list.getBoundingClientRect();
            const cardRect = first.getBoundingClientRect();
            return {
                present: true,
                inView: cardRect.top >= listRect.top - 1
                    && cardRect.top <= listRect.bottom + 1,
                cardTop: Math.round(cardRect.top),
                listTop: Math.round(listRect.top),
                listBottom: Math.round(listRect.bottom),
            };
        }"""
    )


def check_following(page, label: str) -> None:
    result = log_follow_state(page)
    if not check.ok(result["present"], f"{label}: a fresh turn card exists", result):
        return
    check.ok(
        result["inView"],
        f"{label}: the newest card is inside the log-list viewport",
        result,
    )


def drive_rounds(page, min_round: int, step_cap: int = 4000) -> bool:
    print(
        f"[1] driving through round {min_round - 1}, checking follow after every step"
    )
    steps = 0
    checked = 0
    while True:
        if page.evaluate("state.summary.finished"):
            check.ok(
                False, f"reached round {min_round} before the game finished", steps
            )
            return False
        round_number = page.evaluate("state.summary.round_number")
        if round_number >= min_round:
            break
        if steps >= step_cap:
            check.ok(
                False,
                f"reached round {min_round} within {step_cap} steps",
                round_number,
            )
            return False
        before, after = take_step(page)
        steps += 1
        # The render that takes the log from empty to non-empty resets
        # freshFrom to the count it just saw (panels.js renderLog): a fresh
        # game has nothing to compare against, so that first batch of
        # entries is the baseline, not "new since last seen", and correctly
        # shows no .fresh card at all. That is the one step this loop does
        # not check; every later entries-adding step has a real "before" to
        # be fresh against.
        if after > before and before > 0:
            checked += 1
            check_following(page, f"round {round_number} step {steps}")
    check.ok(
        checked > 0,
        "at least one entries-adding step was checked while following",
        checked,
    )
    print(f"  .. {steps} steps through round {min_round - 1}, {checked} checked")
    return True


def check_manual_scroll_preserved(page) -> None:
    print("[2] a reader scrolled to a middle offset keeps their exact place")
    info = page.evaluate(
        """() => {
            const list = document.querySelector('#action-log .log-list');
            return {
                scrollHeight: list.scrollHeight,
                clientHeight: list.clientHeight,
                range: list.scrollHeight - list.clientHeight,
            };
        }"""
    )
    if not check.ok(
        info["range"] > 100, "the log is tall enough to scroll to a middle offset", info
    ):
        return
    middle = info["range"] // 2
    page.evaluate(
        f"document.querySelector('#action-log .log-list').scrollTop = {middle}"
    )
    actual = page.evaluate("document.querySelector('#action-log .log-list').scrollTop")
    before, after = take_step(page)
    check.ok(after > before, "the move actually added a log entry", (before, after))
    kept = page.evaluate("document.querySelector('#action-log .log-list').scrollTop")
    check.ok(
        kept == actual,
        "the scrolled-up offset survives the next render unchanged",
        (actual, kept),
    )


def check_scroll_to_end_resumes_following(page) -> None:
    print("[3] scrolling back to the end resumes following")
    page.evaluate(
        "(() => { const l = document.querySelector('#action-log .log-list');"
        " l.scrollTop = l.scrollHeight; })()"
    )
    before, after = take_step(page)
    check.ok(after > before, "the move actually added a log entry", (before, after))
    check_following(page, "after scrolling to the end and moving again")


def main() -> None:
    with server() as (base, log_path):
        with chrome() as browser:
            context, page, rec = open_context(browser, "log-follow", VIEWPORT)
            create_game(page, base)
            if drive_rounds(page, MIN_ROUND):
                check_manual_scroll_preserved(page)
                check_scroll_to_end_resumes_following(page)
            failed = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
            check.ok(not failed, "no failed requests", failed[:5])
            check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
            if check.failed:
                rec.dump()
            context.close()
        errors = [
            line
            for line in log_path.read_text().splitlines()
            if "ERROR" in line or "Traceback" in line
        ]
        check.ok(not errors, f"no server errors (see {SERVER_LOG_COPY})", errors[:3])
        SERVER_LOG_COPY.write_text(log_path.read_text())
    check.finish()


if __name__ == "__main__":
    main()
