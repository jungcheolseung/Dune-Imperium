"""E2E of the Arrakeen Scouts mode (docs/arrakeen-scouts-design.md slice 9).

One human seat (0) plays a seeded Scouts game against three heuristic seats
to the end, and on the way the page must show:

- the setup box, unchecked by default, and the header badge;
- the Scouts panel: the five subcommittees, each round's item with its
  lines, the mission pieces on the board, the secret picks waiting (and the
  seat's own pick), the running auction (its own bid, who confirmed);
- a secret pick's four buttons, each naming its line (not a bare index);
- a sealed bid as the count stepper plus the one turn-end row, which is the
  confirmation itself (D5);
- Critical Moment's two/three public cards as numbered images; hovering,
  clicking or keyboard activation opens the matching detail without taking
  a card, in both languages and at laptop width; text when art is absent;
- in English, no Hangul anywhere in the panel;
- a Scouts choice with a line the seat cannot take right now (user request
  2026-09-29) shows it greyed out: one row per such line in the server's
  scouts_lines, each with its reason, not clickable (a click changes
  nothing), while the lines it can take are the ordinary rows of exactly
  the legal line actions; in English, no Hangul in the action list;
- a choice the seat is skipped for (nothing it could take) says so in the
  note, naming the item;
- after the game, the finished page without errors;
- a seat steered to the High Council (OQ-076 alternative C, 2026-09-30):
  its subcommittee choice is one more row of the turn ("소위원회 선택"),
  and pressing it opens the list of subcommittees;
- the mission pieces drawn where they lie (design 6, user request
  2026-09-30): six seeded games (PIECE_GAMES) that between them show all
  sixteen missions' pieces, checked whenever the pieces change: one DOM
  piece per view row, inside its space's regions (catalog
  tracks.scouts.regions), on its post's disc (beside a Spy), on the Bene
  Tleilax board's Helix spot or third Tleilaxu space, in its seat's
  Contract chip or on Reclaimed Forces; a seat's pieces (or one mission's
  bank goods) in one region of their space, its goods on its marker or
  troop; a cube per parked troop in the seat's colour; nothing on a hotspot, Agent, Spy, Control marker, bonus
  spice, Commander or garrison ring, and a click at each hotspot's, Agent's
  and Spy's centre still reaches it; titles in Korean and, in English,
  without Hangul; and no face-down card's id (read off the game's save,
  replayed by the engine) or name anywhere on the page;
- the fullest table the missions can leave (an edited view), both pools,
  at 2400x1500 and 1366x900, with and without the Sardaukar Commanders,
  two seats on Prison Planet (each spice on its own marker), and without the board scan the panel's list only. Screenshots go to
  E2E_SHOTS_DIR (a temporary folder by default).

The seat picks each secret line and bids in turn so every kind is seen;
everything else takes the first legal action. Seed 21 meets an unpayable
line for the seat (CHOAM Escort without a Contract, round 2) and skips two
choices (Guild Negotiation, Rotating Doors) -- re-checked 2026-10-01 after
OQ-095's explicit Agent-turn end changed the walk (the unpayable sale it
also met before no longer comes up).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from common import REPO, Check, chrome, open_context, server, set_rule_options
from open_mode import settled

check = Check()
SEEDS = (21, 58, 31, 44)
# COUNCIL_JS's walk takes a council seat with a subcommittee still to join
# (round 4; the list then offers two joins and the decline). Seed 21 until
# OQ-095's explicit Agent-turn end moved its seat to round 7, when every
# subcommittee was taken (2026-10-01).
COUNCIL_SEED = 1
HANGUL = re.compile(r"[가-힣]")

CHOOSE_JS = """(() => {
  const actions = state.actions.actions;
  const find = (id) => actions.findIndex((a) => a.action_id === id);
  const own = state.view.private || {};
  const bid = find("scouts_bid");
  if (bid >= 0) {
    if (own.scouts_bid >= 0) return find("confirm_scouts_bid");
    const bids = actions.filter((a) => a.action_id === "scouts_bid");
    const wanted = Math.min(2, bids.length - 1);
    return actions.findIndex(
      (a) => a.action_id === "scouts_bid" && a.arguments.count === wanted);
  }
  const pick = actions.filter((a) => a.action_id === "scouts_secret_pick");
  if (pick.length) return actions.indexOf(pick[state.view.round_number % pick.length]);
  const call = actions.findIndex(
    (a) => a.action_id === "scouts_call" && a.arguments.count === 1);
  if (call >= 0) return call;
  const join = actions.findIndex((a) => a.action_id === "scouts_join_mission");
  if (join >= 0) return join;
  const other = actions.findIndex((a) => a.action_id !== "switch_graft_card");
  return other >= 0 ? other : 0;
})()"""


# Every line of the seat's Scouts choice, against the rows on the page.
LINES_JS = """(() => {
  const ids = new Set(
    ["scouts_choose_option", "join_subcommittee", "scouts_join_mission"]);
  const lines = state.actions.scouts_lines.lines;
  const order = (a, b) => a - b;
  const legal = state.actions.actions
    .filter((a) => ids.has(a.action_id)).map((a) => a.index).sort(order);
  const rows = [...document.querySelectorAll('#actions .action-item')]
    .map((r) => Number(r.dataset.index)).filter((i) => legal.includes(i)).sort(order);
  const grey = [...document.querySelectorAll('#actions .scouts-line-item.unavailable')];
  return {
    legal,
    rows,
    enabled: lines.filter((l) => l.enabled).map((l) => l.action_index).sort(order),
    unavailable: lines.filter((l) => !l.enabled).length,
    grey: grey.length,
    badges: grey.map(
      (r) => (r.querySelector('.unavailable-badge') || {}).innerText || ''),
    aria: grey.every((r) => r.getAttribute('aria-disabled') === 'true'),
  };
})()"""


# CHOOSE_JS steered to the High Council: send an Agent there whenever the
# seat can, then take the seat.
COUNCIL_JS = CHOOSE_JS.replace(
    "  const own = state.view.private || {};",
    """  const council = actions.findIndex((a) =>
    (a.action_id === 'agent_turn' && a.arguments.space_id === 'high_council')
    || (a.action_id === 'resolve_board_effect'
        && a.arguments.effect === 'high_council'));
  if (council >= 0) return council;
  const own = state.view.private || {};""",
)


# The label of the turn's "choose a subcommittee" row, or null.
CHOOSE_ROW_JS = """(() => {
  const action = state.actions.actions.find(
    (a) => a.action_id === 'choose_subcommittee');
  const row = action && document.querySelector(
    `#actions .action-item[data-index="${action.index}"]`);
  return row ? row.innerText : null;
})()"""


# Keep every note the page shows (it hides itself after a few seconds).
NOTE_SPY_JS = """(() => {
  window.noteLog = [];
  const shown = note;
  note = (text) => {
    window.noteLog.push(String(text));
    shown(text);
  };
})()"""

# The Scouts items the seat was skipped for, by name, from the log.
SKIPPED_JS = """(() => state.log.entries.flatMap((entry) => (entry.events || [])
  .filter((e) => e.kind === 'scouts_choice_skipped'
    && e.payload.player === state.viewSeat)
  .map((e) => scoutsItem(e.payload.item_id).name)))()"""


def create(page, base: str, seed: int) -> None:
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(
            f"#seat-selects select[data-seat='{seat}']",
            "human" if seat == 0 else "heuristic",
        )
    check.ok(not page.is_checked("#opt-scouts"), "the Scouts box starts unchecked")
    set_rule_options(page, "choam")
    page.set_checked("#opt-leader-draft", False)
    page.set_checked("#opt-scouts", True)
    page.fill("#opt-seed", str(seed))
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    page.evaluate(NOTE_SPY_JS)


def panel_text(page) -> str:
    return page.evaluate("document.getElementById('scouts-panel').innerText")


def play(page, seen: dict[str, bool], limit: int = 4000) -> bool:
    for _ in range(limit):
        assert settled(page, 30)
        if page.evaluate("state.summary.finished"):
            return True
        if page.evaluate("state.summary.confirmation === state.viewSeat"):
            page.evaluate("confirmTurn()")
            continue
        if not page.evaluate("Boolean(state.actions && state.actions.actions.length)"):
            time.sleep(0.05)
            continue
        if inspect(page, seen):
            continue
        page.evaluate(f"applyAction({page.evaluate(CHOOSE_JS)})")
    return False


# The seat's own live log entries, oldest first: [action_id, count] pairs.
OWN_STEPS_JS = """state.log.entries
  .filter((e) => e.type === 'action' && !e.undone && e.actor === state.viewSeat)
  .map((e) => [e.action_id, e.arguments.count ?? null])"""


def press_auction(page, seen: dict[str, bool], action_id: str) -> bool:
    """Stage one step up on the auction stepper, then press the turn end once.

    User request 2026-10-05: the stepper only sets the amount and the one
    turn-end press sends it -- a sealed bid and its confirmation, or the open
    call -- with no further press. Returns whether it pressed.
    """

    key = {"scouts_bid": "bid_press", "scouts_call": "call_press"}[action_id]
    if seen.get(key):
        return False
    row = page.locator(f'#actions .count-row[data-action="{action_id}"]')
    if row.count() != 1:
        return False
    plus = row.locator(".stepper button").nth(1)
    if plus.is_enabled():
        plus.click()
    staged = int(row.locator(".stepper-value").inner_text().split()[0])
    before = len(page.evaluate(OWN_STEPS_JS))
    page.locator("#decision-banner .turn-end-row button").click()
    assert settled(page, 30)
    steps = page.evaluate(OWN_STEPS_JS)[before:]
    if action_id == "scouts_call":
        expected = [["scouts_call", staged]]
    else:
        expected = [["scouts_bid", staged]] if staged else []
        expected.append(["confirm_scouts_bid", None])
    seen[key] = check.ok(
        steps == expected
        and page.evaluate("state.summary.confirmation !== state.viewSeat"),
        f"one turn-end press sends the staged {action_id}, nothing left to press",
        (staged, steps),
    )
    return True


def inspect_lines(page, seen: dict[str, bool]) -> None:
    """A Scouts choice with a line the seat cannot take: greyed out, with
    its reason, and a click on it does nothing."""

    if seen.get("lines") or not page.evaluate(
        "Boolean(state.actions.scouts_lines"
        " && state.actions.scouts_lines.lines.some((l) => !l.enabled))"
    ):
        return
    rows = page.evaluate(LINES_JS)
    ok = check.ok(
        rows["grey"] == rows["unavailable"] > 0 and rows["aria"],
        "each line the seat cannot take is one greyed-out row",
        rows,
    )
    ok &= check.ok(
        all(badge.strip() for badge in rows["badges"]),
        "each greyed-out row says why",
        rows["badges"],
    )
    ok &= check.ok(
        rows["enabled"] == rows["legal"] == rows["rows"],
        "the lines it can take are the rows of exactly the legal line actions",
        rows,
    )
    revision = page.evaluate("state.summary.revision")
    # force: the row is announced as a disabled button (aria-disabled), so
    # Playwright would wait for it to be enabled; the click must still land.
    page.click("#actions .scouts-line-item.unavailable >> nth=0", force=True)
    time.sleep(0.3)
    assert settled(page, 10)
    ok &= check.ok(
        page.evaluate("state.summary.revision") == revision
        and page.evaluate("document.getElementById('game-error').hidden"),
        "a click on a greyed-out row changes nothing",
    )
    page.evaluate("setLanguage('en')")
    assert settled(page, 10)
    english = page.evaluate("document.getElementById('actions').innerText")
    ok &= check.ok(
        not HANGUL.search(english)
        and page.evaluate(
            "document.querySelectorAll('#actions .scouts-line-item.unavailable').length"
        )
        == rows["grey"],
        "in English the greyed-out rows carry no Hangul",
        HANGUL.findall(english)[:10],
    )
    page.evaluate("setLanguage('ko')")
    assert settled(page, 10)
    seen["lines"] = ok


def inspect_market(page, seen: dict[str, bool]) -> None:
    cards = page.evaluate("state.view.scouts_market_cards")
    if not cards:
        return
    key = f"market_{len(cards)}"
    taking = page.evaluate(
        "state.actions.actions.some((a) => a.action_id === 'scouts_take_card')"
    )
    if seen.get(key) and (not taking or seen.get("market_take")):
        return
    selector = "#scouts-panel .scouts-market-cards .vcard"
    revision = page.evaluate("state.summary.revision")
    ok = True
    viewport = page.viewport_size
    for lang, width in (("ko", 1600), ("en", 1366)):
        page.set_viewport_size({"width": width, "height": 1000})
        page.evaluate("setLanguage", lang)
        page.locator(selector).first.scroll_into_view_if_needed()
        page.wait_for_function("""() => [...document.querySelectorAll(
          '#scouts-panel .scouts-market-cards .vcard img')]
          .every((img) => img.complete && img.naturalWidth > 0)""")
        rows = page.evaluate("""() => [...document.querySelectorAll(
          '#scouts-panel .scouts-market-cards .scouts-row')].map((row) => {
          const card = row.querySelector('.vcard');
          const img = card.querySelector('img');
          const entry = entryOf(row.dataset.card, 'cards');
          const rect = card.getBoundingClientRect();
          const panel = el('scouts-panel').getBoundingClientRect();
          return {id: card.dataset.instance, text: row.innerText,
            image: img && img.getAttribute('src') === entry.image,
            alt: img && img.alt === entry.name,
            fits: rect.left >= panel.left && rect.right <= panel.right};
        })""")
        ok &= check.ok(
            [r["id"] for r in rows] == cards
            and all(r["image"] and r["alt"] and r["fits"] for r in rows)
            and all(r["text"].startswith(f"{i + 1}.") for i, r in enumerate(rows)),
            f"{key}: numbered card images in order ({lang}, {width}px)",
            rows,
        )
        first = page.locator(selector).first
        first.hover()
        page.wait_for_selector("#card-popover:not([hidden])")
        first.click()
        page.wait_for_function("popoverPinned")
        image = page.locator("#card-popover > img")
        expected = page.evaluate("entryOf(state.view.scouts_market_cards[0]).image")
        ok &= check.ok(
            image.get_attribute("src") == expected,
            f"{key}: hover and click inspect the matching card ({lang})",
        )
        page.wait_for_function("""() => {
          const img = el('card-popover').querySelector(':scope > img');
          return img && img.complete && img.naturalWidth > 0;
        }""")
        if not seen.get(key):
            page.screenshot(path=f"{SHOTS}/{key}_{lang}_{width}.png")
        page.keyboard.press("Escape")
        first.focus()
        page.keyboard.press("Enter")
        ok &= check.ok(
            page.evaluate("popoverPinned && !el('card-popover').hidden")
            and page.evaluate("state.summary.revision") == revision,
            f"{key}: keyboard inspection leaves the decision unchanged ({lang})",
        )
        page.keyboard.press("Escape")
    # With no local art the same public identities stay inspectable as text.
    fallback = page.evaluate("""() => {
      const id = state.view.scouts_market_cards[0];
      const raw = state.catalog.cards[baseId(id)];
      const saved = {image: raw.image, image_ko: raw.image_ko};
      try {
        raw.image = null; raw.image_ko = null;
        renderScouts();
        const card = el('scouts-panel').querySelector('.scouts-market-cards .vcard');
        card.click();
        return card.classList.contains('textcard') && !card.querySelector('img')
          && card.innerText.includes(entryOf(id).name) && popoverPinned;
      } finally { Object.assign(raw, saved); closePopover(); renderScouts(); }
    }""")
    ok &= check.ok(fallback, f"{key}: absent art falls back to inspectable text")
    page.set_viewport_size(viewport)
    page.evaluate("setLanguage('ko')")
    seen[key] = ok
    if taking:
        seen["market_take"] = ok


def inspect(page, seen: dict[str, bool]) -> bool:
    ids = page.evaluate("state.actions.actions.map((a) => a.action_id)")
    text = panel_text(page)
    inspect_lines(page, seen)
    inspect_market(page, seen)
    if not seen.get("subcommittees") and page.evaluate(
        "state.view.scouts_subcommittees.length === 5"
    ):
        rows = page.evaluate(
            "[...document.querySelectorAll('#scouts-panel .scouts-row[data-item]')]"
            ".map((r) => r.dataset.item)"
        )
        seen["subcommittees"] = check.ok(
            all(
                item in rows
                for item in page.evaluate("state.view.scouts_subcommittees")
            ),
            "the panel lists the five subcommittees",
            rows,
        )
    if "choose_subcommittee" in ids and not seen.get("choose"):
        # OQ-076 alternative C: a new High Council seat's subcommittee is one
        # more row among the turn's effects; pressing it opens the list.
        label = page.evaluate(CHOOSE_ROW_JS)
        seen["choose"] = check.ok(
            bool(label) and "소위원회 선택" in label,
            "a new council seat's subcommittee choice is a row of the turn",
            label,
        )
    if not seen.get("choose_grey") and page.evaluate(
        "Boolean(document.querySelector("
        "'#actions .unavailable-item[data-key=\"waiting:choose_subcommittee\"]'))"
    ):
        badge = page.evaluate(
            "document.querySelector('#actions .unavailable-item"
            "[data-key=\"waiting:choose_subcommittee\"] .unavailable-badge')"
            "?.innerText || ''"
        )
        seen["choose_grey"] = check.ok(
            bool(badge.strip()) and "choose_subcommittee" not in ids,
            "a subcommittee choice nothing can meet is greyed out with why",
            badge,
        )
    if "scouts_secret_pick" in ids and not seen.get("pick"):
        details = page.evaluate(
            "state.actions.actions.filter((a) => a.action_id === 'scouts_secret_pick')"
            ".map((a) => a.detail_ko || a.detail)"
        )
        buttons = page.evaluate("document.getElementById('actions').innerText")
        seen["pick"] = check.ok(
            len(details) == 4 and all(details) and "라운드" in buttons,
            "a secret pick's buttons name their lines",
            (details, buttons[:200]),
        )
    if "scouts_bid" in ids and not seen.get("bid"):
        stepper = page.evaluate(
            "Boolean(document.querySelector("
            "'#actions .count-row[data-action=\"scouts_bid\"]'))"
        )
        turn_end = page.evaluate(
            "Boolean(document.querySelector('#decision-banner .turn-end-row'))"
            " && turnEndAction(state.actions.actions)?.action_id"
            " === 'confirm_scouts_bid'"
        )
        seen["bid"] = check.ok(
            stepper and turn_end,
            "a sealed bid is a count stepper and the turn-end row confirms it",
            (stepper, turn_end),
        )
    for auction in ("scouts_bid", "scouts_call"):
        if auction in ids and press_auction(page, seen, auction):
            return True
    if page.evaluate(
        "state.view.private && state.view.private.scouts_bid >= 0"
    ) and not seen.get("own_bid"):
        seen["own_bid"] = check.ok(
            "내 입찰액" in text, "the panel shows the seat's own bid", text[-300:]
        )
    if page.evaluate(
        "Boolean(state.view.private && state.view.private.scouts_secret_picks.length)"
    ) and not seen.get("own_pick"):
        seen["own_pick"] = check.ok(
            "내 선택" in text and "비밀 선택" in text,
            "the panel shows the seat's own waiting pick",
            text[-300:],
        )
    if page.evaluate("state.view.scouts_goods.length > 0") and not seen.get("pieces"):
        seen["pieces"] = check.ok(
            "임무 조각" in text, "the panel shows mission pieces", text[-300:]
        )
    if page.evaluate("state.view.scouts_market_cards.length > 0") and not seen.get(
        "market"
    ):
        seen["market"] = check.ok(
            "공개된 카드" in text, "the panel shows Critical Moment's cards"
        )
    if not seen.get("english") and page.evaluate("state.view.round_number >= 4"):
        page.evaluate("setLanguage('en')")
        assert settled(page, 10)
        english = panel_text(page)
        seen["english"] = check.ok(
            "Arrakeen Scouts" in english and not HANGUL.search(english),
            "in English the panel carries no Hangul",
            HANGUL.findall(english)[:10],
        )
        page.evaluate("setLanguage('ko')")
        assert settled(page, 10)
    return False


def council(page, seen: dict[str, bool], limit: int = 3000) -> None:
    """OQ-076 alternative C: steer the seat to the High Council; its
    subcommittee choice is one more row of the turn ("소위원회 선택"), and
    pressing it opens the list of subcommittees, greyed ones with why."""

    for _ in range(limit):
        assert settled(page, 30)
        if page.evaluate("state.summary.finished"):
            return
        if page.evaluate("state.summary.confirmation === state.viewSeat"):
            page.evaluate("confirmTurn()")
            continue
        if not page.evaluate("Boolean(state.actions && state.actions.actions.length)"):
            time.sleep(0.05)
            continue
        inspect(page, seen)
        ids = page.evaluate("state.actions.actions.map((a) => a.action_id)")
        if "choose_subcommittee" in ids:
            page.evaluate(
                "applyAction(state.actions.actions.find("
                "(a) => a.action_id === 'choose_subcommittee').index)"
            )
            assert settled(page, 10)
            lines = page.evaluate(
                "state.actions.scouts_lines && state.actions.scouts_lines.frame"
            )
            joins = page.evaluate(
                "document.querySelectorAll('#actions .action-item').length"
            )
            seen["choose_list"] = check.ok(
                lines == "scouts_subcommittee" and joins >= 2,
                "pressing it opens the subcommittee list (joins and the decline)",
                (lines, joins),
            )
            return
        page.evaluate(f"applyAction({page.evaluate(COUNCIL_JS)})")


# --- Mission pieces on the boards (design 6, user request 2026-09-30) -------------

# Each view row of Scouts pieces and the one DOM piece that should stand for
# it: on the board scan (a space's regions, a post's disc), on the Bene
# Tleilax scan (the Helix, the third Tleilaxu track space), on the seat's
# Contract chip or on Reclaimed Forces in the Tleilaxu Row. The zoomed Bene
# Tleilax board repeats its pieces and is left out.
PIECES_JS = """(() => {
  const view = state.view;
  const rows = scoutsPieceRows(view);
  const tracks = state.catalog.tracks || {};
  const regions = (tracks.scouts || {}).regions || {};
  const stage = document.querySelector('#board .board-stage');
  const btStage = document.querySelector('#market .bt-stage');
  const outside = (n) => !n.closest('#bt-zoom');
  const pct = (node, host) => {
    const s = host.getBoundingClientRect(), r = node.getBoundingClientRect();
    return { left: (r.left - s.left) / s.width * 100, top: (r.top - s.top) / s.height * 100,
      width: r.width / s.width * 100, height: r.height / s.height * 100 };
  };
  const spies = new Set(view.players.flatMap((p) => p.spy_post_ids));
  const out = rows.map((row) => {
    const all = [...document.querySelectorAll(`.scouts-piece[data-row="${row.key}"]`)]
      .filter(outside);
    const loc = row.location;
    let host = null, where = null;
    if (loc.startsWith('post:') || regions[loc]) { host = stage; where = 'board'; }
    else if (loc === 'helix' || loc === 'tleilaxu_track') { host = btStage; where = 'bt'; }
    else if (loc.startsWith('contract:')) {
      host = document.querySelector(
        `#seats .seat[data-seat="${row.seat}"] .tag[data-contract="${loc.slice(9)}"]`);
      where = 'contract';
    } else if (loc === 'reclaimed_forces') {
      host = document.querySelector('#market .vcard[data-instance="reclaimed_forces"]');
      where = 'card';
    }
    const inside = host ? all.filter((n) => host.contains(n)) : [];
    const node = inside[0] || null;
    let within = null;
    if (node && (where === 'contract' || where === 'card')) {
      const a = node.getBoundingClientRect(), b = host.getBoundingClientRect();
      within = a.left >= b.left - 1 && a.right <= b.right + 1
        && a.top >= b.top - 1 && a.bottom <= b.bottom + 1;
    }
    return {
      key: row.key, kind: row.kind, mission: row.mission, location: loc,
      seat: row.seat, count: row.count, where, host: Boolean(host),
      n: all.length, inside: inside.length,
      rect: node && (where === 'board' || where === 'bt') ? pct(node, host) : null,
      within,
      spied: loc.startsWith('post:') && spies.has(loc.slice(5)),
      title: node ? node.title : null,
      label: node ? node.getAttribute('aria-label') : null,
      cubes: node ? [...node.querySelectorAll('.scouts-cube')]
        .map((c) => getComputedStyle(c).backgroundColor) : [],
    };
  });
  return {
    rows: out,
    total: [...document.querySelectorAll('.scouts-piece')].filter(outside).length,
    scan: Boolean(stage),
    btScan: Boolean(btStage),
    colors: SEAT_COLORS,
  };
})()"""

# What a piece on the board scan must stay off, in stage percent: every
# space's hotspot (its frame, where the Agents stand), the Spies, Control
# markers, the Maker bonus spice, the Commanders and the garrison rings;
# and whether a click at the centre of each hotspot, Agent and Spy still
# lands on it.
BLOCKERS_JS = """(() => {
  const stage = document.querySelector('#board .board-stage');
  if (!stage) return null;
  const s = stage.getBoundingClientRect();
  const pct = (r) => ({ left: (r.left - s.left) / s.width * 100,
    top: (r.top - s.top) / s.height * 100,
    width: r.width / s.width * 100, height: r.height / s.height * 100 });
  const boxes = [];
  const add = (selector, kind) => {
    for (const n of stage.querySelectorAll(selector)) {
      boxes.push({ kind, name: n.dataset.space || n.dataset.seat || '',
        ...pct(n.getBoundingClientRect()) });
    }
  };
  add('.hotspot', 'hotspot');
  add('.spy-post', 'spy');
  add('.control-marker', 'control');
  add('.bonus-spice:not(.scouts-piece)', 'bonus spice');
  add('.commander-piece', 'commander');
  (state.catalog.tracks.garrison_units.rings || []).forEach(([left, top, width, height], seat) => {
    boxes.push({ kind: 'garrison', name: String(seat), left, top, width, height });
  });
  const missed = [];
  const hit = (node, selector) => {
    const r = node.getBoundingClientRect();
    const x = r.left + r.width / 2, y = r.top + r.height / 2;
    if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) return;
    const top = document.elementFromPoint(x, y);
    if (!top || top.closest(selector) !== node.closest(selector)) {
      missed.push([selector, node.dataset.space || node.dataset.seat || '',
        top ? top.className.baseVal ?? top.className : null]);
    }
  };
  for (const n of stage.querySelectorAll('.hotspot')) hit(n, '.hotspot');
  for (const n of stage.querySelectorAll('.hotspot .agent-token')) hit(n, '.hotspot');
  for (const n of stage.querySelectorAll('.spy-post')) hit(n, '.spy-post');
  return { boxes, missed };
})()"""

HANGUL_TITLES_JS = """[...document.querySelectorAll('.scouts-piece')]
  .map((n) => n.title + ' | ' + (n.getAttribute('aria-label') || '') + ' | ' + n.innerText)"""


def _meets(a: dict, b: dict, slack: float = 0.02) -> bool:
    return not (
        a["left"] + a["width"] <= b["left"] + slack
        or b["left"] + b["width"] <= a["left"] + slack
        or a["top"] + a["height"] <= b["top"] + slack
        or b["top"] + b["height"] <= a["top"] + slack
    )


def _inside(rect: dict, box: list[float], tolerance: float = 0.15) -> bool:
    left, top, width, height = box
    return (
        rect["left"] >= left - tolerance
        and rect["top"] >= top - tolerance
        and rect["left"] + rect["width"] <= left + width + tolerance
        and rect["top"] + rect["height"] <= top + height + tolerance
    )


def _rgb(hex_color: str) -> str:
    value = hex_color.lstrip("#")
    red, green, blue = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgb({red}, {green}, {blue})"


def check_pieces(page, label: str) -> set[str]:
    """Every Scouts piece in the view is exactly one DOM piece at its place:
    inside its space's regions, on (or beside a Spy on) its post, on the
    Helix spot or the third Tleilaxu space, in its seat's Contract chip or on
    Reclaimed Forces; parked troops are a cube each in the seat's colour; no
    piece stands on a hotspot, Agent, Spy, Control marker, bonus spice,
    Commander or garrison ring; every piece is titled. Returns the missions
    whose pieces were checked (or rightly left to the panel without a
    scan)."""

    found = page.evaluate(PIECES_JS)
    catalog = page.evaluate(
        "({ scouts: state.catalog.tracks.scouts, posts: state.catalog.posts,"
        " postSize: state.catalog.post_size,"
        " bt: (state.catalog.bene_tleilax || {}).layout || null })"
    )
    colors = found["colors"]
    problems: list[object] = []
    expected_total = 0
    checked: set[str] = set()
    for row in found["rows"]:
        name = f"{row['mission']} {row['kind']} at {row['location']}"
        drawn = (
            (row["where"] == "board" and found["scan"])
            or (row["where"] == "bt" and found["btScan"])
            or row["where"] in ("contract", "card")
        )
        if not drawn:
            # Without the scan the Scouts panel's list is all there is.
            if row["n"]:
                problems.append((name, "drawn without its scan", row["n"]))
            else:
                checked.add(row["mission"])
            continue
        expected_total += 1
        if not (row["host"] and row["n"] == 1 and row["inside"] == 1):
            problems.append((name, "not one piece at its place", row))
            continue
        checked.add(row["mission"])
        if not row["title"] or row["title"] != row["label"]:
            problems.append((name, "untitled", row["title"]))
        if row["kind"] == "troop" and row["cubes"] != [_rgb(colors[row["seat"]])] * row["count"]:
            problems.append((name, "cubes", row["cubes"], row["count"]))
        rect = row["rect"]
        location = row["location"]
        if row["where"] in ("contract", "card"):
            if not row["within"]:
                problems.append((name, "outside its card", row))
        elif location.startswith("post:"):
            x, y = catalog["posts"][location.removeprefix("post:")]
            centre = (rect["left"] + rect["width"] / 2, rect["top"] + rect["height"] / 2)
            if abs(centre[1] - y) > 0.15 or (
                rect["left"] < x + catalog["postSize"] / 2 - 0.1
                if row["spied"]
                else abs(centre[0] - x) > 0.15
            ):
                problems.append((name, "not on its post", rect, (x, y), row["spied"]))
        elif row["where"] == "bt":
            bt = catalog["bt"]["scouts"]
            if location == "helix":
                x, y = bt["helix_spice_point"]
                centre_y = rect["top"] + rect["height"] / 2
                if abs(centre_y - y) > 0.3 or rect["left"] + rect["width"] > x + 3:
                    problems.append((name, "not beside the Helix", rect))
            elif not any(_inside(rect, r["box"], 0.3) for r in bt["regions"][location]):
                problems.append((name, "not on the third space", rect))
        elif not any(
            _inside(rect, region["box"]) for region in catalog["scouts"]["regions"][location]
        ):
            problems.append((name, "outside its regions", rect))
    if found["total"] != expected_total:
        problems.append(("pieces", found["total"], "for", expected_total, "rows"))

    # A seat's pieces (or one mission's bank goods) lie together in one
    # region of their space, and a seat's goods lie on its marker or troop.
    homes: dict[tuple[str, str], set[int]] = {}
    for row in found["rows"]:
        regions = catalog["scouts"]["regions"].get(row["location"])
        if row["where"] != "board" or not regions or not row["rect"]:
            continue
        group = f"seat:{row['seat']}" if row["seat"] >= 0 else f"bank:{row['mission']}"
        index = next(
            (i for i, region in enumerate(regions) if _inside(row["rect"], region["box"])),
            -1,
        )
        homes.setdefault((row["location"], group), set()).add(index)
        if row["kind"] in ("spice", "solari", "water") and row["seat"] >= 0:
            holders = [
                other
                for other in found["rows"]
                if other["kind"] in ("troop", "marker")
                and other["seat"] == row["seat"]
                and other["mission"] == row["mission"]
                and other["location"] == row["location"]
                and other["rect"]
            ]
            if holders and not any(_meets(row["rect"], h["rect"], 0) for h in holders):
                problems.append((f"{row['mission']} {row['kind']}", "off its holder", row["rect"]))
    for (location, group), indexes in homes.items():
        if len(indexes) > 1:
            problems.append((location, group, "split across regions", sorted(indexes)))

    blockers = page.evaluate(BLOCKERS_JS)
    if blockers is not None:
        board_rects = [
            (f"{row['mission']} {row['kind']} at {row['location']}", row["rect"])
            for row in found["rows"]
            if row["where"] == "board" and row["rect"]
        ]
        for name, rect in board_rects:
            for box in blockers["boxes"]:
                if _meets(rect, box):
                    problems.append((name, "on", box["kind"], box["name"]))
        if blockers["missed"]:
            problems.append(("clicks that miss", blockers["missed"][:5]))
    check.ok(not problems, f"{label}: every Scouts piece at its place", problems[:8])
    return checked


def check_titles(page, label: str) -> None:
    """Each piece names its mission and goods in the page's language."""

    korean = page.evaluate(HANGUL_TITLES_JS)
    page.evaluate("setLanguage('en')")
    assert settled(page, 10)
    english = page.evaluate(HANGUL_TITLES_JS)
    page.evaluate("setLanguage('ko')")
    assert settled(page, 10)
    check.ok(
        korean
        and all(title.split(" | ")[0] for title in korean)
        and any(HANGUL.search(title) for title in korean),
        f"{label}: the pieces are titled in Korean",
        korean[:3],
    )
    check.ok(
        len(english) == len(korean)
        and all(title.split(" | ")[0] for title in english)
        and not any(HANGUL.search(title) for title in english),
        f"{label}: in English the pieces' titles carry no Hangul",
        [t for t in english if HANGUL.search(t)][:3],
    )


