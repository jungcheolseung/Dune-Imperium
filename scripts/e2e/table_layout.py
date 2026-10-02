"""Table reading space, independent action/history scrolling and persistence.

Uses a real all-expansion human game. It checks visible geometry rather than
CSS declarations: long action lists must not move the turn header or history.
E2E_SHOTS_DIR optionally records the three desktop sizes for visual review.
"""

from __future__ import annotations

import os
from pathlib import Path

from common import Check, chrome, open_context, server

check = Check()


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

    # Make one actual move to populate the history. It does not need to finish
    # a turn; every placement already creates a public log card.
    page.evaluate(
        "applyAction(state.actions.actions.find("
        "a => a.action_id === 'agent_turn').index)"
    )
    page.wait_for_selector(".log-size-toggle")
    page.wait_for_function("!state.busy && refreshFlight === null")
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

    shots = os.environ.get("E2E_SHOTS_DIR")
    for width, height in ((1366, 768), (1440, 900), (1920, 1080)):
        page.set_viewport_size({"width": width, "height": height})
        geometry = page.evaluate("""() => {
            const box = id => document.getElementById(id).getBoundingClientRect();
            return {bodyWidth: document.body.scrollWidth, viewport: innerWidth,
                decision: box('decision-info').bottom, history: box('action-log').top,
                logBottom: box('action-log').bottom, hand: box('private-zone').top};
        }""")
        check.ok(
            geometry["bodyWidth"] <= geometry["viewport"],
            f"{width}px: page has no horizontal overflow",
            geometry,
        )
        check.ok(
            geometry["decision"] <= geometry["history"]
            and geometry["logBottom"] <= geometry["hand"],
            f"{width}px: controls, history and hand do not overlap",
            geometry,
        )
        if shots:
            Path(shots).mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(Path(shots) / f"table-{width}.png"))
    context.close()


def main() -> None:
    with server() as (base, _), chrome() as browser:
        run(base, browser)
    check.finish()


if __name__ == "__main__":
    main()
