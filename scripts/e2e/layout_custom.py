"""E2E of the layout a player sets for themselves (user feedback 2026-10-11).

After a real game the user asked to set the table's column widths and the
order of the cards in their hand. Both live in this browser only
(static/layout.js): the widths under one localStorage key for every game,
the hand order per game and seat. Nothing reaches the server.

[A] The three column handles, in Korean and English at 1440x900 and
    1920x1080: each drags and its column follows within its clamps, the
    board never goes under its floor (--board-min) and the table never
    sticks out, widths survive a reload, a double click and Enter reset,
    the arrow keys move a handle, a language switch relabels them, and no
    request goes out. At 1920x900, where history stands beside the actions,
    widening the action column takes the history's room first.
[B] Stacked layouts (1200 and 390 px wide): the shared-card handle is gone,
    the other two still sit between side-by-side columns, the stored widths
    apply and nothing overflows the page; folding every shared-card column
    (`c`) hides that handle and gives the board its room back.
[C] The hand's own order: a card dragged along the hand stays there through
    a redraw, a foreign update, a newly drawn card (it comes after the known
    ones) and a reload; a plain click still picks the card for the staged
    Agent turn; Alt+Arrow moves a card; "Reset order" shows only with an
    order of the player's own and restores the server's; the Intrigue strip
    reorders too; dragging sends nothing.
[D] A replay review and a watched game show the server's order and do not
    drag, whatever the browser has stored.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path

from common import (
    REPO,
    SERVER_LOG_COPY,
    Check,
    ServerProcess,
    chrome,
    now,
    open_context,
)
from open_mode import create_game, settled

check = Check()

COLUMNS_KEY = "dune.layout.columns.v1"
DEFAULTS = {"seats": 210, "actions": 340}
NARROW_DEFAULTS = {"seats": 200, "actions": 300}
CLAMPS = {"seats": (160, 420), "actions": (280, 640), "market": (150, 420)}
SPLITTERS = {
    "seats": "#split-seats",
    "actions": "#split-actions",
    "market": "#split-market",
}
# Which way a drag to the right moves each column's width.
GROWS = {"seats": 1, "actions": -1, "market": -1}

GEOMETRY = """() => {
    const rect = (id) => document.getElementById(id).getBoundingClientRect();
    const shown = (id) => {
        const node = document.getElementById(id);
        const box = node.getBoundingClientRect();
        return getComputedStyle(node).display !== 'none' && box.width > 0
            && box.height > 0;
    };
    const middle = (id) => { const box = rect(id); return box.left + box.width / 2; };
    const table = document.getElementById('table');
    const main = document.querySelector('main');
    const inner = rect('table').right
        - parseFloat(getComputedStyle(table).paddingRight);
    return {
        seats: rect('seats').width,
        market: rect('market').width,
        actions: parseFloat(
            getComputedStyle(table).getPropertyValue('--actions-width')),
        board: rect('board').width,
        floor: parseFloat(getComputedStyle(document.getElementById('game-screen'))
            .getPropertyValue('--board-min')),
        logBeside: table.classList.contains('log-beside'),
        stored: localStorage.getItem('dune.layout.columns.v1'),
        pageWide: document.documentElement.scrollWidth > innerWidth + 1,
        mainScrolls: main.scrollWidth > main.clientWidth + 1,
        mainInside: main.getBoundingClientRect().right <= innerWidth + 1,
        sticksOut: rect('side').right - inner,
        shown: {
            seats: shown('split-seats'),
            actions: shown('split-actions'),
            market: shown('split-market'),
        },
        between: {
            seats: rect('seats').right - 0.5 <= middle('split-seats')
                && middle('split-seats') <= rect('center').left + 0.5,
            actions: rect('center').right - 0.5 <= middle('split-actions')
                && middle('split-actions') <= rect('side').left + 0.5,
            market: rect('board').right - 0.5 <= middle('split-market')
                && middle('split-market') <= rect('market').left + 0.5,
        },
        handInside: rect('private-zone').right <= rect('board').right + 0.5,
        marketBelow: rect('market').top >= rect('board').bottom - 0.5,
    };
}"""


def settle(page) -> None:
    page.evaluate(
        """async () => {
            await new Promise(requestAnimationFrame);
            await new Promise(requestAnimationFrame);
        }"""
    )


def geometry(page) -> dict:
    settle(page)
    return page.evaluate(GEOMETRY)


def stored_widths(page) -> dict:
    raw = page.evaluate(f"localStorage.getItem('{COLUMNS_KEY}')")
    return json.loads(raw) if raw else {}


def clear_widths(page) -> None:
    page.evaluate(
        f"localStorage.removeItem('{COLUMNS_KEY}'); loadColumnWidths(); fitActionLog()"
    )
    settle(page)


def game_requests(rec, since: float) -> list[str]:
    """Requests to the game API made since `since` (card pictures are not)."""
    return [
        text
        for at, kind, text in rec.events
        if at >= since and kind == "req" and ("games/" in text or "saves" in text)
    ]


def drag(page, selector: str, dx: float, dy: float = 0.0, steps: int = 8) -> None:
    box = page.locator(selector).bounding_box()
    x = box["x"] + box["width"] / 2
    y = box["y"] + min(box["height"] / 2, 300)
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + dx, y + dy, steps=steps)
    page.mouse.up()
    settle(page)


def near(a: float, b: float, slack: float = 1.0) -> bool:
    return abs(a - b) <= slack


def set_language(page, language: str) -> None:
    if page.evaluate("TERM_LANGUAGE") != language:
        page.click("#language-toggle")
        page.wait_for_function(f"TERM_LANGUAGE === '{language}'")
        settle(page)


def to_agent_turn(page) -> list[dict]:
    """Play first legal actions until seat 0 is offered placements."""
    for _ in range(200):
        assert settled(page)
        placements = page.evaluate(
            "placementActions().map((a) => ({card: a.arguments.card_id,"
            " space: a.arguments.space_id}))"
        )
        if placements or page.evaluate("state.summary.finished"):
            return placements
        if page.evaluate("state.actions && state.actions.actions.length > 0"):
            page.evaluate("applyAction(0)")
        elif page.evaluate("state.summary.confirmation === state.viewSeat"):
            page.evaluate("confirmTurn()")
        else:
            time.sleep(0.05)
    return []


# ---------- [A] the column handles ----------


def check_bounds(page, label: str, name: str, shape: dict) -> None:
    low, high = CLAMPS[name]
    width = shape[name]
    check.ok(
        low - 1 <= width <= high + 1
        and shape["board"] >= shape["floor"] - 0.5
        and shape["sticksOut"] <= 1
        and not shape["pageWide"],
        f"{label}: {name} {width:.0f}px stays within {low}-{high}px, the board"
        " keeps its floor and nothing sticks out",
        shape,
    )


def columns_at(page, rec, viewport: dict, language: str) -> None:
    label = f"{language} {viewport['width']}x{viewport['height']}"
    print(f"[A] column handles, {label}")
    page.set_viewport_size(viewport)
    set_language(page, language)
    clear_widths(page)
    start = geometry(page)
    check.ok(
        near(start["seats"], DEFAULTS["seats"])
        and near(start["actions"], DEFAULTS["actions"])
        and start["market"] <= 190.5
        and start["stored"] is None,
        f"{label}: unset widths are the defaults",
        start,
    )
    check.ok(
        all(start["shown"].values()) and all(start["between"].values()),
        f"{label}: three handles, each in the gap between its two columns",
        start,
    )
    names = page.evaluate(
        """() => ['split-seats', 'split-actions', 'split-market'].map((id) => {
            const node = document.getElementById(id);
            return [node.getAttribute('aria-label'), node.title,
                node.getAttribute('role'), node.tabIndex];
        })"""
    )
    expected = page.evaluate(
        """() => [['html.split_seats_aria'], ['html.split_actions_aria'],
            ['html.split_market_aria']].map(([key]) =>
            [t(key), t('html.split_title'), 'separator', 0])"""
    )
    check.ok(
        names == expected, f"{label}: the handles are named in this language", names
    )

    since = now()
    moves = {"seats": 60, "actions": 50, "market": 40}
    for name, grow in moves.items():
        before = geometry(page)[name]
        drag(page, SPLITTERS[name], GROWS[name] * grow)
        shape = geometry(page)
        check.ok(
            near(shape[name], before + grow)
            and near(stored_widths(page).get(name, -1), before + grow),
            f"{label}: dragging the {name} handle by {grow}px follows the pointer"
            " and is stored",
            (before, shape[name], stored_widths(page)),
        )
        check_bounds(page, label, name, shape)
    check.ok(
        not game_requests(rec, since),
        f"{label}: dragging the handles sends nothing",
        game_requests(rec, since),
    )

    kept = {name: round(geometry(page)[name]) for name in moves}
    page.reload()
    page.wait_for_function("state.view !== null && refreshFlight === null")
    after = geometry(page)
    check.ok(
        all(near(after[name], kept[name]) for name in kept),
        f"{label}: the widths survive a reload",
        (kept, after),
    )

    for name in moves:
        low, high = CLAMPS[name]
        drag(page, SPLITTERS[name], GROWS[name] * 900)
        wide = geometry(page)
        check_bounds(page, label, name, wide)
        check.ok(
            near(wide[name], high) or wide["board"] <= wide["floor"] + 2,
            f"{label}: {name} grows to {high}px or until the board reaches its floor",
            wide,
        )
        drag(page, SPLITTERS[name], -GROWS[name] * 900)
        narrow = geometry(page)
        check.ok(near(narrow[name], low), f"{label}: {name} shrinks to {low}px", narrow)
        check_bounds(page, label, name, narrow)

    for name in moves:
        page.dblclick(SPLITTERS[name])
    settle(page)
    reset = geometry(page)
    check.ok(
        near(reset["seats"], DEFAULTS["seats"])
        and near(reset["actions"], DEFAULTS["actions"])
        and reset["market"] <= 190.5
        and reset["stored"] is None,
        f"{label}: a double click puts each column back to its default",
        reset,
    )

    print(f"    keyboard, {label}")
    for name in moves:
        page.focus(SPLITTERS[name])
        base = geometry(page)[name]
        page.keyboard.press("ArrowRight")
        right = geometry(page)[name]
        page.keyboard.press("Shift+ArrowLeft")
        left = geometry(page)[name]
        check.ok(
            near(right, base + 10 * GROWS[name])
            and near(left, right - 40 * GROWS[name]),
            f"{label}: arrows move the {name} handle by 10px, with Shift 40px",
            (base, right, left),
        )
        check.ok(
            page.evaluate(
                f"Number(document.querySelector('{SPLITTERS[name]}')"
                ".getAttribute('aria-valuenow'))"
            )
            == round(left),
            f"{label}: the {name} handle reports its width",
        )
        page.keyboard.press("Enter")
        back = geometry(page)
        check.ok(
            name not in stored_widths(page)
            and (
                back["market"] <= 190.5
                if name == "market"
                else near(back[name], DEFAULTS[name])
            ),
            f"{label}: Enter puts the {name} column back to its default",
            back,
        )
    page.evaluate("document.activeElement.blur()")


def history_beside(page, rec) -> None:
    """History beside the actions gives its room up first."""
    print("[A] history beside the actions, 1920x900")
    page.set_viewport_size({"width": 1920, "height": 900})
    clear_widths(page)
    start = geometry(page)
    if not start["logBeside"]:
        print("  .. history is not beside the actions here; skipped")
        return
    drag(page, SPLITTERS["actions"], -900)
    shape = geometry(page)
    check_bounds(page, "1920x900 history beside", "actions", shape)
    check.ok(
        near(shape["actions"], CLAMPS["actions"][1])
        or shape["board"] <= shape["floor"] + 2,
        "the action column takes the room history had, up to its clamp",
        (start, shape),
    )
    clear_widths(page)


# ---------- [B] stacked layouts ----------


def stacked(page) -> None:
    for viewport in ({"width": 1200, "height": 800}, {"width": 390, "height": 844}):
        label = f"{viewport['width']}x{viewport['height']}"
        print(f"[B] stacked layout, {label}")
        page.set_viewport_size(viewport)
        clear_widths(page)
        plain = geometry(page)
        check.ok(
            near(plain["seats"], NARROW_DEFAULTS["seats"])
            and near(plain["actions"], NARROW_DEFAULTS["actions"]),
            f"{label}: unset widths are the narrow defaults",
            plain,
        )
        page.evaluate(
            f"""localStorage.setItem('{COLUMNS_KEY}',
                JSON.stringify({{seats: 300, actions: 500, market: 300}}));
            loadColumnWidths(); fitActionLog();"""
        )
        shape = geometry(page)
        check.ok(
            not shape["shown"]["market"]
            and shape["shown"]["seats"]
            and shape["shown"]["actions"]
            and shape["between"]["seats"]
            and shape["between"]["actions"],
            f"{label}: the shared-card handle is gone, the other two sit in their gaps",
            shape,
        )
        check.ok(
            near(shape["seats"], 300) and near(shape["actions"], 500),
            f"{label}: the stored side widths apply",
            shape,
        )
        # Below 600px the header's own buttons are wider than the window
        # already (narrow.py checks the header from 600px up); the table
        # scrolls inside `main` and must not widen the page beyond that.
        check.ok(
            shape["board"] >= shape["floor"] - 0.5
            and shape["marketBelow"]
            and shape["handInside"]
            and shape["mainInside"]
            and (viewport["width"] < 600 or not shape["pageWide"])
            and shape["sticksOut"] <= 1,
            f"{label}: the board keeps its floor, the shared cards stay under it,"
            " and the table never widens the page",
            shape,
        )
        check.ok(
            shape["mainScrolls"],
            f"{label}: the table scrolls sideways under the header instead",
            shape,
        )
        drag(page, SPLITTERS["seats"], -40)
        check.ok(
            near(geometry(page)["seats"], 260),
            f"{label}: the seat handle still drags here",
            geometry(page)["seats"],
        )
        clear_widths(page)

    print("[B] every shared-card column folded")
    page.set_viewport_size({"width": 1440, "height": 900})
    clear_widths(page)
    drag(page, SPLITTERS["market"], -100)
    sized = geometry(page)
    page.evaluate("document.activeElement.blur()")
    page.keyboard.press("c")
    folded = geometry(page)
    check.ok(
        not folded["shown"]["market"]
        and folded["market"] < sized["market"] - 50
        and folded["board"] > sized["board"] + 50,
        "folding every column (c) hides the handle and gives the board the room",
        (sized, folded),
    )
    page.keyboard.press("c")
    unfolded = geometry(page)
    check.ok(
        unfolded["shown"]["market"] and near(unfolded["market"], sized["market"]),
        "unfolded, the column has its set width and handle back",
        unfolded,
    )
    clear_widths(page)


# ---------- [C] the hand's own order ----------

HAND_IDS = (
    "() => [...document.querySelectorAll('.hand-cards .vcard')]"
    ".map((n) => n.dataset.instance)"
)
INTRIGUE_IDS = (
    "() => [...document.querySelectorAll('.intrigue-cards .vcard')]"
    ".map((n) => n.dataset.instance)"
)


def order_key(page) -> str:
    return page.evaluate("handOrderKey()")


def stored_order(page) -> dict | None:
    raw = page.evaluate("(key) => localStorage.getItem(key)", order_key(page))
    return json.loads(raw) if raw else None


def reset_shown(page) -> bool:
    return page.locator("#private-zone .hand-order-reset").count() == 1


def drag_card(page, card_selector: str, target_x: float, inspect: str | None = None):
    box = page.locator(card_selector).bounding_box()
    x = box["x"] + box["width"] / 2
    y = box["y"] + box["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(target_x, y, steps=10)
    seen = page.evaluate(inspect) if inspect else None
    page.mouse.up()
    settle(page)
    return seen


MID_DRAG = """() => ({
    marker: document.querySelectorAll('.hand-cards .hand-drop-marker').length,
    dragging: document.querySelectorAll('.hand-cards .vcard.dragging').length,
    pick: state.pick,
})"""


def hand_order(page, rec) -> None:
    print("[C] the hand's own order")
    page.set_viewport_size({"width": 1440, "height": 900})
    set_language(page, "ko")
    server_ids = page.evaluate("state.view.private.hand.slice()")
    check.ok(len(server_ids) >= 3, "the hand has cards to order", server_ids)
    check.ok(
        page.evaluate(HAND_IDS) == server_ids
        and not reset_shown(page)
        and page.locator(".hand-cards.reorderable").count() == 1,
        "the hand starts in the server's order, with no reset button",
    )

    since = now()
    last = page.locator(".hand-cards .vcard").last.bounding_box()
    mid = drag_card(
        page,
        f".hand-cards .vcard[data-instance='{server_ids[0]}']",
        last["x"] + last["width"] + 4,
        MID_DRAG,
    )
    custom = server_ids[1:] + server_ids[:1]
    check.ok(
        mid["marker"] == 1 and mid["dragging"] == 1 and mid["pick"] is None,
        "while dragging, the card is marked and a drop marker shows where it lands",
        mid,
    )
    check.ok(page.evaluate(HAND_IDS) == custom, "the dragged card lands at the end")
    check.ok(
        page.evaluate("state.pick") is None and not page.evaluate("popoverPinned"),
        "the drag picked nothing and pinned no popover",
    )
    check.ok(
        stored_order(page) == {"hand": custom}
        and order_key(page) == f"dune.handOrder.v1.{page.evaluate('state.gameId')}.0",
        "the order is stored for this game and seat",
        (order_key(page), stored_order(page)),
    )
    check.ok(reset_shown(page), "an order of the player's own shows the reset button")
    check.ok(
        not game_requests(rec, since),
        "dragging a card sends nothing",
        game_requests(rec, since),
    )

    page.evaluate("render()")
    check.ok(page.evaluate(HAND_IDS) == custom, "a redraw keeps the order")
    page.evaluate("render({foreign: true})")
    check.ok(page.evaluate(HAND_IDS) == custom, "a foreign redraw keeps the order")
    page.evaluate("refresh(null, {foreign: true})")
    assert settled(page)
    check.ok(page.evaluate(HAND_IDS) == custom, "a foreign update keeps the order")

    # Two cards the store has never seen, first in the server's list: they
    # come after the known ones, in the server's order.
    drawn = page.evaluate(
        """() => {
            const own = state.view.private;
            const fresh = [own.hand[0].replace(/:\\d+$/, ':97'),
                own.hand[1].replace(/:\\d+$/, ':98')];
            own.hand.unshift(...fresh);
            render({foreign: true});
            return fresh;
        }"""
    )
    check.ok(
        page.evaluate(HAND_IDS) == custom + drawn,
        "newly drawn cards come after the ordered ones, in the server's order",
        page.evaluate(HAND_IDS),
    )
    page.evaluate(
        "(fresh) => { const own = state.view.private;"
        " own.hand = own.hand.filter((id) => !fresh.includes(id)); render(); }",
        drawn,
    )
    check.ok(
        page.evaluate(HAND_IDS) == custom and stored_order(page) == {"hand": custom},
        "they leave again without touching the stored order",
    )

    page.reload()
    page.wait_for_function("state.view !== null && refreshFlight === null")
    settle(page)
    check.ok(
        page.evaluate(HAND_IDS) == custom and reset_shown(page),
        "the order survives a reload",
        page.evaluate(HAND_IDS),
    )

    print("[C] a click is still a click")
    legal = page.evaluate(
        "[...document.querySelectorAll('.hand-cards .vcard.legal')]"
        ".map((n) => n.dataset.instance)"
    )
    check.ok(bool(legal), "a hand card is playable", legal)
    if legal:
        posts = rec.count("POST", "/actions")
        page.click(f".hand-cards .vcard[data-instance='{legal[0]}']")
        check.ok(
            page.evaluate("state.pick && state.pick.cardId") == legal[0]
            and page.evaluate(HAND_IDS) == custom
            and rec.count("POST", "/actions") == posts,
            "a plain click picks the card for the Agent turn and keeps the order",
        )
        page.keyboard.press("Escape")
        card = page.locator(f".hand-cards .vcard[data-instance='{legal[0]}']")
        box = card.bounding_box()
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + 3, y + 1, steps=2)
        page.mouse.up()
        check.ok(
            page.evaluate("state.pick && state.pick.cardId") == legal[0]
            and page.evaluate(HAND_IDS) == custom,
            "a click that wobbles under the drag threshold still picks the card",
        )
        page.keyboard.press("Escape")

    print("[C] Alt+Arrow")
    since = now()
    first = custom[0]
    page.focus(f".hand-cards .vcard[data-instance='{first}']")
    page.keyboard.press("Alt+ArrowRight")
    moved = custom[1:2] + custom[:1] + custom[2:]
    check.ok(
        page.evaluate(HAND_IDS) == moved
        and page.evaluate("document.activeElement.dataset.instance") == first
        and stored_order(page) == {"hand": moved},
        "Alt+Right moves the focused card one place and keeps its focus",
        page.evaluate(HAND_IDS),
    )
    page.keyboard.press("Alt+ArrowLeft")
    check.ok(
        page.evaluate(HAND_IDS) == custom
        and page.evaluate("document.activeElement.dataset.instance") == first,
        "Alt+Left moves it back",
    )
    check.ok(
        page.evaluate("state.pick") is None,
        "moving a card with the keyboard picks nothing",
    )
    check.ok(
        not game_requests(rec, since), "moving a card with the keyboard sends nothing"
    )

    print("[C] the Intrigue cards")
    # Wide enough for the hand and three Intrigue cards side by side: at
    # 1440px the Intrigue strip shrinks to one card and scrolls.
    page.set_viewport_size({"width": 1920, "height": 1080})
    fakes = page.evaluate(
        """() => {
            const ids = Object.keys(state.catalog.intrigue).slice(0, 3)
                .map((id, i) => `intrigue:${id}:${90 + i}`);
            window.__intrigue = state.view.private.intrigue_cards.slice();
            state.view.private.intrigue_cards = ids;
            render();
            return ids;
        }"""
    )
    target = page.locator(".intrigue-cards .vcard").first.bounding_box()
    drag_card(
        page, f".intrigue-cards .vcard[data-instance='{fakes[2]}']", target["x"] + 2
    )
    check.ok(
        page.evaluate(INTRIGUE_IDS) == [fakes[2], fakes[0], fakes[1]]
        and (stored_order(page) or {}).get("intrigue") == [fakes[2], fakes[0], fakes[1]]
        and page.evaluate(HAND_IDS) == custom,
        "an Intrigue card reorders within its own strip",
        page.evaluate(INTRIGUE_IDS),
    )
    page.evaluate("state.view.private.intrigue_cards = window.__intrigue; render()")
    page.set_viewport_size({"width": 1440, "height": 900})

    print("[C] Reset order")
    set_language(page, "en")
    check.ok(
        page.inner_text("#private-zone .hand-order-reset") == "Reset order",
        "the reset button speaks English",
    )
    set_language(page, "ko")
    check.ok(
        page.inner_text("#private-zone .hand-order-reset") == "순서 되돌리기",
        "and Korean",
    )
    page.click("#private-zone .hand-order-reset")
    settle(page)
    check.ok(
        page.evaluate(HAND_IDS) == page.evaluate("state.view.private.hand")
        and not reset_shown(page)
        and stored_order(page) is None,
        "Reset order brings back the server's order and forgets the stored one",
        page.evaluate(HAND_IDS),
    )
    # Dragging a card back where it was leaves nothing stored.
    ids = page.evaluate(HAND_IDS)
    second = page.locator(".hand-cards .vcard").nth(1).bounding_box()
    drag_card(
        page,
        f".hand-cards .vcard[data-instance='{ids[0]}']",
        second["x"] + 4,
    )
    check.ok(
        page.evaluate(HAND_IDS) == ids
        and stored_order(page) is None
        and not reset_shown(page),
        "a card dropped where it was leaves the server's order and stores nothing",
    )


# ---------- [D] review and watching ----------


def review(browser, saves: str, base: str, found: dict) -> None:
    print("[D] a replay review shows the server's order and does not drag")
    context, page, rec = open_context(browser, "review", {"width": 1440, "height": 900})
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    loaded = page.evaluate(
        "(id) => api(`/saves/${id}/load`, {method: 'POST'})", found["finished"]
    )
    page.evaluate("(id) => openGame(id)", loaded["game_id"])
    page.wait_for_function(
        "(id) => state.gameId === id && state.view !== null && refreshFlight === null",
        arg=loaded["game_id"],
    )
    total = page.evaluate(
        "async () => { await enterReview(0, {cursor: 0}); stopPlayback();"
        " return state.review.meta.step_count; }"
    )
    cursor = None
    for step in range(total // 4, total, max(1, total // 40)):
        page.evaluate("async (c) => { await reviewGoto(c); }", step)
        if page.evaluate("(state.view.private.hand || []).length") >= 3:
            cursor = step
            break
    check.ok(
        cursor is not None, "a reviewed step where seat 0 holds three cards", total
    )
    if cursor is None:
        context.close()
        return
    server_ids = page.evaluate("state.view.private.hand.slice()")
    key = f"dune.handOrder.v1.{loaded['game_id']}.0"
    written = {"hand": list(reversed(server_ids))}
    page.evaluate(
        "([key, value]) => { localStorage.setItem(key, value); render(); }",
        [key, json.dumps(written)],
    )
    settle(page)
    check.ok(
        page.evaluate("mySeats().includes(0) && state.review !== null"),
        "the reviewed seat is this browser's own",
    )
    check.ok(
        page.evaluate(HAND_IDS) == server_ids
        and page.locator(".hand-cards.reorderable").count() == 0
        and not reset_shown(page),
        "the review shows the server's order whatever is stored",
        page.evaluate(HAND_IDS),
    )
    last = page.locator(".hand-cards .vcard").last.bounding_box()
    since = now()
    mid = drag_card(
        page,
        f".hand-cards .vcard[data-instance='{server_ids[0]}']",
        last["x"] + last["width"] + 4,
        MID_DRAG,
    )
    check.ok(
        mid["marker"] == 0
        and mid["dragging"] == 0
        and page.evaluate(HAND_IDS) == server_ids
        and json.loads(page.evaluate("(key) => localStorage.getItem(key)", key))
        == written,
        "a drag in the review moves nothing and stores nothing",
        mid,
    )
    check.ok(
        not [r for r in game_requests(rec, since) if "/review" not in r],
        "and makes no game request",
        game_requests(rec, since),
    )
    context.close()

    print("[D] a watched game (AI seats only) does not drag either")
    context, page, _rec = open_context(browser, "watch", {"width": 1440, "height": 900})
    create_game(page, base, kinds=["heuristic"] * 4)
    page.wait_for_function("state.review !== null")
    page.evaluate("stopPlayback()")
    found_hand = False
    for _ in range(60):
        page.evaluate("async () => { await reviewGoto(state.review.cursor + 5); }")
        if page.evaluate("(state.view.private.hand || []).length") >= 2:
            found_hand = True
            break
    check.ok(found_hand, "the watched seat holds cards at some step")
    if found_hand:
        ids = page.evaluate("state.view.private.hand.slice()")
        page.evaluate(
            "(ids) => { localStorage.setItem(handOrderKey(),"
            " JSON.stringify({hand: ids.slice().reverse()})); render(); }",
            ids,
        )
        check.ok(
            page.evaluate(HAND_IDS) == ids
            and page.locator(".hand-cards.reorderable").count() == 0
            and not reset_shown(page),
            "a watched game shows the server's order and offers no reordering",
        )
    context.close()


def finished_save(saves: str) -> dict:
    found: dict = json.loads(
        subprocess.run(
            [
                str(REPO / ".venv/bin/python"),
                str(Path(__file__).parent / "fixtures/finished_human_save.py"),
                saves,
            ],
            cwd=REPO,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    return found


def main() -> None:
    saves = tempfile.mkdtemp(prefix="dune-layout-e2e-")
    found = finished_save(saves)
    process = ServerProcess(saves=saves).start()
    try:
        with chrome() as browser:
            context, page, rec = open_context(
                browser, "layout", {"width": 1440, "height": 900}
            )
            create_game(page, process.base, humans=(0,))
            placements = to_agent_turn(page)
            check.ok(bool(placements), "seat 0 reaches an Agent turn")
            hand_order(page, rec)
            # A move fills the history, so that it can stand beside the actions.
            page.evaluate("clearPick(); applyAction(0)")
            assert settled(page)
            for viewport in (
                {"width": 1440, "height": 900},
                {"width": 1920, "height": 1080},
            ):
                for language in ("ko", "en"):
                    columns_at(page, rec, viewport, language)
            set_language(page, "ko")
            history_beside(page, rec)
            stacked(page)
            context.close()
            review(browser, saves, process.base, found)
        log = process.log_path.read_text()
        errors = [
            line for line in log.splitlines() if "ERROR" in line or "Traceback" in line
        ]
        check.ok(not errors, f"no server errors (see {SERVER_LOG_COPY})", errors[:3])
        SERVER_LOG_COPY.write_text(log)
    finally:
        process.stop()
    check.finish()


if __name__ == "__main__":
    main()
