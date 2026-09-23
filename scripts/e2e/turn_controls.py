"""E2E of the unit stepper and of the Reveal shop.

Both are views of the server's flat action list, like the staged Agent turn:
"deploy 1 / deploy 2 / ..." is one row with a number in it (in the panel and
by the seat's units in the Conflict area, sharing the number), previewed
with the engine's own strength figure (`strength_after`, from the server's
dry run); a Reveal shows the Persuasion still unspent (the summary carries
it), what has been bought (the session log), the cards that can be bought
with their cost, and one clear way out.
"""

from __future__ import annotations

import json
import shutil
import time

from common import SERVER_LOG_COPY, Check, chrome, open_context, server
from open_mode import create_game, settled

check = Check()
COMBAT = ["hagga_basin", "imperial_basin", "arrakeen", "spice_refinery", "deep_desert"]
SEAT = "state.view.players[state.viewSeat]"


def play_until(page, wanted_js: str, choose_js: str, limit: int = 200) -> bool:
    """Apply `choose_js`'s index until `wanted_js` holds for the viewing seat."""
    for _ in range(limit):
        assert settled(page, 20)
        if page.evaluate("state.summary.finished"):
            return False
        if page.evaluate("state.summary.confirmation === state.viewSeat"):
            page.evaluate("confirmTurn()")
            continue
        if not page.evaluate("Boolean(state.actions && state.actions.actions.length)"):
            time.sleep(0.05)
            continue
        if page.evaluate(wanted_js):
            return True
        page.evaluate(f"applyAction({page.evaluate(choose_js)})")
    return False


def of_id(page, action_id: str) -> list[dict]:
    return page.evaluate(
        f"state.actions.actions.filter((a) => a.action_id === '{action_id}')"
        ".map((a) => ({ index: a.index, count: a.arguments.count,"
        " after: a.strength_after }))"
    )


def deployment(page, rec) -> None:
    print("[1] sending units: one row with a number, in the panel and on the board")
    reached = play_until(
        page,
        "state.actions.actions"
        ".filter((a) => a.action_id === 'deploy_troops').length > 1",
        f"""(() => {{ const combat = {json.dumps(COMBAT)};
          const a = state.actions.actions.find((x) => x.action_id === 'agent_turn'
            && combat.includes(x.arguments.space_id));
          return a ? a.index : 0; }})()""",
    )
    if not check.ok(reached, "the seat may send more than one troop"):
        return
    deploys = of_id(page, "deploy_troops")
    rows = page.locator("#actions .count-row[data-action='deploy_troops']")
    check.ok(rows.count() == 1, "the panel folds the counts into one row")
    # finish_agent_turn can be legal here too (a Combat-space deployment is
    # open): it never doubles as an #actions item, appearing only as the
    # banner's turn-end row (render.js EXPLICIT_TURN_END_IDS).
    others = page.evaluate(
        "state.actions.actions.filter((a) => a.action_id !== 'deploy_troops'"
        " && !EXPLICIT_TURN_END_IDS.has(a.action_id)).length"
    )
    check.ok(
        page.locator("#actions .action-item").count() == others + 1,
        "beside the turn's other actions",
    )
    board = page.locator(".force-stepper .count-row[data-action='deploy_troops']")
    check.ok(board.count() == 1, "the same row stands by the seat's units on the board")
    most = max(d["count"] for d in deploys)
    shown = (
        "[...document.querySelectorAll("
        "'.count-row[data-action=\\'deploy_troops\\'] .stepper-value')]"
        ".map((n) => Number(n.textContent))"
    )
    check.ok(
        page.evaluate(shown) == [most, most],
        "both start on all of them",
        page.evaluate(shown),
    )

    posts = rec.count("POST", "/actions")
    board.locator(".stepper button").first.click()
    check.ok(
        page.evaluate(shown) == [most - 1, most - 1],
        "a step on the board moves the panel's number too",
        page.evaluate(shown),
    )
    check.ok(rec.count("POST", "/actions") == posts, "choosing a number sends nothing")

    chosen = next(d for d in deploys if d["count"] == most - 1)
    before = page.evaluate(f"[{SEAT}.troops_conflict, {SEAT}.combat_strength]")
    label = page.locator(
        "#actions .count-row[data-action='deploy_troops'] .count-confirm"
    )
    check.ok(
        f"{before[1]} → {chosen['after']}" in label.inner_text(),
        "the button previews the server's strength for that number",
        label.inner_text(),
    )
    label.click()
    assert settled(page, 20)
    after = page.evaluate(f"[{SEAT}.troops_conflict, {SEAT}.combat_strength]")
    check.ok(
        after == [before[0] + chosen["count"], chosen["after"]],
        "that many troops went in, to exactly the previewed strength",
        (before, after),
    )
    check.ok(rec.count("POST", "/actions") == posts + 1, "with a single request")

    print("[2] taking units back")
    withdraws = of_id(page, "withdraw_troops")
    if not check.ok(bool(withdraws), "the sent troops can be taken back this turn"):
        return
    row = page.locator(".force-stepper .count-row[data-action='withdraw_troops']")
    check.ok(row.count() == 1, "the board offers it, even for a single count")
    least = min(w["count"] for w in withdraws)
    back = next(w for w in withdraws if w["count"] == least)
    row.locator(".count-confirm").click()
    assert settled(page, 20)
    check.ok(
        page.evaluate(f"[{SEAT}.troops_conflict, {SEAT}.combat_strength]")
        == [after[0] - least, back["after"]],
        "one troop came back, to the previewed strength",
    )


