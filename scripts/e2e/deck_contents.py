"""E2E of the deck-contents list and the Intrigue count in the seat zones.

User decision 2026-10-05 (OQ-010 re-check principle): a seat sees which cards
its own draw deck holds, never in what order, and every seat's panel says how
many Intrigue cards that seat holds.

Scenario A drives a real seeded game (seat 0 human, three heuristic seats,
every expansion) to a state where the deck holds copies of one card, then
checks, in Korean and English at 1366x768:

- the seat panels' zone line reads hand/deck/discard/Intrigue for all four
  seats, the Intrigue figure equal to the view's intrigue_card_count (and to
  the icon stat that stays beside it), and no count is broken across lines;
- the hand strip's deck count is a keyboard-reachable button; the list it
  opens is titled "My deck - N cards (order hidden)", N equals the shown deck
  size and the server's deck_cards, the cards are the deck's multiset, copies
  grouped as xN, sorted by name (Intl.Collator), and the popover fits the
  window; Enter and Space open it, Escape closes it and leaves focus on the
  count; a click opens it, a click elsewhere closes it, and clicking a card in
  it posts no action;
- the discard pile count still opens its list, by mouse and keyboard.

Scenario A also checks the top card a card effect shows the owner
(``private.peeked_card_id``: Glowglobes, or Controlled while its choice is
up): exactly when the view names a deck card, that copy is its own entry
marked "Top" right before the rest of its card (user decision 2026-10-10,
option (나)), the list carries a second note and the count's title says the
top card is marked; nothing shows it beside the Intrigue cards, and the
decision panel pictures it exactly while Controlled's choice is offered.

Scenario B plays a four-human game through the HTTP API and, at many
checkpoints, reads every seat's snapshot: each seat's own private block
carries a sorted deck_cards consistent with its other zones, and no other
payload (another seat's view, the seatless snapshot, the summary) carries the
key or any of that deck's cards.

Scenario C edits a four-human game's view in the browser (user decision
2026-10-10, feedback item 3, and option (나) of the same day). With
Glowglobes and the top card one of N copies, in Korean and English: the top
copy is its own outlined entry badged "맨 위" / "Top" right before the other
copies' group (×(N-1), or no count for one), the list is otherwise as it was,
a single copy on top is one entry marked "Top" in its place, the second note
names Glowglobes, the count's title says the top is marked, and nothing is
left beside the Intrigue cards. Controlled's offered choice (user decision
2026-10-10, (나) and "옆에 카드 이미지도 나오지?"), with and without Glowglobes:
the top card's picture stands right above its three buttons in the decision
panel (hover shows it large, a click pins it), each button names the card in
ko and en, the strip beside the Intrigue cards is gone, the card is drawn
nowhere else, a logged step of the choice names no card and the action log is
unchanged; without Glowglobes the list's note names Controlled. It also
opens the deck list and a pile list while a card or a leader popover is
pinned and checks that a foreign render closes them (the pin used to carry
over).

E2E_SHOTS_DIR optionally names where the screenshots go ({start,mid}_deck_{ko,en}.png,
{start,mid}_zones_{ko,en}.png, top_mark_{ko,en}.png and controlled_{ko,en}.png);
otherwise a temporary folder.
"""

from __future__ import annotations

import json
import os
import random
import re
import tempfile
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

SEED = 20260924
SHOTS = Path(os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(prefix="dune-deck-"))

TEXT = {
    "ko": {
        "title": "내 카드덱 · {n}장 (순서 비공개)",
        "note": "이름순으로 보여 줍니다. 뽑는 순서와는 무관합니다.",
        "deck_button": "카드덱 구성 보기 (순서 비공개)",
        "deck_button_top": "카드덱 구성 보기 (순서 비공개, 맨 위 카드 표시)",
        "top_badge": "맨 위",
        "top_title": "카드덱 맨 위 카드",
        "top_note": (
            "맨 위로 표시한 카드는 {source} 효과로 확인한 카드덱 맨 위 카드입니다."
        ),
        "glowglobes": "발광구",
        "strip_badge": "덱 맨 위",
        # Controlled's buttons, naming the card (icons read as their words).
        "choices": {
            "put_back_top_card": "덱 맨 위 카드({card}) 되돌리기",
            "discard_top_card": "덱 맨 위 카드({card}) 버리기",
            "draw_top_card_for_solari": "솔라리 1 지불 → 덱 맨 위 카드({card}) 뽑기",
        },
        # The same steps as the log names them: no card.
        "logged": {
            "put_back_top_card": "덱 맨 위 카드 되돌리기",
            "discard_top_card": "덱 맨 위 카드 버리기",
            "draw_top_card_for_solari": "솔라리 1 지불 → 덱 맨 위 카드 뽑기",
        },
        "discard_button": "버림 더미 보기",
        "discard_title": "내 버림 더미 ({n})",
        "zones": (
            "핸드 {hand} · 카드덱 {deck} · 버림 더미 {discard} · 책략 카드 {intrigue}"
        ),
    },
    "en": {
        "title": "My deck · {n} cards (order hidden)",
        "note": "Shown by name, not in draw order.",
        "deck_button": "View deck contents (order hidden)",
        "deck_button_top": "View deck contents (order hidden, top card marked)",
        "top_badge": "Top",
        "top_title": "top card of the deck",
        "top_note": (
            "The card marked Top is the top card of the deck, seen through {source}."
        ),
        "glowglobes": "Glowglobes",
        "strip_badge": "Top of deck",
        "choices": {
            "put_back_top_card": "Put back top card of deck ({card})",
            "discard_top_card": "Discard top card of deck ({card})",
            "draw_top_card_for_solari": (
                "Pay 1 Solari -> Draw top card of deck ({card})"
            ),
        },
        "logged": {
            "put_back_top_card": "Put back top card of deck",
            "discard_top_card": "Discard top card of deck",
            "draw_top_card_for_solari": "Pay 1 Solari -> Draw top card of deck",
        },
        "discard_button": "View discard pile",
        "discard_title": "My discard pile ({n})",
        "zones": (
            "hand {hand} · deck {deck} · discard pile {discard}"
            " · Intrigue card {intrigue}"
        ),
    },
}

