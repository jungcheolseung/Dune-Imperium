"""E2E of the pieces that lie on printed places of the board scan.

Every space's hotspot is the white frame printed around its picture
(`catalog.spaces[id].box` and `catalog.space_frame`), and the Agents on it
are the rulebook Agent icon's figure in their seat's colour, like the Spies
(the Spy icon's cylinder) on the post discs. The Control marker on
the flag under its space, the bonus spice in the Maker
hexagon, the Maker Hooks token in its garrison's slot and the Alliance token
on its Faction's ring (in the holder's seat panel once somebody earns it) are
drawn from `catalog.tracks`, percent of the scan. The checks compare what the
browser really laid out with those tables, so a CSS or transform slip shows
as a number. Reaching Control, hooks and an Alliance takes rounds of play, so
the view is edited in the page for the geometry checks (the view is the only
input of the render); the Reveal preview and the Intrigue pile are checked on
the live game. The units in the Conflict are a piece each in their seat's
printed quadrant (`catalog.tracks.conflict_units`): a cube per troop, the
seat's Agent figure, the neutral Commander and sandworm pictures, and no
number. A Bloodlines table then checks the Sardaukar Commanders that
stand on their setup spaces, the rulebook's figure on each frame's top-right
corner [Bloodlines p. 3].
"""

from __future__ import annotations

import json
import shutil

from common import (
    SERVER_LOG_COPY,
    Check,
    chrome,
    open_context,
    server,
    set_rule_options,
)
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
    check.ok(not rects(page, ".board-stage .bonus-spice"), "no bonus spice yet")
    check.ok(not rects(page, ".maker-hooks-token"), "no Maker Hooks token yet")


def space_frames(page) -> None:
    print("[1b] every hotspot is the white frame its space prints")
    catalog = page.evaluate(
        "({ spaces: state.catalog.spaces,"
        " cut: (state.catalog.space_frame || {}).cut || null })"
    )
    hotspots = {r["space"]: r for r in rects(page, ".board-stage .hotspot")}
    check.ok(len(hotspots) == 22, "22 printed spaces without Esmar Tuek", len(hotspots))
    for space_id, rect in hotspots.items():
        check.ok(
            box_matches(rect, catalog["spaces"][space_id]["box"]),
            f"{space_id}: the hotspot is the frame's box",
            rect,
        )
    frames = rects(page, ".board-stage .hotspot > .space-frame")
    check.ok(len(frames) == len(hotspots), "one frame outline per hotspot")
    check.ok(catalog["cut"] is not None, "the catalog serves the frame's cut corners")
    cut_x, cut_y = catalog["cut"] or (0, 0)
    points = page.evaluate(
        "[...new Set([...document.querySelectorAll('.space-frame polygon')]"
        ".map((p) => p.getAttribute('points')))]"
    )
    wanted = f"0,0 {100 - cut_x},0 100,{cut_y} 100,100 {cut_x},100 0,{100 - cut_y}"
    check.ok(points == [wanted], "every outline has the frame's cut corners", points)
    # The generic button:hover fill must not paint the hotspot's whole box:
    # the highlight is the outline and a light fill inside it.
    page.hover(".hotspot[data-space='sardaukar']")
    page.wait_for_timeout(300)  # past the outline's 0.15 s transition
    hovered = page.evaluate(
        """() => {
          const hotspot = document.querySelector(".hotspot[data-space='sardaukar']");
          const outline = hotspot.querySelector(".space-frame polygon");
          return {
            background: getComputedStyle(hotspot).backgroundColor,
            stroke: outline ? getComputedStyle(outline).stroke : null,
          };
        }"""
    )
    check.ok(
        hovered["background"] == "rgba(0, 0, 0, 0)", "no box fill on hover", hovered
    )
    check.ok(
        hovered["stroke"] == "rgba(255, 255, 255, 0.7)",
        "the outline lights on hover",
        hovered,
    )
    page.mouse.move(0, 0)


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

    spice = {r["space"]: r for r in rects(page, ".board-stage .bonus-spice")}
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
    check.ok(
        page.locator("#seats .alliance-token").count() == 0,
        "held tokens are represented by their coloured board rings,"
        " not duplicate stats",
    )


