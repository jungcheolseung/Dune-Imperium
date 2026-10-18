"""E2E of card pictures on hover in the action log and the decision rows
(2026-10-11, user requests after a remote game).

A. "공개한 카드가 뭔지 이펙트가 뜨긴 하는데, 이펙트 끝난 후 활동로그에서 볼 때는
   공개한 카드가 텍스트로만 나와서 카드 확인하기가 불편해." A card the action
   log names (panels.js logEventLine / turnLine / chanceLine, the turn
   card's Leader) is now a `.card-name` span (core.js cardNameNode) that
   opens the card popover on hover, pins it on a click and closes on
   Escape, like a chip. The line's text is exactly what it was.
B. "선택지에 마우스 올리면 카드 이미지가 옆에 나오게" -- a decision row about a
   card (render.js rowCardPreview) shows that card's popover beside the
   decision column, level with the row, after the hover delay, and hides
   it when the pointer leaves; "ⓘ" still toggles the row's own detail and
   a click on the row still chooses.

One real game, the one trash_zone.py walks to its three-pile trash
decision (seed 5, base ruleset, Leader draft off, seat 0 human, three
heuristic seats; "confirm every hold; otherwise the seat's first legal
action"). By then every seat has taken a Reveal turn, so the live log holds
their `cards_revealed` lines. In Korean and English at 1600x950:

- every `cards_revealed` event of the log has its line, and that line's
  card names are spans whose words are the catalog names of the payload's
  card ids, in order (read from the catalog's own name/name_ko fields, not
  through the client's lookup);
- hovering each of those names (every card of each seat's latest Reveal
  line, the first card of every earlier one) opens the card popover in
  hover mode titled with that name and showing its picture, while the
  turn card's spotlight is on; moving off closes it; a click pins it (the
  pointer leaving keeps it), Escape closes it;
- no span carries the hidden-card marker, and the whole log's text is the
  same with every span turned back into plain text;
- every card row of the trash decision opens its card's popover beside
  the decision column (no overlap with the row list, level with the row,
  inside the window, the row's own button still the element under the
  pointer); leaving hides it; a row naming no card opens nothing; "ⓘ"
  toggles the row's detail and sends nothing.

Then a click on a hovered row sends that row's own action (and closes the
popover), and an undo brings the decision back; at 1366x768 and 1600x950 a
row's and a log name's popovers fit the window and the page does not
scroll sideways.

E2E_SHOTS_DIR optionally names where the screenshots go
(card_hover_log_ko.png, card_hover_trash_ko.png, Korean at 1600x950);
otherwise a temporary folder.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import Any

from common import (
    LAPTOP_VIEWPORT,
    SERVER_LOG_COPY,
    Check,
    chrome,
    now,
    open_context,
    server,
)
from lang import switch as switch_language
from open_mode import settled
from trash_zone import (
    THREE_ZONE_SEED,
    base_id,
    create_game_no_leader_draft,
    drive_to_zone_duplicate,
    find_three_zones,
)

check = Check()

VIEWPORT = {"width": 1600, "height": 950}
SHOTS = Path(
    os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(prefix="dune-card-hover-")
)

POPOVER_JS = """() => {
    const pop = document.getElementById('card-popover');
    const r = pop.getBoundingClientRect();
    // The card's own picture is the popover's last child image (openPopover);
    // the icons in its text lines are images too.
    const img = pop.querySelector(':scope > img');
    return {
        open: !pop.hidden,
        hover: pop.classList.contains('hover'),
        pinned: popoverPinned,
        title: pop.querySelector('.popover-title')?.textContent ?? null,
        img: img ? {src: img.getAttribute('src'), alt: img.alt,
                    complete: img.complete && img.naturalWidth > 0} : null,
        rect: {left: r.left, top: r.top, right: r.right, bottom: r.bottom},
        window: [innerWidth, innerHeight],
        pageWidth: document.documentElement.scrollWidth,
        spotlight: spotlightGroup !== null,
    };
}"""

# Each Reveal's line: the event's own card ids, in log order, and the line
# on screen that starts with the event's label (read in the page's language).
REVEAL_LINES_JS = """() => {
    window.revealLines = () => {
        const label = phraseText(EVENT_LABELS.cards_revealed) + ' — ';
        return [...document.querySelectorAll('#turn-history .logevent')]
            .filter((line) => line.textContent.startsWith(label));
    };
    const events = [];
    for (const entry of state.log.entries) {
        if (entry.type !== 'action') continue;
        for (const event of entry.events || []) {
            if (event.kind === 'cards_revealed') {
                const ids = event.payload.card_ids;
                events.push({ids: ids.filter(Boolean), player: event.payload.player});
            }
        }
    }
    return {events, lines: revealLines().map((line) => ({
        text: line.textContent,
        names: [...line.querySelectorAll('.card-name')].map((s) => s.textContent),
    }))};
}"""

# The whole log's text, with the names as spans and as plain text: a span
# must change nothing a reader or a screen reader gets.
LOG_TEXT_JS = """() => {
    const text = () => document.getElementById('turn-history').textContent;
    const count = () => document.querySelectorAll('#turn-history .card-name').length;
    const before = text();
    const spans = count();
    const real = window.cardNameNode;
    window.cardNameNode = (entry, words = entry.name) => document.createTextNode(words);
    renderLog();
    const plain = text();
    const plainSpans = count();
    window.cardNameNode = real;
    renderLog();
    return {same: before === plain, spans, plainSpans, again: text() === before,
            hidden: [...document.querySelectorAll('#turn-history .card-name')]
                .filter((s) => s.textContent === t('common.hidden')).length};
}"""

# The point to rest the pointer on for one name: its first line box (a name
# can wrap), scrolled to the middle of the log.
NAME_POINT_JS = """([line, index]) => {
    const span = revealLines()[line].querySelectorAll('.card-name')[index];
    span.scrollIntoView({block: 'center'});
    const r = span.getClientRects()[0];
    return {x: r.left + Math.min(r.width / 2, 12), y: r.top + r.height / 2,
            text: span.textContent};
}"""


def names_of(page: Any, ids: list[str]) -> list[dict[str, str] | None]:
    """The catalog's own names of card ids, in both languages (i18n.js keeps
    the English under name_en once it has put the Korean in name)."""
    names: list[dict[str, str] | None] = page.evaluate(
        """(ids) => ids.map((id) => {
            const e = state.catalog.cards[id];
            if (!e) return null;
            const en = e.name_en ?? e.name;
            return {en, ko: e.name_ko ?? en};
        })""",
        [base_id(card_id) for card_id in ids],
    )
    return names


def popover(page: Any) -> dict[str, Any]:
    info: dict[str, Any] = page.evaluate(POPOVER_JS)
    return info


def wait_images(page: Any) -> None:
    page.wait_for_function(
        "[...document.querySelectorAll('#card-popover img')].every((i) => i.complete)"
    )
    time.sleep(0.05)


def quiet_cues(page: Any) -> None:
    """Drop the card-use cues and phase banners still queued from the walk
    (effects.js): they play out one by one well after it, cover the
    screenshots, and Escape closes a Conflict's result board before a
    pinned popover (app.js), which made the Escape check flaky."""
    page.evaluate("() => { clearPlayEffects(); clearPhaseBanner(); }")


def park_pointer(page: Any) -> None:
    """Rest the pointer on the page title: no card, no row, and no popover
    over it (a pinned one takes the pointer, and what lies under it once
    Escape has closed it would get a hover of its own)."""
    box = page.locator("header h1").bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + 4, box["y"] + 4)


def inside_window(info: dict[str, Any]) -> bool:
    rect, (width, height) = info["rect"], info["window"]
    return (
        rect["left"] >= 0
        and rect["top"] >= 0
        and rect["right"] <= width
        and rect["bottom"] <= height
        and info["pageWidth"] <= width
    )


def hover_name(page: Any, line: int, index: int, expected: str) -> dict[str, Any]:
    point = page.evaluate(NAME_POINT_JS, [line, index])
    page.mouse.move(point["x"], point["y"])
    page.wait_for_function(
        """(name) => {
            const pop = document.getElementById('card-popover');
            return !pop.hidden && pop.classList.contains('hover')
                && pop.querySelector('.popover-title')?.textContent === name;
        }""",
        arg=expected,
        timeout=5000,
    )
    wait_images(page)
    return popover(page)


def check_log(page: Any, lang: str, shoot: bool) -> None:
    what = {"ko": "Korean", "en": "English"}[lang]
    print(f"[log] {what}")
    found = page.evaluate(REVEAL_LINES_JS)
    events, lines = found["events"], found["lines"]
    seats = sorted({event["player"] for event in events})
    check.ok(
        len(events) >= 4 and seats == [0, 1, 2, 3],
        f"{what}: the log holds every seat's Reveal ({len(events)} lines)",
        seats,
    )
    check.ok(
        len(lines) == len(events),
        f"{what}: one log line per Reveal",
        (len(lines), len(events)),
    )
    for number, (event, line) in enumerate(zip(events, lines, strict=False)):
        names = names_of(page, event["ids"])
        expected = [name[lang] if name else None for name in names]
        check.ok(
            None not in expected and line["names"] == expected,
            f"{what}: Reveal {number} (seat {event['player'] + 1}) names its "
            f"{len(expected)} cards as hoverable names, in order",
            (line["names"], expected),
        )
        check.ok(
            ", ".join(n for n in expected if n) in line["text"],
            f"{what}: Reveal {number}'s line still reads the names joined by ', '",
            line["text"],
        )

    text = page.evaluate(LOG_TEXT_JS)
    check.ok(
        text["same"]
        and text["again"]
        and text["spans"] > 0
        and text["plainSpans"] == 0,
        f"{what}: the log's text is the same with the names as spans "
        f"({text['spans']} of them) or as plain text",
        text,
    )
    check.ok(text["hidden"] == 0, f"{what}: no hidden card is a hoverable name")

    # Every card of each seat's latest Reveal line, and the first card of
    # every earlier one, hovered one at a time.
    latest = {event["player"]: number for number, event in enumerate(events)}
    for number, event in enumerate(events):
        for index, name in enumerate(names_of(page, event["ids"])):
            if name is None or (index and number not in latest.values()):
                continue
            shown = hover_name(page, number, index, name[lang])
            image = shown["img"]
            check.ok(
                shown["open"]
                and shown["hover"]
                and not shown["pinned"]
                and image is not None
                and image["complete"]
                and image["alt"] == name[lang],
                f"{what}: Reveal {number}, card {index}: hovering '{name[lang]}' "
                "shows its picture",
                shown,
            )
            check.ok(
                shown["spotlight"],
                f"{what}: Reveal {number}, card {index}: the turn card's spotlight"
                " is on too",
            )
            check.ok(
                inside_window(shown),
                f"{what}: Reveal {number}, card {index}: the popover fits the window",
                shown,
            )
            if shoot and number == len(events) - 1 and index == 0:
                path = SHOTS / f"card_hover_log_{lang}.png"
                page.screenshot(path=str(path))
                print(f"  screenshot: {path}")
            park_pointer(page)
            page.wait_for_function("document.getElementById('card-popover').hidden")

    # A click pins the last line's first card; the pointer leaving keeps it;
    # Escape closes it.
    quiet_cues(page)
    last = len(events) - 1
    first = names_of(page, events[last]["ids"])[0]
    assert first is not None
    point = page.evaluate(NAME_POINT_JS, [last, 0])
    page.mouse.click(point["x"], point["y"])
    park_pointer(page)
    time.sleep(0.3)
    pinned = popover(page)
    check.ok(
        pinned["open"] and pinned["pinned"] and not pinned["hover"]
        and pinned["title"] == first[lang],
        f"{what}: a click pins '{first[lang]}' and the pointer leaving keeps it",
        pinned,
    )
    page.keyboard.press("Escape")
    page.wait_for_function("document.getElementById('card-popover').hidden")
    check.ok(True, f"{what}: Escape closes the pinned card")


# The rows of the decision on screen: index, whether the row names a card
# (the action's arguments, read from state.actions, not from the row).
ROW_POINT_JS = """(index) => {
    const row = document.querySelector(`#actions .action-item[data-index="${index}"]`);
    const button = row.querySelector(':scope > button');
    button.scrollIntoView({block: 'nearest'});
    const r = button.getBoundingClientRect();
    return {x: r.left + r.width / 2, y: r.top + r.height / 2};
}"""

ROW_GEOMETRY_JS = """([index, x, y]) => {
    const row = document.querySelector(`#actions .action-item[data-index="${index}"]`);
    const list = document.getElementById('actions').getBoundingClientRect();
    const column = document.getElementById('side-main').getBoundingClientRect();
    const pop = document.getElementById('card-popover').getBoundingClientRect();
    const r = row.getBoundingClientRect();
    const under = document.elementFromPoint(x, y);
    return {
        row: {top: r.top}, list: {left: list.left, right: list.right},
        column: {left: column.left, right: column.right},
        pop: {left: pop.left, top: pop.top, right: pop.right, bottom: pop.bottom,
              height: pop.height},
        rowUnderPointer: Boolean(under && row.contains(under)),
        innerHeight,
    };
}"""


def hover_row(page: Any, index: int) -> tuple[float, float]:
    point = page.evaluate(ROW_POINT_JS, index)
    page.mouse.move(point["x"], point["y"])
    return point["x"], point["y"]


def check_row_popover(page: Any, label: str, index: int, name: str) -> None:
    x, y = hover_row(page, index)
    page.wait_for_function(
        """(name) => {
            const pop = document.getElementById('card-popover');
            return !pop.hidden && pop.classList.contains('hover')
                && pop.querySelector('.popover-title')?.textContent === name;
        }""",
        arg=name,
        timeout=5000,
    )
    wait_images(page)
    shown = popover(page)
    image = shown["img"]
    check.ok(
        image is not None and image["complete"] and image["alt"] == name,
        f"{label}: hovering the row shows '{name}' with its picture",
        shown,
    )
    geometry = page.evaluate(ROW_GEOMETRY_JS, [index, x, y])
    pop, column, list_box = geometry["pop"], geometry["column"], geometry["list"]
    beside = (
        pop["right"] <= column["left"] + 0.5 or pop["left"] >= column["right"] - 0.5
    )
    clear = (
        pop["right"] <= list_box["left"] + 0.5
        or pop["left"] >= list_box["right"] - 0.5
    )
    lowest = geometry["innerHeight"] - pop["height"] - 8
    level = max(8.0, min(geometry["row"]["top"], lowest))
    check.ok(
        beside and clear and abs(pop["top"] - level) <= 1,
        f"{label}: the popover sits beside the decision column, level with the "
        "row, off the row list",
        geometry,
    )
    check.ok(inside_window(shown), f"{label}: the popover fits the window", shown)
    check.ok(
        geometry["rowUnderPointer"],
        f"{label}: the row is still what the pointer is on",
        geometry,
    )
    park_pointer(page)
    page.wait_for_function("document.getElementById('card-popover').hidden")


def card_rows(page: Any, entries: list[dict]) -> list[tuple[int, str, str]]:
    """(index, zone, card id) of the decision's card rows on screen."""
    return [
        (entry["action"]["index"], entry["zone"], entry["cardId"])
        for entry in entries
        if page.locator(
            f"#actions .action-item[data-index='{entry['action']['index']}']"
        ).count()
    ]


