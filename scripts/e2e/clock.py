"""E2E of the play clock: the game time and each seat's time holding control.

"게임 ui에 플레이한 시간이 기록되면 좋겠어" (user, 2026-10-10). The server
keeps the totals (server/play_clock.py) and the page counts on from the last
snapshot (static/clock.js): the header's game time, each seat panel's total
in its pieces row, and the running seat's spell after the banner's prompt.

[A] Painting, against a stand-in time source (clock.js clockNow and
    clockWallNow) and a made-up clock: h:mm:ss and m:ss, the AI seat a
    narration piece charges before the running seat, the spell, the
    running mark, the "counted since load" title, a stopped clock that
    schedules no tick.
[B] Ticking on the real clock rebuilds nothing and asks for nothing: a
    property put on a seat panel survives, a hover popover stays open, no
    request goes out, and the seat's text moves on.
[C] A loose real-time check: a seat that holds control for about two
    seconds is charged at least one, the AI seats almost nothing.
[D] English titles, and a save loaded without a clock says it counts from
    the load.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from common import LAPTOP_VIEWPORT, SERVER_LOG_COPY, Check, chrome, now, open_context, server
from open_mode import create_game, settled

check = Check()

TEXTS_JS = """() => ({
    header: document.getElementById('game-clock').textContent,
    headerShown: !document.getElementById('game-clock').hidden
        && document.getElementById('game-clock').getClientRects().length > 0,
    headerTitle: document.getElementById('game-clock').title,
    seats: [...document.querySelectorAll("#seats [data-clock='seat']")]
        .map((node) => node.textContent),
    running: [...document.querySelectorAll("#seats [data-clock='seat'].running")]
        .map((node) => Number(node.dataset.clockSeat)),
    spell: [...document.querySelectorAll("#decision-info [data-clock='spell']")]
        .map((node) => node.textContent),
    spellAfterPrompt: (() => {
        const spell = document.querySelector("#decision-info [data-clock='spell']");
        return Boolean(spell && spell.previousElementSibling
            && spell.previousElementSibling.classList.contains('prompt'));
    })(),
    inPrompt: document.querySelectorAll('#decision-info .prompt [data-clock]').length,
    seatTitle: (document.querySelector("#seats [data-clock='seat']") || {}).title || '',
    timer: playClock.timer !== 0,
})"""

# A made-up clock: 59.5 s of game, seat 0 running with half a second of
# spell, seat 1's moves still on the tables for 1.5 s.
CLOCK = {
    "elapsed_ms": 59_500,
    "seat_ms": [1_000, 2_000, 3_000, 4_000],
    "running": 0,
    "spell_ms": 500,
    "narration": [[1, 1_500]],
    "counting": True,
    "known": True,
}

STAND_IN_JS = """(clock) => {
    window.__realClock = window.__realClock || [clockNow, clockWallNow];
    window.clockNow = () => 0;
    window.clockWallNow = () => 0;
    state.summary.clock = clock;
    playClock.anchor = { clock, age: 0, at: 0, wall: 0 };
    render();
}"""

AT_JS = """(at) => {
    window.clockNow = () => at;
    window.clockWallNow = () => at;
    paintClocks();
}"""

REAL_JS = """() => {
    [window.clockNow, window.clockWallNow] = window.__realClock;
}"""


def texts(page) -> dict:
    return page.evaluate(TEXTS_JS)


def painting(page) -> None:
    print("[A] painting against a stand-in clock")
    page.evaluate(STAND_IN_JS, CLOCK)
    steps = [
        # at, header, seats, running mark, spell
        (0, "0:59", ["0:01", "0:02", "0:03", "0:04"], [1], "0:00"),
        (600, "1:00", ["0:01", "0:02", "0:03", "0:04"], [1], "0:00"),
        (1_000, "1:00", ["0:01", "0:03", "0:03", "0:04"], [1], "0:00"),
        (1_500, "1:01", ["0:01", "0:03", "0:03", "0:04"], [0], "0:00"),
        (2_100, "1:01", ["0:01", "0:03", "0:03", "0:04"], [0], "0:01"),
        (2_600, "1:02", ["0:02", "0:03", "0:03", "0:04"], [0], "0:01"),
        (3_600_000, "1:00:59", ["59:59", "0:03", "0:03", "0:04"], [0], "59:59"),
        (3_601_000, "1:01:00", ["1:00:00", "0:03", "0:03", "0:04"], [0], "1:00:00"),
    ]
    for at, header, seats, running, spell in steps:
        page.evaluate(AT_JS, at)
        got = texts(page)
        check.ok(
            got["header"] == header and got["seats"] == seats
            and got["running"] == running and got["spell"] == [spell],
            f"A: at +{at} ms the clocks read {header} / {seats} / spell {spell}"
            f" / running {running}",
            got,
        )
    got = texts(page)
    check.ok(got["headerShown"], "A: the header shows the game time")
    check.ok(
        got["spellAfterPrompt"] and got["inPrompt"] == 0,
        "A: the spell follows the prompt, outside it",
        got,
    )
    check.ok(got["timer"], "A: a running clock schedules its next tick")
    check.ok(
        got["headerTitle"] == page.evaluate("t('clock.game_title')"),
        "A: the header's title names the game time",
        got["headerTitle"],
    )

    unknown = {**CLOCK, "known": False}
    page.evaluate(STAND_IN_JS, unknown)
    got = texts(page)
    since = page.evaluate("t('clock.since_load')")
    check.ok(
        since in got["headerTitle"] and since in got["seatTitle"],
        "A: a clock counted since a load says so in its titles",
        got,
    )

    stopped = {**CLOCK, "running": None, "narration": [], "counting": False}
    page.evaluate(STAND_IN_JS, stopped)
    page.evaluate(AT_JS, 10_000)
    got = texts(page)
    check.ok(
        got["header"] == "0:59" and got["seats"] == ["0:01", "0:02", "0:03", "0:04"]
        and got["running"] == [] and got["spell"] == [] and not got["timer"],
        "A: a stopped clock stands still, marks nobody and schedules no tick",
        got,
    )


PROBE_JS = """() => {
    document.querySelector('#seats .seat').__clockProbe = 'kept';
}"""

PROBE_KEPT_JS = """() => document.querySelector('#seats .seat').__clockProbe === 'kept'"""


def ticking(page, rec) -> None:
    print("[B] ticking rebuilds nothing and asks for nothing")
    page.evaluate(REAL_JS)
    # A fresh snapshot anchors the real clock again.
    page.evaluate("refresh(null, { foreign: true })")
    assert settled(page)
    seat = page.evaluate("state.summary.clock.running")
    check.ok(seat == page.evaluate("state.viewSeat"), "B: the seat on screen holds control")
    page.evaluate(PROBE_JS)
    page.hover("#seats .seat .leader-name.clickable")
    page.wait_for_selector("#card-popover:not([hidden])")
    # The popover's own picture loads first; what follows is the ticks'.
    page.wait_for_timeout(400)
    before = texts(page)
    since = now()
    page.wait_for_timeout(2_600)
    after = texts(page)
    check.ok(
        after["header"] != before["header"]
        and after["seats"][seat] != before["seats"][seat],
        "B: the game time and the running seat's total move on by themselves",
        (before, after),
    )
    check.ok(page.evaluate(PROBE_KEPT_JS), "B: the seat panel was not rebuilt")
    check.ok(
        page.is_visible("#card-popover"), "B: the hover popover stays open through ticks"
    )
    asked = [row for row in rec.events if row[0] >= since and row[1] == "req"]
    check.ok(not asked, "B: ticking makes no request", asked)
    page.mouse.move(5, 300)


def real_time(page) -> None:
    print("[C] a loose real-time check")
    assert settled(page)
    seat = page.evaluate("state.viewSeat")
    start = page.evaluate("state.summary.clock.seat_ms")
    page.wait_for_timeout(1_200)
    if page.evaluate("state.summary.confirmation === state.viewSeat"):
        page.evaluate("confirmTurn()")
    else:
        page.evaluate("applyAction(0)")
    assert settled(page, 20)
    clock = page.evaluate("state.summary.clock")
    gained = [after - was for after, was in zip(clock["seat_ms"], start, strict=True)]
    check.ok(
        gained[seat] >= 1_000,
        "C: the seat that held control was charged its time",
        gained,
    )
    others = [ms for other, ms in enumerate(gained) if other != seat]
    check.ok(
        all(ms < 1_000 for ms in others),
        "C: the AI seats were charged only their own moves",
        gained,
    )
    check.ok(
        clock["elapsed_ms"] >= sum(clock["seat_ms"]) - 5,
        "C: the game time covers every seat's time",
        clock,
    )


def language_and_load(page, saves: Path) -> None:
    print("[D] English titles; a save without a clock counts from the load")
    page.click("#language-toggle")
    page.wait_for_function("TERM_LANGUAGE === 'en'")
    got = texts(page)
    check.ok(got["headerTitle"] == "Game time", "D: English header title", got)
    check.ok(
        got["seatTitle"].startswith("Time used by Player"),
        "D: English seat title",
        got["seatTitle"],
    )
    page.click("#language-toggle")
    page.wait_for_function("TERM_LANGUAGE === 'ko'")

    game_id = page.evaluate("state.gameId")
    saved = page.evaluate(
        """(id) => api(`/games/${id}/save`, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: 'clock'})})""",
        game_id,
    )
    path = saves / f"{saved['save_id']}.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    check.ok(
        isinstance(document.get("clock"), dict)
        and document["clock"]["elapsed_ms"] > 0,
        "D: the save carries the clock",
        document.get("clock"),
    )
    document.pop("clock")
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    loaded = page.evaluate(
        "(id) => api(`/saves/${id}/load`, {method: 'POST'})", saved["save_id"]
    )
    page.evaluate("(id) => openGame(id)", loaded["game_id"])
    page.wait_for_function(
        "(id) => state.gameId === id && state.view !== null && refreshFlight === null",
        arg=loaded["game_id"],
    )
    got = texts(page)
    since = page.evaluate("t('clock.since_load')")
    check.ok(
        got["headerShown"] and since in got["headerTitle"],
        "D: the loaded game's clock says it counts from the load",
        got,
    )


def main() -> None:
    with server() as (base, log_path), chrome() as browser:
        try:
            _, page, rec = open_context(browser, "clock", LAPTOP_VIEWPORT)
            create_game(page, base, humans=(0,), seed=7)
            painting(page)
            ticking(page, rec)
            real_time(page)
            language_and_load(page, Path(log_path).parent)
        finally:
            shutil.copy(log_path, SERVER_LOG_COPY)
    check.finish()


if __name__ == "__main__":
    main()
