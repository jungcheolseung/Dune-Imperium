"""Guild Accord's Heighliner cut as a graft partner in the browser (stage P7g
of docs/base-game-and-ix-plan.md, OQ-158).

"Both played cards are considered to have “sent” the Agent, no matter which
card’s icon you use." [Immortality p. 10]; Ghola "copies the entire Agent
box" [Immortality p. 14], Guild Accord's cut included (OQ-158). The cost is
paid as the Agent goes and the partner is chosen next, so a graft placement
on the Heighliner promises its partner's cut and the partner choice keeps
only the cards that give exactly that cut.

The table comes from fixtures/guild_accord_table.py (a play server of its
own: an original + Rise of Ix + Immortality game at seat 0's first turn,
seat 0 given Guild Accord, Ghola and Usurp and 6 spice, twice), since no
searched game holds the three at once; tests/server's
test_guild_accord_placements pins the same rows.

[1] Guild Accord picked alone, then the Heighliner: the chooser lists it
    alone, grafted with no cut (its partner Usurp) and grafted with 2 more
    off (its partner Ghola), each line different and naming its partner and
    cut, in both languages; the promised line taken, the partner window
    offers Ghola alone, and Ghola taken, the seat paid 2 of the 6 spice.
[2] Guild Accord and Ghola picked together, then the Heighliner: the one
    placement that fits the pair goes at once and Ghola follows as its
    partner by itself; the seat paid 2 spice and no partner choice waits.
[3] Guild Accord alone grafted with no cut (its partner Usurp, 4 spice
    paid), then one undo press: the whole placement goes back, card pick
    included, and the pair placed afresh goes at once with Ghola. The same
    placement again, then an undo of its space pick alone (the server's one
    step): the server still holds Guild Accord grafted and lists no
    placements, and its Heighliner space picks name their partners
    themselves (Usurp for no cut, Ghola for 2 more off); Ghola picked as the
    partner, the Heighliner places the promised one at once and Ghola
    follows, 2 spice paid. Until 2026-10-31 those space picks named none, so
    both promises stayed, the chooser opened, and its no-cut line paid 4 and
    offered Usurp alone (Codex review of P7g).
[4] Guild Accord's grafted card pick sent alone and the page reloaded (a
    reload between the two posts): the same, the Heighliner's two lines in
    the chooser naming their partners, and the pair placed at once.
[0] First, the hand card's picture held back by the page's route (a slow
    picture, as a card scrolled into view loads lazily): the card already
    stands at its face's size, one click picks it, and the picture's arrival
    changes nothing. Until 2026-10-31 such a card was 4 px tall and grew
    under the press, which then fell on the strip while the release fell on
    the card, and the click was lost (a player's too).
Every page: no JS errors; the fixture server logs no Traceback.
"""

from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path

from common import PROJECT_PYTHON, REPO, Check, chrome, free_port, open_context
from open_mode import settled

check = Check()

GUILD_ACCORD = "imperium:guild_accord:0"
GHOLA = "tleilaxu:ghola:0"
USURP = "tleilaxu:usurp:0"
HEIGHLINER = "imperium_heighliner"
FIXTURE = Path(__file__).parent / "fixtures" / "guild_accord_table.py"

CHOOSER_JS = """([guild, ghola, usurp]) => {
  const pop = document.getElementById("card-popover");
  const norm = (s) => s.replace(/\\s+/g, " ").trim();
  return {
    open: Boolean(pop && !pop.hidden && pop.querySelector(".pick-option")),
    lines: [...pop.querySelectorAll(".pick-option")].map((n) => norm(n.textContent)),
    names: {guild: nameOf(guild), ghola: nameOf(ghola), usurp: nameOf(usurp)},
  };
}"""

TABLE_JS = """() => ({
  kind: state.summary.decision ? state.summary.decision.kind : null,
  partners: (state.actions ? state.actions.actions : [])
    .filter((row) => row.action_id === "choose_graft_partner")
    .map((row) => ({index: row.index, card: row.arguments.card_id})),
  spice: state.view.players[0].resources.spice,
  agents: state.view.players[0].agent_locations,
  confirmation: state.summary.confirmation,
})"""