def agent_pieces(page) -> None:
    print("[3b] Agents: the Agent icon's figure in the seat's colour (edited view)")
    colors = page.evaluate("SEAT_COLORS")
    placed = {
        "sardaukar": [0],
        "arrakeen": [0, 1, 2],
        "imperial_basin": [0, 1, 2, 3],
        "hagga_basin": [3],
    }
    page.evaluate(
        """(placed) => {
          for (const player of state.view.players) player.agent_locations = [];
          for (const [space, seats] of Object.entries(placed)) {
            for (const seat of seats) {
              state.view.players[seat].agent_locations.push(space);
            }
          }
          render();
        }""",
        placed,
    )
    # New Agents fly in from their seats' panels; measure them once landed.
    page.wait_for_function("!document.querySelector('.agent-token.flying')")
    page.wait_for_timeout(350)  # past the pop-in of any token without an origin
    tokens = page.evaluate(
        """() => {
          const stage = document.querySelector(".board-stage").getBoundingClientRect();
          const pct = (r) => ({
            left: (r.left - stage.left) / stage.width * 100,
            top: (r.top - stage.top) / stage.height * 100,
            width: r.width / stage.width * 100,
            height: r.height / stage.height * 100,
          });
          const all = document.querySelectorAll(".hotspot .agent-token");
          return [...all].map((token) => ({
            body: token.querySelector(".piece-body"),
            token,
          })).map(({ body, token }) => ({
            space: token.closest(".hotspot").dataset.space,
            frame: pct(token.closest(".hotspot").getBoundingClientRect()),
            rect: pct(token.getBoundingClientRect()),
            seat: Number(token.dataset.seat),
            tag: token.tagName,
            role: token.getAttribute("role"),
            label: token.getAttribute("aria-label"),
            wantedLabel: t("common.seat", { seat: Number(token.dataset.seat) }),
            fill: body ? getComputedStyle(body).fill : null,
            drawnText: token.querySelectorAll("text").length + (body ? 0 : 1),
            outline: body ? body.getAttribute("href") : null,
          }));
        }"""
    )
    by_space: dict[str, list[dict]] = {}
    for token in tokens:
        by_space.setdefault(token["space"], []).append(token)
    check.ok(
        {space: [t["seat"] for t in group] for space, group in by_space.items()}
        == placed,
        "one Agent per placement, in seat order",
        {space: [t["seat"] for t in group] for space, group in by_space.items()},
    )
    check.ok(
        page.evaluate("document.querySelectorAll('#agent-outline').length") == 1,
        "one shared Agent outline",
    )

    def rgb(hex_color: str) -> str:
        value = hex_color.lstrip("#")
        red, green, blue = (int(value[i : i + 2], 16) for i in (0, 2, 4))
        return f"rgb({red}, {green}, {blue})"

    for token in tokens:
        name = f"{token['space']} seat {token['seat']}"
        check.ok(
            token["tag"] == "svg" and token["outline"] == "#agent-outline",
            f"{name}: drawn from the Agent outline",
            token,
        )
        check.ok(
            token["fill"] == rgb(colors[token["seat"]]),
            f"{name}: in the seat's colour",
            (token["fill"], colors[token["seat"]]),
        )
        check.ok(token["drawnText"] == 0, f"{name}: no seat number drawn", token)
        check.ok(
            token["role"] == "img" and token["label"] == token["wantedLabel"],
            f"{name}: named after its seat",
            token,
        )
        rect, frame = token["rect"], token["frame"]
        right, bottom = rect["left"] + rect["width"], rect["top"] + rect["height"]
        check.ok(
            frame["left"] - TOLERANCE <= rect["left"]
            and right <= frame["left"] + frame["width"] + TOLERANCE
            and frame["top"] - TOLERANCE <= rect["top"]
            and bottom <= frame["top"] + frame["height"] + TOLERANCE,
            f"{name}: stands inside the space's frame",
            (rect, frame),
        )
        # The figure keeps the icon's shape: 52 x 81 in pixels (the stage's
        # percent units are near square, 6012 x 6005).
        shape = rect["width"] / rect["height"] * 6012 / 6005
        check.ok(abs(shape - 52 / 81) < 0.02, f"{name}: the icon's proportions", shape)
    for space, group in by_space.items():
        apart = all(
            left["rect"]["left"] + left["rect"]["width"] <= right["rect"]["left"] + 0.01
            for left, right in zip(group, group[1:], strict=False)
        )
        check.ok(apart, f"{space}: Agents side by side, not stacked")
    alone = by_space["sardaukar"][0]
    check.ok(
        near(alone["rect"]["height"], alone["frame"]["height"] * 0.72, 0.1),
        "a lone Agent stands 72% of the frame's height",
        (alone["rect"], alone["frame"]),
    )


# A shared post's Spies arrive in this order (bottom first), deliberately not
# seat order; the fake log entries below carry it.
SPY_ARRIVALS = {
    "emperor-sardaukar-dutiful-service": [2],
    "arrakis-hagga-basin": [2, 0, 3, 1],
    "fremen-desert-tactics-fremkit": [3, 1],
}

