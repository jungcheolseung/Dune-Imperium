"""E2E of the Victory Point ledger (panels.js vpLedgerContent, 2026-10-11).

User request 2026-10-11: clicking a seat's Victory Points on its seat panel
shows by what means they were scored. The server walks the game and reports
each seat's change per step (GET /games/{id}/vp-ledger, sessions.py
vp_ledger); the page shows one seat's rows in the pile viewer, "R3 +1 → 4"
and the cause drawn from its own log entry, and a click on a row finds that
entry in the action log.

[A] A finished game of AI seats only (every expansion, seed 3), which the
page opens as a review. With the cursor at the end, in Korean and English at
1366x768 and 1600x950, for every seat:

- its Victory Point count is a button that opens the viewer, titled with
  the seat's Leader and its current points, the rows loaded (aria-busy
  false);
- the rows (the start row and one per step) add up to the count on the
  seat panel and to the view's points, each row's total is the running sum,
  its change is signed and coloured, its round reads "R<n>", and every step
  row names its cause;
- a click on a step row scrolls the action log to that entry (visible in the
  log's box) and marks it;
- the viewer fits the window and nothing scrolls sideways.

Then the review cut-off: with the viewer open, a seek to the middle of the
game keeps it open and cuts the rows at the cursor (they add up to the
reviewed points); back at the end, all rows return.

[B] A live game (seat 0 human, three heuristic seats, seed 11): the viewer
stays open while the game is played on, and when the watched seat's points
change it refreshes, its rows adding up to the new count.

[C] A remote server: the seated host opens a seat's ledger; a browser
holding no seat is refused it while the game runs (403, and its page offers
no opener), and reads a finished game's ledger with the room link alone,
opening it from the review.

[D] The log's pictures arriving after the click (2026-10-12): the finished
game of [A] opened in a fresh 1366x768 browser per language, its pictures
held back until a row is clicked. A row whose Victory Point line the game's
own card files apart from its step's line (seed 3: seat 0's Endgame wild
battle icon match, #1014, with the two matched cards' pictures between)
starts out of the log's view; the click shows it marked, and it stays in
view, marked, once the pictures above it have arrived. The page used to
stop holding it there when the browser's scroll anchoring moved the log as
the pictures came, taking that for the reader's own scroll. A third browser
wheels the log away from the line before the pictures come, and they leave
it where the reader put it.

Every scenario: no failed request, no JS error. E2E_SHOTS_DIR names where
the screenshots go (vp_ledger_{ko,en}_{1366,1600}.png), otherwise a
temporary folder.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from common import (
    SERVER_LOG_COPY,
    Check,
    chrome,
    open_context,
    server,
    set_rule_options,
)
from log_follow import take_step
from open_mode import create_game, settled
from playwright.sync_api import TimeoutError as PlaywrightTimeout

check = Check()

SHOTS = Path(os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(prefix="dune-vp-"))
KEY = "e2e-admin-key"
VIEWPORTS = ({"width": 1366, "height": 768}, {"width": 1600, "height": 950})
WORDS = {
    "ko": {"history": "승점 기록", "start": "게임 시작", "now": "현재"},
    "en": {"history": "Victory Point history", "start": "Game start", "now": "now"},
}

LEDGER_JS = """(seat) => {
  const viewer = document.getElementById('pile-viewer');
  const body = document.getElementById('pile-viewer-body');
  const list = viewer.querySelector('.vp-ledger');
  const stat = document.querySelector(
    `#seats .seat[data-seat="${seat}"] .stat[data-stat="victory_point"]`);
  const box = viewer.getBoundingClientRect();
  const log = state.review ? reviewLog(state.review) : state.log;
  return {
    open: !viewer.hidden,
    busy: list ? list.getAttribute('aria-busy') : null,
    seat: list ? Number(list.dataset.seat) : null,
    title: document.getElementById('pile-viewer-title').textContent,
    rows: list ? [...list.querySelectorAll('.vp-row')].map((row) => ({
      index: row.dataset.ledgerIndex === undefined ? null
        : Number(row.dataset.ledgerIndex),
      delta: Number(row.dataset.delta),
      total: Number(row.dataset.total),
      round: row.querySelector('.vp-round').textContent,
      deltaText: row.querySelector('.vp-delta').textContent,
      deltaClass: row.querySelector('.vp-delta').className,
      cause: row.querySelector('.vp-cause').textContent.trim(),
      head: Boolean(row.querySelector('.vp-cause-head')),
      button: Boolean(row.querySelector('[role=button]')),
      wide: row.scrollWidth > row.clientWidth + 1,
    })) : [],
    stat: stat ? {
      shown: Number(stat.lastChild.textContent),
      button: stat.getAttribute('role') === 'button' && stat.tabIndex === 0,
      label: stat.getAttribute('aria-label'),
    } : null,
    points: state.view.players.find((p) => p.player === seat).victory_points,
    leader: seatLeaderName(seat),
    logEnd: log ? log.count : null,
    rect: { left: box.left, top: box.top, right: box.right, bottom: box.bottom },
    page: [document.documentElement.scrollWidth, innerWidth, innerHeight],
    bodyWide: body.scrollWidth > body.clientWidth + 1,
  };
}"""

# Where an entry's lines sit against the log's own box, and which are marked.
LOG_TARGET_JS = """(index) => {
  const list = document.querySelector('#action-log .log-list');
  if (!list) return null;
  const box = list.getBoundingClientRect();
  const nodes = [...list.querySelectorAll(`[data-log-index="${index}"]`)];
  return {
    scrollTop: list.scrollTop,
    nodes: nodes.length,
    marked: nodes.filter((n) => n.classList.contains('log-target')).length,
    visible: nodes.some((n) => {
      const r = n.getBoundingClientRect();
      return r.bottom > box.top && r.top < box.bottom && r.height > 0;
    }),
  };
}"""


# The first of `indices` whose Victory Point line (the one findLogEntry aims
# at) the game's own card files apart from the step's own line: an Endgame
# match, a Combat's rewards.
APART_JS = """(indices) => {
  const list = document.querySelector('#action-log .log-list');
  for (const index of indices) {
    const nodes = [...list.querySelectorAll(`[data-log-index="${index}"]`)];
    const line = nodes.find((n) => n.classList.contains('turn-line'));
    const vp = nodes.find((n) => VP_CAUSE_KINDS.has(n.dataset.eventKind));
    if (line && vp && line.closest('.turn-card') !== vp.closest('.turn-card')) {
      return index;
    }
  }
  return null;
}"""

# From here on, count the pictures above the entry's Victory Point line that
# arrive; and say where that line is and how many pictures above it wait.
WATCH_JS = """(index) => {
  const list = document.querySelector('#action-log .log-list');
  const nodes = [...list.querySelectorAll(`[data-log-index="${index}"]`)];
  const vp = nodes.find((n) => VP_CAUSE_KINDS.has(n.dataset.eventKind));
  const above = (image) =>
    Boolean(image.compareDocumentPosition(vp) & Node.DOCUMENT_POSITION_FOLLOWING);
  const watch = { arrived: 0, last: performance.now() };
  window.vpLedgerPictures = watch;
  list.addEventListener('load', (event) => {
    if (event.target.tagName !== 'IMG') return;
    watch.last = performance.now();
    if (above(event.target)) watch.arrived += 1;
  }, true);
  const box = list.getBoundingClientRect();
  const line = vp.getBoundingClientRect();
  return {
    inView: line.bottom > box.top && line.top < box.bottom,
    waiting: [...list.querySelectorAll('img')]
      .filter((image) => !image.complete && above(image)).length,
  };
}"""

# The entry's Victory Point line itself against the log's box.
VP_LINE_JS = """(index) => {
  const list = document.querySelector('#action-log .log-list');
  const nodes = [...list.querySelectorAll(`[data-log-index="${index}"]`)];
  const vp = nodes.find((n) => VP_CAUSE_KINDS.has(n.dataset.eventKind));
  const box = list.getBoundingClientRect();
  const line = vp.getBoundingClientRect();
  return {
    arrived: window.vpLedgerPictures.arrived,
    marked: nodes.length > 0 && nodes.every((n) => n.classList.contains('log-target')),
    visible: line.bottom > box.top && line.top < box.bottom && line.height > 0,
    line: [Math.round(line.top - box.top), Math.round(line.bottom - box.top)],
    box: Math.round(box.height),
  };
}"""


def ledger(page: Any, seat: int) -> dict[str, Any]:
    result: dict[str, Any] = page.evaluate(LEDGER_JS, seat)
    return result


def opener(seat: int) -> str:
    return f"[data-pile-opener='seat-vp:{seat}']"


def wait_loaded(page: Any, seat: int) -> dict[str, Any]:
    page.wait_for_function(
        "(seat) => { const list = document.querySelector('#pile-viewer .vp-ledger');"
        " return !document.getElementById('pile-viewer').hidden && list"
        " && Number(list.dataset.seat) === seat"
        " && list.getAttribute('aria-busy') === 'false'; }",
        arg=seat,
    )
    return ledger(page, seat)


def open_ledger(page: Any, seat: int) -> dict[str, Any]:
    page.locator(opener(seat)).first.click()
    return wait_loaded(page, seat)


def close_viewer(page: Any) -> None:
    for _ in range(3):
        if page.evaluate("document.getElementById('pile-viewer').hidden"):
            return
        page.keyboard.press("Escape")


def check_rows(info: dict[str, Any], label: str, lang: str) -> None:
    rows = info["rows"]
    stat = info["stat"]
    check.ok(
        info["open"] and info["busy"] == "false" and rows,
        f"{label}: the viewer is open with its rows loaded",
        (info["open"], info["busy"], len(rows)),
    )
    if not rows or stat is None:
        return
    total = sum(row["delta"] for row in rows)
    check.ok(
        total == stat["shown"] == info["points"],
        f"{label}: the rows add up to the seat panel's {stat['shown']}",
        (total, stat["shown"], info["points"]),
    )
    running = 0
    chained = True
    for row in rows:
        running += row["delta"]
        chained = chained and row["total"] == running
    check.ok(chained, f"{label}: each row's total is the running sum")
    start, steps = rows[0], rows[1:]
    words = WORDS[lang]
    check.ok(
        start["index"] is None and start["cause"] == words["start"],
        f"{label}: the first row is the start ({words['start']})",
        start,
    )
    check.ok(
        info["title"].startswith(info["leader"])
        and words["history"] in info["title"]
        and f"{words['now']} {stat['shown']}" in info["title"],
        f"{label}: the title names the seat and its points",
        info["title"],
    )
    bad = [
        row
        for row in steps
        if row["index"] is None
        or row["index"] >= info["logEnd"]
        or row["delta"] == 0
        or not re.fullmatch(r"R\d+", row["round"])
        or row["deltaText"]
        != ("+" if row["delta"] > 0 else "−") + str(abs(row["delta"]))
        or ("gain" if row["delta"] > 0 else "loss") not in row["deltaClass"]
        or not row["head"]
        or not row["cause"]
        or not row["button"]
    ]
    check.ok(
        not bad,
        f"{label}: {len(steps)} step rows, each with a round, a signed change and"
        " a cause, inside the log on screen",
        bad[:2],
    )


def check_fit(info: dict[str, Any], label: str) -> None:
    rect = info["rect"]
    width, inner_width, inner_height = info["page"]
    check.ok(
        rect["left"] >= 0
        and rect["top"] >= 0
        and rect["right"] <= inner_width
        and rect["bottom"] <= inner_height
        and width == inner_width
        and not info["bodyWide"]
        and not any(row["wide"] for row in info["rows"]),
        f"{label}: the viewer fits the {inner_width}x{inner_height} window,"
        " nothing scrolls sideways",
        (rect, info["page"], info["bodyWide"]),
    )


def check_find(page: Any, info: dict[str, Any], label: str) -> None:
    """A click on a step row moves the log to that entry and marks it."""

    steps = [row for row in info["rows"] if row["index"] is not None]
    if not steps:
        return
    # The first row too, far from where the log stands when it follows the
    # end, so the click has to move it.
    for row in {row["index"]: row for row in (steps[0], steps[-1])}.values():
        index = row["index"]
        page.locator(
            f"#pile-viewer .vp-row[data-ledger-index='{index}'] [role=button]"
        ).click()
        page.wait_for_timeout(50)
        found = page.evaluate(LOG_TARGET_JS, index)
        check.ok(
            found is not None
            and found["nodes"] > 0
            and found["marked"] == found["nodes"]
            and found["visible"],
            f"{label}: a click on the row of entry #{index} shows it marked in the log",
            found,
        )
    check.ok(
        ledger(page, info["seat"])["open"], f"{label}: the viewer stays open after it"
    )


def shoot(page: Any, info: dict[str, Any], name: str) -> None:
    """The viewer from its top, its first step found in the log."""

    page.evaluate("document.getElementById('pile-viewer-body').scrollTop = 0")
    steps = [row for row in info["rows"] if row["index"] is not None]
    if steps:
        page.locator(
            f"#pile-viewer .vp-row[data-ledger-index='{steps[0]['index']}']"
            " [role=button]"
        ).click()
        page.wait_for_timeout(50)
    page.screenshot(path=str(SHOTS / name))


def scenario_review(base: str, browser: Any) -> str:
    print("[A] a finished game of AI seats, reviewed")
    context, page, rec = open_context(browser, "review", VIEWPORTS[0])
    game_id = create_game(page, base, humans=(), seed=3, options=None)
    page.wait_for_function("state.review !== null && state.view !== null")
    page.evaluate("stopPlayback()")
    end = page.evaluate("state.review.meta.step_count")
    page.evaluate("(cursor) => reviewSeek(cursor)", end)
    page.wait_for_function(
        "(end) => state.review.cursor === end && !state.review.seek", arg=end
    )
    for lang in ("ko", "en"):
        if page.evaluate("TERM_LANGUAGE") != lang:
            page.click("#language-toggle")
            page.wait_for_function(f"TERM_LANGUAGE === '{lang}'")
        for viewport in VIEWPORTS:
            page.set_viewport_size(viewport)
            page.wait_for_timeout(150)
            settle_review(page)
            size = f"[{lang} {viewport['width']}]"
            for seat in range(4):
                stat = ledger(page, seat)["stat"]
                check.ok(
                    stat is not None and stat["button"],
                    f"{size} seat {seat}: its Victory Points are a button",
                    stat,
                )
                info = open_ledger(page, seat)
                check_rows(info, f"{size} seat {seat}", lang)
                check_fit(info, f"{size} seat {seat}")
                check_find(page, info, f"{size} seat {seat}")
                if seat == 1:
                    shoot(page, info, f"vp_ledger_{lang}_{viewport['width']}.png")
                close_viewer(page)
    check_review_cut(page, end)
    failed = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
    check.ok(not failed, "[A] no failed requests", failed[:5])
    context.close()
    return game_id


def settle_review(page: Any) -> None:
    """A language switch in a review seeks the cursor again (i18n.js
    redrawForLanguage), and the render it ends with puts the log back at the
    cursor: wait for it before finding anything in the log."""

    page.wait_for_function(
        "state.review !== null && !state.review.seek && refreshFlight === null"
    )


def check_review_cut(page: Any, end: int) -> None:
    """The open ledger follows the review cursor."""

    points = vp_of(page)
    seat = max(range(4), key=lambda s: points[s])
    info = open_ledger(page, seat)
    full = len(info["rows"])
    middle = end // 2
    page.evaluate("(cursor) => reviewSeek(cursor)", middle)
    page.wait_for_function(
        "(cursor) => state.review.cursor === cursor && !state.review.seek", arg=middle
    )
    cut = wait_loaded(page, seat)
    check.ok(
        cut["open"] and len(cut["rows"]) < full,
        "[cut] a seek to the middle keeps the viewer open with fewer rows",
        (cut["open"], len(cut["rows"]), full),
    )
    check_rows(cut, "[cut] mid-game", page.evaluate("TERM_LANGUAGE"))
    page.evaluate("(cursor) => reviewSeek(cursor)", end)
    page.wait_for_function(
        "(end) => state.review.cursor === end && !state.review.seek", arg=end
    )
    back = wait_loaded(page, seat)
    check.ok(
        len(back["rows"]) == full,
        "[cut] back at the end, every row returns",
        (len(back["rows"]), full),
    )
    close_viewer(page)


def scenario_slow_pictures(base: str, browser: Any, game_id: str) -> None:
    """[D] The log's pictures arrive after the click, as over a slow link.

    A row whose Victory Point line the game's own card files apart from its
    step's line (an Endgame match, a Combat's rewards) has the log's card
    pictures between the two. They load as they come, and the browser's
    scroll anchoring holds the line at the top of the box in place as they
    arrive, not the target: in a 1366x768 window, whose log is a few lines
    tall, the Victory Point line slid out of view (2026-10-12, an Endgame
    wild battle icon match, while the first pictures were still loading).
    Each language opens the finished game of [A] in a fresh browser whose
    pictures are held back until after the click, then let through. A third
    browser scrolls the log itself before they come: the page leaves the
    reader's own scroll alone.
    """

    print("[D] the log's pictures arrive after a row's click")
    for lang in ("ko", "en"):
        check_slow_pictures(base, browser, game_id, lang, reader_scrolls=False)
    check_slow_pictures(base, browser, game_id, "ko", reader_scrolls=True)


def check_slow_pictures(
    base: str, browser: Any, game_id: str, lang: str, reader_scrolls: bool
) -> None:
    label = f"[pictures {lang} {VIEWPORTS[0]['width']}{' scrolled' * reader_scrolls}]"
    context, page, rec = open_context(browser, f"pictures-{lang}", VIEWPORTS[0])
    held: list[Any] = []
    holding = [True]

    def hold(route: Any) -> None:
        if holding[0] and route.request.resource_type == "image":
            held.append(route)
        else:
            route.continue_()

    def release() -> None:
        holding[0] = False
        while held:
            held.pop().continue_()

    context.route("**/*", hold)
    try:
        page.goto(f"{base}/#game={game_id}")
        page.wait_for_function(
            "(id) => state.gameId === id && state.review !== null"
            " && state.view !== null",
            arg=game_id,
        )
        page.evaluate("stopPlayback()")
        end = page.evaluate("state.review.meta.step_count")
        page.evaluate("(cursor) => reviewSeek(cursor)", end)
        page.wait_for_function(
            "(end) => state.review.cursor === end && !state.review.seek", arg=end
        )
        if page.evaluate("TERM_LANGUAGE") != lang:
            page.click("#language-toggle")
            page.wait_for_function(f"TERM_LANGUAGE === '{lang}'")
        settle_review(page)
        index = None
        for seat in range(4):
            info = open_ledger(page, seat)
            steps = [row["index"] for row in info["rows"] if row["index"] is not None]
            index = page.evaluate(APART_JS, steps)
            if index is not None:
                break
            close_viewer(page)
        if not check.ok(
            index is not None,
            f"{label}: some seat's row has its Victory Point line in the game's"
            " card, apart from its step's line",
        ):
            return
        before = page.evaluate(WATCH_JS, index)
        check.ok(
            not before["inView"] and before["waiting"] > 0 and bool(held),
            f"{label} seat {seat}: entry #{index}'s line is out of the log's view,"
            " below pictures held back",
            (before, len(held)),
        )
        page.locator(
            f"#pile-viewer .vp-row[data-ledger-index='{index}'] [role=button]"
        ).click()
        # The pictures the scroll brings near are asked for, and held too.
        page.wait_for_timeout(200)
        placed = page.evaluate(VP_LINE_JS, index)
        check.ok(
            placed["marked"] and placed["visible"],
            f"{label} seat {seat}: a click on its row shows that line marked",
            placed,
        )
        if reader_scrolls:
            # The reader's own wheel on the log, up and away from the line.
            box = page.locator("#action-log .log-list").bounding_box()
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.mouse.wheel(0, -400)
            page.wait_for_function(
                "(index) => { const list = document.querySelector("
                "'#action-log .log-list'); const vp = [...list.querySelectorAll("
                "`[data-log-index=\"${index}\"]`)].find((n) =>"
                " VP_CAUSE_KINDS.has(n.dataset.eventKind));"
                " return vp.getBoundingClientRect().top"
                " > list.getBoundingClientRect().bottom; }",
                arg=index,
            )
        release()
        try:
            page.wait_for_function(
                "() => window.vpLedgerPictures.arrived > 0"
                " && performance.now() - window.vpLedgerPictures.last > 250",
                timeout=2000,
            )
        except PlaywrightTimeout:  # reported by the check below
            pass
        found = page.evaluate(VP_LINE_JS, index)
        if reader_scrolls:
            check.ok(
                found["arrived"] > 0 and found["marked"] and not found["visible"],
                f"{label} seat {seat}: once the reader scrolls the log, the"
                " pictures arriving leave it where the reader put it",
                found,
            )
        else:
            check.ok(
                found["arrived"] > 0 and found["marked"] and found["visible"],
                f"{label} seat {seat}: it stays in view, marked, while the pictures"
                " above it arrive",
                found,
            )
        failed = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
        check.ok(not failed, f"{label}: no failed requests", failed[:5])
    finally:
        release()
        context.close()


def vp_of(page: Any) -> list[int]:
    points: list[int] = page.evaluate(
        "state.view.players.map((p) => p.victory_points)"
    )
    return points


def scenario_live(base: str, browser: Any) -> None:
    print("[B] a live game: the open ledger refreshes as points change")
    context, page, rec = open_context(browser, "live", VIEWPORTS[1])
    create_game(page, base, humans=(0,), seed=11)
    # Play into the game until some seat has scored.
    for _ in range(400):
        if max(vp_of(page)) >= 3 or page.evaluate("state.summary.finished"):
            break
        take_step(page)
    points = vp_of(page)
    seat = max(range(4), key=lambda s: points[s])
    info = open_ledger(page, seat)
    check_rows(info, f"[live] seat {seat}", "ko")
    check_find(page, info, f"[live] seat {seat}")
    before = points[seat]
    rows = len(info["rows"])
    changed = False
    stayed_open = True
    steps = 0
    while steps < 400 and not page.evaluate("state.summary.finished"):
        take_step(page)
        steps += 1
        assert settled(page, 20)
        stayed_open = stayed_open and ledger(page, seat)["open"]
        if vp_of(page)[seat] != before:
            changed = True
            break
    check.ok(
        stayed_open,
        f"[live] the viewer stayed open through {steps} steps of play",
    )
    if check.ok(changed, f"[live] seat {seat}'s points changed during play"):
        after = wait_loaded(page, seat)
        check.ok(
            after["open"] and len(after["rows"]) > rows,
            "[live] the open viewer refreshed with the new step's row",
            (after["open"], len(after["rows"]), rows),
        )
        check_rows(after, f"[live] seat {seat} after the change", "ko")
    close_viewer(page)
    failed = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
    check.ok(not failed, "[B] no failed requests", failed[:5])
    context.close()


FETCH_LEDGER_JS = """async (id) => {
  const response = await fetch(`/games/${id}/vp-ledger`);
  return { status: response.status, body: await response.json() };
}"""

CREATE_AI_GAME_JS = """async () => {
  const response = await fetch('/games', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ seats: ['heuristic', 'heuristic', 'heuristic',
                                   'heuristic'], game_seed: 3 }),
  });
  return response.json();
}"""


def check_finished_remote(guest: Any, host: Any, base: str) -> None:
    """A finished game is public (OQ-010 ruling 4): the room link alone reads
    its ledger, and a seatless browser watching it opens the viewer."""

    done = host.evaluate(CREATE_AI_GAME_JS)
    check.ok(done.get("finished") is True, "[remote] the host made a finished AI game")
    allowed = guest.evaluate(FETCH_LEDGER_JS, done["game_id"])
    check.ok(
        allowed["status"] == 200 and "entries" in allowed["body"],
        "[remote] the room link reads a finished game's ledger",
        allowed["status"],
    )
    guest.goto(f"{base}/#game={done['game_id']}")
    guest.wait_for_function(
        "(id) => state.gameId === id && state.review !== null && state.view !== null",
        arg=done["game_id"],
    )
    guest.evaluate("stopPlayback()")
    end = guest.evaluate("state.review.meta.step_count")
    guest.evaluate("(cursor) => reviewSeek(cursor)", end)
    guest.wait_for_function(
        "(end) => state.review.cursor === end && !state.review.seek", arg=end
    )
    info = open_ledger(guest, 0)
    check_rows(info, "[remote] seatless, finished game, seat 0", "ko")
    close_viewer(guest)


def scenario_remote(browser: Any) -> None:
    print("[C] a remote server: a seat and a browser holding none")
    with server("--remote", "--admin-key", KEY) as (base, log_path):
        context, host, rec = open_context(browser, "host", VIEWPORTS[0])
        guest_context, guest, guest_rec = open_context(browser, "guest", VIEWPORTS[0])
        try:
            host.goto(f"{base}/#admin={KEY}")
            host.wait_for_selector("#setup-screen:not([hidden])")
            host.wait_for_function(
                "state.server !== null"
                " && document.querySelectorAll('#seat-selects select').length === 4"
            )
            for seat in (1, 2, 3):
                host.select_option(
                    f"#seat-selects select[data-seat='{seat}']", "heuristic"
                )
            set_rule_options(host)
            host.click("#create-game")
            host.wait_for_selector("#lobby-screen:not([hidden])")
            game_id = host.evaluate("state.gameId")
            host.fill("#lobby-name", "호스트")
            host.click("#lobby-seats li[data-seat='0'] button")
            host.wait_for_selector("#game-screen:not([hidden])")
            host.wait_for_function("state.view !== null && refreshFlight === null")
            for _ in range(300):
                if max(vp_of(host)) >= 2 or host.evaluate("state.summary.finished"):
                    break
                take_step(host)
            points = vp_of(host)
            seat = max(range(4), key=lambda s: points[s])
            info = open_ledger(host, seat)
            check_rows(info, f"[remote] host, seat {seat}", "ko")
            check_find(host, info, f"[remote] host, seat {seat}")
            close_viewer(host)
            guest.goto(f"{base}/#game={game_id}")
            guest.wait_for_selector("#lobby-screen:not([hidden])")
            refused = guest.evaluate(FETCH_LEDGER_JS, game_id)
            check.ok(
                refused["status"] == 403 and "entries" not in refused["body"],
                "[remote] a browser holding no seat gets no ledger while the game"
                " runs (403)",
                refused,
            )
            check.ok(
                not guest.evaluate("vpLedgerReadable()")
                and host.evaluate("vpLedgerReadable()"),
                "[remote] so its page offers no opener; the seated host's does",
            )
            check_finished_remote(guest, host, base)
            for name, recorder in (("host", rec), ("guest", guest_rec)):
                failed = [
                    r
                    for r in recorder.requests
                    if r[3] is not None
                    and r[3] >= 400
                    and not (name == "guest" and r[3] == 403 and "vp-ledger" in r[2])
                ]
                check.ok(
                    not failed, f"[C] {name}: no other failed requests", failed[:5]
                )
        finally:
            context.close()
            guest_context.close()
            shutil.copy(log_path, SERVER_LOG_COPY.with_name("dune-e2e-vp-remote.log"))
        text = log_path.read_text()
        check.ok(
            "Traceback" not in text and "ERROR" not in text,
            "[C] no server errors",
        )


def main() -> None:
    with server() as (base, log_path), chrome() as browser:
        try:
            game_id = scenario_review(base, browser)
            scenario_slow_pictures(base, browser, game_id)
            scenario_live(base, browser)
            scenario_remote(browser)
        finally:
            shutil.copy(log_path, SERVER_LOG_COPY)
        text = log_path.read_text()
        check.ok(
            "Traceback" not in text and "ERROR" not in text,
            f"no server errors (see {SERVER_LOG_COPY})",
        )
    print(f"screenshots: {SHOTS}")
    check.finish()


if __name__ == "__main__":
    main()