def check_rows(
    page: Any, rec: Any, lang: str, entries: list[dict], shoot: bool
) -> None:
    what = {"ko": "Korean", "en": "English"}[lang]
    print(f"[rows] {what}")
    rows = card_rows(page, entries)
    check.ok(len(rows) == len(entries), f"{what}: every card row is on screen", rows)
    for index, zone, card_id in rows:
        name = names_of(page, [card_id])[0]
        assert name is not None
        check_row_popover(page, f"{what}: {zone} row {index}", index, name[lang])
    if shoot and rows:
        index, _zone, card_id = rows[0]
        name = names_of(page, [card_id])[0]
        assert name is not None
        hover_row(page, index)
        page.wait_for_function(
            "(name) => document.querySelector('#card-popover .popover-title')"
            "?.textContent === name && !document.getElementById('card-popover').hidden",
            arg=name[lang],
        )
        wait_images(page)
        path = SHOTS / f"card_hover_trash_{lang}.png"
        page.screenshot(path=str(path))
        print(f"  screenshot: {path}")
        park_pointer(page)
        page.wait_for_function("document.getElementById('card-popover').hidden")

    # A row about no card (the decline) opens nothing.
    plain = page.evaluate(
        """() => state.actions.actions
            .filter((a) => !Object.entries(a.arguments).some(([k, v]) =>
                k !== 'space_id' && typeof v === 'string' && cardEntryOf(v)))
            .map((a) => a.index)
            .filter((i) => document.querySelector(
                `#actions .action-item[data-index="${i}"]`))"""
    )
    if plain:
        hover_row(page, plain[0])
        time.sleep(0.4)
        check.ok(
            not popover(page)["open"],
            f"{what}: a row about no card ({plain[0]}) opens no popover",
        )
        park_pointer(page)
    else:
        print("  (no row about no card in this decision)")

    # "ⓘ" still toggles the row's own detail and sends nothing.
    index = rows[0][0]
    row = f"#actions .action-item[data-index='{index}']"
    info = page.locator(f"{row} > .action-info")
    detail = page.locator(f"{row} > .action-detail")
    since = now()
    info.click()
    opened = detail.is_visible()
    info.click()
    closed = not detail.is_visible()
    check.ok(
        info.count() == 1 and opened and closed,
        f"{what}: 'ⓘ' opens and closes the row's detail",
        (opened, closed),
    )
    time.sleep(0.2)
    check.ok(
        settled(page, 5) and rec.count("POST", "/actions", since) == 0,
        f"{what}: 'ⓘ' sends nothing",
    )
    park_pointer(page)


