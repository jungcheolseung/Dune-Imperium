"""E2E of touch where the desktop uses hover, on a phone (docs/mobile-ui-plan.md
M3, user decision 2026-11-06).

A pointer that rests opens card pictures on the desktop (card_hover.py): the
log's card names, the decision rows about a card, the table's cards and
spaces. A phone has no resting pointer, but its browser still fires
mouseenter where a finger lifted, so a picture could open in hover mode over
whatever lay there next and stay. Since M3 the hover preview opens only on a
device that can hover (core.js hoverPopover); a tap pins a picture as a
click always did, and "ⓘ" shows a decision row's card in the panel.

In a phone's Chrome (common.open_phone_context), touched with tap() only:

A. At the first decision with a row about a card: a mouseenter (what a
   lifted finger leaves) on a log card name, a board space and that row,
   each required to be there, opens no hover popover; in a window with a
   mouse on the same game the same three each preview. A tap on a log
   card name pins its picture inside the screen; a tap elsewhere closes it.
B. "ⓘ" on a Leader draft row is at least 44x44px; a tap opens the row's
   detail with the Leader's picture (loaded) and sends nothing; a second
   tap closes it.
C. What opens over the table fits the screen and closes by a tap: a seat's
   Leader popover (players view), a pile viewer of the hand (hand view, its
   ×), the help (menu, its 닫기) and the Bene Tleilax board's
   zoom (shared cards view, its 닫기).
D. Every enabled button of the decision panel, and the tabs, are at least
   44px tall and 32px wide, at each of the first decisions of a game.

E2E_SHOTS_DIR optionally names where the screenshots go (mobile_touch_*.png).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from common import (
    ONE_HUMAN,
    PHONE_SIZES,
    SERVER_LOG_COPY,
    Check,
    chrome,
    client_state,
    create_by_touch,
    open_phone_context,
    server,
)
from open_mode import settled

check = Check()
SHOTS = Path(os.environ["E2E_SHOTS_DIR"]) if os.environ.get("E2E_SHOTS_DIR") else None

POPOVER = """() => {
  const p = document.getElementById('card-popover');
  if (p.hidden) return {state: 'hidden'};
  const r = p.getBoundingClientRect();
  return {state: p.classList.contains('hover') ? 'hover' : 'pinned',
          box: [r.left, r.top, r.right, r.bottom], vw: innerWidth, vh: innerHeight};
}"""
BOX = """(sel) => {
  const e = document.querySelector(sel);
  if (!e) return null;
  const r = e.getBoundingClientRect();
  return {box: [r.left, r.top, r.right, r.bottom], vw: innerWidth, vh: innerHeight,
          shown: r.width > 0 && r.height > 0};
}"""
DETAIL_PICTURE = "#actions .action-detail:not([hidden]) img.detail-card"
HIDDEN = "(id) => document.getElementById(id).hidden"
SMALL = """() => {
  const out = [];
  const shown = (e) => {
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden';
  };
  for (const b of document.querySelectorAll('#side-main button, #phone-tabs button')) {
    if (!shown(b) || b.disabled) continue;
    const r = b.getBoundingClientRect();
    if (r.height < 43.5 || r.width < 31.5) {
      out.push([b.className || b.id || 'button', b.textContent.trim().slice(0, 24),
                Math.round(r.width), Math.round(r.height)]);
    }
  }
  return out;
}"""


def shoot(page, name: str) -> None:
    if SHOTS:
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"mobile_touch_{name}.png"))


def inside(found: dict | None) -> bool:
    if not found:
        return False
    left, top, right, bottom = found["box"]
    return (
        left >= -0.5
        and top >= -0.5
        and right <= found["vw"] + 0.5
        and bottom <= found["vh"] + 0.5
    )


def tap_outside(page) -> None:
    """A tap on the decision panel's prompt, which does nothing."""
    page.tap("#decision-info", position={"x": 8, "y": 8})


