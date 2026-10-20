"""E2E of the seat panels folding their detail away.

Four panels of everything do not fit the column they live in. Measured on an
all-expansion game before this: the four cards came to 1,678px mid-game and
2,189px late against 751px of room, so the fourth seat was always below the
fold and the card lines — Battle, In play, Tech, Contracts — were most of the
weight.

Board-visible Influence, garrison, Conflict forces, strength and Bene Tleilax
track positions are absent from the panel; troop supply is absent too. Specimens
remain as an icon count. Head, compact stats and the zone counts stay. The rest
folds, and the fold still says what it is holding rather than going blank. `s`
folds or opens all four, and the choice is remembered per browser.

The one supply count of Sardaukar Commanders is the exception (2026-10-10,
user request): the board draws the garrison and Conflict ones but nothing on
it shows those back in the supply after a Combat [Bloodlines p. 4], and the
supply is public [Main p. 5]. A Bloodlines game shows it beside the Spies,
0 included, as the rulebook figure (`catalog.commander_token`) or a drawn
"C" without it; a game without Bloodlines does not.

The holder of the First Player marker shows the app's token beside its
name (`catalog.first_player_token`), or the text badge without the picture;
a review step marks that step's holder, not the game's last one.

Also guards the last English line in the panel: the zone counts used to read
`hand 5 · deck 5 · discard 0`, which the label de-mixing never reached
because it is built by concatenation rather than from a label table.
"""

from __future__ import annotations

import re

from common import (
    LAPTOP_VIEWPORT,
    REVIEW_LANDING,
    SERVER_LOG_COPY,
    Check,
    chrome,
    open_context,
    server,
)
from open_mode import settled

check = Check()

SEED = 7
EXPANSIONS = ("choam", "bloodlines", "tech", "immortality", "promo")

SEATS = """() => {
    const wrap = document.getElementById('seats');
    return {
        client: wrap.clientHeight,
        scroll: wrap.scrollHeight,
        cards: [...wrap.children].map((c) => ({
            height: c.getBoundingClientRect().height,
            hasMore: !!c.querySelector('.seat-more'),
            expanded: c.querySelector('.seat-more')
                ? c.querySelector('.seat-more').getAttribute('aria-expanded') : null,
            summary: c.querySelector('.seat-more')
                ? c.querySelector('.seat-more').textContent : '',
            detailShown: !!c.querySelector('.seat-detail:not([hidden])'),
            zones: c.querySelector('.zones')
                ? c.querySelector('.zones').textContent : '',
        })),
    };
}"""


def watched_game(page, base: str) -> None:
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    page.wait_for_selector("#seat-selects select")
    setup_labels = page.locator("#seat-selects label > span").all_text_contents()
    check.ok(
        setup_labels == ["플레이어1", "플레이어2", "플레이어3", "플레이어4"],
        "setup displays seats 1 through 4",
        setup_labels,
    )
    for seat in range(4):
        page.select_option(f"#seat-selects select[data-seat='{seat}']", "heuristic")
    for option in EXPANSIONS:
        page.check(f"#opt-{option}")
    page.fill("#opt-seed", str(SEED))
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.review !== null && state.view !== null")
    target = page.evaluate("Math.floor(state.review.meta.step_count * 0.95)")
    page.evaluate(f"stopPlayback(); reviewSeek({target})")
    page.wait_for_function(
        f"state.review.cursor === {target} && refreshFlight === null"
    )