# The face-down cards on the board, read off the game's own save: the page
# never learns them (the view carries counts only), so the script asks the
# engine, replaying the saved game in this checkout.
REPLAY_PY = """
import json, sys
from dune_imperium.core.replay import replay_game
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.server.persistence import parse_save_document
document = json.loads(open(sys.argv[1], encoding="utf-8").read())
state = replay_game(UprisingRulesEngine(), parse_save_document(document).replay)
print(json.dumps([card for _, _, card in state.scouts_goods_cards]))
"""


def face_down_ids(page, base: str, saves: Path) -> list[str]:
    game_id = page.evaluate("state.gameId")
    response = page.request.post(f"{base}/games/{game_id}/save", data={})
    save_id = response.json()["save_id"]
    result = subprocess.run(
        [str(REPO / ".venv/bin/python"), "-c", REPLAY_PY, str(saves / f"{save_id}.json")],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO,
    )
    return json.loads(result.stdout)


# Every attribute value and text of the page and the view, split into id-like
# words: a face-down card's id must be none of them.
WORDS_JS = """(() => {
  const words = new Set();
  const add = (text) => { for (const w of String(text).split(/[^A-Za-z0-9_]+/)) if (w) words.add(w); };
  for (const node of document.querySelectorAll('*')) {
    for (const attribute of node.attributes) add(attribute.value);
  }
  add(document.body.innerText);
  add(JSON.stringify(state.view));
  return [...words];
})()"""


