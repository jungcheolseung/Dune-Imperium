"""Phase and turn banners (effects.js, user requests 2026-10-05 and 2026-10-08).

A: a real seeded Arrakeen Scouts game (seat 0 human, three heuristic seats,
   Leader draft on so round 1's Conflict reveal reaches the log) is walked
   to the end. After every step the page's pending banners are compared with
   the cues read independently off the new public log events and the
   summary, and each one is drawn and read back from the DOM: the round
   banner names the summary's round and the revealed Conflict (with its card
   image), the combat banner the Conflict of that round (the view's own
   history), a Scouts banner the item's kind and name, the Endgame banner
   the phase, every AI turn its own "플레이어N 차례" at its seat's first step
   since the last turn end, the Combat result board the logged standing
   (combat_standing), and "내 차례" comes exactly when seat 0's turn starts. A
   re-render, a language switch and a reload never show it again; the
   switch redraws the banner on screen in the other language without
   queueing anything. Every banner keeps clear of clicks and inside the
   window at 1366x768, 1920x1080 and a narrow 1100x800, in both languages
   and with reduced motion (opacity only). The result board alone takes a
   click, and a click or Escape closes it.
B: a remote room (host seat 0, guest seat 1): the guest's turn start reads
   "플레이어2 차례" (seats are numbered from one) on the host's screen and
   "내 차례" on the guest's.
C: AI-only playback shows phase banners and every seat's turn as another
   player's; pausing and seeking clear them.

Sounds (sounds.js, user request 2026-10-11): the page's playSound is
recorded instead of played. A Round, combat and Scouts banner each asks for
its own sound once as the live queue starts it (a turn or the Endgame for
none), a local table has no decision sound, the real Web Audio path plays
every sound without an error, a review plays none, and on the remote table
the host's round 1 banner sounds and a decision reaching the guest plays
the decision sound.

Screenshots of every banner in both languages go to E2E_SHOTS_DIR (a
temporary folder by default).
"""

from __future__ import annotations

import os
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
SHOTS = os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(
    prefix="dune-e2e-phase-banner-"
)
SEED = 21
KEY = "e2e-admin-key"
SIZES = (
    {"width": 1366, "height": 768},
    {"width": 1920, "height": 1080},
    {"width": 1100, "height": 800},
)

# Every band drawn in this page, read the moment it is inserted: a record
# that does not depend on reading the page before a banner times out.
RECORDER = """
window.__banners = [];
window.__sounds = [];
document.addEventListener('DOMContentLoaded', () => {
  // Every sound the page asks for (sounds.js), recorded instead of played.
  window.__playSound = window.playSound;
  window.playSound = (name) => { window.__sounds.push(name); };
  const box = document.getElementById('phase-banner');
  new MutationObserver((changes) => {
    for (const change of changes) for (const node of change.addedNodes) {
      if (!(node instanceof Element)) continue;
      if (!node.classList.contains('phase-banner')) continue;
      const text = (s) => (node.querySelector(s) || {}).textContent || '';
      window.__banners.push({cue: node.dataset.cue,
        seat: node.dataset.seat || null, mine: node.classList.contains('mine'),
        title: text('.phase-banner-title'),
        subtitle: text('.phase-banner-subtitle')});
    }
  }).observe(box, {childList: true});
});
"""

# The banners waiting in the page, the one on screen first, frozen in place.
PENDING_JS = """() => {
  clearTimeout(phaseBanner.timer);
  return [phaseBanner.current, ...phaseBanner.queue].filter(Boolean).map((c) => ({
    type: c.type, round: c.round ?? null, conflict: c.conflictId ?? null,
    item: c.itemId ?? null, seat: c.seat ?? null,
    rows: c.rows ? c.rows.map((r) => [r.seat, r.rank, r.strength, r.multiplier])
      : null, count: c.count ?? null}));
}"""