def check_compact_stats(page) -> None:
    """Only off-board counts remain, with Specimens promoted to an icon stat."""
    rows = page.evaluate(
        """() => state.view.players.map((player, index) => {
            const card = document.querySelectorAll('#seats article.seat')[index];
            const stats = [...card.querySelectorAll(':scope > .stats .stat')];
            const detail = card.querySelector('.seat-detail');
            const lines = [...detail.querySelectorAll(':scope > .cardline')];
            const status = lines.find((line) =>
                line.querySelector('strong')?.textContent.trim() ===
                    t('panels.status_label'));
            const specimen = stats.find((s) => s.title === phraseText('{specimen}'));
            return {
                intrigue: player.intrigue_card_count,
                intrigueShown: stats.some((s) => s.title === phraseText('{intrigue}')
                    && s.textContent.trim() === String(player.intrigue_card_count)),
                specimen: player.specimens || 0,
                specimenShown: specimen
                    ? specimen.textContent.trim() === String(player.specimens || 0)
                    : false,
                specimenImage: specimen?.querySelector('img.icon')?.getAttribute('src'),
                statTitles: stats.map((s) => s.title),
                expectedTitles: [
                    // The Victory Points open their ledger (vp_ledger.py).
                    t('panels.vp_ledger_open', { points: player.victory_points }),
                    phraseText('{spice}'),
                    phraseText('{solari}'),
                    phraseText('{water}'),
                    phraseText('{intrigue}'),
                    phraseText('{specimen}'),
                    t('panels.agent_remaining'),
                    t('panels.supply_spy'),
                    t('panels.supply_commander'),
                ],
                supplyLine: lines.some((line) =>
                    line.querySelector('strong')?.textContent.trim() ===
                        phraseText('{supply}')),
                statusText: status?.textContent || '',
                researchText: player.research_space
                    ? researchSpaceName(player.research_space, false) : '',
                tleilaxuText:
                    phraseText('{tleilaxu}') + ' ' + String(player.tleilaxu_space || 0),
            };
        })"""
    )
    missing = []
    for seat, row in enumerate(rows):
        if not row["intrigueShown"]:
            missing.append((seat, "intrigue", row["intrigue"]))
        if not row["specimenShown"] or "/icons/specimen.png" not in (
            row["specimenImage"] or ""
        ):
            missing.append(
                (seat, "specimen icon/count", row["specimen"], row["specimenImage"])
            )
        if set(row["statTitles"]) != set(row["expectedTitles"]):
            missing.append((seat, "stats", row["statTitles"]))
        if row["supplyLine"]:
            missing.append((seat, "troop supply line"))
        if row["researchText"] and row["researchText"] in row["statusText"]:
            missing.append((seat, "research track", row["statusText"]))
        if row["tleilaxuText"] in row["statusText"]:
            missing.append((seat, "Tleilaxu track", row["statusText"]))
    check.ok(
        not missing,
        "seat stats omit board-visible tracks and forces, but show specimen icons",
        missing,
    )


COMMANDER_STATS = """() => [...document.querySelectorAll('#seats article.seat')]
    .map((card) => {
        const rows = [...card.querySelectorAll(':scope > .stats')];
        const stat = card.querySelector('.stat[data-stat="commander"]');
        if (!stat) return { seat: Number(card.dataset.seat), stat: null };
        const img = stat.querySelector('img.commander-stat-icon');
        const drawn = stat.querySelector('.commander-stat-icon.drawn');
        const spy = card.querySelector('.stat[data-stat="spy"] .icon');
        const count = [...stat.childNodes]
            .filter((node) => node.nodeType === Node.TEXT_NODE)
            .map((node) => node.textContent).join('').trim();
        return {
            seat: Number(card.dataset.seat),
            stat: {
                title: stat.title,
                count,
                row: rows.findIndex((row) => row.contains(stat)),
                afterSpy: stat.previousElementSibling
                    ? stat.previousElementSibling.dataset.stat : null,
                image: img ? {
                    src: img.getAttribute('src'), alt: img.alt, title: img.title,
                    loaded: img.complete && img.naturalWidth > 0,
                    height: img.getBoundingClientRect().height,
                } : null,
                drawn: drawn ? {
                    text: drawn.textContent, title: drawn.title,
                    role: drawn.getAttribute('role'),
                    aria: drawn.getAttribute('aria-label'),
                    height: drawn.getBoundingClientRect().height,
                    width: drawn.getBoundingClientRect().width,
                } : null,
                spyHeight: spy ? spy.getBoundingClientRect().height : null,
            },
        };
    })"""


