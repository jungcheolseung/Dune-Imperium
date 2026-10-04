"""E2E of the greyed-out choices of the whole game (user request 2026-09-29).

An option the seat cannot take right now is shown, not selectable, with the
reason, and becomes selectable as soon as it can be taken (and the reverse):
Arrakeen Scouts lines already did (scouts.py); the server's `unavailable`
payload (display/unavailable.py) does it for the rest of the game. One human
seat (0) plays seeded games against three heuristic seats until it has met
both of these, and the page must show:

- a Reveal with cards it cannot afford: one greyed-out row per `acquire`
  row of the payload, under the rows of exactly the legal acquisitions;
- an Intrigue card it holds but cannot play in an open Intrigue window: one
  greyed-out row per `intrigue` row of the payload;
- for each: every row says why (a badge), is announced as a disabled button
  and is not an action row, and a click on it changes nothing; no payload
  row is a legal action; in English the action list carries no Hangul;
- the table: every card the payload dims (`refs`) is dimmed wherever it is
  drawn, with the reason in its title, only those, and never a lit one.

The seat takes the first legal action (not a graft switch), so it buys what
the first row offers and plays along; the seeds were picked to meet an
unplayable Intrigue card early.

A third case covers the "choice" surface, a branch of an open choice the
seat cannot take: Desert Power revealed without Maker Hooks opens its
choice with only the Persuasion branch legal and the sandworm branch greyed
out, "{maker_hooks} 없음" (option (B), user ruling 2026-09-30). A first-row
seat almost never buys Desert Power, so this checkout's own engine plays
seat 0 with a heuristic to that point and saves the game
(`SAVE_AT_ROW_PY`); the page loads the save and must show the row under
its own heading, beside the legal Persuasion branch, and drop it once the
Persuasion branch is taken. A fourth case, on the same surface, is
Imperial Privilege with no other Agent to recall: the recall greys out,
"소환할 다른 {agent} 없음", beside the confirm the seat now takes itself
(`resolve_imperial_privilege_without_recall`, user ruling 2026-09-30,
"결정 창 없이 자동으로 넘어가는 곳도 모두 결정 창을 연다"), and goes once the
confirm is taken.

The last case is the first "choice" window a human answers inside another
seat's open Agent turn: Holy War's unit loss (user ruling 2026-09-30,
OQ-036 (a), "선택지가 단 하나여도 어쨌든 확인을 거치는 걸로 통일하는게
깔끔해"), on a --remote server with the card player and the answering
seat held by two browsers. Twice: an opponent with no unit at all, who is
offered only the confirm (`resolve_unit_loss_without_unit`) beside rows
that all read "잃을 유닛 없음", and an opponent with a single unit to lose,
whose other zones grey out as "{garrison}에 {troop} 없음" and the like, the
terms substituted on the page. Until that seat answers, the card player's
page shows no turn-end control and none of the answering seat's rows; the
answer is not held for a turn end of the answering seat's own, and gives
the card player back its "턴 종료" (OQ-095, server ``INTERRUPT_KINDS``).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

from common import REPO, Check, chrome, open_context, server, set_rule_options
from open_mode import settled

check = Check()
SEEDS = (3, 8, 13, 21)
HANGUL = re.compile(r"[가-힣]")

CHOOSE_JS = """(() => {
  const actions = state.actions.actions;
  const other = actions.findIndex((a) => a.action_id !== "switch_graft_card");
  return other >= 0 ? other : 0;
})()"""

# The payload rows of one surface against the greyed-out rows on the page.
ROWS_JS = """(surface) => {
  const info = state.actions.unavailable;
  const rows = info ? info.rows.filter((r) => r.surface === surface) : [];
  const same = (a, b) => a.action_id === b.action_id
    && JSON.stringify(a.arguments) === JSON.stringify(b.arguments);
  const grey = [...document.querySelectorAll(
    `#actions .unavailable-item[data-surface="${surface}"]`)];
  return {
    payload: rows.map((r) => r.key),
    grey: grey.map((g) => g.dataset.key),
    badges: grey.map(
      (g) => (g.querySelector('.unavailable-badge') || {}).innerText || ''),
    aria: grey.every((g) => g.getAttribute('aria-disabled') === 'true'
      && g.getAttribute('role') === 'button' && !g.closest('.action-item')),
    legal: rows.filter((r) => state.actions.actions.some((a) => same(a, r.action)))
      .map((r) => r.key),
  };
}"""

# The legal acquisitions against their ordinary action rows.
BUYS_JS = """(() => {
  const legal = state.actions.actions.filter((a) => a.action_id.startsWith('acquire'))
    .map((a) => a.index).sort((a, b) => a - b);
  const rows = [...document.querySelectorAll('#actions .action-item')]
    .map((r) => Number(r.dataset.index)).filter((i) => legal.includes(i))
    .sort((a, b) => a - b);
  return { legal, rows };
})()"""

# The dimmed table cards against the payload's refs.
REFS_JS = """(() => {
  const refs = (state.actions.unavailable || {}).refs || {};
  const cards = [...document.querySelectorAll('.vcard')];
  const blocked = cards.filter((c) => c.classList.contains('blocked'));
  return {
    refs: Object.keys(refs),
    stray: blocked.filter((c) => !(c.dataset.instance in refs))
      .map((c) => c.dataset.instance),
    undimmed: cards.filter((c) => c.dataset.instance in refs
      && !c.classList.contains('blocked')).map((c) => c.dataset.instance),
    lit: blocked.filter((c) => c.classList.contains('legal')).length,
    untitled: blocked.filter((c) => !c.title.includes(' — ')).length,
    shown: blocked.length,
  };
})()"""


def create(page, base: str, seed: int) -> None:
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(
            f"#seat-selects select[data-seat='{seat}']",
            "human" if seat == 0 else "heuristic",
        )
    set_rule_options(page, "choam", "immortality")
    page.set_checked("#opt-leader-draft", False)
    page.fill("#opt-seed", str(seed))
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")


def has_rows(page, surface: str) -> bool:
    return page.evaluate(
        "(surface) => Boolean(state.actions.unavailable"
        " && state.actions.unavailable.rows.some((r) => r.surface === surface))",
        surface,
    )


def inspect_surface(page, surface: str, label: str) -> bool:
    """The greyed-out rows of `surface` are the payload's, each says why,
    none is legal, a click changes nothing, English has no Hangul."""

    rows = page.evaluate(ROWS_JS, surface)
    ok = check.ok(
        rows["grey"] == rows["payload"] and rows["payload"] and rows["aria"],
        f"{label}: one greyed-out row per payload row, a disabled button",
        rows,
    )
    ok &= check.ok(
        all(badge.strip() for badge in rows["badges"]),
        f"{label}: each greyed-out row says why",
        rows["badges"],
    )
    ok &= check.ok(not rows["legal"], f"{label}: no greyed-out row is legal", rows)
    revision = page.evaluate("state.summary.revision")
    # force: the row is announced as a disabled button (aria-disabled), so
    # Playwright would wait for it to be enabled; the click must still land.
    page.click(
        f'#actions .unavailable-item[data-surface="{surface}"] >> nth=0', force=True
    )
    time.sleep(0.3)
    assert settled(page, 10)
    ok &= check.ok(
        page.evaluate("state.summary.revision") == revision
        and page.evaluate("document.getElementById('game-error').hidden"),
        f"{label}: a click on a greyed-out row changes nothing",
    )
    page.evaluate("setLanguage('en')")
    assert settled(page, 10)
    english = page.evaluate("document.getElementById('actions').innerText")
    count = page.evaluate(
        "(surface) => document.querySelectorAll("
        "`#actions .unavailable-item[data-surface=\"${surface}\"]`).length",
        surface,
    )
    ok &= check.ok(
        not HANGUL.search(english) and count == len(rows["grey"]),
        f"{label}: in English the greyed-out rows carry no Hangul",
        HANGUL.findall(english)[:10],
    )
    page.evaluate("setLanguage('ko')")
    assert settled(page, 10)
    return ok


def inspect_refs(page, label: str) -> bool:
    refs = page.evaluate(REFS_JS)
    return check.ok(
        refs["shown"] > 0
        and not refs["stray"]
        and not refs["undimmed"]
        and refs["lit"] == 0
        and refs["untitled"] == 0,
        f"{label}: the table dims exactly the payload's cards, each with its reason",
        refs,
    )


def inspect(page, seen: dict[str, bool]) -> None:
    if not seen.get("acquire") and has_rows(page, "acquire"):
        buys = page.evaluate(BUYS_JS)
        ok = check.ok(
            buys["legal"] == buys["rows"],
            "Reveal: the cards it can buy are the rows of exactly the legal buys",
            buys,
        )
        ok &= inspect_surface(page, "acquire", "Reveal")
        ok &= inspect_refs(page, "Reveal")
        seen["acquire"] = ok
    if not seen.get("intrigue") and has_rows(page, "intrigue"):
        ok = inspect_surface(page, "intrigue", "Intrigue")
        ok &= inspect_refs(page, "Intrigue")
        seen["intrigue"] = ok


def play(page, seen: dict[str, bool], limit: int = 1500) -> None:
    for _ in range(limit):
        assert settled(page, 30)
        if page.evaluate("state.summary.finished") or all(
            seen.get(key) for key in ("acquire", "intrigue")
        ):
            return
        if page.evaluate("state.summary.confirmation === state.viewSeat"):
            page.evaluate("confirmTurn()")
            continue
        if not page.evaluate("Boolean(state.actions && state.actions.actions.length)"):
            time.sleep(0.05)
            continue
        inspect(page, seen)
        page.evaluate(f"applyAction({page.evaluate(CHOOSE_JS)})")


# Seat 0 (human) played by a heuristic in this checkout until the payload
# carries the row whose key is the last argument (the row itself, not just
# its surface: since the Imperial Privilege confirm, 2026-10-02, the
# "choice" surface has more than one kind of row); that game is saved into
# the server's saves directory. The seeds are tried in order, so a rule
# change that moves a game only moves the case to a later seed: today seed
# 5 of the base game reaches Desert Power without Maker Hooks, and seed 0
# an Imperial Privilege with no other Agent to recall.
SAVE_AT_ROW_PY = """
import json, sys
from pathlib import Path
from dune_imperium.agents import make_agent
from dune_imperium.server.persistence import SaveStore
from dune_imperium.server.sessions import GameSessionManager
saves, seeds = Path(sys.argv[1]), range(int(sys.argv[2]), int(sys.argv[3]))
key = sys.argv[4]
for seed in seeds:
    manager = GameSessionManager()
    seats = ("human", "heuristic", "heuristic", "heuristic")
    game_id = str(manager.create_game(seats, game_seed=seed)["game_id"])
    session = manager._get(game_id)
    agent = make_agent("heuristic", seed, session.config)
    while not (summary := manager.summary(game_id))["finished"]:
        if summary["confirmation"] == 0:
            manager.confirm_turn(game_id, 0, int(summary["revision"]))
            continue
        payload = manager.legal_actions(game_id, 0)
        rows = (payload["unavailable"] or {}).get("rows", [])
        if any(row["key"] == key for row in rows):
            document = manager.save_document(game_id, name=key)
            stored = SaveStore(saves).write(document)
            print(json.dumps({"seed": seed, "save_id": stored["save_id"]}))
            sys.exit(0)
        legal = session.engine.legal_actions(session.state, 0)
        view = session.engine.observe(session.state, 0)
        index = legal.index(agent.choose_action(view, legal))
        manager.apply_action(game_id, 0, int(payload["revision"]), index)
