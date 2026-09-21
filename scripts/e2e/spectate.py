"""E2E of watching a game that only AI seats play.

Nobody can sit at such a game, and the server has played it to the end by
the time it answers the create request (a session rests on a human decision
or on the finished game). The page therefore opens it as a replay review
from the first position with playback running: one turn per second by
default, the action log following the cursor. The checks read the cursor
against the page's own table of turn stops, so "one turn per tick" is a
number and not an impression, then walk through the controls: pause, one
step at a time, a faster interval, stepping by hand (takes the wheel), a
seek (does not), another seat's eyes, the end of the game (the result shows,
play starts over), leaving and coming back, a reload. A game with a human
seat must not start playing by itself.
"""

from __future__ import annotations

import json
import shutil
import time

from common import SERVER_LOG_COPY, Check, chrome, now, open_context, server
from open_mode import create_game
from playwright.sync_api import TimeoutError as PlaywrightTimeout

check = Check()

REVIEW_JS = """() => state.review && ({
  seat: state.review.seat,
  cursor: state.review.cursor,
  cameFrom: state.review.cameFrom,
  total: state.review.meta.step_count,
  playing: playback.playing,
  unit: playback.unit,
  intervalMs: playback.intervalMs,
})"""


def review(page) -> dict | None:
    return page.evaluate(REVIEW_JS)


def choose(page, selector: str, value: str) -> None:
    page.select_option(selector, value)


def slow_review(route) -> None:
    time.sleep(0.6)
    route.continue_()


def seek(page, cursor: int) -> None:
    page.evaluate(
        """(cursor) => {
          const slider = document.getElementById("review-slider");
          slider.value = String(cursor);
          slider.dispatchEvent(new Event("change", { bubbles: true }));
        }""",
        cursor,
    )


def sample_moves(page, seconds: float) -> list[tuple[float, int]]:
    """The cursor's distinct values over a while, with when each was first seen."""

    moves: list[tuple[float, int]] = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        cursor = page.evaluate("state.review ? state.review.cursor : -1")
        if not moves or moves[-1][1] != cursor:
            moves.append((time.monotonic(), cursor))
        time.sleep(0.02)
    return moves


def opens_playing(page) -> None:
    print("[1] a game of AI seats only opens as a playing review")
    page.wait_for_function("state.review !== null && state.view !== null")
    now = review(page)
    check.ok(now is not None and now["playing"], "playback is running", now)
    check.ok(
        now is not None and now["unit"] == "turn" and now["intervalMs"] == 1000,
        "one turn per second by default",
        now,
    )
    check.ok(page.is_visible("#review-bar"), "the review bar is up")
    check.ok(page.is_visible("#board .board-stage"), "the board is drawn")
    check.ok(
        "AI 대국 관전" in page.inner_text("#header-status"),
        "the header says what this is",
        page.inner_text("#header-status"),
    )
    check.ok(not page.is_visible("#standings"), "the result is not given away")
    check.ok(
        page.inner_text("#review-play") == "일시정지", "the play button offers a pause"
    )
    own = page.inner_text("#review-next-own")
    check.ok("이 좌석" in own, "nobody's actions are called mine", own)


def walks_turn_by_turn(page, rec) -> None:
    print("[2] the cursor walks along the turn stops, a second apart")
    stops = page.evaluate("state.review.stops")
    total = page.evaluate("state.review.meta.step_count")
    check.ok(
        stops == sorted(set(stops)) and stops[-1] == total and len(stops) > 50,
        "turn stops are increasing and end at the last step",
        (len(stops), stops[:6]),
    )
    labels = page.evaluate("state.review.meta.steps")
    closing = {"finish_agent_turn", "finish_reveal", "pass", "pick_leader"}
    wrong = []
    for stop in stops[:-1]:
        before = [label for label in labels[:stop] if label["type"] == "action"][-1]
        after = labels[stop]
        if after["type"] != "action" or not (
            before["action_id"] in closing or before["actor"] != after["actor"]
        ):
            wrong.append(stop)
    check.ok(not wrong, "every stop lies between two turns", wrong[:5])

    window = now()  # the recorder's clock
    moves = sample_moves(page, 4.3)
    seen = [cursor for _, cursor in moves]
    check.ok(len(seen) >= 4, "it moved several times in four seconds", seen)
    check.ok(
        all(cursor in stops or cursor == 0 for cursor in seen), "only to stops", seen
    )
    indexes = [stops.index(cursor) for cursor in seen if cursor in stops]
    check.ok(
        indexes == list(range(indexes[0], indexes[0] + len(indexes))),
        "and to each stop in turn",
        seen,
    )
    # Playback keeps its interval from one move's request to the next
    # (playbackTick), so that is what is timed. Timing the draws instead let
    # one slow answer — the first replay after the game was made — make the
    # next gap look like half a second on the slower laptop.
    starts = [
        at
        for at, kind, text in rec.events
        if kind == "req" and "/review/" in text and at >= window
    ]
    gaps = [
        round(later - earlier, 2)
        for earlier, later in zip(starts, starts[1:], strict=False)
    ]
    check.ok(
        len(gaps) >= 3 and all(0.8 <= gap <= 1.4 for gap in gaps),
        "about a second between moves",
        gaps,
    )