def check_supply_commanders(page, label: str) -> None:
    """Each seat's Sardaukar Commanders in its supply, in a Bloodlines game.

    "각 플레이어의 남은 개인 구성물은 다른 모든 플레이어가 명확히 볼 수
    있는 supply에 둔다." (docs/rules/information-visibility.md, [Main p. 5]);
    "Combat이 해결되고 보상이 지급되면 Commander는 소유자의 supply로
    돌아간다." (docs/rules/bloodlines.md, [Bloodlines p. 4]). Display only:
    the count is ``players[i].commanders_supply`` of every seat's view.
    """
    # A language switch in review re-fetches the step (redrawForLanguage's
    # reviewSeek); a value injected before it lands would be overwritten.
    page.wait_for_function("!state.review || !state.review.seek")
    page.wait_for_function(
        "[...document.querySelectorAll('#seats img')].every((i) => i.complete)"
    )
    name = page.evaluate("t('panels.supply_commander')")
    url = page.evaluate("state.catalog.commander_token")
    counts = page.evaluate(
        "state.view.players.map((player) => String(player.commanders_supply || 0))"
    )
    rows = page.evaluate(COMMANDER_STATS)
    wrong = [
        row
        for row, count in zip(rows, counts, strict=True)
        if not row["stat"]
        or row["stat"]["title"] != name
        or row["stat"]["count"] != count
        or row["stat"]["row"] != 1
        or row["stat"]["afterSpy"] != "spy"
    ]
    check.ok(
        len(rows) == 4 and not wrong,
        f"{label}: each seat counts supply Commanders beside its Spies ({name!r})",
        wrong or rows,
    )
    check.ok(
        bool(url)
        and all(
            row["stat"]["image"]
            and row["stat"]["image"]["src"] == url
            and row["stat"]["image"]["loaded"]
            and row["stat"]["image"]["alt"] == row["stat"]["image"]["title"] == name
            and row["stat"]["spyHeight"]
            and abs(row["stat"]["image"]["height"] - row["stat"]["spyHeight"]) < 1
            and row["stat"]["drawn"] is None
            for row in rows
        ),
        f"{label}: the stat is the rulebook's Commander figure at a stat icon's height",
        [(url, row["stat"]) for row in rows[:1]],
    )

    # Seed 7 has no Commander in any supply at this step: inject one.
    page.evaluate(
        "state.keptCommanders = state.view.players[1].commanders_supply;"
        " state.view.players[1].commanders_supply = 2; renderSeats();"
    )
    injected = page.evaluate(COMMANDER_STATS)
    check.ok(
        injected[1]["stat"]
        and injected[1]["stat"]["count"] == "2"
        and [row["stat"]["count"] for row in injected[:1] + injected[2:]]
        == counts[:1] + counts[2:],
        f"{label}: two Commanders in seat 2's supply read 2 there only",
        [row["stat"] and row["stat"]["count"] for row in injected],
    )

    # Without the picture: the drawn mark, named the same, at the same height.
    page.evaluate(
        "state.commanderUrl = state.catalog.commander_token;"
        " state.catalog.commander_token = null; renderSeats();"
    )
    drawn = page.evaluate(COMMANDER_STATS)[1]["stat"]
    check.ok(
        drawn
        and drawn["image"] is None
        and drawn["drawn"]
        and drawn["drawn"]["text"] == "C"
        and drawn["drawn"]["title"] == drawn["drawn"]["aria"] == name
        and drawn["drawn"]["role"] == "img"
        and drawn["count"] == "2"
        and drawn["spyHeight"]
        and abs(drawn["drawn"]["height"] - drawn["spyHeight"]) < 1.5
        and drawn["drawn"]["width"] < drawn["drawn"]["height"],
        f"{label}: without the picture, a drawn C mark of the same height",
        drawn,
    )
    page.evaluate(
        "state.catalog.commander_token = state.commanderUrl;"
        " delete state.commanderUrl; renderSeats();"
    )

    # A game without Bloodlines has no Commanders to count.
    page.evaluate("state.summary.bloodlines = false; renderSeats();")
    absent = page.evaluate(COMMANDER_STATS)
    check.ok(
        all(row["stat"] is None for row in absent),
        f"{label}: no Commander stat without Bloodlines",
        absent,
    )
    page.evaluate(
        "state.summary.bloodlines = true;"
        " state.view.players[1].commanders_supply = state.keptCommanders;"
        " delete state.keptCommanders; renderSeats();"
    )
    restored = page.evaluate(COMMANDER_STATS)
    check.ok(
        [row["stat"] and row["stat"]["count"] for row in restored] == counts,
        f"{label}: the stat returns with the real counts",
        [row["stat"] and row["stat"]["count"] for row in restored],
    )


