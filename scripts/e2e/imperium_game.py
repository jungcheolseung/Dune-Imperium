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
Every page: no JS errors; the server logs no Traceback or ERROR.
"""

from __future__ import annotations

import json

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
