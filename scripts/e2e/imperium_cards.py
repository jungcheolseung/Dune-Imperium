"""Uprising with the original game's cards in the play UI (stage P7e of
docs/base-game-and-ix-plan.md, 19.4 P7-2).

The ``imperium_cards`` option shuffles the original Imperium and Intrigue
cards (all but Calculated Hire) into Uprising's decks and adds the original
eight Leaders ("COMBINING WITH BASE DUNE: IMPERIUM" [Main p. 18],
docs/rules/imperium-base.md 13.4). Their names, text and faces come from
the catalog the original game's screens already use (P5), on Uprising's
board:

[1] The setup box: its label is the table's text in both languages, it
    opens unchecked, the original game clears and locks it (the cards are
    its own) and gives it back on a return to Uprising, POST /games carries
    it, and the header's badge names it.
[2] Three finished Uprising games with the original cards played by AI seats
    with the Leader draft and the promo cards (heuristic seeds 5 and 3,
    random seed 2, picked 2026-10-30 by a scan of seeds 1-30 for the lines
    below), their logs rendered with the page's own functions in both
    languages (log_words.check_log): prettify() never reached, no English
    in the Korean log outside names, no Hangul in the English log, no
    engine id's shape. The games reach the original cards' lines on
    Uprising's board: Masterstroke's Factions chosen and revealed, a card
    Helena's Manipulate sets aside.
[3] One human seat against three heuristic AIs, played in the browser to
    the end with a varied pick, Korean then English from step 50: the
    draft strip draws the original Leaders' faces, the human drafts Baron
    Harkonnen, every step settles without an error banner, every id the
    view names is in the catalog, prettify() is never called, and the
    seats' Leader thumbnails are pictures.
[4] Rows a game seldom reaches, put in a four-human game's state at its
    first decision (as ix_screens' Disposal Facility step does), in both
    languages: Kwisatz Haderach's Agent sent from the Conflict (Into the
    Fray's, ``from_space: "conflict"``, OQ-146) beside one sent from a
    board space, each with the page's words for its label and its origin;
    Earl Memnon's Connections rows naming each Faction and the Leader (the
    word, as every Leader ability's row does); and
    The Voice's barred space on Uprising's board, named on the space's
    title and marked on it (OQ-116).
Every page: no JS errors; the server logs no Traceback or ERROR.
"""

from __future__ import annotations

import json

from common import SERVER_LOG_COPY, Check, chrome, client_state, open_context, server
from imperium_game import MISSING_JS, PICK_JS
from log_words import RENDER_JS, check_log
from log_words import check as log_words_check
from open_mode import settled

check = Check()

CARDS = {"imperium_cards": True, "leader_draft": True, "promo_cards": True}
GAMES = (
    {"seats": ["heuristic"] * 4, "game_seed": 5, "policy_seed": 5, **CARDS},
    {"seats": ["heuristic"] * 4, "game_seed": 3, "policy_seed": 3, **CARDS},
    {"seats": ["random"] * 4, "game_seed": 2, "policy_seed": 2, **CARDS},
)
WANTED = {
    "a secret Masterstroke Faction chosen": "action choose_masterstroke_faction",
    "Masterstroke revealed": "event masterstroke_revealed",
    "a card Manipulate sets aside": "event imperium_row_card_set_aside",
}
ORIGINAL_LEADERS = {
    "paul_atreides",
    "duke_leto_atreides",
    "baron_vladimir_harkonnen",
    "glossu_rabban",
    "count_ilban_richese",
    "helena_richese",
    "earl_memnon_thorvald",
    "countess_ariana_thorvald",
}
# Seed 2's draft offers seat 0 Baron Harkonnen (tests/server's
# test_imperium_cards_game picks him there too).
HUMAN = {"seats": ["human", "heuristic", "heuristic", "heuristic"], "game_seed": 2}
# The human's step that switches the page to English (its game takes about
# a hundred).
SWITCH_AT = 50

POST_JS = """async (body) => {
  const r = await fetch('/games', {method: 'POST',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  return {status: r.status, body: await r.json()};
}"""

BOX_JS = """() => {
  const input = document.getElementById("opt-imperium-cards");
  return {
    checked: input.checked, disabled: input.disabled,
    shown: input.parentElement.textContent.trim(),
    want: t("html.opt_imperium_cards"),
    promo: [...document.querySelectorAll("#opt-promo ~ span")]
      .filter((span) => !span.hidden).map((span) => span.textContent.trim()),
    promoWant: t("html.opt_promo"),
  };
}"""