def start_fixture() -> tuple[subprocess.Popen[bytes], str, list[str], Path]:
    port = free_port()
    saves = Path(tempfile.mkdtemp(prefix="dune-e2e-guild-accord-"))
    log = saves / "server.log"
    process = subprocess.Popen(
        [
            str(PROJECT_PYTHON),
            str(FIXTURE),
            "--port",
            str(port),
            "--saves-dir",
            str(saves),
        ],
        cwd=REPO,
        stdout=open(log, "w"),
        stderr=subprocess.STDOUT,
    )
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        text = log.read_text() if log.exists() else ""
        for line in text.splitlines():
            if line.startswith("READY "):
                return process, f"http://127.0.0.1:{port}", line.split()[1:], log
        if process.poll() is not None:
            raise RuntimeError(text)
        time.sleep(0.2)
    process.kill()
    raise RuntimeError("the fixture server did not start")


def open_table(page, base: str, game_id: str) -> None:
    page.goto(f"{base}/#game={game_id}")
    page.wait_for_selector("#game-screen:not([hidden])")
    # The staged turn needs the card picks' placements before a click.
    page.wait_for_function(
        "state.view !== null && refreshFlight === null && state.actions"
        " && (state.actions.agent_placements || []).length > 0"
    )
    settled(page)


def click_card(page, instance: str) -> None:
    page.click(f'#private-zone .vcard[data-instance="{instance}"]')
    settled(page)


def click_space(page, space: str) -> None:
    page.click(f'#board .hotspot[data-space="{space}"]')
    settled(page)


def open_chooser(page) -> None:
    """Guild Accord picked, then the Heighliner: the chooser open."""

    page.evaluate("state.pick = null; closePopover(); render()")
    settled(page)
    click_card(page, GUILD_ACCORD)
    click_space(page, HEIGHLINER)
    page.wait_for_selector("#card-popover .pick-option", timeout=10_000)


CARD_BOX_JS = """(id) => {
  const card = document.querySelector(`#private-zone .vcard[data-instance="${id}"]`);
  const img = card && card.querySelector("img");
  return card ? {height: card.getBoundingClientRect().height,
                 loaded: Boolean(img && img.complete && img.naturalHeight)} : null;
}"""


def held_picture(page, base: str, game_id: str) -> None:
    print("[0] the hand card holds its place before its picture arrives")
    held = []

    def hold(route) -> None:
        held.append(route)

    def picture(url: str) -> bool:
        return "Guild%20Accord" in url

    page.route(picture, hold)
    open_table(page, base, game_id)
    page.evaluate(
        '(id) => document.querySelector(`#private-zone .vcard[data-instance="${id}"]`)'
        ".scrollIntoView({block: 'nearest', inline: 'nearest'})",
        GUILD_ACCORD,
    )
    before = page.evaluate(CARD_BOX_JS, GUILD_ACCORD)
    click_card(page, GUILD_ACCORD)
    picked = page.evaluate("state.pick && state.pick.cardId")
    for route in held:
        route.continue_()
    # Removed by its own matcher, or a later reload's picture is held too.
    page.unroute(picture, hold)
    page.wait_for_function(
        "(id) => { const img = document.querySelector("
        '`#private-zone .vcard[data-instance="${id}"] img`);'
        " return img && img.complete && img.naturalHeight > 0; }",
        arg=GUILD_ACCORD,
    )
    after = page.evaluate(CARD_BOX_JS, GUILD_ACCORD)
    check.ok(
        held
        and before is not None
        and not before["loaded"]
        and before["height"] > 100
        and picked == GUILD_ACCORD
        and after["loaded"]
        and abs(after["height"] - before["height"]) < 1,
        "with its picture held back the card stands at its face's size, one"
        " click picks it, and the picture's arrival moves nothing",
        {"held": len(held), "before": before, "picked": picked, "after": after},
    )
    page.evaluate("state.pick = null; closePopover(); render()")