def check_face_down(page, base: str, saves: Path, label: str) -> bool:
    ids = face_down_ids(page, base, saves)
    counts = page.evaluate("state.view.scouts_board_card_counts")
    words = set(page.evaluate(WORDS_JS))
    piles = page.evaluate(
        "[...document.querySelectorAll('.scouts-intrigue, .scouts-contract')]"
        ".map((n) => ({ text: n.innerText.trim(), title: n.title,"
        " data: JSON.stringify(n.dataset) }))"
    )
    names = page.evaluate(
        "Object.values({...state.catalog.intrigue, ...state.catalog.contracts})"
        ".map((e) => e.name)"
    )
    leaked = [card for card in ids if card in words]
    named = [
        pile for pile in piles if any(name in pile["title"] + pile["text"] for name in names)
    ]
    return check.ok(
        ids
        and len(ids) == sum(count for _, _, count in counts)
        and not leaked
        and not named
        and all(pile["text"].isdigit() for pile in piles),
        f"{label}: no face-down card's id or name reaches the page",
        (ids, counts, leaked, named, piles),
    )


# Games whose missions leave every kind of piece (seed search 2026-09-30 over
# seeds 1-40 of both pools, seat 0 playing CHOOSE_JS as here; searched again
# 2026-10-01 over seeds 1-60 after OQ-095's explicit Agent-turn end moved
# seeds 16 and 36 off Security Detail and Planetary Exploration, so seed 19
# replaced seed 1): (rule options, seed, rounds to play). Missions come out
# in rounds 2 and 3 and place their pieces then, so three rounds show them
# all.
# Six games cover all sixteen missions; seat 0 joins every mission it can,
# so each parking mission has troops on the board.
UPRISING_POOL = ("choam",)
IMMORTALITY_POOL = ("choam", "immortality")
PIECE_GAMES: tuple[tuple[tuple[str, ...], int, int], ...] = (
    (UPRISING_POOL, 2, 3),  # CHOAM Research, Prison Planet, Urban Surveillance
    (UPRISING_POOL, 7, 3),  # Desert Riding, Imperial Reserve, Send for Aid
    (UPRISING_POOL, 19, 3),  # Planetary Exploration, Security Detail,
    # Send for Aid
    (IMMORTALITY_POOL, 4, 3),  # CHOAM Escort, Tleilaxu Offering, Weirding Warfare
    (IMMORTALITY_POOL, 16, 3),  # Emperor's Schemes, Fedaykin Assistance
    (IMMORTALITY_POOL, 36, 3),  # Back Room Deal, Coordinate With The Emperor,
    # Sponsored Research
)
EXPECTED_MISSIONS = frozenset(
    {
        "security_detail",
        "imperial_reserve",
        "desert_riding",
        "urban_surveillance",
        "planetary_exploration",
        "choam_research",
        "choam_escort",
        "sponsored_research",
        "back_room_deal",
        "prison_planet",
        "emperors_schemes",
        "fedaykin_assistance",
        "weirding_warfare",
        "send_for_aid",
        "coordinate_with_the_emperor",
        "tleilaxu_offering",
    }
)