def log_follows(page) -> None:
    print("[3] the action log and the status follow the cursor")
    page.click("#review-play")
    page.wait_for_function("!playback.playing")
    now = review(page)
    assert now is not None
    shown = page.evaluate(
        "[...document.querySelectorAll('#action-log .turn-index')]"
        ".map((node) => Number(node.textContent.slice(1)))"
    )
    # Nobody could take a step back in this game: log index == step index.
    check.ok(
        bool(shown) and max(shown) == now["cursor"] - 1,
        "the log ends at the step under the cursor",
        (now["cursor"], shown[-3:]),
    )
    fresh = page.evaluate(
        "[...document.querySelectorAll('#action-log .turn-card.fresh .turn-index')]"
        ".map((node) => Number(node.textContent.slice(1)))"
    )
    check.ok(
        bool(fresh) and min(fresh) >= now["cameFrom"],
        "what the last move added is marked fresh",
        (now["cameFrom"], fresh),
    )
    status = page.inner_text("#review-status")
    stride = now["cursor"] - now["cameFrom"]
    check.ok(
        f"step {now['cursor']}/{now['total']}" in status
        and (stride <= 1 or f"외 {stride - 1}수" in status),
        "the status names the turn and how many steps it took",
        status,
    )
    # describeAction() returns nodes; in a template string it read
    # "좌석 0: [object DocumentFragment]" and the check above still passed.
    check.ok("[object" not in status, "the status spells the action out", status)
    header = page.inner_text("#header-status")
    shown_round = page.evaluate("state.review.round")
    check.ok(
        f"라운드 {shown_round} " in header and "게임 종료" not in header,
        "the header shows the position on screen, not the final one",
        header,
    )


def controls(page) -> None:
    print("[4] pause, step unit, interval, hand steps and seeks")
    paused = review(page)
    assert paused is not None
    time.sleep(1.5)
    still = review(page)
    assert still is not None
    check.ok(
        not still["playing"] and still["cursor"] == paused["cursor"],
        "paused means still",
        (paused, still),
    )
    check.ok(page.inner_text("#review-play") == "재생", "the button offers play again")

    choose(page, "#review-unit", "step")
    choose(page, "#review-interval", "250")
    page.click("#review-play")
    moves = sample_moves(page, 1.6)
    page.click("#review-play")
    page.wait_for_function("!playback.playing")
    seen = [cursor for _, cursor in moves]
    check.ok(
        len(seen) >= 4 and seen == list(range(seen[0], seen[0] + len(seen))),
        "one step at a time, four to the second",
        seen,
    )

    choose(page, "#review-unit", "turn")
    choose(page, "#review-interval", "1000")
    page.click("#review-play")
    page.wait_for_function("playback.playing")
    page.click("#review-next")
    page.wait_for_function("!playback.playing")
    check.ok(True, "stepping by hand takes the wheel")

    page.click("#review-play")
    target = page.evaluate("state.review.stops[60]")
    seek(page, target)
    page.wait_for_function(f"state.review.cursor === {target}")
    check.ok(page.evaluate("playback.playing"), "a seek leaves playback running")
    page.wait_for_function(f"state.review.cursor > {target}", timeout=4000)
    check.ok(
        page.evaluate("state.review.cursor === state.review.stops[61]"),
        "and it carries on from there, one turn on",
    )

    # A seek must survive an answer slower than the playback interval. The
    # next tick used to fire while the seek was in flight, ask for the step
    # after the OLD cursor, and win as the later request — on this repo's
    # slower laptop (0.3 s loads against 0.25 s) every seek was thrown away.
    # Every review answer is held 0.6 s here, so the race is not left to the
    # machine's speed.
    choose(page, "#review-interval", "250")
    page.route("**/review/*", slow_review)
    target = page.evaluate("state.review.stops[100]")
    seek(page, target)
    try:
        page.wait_for_function(f"state.review.cursor >= {target}", timeout=10000)
        reached = True
    except PlaywrightTimeout:
        reached = False
    page.unroute("**/review/*")
    check.ok(
        reached and page.evaluate("playback.playing"),
        "a seek survives a review answer slower than the playback interval",
        (target, page.evaluate("state.review.cursor")),
    )

    # The same race from the other side: paused, seek, and press Play before
    # the answer lands — Play scheduled a tick off the old cursor at once.
    # Both happen in one page task, so the tick always beats the answer.
    page.click("#review-play")
    page.wait_for_function("!playback.playing")
    page.route("**/review/*", slow_review)
    target = page.evaluate(
        "state.review.stops[Math.min(140, state.review.stops.length - 2)]"
    )
    page.evaluate(
        """(cursor) => {
          const slider = document.getElementById("review-slider");
          slider.value = String(cursor);
          slider.dispatchEvent(new Event("change", { bubbles: true }));
          document.getElementById("review-play").click();
        }""",
        target,
    )
    try:
        page.wait_for_function(f"state.review.cursor >= {target}", timeout=10000)
        reached = True
    except PlaywrightTimeout:
        reached = False
    page.unroute("**/review/*")
    check.ok(
        reached and page.evaluate("playback.playing"),
        "pressing Play while a seek is in flight keeps the seek",
        (target, page.evaluate("state.review.cursor")),
    )
    choose(page, "#review-interval", "1000")