def promise_alone(page, base: str, game_id: str) -> None:
    print("[1] Guild Accord alone, then the Heighliner: the chooser's promises")
    open_table(page, base, game_id)
    shown = {}
    for language in ("ko", "en"):
        page.evaluate(f"setLanguage('{language}')")
        settled(page)
        open_chooser(page)
        chooser = page.evaluate(CHOOSER_JS, [GUILD_ACCORD, GHOLA, USURP])
        print(f"  .. [{language}] " + " | ".join(chooser["lines"]))
        shown[language] = chooser
        names = chooser["names"]
        lines = chooser["lines"]
        ghola = [line for line in lines if names["ghola"] in line]
        usurp = [line for line in lines if names["usurp"] in line]
        check.ok(
            chooser["open"]
            and len(lines) == 3
            and len(set(lines)) == 3
            and len(ghola) == 1
            and "2" in ghola[0]
            and len(usurp) == 1
            and not any("{" in line for line in lines),
            f"[{language}] three different lines: alone, with Usurp (no cut), with"
            " Ghola (2 more off)",
            chooser,
        )
    page.evaluate("setLanguage('ko')")
    settled(page)
    open_chooser(page)
    ghola_name = shown["ko"]["names"]["ghola"]
    promised = page.locator("#card-popover .action-item button", has_text=ghola_name)
    if not check.ok(promised.count() == 1, "the chooser has the line promising Ghola"):
        return
    promised.first.click()
    settled(page, 20)
    after = page.evaluate(TABLE_JS)
    check.ok(
        after["kind"] == "graft_partner"
        and [row["card"] for row in after["partners"]] == [GHOLA],
        "the promised placement taken, the partner window offers Ghola alone",
        after,
    )
    if after["partners"]:
        page.evaluate(f"applyAction({after['partners'][0]['index']})")
        settled(page, 20)
    final = page.evaluate(TABLE_JS)
    check.ok(
        final["kind"] != "graft_partner"
        and final["spice"] == 4
        and HEIGHLINER in final["agents"],
        "Ghola taken: the Agent is on the Heighliner and 2 of the 6 spice paid",
        final,
    )


def pair_together(page, base: str, game_id: str) -> None:
    print("[2] Guild Accord and Ghola together, then the Heighliner")
    open_table(page, base, game_id)
    click_card(page, GUILD_ACCORD)
    click_card(page, GHOLA)
    picked = page.evaluate("state.pick")
    click_space(page, HEIGHLINER)
    settled(page, 20)
    final = page.evaluate(TABLE_JS)
    check.ok(
        picked
        and picked.get("partnerId") == GHOLA
        and final["kind"] != "graft_partner"
        and final["spice"] == 4
        and HEIGHLINER in final["agents"],
        "the pair's one placement goes at once, Ghola follows as its partner, 2"
        " spice paid",
        {"picked": picked, "final": final},
    )


HELD_JS = """() => {
  const own = state.view.private;
  const heighliner = placementActions().filter(
    (action) => action.arguments.space_id === "imperium_heighliner");
  return {
    card: own.agent_card_pick,
    graft: own.agent_card_pick_graft,
    listed: state.actions.agent_placements,
    pick: state.pick,
    partners: Object.fromEntries(heighliner.map((action) => [
      action.arguments.partner_discount || 0, action.graft_partners || null])),
  };
}"""


def pair_placed(page, label: str) -> None:
    """Ghola joined as the partner, then the Heighliner: placed at once."""

    click_card(page, GHOLA)
    picked = page.evaluate("state.pick")
    click_space(page, HEIGHLINER)
    settled(page, 20)
    final = page.evaluate(TABLE_JS)
    chooser = page.evaluate(
        "Boolean(document.querySelector('#card-popover:not([hidden]) .pick-option'))"
    )
    check.ok(
        picked
        and picked.get("cardId") == GUILD_ACCORD
        and picked.get("partnerId") == GHOLA
        and not chooser
        and final["kind"] != "graft_partner"
        and final["spice"] == 4
        and HEIGHLINER in final["agents"],
        f"{label}: Ghola joined, the promised placement goes at once, Ghola"
        " follows, 2 spice paid",
        {"picked": picked, "chooser": chooser, "final": final},
    )


