"""E2E of the layout below 1100px, with every expansion on.

style.css has four media queries and every script ran at one size, which is
how a scroll promise stayed vacuous for months (README). Below 1100px the
table changes shape in ways nothing has ever checked: #center stacks the
board above the shared cards instead of putting them side by side, #market
becomes a row of strips instead of a column, and each strip's card row stops
wrapping and scrolls sideways.

Not checked here, and deliberately: the sideways scroll those rows are allowed
has no offset to lose. #market wraps, so every strip keeps its natural width —
measured at 1090, 1000, 820 and 700px with all five expansions on, no strip
ever had scrollWidth > clientWidth. The rule is reachable CSS over an
unreachable state, so there is nothing for a check to assert and nothing for
render() to carry. Re-measure before adding one.

The header (2026-09-24): on a half-laptop window its status line used to wrap
to three lines inside the fixed 44px header, cutting the round off the top
and running over the seats. It is one line now: the round and phase, the
review label, then the seed and ruleset badges, which alone give way to an
ellipsis. check_header() looks at the widths a window beside a chat app has,
in both languages, in a watched game (the review label) and a live one.
"""

from __future__ import annotations

from common import (
    SERVER_LOG_COPY,
    Check,
    chrome,
    open_context,
    server,
)

check = Check()

SEED = 7
NARROW = {"width": 1000, "height": 900}
EXPANSIONS = ("choam", "bloodlines", "tech", "immortality", "promo")


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
    page.evaluate(
        "stopPlayback();"
        " reviewSeek(Math.floor(state.review.meta.step_count / 2))"
    )
    page.wait_for_function("refreshFlight === null")


def run(base: str, browser) -> None:
    context, page, rec = open_context(browser, "narrow", NARROW)
    watched_game(page, base)

    shape = page.evaluate(
        """() => {
            const css = (id, prop) =>
                getComputedStyle(document.getElementById(id))[prop];
            const box = (id) => document.getElementById(id).getBoundingClientRect();
            const rows = [...document.querySelectorAll('#market .strip-cards')];
            return {
                viewport: [innerWidth, innerHeight],
                boardBottom: box('board').bottom,
                boardH: box('board').height,
                boardW: box('board').width,
                boardRight: box('board').right,
                marketTop: box('market').top,
                marketLeft: box('market').left,
                marketH: box('market').height,
                marketW: box('market').width,
                centerW: box('center').width,
                marketDirection: css('market', 'flexDirection'),
                stripWrap: rows.length ? getComputedStyle(rows[0]).flexWrap : null,
                stripOverflowX:
                    rows.length ? getComputedStyle(rows[0]).overflowX : null,
                strips: rows.length,
                scrollable:
                    rows.filter((r) => r.scrollWidth > r.clientWidth + 1).length,
            };
        }"""
    )
    print(
        f"  .. {shape['viewport']}: {shape['strips']} strips,"
        f" {shape['scrollable']} scroll sideways"
    )
    # Geometry, not the grid-track string: a rule that still declares one
    # column while the market renders empty or zero-size would pass a track
    # count. Ask where the two panels actually are.
    check.ok(
        shape["marketTop"] >= shape["boardBottom"] - 1,
        "below 1100px the shared cards sit BELOW the board, not beside it",
        (shape["boardBottom"], shape["marketTop"]),
    )
    check.ok(
        shape["marketW"] >= shape["centerW"] - 2,
        "the stacked shared cards span the whole centre column",
        (shape["marketW"], shape["centerW"]),
    )
    check.ok(
        shape["boardH"] > 0 and shape["marketH"] > 0,
        "both panels are actually drawn when stacked",
        (shape["boardH"], shape["marketH"]),
    )
    check.ok(
        shape["marketDirection"] == "row",
        "below 1100px the shared columns lay out as a row",
        shape["marketDirection"],
    )
    check.ok(
        shape["stripWrap"] == "nowrap" and shape["stripOverflowX"] == "auto",
        "a strip's cards stop wrapping and scroll sideways",
        (shape["stripWrap"], shape["stripOverflowX"]),
    )
    check.ok(
        shape["scrollable"] == 0,
        "no strip actually overflows sideways, so nothing needs carrying",
        shape["scrollable"],
    )

    # The Bene Tleilax board and the Tleilaxu Row are drawn here too; nothing
    # had ever opened them at any width.
    # By the columns' fixed names (data-strip); their titles follow the language.
    strips = page.eval_on_selector_all(
        "#market .strip[data-strip]", "els => els.map((e) => e.dataset.strip)"
    )
    for want in ("Tleilaxu Row", "Bene Tleilax board", "Imperium Row"):
        check.ok(
            any(want in s for s in strips),
            f"the shared columns include {want}",
            strips,
        )
    check_tleilaxu_row(page)

    bad = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
    check.ok(not bad, "no failed requests", bad[:3])
    check.ok(not rec.js_errors, "no JS errors", rec.js_errors[:3])
    if check.failed:
        rec.dump()
    context.close()


