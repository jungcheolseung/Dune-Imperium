"""E2E of the turn-start window (user decision 2026-10-14).

"At the start of your turn: ..." [Litany Against Fear card] [Withdrawn
card]: either play is only the turn's first action (OQ-095 (6)), and the
engine offers it among the turn's usual actions until the seat acts
otherwise. The page asks for it first and alone: while the seat's own legal
rows hold such a play (the server tags them ``turn_start``), its page shows
only those plays and "턴 시작 카드 쓰지 않음" / "Keep the turn-start card"
(static/turn.js). That button sends nothing; the turn's usual view follows
with the plays still in it. The window is a view of the owner's page alone:
no request, no log line, nothing another seat sees.

The position is real: ``fixtures/turn_start_window_saves.py`` saves seat 2's
turn start in round 6 of a seeded four-human game, holding Litany Against
Fear and Withdrawn with a Plot it may play instead, and records the steps to
seat 2's next turn start, where both plays are legal again.

- [A] Korean, one page holding every seat (open server): the window shows
  exactly the two plays and the button, the board, the hand and the rest
  offer nothing; the button sends no request at all and the staged Agent
  turn follows with the two plays among its other rows; a re-render, a
  poll, a language switch and a reload keep the window aside.
- [B] English: the window's words, no Hangul; picking Litany Against Fear
  posts exactly that row, and the turn passes.
- [C] Korean: picking Withdrawn posts exactly that row, and the turn passes.
- [D] Korean: put aside, then the Plot first: no window, both plays greyed
  out with "이번 차례에 이미 다른 행동을 했음"; a reload keeps it so; the
  undo goes back to the turn start, where the window stays aside; the
  recorded steps lead to seat 2's next turn, where the window opens again.
- [E] Blocked site data (localStorage throws): the window still works and
  stays aside through re-renders and polls of the same page.
- [F] Remote server: seat 2's owner and seat 0's player in two browsers, a
  seatless visitor in a third. Seat 0's page shows the plain turn-start
  wait (the engine's own prompt, no actions, no window); putting the window
  aside makes no request from any page and changes nothing on the others;
  the play itself then reaches every page as before.

Screenshots go to ``E2E_SHOTS_DIR`` (a temporary folder otherwise):
turn_start_window_{ko,en}.png, turn_start_dismissed_ko.png,
turn_start_greyed_ko.png, turn_start_next_turn_ko.png,
turn_start_other_seat_ko.png.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from common import (
    REPO,
    SERVER_LOG_COPY,
    Check,
    ServerProcess,
    chrome,
    open_context,
)
from open_mode import settled

check = Check()

SHOTS = Path(
    os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(prefix="dune-turn-start-")
)
HANGUL = re.compile("[가-힣]")
KEY = "e2e-admin-key"
KEPT_KEY = "dune.turnStartKept"
WINDOW_PROMPT = {
    "ko": "턴 시작 카드 사용, 또는 쓰지 않고 차례 시작",
    "en": "Play a turn-start card, or keep it and start your turn",
}
KEEP_TEXT = {"ko": "턴 시작 카드 쓰지 않음", "en": "Keep the turn-start card"}
GREYED_KO = "차례를 시작할 때만 사용 — 이번 차례에 이미 다른 행동을 했음"
# Paths of the play server's API, as common.short() writes them.
API = ("games", "saves", "auth", "whoami", "catalog")

# What the decision panel shows, read in one go.
PANEL_JS = """() => {
  const box = document.getElementById('actions');
  const buttons = [...box.querySelectorAll('button')]
    .filter((b) => !b.classList.contains('action-info'));
  return {
    window: Boolean(state.actions && state.actions.turnStartWindow),
    rows: [...box.querySelectorAll('.action-item[data-index]')]
      .map((n) => Number(n.dataset.index)),
    keep: [...box.querySelectorAll('.turn-start-keep button')]
      .map((b) => b.textContent),
    buttons: buttons.length,
    steps: box.querySelectorAll('.pick-steps').length,
    toggle: box.querySelectorAll('.action-list-toggle').length,
    greyed: box.querySelectorAll('.unavailable-item').length,
    turnEnd: document.querySelectorAll('.turn-end-row, .held-send-row').length,
    prompt: (document.querySelector('#decision-info .prompt') || {}).textContent,
    litSpaces: document.querySelectorAll('.hotspot.legal, .space-row.legal').length,
    litCards: [...new Set([...document.querySelectorAll('.vcard.legal')]
      .map((n) => n.dataset.instance))].sort(),
    offered: state.actions ? state.actions.actions.map((a) => a.index) : null,
    full: state.actions
      ? (state.actions.turnStartWindow
          ? state.actions.turnStartWindow.full.actions.length
          : state.actions.actions.length)
      : null,
    tagged: state.actions
      ? (state.actions.turnStartWindow
          ? state.actions.turnStartWindow.full : state.actions)
        .actions.filter((a) => a.turn_start === true).map((a) => a.index)
      : [],
    revision: state.summary.revision,
    owner: state.summary.decision ? state.summary.decision.owner : null,
    kind: state.summary.decision ? state.summary.decision.kind : null,
    seat: state.viewSeat,
  };
}"""


def run_fixture(saves: str) -> dict:
    output = subprocess.run(
        [
            str(REPO / ".venv/bin/python"),
            str(Path(__file__).parent / "fixtures/turn_start_window_saves.py"),
            saves,
        ],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(output)["turn-start"]


def record(page) -> list[tuple[str, str]]:
    """Every request the page starts, as (method, path), from that moment."""

    seen: list[tuple[str, str]] = []
    page.on(
        "request",
        lambda r: seen.append((r.method, r.url.split("://", 1)[-1].split("/", 1)[-1])),
    )
    return seen


def api_calls(seen, since: int) -> list[tuple[str, str]]:
    return [(m, p) for m, p in seen[since:] if p.split("?")[0].split("/")[0] in API]


def wait_for(page, predicate_js: str, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if page.evaluate(
            f"!state.busy && refreshFlight === null && Boolean({predicate_js})"
        ):
            return True
        time.sleep(0.05)
    return False


def panel(page) -> dict:
    return page.evaluate(PANEL_JS)


def open_save(browser, base: str, save_id: str, label: str, init_js: str = ""):
    """A fresh game from the save, on a page holding every seat (open
    server): the page follows the seat to move, seat 2 here."""

    context, page, rec = open_context(browser, label)
    if init_js:
        page.add_init_script(init_js)
    seen = record(page)
    page.goto(base + "/")
    page.wait_for_function("state.catalog !== null && state.server !== null")
    game_id = page.evaluate(
        """async (id) => {
          const summary = await api(`/saves/${id}/load`, { method: 'POST' });
          await openGame(summary.game_id);
          return summary.game_id;
        }""",
        save_id,
    )
    assert wait_for(page, "state.view && state.actions"), label
    return context, page, rec, seen, game_id


def row_click(page, index: int) -> None:
    page.locator(
        f"#actions .action-item[data-index='{index}'] > button:not(.action-info)"
    ).click()
    assert settled(page, 20)


def keep_click(page) -> None:
    page.locator("#actions .turn-start-keep button").click()


def check_window(page, fixture: dict, label: str, lang: str = "ko") -> None:
    shown = panel(page)
    plays = sorted(play["index"] for play in fixture["plays"])
    check.ok(
        shown["window"] and shown["seat"] == fixture["seat"]
        and shown["revision"] == fixture["revision"],
        f"{label}: seat {fixture['seat']}'s turn start opens the window",
        shown,
    )
    check.ok(
        sorted(shown["tagged"]) == plays and sorted(shown["offered"]) == plays,
        f"{label}: the server tags exactly the two plays, and only they are offered",
        (shown["tagged"], shown["offered"], plays),
    )
    check.ok(
        sorted(shown["rows"]) == plays
        and shown["keep"] == [KEEP_TEXT[lang]]
        and shown["buttons"] == len(plays) + 1,
        f"{label}: the panel holds the two plays and '{KEEP_TEXT[lang]}', nothing else",
        shown,
    )
    check.ok(
        shown["steps"] == 0 and shown["toggle"] == 0 and shown["greyed"] == 0
        and shown["turnEnd"] == 0,
        f"{label}: no staged turn, list toggle, greyed row or turn-end row",
        shown,
    )
    check.ok(
        shown["prompt"] == WINDOW_PROMPT[lang],
        f"{label}: the banner asks the window's question",
        shown["prompt"],
    )
    cards = sorted(play["card_id"] for play in fixture["plays"])
    check.ok(
        shown["litSpaces"] == 0 and shown["litCards"] == cards,
        f"{label}: no space is lit, and of the cards only the two",
        (shown["litSpaces"], shown["litCards"]),
    )


def scenario_dismiss(browser, base: str, fixture: dict) -> None:
    print("[A] Korean: the window, then put aside with no request")
    context, page, rec, seen, game_id = open_save(
        browser, base, fixture["save_id"], "ko-dismiss"
    )
    check_window(page, fixture, "A1")
    log_count = page.evaluate("state.summary.log_count")
    undo_count = page.evaluate("state.summary.undo_count")
    page.screenshot(path=str(SHOTS / "turn_start_window_ko.png"))

    # The rest of the table offers nothing while the window is up.
    full = page.evaluate(
        "state.actions.turnStartWindow.full.actions"
        ".filter((a) => a.action_id === 'agent_turn')"
        ".map((a) => [a.arguments.card_id, a.arguments.space_id])"
    )
    card, space = full[0]
    before = len(seen)
    clicked = page.evaluate(
        """([card, space]) => {
          const hand = document.querySelector(
            `.hand-cards .vcard[data-instance="${card}"]`);
          if (hand) hand.click();
          const spot = document.querySelector(`.hotspot[data-space="${space}"]`);
          if (spot) spot.click();
          return [Boolean(hand), Boolean(spot)];
        }""",
        [card, space],
    )
    time.sleep(0.5)
    shown = panel(page)
    check.ok(
        clicked == [True, True]
        and not api_calls(seen, before)
        and shown["window"]
        and page.evaluate("state.pick") is None,
        "A2: a click on a playable hand card and its space sends nothing, picks"
        " nothing, and the window stays",
        (clicked, api_calls(seen, before), shown["window"]),
    )
    page.keyboard.press("Escape")
    check.ok(panel(page)["window"], "A2: Escape does not put the window aside")

    # A turn-start card in the hand points at its row and plays nothing: a
    # one-click play would draw and pass the turn, where the same click
    # outside the window only picks the card (independent review
    # 2026-10-14).
    litany = page.evaluate(
        "state.actions.actions.find((a) => a.action_id === 'play_turn_start_card')"
        ".arguments.card_id"
    )
    before = len(seen)
    clicked = page.evaluate(
        """(card) => {
          const hand = document.querySelector(
            `.hand-cards .vcard[data-instance="${card}"]`);
          if (hand) hand.click();
          return Boolean(hand);
        }""",
        litany,
    )
    time.sleep(0.5)
    matched = page.evaluate(
        """(card) => [...document.querySelectorAll("#actions .action-item.action-match")]
          .some((item) => JSON.parse(item.dataset.refs || "[]").includes(card))""",
        litany,
    )
    check.ok(
        clicked
        and not api_calls(seen, before)
        and panel(page)["window"]
        and matched,
        "A2: a click on the Litany card in the hand sends nothing and points at"
        " its row",
        (clicked, api_calls(seen, before), matched),
    )
    page.keyboard.press("Escape")

    before = len(seen)
    keep_click(page)
    time.sleep(1.0)
    shown = panel(page)
    check.ok(
        not api_calls(seen, before),
        "A3: '턴 시작 카드 쓰지 않음' makes no request",
        seen[before:],
    )
    plays = sorted(play["index"] for play in fixture["plays"])
    check.ok(
        not shown["window"] and not shown["keep"] and shown["steps"] == 1
        and shown["offered"] is not None and len(shown["offered"]) == shown["full"],
        "A3: the staged Agent turn follows with the whole list",
        shown,
    )
    check.ok(
        all(index in shown["rows"] for index in plays),
        "A3: both plays stay among the turn's other rows",
        (shown["rows"], plays),
    )
    turn_prompt = page.evaluate("promptText(state.summary.decision.prompt)")
    check.ok(
        shown["prompt"] == turn_prompt == "에이전트 차례 또는 공개 차례 선택"
        and shown["litSpaces"] > 0,
        "A3: the turn's own prompt, and the spaces are lit again",
        (shown["prompt"], turn_prompt, shown["litSpaces"]),
    )
    key = f"{game_id}:{fixture['seat']}:{fixture['revision']}"
    stored = page.evaluate(f"JSON.parse(localStorage.getItem('{KEPT_KEY}') || '[]')")
    check.ok(key in stored, "A3: the turn is remembered in localStorage", stored)
    page.screenshot(path=str(SHOTS / "turn_start_dismissed_ko.png"))

    page.evaluate("render()")
    page.evaluate("refresh(null, { foreign: true })")
    assert settled(page, 10)
    check.ok(not panel(page)["window"], "A4: a re-render and a poll keep it aside")
    page.evaluate("setLanguage('en')")
    page.evaluate("setLanguage('ko')")
    check.ok(not panel(page)["window"], "A4: a language switch keeps it aside")
    page.reload()
    assert wait_for(page, "state.view && state.actions"), "A5 reload"
    shown = panel(page)
    check.ok(
        not shown["window"] and shown["steps"] == 1
        and shown["revision"] == fixture["revision"],
        "A5: after a reload the window stays aside for this turn",
        shown,
    )
    check.ok(
        page.evaluate("state.summary.log_count") == log_count
        and page.evaluate("state.summary.undo_count") == undo_count,
        "A5: the game's log and undo count are as they were before the window",
        (page.evaluate("state.summary.log_count"), log_count),
    )
    finish(context, rec, "A")


def scenario_pick(browser, base: str, fixture: dict, which: int, lang: str) -> None:
    play = sorted(fixture["plays"], key=lambda p: p["index"])[which]
    name = "Litany Against Fear" if which == 0 else "Withdrawn"
    tag = "B" if which == 0 else "C"
    print(f"[{tag}] {lang}: picking {name} from the window")
    context, page, rec, seen, _ = open_save(
        browser, base, fixture["save_id"], f"{lang}-pick-{which}"
    )
    if lang == "en":
        page.evaluate("setLanguage('en')")
        assert settled(page, 10)
    check_window(page, fixture, tag, lang)
    hint = page.inner_text("#actions .pick-hint")
    if lang == "en":
        text = page.inner_text("#decision-info") + page.inner_text("#actions")
        check.ok(
            not HANGUL.search(text) and "action list" in hint,
            f"{tag}: in English the window carries no Hangul",
            HANGUL.findall(text)[:5],
        )
        page.screenshot(path=str(SHOTS / "turn_start_window_en.png"))
    else:
        check.ok("행동 목록" in hint, f"{tag}: the hint says the list keeps it", hint)
    before = len(seen)
    row_click(page, play["index"])
    posts = [call for call in api_calls(seen, before) if call[0] == "POST"]
    check.ok(
        len(posts) == 1 and posts[0][1].endswith("/actions"),
        f"{tag}: one POST /actions",
        posts,
    )
    entries = page.evaluate(
        f"""state.log.entries.filter((e) => e.type === 'action' && !e.undone
             && e.actor === {fixture['seat']})"""
    )
    last = entries[-1]
    events = {event["kind"] for event in last["events"]}
    wanted = "turn_start_card_played" if which == 0 else "turn_passed"
    check.ok(
        last["action_id"] == play["action_id"]
        and last["arguments"]["card_id"] == play["card_id"]
        and wanted in events,
        f"{tag}: the log has exactly that play, and {wanted}",
        (last["action_id"], last["arguments"], sorted(events)),
    )
    summary = page.evaluate("state.summary")
    check.ok(
        summary["revision"] > fixture["revision"]
        and summary["confirmation"] is None
        and summary["decision"]["owner"] != fixture["seat"],
        f"{tag}: the turn passes to the next seat",
        (summary["revision"], summary["confirmation"], summary["decision"]),
    )
    finish(context, rec, tag)


def scenario_other_action(browser, base: str, fixture: dict) -> None:
    print("[D] Korean: the Plot first, then the undo, then the next turn")
    context, page, rec, seen, game_id = open_save(
        browser, base, fixture["save_id"], "ko-plot"
    )
    check_window(page, fixture, "D1")
    keep_click(page)
    plot = fixture["plot"]
    row_click(page, plot["index"])
    assert wait_for(page, f"state.summary.revision > {fixture['revision']}")
    assert wait_for(page, "state.actions")
    shown = panel(page)
    check.ok(
        shown["kind"] == "turn" and shown["owner"] == fixture["seat"]
        and not shown["window"] and shown["tagged"] == [],
        "D2: after the Plot the turn frame is back, with no window and no play",
        shown,
    )
    greyed = page.evaluate(
        """() => (state.actions.unavailable ? state.actions.unavailable.rows : [])
          .filter((r) => r.code === 'turn_started')
          .map((r) => [r.action.arguments.card_id, r.reason_ko, r.key])"""
    )
    cards = sorted(play["card_id"] for play in fixture["plays"])
    check.ok(
        sorted(card for card, _, _ in greyed) == cards
        and all(reason == GREYED_KO for _, reason, _ in greyed),
        "D2: both plays are greyed out as already past the turn's start",
        greyed,
    )
    badges = page.evaluate(
        """(keys) => keys.map((k) => {
          const row = document.querySelector(
            `#actions .unavailable-item[data-key="${CSS.escape(k)}"]`);
          return row ? row.innerText : null;
        })""",
        [key for _, _, key in greyed],
    )
    check.ok(
        all(badge and GREYED_KO in badge for badge in badges),
        "D2: the greyed rows say why on the page",
        badges,
    )
    page.screenshot(path=str(SHOTS / "turn_start_greyed_ko.png"))
    page.reload()
    assert wait_for(page, "state.view && state.actions"), "D3 reload"
    check.ok(not panel(page)["window"], "D3: no window after a reload either")

    if plot["undoable"]:
        before = len(seen)
        page.locator(".undo-row button").first.click()
        assert wait_for(page, f"state.summary.revision === {fixture['revision']}")
        assert wait_for(page, "state.actions")
        shown = panel(page)
        posts = [call for call in api_calls(seen, before) if call[0] == "POST"]
        check.ok(
            [path.rsplit("/", 1)[-1] for _, path in posts] == ["undo"],
            "D4: the undo is the one request",
            posts,
        )
        check.ok(
            sorted(shown["tagged"]) == sorted(p["index"] for p in fixture["plays"])
            and not shown["window"]
            and all(p["index"] in shown["rows"] for p in fixture["plays"]),
            "D4: back at the turn start the plays are legal again, and the window"
            " stays aside",
            shown,
        )
        row_click(page, plot["index"])
        assert wait_for(page, f"state.summary.revision > {fixture['revision']}")
    else:
        check.ok(False, "D4: the fixture's Plot can be taken back", plot)

    # The recorded steps to seat 2's next turn start.
    for kind, seat, *rest in fixture["steps"]:
        assert wait_for(page, "state.summary")
        if kind == "confirm":
            assert wait_for(page, f"state.summary.confirmation === {seat}")
            page.evaluate("confirmTurn()")
        else:
            assert wait_for(
                page, f"state.viewSeat === {seat} && state.actions"
            ), (kind, seat, rest)
            page.evaluate(f"applyAction({rest[0]})")
        assert settled(page, 20)
    assert wait_for(page, f"state.summary.revision === {fixture['next_revision']}")
    assert wait_for(page, "state.actions")
    shown = panel(page)
    nexts = sorted(play["index"] for play in fixture["next_plays"])
    check.ok(
        shown["window"] and shown["seat"] == fixture["seat"]
        and sorted(shown["offered"]) == nexts
        and sorted(shown["rows"]) == nexts
        and shown["keep"] == [KEEP_TEXT["ko"]],
        "D5: seat 2's next turn, the cards still playable, opens the window again",
        shown,
    )
    stored = page.evaluate(f"JSON.parse(localStorage.getItem('{KEPT_KEY}') || '[]')")
    check.ok(
        f"{game_id}:{fixture['seat']}:{fixture['revision']}" in stored
        and f"{game_id}:{fixture['seat']}:{fixture['next_revision']}" not in stored,
        "D5: only the earlier turn is remembered as put aside",
        stored,
    )
    page.screenshot(path=str(SHOTS / "turn_start_next_turn_ko.png"))
    finish(context, rec, "D")


BLOCK_STORAGE_JS = """
Object.defineProperty(window, 'localStorage', {
  configurable: true,
  get() { throw new DOMException('blocked', 'SecurityError'); },
});
"""


def scenario_blocked_storage(browser, base: str, fixture: dict) -> None:
    print("[E] blocked site data: the window still works on the page")
    context, page, rec, seen, _ = open_save(
        browser, base, fixture["save_id"], "blocked", BLOCK_STORAGE_JS
    )
    blocked = page.evaluate(
        "(() => { try { window.localStorage; return false; }"
        " catch { return true; } })()"
    )
    check.ok(blocked, "E1: localStorage throws on this page")
    check_window(page, fixture, "E1")
    before = len(seen)
    keep_click(page)
    time.sleep(0.5)
    check.ok(
        not panel(page)["window"] and not api_calls(seen, before),
        "E2: put aside, with no request",
    )
    page.evaluate("render()")
    page.evaluate("refresh(null, { foreign: true })")
    assert settled(page, 10)
    check.ok(
        not panel(page)["window"],
        "E2: a re-render and a poll keep it aside (kept in the page)",
    )
    check.ok(not rec.js_errors, "E2: no JS errors", rec.js_errors[:3])
    finish(context, rec, "E")


def take_seat(page, base: str, game_id: str, seat: int, name: str) -> None:
    page.goto(f"{base}/#game={game_id}")
    page.wait_for_selector("#lobby-screen:not([hidden])")
    page.fill("#lobby-name", name)
    page.click(f"#lobby-seats li[data-seat='{seat}'] button")
    page.wait_for_selector("#game-screen:not([hidden])")


OTHER_JS = """() => ({
  revision: state.summary.revision,
  logCount: state.summary.log_count,
  logLen: state.log ? state.log.entries.length : null,
  actions: state.actions,
  window: document.querySelectorAll('.turn-start-keep').length,
  banner: (() => {
    // The seat's running time ticks on its own (clock.js): left out.
    const info = document.getElementById('decision-info').cloneNode(true);
    info.querySelectorAll('[data-clock]').forEach((n) => n.remove());
    return info.textContent;
  })(),
  panel: document.getElementById('actions').innerHTML,
  prompt: (document.querySelector('#decision-info .meta') || {}).textContent,
  turnPrompt: state.summary.decision ? promptText(state.summary.decision.prompt) : null,
  rawPrompt: state.summary.decision ? state.summary.decision.prompt : null,
})"""


def scenario_remote(browser, base: str, fixture: dict) -> None:
    print("[F] remote: another seat's page and a seatless visitor see nothing")
    seat = fixture["seat"]
    other = 0 if seat != 0 else 1
    host_context, host, host_rec = open_context(browser, "remote-owner")
    guest_context, guest, guest_rec = open_context(browser, "remote-other")
    visit_context, visitor, visit_rec = open_context(browser, "remote-visitor")
    host.goto(f"{base}/#admin={KEY}")
    host.wait_for_function("state.server !== null && state.server.admin === true")
    response = host.request.post(f"{base}/saves/{fixture['save_id']}/load", data={})
    game_id = response.json()["game_id"]
    take_seat(host, base, game_id, seat, "주인")
    take_seat(guest, base, game_id, other, "상대")
    visitor.goto(f"{base}/#game={game_id}")
    visitor.wait_for_selector("#lobby-screen:not([hidden])")
    assert wait_for(host, "state.actions")
    assert wait_for(guest, f"state.summary.players[{seat}].claimed")
    check_window(host, fixture, "F1")
    plain = guest.evaluate(OTHER_JS)
    check.ok(
        plain["actions"] is None and plain["window"] == 0
        and plain["rawPrompt"] == "Choose an Agent turn or Reveal turn"
        and plain["prompt"] == plain["turnPrompt"],
        "F1: the other seat's page shows the engine's plain turn-start wait",
        plain,
    )
    guest.screenshot(path=str(SHOTS / "turn_start_other_seat_ko.png"))
    seen = {name: record(page) for name, page in
            (("owner", host), ("other", guest), ("visitor", visitor))}
    visitor_before = visitor.evaluate("JSON.stringify(state.summary)")
    keep_click(host)
    time.sleep(1.5)
    calls = {name: api_calls(rows, 0) for name, rows in seen.items()}
    check.ok(
        not any(calls.values()),
        "F2: putting it aside makes no request from any page",
        calls,
    )
    after = guest.evaluate(OTHER_JS)
    check.ok(after == plain, "F2: the other seat's page is unchanged", (plain, after))
    check.ok(
        visitor.evaluate("JSON.stringify(state.summary)") == visitor_before,
        "F2: the visitor's summary is unchanged",
    )
    litany = next(
        play for play in fixture["plays"] if play["action_id"] == "play_turn_start_card"
    )
    row_click(host, litany["index"])
    check.ok(
        wait_for(guest, f"state.summary.revision > {fixture['revision']}"),
        "F3: the play itself reaches the other seat's page",
    )
    entries = guest.evaluate(
        f"state.log.entries.filter((e) => e.actor === {seat} && e.type === 'action')"
    )
    check.ok(
        entries and entries[-1]["action_id"] == "play_turn_start_card",
        "F3: as the logged play_turn_start_card, as before",
        entries[-1:] if entries else entries,
    )
    for context, rec, name in (
        (host_context, host_rec, "F owner"),
        (guest_context, guest_rec, "F other"),
        (visit_context, visit_rec, "F visitor"),
    ):
        finish(context, rec, name)


def finish(context, rec, what: str) -> None:
    failed = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
    check.ok(not failed, f"{what}: no failed requests", failed[:5])
    context.close()


def main() -> None:
    saves = tempfile.mkdtemp(prefix="dune-turn-start-e2e-")
    fixture = run_fixture(saves)
    print(
        f"fixture: seat {fixture['seat']} round {fixture['round']} revision"
        f" {fixture['revision']}, plays {fixture['plays']}, Plot {fixture['plot']},"
        f" {len(fixture['steps'])} steps to revision {fixture['next_revision']}"
    )
    SHOTS.mkdir(parents=True, exist_ok=True)
    logs = []
    with chrome() as browser:
        server = ServerProcess(saves=saves).start()
        try:
            scenario_dismiss(browser, server.base, fixture)
            scenario_pick(browser, server.base, fixture, 0, "en")
            scenario_pick(browser, server.base, fixture, 1, "ko")
            scenario_other_action(browser, server.base, fixture)
            scenario_blocked_storage(browser, server.base, fixture)
        finally:
            server.stop()
            logs.append(server.log_path)
        remote = ServerProcess("--remote", "--admin-key", KEY, saves=saves).start()
        try:
            scenario_remote(browser, remote.base, fixture)
        finally:
            remote.stop()
            logs.append(remote.log_path)
    shutil.copy(logs[-1], SERVER_LOG_COPY)
    for log in logs:
        text = Path(log).read_text()
        check.ok(
            "Traceback" not in text and "ERROR" not in text,
            f"no server errors ({log})",
        )
    print(f"Screenshots: {SHOTS}")
    check.finish()


if __name__ == "__main__":
    main()
