"""Pieces that move between places, and the switch for every effect
(motion.js, UI stage 12's deferred ③⑤⑦⑧⑩, user request 2026-11-10).

A: one human seat against three heuristic seats, Uprising, walked to the
   end of a seeded game. After every step the moves the page queued are
   compared with the ones read independently off the step's new public log
   events and views:
   - ③ every acquisition (card_acquired, tleilaxu_card_acquired): its card,
     its buyer and where it went;
   - ⑤ every Alliance won, taken or lost has its banner, and every Influence
     cube whose level changed slides (and no other);
   - ⑦ every Conflict a winner keeps (won_conflict_ids) flies to that winner;
   - ⑧ each step's Maker spaces land together, and every recall sends home
     exactly the Agents placed since the last one, and passes the First
     Player marker.
   The first move of each kind is then shown on its own and stopped
   mid-flight: its piece flies from inside the window to its seat's panel
   (or, at phone width, to the players' tab), and is screenshotted in Korean
   and English, at 1366x768 and 390x844.
C: the original board, two rounds: the same comparison, and a Conflict won
   there flies to nobody (its cards stay where they were revealed).
D: an Arrakeen Scouts game until cards are won at auction: the same
   comparison, with scouts_card_bought among the bought cards.
B: ⑩ the help panel's switch turns every effect off: steps then queue and
   draw nothing (no card cue, banner, rising number, flying Agent or moving
   piece). The choice survives a reload, and turning effects back on
   replays nothing old while new steps show their cues again.

Screenshots go to E2E_SHOTS_DIR (a temporary folder by default).
"""

from __future__ import annotations

import os
import sys
import tempfile
import time

from common import (
    LAPTOP_VIEWPORT,
    Check,
    chrome,
    open_context,
    server,
    set_rule_options,
)
from open_mode import create_game, settled

check = Check()
SHOTS = os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(prefix="dune-e2e-motion-")
SEED = 7
PHONE = {"width": 390, "height": 844}
BUY_EVENTS = {"card_acquired", "tleilaxu_card_acquired", "scouts_card_bought"}
ALLIANCE_EVENTS = {"alliance_gained", "alliance_transferred", "alliance_lost"}

HOOKS = """() => {
  window.__made = []; window.__bands = []; window.__slides = []; window.__ghosts = [];
  const made = motionCues;
  motionCues = (entries) => {
    const out = made(entries);
    window.__made.push(...out);
    return out;
  };
  const bands = phaseBannerCues;
  phaseBannerCues = (entries, from) => {
    const out = bands(entries, from);
    window.__bands.push(...out.filter((cue) => cue.type === 'alliance'));
    return out;
  };
  const slide = slideInfluenceCubes;
  slideInfluenceCubes = () => {
    slide();
    for (const cube of document.querySelectorAll('#board .track-cube.fx-sliding')) {
      window.__slides.push(`${cube.dataset.seat}:${cube.dataset.faction}:${cube.dataset.level}`);
    }
  };
  new MutationObserver((changes) => {
    for (const change of changes) for (const node of change.addedNodes) {
      if (node instanceof Element && node.dataset.fx) {
        window.__ghosts.push({fx: node.dataset.fx, seat: node.dataset.seat || null});
      }
    }
  }).observe(document.getElementById('fx-layer'), {childList: true});
}"""

# The page's moves of this step, made comparable.
MADE = """() => window.__made.map((c) => ({
  type: c.type, index: c.index, seat: c.seat ?? null,
  card: c.cardId || c.conflictId || null, destination: c.destination || null,
  spaces: c.spaces ? [...c.spaces].sort() : null,
  agents: c.agents ? c.agents.map((a) => `${a.seat}:${a.space}`).sort() : null,
  first: c.firstPlayer ?? null,
}))"""

BANDS = """() => window.__bands.map((c) => ({index: c.index, faction: c.faction,
  from: c.from, to: c.to}))"""

