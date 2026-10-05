"""Table reading space, independent action/history scrolling and persistence.

Uses a real all-expansion human game. It checks visible geometry rather than
CSS declarations: long action lists must not move the turn header or history.
E2E_SHOTS_DIR optionally records compact and wide layouts for visual review.
"""

from __future__ import annotations

import os
from pathlib import Path

from common import Check, chrome, open_context, server

check = Check()


def settle_layout(page) -> None:
    """Let the browser lay out a resize and the layout observer's response."""
    page.evaluate("""async () => {
        await new Promise(requestAnimationFrame);
        await new Promise(requestAnimationFrame);
    }""")


def run(base: str, browser) -> None:
    context, page, _ = open_context(
        browser, "table-layout", {"width": 1440, "height": 900}
    )
    page.goto(base)
    page.wait_for_selector("#seat-selects select")
    for seat in range(4):
        page.select_option(f"#seat-selects select[data-seat='{seat}']", "human")
    page.uncheck("#opt-leader-draft")
    page.fill("#opt-seed", "11")
    page.click("#create-game")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    board = page.locator("#board").bounding_box()
    check.ok(
        board["width"] >= 600,
        "1440px gives the board at least 600px (was 480px)",
        board,
    )
    page.set_viewport_size({"width": 1920, "height": 900})
    settle_layout(page)
    empty_log = page.evaluate("""() => ({
        hidden: document.getElementById('action-log').hidden,
        beside: document.getElementById('table').classList.contains('log-beside'),
    })""")
    check.ok(
        empty_log["hidden"] and not empty_log["beside"],
        "a new game does not reserve a wide column for empty history",
        empty_log,
    )
    page.set_viewport_size({"width": 1440, "height": 900})
    settle_layout(page)

    # Make one actual move to populate the history. It does not need to finish
    # a turn; every placement already creates a public log card.
    page.evaluate(
        "applyAction(state.actions.actions.find("
        "a => a.action_id === 'agent_turn').index)"
    )
    page.wait_for_selector(".log-size-toggle")
    page.wait_for_function("!state.busy && refreshFlight === null")
    page.evaluate("clearTimeout(playEffects.timer)")
    page.set_viewport_size({"width": 1920, "height": 900})
    settle_layout(page)
    cue = page.evaluate("""() => ({
        visible: !document.getElementById('play-effects').hidden,
        right: document.getElementById('play-effects').getBoundingClientRect().right,
        boardRight: document.getElementById('board').getBoundingClientRect().right,
    })""")
    check.ok(
        cue["visible"] and cue["right"] <= cue["boardRight"] - 10,
        "a card-play cue follows the board when history moves beside the choices",
        cue,
    )
    page.set_viewport_size({"width": 1440, "height": 900})
    settle_layout(page)
    page.evaluate("clearPlayEffects()")
    before = page.evaluate("JSON.stringify(state.actions)")
    small = page.locator("#action-log").bounding_box()["height"]
    page.click(".log-size-toggle")
    large = page.locator("#action-log").bounding_box()["height"]
    check.ok(
        large > small + 40, "history expands without leaving the table", [small, large]
    )
    check.ok(
        page.get_attribute(".log-size-toggle", "aria-expanded") == "true",
        "history exposes its expanded state",
    )
    check.ok(
        before == page.evaluate("JSON.stringify(state.actions)"),
        "resizing history never changes the decision",
    )
    page.evaluate("render({foreign: true})")
    check.ok(
        page.get_attribute(".log-size-toggle", "aria-expanded") == "true",
        "history preference survives remote renders",
    )
    page.reload()
    page.wait_for_selector(".log-size-toggle")
    check.ok(
        page.get_attribute(".log-size-toggle", "aria-expanded") == "true",
        "history preference survives reload",
    )
    page.click("#language-toggle")
    check.ok(
        page.inner_text(".log-size-toggle") == "Compact history",
        "history control follows English",
    )
    page.click(".log-size-toggle")
    page.click("#language-toggle")
    check.ok(
        page.inner_text(".log-size-toggle") == "기록 크게 보기",
        "history control follows Korean",
    )

    # Return to the placement choice, and expose the real long action list.
    page.click(".undo-row button")
    page.wait_for_function("!state.busy && refreshFlight === null")
    page.click(".action-list-toggle")
    page.set_viewport_size({"width": 1366, "height": 768})
    scroll = page.evaluate("""() => {
        const actions = document.getElementById('actions');
        const header = document.getElementById('decision-info');
        const log = document.getElementById('action-log');
        const top = header.getBoundingClientRect().top;
        const logTop = log.getBoundingClientRect().top;
        actions.scrollTop = 80;
        return {offset: actions.scrollTop, top,
            after: header.getBoundingClientRect().top,
            logTop, logAfter: log.getBoundingClientRect().top};
    }""")
    check.ok(scroll["offset"] > 0, "long choices scroll inside the action list", scroll)
    check.ok(
        scroll["top"] == scroll["after"] and scroll["logTop"] == scroll["logAfter"],
        "scrolling choices leaves the decision header and history in place",
        scroll,
    )
    page.evaluate("render({foreign: true})")
    check.ok(
        abs(page.eval_on_selector("#actions", "e => e.scrollTop") - scroll["offset"])
        <= 1,
        "remote refresh preserves the action list scroll",
    )

    # The stored vertical expansion should still be there after a wide layout.
    page.click(".log-size-toggle")
    decisions = page.evaluate("JSON.stringify(state.actions)")
    shots = os.environ.get("E2E_SHOTS_DIR")
    sizes = (
        (1366, 768, False),
        (1440, 900, False),
        (1920, 900, True),
        (1920, 1080, False),
        (1920, 1200, False),
        (2560, 1080, True),
        (2560, 1440, True),
        (2400, 1500, True),
        (1280, 800, False),
        (1440, 900, False),
    )
    for width, height, beside in sizes:
        page.set_viewport_size({"width": width, "height": height})
        settle_layout(page)
        geometry = page.evaluate("""() => {
            const box = id => document.getElementById(id).getBoundingClientRect();
            const scan = document.querySelector('.board-stage').getBoundingClientRect();
            return {bodyWidth: document.body.scrollWidth, viewport: innerWidth,
                beside: document.getElementById('table')
                    .classList.contains('log-beside'),
                actionsRight: box('side-main').right,
                actionsWidth: box('side-main').width,
                decision: box('decision-info').bottom,
                history: box('action-log').top, historyLeft: box('action-log').left,
                historyWidth: box('action-log').width,
                historyHeight: box('action-log').height,
                logBottom: box('action-log').bottom, hand: box('private-zone').top,
                boardHeight: box('board').height, scanHeight: scan.height,
                toggleVisible: !!document.querySelector('.log-size-toggle')
                    .offsetParent};
        }""")
        label = f"{width}×{height}"
        check.ok(
            geometry["bodyWidth"] <= geometry["viewport"],
            f"{label}: page has no horizontal overflow",
            geometry,
        )
        check.ok(
            (
                geometry["actionsRight"] <= geometry["historyLeft"]
                if beside
                else geometry["decision"] <= geometry["history"]
            )
            and geometry["logBottom"] <= geometry["hand"],
            f"{label}: controls, history and hand do not overlap",
            geometry,
        )
        check.ok(
            geometry["beside"] == beside and geometry["toggleVisible"] != beside,
            f"{label}: history uses spare board width only when it fits",
            geometry,
        )
        if beside:
            check.ok(
                340 <= geometry["historyWidth"] <= 600
                and geometry["actionsWidth"] == 340
                and abs(geometry["historyHeight"] - geometry["boardHeight"]) <= 1
                and abs(geometry["scanHeight"] - geometry["boardHeight"]) <= 2,
                f"{label}: full-height history preserves board and choice sizes",
                geometry,
            )
        if shots:
            Path(shots).mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(Path(shots) / f"table-{width}-{height}.png"))
    check.ok(
        page.get_attribute(".log-size-toggle", "aria-expanded") == "true"
        and page.locator("#action-log").bounding_box()["height"] > small + 40,
        "the vertical history expansion survives wide and compact layouts",
    )
    check.ok(
        decisions == page.evaluate("JSON.stringify(state.actions)"),
        "responsive layout never changes the available actions",
    )
    page.set_viewport_size({"width": 1760, "height": 900})
    settle_layout(page)
    scan_height = page.locator(".board-stage").bounding_box()["height"]
    check.ok(
        not page.evaluate("el('table').classList.contains('log-beside')"),
        "history stays below when the open market leaves too little spare width",
    )
    page.keyboard.press("c")
    settle_layout(page)
    check.ok(
        page.evaluate("el('table').classList.contains('log-beside')")
        and abs(page.locator(".board-stage").bounding_box()["height"] - scan_height)
        <= 2,
        "folding the market lends spare width to history without shrinking the scan",
    )
    page.keyboard.press("c")
    settle_layout(page)
    check.ok(
        not page.evaluate("el('table').classList.contains('log-beside')"),
        "opening the market returns history below the choices when room runs out",
    )

    # Accumulate a real history to check the full-height scroller, not just
    # the single short card used for geometry above.
    for _ in range(60):
        page.evaluate(
            "typeof state.summary.confirmation === 'number'"
            " ? confirmTurn() : applyAction(0)"
        )
        page.wait_for_function("!state.busy && refreshFlight === null")
    page.set_viewport_size({"width": 1920, "height": 900})
    settle_layout(page)
    scrolling = page.evaluate("""() => {
        const list = document.querySelector('#action-log .log-list');
        const choices = document.getElementById('side-main');
        const top = choices.getBoundingClientRect().top;
        const choiceScroll = choices.scrollTop;
        list.scrollTop = 80;
        window.__historyList = list;
        return {offset: list.scrollTop, top, after: choices.getBoundingClientRect().top,
            choiceScroll, choiceAfter: choices.scrollTop};
    }""")
    check.ok(
        scrolling["offset"] == 80
        and scrolling["top"] == scrolling["after"]
        and scrolling["choiceScroll"] == scrolling["choiceAfter"],
        "wide history scrolls independently of the turn choices",
        scrolling,
    )
    for height in (1200, 900):
        page.set_viewport_size({"width": 1920, "height": height})
        settle_layout(page)
        position = page.evaluate("""() => ({
            same: window.__historyList ===
                document.querySelector('#action-log .log-list'),
            scroll: window.__historyList.scrollTop,
        })""")
        check.ok(
            position["same"] and position["scroll"] == 80,
            f"history keeps its reading position after resizing to 1920×{height}",
            position,
        )
    page.evaluate("window.__historyList.scrollTop = window.__historyList.scrollHeight")
    for height in (1200, 900):
        page.set_viewport_size({"width": 1920, "height": height})
        settle_layout(page)
        remaining = page.evaluate(
            "window.__historyList.scrollHeight - window.__historyList.scrollTop"
            " - window.__historyList.clientHeight"
        )
        check.ok(
            remaining <= 2,
            f"a reader at the latest entry stays there after resizing to 1920×{height}",
            remaining,
        )
    if shots:
        page.evaluate("clearPlayEffects()")
        page.screenshot(path=str(Path(shots) / "table-wide-history.png"))
    context.close()


def main() -> None:
    with server() as (base, _), chrome() as browser:
        run(base, browser)
    check.finish()


if __name__ == "__main__":
    main()
