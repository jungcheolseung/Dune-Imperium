"""E2E of the unit stepper and of the Reveal shop.

Both are views of the server's flat action list, like the staged Agent turn:
"deploy 1 / deploy 2 / ..." is one row with a number in it (in the panel and,
when the board is large enough, in the plain desert above the Conflict,
sharing the number; a narrow board leaves it to the panel), previewed
with the engine's own strength figure (`strength_after`, from the server's
dry run); a Reveal shows the Persuasion still unspent (the summary carries
it), what has been bought (the session log), the cards that can be bought
with their cost, and one clear way out.
"""

from __future__ import annotations

import json
import shutil
import time

from common import (
    SERVER_LOG_COPY,
    Check,
    chrome,
    open_context,
    server,
    set_rule_options,
)
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


def troop_pieces(page) -> int:
    """The viewing seat's troop cubes standing in its Conflict quadrant."""
    return page.evaluate(
        "document.querySelectorAll(`.board-stage .conflict-unit"
        "[data-seat='${state.viewSeat}'][data-kind='troop']`).length"
    )


# The board's copy of the count rows shows only where its band (plain desert
# above the Conflict) holds it at a readable size: at 2400x1500 the board is
# about 1050 px, at 800x900 only 268 px and the rows stay in the panel.
LARGE = {"width": 2400, "height": 1500}
SMALL = {"width": 800, "height": 900}

# Everything the board draws that the stepper must not cover.
PIECES = (
    ".conflict-unit, .garrison-unit, .hotspot, .bonus-spice, .maker-hooks-token,"
    " .board-tile, .commander-piece, .spy-post, .control-marker, .slot-card"
)

STEPPER_JS = """(pieces) => {
  const stage = document.querySelector('.board-stage').getBoundingClientRect();
  const pct = (r) => ({
    left: (r.left - stage.left) / stage.width * 100,
    top: (r.top - stage.top) / stage.height * 100,
    width: r.width / stage.width * 100,
    height: r.height / stage.height * 100,
  });
  const control = document.querySelector('.board-stage .force-stepper');
  if (!control) return null;
  const tracks = state.catalog.tracks;
  return {
    shown: !control.hidden && control.getClientRects().length > 0,
    rect: pct(control.getBoundingClientRect()),
    font: parseFloat(getComputedStyle(control).fontSize),
    stage: stage.width,
    band: tracks.force_stepper_band,
    printed: [...tracks.garrison_units.rings, ...tracks.conflict_units.boxes],
    pieces: [...document.querySelectorAll('.board-stage :is(' + pieces + ')')]
      .map((node) => ({ what: node.className.baseVal ?? node.className,
                        rect: pct(node.getBoundingClientRect()) })),
  };
}"""


def next_frames(page) -> None:
    """Past the next paint: the stepper is fitted by a ResizeObserver."""
    page.evaluate(
        "new Promise((done) =>"
        " requestAnimationFrame(() => requestAnimationFrame(done)))"
    )


def board_stepper(page) -> dict | None:
    next_frames(page)
    return page.evaluate(STEPPER_JS, PIECES)


def meets(a: dict, b: dict) -> bool:
    return (
        a["left"] + a["width"] > b["left"]
        and b["left"] + b["width"] > a["left"]
        and a["top"] + a["height"] > b["top"]
        and b["top"] + b["height"] > a["top"]
    )


def stepper_in_its_band(info: dict, where: str) -> None:
    """Shown, inside the band, and on nothing the board draws or prints."""
    rect = info["rect"]
    left, top, width, height = info["band"]
    slack = 0.05
    check.ok(
        rect["left"] >= left - slack
        and rect["top"] >= top - slack
        and rect["left"] + rect["width"] <= left + width + slack
        and rect["top"] + rect["height"] <= top + height + slack,
        f"{where}: the board's stepper lies inside its band above the Conflict",
        (rect, info["band"]),
    )
    check.ok(
        abs(rect["top"] + rect["height"] - (top + height)) < 0.1
        and abs(rect["left"] + rect["width"] / 2 - (left + width / 2)) < 0.1,
        f"{where}: on the band's bottom edge, centred",
        rect,
    )
    covered = [p["what"] for p in info["pieces"] if meets(rect, p["rect"])]
    covered += [
        box
        for box in info["printed"]
        if meets(rect, dict(zip(("left", "top", "width", "height"), box, strict=True)))
    ]
    check.ok(
        not covered,
        f"{where}: it covers no piece, space, bonus spice, garrison ring or quadrant",
        covered[:4],
    )


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
    check.ok(board.count() == 1, "the same row stands on the board")
    # In the plain desert above the Conflict, on nothing the board shows.
    info = board_stepper(page)
    if check.ok(
        info is not None and info["shown"],
        f"a {info and round(info['stage'])} px board shows it",
        info and (info["shown"], info["font"]),
    ):
        stepper_in_its_band(info, "large window")
    # The window narrows: the same rows no longer fit, and the band hides
    # them without a new render (the node stays), and shows them again.
    page.evaluate("window.__stepper = document.querySelector('.force-stepper')")
    page.set_viewport_size(SMALL)
    narrow = board_stepper(page)
    same = "window.__stepper === document.querySelector('.force-stepper')"
    check.ok(
        page.evaluate(same) and narrow is not None and not narrow["shown"],
        "narrowed to 800x900, the board hides its stepper without a re-render",
        narrow and (narrow["stage"], narrow["shown"], narrow["font"]),
    )
    page.set_viewport_size(LARGE)
    wide = board_stepper(page)
    check.ok(
        page.evaluate(same) and wide is not None and wide["shown"],
        "widened again, it shows the same stepper again",
    )
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
    check.ok(
        troop_pieces(page) == after[0],
        "a troop cube stands in the seat's quadrant for each troop sent",
        (troop_pieces(page), after[0]),
    )

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
    check.ok(
        troop_pieces(page) == after[0] - least,
        "and its cube left the quadrant",
        (troop_pieces(page), after[0] - least),
    )