INFLUENCE = """() => state.view.players.map((p) => Object.fromEntries(
  Object.keys(FACTION_LABELS).map((k) =>
    [k, Math.max(0, Math.min(6, p.influence[k] || 0))])))"""

# Show one move or banner on its own, then stop every animation of the
# effects layer, the banner and the cubes at `share` of its length.
SHOW = """async ([kind, cue, share]) => {
  hidePlayEffect(); hidePhaseBanner(); hideMotion();
  playEffects.queue = []; phaseBanner.queue = []; motion.queue = [];
  if (kind === 'alliance') { phaseBanner.queue.unshift(cue); nextPhaseBanner(); }
  else { motion.queue.unshift(cue); nextMotion(); }
  clearTimeout(motion.timer); clearTimeout(phaseBanner.timer);
  // Recalled Agents leave one after another (45 ms apart).
  await new Promise((done) => setTimeout(done, 500));
  for (const animation of document.getAnimations()) {
    const target = animation.effect && animation.effect.target;
    if (!target || !target.closest('#fx-layer, #phase-banner')) continue;
    animation.pause();
    animation.currentTime = animation.effect.getTiming().duration * share;
  }
}"""

# Each flying piece: where it starts and where its last frame puts it.
FLIGHTS = """() => [...document.querySelectorAll('#fx-layer .fx-ghost')].map((node) => {
  const animation = node.getAnimations()[0];
  const frames = animation ? animation.effect.getKeyframes() : [];
  const last = frames.length ? frames[frames.length - 1].transform || '' : '';
  const move = /translate\\(([-\\d.]+)px, ([-\\d.]+)px\\)/.exec(last);
  const left = parseFloat(node.style.left), top = parseFloat(node.style.top);
  const width = parseFloat(node.style.width), height = parseFloat(node.style.height);
  const x = left + width / 2, y = top + height / 2;
  return {fx: node.dataset.fx, seat: node.dataset.seat ?? null,
    space: node.dataset.space ?? null,
    card: node.dataset.card ?? null, start: [x, y],
    end: move ? [x + Number(move[1]), y + Number(move[2])] : null,
    image: (node.querySelector('img') || {}).src || null};
})"""

RECTS = """() => {
  const box = (node) => {
    if (!node) return null;
    const r = node.getBoundingClientRect();
    return r.width ? [r.left, r.top, r.right, r.bottom] : null; };
  const seats = {};
  for (const seat of [0, 1, 2, 3]) {
    seats[seat] = box(document.querySelector(`#seats .seat[data-seat="${seat}"]`));
  }
  const spaces = {};
  for (const node of document.querySelectorAll('#board .hotspot[data-space]')) {
    spaces[node.dataset.space] = box(node);
  }
  for (const node of document.querySelectorAll('#board .bonus-spice[data-space]')) {
    spaces[node.dataset.space] = box(node);
  }
  const tab = box(document.querySelector('#phone-tabs [data-view="seats"]'));
  return {seats, spaces, tab,
    window: [0, 0, innerWidth, innerHeight]};
}"""

BAND_TEXT = """() => {
  const band = document.querySelector('#phase-banner .phase-banner');
  const art = band && band.querySelector('.phase-banner-alliance .alliance-token');
  return band ? {cue: band.dataset.cue, seat: band.dataset.seat,
    faction: band.dataset.faction, text: band.innerText, art: Boolean(art)}
    : null;
}"""


def inside(point, box, slack: float = 2.0) -> bool:
    return bool(
        point
        and box
        and box[0] - slack <= point[0] <= box[2] + slack
        and box[1] - slack <= point[1] <= box[3] + slack
    )