# The same cues, read from the log and the view without the page's helpers,
# in the order they go on screen. A combat's Conflict is the view's history
# entry of the round it ran in: the summary's round, or the round before a
# reveal later in the batch. An AI seat's turn (seat 0 is announced from the
# summary) stands at that seat's first step since the last turn end or the
# last entry that opened a phase.
EXPECTED_JS = """(from) => {
  const out = [];
  const cue = (at, type, round, conflict, item, seat = null, rows = null,
    count = null) => out.push({at, cue: {type, round, conflict, item, seat, rows,
    count}});
  const live = state.log.entries.filter((e) => !e.undone && e.type !== 'undo');
  const fresh = live.filter((e) => e.index >= from);
  const events = fresh.flatMap((e) => (e.events || []).map((event, position) =>
    ({event, at: [e.index, position]})));
  const history = state.view.conflict_history;
  const boundary = ['conflict_revealed', 'combat_intrigue_started',
    'combat_intrigue_finished', 'combat_standing', 'scouts_item_revealed',
    'endgame_started', 'turn_passed'];
  let ended = -1;
  let opened = -1;
  for (const e of live) {
    const taking = ['agent_turn', 'reveal_turn', 'play_turn_start_card'];
    if (e.index >= from && e.type === 'action' && e.actor !== 0
        && taking.includes(e.action_id)) {
      const since = Math.max(ended, opened);
      const first = live.find((x) => x.type === 'action' && x.actor === e.actor
        && x.index > since);
      cue([first.index, -1], 'turn', null, null, null, e.actor);
    }
    if ((e.events || []).some((v) => boundary.includes(v.kind))) opened = e.index;
    const ends = ['finish_agent_turn', 'finish_reveal'];
    if (e.type === 'action' && ends.includes(e.action_id)) ended = e.index;
  }
  let standing = null;
  events.forEach(({event, at}, position) => {
    const p = event.payload || {};
    if (event.kind === 'conflict_revealed') {
      cue(at, 'round', p.round, p.conflict_id, null);
    } else if (event.kind === 'combat_intrigue_started') {
      const later = events.slice(position)
        .find((e) => e.event.kind === 'conflict_revealed');
      const round = later ? later.event.payload.round - 1 : state.summary.round_number;
      const row = history.find((h) => h.round === round);
      cue(at, 'combat', round, row ? row.conflict_id : null, null);
    } else if (event.kind === 'combat_standing') {
      if (!standing || standing.at[0] !== at[0]) {
        const row = history.find((h) => h.conflict_id === p.conflict_id);
        cue(at, 'result', row ? row.round : null, p.conflict_id, null, null, []);
        standing = out[out.length - 1];
      }
      standing.cue.rows.push([p.player, p.rank, p.strength, p.multiplier]);
    } else if (event.kind === 'scouts_item_revealed') {
      cue(at, 'scouts', p.round, null, p.item_id);
    } else if (event.kind === 'endgame_started') {
      cue(at, 'endgame', null, null, null);
    } else if (['sandworm_deployed', 'reveal_sandworm_deployed'].includes(event.kind)) {
      const count = p.count ?? p.amount ?? 1;
      const last = out[out.length - 1];
      if (last && last.cue.type === 'sandworm' && last.at[0] === at[0]
          && last.cue.seat === p.player) last.cue.count += count;
      else cue(at, 'sandworm', null, null, null, p.player, null, count);
    } else if (event.kind === 'shield_wall_destroyed') {
      cue(at, 'shield_wall', null, null, null);
    } else if (event.kind === 'game_finished') {
      cue(at, 'final', null, null, null);
    }
  });
  out.sort((a, b) => a.at[0] - b.at[0] || a.at[1] - b.at[1]);
  return out.map((item) => item.cue);
}"""

# Turn ends since `from`, and whether seat 0 stands at its own turn frame.
TURN_JS = """(from) => ({
  ended: state.log.entries.slice(from).some((e) => !e.undone && e.type === 'action'
    && ['finish_agent_turn', 'finish_reveal'].includes(e.action_id)),
  start: !state.summary.finished && state.summary.confirmation === null
    && state.summary.decision !== null && state.summary.decision.kind === 'turn'
    && state.summary.decision.owner === 0,
})"""

# The human seat's step: confirm a bid once made, otherwise the first row.
CHOOSE_JS = """(() => {
  const actions = state.actions.actions;
  const find = (id) => actions.findIndex((a) => a.action_id === id);
  const own = state.view.private || {};
  if (find('scouts_bid') >= 0) {
    return own.scouts_bid >= 0 ? find('confirm_scouts_bid') : find('scouts_bid');
  }
  return 0;
})()"""

# Draw one cue as the page would and hold it still, mid-way, for reading.
SHOW_JS = """(cue) => {
  clearTimeout(phaseBanner.timer);
  phaseBanner.queue = [];
  phaseBanner.current = cue;
  phaseBanner.duration = 1600;
  phaseBanner.shownAt = performance.now() - 1000;
  drawPhaseBanner();
  for (const a of el('phase-banner').getAnimations({subtree: true})) a.pause();
}"""

