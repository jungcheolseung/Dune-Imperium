"""E2E of the staged Agent turn (card, then space, then what is left).

The server offers an Agent turn as one flat list of `agent_turn` actions;
the page shows it in steps and posts the one index the pick comes down to.
This checks the view against that list at every step: what is lit is
exactly what the list allows, a pick costs no request, either order works,
a pick can be swapped or cancelled, a complete pick plays the very action it
names, the chooser offers exactly the remaining ones, and the flat list is
one toggle away.

A saved game (fixtures/navigation_chamber_saves.py) checks Navigation
Chamber's cut, which is mandatory (OQ-104, codec v142): no costed space is
offered at full price, the chooser names the cut ("1 spice discount") on the
Spice Refinery line that carries it, with the printed cost struck through
and the paid one after it, and never says "no discount" on the free line.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from common import (
    REPO,
    SERVER_LOG_COPY,
    Check,
    ServerProcess,
    chrome,
    open_context,
    server,
    set_rule_options,
)
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
    # finish_agent_turn is the seat's explicit turn-end action: it never
    # doubles as an #actions item, appearing only as the banner's turn-end
    # row (render.js EXPLICIT_TURN_END_IDS / turnEndAction).
    others = page.evaluate(
        "state.actions.actions.filter((a) => a.action_id !== 'agent_turn'"
        " && !EXPLICIT_TURN_END_IDS.has(a.action_id)).length"
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
    # finish_agent_turn is never legal at this point (a fresh turn start,
    # before any Combat-space deployment is open); that it is pulled out of
    # #actions when it IS legal is checked where it happens,
    # turn_end.py's check_finish_agent_turn (combined_scenarios [c]).
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
        total = page.evaluate(
            "state.actions.actions.filter((a) =>"
            " !EXPLICIT_TURN_END_IDS.has(a.action_id)).length"
        )
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


GRAFTS = """() => placementActions().filter((a) => a.arguments.graft === true)
  .map((a) => ({ card: a.arguments.card_id, space: a.arguments.space_id }))"""


def graft_scenario(base, browser) -> None:
    """Two cards first: a graft pair reaches the union of the two cards' spaces."""
    print("[7] a graft pair: both cards first, then the space")
    context, page, rec = open_context(browser, "grafter")
    grafts: list[dict] = []
    for seed in range(1, 7):
        page.goto(base + "/")
        page.wait_for_selector("#setup-screen:not([hidden])")
        for seat in range(4):
            page.select_option(
                f"#seat-selects select[data-seat='{seat}']",
                "human" if seat == 0 else "heuristic",
            )
        set_rule_options(page, "immortality")
        page.fill("#opt-seed", str(seed))
        page.click("#create-game")
        page.wait_for_selector("#game-screen:not([hidden])")
        page.wait_for_function("state.view !== null && refreshFlight === null")
        # Acquire cards now and then, so that Graft cards reach the hand.
        for step in range(500):
            assert settled(page, 20)
            if page.evaluate("state.summary.finished"):
                break
            if page.evaluate("state.summary.confirmation === state.viewSeat"):
                page.evaluate("confirmTurn()")
                continue
            count = page.evaluate("state.actions ? state.actions.actions.length : 0")
            if not count:
                time.sleep(0.05)
                continue
            grafts = page.evaluate(GRAFTS)
            if grafts:
                break
            last = step % 3 == 0 and count > 1
            page.evaluate(f"applyAction({count - 1 if last else 0})")
        if grafts:
            break
        page.click("#leave-game")
    if not grafts:
        print("  .. no graft placement within six games; skipped")
        context.close()
        return

    first = grafts[0]["card"]
    page.click(f".hand-cards .vcard[data-instance='{first}']")
    partners = page.evaluate(
        "[...document.querySelectorAll('.hand-cards .vcard.partner')]"
        ".map((n) => n.dataset.instance)"
    )
    check.ok(
        len(partners) > 0, "the cards that can be grafted to it are marked", partners
    )
    graft_cards = page.evaluate(
        "state.view.private.hand.filter((id) => isGraftCard(id))"
    )
    check.ok(
        all(first in graft_cards or p in graft_cards for p in partners),
        "every marked pair has a Graft card in it",
        (first, partners, graft_cards),
    )
    second = partners[0]
    page.click(f".hand-cards .vcard[data-instance='{second}']")
    check.ok(
        page.evaluate("state.pick && state.pick.partnerId") == second
        and page.evaluate("state.pick.cardId") == first,
        "the second card joins the pick instead of replacing it",
    )
    union = sorted({g["space"] for g in grafts if g["card"] in (first, second)})
    check.ok(
        page.evaluate(LIT_SPACES) == union,
        "the lit spaces are the union of the two cards' graft placements",
        (page.evaluate(LIT_SPACES), union),
    )
    check.ok(
        page.locator(".hand-cards .vcard.picked").count() == 2,
        "both cards are marked as picked",
    )

    posts = rec.count("POST", "/actions")
    revision = page.evaluate("state.summary.revision")
    space = union[0]
    page.click(f".hotspot[data-space='{space}']")
    if page.locator("#card-popover .action-item").count():
        page.locator("#card-popover .action-item > button").first.click()
    played = wait_for(
        page,
        "!state.busy && refreshFlight === null && state.summary.decision"
        " && state.summary.decision.kind !== 'turn'"
        " && state.summary.decision.kind !== 'graft_partner'",
        10,
    )
    check.ok(played, "the placement and the partner were both played")
    check.ok(
        rec.count("POST", "/actions") == posts + 2
        and page.evaluate("state.summary.revision") == revision + 2,
        "as the engine's own two steps",
        (
            rec.count("POST", "/actions") - posts,
            page.evaluate("state.summary.revision") - revision,
        ),
    )
    in_play = page.evaluate("state.view.players[state.viewSeat].in_play")
    check.ok(first in in_play and second in in_play, "both cards are in play", in_play)
    check.ok(
        page.evaluate(
            f"state.view.players[state.viewSeat].agent_locations.includes('{space}')"
        ),
        "and the Agent stands on the picked space",
    )
    failed = [r for r in rec.requests if r[3] >= 400]
    check.ok(not failed, "no failed requests in the graft game", failed[:5])
    check.ok(not rec.js_errors, "no JS exceptions in the graft game", rec.js_errors[:5])
    context.close()