CARD_KEY = re.compile(
    r"^(?:player:\d+:starter:(?P<starter>.+)|(?P<shared>imperium|reserve|tleilaxu):"
    r"(?P<id>.+)):\d+$"
)

POPOVER_JS = """() => {
  const pop = document.getElementById('card-popover');
  const box = pop.getBoundingClientRect();
  const text = (selector) => {
    const node = pop.querySelector(selector);
    return node ? node.textContent : null;
  };
  return {
    hidden: pop.hidden,
    title: text('.popover-title'),
    note: text('.popover-note'),
    notes: [...pop.querySelectorAll('.popover-note')].map((node) => node.textContent),
    pinned: popoverPinned,
    rect: { left: box.left, top: box.top, right: box.right, bottom: box.bottom },
    cards: [...pop.querySelectorAll('.vcard')].map((card) => {
      const badge = card.querySelector('.vcard-badge');
      const own = card.getBoundingClientRect();
      const mark = badge ? badge.getBoundingClientRect() : null;
      return {
        instance: card.dataset.instance,
        title: card.title,
        aria: card.getAttribute('aria-label'),
        badge: badge ? badge.textContent : null,
        top: card.classList.contains('deck-top'),
        outline: getComputedStyle(card).outlineStyle,
        badgeFits: !badge || (badge.getClientRects().length === 1
          && mark.height < 20 && mark.left >= own.left - 0.5
          && mark.right <= own.right + 0.5),
      };
    }),
  };
}"""

# The deck's top card outside the list: the hand zone's old peek strip,
# gone since 2026-10-10 (user decision), for Glowglobes and Controlled alike.
STRIP_JS = """(badge) => [...document.querySelectorAll('#private-zone .vcard')]
  .filter((card) => {
    const mark = card.querySelector('.vcard-badge');
    return mark && mark.textContent === badge;
  })
  .map((card) => card.dataset.instance)"""

# Controlled's choice on the top card (rules/intrigue.py PeekTopCard).
DECK_TOP_CHOICES = ("put_back_top_card", "discard_top_card", "draw_top_card_for_solari")

# The decision panel while Controlled's choice is offered: the card pictured
# above the buttons, and each button's own label (badges left out, icons read
# as their words, as describeActionText does).
CHOICE_PANEL_JS = """(top) => {
  const box = document.getElementById('actions');
  const pictures = [...box.querySelectorAll('.deck-top-choice .vcard')];
  const items = [...box.querySelectorAll('.action-item')];
  const label = (button) => {
    const copy = button.cloneNode(true);
    for (const node of copy.querySelectorAll(
      '.irreversible-badge, .shortfall-badge, .strength-preview')) node.remove();
    for (const node of copy.querySelectorAll('.amount')) node.replaceWith(node.title);
    for (const node of copy.querySelectorAll('img')) node.replaceWith(node.alt);
    return copy.textContent.trim();
  };
  const picture = pictures[0];
  const rect = picture ? picture.getBoundingClientRect() : null;
  const first = items[0] ? items[0].getBoundingClientRect() : null;
  return {
    pictures: pictures.map((card) => ({
      instance: card.dataset.instance,
      badge: (card.querySelector('.vcard-badge') || {}).textContent || null,
      image: Boolean(card.querySelector('img') && card.querySelector('img').complete
        && card.querySelector('img').naturalWidth > 0),
      width: card.getBoundingClientRect().width,
    })),
    above: Boolean(picture && first
      && (picture.compareDocumentPosition(items[0]) & Node.DOCUMENT_POSITION_FOLLOWING)
      && rect.bottom <= first.top + 1),
    buttons: items.map((item) => ({
      action: state.actions.actions[Number(item.dataset.index)].action_id,
      text: label(item.querySelector('button')),
    })),
    elsewhere: [...document.querySelectorAll('.vcard')]
      .filter((card) => card.dataset.instance === top && !card.closest('#actions')
        && !card.closest('[hidden]'))
      .map((card) => card.parentElement.className),
  };
}"""

SEATS_JS = """() => state.view.players.map((player) => {
  const card = document.querySelector(`#seats .seat[data-seat='${player.player}']`);
  const zones = card.querySelector('.zones');
  const intrigueStat = [...card.querySelectorAll('.stats .stat')]
    .find((stat) => stat.title === phraseText('{intrigue}'));
  return {
    seat: player.player,
    zones: zones.textContent.replace(/\\s+/g, ' ').trim(),
    parts: [...zones.querySelectorAll('.zone-count')]
      .map((part) => part.getClientRects().length),
    lines: Math.round(zones.getBoundingClientRect().height /
      parseFloat(getComputedStyle(zones).lineHeight || 16)),
    hand: player.hand_size,
    deck: player.deck_size,
    discard: player.discard_pile.length,
    intrigue: player.intrigue_card_count,
    stat: intrigueStat ? intrigueStat.textContent.trim() : null,
  };
})"""