def check_number_badges(page, label: str) -> None:
    marks = page.eval_on_selector_all(
        "#seats .who-name > .seat-mark",
        """nodes => nodes.map(n => {
            const b = n.getBoundingClientRect();
            const r = document.createRange();
            r.selectNodeContents(n);
            const text = r.getBoundingClientRect();
            return { number: n.textContent, width: b.width, height: b.height,
                textCentre: (text.left + text.right) / 2,
                centre: (b.left + b.right) / 2 };
        })""",
    )
    check.ok(
        len(marks) == 4
        and all(abs(m["width"] - m["height"]) < 0.1 for m in marks)
        and all(m["width"] >= 12 for m in marks)
        and max(m["width"] for m in marks) - min(m["width"] for m in marks) < 0.1,
        f"{label}: four readable circles of the same size beside the Leader names",
        marks,
    )
    check.ok(
        all(abs(m["textCentre"] - m["centre"]) < 0.5 for m in marks),
        f"{label}: the numbers are centred inside their circles",
        marks,
    )


FIRST_PLAYER_MARKS = """() => [...document.querySelectorAll('#seats article.seat')]
    .map((card) => {
        const token = card.querySelector('.who img.first-player-token');
        const badges = [...card.querySelectorAll('.who .badge')]
            .filter((b) => b.textContent === t('panels.first_badge'));
        return {
            seat: Number(card.dataset.seat),
            token: token ? {
                src: token.getAttribute('src'), alt: token.alt, title: token.title,
                loaded: token.complete && token.naturalWidth > 0,
                height: token.getBoundingClientRect().height,
            } : null,
            badges: badges.map((b) => b.title),
        };
    })"""


def check_first_player(page, label: str) -> None:
    """The First Player marker beside its holder's name [Main p. 5]: the
    app's token where the assets have it (catalog.first_player_token), the
    text badge without it, named by the glossary's term either way."""
    page.wait_for_function(
        "[...document.querySelectorAll('#seats img')].every((i) => i.complete)"
    )
    holder = page.evaluate(
        "state.review ? state.view.first_player : state.summary.first_player"
    )
    name = page.evaluate("phraseText('{first_player}')")
    url = page.evaluate("state.catalog.first_player_token")
    marks = page.evaluate(FIRST_PLAYER_MARKS)
    marked = [m["seat"] for m in marks if m["token"] or m["badges"]]
    check.ok(marked == [holder], f"{label}: only the holder's seat is marked", marks)
    mine = next((m for m in marks if m["seat"] == holder), None)
    if url:
        token = mine and mine["token"]
        check.ok(
            bool(token)
            and token["src"] == url
            and token["loaded"]
            and token["alt"] == token["title"] == name
            and 14 <= token["height"] <= 30
            and not mine["badges"],
            f"{label}: the app's First Player token, named {name!r}",
            mine,
        )
    page.evaluate(
        "state.firstPlayerUrl = state.catalog.first_player_token;"
        " state.catalog.first_player_token = null; render();"
    )
    mine = next(m for m in page.evaluate(FIRST_PLAYER_MARKS) if m["seat"] == holder)
    check.ok(
        mine["token"] is None and mine["badges"] == [name],
        f"{label}: without the picture, the text badge named {name!r}",
        mine,
    )
    page.evaluate(
        "state.catalog.first_player_token = state.firstPlayerUrl;"
        " delete state.firstPlayerUrl; render();"
    )


