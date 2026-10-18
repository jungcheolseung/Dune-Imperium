"""E2E of the seat panels' deck pool (panels.js deckPoolSection, 2026-10-13).

OQ-010 ruling 6 (user decision 2026-10-13): every card enters or leaves a
seat's deck or hand through a public place, so the cards that are in a
seat's draw deck and in the hidden part of its hand, together, are public.
The server sends them as ``view.players[i].deck_pool`` (card ids, one entry
per copy, sorted by id); which of the two zones holds a card stays hidden.
The seat panel's zones line ("손패 N . 덱 N . 버림 N . 책략 N") opens that list
in the pile viewer (#pile-viewer), the seat's discard pile after it.

One real game (seat 0 human, three heuristic seats, every expansion, a fixed
seed) is played until round 2, so that the pools differ from the starting
decks. Then, in Korean and English at 1366x768, for all four seats (seat 0 is
this browser's own, the others are "another seat"):

- the zones line is a clickable line with the tooltip "deck, hand and
  discard pile";
- a click opens the viewer with the pool section first (its title with the
  seat and the number of copies, the note under it) and the discard section
  after it (the existing "discard pile (N)" title and its cards, only when
  the pile is not empty), nothing else;
- the pool's cards are one per distinct card id, with a x N badge from two
  copies on and none for one, sorted by the name on screen (localeCompare in
  the page's language), and they are exactly the view's deck_pool;
- the pool's total (the badges summed) is the view's
  deck_size + hand_size - len(hand_public), and len(deck_pool), and the count
  in the title;
- no card in the pool carries an instance id (its data-instance has no ":");
- the note is shown, a click on a card pins its enlargement and posts nothing,
  Escape closes the viewer (the pinned card first);
- the page never scrolls sideways and the viewer fits the window.

And once per language: the open viewer draws again from a foreign render (a
card more in the pool, no pool left but a discard pile, nothing left to show
closes it), and a card in the seat's public hand (``hand_public``: acquired
straight to the hand, Price is No Object) is shown in its own section between
the pool and the discard pile, or alone (the zones line still opens it) when
the seat has nothing else to show (user report 2026-10-19: it was missing).

E2E_SHOTS_DIR optionally names where the screenshots go
(deck_pool_{ko,en}.png); otherwise a temporary folder.
"""

from __future__ import annotations

import os
import tempfile
from collections import Counter
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

check = Check()

SEED = 20261014
SHOTS = Path(os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(prefix="dune-pool-"))

TEXT = {
    "ko": {
        "tooltip": "카드덱·핸드와 버림 더미 보기",
        "pool_mine": "내 카드덱·핸드에 있는 카드 · {n}장",
        "pool_seat": "플레이어{seat}의 카드덱·핸드에 있는 카드 · {n}장",
        "discard_mine": "내 버림 더미 ({n})",
        "discard_seat": "플레이어{seat}의 버림 더미 ({n})",
        "hand_public_seat": "플레이어{seat} 핸드의 공개된 카드 ({n})",
        "note": (
            "어느 카드가 카드덱에 있고 어느 카드가 핸드에 있는지는 알 수 없습니다. "
            "산 카드·버린 카드·폐기한 카드가 모두 공개되므로 누구나 셀 수 있는 "
            "목록입니다."
        ),
    },
    "en": {
        "tooltip": "View the deck, hand and discard pile",
        "pool_mine": "In my deck or hand · {n} cards",
        "pool_seat": "In Player {seat}'s deck or hand · {n} cards",
        "discard_mine": "My discard pile ({n})",
        "discard_seat": "Player {seat}'s discard pile ({n})",
        "hand_public_seat": "Public cards in Player {seat}'s hand ({n})",
        "note": (
            "Which of these are in the deck and which in the hand is not known. "
            "Every card bought, discarded or trashed is public, so anyone can "
            "count this list."
        ),
    },
}

SEATS = range(4)
# Every x N badge the pools showed, so that "a badge from two copies on" is
# known to have been looked at and not only passed for want of a badge.
BADGES: list[str] = []

