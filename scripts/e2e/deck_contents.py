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

Scenario B plays a four-human game through the HTTP API and, at many
checkpoints, reads every seat's snapshot: each seat's own private block
carries a sorted deck_cards consistent with its other zones, and no other
payload (another seat's view, the seatless snapshot, the summary) carries the
key or any of that deck's cards.

E2E_SHOTS_DIR optionally names where the screenshots go ({start,mid}_deck_{ko,en}.png
and {start,mid}_zones_{ko,en}.png); otherwise a temporary folder.
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
    rect: { left: box.left, top: box.top, right: box.right, bottom: box.bottom },
    cards: [...pop.querySelectorAll('.vcard')].map((card) => ({
      instance: card.dataset.instance,
      title: card.title,
      aria: card.getAttribute('aria-label'),
      badge: card.querySelector('.vcard-badge')
        ? card.querySelector('.vcard-badge').textContent : null,
    })),
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


def create_game(page: Any, base: str) -> None:
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
    attributes = (
        stat.get_attribute("role"),
        stat.get_attribute("tabindex"),
        stat.get_attribute("title"),
        stat.get_attribute("aria-label"),
    )
    check.ok(
        attributes == ("button", "0", words["deck_button"], words["deck_button"]),
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
    expected_groups: dict[str, int] = {}
    for instance in deck_cards:
        key = group_key(instance)
        expected_groups[key] = expected_groups.get(key, 0) + 1
    shown_groups: dict[str, int] = {}
    badges_ok = True
    for card in opened["cards"]:
        key = group_key(card["instance"])
        count = expected_groups.get(key, 0)
        shown_groups[key] = shown_groups.get(key, 0) + 1
        if count > 1:
            badges_ok &= card["badge"] == f"×{count}"
            badges_ok &= card["title"].endswith(f" ×{count}")
        else:
            badges_ok &= card["badge"] is None and "×" not in card["title"]
        badges_ok &= card["aria"] == card["title"]
    check.ok(
        set(shown_groups) == set(expected_groups)
        and all(value == 1 for value in shown_groups.values()),
        f"{label} one card per distinct deck card, none missing or extra",
        (sorted(shown_groups), sorted(expected_groups)),
    )
    check.ok(
        any(count > 1 for count in expected_groups.values()),
        f"{label} the deck has copies, so grouping is exercised",
        expected_groups,
    )
    check.ok(
        badges_ok,
        f"{label} copies show xN, single cards no badge",
        opened["cards"][:3],
    )
    check.ok(
        sum(expected_groups.values()) == deck_size,
        f"{label} the xN figures add up to the deck size",
    )
    names = [re.sub(r" ×\d+$", "", card["title"]) for card in opened["cards"]]
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


def main() -> None:
    with server() as (base, log_path):
        with chrome() as browser:
            scenario_a(base, browser)
            scenario_b(base, browser)
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