def create_with(page, base: str, seed: int, options: tuple[str, ...]) -> None:
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(
            f"#seat-selects select[data-seat='{seat}']",
            "human" if seat == 0 else "heuristic",
        )
    set_rule_options(page, *options)
    page.set_checked("#opt-leader-draft", False)
    page.set_checked("#opt-scouts", True)
    page.fill("#opt-seed", str(seed))
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")


# The pieces change a few times a game; the Spies decide where a post's
# goods lie.
PIECE_KEY_JS = """JSON.stringify([state.view.scouts_goods, state.view.scouts_parked,
  state.view.scouts_board_card_counts, state.view.players.map((p) => p.spy_post_ids),
  state.view.players.map((p) => p.active_contract_ids)])"""


def piece_games(page, base: str, saves: Path) -> None:
    """Live games: whenever the pieces change, check them where they lie;
    the face-down piles once per game against the engine's cards."""

    covered: set[str] = set()
    for options, seed, rounds in PIECE_GAMES:
        label = f"{'+'.join(options) or 'base'} seed {seed}"
        print(f"[pieces] {label}")
        create_with(page, base, seed, options)
        last = None
        piles = False
        titled = False
        for _ in range(4000):
            assert settled(page, 30)
            if page.evaluate(
                f"state.summary.finished || state.view.round_number > {rounds}"
            ):
                break
            key = page.evaluate(PIECE_KEY_JS)
            if key != last:
                last = key
                # Agents just placed fly in from their seats' panels first.
                page.wait_for_function("!document.querySelector('.agent-token.flying')")
                covered |= check_pieces(page, label)
                if not titled and page.evaluate("scoutsPieceRows(state.view).length > 0"):
                    check_titles(page, label)
                    titled = True
                if not piles and page.evaluate(
                    "state.view.scouts_board_card_counts.length > 0"
                ):
                    piles = check_face_down(page, base, saves, label)
            if page.evaluate("state.summary.confirmation === state.viewSeat"):
                page.evaluate("confirmTurn()")
                continue
            if not page.evaluate(
                "Boolean(state.actions && state.actions.actions.length)"
            ):
                time.sleep(0.05)
                continue
            page.evaluate(f"applyAction({page.evaluate(CHOOSE_JS)})")
    check.ok(
        EXPECTED_MISSIONS <= covered,
        "the seeded games show every mission's pieces",
        sorted(EXPECTED_MISSIONS - covered),
    )