def expected_moves(
    entries: list[dict], log: list[dict], players: list[dict]
) -> list[dict]:
    """The moves the step's new entries call for, read off the events alone."""
    moves: list[dict] = []
    # The Agents on the board before this step: every placement since the
    # last recall in the live log before it.
    agents: list[str] = []
    first_new = entries[0]["index"] if entries else len(log)
    for entry in log:
        if entry.get("undone") or entry.get("type") == "undo":
            continue
        fresh = entry["index"] >= first_new
        maker_spaces: list[str] = []
        maker_at = None
        for event in entry.get("events") or []:
            kind, payload = event["kind"], event.get("payload") or {}
            if kind == "agent_placed":
                agents.append(f"{payload['player']}:{payload['space_id']}")
            elif kind == "agent_recalled":
                key = f"{payload.get('player')}:{payload.get('space_id')}"
                if key in agents:
                    agents.remove(key)
            elif kind == "agents_recalled":
                if fresh:
                    moves.append(
                        {
                            "type": "recall",
                            "index": entry["index"],
                            "agents": sorted(agents),
                            "first": payload.get("first_player"),
                        }
                    )
                agents = []
            if not fresh:
                continue
            bought = payload.get("card_id") or payload.get("instance_id")
            if kind in BUY_EVENTS and isinstance(bought, str):
                moves.append(
                    {
                        "type": "buy",
                        "index": entry["index"],
                        "seat": payload["player"],
                        "card": bought,
                        "destination": payload.get("destination") or "discard",
                    }
                )
            elif kind == "conflict_won":
                won = players[payload["player"]].get("won_conflict_ids") or []
                if payload["conflict_id"] in won:
                    moves.append(
                        {
                            "type": "conflict",
                            "index": entry["index"],
                            "seat": payload["player"],
                            "card": payload["conflict_id"],
                        }
                    )
            elif kind == "maker_spice_added":
                maker_spaces.append(payload["space_id"])
                maker_at = entry["index"]
        if maker_at is not None:
            moves.append(
                {"type": "makers", "index": maker_at, "spaces": sorted(maker_spaces)}
            )
    return moves


def made_comparable(made: list[dict]) -> list[dict]:
    out = []
    for cue in made:
        kind = cue["type"]
        if kind == "buy":
            out.append(
                {
                    "type": kind,
                    "index": cue["index"],
                    "seat": cue["seat"],
                    "card": cue["card"],
                    "destination": cue["destination"],
                }
            )
        elif kind == "conflict":
            out.append(
                {
                    "type": kind,
                    "index": cue["index"],
                    "seat": cue["seat"],
                    "card": cue["card"],
                }
            )
        elif kind == "makers":
            out.append({"type": kind, "index": cue["index"], "spaces": cue["spaces"]})
        elif kind == "recall":
            out.append(
                {
                    "type": kind,
                    "index": cue["index"],
                    "agents": cue["agents"],
                    "first": cue["first"],
                }
            )
    return out


def key(move: dict) -> str:
    return repr(sorted(move.items()))


def step(page) -> None:
    if page.evaluate("state.summary.confirmation === state.viewSeat"):
        page.evaluate("confirmTurn()")
        return
    if not page.evaluate("Boolean(state.actions && state.actions.actions.length)"):
        # Another seat's sealed choice: nothing for this seat to do yet.
        time.sleep(0.05)
        return
    index = page.evaluate("""() => {
      const rows = state.actions.actions;
      const pick = (id) => rows.find((a) => a.action_id === id);
      // Buy what the human can afford, so its own acquisitions show too.
      return (pick('choose_agent_card') || pick('place_agent') || pick('acquire_card')
        || rows[0]).index;
    }""")
    page.evaluate(f"applyAction({index})")