VIEWER_JS = """() => {
  const viewer = document.getElementById('pile-viewer');
  const body = document.getElementById('pile-viewer-body');
  const box = viewer.getBoundingClientRect();
  const kids = [...body.children];
  const kind = (node) => node.classList.contains('strip-cards') ? 'cards'
    : node.classList.contains('popover-note') ? 'note'
    : node.classList.contains('popover-title') ? 'title' : node.className;
  const cards = (node) => [...node.querySelectorAll('.vcard')].map((c) => {
    const badge = c.querySelector('.vcard-badge');
    const image = c.querySelector('img');
    const label = c.querySelector('.vcard-name');
    return {
      instance: c.dataset.instance,
      badge: badge ? badge.textContent : '',
      name: image ? image.alt : (label ? label.textContent : ''),
    };
  });
  return {
    open: !viewer.hidden,
    title: document.getElementById('pile-viewer-title').textContent,
    layout: kids.map(kind),
    notes: kids.filter((n) => kind(n) === 'note').map((n) => n.textContent),
    heads: kids.filter((n) => kind(n) === 'title').map((n) => n.textContent),
    rows: kids.filter((n) => kind(n) === 'cards').map(cards),
    rect: { left: box.left, top: box.top, right: box.right, bottom: box.bottom },
    page: [document.documentElement.scrollWidth, innerWidth, innerHeight],
    popover: !document.getElementById('card-popover').hidden,
  };
}"""

SEAT_JS = """(seat) => {
  const p = state.view.players.find((q) => q.player === seat);
  return { pool: [...p.deck_pool], discard: [...p.discard_pile],
           deck_size: p.deck_size, hand_size: p.hand_size,
           hand_public: p.hand_public.length };
}"""

# The names the catalog gives the pool's card ids, in the page's language.
NAMES_JS = """(ids) => ids.map((id) => (lookup(id, 'cards') || {}).name || '')"""

SORTED_JS = """([names, locale]) => names.every(
  (name, i) => i === 0 || names[i - 1].localeCompare(name, locale) <= 0)"""

# The view kept aside while this script edits it; the edit is drawn by a
# foreign render, as another seat's move would be.
EDIT_JS = """([seat, edit]) => {
  if (!window.__realView) window.__realView = state.view;
  const view = structuredClone(state.view);
  const own = view.players.find((p) => p.player === seat);
  if (edit === 'more') own.deck_pool = [...own.deck_pool, 'dagger'].sort();
  else if (edit === 'no_pool') own.deck_pool = [];
  else if (edit === 'empty') { own.deck_pool = []; own.discard_pile = []; }
  else if (edit === 'public_hand') {
    own.hand_public = [own.discard_pile[0]];
    own.hand_size += 1;
  } else if (edit === 'public_only') {
    own.hand_public = [own.discard_pile[0]];
    own.deck_pool = [];
    own.discard_pile = [];
  }
  state.view = view;
  render({ foreign: true });
}"""

RESTORE_JS = """() => {
  if (window.__realView) state.view = window.__realView;
  window.__realView = null;
  render();
}"""

READY_JS = """() => {
  const players = state.view.players;
  const seat = state.view.player;
  return state.summary.round_number >= 2
    && players[seat].discard_pile.length > 0
    && players.every((p) => p.deck_pool.length > 0)
    && players.some((p) => p.player !== seat && p.discard_pile.length > 0)
    && Boolean(state.actions && state.actions.actions.length);
}"""


def viewer(page: Any) -> dict[str, Any]:
    result: dict[str, Any] = page.evaluate(VIEWER_JS)
    return result


def seat_view(page: Any, seat: int) -> dict[str, Any]:
    result: dict[str, Any] = page.evaluate(SEAT_JS, seat)
    return result


def opener(seat: int) -> str:
    return f"#seats article.seat[data-seat='{seat}'] .zones"


def open_zones(page: Any, seat: int) -> dict[str, Any]:
    page.locator(opener(seat)).click()
    page.wait_for_function("!document.getElementById('pile-viewer').hidden")
    page.wait_for_function(
        "[...document.querySelectorAll('#pile-viewer img')].every((i) => i.complete)"
    )
    return viewer(page)


def close_viewer(page: Any) -> None:
    for _ in range(3):
        if not page.evaluate(
            "!document.getElementById('card-popover').hidden"
            " || !document.getElementById('pile-viewer').hidden"
        ):
            return
        page.keyboard.press("Escape")


def copies(card: dict[str, str]) -> int:
    """The number of copies a pool card stands for: its x N badge, or one."""
    badge = card["badge"]
    return int(badge[1:]) if badge else 1


def check_fits(info: dict[str, Any], label: str) -> None:
    rect = info["rect"]
    width, inner_width, inner_height = info["page"]
    check.ok(
        width <= inner_width
        and rect["left"] >= 0
        and rect["top"] >= 0
        and rect["right"] <= inner_width
        and rect["bottom"] <= inner_height,
        f"{label}: the viewer fits the {inner_width}x{inner_height} window,"
        " the page does not scroll sideways",
        (rect, info["page"]),
    )