# A state to check: copies in seat 0's deck, a discard pile to list, another
# seat's Intrigue card to count. "mid" also wants the round advanced and the
# seats' Intrigue counts to differ, so the figure is not the same everywhere.
READY_JS = """(stage) => {
  const cards = state.view.private.deck_cards || [];
  const keys = cards.map((id) => id.replace(/^player:\\d+:starter:/, '')
    .replace(/:\\d+$/, ''));
  const copies = keys.some((key, index) => keys.indexOf(key) !== index);
  const seat = state.view.player;
  const counts = state.view.players.map((p) => p.intrigue_card_count);
  return copies && cards.length >= 4
    && state.view.players.some((p, i) => i !== seat && p.intrigue_card_count > 0)
    && state.view.players[seat].discard_pile.length > 0
    && (stage !== 'mid' || (state.summary.round_number >= 3
                            && new Set(counts).size > 1));
}"""


def api(
    context: Any,
    base: str,
    path: str,
    method: str = "GET",
    data: dict[str, Any] | None = None,
) -> Any:
    response = context.request.fetch(
        base + path,
        method=method,
        data=json.dumps(data) if data is not None else None,
        headers={"content-type": "application/json"} if data is not None else None,
    )
    assert response.ok, f"{method} {path}: {response.status} {response.text()[:200]}"
    return response.json()


def group_key(instance: str) -> str:
    match = CARD_KEY.match(instance)
    assert match, instance
    return match.group("starter") or f"{match.group('shared')}:{match.group('id')}"


def create_game(page: Any, base: str, humans: int = 1, seed: int = SEED) -> None:
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(
            f"#seat-selects select[data-seat='{seat}']",
            "human" if seat < humans else "heuristic",
        )
    set_rule_options(page, *RULE_OPTIONS)
    page.set_checked("#opt-leader-draft", False)
    page.fill("#opt-seed", str(seed))
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")


def drive_to(page: Any, stage: str, cap: int = 2500) -> int:
    for taken in range(cap):
        if page.evaluate(READY_JS, stage):
            return taken
        if page.evaluate("state.summary.finished"):
            break
        take_step(page)
    return -1


def popover(page: Any) -> dict[str, Any]:
    result: dict[str, Any] = page.evaluate(POPOVER_JS)
    return result


def open_deck_list(page: Any, how: str) -> dict[str, Any]:
    stat = page.locator("#private-zone .hand-counts .stat").first
    if how == "click":
        stat.click()
    else:
        stat.focus()
        page.keyboard.press(how)
    page.wait_for_function("!document.getElementById('card-popover').hidden")
    page.wait_for_function(
        "[...document.querySelectorAll('#card-popover img')].every(i => i.complete)"
    )
    return popover(page)


def check_zone_lines(page: Any, lang: str, stage: str) -> None:
    label = f"[{stage} {lang}]"
    seats = page.evaluate(SEATS_JS)
    check.ok(len(seats) == 4, f"{label} four seat panels", len(seats))
    for row in seats:
        expected = TEXT[lang]["zones"].format(**row)
        seat = row["seat"]
        check.ok(
            row["zones"] == expected,
            f"{label} seat {seat} zone line reads hand/deck/discard/Intrigue",
            (row["zones"], expected),
        )
        check.ok(
            row["stat"] == str(row["intrigue"]),
            f"{label} seat {seat} keeps its Intrigue icon stat",
            (row["stat"], row["intrigue"]),
        )
        check.ok(
            row["parts"] == [1, 1, 1, 1],
            f"{label} seat {seat} breaks the line between counts only",
            row["parts"],
        )
        check.ok(
            row["lines"] <= 2,
            f"{label} seat {seat} zone line is at most two lines",
            row["lines"],
        )
    check.ok(
        any(row["intrigue"] > 0 for row in seats),
        f"{label} some seat holds Intrigue, so the figure is not all zeros",
        [row["intrigue"] for row in seats],
    )
    fit = page.evaluate(
        "[document.getElementById('seats').scrollHeight,"
        " document.getElementById('seats').clientHeight]"
    )
    check.ok(fit[0] <= fit[1] + 1, f"{label} the four seat panels fit the column", fit)