def setup_box(base: str, browser) -> None:
    print("[1] the setup box")
    context, page, rec = open_context(browser, "imperium-cards-setup")
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    page.wait_for_function(
        "state.server !== null"
        " && document.querySelectorAll('#seat-selects select').length === 4"
    )
    for language in ("ko", "en"):
        page.evaluate(f"setLanguage('{language}')")
        box = page.evaluate(BOX_JS)
        check.ok(
            box["shown"] == box["want"] and box["want"],
            f"[{language}] the box's label is the table's text",
            box,
        )
        check.ok(
            box["promo"] == [box["promoWant"]],
            f"[{language}] the promo box names the original promos as well",
            box["promo"],
        )
    page.evaluate("setLanguage('ko')")
    opened = page.evaluate(BOX_JS)
    check.ok(
        (opened["checked"], opened["disabled"]) == (False, False),
        "the box opens unchecked on Uprising",
        opened,
    )
    page.check("#opt-imperium-cards")
    page.select_option("#opt-base-game", "imperium")
    locked = page.evaluate(BOX_JS)
    check.ok(
        (locked["checked"], locked["disabled"]) == (False, True),
        "the original game clears and locks it",
        locked,
    )
    page.select_option("#opt-base-game", "uprising")
    back = page.evaluate(BOX_JS)
    check.ok(
        (back["checked"], back["disabled"]) == (True, False),
        "back on Uprising the box is checked again",
        back,
    )
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
        body.get("imperium_cards") is True and body.get("base_game") == "uprising",
        "POST /games carries the box",
        body,
    )
    badges = page.evaluate(
        """() => ({
          shown: document.getElementById("header-status").title,
          want: t("render.badge_imperium_cards"),
          summary: state.summary.imperium_cards,
        })"""
    )
    check.ok(
        badges["summary"] is True and badges["want"] in badges["shown"],
        "the summary and the header's title name the option",
        badges,
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
        label = f"{config['seats'][0]} seed {config['game_seed']}"
        body = created["body"]
        check.ok(
            created["status"] == 200
            and body["finished"]
            and body["imperium_cards"] is True,
            f"{label}: a finished Uprising game with the original cards",
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


DRAFT_JS = """(original) => {
  const cards = [...document.querySelectorAll("#market .vcard.leader")];
  return {
    pool: state.view.leader_draft_pool,
    original: state.view.leader_draft_pool.filter((id) => original.includes(id)),
    pictured: cards.filter((card) => card.querySelector("img")).length,
    cards: cards.length,
  };
}"""

PICK_LEADER_JS = """(leader) => {
  const row = state.actions.actions.find((row) =>
    row.action_id === "pick_leader" && row.arguments.leader_id === leader);
  if (!row) return false;
  applyAction(row.index);
  return true;
}"""

THUMBS_JS = """() => [...document.querySelectorAll("#seats article.seat")].map(
  (card) => Boolean(card.querySelector("img.leader-thumb")))"""


def play_human(page, rec) -> None:
    print("[3] one human seat against three heuristic AIs, played in the browser")
    page.evaluate("setLanguage('ko')")
    created = page.evaluate(POST_JS, {**HUMAN, **CARDS})
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
    draft = page.evaluate(DRAFT_JS, sorted(ORIGINAL_LEADERS))
    check.ok(
        draft["original"]
        and draft["cards"] == len(draft["pool"])
        and draft["pictured"] == draft["cards"],
        "the draft strip draws every Leader of the pool, the original ones among"
        " them, as pictures",
        draft,
    )
    check.ok(
        page.evaluate(PICK_LEADER_JS, "baron_vladimir_harkonnen"),
        "the human seat drafts Baron Harkonnen",
    )
    settled(page)
    steps = 0
    missing: set[str] = set()
    switched = False
    thumbs: list[bool] = []
    while steps < 3000:
        snap = client_state(page)
        if snap["finished"]:
            break
        if snap["error"]:
            check.ok(False, "no error banner", snap["error"])
            break
        if not switched and steps == SWITCH_AT:
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
            if not thumbs:
                thumbs = page.evaluate(THUMBS_JS)
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
    leaders = page.evaluate("state.view.players.map((player) => player.leader_id)")
    check.ok(
        leaders[0] == "baron_vladimir_harkonnen" and thumbs == [True] * 4,
        "the Baron sits at seat 0 and every seat's Leader is drawn as a picture",
        {"leaders": leaders, "thumbs": thumbs},
    )
    check.ok(not rec.js_errors, "no page errors while playing", rec.js_errors[:3])
    page.evaluate("setLanguage('ko')")


# Rows put in the page's state at a four-human game's first decision (the
# decision's own rows replaced), each drawn in the flat action list; the
# page's words for its label (the text between its icons) and the words of
# what it names must all be in the row.
ROWS_JS = """([rows, leader]) => {
  try { window.localStorage.setItem("dune.fullActionList", "1"); } catch (e) {}
  state.view.players[0].leader_id = leader;
  state.actions.actions = rows.map(([action_id, args], index) => ({
    action_id, arguments: args, index, detail: null, detail_ko: null,
    undoable: true, sent_by_turn_end: false, warning: null, shortfall: null,
    strength_after: null,
  }));
  state.actions.agent_placements = null;
  render();
  const norm = (s) => s.replace(/\\s+/g, " ").trim();
  const words = (id) => (ACTION_LABELS[id] || "{missing}")
    .split(/\\{[^}]*\\}/).map(norm).filter(Boolean);
  return rows.map(([action_id, args], index) => ({
    action_id, args,
    words: words(action_id),
    shown: [...document.querySelectorAll(
      `#actions .action-item[data-index="${index}"]`)]
      .map((item) => norm(item.innerText)),
  }));
}"""

NAMES_JS = """(spaces) => ({
  leader: phraseText("{leader}"),
  conflict: phraseText("{conflict}"),
  spaces: Object.fromEntries(spaces.map((id) => [id, spaceName(id)])),
  factions: FACTION_LABELS,
})"""

VOICE_JS = """([space, seat]) => {
  state.view.players[seat].voice_blocked_space_ids = [space];
  render();
  const hotspot = document.querySelector(
    `#board .board-stage .hotspot[data-space="${space}"]`);
  const voice = lookup("the_voice", "cards");
  return {
    title: hotspot ? hotspot.title : null,
    marked: hotspot ? hotspot.querySelectorAll(".voice-barred-seat").length : 0,
    want: t("board.voice_blocked", {
      card: voice ? voice.name : "The Voice",
      seats: t("common.seat", {seat}),
    }),
  };
}"""

KWISATZ = "imperium:kwisatz_haderach:0"
KWISATZ_ROWS = [
    (
        "place_agent",
        {"card_id": KWISATZ, "space_id": "arrakeen", "from_space": "conflict"},
    ),
    (
        "place_agent",
        {"card_id": KWISATZ, "space_id": "arrakeen", "from_space": "carthag"},
    ),
]
CONNECTIONS_ROWS = [
    ("choose_connections_influence", {"faction": faction})
    for faction in ("emperor", "spacing_guild", "bene_gesserit", "fremen")
]


def injected_rows(page) -> None:
    print("[4] rows a game seldom reaches, in a four-human game's state")
    created = page.evaluate(POST_JS, {"seats": ["human"] * 4, "game_seed": 4, **CARDS})
    page.evaluate("(id) => openGame(id)", created["body"]["game_id"])
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    settled(page)
    for language in ("ko", "en"):
        page.evaluate(f"setLanguage('{language}')")
        settled(page)
        names = page.evaluate(NAMES_JS, ["arrakeen", "carthag"])
        kwisatz = page.evaluate(ROWS_JS, [KWISATZ_ROWS, "earl_memnon_thorvald"])
        wrong = [
            row
            for row in kwisatz
            if len(row["shown"]) != 1
            or not all(word in row["shown"][0] for word in row["words"])
            or names["spaces"]["arrakeen"] not in row["shown"][0]
            or "{" in row["shown"][0]
        ]
        conflict, carthag = (row["shown"][0] if row["shown"] else "" for row in kwisatz)
        check.ok(
            not wrong
            and names["conflict"] in conflict
            and "conflict" not in conflict.replace(names["conflict"], "")
            and names["spaces"]["carthag"] in carthag,
            f"[{language}] Kwisatz Haderach's rows name where the Agent comes from:"
            f" the Conflict ({names['conflict']}) or a board space",
            (wrong[:2], conflict, carthag),
        )
        connections = page.evaluate(ROWS_JS, [CONNECTIONS_ROWS, "earl_memnon_thorvald"])
        wrong = [
            row
            for row in connections
            if len(row["shown"]) != 1
            or not all(word in row["shown"][0] for word in row["words"])
            or names["factions"][row["args"]["faction"]] not in row["shown"][0]
            or names["leader"] not in row["shown"][0]
            or "{" in row["shown"][0]
        ]
        check.ok(
            not wrong,
            f"[{language}] each Connections row names its Faction and, as every"
            " Leader ability's row does, the Leader",
            wrong[:2] or [row["shown"] for row in connections],
        )
        voice = page.evaluate(VOICE_JS, ["arrakeen", 1])
        check.ok(
            voice["title"] is not None
            and voice["want"] in voice["title"]
            and voice["marked"] == 1,
            f"[{language}] The Voice's barred space is named and marked on"
            " Uprising's board",
            voice,
        )
    try:
        page.evaluate("window.localStorage.removeItem('dune.fullActionList')")
    finally:
        page.evaluate("setLanguage('ko')")


def main() -> None:
    with server() as (base, log_path), chrome() as browser:
        setup_box(base, browser)
        _, page, rec = open_context(browser, "imperium-cards")
        page.goto(base + "/")
        page.wait_for_function("state.catalog !== null")
        ai_logs(page)
        play_human(page, rec)
        injected_rows(page)
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