def check_click(page: Any, entries: list[dict]) -> None:
    """A click on a hovered row sends that row's action; undo restores."""
    print("[click] a hovered row still chooses")
    index, _zone, card_id = card_rows(page, entries)[-1]
    before = [a["index"] for a in page.evaluate("state.actions.actions")]
    name = names_of(page, [card_id])[0]
    assert name is not None
    lang = page.evaluate("TERM_LANGUAGE")
    hover_row(page, index)
    page.wait_for_function(
        "(name) => !document.getElementById('card-popover').hidden"
        " && document.querySelector('#card-popover .popover-title')?.textContent"
        " === name",
        arg=name[lang],
    )
    with page.expect_request(
        lambda r: r.method == "POST" and r.url.endswith("/actions")
    ) as sent:
        row = f"#actions .action-item[data-index='{index}']"
        page.locator(f"{row} > button").first.click()
    check.ok(
        sent.value.post_data_json["index"] == index,
        "a click on the hovered row sends that row's own action",
        sent.value.post_data_json,
    )
    assert settled(page, 20)
    check.ok(
        page.evaluate("document.getElementById('card-popover').hidden"),
        "the popover is gone after the click",
    )
    page.click("#decision-info .undo-row button")
    assert settled(page, 20)
    check.ok(
        [a["index"] for a in page.evaluate("state.actions.actions")] == before,
        "undo brings the same decision back",
    )
    quiet_cues(page)
    park_pointer(page)