SPIES_JS = """() => {
  const stage = document.querySelector(".board-stage").getBoundingClientRect();
  const pct = (r) => ({
    left: (r.left - stage.left) / stage.width * 100,
    top: (r.top - stage.top) / stage.height * 100,
    width: r.width / stage.width * 100,
    height: r.height / stage.height * 100,
  });
  const posts = document.querySelectorAll(".board-stage .spy-post");
  return [...posts].map((post) => ({
    rect: pct(post.getBoundingClientRect()),
    spies: [...post.querySelectorAll(".spy-token")].map((spy) => {
      const body = spy.querySelector(".piece-body");
      return {
        rect: pct(spy.getBoundingClientRect()),
        seat: Number(spy.dataset.seat),
        tag: spy.tagName,
        outline: body ? body.getAttribute("href") : null,
        fill: body ? getComputedStyle(body).fill : null,
        top: spy.querySelectorAll(".piece-top").length,
        drawnText: spy.querySelectorAll("text").length + (body ? 0 : 1),
        role: spy.getAttribute("role"),
        label: spy.getAttribute("aria-label"),
        wantedLabel: t("common.seat", { seat: Number(spy.dataset.seat) }),
      };
    }),
  }));
}"""

# One log entry per placement: what spyArrivals() reads (board.js).
LOG_PLACEMENTS_JS = """(placements) => {
  for (const [post, seat] of placements) {
    state.log.entries.push({
      type: "action", index: state.log.entries.length, actor: seat,
      action_id: "place_spy_on_space", arguments: {}, undone: false,
      events: [{kind: "spy_placed", payload: {player: seat, post_id: post}}],
    });
  }
  render();
}"""