def check_first_player_in_review(page) -> None:
    """A review step marks the seat that held the First Player marker at
    that step (``view.first_player``), not the game's last holder in the
    summary: the marker passes clockwise in every Recall [Main p. 15]."""
    final = page.evaluate("state.summary.first_player")
    held = final
    for fraction in (0.5, 0.35, 0.65, 0.2, 0.8):
        seek(page, fraction)
        held = page.evaluate("state.view.first_player")
        if held != final:
            break
    marks = page.evaluate(FIRST_PLAYER_MARKS)
    marked = [m["seat"] for m in marks if m["token"] or m["badges"]]
    check.ok(
        held != final and marked == [held],
        "review: the step's holder carries the First Player marker, not the last one",
        {"step holder": held, "last holder": final, "marks": marks},
    )
    seek(page, 0.95)


def run(base: str, browser) -> None:
    context, page, rec = open_context(browser, "seats")
    watched_game(page, base)

    marks = page.locator("#seats .seat-mark").all_text_contents()
    check.ok(marks == ["1", "2", "3", "4"], "seat badges display 1 through 4", marks)
    for language, prefix in (("ko", "플레이어"), ("en", "Player ")):
        page.evaluate("setLanguage", language)
        check_number_badges(page, f"{language} desktop")
        numbers = page.evaluate("""() => ({
            marks: [...document.querySelectorAll('#seats .seat-mark')].map(e => ({
                id: e.dataset.seat, title: e.title, aria: e.getAttribute('aria-label'),
            })),
            review: [...document.querySelectorAll('#review-seat option')].map(e => ({
                id: e.value, label: e.textContent,
            })),
        })""")
        check.ok(
            all(
                mark["id"] == str(seat)
                and mark["title"] == mark["aria"] == f"{prefix}{seat + 1}"
                for seat, mark in enumerate(numbers["marks"])
            ),
            f"{language}: badges use visible seat numbers and stable IDs",
            numbers["marks"],
        )
        check.ok(
            len(numbers["review"]) == 4
            and all(
                option["id"] == str(seat)
                and option["label"].startswith(f"{prefix}{seat + 1}")
                for seat, option in enumerate(numbers["review"])
            ),
            f"{language}: review seat choices display 1 through 4 with original values",
            numbers["review"],
        )
        check_first_player(page, language)
        check_supply_commanders(page, language)
    page.evaluate("setLanguage('ko')")
    check_first_player_in_review(page)

    folded = page.evaluate(SEATS)
    check.ok(len(folded["cards"]) == 4, "four seat panels", len(folded["cards"]))
    check.ok(
        all(c["hasMore"] for c in folded["cards"]),
        "every seat offers its detail",
        [i for i, c in enumerate(folded["cards"]) if not c["hasMore"]],
    )
    check.ok(
        all(c["expanded"] == "false" for c in folded["cards"]),
        "seats start folded",
        [c["expanded"] for c in folded["cards"]],
    )
    check.ok(
        not any(c["detailShown"] for c in folded["cards"]),
        "a folded seat's card lines are hidden",
    )
    # A fold that says nothing would be worse than the scroll it replaces.
    check.ok(
        all(len(c["summary"]) > len("자세히 ▸ · ") for c in folded["cards"]),
        "a folded seat names what it is holding",
        [c["summary"][:40] for c in folded["cards"]],
    )

    # The zone counts must speak the same language as the rest.
    english = [
        c["zones"]
        for c in folded["cards"]
        if any(word in c["zones"] for word in ("hand", "deck", "discard", "supply"))
    ]
    check.ok(not english, "the zone counts are not left in English", english[:2])

    # The zone counts are clickable when a seat has a deck pool or a discard
    # pile, opening a viewer whose discard title used to concatenate
    # `${t("common.seat", {seat})} discard` (ITEM 8f, 2026-09-25): fixed English
    # word next to a Korean seat label. watched_game's game is all-heuristic in
    # review, so this browser plays no seat (mySeats() == []); every title here
    # must read "seat N's ...", never "my ..." -- crediting an AI seat's pile
    # to this browser just because it is the one under review was the fix's own
    # regression (reviewer-found blocker, 2026-09-25). Since 2026-10-13 the
    # viewer shows the seat's deck pool first and its discard pile after it
    # (deck_pool.py checks the lists themselves).
    my_seats = page.evaluate("mySeats()")
    check.ok(not my_seats, "watched_game is spectating, no seats of its own", my_seats)
    discard_seats = page.evaluate(
        "[...document.querySelectorAll('#seats .seat')]"
        ".map((c, i) => (c.querySelector('.zones.clickable') ? i : -1))"
        ".filter((i) => i >= 0)"
    )
    check.ok(discard_seats, "some seat has a pile to click", discard_seats)
    titles = {}
    for seat in discard_seats:
        page.click(f"#seats article.seat[data-seat='{seat}'] .zones")
        page.wait_for_selector("#pile-viewer:not([hidden]) .popover-title")
        titles[seat] = page.evaluate(
            "[document.getElementById('pile-viewer-title').textContent,"
            " ...[...document.querySelectorAll('#pile-viewer-body > .popover-title')]"
            ".map((n) => n.textContent)]"
        )
        page.keyboard.press("Escape")
    latin = {
        seat: found
        for seat, found in titles.items()
        if any(re.search(r"[A-Za-z]", title) for title in found)
    }
    check.ok(not latin, "no seat's pile popover title has Latin letters", latin)
    expected = {
        # pileListContent appends " (<count>)" itself (panels.js); a seat with
        # no pool or no discard pile has no such section.
        seat: page.evaluate(
            "(seat) => { const p = state.view.players.find((q) => q.player === seat);"
            " const seatLabel = t('common.seat', { seat });"
            " return [...(p.deck_pool.length ? [t('panels.seat_deck_pool',"
            " { seat: seatLabel, count: p.deck_pool.length })] : []),"
            " ...(p.discard_pile.length ? [t('panels.seat_discard', { seat: seatLabel })"
            " + ` (${p.discard_pile.length})`] : [])]; }",
            seat,
        )
        for seat in discard_seats
    }
    check.ok(
        titles == expected,
        "an all-AI review never calls a seat's pile 'my ...'",
        {
            s: (titles[s], expected[s])
            for s in discard_seats
            if titles[s] != expected[s]
        },
    )

    # The point of folding: all four seats in the column at 1600x1000, late in
    # an every-expansion game. They took 986px of 751 before the rows were
    # tightened (a wrapping name, "Commander 0/1", a two-row zone line).
    check.ok(
        folded["scroll"] <= folded["client"],
        "all four folded seats fit the column",
        (folded["scroll"], folded["client"]),
    )
    # A tall screen keeps the Leader pictures; only short ones give them up.
    shown = page.evaluate(
        "[...document.querySelectorAll('#seats .leader-thumb')]"
        ".filter((img) => getComputedStyle(img).display !== 'none').length"
    )
    check.ok(shown == 4, "1600x1000 keeps the four Leader pictures", shown)
    check_compact_stats(page)

    # Open one seat: only that one grows.
    page.click("#seats article.seat[data-seat='1'] .seat-more")
    one = page.evaluate(SEATS)
    check.ok(one["cards"][1]["expanded"] == "true", "the clicked seat opened")
    check.ok(one["cards"][1]["detailShown"], "its card lines are shown")
    check.ok(
        sum(1 for c in one["cards"] if c["detailShown"]) == 1,
        "opening one seat leaves the others folded",
        [i for i, c in enumerate(one["cards"]) if c["detailShown"]],
    )
    check.ok(
        one["cards"][1]["height"] > folded["cards"][1]["height"],
        "the opened seat is taller than it was",
        (folded["cards"][1]["height"], one["cards"][1]["height"]),
    )

    # #seats is rebuilt by every render, so the choice must live outside it.
    page.evaluate("render({ foreign: true })")
    after = page.evaluate(SEATS)
    check.ok(
        after["cards"][1]["expanded"] == "true",
        "the choice survives another seat moving",
    )

    # `s` opens them all, and that is what the fold is buying.
    page.keyboard.press("s")
    opened = page.evaluate(SEATS)
    check.ok(
        all(c["expanded"] == "true" for c in opened["cards"]),
        "s opens every seat",
        [c["expanded"] for c in opened["cards"]],
    )
    check.ok(
        opened["scroll"] > folded["scroll"],
        "folding really is what keeps the column short",
        (folded["scroll"], opened["scroll"]),
    )
    print(
        f"  .. column holds {folded['scroll']:.0f}px folded"
        f" vs {opened['scroll']:.0f}px open, in {folded['client']:.0f}px of room"
    )
    page.keyboard.press("s")
    check.ok(
        all(c["expanded"] == "false" for c in page.evaluate(SEATS)["cards"]),
        "s again folds every seat",
    )

    # Remembered across a reload.
    page.click("#seats article.seat[data-seat='2'] .seat-more")
    page.reload()
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    reloaded = page.evaluate(SEATS)
    check.ok(
        [c["expanded"] for c in reloaded["cards"]]
        == ["false", "false", "true", "false"],
        "the opened seat is remembered across a reload",
        [c["expanded"] for c in reloaded["cards"]],
    )

    bad = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
    check.ok(not bad, "no failed requests", bad[:3])
    check.ok(not rec.js_errors, "no JS errors", rec.js_errors[:3])
    if check.failed:
        rec.dump()
    context.close()