def check_deck_list(
    page: Any, rec: Recorder, base: str, game_id: str, lang: str, stage: str
) -> None:
    words = TEXT[lang]
    label = f"[{stage} {lang}]"
    snapshot = api(page.context, base, f"/games/{game_id}/snapshot?seat=0")
    private = snapshot["view"]["private"]
    deck_cards = private["deck_cards"]
    deck_size = private["deck_size"]
    stat = page.locator("#private-zone .hand-counts .stat").first
    check.ok(
        len(deck_cards) == deck_size == int(stat.text_content().strip()),
        f"{label} the count on screen, deck_size and the server's list agree",
        (len(deck_cards), deck_size, stat.text_content()),
    )
    check.ok(
        page.evaluate("state.view.private.deck_cards") == deck_cards,
        f"{label} the client holds the server's list as sent",
    )
    check.ok(
        deck_cards == sorted(deck_cards) and len(set(deck_cards)) == len(deck_cards),
        f"{label} the server's list is sorted by card id, no card twice",
    )
    # The top card a card effect shows the owner (Glowglobes; Controlled
    # while its choice is up) is marked in the list exactly when the view
    # names it; nothing shows it beside the Intrigue cards, and the decision
    # panel pictures it exactly while Controlled's choice is offered.
    seat = snapshot["view"]["player"]
    peeked = private.get("peeked_card_id") or ""
    marked = bool(peeked) and peeked in deck_cards
    glowglobes = "glowglobes" in snapshot["view"]["players"][seat]["tech_ids"]
    offered = page.evaluate(
        "ids => Boolean(state.actions && state.actions.actions.some("
        "(a) => ids.includes(a.action_id)))",
        list(DECK_TOP_CHOICES),
    )
    print(
        f"  .. {label} glowglobes={glowglobes} peeked={peeked!r} controlled={offered}"
    )
    check.ok(
        page.evaluate("state.view.private.peeked_card_id || ''") == peeked,
        f"{label} the client holds the server's peeked card",
    )
    check.ok(
        page.evaluate(STRIP_JS, words["strip_badge"]) == [],
        f"{label} no top card beside the Intrigue cards",
        page.evaluate(STRIP_JS, words["strip_badge"]),
    )
    panel = page.evaluate(CHOICE_PANEL_JS, peeked)
    check.ok(
        [card["instance"] for card in panel["pictures"]]
        == ([peeked] if peeked and offered else []),
        f"{label} the decision panel pictures the top card only during "
        "Controlled's choice",
        panel["pictures"],
    )
    button = words["deck_button_top" if marked else "deck_button"]
    attributes = (
        stat.get_attribute("role"),
        stat.get_attribute("tabindex"),
        stat.get_attribute("title"),
        stat.get_attribute("aria-label"),
    )
    check.ok(
        attributes == ("button", "0", button, button),
        f"{label} the deck count is a labelled, focusable button",
        attributes,
    )

    opened = open_deck_list(page, "click")
    check.ok(
        opened["title"] == words["title"].format(n=deck_size),
        f"{label} the list is titled with the deck size and 'order hidden'",
        opened["title"],
    )
    check.ok(
        opened["note"] == words["note"],
        f"{label} the list says how it is ordered",
        opened["note"],
    )
    source = (
        words["glowglobes"]
        if glowglobes
        else page.evaluate("lookup('twisted_controlled', 'intrigue').name")
    )
    check.ok(
        opened["notes"]
        == [
            words["note"],
            *([words["top_note"].format(source=source)] if marked else []),
        ],
        f"{label} a second note explains the top mark exactly when it is shown",
        opened["notes"],
    )
    # The top copy is its own entry ("Top", no count) right before the rest
    # of its card, which keep their group (user decision 2026-10-10).
    top_key = group_key(peeked) if marked else None
    expected_groups: dict[str, int] = {}
    for instance in deck_cards:
        key = group_key(instance)
        expected_groups[key] = expected_groups.get(key, 0) + 1
    entries: dict[str, int] = {}
    copies_shown: dict[str, int] = {}
    badges_ok = True
    names = []
    for card in opened["cards"]:
        key = group_key(card["instance"])
        entries[key] = entries.get(key, 0) + 1
        title = card["title"]
        if card["top"]:
            badges_ok &= key == top_key and card["instance"] == peeked
            badges_ok &= card["badge"] == words["top_badge"]
            badges_ok &= title.endswith(f" · {words['top_title']}")
            title = title.removesuffix(f" · {words['top_title']}")
            badges_ok &= "×" not in title
            count = 1
        else:
            count = expected_groups.get(key, 0) - (1 if key == top_key else 0)
            badges_ok &= card["badge"] == (f"×{count}" if count > 1 else None)
            if count > 1:
                badges_ok &= title.endswith(f" ×{count}")
            else:
                badges_ok &= "×" not in title
        copies_shown[key] = copies_shown.get(key, 0) + count
        badges_ok &= card["aria"] == card["title"]
        names.append(re.sub(r" ×\d+$", "", title))
    check.ok(
        sum(card["top"] for card in opened["cards"]) == (1 if marked else 0),
        f"{label} one card is marked Top exactly when the view names the top card",
        [card for card in opened["cards"] if card["top"]],
    )
    check.ok(
        set(entries) == set(expected_groups)
        and all(
            value == (2 if key == top_key and expected_groups[key] > 1 else 1)
            for key, value in entries.items()
        ),
        f"{label} one entry per distinct deck card (the top copy apart), "
        "none missing or extra",
        (entries, expected_groups),
    )
    if marked:
        at = [card["top"] for card in opened["cards"]].index(True)
        after = opened["cards"][at + 1 : at + 2]
        check.ok(
            expected_groups[top_key] == 1
            or (bool(after) and group_key(after[0]["instance"]) == top_key),
            f"{label} the top copy stands right before the rest of its card",
            opened["cards"][at : at + 2],
        )
    check.ok(
        any(count > 1 for count in expected_groups.values()),
        f"{label} the deck has copies, so grouping is exercised",
        expected_groups,
    )
    check.ok(
        badges_ok,
        f"{label} copies show xN, the top copy Top alone, single cards no badge",
        opened["cards"][:3],
    )
    check.ok(
        copies_shown == expected_groups and sum(copies_shown.values()) == deck_size,
        f"{label} the entries add up to each card's copies and the deck size",
        (copies_shown, expected_groups),
    )
    check.ok(
        page.evaluate(
            "([names, lang]) => names.every((name, i) => i === 0"
            " || new Intl.Collator(lang).compare(names[i - 1], name) <= 0)",
            [names, lang],
        ),
        f"{label} the cards are sorted by the name on screen",
        names,
    )
    rect = opened["rect"]
    check.ok(
        rect["left"] >= 0
        and rect["top"] >= 0
        and rect["right"] <= LAPTOP_VIEWPORT["width"]
        and rect["bottom"] <= LAPTOP_VIEWPORT["height"],
        f"{label} the list fits a 1366x768 window",
        rect,
    )
    page.screenshot(path=str(SHOTS / f"{stage}_deck_{lang}.png"))
    seats_box = page.locator("#seats").bounding_box()
    if seats_box:
        page.screenshot(path=str(SHOTS / f"{stage}_zones_{lang}.png"), clip=seats_box)

    before = rec.count("POST", "/actions")
    page.locator("#card-popover .vcard").first.click()
    check.ok(
        rec.count("POST", "/actions") == before,
        f"{label} clicking a card in the list posts no action",
    )
    page.keyboard.press("Escape")
    open_deck_list(page, "click")
    page.mouse.click(5, 5)
    check.ok(popover(page)["hidden"], f"{label} a click elsewhere closes the list")

    for key in ("Enter", "Space"):
        shown = open_deck_list(page, key)
        check.ok(
            shown["title"] == words["title"].format(n=deck_size),
            f"{label} {key} opens the list",
            shown["title"],
        )
        page.keyboard.press("Escape")
        check.ok(popover(page)["hidden"], f"{label} Escape closes it")
        check.ok(
            page.evaluate(
                "document.activeElement === document.querySelector("
                "'#private-zone .hand-counts .stat')"
            ),
            f"{label} focus stays on the deck count",
        )


