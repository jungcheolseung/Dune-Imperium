"""The original Dune: Imperium in the play UI (stage P5a of
docs/base-game-and-ix-plan.md, section 18).

The original game is played on the text board until its own board scan and
layout arrive (P5b); its spaces, Conflicts, Leaders and cards come from the
catalog (names and text). This checks that a whole original game reads as
words, the way log_words.py checks Uprising's:

[1] Three finished original games played by AI seats (heuristic seed 7;
    random seeds 1 and 2 with the Leader draft and the promo cards, picked
    2026-10-29 by a scan of seeds 1-12 for the lines below), their logs
    rendered with the page's own functions in both
    languages: prettify() never reached (every id resolves through the
    catalog), the Korean log holds no English outside the catalog's names,
    the English log no Hangul, and neither an engine id's shape. The games
    must reach the original game's own lines (the Mentat taken and won,
    Masterstroke's secret Factions chosen and revealed, Helena's Manipulate
    setting a card aside, a Conflict reward line taken from a "-OR-" or
    "Choose two:" row), or the check says so instead of passing empty.
[2] One human seat against three heuristic AIs, the original game, played
    in the browser to the end with a varied pick (a step-seeded index of
    the legal list, not always the first) in Korean, then in English from
    the middle: every step settles without an error banner, prettify() is
    never called, every id the view names is in the catalog, the board is
    the text board with the original game's 22 spaces, and the standings
    show at the end.
[3] The finished game's review screen in both languages, titles included,
    shows no engine id (log_words.check_page).
[4] The original game's markers (P5c) on a four-human game's first
    decision, its view edited in the browser the way deck_contents.py's
    scenario C does: The Voice's barred space on the seat panel and the
    text board, Infiltrate's turn and Recruitment Mission's round,
    Masterstroke's secret (to the others), its Factions (to the Baron's own
    seat only, from the view's private block) and once revealed, and the
    Mentat lying on its space with the seat that takes it next round; in
    both languages, with no placeholder left.
[5] A four-human original game with the Leader draft (P5e): a seat drafts
    Baron Harkonnen and, before the first round, chooses its two secret
    Factions on screen; the banner asks in Korean with no English left but
    names, the rows name the Factions, the Baron's own panel names the
    Faction already picked while he picks the second, and the server's view
    of every other seat says only that he holds a secret (imperium-base.md
    14), while his own carries both.
Every page: no JS errors; the server logs no Traceback or ERROR.
"""

from __future__ import annotations

import json
import re

from common import SERVER_LOG_COPY, Check, chrome, client_state, open_context, server
from log_words import (
    RENDER_JS,
    check_log,
    check_page,
)
from log_words import check as log_words_check
from open_mode import settled

check = Check()

ORIGINAL = {"base_game": "imperium"}
DRAFT = {"leader_draft": True, "promo_cards": True}
GAMES = (
    {"seats": ["heuristic"] * 4, "game_seed": 7, **ORIGINAL},
    {"seats": ["random"] * 4, "game_seed": 1, "policy_seed": 1, **DRAFT, **ORIGINAL},
    {"seats": ["random"] * 4, "game_seed": 2, "policy_seed": 2, **DRAFT, **ORIGINAL},
)
# The original game's own log lines the three games must reach.
WANTED = {
    "the Mentat taken": "event mentat_taken",
    "the Mentat won for the next round": "event mentat_won",
    "a secret Masterstroke Faction chosen": "action choose_masterstroke_faction",
    "Masterstroke revealed": "event masterstroke_revealed",
    "a card Manipulate sets aside": "event imperium_row_card_set_aside",
    "a Conflict reward line taken from a choice row": "event combat_reward_line_chosen",
}

HUMAN_SEED = 31
HUMAN_SEATS = ["human", "heuristic", "heuristic", "heuristic"]