# Board spaces with a spice or Solari cost [Board Guide pp. 1-2]: with
# Navigation Chamber each is offered only with the cut (OQ-104).
COSTED_SPACES = [
    "sardaukar",
    "heighliner",
    "espionage",
    "shipping",
    "high_council",
    "imperial_privilege",
    "swordmaster",
]
REFINERY_CARD = """() => {
  const byCard = {};
  for (const a of placementActions()) {
    if (a.arguments.space_id !== "spice_refinery" || a.arguments.graft) continue;
    (byCard[a.arguments.card_id] ||= []).push(a);
  }
  return Object.keys(byCard).find((card) => byCard[card].length === 2
    && byCard[card].some((a) => a.arguments.discount === "spice")) || null;
}"""
CHOOSER_LINES = """() => [...document.querySelectorAll("#card-popover .action-item")]
  .map((node) => {
    const action = state.actions.actions[Number(node.dataset.index)];
    const cut = node.querySelector(".pick-option > .pick-discount");
    const printed = node.querySelector(".pick-option > .cost-printed");
    return {
      index: action.index,
      option: action.arguments.cost_option ?? null,
      discount: action.arguments.discount ?? null,
      text: node.innerText,
      cut: cut ? cut.textContent : null,
      cutTitle: cut && cut.querySelector(".amount")
        ? cut.querySelector(".amount").title : null,
      printed: printed ? printed.textContent : null,
      paid: [...node.querySelectorAll(".pick-option > .cost:not(.cost-printed)")]
        .map((c) => c.textContent),
    };
  })"""


