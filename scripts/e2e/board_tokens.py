"""E2E of the pieces that lie on printed places of the board scan.

The Control marker on the flag under its space, the bonus spice in the Maker
hexagon, the Maker Hooks token in its garrison's slot and the Alliance token
on its Faction's ring (in the holder's seat panel once somebody earns it) are
drawn from `catalog.tracks`, percent of the scan. The checks compare what the
browser really laid out with those tables, so a CSS or transform slip shows
as a number. Reaching Control, hooks and an Alliance takes rounds of play, so
the view is edited in the page for the geometry checks (the view is the only
input of the render); the Reveal preview and the Intrigue pile are checked on
the live game.
"""

from __future__ import annotations

import json
import shutil

from common import SERVER_LOG_COPY, Check, chrome, open_context, server
from open_mode import create_game
from turn_controls import play_until

check = Check()
TOLERANCE = 0.06  # percent of the stage: about half a pixel of a 900 px stage

RECT_JS = """(selector) => {
  const stage = document.querySelector(".board-stage").getBoundingClientRect();
  return [...document.querySelectorAll(selector)].map((node) => {
    const r = node.getBoundingClientRect();
    return {
      seat: node.dataset.seat ?? null,
      space: node.dataset.space ?? null,
      faction: node.dataset.faction ?? null,
      text: node.textContent.trim(),
      left: (r.left - stage.left) / stage.width * 100,
      top: (r.top - stage.top) / stage.height * 100,
      width: r.width / stage.width * 100,
      height: r.height / stage.height * 100,
    };
  });
}"""


def rects(page, selector: str) -> list[dict]:
    return page.evaluate(RECT_JS, selector)


def near(value: float, wanted: float, tolerance: float = TOLERANCE) -> bool:
    return abs(value - wanted) <= tolerance


def box_matches(rect: dict, box: list[float], tolerance: float = TOLERANCE) -> bool:
    left, top, width, height = box
    return (
        near(rect["left"], left, tolerance)
        and near(rect["top"], top, tolerance)
        and near(rect["width"], width, tolerance)
        and near(rect["height"], height, tolerance)
    )


def images_loaded(page) -> None:
    page.wait_for_function(
        "[...document.querySelectorAll('.board-stage img')].every((i) => i.complete)"
    )


def fresh_table(page) -> None:
    print("[1] a fresh table: four Alliance tokens on their rings, nothing else")
    tracks = page.evaluate("state.catalog.tracks")
    images_loaded(page)
    tokens = {r["faction"]: r for r in rects(page, ".board-stage .alliance-token")}
    check.ok(
        set(tokens) == set(tracks["influence"]["offsets"]), "one token per Faction"
    )
    x, y = tracks["influence"]["alliance"]
    size = tracks["influence"]["alliance_size"]
    for faction, offset in tracks["influence"]["offsets"].items():
        rect = tokens.get(faction)
        if rect is None:
            continue
        check.ok(
            box_matches(rect, [x - size / 2, y + offset - size / 2, size, size], 0.1),
            f"the {faction} token covers its printed ring",
            rect,
        )
    check.ok(not rects(page, ".alliance-ring"), "no ring without a holder")
    check.ok(not rects(page, ".control-marker"), "no Control marker yet")
    check.ok(not rects(page, ".bonus-spice"), "no bonus spice yet")
    check.ok(not rects(page, ".maker-hooks-token"), "no Maker Hooks token yet")


