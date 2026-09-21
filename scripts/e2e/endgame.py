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

    # In a review it starts folded (사용자 결정 2026-09-21): every hand and deck
    # order as of the reviewed step is the replay's own future.
    folded = disclosure_state(page)
    check.ok(
        folded["expanded"] == "false" and not folded["sections"] and not folded["tags"],
        "in a review the disclosure starts folded, with no seat or card on show",
        folded,
    )
    if folded["expanded"] is not None:  # an unfoldable panel fails just above
        page.click("#disclosure h2 button")
    opened = disclosure_state(page)
    check.ok(
        opened["expanded"] == "true" and len(opened["sections"]) >= 4,
        "one click on its heading opens it",
        opened,
    )
    # A cursor move re-renders everything; opened by hand, it stays open.
    page.evaluate("reviewSeek(state.review.meta.step_count - 1)")
    page.wait_for_function(
        "state.review.cursor === state.review.meta.step_count - 1"
        " && refreshFlight === null"
    )
    seek_to_end(page)
    check.ok(
        disclosure_state(page)["expanded"] == "true",
        "the opened disclosure survives the review moving",
    )
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

    # Another seat's eyes on the same position keep it open too.
    page.select_option("#review-seat", "1")
    # phase is reset to null by enterReview and set just before its render().
    page.wait_for_function("state.review.seat === 1 && state.review.phase !== null")
    check.ok(
        disclosure_state(page)["expanded"] == "true",
        "switching the reviewed seat keeps the disclosure open",
    )

    # Leaving the review shows the live banner. Nobody sits at a watched game,
    # so there is no seat view (pickViewSeat) and no disclosure out of review;
    # open_mode.py checks the unfolded panel on a game with human seats.
    page.evaluate("exitReview()")
    page.wait_for_function("state.review === null && refreshFlight === null")
    page.wait_for_selector("#decision-banner:not([hidden])")
    check_banner(page, standings)

    # Watching the game again starts a new review: folded again.
    page.click("#standings button")
    page.wait_for_function("state.review !== null && state.review.phase !== null")
    page.evaluate("stopPlayback()")
    check.ok(
        disclosure_state(page)["expanded"] == "false",
        "a new review folds the disclosure again",
    )
    page.evaluate("stopPlayback(); exitReview()")
    page.wait_for_function("state.review === null && refreshFlight === null")

    check_margins(page)

    bad = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
    check.ok(not bad, "no failed requests", bad[:3])
    check.ok(not rec.js_errors, "no JS errors", rec.js_errors[:3])
    if check.failed:
        rec.dump()
    context.close()


def disclosure_state(page) -> dict:
    return page.evaluate(
        """() => {
            const panel = document.getElementById('disclosure');
            const button = panel.querySelector('h2 button');
            return {
                expanded: button ? button.getAttribute('aria-expanded') : null,
                sections: [...panel.querySelectorAll('h3')].map((e) => e.textContent),
                tags: panel.querySelectorAll('.tag').length,
            };
        }"""
    )


# The Uprising tiebreaks after equal VP, in order [Main p. 15] (a garrisoned
# Commander counting as a troop, OQ-047), then the most recent Reveal turn
# [FAQ p. 2]. Written out here rather than read from the client, so the banner
# is checked against the rulebook's order and not against itself.
TIEBREAK_ORDER = (
    ("스파이스", lambda e: e["spice"]),
    ("솔라리", lambda e: e["solari"]),
    ("물", lambda e: e["water"]),
    ("주둔지 병력", lambda e: e["troops_garrison"] + e.get("commanders_garrison", 0)),
)


def expected_margin(first: dict, second: dict) -> str:
    """The banner's margin line as read with each icon's alt text — the same
    text the line shows on a machine without the icon set."""
    vp = f"{first['victory_points']}승점"
    if first["victory_points"] != second["victory_points"]:
        return f"{vp} ({first['victory_points'] - second['victory_points']} 차)"
    for label, value in TIEBREAK_ORDER:
        if value(first) != value(second):
            return f"{vp} 동점 · 동점 판정 {label} {value(first)} 대 {value(second)}"
    last = "공개 차례를 더 늦게 마친 좌석이 승리"
    return f"{vp} 동점 · 동점 판정 항목도 모두 같아 {last}"


# Text of an element with every icon read as its alt text.
READ_WITH_ALT = """(e) => {
    const copy = e.cloneNode(true);
    copy.querySelectorAll('img').forEach((img) => img.replaceWith(img.alt));
    return copy.textContent;
}"""


def check_banner(page, standings: list) -> None:
    """The finished banner names the winner and what beat second place."""
    by_rank = sorted(standings, key=lambda entry: entry["rank"])
    first, second = by_rank[0], by_rank[1]
    label = page.evaluate(f"playerLabel({first['player']})")
    second_label = page.evaluate(f"playerLabel({second['player']})")
    prompt = page.inner_text("#decision-info .prompt").strip()
    check.ok(
        prompt == f"게임 종료 — {label} 승리",
        "the finished banner names the rank-1 seat as the winner",
        prompt,
    )
    meta = page.evaluate(
        f"""() => {{
            const meta = document.querySelector('#decision-info .meta');
            return meta ? ({READ_WITH_ALT})(meta).trim() : null;
        }}"""
    )
    want = f"{expected_margin(first, second)} · 2위 {second_label}"
    check.ok(meta == want, "the banner says what put the winner ahead", (meta, want))


def check_margins(page) -> None:
    """Every branch of the margin line, on made-up standings.

    One seeded game reaches one branch; a VP tie is rare. The rows below are
    built so that each tiebreak in turn is the first to differ.
    """
    base = {
        "victory_points": 11,
        "spice": 3,
        "solari": 4,
        "water": 1,
        "troops_garrison": 2,
        "commanders_garrison": 0,
    }
    cases = {
        "VP": ({**base, "victory_points": 12}, base),
        "spice": ({**base, "spice": 5}, base),
        "solari": ({**base, "solari": 6}, base),
        "water": ({**base, "water": 2}, base),
        # 2 troops + 2 Commanders against 3 troops: the troops alone would
        # rank them the other way round.
        "garrison": (
            {**base, "commanders_garrison": 2},
            {**base, "troops_garrison": 3},
        ),
        "reveal": (base, dict(base)),
    }
    for name, (first, second) in cases.items():
        try:
            text = page.evaluate(
                f"""([a, b]) => {{
                    const box = document.createElement('div');
                    box.append(phrase(gameOverMargin(a, b)));
                    return ({READ_WITH_ALT})(box);
                }}""",
                [first, second],
            )
        except Exception as error:  # the old client has no gameOverMargin
            text = f"<error: {str(error).splitlines()[0]}>"
        want = expected_margin(first, second)
        check.ok(text == want, f"the margin line for a {name} decision", (text, want))


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
