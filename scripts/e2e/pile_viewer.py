"""E2E of the pile viewer (panels.js openPileViewer, 2026-10-11).

User feedback after a remote game with friends (2026-10-11): an opened
discard pile should stay on screen. The lists were drawn into the card
popover: hovering a card in one replaced the list with that card's
enlargement, which ignores the pointer, so the card under it on the table
took the pointer and the popover (the Conflict card, in this script's seed)
and the list was gone; render() also closed the list on every update,
anyone's move included. The lists now open in their own viewer,
#pile-viewer.

One real game (seat 0 human, three heuristic seats, every expansion, seed
7) is driven until the seat's discard pile and another seat's hold cards.
Then, in Korean and English at 1366x768:

- the hand strip's discard count opens the viewer, titled with the pile and
  its count, a dialog named by that title, with a labelled × ("닫기" /
  "Close"), the card popover above it and the viewer taking the pointer;
- hovering a card in it shows that card enlarged in the card popover while
  the viewer stays open with the same cards and the pointer stays on the
  card; moving off the card closes only the enlargement; a click on a card
  pins its enlargement, a click inside the viewer closes that, and Escape
  closes a pinned card first and the viewer next;
- a click on the board (a spot with no control) leaves it open and posts
  nothing; a decision button's click plays the step and the viewer is
  still open, showing the new state's pile;
- the deck list keeps its Top mark rules: the top card is marked exactly
  while peeked_card_id names a deck card, and every render reads it again;
- × and Escape close it, a second click on its opener closes it, another
  pile's opener moves it there;
- the Intrigue discard pile (newest first) and another seat's discard pile
  open in it, and hovering their cards keeps it;
- edits of the view show through a foreign render (a card more), and an
  emptied pile closes it;
- a long pile scrolls inside it; it fits 1366x768 and a 390x844 window and
  the page never scrolls sideways.

Once, between the languages: a language switch redraws the open viewer in
the new one; and with the AI pace at "fast" the AI seats' moves arrive as
foreign updates (the doorbell) and the viewer stays open through every one
of them, showing the state's pile each time.

E2E_SHOTS_DIR optionally names where the screenshots go
(pile_viewer_hover_{ko,en}.png, pile_viewer_long_{ko,en}.png,
pile_viewer_390_{ko,en}.png); otherwise a temporary folder.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import Any

from common import (
    LAPTOP_VIEWPORT,
    RULE_OPTIONS,
    SERVER_LOG_COPY,
    Check,
    Recorder,
    chrome,
    open_context,
    server,
    set_rule_options,
)
from log_follow import take_step
from open_mode import settled

check = Check()

SEED = 7
NARROW = {"width": 390, "height": 844}
SHOTS = Path(os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(prefix="dune-piles-"))

TEXT = {
    "ko": {"my_discard": "내 버림 더미 ({n})", "close": "닫기", "top": "맨 위"},
    "en": {"my_discard": "My discard pile ({n})", "close": "Close", "top": "Top"},
}

HAND_DISCARD = "[data-pile-opener='hand-discard']"
HAND_DECK = "[data-pile-opener='hand-deck']"
INTRIGUE_DISCARD = "[data-pile-opener='intrigue-discard']"

VIEWER_JS = """() => {
  const viewer = document.getElementById('pile-viewer');
  const pop = document.getElementById('card-popover');
  const body = document.getElementById('pile-viewer-body');
  const title = document.getElementById('pile-viewer-title');
  const close = document.getElementById('pile-viewer-close');
  const box = viewer.getBoundingClientRect();
  return {
    open: !viewer.hidden,
    title: title.textContent,
    named: viewer.getAttribute('role') === 'dialog'
      && viewer.getAttribute('aria-labelledby') === title.id,
    close: [close.getAttribute('aria-label'), close.textContent],
    notes: [...body.querySelectorAll('.popover-note')].map((n) => n.textContent),
    heads: [...body.querySelectorAll(':scope > .popover-title')].map((n) => n.textContent),
    cards: [...body.querySelectorAll('.vcard')].map((c) => c.dataset.instance),
    tops: [...body.querySelectorAll('.vcard.deck-top')].map((c) => c.dataset.instance),
    rect: { left: box.left, top: box.top, right: box.right, bottom: box.bottom,
            height: box.height },
    scroll: [body.scrollHeight, body.clientHeight],
    pointer: getComputedStyle(viewer).pointerEvents,
    z: [Number(getComputedStyle(viewer).zIndex), Number(getComputedStyle(pop).zIndex)],
    popover: {
      open: !pop.hidden,
      hover: pop.classList.contains('hover'),
      pinned: popoverPinned,
      title: (pop.querySelector('.popover-title') || {}).textContent || null,
    },
    page: [document.documentElement.scrollWidth, innerWidth, innerHeight],
  };
}"""

# What is under the pointer: the old popover gave it to the table.
UNDER_JS = """([x, y]) => {
  const node = document.elementFromPoint(x, y);
  const card = node && node.closest('.vcard');
  return { inViewer: Boolean(node && node.closest('#pile-viewer')),
           instance: card ? card.dataset.instance : null };
}"""

# A spot on the board with no control under it, outside the viewer.
FREE_POINT_JS = """() => {
  const board = document.getElementById('board');
  const rect = board.getBoundingClientRect();
  const box = document.getElementById('pile-viewer').getBoundingClientRect();
  const controls = 'button, a, input, select, [role=button], .hotspot, '
    + '[data-space], [data-instance], .clickable, [tabindex]';
  for (let fy = 0.1; fy < 0.95; fy += 0.05) {
    for (let fx = 0.1; fx < 0.95; fx += 0.05) {
      const x = rect.left + rect.width * fx;
      const y = rect.top + rect.height * fy;
      if (x < 1 || y < 1 || x > innerWidth - 1 || y > innerHeight - 1) continue;
      if (x >= box.left && x <= box.right && y >= box.top && y <= box.bottom) continue;
      const node = document.elementFromPoint(x, y);
      if (!node || !board.contains(node) || node.closest(controls)) continue;
      return [x, y];
    }
  }
  return null;
}"""

# A spot inside the viewer that is neither a card nor its ×, and not under
# the card popover pinned over it.
INSIDE_POINT_JS = """() => {
  const viewer = document.getElementById('pile-viewer');
  const box = viewer.getBoundingClientRect();
  for (let fy = 0.02; fy < 1; fy += 0.04) {
    for (let fx = 0.02; fx < 1; fx += 0.04) {
      const x = box.left + box.width * fx;
      const y = box.top + box.height * fy;
      const node = document.elementFromPoint(x, y);
      if (!node || !viewer.contains(node) || node.closest('.vcard, button')) continue;
      return [x, y];
    }
  }
  return null;
}"""

# Every render while the viewer watches seat `seat`'s discard pile: whether
# it was foreign, what the viewer showed and what the state held.
RENDER_HOOK_JS = """(seat) => {
  window.__renders = [];
  const original = window.__originalRender || render;
  window.__originalRender = original;
  window.render = function (options) {
    original(options);
    const viewer = document.getElementById('pile-viewer');
    const player = state.view && state.view.players.find((p) => p.player === seat);
    window.__renders.push({
      foreign: Boolean(options && options.foreign),
      shown: viewer.hidden ? null
        : [...viewer.querySelectorAll('.vcard')].map((c) => c.dataset.instance),
      expected: player ? [...player.discard_pile] : null,
    });
  };
}"""

# The view kept aside while this script edits it; the edits are drawn by a
# foreign render, as another seat's move would be.
EDIT_JS = """([seat, edit]) => {
  if (!window.__realView) window.__realView = state.view;
  const view = structuredClone(state.view);
  const own = view.players.find((p) => p.player === seat);
  const copy = (id, n) => id.replace(/:(\\d+)$/, (whole, k) => `:${Number(k) + n}`);
  let result = null;
  if (edit === 'more') {
    result = copy(own.discard_pile[0], 70);
    own.discard_pile = [...own.discard_pile, result];
  } else if (edit === 'empty') {
    own.discard_pile = [];
  } else if (edit === 'long') {
    const pile = own.discard_pile;
    own.discard_pile = Array.from(
      { length: 40 }, (_, i) => copy(pile[i % pile.length], 100 + i));
  } else if (edit.startsWith('peek:')) {
    const mine = view.players[view.player];
    mine.tech_ids = [...(mine.tech_ids || []).filter((id) => id !== 'glowglobes'),
                     'glowglobes'];
    view.private.peeked_card_id = edit.slice(5);
  } else if (edit === 'intrigue') {
    result = Object.keys(state.catalog.intrigue || {}).slice(0, 3)
      .map((id) => `intrigue:${id}:1`);
    view.intrigue_discard = result;
  }
  state.view = view;
  render({ foreign: true });
  return result;
}"""

RESTORE_JS = """() => {
  if (window.__realView) state.view = window.__realView;
  window.__realView = null;
  render();
}"""


def viewer(page: Any) -> dict[str, Any]:
    result: dict[str, Any] = page.evaluate(VIEWER_JS)
    return result


def open_pile(page: Any, selector: str) -> dict[str, Any]:
    page.locator(selector).first.click()
    page.wait_for_function("!document.getElementById('pile-viewer').hidden")
    page.wait_for_function(
        "[...document.querySelectorAll('#pile-viewer img')].every((i) => i.complete)"
    )
    return viewer(page)


def close_all(page: Any) -> None:
    """Escape until neither the card popover nor the viewer is open."""
    for _ in range(3):
        if not page.evaluate(
            "!document.getElementById('card-popover').hidden"
            " || !document.getElementById('pile-viewer').hidden"
        ):
            return
        page.keyboard.press("Escape")


def discard_of(page: Any, seat: int) -> list[str]:
    ids: list[str] = page.evaluate(
        "(seat) => [...state.view.players.find((p) => p.player === seat).discard_pile]",
        seat,
    )
    return ids


def page_width(page: Any) -> int:
    width: int = page.evaluate("document.documentElement.scrollWidth")
    return width


def fits(info: dict[str, Any], label: str, closed_width: int) -> None:
    """Inside the window, and the page no wider than with the viewer closed
    (at 390px the header's buttons already make it 514px wide)."""
    rect = info["rect"]
    width, inner_width, inner_height = info["page"]
    check.ok(
        rect["left"] >= 0
        and rect["top"] >= 0
        and rect["right"] <= inner_width
        and rect["bottom"] <= inner_height
        and rect["height"] <= 0.8 * inner_height + 1
        and width == closed_width,
        f"{label}: the viewer fits the {inner_width}x{inner_height} window"
        " and widens nothing",
        (rect, info["page"], closed_width),
    )


def hover_card(page: Any, index: int = 0) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Rest the pointer on a card in the viewer for longer than the hover
    delay and the old hand-over to the card beneath took."""
    card = page.locator("#pile-viewer-body .vcard").nth(index)
    card.scroll_into_view_if_needed()
    instance = card.get_attribute("data-instance") or ""
    box = card.bounding_box()
    assert box is not None
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(x, y)
    page.wait_for_function(
        "!document.getElementById('card-popover').hidden"
        " && document.getElementById('card-popover').classList.contains('hover')"
    )
    time.sleep(0.45)
    under: dict[str, Any] = page.evaluate(UNDER_JS, [x, y])
    return viewer(page), under, instance


def move_off_card(page: Any) -> dict[str, Any]:
    box = page.locator("#pile-viewer-title").bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + 4, box["y"] + box["height"] / 2)
    page.wait_for_function("document.getElementById('card-popover').hidden")
    return viewer(page)


def check_hover(page: Any, label: str, index: int = 0) -> None:
    before = viewer(page)
    shown, under, instance = hover_card(page, index)
    name = page.evaluate("(id) => (entryOf(id) || {}).name || nameOf(id)", instance)
    check.ok(
        shown["open"] and shown["cards"] == before["cards"],
        f"{label}: hovering a card keeps the viewer open with the same cards",
        (shown["open"], len(shown["cards"]), len(before["cards"])),
    )
    check.ok(
        shown["popover"]["open"]
        and shown["popover"]["hover"]
        and shown["popover"]["title"] == name,
        f"{label}: the hovered card shows enlarged ({name})",
        shown["popover"],
    )
    check.ok(
        under["inViewer"] and under["instance"] == instance,
        f"{label}: the pointer stays on the card in the viewer, not the table below",
        under,
    )
    check.ok(
        shown["z"][1] > shown["z"][0] and shown["pointer"] != "none",
        f"{label}: the enlargement lies above the viewer, the viewer takes the pointer",
        (shown["z"], shown["pointer"]),
    )
    off = move_off_card(page)
    check.ok(
        off["open"] and off["cards"] == before["cards"] and not off["popover"]["open"],
        f"{label}: moving off the card closes only the enlargement",
        (off["open"], off["popover"]),
    )


def check_language(page: Any, rec: Recorder, lang: str) -> None:
    words = TEXT[lang]
    label = f"[{lang}]"
    seat = page.evaluate("state.view.player")
    pile = discard_of(page, seat)
    closed_width = page_width(page)
    check.ok(
        closed_width == LAPTOP_VIEWPORT["width"],
        f"{label} the page does not scroll sideways at 1366x768",
        closed_width,
    )

    # The own discard pile, opened from the hand strip.
    opened = open_pile(page, HAND_DISCARD)
    check.ok(
        opened["open"]
        and opened["title"] == words["my_discard"].format(n=len(pile))
        and opened["cards"] == pile,
        f"{label} the discard count opens the viewer with the pile",
        (opened["title"], len(opened["cards"]), len(pile)),
    )
    check.ok(
        opened["named"] and opened["close"] == [words["close"], "×"],
        f"{label} a dialog named by its title, its × labelled '{words['close']}'",
        opened["close"],
    )
    check.ok(
        not opened["popover"]["open"], f"{label} no card popover opens with it"
    )
    fits(opened, f"{label} 1366x768", closed_width)
    check_hover(page, f"{label} own discard")
    hovered = hover_card(page, len(pile) - 1)
    page.screenshot(path=str(SHOTS / f"pile_viewer_hover_{lang}.png"))
    check.ok(
        hovered[0]["open"] and hovered[1]["inViewer"],
        f"{label} the last card hovers the same way",
    )
    move_off_card(page)

    # A click on a card pins its enlargement; the viewer stays.
    posts = rec.count("POST", "/actions")
    index = page.evaluate(
        "() => [...document.querySelectorAll('#pile-viewer-body .vcard')]"
        ".findIndex((c) => !legalActionsFor(c.dataset.instance).length)"
    )
    if check.ok(index >= 0, f"{label} a card in the pile with nothing to play"):
        page.locator("#pile-viewer-body .vcard").nth(index).click()
        pinned = viewer(page)
        check.ok(
            pinned["open"]
            and pinned["popover"]["open"]
            and pinned["popover"]["pinned"]
            and rec.count("POST", "/actions") == posts,
            f"{label} a click on a card pins its enlargement, the viewer stays",
            pinned["popover"],
        )
        spot = page.evaluate(INSIDE_POINT_JS)
        if check.ok(spot is not None, f"{label} a bare spot inside the viewer"):
            page.mouse.click(spot[0], spot[1])
            inside = viewer(page)
            check.ok(
                inside["open"] and not inside["popover"]["open"],
                f"{label} a click inside the viewer closes the pinned card,"
                " not the viewer",
            )
        page.locator("#pile-viewer-body .vcard").nth(index).click()
        page.keyboard.press("Escape")
        first = viewer(page)
        page.keyboard.press("Escape")
        second = viewer(page)
        check.ok(
            first["open"] and not first["popover"]["open"] and not second["open"],
            f"{label} Escape closes the pinned card first, then the viewer",
            (first["open"], first["popover"]["open"], second["open"]),
        )

    # A click on the board leaves it open.
    open_pile(page, HAND_DISCARD)
    point = page.evaluate(FREE_POINT_JS)
    if check.ok(point is not None, f"{label} a spot on the board with no control"):
        posts = rec.count("POST", "/actions")
        page.mouse.click(point[0], point[1])
        time.sleep(0.2)
        check.ok(
            viewer(page)["open"] and rec.count("POST", "/actions") == posts,
            f"{label} a click on the board leaves the viewer open, posts nothing",
        )

    # The × closes it; so does a second click on its opener.
    page.locator("#pile-viewer-close").click()
    check.ok(not viewer(page)["open"], f"{label} the × closes it")
    open_pile(page, HAND_DISCARD)
    page.keyboard.press("Escape")
    check.ok(not viewer(page)["open"], f"{label} Escape closes it")
    open_pile(page, HAND_DISCARD)
    page.locator(HAND_DISCARD).click()
    check.ok(
        not viewer(page)["open"], f"{label} a second click on the opener closes it"
    )

    # A foreign render with a card more redraws it; an empty pile closes it.
    open_pile(page, HAND_DISCARD)
    extra = page.evaluate(EDIT_JS, [seat, "more"])
    more = viewer(page)
    check.ok(
        more["open"]
        and more["cards"] == [*pile, extra]
        and more["title"] == words["my_discard"].format(n=len(pile) + 1),
        f"{label} a foreign update with a card more redraws it, still open",
        (more["title"], more["cards"][-1:]),
    )
    page.evaluate(EDIT_JS, [seat, "empty"])
    check.ok(not viewer(page)["open"], f"{label} the pile emptied closes it")
    page.evaluate(RESTORE_JS)

    # A long pile scrolls inside the viewer.
    page.evaluate(EDIT_JS, [seat, "long"])
    long = open_pile(page, HAND_DISCARD)
    check.ok(
        len(long["cards"]) == 40 and long["scroll"][0] > long["scroll"][1],
        f"{label} a 40-card pile scrolls inside the viewer",
        long["scroll"],
    )
    fits(long, f"{label} 40 cards at 1366x768", closed_width)
    page.screenshot(path=str(SHOTS / f"pile_viewer_long_{lang}.png"))
    close_all(page)
    page.evaluate(RESTORE_JS)

    check_deck_top(page, lang)
    check_other_piles(page, lang, seat)
    check_narrow(page, lang, seat)


def check_deck_top(page: Any, lang: str) -> None:
    """The deck list's Top mark (OQ-010 ruling 5 and the user decision of
    2026-10-10): only while peeked_card_id names a card of the deck, read
    again on every render while the viewer stays open."""

    label = f"[{lang} deck]"
    deck = page.evaluate("[...(state.view.private.deck_cards || [])]")
    if not check.ok(len(deck) >= 2, f"{label} the deck holds cards", len(deck)):
        return
    top = deck[-1]
    page.evaluate(EDIT_JS, [0, f"peek:{top}"])
    marked = open_pile(page, HAND_DECK)
    check.ok(
        marked["tops"] == [top] and len(marked["notes"]) == 2,
        f"{label} the top card is marked '{TEXT[lang]['top']}' while the view names it",
        (marked["tops"], marked["notes"]),
    )
    badge = page.evaluate(
        "() => document.querySelector('#pile-viewer .vcard.deck-top .vcard-badge')"
        ".textContent"
    )
    check.ok(badge == TEXT[lang]["top"], f"{label} its badge", badge)
    page.evaluate(EDIT_JS, [0, "peek:"])
    plain = viewer(page)
    check.ok(
        plain["open"]
        and plain["tops"] == []
        and len(plain["notes"]) == 1
        and plain["title"] == marked["title"],
        f"{label} the next render drops the mark once the view names no card",
        (plain["open"], plain["tops"], plain["notes"]),
    )
    hand = page.evaluate("state.view.private.hand[0] || 'nothing:0'")
    page.evaluate(EDIT_JS, [0, f"peek:{hand}"])
    check.ok(
        viewer(page)["tops"] == [],
        f"{label} a peeked card outside the deck marks nothing",
    )
    page.evaluate(EDIT_JS, [0, f"peek:{top}"])
    check.ok(
        viewer(page)["open"] and viewer(page)["tops"] == [top],
        f"{label} the mark comes back with the view naming the top again",
    )
    close_all(page)
    page.evaluate(RESTORE_JS)


def check_other_piles(page: Any, lang: str, seat: int) -> None:
    label = f"[{lang}]"
    # The Intrigue discard pile, newest first.
    ids = page.evaluate(EDIT_JS, [seat, "intrigue"])
    title = page.evaluate("t('board.pile_intrigue_discard')") + " (3)"
    shown = open_pile(page, INTRIGUE_DISCARD)
    check.ok(
        shown["title"] == title and shown["cards"] == [ids[2], ids[1], ids[0]],
        f"{label} the Intrigue discard opens in the viewer, newest first",
        (shown["title"], shown["cards"]),
    )
    check_hover(page, f"{label} Intrigue discard")
    page.locator(INTRIGUE_DISCARD).click()
    check.ok(not viewer(page)["open"], f"{label} its opener closes it again")
    page.evaluate(RESTORE_JS)

    # Another seat's discard pile, from its seat panel; then the seat's own
    # panel moves the viewer there.
    other = page.evaluate(
        "(seat) => (state.view.players.find((p) => p.player !== seat"
        " && p.discard_pile.length) || {}).player",
        seat,
    )
    if not check.ok(other is not None, f"{label} another seat has a discard pile"):
        return
    pile = discard_of(page, other)
    expected = page.evaluate(
        "(seat) => t('panels.seat_discard', { seat: t('common.seat', { seat }) })",
        other,
    ) + f" ({len(pile)})"
    # A seat panel's zones line opens the seat's deck pool first (2026-10-13,
    # deck_pool.py checks it in full), its discard pile as the second section.
    pool_title = page.evaluate(
        "(seat) => t('panels.seat_deck_pool', { seat: t('common.seat', { seat }),"
        " count: state.view.players.find((p) => p.player === seat)"
        ".deck_pool.length })",
        other,
    )
    theirs = open_pile(page, f"[data-pile-opener='seat-discard:{other}']")
    check.ok(
        theirs["title"] == pool_title
        and theirs["heads"] == [expected]
        and theirs["cards"][len(theirs["cards"]) - len(pile) :] == pile,
        f"{label} seat {other}'s discard pile opens in the viewer, after its pool",
        (theirs["title"], theirs["heads"], len(theirs["cards"])),
    )
    check_hover(page, f"{label} seat {other}'s discard")
    own = open_pile(page, f"[data-pile-opener='seat-discard:{seat}']")
    own_pool = page.evaluate(
        "(seat) => t('panels.my_deck_pool', { count: state.view.players"
        ".find((p) => p.player === seat).deck_pool.length })",
        seat,
    )
    check.ok(
        own["title"] == own_pool
        and own["heads"] == [TEXT[lang]["my_discard"].format(n=len(discard_of(page, seat)))]
        and own["rect"] != theirs["rect"],
        f"{label} another pile's opener replaces the contents and moves the viewer",
        (own["title"], own["heads"], own["rect"], theirs["rect"]),
    )
    page.locator(f"[data-pile-opener='seat-discard:{seat}']").click()
    check.ok(not viewer(page)["open"], f"{label} and its own opener closes it")


def check_narrow(page: Any, lang: str, seat: int) -> None:
    label = f"[{lang} 390px]"
    page.set_viewport_size(NARROW)
    try:
        page.wait_for_timeout(200)
        closed_width = page_width(page)
        shown = open_pile(page, HAND_DISCARD)
        fits(shown, label, closed_width)
        check_hover(page, label)
        page.screenshot(path=str(SHOTS / f"pile_viewer_390_{lang}.png"))
        close_all(page)
        page.evaluate(EDIT_JS, [seat, "long"])
        long = open_pile(page, HAND_DISCARD)
        check.ok(
            long["scroll"][0] > long["scroll"][1],
            f"{label} a 40-card pile scrolls inside the viewer",
            long["scroll"],
        )
        fits(long, f"{label} 40 cards", closed_width)
        close_all(page)
        page.evaluate(RESTORE_JS)
    finally:
        page.set_viewport_size(LAPTOP_VIEWPORT)
        page.wait_for_timeout(200)


def check_language_switch(page: Any) -> None:
    """Korean on screen: the open viewer follows a switch to English."""
    seat = page.evaluate("state.view.player")
    n = len(discard_of(page, seat))
    open_pile(page, HAND_DISCARD)
    page.click("#language-toggle")
    page.wait_for_function("TERM_LANGUAGE === 'en'")
    switched = viewer(page)
    check.ok(
        switched["open"]
        and switched["title"] == TEXT["en"]["my_discard"].format(n=n)
        and switched["close"] == [TEXT["en"]["close"], "×"],
        "[ko -> en] a language switch redraws the open viewer in English",
        (switched["open"], switched["title"], switched["close"]),
    )
    close_all(page)


def check_foreign_moves(page: Any, rec: Recorder) -> None:
    """AI moves paced by the server reach the page as foreign updates (the
    doorbell, session.js): the viewer stays open through every render and
    shows the state's pile each time."""

    label = "[AI moves]"
    seat = page.evaluate("state.view.player")
    page.evaluate("async () => { await setAiPace('fast'); }")
    open_pile(page, HAND_DISCARD)
    page.evaluate(RENDER_HOOK_JS, seat)
    # A decision button's click plays the step; the AI seats answer after it.
    button = page.locator("#actions .action-item > button").first
    if page.evaluate("state.summary.confirmation === state.viewSeat"):
        page.evaluate("confirmTurn()")
    elif button.count():
        button.click()
    else:
        take_step(page)
    assert settled(page, 20)
    if page.evaluate("Boolean(state.pick) || Boolean(heldChoice())"):
        # The click picked a card or held an irreversible choice: Escape lets
        # it go before the viewer.
        page.keyboard.press("Escape")
        check.ok(
            viewer(page)["open"], f"{label} letting the choice go keeps the viewer"
        )
        take_step(page)
    # Play the human seat on whenever it is its turn again, until three
    # foreign updates have come in.
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        foreign = page.evaluate("window.__renders.filter((r) => r.foreign).length")
        if foreign >= 3:
            break
        if page.evaluate(
            "!state.busy && refreshFlight === null && ((state.actions"
            " && state.actions.actions.length)"
            " || state.summary.confirmation === state.viewSeat)"
        ):
            take_step(page)
        time.sleep(0.2)
    page.evaluate("async () => { await setAiPace('instant'); }")
    page.wait_for_function(
        "(state.actions && state.actions.actions.length)"
        " || state.summary.confirmation === state.viewSeat",
        timeout=60000,
    )
    assert settled(page, 20)
    renders = page.evaluate("window.__renders")
    page.evaluate("() => { window.render = window.__originalRender; }")
    foreign = [r for r in renders if r["foreign"]]
    check.ok(
        len(foreign) >= 3, f"{label} AI moves arrived as foreign updates", len(foreign)
    )
    wrong = [
        r
        for r in renders
        if (r["shown"] != r["expected"] if r["expected"] else r["shown"] is not None)
    ]
    check.ok(
        not wrong,
        f"{label} through {len(renders)} renders the viewer stayed open on the pile",
        wrong[:2],
    )
    check.ok(
        any(r["foreign"] and r["shown"] for r in renders),
        f"{label} it was open during a foreign update",
    )
    close_all(page)


