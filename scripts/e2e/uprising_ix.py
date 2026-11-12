"""Uprising with Rise of Ix in the play UI (stage P7f of
docs/base-game-and-ix-plan.md, 19.5).

"Unfold only half of the CHOAM board overlay to cover only the top-right
corner of the UPRISING board" [Main p. 18] (docs/rules/rise-of-ix.md 17):
the overlay's CHOAM piece covers Assembly Hall, Gather Support, Shipping and
Accept Contract and their two posts, and prints Interstellar Shipping,
Smuggling and the Shipping track; the Ix board lies beside the board; each
of the two counts one observation post the page draws
(display.board_layout_uprising_ix).

[1] The setup screen: the Rise of Ix box is open on Uprising, unchecked;
    checked there it shows its note in both languages and, since stage
    P7f-2, locks nothing (the CHOAM module, the Tech Module and Arrakeen
    Scouts all play with it); across a switch to the original game and back
    each box keeps its own choice; POST /games carries Uprising with
    rise_of_ix and those options.
[2] Six finished Uprising + Rise of Ix games played by AI seats with the
    Leader draft and the promo cards (heuristic seeds 2 and 4; seed 3 with
    Bloodlines, picked 2026-10-30 by a scan of seeds 1-5 and 1-4; and, since
    P7f-2, seed 2 with the CHOAM module, seed 2 with Arrakeen Scouts (Secret
    Stash) and seed 3 with Bloodlines and the Tech Module, from seeds 1-3),
    their logs rendered with the page's own functions in both languages
    (log_words.check_log); they reach a Freighter moved, a dreadnought
    deployed and controlling a space, a Tech tile acquired and the starting
    Contracts revealed.
[3] A four-human Uprising + Rise of Ix + Bloodlines table at its first
    decision: the CHOAM piece lies in its box, raised so that Smuggling lies
    where Gather Support was, and the part above the board's top edge is cut
    off there, and the Ix board beside it raised the same way so that its
    Dreadnought lies level with Smuggling (user decision 2026-10-31); the
    board's hotspots include Interstellar Shipping and Smuggling and none of
    the four covered spaces; the Ix board beside it has Tech Negotiation and
    Dreadnought; one drawn post on each board, the covered posts gone; the
    four Freighters on the piece's bottom step; the Commanders on
    Dreadnought and Tech Negotiation stand on the Ix board; the Reserve
    offers Ilesa's Foldspace stack. Spy rows put in the page's state for the
    two new posts light a target on the right board. A screenshot of the
    board goes to E2E_SHOTS_DIR.
[4] One human seat against three heuristic AIs on Uprising + Rise of Ix,
    played in the browser to the end with a varied pick, Korean then
    English: every step settles without an error banner, every id the view
    names is in the catalog, prettify() is never called.
[5] The Rise of Ix starting Contracts (CHOAM module, stage P7f-2; "Each
    player looks at the two they've been given, choosing simultaneously"
    [Main p. 16]), a four-human table, seat by seat from the First Player:
    the chooser's page offers its own two, names them on its own panel and
    shows their faces; no earlier chooser's two reach the page's state (its
    view, rows, log, summary) while the choice is open; once the last seat
    has chosen, every seat's choice is among the active Contracts in the
    view, both languages with no placeholder left.
[6] Arrakeen Scouts' Rise of Ix missions' pieces (stage P7f-2), put in a
    four-human Uprising + Rise of Ix + Scouts game's view: Secret Stash's
    spice and Stowaways' troops on Smuggling on the overlay, Armed Escort's
    dreadnought and spice on the Ix board's Dreadnought, each piece with its
    words in both languages.
Every page: no JS errors; the server logs no Traceback or ERROR.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from common import SERVER_LOG_COPY, Check, chrome, client_state, open_context, server
from imperium_game import MISSING_JS, PICK_JS
from log_words import RENDER_JS, check_log
from log_words import check as log_words_check
from open_mode import settled

check = Check()
SHOTS = Path(
    os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(prefix="dune-uprising-ix-")
)

IX = {"rise_of_ix": True, "leader_draft": True, "promo_cards": True}
GAMES = (
    {"seats": ["heuristic"] * 4, "game_seed": 2, "policy_seed": 2, **IX},
    {"seats": ["heuristic"] * 4, "game_seed": 4, "policy_seed": 4, **IX},
    {
        "seats": ["heuristic"] * 4,
        "game_seed": 3,
        "policy_seed": 3,
        "bloodlines": True,
        **IX,
    },
    # Stage P7f-2: the CHOAM module, Arrakeen Scouts, the Tech Module.
    {
        "seats": ["heuristic"] * 4,
        "game_seed": 2,
        "policy_seed": 2,
        "choam_module": True,
        **IX,
    },
    {
        "seats": ["heuristic"] * 4,
        "game_seed": 2,
        "policy_seed": 2,
        "arrakeen_scouts": True,
        **IX,
    },
    {
        "seats": ["heuristic"] * 4,
        "game_seed": 3,
        "policy_seed": 3,
        "bloodlines": True,
        "tech_module": True,
        **IX,
    },
)
WANTED = {
    "a Freighter moved": "event freighter_moved",
    "a dreadnought deployed": "event dreadnoughts_deployed",
    "a dreadnought controlling a space": "event dreadnought_control_placed",
    "a Tech tile acquired": "event tech_acquired",
    "the starting Contracts revealed": "event starting_contract_revealed",
}
COVERED = {"assembly_hall", "gather_support", "shipping", "accept_contract"}
COVERED_POSTS = {
    "landsraad-assembly-hall-gather-support",
    "choam-shipping-accept-contract",
}
OVERLAY_POST = "choam-interstellar-shipping-smuggling"
IX_BOARD_POST = "landsraad-tech-negotiation-dreadnought"

POST_JS = """async (body) => {
  const r = await fetch('/games', {method: 'POST',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  return {status: r.status, body: await r.json()};
}"""

BOXES_JS = """() => {
  const box = (id) => {
    const input = document.getElementById(id);
    return {checked: input.checked, disabled: input.disabled};
  };
  const note = document.getElementById("opt-uprising-ix-note");
  return {
    ix: box("opt-rise-of-ix"), choam: box("opt-choam"), tech: box("opt-tech"),
    scouts: box("opt-scouts"), cards: box("opt-imperium-cards"),
    note: !note.hidden, noteText: note.textContent.trim(),
    noteWant: t("html.uprising_ix_note"),
  };
}"""


def setup_box(base: str, browser) -> None:
    print("[1] the setup screen: Rise of Ix on Uprising")
    context, page, rec = open_context(browser, "uprising-ix-setup")
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    page.wait_for_function(
        "state.server !== null"
        " && document.querySelectorAll('#seat-selects select').length === 4"
    )
    page.check("#opt-choam")
    page.check("#opt-scouts")
    opened = page.evaluate(BOXES_JS)
    check.ok(
        opened["ix"] == {"checked": False, "disabled": False} and not opened["note"],
        "the Rise of Ix box is open on Uprising, unchecked, with no note",
        opened,
    )
    page.check("#opt-rise-of-ix")
    open_box = {"checked": True, "disabled": False}
    for language in ("ko", "en"):
        page.evaluate(f"setLanguage('{language}')")
        shown = page.evaluate(BOXES_JS)
        check.ok(
            all(shown[key] == open_box for key in ("choam", "tech", "scouts"))
            and shown["note"]
            and shown["noteText"] == shown["noteWant"],
            f"[{language}] Rise of Ix on Uprising shows its note and locks nothing"
            " (stage P7f-2)",
            shown,
        )
    page.evaluate("setLanguage('ko')")
    page.select_option("#opt-base-game", "imperium")
    original = page.evaluate(BOXES_JS)
    page.select_option("#opt-base-game", "uprising")
    again = page.evaluate(BOXES_JS)
    page.uncheck("#opt-rise-of-ix")
    back = page.evaluate(BOXES_JS)
    check.ok(
        original["ix"]["checked"]
        # The original game takes the Tech Module (P7c) and Arrakeen Scouts
        # (P8), never the CHOAM module.
        and original["tech"] == original["scouts"] == open_box
        and original["choam"] == {"checked": False, "disabled": True}
        and not original["note"]
        and all(again[key] == open_box for key in ("choam", "tech", "scouts"))
        and again["note"]
        and all(back[key] == open_box for key in ("choam", "tech", "scouts"))
        and not back["note"],
        "the boxes keep their own choices across the base game and Rise of Ix",
        {"original": original, "again": again, "back": back},
    )
    page.check("#opt-rise-of-ix")
    for seat in range(4):
        page.select_option(f"#seat-selects select[data-seat='{seat}']", "human")
    with page.expect_request(
        lambda r: r.method == "POST" and r.url.endswith("/games")
    ) as sent:
        page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    settled(page)
    body = sent.value.post_data_json
    check.ok(
        body.get("base_game") == "uprising"
        and body.get("rise_of_ix") is True
        and all(
            body.get(key) is True
            for key in ("choam_module", "tech_module", "arrakeen_scouts")
        ),
        "POST /games carries Uprising with Rise of Ix, the CHOAM module, the Tech"
        " Module and Arrakeen Scouts",
        body,
    )
    check.ok(not rec.js_errors, "no page errors on the setup screen", rec.js_errors[:3])
    context.close()


def ai_logs(page) -> None:
    print(f"[2] the logs of {len(GAMES)} finished AI games, both languages")
    records: list[dict] = []
    names: set[str] = set()
    posts: list[str] = []
    for config in GAMES:
        created = page.evaluate(POST_JS, config)
        label = f"seed {config['game_seed']}"
        body = created["body"]
        check.ok(
            created["status"] == 200 and body["finished"] and body["rise_of_ix"],
            f"{label}: a finished Uprising game with Rise of Ix",
            {key: body.get(key) for key in ("finished", "round_number", "detail")},
        )
        if created["status"] != 200:
            continue
        result = page.evaluate(RENDER_JS, {"gameId": body["game_id"]})
        records.extend(result["out"])
        names.update(result["names"])
        posts = result["posts"]
    print(f"  .. {len(records)} rendered lines")
    sources = {record["src"] for record in records}
    for label, source in WANTED.items():
        check.ok(source in sources, f"the games reach {label}", source)
    check_log(records, sorted(names, key=len, reverse=True), posts)


TABLE_JS = """() => {
  const main = document.querySelector("#board .board-stage:not(.ix-stage)");
  const ix = document.querySelector("#board .ix-stage");
  const spaces = (stage) => stage
    ? [...stage.querySelectorAll(".hotspot[data-space]")].map((n) => n.dataset.space)
    : [];
  const posts = (stage) => stage
    ? [...stage.querySelectorAll(".drawn-post")].map((n) => n.dataset.post) : [];
  const commanders = (stage) => stage
    ? [...stage.querySelectorAll(".commander-piece")].map((n) => n.dataset.space)
    : [];
  const overlay = main && main.querySelector(".board-overlay");
  const layout = boardLayout();
  const stageRect = main ? main.getBoundingClientRect() : null;
  const pieceRect = overlay ? overlay.getBoundingClientRect() : null;
  const clip = overlay ? getComputedStyle(overlay).clipPath : "";
  const insetTop = parseFloat((clip.match(/inset\\(([-\\d.]+)%/) || [])[1]);
  const smuggling = main && main.querySelector('.hotspot[data-space="smuggling"]');
  const dreadnought = ix && ix.querySelector('.hotspot[data-space="dreadnought"]');
  const ixMap = ix && ix.querySelector(".board-map");
  const ixRect = ixMap ? ixMap.getBoundingClientRect() : null;
  const ixClip = ixMap ? getComputedStyle(ixMap).clipPath : "";
  const ixInset = parseFloat((ixClip.match(/inset\\(([-\\d.]+)%/) || [])[1]);
  return {
    overlay: overlay ? {src: overlay.getAttribute("src"),
      box: [overlay.style.left, overlay.style.top, overlay.style.width,
            overlay.style.height].map(parseFloat)} : null,
    edge: pieceRect ? {stageTop: stageRect.top, pieceTop: pieceRect.top, clip,
      shownTop: pieceRect.top + insetTop / 100 * pieceRect.height} : null,
    smugglingTop: smuggling ? parseFloat(smuggling.style.top) : null,
    level: smuggling && dreadnought && ixRect ? {
      smuggling: smuggling.getBoundingClientRect().top,
      dreadnought: dreadnought.getBoundingClientRect().top,
      ixTop: ixRect.top, ixShownTop: ixRect.top + ixInset / 100 * ixRect.height,
      stageTop: stageRect.top} : null,
    gatherSupportTop: state.catalog.spaces.gather_support.box[1],
    overlayBox: state.catalog.ix.overlays.choam,
    main: spaces(main), ix: spaces(ix),
    mainPosts: posts(main), ixPosts: posts(ix),
    layoutPosts: Object.keys(layout.posts),
    freighters: main ? main.querySelectorAll(".freighter-disc").length : 0,
    commanders: state.view.sardaukar_commander_space_ids,
    mainCommanders: commanders(main), ixCommanders: commanders(ix),
    reserve: (state.view.reserve_stacks || []).map(([id, count]) => [id, count]),
  };
}"""

SPY_JS = """([overlayPost, ixPost]) => {
  const blank = {detail: null, detail_ko: null, undoable: true,
    sent_by_turn_end: false, warning: null, shortfall: null,
    strength_after: null};
  state.actions.actions = [overlayPost, ixPost].map((post, index) =>
    ({...blank, index, action_id: "place_reveal_spy", arguments: {post_id: post}}));
  state.actions.agent_placements = null;
  render();
  const where = (post) => {
    const node = document.querySelector(`.spy-post-hotspot[data-post="${post}"]`);
    if (!node) return null;
    return node.closest(".ix-stage") ? "ix" : "main";
  };
  return {overlay: where(overlayPost), ix: where(ixPost)};
}"""


def check_table(page) -> None:
    print("[3] an Uprising + Rise of Ix + Bloodlines table at its first decision")
    created = page.evaluate(
        POST_JS,
        {
            "seats": ["human"] * 4,
            "game_seed": 3,
            "rise_of_ix": True,
            "bloodlines": True,
        },
    )
    page.evaluate("(id) => openGame(id)", created["body"]["game_id"])
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    settled(page)
    table = page.evaluate(TABLE_JS)
    overlay = table["overlay"]
    check.ok(
        overlay is not None
        and "choam" in overlay["src"]
        and all(
            abs(a - b) < 0.01
            for a, b in zip(overlay["box"], table["overlayBox"], strict=True)
        ),
        "the CHOAM piece lies over the board's top-right corner in its box",
        table,
    )
    edge = table["edge"]
    check.ok(
        edge is not None
        and edge["pieceTop"] < edge["stageTop"] - 0.5
        and abs(edge["shownTop"] - edge["stageTop"]) < 0.5
        and table["smugglingTop"] is not None
        and abs(table["smugglingTop"] - table["gatherSupportTop"]) < 0.01,
        "Smuggling lies where Gather Support was; the piece reaches above the"
        " board and is cut off at the board's top edge (user decision 2026-10-31)",
        {key: table[key] for key in ("edge", "smugglingTop", "gatherSupportTop")},
    )
    level = table["level"]
    check.ok(
        level is not None
        and abs(level["dreadnought"] - level["smuggling"]) < 1
        and level["ixTop"] < level["stageTop"] - 0.5
        and abs(level["ixShownTop"] - level["stageTop"]) < 0.5,
        "the Ix board's Dreadnought lies level with Smuggling; the Ix board"
        " reaches above the board and its picture is cut off at the board's top"
        " edge (user decision 2026-10-31)",
        level,
    )
    check.ok(
        {"interstellar_shipping", "smuggling"} <= set(table["main"])
        and not COVERED & set(table["main"])
        and sorted(table["ix"]) == ["dreadnought", "tech_negotiation"],
        "the board's hotspots take the piece's two spaces and none it covers; the"
        " Ix board beside it has its two",
        table,
    )
    check.ok(
        table["mainPosts"] == [OVERLAY_POST]
        and table["ixPosts"] == [IX_BOARD_POST]
        and OVERLAY_POST in table["layoutPosts"]
        and not COVERED_POSTS & set(table["layoutPosts"]),
        "one drawn post on each board, the covered posts gone",
        table,
    )
    check.ok(table["freighters"] == 4, "four Freighters on the Shipping track", table)
    on_ix = {"dreadnought", "tech_negotiation"} & set(table["commanders"])
    check.ok(
        on_ix
        and sorted(table["ixCommanders"]) == sorted(on_ix)
        and sorted(table["mainCommanders"]) == sorted(set(table["commanders"]) - on_ix),
        "the Commanders on Dreadnought and Tech Negotiation stand on the Ix board",
        table,
    )
    foldspace = dict(table["reserve"]).get("foldspace_card")
    check.ok(
        foldspace == 6,
        "the Reserve holds the original game's six Foldspace cards for Ilesa",
        table["reserve"],
    )
    spies = page.evaluate(SPY_JS, [OVERLAY_POST, IX_BOARD_POST])
    check.ok(
        spies == {"overlay": "main", "ix": "ix"},
        "a Spy row lights each new post on its own board",
        spies,
    )
    page.evaluate("render()")
    settled(page)
    board = page.locator("#board")
    shot = SHOTS / "uprising_ix_board.png"
    board.screenshot(path=str(shot))
    print(f"  .. board screenshot {shot}")


def play_human(page, rec) -> None:
    print("[4] one human seat against three heuristic AIs, played in the browser")
    page.evaluate("setLanguage('ko')")
    created = page.evaluate(
        POST_JS,
        {
            "seats": ["human", "heuristic", "heuristic", "heuristic"],
            "game_seed": 5,
            "rise_of_ix": True,
        },
    )
    page.evaluate("(id) => openGame(id)", created["body"]["game_id"])
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    settled(page)
    page.evaluate(
        """() => {
          window.prettifyCalls = [];
          const real = window.prettify;
          window.prettify = (id) => { window.prettifyCalls.push(String(id));
                                      return real(id); };
        }"""
    )
    steps = 0
    missing: set[str] = set()
    switched = False
    while steps < 3000:
        snap = client_state(page)
        if snap["finished"]:
            break
        if snap["error"]:
            check.ok(False, "no error banner", snap["error"])
            break
        if not switched and steps == 50:
            page.evaluate("setLanguage('en')")
            page.wait_for_function("refreshFlight === null")
            switched = True
        if snap["confirmation"] is not None:
            page.evaluate("confirmTurn()")
        else:
            page.evaluate(PICK_JS, steps)
        if not settled(page, 20):
            print("  NOT SETTLED", json.dumps(client_state(page), ensure_ascii=False))
            check.ok(False, "every step settles")
            break
        steps += 1
        if steps % 10 == 0:
            missing.update(page.evaluate(MISSING_JS))
    final = client_state(page)
    print(f"  .. {steps} human steps")
    check.ok(final["finished"], "the game reaches its end in the browser", final)
    check.ok(switched, "the language switched halfway", steps)
    check.ok(
        not missing, "every id the view names is in the catalog", sorted(missing)[:6]
    )
    calls = page.evaluate("window.prettifyCalls")
    check.ok(
        not calls, "prettify() is never called while playing", sorted(set(calls))[:6]
    )
    check.ok(not rec.js_errors, "no page errors while playing", rec.js_errors[:3])
    page.evaluate("setLanguage('ko')")


CONTRACT_STATE_JS = """() => {
  const decision = state.summary.decision || {};
  const rows = (state.actions ? state.actions.actions : [])
    .filter((row) => row.action_id === "choose_starting_contract");
  const own = state.view.private || {};
  const seat = state.view.player;
  const panel = document.querySelector(`#seats article.seat[data-seat="${seat}"]`);
  const pair = own.starting_contract_ids || [];
  return {
    kind: decision.kind || null, owner: decision.owner, seat,
    confirmation: state.summary.confirmation,
    rows: rows.map((row) => ({index: row.index, id: row.arguments.instance_id})),
    shown: rows.map((row) => [...document.querySelectorAll(
      `#actions .action-item[data-index="${row.index}"]`)]
      .map((n) => n.innerText).join("")),
    pair, pick: own.starting_contract_pick || "",
    names: pair.map((id) => nameOf(id)),
    faces: pair.map((id) => Boolean((state.catalog.contracts[baseId(id)] || {}).image)),
    panel: panel ? panel.innerText : "",
    blob: JSON.stringify([state.view, state.actions, state.log, state.summary]),
    active: state.view.players.map((player) => player.active_contract_ids || []),
  };
}"""


def check_starting_contracts(page) -> None:
    print("[5] the Rise of Ix starting Contracts, seat by seat")
    page.evaluate("setLanguage('ko')")
    created = page.evaluate(
        POST_JS,
        {
            "seats": ["human"] * 4,
            "game_seed": 2,
            "rise_of_ix": True,
            "choam_module": True,
        },
    )
    page.evaluate("(id) => openGame(id)", created["body"]["game_id"])
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    settled(page)
    earlier: list[str] = []
    picks: dict[int, str] = {}
    for step in range(4):
        shown = page.evaluate(CONTRACT_STATE_JS)
        leaked = [card for card in earlier if card in shown["blob"]]
        check.ok(
            shown["kind"] == "starting_contract"
            and shown["owner"] == shown["seat"]
            and len(shown["rows"]) == 2
            and sorted(row["id"] for row in shown["rows"]) == sorted(shown["pair"])
            and all(name in shown["panel"] for name in shown["names"])
            and all(shown["faces"])
            and not shown["pick"]
            and all(
                name in text
                for name, text in zip(shown["names"], shown["shown"], strict=True)
            ),
            f"seat {shown['seat']}: its own two Contracts offered, named on its"
            " panel, with their faces",
            {
                key: shown[key]
                for key in (
                    "kind",
                    "owner",
                    "seat",
                    "rows",
                    "names",
                    "faces",
                    "panel",
                    "shown",
                )
            },
        )
        check.ok(
            not leaked,
            f"seat {shown['seat']}: no earlier chooser's two reach its page",
            leaked,
        )
        page.evaluate("setLanguage('en')")
        settled(page)
        english = page.evaluate(CONTRACT_STATE_JS)
        page.evaluate("setLanguage('ko')")
        settled(page)
        check.ok(
            all(name in english["panel"] for name in english["names"])
            and "{" not in english["panel"] + shown["panel"],
            f"seat {shown['seat']}: the panel line in both languages",
            {"ko": shown["panel"], "en": english["panel"]},
        )
        row = shown["rows"][step % 2]
        picks[shown["seat"]] = row["id"]
        earlier.extend(shown["pair"])
        page.evaluate(f"applyAction({row['index']})")
        settled(page, 20)
        if page.evaluate("state.summary.confirmation") is not None:
            page.evaluate("confirmTurn()")
            settled(page, 20)
    final = page.evaluate(CONTRACT_STATE_JS)
    check.ok(
        final["kind"] != "starting_contract"
        and all(
            any(
                card in active or card.split(":", 1)[-1] in active
                for active in [final["active"][seat]]
            )
            for seat, card in picks.items()
        ),
        "once the last seat has chosen, every choice is among its active Contracts",
        {"picks": picks, "active": final["active"], "kind": final["kind"]},
    )


SCOUTS_JS = """() => {
  state.view.scouts_goods = [
    ["secret_stash", "smuggling", "spice", 2, -1],
    ["armed_escort", "dreadnought", "spice", 1, 0],
  ];
  state.view.scouts_parked = [
    ["armed_escort", 0, "dreadnought", 1],
    ["stowaways", 1, "smuggling", 2],
  ];
  render();
  return [...document.querySelectorAll("#board .scouts-piece")].map((n) => ({
    location: n.dataset.location, kind: n.dataset.kind, mission: n.dataset.mission,
    ix: Boolean(n.closest(".ix-stage")), title: n.title,
  }));
}"""


def check_scouts_missions(page) -> None:
    print("[6] Arrakeen Scouts' Rise of Ix missions' pieces")
    created = page.evaluate(
        POST_JS,
        {
            "seats": ["human"] * 4,
            "game_seed": 2,
            "rise_of_ix": True,
            "arrakeen_scouts": True,
        },
    )
    page.evaluate("(id) => openGame(id)", created["body"]["game_id"])
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    settled(page)
    for language in ("ko", "en"):
        page.evaluate(f"setLanguage('{language}')")
        settled(page)
        pieces = page.evaluate(SCOUTS_JS)
        smuggling = [p for p in pieces if p["location"] == "smuggling"]
        dreadnought = [p for p in pieces if p["location"] == "dreadnought"]
        check.ok(
            sorted(p["kind"] for p in smuggling) == ["spice", "troop"]
            and not any(p["ix"] for p in smuggling)
            and sorted(p["kind"] for p in dreadnought) == ["dreadnought", "spice"]
            and all(p["ix"] for p in dreadnought)
            and all(p["title"] and "{" not in p["title"] for p in pieces),
            f"[{language}] Smuggling's pieces on the overlay, Dreadnought's on the"
            " Ix board, Armed Escort's as a dreadnought",
            pieces,
        )
    page.evaluate("setLanguage('ko')")


def main() -> None:
    with server() as (base, log_path), chrome() as browser:
        setup_box(base, browser)
        _, page, rec = open_context(browser, "uprising-ix")
        page.goto(base + "/")
        page.wait_for_function("state.catalog !== null")
        ai_logs(page)
        check_table(page)
        play_human(page, rec)
        check_starting_contracts(page)
        check_scouts_missions(page)
        check.ok(not rec.js_errors, "no page errors", rec.js_errors[:3])
        errors = [
            line
            for line in log_path.read_text().splitlines()
            if "ERROR" in line or "Traceback" in line
        ]
        check.ok(not errors, f"no server errors (see {SERVER_LOG_COPY})", errors[:3])
        SERVER_LOG_COPY.write_text(log_path.read_text())
    # log_words' checks count on its own Check; fold them into this run.
    check.passed += log_words_check.passed
    check.failed.extend(log_words_check.failed)
    check.finish()


if __name__ == "__main__":
    main()