# Every id the view names, by the catalog section it must be found in.
MISSING_JS = """() => {
  const view = state.view;
  const want = [];
  const card = (id) => want.push(["cards", instanceRef(id).id, id]);
  for (const player of view.players) {
    if (player.leader_id) want.push(["leaders", player.leader_id, "leader"]);
    for (const space of player.agent_locations || []) {
      want.push(["spaces", space, "agent"]);
    }
    for (const id of [...(player.in_play || []), ...(player.discard_pile || []),
                      ...(player.trashed || [])]) card(id);
  }
  for (const id of view.imperium_row || []) card(id);
  for (const [id] of view.reserve_stacks || []) want.push(["cards", id, "reserve"]);
  for (const id of view.current_conflict_ids || []) {
    want.push(["conflicts", id, "conflict"]);
  }
  for (const entry of view.conflict_history || []) {
    want.push(["conflicts", entry.conflict_id, "history"]);
  }
  if (view.private) {
    for (const id of view.private.hand || []) card(id);
    for (const id of view.private.intrigue_cards || []) {
      want.push(["intrigue", instanceRef(id).id, id]);
    }
  }
  for (const id of view.intrigue_discard || []) {
    want.push(["intrigue", instanceRef(id).id, id]);
  }
  return want.filter(([section, id]) => !(state.catalog[section] || {})[id])
    .map(([section, id, from]) => `${section}:${id} (${from})`);
}"""

PICK_JS = """(step) => {
  const rows = state.actions.actions;
  const picks = rows.filter((row) => row.action_id !== "withdraw_troops");
  const row = (picks.length ? picks : rows)[(step * 7) % (picks.length || rows.length)];
  applyAction(row.index);
}"""

TABLE_JS = """() => ({
  base: state.view.base_game,
  scan: Boolean(document.querySelector("#board .board-stage")),
  spaces: [...document.querySelectorAll("#board .space-row")].map(
    (row) => row.dataset.space),
  // The track counts each seat panel shows on the text board.
  trackStats: [...document.querySelectorAll("#seats article.seat")].map(
    (card) => card.querySelectorAll(".text-board-stats .stat").length),
})"""


def render_logs(page) -> tuple[list[dict], list[str], list[str], list[str]]:
    records: list[dict] = []
    names: set[str] = set()
    posts: list[str] = []
    game_ids: list[str] = []
    for config in GAMES:
        created = page.evaluate(
            """async (body) => {
              const r = await fetch('/games', {method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)});
              return {status: r.status, body: await r.json()};
            }""",
            config,
        )
        label = f"{config['seats'][0]} seed {config['game_seed']}"
        check.ok(
            created["status"] == 200, f"created the original game {label}", created
        )
        if created["status"] != 200:
            continue
        body = created["body"]
        check.ok(
            body["base_game"] == "imperium" and body["finished"],
            f"{label}: an original game the AI seats finish",
            {key: body.get(key) for key in ("base_game", "finished", "round_number")},
        )
        game_ids.append(body["game_id"])
        result = page.evaluate(RENDER_JS, {"gameId": body["game_id"]})
        records.extend(result["out"])
        names.update(result["names"])
        posts = result["posts"]
    return records, sorted(names, key=len, reverse=True), posts, game_ids


def check_coverage(records: list[dict]) -> None:
    sources = {record["src"] for record in records}
    for label, source in WANTED.items():
        check.ok(source in sources, f"the games reach {label}", source)