def drive(page: Any, cap: int = 600) -> bool:
    ready = (
        "() => { const seat = state.view.player; const players = state.view.players;"
        " return players[seat].discard_pile.length >= 3"
        " && players.some((p) => p.player !== seat && p.discard_pile.length)"
        " && (state.view.private.deck_cards || []).length >= 2"
        " && Boolean(state.actions && state.actions.actions.length); }"
    )
    for _ in range(cap):
        if page.evaluate(ready):
            return True
        if page.evaluate("state.summary.finished"):
            return False
        take_step(page)
    return False


def main() -> None:
    with server() as (base, log_path):
        with chrome() as browser:
            context, page, rec = open_context(browser, "pile-viewer", LAPTOP_VIEWPORT)
            page.goto(base + "/")
            page.wait_for_selector("#setup-screen:not([hidden])")
            for seat in range(4):
                page.select_option(
                    f"#seat-selects select[data-seat='{seat}']",
                    "human" if seat == 0 else "heuristic",
                )
            set_rule_options(page, *RULE_OPTIONS)
            page.set_checked("#opt-leader-draft", False)
            page.fill("#opt-seed", str(SEED))
            page.click("#create-game")
            page.wait_for_selector("#game-screen:not([hidden])")
            page.wait_for_function("state.view !== null && refreshFlight === null")
            if check.ok(drive(page), "a state with piles to look at was reached"):
                for lang in ("ko", "en"):
                    if page.evaluate("TERM_LANGUAGE") != lang:
                        page.click("#language-toggle")
                        page.wait_for_function(f"TERM_LANGUAGE === '{lang}'")
                    check_language(page, rec, lang)
                    if lang == "ko":
                        check_language_switch(page)
                check_foreign_moves(page, rec)
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
    print(f"screenshots: {SHOTS}")
    check.finish()


if __name__ == "__main__":
    main()
