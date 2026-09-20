"""E2E of how a game ENDS, with every expansion on.

Nothing checked this before: `grep -ril standings scripts/e2e` found only
`is_visible`, and `disclosure`, `tleilax` and `contract` found nothing at all.
Both surfaces only exist once a game is over, and only an all-AI game reaches
that cheaply — the server plays it to the end inside the create request.

The sharp one is the Garrison column. The endgame tiebreak counts a garrisoned
Sardaukar Commander as a troop — `rules/endgame.py` ranks on
`troops_garrison + commanders_garrison` (OQ-047, 사용자 판정 2026-09-08,
`docs/rules/open-questions.md`) — so a table printing the troops alone shows a
number that does not explain the order it stands in. At seed 7 two seats hold a
Commander in garrison, which is why this check uses that seed.
"""

from __future__ import annotations

from common import LAPTOP_VIEWPORT, SERVER_LOG_COPY, Check, chrome, open_context, server

check = Check()

SEED = 7
EXPANSIONS = ("choam", "bloodlines", "tech", "immortality", "promo")


def watched_game(page, base: str, seed: int = SEED) -> str:
    """Create an all-AI game with every expansion; the page opens it watched."""
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(f"#seat-selects select[data-seat='{seat}']", "heuristic")
    for option in EXPANSIONS:
        page.check(f"#opt-{option}")
    page.fill("#opt-seed", str(seed))
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.review !== null && state.view !== null")
    return page.evaluate("state.gameId")


def seek_to_end(page) -> None:
    page.evaluate("stopPlayback(); reviewSeek(state.review.meta.step_count)")
    page.wait_for_function(
        "state.review.cursor === state.review.meta.step_count"
        " && !playback.playing && refreshFlight === null"
    )


def run(base: str, browser) -> None:
    context, page, rec = open_context(browser, "endgame")
    game_id = watched_game(page, base)
    print(f"  .. watched game {game_id[:8]} (all expansions, seed {SEED})")
    seek_to_end(page)

    summary = page.evaluate("state.summary")
    check.ok(summary["finished"], "the watched game is finished")
    standings = summary["standings"]
    check.ok(
        bool(standings) and len(standings) == 4,
        "the server sent four standings rows",
        standings and len(standings),
    )

    # The table must be on screen once the replay reaches the end.
    check.ok(
        page.is_visible("#standings"), "the final standings show at the end of a replay"
    )
    header = page.eval_on_selector_all(
        "#standings tr:first-child th", "els => els.map((e) => e.textContent.trim())"
    )
    check.ok(
        header == ["순위", "좌석", "VP", "Spice", "Solari", "Water", "Garrison"],
        "the standings header is the seven printed columns",
        header,
    )

    rows = page.eval_on_selector_all(
        "#standings tr:not(:first-child)",
        """els => els.map((e) => ({
            cells: [...e.querySelectorAll('td')].map((c) => c.textContent.trim()),
            title: e.querySelector('td:last-child').getAttribute('title'),
            winner: e.classList.contains('winner'),
        }))""",
    )
    check.ok(len(rows) == 4, "four rows are drawn", len(rows))

    # The Garrison cell must be the number the tiebreak used, not the troops
    # alone. Seat order in the table is rank order, so pair by rank.
    by_rank = {entry["rank"]: entry for entry in standings}
    wrong = []
    for index, row in enumerate(rows, start=1):
        entry = by_rank[index]
        expected = entry["troops_garrison"] + entry.get("commanders_garrison", 0)
        if row["cells"][6] != str(expected):
            wrong.append((index, row["cells"][6], expected))
    check.ok(
        not wrong,
        "Garrison shows troops + garrisoned Commanders, the tiebreak's own number",
        wrong,
    )

    # A Commander in garrison must also be spelled out, or the number is a
    # bare total nobody can check against the board.
    with_commanders = [
        index
        for index, row in enumerate(rows, start=1)
        if by_rank[index].get("commanders_garrison", 0)
    ]
    check.ok(
        bool(with_commanders),
        f"seed {SEED} really does leave a Commander in a garrison",
        [(i, by_rank[i]["commanders_garrison"]) for i in with_commanders],
    )
    missing_title = [i for i in with_commanders if not rows[i - 1]["title"]]
    check.ok(
        not missing_title,
        "a row counting Commanders explains the split in its title",
        missing_title,
    )

    winners = [index for index, row in enumerate(rows, start=1) if row["winner"]]
    check.ok(winners == [1], "exactly the rank-1 row is marked the winner", winners)

    # Post-game disclosure (OQ-010 ruling 4): every hidden zone, for every seat.
    view = page.evaluate("state.view")
    check.ok("disclosure" in view, "the finished view carries disclosure")
    check.ok(page.is_visible("#disclosure"), "the disclosure panel is shown")
    # section() in turn.js appends its h3 straight to the panel; there is no
    # wrapping <section> element to select.
    seats = page.eval_on_selector_all(
        "#disclosure h3", "els => els.map((e) => e.textContent.trim())"
    )
    check.ok(
        len([s for s in seats if s.startswith("좌석")]) == 4,
        "disclosure has a section per seat",
        seats,
    )
    lines = page.inner_text("#disclosure")
    for label in ("Hand", "Deck 순서", "Intrigue", "Imperium deck", "Conflict deck"):
        check.ok(label in lines, f"disclosure lists {label}")
    # With CHOAM on there is a contract bank to reveal.
    check.ok(
        "Contract bank" in lines,
        "disclosure lists the Contract bank when CHOAM is on",
    )

    # The expansion surfaces exist at all: no check had ever opened one.
    strips = page.eval_on_selector_all(
        "#market .strip h3", "els => els.map((e) => e.textContent.trim())"
    )
    for want in ("Imperium Row", "Reserve", "Tleilaxu Row", "Bene Tleilax board"):
        check.ok(
            any(want in s for s in strips),
            f"the shared columns include {want}",
            strips,
        )

    bad = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
    check.ok(not bad, "no failed requests", bad[:3])
    check.ok(not rec.js_errors, "no JS errors", rec.js_errors[:3])
    if check.failed:
        rec.dump()
    context.close()


