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


# The first block of the history the reader can still see, its offset from
# the list's top and its line height (defined on the page by evaluating this
# once).
READING_ANCHOR_JS = """window.readingAnchor = () => {
    const list = window.__historyList;
    const top = list.getBoundingClientRect().top;
    const node = [...list.querySelectorAll(
        '.turn-head, .turn-line-head, .logevent, .turn-cards, .undo-marker')]
        .find((n) => n.getBoundingClientRect().bottom > top + 1);
    const line = parseFloat(getComputedStyle(node).lineHeight)
        || parseFloat(getComputedStyle(node).fontSize) * 1.2;
    return {node, offset: node.getBoundingClientRect().top - top, line};
}"""


def settle_layout(page) -> None:
    """Let the browser lay out a resize and the layout observer's response."""
    page.evaluate("""async () => {
        await new Promise(requestAnimationFrame);
        await new Promise(requestAnimationFrame);
    }""")


def check_hand(base: str, browser) -> None:
    """Stress the hand projection without inventing or posting engine actions."""
    context, page, rec = open_context(
        browser, "hand-layout", {"width": 1366, "height": 768}
    )
    page.goto(base)
    page.wait_for_selector("#seat-selects select")
    for seat in range(4):
        page.select_option(f"#seat-selects select[data-seat='{seat}']", "human")
    page.uncheck("#opt-leader-draft")
    page.fill("#opt-seed", "11")
    page.click("#create-game")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    # Only the browser's visible projection is enlarged. The real game and
    # its legal actions remain intact; staging a card never posts an action.
    page.evaluate("""() => {
        window.__originalPrivate = structuredClone(state.view.private);
        const own = state.view.private;
        own.hand = Array(4).fill(own.hand).flat();
        own.intrigue_cards = Array(12).fill(own.intrigue_cards).flat();
        own.peeked_card_id = own.hand[0];
        own.peeked_intrigue_ids = own.intrigue_cards.slice(0, 1);
        render();
    }""")
    for language in ("ko", "en"):
        if page.evaluate("TERM_LANGUAGE") != language:
            page.click("#language-toggle")
        settle_layout(page)
        shape = page.evaluate("""() => {
            const box = n => n.getBoundingClientRect();
            const zone = document.getElementById('private-zone');
            const row = zone.querySelector('.hand-zones');
            const hand = row.querySelector('.hand-cards');
            const intrigue = row.querySelector('.intrigue-cards');
            return {height: box(zone).height,
                bottom: box(zone).bottom, viewport: innerHeight,
                handScrolls: hand.scrollWidth > hand.clientWidth + 1,
                intrigueScrolls: intrigue.scrollWidth > intrigue.clientWidth + 1,
                sameRow: [...row.querySelectorAll('.hand-cards .vcard')]
                    .every(n => Math.abs(box(n).top - box(hand.firstChild).top) < 1),
                labelInside: [...zone.querySelector('.hand-label').children]
                    .every(n => box(n).left >= box(zone).left
                        && box(n).right <= box(zone).right),
                cardCount: hand.querySelectorAll('.vcard').length,
                intrigueCount: intrigue.querySelectorAll('.vcard').length};
        }""")
        check.ok(
            shape["cardCount"] == 20
            and shape["intrigueCount"] == 12
            and shape["handScrolls"]
            and shape["intrigueScrolls"]
            and shape["sameRow"]
            and shape["height"] < 230
            and shape["bottom"] <= shape["viewport"]
            and shape["labelInside"],
            f"{language}: a large hand, Intrigue and peeks keep a compact hand zone",
            shape,
        )
        last = page.locator(".hand-cards .vcard.legal").last
        card_id = last.get_attribute("data-instance")
        posts = rec.count("POST", "/actions")
        last.click()
        selected = page.evaluate("""() => {
            const hand = document.querySelector('.hand-cards');
            const cards = [...hand.querySelectorAll('.picked')];
            const card = cards.at(-1).getBoundingClientRect();
            const pane = hand.getBoundingClientRect();
            return {picked: state.pick.cardId, offset: hand.scrollLeft,
                visible: card.left >= pane.left - 1 && card.right <= pane.right + 1};
        }""")
        check.ok(
            selected["picked"] == card_id
            and selected["offset"] > 0
            and selected["visible"]
            and rec.count("POST", "/actions") == posts,
            f"{language}: the last card remains visible when staged after scrolling",
            selected,
        )
        shots = os.environ.get("E2E_SHOTS_DIR")
        if shots:
            Path(shots).mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(Path(shots) / f"hand-large-{language}.png"))
        page.keyboard.press("Escape")
        last_intrigue = page.locator(".intrigue-cards .vcard").last
        last_intrigue.hover()
        page.wait_for_selector("#card-popover:not([hidden])")
        check.ok(
            page.evaluate("document.querySelector('.intrigue-cards').scrollLeft > 0"),
            f"{language}: the last Intrigue card can be reached and inspected",
        )
        before = page.evaluate("""() => [...document.querySelectorAll(
            '#private-zone .strip-cards')].map(n => n.scrollLeft)""")
        page.evaluate("render({foreign: true})")
        after = page.evaluate("""() => [...document.querySelectorAll(
            '#private-zone .strip-cards')].map(n => n.scrollLeft)""")
        check.ok(
            before == after,
            f"{language}: a foreign refresh keeps the hand and Intrigue scroll offsets",
            (before, after),
        )

    page.evaluate("state.view.private.hand.reverse(); render({foreign: true})")
    changed = page.evaluate("""() => [...document.querySelectorAll(
        '#private-zone .strip-cards')].map(n => n.scrollLeft)""")
    check.ok(
        changed[0] == 0 and changed[1:] == after[1:],
        "a changed hand resets its offset while unchanged Intrigue keeps its position",
        (after, changed),
    )
    page.set_viewport_size({"width": 1440, "height": 900})
    sizes = """() => ({
        zone: document.querySelector('#private-zone').getBoundingClientRect().height,
        board: document.querySelector('#board .board-stage, #board')
            .getBoundingClientRect().width,
    })"""
    page.evaluate("""() => {
        state.view.private = structuredClone(window.__originalPrivate);
        render();
    }""")
    settle_layout(page)
    full = page.evaluate(sizes)
    page.evaluate("""() => {
        state.view.private.hand = [];
        state.view.private.intrigue_cards = [];
        render();
    }""")
    settle_layout(page)
    empty = page.evaluate(sizes)
    # A Reveal turn with nothing left in hand must not grow the square board
    # into the hand row (user, 2026-10-11): the row keeps a card's height.
    check.ok(
        abs(empty["zone"] - full["zone"]) <= 1
        and abs(empty["board"] - full["board"]) <= 1
        and page.locator("#private-zone .muted").is_visible(),
        "an empty hand keeps the hand row's height, so the board keeps its size",
        (full, empty),
    )
    page.evaluate("state.view.private = null; renderPrivate()")
    settle_layout(page)
    check.ok(
        page.locator("#private-zone").is_hidden()
        and abs(
            page.locator("#board").bounding_box()["height"]
            - page.locator("#market").bounding_box()["height"]
        )
        <= 1,
        "a public view without a private hand lends the entire column to the board",
    )
    context.close()


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
    # a turn; every placement already creates a public log card. A placement
    # is two steps (the card pick, then the space pick that names the Agent's
    # card-play cue), so wait for both. The card with the most space picks
    # goes, so that taking its space pick back below leaves the longest list
    # of choices this turn can show.
    revision = page.evaluate("state.summary.revision")
    page.evaluate(
        """() => {
        const all = placementActions();
        const count = (p) =>
          all.filter((q) => q.arguments.card_id === p.arguments.card_id).length;
        applyPlacement(all.reduce((best, p) => (count(p) > count(best) ? p : best)));
    }"""
    )
    page.wait_for_selector(".log-size-toggle")
    page.wait_for_function(
        f"state.summary.revision === {revision + 2}"
        " && !state.busy && refreshFlight === null"
    )
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

    # Take the space pick back and expose the real long action list: the
    # picked card's space picks (about seven rows; the flat list used to hold
    # every card's placements, nearly three times as many). A 1366x768 window
    # now holds them all, so the check uses one short enough to overflow.
    page.click(".undo-row button")
    page.wait_for_function("!state.busy && refreshFlight === null")
    page.click(".action-list-toggle")
    page.set_viewport_size({"width": 1366, "height": 560})
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
                sideLeft: box('side').left, sideHeight: box('side').height,
                sideBottom: box('side').bottom,
                actionsWidth: box('side-main').width,
                decision: box('decision-info').bottom,
                history: box('action-log').top, historyLeft: box('action-log').left,
                historyWidth: box('action-log').width,
                historyHeight: box('action-log').height,
                logBottom: box('action-log').bottom,
                handTop: box('private-zone').top,
                handLeft: box('private-zone').left,
                handRight: box('private-zone').right,
                handBottom: box('private-zone').bottom,
                boardLeft: box('board').left, boardRight: box('board').right,
                boardBottom: box('board').bottom,
                marketLeft: box('market').left, marketBottom: box('market').bottom,
                viewportHeight: innerHeight,
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
            and geometry["handRight"] <= geometry["sideLeft"]
            and geometry["boardBottom"] <= geometry["handTop"],
            f"{label}: controls, history and hand do not overlap",
            geometry,
        )
        check.ok(
            abs(geometry["handLeft"] - geometry["boardLeft"]) <= 1
            and abs(geometry["handRight"] - geometry["boardRight"]) <= 1,
            f"{label}: the hand occupies only the board column",
            geometry,
        )
        check.ok(
            geometry["viewportHeight"] - 9
            <= geometry["sideBottom"]
            <= geometry["viewportHeight"]
            and abs(geometry["logBottom"] - geometry["sideBottom"]) <= 1,
            f"{label}: decisions and history reach the bottom beside the hand",
            geometry,
        )
        check.ok(
            (
                geometry["handRight"] <= geometry["marketLeft"]
                and abs(geometry["marketBottom"] - geometry["handBottom"]) <= 1
                if width > 1340
                else geometry["marketBottom"] <= geometry["handTop"]
            ),
            f"{label}: shared cards use full height beside the hand or stack above it",
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
                and abs(geometry["historyHeight"] - geometry["sideHeight"]) <= 1
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
    # The reading position is the line the reader is at: the first block of
    # the history still (partly) in view, and how far its top sits from the
    # list's top. A narrower history wraps the lines above it onto more rows
    # (the undone placement's lines, at 312px instead of 467px), and the
    # browser's own scroll anchoring then moves scrollTop to keep the reader
    # where they were, so the number scrollTop is not the position. The
    # anchoring holds a line of text, so a block whose own words re-wrap may
    # shift by less than one of its lines: the reader is still on it.
    page.evaluate(READING_ANCHOR_JS)
    page.evaluate("window.__readingAt = readingAnchor()")
    for height in (1200, 900):
        page.set_viewport_size({"width": 1920, "height": height})
        settle_layout(page)
        position = page.evaluate("""() => {
            const now = readingAnchor();
            return {
                same: window.__historyList ===
                    document.querySelector('#action-log .log-list'),
                line: now.node === window.__readingAt.node,
                moved: now.offset - window.__readingAt.offset,
                height: now.line,
                scroll: window.__historyList.scrollTop,
            };
        }""")
        check.ok(
            position["same"]
            and position["line"]
            and abs(position["moved"]) < position["height"],
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
        check_hand(base, browser)
        run(base, browser)
    check.finish()


if __name__ == "__main__":
    main()