def spy_pieces(page) -> None:
    print("[3c] Spies: the Spy icon's cylinder on the post disc (edited view)")
    catalog = page.evaluate(
        "({ posts: state.catalog.posts, size: state.catalog.post_size })"
    )
    colors = page.evaluate("SEAT_COLORS")
    page.evaluate(
        """(placed) => {
          for (const player of state.view.players) player.spy_post_ids = [];
          for (const [post, seats] of Object.entries(placed)) {
            for (const seat of seats) {
              state.view.players[seat].spy_post_ids.push(post);
            }
          }
        }""",
        SPY_ARRIVALS,
    )
    # The arrivals go in round-robin across posts, as a game would interleave.
    longest = max(len(seats) for seats in SPY_ARRIVALS.values())
    placements = [
        [post, seats[turn]]
        for turn in range(longest)
        for post, seats in SPY_ARRIVALS.items()
        if turn < len(seats)
    ]
    page.evaluate(LOG_PLACEMENTS_JS, placements)
    shown = page.evaluate(SPIES_JS)

    def rgb(hex_color: str) -> str:
        value = hex_color.lstrip("#")
        red, green, blue = (int(value[i : i + 2], 16) for i in (0, 2, 4))
        return f"rgb({red}, {green}, {blue})"

    def post_at(rect: dict) -> str | None:
        centre = (rect["left"] + rect["width"] / 2, rect["top"] + rect["height"] / 2)
        for post_id, (x, y) in catalog["posts"].items():
            if near(centre[0], x) and near(centre[1], y):
                return post_id
        return None

    by_post = {post_at(group["rect"]): group for group in shown}
    check.ok(
        {post: [s["seat"] for s in group["spies"]] for post, group in by_post.items()}
        == SPY_ARRIVALS,
        "each post's Spies on its printed disc, the first to arrive at the bottom",
        [(group["rect"], [s["seat"] for s in group["spies"]]) for group in shown],
    )
    for post_id, group in by_post.items():
        for spy in group["spies"]:
            name = f"{post_id} seat {spy['seat']}"
            check.ok(
                spy["tag"] == "svg" and spy["outline"] == "#spy-outline",
                f"{name}: drawn from the Spy outline",
                spy,
            )
            check.ok(
                spy["fill"] == rgb(colors[spy["seat"]]),
                f"{name}: in the seat's colour",
                (spy["fill"], colors[spy["seat"]]),
            )
            check.ok(spy["top"] == 1, f"{name}: the cylinder's top face", spy)
            check.ok(spy["drawnText"] == 0, f"{name}: no seat number drawn", spy)
            check.ok(
                spy["role"] == "img" and spy["label"] == spy["wantedLabel"],
                f"{name}: named after its seat",
                spy,
            )
            shape = spy["rect"]["width"] / spy["rect"]["height"] * 6012 / 6005
            check.ok(
                abs(shape - 56 / 80) < 0.02, f"{name}: the icon's proportions", shape
            )
        # Stacked, as on the table: every Spy the disc's width, centred over
        # the post, each standing on the top face of the one below it (the
        # faces' centres are 48 of the icon's 80 units apart).
        x, y = catalog["posts"][post_id]
        spies = group["spies"]
        bottom = spies[0]["rect"]
        check.ok(
            near(bottom["left"] + bottom["width"] / 2, x)
            and near(bottom["top"] + bottom["height"] / 2, y),
            f"{post_id}: the first Spy stands on the disc",
            bottom,
        )
        stacked = all(
            near(spy["rect"]["width"], catalog["size"])
            and near(spy["rect"]["left"] + spy["rect"]["width"] / 2, x)
            and near(
                spy["rect"]["top"],
                bottom["top"] - level * 0.6 * bottom["height"],
            )
            for level, spy in enumerate(spies)
        )
        check.ok(
            stacked,
            f"{post_id}: each Spy the disc's width, on top of the one below",
            [(round(s["rect"]["top"], 2), round(s["rect"]["width"], 2)) for s in spies],
        )
    check.ok(
        page.evaluate(
            """() => [...document.querySelectorAll('.board-stage .spy-post')]
                 .every((post) => [...post.querySelectorAll('.spy-token')]
                   .every((spy, i, all) => i === 0 ||
                     spy.compareDocumentPosition(all[i - 1])
                       === Node.DOCUMENT_POSITION_PRECEDING))"""
        ),
        "a higher Spy is drawn over the one it stands on",
    )
    # Recalled and placed again, a Spy goes back on top.
    page.evaluate(LOG_PLACEMENTS_JS, [["fremen-desert-tactics-fremkit", 3]])
    again = {
        post_at(group["rect"]): [s["seat"] for s in group["spies"]]
        for group in page.evaluate(SPIES_JS)
    }
    check.ok(
        again.get("fremen-desert-tactics-fremkit") == [1, 3],
        "a Spy placed again stands on top",
        again.get("fremen-desert-tactics-fremkit"),
    )
    check.ok(
        page.evaluate("document.querySelectorAll('#spy-outline').length") == 1,
        "one shared Spy outline",
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


# The view fields behind each kind of unit in the Conflict (PublicPlayerView).
UNIT_FIELDS = {
    "troop": "troops_conflict",
    "commander": "commanders_conflict",
    "agent": "agent_in_conflict",
    "sandworm": "sandworms_conflict",
}
# Seat by seat: a full row and a partial one, troops with sandworms, troops
# with both kinds of figure, and nobody.
CONFLICT_UNITS = [
    {"troop": 12},
    {"troop": 3, "sandworm": 2},
    {"troop": 4, "commander": 2, "agent": 1},
    {},
]
# The most one quadrant is likely to hold: it must shrink, and stay inside.
CONFLICT_STRESS = {"troop": 12, "sandworm": 3, "commander": 3, "agent": 2}

SET_UNITS_JS = """([units, fields]) => {
  state.view.players.forEach((player, seat) => {
    for (const [kind, field] of Object.entries(fields)) {
      player[field] = (units[seat] || {})[kind] || 0;
    }
  });
  render();
}"""

UNITS_JS = """() => {
  const stage = document.querySelector(".board-stage").getBoundingClientRect();
  const pct = (r) => ({
    left: (r.left - stage.left) / stage.width * 100,
    top: (r.top - stage.top) / stage.height * 100,
    width: r.width / stage.width * 100,
    height: r.height / stage.height * 100,
  });
  const units = document.querySelectorAll(".board-stage .conflict-units");
  return [...units].map((wrap) => ({
    seat: Number(wrap.dataset.seat),
    scale: Number(wrap.dataset.scale),
    role: wrap.getAttribute("role"),
    label: wrap.getAttribute("aria-label"),
    text: wrap.innerText,
    pieces: [...wrap.querySelectorAll(".conflict-unit")].map((piece) => {
      const body = piece.querySelector(".piece-body");
      return {
        seat: Number(piece.dataset.seat),
        kind: piece.dataset.kind,
        tag: piece.tagName.toLowerCase(),
        rect: pct(piece.getBoundingClientRect()),
        background: getComputedStyle(piece).backgroundColor,
        fill: body ? getComputedStyle(body).fill : null,
        src: piece.getAttribute("src"),
        loaded: piece.tagName === "IMG" ? piece.complete && piece.naturalWidth > 0 : null,
        pointer: getComputedStyle(piece).pointerEvents,
      };
    }),
  }));
}"""


def rgb(hex_color: str) -> str:
    value = hex_color.lstrip("#")
    red, green, blue = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgb({red}, {green}, {blue})"


def overlapping(pieces: list[dict], slack: float = 0.01) -> list[tuple[int, int]]:
    """Pairs of pieces whose rectangles overlap by more than `slack`."""
    pairs = []
    for i, first in enumerate(pieces):
        for j in range(i + 1, len(pieces)):
            a, b = first["rect"], pieces[j]["rect"]
            if (
                a["left"] + a["width"] > b["left"] + slack
                and b["left"] + b["width"] > a["left"] + slack
                and a["top"] + a["height"] > b["top"] + slack
                and b["top"] + b["height"] > a["top"] + slack
            ):
                pairs.append((i, j))
    return pairs


def inside_box(rect: dict, box: list[float], tolerance: float = 0.12) -> bool:
    left, top, width, height = box
    return (
        rect["left"] >= left - tolerance
        and rect["top"] >= top - tolerance
        and rect["left"] + rect["width"] <= left + width + tolerance
        and rect["top"] + rect["height"] <= top + height + tolerance
    )


def conflict_units(page) -> None:
    print("[3d] units in the Conflict (edited view): a piece per unit, no numbers")
    tracks = page.evaluate("state.catalog.tracks")
    layout = tracks["conflict_units"] if "conflict_units" in tracks else None
    colors = page.evaluate("SEAT_COLORS")
    pictures = page.evaluate(
        "({ commander: state.catalog.commander_token,"
        " sandworm: (state.catalog.icons || {}).sandworm || null })"
    )
    page.evaluate(SET_UNITS_JS, [CONFLICT_UNITS, UNIT_FIELDS])
    images_loaded(page)
    shown = {group["seat"]: group for group in page.evaluate(UNITS_JS)}
    boxes = layout["boxes"] if layout else [[0, 0, 0, 0]] * 4
    padding = layout["padding"] if layout else 0

    for seat, wanted in enumerate(CONFLICT_UNITS):
        group = shown.get(seat)
        if not wanted:
            check.ok(group is None, f"seat {seat}: nothing in the Conflict, no pieces")
            continue
        if not check.ok(group is not None, f"seat {seat}: its units are drawn"):
            continue
        counts = {kind: 0 for kind in UNIT_FIELDS}
        for piece in group["pieces"]:
            counts[piece["kind"]] = counts.get(piece["kind"], 0) + 1
        check.ok(
            all(counts[kind] == wanted.get(kind, 0) for kind in UNIT_FIELDS)
            and all(piece["seat"] == seat for piece in group["pieces"]),
            f"seat {seat}: one piece per unit, by kind",
            (counts, wanted),
        )
        check.ok(group["scale"] == 1, f"seat {seat}: full size", group["scale"])
        box = boxes[seat]
        check.ok(
            all(inside_box(piece["rect"], box) for piece in group["pieces"]),
            f"seat {seat}: every piece inside its quadrant",
            [piece["rect"] for piece in group["pieces"]
             if not inside_box(piece["rect"], box)][:3],
        )
        check.ok(
            not overlapping(group["pieces"]),
            f"seat {seat}: no two pieces overlap",
            overlapping(group["pieces"])[:3],
        )
        check.ok(
            all(piece["pointer"] == "none" for piece in group["pieces"]),
            f"seat {seat}: the pieces never take a click",
        )
        troops = [p for p in group["pieces"] if p["kind"] == "troop"]
        check.ok(
            all(p["background"] == rgb(colors[seat]) for p in troops),
            f"seat {seat}: troops are cubes in the seat's colour",
            {p["background"] for p in troops},
        )
        cube = tracks["influence"]["cube_size"]
        check.ok(
            all(near(p["rect"]["width"], cube) for p in troops),
            f"seat {seat}: a troop is an Influence cube's size ({cube})",
            [round(p["rect"]["width"], 3) for p in troops][:3],
        )
        agents = [p for p in group["pieces"] if p["kind"] == "agent"]
        check.ok(
            all(p["tag"] == "svg" and p["fill"] == rgb(colors[seat]) for p in agents),
            f"seat {seat}: an Agent is the seat's Agent figure",
            [(p["tag"], p["fill"]) for p in agents],
        )
        for kind in ("commander", "sandworm"):
            figures = [p for p in group["pieces"] if p["kind"] == kind]
            if not figures:
                continue
            if pictures[kind]:
                check.ok(
                    all(p["src"] == pictures[kind] and p["loaded"] for p in figures),
                    f"seat {seat}: a {kind} is its own picture, loaded",
                    [(p["src"], p["loaded"]) for p in figures],
                )
            else:
                print(f"  .. no local {kind} picture: the drawn piece is checked")
        # The garrison side and the outer edge fill first: rows from the
        # outer edge, each from the garrison side, a partial row innermost.
        from_right = seat in (2, 3)
        from_bottom = seat in (0, 3)
        left, top, width, height = box
        rows: dict[float, list[dict]] = {}
        for piece in troops:
            rows.setdefault(round(piece["rect"]["top"], 1), []).append(piece)
        ordered = [rows[y] for y in sorted(rows, reverse=from_bottom)]
        hugs = all(
            near(
                max(p["rect"]["left"] + p["rect"]["width"] for p in row)
                if from_right
                else min(p["rect"]["left"] for p in row),
                left + width - padding if from_right else left + padding,
            )
            for row in ordered
        )
        outer = ordered[0][0]["rect"] if ordered else None
        check.ok(
            bool(ordered)
            and hugs
            and outer is not None
            and near(
                outer["top"] + outer["height"] if from_bottom else outer["top"],
                top + height - padding if from_bottom else top + padding,
            )
            and [len(row) for row in ordered]
            == sorted((len(row) for row in ordered), reverse=True),
            f"seat {seat}: troops fill from the garrison side and the outer edge",
            [len(row) for row in ordered],
        )
        figures = [p for p in group["pieces"] if p["kind"] != "troop"]
        if figures and troops:
            if from_bottom:
                ahead = all(f["rect"]["top"] + f["rect"]["height"]
                            <= min(t["rect"]["top"] for t in troops) + 0.01
                            for f in figures)
            else:
                ahead = all(f["rect"]["top"]
                            >= max(t["rect"]["top"] + t["rect"]["height"]
                                   for t in troops) - 0.01
                            for f in figures)
            check.ok(ahead, f"seat {seat}: the figures stand past the troops, toward the cross")
        check.ok(
            group["role"] == "img"
            and all(
                page.evaluate(f"phraseText('{{{kind}:{count}}}')") in (group["label"] or "")
                for kind, count in wanted.items()
            )
            and all(
                page.evaluate(f"phraseText('{{{kind}}}')") not in (group["label"] or "")
                for kind in UNIT_FIELDS
                if kind not in wanted
            ),
            f"seat {seat}: its name counts every kind it has",
            group["label"],
        )
        check.ok(
            not any(ch.isdigit() for ch in group["text"]),
            f"seat {seat}: no number drawn in the quadrant",
            group["text"],
        )
    check.ok(
        page.locator(".force-chip.deployed, .force-strength").count() == 0,
        "no count chip and no strength badge in the Conflict",
    )

    # Crowded: the pieces shrink (not below half size) and stay inside.
    stress = [{}, {}, {}, CONFLICT_STRESS]
    page.evaluate(SET_UNITS_JS, [stress, UNIT_FIELDS])
    images_loaded(page)
    crowded = {group["seat"]: group for group in page.evaluate(UNITS_JS)}.get(3)
    if check.ok(crowded is not None, "a crowded quadrant is drawn"):
        counts = {}
        for piece in crowded["pieces"]:
            counts[piece["kind"]] = counts.get(piece["kind"], 0) + 1
        check.ok(counts == CONFLICT_STRESS, "crowded: still a piece per unit", counts)
        check.ok(
            0.5 <= crowded["scale"] < 1,
            "crowded: the pieces shrink, to half size at most",
            crowded["scale"],
        )
        check.ok(
            all(inside_box(piece["rect"], boxes[3]) for piece in crowded["pieces"]),
            "crowded: every piece stays inside the quadrant",
        )

    # Without the pictures the drawn pieces take their places.
    page.evaluate(
        "state.catalog.commander_token = null;"
        " if (state.catalog.icons) delete state.catalog.icons.sandworm;"
    )
    page.evaluate(SET_UNITS_JS, [CONFLICT_UNITS, UNIT_FIELDS])
    drawn = {group["seat"]: group for group in page.evaluate(UNITS_JS)}
    for seat, kind in ((2, "commander"), (1, "sandworm")):
        group = drawn.get(seat) or {"pieces": []}
        pieces = [p for p in group["pieces"] if p["kind"] == kind]
        check.ok(
            len(pieces) == CONFLICT_UNITS[seat][kind]
            and all(p["tag"] in ("span", "svg") and p["src"] is None for p in pieces)
            and all(inside_box(p["rect"], boxes[seat]) for p in pieces)
            and all(p["rect"]["width"] > 0.5 for p in pieces),
            f"without the picture a {kind} is drawn, counted and inside",
            [(p["tag"], p["rect"]) for p in pieces],
        )
    page.evaluate(
        """([pictures]) => {
          state.catalog.commander_token = pictures.commander;
          if (pictures.sandworm) state.catalog.icons.sandworm = pictures.sandworm;
        }""",
        [pictures],
    )
    page.evaluate(SET_UNITS_JS, [[{}, {}, {}, {}], UNIT_FIELDS])


# Setup: "Place five of them on the game board, one on each of the following
# spaces: Sardaukar, Dutiful Service, Deliver Supplies, High Council, and
# Gather Support. Leave room on each space for an Agent" and a sixth on
# Assembly Hall with four players [Bloodlines p. 3] (docs/rules/bloodlines.md).
COMMANDER_SETUP_SPACES = {
    "sardaukar",
    "dutiful_service",
    "deliver_supplies",
    "high_council",
    "gather_support",
    "assembly_hall",
}

COMMANDERS_JS = """() => {
  const stage = document.querySelector(".board-stage").getBoundingClientRect();
  const pct = (r) => ({
    left: (r.left - stage.left) / stage.width * 100,
    top: (r.top - stage.top) / stage.height * 100,
    width: r.width / stage.width * 100,
    height: r.height / stage.height * 100,
  });
  return [...document.querySelectorAll(".board-stage .commander-piece")].map((p) => ({
    space: p.dataset.space,
    tag: p.tagName,
    src: p.getAttribute("src"),
    loaded: p.tagName === "IMG" ? p.complete && p.naturalWidth > 0 : null,
    pointer: getComputedStyle(p).pointerEvents,
    rect: pct(p.getBoundingClientRect()),
  }));
}"""


def commander_pieces(base: str, browser) -> None:
    print("[5] Sardaukar Commanders stand on their setup spaces (Bloodlines)")
    context, page, rec = open_context(browser, "commanders")
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(
            f"#seat-selects select[data-seat='{seat}']",
            "human" if seat == 0 else "heuristic",
        )
    set_rule_options(page, "bloodlines")
    page.fill("#opt-seed", "11")
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    images_loaded(page)
    catalog = page.evaluate(
        "({token: state.catalog.commander_token, spot: state.catalog.commander_spot,"
        " spaces: state.catalog.spaces})"
    )
    spot = catalog["spot"]
    waiting = set(page.evaluate("state.view.sardaukar_commander_space_ids"))
    check.ok(
        waiting == COMMANDER_SETUP_SPACES,
        "a four-player setup puts Commanders on the six spaces [Bloodlines p. 3]",
        sorted(waiting),
    )
    pieces = page.evaluate(COMMANDERS_JS)
    check.ok(
        sorted(p["space"] for p in pieces) == sorted(waiting),
        "one Commander stands on each space that holds one",
        sorted(p["space"] for p in pieces),
    )
    check.ok(
        page.evaluate("document.querySelectorAll('.commander-mark').length") == 0,
        "the old red C badge is gone",
    )
    pictured = catalog["token"] is not None
    if pictured:
        check.ok(
            all(p["tag"] == "IMG" and p["src"] == catalog["token"] for p in pieces)
            and all(p["loaded"] for p in pieces),
            "each is the rulebook figure (catalog.commander_token), loaded",
            [(p["space"], p["tag"], p["loaded"]) for p in pieces],
        )
    else:
        print("  .. no local commander picture: the drawn mark is checked below only")

    def geometry(pieces, label):
        wrong = []
        for piece in pieces:
            left, top, width, height = catalog["spaces"][piece["space"]]["box"]
            rect = piece["rect"]
            base_x = rect["left"] + rect["width"] * spot["base"][0]
            base_y = rect["top"] + rect["height"] * spot["base"][1]
            want_x = left + width * spot["anchor"][0]
            want_y = top + height * spot["anchor"][1]
            bottom = rect["top"] + rect["height"]
            ok = (
                near(base_x, want_x, 0.12)
                and near(base_y, want_y, 0.12)
                and near(rect["height"], height * spot["height"], 0.12)
                # the top-right corner: the base in the frame's right fifth
                # and top fifth, the frame below it left to the Agents
                and base_x > left + width * 0.8
                and base_y < top + height * 0.2
                and bottom < top + height * 0.35
            )
            if not ok:
                wrong.append((piece["space"], round(base_x, 2), round(want_x, 2),
                              round(base_y, 2), round(want_y, 2)))
        # An empty board would pass every corner vacuously.
        check.ok(bool(pieces) and not wrong, label, wrong or "no pieces")

    geometry(pieces, "its base sits on the frame's top-right corner, frame-tall")
    if pictured:
        ratios = [p["rect"]["width"] / p["rect"]["height"] for p in pieces]
        stage_ratio = page.evaluate(
            "(() => { const r = document.querySelector('.board-stage')"
            ".getBoundingClientRect(); return r.height / r.width; })()"
        )
        check.ok(
            all(near(r * stage_ratio, 130 / 195, 0.02) for r in ratios),
            "the figure keeps the picture's proportions",
            [round(r * stage_ratio, 3) for r in ratios],
        )
    check.ok(
        bool(pieces) and all(p["pointer"] == "none" for p in pieces),
        "a Commander never takes the click meant for its space",
    )
    word = page.evaluate("phraseText('{commander}')")
    labels = page.evaluate(
        """() => Object.fromEntries([...document.querySelectorAll('.hotspot')]
             .map((h) => [h.dataset.space, h.getAttribute('aria-label')]))"""
    )
    check.ok(
        all(word in labels[space] for space in waiting)
        and all(word not in label for space, label in labels.items()
                if space not in waiting),
        "a space with a Commander says so in its name",
        {space: labels.get(space) for space in sorted(waiting)[:2]},
    )

    # Acquired: the figure leaves the board (the view is the render's input).
    page.evaluate(
        """() => {
          const view = state.view;
          view.sardaukar_commander_space_ids =
            view.sardaukar_commander_space_ids.filter((s) => s !== "high_council");
          render();
        }"""
    )
    left_on_board = sorted(p["space"] for p in page.evaluate(COMMANDERS_JS))
    check.ok(
        left_on_board == sorted(waiting - {"high_council"}),
        "an acquired Commander leaves its space",
        left_on_board,
    )
    check.ok(
        word not in page.evaluate(
            "document.querySelector(\".hotspot[data-space='high_council']\")"
            ".getAttribute('aria-label')"
        ),
        "and its space no longer says it has one",
    )

    # Without the local picture the same places get a drawn mark.
    page.evaluate("state.catalog.commander_token = null; render();")
    drawn = page.evaluate(COMMANDERS_JS)
    check.ok(
        bool(drawn)
        and len(drawn) == len(left_on_board)
        and all(p["tag"] == "SPAN" for p in drawn),
        "without the picture each Commander is a drawn mark",
        [(p["space"], p["tag"]) for p in drawn],
    )
    geometry(drawn, "the drawn mark stands where the figure would")
    check.ok(not rec.js_errors, "no JS exceptions (Bloodlines)", rec.js_errors[:5])
    context.close()


# The Tleilaxu track's setup spice [Immortality p. 4] on the Bene Tleilax
# scan: the same hexagon as a Maker space's bonus spice, over the fourth
# space's printed "1st / 2" hexagon (catalog.bene_tleilax.layout).
BT_SPICE_JS = """(stageSelector) => {
  const stageNode = document.querySelector(stageSelector);
  if (!stageNode) return null;
  const stage = stageNode.getBoundingClientRect();
  return [...stageNode.querySelectorAll(".bonus-spice")].map((node) => {
    const r = node.getBoundingClientRect();
    const style = getComputedStyle(node);
    return {
      text: node.textContent.trim(),
      clip: style.clipPath,
      background: style.backgroundColor,
      left: (r.left - stage.left) / stage.width * 100,
      top: (r.top - stage.top) / stage.height * 100,
      width: r.width / stage.width * 100,
      height: r.height / stage.height * 100,
      stagePx: stage.width,
    };
  });
}"""


def tleilaxu_spice(base: str, browser) -> None:
    print("[6] the Tleilaxu track's setup spice (Immortality)")
    context, page, rec = open_context(browser, "tleilaxu-spice")
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(
            f"#seat-selects select[data-seat='{seat}']",
            "human" if seat == 0 else "heuristic",
        )
    set_rule_options(page, "immortality")
    page.fill("#opt-seed", "11")
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    board = page.evaluate("state.catalog.bene_tleilax")
    if not board.get("image"):
        print("  .. SKIP: no local Bene Tleilax scan, so no printed hexagon to cover")
        context.close()
        return
    page.wait_for_function(
        "[...document.querySelectorAll('img.bt-map')].every((i) => i.complete)"
    )
    layout = board["layout"]
    (x, y), (width, height) = layout["spice_point"], layout["spice_size"]
    want = [x - width / 2, y - height / 2, width, height]
    maker_background = page.evaluate(
        """() => { const probe = document.createElement("span");
          probe.className = "bonus-spice"; document.body.appendChild(probe);
          const colour = getComputedStyle(probe).backgroundColor;
          probe.remove(); return colour; }"""
    )

    def hexagon(stage_selector: str, label: str, tolerance: float) -> None:
        found = page.evaluate(BT_SPICE_JS, stage_selector) or []
        if not check.ok(len(found) == 1, f"{label}: one spice hexagon", found):
            return
        spice = found[0]
        check.ok(
            box_matches(spice, want, tolerance),
            f"{label}: it covers the printed hexagon's white outline",
            (spice, want),
        )
        check.ok(
            spice["text"] == str(page.evaluate("state.view.tleilaxu_track_spice"))
            and spice["clip"].startswith("polygon(")
            and spice["background"] == maker_background,
            f"{label}: the Maker spaces' bonus spice hexagon with the amount",
            spice,
        )

    check.ok(
        page.evaluate("state.view.tleilaxu_track_spice") == 2,
        "setup puts 2 spice on the track's fourth space [Immortality p. 4]",
    )
    # The column copy is a small stage: about a pixel of it in percent.
    small = page.evaluate(
        "document.querySelector('#market .bene-tleilax .bt-stage')"
        ".getBoundingClientRect().width"
    )
    hexagon("#market .bene-tleilax .bt-stage", "the column", max(0.12, 100 / small))
    check.ok(
        page.evaluate(
            "document.querySelectorAll('.bt-stage .bt-spice:not(.bonus-spice)').length"
        )
        == 0,
        "no dark rounded pill is left",
    )
    page.click(".bt-open")
    page.wait_for_selector("#bt-zoom:not([hidden])")
    hexagon("#bt-zoom-body .bt-stage", "the enlarged board", TOLERANCE)
    page.keyboard.press("Escape")
    page.evaluate("state.view.tleilaxu_track_spice = 0; render();")
    check.ok(
        page.evaluate("document.querySelectorAll('.bt-stage .bonus-spice').length")
        == 0,
        "taken by the first to reach the space, it leaves the board",
    )
    context.close()


def main() -> None:
    with server() as (base, server_log), chrome() as browser:
        try:
            context, page, rec = open_context(browser, "player")
            create_game(page, base, humans=(0,), seed=11)
            fresh_table(page)
            space_frames(page)
            reveal_preview(page)
            printed_places(page)
            agent_pieces(page)
            spy_pieces(page)
            conflict_units(page)
            intrigue_pile(page)
            failed = [r for r in rec.requests if r[3] >= 400]
            check.ok(not failed, "no failed requests", failed[:5])
            check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
            context.close()
            commander_pieces(base, browser)
            tleilaxu_spice(base, browser)
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
