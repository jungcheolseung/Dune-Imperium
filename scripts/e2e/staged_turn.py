"""E2E of the staged Agent turn (card, then space, then what is left).

The server offers an Agent turn as one flat list of `agent_turn` actions;
the page shows it in steps and posts the one index the pick comes down to.
This checks the view against that list at every step: what is lit is
exactly what the list allows, a pick costs no request, either order works,
a pick can be swapped or cancelled, a complete pick plays the very action it
names, the chooser offers exactly the remaining ones, and the flat list is
one toggle away.
"""

from __future__ import annotations

import shutil
import time

from common import SERVER_LOG_COPY, Check, chrome, open_context, server
from open_mode import create_game, settled

check = Check()

PLACEMENTS = """() => placementActions().map((a) => ({
  index: a.index, card: a.arguments.card_id, space: a.arguments.space_id }))"""
LIT_CARDS = """() => [...document.querySelectorAll('.hand-cards .vcard.legal')]
  .map((n) => n.dataset.instance).sort()"""
LIT_SPACES = """() => [...document.querySelectorAll('.hotspot.legal')]
  .map((n) => n.dataset.space).sort()"""


def wait_for(page, predicate_js: str, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if page.evaluate(predicate_js):
            return True
        time.sleep(0.02)
    return False


def to_agent_turn(page) -> list[dict]:
    """Play first legal actions until this seat is offered placements again."""
    for _ in range(200):
        assert settled(page)
        placements = page.evaluate(PLACEMENTS)
        if placements or page.evaluate("state.summary.finished"):
            return placements
        if page.evaluate("state.actions && state.actions.actions.length > 0"):
            page.evaluate("applyAction(0)")
        elif page.evaluate("state.summary.confirmation === state.viewSeat"):
            page.evaluate("confirmTurn()")
        else:
            time.sleep(0.05)
    return []


def scenario(base, browser) -> None:
    context, page, rec = open_context(browser, "player")
    create_game(page, base, humans=(0,))
    placements = to_agent_turn(page)
    check.ok(len(placements) > 1, "the seat is offered placements", len(placements))

    print("[1] the panel shows steps, not the flat list")
    others = page.evaluate(
        "state.actions.actions.filter((a) => a.action_id !== 'agent_turn').length"
    )
    check.ok(page.evaluate("stagedTurn()"), "the turn is staged")
    check.ok(
        page.locator("#actions .pick-steps").count() == 1, "the two steps are shown"
    )
    check.ok(
        page.locator("#actions .action-item").count() == others,
        "only the turn's other actions are listed",
        (page.locator("#actions .action-item").count(), others),
    )
    cards = sorted({p["card"] for p in placements})
    spaces = sorted({p["space"] for p in placements})
    check.ok(
        page.evaluate(LIT_CARDS) == cards, "every playable card is lit, and no other"
    )
    check.ok(
        page.evaluate(LIT_SPACES) == spaces,
        "every reachable space is lit, and no other",
    )

    print("[2] a card: only its spaces stay lit, and nothing is sent")
    posts = rec.count("POST", "/actions")
    revision = page.evaluate("state.summary.revision")
    card = cards[0]
    page.click(f".hand-cards .vcard[data-instance='{card}']")
    check.ok(
        page.evaluate("state.pick && state.pick.cardId") == card, "the card is the pick"
    )
    of_card = sorted({p["space"] for p in placements if p["card"] == card})
    check.ok(page.evaluate(LIT_SPACES) == of_card, "only that card's spaces are lit")
    check.ok(
        page.locator(f".hand-cards .vcard.picked[data-instance='{card}']").count() == 1,
        "the card is marked as picked",
    )
    check.ok(
        rec.count("POST", "/actions") == posts
        and page.evaluate("state.summary.revision") == revision,
        "a pick sends nothing",
    )

    print("[3] cancel, swap, and the space first")
    page.keyboard.press("Escape")
    check.ok(page.evaluate("state.pick") is None, "Escape cancels the pick")
    check.ok(page.evaluate(LIT_SPACES) == spaces, "every reachable space is lit again")
    page.click(f".hand-cards .vcard[data-instance='{card}']")
    other = next((c for c in cards if c != card), None)
    if other is not None:
        page.click(f".hand-cards .vcard[data-instance='{other}']")
        check.ok(
            page.evaluate("state.pick && state.pick.cardId") == other,
            "another card swaps the pick",
        )
    page.keyboard.press("Escape")
    space = spaces[0]
    page.click(f".hotspot[data-space='{space}']")
    check.ok(
        page.evaluate("state.pick && state.pick.spaceId") == space,
        "a space can come first",
    )
    to_space = sorted({p["card"] for p in placements if p["space"] == space})
    check.ok(
        page.evaluate(LIT_CARDS) == to_space, "only the cards that reach it are lit"
    )
    page.click("#actions .pick-step.done")
    check.ok(page.evaluate("state.pick") is None, "the step chip clears its pick")

    print("[4] a complete pick plays the one action it names")
    by_pair: dict[tuple[str, str], list[int]] = {}
    for p in placements:
        by_pair.setdefault((p["card"], p["space"]), []).append(p["index"])
    (card, space), (index,) = next(
        (pair, idx) for pair, idx in by_pair.items() if len(idx) == 1
    )
    wanted = page.evaluate(f"state.actions.actions[{index}].arguments")
    page.click(f".hand-cards .vcard[data-instance='{card}']")
    page.click(f".hotspot[data-space='{space}']")
    check.ok(
        wait_for(page, f"state.summary.revision === {revision + 1} && !state.busy"),
        "one step was played",
    )
    check.ok(page.evaluate("state.pick") is None, "the pick is gone")
    check.ok(
        page.evaluate(
            f"state.view.players[state.viewSeat].agent_locations.includes('{space}')"
        ),
        "the Agent stands on the picked space",
        wanted,
    )
    check.ok(
        rec.count("POST", "/actions") == posts + 1,
        "with a single request",
        rec.count("POST", "/actions"),
    )

    print("[5] a pick with several placements left opens the chooser")
    found = None
    for _ in range(40):
        placements = to_agent_turn(page)
        if not placements:
            break
        pairs: dict[tuple[str, str], list[int]] = {}
        for p in placements:
            pairs.setdefault((p["card"], p["space"]), []).append(p["index"])
        found = next(((pair, idx) for pair, idx in pairs.items() if len(idx) > 1), None)
        if found:
            break
        page.evaluate("applyAction(0)")
    if found is None:
        print("  .. no card and space with several placements in this game; skipped")
    else:
        (card, space), indexes = found
        before = page.evaluate("state.summary.revision")
        page.click(f".hand-cards .vcard[data-instance='{card}']")
        page.click(f".hotspot[data-space='{space}']")
        check.ok(
            page.evaluate("state.summary.revision") == before,
            "several left: nothing is sent yet",
        )
        offered = page.evaluate(
            "[...document.querySelectorAll('#card-popover .action-item')]"
            ".map((n) => Number(n.dataset.index))"
        )
        check.ok(
            sorted(offered) == sorted(indexes),
            "the chooser offers exactly those",
            offered,
        )
        listed = page.evaluate(
            "[...document.querySelectorAll('#actions .pick-hint ~ .action-item')]"
            ".map((n) => Number(n.dataset.index)).filter((i) => "
            "state.actions.actions[i].action_id === 'agent_turn')"
        )
        check.ok(sorted(listed) == sorted(indexes), "and so does the panel", listed)
        chosen = indexes[-1]
        wanted = page.evaluate(f"state.actions.actions[{chosen}].arguments")
        page.click(f"#card-popover .action-item[data-index='{chosen}'] > button")
        check.ok(
            wait_for(page, f"state.summary.revision === {before + 1} && !state.busy"),
            "the chosen option was played",
            wanted,
        )

    print("[6] the flat list is one toggle away, and the choice is remembered")
    placements = to_agent_turn(page)
    if placements:
        total = page.evaluate("state.actions.actions.length")
        page.click("#actions .action-list-toggle")
        check.ok(not page.evaluate("stagedTurn()"), "the toggle leaves the staged view")
        check.ok(
            page.locator("#actions .action-item").count() == total,
            "every legal action is listed",
            (page.locator("#actions .action-item").count(), total),
        )
        page.reload()
        page.wait_for_function("state.view !== null && refreshFlight === null")
        check.ok(not page.evaluate("stagedTurn()"), "a reload keeps the flat list")
        page.click("#actions .action-list-toggle")
        check.ok(page.evaluate("stagedTurn()"), "the toggle brings the steps back")
    else:
        print("  .. the game ended first; skipped")

    failed = [r for r in rec.requests if r[3] >= 400]
    check.ok(not failed, "no failed requests", failed[:5])
    check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
    context.close()


def main() -> None:
    with server() as (base, server_log), chrome() as browser:
        try:
            scenario(base, browser)
        finally:
            shutil.copy(server_log, SERVER_LOG_COPY)
        text = server_log.read_text()
        check.ok(
            "Traceback" not in text and "ERROR" not in text,
            f"no server errors (see {SERVER_LOG_COPY})",
        )
    check.finish()


if __name__ == "__main__":
    main()