def check_discard_list(page: Any, lang: str, stage: str) -> None:
    words = TEXT[lang]
    label = f"[{stage} {lang}]"
    discard = page.locator("#private-zone .hand-counts .stat").nth(1)
    size = page.evaluate("state.view.players[state.view.player].discard_pile.length")
    check.ok(
        discard.get_attribute("role") == "button"
        and discard.get_attribute("title") == words["discard_button"],
        f"{label} the discard count is a button",
        discard.get_attribute("title"),
    )
    discard.focus()
    page.keyboard.press("Enter")
    page.wait_for_function("!document.getElementById('card-popover').hidden")
    opened = popover(page)
    check.ok(
        opened["title"] == words["discard_title"].format(n=size)
        and len(opened["cards"]) == size,
        f"{label} the discard list opens by keyboard with its cards",
        (opened["title"], len(opened["cards"]), size),
    )
    page.keyboard.press("Escape")
    check.ok(popover(page)["hidden"], f"{label} Escape closes the discard list")


def scenario_a(base: str, browser: Any) -> None:
    print("[A] deck list and zone line in a real game")
    context, page, rec = open_context(browser, "deck-list", LAPTOP_VIEWPORT)
    create_game(page, base)
    game_id = page.evaluate("state.gameId")
    for stage in ("start", "mid"):
        taken = drive_to(page, stage)
        if not check.ok(taken >= 0, f"[{stage}] a state to check was reached", taken):
            return
        round_number = page.evaluate("state.summary.round_number")
        print(f"  .. {stage}: after {taken} more steps, round {round_number}")
        for lang in ("ko", "en"):
            if page.evaluate("TERM_LANGUAGE") != lang:
                page.click("#language-toggle")
                page.wait_for_function(f"TERM_LANGUAGE === '{lang}'")
            check.ok(
                page.evaluate("TERM_LANGUAGE") == lang,
                f"[{stage} {lang}] the page speaks it",
            )
            check_zone_lines(page, lang, stage)
            check_deck_list(page, rec, base, game_id, lang, stage)
            check_discard_list(page, lang, stage)
    failed = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
    check.ok(not failed, "no failed requests", failed[:5])
    check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
    if check.failed:
        rec.dump()
    context.close()


def scenario_b(base: str, browser: Any) -> None:
    print("[B] no other payload carries a seat's deck (four humans, HTTP)")
    context, page, rec = open_context(browser, "deck-leak", LAPTOP_VIEWPORT)
    page.goto(base + "/")
    options = {
        "choam_module": True,
        "promo_cards": True,
        "bloodlines": True,
        "tech_module": True,
        "immortality": True,
        "go_to_11": True,
        "epic_game": True,
    }
    summary = api(
        context,
        base,
        "/games",
        "POST",
        {"seats": ["human"] * 4, "game_seed": 5, "leader_draft": False, **options},
    )
    game_id = summary["game_id"]
    rng = random.Random(5)
    checkpoints = 0
    sizes: dict[int, list[int]] = {seat: [] for seat in range(4)}
    for step in range(500):
        if step % 10 == 0:
            checkpoints += 1
            check_leak(context, base, game_id, step, sizes)
        summary = api(context, base, f"/games/{game_id}")
        if summary["finished"]:
            break
        revision = summary["revision"]
        if isinstance(summary["confirmation"], int):
            body = {"seat": summary["confirmation"], "revision": revision}
            api(context, base, f"/games/{game_id}/confirm", "POST", body)
            continue
        owner = summary["decision"]["owner"]
        listing = api(context, base, f"/games/{game_id}/seats/{owner}/actions")
        chosen = rng.choice(listing["actions"])
        body = {"seat": owner, "revision": revision, "index": chosen["index"]}
        api(context, base, f"/games/{game_id}/actions", "POST", body)
    check.ok(checkpoints >= 30, "thirty checkpoints of the leak check ran", checkpoints)
    grew = [
        seat
        for seat, series in sizes.items()
        if any(
            later > earlier for earlier, later in zip(series, series[1:], strict=False)
        )
    ]
    check.ok(
        len(grew) >= 2,
        "at least two seats' decks grew (a reshuffle) along the walk",
        sizes,
    )
    check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
    context.close()