def check_tleilaxu_row(page) -> None:
    """The Tleilaxu Row is two deck cards plus the fixed Reclaimed Forces.

    `Reclaimed Forces` is never removed and always sits last
    (`rules/tleilaxu_row.py`, [Immortality p. 9]), so its position and its
    marker class are a contract the renderer must keep. The names are read
    from each card's title, which visualCard sets from the catalog entry, so a
    baseId/lookup regression that put a raw instance id on the face fails here
    whether or not the image cache is present.
    """
    row = page.evaluate(
        """() => {
            const strip = document.querySelector(
                '#market .strip[data-strip="Tleilaxu Row"]');
            if (!strip) return null;
            const cards = [...strip.querySelectorAll('.vcard[data-instance]')];
            return {
                // the heading is a collapse button; drop its ▾/▸ marker
                heading: strip.querySelector('.strip-toggle')
                    .textContent.replace(/^[▾▸]\s*/, '').trim(),
                deckSize: state.view.tleilaxu_deck_size,
                expected: [...state.view.tleilaxu_row, 'reclaimed_forces'],
                ids: cards.map((c) => c.dataset.instance),
                titles: cards.map((c) => c.title),
                reclaimed: cards.map((c) => c.classList.contains('reclaimed')),
                sized: cards.map((c) => {
                    const r = c.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                }),
                strayReclaimed: document.querySelectorAll(
                    '#market .vcard.reclaimed').length,
            };
        }"""
    )
    if not check.ok(row is not None, "the Tleilaxu Row strip is on screen"):
        return
    check.ok(
        row["heading"] == f"틀레이락스 열 · 카드덱 {row['deckSize']}",
        "the strip heading carries the live deck count",
        (row["heading"], row["deckSize"]),
    )
    check.ok(
        row["ids"] == row["expected"],
        "the row is the view's cards with Reclaimed Forces appended last",
        (row["ids"], row["expected"]),
    )
    check.ok(
        row["reclaimed"] == [False] * (len(row["ids"]) - 1) + [True],
        "only the last card is marked reclaimed",
        row["reclaimed"],
    )
    check.ok(
        row["strayReclaimed"] == 1,
        "nothing else in the shared columns claims the reclaimed marker",
        row["strayReclaimed"],
    )
    # A raw instance id on the face is the symptom a player would see.
    raw = [t for t in row["titles"] if t.startswith("tleilaxu:") or t.endswith(":0")]
    check.ok(not raw, "every card resolved to its catalog name", raw)
    check.ok(all(row["sized"]), "every card in the row has size", row["sized"])



HEADER_SIZES = ((600, 800), (683, 768), (720, 900), (768, 864), (1366, 768))

HEADER_JS = """() => {
    const header = document.querySelector('header').getBoundingClientRect();
    const status = document.getElementById('header-status');
    const box = status.getBoundingClientRect();
    const whole = (selector) => {
        const span = status.querySelector(selector);
        if (!span) return null;
        const b = span.getBoundingClientRect();
        return b.left >= box.left - 0.5 && b.right <= box.right + 0.5
            && b.right <= innerWidth + 0.5 && span.scrollWidth <= span.clientWidth + 0.5;
    };
    const badges = status.querySelector('.status-badges');
    return {
        headerH: header.height,
        inside: box.top >= header.top - 0.5 && box.bottom <= header.bottom + 0.5,
        statusH: box.height,
        core: whole('.status-core'),
        label: whole('.status-label'),
        badgesWhole: badges ? badges.scrollWidth <= badges.clientWidth + 0.5 : null,
        sideways: document.documentElement.scrollWidth > innerWidth + 0.5,
        title: status.title === status.textContent,
        text: status.textContent,
    };
}"""


def live_game(page, base: str) -> None:
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(1, 4):
        page.select_option(f"#seat-selects select[data-seat='{seat}']", "heuristic")
    for option in EXPANSIONS:
        page.check(f"#opt-{option}")
    page.fill("#opt-seed", str(SEED))
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null")


def check_header(browser, base: str) -> None:
    for mode, start in (("watched", watched_game), ("live", live_game)):
        context, page, _rec = open_context(browser, f"header-{mode}", NARROW)
        start(page, base)
        for language in ("ko", "en"):
            if page.evaluate("TERM_LANGUAGE") != language:
                page.click("#language-toggle")
                page.wait_for_function(f"TERM_LANGUAGE === '{language}'")
            for width, height in HEADER_SIZES:
                page.set_viewport_size({"width": width, "height": height})
                page.wait_for_timeout(50)
                g = page.evaluate(HEADER_JS)
                where = f"{mode} {language} {width}x{height}"
                check.ok(
                    abs(g["headerH"] - 44) < 0.5 and g["inside"] and g["statusH"] < 30,
                    f"{where}: the header stays one 44px line",
                    g,
                )
                check.ok(g["core"], f"{where}: the round and phase are whole", g["text"])
                if mode == "watched":
                    check.ok(g["label"], f"{where}: the review label is whole", g["text"])
                check.ok(not g["sideways"], f"{where}: the page does not scroll sideways")
                check.ok(g["title"], f"{where}: the full status is in the title")
                if width >= 1366 and language == "ko" and mode == "live":
                    check.ok(g["badgesWhole"], f"{where}: nothing is cut when there is room")
        context.close()


def main() -> None:
    with server() as (base, log_path):
        with chrome() as browser:
            run(base, browser)
            check_header(browser, base)
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