print(json.dumps(None))
"""

HEADING_JS = """(surface) => {
  const row = document.querySelector(
    `#actions .unavailable-item[data-surface="${surface}"]`);
  let node = row && row.previousElementSibling;
  while (node && node.classList.contains('unavailable-item')) {
    node = node.previousElementSibling;
  }
  return node && node.classList.contains('unavailable-heading')
    ? node.textContent : null;
}"""


# A node's words with each icon as its name (an icon is an <img> whose alt
# is the term), so "{maker_hooks} 없음" reads "메이커 작살 없음".
WORDS_OF_JS = """(selector) => {
  const node = document.querySelector(selector);
  const walk = (n) => n.nodeType === 3 ? n.textContent
    : n.tagName === 'IMG' ? n.alt : [...n.childNodes].map(walk).join('');
  return node ? walk(node).replace(/ +/g, ' ').trim() : null;
}"""
BADGE = '#actions .unavailable-item[data-surface="choice"] .unavailable-badge'


def save_at_row(saves: Path, key: str) -> dict | None:
    result = subprocess.run(
        [
            str(REPO / ".venv/bin/python"),
            "-c",
            SAVE_AT_ROW_PY,
            str(saves),
            "0",
            "8",
            key,
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO,
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def load_saved(page, base: str, found: dict) -> None:
    response = page.request.post(f"{base}/saves/{found['save_id']}/load", data={})
    game_id = response.json()["game_id"]
    page.goto(f"{base}/#game={game_id}")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    assert settled(page, 10)


def choice_rows_left(page) -> int:
    return page.evaluate(
        "(surface) => document.querySelectorAll("
        '`#actions .unavailable-item[data-surface="${surface}"]`).length',
        "choice",
    )


def choice_reasons(page) -> list:
    return page.evaluate(
        "state.actions.unavailable.rows.filter((r) => r.surface === 'choice')"
        ".map((r) => [r.code, r.reason_ko])"
    )


def choice_case(page, base: str, saves: Path) -> bool:
    """Desert Power without Maker Hooks: the "choice" surface."""

    print("[choice] Desert Power revealed without Maker Hooks")
    found = save_at_row(saves, "choice:pay_reveal_water_for_sandworm")
    if not check.ok(found is not None, "a seed reaches Desert Power without hooks"):
        return False
    print(f"  .. seed {found['seed']}")
    load_saved(page, base, found)
    legal = page.evaluate("state.actions.actions.map((a) => a.action_id).sort()")
    ok = check.ok(
        page.evaluate("state.summary.decision.kind") == "reveal_choice"
        and legal == ["decline_reveal_sandworm", "defer_reveal_choice"],
        "Desert Power: the choice opens with the Persuasion branch legal",
        legal,
    )
    reason = choice_reasons(page)
    ok &= check.ok(
        reason == [["maker_hooks", "{maker_hooks} 없음"]],
        "Desert Power: the sandworm branch greys out for want of Maker Hooks",
        reason,
    )
    korean = (page.evaluate(HEADING_JS, "choice"), page.evaluate(WORDS_OF_JS, BADGE))
    ok &= check.ok(
        korean == ("지금 고를 수 없는 선택지", "메이커 작살 없음"),
        "Desert Power: the row sits under the choice heading, with its reason",
        korean,
    )
    ok &= inspect_surface(page, "choice", "Desert Power")
    page.evaluate("setLanguage('en')")
    assert settled(page, 10)
    english = (page.evaluate(HEADING_JS, "choice"), page.evaluate(WORDS_OF_JS, BADGE))
    ok &= check.ok(
        english == ("Choices you cannot take now", "No Maker Hooks"),
        "Desert Power: in English the heading and the reason",
        english,
    )
    page.evaluate("setLanguage('ko')")
    assert settled(page, 10)
    decline = page.evaluate(
        "state.actions.actions.findIndex("
        "(a) => a.action_id === 'decline_reveal_sandworm')"
    )
    page.evaluate(f"applyAction({decline})")
    assert settled(page, 20)
    left = choice_rows_left(page)
    ok &= check.ok(
        page.evaluate("state.summary.decision.kind") == "reveal" and left == 0,
        "Desert Power: the row goes with the choice once the Persuasion is taken",
        left,
    )
    return ok


def recall_case(page, base: str, saves: Path) -> bool:
    """Imperial Privilege with no other Agent to recall: the confirm."""

    print("[choice] Imperial Privilege with no other Agent to recall")
    found = save_at_row(saves, "choice:imperial_privilege_recall")
    if not check.ok(found is not None, "a seed reaches Imperial Privilege, no Agent"):
        return False
    print(f"  .. seed {found['seed']}")
    load_saved(page, base, found)
    confirm = "resolve_imperial_privilege_without_recall"
    legal = page.evaluate("state.actions.actions.map((a) => a.action_id)")
    ok = check.ok(
        page.evaluate("state.summary.decision.kind") == "agent_effects"
        and confirm in legal
        and not any(a.startswith("recall_") for a in legal),
        "Imperial Privilege: the confirm is offered and no recall",
        legal,
    )
    reason = choice_reasons(page)
    ok &= check.ok(
        reason
        == [["no_target", "소환할 다른 {agent} 없음 (이번 차례에 보낸 {agent} 제외)"]],
        "Imperial Privilege: the recall greys out for want of another Agent",
        reason,
    )
    korean = (page.evaluate(HEADING_JS, "choice"), page.evaluate(WORDS_OF_JS, BADGE))
    ok &= check.ok(
        korean
        == (
            "지금 고를 수 없는 선택지",
            "소환할 다른 에이전트 없음 (이번 차례에 보낸 에이전트 제외)",
        ),
        "Imperial Privilege: the row sits under the choice heading, with its reason",
        korean,
    )
    ok &= inspect_surface(page, "choice", "Imperial Privilege")
    page.evaluate("setLanguage('en')")
    assert settled(page, 10)
    english = (page.evaluate(HEADING_JS, "choice"), page.evaluate(WORDS_OF_JS, BADGE))
    ok &= check.ok(
        english
        == (
            "Choices you cannot take now",
            "No other Agent of yours to recall (not the one sent this turn)",
        ),
        "Imperial Privilege: in English the heading and the reason",
        english,
    )
    page.evaluate("setLanguage('ko')")
    assert settled(page, 10)
    index = page.evaluate(
        "(id) => state.actions.actions.findIndex((a) => a.action_id === id)", confirm
    )
    page.evaluate(f"applyAction({index})")
    assert settled(page, 20)
    after = page.evaluate("state.actions.actions.map((a) => a.action_id)")
    left = choice_rows_left(page)
    ok &= check.ok(
        confirm not in after and left == 0,
        "Imperial Privilege: the row goes once the confirm is taken",
        [left, after],
    )
    return ok


# Seats 0 and 1 (human) played by heuristics in this checkout, seats 2 and
# 3 by the server's own, on the Bloodlines ruleset, until one human seat
# must answer the Holy War the other human seat played, with the offer
# named by the last argument: "confirm" (no unit at all, only
# resolve_unit_loss_without_unit) or "single" (one lose_unit), greyed rows
# beside it either way. The answer must hand the card player its turn end
# straight away (the AI seats answer at once, no Spy to move, nothing else
# left of that Agent turn), or the seed is passed over. That game is saved
# before the answer. The seeds are tried in order from HOLY_WAR_SEEDS, as in
# SAVE_AT_ROW_PY: today seed 5 reaches the single loss and seed 243 the
# confirm (seat 0's Holy War, seat 1 answers, both; 283, 286 and 300 also
# do). The confirm starts at 243 only to spare the script the games before
# it; it was seed 56 until the 2026-10-04 rulings (codec v131) moved that
# game -- the case is rare (4 of seeds 0-399 qualify).
HOLY_WAR_SEEDS = {"confirm": 243, "single": 0}
HOLY_WAR_SAVE_PY = """
import json, sys
from pathlib import Path
from dune_imperium.agents import make_agent
from dune_imperium.server.persistence import SaveStore
from dune_imperium.server.sessions import GameSessionManager
saves, seeds = Path(sys.argv[1]), range(int(sys.argv[2]), int(sys.argv[3]))
want = sys.argv[4]
seats = ("human", "human", "heuristic", "heuristic")
offer = {"confirm": "resolve_unit_loss_without_unit", "single": "lose_unit"}[want]
for seed in seeds:
    manager = GameSessionManager()
    created = manager.create_game(seats, game_seed=seed, bloodlines=True)
    game_id = str(created["game_id"])
    session = manager._get(game_id)
    agents = [make_agent("heuristic", seed + seat, session.config) for seat in (0, 1)]
    while not (summary := manager.summary(game_id))["finished"]:
        if isinstance(summary["confirmation"], int):
            seat = summary["confirmation"]
            manager.confirm_turn(game_id, seat, int(summary["revision"]))
            continue
        seat = summary["decision"]["owner"]
        payload = manager.legal_actions(game_id, seat)
        owner = next(
            (
                frame.decision.owner
                for frame in reversed(session.state.decision_stack)
                if str(frame.kind) == "agent_effects"
            ),
            None,
        )
        ids = [action["action_id"] for action in payload["actions"]]
        if (
            summary["decision"]["kind"] == "opponent_unit_loss"
            and owner in (0, 1)
            and owner != seat
            and ids == [offer]
            and (payload["unavailable"] or {}).get("rows")
        ):
            document = manager.save_document(game_id, name=f"holy_war_{want}")
            answer = manager.apply_action(game_id, seat, int(payload["revision"]), 0)
            back = answer["decision"]
            if back["owner"] == owner and back.get("turn_end_ready") is True:
                stored = SaveStore(saves).write(document)
                found = {"seed": seed, "save_id": stored["save_id"]}
                print(json.dumps({**found, "owner": owner, "answerer": seat}))
                sys.exit(0)
            break
        legal = session.engine.legal_actions(session.state, seat)
        view = session.engine.observe(session.state, seat)
        index = legal.index(agents[seat].choose_action(view, legal))
        manager.apply_action(game_id, seat, int(payload["revision"]), index)