def seek(page, fraction: float) -> None:
    target = page.evaluate(f"Math.floor(state.review.meta.step_count * {fraction})")
    landing = page.evaluate(REVIEW_LANDING, target)
    page.evaluate(f"stopPlayback(); reviewSeek({target})")
    page.wait_for_function(
        f"state.review.cursor === {landing} && refreshFlight === null"
    )


FOLD_GEOMETRY = """() => [...document.querySelectorAll('#seats .seat')].map((card) => {
    const more = card.querySelector('.seat-more').getBoundingClientRect();
    const head = card.querySelector('.seat-head').getBoundingClientRect();
    return {
        width: Math.round(more.width),
        onHeadLine: more.top < head.bottom && more.bottom > head.top,
        name: card.querySelector('.leader-name').textContent,
    };
})"""


def run_laptop(base: str, browser) -> None:
    """A 1366x768 laptop: the column is 519-652px tall (it loses a row when the
    hand takes two lines) and the four folded seats took 703-738px of it at
    every point of this game. The short-screen layout (style.css, max-height:
    960px) drops the Leader picture and puts the fold on the head's line."""
    context, page, rec = open_context(browser, "seats-laptop", LAPTOP_VIEWPORT)
    watched_game(page, base)
    for fraction in (0.25, 0.5, 0.75, 0.95):
        seek(page, fraction)
        check_number_badges(page, f"1366x768 at {fraction:.0%}")
        seats = page.evaluate(SEATS)
        check.ok(
            seats["scroll"] <= seats["client"],
            f"1366x768 at {fraction:.0%}: all four folded seats fit the column",
            (seats["scroll"], seats["client"]),
        )
    geometry = page.evaluate(FOLD_GEOMETRY)
    check.ok(
        all(g["width"] >= 12 and g["onHeadLine"] for g in geometry),
        "the fold is an arrow on each seat's head line, wide enough to press",
        geometry,
    )
    check.ok(
        all(g["name"].strip() for g in geometry),
        "the Leader is still named where the picture was",
        [g["name"] for g in geometry],
    )
    page.click("#seats article.seat[data-seat='0'] .seat-more")
    opened = page.evaluate(SEATS)["cards"][0]
    check.ok(
        opened["expanded"] == "true" and opened["detailShown"],
        "the arrow opens its seat",
        opened["expanded"],
    )
    page.click("#seats article.seat[data-seat='0'] .seat-more")
    check.ok(
        page.evaluate(SEATS)["cards"][0]["expanded"] == "false",
        "and folds it again",
    )
    check.ok(not rec.js_errors, "no JS errors on the laptop", rec.js_errors[:3])
    context.close()