def spot_check(page, kind: str, cue: dict, seen: dict) -> None:
    """Show one move on its own in both languages, at laptop and phone
    width, stopped mid-flight; check where its pieces go."""
    for lang in ("ko", "en"):
        page.evaluate("(lang) => setLanguage(lang)", lang)
        for size_name, size in (("desktop", LAPTOP_VIEWPORT), ("phone", PHONE)):
            page.set_viewport_size(size)
            page.wait_for_timeout(150)
            shown = dict(cue)
            if kind == "buy" and size_name == "phone":
                # A phone shows one view: the shared cards are out of sight.
                shown["origin"] = None
            page.evaluate(SHOW, [kind, shown, 0.35])
            flights = page.evaluate(FLIGHTS)
            rects = page.evaluate(RECTS)
            tag = f"{kind} {lang} {size_name}"
            if kind == "alliance":
                band = page.evaluate(BAND_TEXT)
                check.ok(
                    bool(band) and band["cue"] == "alliance" and band["art"],
                    f"{tag}: the alliance banner shows with its token",
                    band,
                )
                if band:
                    seat_label = page.evaluate(
                        "(seat) => playerLabel(seat)", cue["seat"]
                    )
                    check.ok(
                        seat_label.lower() in band["text"].lower(),
                        f"{tag}: the banner names the seat",
                        band["text"],
                    )
            ghosts = [
                f
                for f in flights
                if f["fx"]
                == {
                    "buy": "buy",
                    "conflict": "conflict",
                    "makers": "makers",
                    "recall": "recall",
                    "alliance": "alliance",
                }[kind]
            ]
            check.ok(bool(ghosts), f"{tag}: a piece is on its way", flights)
            for ghost in ghosts:
                check.ok(
                    inside(ghost["start"], rects["window"]),
                    f"{tag}: it starts inside the window",
                    ghost,
                )
                if kind == "makers":
                    check.ok(
                        inside(ghost["end"], rects["spaces"].get(ghost["space"])),
                        f"{tag}: the spice lands on its Maker space",
                        ghost,
                    )
                    continue
                if kind == "alliance" and cue.get("lost"):
                    continue  # back to its strip on the board
                seat = ghost["seat"] if kind != "alliance" else str(cue["seat"])
                target = (
                    rects["tab"]
                    if size_name == "phone"
                    else rects["seats"].get(str(seat))
                )
                check.ok(
                    inside(ghost["end"], target),
                    f"{tag}: it lands on seat {seat}'s panel (or the players' tab)",
                    (ghost, target),
                )
            if kind in ("buy", "conflict"):
                section = "cards" if kind == "buy" else "conflicts"
                image = page.evaluate(
                    "([id, s]) => { const e = s === 'cards' ? entryOf(id, 'cards')"
                    " : lookup(id, 'conflicts'); return e && e.image; }",
                    [cue.get("cardId") or cue.get("conflictId"), section],
                )
                if image and ghosts:
                    check.ok(
                        ghosts[0]["image"] and ghosts[0]["image"].endswith(image),
                        f"{tag}: the flying card is the logged card",
                        (ghosts[0], image),
                    )
            if kind == "recall":
                check.ok(
                    len(ghosts) == len(cue["agents"]) or size_name == "phone",
                    f"{tag}: every recalled Agent flies home",
                    (len(ghosts), len(cue["agents"])),
                )
            page.screenshot(path=os.path.join(SHOTS, f"{kind}_{lang}_{size_name}.png"))
            seen.setdefault(kind, []).append(f"{lang}-{size_name}")
    page.evaluate("setLanguage('ko')")
    page.set_viewport_size(LAPTOP_VIEWPORT)
    page.evaluate(
        "hidePhaseBanner(); hideMotion();"
        " document.getAnimations().filter((a) => a.effect && a.effect.target"
        " && a.effect.target.closest('#fx-layer, #phase-banner'))"
        ".forEach((a) => a.cancel())"
    )