def run_laptop(base: str, browser) -> None:
    """The same finished game at a laptop size.

    Every other script runs at one viewport, which is how a scroll check stayed
    vacuous for months (README). The standings and the disclosure panel are the
    tallest things the UI ever draws, so they are the right place to ask
    whether the result is reachable on a smaller screen.
    """
    context, page, rec = open_context(browser, "endgame-laptop", LAPTOP_VIEWPORT)
    watched_game(page, base)
    seek_to_end(page)
    size = page.evaluate(
        """() => {
            const side = document.getElementById('side');
            const standings = document.getElementById('standings');
            return {
                viewport: [innerWidth, innerHeight],
                sideScrolls: getComputedStyle(side).overflowY,
                sideScrollH: side.scrollHeight,
                sideClientH: side.clientHeight,
                standingsTop: standings.getBoundingClientRect().top,
                standingsH: standings.getBoundingClientRect().height,
                disclosureH: document
                    .getElementById('disclosure')
                    .getBoundingClientRect().height,
            };
        }"""
    )
    print(
        f"  .. laptop {size['viewport']}: "
        f"side {size['sideScrollH']}px in {size['sideClientH']}px"
    )
    check.ok(
        size["sideScrolls"] in ("auto", "scroll"),
        "at a laptop width the side column is the scroller",
        size["sideScrolls"],
    )
    # The result must be reachable: the panel exists, has height, and the
    # column it lives in can be scrolled to it.
    check.ok(
        size["standingsH"] > 0, "the standings panel has height", size["standingsH"]
    )
    check.ok(
        size["standingsTop"] < size["sideScrollH"],
        "the standings sit inside the scrollable side column",
        (size["standingsTop"], size["sideScrollH"]),
    )
    reached = page.evaluate(
        """() => {
            const side = document.getElementById('side');
            const standings = document.getElementById('standings');
            standings.scrollIntoView({block: 'start'});
            const box = standings.getBoundingClientRect();
            const host = side.getBoundingClientRect();
            return box.top >= host.top - 2 && box.top < host.bottom;
        }"""
    )
    check.ok(reached, "the standings can be scrolled into view on a laptop screen")
    print(f"  .. disclosure is {size['disclosureH']:.0f}px tall here")
    context.close()


def main() -> None:
    with server() as (base, log_path):
        with chrome() as browser:
            run(base, browser)
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