# Each live seat's play clock (static/clock.js): last in the pieces row, on
# that row's line, and not a .stat.
CLOCK_ROW_JS = """() => [...document.querySelectorAll('#seats article.seat')].map((card) => {
    const rows = card.querySelectorAll(':scope > .stats');
    const clock = card.querySelector('.seat-clock');
    const first = rows[1] && rows[1].firstElementChild;
    const top = (node) => node.getBoundingClientRect().top;
    return {
        inPieces: Boolean(clock && rows[1] && clock.parentElement === rows[1]
            && rows[1].lastElementChild === clock),
        oneLine: Boolean(clock && first && Math.abs(top(clock) - top(first)) < 4),
        isStat: Boolean(clock && clock.classList.contains('stat')),
        text: clock ? clock.textContent : null,
    };
})"""


def run_laptop_live(base: str, browser) -> None:
    """A live game on a 1366x768 laptop: the seat clocks take no extra line,
    so the four folded seats still fit the column."""
    context, page, rec = open_context(browser, "seats-laptop-live", LAPTOP_VIEWPORT)
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(1, 4):
        page.select_option(f"#seat-selects select[data-seat='{seat}']", "heuristic")
    for option in EXPANSIONS:
        page.check(f"#opt-{option}")
    page.fill("#opt-seed", str(SEED))
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    for stretch in (0, 25, 60):
        for _ in range(stretch):
            assert settled(page, 20)
            if page.evaluate("state.summary.finished"):
                break
            page.evaluate(
                "state.summary.confirmation === state.viewSeat"
                " ? confirmTurn() : applyAction(0)"
            )
        assert settled(page, 20)
        where = f"live 1366x768, round {page.evaluate('state.summary.round_number')}"
        rows = page.evaluate(CLOCK_ROW_JS)
        check.ok(
            len(rows) == 4
            and all(r["inPieces"] and r["oneLine"] and not r["isStat"] for r in rows),
            f"{where}: each seat's clock ends its pieces row, on its line",
            rows,
        )
        seats = page.evaluate(SEATS)
        check.ok(
            seats["scroll"] <= seats["client"],
            f"{where}: all four folded seats fit the column with their clocks",
            (seats["scroll"], seats["client"]),
        )
    check_compact_stats(page)
    check.ok(not rec.js_errors, "no JS errors in the live game", rec.js_errors[:3])
    context.close()


def main() -> None:
    with server() as (base, log_path):
        with chrome() as browser:
            run(base, browser)
            print("[laptop] 1366x768")
            run_laptop(base, browser)
            print("[laptop] 1366x768, live, with the play clocks")
            run_laptop_live(base, browser)
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