# What the band on screen says and where it sits.
READ_JS = """() => {
  const box = el('phase-banner');
  const band = box.querySelector('.phase-banner');
  const rect = box.getBoundingClientRect();
  const board = el('board').getBoundingClientRect();
  const side = el('side').getBoundingClientRect();
  const text = (s) => (band.querySelector(s) || {}).textContent || null;
  const x = rect.left + rect.width / 2, y = rect.top + rect.height / 2;
  const hit = document.elementFromPoint(x, y);
  const img = band.querySelector('img');
  return {
    cue: band.dataset.cue, seat: band.dataset.seat || null,
    mine: band.classList.contains('mine'),
    kicker: text('.phase-banner-kicker'), title: text('.phase-banner-title'),
    subtitle: text('.phase-banner-subtitle'),
    image: img ? img.getAttribute('src') : null,
    imageLoaded: img ? img.complete && img.naturalWidth > 0 : null,
    fits: rect.left >= 0 && rect.top >= 0 && rect.right <= innerWidth
      && rect.bottom <= innerHeight && rect.width > 200,
    titleSize: parseFloat(
      getComputedStyle(band.querySelector('.phase-banner-title')).fontSize),
    overBoard: x >= board.left && x <= board.right,
    clearOfSide: side.left < board.right || rect.right <= side.left + 1,
    through: [box, ...box.querySelectorAll('*')]
      .every((n) => getComputedStyle(n).pointerEvents === 'none'),
    hitOutside: hit !== null && !box.contains(hit),
    color: getComputedStyle(band).getPropertyValue('--banner-color').trim(),
    live: box.getAttribute('aria-live'),
    hidden: band.getAttribute('aria-hidden'),
    z: Number(getComputedStyle(box).zIndex),
    rows: [...band.querySelectorAll('.phase-result-row')].map((r) => ({
      seat: Number(r.dataset.seat), rank: Number(r.dataset.rank),
      rankText: r.querySelector('.phase-result-rank').textContent,
      strength: r.querySelector('.phase-result-strength').textContent.trim(),
      mine: r.classList.contains('mine')})),
    takesClicks: getComputedStyle(band).pointerEvents !== 'none',
  };
}"""