def reveal_shop(page, rec) -> None:
    print("[3] a Reveal: the Persuasion left, the cards to buy, one way out")
    reached = play_until(
        page,
        "state.summary.decision && state.summary.decision.kind === 'reveal'"
        " && state.summary.decision.owner === state.viewSeat",
        """(() => { const A = state.actions.actions;
          const pick = A.find((x) => x.action_id === 'reveal_turn')
            || A.find((x) => x.action_id === 'finish_agent_turn');
          return pick ? pick.index : 0; })()""",
    )
    if not check.ok(reached, "the seat reveals"):
        return
    unspent = page.evaluate("state.summary.decision.persuasion")
    check.ok(
        isinstance(unspent, int), "the summary carries the unspent Persuasion", unspent
    )
    check.ok(
        page.evaluate(
            "Number(document.querySelector('.reveal-persuasion').dataset.persuasion)"
        )
        == unspent,
        "and the panel shows it",
    )
    buys = page.evaluate(
        "state.actions.actions.filter((a) => a.action_id.startsWith('acquire')).length"
    )
    check.ok(
        page.locator("#actions .acquire-cost").count() == buys and buys > 0,
        "every card that can be bought is listed with its cost",
        (page.locator("#actions .acquire-cost").count(), buys),
    )
    # finish_reveal is the seat's explicit turn-end action: it is pulled out
    # of the panel and shown as the banner's turn-end row instead (render.js
    # turnEndAction / appendTurnEndRow), never as an #actions item, though it
    # stays in the raw legal-action list the server sends.
    finish = page.evaluate(
        "state.actions.actions.find((a) => a.action_id === 'finish_reveal')"
    )
    check.ok(
        finish is not None
        and not page.evaluate(
            "[...document.querySelectorAll('#actions .action-item')]"
            f".some((n) => Number(n.dataset.index) === {finish['index']})"
        ),
        "finish_reveal is not among the panel's items",
    )
    check.ok(
        page.locator(".turn-end-row button").count() == 1,
        "the way out is the banner's turn-end row",
    )
    # The prefix follows whether the Reveal still offers buyable cards
    # (isAcquire actions among state.actions.actions), not whether anything
    # has been bought yet -- so it already shows here, before any purchase,
    # since `buys > 0` was just asserted above.
    check.ok(
        "구매 끝" in page.locator(".turn-end-row button").inner_text(),
        "the turn-end row carries the prefix while buyable cards remain",
        page.locator(".turn-end-row button").inner_text(),
    )

    lit = page.evaluate(
        "[...document.querySelectorAll('#market .vcard.legal')]"
        ".map((n) => n.dataset.instance)"
    )
    if not check.ok(bool(lit), "the cards that can be bought are lit on the table"):
        return
    cost = page.evaluate(f"lookup(baseId('{lit[0]}')).cost")
    page.click(f"#market .vcard[data-instance='{lit[0]}']")
    assert settled(page, 20)
    check.ok(
        page.evaluate("state.summary.decision.persuasion") == unspent - cost,
        "a click on a lit card buys it for its cost",
        (unspent, cost, page.evaluate("state.summary.decision.persuasion")),
    )
    name = page.evaluate(f"lookup(baseId('{lit[0]}')).name")
    check.ok(
        name in page.locator(".reveal-bought").inner_text(),
        "the panel lists what has been bought",
        page.locator(".reveal-bought").inner_text(),
    )
    still_buyable = page.evaluate(
        "state.actions.actions.some((a) => a.action_id.startsWith('acquire'))"
    )
    check.ok(
        ("구매 끝" in page.locator(".turn-end-row button").inner_text()) == still_buyable,
        "and after the purchase, the prefix follows what remains buyable, not the purchase",
        (page.locator(".turn-end-row button").inner_text(), still_buyable),
    )
    page.click(".turn-end-row button")
    assert settled(page, 20)
    # finish_reveal is an explicit turn-end action: applying it seals the
    # turn and hands over at once (server/turn_end.py EXPLICIT_TURN_ENDS),
    # so this seat is never held for a second press afterwards.
    check.ok(
        page.evaluate("state.summary.confirmation !== state.viewSeat"),
        "the way out never holds this seat for a second press",
    )
    check.ok(
        page.evaluate(
            "!state.summary.decision || state.summary.decision.kind !== 'reveal'"
            " || state.summary.decision.owner !== state.viewSeat"
        ),
        "and ends the Reveal",
    )


def main() -> None:
    with server() as (base, server_log), chrome() as browser:
        try:
            context, page, rec = open_context(browser, "player")
            create_game(page, base, humans=(0,), seed=11)
            deployment(page, rec)
            reveal_shop(page, rec)
            failed = [r for r in rec.requests if r[3] >= 400]
            check.ok(not failed, "no failed requests", failed[:5])
            check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
            context.close()
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