def reveal_preview(page) -> None:
    print("[2] what the hand is worth revealed right now")
    # The setup screen's default game opens with the Leader draft: pick until
    # the seat's first turn offers the Reveal.
    reached = play_until(
        page,
        "state.actions.actions.some((a) => a.action_id === 'reveal_turn')",
        "state.actions.actions[0].index",
    )
    if not check.ok(reached, "the seat's turn offers reveal_turn"):
        return
    served = page.evaluate(
        "(state.actions.actions.find((a) => a.action_id === 'reveal_turn') || {})"
        ".reveal_preview || null"
    )
    if not check.ok(served is not None, "the server previews reveal_turn"):
        return
    note = page.locator(".hand-reveal-note")
    check.ok(note.count() == 1, "the hand says what revealing now gives")
    check.ok(
        str(served["persuasion"]) in note.inner_text(),
        "with the server's Persuasion figure",
        (served, note.inner_text()),
    )
    button = page.locator("#actions .action-item .reveal-preview")
    check.ok(button.count() == 1, "and so does the Reveal button")


def printed_places(page) -> None:
    print("[3] Control, bonus spice, Maker Hooks, a held Alliance (edited view)")
    tracks = page.evaluate("state.catalog.tracks")
    colors = page.evaluate("SEAT_COLORS")
    page.evaluate(
        """() => {
          const v = state.view;
          v.maker_bonus_spice = [
            ["deep_desert", 3], ["hagga_basin", 0], ["imperial_basin", 12],
          ];
          v.players.forEach((p) => { p.maker_hooks = true; p.control_space_ids = []; });
          v.players[0].control_space_ids = ["imperial_basin"];
          v.players[1].control_space_ids = ["arrakeen"];
          v.players[2].control_space_ids = ["spice_refinery"];
          v.players.forEach((p) => { p.alliance_faction_ids = []; });
          v.players[0].alliance_faction_ids = ["emperor"];
          v.players[3].alliance_faction_ids = ["fremen"];
          render();
        }"""
    )
    # The two tokens that changed hands fly to their holders' panels (a copy
    # above the page while the token itself waits hidden), then land.
    flying = page.evaluate(
        "[...document.querySelectorAll('.alliance-token.flying')]"
        ".map((n) => n.dataset.faction)"
    )
    check.ok(
        sorted(flying) == ["emperor", "fremen"],
        "earned tokens fly to their holders",
        flying,
    )
    page.wait_for_function(
        "document.querySelectorAll('.alliance-token.flying').length === 0"
    )
    hidden = page.evaluate(
        "[...document.querySelectorAll('.alliance-token')]"
        ".filter((n) => n.style.visibility === 'hidden').length"
    )
    check.ok(hidden == 0, "and land: every token shows again")
    images_loaded(page)

    holders = {"imperial_basin": 0, "arrakeen": 1, "spice_refinery": 2}
    markers = {r["space"]: r for r in rects(page, ".control-marker")}
    check.ok(set(markers) == set(holders), "a marker per controlled space", markers)
    for space_id, seat in holders.items():
        rect = markers.get(space_id)
        if rect is None:
            continue
        check.ok(
            box_matches(rect, tracks["control_flags"]["boxes"][space_id]),
            f"{space_id}: the marker is the printed flag's box",
            rect,
        )
        fill = page.evaluate(
            "(space) => document.querySelector(`.control-marker[data-space='${space}']"
            " polygon`).getAttribute('fill')",
            space_id,
        )
        check.ok(
            rect["seat"] == str(seat) and fill == colors[seat],
            f"{space_id}: seat colour",
        )
    check.ok(
        page.locator(".hotspot .control-flag").count() == 0,
        "no Control mark left inside the hotspots",
    )

    spice = {r["space"]: r for r in rects(page, ".bonus-spice")}
    check.ok(
        set(spice) == {"deep_desert", "imperial_basin"}, "spice only where it waits"
    )
    width, height = tracks["maker_spice"]["size"]
    for space_id, amount in (("deep_desert", "3"), ("imperial_basin", "12")):
        rect = spice.get(space_id)
        if rect is None:
            continue
        x, y = tracks["maker_spice"]["points"][space_id]
        check.ok(
            box_matches(rect, [x - width / 2, y - height / 2, width, height]),
            f"{space_id}: the spice hexagon covers the printed one",
            rect,
        )
        check.ok(rect["text"] == amount, f"{space_id}: shows {amount}", rect["text"])
    check.ok(
        page.locator(".hotspot .maker-bonus").count() == 0,
        "no bonus-spice mark left inside the hotspots",
    )

    hooks = {r["seat"]: r for r in rects(page, ".maker-hooks-token")}
    check.ok(len(hooks) == 4, "a Maker Hooks token per seat that has one", hooks)
    slot_width, slot_height = tracks["maker_hooks"]["size"]
    pictured = page.evaluate("Boolean(state.catalog.maker_hooks_token)")
    for seat, (x, y) in enumerate(tracks["maker_hooks"]["points"]):
        rect = hooks.get(str(seat))
        if rect is None:
            continue
        check.ok(
            box_matches(
                rect,
                [x - slot_width / 2, y - slot_height / 2, slot_width, slot_height],
                0.12 if pictured else TOLERANCE,
            ),
            f"seat {seat}: the token fills its garrison's slot",
            rect,
        )

    on_board = {r["faction"] for r in rects(page, ".board-stage .alliance-token")}
    check.ok(
        on_board == {"spacing_guild", "bene_gesserit"}, "held tokens left the board"
    )
    rings = page.evaluate(
        "[...document.querySelectorAll('.alliance-ring')].map((n) =>"
        " [n.dataset.faction, n.style.borderColor])"
    )
    check.ok(
        sorted(f for f, _ in rings) == ["emperor", "fremen"],
        "the vacated rings take the holders' colours",
        rings,
    )
    for seat, faction in ((0, "emperor"), (3, "fremen")):
        held = page.locator(
            f"#seats .seat[data-seat='{seat}']"
            f" .alliance-token.inline[data-faction='{faction}']"
        )
        check.ok(held.count() == 1, f"seat {seat}'s panel holds the {faction} token")
    check.ok(
        page.locator("#seats .alliance-token.inline").count() == 2,
        "and nobody else's panel shows one",
    )