def check_seat(
    page: Any, rec: Recorder, lang: str, seat: int, extras: bool = False
) -> None:
    words = TEXT[lang]
    label = f"[{lang} seat {seat}]"
    mine = seat == page.evaluate("state.view.player")
    data = seat_view(page, seat)
    pool, discard = data["pool"], data["discard"]

    clickable = page.evaluate(
        "(sel) => document.querySelector(sel).classList.contains('clickable')",
        opener(seat),
    )
    if not pool and not discard:
        check.ok(not clickable, f"{label} nothing to show, the zones line is plain")
        return
    check.ok(clickable, f"{label} the zones line is clickable")
    check.ok(
        page.get_attribute(opener(seat), "title") == words["tooltip"],
        f"{label} its tooltip reads '{words['tooltip']}'",
        page.get_attribute(opener(seat), "title"),
    )

    info = open_zones(page, seat)
    check.ok(info["open"], f"{label} a click opens the viewer")

    # The pool section, then the discard section, nothing else.
    expected_layout = ["note", "cards"] + (["title", "cards"] if discard else [])
    if not pool:
        expected_layout = ["cards"]
    check.ok(
        info["layout"] == expected_layout,
        f"{label} the pool section (note, cards) comes first, the discard"
        " section after it" + ("" if discard else " (empty, left out)"),
        info["layout"],
    )
    if not pool:
        return

    total = len(pool)
    check.ok(
        total == data["deck_size"] + data["hand_size"] - data["hand_public"],
        f"{label} deck_pool holds deck_size + hand_size - len(hand_public)",
        (total, data["deck_size"], data["hand_size"], data["hand_public"]),
    )
    pool_title = words["pool_mine" if mine else "pool_seat"].format(
        n=total, seat=seat + 1
    )
    check.ok(
        info["title"] == pool_title,
        f"{label} the viewer's title is the pool's: '{pool_title}'",
        info["title"],
    )
    check.ok(
        info["notes"] == [words["note"]],
        f"{label} the note is shown",
        info["notes"],
    )

    cards = info["rows"][0]
    BADGES.extend(c["badge"] for c in cards if c["badge"])
    shown = sum(copies(c) for c in cards)
    check.ok(
        shown == total,
        f"{label} the badges add up to the pool's {total} cards",
        shown,
    )
    check.ok(
        {c["instance"]: copies(c) for c in cards} == dict(Counter(pool)),
        f"{label} one card per distinct id with its copies, as deck_pool lists",
        ([c["instance"] for c in cards][:6], sorted(set(pool))[:6]),
    )
    check.ok(
        all(c["badge"] == "" or copies(c) > 1 for c in cards)
        and all(c["badge"] == f"×{copies(c)}" for c in cards if c["badge"]),
        f"{label} a x N badge from two copies on, none for one",
        [c["badge"] for c in cards][:8],
    )
    check.ok(
        all(":" not in c["instance"] for c in cards),
        f"{label} no card in the pool carries an instance id",
        [c["instance"] for c in cards if ":" in c["instance"]][:3],
    )
    names = page.evaluate(NAMES_JS, [c["instance"] for c in cards])
    check.ok(
        names == [c["name"] for c in cards],
        f"{label} each card shows its catalog name",
        (names[:4], [c["name"] for c in cards][:4]),
    )
    check.ok(
        page.evaluate(SORTED_JS, [[c["name"] for c in cards], lang]),
        f"{label} the cards are sorted by the name on screen",
        [c["name"] for c in cards],
    )

    if discard:
        discard_title = words["discard_mine" if mine else "discard_seat"].format(
            n=len(discard), seat=seat + 1
        )
        check.ok(
            info["heads"] == [discard_title],
            f"{label} the discard section keeps its title: '{discard_title}'",
            info["heads"],
        )
        check.ok(
            [c["instance"] for c in info["rows"][1]] == discard,
            f"{label} and its cards, in the pile's order",
            (len(info["rows"][1]), len(discard)),
        )
    check_fits(info, label)
    if extras:
        page.screenshot(path=str(SHOTS / f"deck_pool_{lang}.png"))
        check_pin(page, rec, label)
        check_foreign(page, label, seat, lang, discard)

    page.keyboard.press("Escape")
    check.ok(not viewer(page)["open"], f"{label} Escape closes the viewer")


def check_pin(page: Any, rec: Recorder, label: str) -> None:
    """A click on a pool card pins its enlargement; it is no card to act on."""
    posts = rec.count("POST", "/actions")
    page.locator("#pile-viewer-body .vcard").first.click()
    pinned = viewer(page)
    check.ok(
        pinned["open"] and pinned["popover"] and rec.count("POST", "/actions") == posts,
        f"{label} a click on a pool card pins its enlargement, posts nothing",
        (pinned["open"], pinned["popover"]),
    )
    page.keyboard.press("Escape")
    closed_card = viewer(page)
    check.ok(
        closed_card["open"] and not closed_card["popover"],
        f"{label} Escape closes the pinned card first, the viewer stays",
    )