# The fullest table the missions can leave (an edited view, the render's only
# input): four seats on every parking mission, the bank's goods everywhere,
# both face-down piles, goods on every post (one guarded by a Spy), Agents
# on every mission space and the Sardaukar Commanders on their setup spaces.
FILL_JS = """(variant) => {
  const v = state.view;
  const goods = [], parked = [], cards = [];
  const seats = [0, 1, 2, 3];
  if (variant === 'uprising') {
    for (const s of seats) {
      goods.push(['prison_planet', 'sardaukar', 'marker', 1, s]);
      goods.push(['prison_planet', 'sardaukar', 'spice', 2, s]);
    }
  } else {
    cards.push(['emperors_schemes', 'sardaukar', 2]);
    for (const s of seats) {
      parked.push(['coordinate_with_the_emperor', s, 'sardaukar', 1]);
      goods.push(['coordinate_with_the_emperor', 'sardaukar', 'solari', 2, s]);
    }
  }
  for (const s of seats) parked.push(['security_detail', s, 'deliver_supplies', 1]);
  for (const s of seats) parked.push(['weirding_warfare', s, 'espionage', 2]);
  for (const s of seats) parked.push(['fedaykin_assistance', s, 'desert_tactics', 2]);
  goods.push(['imperial_reserve', 'imperial_privilege', 'spice', 1, -1]);
  goods.push(['imperial_reserve', 'imperial_privilege', 'solari', 2, -1]);
  for (const s of seats) {
    parked.push(['send_for_aid', s, 'gather_support', 1]);
    goods.push(['send_for_aid', 'gather_support', 'water', 1, s]);
  }
  cards.push(['choam_research', 'research_station', 2]);
  goods.push(['desert_riding', 'hagga_basin', 'maker_hooks', 1, -1]);
  const posts = Object.keys(state.catalog.posts);
  posts.forEach((post, i) => {
    goods.push([i % 2 ? 'urban_surveillance' : 'planetary_exploration', `post:${post}`,
      i % 2 ? 'solari' : 'spice', 1, -1]);
  });
  const contract = Object.keys(state.catalog.contracts)[0];
  v.players[0].active_contract_ids = [contract];
  goods.push(['choam_escort', `contract:${contract}`, 'solari', 1, 0]);
  goods.push(['choam_escort', `contract:${contract}`, 'spice', 1, 0]);
  goods.push(['sponsored_research', 'helix', 'spice', 2, -1]);
  goods.push(['back_room_deal', 'reclaimed_forces', 'solari', 2, -1]);
  for (const s of seats) parked.push(['tleilaxu_offering', s, 'tleilaxu_track', 2]);
  v.scouts_goods = goods;
  v.scouts_parked = parked;
  v.scouts_board_card_counts = cards;
  const busy = ['sardaukar', 'deliver_supplies', 'espionage', 'desert_tactics',
    'imperial_privilege', 'gather_support', 'research_station', 'hagga_basin'];
  v.players.forEach((p, s) => {
    p.agent_locations = busy.slice();
    p.spy_post_ids = [];
    p.tleilaxu_space = s + 1;
  });
  v.players[1].spy_post_ids = [posts[0]];
  v.sardaukar_commander_space_ids = ['sardaukar', 'dutiful_service', 'deliver_supplies',
    'high_council', 'gather_support', 'assembly_hall'];
  render();
}"""

