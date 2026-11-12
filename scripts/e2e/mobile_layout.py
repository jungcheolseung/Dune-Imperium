"""E2E of the phone layout (docs/mobile-ui-plan.md M1, user decision 2026-11-06).

Below 600px wide the three-column table never fit: at 375px it kept its
1012px floor, so the decisions sat 640px off the screen, and the header's
buttons pushed the page itself sideways (survey of 2026-11-06). There the
table is now one column (phone.css, phone.js): one view at a time (board,
hand, players, shared cards or log), the decision panel under it, a tab bar
at the bottom, and the header's buttons folded into a menu.

Every page here is a phone's Chrome (common.open_phone_context: mobile
viewport rules, touch, no mouse) at one of common.PHONE_SIZES, and is
touched only with tap(). Checked:

A. A whole game with every expansion on Uprising (the setup screen's own
   boxes plus the original cards, Rise of Ix and Arrakeen Scouts), seat 0
   human, three heuristic seats, at 390x844. At every decision of the
   human seat: the page does not scroll either way; the decision panel lies
   inside the screen, above the tab bar, the tab bar inside the screen; no
   button of the decision panel sticks out sideways; and the first button
   the seat can press is on screen without scrolling. The seat takes its
   first legal action (applyAction; mobile_turn.py plays by taps).
B. The same at 360x780 and 412x915 for the first decisions of a game with
   the setup screen's boxes, and at 360x780 for the original board with
   Rise of Ix and Arrakeen Scouts.
C. The tabs: each shows its view and no other, inside the space between
   the header and the decision panel, and marks itself pressed.
D. The header menu: closed, only the round line and the menu button show;
   open, every header button the game shows is there, at least 44px tall
   and inside the screen, and the page still does not scroll; a tap
   elsewhere closes it, and so does a choice from it (the language).
E. With no hand to show (the zone hidden, as for a remote spectator): no
   hand tab, and a hand view left open shows the board.
F. At 600x800 and 1000x900 with a mouse, none of it: no tab bar, no menu
   button, the players and the decisions beside the board (narrow.py checks
   the rest of those widths).
G. A remote room's link opened on a phone: the name field and the place
   buttons are 44px tall and on screen, the page does not scroll, and a tap
   on a place reaches the table in the phone layout.
H. A watched game (four AI seats) at 360x780: the review bar sits in the
   decision panel, its controls finger-sized and on screen, and with
   playback stopped a tap on ▶ moves the review by exactly one step.

E2E_SHOTS_DIR optionally names where the screenshots go (mobile_*.png).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from common import (
    EVERY_EXPANSION,
    ONE_HUMAN,
    ORIGINAL_EXPANSIONS,
    PHONE_SEED,
    PHONE_SIZES,
    REVIEW_LANDING,
    SERVER_LOG_COPY,
    Check,
    chrome,
    client_state,
    create_by_touch,
    open_context,
    open_phone_context,
    server,
)
from open_mode import settled

check = Check()
SHOTS = Path(os.environ["E2E_SHOTS_DIR"]) if os.environ.get("E2E_SHOTS_DIR") else None
HEADER_BUTTONS = (
    "open-help",
    "language-toggle",
    "open-lobby",
    "ai-pace",
    "save-game",
    "leave-game",
)
MENU_OPEN = "document.querySelector('header').classList.contains('menu-open')"
VIEWS = {
    "board": "#board",
    "hand": "#private-zone",
    "seats": "#seats",
    "market": "#market",
    "log": "#side-log",
}

LAYOUT = r"""() => {
  const vw = innerWidth, vh = innerHeight;
  const box = (e) => e.getBoundingClientRect();
  const shown = (e) => {
    const r = box(e);
    return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden';
  };
  const sheet = box(document.getElementById('side-main'));
  const tabs = box(document.getElementById('phone-tabs'));
  const buttons = [...document.querySelectorAll('#decision-banner button')]
    .filter(shown);
  const cut = buttons
    .filter((b) => { const r = box(b); return r.left < -1 || r.right > vw + 1; })
    .map((b) => b.textContent.trim().slice(0, 40));
  const first = buttons.find((b) => !b.disabled);
  const r = first && box(first);
  return {
    vw, vh,
    doc: [document.documentElement.scrollWidth, document.documentElement.scrollHeight],
    sheet: [sheet.left, sheet.top, sheet.right, sheet.bottom],
    tabs: [tabs.left, tabs.top, tabs.right, tabs.bottom],
    cut,
    first: r
      ? [r.left, r.top, r.right, r.bottom, first.textContent.trim().slice(0, 30)]
      : null,
  };
}"""


def layout_faults(m: dict) -> list[str]:
    faults = []
    vw, vh = m["vw"], m["vh"]
    if m["doc"][0] > vw or m["doc"][1] > vh:
        faults.append(f"page scrolls {m['doc']} in {vw}x{vh}")
    left, top, right, bottom = m["sheet"]
    if left < -0.5 or right > vw + 0.5 or top >= vh or bottom > m["tabs"][1] + 0.5:
        faults.append(f"decision panel {m['sheet']} not on screen above the tabs")
    t_left, t_top, t_right, t_bottom = m["tabs"]
    if t_left < -0.5 or t_right > vw + 0.5 or t_bottom > vh + 0.5 or t_top <= 0:
        faults.append(f"tab bar {m['tabs']} not inside the screen")
    if m["cut"]:
        faults.append(f"buttons cut at the side: {m['cut'][:3]}")
    if m["first"]:
        f_left, f_top, f_right, f_bottom, label = m["first"]
        outside = f_left < -0.5 or f_right > vw + 0.5
        if f_top < top - 1 or f_bottom > bottom + 1 or outside:
            faults.append(f"first button {label!r} {m['first'][:4]} not on screen")
    return faults


def shoot(page, name: str) -> None:
    if SHOTS:
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"mobile_{name}.png"))


def play_checking(page, what: str, limit: int | None = None) -> int:
    """Play seat 0's first legal actions, checking the layout at each of its
    decisions; returns how many decisions were checked."""
    checked, faults, kinds = 0, [], set()
    for _ in range(4000):
        assert settled(page, 30), "every step settles"
        snap = client_state(page)
        if snap["finished"] or (limit is not None and checked >= limit):
            break
        mine = snap["owner"] == snap["viewSeat"] and snap["nActions"]
        confirm = (
            snap["confirmation"] is not None
            and snap["confirmation"] == snap["viewSeat"]
        )
        if mine or confirm:
            checked += 1
            found = layout_faults(page.evaluate(LAYOUT))
            if found:
                faults.append((checked, snap["kind"], found))
            if snap["kind"] not in kinds:
                kinds.add(snap["kind"])
                shoot(page, f"{what}_{snap['kind'] or 'confirm'}")
        if confirm:
            page.evaluate("confirmTurn()")
        elif snap["nActions"]:
            page.evaluate("applyAction(0)")
        else:
            time.sleep(0.05)
    check.ok(
        not faults,
        f"{what}: the layout holds at all {checked} decisions ({len(kinds)} kinds)",
        faults[:4],
    )
    return checked


def check_whole_game(base: str, browser) -> None:
    print("[A] a whole game, every expansion, 390x844")
    _, page, _ = open_phone_context(browser, "phone-390", PHONE_SIZES[1])
    create_by_touch(page, base, ONE_HUMAN, EVERY_EXPANSION)
    checked = play_checking(page, "every_expansion")
    check.ok(checked > 50, "the human seat had decisions to check", checked)
    check.ok(client_state(page)["finished"], "the game finished")
    m = page.evaluate(LAYOUT)
    check.ok(
        m["doc"][0] <= m["vw"] and m["doc"][1] <= m["vh"],
        "the finished game does not scroll the page",
        m["doc"],
    )
    shoot(page, "every_expansion_end")
    page.context.close()


def check_other_sizes(base: str, browser) -> None:
    print("[B] the first decisions at 360x780 and 412x915, and the original board")
    for size in (PHONE_SIZES[0], PHONE_SIZES[2]):
        _, page, _ = open_phone_context(browser, f"phone-{size['width']}", size)
        create_by_touch(page, base, ONE_HUMAN)
        play_checking(page, f"setup_boxes_{size['width']}", limit=40)
        page.context.close()
    _, page, _ = open_phone_context(browser, "phone-original", PHONE_SIZES[0])
    create_by_touch(
        page, base, ONE_HUMAN, ORIGINAL_EXPANSIONS, base_game="imperium"
    )
    play_checking(page, "original_360", limit=40)
    page.context.close()


def view_shape(page) -> dict:
    return page.evaluate(
        """(views) => {
          const shown = {};
          for (const [view, sel] of Object.entries(views)) {
            const e = document.querySelector(sel);
            const r = e.getBoundingClientRect();
            shown[view] = r.width > 0 && r.height > 0
              ? [r.left, r.top, r.right, r.bottom] : null;
          }
          const header = document.querySelector('header').getBoundingClientRect();
          const sheet = document.getElementById('side-main').getBoundingClientRect();
          return {
            view: document.getElementById('game-screen').dataset.phoneView,
            shown,
            pressed: [...document.querySelectorAll('#phone-tabs [data-view]')]
              .filter((b) => b.getAttribute('aria-pressed') === 'true')
              .map((b) => b.dataset.view),
            room: [header.bottom, sheet.top],
            vw: innerWidth,
          };
        }""",
        VIEWS,
    )


def check_tabs_and_menu(base: str, browser) -> None:
    print("[C] the tabs, [D] the header menu")
    _, page, _ = open_phone_context(browser, "phone-tabs", PHONE_SIZES[1])
    create_by_touch(page, base, ONE_HUMAN)
    play_checking(page, "tabs_game", limit=3)
    for view in VIEWS:
        page.tap(f"#phone-tabs [data-view='{view}']")
        shape = view_shape(page)
        visible = [name for name, rect in shape["shown"].items() if rect]
        check.ok(
            shape["view"] == view and visible == [view],
            f"the {view} tab shows the {view} alone",
            (shape["view"], visible),
        )
        check.ok(
            shape["pressed"] == [view],
            f"the {view} tab is the one pressed",
            shape["pressed"],
        )
        rect = shape["shown"].get(view)
        top, bottom = shape["room"]
        check.ok(
            rect is not None
            and rect[1] >= top - 0.5
            and rect[3] <= bottom + 0.5
            and rect[0] >= -0.5
            and rect[2] <= shape["vw"] + 0.5,
            f"the {view} view lies between the header and the decisions",
            (rect, shape["room"]),
        )
        shoot(page, f"view_{view}")
    page.tap("#phone-tabs [data-view='board']")

    closed = page.evaluate(
        """(ids) => ids.filter((id) => {
          const e = document.getElementById(id);
          return getComputedStyle(e).display !== 'none';
        })""",
        list(HEADER_BUTTONS),
    )
    check.ok(closed == [], "closed, the menu's buttons are not in the header", closed)
    check.ok(page.is_visible("#phone-menu"), "the menu button is in the header")
    expected = page.evaluate(
        "(ids) => ids.filter((id) => !document.getElementById(id).hidden)",
        list(HEADER_BUTTONS),
    )
    page.tap("#phone-menu")
    menu = page.evaluate(
        """(ids) => ({
          open: document.querySelector('header').classList.contains('menu-open'),
          expanded: document.getElementById('phone-menu').getAttribute('aria-expanded'),
          items: ids.map((id) => {
            const e = document.getElementById(id);
            const r = e.getBoundingClientRect();
            const on = getComputedStyle(e).display !== 'none';
            return [id, on, r.left, r.right, r.height, r.bottom];
          }),
          doc: [document.documentElement.scrollWidth,
                document.documentElement.scrollHeight],
          vw: innerWidth, vh: innerHeight,
        })""",
        list(HEADER_BUTTONS),
    )
    shoot(page, "menu_open")
    check.ok(
        menu["open"] and menu["expanded"] == "true",
        "the menu button opens the menu",
        menu["expanded"],
    )
    shown = [item[0] for item in menu["items"] if item[1]]
    check.ok(
        shown == expected,
        "every header button the game shows is in the menu",
        (shown, expected),
    )
    bad = [
        item
        for item in menu["items"]
        if item[1]
        and (
            item[2] < -0.5
            or item[3] > menu["vw"] + 0.5
            or item[4] < 44
            or item[5] > menu["vh"]
        )
    ]
    check.ok(not bad, "each is at least 44px tall and inside the screen", bad)
    check.ok(
        menu["doc"][0] <= menu["vw"] and menu["doc"][1] <= menu["vh"],
        "the open menu does not scroll the page",
        menu["doc"],
    )
    sheet = page.locator("#side-main").bounding_box()
    page.touchscreen.tap(sheet["x"] + sheet["width"] / 2, sheet["y"] + 8)
    check.ok(
        not page.evaluate(MENU_OPEN),
        "a tap elsewhere closes it",
    )
    page.tap("#phone-menu")
    language = page.evaluate("TERM_LANGUAGE")
    page.tap("#language-toggle")
    check.ok(
        page.evaluate("TERM_LANGUAGE") != language
        and not page.evaluate(MENU_OPEN),
        "a choice from it acts and closes it",
        page.evaluate("TERM_LANGUAGE"),
    )
    check.ok(
        page.inner_text("#phone-tabs [data-view='hand']").strip() == "Hand",
        "the tabs speak the chosen language",
        page.inner_text("#phone-tabs [data-view='hand']"),
    )
    page.tap("#phone-menu")
    page.tap("#language-toggle")
    page.context.close()


def check_no_hand(base: str, browser) -> None:
    print("[E] a screen with no hand to show: no hand tab")
    _, page, _ = open_phone_context(browser, "phone-no-hand", PHONE_SIZES[1])
    create_by_touch(page, base, ONE_HUMAN)
    page.tap("#phone-tabs [data-view='hand']")
    # renderPrivate() hides the zone when the view has no private part (a
    # remote spectator); a review shows the reviewed seat's hand.
    page.evaluate("document.getElementById('private-zone').hidden = true")
    check.ok(
        not page.is_visible("#phone-tabs [data-view='hand']"), "the hand tab is gone"
    )
    shape = view_shape(page)
    check.ok(
        [name for name, rect in shape["shown"].items() if rect] == ["board"],
        "a hand view left open shows the board",
        shape["shown"],
    )
    page.context.close()


FINGER = r"""(selector) => {
  const out = [];
  for (const e of document.querySelectorAll(selector)) {
    const r = e.getBoundingClientRect();
    if (!r.width || !r.height || e.disabled) continue;
    const min = e.tagName === 'SELECT' ? 39.5 : 43.5;
    if (r.height < min || r.left < -0.5 || r.right > innerWidth + 0.5) {
      out.push([e.id || e.className || e.tagName, Math.round(r.left),
                Math.round(r.right), Math.round(r.height)]);
    }
  }
  return {bad: out, doc: [document.documentElement.scrollWidth,
                          document.documentElement.scrollHeight],
          vw: innerWidth, vh: innerHeight};
}"""
ROOM_KEY = "phone-layout-admin-key-0123456789"


def check_room_link(browser) -> None:
    print("[G] a room link opened on a phone: the places, then the table")
    with server("--remote", "--admin-key", ROOM_KEY, "--seating", "fixed") as (
        base,
        _,
    ):
        _, host, _ = open_context(browser, "room-host")
        host.goto(f"{base}/#admin={ROOM_KEY}")
        host.wait_for_function(
            "document.querySelectorAll('#seat-selects select').length === 4"
            " && state.server !== null"
        )
        for seat, kind in enumerate(("human", "human", "heuristic", "heuristic")):
            host.select_option(f"#seat-selects select[data-seat='{seat}']", kind)
        host.click("#create-game")
        host.wait_for_selector("#lobby-screen:not([hidden])")
        game_id = host.evaluate("state.gameId")
        _, page, _ = open_phone_context(browser, "phone-room", PHONE_SIZES[1])
        page.goto(f"{base}/#game={game_id}")
        page.wait_for_selector("#lobby-screen:not([hidden])")
        found = page.evaluate(FINGER, "#lobby-screen input, #lobby-screen button")
        shoot(page, "room_places")
        check.ok(
            not found["bad"]
            and found["doc"][0] <= found["vw"]
            and found["doc"][1] <= found["vh"],
            "the name field and the place buttons are 44px tall, on screen,"
            " and the page does not scroll",
            found,
        )
        page.tap("#lobby-name")
        page.keyboard.type("폰")
        page.locator("#lobby-seats button").first.tap()
        page.wait_for_selector("#game-screen:not([hidden])")
        page.wait_for_function("state.view !== null && refreshFlight === null")
        m = page.evaluate(LAYOUT)
        check.ok(
            not layout_faults(m) and page.is_visible("#phone-tabs"),
            "a tap on a place reaches the table in the phone layout",
            layout_faults(m),
        )
        shoot(page, "room_table")
        page.context.close()
        host.context.close()


def check_review_bar(base: str, browser) -> None:
    print("[H] a watched game: the review bar in the decision panel")
    _, page, _ = open_phone_context(browser, "phone-review", PHONE_SIZES[0])
    create_by_touch(page, base, ["heuristic"] * 4)
    page.wait_for_function("state.review !== null")
    page.wait_for_selector("#review-bar:not([hidden])")
    found = page.evaluate(FINGER, "#review-bar button, #review-bar select")
    bar = page.locator("#review-bar").bounding_box()
    sheet = page.locator("#side-main").bounding_box()
    shoot(page, "review_bar")
    check.ok(
        not found["bad"]
        and found["doc"][0] <= found["vw"]
        and found["doc"][1] <= found["vh"],
        "the review bar's controls are finger-sized, on screen, and the page"
        " does not scroll",
        found,
    )
    check.ok(
        bar["y"] >= sheet["y"] - 0.5 and bar["x"] + bar["width"] <= found["vw"] + 0.5,
        "the review bar sits in the decision panel",
        (bar, sheet),
    )
    # A watched game opens playing: stop it and let the position settle, so
    # only the tap can move the cursor, by exactly one step's landing
    # (common.REVIEW_LANDING: a pick step goes on to its effect's end).
    page.evaluate("stopPlayback()")
    page.wait_for_function("refreshFlight === null && !playback.playing")
    time.sleep(0.3)
    page.wait_for_function("refreshFlight === null")
    before = page.evaluate("state.review.cursor")
    expected = page.evaluate(REVIEW_LANDING, before + 1)
    page.tap("#review-next")
    try:
        page.wait_for_function(
            f"refreshFlight === null && state.review.cursor === {expected}",
            timeout=10000,
        )
    except Exception:  # noqa: BLE001 - reported below
        pass
    time.sleep(1.5)
    after = page.evaluate("state.review.cursor")
    check.ok(
        expected > before
        and after == expected
        and not page.evaluate("playback.playing"),
        "with playback stopped, a tap on ▶ steps the review by exactly one step",
        (before, expected, after),
    )
    page.context.close()


def check_desktop(base: str, browser) -> None:
    print("[F] 600px and wider: none of it")
    for size in ({"width": 600, "height": 800}, {"width": 1000, "height": 900}):
        _, page, _ = open_context(browser, f"desktop-{size['width']}", size)
        page.goto(base + "/")
        page.wait_for_function(
            "document.querySelectorAll('#seat-selects select').length === 4"
            " && state.server !== null"
        )
        for seat, kind in enumerate(ONE_HUMAN):
            page.select_option(f"#seat-selects select[data-seat='{seat}']", kind)
        page.fill("#opt-seed", str(PHONE_SEED))
        page.click("#create-game")
        page.wait_for_selector("#game-screen:not([hidden])")
        page.wait_for_function("state.view !== null && refreshFlight === null")
        shape = page.evaluate(
            """() => {
              const r = (id) => document.getElementById(id).getBoundingClientRect();
              const d = (id) => getComputedStyle(document.getElementById(id)).display;
              return {tabs: d('phone-tabs'), menu: d('phone-menu'),
                      seats: r('seats').right,
                      board: [r('board').left, r('board').right], side: r('side').left,
                      buttons: ['open-help', 'language-toggle'].map(d)};
            }"""
        )
        check.ok(
            shape["tabs"] == "none" and shape["menu"] == "none",
            f"{size['width']}px: no tab bar and no menu button",
            shape,
        )
        check.ok(
            "none" not in shape["buttons"],
            f"{size['width']}px: the header keeps its buttons",
            shape["buttons"],
        )
        check.ok(
            shape["seats"] <= shape["board"][0] and shape["board"][1] <= shape["side"],
            f"{size['width']}px: players, board and decisions side by side",
            shape,
        )
        page.context.close()


def main() -> None:
    with server() as (base, log_path):
        with chrome() as browser:
            check_tabs_and_menu(base, browser)
            check_no_hand(base, browser)
            check_desktop(base, browser)
            check_other_sizes(base, browser)
            check_review_bar(base, browser)
            check_room_link(browser)
            check_whole_game(base, browser)
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