def other_eyes(page) -> None:
    print("[5] another seat's eyes on the same game")
    before = review(page)
    assert before is not None
    choose(page, "#review-seat", "2")
    page.wait_for_function("state.review && state.review.seat === 2 && state.view")
    page.wait_for_function("playback.playing")
    now = review(page)
    assert now is not None
    check.ok(
        before["cursor"] <= now["cursor"] <= before["cursor"] + 40,
        "the position is kept (it used to jump to the end)",
        (before["cursor"], now["cursor"]),
    )
    hand = page.inner_text("#private-zone .hand-label strong")
    check.ok(
        "좌석 2" in hand and "내 손패" not in hand,
        "an AI seat's hand is not called mine",
        hand,
    )


def the_end(page) -> None:
    print("[6] the end of the game, and starting over")
    choose(page, "#review-interval", "250")
    stops = page.evaluate("state.review.stops")
    seek(page, stops[-4])
    page.wait_for_function(
        "state.review.cursor === state.review.meta.step_count && !playback.playing",
        timeout=8000,
    )
    check.ok(page.is_visible("#standings"), "the result shows on reaching the end")
    check.ok(
        page.locator("#standings tr.winner").count() == 1, "with its winner marked"
    )
    check.ok(
        page.locator("#standings button").count() == 0,
        "no second way in while the game is on screen",
    )
    check.ok(
        page.inner_text("#review-play") == "처음부터 재생",
        "the play button offers to start over",
    )
    page.click("#review-play")
    page.wait_for_function(
        "playback.playing && state.review.cursor < state.review.stops[8]"
    )
    check.ok(not page.is_visible("#standings"), "the result hides again")

    page.click("#review-exit")
    page.wait_for_function("state.review === null && refreshFlight === null")
    check.ok(not page.evaluate("playback.playing"), "leaving stops playback")
    check.ok(page.is_visible("#standings"), "the result stays outside the review")
    check.ok(
        "AI 대국 다시 보기" in page.inner_text("#board"),
        "the empty board says how to get back in",
        page.inner_text("#board"),
    )
    page.click("#standings button")
    page.wait_for_function("state.review !== null && playback.playing")
    check.ok(
        page.evaluate("state.review.cursor < state.review.stops[8]"),
        "the button starts the game over",
    )

    page.reload()
    page.wait_for_function(
        "typeof state !== 'undefined' && state.review !== null && playback.playing"
    )
    check.ok(
        page.evaluate("state.review.cursor < state.review.stops[8]"),
        "a reload opens the same room, playing from the start",
    )
    choose(page, "#review-interval", "1000")


def human_game_is_left_alone(page, base: str) -> None:
    print("[7] a game with a human seat does not play by itself")
    create_game(page, base, humans=(0,), seed=11)
    time.sleep(1.2)
    check.ok(page.evaluate("state.review === null"), "no review opened")
    check.ok(not page.evaluate("playback.playing"), "no playback running")
    check.ok(not page.is_visible("#review-bar"), "no review bar")
    check.ok(page.evaluate("state.actions !== null"), "the human seat has its actions")


def main() -> None:
    with server() as (base, server_log), chrome() as browser:
        try:
            context, page, rec = open_context(browser, "spectator")
            create_game(page, base, humans=(), seed=3)
            opens_playing(page)
            walks_turn_by_turn(page, rec)
            log_follows(page)
            controls(page)
            other_eyes(page)
            the_end(page)
            human_game_is_left_alone(page, base)
            failed = [r for r in rec.requests if r[3] >= 400]
            check.ok(not failed, "no failed requests", failed[:5])
            check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
            context.close()
        finally:
            shutil.copy(server_log, SERVER_LOG_COPY)
        text = server_log.read_text()
        check.ok(
            "Traceback" not in text and "ERROR" not in text,
            f"no server errors (see {SERVER_LOG_COPY})",
        )
    print(json.dumps({"passed": check.passed, "failed": check.failed}))
    check.finish()


if __name__ == "__main__":
    main()