# Seats 0 and 2 joined Prison Planet: two markers, each with its 2 spice.
PRISON_PLANET_JS = """(() => {
  const v = state.view;
  v.scouts_goods = [0, 2].flatMap((s) => [
    ['prison_planet', 'sardaukar', 'marker', 1, s],
    ['prison_planet', 'sardaukar', 'spice', 2, s]]);
  v.scouts_parked = [];
  v.scouts_board_card_counts = [];
  v.sardaukar_commander_space_ids = [];
  render();
})()"""

SHOTS = os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(prefix="dune-e2e-scouts-")


def fullest_table(base: str, browser) -> None:
    """The fullest table at two window sizes, both mission pools, with and
    without the Commanders."""

    for viewport in ({"width": 2400, "height": 1500}, {"width": 1366, "height": 900}):
        _, page, _ = open_context(browser, f"fullest-{viewport['width']}", viewport)
        create_with(page, base, 5, ("choam", "bloodlines", "immortality"))
        for variant in ("uprising", "immortality"):
            label = f"fullest table ({variant}, {viewport['width']}px)"
            print(f"[pieces] {label}")
            page.evaluate(FILL_JS, variant)
            page.wait_for_function(
                "[...document.querySelectorAll('.board-stage img')].every((i) => i.complete)"
            )
            page.wait_for_function("!document.querySelector('.agent-token.flying')")
            page.wait_for_timeout(350)
            check_pieces(page, label)
            scales = page.evaluate(
                "[...document.querySelectorAll('.board-stage .scouts-piece[data-scale]')]"
                ".map((n) => Number(n.dataset.scale))"
            )
            check.ok(
                scales and min(scales) >= 0.5,
                f"{label}: a crowded space shrinks no piece below half",
                sorted(set(scales)),
            )
            page.screenshot(path=f"{SHOTS}/scouts_pieces_{variant}_{viewport['width']}.png")
            if viewport["width"] == 2400:
                check_titles(page, label)
                page.evaluate(
                    "state.view.sardaukar_commander_space_ids = []; render();"
                )
                page.wait_for_timeout(100)
                check_pieces(page, f"{label}, no Commanders")
        # Two seats on Prison Planet and no Commander: each seat's spice
        # lies on its own marker, in the same region (verify 2026-09-30).
        page.evaluate(PRISON_PLANET_JS)
        page.wait_for_timeout(100)
        check_pieces(page, f"two seats on Prison Planet ({viewport['width']}px)")
        # Without the board scan the pieces are the panel's text only.
        page.evaluate("state.catalog.board_image = null; render();")
        check.ok(
            page.evaluate("document.querySelectorAll('#board .scouts-piece').length") == 0
            and "임무 조각" in panel_text(page),
            f"fullest table ({viewport['width']}px): no scan, the panel's list only",
        )
        page.context.close()