def play_human(page, rec) -> None:
    print("[2] one human seat against three heuristic AIs, played in the browser")
    page.evaluate("setLanguage('ko')")
    created = page.evaluate(
        """async (body) => {
          const r = await fetch('/games', {method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)});
          return await r.json();
        }""",
        {"seats": HUMAN_SEATS, "game_seed": HUMAN_SEED, **ORIGINAL},
    )
    page.evaluate("(id) => openGame(id)", created["game_id"])
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
    table = page.evaluate(TABLE_JS)
    check.ok(
        table["base"] == "imperium" and not table["scan"]
        and len(table["spaces"]) == 22 and "carthag" in table["spaces"],
        "the text board lists the original game's 22 spaces",
        table,
    )
    check.ok(
        table["trackStats"] == [7, 7, 7, 7],
        "each seat shows its Influence, troops and strength on the text board",
        table["trackStats"],
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
        if not switched and steps == 120:
            page.evaluate("setLanguage('en')")
            page.wait_for_function("refreshFlight === null")
            switched = True
        if snap["confirmation"] is not None:
            page.evaluate("confirmTurn()")
        else:
            # A varied pick, so the game reaches the original game's choices
            # beyond the first row; never a troop withdrawal, which only
            # undoes a deployment (picking both in turn never ends the turn).
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
    check.ok(
        final["finished"], "the original game reaches its end in the browser", final
    )
    check.ok(switched, "the language switched halfway", steps)
    check.ok(
        not missing, "every id the view names is in the catalog", sorted(missing)[:6]
    )
    calls = page.evaluate("window.prettifyCalls")
    check.ok(
        not calls, "prettify() is never called while playing", sorted(set(calls))[:6]
    )
    check.ok(
        page.evaluate("Boolean(document.querySelector('#standings, .standings'))")
        or "standings" in page.evaluate("JSON.stringify(state.summary)"),
        "the finished game shows its standings",
    )
    check.ok(not rec.js_errors, "no page errors while playing", rec.js_errors[:3])
    page.evaluate("setLanguage('ko')")


# The markers' view: seat 1 barred from Carthag by The Voice and under
# Infiltrate and Recruitment Mission; seat 2 holding a Masterstroke secret;
# seat 3's revealed Factions; the observing seat's own secret Factions; the
# Mentat on its space, owed to seat 1 next round.
MARKERS_JS = """() => {
  window.__markersReal = state.view;
  const view = structuredClone(state.view);
  for (const player of view.players) {
    player.mentat = false;
    player.voice_blocked_space_ids = [];
    player.enemy_agents_ignored_turn = false;
    player.acquire_to_deck_top_round = false;
    player.masterstroke_secret = false;
    player.masterstroke_revealed_factions = [];
  }
  const me = view.player;
  const other = (n) => (me + n) % 4;
  view.players[other(1)].voice_blocked_space_ids = ["carthag"];
  view.players[other(1)].enemy_agents_ignored_turn = true;
  view.players[other(1)].acquire_to_deck_top_round = true;
  view.players[other(2)].masterstroke_secret = true;
  view.players[other(3)].masterstroke_revealed_factions = ["emperor", "fremen"];
  view.players[me].masterstroke_secret = true;
  view.private.masterstroke_factions = ["bene_gesserit", "spacing_guild"];
  view.mentat_owed_to = other(1);
  state.view = view;
  render();
  const panel = (seat) => {
    const card = document.querySelector(`article.seat[data-seat="${seat}"]`);
    const detail = card && card.querySelector('.seat-detail');
    return detail ? detail.innerText : '';
  };
  const row = (space) => {
    const node = document.querySelector(`#board .space-row[data-space="${space}"]`);
    return node ? node.innerText : '';
  };
  const out = {
    me, other1: other(1),
    panels: [0, 1, 2, 3].map(panel),
    mentatRow: row("mentat"), carthagRow: row("carthag"),
    names: {
      voice: lookup("the_voice", "cards").name,
      infiltrate: lookup("infiltrate", "intrigue").name,
      recruitment: lookup("recruitment_mission", "intrigue").name,
      seat1: t("common.seat", {seat: other(1)}),
      carthag: spaceName("carthag"),
      masterstroke: t("panels.masterstroke_name"),
      mentatHere: t("board.mentat_here"),
      emperor: FACTION_LABELS.emperor, fremen: FACTION_LABELS.fremen,
      bg: FACTION_LABELS.bene_gesserit, guild: FACTION_LABELS.spacing_guild,
    },
  };
  state.view = window.__markersReal;
  render();
  return out;
}"""

PLACEHOLDER = re.compile(r"\{[a-z_]+(?::\d+)?\}|\[object|undefined")


def check_markers(page) -> None:
    print("[4] the original game's markers on the seat panels and the text board")
    created = page.evaluate(
        """async (body) => {
          const r = await fetch('/games', {method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)});
          return await r.json();
        }""",
        {"seats": ["human"] * 4, "game_seed": HUMAN_SEED, **ORIGINAL},
    )
    page.evaluate("(id) => openGame(id)", created["game_id"])
    page.wait_for_function(
        "state.view !== null && refreshFlight === null"
        f" && state.gameId === {json.dumps(created['game_id'])}"
    )
    settled(page)
    for lang in ("ko", "en"):
        page.evaluate(f"setLanguage('{lang}')")
        page.wait_for_function("refreshFlight === null")
        shown = page.evaluate(MARKERS_JS)
        names = shown["names"]
        me, other1 = shown["me"], shown["other1"]
        panels = shown["panels"]
        barred = panels[other1]
        check.ok(
            names["voice"] in barred and names["carthag"] in barred
            and names["infiltrate"] in barred and names["recruitment"] in barred,
            f"{lang}: The Voice, Infiltrate and Recruitment Mission on their seat",
            barred,
        )
        mine = panels[me]
        check.ok(
            names["bg"] in mine and names["guild"] in mine,
            f"{lang}: the Baron's own seat names its secret Factions",
            mine,
        )
        secret = panels[(me + 2) % 4]
        check.ok(
            names["masterstroke"] in secret and names["bg"] not in secret
            and names["guild"] not in secret,
            f"{lang}: another Baron's secret shows as held, never which",
            secret,
        )
        revealed = panels[(me + 3) % 4]
        check.ok(
            names["emperor"] in revealed and names["fremen"] in revealed,
            f"{lang}: revealed Factions are named",
            revealed,
        )
        check.ok(
            names["seat1"] in shown["mentatRow"]
            and names["mentatHere"] in shown["mentatRow"],
            f"{lang}: the Mentat on its space, owed to the next round's seat",
            shown["mentatRow"],
        )
        check.ok(
            names["voice"] in shown["carthagRow"]
            and names["seat1"] in shown["carthagRow"],
            f"{lang}: the text board marks the space The Voice bars",
            shown["carthagRow"],
        )
        leaks = [
            text for text in (*panels, shown["mentatRow"], shown["carthagRow"])
            if PLACEHOLDER.search(text)
        ]
        check.ok(not leaks, f"{lang}: no placeholder left in the markers", leaks[:2])
    page.evaluate("setLanguage('ko')")


# Seat rows the browser offers now: (index, action id, leader id, faction).
ROWS_JS = """() => (state.actions ? state.actions.actions : []).map((row) => [
  row.index, row.action_id, (row.arguments || {}).leader_id || null,
  (row.arguments || {}).faction || null])"""

BANNER_JS = """() => ({
  prompt: (document.querySelector('#decision-info .prompt') || {}).textContent || '',
  rows: document.getElementById('actions').innerText,
  kind: state.summary.decision ? state.summary.decision.kind : null,
  owner: state.summary.decision ? state.summary.decision.owner : null,
  emperor: FACTION_LABELS.emperor, fremen: FACTION_LABELS.fremen,
})"""

OWN_PANEL_JS = """(seat) => {
  const card = document.querySelector(`article.seat[data-seat="${seat}"]`);
  const detail = card && card.querySelector('.seat-detail');
  return {text: detail ? detail.innerText : '', viewer: state.view.player};
}"""

SEAT_VIEW_JS = (
    "async ([id, seat]) => (await fetch(`/games/${id}/seats/${seat}/view`)).json()"
)

LATIN_WORD = re.compile(r"[A-Za-z]{3,}")


def check_masterstroke_pick(page) -> None:
    print("[5] a human Baron Harkonnen drafts and chooses his secret Factions")
    page.evaluate("setLanguage('ko')")
    created = page.evaluate(
        """async (body) => {
          const r = await fetch('/games', {method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)});
          return await r.json();
        }""",
        {"seats": ["human"] * 4, "game_seed": 3, "leader_draft": True, **ORIGINAL},
    )
    game_id = created["game_id"]
    page.evaluate("(id) => openGame(id)", game_id)
    page.wait_for_function(
        "state.view !== null && refreshFlight === null"
        f" && state.gameId === {json.dumps(game_id)}"
    )
    settled(page)
    baron = None
    for _ in range(80):
        snap = client_state(page)
        if snap["kind"] == "masterstroke_setup" or snap["finished"]:
            break
        if snap["confirmation"] is not None:
            page.evaluate("confirmTurn()")
        else:
            rows = page.evaluate(ROWS_JS)
            pick = next(
                (row for row in rows if row[2] == "baron_vladimir_harkonnen"), rows[0]
            )
            if pick[2] == "baron_vladimir_harkonnen":
                baron = snap["owner"]
            page.evaluate(f"applyAction({pick[0]})")
        settled(page, 20)
    banner = page.evaluate(BANNER_JS)
    check.ok(
        baron is not None
        and banner["kind"] == "masterstroke_setup"
        and banner["owner"] == baron,
        "the seat that drafted the Baron chooses its secret Factions first",
        (baron, banner["kind"], banner["owner"]),
    )
    abilities = page.evaluate(
        "Object.values(state.catalog.leaders).map((l) => l.ability || '')"
    )
    stray = [
        word
        for word in LATIN_WORD.findall(banner["prompt"])
        if not any(word in ability for ability in abilities)
    ]
    check.ok(
        bool(banner["prompt"]) and not stray,
        "ko: the banner asks for the secret Factions in Korean",
        banner["prompt"],
    )
    check.ok(
        banner["emperor"] in banner["rows"] and banner["fremen"] in banner["rows"],
        "ko: the rows name the Factions",
        banner["rows"][:200],
    )
    for number, faction in enumerate(("emperor", "fremen")):
        rows = page.evaluate(ROWS_JS)
        row = next(row for row in rows if row[3] == faction)
        page.evaluate(f"applyAction({row[0]})")
        settled(page, 20)
        if number == 0:
            own = page.evaluate(OWN_PANEL_JS, baron)
            check.ok(
                own["viewer"] == baron and banner["emperor"] in own["text"],
                "the Baron's own panel names the Faction he picked",
                own,
            )
        if client_state(page)["confirmation"] is not None:
            page.evaluate("confirmTurn()")
            settled(page, 20)
    mine = page.evaluate(SEAT_VIEW_JS, [game_id, baron])
    check.ok(
        sorted((mine.get("private") or {}).get("masterstroke_factions") or [])
        == ["emperor", "fremen"],
        "the Baron's own view carries both secret Factions",
        (mine.get("private") or {}).get("masterstroke_factions"),
    )
    leaks = []
    for seat in range(4):
        if seat == baron:
            continue
        view = page.evaluate(SEAT_VIEW_JS, [game_id, seat])
        held = view["players"][baron]
        private = view.get("private") or {}
        if (
            not held.get("masterstroke_secret")
            or held.get("masterstroke_revealed_factions")
            or private.get("masterstroke_factions")
        ):
            leaks.append((seat, held.get("masterstroke_secret"), private))
    check.ok(
        not leaks,
        "every other seat's view says only that the Baron holds a secret",
        leaks,
    )


def main() -> None:
    with server() as (base, log_path), chrome() as browser:
        _, page, rec = open_context(browser, "imperium-game")
        page.goto(base + "/")
        page.wait_for_function("state.catalog !== null")
        print(f"[1] the logs of {len(GAMES)} finished original games, both languages")
        records, names, posts, game_ids = render_logs(page)
        print(f"  .. {len(records)} rendered lines")
        check_coverage(records)
        check_log(records, names, posts)
        play_human(page, rec)
        print("[3] the whole screen at the end of the first game's review")
        if game_ids:
            check_page(page, base, game_ids[0], posts, names)
        check_markers(page)
        check_masterstroke_pick(page)
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