def navigation_chamber_scenario(browser) -> None:
    print("[8] Navigation Chamber: the cut is named on the line that carries it")
    saves = tempfile.mkdtemp(prefix="dune-staged-nav-")
    produced = subprocess.run(
        [
            str(REPO / ".venv/bin/python"),
            str(Path(__file__).parent / "fixtures/navigation_chamber_saves.py"),
            saves,
        ],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    )
    fixture = json.loads(produced.stdout.strip().splitlines()[-1])
    process = ServerProcess(saves=saves).start()
    try:
        context, page, rec = open_context(browser, "navigator")
        page.goto(process.base + "/")
        page.wait_for_function(
            "document.querySelectorAll('#save-list li').length === 1"
        )
        page.locator(
            "#save-list li:has-text('navigation-chamber') button"
        ).first.click()
        page.wait_for_function("state.view !== null && refreshFlight === null")
        assert settled(page, 20)
        check.ok(
            page.evaluate("state.viewSeat") == fixture["seat"],
            "the saved game opens on the seat holding Navigation Chamber",
            (page.evaluate("state.viewSeat"), fixture["seat"]),
        )
        check.ok(
            "navigation_chamber"
            in page.evaluate("state.view.players[state.viewSeat].tech_ids || []"),
            "the seat holds Navigation Chamber",
        )
        check.ok(page.evaluate("stagedTurn()"), "its Agent turn is staged")
        full_price = page.evaluate(
            "(costed) => placementActions().filter((a) =>"
            " costed.includes(a.arguments.space_id) && !a.arguments.discount).length",
            COSTED_SPACES,
        )
        check.ok(
            full_price == 0, "no costed space is offered at full price", full_price
        )
        card = page.evaluate(REFINERY_CARD)
        check.ok(card is not None, "a card reaches both Spice Refinery options")
        if card is None:
            context.close()
            return
        spice = page.evaluate("state.view.players[state.viewSeat].resources.spice")
        for lang, free, suffix, no_cut in (
            ("ko", "무료", "할인", "할인 없이"),
            ("en", "Free", "discount", "No discount"),
        ):
            page.evaluate("lang => setLanguage(lang)", lang)
            page.evaluate("clearPick()")
            page.click(f".hand-cards .vcard[data-instance='{card}']")
            page.click(".hotspot[data-space='spice_refinery']")
            lines = page.evaluate(CHOOSER_LINES)
            check.ok(len(lines) == 2, f"{lang}: the chooser offers both options", lines)
            plain = next((line for line in lines if line["option"] == 0), None)
            cut = next((line for line in lines if line["option"] == 1), None)
            if plain is None or cut is None:
                continue
            check.ok(
                plain["discount"] is None
                and plain["cut"] is None
                and plain["printed"] is None
                and no_cut not in plain["text"],
                f"{lang}: the free option names no cut and no missing one",
                plain,
            )
            spice_word = page.evaluate("termLabel('spice')")
            check.ok(
                cut["discount"] == "spice"
                and cut["cut"] is not None
                and cut["cut"].strip().endswith(suffix)
                and cut["cutTitle"] == f"1 {spice_word}",
                f"{lang}: the cut option names the 1 spice cut",
                cut,
            )
            check.ok(
                cut["printed"] == "1" and cut["paid"] == [free],
                f"{lang}: the printed 1 spice is struck through, then what is paid",
                cut,
            )
            shots = os.environ.get("E2E_SHOTS_DIR")
            if shots:
                Path(shots).mkdir(parents=True, exist_ok=True)
                page.screenshot(
                    path=str(Path(shots) / f"staged_turn_navigation_chamber_{lang}.png")
                )
        before = page.evaluate("state.summary.revision")
        page.click(f"#card-popover .action-item[data-index='{cut['index']}'] > button")
        check.ok(
            wait_for(page, f"state.summary.revision === {before + 1} && !state.busy"),
            "the cut option was played",
        )
        after = page.evaluate("state.view.players[state.viewSeat].resources.spice")
        check.ok(after == spice, "the trade cost no spice", (spice, after))
        failed = [r for r in rec.requests if r[3] >= 400]
        check.ok(not failed, "no failed requests in the saved game", failed[:5])
        check.ok(
            not rec.js_errors, "no JS exceptions in the saved game", rec.js_errors[:5]
        )
        context.close()
        text = process.log_path.read_text()
        check.ok(
            "Traceback" not in text and "ERROR" not in text,
            "no server errors in the saved game",
        )
    finally:
        process.stop()


def main() -> None:
    with server() as (base, server_log), chrome() as browser:
        try:
            scenario(base, browser)
            graft_scenario(base, browser)
            navigation_chamber_scenario(browser)
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
