"""E2E of the seat panels folding their detail away.

Four panels of everything do not fit the column they live in. Measured on an
all-expansion game before this: the four cards came to 1,678px mid-game and
2,189px late against 751px of room, so the fourth seat was always below the
fold and the card lines — Battle, In play, Tech, Contracts — were most of the
weight.

Head, stats and the zone counts stay. The rest folds, and the fold still says
what it is holding, so a folded seat is informative rather than blank. `s`
folds or opens all four, and the choice is remembered per browser.

Also guards the last English line in the panel: the zone counts used to read
`hand 5 · deck 5 · discard 0`, which the label de-mixing never reached
because it is built by concatenation rather than from a label table.
"""

from __future__ import annotations

from common import LAPTOP_VIEWPORT, SERVER_LOG_COPY, Check, chrome, open_context, server

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


def check_moved_counts(page) -> None:
    """What left the zone line is still on the panel: the Intrigue count on the
    resource row, the supply in the garrison's title and the detail, the
    garrisoned and supplied Commanders as C chips."""
    rows = page.evaluate(
        """() => state.view.players.map((player, index) => {
            const card = document.querySelectorAll('#seats article.seat')[index];
            const stats = [...card.querySelectorAll(':scope > .stats .stat')];
            const head = phraseText('{garrison}');
            const garrison = stats.find((s) => s.title.startsWith(head));
            const detail = card.querySelector('.seat-detail');
            return {
                intrigue: player.intrigue_card_count,
                intrigueShown: stats.some((s) => s.title === phraseText('{intrigue}')
                    && s.textContent.trim() === String(player.intrigue_card_count)),
                supply: player.troops_supply,
                garrisonTitle: garrison ? garrison.title : null,
                detailText: detail ? detail.textContent : '',
                commandersGarrison: player.commanders_garrison || 0,
                commandersSupply: player.commanders_supply || 0,
                garrisonChip: garrison && garrison.querySelector('.commander-count')
                    ? garrison.querySelector('.commander-count').textContent : null,
            };
        })"""
    )
    missing = []
    for seat, row in enumerate(rows):
        if not row["intrigueShown"]:
            missing.append((seat, "intrigue", row["intrigue"]))
        supply = f"{row['supply']}"
        if not (row["garrisonTitle"] and row["garrisonTitle"].endswith(supply)):
            missing.append((seat, "supply in title", row["garrisonTitle"]))
        if supply not in row["detailText"]:
            missing.append((seat, "supply in detail", row["detailText"][-40:]))
        want = f"C{row['commandersGarrison']}" if row["commandersGarrison"] else None
        if row["garrisonChip"] != want:
            missing.append((seat, "garrison C chip", row["garrisonChip"], want))
        supplied = row["commandersSupply"]
        if supplied and f"C{supplied}" not in row["detailText"]:
            missing.append((seat, "supply C chip", supplied))
    check.ok(
        not missing, "the counts that moved off the zone line are still shown", missing
    )
    check.ok(
        any(row["commandersGarrison"] or row["commandersSupply"] for row in rows),
        f"seed {SEED} really has a Commander to show",
    )


def run(base: str, browser) -> None:
    context, page, rec = open_context(browser, "seats")
    watched_game(page, base)

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
    check_moved_counts(page)

    # Open one seat: only that one grows.
    page.click("#seats > *:nth-child(2) .seat-more")
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
    page.click("#seats > *:nth-child(3) .seat-more")
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
    page.evaluate(f"stopPlayback(); reviewSeek({target})")
    page.wait_for_function(
        f"state.review.cursor === {target} && refreshFlight === null"
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
    page.click("#seats > *:nth-child(1) .seat-more")
    opened = page.evaluate(SEATS)["cards"][0]
    check.ok(
        opened["expanded"] == "true" and opened["detailShown"],
        "the arrow opens its seat",
        opened["expanded"],
    )
    page.click("#seats > *:nth-child(1) .seat-more")
    check.ok(
        page.evaluate(SEATS)["cards"][0]["expanded"] == "false",
        "and folds it again",
    )
    check.ok(not rec.js_errors, "no JS errors on the laptop", rec.js_errors[:3])
    context.close()


def main() -> None:
    with server() as (base, log_path):
        with chrome() as browser:
            run(base, browser)
            print("[laptop] 1366x768")
            run_laptop(base, browser)
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