def intrigue_pile(page) -> None:
    print("[4] the Intrigue discard is one line; a click lists the cards")
    ids = page.evaluate(
        "Object.keys(state.catalog.intrigue || {}).slice(0, 3).map((id) => `${id}:1`)"
    )
    if not check.ok(len(ids) == 3, "the catalog has Intrigue cards", ids):
        return
    page.evaluate(
        "(ids) => { state.view.intrigue_discard = ids.slice(0, 2);"
        " state.view.intrigue_trash = ids.slice(2); render(); }",
        ids,
    )
    pile = page.locator(".pile-button[data-pile='intrigue']")
    check.ok(pile.count() == 1, "one pile line")
    text = pile.inner_text()
    trash = page.evaluate("phraseText('{trash}')")
    check.ok("2" in text and f"{trash} 1" in text, "with both counts", text)
    check.ok(
        page.locator("#market .vcard.intrigue").count() == 0,
        "no Intrigue card faces in the column",
    )
    pile.click()
    listed = page.evaluate(
        "[...document.querySelectorAll('#card-popover .vcard')]"
        ".map((n) => n.dataset.instance)"
    )
    check.ok(
        listed == [ids[1], ids[0], ids[2]],
        "the list: discard newest first, then the trash",
        listed,
    )
    titles = page.evaluate(
        "[...document.querySelectorAll('#card-popover .popover-title')]"
        ".map((n) => n.textContent)"
    )
    check.ok(len(titles) == 2, "two headed piles", titles)


def main() -> None:
    with server() as (base, server_log), chrome() as browser:
        try:
            context, page, rec = open_context(browser, "player")
            create_game(page, base, humans=(0,), seed=11)
            fresh_table(page)
            reveal_preview(page)
            printed_places(page)
            intrigue_pile(page)
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
    print(json.dumps({"passed": check.passed, "failed": check.failed}))
    check.finish()


if __name__ == "__main__":
    main()