def check_fit(page: Any, entries: list[dict], viewport: dict[str, int]) -> None:
    label = f"{viewport['width']}x{viewport['height']}"
    print(f"[fit] {label}")
    page.set_viewport_size(viewport)
    time.sleep(0.3)
    assert settled(page, 10)
    lang = page.evaluate("TERM_LANGUAGE")
    for index, zone, card_id in card_rows(page, entries)[:2]:
        name = names_of(page, [card_id])[0]
        assert name is not None
        check_row_popover(page, f"{label}: {zone} row {index}", index, name[lang])
    found = page.evaluate(REVEAL_LINES_JS)
    last = len(found["events"]) - 1
    name = names_of(page, found["events"][last]["ids"])[0]
    assert name is not None
    shown = hover_name(page, last, 0, name[lang])
    check.ok(
        inside_window(shown), f"{label}: a log name's popover fits the window", shown
    )
    park_pointer(page)
    page.wait_for_function("document.getElementById('card-popover').hidden")
    check.ok(
        page.evaluate("document.documentElement.scrollWidth <= innerWidth"),
        f"{label}: the page does not scroll sideways",
    )


def main() -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    with server() as (base, log_path), chrome() as browser:
        context, page, rec = open_context(browser, "card-hover", VIEWPORT)
        create_game_no_leader_draft(page, base, (0,), THREE_ZONE_SEED)
        entries = drive_to_zone_duplicate(page, find=find_three_zones)
        if entries is None:
            check.ok(
                False, f"seed {THREE_ZONE_SEED} reached the three-pile trash decision"
            )
            check.finish()
            return
        print(f"trash decision reached: {len(entries)} card rows")
        for lang in ("ko", "en"):
            switch_language(page, lang)
            quiet_cues(page)
            check_log(page, lang, shoot=lang == "ko")
            check_rows(page, rec, lang, entries, shoot=lang == "ko")
        check_click(page, entries)
        switch_language(page, "ko")
        for viewport in (LAPTOP_VIEWPORT, VIEWPORT):
            check_fit(page, entries, viewport)
        failed = [r for r in rec.requests if r[3] >= 400]
        check.ok(not failed, "no failed requests", failed[:5])
        check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
        context.close()
        SERVER_LOG_COPY.write_text(Path(log_path).read_text())
    check.finish()


if __name__ == "__main__":
    main()
