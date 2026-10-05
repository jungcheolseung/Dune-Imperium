"""Specimens are coloured troop cubes on the printed Axolotl tanks.

Exercise an actual Experimentation reveal and specimen return, then check
four-player geometry, a full troop supply, zoom updates, both languages and
the text-board fallback. All actions use this script's isolated server.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from common import Check, chrome, open_context, server, set_rule_options
from lang import switch

check = Check()
SHOTS = Path(
    os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(prefix="dune-specimens-")
)


def act(page, action_id: str) -> None:
    page.evaluate(
        """async id => {
          const a = state.actions.actions.find(a => a.action_id === id);
          if (!a) throw new Error('Missing action: ' + id);
          await applyAction(a.index);
        }""",
        action_id,
    )
    page.wait_for_function("!state.busy && refreshFlight === null")


def set_counts(page, counts: list[int]) -> None:
    page.evaluate(
        """counts => {
          state.view.players.forEach(p => p.specimens = counts[p.player]);
          render({foreign: true});
        }""",
        counts,
    )


def pieces_match(page, selector: str, counts: list[int], label: str) -> None:
    page.wait_for_function(
        "selector => { const s = document.querySelector(selector); "
        "return s && [...s.querySelectorAll('img')].every(i => i.complete); }",
        arg=selector,
    )
    pieces = page.eval_on_selector_all(
        f"{selector} .bt-specimen",
        """nodes => nodes.map(n => {
          const s = n.closest('.bt-stage').getBoundingClientRect();
          const b = n.getBoundingClientRect();
          return { seat: Number(n.dataset.seat), kind: n.dataset.kind,
            left: (b.left - s.left) / s.width * 100,
            right: (b.right - s.left) / s.width * 100,
            top: (b.top - s.top) / s.height * 100,
            bottom: (b.bottom - s.top) / s.height * 100,
            width: b.width, height: b.height };
        })""",
    )
    check.ok(
        [sum(p["seat"] == seat for p in pieces) for seat in range(4)] == counts,
        f"{label}: one troop cube per public specimen, grouped by player",
    )
    # Independent bounds from the actual printed panel, not the new
    # catalog's layout. No cube may spill into the research hexes above.
    check.ok(
        all(
            1.6 <= p["left"] < p["right"] <= 26.7
            and 74 <= p["top"] < p["bottom"] <= 96.5
            and abs(p["width"] - p["height"]) < 0.08
            and p["kind"] == "troop"
            for p in pieces
        ),
        f"{label}: square troop cubes stay inside the printed tanks",
        pieces,
    )
    check.ok(
        all(
            a["right"] <= b["left"] + 0.001
            or b["right"] <= a["left"] + 0.001
            or a["bottom"] <= b["top"] + 0.001
            or b["bottom"] <= a["top"] + 0.001
            for i, a in enumerate(pieces)
            for b in pieces[i + 1 :]
        ),
        f"{label}: cubes and players' groups do not overlap",
    )
    check.ok(
        page.eval_on_selector_all(
            f"{selector} .bt-specimen",
            "nodes => nodes.every(n => getComputedStyle(n).backgroundColor "
            "=== (() => { const s = document.createElement('span'); "
            "s.style.color = SEAT_COLORS[n.dataset.seat]; "
            "document.body.appendChild(s); const c = getComputedStyle(s).color; "
            "s.remove(); return c; })())",
        ),
        f"{label}: each cube wears its player's colour",
    )
    labels = page.eval_on_selector_all(
        f"{selector} .bt-specimen-group",
        "nodes => nodes.map(n => ({seat: Number(n.dataset.seat), "
        "label: n.getAttribute('aria-label'), title: n.title}))",
    )
    language = page.evaluate("TERM_LANGUAGE")
    check.ok(
        all(
            row["label"] == row["title"]
            and ("플레이어" if language == "ko" else "Player ") + str(row["seat"] + 1)
            in row["label"]
            and ("표본" if language == "ko" else "specimen") in row["label"]
            and str(counts[row["seat"]]) in row["label"]
            for row in labels
        ),
        f"{label}: tooltip and accessibility label name player 1–4 and count",
        labels,
    )


def main() -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    small = "#market .bene-tleilax .bt-stage"
    large = "#bt-zoom-body .bt-stage"
    with server() as (base, _), chrome() as browser:
        context, page, _ = open_context(browser, "bene-specimens")
        page.goto(base)
        page.wait_for_selector("#setup-screen:not([hidden])")
        for seat in range(4):
            page.select_option(f"#seat-selects select[data-seat='{seat}']", "human")
        set_rule_options(page, "immortality")
        page.set_checked("#opt-leader-draft", False)
        page.set_checked("#opt-scouts", False)
        page.fill("#opt-seed", "2")
        page.click("#create-game")
        page.wait_for_function("state.view !== null && refreshFlight === null")
        has_scan = page.evaluate("Boolean(state.catalog.bene_tleilax.image)")
        if has_scan:
            pieces_match(page, small, [0] * 4, "initial empty tanks")
        actor = page.evaluate("state.viewSeat")
        supply = page.evaluate("seat => state.view.players[seat].troops_supply", actor)
        generated = [0] * 4
        generated[actor] = 1
        act(page, "reveal_turn")
        act(page, "generate_reveal_specimens")
        check.ok(
            page.evaluate("seat => state.view.players[seat].specimens", actor) == 1
            and page.evaluate("seat => state.view.players[seat].troops_supply", actor)
            == supply - 1,
            "actual Experimentation reveal moves one supply troop into specimens",
        )
        if has_scan:
            pieces_match(page, small, generated, "after actual generation")
            page.locator("#market .bt-open").click()
            pieces_match(page, large, generated, "initial enlarged tanks")
        act(page, "return_specimen")
        check.ok(
            page.evaluate("seat => state.view.players[seat].specimens", actor) == 0
            and page.evaluate("seat => state.view.players[seat].troops_supply", actor)
            == supply,
            "actual specimen return restores the troop supply",
        )
        if has_scan:
            pieces_match(page, small, [0] * 4, "after actual return")
            pieces_match(page, large, [0] * 4, "open zoom follows the actual return")
            page.evaluate("closeBeneTleilaxZoom()")
            for language in ("ko", "en"):
                switch(page, language)
                for width in (1366, 1920):
                    page.set_viewport_size({"width": width, "height": 1000})
                    counts = [1, 2, 3, 4]
                    set_counts(page, counts)
                    pieces_match(page, small, counts, f"{language} column {width}px")
                    page.locator("#market .bt-open").click()
                    pieces_match(page, large, counts, f"{language} zoom {width}px")
                    counts = [12] * 4
                    set_counts(page, counts)
                    pieces_match(page, small, counts, f"{language} full tank {width}px")
                    pieces_match(page, large, counts, f"{language} full zoom {width}px")
                    page.screenshot(
                        path=str(SHOTS / f"specimens_{language}_{width}.png")
                    )
                    set_counts(page, [0] * 4)
                    pieces_match(page, large, [0] * 4, "all spent / returned")
                    page.evaluate("closeBeneTleilaxZoom()")
        else:
            print("SKIP scan geometry: no machine-local Bene Tleilax image")

        page.evaluate("state.catalog.bene_tleilax.image = null")
        for language in ("ko", "en"):
            switch(page, language)
            set_counts(page, [0, 1, 6, 12])
            summary = page.locator(".bt-specimens-summary")
            rows = summary.locator(".bt-specimens-count").all_inner_texts()
            check.ok(
                len(rows) == 4
                and all(
                    ("플레이어" if language == "ko" else "Player ") + str(seat + 1)
                    in rows[seat]
                    and str(count) in rows[seat]
                    for seat, count in enumerate([0, 1, 6, 12])
                )
                and summary.locator(".bt-specimen-swatch").count() == 4,
                f"{language}: text fallback retains all four specimen counts",
                rows,
            )
        context.close()
    print(f"Screenshots: {SHOTS}")
    check.finish()


if __name__ == "__main__":
    main()
