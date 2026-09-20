"""E2E of folding the shared card columns away.

With every expansion on there are eight of them. Each now folds from its own
heading, `c` folds them all, and the choice is remembered per browser.

The state cannot live in the DOM: #market is emptied and rebuilt by every
render, so a fold would come undone the moment anyone moved. These checks
press on exactly that — fold, let another seat move, reload.

What folding buys, measured rather than assumed: the column gives back its
own width (190px to 170px at the default size, once #market's min-width stops
applying). The board grows by that much and no more — it is sized by the
centre grid, not by these columns. Runs at the default viewport because that
is where the column is vertical and its width is the thing at stake; below
1100px the column is a full-width row and folding only shortens it.
"""

from __future__ import annotations

from common import SERVER_LOG_COPY, Check, chrome, open_context, server

check = Check()

SEED = 7
EXPANSIONS = ("choam", "bloodlines", "tech", "immortality", "promo")

GEOMETRY = """() => {
    const box = (id) => document.getElementById(id).getBoundingClientRect();
    const strips = [...document.querySelectorAll('#market .strip[data-strip]')];
    return {
        boardH: box('board').height,
        boardW: box('board').width,
        marketH: box('market').height,
        marketW: box('market').width,
        allFolded: document.getElementById('market').classList.contains('all-folded'),
        strips: strips.map((s) => ({
            name: s.dataset.strip,
            collapsed: s.classList.contains('collapsed'),
            expanded: s.querySelector('.strip-toggle').getAttribute('aria-expanded'),
            bodyShown: [...s.children].some(
                (c) => c.tagName !== 'H3' && c.getBoundingClientRect().height > 0),
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
    target = page.evaluate("Math.floor(state.review.meta.step_count / 2)")
    page.evaluate(f"stopPlayback(); reviewSeek({target})")
    # Wait for the cursor itself, not just for the flight to end: the first
    # snapshot was otherwise taken before the seek had rendered, and the strip
    # list still held the Leader draft column.
    page.wait_for_function(
        f"state.review.cursor === {target} && refreshFlight === null"
    )


def run(base: str, browser) -> None:
    context, page, rec = open_context(browser, "columns")
    watched_game(page, base)

    start = page.evaluate(GEOMETRY)
    names = [s["name"] for s in start["strips"]]
    print(f"  .. {len(names)} shared columns: {names}")
    check.ok(len(names) >= 5, "an all-expansion game really has many columns", names)
    check.ok(
        all(not s["collapsed"] for s in start["strips"]),
        "every column starts open",
        [s["name"] for s in start["strips"] if s["collapsed"]],
    )
    check.ok(
        all(s["expanded"] == "true" for s in start["strips"]),
        "an open column says so to a screen reader",
        [(s["name"], s["expanded"]) for s in start["strips"]],
    )

    # Fold one column from its own heading.
    target = "Imperium Row"
    page.click(f"#market .strip[data-strip='{target}'] .strip-toggle")
    one = page.evaluate(GEOMETRY)
    folded = next(s for s in one["strips"] if s["name"] == target)
    check.ok(folded["collapsed"], f"{target} folded when its heading was clicked")
    check.ok(not folded["bodyShown"], f"{target}'s cards are hidden when folded")
    check.ok(
        folded["expanded"] == "false",
        "a folded column says so to a screen reader",
        folded["expanded"],
    )
    check.ok(
        sum(1 for s in one["strips"] if s["collapsed"]) == 1,
        "folding one column leaves the others alone",
        [s["name"] for s in one["strips"] if s["collapsed"]],
    )
    check.ok(
        one["strips"] and all(
            s["name"] in names for s in one["strips"]
        ) and len(one["strips"]) == len(names),
        "a folded column is still listed, not removed",
        [s["name"] for s in one["strips"]],
    )

    # The fold must survive somebody else's move rebuilding #market.
    page.evaluate("render({ foreign: true })")
    after = page.evaluate(GEOMETRY)
    still = next(s for s in after["strips"] if s["name"] == target)
    check.ok(still["collapsed"], "the fold survives a re-render caused by another seat")

    # `c` folds them all, and again to unfold.
    page.keyboard.press("c")
    allfolded = page.evaluate(GEOMETRY)
    check.ok(
        all(s["collapsed"] for s in allfolded["strips"]),
        "c folds every column",
        [s["name"] for s in allfolded["strips"] if not s["collapsed"]],
    )
    # What folding actually buys is the column's own width: #market carries a
    # min-width that would otherwise hold it open, dropped once nothing is
    # expanded. The board grows by whatever that releases, which is small —
    # the board is sized by the centre grid, not by these columns, and making
    # it bigger is its own change.
    check.ok(allfolded["allFolded"], "the column marks itself fully folded")
    check.ok(
        allfolded["marketW"] < start["marketW"],
        "the shared column gives width back when every column is folded",
        (start["marketW"], allfolded["marketW"]),
    )
    print(
        f"  .. column {start['marketW']:.0f}px open"
        f" -> {allfolded['marketW']:.0f}px folded"
        f" (board {start['boardW']:.0f} -> {allfolded['boardW']:.0f})"
    )

    page.keyboard.press("c")
    unfolded = page.evaluate(GEOMETRY)
    check.ok(
        all(not s["collapsed"] for s in unfolded["strips"]),
        "c again opens every column",
        [s["name"] for s in unfolded["strips"] if s["collapsed"]],
    )

    # The Hangul IME is the normal state for this UI's players: the same
    # physical key then arrives as key "ㅊ", and matching on event.key meant
    # the shortcut did nothing at all until you switched back to English.
    page.evaluate(
        """() => document.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'ㅊ', code: 'KeyC', bubbles: true,
        }))"""
    )
    hangul = page.evaluate(GEOMETRY)
    check.ok(
        all(s["collapsed"] for s in hangul["strips"]),
        "the shortcut works with the Hangul IME on (key ㅊ, code KeyC)",
        [s["name"] for s in hangul["strips"] if not s["collapsed"]],
    )
    page.evaluate(
        """() => document.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'ㅊ', code: 'KeyC', bubbles: true,
        }))"""
    )
    # ...and a key that is only mid-composition must not fold anything.
    page.evaluate(
        """() => document.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'ㅊ', code: 'KeyC', isComposing: true, bubbles: true,
        }))"""
    )
    composing = page.evaluate(GEOMETRY)
    check.ok(
        all(not s["collapsed"] for s in composing["strips"]),
        "a keystroke the IME is still composing is left alone",
        [s["name"] for s in composing["strips"] if s["collapsed"]],
    )

    # A remembered choice: fold two, reload, they are still folded.
    page.click("#market .strip[data-strip='Reserve'] .strip-toggle")
    page.click(f"#market .strip[data-strip='{target}'] .strip-toggle")
    page.reload()
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    reloaded = page.evaluate(GEOMETRY)
    folded_names = sorted(s["name"] for s in reloaded["strips"] if s["collapsed"])
    check.ok(
        folded_names == sorted([target, "Reserve"]),
        "the folded columns are remembered across a reload",
        folded_names,
    )

    # Typing must not fold anything: `c` in a text field is a letter.
    page.click("#market .strip[data-strip='Reserve'] .strip-toggle")
    page.click(f"#market .strip[data-strip='{target}'] .strip-toggle")
    page.evaluate("document.getElementById('game-error').hidden = true")
    page.keyboard.press("Escape")
    before_typing = page.evaluate(GEOMETRY)
    page.evaluate(
        """() => {
            const probe = document.createElement('input');
            probe.id = 'e2e-probe';
            document.body.appendChild(probe);
            probe.focus();
        }"""
    )
    page.keyboard.press("c")
    typed = page.evaluate(GEOMETRY)
    page.evaluate("document.getElementById('e2e-probe').remove()")
    check.ok(
        [s["collapsed"] for s in typed["strips"]]
        == [s["collapsed"] for s in before_typing["strips"]],
        "c typed into a field does not fold the columns",
        [s["name"] for s in typed["strips"] if s["collapsed"]],
    )

    check_bene_tleilax_zoom(page)

    bad = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
    check.ok(not bad, "no failed requests", bad[:3])
    check.ok(not rec.js_errors, "no JS errors", rec.js_errors[:3])
    if check.failed:
        rec.dump()
    context.close()


STAGE = """(sel) => {
    const stage = document.querySelector(sel);
    if (!stage) return null;
    const map = stage.querySelector('.bt-map');
    const hexes = [...stage.querySelectorAll('.bt-hex')];
    const tokens = [...stage.querySelectorAll('.bt-token')];
    const r = (e) => e.getBoundingClientRect();
    return {
        width: r(stage).width,
        downscale: map ? map.naturalWidth / r(map).width : null,
        hexes: hexes.length,
        hexWidth: hexes.length ? r(hexes[0]).width : 0,
        tokenWidth: tokens.length ? r(tokens[0]).width : 0,
    };
}"""


def check_bene_tleilax_zoom(page) -> None:
    """The Bene Tleilax board is a real board, not a thumbnail.

    In the shared column its scan is reduced about 31x — the main board scan
    is reduced 10x — which leaves its 22 research spaces around 20px and the
    seat tokens at 10px. The column keeps that as a marker; "크게 보기" opens
    the same stage at a size you can actually read, which costs nothing
    because renderBeneTleilaxScan positions everything in percentages.
    """
    small = page.evaluate(STAGE, "#market .bene-tleilax .bt-stage")
    if not check.ok(small is not None, "the Bene Tleilax board is in the column"):
        return
    check.ok(small["hexes"] == 22, "all 22 research spaces are drawn", small["hexes"])
    check.ok(
        small["downscale"] > 20,
        "the column copy really is a thumbnail",
        round(small["downscale"], 1),
    )

    page.click(".bt-open")
    page.wait_for_selector("#bt-zoom:not([hidden])")
    big = page.evaluate(STAGE, "#bt-zoom-body .bt-stage")
    if not check.ok(big is not None, "the enlarged board opened"):
        return
    check.ok(big["hexes"] == 22, "the enlarged board draws all 22 spaces", big["hexes"])
    check.ok(
        big["hexWidth"] >= small["hexWidth"] * 4,
        "a research space is at least four times the size it was",
        (round(small["hexWidth"]), round(big["hexWidth"])),
    )
    check.ok(
        big["downscale"] < 10.4,
        "the enlarged scan is reduced less than the main board's 10.4x",
        round(big["downscale"], 1),
    )
    check.ok(
        big["tokenWidth"] >= 24,
        "a seat token is big enough to see",
        round(big["tokenWidth"]),
    )
    print(
        f"  .. board x{small['downscale']:.1f} in the column"
        f" -> x{big['downscale']:.1f} enlarged"
        f" (space {small['hexWidth']:.0f}px -> {big['hexWidth']:.0f}px)"
    )

    # It must survive somebody else's move, since render() rebuilds #market.
    page.evaluate("render({ foreign: true })")
    check.ok(
        page.is_visible("#bt-zoom") and page.evaluate(STAGE, "#bt-zoom-body .bt-stage"),
        "the enlarged board stays open when another seat moves",
    )

    page.keyboard.press("Escape")
    check.ok(page.is_hidden("#bt-zoom"), "Escape closes the enlarged board")
    page.click(".bt-open")
    page.wait_for_selector("#bt-zoom:not([hidden])")
    page.evaluate("document.getElementById('bt-zoom').click()")
    check.ok(page.is_hidden("#bt-zoom"), "clicking the backdrop closes it")


def main() -> None:
    with server() as (base, log_path):
        with chrome() as browser:
            run(base, browser)
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
