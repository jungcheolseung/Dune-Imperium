"""Arrakeen Scouts on the original game in the play UI (stage P8e of
docs/base-game-and-ix-plan.md, 20.6; the pools in
docs/rules/arrakeen-scouts.md 9a).

[1] Seven finished AI games on the original game's four schedules (alone,
    with Immortality, with Rise of Ix, with both and Bloodlines; heuristic
    seeds picked 2026-10-31 by a scan of seeds 1-8 each for the original
    items they reveal), their logs rendered with the page's own functions in
    both languages (log_words.check_log). Between them they reach the
    original items' events: a Mentat auction and a sealed Treachery won, a
    Covert Operation pick revealed with the Faction it named (the line says
    which, in both languages), an Intrigue card discarded, troops parked by
    a mission, a Sapho Juice marker taken back, a unit lost.
[2] Every original mission's pieces for four seats put in the page's view of
    a four-human original table and an original + Rise of Ix one: one piece
    per row, each inside a region of its own location on the shown board
    (the original board's tracks.scouts, with Rise of Ix the overlay's for
    the Mentat and Smuggling and the Ix board's for Dreadnought), its title
    naming the mission with no placeholder, in both languages.
[3] Real engine/server payloads (GameSessionManager in a subprocess):
    (d) the original items' own decisions, the item's tasks run until seat 0
        decides: Rotating Doors' and Intriguing Gift's Intrigue discard and,
        the line taken, the Intrigue card to discard; Stationed Support's
        join and the hand card it discards; Fremen Exchange's choice and the
        unit window its troop line opens (OQ-163); No Coming Back's starter
        cards -- the header names the item and the rows read apart, with no
        placeholder, in each language;
    (a) the original Covert Operation after seat 0 picked a line naming a
        Faction: seat 0's Scouts panel names the Faction beside its pick;
        seat 1's view carries no Faction and no pick of seat 0's, and its
        panel only says seat 0 has picked;
    (b) Secrets in the Desert's two face-down Intrigue cards on Research
        Station: the board's pile and the Scouts panel count two, and no
        seat's view names either card;
    (c) on an original + Immortality table the auction Treachery and the
        event Betrayal, both 배반 in the app's Korean, read with their kind
        beside the name; in English, and on an original table without
        Immortality (no Betrayal), the name alone.
[4] One human seat against three heuristic AIs on an original + Immortality
    + Arrakeen Scouts game, played in the browser to the end with a varied
    pick, Korean then English: every step settles without an error banner,
    every id the view names is in the catalog, prettify() is never called.
Every page: no JS errors; the server logs no Traceback or ERROR.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from common import (
    REPO,
    SERVER_LOG_COPY,
    Check,
    chrome,
    client_state,
    open_context,
    server,
)
from imperium_game import MISSING_JS, PICK_JS
from log_words import RENDER_JS, check_log
from log_words import check as log_words_check
from open_mode import settled

check = Check()
SHOTS = Path(
    os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(prefix="dune-imperium-scouts-")
)

ORIGINAL = {"base_game": "imperium", "arrakeen_scouts": True}
HANGUL = re.compile(r"[가-힣]")
GAMES = (
    {"seed": 7},
    {"seed": 3},
    {"seed": 6, "immortality": True},
    {"seed": 2, "immortality": True},
    {"seed": 4, "rise_of_ix": True},
    {"seed": 1, "rise_of_ix": True},
    {"seed": 4, "rise_of_ix": True, "immortality": True, "bloodlines": True},
)
WANTED = {
    "an auction won": "event scouts_auction_won",
    "a Covert Operation pick revealed": "event scouts_secret_revealed",
    "an Intrigue card discarded": "event intrigue_card_discarded",
    "troops parked by a mission": "event scouts_mission_troops_parked",
    "a Sapho Juice marker taken back": "event scouts_sapho_marker_taken",
    "a unit lost": "event unit_lost",
}
FACTION_WORDS = {
    "ko": ("황제", "우주 항행 길드", "베네 게세리트", "프레멘"),
    "en": ("Emperor", "Spacing Guild", "Bene Gesserit", "Fremen"),
}

POST_JS = """async (body) => {
  const r = await fetch('/games', {method: 'POST',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  return {status: r.status, body: await r.json()};
}"""


def ai_logs(page) -> None:
    print(f"[1] the logs of {len(GAMES)} finished original Scouts AI games")
    records: list[dict] = []
    names: set[str] = set()
    posts: list[str] = []
    for game in GAMES:
        options = {key: value for key, value in game.items() if key != "seed"}
        config = {
            "seats": ["heuristic"] * 4,
            "game_seed": game["seed"],
            "policy_seed": game["seed"],
            **ORIGINAL,
            **options,
        }
        created = page.evaluate(POST_JS, config)
        label = f"seed {game['seed']} {sorted(options)}"
        body = created["body"]
        check.ok(
            created["status"] == 200
            and body["finished"]
            and body["arrakeen_scouts"]
            and body.get("base_game") == "imperium",
            f"{label}: a finished original game with Arrakeen Scouts",
            {key: body.get(key) for key in ("finished", "base_game", "detail")},
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
    for language, words in FACTION_WORDS.items():
        revealed = [
            record["text"]
            for record in records
            if record["src"] == "event scouts_secret_revealed"
            and record["lang"] == language
        ]
        named = [text for text in revealed if any(word in text for word in words)]
        check.ok(
            named,
            f"[{language}] a revealed Covert Operation pick names its Faction",
            revealed[:4],
        )
    check_log(records, sorted(names, key=len, reverse=True), posts)


FILL_JS = """(ix) => {
  const seats = [0, 1, 2, 3];
  const goods = [
    ["space_travel_deal", "imperium_heighliner", "solari", 3, -1],
    ...seats.flatMap((s) => [
      ["sapho_juice", "mentat", "marker", 1, s],
      ["sapho_juice", "mentat", "spice", 1, s],
      ["genetic_research", "selective_breeding", "solari", 2, s],
      ["imperium_coordinate_with_the_emperor", "conspire", "solari", 2, s],
    ]),
  ];
  // Genetic Research: seats 0 and 1 moved a garrison troop, seats 2 and 3 a
  // garrison Sardaukar Commander in its place (Bloodlines, OQ-166).
  const parked = seats.flatMap((s) => [
    ...(s < 2 ? [["genetic_research", s, "selective_breeding", 1]] : []),
    ["botanical_stationed_support", s, "imperium_research_station", 2],
    ["imperium_coordinate_with_the_emperor", s, "conspire", 1],
  ]);
  const commanders = [2, 3].map((s) => ["genetic_research", s, "selective_breeding"]);
  if (ix) {
    goods.push(["secret_stash", "smuggling", "spice", 2, -1]);
    seats.forEach((s) => {
      goods.push(["armed_escort", "dreadnought", "spice", 1, s]);
      parked.push(["armed_escort", s, "dreadnought", 1]);
      parked.push(["stowaways", s, "smuggling", 2]);
    });
  } else {
    goods.push(["muster_spice_incentive", "rally_troops", "spice", 2, -1]);
    seats.forEach((s) => {
      parked.push(["muster_strongarmed_alliance", s, "rally_troops", 1]);
      parked.push(["guild_maneuvers", s, "foldspace", 2]);
    });
  }
  state.view.scouts_goods = goods;
  state.view.scouts_parked = parked;
  state.view.scouts_parked_commanders = commanders;
  state.view.scouts_board_card_counts = [
    ["botanical_secrets_in_the_desert", "imperium_research_station", 2]];
  render();
  const layout = boardLayout();
  const scouts = layout.tracks.scouts;
  const regions = {...scouts.regions, ...(layout.scoutsRegions || {})};
  const ixRegions = (layout.ixBoard && layout.ixBoard.scouts_regions) || {};
  const rows = goods.length + parked.length + commanders.length + 1;
  const pieces = [...document.querySelectorAll("#board .scouts-piece")].map((n) => {
    const ix = Boolean(n.closest(".ix-stage"));
    const stage = n.closest(".board-stage").getBoundingClientRect();
    const r = n.getBoundingClientRect();
    const box = [100 * (r.left - stage.left) / stage.width,
                 100 * (r.top - stage.top) / stage.height,
                 100 * r.width / stage.width, 100 * r.height / stage.height];
    const own = (ix ? ixRegions : regions)[n.dataset.location] || [];
    const inside = own.some(({box: [l, t, w, h]}) =>
      box[0] >= l - 0.05 && box[1] >= t - 0.05
      && box[0] + box[2] <= l + w + 0.05 && box[1] + box[3] <= t + h + 0.05);
    return {location: n.dataset.location, mission: n.dataset.mission,
            kind: n.dataset.kind, ix, inside, title: n.title};
  });
  return {rows, pieces};
}"""


def open_table(page, body: dict) -> None:
    created = page.evaluate(POST_JS, body)
    page.evaluate("(id) => openGame(id)", created["body"]["game_id"])
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    settled(page)


def check_pieces(page) -> None:
    print("[2] every original mission's pieces on the original board")
    for ix in (False, True):
        board = "original + Rise of Ix" if ix else "original"
        open_table(
            page,
            {
                "seats": ["human"] * 4,
                "game_seed": 3,
                **ORIGINAL,
                "immortality": True,
                "bloodlines": True,
                **({"rise_of_ix": True} if ix else {}),
            },
        )
        for language in ("ko", "en"):
            page.evaluate(f"setLanguage('{language}')")
            settled(page)
            shown = page.evaluate(FILL_JS, ix)
            pieces = shown["pieces"]
            outside = [p for p in pieces if not p["inside"]]
            bad_titles = [
                p["title"] for p in pieces if not p["title"] or "{" in p["title"]
            ]
            locations = {p["location"] for p in pieces}
            want = {
                "imperium_heighliner",
                "mentat",
                "selective_breeding",
                "conspire",
                "imperium_research_station",
                *(
                    ("smuggling", "dreadnought")
                    if ix
                    else ("rally_troops", "foldspace")
                ),
            }
            check.ok(
                len(pieces) == shown["rows"]
                and locations == want
                and not outside
                and not bad_titles
                and all(p["ix"] == (p["location"] == "dreadnought") for p in pieces)
                # The two parked Commanders (OQ-166) at Selective Breeding.
                and [p["location"] for p in pieces if p["kind"] == "commander"]
                == ["selective_breeding"] * 2,
                f"[{board}, {language}] a piece per row, each in a region of its own"
                " location on the shown board",
                {
                    "outside": outside[:4],
                    "titles": bad_titles[:3],
                    "locations": sorted(locations),
                    "count": len(pieces),
                },
            )
        page.locator("#board").screenshot(
            path=str(SHOTS / f"imperium_scouts_pieces{'_ix' if ix else ''}.png")
        )
    page.evaluate("setLanguage('ko')")


FIXTURES = r"""
import json
from dataclasses import replace
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.content.arrakeen_scouts import EVENTS_BY_ID, MISSIONS_BY_ID
from dune_imperium.core import DomainAction, Resources
from dune_imperium.rules.scouts import _item_tasks, advance_scouts_step
from dune_imperium.server.sessions import GameSessionManager

manager = GameSessionManager()

def table(**options):
    summary = manager.create_game(("human",) * 4, game_seed=21, base_game="imperium",
                                  arrakeen_scouts=True, **options)
    game_id = str(summary["game_id"])
    for _ in range(12):
        if summary["phase"] == "player_turns":
            break
        seat = summary["decision"]["owner"]
        listed = manager.legal_actions(game_id, seat)
        summary = manager.apply_action(game_id, seat, summary["revision"],
            listed["actions"][0]["index"], undo_count=summary["undo_count"])
        if summary["confirmation"] is not None:
            summary = manager.confirm_turn(game_id, summary["confirmation"],
                summary["revision"], undo_count=summary["undo_count"])
    return game_id

def snapshot(game_id, state, seat):
    manager._get(game_id).state = state
    return {"summary": manager.summary(game_id), "view": manager.view(game_id, seat),
            "actions": manager.legal_actions(game_id, seat)}

game = table(immortality=True)
session = manager._get(game)
turn = session.state

# (a) The original Covert Operation, seat 0's line naming a Faction.
item = "imperium_covert_operation"
round_number = EVENTS_BY_ID[item].rounds[0]
state = replace(turn, round_number=round_number, first_player=0, decision_stack=(),
                scouts_opening=True, scouts_item=item,
                scouts_revealed=((round_number, item),), scouts_tasks=())
state = replace(state, scouts_tasks=_item_tasks(state, item))
while not state.decision_stack:
    state = advance_scouts_step(state).state
session.state = state
rows = manager.legal_actions(game, 0)["actions"]
named = next(row for row in rows if "faction" in row["arguments"])
arguments = tuple(sorted(named["arguments"].items()))
action = DomainAction("scouts_secret_pick", 0, arguments)
picked = apply_whole(session.engine, state, action).state

# (b) Secrets in the Desert's two face-down cards on Research Station.
cards = turn.intrigue_deck[:2]
mission = "botanical_secrets_in_the_desert"
desert = replace(turn, intrigue_deck=turn.intrigue_deck[2:],
                 scouts_goods_cards=tuple((mission, "imperium_research_station", card)
                                          for card in cards))

# (d) The original items' own decisions, each seat holding resources and two
# Intrigue cards: their first rows, and the window a first line opens.
def rich(state):
    deck = state.intrigue_deck
    players = tuple(
        replace(p, resources=Resources(solari=9, spice=9, water=9),
                intrigue_cards=deck[2 * p.player_id: 2 * p.player_id + 2])
        for p in state.players)
    return replace(state, players=players, intrigue_deck=deck[8:])

def step(item):
    entry = EVENTS_BY_ID.get(item) or MISSIONS_BY_ID[item]
    round_number = entry.rounds[0]
    state = replace(rich(turn), round_number=round_number, first_player=0,
                    decision_stack=(), scouts_opening=True, scouts_item=item,
                    scouts_revealed=((round_number, item),), scouts_tasks=())
    state = replace(state, scouts_tasks=_item_tasks(state, item))
    while not state.decision_stack:
        state = advance_scouts_step(state).state
    return state

scenes = {}
for item in ("imperium_rotating_doors", "intriguing_gift",
             "botanical_stationed_support", "fremen_exchange", "no_coming_back"):
    state = step(item)
    scenes[item] = snapshot(game, state, 0)
    if item in ("fremen_exchange", "imperium_rotating_doors",
                "botanical_stationed_support"):
        # The first line that is not a pass, sent as the page sends it: the
        # card or unit to give up is the seat's next step.
        session.state = state
        summary = manager.summary(game)
        rows = manager.legal_actions(game, 0)["actions"]
        line = next(row for row in rows if row["action_id"] not in (
            "scouts_pass", "scouts_decline_mission"))
        manager.apply_action(game, 0, summary["revision"], line["index"],
                             undo_count=summary["undo_count"])
        scenes[item + "_unit"] = snapshot(game, session.state, 0)

fixtures = {
    "scenes": scenes,
    "covert": {"faction": named["arguments"]["faction"],
               "pick": named["arguments"]["pick"],
               "own": snapshot(game, picked, 0),
               "other": snapshot(game, picked, 1)},
    "desert": {"cards": list(cards),
               "seats": [snapshot(game, desert, seat) for seat in range(4)]},
    "names": {"immortality": snapshot(game, turn, 0)},
}
plain = table()
fixtures["names"]["plain"] = snapshot(plain, manager._get(plain).state, 0)
print(json.dumps(fixtures))
"""

RENDER = """({fixture, seat, language}) => {
    setLanguage(language, false);
    Object.assign(state, fixture, {viewSeat: seat, me: {seats: [0, 1, 2, 3]},
        gameId: fixture.summary.game_id, review: null, busy: false,
        pick: null, held: null, counts: {}, log: {entries: []}});
    window.applyAction = () => {};
    showScreen('game-screen');
    render();
}"""

# The decision panel: the Scouts item it names and its rows as shown (the
# turn-end row's button too).
SCENE_JS = """() => {
  const info = el('decision-info');
  const header = info.querySelector('.scouts-decision-item');
  const rows = [...document.querySelectorAll('#actions .action-item, '
    + '#actions .count-row, #decision-banner .turn-end-row button')]
    .map((n) => n.innerHTML.replace(/<[^>]*alt="([^"]*)"[^>]*>/g, ' $1 ')
      .replace(/<[^>]+>/g, '').replace(/\\s+/g, ' ').trim());
  return {item: header ? header.dataset.item : null, rows, info: info.innerText};
}"""

PANEL_JS = """() => {
  const panel = el('scouts-panel');
  const own = [...panel.querySelectorAll('.scouts-own')].map((n) => n.innerText);
  return {text: panel.innerText, own,
          factions: [...document.querySelectorAll('.scouts-pick-faction')].map(
            (n) => n.dataset.faction)};
}"""


def check_payloads(page) -> None:
    print("[3] real payloads: the Covert Operation's Faction, Secrets in the Desert")
    result = subprocess.run(
        [str(REPO / ".venv/bin/python"), "-c", FIXTURES],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=True,
    )
    fixtures = json.loads(result.stdout)
    covert = fixtures["covert"]
    faction = covert["faction"]
    other_private = covert["other"]["view"]["private"]
    check.ok(
        not other_private.get("scouts_secret_factions")
        and not other_private.get("scouts_secret_picks")
        and faction not in json.dumps(covert["other"]["view"]["scouts_secret_pending"])
        and any(
            row[2] == 0 for row in covert["other"]["view"]["scouts_secret_pending"]
        ),
        "seat 1's view says seat 0 picked, with neither its line nor its Faction",
        {
            "private": {
                k: other_private.get(k)
                for k in ("scouts_secret_factions", "scouts_secret_picks")
            },
            "pending": covert["other"]["view"]["scouts_secret_pending"],
        },
    )
    for language in ("ko", "en"):
        words = dict(
            zip(
                ("emperor", "spacing_guild", "bene_gesserit", "fremen"),
                FACTION_WORDS[language],
                strict=True,
            )
        )
        page.evaluate(
            RENDER, {"fixture": covert["own"], "seat": 0, "language": language}
        )
        own = page.evaluate(PANEL_JS)
        check.ok(
            own["factions"] == [faction]
            and words[faction] in own["text"]
            and own["own"]
            and "{" not in own["text"],
            f"[{language}] seat 0's own pick names the Faction it named",
            own["own"],
        )
        page.evaluate(
            RENDER, {"fixture": covert["other"], "seat": 1, "language": language}
        )
        other = page.evaluate(PANEL_JS)
        player = {"ko": "플레이어1", "en": "Player 1"}[language]
        check.ok(
            not other["factions"] and not other["own"] and player in other["text"],
            f"[{language}] seat 1's panel only says seat 0 has picked",
            other["text"][-300:],
        )
    desert = fixtures["desert"]
    for seat, snapshot in enumerate(desert["seats"]):
        dumped = json.dumps(snapshot["view"])
        check.ok(
            not any(card in dumped for card in desert["cards"]),
            f"seat {seat}'s view names neither face-down card",
        )
    for language in ("ko", "en"):
        page.evaluate(
            RENDER, {"fixture": desert["seats"][0], "seat": 0, "language": language}
        )
        pile = page.evaluate("""() => {
          const node = document.querySelector(
            '#board .scouts-piece[data-location="imperium_research_station"]');
          return node ? {kind: node.dataset.kind, text: node.innerText,
                         title: node.title} : null;
        }""")
        panel = page.evaluate(PANEL_JS)["text"]
        face_down = {"ko": "뒷면 카드 2장", "en": "2 face-down cards"}[language]
        check.ok(
            pile is not None
            and pile["kind"] == "intrigue"
            and "2" in pile["text"]
            and face_down in panel,
            f"[{language}] the board's pile and the panel count two face-down cards",
            {"pile": pile, "panel": panel[-200:]},
        )
    for name, scene in fixtures["scenes"].items():
        item = name.removesuffix("_unit")
        for language in ("ko", "en"):
            page.evaluate(RENDER, {"fixture": scene, "seat": 0, "language": language})
            shown = page.evaluate(SCENE_JS)
            texts = [*shown["rows"], shown["info"]]
            hangul = any(HANGUL.search(text) for text in texts)
            check.ok(
                shown["item"] == item
                and shown["rows"]
                # Two copies of one hand card read the same, and either is
                # the same discard.
                and (
                    name == "botanical_stationed_support_unit"
                    or len(set(shown["rows"])) == len(shown["rows"])
                )
                and not any("{" in text for text in texts)
                and (hangul if language == "ko" else not hangul),
                f"[{language}] {name}: the decision names its item and offers"
                " distinct rows in the page's language",
                shown,
            )
    names = fixtures["names"]
    for language, want in (
        ("ko", ("배반 (경매)", "배반 (이벤트)", "배반")),
        ("en", ("Treachery", "Betrayal", "Treachery")),
    ):
        page.evaluate(
            RENDER, {"fixture": names["immortality"], "seat": 0, "language": language}
        )
        mixed = page.evaluate(
            "() => [scoutsItem('treachery_mid').name, scoutsItem('betrayal').name,"
            " scoutsItem('mentat_mid').name]"
        )
        page.evaluate(
            RENDER, {"fixture": names["plain"], "seat": 0, "language": language}
        )
        plain = page.evaluate("() => scoutsItem('treachery_late').name")
        check.ok(
            mixed[:2] == list(want[:2]) and plain == want[2] and "(" not in mixed[2],
            f"[{language}] Treachery and Betrayal told apart on an original +"
            " Immortality table only",
            {"mixed": mixed, "plain": plain},
        )


def play_human(browser, base: str) -> None:
    print("[4] one human seat against three heuristic AIs, played in the browser")
    # A page of its own: [3] stands in for the page's applyAction.
    _, page, rec = open_context(browser, "imperium-scouts-human")
    page.goto(base + "/")
    page.wait_for_function("state.catalog !== null")
    open_table(
        page,
        {
            "seats": ["human", "heuristic", "heuristic", "heuristic"],
            "game_seed": 2,
            "policy_seed": 2,
            **ORIGINAL,
            "immortality": True,
        },
    )
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


def main() -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    with server() as (base, log_path), chrome() as browser:
        _, page, rec = open_context(browser, "imperium-scouts")
        page.goto(base + "/")
        page.wait_for_function("state.catalog !== null")
        ai_logs(page)
        check_pieces(page)
        check_payloads(page)
        play_human(browser, base)
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
    print(f"Screenshots: {SHOTS}")
    check.finish()


if __name__ == "__main__":
    main()