def compare_step(page, totals: dict[str, int]) -> int:
    """Take one step; compare the moves, alliance banners and cube slides
    the page made with the ones its new log entries and views call for.
    Returns the number of mismatches."""
    mismatches = 0
    # One call, so a late update of the last step cannot fall in between.
    before, influence = page.evaluate(
        f"""() => {{
          window.__made = []; window.__bands = []; window.__slides = [];
          return [state.log.count, ({INFLUENCE})()];
        }}"""
    )
    step(page)
    assert settled(page, 30)
    log = page.evaluate("state.log.entries")
    players = page.evaluate("state.view.players")
    fresh = [e for e in log if e["index"] >= before]
    want = expected_moves(fresh, log, players)
    made = made_comparable(page.evaluate(MADE))
    if sorted(map(key, made)) != sorted(map(key, want)):
        mismatches += 1
        check.ok(False, "the step's moves match its log", (made, want))
    bands = page.evaluate(BANDS)
    want_bands = [
        {
            "index": e["index"],
            "faction": ev["payload"]["faction"],
            "from": ev["payload"]["from_player"]
            if ev["payload"]["from_player"] >= 0
            else None,
            "to": ev["payload"]["to_player"]
            if ev["payload"]["to_player"] >= 0
            else None,
        }
        for e in fresh
        if not e.get("undone")
        for ev in e.get("events") or []
        if ev["kind"] in ALLIANCE_EVENTS
    ]
    if sorted(map(key, bands)) != sorted(map(key, want_bands)):
        mismatches += 1
        check.ok(
            False, "the step's alliance banners match its log", (bands, want_bands)
        )
    after = page.evaluate(INFLUENCE)
    want_slides = sorted(
        f"{seat}:{faction}:{level}"
        for seat, levels in enumerate(after)
        for faction, level in levels.items()
        if influence[seat][faction] != level
    )
    slides = sorted(set(page.evaluate("window.__slides")))
    if slides != want_slides:
        mismatches += 1
        check.ok(
            False,
            "the cubes that slid are the ones whose level changed",
            (slides, want_slides),
        )
    totals["slide"] += len(slides)
    totals["alliance"] += len(bands)
    for move in made:
        totals[move["type"]] += 1
    return mismatches


def walk(base, browser) -> None:
    context, page, rec = open_context(browser, "table-motion", LAPTOP_VIEWPORT)
    create_game(page, base, humans=(0,), seed=SEED)
    page.evaluate(HOOKS)
    print("[A] moves read off the log, step by step, to the game's end")
    totals = {
        "buy": 0,
        "conflict": 0,
        "makers": 0,
        "recall": 0,
        "alliance": 0,
        "slide": 0,
    }
    mismatches = 0
    seen: dict[str, list[str]] = {}
    for _ in range(1500):
        assert settled(page, 30)
        if page.evaluate("state.summary.finished"):
            break
        mismatches += compare_step(page, totals)
        if mismatches > 5:
            break
        # The first move of each kind, on its own, in both languages and sizes.
        for kind in ("buy", "conflict", "makers", "recall"):
            if kind in seen:
                continue
            cue = page.evaluate(
                "(kind) => { const c = window.__made.find((c) => c.type === kind);"
                " return c ? JSON.parse(JSON.stringify(c)) : null; }",
                kind,
            )
            if cue and (kind != "recall" or len(cue["agents"]) >= 4):
                spot_check(page, kind, cue, seen)
        if "alliance" not in seen:
            cue = page.evaluate(
                "() => { const c = window.__bands[0];"
                " return c ? JSON.parse(JSON.stringify(c)) : null; }"
            )
            if cue:
                spot_check(page, "alliance", cue, seen)
    check.ok(page.evaluate("state.summary.finished"), "the seeded game reaches its end")
    check.ok(mismatches == 0, f"every step's moves matched its log ({mismatches})")
    print("    moves:", totals)
    for kind in ("buy", "conflict", "makers", "recall", "alliance", "slide"):
        check.ok(totals[kind] >= 1, f"the walk had {kind} moves ({totals[kind]})")
    for kind in ("buy", "conflict", "makers", "recall", "alliance"):
        check.ok(
            len(seen.get(kind, [])) == 4,
            f"{kind} shown in both languages and sizes",
            seen.get(kind),
        )
    ghosts = page.evaluate("window.__ghosts.length")
    check.ok(ghosts > 0, f"pieces flew during the walk ({ghosts})")
    check.ok(not rec.js_errors, "no JS errors", rec.js_errors[:3])
    context.close()