def check_leak(
    context: Any, base: str, game_id: str, step: int, sizes: dict[int, list[int]]
) -> None:
    label = f"[B step {step}]"
    snapshots = {
        seat: api(context, base, f"/games/{game_id}/snapshot?seat={seat}")
        for seat in range(4)
    }
    seatless = api(context, base, f"/games/{game_id}/snapshot")
    summary = api(context, base, f"/games/{game_id}")
    every_deck = [
        card
        for snapshot in snapshots.values()
        for card in snapshot["view"]["private"]["deck_cards"]
    ]
    for seat, snapshot in snapshots.items():
        view = snapshot["view"]
        private = view["private"]
        deck = private["deck_cards"]
        sizes[seat].append(len(deck))
        own = view["players"][seat]
        elsewhere = {
            *private["hand"],
            *own["discard_pile"],
            *own["in_play"],
            *own["trashed"],
        }
        check.ok(
            deck == sorted(deck)
            and len(set(deck)) == len(deck)
            and len(deck) == private["deck_size"] == own["deck_size"]
            and not (set(deck) & elsewhere),
            f"{label} seat {seat}: sorted, unique, sized, and in no other zone",
            (len(deck), private["deck_size"]),
        )
        check.ok(
            "deck_cards" not in own,
            f"{label} seat {seat}: the public block has no list",
        )
        for other, other_snapshot in snapshots.items():
            if other == seat:
                continue
            text = json.dumps(other_snapshot["view"])
            leaked = [card for card in deck if card in text]
            check.ok(
                not leaked,
                f"{label} seat {other}'s view names none of seat {seat}'s deck",
                leaked[:3],
            )
    for name, payload in (("seatless snapshot", seatless), ("summary", summary)):
        text = json.dumps(payload)
        check.ok(
            "deck_cards" not in text
            and not [card for card in every_deck if card in text],
            f"{label} the {name} carries no deck list or deck card",
        )


# Scenario C: a four-human game (nothing moves unless this script acts), so
# the browser's view can be edited in place, the way table_layout.py stresses
# the hand. Seed 13 starts with the first seat's deck holding copies of a card.
TOP_SEED = 13

# The real view, kept once (with a third copy added to a card the deck holds
# twice), the deck's largest group of copies and a card with a single copy:
# the top card is put on the group's largest instance id, so the rest of the
# group keeps its representative (the smallest).
TOP_SETUP_JS = """() => {
  const key = (id) => { const ref = instanceRef(id); return `${ref.kind}:${ref.id}`; };
  const groupsOf = (cards) => {
    const groups = new Map();
    for (const id of cards) groups.set(key(id), [...(groups.get(key(id)) || []), id]);
    return groups;
  };
  if (!window.__deckTop) {
    const view = structuredClone(state.view);
    /* A third copy of a card the deck holds twice, so the copies left under
       the top keep a "×2" group. */
    const pair = [...groupsOf(view.private.deck_cards).values()]
      .find((ids) => ids.length === 2);
    if (pair) {
      const extra = pair[1].replace(/:(\d+)$/, (whole, n) => `:${Number(n) + 50}`);
      view.private.deck_cards = [...view.private.deck_cards, extra].sort();
      view.private.deck_size += 1;
      view.players[view.player].deck_size += 1;
    }
    window.__deckTop = { real: state.view, view, actions: state.actions };
  }
  const groups = groupsOf(window.__deckTop.view.private.deck_cards);
  const group = [...groups.values()].sort((a, b) => b.length - a.length)[0];
  if (!group || group.length < 2) return null;
  const ids = [...group].sort();
  const single = [...groups.values()].find((ids) => ids.length === 1);
  return { top: ids[ids.length - 1], representative: ids[0], count: ids.length,
           single: single ? single[0] : null };
}"""

# One variant of the kept view: whether the seat owns Glowglobes, the card the
# view names as the top (peeked_card_id), and whether Controlled's choice on
# it is offered (its three actions, as the seat's live actions).
TOP_VARIANT_JS = """([glowglobes, peeked, controlled]) => {
  const saved = window.__deckTop;
  state.view = structuredClone(saved.view);
  const own = state.view.players[state.view.player];
  own.tech_ids = [...(own.tech_ids || []).filter((id) => id !== 'glowglobes'),
                  ...(glowglobes ? ['glowglobes'] : [])];
  state.view.private.peeked_card_id = peeked;
  const offer = (action_id, index) => ({ index, action_id, arguments: {},
    detail: null, detail_ko: null, undoable: false });
  state.actions = controlled
    ? { actions: ['put_back_top_card', 'discard_top_card',
                  'draw_top_card_for_solari'].map(offer),
        scouts_lines: null, unavailable: null }
    : saved.actions;
  render();
}"""

TOP_RESTORE_JS = """() => {
  state.view = window.__deckTop.real;
  state.actions = window.__deckTop.actions;
  render();
}"""


def deck_stat_title(page: Any) -> str | None:
    title: str | None = page.locator(
        "#private-zone .hand-counts .stat"
    ).first.get_attribute("title")
    return title