def check_foreign(
    page: Any, label: str, seat: int, lang: str, discard: list[str]
) -> None:
    """The viewer reads the view again on every render."""
    words = TEXT[lang]
    before = viewer(page)
    total = sum(copies(c) for c in before["rows"][0])
    page.evaluate(EDIT_JS, [seat, "more"])
    more = viewer(page)
    check.ok(
        more["open"]
        and sum(copies(c) for c in more["rows"][0]) == total + 1
        and more["title"] == words["pool_seat"].format(n=total + 1, seat=seat + 1),
        f"{label} a foreign update with a card more redraws the open viewer",
        (more["open"], more["title"]),
    )
    page.evaluate(RESTORE_JS)
    page.evaluate(EDIT_JS, [seat, "no_pool"])
    only = viewer(page)
    check.ok(
        only["open"]
        and only["layout"] == ["cards"]
        and only["title"]
        == words["discard_seat"].format(n=len(discard), seat=seat + 1),
        f"{label} with no pool left the viewer shows the discard pile alone",
        (only["open"], only["layout"], only["title"]),
    )
    page.evaluate(RESTORE_JS)
    page.evaluate(EDIT_JS, [seat, "public_hand"])
    public = viewer(page)
    want = words["hand_public_seat"].format(n=1, seat=seat + 1)
    check.ok(
        public["open"]
        and public["layout"] == ["note", "cards", "title", "cards", "title", "cards"]
        and public["heads"]
        == [want, words["discard_seat"].format(n=len(discard), seat=seat + 1)]
        and [c["instance"] for c in public["rows"][1]] == [discard[0]],
        f"{label} a public hand card has its own section '{want}' between the"
        " pool and the discard pile",
        (public["layout"], public["heads"], public["rows"][1:2]),
    )
    page.evaluate(RESTORE_JS)
    page.evaluate(EDIT_JS, [seat, "public_only"])
    alone = viewer(page)
    clickable = page.evaluate(
        "(sel) => document.querySelector(sel).classList.contains('clickable')",
        opener(seat),
    )
    check.ok(
        alone["open"]
        and alone["layout"] == ["cards"]
        and alone["title"] == want
        and clickable,
        f"{label} with only a public hand card left the viewer shows it alone"
        " and the zones line still opens it",
        (alone["open"], alone["layout"], alone["title"], clickable),
    )
    page.evaluate(RESTORE_JS)
    page.evaluate(EDIT_JS, [seat, "empty"])
    check.ok(
        not viewer(page)["open"],
        f"{label} nothing left to show closes the viewer",
    )
    page.evaluate(RESTORE_JS)
    open_zones(page, seat)


def check_language(page: Any, rec: Recorder, lang: str) -> None:
    own = page.evaluate("state.view.player")
    # The seat whose viewer also gets the pin and the foreign-update checks:
    # another seat with both a pool and a discard pile.
    extra = next(
        seat
        for seat in SEATS
        if seat != own
        and seat_view(page, seat)["pool"]
        and seat_view(page, seat)["discard"]
    )
    for seat in SEATS:
        check_seat(page, rec, lang, seat, extras=seat == extra)
        close_viewer(page)


def drive(page: Any, cap: int = 800) -> bool:
    for _ in range(cap):
        if page.evaluate(READY_JS):
            return True
        if page.evaluate("state.summary.finished"):
            return False
        take_step(page)
    return False


def main() -> None:
    with server() as (base, log_path):
        with chrome() as browser:
            context, page, rec = open_context(browser, "deck-pool", LAPTOP_VIEWPORT)
            page.goto(base + "/")
            page.wait_for_selector("#setup-screen:not([hidden])")
            for seat in SEATS:
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
            start = page.evaluate(
                "state.view.players.map((p) => [...p.deck_pool].join(','))"
            )
            if check.ok(drive(page), "round 2 was reached with piles to look at"):
                now = page.evaluate(
                    "state.view.players.map((p) => [...p.deck_pool].join(','))"
                )
                check.ok(
                    sum(a != b for a, b in zip(start, now, strict=True)) >= 2,
                    "the pools differ from the starting decks",
                    (start, now),
                )
                for lang in ("ko", "en"):
                    if page.evaluate("TERM_LANGUAGE") != lang:
                        page.click("#language-toggle")
                        page.wait_for_function(f"TERM_LANGUAGE === '{lang}'")
                    check_language(page, rec, lang)
                check.ok(
                    len(BADGES) >= 4,
                    "the pools showed x N badges (so the badge rules were looked at)",
                    BADGES,
                )
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