def check_info_button(page) -> None:
    print("[B] the Leader draft's ⓘ")
    page.wait_for_function(
        "state.summary.decision && state.summary.decision.kind === 'leader_draft'"
    )
    info = page.locator("#actions .action-item .action-info").first
    box = info.bounding_box()
    check.ok(
        box["width"] >= 43.5 and box["height"] >= 43.5,
        "ⓘ is at least 44x44px",
        box,
    )
    revision = page.evaluate("state.summary.revision")
    info.tap()
    detail = page.locator("#actions .action-item .action-detail").first
    check.ok(detail.is_visible(), "a tap opens the row's detail")
    page.wait_for_function(
        "(sel) => { const i = document.querySelector(sel);"
        " return i && i.complete && i.naturalWidth > 0; }",
        arg=DETAIL_PICTURE,
    )
    picture = page.evaluate(BOX, DETAIL_PICTURE)
    check.ok(
        picture and picture["shown"] and picture["box"][2] <= picture["vw"] + 0.5,
        "the detail shows the Leader's picture",
        picture,
    )
    shoot(page, "info_open")
    check.ok(
        page.evaluate("state.summary.revision") == revision,
        "ⓘ sends nothing",
    )
    info.tap()
    check.ok(not detail.is_visible(), "a second tap closes it")
    # ⓘ stops its click; the open menu still closes on it.
    page.tap("#phone-menu")
    info.tap()
    check.ok(
        not page.evaluate(
            "document.querySelector('header').classList.contains('menu-open')"
        )
        and detail.is_visible(),
        "with the menu open, a tap on ⓘ closes the menu and opens the detail",
    )
    info.tap()


CARD_ROW = """() => {
  if (!state.actions) return null;
  for (const row of document.querySelectorAll('#actions .action-item[data-index]')) {
    const action = state.actions.actions
      .find((a) => String(a.index) === row.dataset.index);
    if (action && actionCardEntry(action)) return row.dataset.index;
  }
  return null;
}"""
HOVER = """([sel, kind]) => {
  const e = document.querySelector(sel);
  if (!e) return false;
  e.dispatchEvent(new MouseEvent(kind));
  return true;
}"""


def hover_states(page, anchors: list[str]) -> list[tuple[str, bool, str]]:
    """Each anchor: whether it is on the page, and the popover a mouseenter
    on it leaves after the hover delay (then a mouseleave)."""
    found = []
    for selector in anchors:
        present = page.evaluate(HOVER, [selector, "mouseenter"])
        time.sleep(0.4)
        found.append((selector, present, page.evaluate(POPOVER)["state"]))
        page.evaluate(HOVER, [selector, "mouseleave"])
        time.sleep(0.1)
    return found


def check_no_hover(page, row_index: str) -> None:
    """At a decision with a row about a card (core.js rowCardPreview hangs
    a hover preview on it), and the same decision in a window with a mouse."""
    print("[A] no hover popover from a lifted finger")
    anchors = [
        "#action-log .card-name",
        "#board .hotspot",
        f"#actions .action-item[data-index='{row_index}']",
    ]
    for selector, present, state in hover_states(page, anchors):
        check.ok(
            present and state == "hidden",
            f"phone: {selector} is there, and a mouseenter on it opens nothing",
            (present, state),
        )
    # The same anchors where a pointer can rest: each previews, so it is the
    # device, not the event or a missing listener, that kept the phone shut.
    desktop = page.context.browser.new_context(viewport={"width": 1000, "height": 900})
    other = desktop.new_page()
    other.goto(page.url)
    other.wait_for_function("state.view !== null && refreshFlight === null")
    other.wait_for_selector(anchors[2])
    for selector, present, state in hover_states(other, anchors):
        check.ok(
            present and state == "hover",
            f"mouse window: a mouseenter on {selector} previews",
            (present, state),
        )
    desktop.close()


def check_log_tap(page) -> None:
    print("[A] a tap on a log card name")
    page.tap("#phone-tabs [data-view='log']")
    page.locator("#action-log .card-name").first.tap()
    pop = page.evaluate(POPOVER)
    shoot(page, "log_name")
    check.ok(
        pop["state"] == "pinned" and inside(pop),
        "a tap on a log card name pins its picture inside the screen",
        pop,
    )
    tap_outside(page)
    check.ok(page.evaluate(POPOVER)["state"] == "hidden", "a tap elsewhere closes it")