def check_top_mark(page: Any, lang: str) -> None:
    words = TEXT[lang]
    label = f"[C {lang}]"
    group = page.evaluate(TOP_SETUP_JS)
    if not check.ok(
        group is not None, f"{label} the deck holds copies of a card (seed {TOP_SEED})"
    ):
        return
    top, representative, count = group["top"], group["representative"], group["count"]
    strip = words["strip_badge"]
    page.evaluate(
        "window.__deckTopLog = document.getElementById('action-log').innerText"
    )

    page.evaluate(TOP_VARIANT_JS, [False, "", False])
    check.ok(
        page.evaluate(STRIP_JS, strip) == []
        and deck_stat_title(page) == words["deck_button"],
        f"{label} no peek: no strip, the plain deck count title",
        deck_stat_title(page),
    )
    plain = open_deck_list(page, "click")
    page.keyboard.press("Escape")
    check.ok(
        not any(card["top"] for card in plain["cards"])
        and plain["notes"] == [words["note"]],
        f"{label} no peek: nothing marked, one note",
        plain["notes"],
    )

    page.evaluate(TOP_VARIANT_JS, [True, top, False])
    check.ok(
        page.evaluate(STRIP_JS, strip) == []
        and page.evaluate(CHOICE_PANEL_JS, top)["pictures"] == [],
        f"{label} Glowglobes alone puts no card beside the Intrigue cards"
        " nor in the decision panel",
        page.evaluate(STRIP_JS, strip),
    )
    check.ok(
        deck_stat_title(page) == words["deck_button_top"],
        f"{label} the deck count's title says the top card is marked",
        deck_stat_title(page),
    )
    marked = open_deck_list(page, "click")
    tops = [card for card in marked["cards"] if card["top"]]
    name = page.evaluate("(id) => nameOf(id)", top)
    check.ok(
        len(tops) == 1
        and tops[0]["instance"] == top
        and tops[0]["badge"] == words["top_badge"]
        and tops[0]["title"] == f"{name} · {words['top_title']}"
        and tops[0]["aria"] == tops[0]["title"]
        and tops[0]["outline"] == "solid"
        and tops[0]["badgeFits"],
        f"{label} the top copy is its own entry marked '{words['top_badge']}', "
        "outlined, badge on one line",
        tops,
    )
    rest = count - 1
    at = [card["instance"] for card in marked["cards"]].index(top)
    following = marked["cards"][at + 1] if at + 1 < len(marked["cards"]) else {}
    check.ok(
        following.get("instance") == representative
        and following.get("badge") == (f"×{rest}" if rest > 1 else None)
        and following.get("title") == (f"{name} ×{rest}" if rest > 1 else name)
        and not following.get("top"),
        f"{label} the other {rest} copies follow it as their own group"
        f" ({'×' + str(rest) if rest > 1 else 'no count'})",
        following,
    )
    plain_order = [card["instance"] for card in plain["cards"]]
    at_plain = plain_order.index(representative)
    check.ok(
        [card["instance"] for card in marked["cards"]]
        == [*plain_order[:at_plain], top, *plain_order[at_plain:]]
        and marked["title"] == plain["title"],
        f"{label} the split adds the top entry before its card and leaves the rest"
        " of the list as it was",
    )
    check.ok(
        marked["notes"]
        == [words["note"], words["top_note"].format(source=words["glowglobes"])],
        f"{label} a second note says the mark is the top card seen through Glowglobes",
        marked["notes"],
    )
    page.screenshot(path=str(SHOTS / f"top_mark_{lang}.png"))
    page.keyboard.press("Escape")

    # A card with one copy: its one entry is the top, with no group after it.
    single = group["single"]
    if check.ok(single is not None, f"{label} the deck holds a single copy too"):
        page.evaluate(TOP_VARIANT_JS, [True, single, False])
        alone = open_deck_list(page, "click")
        page.keyboard.press("Escape")
        name = page.evaluate("(id) => nameOf(id)", single)
        entries = [
            card
            for card in alone["cards"]
            if group_key(card["instance"]) == group_key(single)
        ]
        check.ok(
            [card["instance"] for card in alone["cards"]]
            == [card["instance"] for card in plain["cards"]]
            and len(entries) == 1
            and entries[0]["top"]
            and entries[0]["badge"] == words["top_badge"]
            and entries[0]["title"] == f"{name} · {words['top_title']}",
            f"{label} a single copy on top is one entry marked "
            f"'{words['top_badge']}' in its place",
            entries,
        )

    page.evaluate(TOP_VARIANT_JS, [True, top, True])
    check_controlled_panel(page, lang, top, "with Glowglobes")
    during = open_deck_list(page, "click")
    page.keyboard.press("Escape")
    check.ok(
        [card["instance"] for card in during["cards"] if card["top"]] == [top],
        f"{label} the list keeps its mark during Controlled's choice",
    )

    page.evaluate(TOP_VARIANT_JS, [False, top, True])
    controlled = page.evaluate("lookup('twisted_controlled', 'intrigue').name")
    check_controlled_panel(page, lang, top, "without Glowglobes")
    page.screenshot(path=str(SHOTS / f"controlled_{lang}.png"))
    shown = open_deck_list(page, "click")
    page.keyboard.press("Escape")
    check.ok(
        shown["notes"] == [words["note"], words["top_note"].format(source=controlled)],
        f"{label} without Glowglobes the note names Controlled",
        shown["notes"],
    )
    page.evaluate(TOP_RESTORE_JS)