def main() -> None:
    wanted = (
        "subcommittees",
        "pick",
        "bid",
        "bid_press",
        "call_press",
        "own_bid",
        "own_pick",
        "pieces",
        "english",
        "lines",
        "skip_notice",
        "market_2",
        "market_3",
    )
    with server() as (base, _server_log), chrome() as browser:
        _, page, _ = open_context(browser, "scouts")
        seen: dict[str, bool] = {}
        for seed in SEEDS:
            print(f"[game] seed {seed}")
            create(page, base, seed)
            check.ok(
                "아라킨 스카웃" in page.evaluate("el('header-status').innerText"),
                "the header names the Scouts mode",
            )
            finished = play(page, seen)
            check.ok(finished, f"seed {seed} plays to the end")
            skipped = page.evaluate(SKIPPED_JS)
            if skipped and not seen.get("skip_notice"):
                notes = page.evaluate("window.noteLog")
                seen["skip_notice"] = check.ok(
                    all(
                        any(note.startswith(f"{name}: ") for note in notes)
                        for name in skipped
                    ),
                    "a skipped choice says so in the note, naming the item",
                    (skipped, notes),
                )
            check.ok(
                page.evaluate("!document.getElementById('scouts-panel').hidden"),
                "the finished game still shows the panel",
            )
            if all(seen.get(name) for name in wanted):
                break
        print("[game] the High Council seat's subcommittee choice")
        create(page, base, COUNCIL_SEED)
        council(page, seen)
        for name in (*wanted, "choose", "choose_list"):
            check.ok(bool(seen.get(name)), f"seen: {name}")
        piece_games(page, base, Path(_server_log).parent)
        fullest_table(base, browser)
    print(f"[pieces] screenshots in {SHOTS}")
    check.finish()


if __name__ == "__main__":
    sys.exit(main())