def original_board(base, browser) -> None:
    """C: the original board's Conflict cards stay where they were revealed
    [DI p. 8]: a Conflict won there flies to nobody, while the rest moves as
    on Uprising's board."""
    print("[C] the original board: two rounds, no Conflict card flies")
    context, page, rec = open_context(browser, "table-motion-imperium", LAPTOP_VIEWPORT)
    create_game(page, base, humans=(0,), seed=SEED, base_game="imperium")
    page.evaluate(HOOKS)
    totals = dict.fromkeys(
        ("buy", "conflict", "makers", "recall", "alliance", "slide"), 0
    )
    mismatches = 0
    for _ in range(600):
        assert settled(page, 30)
        if page.evaluate("state.summary.finished") or totals["recall"] >= 2:
            break
        mismatches += compare_step(page, totals)
        if mismatches > 5:
            break
    won = page.evaluate(
        "state.log.entries.filter((e) => !e.undone && (e.events || [])"
        ".some((ev) => ev.kind === 'conflict_won')).length"
    )
    print("    moves:", totals, "conflicts won:", won)
    check.ok(mismatches == 0, f"every step's moves matched its log ({mismatches})")
    check.ok(totals["recall"] >= 2, "two rounds were recalled")
    check.ok(won >= 1 and totals["conflict"] == 0, "Conflicts were won, none flew")
    check.ok(totals["buy"] >= 1 and totals["slide"] >= 1, "cards and cubes moved")
    check.ok(not rec.js_errors, "no JS errors", rec.js_errors[:3])
    context.close()


def scouts_auction(base, browser) -> None:
    """D: an Arrakeen Scouts game: a card won at auction (scouts_card_bought,
    named by its instance) flies to its buyer like any bought card."""
    print("[D] Arrakeen Scouts: an auction's card flies to its buyer")
    context, page, rec = open_context(browser, "table-motion-scouts", LAPTOP_VIEWPORT)
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(
            f"#seat-selects select[data-seat='{seat}']",
            "human" if seat == 0 else "heuristic",
        )
    set_rule_options(page, "choam")
    page.set_checked("#opt-leader-draft", False)
    page.set_checked("#opt-scouts", True)
    page.fill("#opt-seed", str(SEED))
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    page.evaluate(HOOKS)
    totals = dict.fromkeys(
        ("buy", "conflict", "makers", "recall", "alliance", "slide"), 0
    )
    mismatches = 0
    auctions = 0
    for _ in range(2500):
        assert settled(page, 30)
        if page.evaluate("state.summary.finished"):
            break
        mismatches += compare_step(page, totals)
        auctions = page.evaluate(
            "state.log.entries.filter((e) => !e.undone && (e.events || [])"
            ".some((ev) => ev.kind === 'scouts_card_bought')).length"
        )
        if mismatches > 5 or (auctions >= 2 and totals["recall"] >= 1):
            break
    print("    moves:", totals, "auction buys:", auctions)
    check.ok(mismatches == 0, f"every step's moves matched its log ({mismatches})")
    check.ok(auctions >= 1, f"cards were won at auction ({auctions})")
    check.ok(not rec.js_errors, "no JS errors", rec.js_errors[:3])
    context.close()


QUIET = """() => ({
  card: !document.getElementById('play-effects').hidden,
  band: !document.getElementById('phase-banner').hidden,
  floats: document.getElementById('stat-floats').childElementCount,
  fx: document.getElementById('fx-layer').childElementCount,
  flying: document.querySelectorAll('#board .agent-token.flying').length,
  sliding: document.querySelectorAll('#board .track-cube.fx-sliding').length,
  queued: playEffects.queue.length + phaseBanner.queue.length + motion.queue.length
    + (playEffects.current ? 1 : 0) + (phaseBanner.current ? 1 : 0)
    + (motion.current ? 1 : 0),
})"""