def check_controlled_panel(page: Any, lang: str, top: str, case: str) -> None:
    """Controlled's offered choice (user decision 2026-10-10, (나) and "옆에
    카드 이미지도 나오지?"): the top card's picture right above the three
    buttons, each naming the card; the strip beside the Intrigue cards is
    gone; the card is drawn nowhere else, and a logged step of the same
    choice names no card."""

    words = TEXT[lang]
    label = f"[C {lang} Controlled, {case}]"
    name = page.evaluate("(id) => nameOf(id)", top)
    panel = page.evaluate(CHOICE_PANEL_JS, top)
    pictures = panel["pictures"]
    check.ok(
        len(pictures) == 1
        and pictures[0]["instance"] == top
        and pictures[0]["badge"] == words["strip_badge"]
        and pictures[0]["image"]
        and pictures[0]["width"] >= 80,
        f"{label} the top card's picture is in the decision panel",
        pictures,
    )
    check.ok(panel["above"], f"{label} the picture stands above the buttons")
    want = [
        {"action": action, "text": words["choices"][action].format(card=name)}
        for action in DECK_TOP_CHOICES
    ]
    check.ok(
        panel["buttons"] == want,
        f"{label} each button names the card ({name})",
        panel["buttons"],
    )
    check.ok(
        page.evaluate(STRIP_JS, words["strip_badge"]) == [] and not panel["elsewhere"],
        f"{label} no strip beside the Intrigue cards, the card nowhere else",
        (page.evaluate(STRIP_JS, words["strip_badge"]), panel["elsewhere"]),
    )
    logged = page.evaluate(
        """(ids) => ids.map((action_id) => describeActionText(
          { type: 'action', action_id, actor: state.view.player, arguments: {},
            events: [] }))""",
        list(DECK_TOP_CHOICES),
    )
    check.ok(
        logged == [words["logged"][action] for action in DECK_TOP_CHOICES]
        and not any(name in text for text in logged),
        f"{label} a logged step of the choice names no card",
        logged,
    )
    log_text = page.evaluate("document.getElementById('action-log').innerText")
    check.ok(
        log_text == page.evaluate("window.__deckTopLog"),
        f"{label} the action log is as it was",
    )
    picture = page.locator("#actions .deck-top-choice .vcard").first
    picture.hover()
    page.wait_for_function(
        "!document.getElementById('card-popover').hidden"
        " && document.getElementById('card-popover').classList.contains('hover')"
    )
    hovered = popover(page)
    picture.click()
    clicked = popover(page)
    check.ok(
        hovered["title"] == name and clicked["title"] == name and clicked["pinned"],
        f"{label} hover shows the card large, a click pins it",
        (hovered["title"], clicked["title"], clicked["pinned"]),
    )
    page.keyboard.press("Escape")
    page.mouse.move(5, 5)


def check_stale_pin(page: Any) -> None:
    """A list opened while another popover is pinned is not pinned itself:
    the opener's click never reaches the document's click-elsewhere close,
    so the old pin used to carry over and keep the list (and its top mark)
    open, unrefreshed, through every foreign update."""

    label = "[C pin]"
    title = TEXT[page.evaluate("TERM_LANGUAGE")]["title"].format(
        n=page.evaluate("state.view.private.deck_size")
    )
    pins = {
        "a card": """() => {
          const card = document.querySelector('#private-zone .hand-cards .vcard');
          pinPopover(entryOf(card.dataset.instance), card);
          return popoverPinned;
        }""",
        "a leader": """() => {
          const seat = state.view.players.find(
            (p) => p.player !== state.view.player);
          const anchor = document.querySelector(
            `.seat[data-seat="${seat.player}"] .leader-name`);
          const leader = lookup(seat.leader_face_id || seat.leader_id, 'leaders');
          pinPopover(leader, anchor, seat);
          return popoverPinned && pinnedLeaderSeat === seat.player;
        }""",
    }
    opens = {
        "deck list": (
            "document.querySelector('#private-zone .hand-counts .stat').click()"
        ),
        "pile list": (
            "openPileList(t('panels.my_discard'), state.view.private.hand,"
            " document.querySelector('#private-zone .hand-counts .stat'))"
        ),
    }
    for pin_name, pin_js in pins.items():
        for list_name, open_js in opens.items():
            page.keyboard.press("Escape")
            where = f"{label} {list_name} over {pin_name}"
            if not check.ok(
                page.evaluate(pin_js), f"{where}: the popover is pinned first"
            ):
                continue
            page.evaluate(open_js)
            opened = popover(page)
            check.ok(
                not opened["hidden"]
                and not opened["pinned"]
                and page.evaluate("pinnedLeaderSeat === null")
                and (list_name != "deck list" or opened["title"] == title),
                f"{where}: the list opens unpinned",
                (opened["title"], opened["pinned"]),
            )
            page.evaluate("render({ foreign: true })")
            check.ok(
                popover(page)["hidden"],
                f"{where}: a foreign update closes it",
                popover(page)["title"],
            )


def scenario_c(base: str, browser: Any) -> None:
    print("[C] the deck list's top card mark and a stale pin (view edits, four humans)")
    context, page, rec = open_context(browser, "deck-top", LAPTOP_VIEWPORT)
    create_game(page, base, humans=4, seed=TOP_SEED)
    posts = rec.count("POST", "/actions")
    check_stale_pin(page)
    for lang in ("ko", "en"):
        if page.evaluate("TERM_LANGUAGE") != lang:
            page.click("#language-toggle")
            page.wait_for_function(f"TERM_LANGUAGE === '{lang}'")
        check_top_mark(page, lang)
    check.ok(
        rec.count("POST", "/actions") == posts, "[C] the view edits post no action"
    )
    failed = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
    check.ok(not failed, "[C] no failed requests", failed[:5])
    check.ok(not rec.js_errors, "[C] no JS exceptions", rec.js_errors[:5])
    if check.failed:
        rec.dump()
    context.close()


def main() -> None:
    with server() as (base, log_path):
        with chrome() as browser:
            scenario_a(base, browser)
            scenario_b(base, browser)
            scenario_c(base, browser)
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