def narrow_deployment(base: str, browser) -> None:
    """A board too small for the stepper: the panel's row sends the units."""
    print("[1b] a narrow window (800x900): the panel sends the units")
    context, page, rec = open_context(browser, "narrow", SMALL)
    create_game(page, base, humans=(0,), seed=11)
    reached = play_until(
        page,
        "state.actions.actions"
        ".filter((a) => a.action_id === 'deploy_troops').length > 1",
        f"""(() => {{ const combat = {json.dumps(COMBAT)};
          const a = state.actions.actions.find((x) => x.action_id === 'agent_turn'
            && combat.includes(x.arguments.space_id));
          return a ? a.index : 0; }})()""",
    )
    if not check.ok(reached, "narrow: the seat may send troops"):
        context.close()
        return
    info = board_stepper(page)
    check.ok(
        info is None or not info["shown"],
        f"narrow: a {info and round(info['stage'])} px board shows no stepper",
        info and (info["shown"], info["font"]),
    )
    most = max(d["count"] for d in of_id(page, "deploy_troops"))
    before = page.evaluate(f"{SEAT}.troops_conflict")
    posts = rec.count("POST", "/actions")
    page.locator(
        "#actions .count-row[data-action='deploy_troops'] .count-confirm"
    ).click()
    assert settled(page, 20)
    after = page.evaluate(f"{SEAT}.troops_conflict")
    check.ok(
        after == before + most and rec.count("POST", "/actions") == posts + 1,
        "narrow: the panel's row sends them, with a single request",
        (before, most, after),
    )
    check.ok(
        troop_pieces(page) == after,
        "narrow: a troop cube stands in the quadrant for each",
        (troop_pieces(page), after),
    )
    context.close()


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


def tleilaxu_shop(base: str, browser) -> None:
    """A Tleilaxu Row card is acquired like an Imperium card, for specimens
    [Immortality p. 8]: the Reveal panel lists it among what was acquired
    (it once listed only Imperium and Reserve cards, 2026-09-27)."""
    print("[4] a Reveal that acquires from the Tleilaxu Row (Immortality)")
    context, page, rec = open_context(browser, "tleilaxu")
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(
            f"#seat-selects select[data-seat='{seat}']",
            "human" if seat == 0 else "heuristic",
        )
    set_rule_options(page, "immortality")
    page.fill("#opt-seed", "3")
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    reached = play_until(
        page,
        "state.actions.actions.some((a) => a.action_id === 'acquire_tleilaxu')",
        """(() => { const A = state.actions.actions;
          const pick = A.find((x) => x.action_id === 'generate_reveal_specimens');
          return pick ? pick.index : A[A.length - 1].index; })()""",
    )
    if not check.ok(reached, "the seat can acquire from the Tleilaxu Row"):
        context.close()
        return
    buys = page.evaluate(
        "state.actions.actions.filter((a) => a.action_id.startsWith('acquire')).length"
    )
    check.ok(
        page.locator("#actions .acquire-cost").count() == buys,
        "every card that can be acquired is listed with its cost (specimens too)",
        (page.locator("#actions .acquire-cost").count(), buys),
    )
    # Reclaimed Forces' row names the effect chosen, not the card; its cost
    # is the card's specimens all the same (a game rarely offers it here).
    reclaimed = page.evaluate(
        """() => {
          const node = acquireCostNode({action_id: 'acquire_reclaimed_forces',
                                        arguments: {choice: 'troops'}});
          return node ? node.textContent : null;
        }"""
    )
    specimens = page.evaluate("state.catalog.cards.reclaimed_forces.specimens")
    check.ok(
        reclaimed is not None and reclaimed.endswith(f" {specimens}"),
        "a Reclaimed Forces row shows its specimen cost",
        (reclaimed, specimens),
    )
    action = page.evaluate(
        "state.actions.actions.find((a) => a.action_id === 'acquire_tleilaxu'"
        " && !a.arguments.to_deck_top)"
    )
    card = page.evaluate("(id) => baseId(id)", action["arguments"]["instance_id"])
    page.evaluate(f"applyAction({action['index']})")
    assert settled(page, 20)
    # The oracle reads the cards section itself, never the panel's own lookup.
    name = page.evaluate("(id) => state.catalog.cards[id].name", card)
    bought = page.locator(".reveal-bought")
    check.ok(
        bought.count() == 1 and name in bought.inner_text(),
        "the panel lists the Tleilaxu card among what was acquired",
        (name, bought.inner_text() if bought.count() else None),
    )
    context.close()


def main() -> None:
    with server() as (base, server_log), chrome() as browser:
        try:
            context, page, rec = open_context(browser, "player", LARGE)
            create_game(page, base, humans=(0,), seed=11)
            deployment(page, rec)
            reveal_shop(page, rec)
            failed = [r for r in rec.requests if r[3] >= 400]
            check.ok(not failed, "no failed requests", failed[:5])
            check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
            context.close()
            narrow_deployment(base, browser)
            tleilaxu_shop(base, browser)
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