def effects_off(base, browser) -> None:
    print("[B] the help panel's switch turns every effect off, and back on")
    context, page, rec = open_context(browser, "table-motion-off", LAPTOP_VIEWPORT)
    create_game(page, base, humans=(0,), seed=SEED)
    page.click("#open-help")
    page.wait_for_selector("#effects-toggle")
    check.ok(page.is_checked("#effects-toggle"), "effects start on")
    page.screenshot(path=os.path.join(SHOTS, "setting_ko_desktop.png"))
    page.uncheck("#effects-toggle")
    check.ok(
        page.evaluate("localStorage.getItem('dune.effectsOff')") == "1",
        "the choice is kept in this browser",
    )
    page.click("#help .help-close")
    page.evaluate(HOOKS)
    # Sounds are recorded, not played (sounds.js).
    page.evaluate(
        "window.__sounds = []; playSound = (name) => window.__sounds.push(name)"
    )
    loud = 0
    for _ in range(140):
        assert settled(page, 30)
        step(page)
        assert settled(page, 30)
        quiet = page.evaluate(QUIET)
        if any(quiet.values()):
            loud += 1
            check.ok(False, "nothing shows with effects off", quiet)
            if loud > 3:
                break
    check.ok(loud == 0, "140 steps with effects off drew nothing")
    check.ok(page.evaluate("window.__ghosts.length") == 0, "no piece flew")
    check.ok(page.evaluate("window.__made.length") > 0, "the steps had moves to drop")
    sounds = page.evaluate("window.__sounds")
    check.ok(
        any(name in ("round", "combat") for name in sounds),
        f"a phase's sound still plays with effects off ({sounds})",
    )
    page.reload()
    page.wait_for_function("state.view !== null && refreshFlight === null")
    check.ok(page.evaluate("effectsOff()"), "the switch survives a reload")
    page.click("#open-help")
    check.ok(not page.is_checked("#effects-toggle"), "the help panel shows it off")
    page.evaluate("setLanguage('en')")
    page.click("#help .help-close")
    page.click("#open-help")
    page.screenshot(path=os.path.join(SHOTS, "setting_en_desktop.png"))
    page.set_viewport_size(PHONE)
    page.wait_for_timeout(200)
    page.screenshot(path=os.path.join(SHOTS, "setting_en_phone.png"))
    page.evaluate("setLanguage('ko')")
    page.click("#help .help-close")
    # A phone folds the header's buttons into its menu.
    page.click("#phone-menu")
    page.click("#open-help")
    page.screenshot(path=os.path.join(SHOTS, "setting_ko_phone.png"))
    page.set_viewport_size(LAPTOP_VIEWPORT)
    page.check("#effects-toggle")
    page.click("#help .help-close")
    check.ok(
        page.evaluate("localStorage.getItem('dune.effectsOff')") is None,
        "turning them on forgets the switch",
    )
    page.evaluate("render(); render({foreign: true})")
    check.ok(page.evaluate(QUIET)["queued"] == 0, "turning them on replays nothing old")
    shown = False
    for _ in range(40):
        assert settled(page, 30)
        step(page)
        assert settled(page, 30)
        if page.evaluate(QUIET)["queued"]:
            shown = True
            break
    check.ok(shown, "with effects on again, new steps show their cues")
    check.ok(not rec.js_errors, "no JS errors", rec.js_errors[:3])
    context.close()


def main() -> None:
    started = time.monotonic()
    with server() as (base, _), chrome() as browser:
        # Scenarios by letter (all by default): `table_motion.py B` runs B.
        chosen = set(sys.argv[1:]) or {"A", "B", "C", "D"}
        if "A" in chosen:
            walk(base, browser)
        if "C" in chosen:
            original_board(base, browser)
        if "D" in chosen:
            scouts_auction(base, browser)
        if "B" in chosen:
            effects_off(base, browser)
    print(f"    screenshots: {SHOTS} ({time.monotonic() - started:.0f}s)")
    check.finish()


if __name__ == "__main__":
    main()
