"""The board's Conflict keeps its hover preview and opens the round history.

An actual finished game provides review states. Expectations come from the
initial board and the independently read public reveal events, including
the initial reveal absent from the session log. Check both languages,
details/back, keyboard, foreign refresh, empty slots and missing assets.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from common import Check, chrome, open_context, server, set_rule_options
from lang import switch

check = Check()
SHOTS = Path(
    os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(prefix="dune-conflicts-")
)


def seek(page, cursor: int) -> None:
    page.evaluate("async n => { stopPlayback(); await reviewGoto(n); }", cursor)
    # The snapshot is ready before the board/hand images and the layout
    # observer settle. A still-moving card can cancel its hover delay.
    page.wait_for_function("""() => [...document.querySelectorAll(
        '#board .board-map, .hand-cards .vcard:first-child img')]
        .every(i => i.complete && i.naturalWidth > 0)""")
    page.evaluate("""async () => {
        await new Promise(requestAnimationFrame);
        await new Promise(requestAnimationFrame);
    }""")


def trigger(page):
    return page.locator(
        "#board .slot-card.conflict, #market .vcard.conflict, .conflict-history-trigger"
    ).last


def history_matches(page, expected: list[dict], language: str, label: str) -> None:
    actual = page.eval_on_selector_all(
        "#card-popover .conflict-history-item",
        """nodes => nodes.map(n => ({
          round: Number(n.dataset.round),
          conflict_id: n.querySelector('.vcard').dataset.instance,
          name: n.querySelector('.conflict-history-name').textContent,
          expectedName: state.catalog.conflicts[
            n.querySelector('.vcard').dataset.instance].name,
          images: [...n.querySelectorAll('img')].map(i => i.getAttribute('src')),
          expectedImage: state.catalog.conflicts[
            n.querySelector('.vcard').dataset.instance].image || null,
          current: n.classList.contains('current'),
          roundLabel: n.querySelector('.conflict-history-round').textContent
        }))""",
    )
    check.ok(
        [{k: row[k] for k in ("round", "conflict_id")} for row in actual]
        == list(reversed(expected)),
        f"{label}: one card per revealed round, newest first",
        actual,
    )
    check.ok(
        all(
            row["name"] == row["expectedName"]
            and row["images"]
            == ([row["expectedImage"]] if row["expectedImage"] else [])
            and ("라운드" if language == "ko" else "Round") in row["roundLabel"]
            for row in actual
        ),
        f"{label}: localized round labels, card names and images",
    )
    current = page.evaluate("state.view.round_number")
    check.ok(
        [row["round"] for row in actual if row["current"]] == [current],
        f"{label}: only the current round is marked",
    )
    pop = page.locator("#card-popover")
    check.ok(
        pop.locator(".popover-title").inner_text()
        == ("교전 카드 이력" if language == "ko" else "Conflict card history")
        and page.evaluate("popoverPinned")
        and "hover" not in (pop.get_attribute("class") or ""),
        f"{label}: the history is pinned and interactive",
    )


def bounds(page, label: str) -> None:
    page.wait_for_function(
        "[...document.querySelectorAll('#card-popover img')]"
        ".every(i => i.complete && i.naturalWidth > 0)"
    )
    check.ok(
        page.evaluate("""() => {
          const p = document.getElementById('card-popover');
          const b = p.getBoundingClientRect();
          return b.left >= 0 && b.right <= innerWidth && b.top >= 0
            && b.bottom <= innerHeight && p.scrollWidth <= p.clientWidth + 1;
        }"""),
        f"{label}: the loaded history fits without horizontal overflow",
    )


def main() -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    with server() as (base, _), chrome() as browser:
        context, page, recorder = open_context(browser, "conflict-history")
        page.goto(base)
        page.wait_for_selector("#setup-screen:not([hidden])")
        for seat in range(4):
            page.select_option(f"#seat-selects select[data-seat='{seat}']", "heuristic")
        set_rule_options(page)
        page.set_checked("#opt-leader-draft", False)
        page.set_checked("#opt-scouts", False)
        page.fill("#opt-seed", "13")
        page.click("#create-game")
        page.wait_for_function("state.review !== null && state.view !== null")
        seek(page, 0)
        first = page.evaluate("state.view.current_conflict_ids[0]")
        expected = [{"round": 1, "conflict_id": first}]
        entries = page.evaluate("state.review.meta.log")
        reveal_steps = {}
        position = 0
        for entry in entries:
            if entry["type"] == "undo" or entry.get("undone"):
                continue
            position += 1
            for event in entry.get("events", []):
                if event["kind"] != "conflict_revealed":
                    continue
                payload = event["payload"]
                expected.append({k: payload[k] for k in ("round", "conflict_id")})
                reveal_steps[payload["round"]] = position
        check.ok(1 not in reveal_steps, "round 1 really predates the session log")

        for language in ("ko", "en"):
            switch(page, language)
            seek(page, 0)
            card = trigger(page)
            card.hover()
            page.wait_for_selector("#card-popover.hover:not([hidden])")
            name = page.evaluate("id => state.catalog.conflicts[id].name", first)
            check.ok(
                page.locator("#card-popover .popover-title").inner_text() == name,
                f"{language}: hovering still shows the current card's information",
            )
            card.click()
            history_matches(page, expected[:1], language, f"{language} first round")
            page.mouse.move(2, 2)
            check.ok(
                page.locator(".conflict-history").is_visible(),
                f"{language}: moving the pointer leaves the clicked history open",
            )
            page.keyboard.press("Escape")
            check.ok(page.locator("#card-popover").is_hidden(), "Escape closes history")

            seek(page, reveal_steps[3])
            card = trigger(page)
            card.focus()
            card.press("Enter")
            history_matches(page, expected[:3], language, f"{language} round 3")
            bounds(page, f"{language} desktop")
            # Opening an old card enlarges its own details, with a return
            # control. Neither operation posts a game action.
            oldest = page.locator(".conflict-history-item[data-round='1'] .vcard")
            oldest.click()
            check.ok(
                page.locator("#card-popover .popover-title").inner_text() == name
                and page.locator("#card-popover .conflict-history-back").is_visible(),
                f"{language}: a past card opens its detailed card view",
            )
            page.locator(".conflict-history-back").click()
            history_matches(page, expected[:3], language, f"{language} return")

            game_id = page.evaluate("state.gameId")
            next_view = page.request.get(
                f"{base}/games/{game_id}/review/{reveal_steps[4]}?seat=0"
            ).json()["view"]
            page.evaluate(
                "v => { state.view = v; state.review.round = v.round_number; "
                "render({foreign: true}); }",
                next_view,
            )
            history_matches(page, expected[:4], language, f"{language} foreign update")
            page.locator(".conflict-history-close").click()
            check.ok(
                page.locator("#card-popover").is_hidden(), "Close button closes history"
            )

            seek(page, page.evaluate("state.review.meta.step_count"))
            trigger(page).click()
            history_matches(page, expected, language, f"{language} finished game")
            page.set_viewport_size({"width": 390, "height": 844})
            page.evaluate("closePopover();")
            trigger(page).click()
            bounds(page, f"{language} narrow")
            page.screenshot(path=str(SHOTS / f"history_{language}_390.png"))
            page.keyboard.press("Escape")
            page.set_viewport_size({"width": 1600, "height": 1000})

        # Text-board and text-card fallback, with an empty Conflict slot
        # after the final award. The history itself retains all ten cards.
        page.evaluate("""() => {
          state.catalog.board_image = null;
          for (const card of Object.values(state.catalog.conflicts)) card.image = null;
          state.view.current_conflict_ids = [];
          render();
        }""")
        trigger(page).click()
        history_matches(page, expected, "en", "no assets / empty slot")
        check.ok(
            page.locator(".conflict-history .textcard").count() == len(expected),
            "without card images every past round still has a named text card",
        )
        check.ok(
            recorder.count("POST", "/actions") == 0,
            "viewing history and details never submits a game action",
        )
        context.close()
    print(f"Screenshots: {SHOTS}")
    check.finish()


if __name__ == "__main__":
    main()