def held_names_partners(page, label: str) -> None:
    held = page.evaluate(HELD_JS)
    check.ok(
        held["card"] == GUILD_ACCORD
        and held["graft"] is True
        and held["listed"] is None
        and (held["pick"] or {}).get("cardId") == GUILD_ACCORD
        and held["partners"] == {"0": [USURP], "2": [GHOLA]},
        f"{label}: Guild Accord held grafted, no placements listed, and the"
        " Heighliner space picks name Usurp (no cut) and Ghola (2 more off)",
        held,
    )


def unpromised_line(page) -> bool:
    """Guild Accord alone, the Heighliner, its no-cut graft line (Usurp)."""

    open_chooser(page)
    names = page.evaluate(CHOOSER_JS, [GUILD_ACCORD, GHOLA, USURP])["names"]
    line = page.locator("#card-popover .action-item button", has_text=names["usurp"])
    if not check.ok(line.count() == 1, "the chooser has the line promising Usurp"):
        return False
    line.first.click()
    settled(page, 20)
    placed = page.evaluate(TABLE_JS)
    return check.ok(
        placed["kind"] == "graft_partner"
        and [row["card"] for row in placed["partners"]] == [USURP]
        and placed["spice"] == 2,
        "the no-cut line taken: 4 spice paid, the partner window offers Usurp",
        placed,
    )


def undone_space_pick(page, base: str, game_id: str) -> None:
    print("[3] undo after a graft placement on the Heighliner")
    open_table(page, base, game_id)
    page.evaluate("setLanguage('ko')")
    settled(page)
    if not unpromised_line(page):
        return
    page.locator(".undo-row button").first.click()
    settled(page, 20)
    back = page.evaluate(HELD_JS)
    check.ok(
        back["card"] == "" and back["listed"] and page.evaluate(TABLE_JS)["spice"] == 6,
        "one undo press takes the whole placement back, card pick included",
        back,
    )
    if not unpromised_line(page):
        return
    page.evaluate("submitUndo(state.viewSeat, 1)")
    settled(page, 20)
    # Played on when the rows fail, so a check run shows what the player
    # would meet then too.
    held_names_partners(page, "the space pick alone undone")
    pair_placed(page, "after the undo")


def reloaded_card_pick(page, base: str, game_id: str) -> None:
    print("[4] the page reloaded between the card pick and the space pick")
    open_table(page, base, game_id)
    pick = page.evaluate(
        """() => state.actions.agent_placements.find((entry) =>
             entry.arguments.card_id === "imperium:guild_accord:0"
             && entry.arguments.graft === true).index"""
    )
    revision = page.evaluate("state.summary.revision")
    page.evaluate(f"applyAction({pick})")
    page.wait_for_function(f"state.summary.revision === {revision + 1} && !state.busy")
    page.reload()
    page.wait_for_function("state.view !== null && refreshFlight === null")
    settled(page)
    held_names_partners(page, "after the reload")
    click_space(page, HEIGHLINER)
    page.wait_for_selector("#card-popover .pick-option", timeout=10_000)
    chooser = page.evaluate(CHOOSER_JS, [GUILD_ACCORD, GHOLA, USURP])
    names = chooser["names"]
    lines = chooser["lines"]
    print("  .. " + " | ".join(lines))
    check.ok(
        len(lines) == 2
        and sum(names["ghola"] in line and "2" in line for line in lines) == 1
        and sum(names["usurp"] in line for line in lines) == 1,
        "the held card's Heighliner chooser names each line's partner",
        chooser,
    )
    page.evaluate("closePopover(); state.pick = {cardId: state.pick.cardId}; render()")
    settled(page)
    pair_placed(page, "after the reload")


def main() -> None:
    process, base, games, log = start_fixture()
    try:
        with chrome() as browser:
            _, page, rec = open_context(browser, "guild-accord")
            held_picture(page, base, games[0])
            promise_alone(page, base, games[0])
            pair_together(page, base, games[1])
            undone_space_pick(page, base, games[2])
            reloaded_card_pick(page, base, games[3])
            check.ok(not rec.js_errors, "no page errors", rec.js_errors[:3])
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
    text = log.read_text()
    check.ok(
        "Traceback" not in text, "the fixture server logs no Traceback", text[-400:]
    )
    check.finish()


if __name__ == "__main__":
    main()