print(json.dumps(None))
"""

KEY = "e2e-admin-key"
# The Korean words of a greyed lose_unit row, by its key's zone and unit.
ZONE_KO = {"garrison": "주둔지", "conflict": "교전"}
UNIT_KO = {"0": "병력", "1": "사다우카 지휘관"}

# The words of every greyed "choice" badge, icons read as their names.
BADGE_WORDS_JS = """() => {
  const walk = (n) => n.nodeType === 3 ? n.textContent
    : n.tagName === 'IMG' ? n.alt : [...n.childNodes].map(walk).join('');
  return [...document.querySelectorAll(
    '#actions .unavailable-item[data-surface="choice"]')].map((row) => [
      row.dataset.key,
      walk(row.querySelector('.unavailable-badge')).replace(/ +/g, ' ').trim(),
    ]);
}"""

# What a seat's page holds: its view, its actions, its turn-end control.
TABLE_JS = """() => ({
  seat: state.viewSeat,
  kind: state.summary.decision ? state.summary.decision.kind : null,
  owner: state.summary.decision ? state.summary.decision.owner : null,
  ready: state.summary.decision ? state.summary.decision.turn_end_ready : null,
  confirmation: state.summary.confirmation,
  actions: state.actions ? state.actions.actions.map((a) => a.action_id) : null,
  greyed: document.querySelectorAll('#actions .unavailable-item').length,
  turnEnd: document.querySelectorAll('.turn-end-row button').length,
  revision: state.summary.revision,
})"""


def wait_for(page, predicate_js: str, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if page.evaluate(
            f"!state.busy && refreshFlight === null && Boolean({predicate_js})"
        ):
            return True
        time.sleep(0.05)
    return False


def holy_war_save(saves: Path, want: str) -> dict | None:
    result = subprocess.run(
        [str(REPO / ".venv/bin/python"), "-c", HOLY_WAR_SAVE_PY, str(saves)]
        + [str(HOLY_WAR_SEEDS[want]), str(HOLY_WAR_SEEDS[want] + 60), want],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO,
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def take_seat(page, base: str, game_id: str, seat: int, name: str) -> None:
    page.goto(f"{base}/#game={game_id}")
    page.wait_for_selector("#lobby-screen:not([hidden])")
    page.fill("#lobby-name", name)
    page.click(f"#lobby-seats li[data-seat='{seat}'] button")
    page.wait_for_selector("#game-screen:not([hidden])")


def holy_war_case(browser, base: str, saves: Path, want: str) -> bool:
    """Holy War's unit loss answered by a human inside another seat's turn."""

    label = f"Holy War ({want})"
    print(f"[choice] {label}: a human answers another human's Holy War")
    found = holy_war_save(saves, want)
    if not check.ok(found is not None, f"{label}: a seed reaches it"):
        return False
    owner, answerer = found["owner"], found["answerer"]
    print(f"  .. seed {found['seed']}: seat {owner} played it, {answerer} answers")
    _, host, _ = open_context(browser, f"holy-war-{want}-card-player")
    _, guest, _ = open_context(browser, f"holy-war-{want}-answering")
    host.goto(f"{base}/#admin={KEY}")
    host.wait_for_selector("#setup-screen:not([hidden])")
    host.wait_for_function("state.server !== null && state.server.admin === true")
    response = host.request.post(f"{base}/saves/{found['save_id']}/load", data={})
    game_id = response.json()["game_id"]
    take_seat(host, base, game_id, owner, "카드")
    take_seat(guest, base, game_id, answerer, "상대")
    ok = check.ok(
        wait_for(guest, "state.actions && state.actions.actions.length")
        and wait_for(host, f"state.viewSeat === {owner} && state.actions === null"),
        f"{label}: both pages reach the loss window",
        [host.evaluate(TABLE_JS), guest.evaluate(TABLE_JS)],
    )
    table = host.evaluate(TABLE_JS)
    ok &= check.ok(
        table["kind"] == "opponent_unit_loss"
        and table["owner"] == answerer
        and table["ready"] is False
        and table["turnEnd"] == 0
        and table["greyed"] == 0,
        f"{label}: the card player's page waits, no turn end, no greyed rows",
        table,
    )
    offer = "resolve_unit_loss_without_unit" if want == "confirm" else "lose_unit"
    rows = guest.evaluate(
        "[...document.querySelectorAll('#actions .action-item')]"
        ".map((r) => r.innerText)"
    )
    ok &= check.ok(
        guest.evaluate(TABLE_JS)["actions"] == [offer]
        and len(rows) == 1
        and (want != "confirm" or "잃을 유닛 없음 — 확인" in rows[0]),
        f"{label}: the answering seat is offered {offer} alone",
        rows,
    )
    reasons = guest.evaluate(
        "state.actions.unavailable.rows.map((r) => [r.key, r.reason_ko, r.reason])"
    )
    words = guest.evaluate(BADGE_WORDS_JS)
    if want == "confirm":
        expected = [[key, "잃을 유닛 없음"] for key, _, _ in reasons]
    else:
        expected = [
            [key, f"{ZONE_KO[key.split(':')[2]]}에 {UNIT_KO[key.split(':')[3]]} 없음"]
            for key, _, _ in reasons
        ]
    ok &= check.ok(
        bool(reasons) and words == expected,
        f"{label}: every greyed row says why, the terms substituted",
        [words, expected],
    )
    ok &= check.ok(
        guest.evaluate(HEADING_JS, "choice") == "지금 고를 수 없는 선택지",
        f"{label}: under the choice heading",
        guest.evaluate(HEADING_JS, "choice"),
    )
    ok &= inspect_surface(guest, "choice", label)
    guest.evaluate("setLanguage('en')")
    assert settled(guest, 10)
    english = guest.evaluate(BADGE_WORDS_JS)
    ok &= check.ok(
        english == [[key, reason] for key, _, reason in reasons]
        and guest.evaluate(HEADING_JS, "choice") == "Choices you cannot take now",
        f"{label}: in English the heading and the reasons",
        english,
    )
    guest.evaluate("setLanguage('ko')")
    assert settled(guest, 10)
    guest.evaluate("applyAction(0)")
    ok &= check.ok(
        wait_for(host, "state.actions && state.actions.actions.length")
        and wait_for(guest, "state.actions === null"),
        f"{label}: the answer reaches both pages",
        [host.evaluate(TABLE_JS), guest.evaluate(TABLE_JS)],
    )
    after = guest.evaluate(TABLE_JS)
    ok &= check.ok(
        after["confirmation"] is None and after["greyed"] == 0,
        f"{label}: the answer is not held as the answering seat's turn end",
        after,
    )
    table = host.evaluate(TABLE_JS)
    ok &= check.ok(
        table["kind"] == "agent_effects"
        and table["owner"] == owner
        and table["ready"] is True
        and "finish_agent_turn" in (table["actions"] or [])
        and table["turnEnd"] == 1,
        f"{label}: the card player gets its turn-end control back",
        table,
    )
    return ok


def main() -> None:
    with server() as (base, server_log), chrome() as browser:
        _, page, _ = open_context(browser, "unavailable")
        seen: dict[str, bool] = {}
        for seed in SEEDS:
            if all(seen.get(key) for key in ("acquire", "intrigue")):
                break
            print(f"[game] seed {seed}")
            create(page, base, seed)
            play(page, seen)
        for key in ("acquire", "intrigue"):
            check.ok(seen.get(key, False), f"met and checked: {key}")
        saves = Path(server_log).parent
        seen["choice"] = choice_case(page, base, saves)
        check.ok(seen["choice"], "met and checked: choice")
        seen["recall"] = recall_case(page, base, saves)
        check.ok(seen["recall"], "met and checked: the recall confirm")
        with server("--remote", "--admin-key", KEY) as (remote, remote_log):
            for want in ("confirm", "single"):
                saves = Path(remote_log).parent
                seen[want] = holy_war_case(browser, remote, saves, want)
                check.ok(seen[want], f"met and checked: Holy War ({want})")
    check.finish()


if __name__ == "__main__":
    sys.exit(main())