def check_overlays(page) -> None:
    print("[C] what opens over the table fits and closes by a tap")
    page.tap("#phone-tabs [data-view='seats']")
    page.locator("#seats .leader-name").first.tap()
    pop = page.evaluate(POPOVER)
    shoot(page, "leader")
    check.ok(
        pop["state"] == "pinned" and inside(pop),
        "a seat's Leader popover is inside the screen",
        pop,
    )
    tap_outside(page)
    check.ok(page.evaluate(POPOVER)["state"] == "hidden", "a tap elsewhere closes it")

    page.tap("#phone-tabs [data-view='hand']")
    # The hand's deck or discard pile, whichever has cards now.
    page.locator("#private-zone [data-pile-opener^='hand-']").first.tap()
    page.wait_for_function("!document.getElementById('pile-viewer').hidden")
    viewer = page.evaluate(BOX, "#pile-viewer")
    shoot(page, "pile_viewer")
    check.ok(
        inside(viewer), "the hand's pile viewer is inside the screen", viewer
    )
    page.tap("#pile-viewer-close")
    check.ok(page.evaluate(HIDDEN, "pile-viewer"), "its × closes it")

    page.tap("#phone-menu")
    page.tap("#open-help")
    page.wait_for_function("!document.getElementById('help').hidden")
    help_box = page.evaluate(BOX, "#help-body")
    shoot(page, "help")
    check.ok(inside(help_box), "the help is inside the screen", help_box)
    page.tap("#help-body .help-close")
    check.ok(page.evaluate(HIDDEN, "help"), "its 닫기 closes it")

    page.tap("#phone-tabs [data-view='market']")
    opener = page.locator("#market .bt-open")
    if opener.count():
        opener.first.tap()
        page.wait_for_function("!document.getElementById('bt-zoom').hidden")
        zoom = page.evaluate(BOX, "#bt-zoom-body")
        shoot(page, "bene_tleilax")
        check.ok(inside(zoom), "the Bene Tleilax zoom is inside the screen", zoom)
        page.tap("#bt-zoom-body .bt-zoom-close")
        check.ok(page.evaluate(HIDDEN, "bt-zoom"), "its 닫기 closes it")
    else:
        check.ok(False, "the game shows the Bene Tleilax board")
    page.tap("#phone-tabs [data-view='board']")


def check_targets(page, decisions: int) -> None:
    print(f"[D] the decision panel's buttons, over {decisions} decisions")
    small, seen, hover_checked = [], 0, False
    for _ in range(600):
        assert settled(page, 30)
        snap = client_state(page)
        if snap["finished"] or seen >= decisions:
            break
        mine = snap["owner"] == snap["viewSeat"] and snap["nActions"]
        confirm = snap["confirmation"] == snap["viewSeat"]
        if mine or confirm:
            seen += 1
            found = page.evaluate(SMALL)
            if found:
                small.append((snap["kind"], found[:4]))
            row = page.evaluate(CARD_ROW) if mine else None
            if row is not None and not hover_checked:
                hover_checked = True
                check_no_hover(page, row)
        if confirm:
            page.evaluate("confirmTurn()")
        elif snap["nActions"]:
            page.evaluate("applyAction(0)")
        else:
            time.sleep(0.05)
    check.ok(seen >= decisions, "the seat had the decisions", seen)
    check.ok(hover_checked, "a decision offered a row about a card ([A] ran)")
    check.ok(
        not small,
        "every enabled button is at least 44px tall and 32px wide",
        small[:4],
    )


def main() -> None:
    with server() as (base, log_path):
        with chrome() as browser:
            _, page, _ = open_phone_context(browser, "phone-touch", PHONE_SIZES[1])
            create_by_touch(page, base, ONE_HUMAN)
            check_info_button(page)
            check_targets(page, 30)
            check_log_tap(page)
            check_overlays(page)
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