TITLES = {
    "ko": {
        "round": "라운드 {round}",
        "combat": "전투",
        "scouts": "아라킨 스카웃",
        "endgame": "종료 단계",
        "mine": "내 차례",
        "other": "플레이어{seat} 차례",
        "round_start": "라운드 시작",
        "conflict": "교전: {name}",
        "result": "전투 결과",
        "ranks": {1: "1위", 2: "2위", 3: "3위", 0: "보상 없음"},
        "final_ranks": {1: "1위", 2: "2위", 3: "3위", 4: "4위"},
        "sandworm": "모래벌레 소환!",
        "sandworms": "모래벌레 {count}마리 소환!",
        "shield_wall": "방어벽 파괴!",
        "final": "최종 순위",
        "winner": "승자: {name}",
        "game_over": "게임 종료",
    },
    "en": {
        "round": "Round {round}",
        "combat": "Combat",
        "scouts": "Arrakeen Scouts",
        "endgame": "Endgame",
        "mine": "Your turn",
        "other": "Player {seat}'s turn",
        "round_start": "Round Start",
        "conflict": "Conflict: {name}",
        "result": "Combat Result",
        "ranks": {1: "1st", 2: "2nd", 3: "3rd", 0: "No reward"},
        "final_ranks": {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"},
        "sandworm": "Sandworm summoned!",
        "sandworms": "{count} sandworms summoned!",
        "shield_wall": "Shield Wall destroyed!",
        "final": "Final Standings",
        "winner": "Winner: {name}",
        "game_over": "Game over",
    },
}
SCOUTS_KINDS = {
    "ko": {
        "mission": "임무",
        "event": "이벤트",
        "auction": "경매",
        "sale": "판매",
        "subcommittee": "소위원회",
    },
    "en": {
        "mission": "Mission",
        "event": "Event",
        "auction": "Auction",
        "sale": "Sale",
        "subcommittee": "Subcommittee",
    },
}


def catalog(page, section: str, key: str) -> dict:
    return page.evaluate(
        "([s, k]) => { const e = state.catalog[s][k] || {};"
        " return {name: e.name, image: e.image || null, kind: e.kind || null}; }",
        [section, key],
    )


def leader_of(page, seat: int) -> dict:
    return page.evaluate(
        """(seat) => { const p = state.view.players[seat];
        const e = state.catalog.leaders[p.leader_face_id || p.leader_id];
        return {name: e.name, image: e.image || null}; }""",
        seat,
    )


def expected_words(page, cue: dict, lang: str) -> dict:
    """The kicker, title, subtitle and art a cue must show, from the catalog."""
    words = TITLES[lang]
    if cue["type"] in ("round", "combat"):
        conflict = catalog(page, "conflicts", cue["conflict"])
        round_line = words["round"].format(round=cue["round"])
        return {
            "kicker": words["round_start"] if cue["type"] == "round" else round_line,
            "title": round_line if cue["type"] == "round" else words["combat"],
            "subtitle": words["conflict"].format(name=conflict["name"]),
            "image": conflict["image"],
        }
    if cue["type"] == "scouts":
        item = catalog(page, "scouts_items", cue["item"])
        return {
            "kicker": words["round"].format(round=cue["round"]),
            "title": words["scouts"],
            "subtitle": f"{SCOUTS_KINDS[lang][item['kind']]} · {item['name']}",
            "image": None,
        }
    if cue["type"] == "endgame":
        return {
            "kicker": None,
            "title": words["endgame"],
            "subtitle": None,
            "image": None,
        }
    if cue["type"] == "result":
        conflict = catalog(page, "conflicts", cue["conflict"])
        return {
            "kicker": words["round"].format(round=cue["round"]),
            "title": words["result"],
            "subtitle": words["conflict"].format(name=conflict["name"]),
            "image": conflict["image"],
        }
    if cue["type"] == "shield_wall":
        return {
            "kicker": None,
            "title": words["shield_wall"],
            "subtitle": None,
            "image": page.evaluate("iconUrl('shield_wall')"),
        }
    if cue["type"] == "final":
        winner = page.evaluate("state.summary.standings[0].player")
        leader = leader_of(page, winner)
        label = page.evaluate("(seat) => playerLabel(seat)", winner)
        return {
            "kicker": words["game_over"],
            "title": words["final"],
            "subtitle": words["winner"].format(name=f"{leader['name']} · {label}"),
            "image": leader["image"],
        }
    leader = leader_of(page, cue["seat"])
    if cue["type"] == "sandworm":
        count = cue["count"]
        return {
            "kicker": page.evaluate("(seat) => playerLabel(seat)", cue["seat"]),
            "title": words["sandworm"]
            if count == 1
            else words["sandworms"].format(count=count),
            "subtitle": leader["name"],
            "image": page.evaluate("iconUrl('sandworm')"),
        }
    if cue["seat"] != 0:
        name = page.evaluate("(seat) => playerName(seat)", cue["seat"])
        return {
            "kicker": None,
            "title": words["other"].format(seat=cue["seat"] + 1),
            "subtitle": f"{leader['name']} · {name}",
            "image": leader["image"],
        }
    return {
        "kicker": None,
        "title": words["mine"],
        "subtitle": leader["name"],
        "image": leader["image"],
    }


def verify_drawn(page, pair: tuple[dict, dict], label: str) -> dict:
    """Draw a cue, read it back and check words, art, place and click-through.

    `pair` is the page's own cue (to draw) and its normalized reading."""
    full, cue = pair
    width = page.evaluate("document.documentElement.scrollWidth")
    page.evaluate(SHOW_JS, full)
    lang = page.evaluate("TERM_LANGUAGE")
    if cue["type"] in (
        "round", "combat", "result", "final", "sandworm", "shield_wall", "turn"
    ):
        page.wait_for_function(
            "() => { const i = el('phase-banner').querySelector('img');"
            " return !i || (i.complete && i.naturalWidth > 0); }"
        )
    info = page.evaluate(READ_JS)
    want = expected_words(page, cue, lang)
    got = {key: info[key] for key in ("kicker", "title", "subtitle", "image")}
    check.ok(
        got == want,
        f"{label}: {cue['type']} banner words and art ({lang})",
        (got, want),
    )
    if cue["type"] == "result":
        words = TITLES[lang]["ranks"]
        want_rows = [
            {"seat": seat, "rank": rank, "rankText": words[rank],
             "strength": str(strength), "mine": seat == 0}
            for seat, rank, strength, _ in cue["rows"]
        ]
        got_rows = [
            {**row, "strength": row["strength"].split(" ")[0]} for row in info["rows"]
        ]
        doubled = [row[3] == 2 for row in cue["rows"]]
        check.ok(
            got_rows == want_rows
            and [("×2" in row["strength"]) for row in info["rows"]] == doubled,
            f"{label}: the result board lists the logged standing ({lang})",
            (info["rows"], want_rows),
        )
    if cue["type"] == "final":
        ranks = TITLES[lang]["final_ranks"]
        standings = page.evaluate("state.summary.standings")
        want_rows = [
            {"seat": e["player"], "rank": e["rank"], "rankText": ranks[e["rank"]],
             "strength": str(e["victory_points"]), "mine": e["player"] == 0}
            for e in standings
        ]
        got_rows = [
            {**row, "strength": row["strength"].split(" ")[0]} for row in info["rows"]
        ]
        check.ok(
            got_rows == want_rows,
            f"{label}: the final board lists the standings ({lang})",
            (info["rows"], want_rows),
        )
    boards = ("result", "final")
    clicks = ("through", "hitOutside") if cue["type"] not in boards else ()
    placed = {
        key: info[key] for key in ("fits", "overBoard", "clearOfSide", *clicks)
    }
    if cue["type"] in boards:
        placed["takesClicks"] = info["takesClicks"]
    placed["noOverflow"] = (
        page.evaluate("document.documentElement.scrollWidth") == width
    )
    check.ok(all(placed.values()), f"{label}: {cue['type']} banner placement", placed)
    return info


def walk(page) -> dict:
    """Play the seeded game to the end, checking every step's banners."""
    seen: dict[str, tuple[dict, dict]] = {}
    rerendered = False
    turn_end_due = True
    turns = 0
    others = 0
    mismatches = 0
    for _ in range(3000):
        assert settled(page, 30)
        before = page.evaluate("state.log.count")
        if page.evaluate("state.summary.finished"):
            break
        if page.evaluate("state.summary.confirmation === state.viewSeat"):
            page.evaluate("confirmTurn()")
        elif page.evaluate("Boolean(state.actions && state.actions.actions.length)"):
            page.evaluate(f"applyAction({page.evaluate(CHOOSE_JS)})")
        else:
            time.sleep(0.05)
            continue
        assert settled(page, 30)
        pending = page.evaluate(PENDING_JS)
        fulls = page.evaluate(
            "[phaseBanner.current, ...phaseBanner.queue].filter(Boolean)"
        )
        expected = page.evaluate(EXPECTED_JS, before)
        turn = page.evaluate(TURN_JS, before)
        turn_end_due = turn_end_due or turn["ended"]
        if turn["start"] and turn_end_due:
            expected.append(
                {
                    "type": "turn",
                    "round": None,
                    "conflict": None,
                    "item": None,
                    "seat": 0,
                    "rows": None,
                    "count": None,
                }
            )
            turn_end_due = False
            turns += 1
        if pending != expected:
            mismatches += 1
            check.ok(
                False,
                "pending banners match the step's public events",
                (pending, expected),
            )
            if mismatches > 3:
                break
        for full, cue in zip(fulls, pending, strict=True):
            if cue["type"] == "round":
                check.ok(
                    cue["round"] == page.evaluate("state.summary.round_number"),
                    f"round banner {cue['round']} is the summary's round",
                )
            other = cue["type"] == "turn" and cue["seat"] != 0
            kind = "other" if other else cue["type"]
            if kind == "other":
                others += 1
            if kind not in seen:
                seen[kind] = (full, cue)
                verify_drawn(page, (full, cue), "live 1366x768")
        if pending and pending[-1]["type"] == "turn" and not rerendered:
            rerendered = True
            page.evaluate("phaseBanner.current = null; phaseBanner.queue = []")
            page.evaluate("render(); render({foreign: true})")
            check.ok(
                page.evaluate(
                    "phaseBanner.current === null && !phaseBanner.queue.length"
                ),
                "re-rendering at a turn start never queues it again",
            )
        page.evaluate("clearPhaseBanner()")
    check.ok(page.evaluate("state.summary.finished"), "the seeded game reaches its end")
    check.ok(mismatches == 0, "every step's banners matched its public events")
    check.ok(rerendered, "a turn start was re-rendered without queueing it again")
    check.ok(turns >= 5, f"seat 0's turn starts were announced ({turns})")
    check.ok(others >= 30, f"the AI seats' turns were announced ({others})")
    for kind in (
        "round", "combat", "result", "scouts", "endgame", "final", "turn", "other"
    ):
        check.ok(kind in seen, f"the walk met a {kind} banner")
    print(f"  (the walk also met: {sorted(set(seen) & {'sandworm', 'shield_wall'})})")
    return seen


def turn_lifecycle(page) -> None:
    """A real turn start: language switch, reload and leaving."""
    # Play on to the next own turn start and catch its banner live (the AI
    # turns queued before it are dropped, to put it on screen now).
    own = "(c) => c && c.type === 'turn' && c.source === 'summary'"
    for _ in range(400):
        assert settled(page, 30)
        if page.evaluate(f"[phaseBanner.current, ...phaseBanner.queue].some({own})"):
            page.evaluate(f"""() => {{
              phaseBanner.queue = phaseBanner.queue.filter({own});
              if (!({own})(phaseBanner.current)) hidePhaseBanner();
              playEffects.queue = []; hidePlayEffect(); advanceEffects();
            }}""")
            break
        page.evaluate("clearPhaseBanner()")
        if page.evaluate("state.summary.confirmation === state.viewSeat"):
            page.evaluate("confirmTurn()")
        else:
            page.evaluate(f"applyAction({page.evaluate(CHOOSE_JS)})")
    page.evaluate("clearTimeout(phaseBanner.timer)")
    current = page.evaluate("JSON.stringify(phaseBanner.current)")
    check.ok(
        page.evaluate("phaseBanner.current.type") == "turn", "a live turn start shows"
    )
    queued = page.evaluate("phaseBanner.queue.length")
    page.evaluate("setLanguage('en')")
    settled(page)
    page.evaluate("clearTimeout(phaseBanner.timer)")
    check.ok(
        page.evaluate("JSON.stringify(phaseBanner.current)") == current
        and page.evaluate("phaseBanner.queue.length") == queued
        and page.inner_text("#phase-banner .phase-banner-title") == "Your turn",
        "a language switch redraws the turn banner in English without requeueing",
    )
    page.evaluate("setLanguage('ko')")
    settled(page)
    page.evaluate("window.__banners = []")
    page.reload()
    page.wait_for_function("state.view !== null && refreshFlight === null")
    page.evaluate("render(); render({foreign: true})")
    time.sleep(0.3)
    check.ok(
        page.is_hidden("#phase-banner")
        and page.evaluate("phaseBanner.current === null && !phaseBanner.queue.length")
        and page.evaluate("window.__banners.length") == 0,
        "a reload at a turn start does not show it again",
    )
    check.ok(
        page.evaluate("state.summary.decision.kind === 'turn'"),
        "the reload happened at the turn start itself",
    )


KINDS_TO_LOOK = (
    "round", "combat", "result", "scouts", "endgame", "final", "sandworm",
    "shield_wall", "turn", "other",
)


def look(page, seen: dict, tag: str) -> None:
    """Every banner kind in both languages and three window sizes."""
    for lang in ("ko", "en"):
        page.evaluate("(lang) => setLanguage(lang)", lang)
        settled(page)
        for size in SIZES:
            page.set_viewport_size(size)
            page.evaluate("fitActionLog()")
            kinds = [kind for kind in KINDS_TO_LOOK if kind in seen]
            for kind in kinds:
                width = f"{size['width']}x{size['height']}"
                info = verify_drawn(page, seen[kind], f"{tag} {width}")
                if kind == "other":
                    # Visible seat numbers are one-based (i18n.js seatNumber).
                    seat = seen[kind][1]["seat"]
                    check.ok(
                        info["seat"] == str(seat)
                        and not info["mine"]
                        and info["hidden"] == "true"
                        and info["color"].lower()
                        == page.evaluate(f"SEAT_COLORS[{seat}]").lower(),
                        f"an AI seat's turn banner in its colour ({lang} {width})",
                        info,
                    )
                if kind == "turn":
                    check.ok(
                        info["mine"]
                        and info["hidden"] == "true"
                        and info["titleSize"] >= 35,
                        f"the own turn banner stands out, unannounced ({lang})",
                        info,
                    )
                if kind == "round" and size["width"] == 1366:
                    check.ok(
                        info["live"] == "polite"
                        and info["hidden"] is None
                        and 34 <= info["titleSize"] <= 42
                        and 35 < info["z"] < 40,
                        f"phase banners: announced, big, under zoom/help ({lang})",
                        info,
                    )
                page.screenshot(path=f"{SHOTS}/{kind}_{lang}_{width}.png")
    page.evaluate("clearPhaseBanner()")
    page.set_viewport_size(LAPTOP_VIEWPORT)
    page.evaluate("setLanguage('ko')")
    settled(page)
    page.emulate_media(reduced_motion="reduce")
    page.evaluate(SHOW_JS, seen["round"][0])
    motion = page.evaluate("""() => {
      const animations = el('phase-banner').getAnimations({subtree: true});
      return {names: animations.map((a) => a.animationName),
        moves: animations.some((a) => a.effect.getKeyframes()
          .some((k) => 'transform' in k || 'translate' in k || 'scale' in k))};
    }""")
    check.ok(
        motion["names"] == ["phase-banner-fade"] and not motion["moves"],
        "reduced motion only fades the banner",
        motion,
    )
    page.emulate_media(reduced_motion="no-preference")
    page.evaluate("clearPhaseBanner()")
    # The result board closes on a click on it, or on Escape; a band never
    # takes the click.
    for how in ("click", "Escape"):
        page.evaluate(
            """(cue) => { phaseBanner.queue = [cue]; hidePhaseBanner();
              playEffects.queue = []; hidePlayEffect(); advanceEffects(); }""",
            seen["result"][0],
        )
        check.ok(page.is_visible("#phase-banner .phase-banner.result"), "result shows")
        if how == "click":
            page.click("#phase-banner .phase-banner.result")
        else:
            page.keyboard.press("Escape")
        check.ok(
            page.is_hidden("#phase-banner")
            and page.evaluate("phaseBanner.current === null"),
            f"the result board closes on {how}",
        )


# The banners that sound (sounds.js PHASE_SOUNDS), user request 2026-10-11:
# "라운드 시작 / 전투 단계 시작 / 아라킨 스카웃 이때도 소리 들어가면 좋겠는데".
def sounds(page) -> None:
    """The walk draws its banners directly (SHOW_JS), so the sounds are
    checked here through the page's own queue: the game's real cues, one of
    each kind, each started by nextPhaseBanner as advanceEffects does."""
    page.evaluate("window.__sounds = []")
    heard = page.evaluate(
        """() => {
          const cues = phaseBannerCues(state.log.entries, 0);
          const pick = ['round', 'combat', 'scouts', 'turn', 'endgame']
            .map((type) => cues.find((cue) => cue.type === type)).filter(Boolean);
          const kinds = pick.map((cue) => cue.type);
          for (const cue of pick) {
            phaseBanner.queue = [cue];
            nextPhaseBanner();
            clearTimeout(phaseBanner.timer);
          }
          hidePhaseBanner();
          return {kinds, sounds: window.__sounds.slice()};
        }"""
    )
    check.ok(
        {"round", "combat", "scouts", "turn"} <= set(heard["kinds"])
        and heard["sounds"] == ["round", "combat", "scouts"],
        "a Round, combat and Scouts banner each plays its own sound; a turn or"
        " the Endgame plays none",
        heard,
    )
    check.ok(
        "decision" not in page.evaluate("window.__sounds"),
        "a local table plays no decision sound",
    )
    played = page.evaluate(
        """() => ['decision', 'round', 'combat', 'scouts'].map((name) => {
          try { window.__playSound(name); return true; } catch (e) { return false; }
        })"""
    )
    check.ok(all(played), "every sound plays through the real Web Audio path", played)


def live(browser, base: str) -> None:
    print("[A] a seeded Scouts game, one human seat against three heuristic seats")
    context, page, rec = open_context(browser, "phase-banner", LAPTOP_VIEWPORT)
    context.add_init_script(RECORDER)
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    page.wait_for_function(
        "document.querySelectorAll('#seat-selects select').length === 4"
    )
    for seat in range(4):
        page.select_option(
            f"#seat-selects select[data-seat='{seat}']",
            "human" if seat == 0 else "heuristic",
        )
    set_rule_options(page, "choam")
    page.set_checked("#opt-leader-draft", True)
    page.set_checked("#opt-scouts", True)
    page.fill("#opt-seed", str(SEED))
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    check.ok(page.is_hidden("#phase-banner"), "joining a game is a quiet baseline")
    # A whole game first for the cues; a second one for the turn lifecycle.
    seen = walk(page)
    sounds(page)
    look(page, seen, "look")
    page.evaluate("leaveGame()")
    check.ok(page.is_hidden("#phase-banner"), "leaving the table clears the banner")
    create_game(page, base, humans=(0,), seed=SEED, options=("choam",))
    turn_lifecycle(page)
    bad = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
    # Leaving the table closes its doorbell stream on purpose.
    failed = [
        e
        for e in rec.events
        if e[1] == "reqfail" and not ("/events " in e[2] and "ERR_ABORTED" in e[2])
    ]
    check.ok(not bad and not failed, "no failed requests", (bad[:3], failed[:3]))
    context.close()


def remote(browser) -> None:
    print("[B] a remote room: the guest's turn start on both screens")
    from remote import seat_two_players

    with server("--remote", "--admin-key", KEY) as (base, _):
        host_context, host, _ = open_context(browser, "host", LAPTOP_VIEWPORT)
        guest_context, guest, _ = open_context(browser, "guest", LAPTOP_VIEWPORT)
        for context in (host_context, guest_context):
            context.add_init_script(RECORDER)
        game_id = seat_two_players(base, host, guest)
        pages = {0: host, 1: guest}
        found = False
        for _ in range(400):
            summary = host.evaluate(f"fetch('/games/{game_id}').then((r) => r.json())")
            if summary["finished"]:
                break
            decision = summary["decision"]
            if (
                summary["confirmation"] is None
                and decision["kind"] == "turn"
                and decision["owner"] == 1
            ):
                found = True
                break
            if isinstance(summary["confirmation"], int):
                pages[summary["confirmation"]].evaluate("confirmTurn()")
            else:
                pages[decision["owner"]].evaluate("applyAction(0)")
            now = host.evaluate(f"fetch('/games/{game_id}').then((r) => r.json())")
            wanted = [now["revision"], now["confirmation"], now["log_count"]]
            for page in pages.values():
                page.wait_for_function(
                    """(w) => !state.busy && refreshFlight === null && JSON.stringify(
                      [state.summary.revision, state.summary.confirmation,
                       state.summary.log_count]) === JSON.stringify(w)""",
                    arg=wanted,
                )
        check.ok(found, "the walk reached the guest's turn start")
        guests = "window.__banners.filter((b) => b.cue === 'turn' && b.seat === '1')"
        for page in pages.values():
            page.wait_for_function(f"() => {guests}.length > 0", timeout=15000)
        host_turns = host.evaluate(guests)
        guest_turns = guest.evaluate(guests)
        check.ok(
            host_turns[-1]["seat"] == "1"
            and host_turns[-1]["title"] == "플레이어2 차례"
            and not host_turns[-1]["mine"],
            "the host sees the guest's turn as another player's",
            host_turns,
        )
        check.ok(
            guest_turns[-1]["seat"] == "1"
            and guest_turns[-1]["title"] == "내 차례"
            and guest_turns[-1]["mine"],
            "the guest sees its own turn",
            guest_turns,
        )
        check.ok(
            host.evaluate("window.__banners.some((b) => b.cue === 'round')"),
            "the round 1 reveal after the Leader draft shows on the host's screen",
        )
        check.ok(
            host.evaluate("window.__sounds.includes('round')"),
            "the host's round 1 banner, shown by the live queue, sounds",
            host.evaluate("window.__sounds"),
        )
        check.ok(
            guest.evaluate("window.__sounds.includes('decision')"),
            "a decision coming to the guest's seat plays the decision sound",
            guest.evaluate("window.__sounds"),
        )
        host_context.close()
        guest_context.close()


def playback(browser, base: str) -> None:
    print("[C] AI-only playback")
    context, page, _ = open_context(browser, "phase-banner-replay")
    context.add_init_script(RECORDER)
    create_game(page, base, humans=(), seed=11)
    page.wait_for_function("state.review !== null && playback.playing")
    page.wait_for_selector("#phase-banner:not([hidden])", timeout=30000)
    kinds = page.evaluate("window.__banners.map((b) => b.cue)")
    check.ok(kinds and kinds[0] == "round", "AI-only playback opens on a round", kinds)
    page.wait_for_function(
        "() => window.__banners.some((b) => b.cue === 'turn')", timeout=30000
    )
    turns = page.evaluate("window.__banners.filter((b) => b.cue === 'turn')")
    check.ok(
        all(not b["mine"] and b["title"].endswith("차례") for b in turns),
        "AI-only playback announces each turn as another player's",
        turns,
    )
    check.ok(
        page.evaluate("window.__sounds.length") == 0,
        "a review plays no sound",
        page.evaluate("window.__sounds"),
    )
    page.evaluate("stopPlayback()")
    check.ok(page.is_hidden("#phase-banner"), "pausing playback clears the banners")
    page.evaluate("window.__banners = []")
    page.evaluate("reviewSeek(state.review.meta.step_count)")
    page.wait_for_function("state.review.cursor === state.review.meta.step_count")
    time.sleep(0.3)
    check.ok(
        page.is_hidden("#phase-banner")
        and page.evaluate("window.__banners.length") == 0,
        "a manual seek shows no past banners",
    )
    context.close()


def main() -> None:
    with server() as (base, _), chrome() as browser:
        live(browser, base)
        playback(browser, base)
        remote(browser)
    print(f"screenshots in {SHOTS}")
    check.finish()


if __name__ == "__main__":
    main()
