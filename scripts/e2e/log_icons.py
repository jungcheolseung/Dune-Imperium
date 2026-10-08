"""E2E: the action log's pictures (static/log_icons.js, 2026-10-08).

Like the Steam app's Action Log, an event line shows the picture the app's
log uses for that kind of entry on a small dark tile, and a "game" card's
head shows the Round numeral, the Conflict, the Endgame or the winner's
wreath in place of its "⚙" mark. This checks, in both languages:

- known events show the expected picture, named here by hand rather than
  read off the page's table: the Faction's own mark for an Influence gain,
  the app's Influence-down mark for a loss, the Alliance token, the board
  space's Agent icon, the app log's red cross for a trashed card, its bare
  Intrigue glyph for a draw; a kind without a picture, or an event missing
  the field a picture needs, stays text only;
- a picture never changes what a line says: its textContent equals the same
  line rendered with the log pictures turned off (an image's alt text is no
  part of textContent), and the words keep the event line's muted opacity
  while the picture stays at full strength on the app's navy tile, on the
  light page and on the dark game table alike;
- an icon line's words start in the same column as a line without one;
- a "game" card shows the Round numeral (1-10), the winner's wreath at the
  game's end, and keeps "⚙" past Round 10 and for the Leader-draft setup;
- a finished game's log panel (heuristic seed 7, every expansion) shows
  loaded pictures, Round numerals that match their cards' titles, and the
  same text with and without them;
- a machine without the pictures renders exactly today's log: with the
  catalog's picture tables empty the panel's HTML equals the one rendered
  with the hook switched off.

The pictures come from the private assets checkout
(scripts/dwgr/app_log_icons.py); without them the picture checks are
skipped and only the fallback is checked. Screenshots go to E2E_SHOTS_DIR.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from common import (
    RULE_OPTIONS,
    SERVER_LOG_COPY,
    Check,
    chrome,
    open_context,
    server,
    set_rule_options,
)

check = Check()
SHOTS = Path(
    os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(prefix="dune-log-icons-")
)
VIEWPORT = {"width": 1440, "height": 900}
NAVY = "rgb(16, 22, 30)"

# (event, (catalog table, picture name) or None for a text-only line).
KNOWN = (
    (
        {"kind": "conflict_revealed", "payload": {"round": 3}},
        ("log_icons", "conflict"),
    ),
    (
        {"kind": "troops_deployed", "payload": {"player": 0, "count": 2}},
        ("log_icons", "troop_deploy"),
    ),
    (
        {"kind": "troops_retreated", "payload": {"player": 0, "count": 1}},
        ("log_icons", "troop_retreat"),
    ),
    (
        {
            "kind": "influence_gained",
            "payload": {"amount": 1, "faction": "fremen", "player": 0},
        },
        ("icons", "influence_fremen"),
    ),
    (
        {
            "kind": "influence_lost",
            "payload": {"amount": 1, "faction": "spacing_guild", "player": 0},
        },
        ("log_icons", "influence_down_spacing_guild"),
    ),
    (
        {
            "kind": "alliance_gained",
            "payload": {"faction": "bene_gesserit", "from_player": -1, "to_player": 0},
        },
        ("alliance_tokens", "bene_gesserit"),
    ),
    (
        {"kind": "agent_placed", "payload": {"player": 0, "space_id": "arrakeen"}},
        ("icons", "agent_icon_city"),
    ),
    (
        {"kind": "agent_placed", "payload": {"player": 0, "space_id": "hagga_basin"}},
        ("icons", "agent_icon_spice_trade"),
    ),
    ({"kind": "card_trashed", "payload": {"player": 0}}, ("log_icons", "card_trashed")),
    (
        {"kind": "intrigue_card_trashed", "payload": {"player": 0}},
        ("log_icons", "card_trashed"),
    ),
    (
        {"kind": "intrigue_card_drawn", "payload": {"player": 0}},
        ("log_icons", "intrigue"),
    ),
    (
        {"kind": "intrigue_played", "payload": {"player": 0}},
        ("log_icons", "intrigue_played"),
    ),
    (
        {"kind": "personal_discard_shuffled", "payload": {"player": 0}},
        ("log_icons", "reshuffle"),
    ),
    ({"kind": "spy_placed", "payload": {"player": 0}}, ("icons", "spy")),
    ({"kind": "cards_drawn", "payload": {"player": 0, "count": 5}}, ("icons", "draw")),
    (
        {"kind": "first_place_influence_pledged", "payload": {"player": 0}},
        ("icons", "influence_any"),
    ),
    ({"kind": "game_finished", "payload": {}}, ("log_icons", "vp_winner")),
    # Text only: a kind without a picture, and an event without its Faction.
    ({"kind": "turn_passed", "payload": {"player": 0}}, None),
    ({"kind": "agent_turn_finished", "payload": {"player": 0}}, None),
    ({"kind": "influence_gained", "payload": {"amount": 1, "player": 0}}, None),
)

PROBE_JS = r"""({events, language, game}) => {
  setLanguage(language, false);
  document.body.classList.toggle('in-game', game);
  document.getElementById('icons-probe')?.remove();
  const host = document.createElement('section');
  host.id = 'icons-probe';
  Object.assign(host.style, {position: 'fixed', left: '12px', top: '12px',
      width: '430px', padding: '10px', background: 'var(--panel)',
      color: 'var(--ink)', zIndex: '9999', fontSize: '0.8rem'});
  const card = document.createElement('div');
  card.className = 'turn-card';
  card.style.borderLeftColor = SEAT_COLORS[0];
  const lines = document.createElement('div');
  lines.className = 'turn-lines';
  const line = document.createElement('div');
  line.className = 'turn-line';
  for (const event of events) line.appendChild(logEventLine(event));
  lines.appendChild(line);
  card.appendChild(lines);
  host.appendChild(card);
  document.body.appendChild(host);
  const rows = [...host.querySelectorAll('.logevent')];
  // The same lines with the log's pictures off: what the line says alone.
  const realUrl = window.logIconUrl;
  window.logIconUrl = () => null;
  const plain = events.map((event) => logEventLine(event).textContent);
  window.logIconUrl = realUrl;
  return rows.map((row, index) => {
    const img = row.querySelector('.log-icon img');
    const words = row.querySelector('.log-text');
    return {
      kind: events[index].kind,
      src: img ? img.getAttribute('src') : null,
      alt: img ? img.alt : null,
      hasIcon: row.classList.contains('has-icon'),
      text: row.textContent,
      plain: plain[index],
      lineOpacity: getComputedStyle(row).opacity,
      wordsOpacity: words ? getComputedStyle(words).opacity : null,
      tile: img ? getComputedStyle(img.parentElement).backgroundColor : null,
      wordsLeft: (words || row).getBoundingClientRect().left,
      tileBox: img ? img.parentElement.getBoundingClientRect().toJSON() : null,
    };
  });
}"""

NEUTRAL_JS = r"""({groups, language}) => {
  setLanguage(language, false);
  document.getElementById('icons-neutral')?.remove();
  const host = document.createElement('section');
  host.id = 'icons-neutral';
  Object.assign(host.style, {position: 'fixed', left: '460px', top: '12px',
      width: '360px', padding: '10px', background: 'var(--panel)',
      color: 'var(--ink)', zIndex: '9999', fontSize: '0.8rem'});
  document.body.appendChild(host);
  const out = [];
  for (const items of groups) {
    // An item is an event, or {chance: entry} for a chance step.
    const group = {kind: 'neutral', firstIndex: 1, lastIndex: 1,
        items: items.map((item) => item.chance
          ? {chance: item.chance} : {event: item, index: 1})};
    const card = neutralCard(group, Infinity);
    host.appendChild(card);
    const mark = card.querySelector('.neutral-mark');
    const img = mark.querySelector('.log-icon img');
    out.push({
      title: card.querySelector('strong').textContent,
      mark: mark.textContent,
      src: img ? img.getAttribute('src') : null,
      markOpacity: getComputedStyle(mark).opacity,
      lefts: [...card.querySelectorAll('.logevent')].map((row) =>
          (row.querySelector('.log-text') || row).getBoundingClientRect().left),
    });
  }
  return out;
}"""

PANEL_JS = r"""() => {
  const panel = document.getElementById('action-log');
  const rows = [...panel.querySelectorAll('.logevent')];
  const imgs = [...panel.querySelectorAll('.log-icon img')];
  const rounds = [...panel.querySelectorAll('.turn-card.neutral')]
    .map((card) => {
      const tile = card.querySelector('.neutral-mark .log-icon');
      return tile && tile.dataset.icon.startsWith('log:round_')
        ? {icon: tile.dataset.icon, title: card.querySelector('strong').textContent}
        : null;
    })
    .filter(Boolean);
  return {
    lines: rows.length,
    iconLines: rows.filter((row) => row.classList.contains('has-icon')).length,
    texts: rows.map((row) => row.textContent),
    broken: imgs.filter((img) => !img.complete || img.naturalWidth === 0)
      .map((img) => img.getAttribute('src')),
    icons: imgs.length,
    rounds,
    html: panel.innerHTML,
  };
}"""

LOADED_JS = """() =>
  [...document.querySelectorAll('#icons-probe img, #icons-neutral img')]
    .every((img) => img.complete && img.naturalWidth > 0)"""


def expected_url(page, where: tuple[str, str] | None) -> str | None:
    if where is None:
        return None
    table, name = where
    return page.evaluate(
        "([table, name]) => (state.catalog[table] || {})[name] || null", [table, name]
    )


def check_known(page, language: str, game: bool) -> None:
    tag = f"{language} {'table' if game else 'page'}"
    events = [event for event, _ in KNOWN]
    rows = page.evaluate(
        PROBE_JS, {"events": events, "language": language, "game": game}
    )
    page.wait_for_function(LOADED_JS)
    for row, (event, where) in zip(rows, KNOWN, strict=True):
        url = expected_url(page, where)
        label = f"{tag}: {event['kind']}"
        if where is not None and url is None:
            print(f"  SKIP {label}: no {where[0]}.{where[1]} picture here")
            continue
        shown = check.ok(
            row["src"] == url and row["hasIcon"] == (url is not None),
            f"{label} shows {where[1] if where else 'no picture'}",
            row["src"],
        )
        check.ok(
            row["text"] == row["plain"],
            f"{label}: the picture leaves the line's text as it was",
            [row["text"], row["plain"]],
        )
        if url is None or not shown:
            continue
        check.ok(
            bool(row["alt"]),
            f"{label}: the picture has alt text (outside textContent, above)",
            row["alt"],
        )
        check.ok(
            row["lineOpacity"] == "1"
            and row["wordsOpacity"] == "0.65"
            and row["tile"] == NAVY,
            f"{label}: full-strength picture on the navy tile, muted words",
            [row["lineOpacity"], row["wordsOpacity"], row["tile"]],
        )
        box = row["tileBox"]
        check.ok(
            box["width"] >= 16 and abs(box["width"] - box["height"]) < 0.5,
            f"{label}: the tile is a square of at least 16 px",
            box,
        )
    with_icon = [row["wordsLeft"] for row in rows if row["hasIcon"]]
    without = [row["wordsLeft"] for row in rows if not row["hasIcon"]]
    if with_icon and without:
        check.ok(
            max(with_icon + without) - min(with_icon + without) < 1.5,
            f"{tag}: words start in one column with or without a picture",
            [min(with_icon), max(with_icon), min(without), max(without)],
        )
    page.locator("#icons-probe").screenshot(
        path=str(
            SHOTS / f"log_icons_events_{language}_{'table' if game else 'page'}.png"
        )
    )


def check_neutral(page, language: str) -> None:
    def revealed(round_number: int) -> list[dict]:
        return [
            {"kind": "agents_recalled", "payload": {}},
            {
                "kind": "conflict_revealed",
                "payload": {"conflict_id": "skirmish_a", "round": round_number},
            },
            {"kind": "cards_drawn", "payload": {"player": 0, "count": 5}},
        ]

    # The reveal arriving in a chance step's events, as most Rounds' do
    # (the discard reshuffle drawn before it): the title says only that a
    # Round started, and the numeral says which.
    in_chance = [
        {"kind": "agents_recalled", "payload": {}},
        {
            "chance": {
                "type": "chance",
                "index": 1,
                "decision_id": "round:5:player:0:discard_shuffle",
                "events": [
                    {"kind": "personal_discard_shuffled", "payload": {"player": 0}},
                    *revealed(5)[1:],
                ],
            }
        },
    ]
    groups = [
        revealed(3),
        in_chance,
        revealed(10),
        revealed(11),
        [{"kind": "leader_draft_pool_revealed", "payload": {}}],
        [
            {"kind": "combat_intrigue_started", "payload": {}},
            {"kind": "combat_intrigue_finished", "payload": {}},
        ],
        [
            {"kind": "endgame_started", "payload": {}},
            {"kind": "game_finished", "payload": {}},
        ],
    ]
    cards = page.evaluate(NEUTRAL_JS, {"groups": groups, "language": language})
    page.wait_for_function(LOADED_JS)
    wanted = [
        ("log_icons", "round_3"),
        ("log_icons", "round_5"),
        ("log_icons", "round_10"),
        None,
        None,
        ("log_icons", "conflict"),
        ("log_icons", "vp_winner"),
    ]
    names = [
        "Round 3",
        "Round 5 (chance)",
        "Round 10",
        "Round 11",
        "setup",
        "Combat Intrigue",
        "game over",
    ]
    for card, where, name in zip(cards, wanted, names, strict=True):
        url = expected_url(page, where)
        label = f"{language}: {name} card"
        if where is not None and url is None:
            print(f"  SKIP {label}: no {where[1]} picture here")
            continue
        if url is None:
            check.ok(
                card["src"] is None and card["mark"] == "⚙",
                f"{label} keeps the ⚙ mark",
                card,
            )
            continue
        check.ok(
            card["src"] == url and card["mark"] == "" and card["markOpacity"] == "1",
            f"{label} shows {where[1]} at full strength",
            card,
        )
        if card["lefts"]:
            check.ok(
                max(card["lefts"]) - min(card["lefts"]) < 1.5,
                f"{label}: its lines' words start in one column",
                card["lefts"],
            )
    page.locator("#icons-neutral").screenshot(
        path=str(SHOTS / f"log_icons_neutral_{language}.png")
    )
    page.evaluate("document.getElementById('icons-neutral')?.remove()")


def create_ai_game(page, base: str) -> None:
    """heuristic seed 7 with every expansion, reviewed to the end (the game
    log_words.py and log_passes.py read)."""
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(f"#seat-selects select[data-seat='{seat}']", "heuristic")
    set_rule_options(page, *RULE_OPTIONS)
    page.fill("#opt-seed", "7")
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.review !== null && state.view !== null")
    page.evaluate("stopPlayback(); reviewSeek(state.review.meta.step_count)")
    page.wait_for_function(
        "state.review.cursor === state.review.meta.step_count"
        " && !playback.playing && refreshFlight === null"
    )


def check_panel(page, language: str, pictures: bool) -> None:
    page.evaluate(f"setLanguage('{language}')")
    page.wait_for_function("refreshFlight === null")
    page.wait_for_timeout(300)
    page.wait_for_function(
        "[...document.querySelectorAll('#action-log img')].every((img) => img.complete)"
    )
    panel = page.evaluate(PANEL_JS)
    tag = f"{language} finished game"
    check.ok(
        panel["lines"] > 200, f"{tag}: the log panel holds the game", panel["lines"]
    )
    if pictures:
        check.ok(
            panel["iconLines"] > panel["lines"] // 4,
            f"{tag}: many event lines show a picture",
            [panel["iconLines"], panel["lines"]],
        )
        check.ok(
            not panel["broken"], f"{tag}: every picture loads", panel["broken"][:3]
        )
        numerals = [
            int(round_["icon"].removeprefix("log:round_")) for round_ in panel["rounds"]
        ]
        check.ok(
            len(numerals) >= 8 and numerals == sorted(set(numerals)),
            f"{tag}: the game cards' Round numerals count up, one per Round",
            numerals,
        )
        said = [
            (number, round_["title"])
            for number, round_ in zip(numerals, panel["rounds"], strict=True)
            if re.search(r"\d", round_["title"])
            and not re.search(rf"\b{number}\b", round_["title"])
        ]
        check.ok(not said, f"{tag}: a numeral agrees with its card's title", said[:3])
    page.evaluate(
        "window.__realLogIconUrl = logIconUrl; window.logIconUrl = () => null"
    )
    page.evaluate("renderLog()")
    plain = page.evaluate(PANEL_JS)
    page.evaluate("window.logIconUrl = window.__realLogIconUrl; renderLog()")
    check.ok(
        plain["icons"] == 0 and plain["texts"] == panel["texts"],
        f"{tag}: the pictures leave every line's text as it was",
        next(
            (
                pair
                for pair in zip(panel["texts"], plain["texts"], strict=False)
                if pair[0] != pair[1]
            ),
            None,
        ),
    )


def check_fallback(page, language: str) -> None:
    """Without the pictures (an empty catalog table) the panel's HTML is
    exactly the one the hook-less log renders."""
    tag = f"{language} without pictures"
    page.evaluate(
        """() => {
          window.__tables = ['icons', 'log_icons', 'alliance_tokens']
            .map((name) => [name, state.catalog[name]]);
          for (const [name] of window.__tables) state.catalog[name] = {};
          renderLog();
        }"""
    )
    bare = page.evaluate(PANEL_JS)
    page.evaluate(
        """() => {
          window.__hook = addLogEventIcon; window.addLogEventIcon = () => {};
          window.__neutral = neutralLogIcon; window.neutralLogIcon = () => null;
          renderLog();
        }"""
    )
    today = page.evaluate(PANEL_JS)
    page.evaluate(
        """() => {
          window.addLogEventIcon = window.__hook;
          window.neutralLogIcon = window.__neutral;
          for (const [name, table] of window.__tables) state.catalog[name] = table;
          renderLog();
        }"""
    )
    check.ok(
        bare["icons"] == 0
        and "has-icon" not in bare["html"]
        and "log-text" not in bare["html"],
        f"{tag}: no picture, tile or wrapper",
    )
    check.ok(bare["html"] == today["html"], f"{tag}: the log is exactly today's")
    check.ok("⚙" in bare["html"], f"{tag}: game cards keep the ⚙ mark")


def main() -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    with server() as (base, log_path), chrome() as browser:
        _context, page, _recorder = open_context(browser, "log-icons", VIEWPORT)
        page.goto(base)
        page.wait_for_function("state.catalog !== null")
        pictures = page.evaluate("Object.keys(state.catalog.log_icons || {}).length")
        print(f"log pictures on this machine: {pictures}")
        for language in ("ko", "en"):
            for game in (False, True):
                check_known(page, language, game)
            check_neutral(page, language)
        page.evaluate(
            "document.getElementById('icons-probe')?.remove();"
            "document.body.classList.remove('in-game')"
        )

        create_ai_game(page, base)
        for language in ("ko", "en"):
            check_panel(page, language, bool(pictures))
            check_fallback(page, language)
            page.locator("#action-log").screenshot(
                path=str(SHOTS / f"log_icons_panel_{language}.png")
            )
        errors = [
            line
            for line in log_path.read_text().splitlines()
            if "ERROR" in line or "Traceback" in line
        ]
        check.ok(not errors, f"no server errors (see {SERVER_LOG_COPY})", errors[:3])
        SERVER_LOG_COPY.write_text(log_path.read_text())
    print(f"Screenshots: {SHOTS}")
    check.finish()


if __name__ == "__main__":
    main()
