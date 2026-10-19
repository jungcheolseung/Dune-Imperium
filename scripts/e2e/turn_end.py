"""E2E of the unified turn-end control (2026-09-24).

One press, EXACTLY one, ends a human seat's turn, whatever step closes it:
- a hold (server ``awaiting_confirmation``, ``summary.confirmation`` == the
  seat) renders the banner's turn-end row, its button calling
  ``confirmTurn()`` (POST /confirm);
- the seat's own explicit turn-end action (``EXPLICIT_TURN_END_IDS`` in
  render.js, mirroring ``EXPLICIT_TURN_ENDS`` in server/turn_end.py:
  ``finish_agent_turn``, ``finish_leader_draft``, ``finish_reveal``,
  ``pass_combat_intrigue``,
  ``pass_endgame_intrigue``, the Conflict-end window's
  ``decline_conflict_end_intrigue``, and Arrakeen Scouts'
  ``confirm_scouts_bid``)
  renders as that SAME row instead, its button
  applying that action directly (POST /actions) -- and never doubles as an
  item in any action list (the staged Agent turn's steps, its "or" list,
  the full-list toggle, the Reveal panel).

Both are `div.confirm-row.turn-end-row` with one button whose text ends in
"턴 종료 ▶" / "End turn ▶": this checks that the row is the one and only
turn-end control, in the one place, for every one of these steps, and that
pressing it is always a single request with no second step afterwards. It
also checks the row in English (no Hangul, "End turn ▶") at a hold and at
an explicit-end decision, and pass_endgame_intrigue's own label, once a
seed search (raw HTTP, no browser) finds one that reaches it. At
finish_agent_turn, pass_combat_intrigue and the English explicit end it
also checks that the row carries the shortfall badge of a warning on the
action (held Contract icons that fizzle with the turn, user ruling
2026-10-02, L2-Q4), worded from the payload in either language, with the
label unchanged (TURN_END_BADGE_JS). Last, (h) a Conflict-end window that
offers only "쓰지 않음" to one of two human seats (it opens on public facts,
OQ-103, 2026-10-09): the prompt reads for a seat with nothing to play, the
decline is the row "쓰지 않음 · 턴 종료 ▶" / "Decline · End turn ▶", one
click hands over, and the log shows no per-seat "offered" line. Then (i)
the same window for the one human seat of a game, which the server answers
for it (sessions.py _auto_decline_locked): at the seat's next decision the
Combat result and the AI moves after its last press still glow as new
(panels.js ownGlowFrom does not stop at the seat's own declines), and the
server's decline sits in a fold card.
"""

from __future__ import annotations

import json
import re
import shutil
import time
import urllib.request
from typing import Any

from common import SERVER_LOG_COPY, Check, chrome, open_context, server
from lang import switch as switch_language
from open_mode import create_game, settled
from turn_controls import COMBAT

check = Check()

# Mirrors EXPLICIT_TURN_END_IDS in render.js / EXPLICIT_TURN_ENDS in
# server/turn_end.py: kept as a plain Python set (not read off the page) so
# the raw-HTTP seed searches below, which never load the client, can also
# use it. tests/server/test_turn_end.py
# (test_every_copy_of_the_explicit_turn_end_ids_matches_the_server) keeps it
# equal to the server's set; it lacked confirm_scouts_bid until 2026-10-01.
EXPLICIT_TURN_END_IDS = {
    "finish_agent_turn",
    "finish_leader_draft",
    "finish_reveal",
    "pass_combat_intrigue",
    "pass_endgame_intrigue",
    # The Conflict-end window's "쓰지 않음" (OQ-103, 2026-10-09), and its
    # "끝내기" after a play (2026-10-18).
    "decline_conflict_end_intrigue",
    "finish_conflict_end_intrigue",
    # Arrakeen Scouts: confirming a sealed bid is the seat's turn end (D5).
    "confirm_scouts_bid",
    "resolve_scouts_choice_without_option",
    # Critical Moment's open call, sent with the turn-end press (2026-10-05).
    "scouts_call",
}

# Every Hangul run: the English scenario asserts the turn-end row has none.
HANGUL = re.compile("[가-힣]")

# The seed the combined-game scenarios below drive: turn_controls.py's
# deployment() already showed this seed reaches a Combat space with more
# than one legal troop count for seat 0, which is what pass_combat_intrigue
# below also needs (a seat only sits in the Combat Intrigue rotation once
# it has deployed at least one troop that round).
SEED = 11


def _api_post(base: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        result: dict[str, Any] = json.loads(response.read())
    return result


def _api_get(base: str, path: str) -> dict[str, Any]:
    with urllib.request.urlopen(base + path) as response:
        result: dict[str, Any] = json.loads(response.read())
    return result


def find_draft_seed(base: str, *, human_first: bool, limit: int = 80) -> int | None:
    """A game_seed where seat 0 is (or is not) the Leader draft's First
    Player -- the last picker (OQ-007, leader_draft.py). One raw request per
    candidate seed is far cheaper than driving a browser through each one."""

    for seed in range(limit):
        summary = _api_post(
            base,
            "/games",
            {
                "seats": ["human", "heuristic", "heuristic", "heuristic"],
                "leader_draft": True,
                "game_seed": seed,
            },
        )
        if (summary["first_player"] == 0) == human_first:
            return seed
    return None


def scenario_last_pick(base, browser, seed: int) -> None:
    print("[a] the seat picks last in the Leader draft (it is the First Player)")
    context, page, rec = open_context(browser, "draft-last")
    create_game(page, base, humans=(0,), seed=seed)
    check.ok(
        page.evaluate("Boolean(state.summary.decision)")
        and page.evaluate("state.summary.decision.kind") == "leader_draft",
        "the seat's own pick is offered right away",
    )
    check.ok(
        page.evaluate("state.summary.confirmation") is None,
        "not held before the pick",
    )
    check.ok(
        page.locator("#actions .irreversible-badge").count() == 0,
        "every last-pick choice is reversible",
    )
    first = page.evaluate("state.actions.actions[0]")
    page.click(f"#actions .action-item[data-index='{first['index']}'] > button")
    assert settled(page, 20)
    check.ok(
        page.evaluate("state.summary.phase === 'setup' && state.summary.round_number === 0"),
        "the last pick stays in setup before dealing cards",
    )
    check.ok(page.evaluate("state.view.private.hand.length") == 0, "no starting hand is exposed")
    check.ok(page.evaluate("state.view.private.intrigue_cards.length") == 0, "no setup Intrigue is exposed")
    check.ok(page.locator("#actions .action-item").count() == 0, "only the turn-end row remains")
    check.ok(page.locator(".undo-row button").count() == 1, "the last pick has an undo button")
    page.locator(".undo-row button").click()
    assert settled(page, 20)
    check.ok(
        page.evaluate("state.actions.actions.every((a) => a.action_id === 'pick_leader')"),
        "undo restores the Leader choices",
    )
    other = page.evaluate("state.actions.actions[1]")
    page.click(f"#actions .action-item[data-index='{other['index']}'] > button")
    assert settled(page, 20)
    check.ok(
        page.evaluate("state.view.players[state.viewSeat].leader_id") == other["arguments"]["leader_id"],
        "another Leader can be picked",
    )
    # A fresh snapshot after reload must keep both the pick and its undo.
    page.reload()
    page.wait_for_selector(".undo-row button")
    assert settled(page, 20)
    check.ok(page.locator(".undo-row button").count() == 1, "reload preserves undo")
    row = page.locator(".turn-end-row button")
    check.ok(row.count() == 1, "the turn-end row is shown exactly once")
    check.ok(
        row.inner_text() == page.evaluate("t('render.turn_end_button')"),
        "labelled plainly",
        row.inner_text(),
    )
    posts = rec.count("POST", "/actions")
    row.click()
    assert settled(page, 20)
    check.ok(
        rec.count("POST", "/actions") == posts + 1,
        "one turn-end press confirms the draft",
    )
    check.ok(page.locator(".undo-row button").count() == 0, "the confirmed pick is sealed")
    check.ok(page.evaluate("state.view.private.hand.length") == 5, "the starting hand is dealt after confirmation")
    check.ok(
        page.evaluate("state.summary.confirmation !== state.viewSeat"),
        "the seat is not held for a second press",
    )
    check.ok(
        page.evaluate(
            "state.summary.decision && state.summary.decision.owner === state.viewSeat"
            " && Boolean(state.actions && state.actions.actions.length)"
        ),
        "and the seat's own first-turn actions appear",
    )

    failed = [r for r in rec.requests if r[3] >= 400]
    check.ok(not failed, "no failed requests", failed[:5])
    check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
    context.close()


def scenario_non_last_pick(base, browser, seed: int) -> None:
    print("[b] a non-last pick: the same row, then the next picker")
    context, page, rec = open_context(browser, "draft-next")
    create_game(page, base, humans=(0,), seed=seed)
    action = page.evaluate("state.actions.actions[0]")
    page.click(f"#actions .action-item[data-index='{action['index']}'] > button")
    assert settled(page, 20)

    check.ok(
        page.evaluate("state.summary.confirmation === state.viewSeat"),
        "held after a non-last pick too",
    )
    check.ok(
        page.evaluate("state.summary.decision.owner !== state.viewSeat"),
        "the pending decision belongs to the next picker, not this seat",
    )
    row = page.locator(".turn-end-row button")
    check.ok(row.count() == 1, "the same turn-end row is shown")
    check.ok(
        row.inner_text() == page.evaluate("t('render.turn_end_button')"),
        "labelled the same way",
        row.inner_text(),
    )

    revision = page.evaluate("state.summary.revision")
    confirms = rec.count("POST", "/confirm")
    row.click()
    assert settled(page, 20)
    check.ok(
        rec.count("POST", "/confirm") == confirms + 1,
        "pressing it posts to /confirm exactly once",
    )
    check.ok(
        page.evaluate("state.summary.confirmation !== state.viewSeat"),
        "the seat is not held again for the same pick",
    )
    check.ok(
        page.evaluate("state.summary.revision") > revision,
        "the next picker (and whatever follows) played on",
    )

    failed = [r for r in rec.requests if r[3] >= 400]
    check.ok(not failed, "no failed requests", failed[:5])
    check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
    context.close()


# The turn-end row with a shortfall warning on the seat's own explicit
# turn-end action (sessions.shortfall_warning): held Contract icons that
# fizzle as the turn ends (OQ-059), warned before the press (user ruling
# 2026-10-02, L2-Q4: "로그 + 클릭 전 경고"). No seeded game reaches one (300
# heuristic CHOAM+Bloodlines+Tech games met none), so the serialized fields
# the server sends (tests/server/test_sessions.py
# test_serialized_actions_warn_about_shortfalls_with_nothing_to_choose) are
# put on the live action, the page re-rendered, the row read and the action
# restored, all in one evaluate so no refresh can come in between.
TURN_END_BADGE_JS = """(actionId) => {
  const action = state.actions.actions.find((a) => a.action_id === actionId);
  const saved = [action.warning, action.shortfall];
  action.warning = '계약 아이콘 1개 소멸 — 가져갈 수 있는 계약 없음';
  action.shortfall = [{ kind: 'contract', requested: 1, made: 0 }];
  render();
  const rows = [...document.querySelectorAll('.turn-end-row')];
  const button = rows.length ? rows[0].querySelector('button') : null;
  const badges = button ? [...button.querySelectorAll('.shortfall-badge')] : [];
  const shown = {
    rows: rows.length,
    marked: rows.length === 1 && rows[0].classList.contains('shortfall'),
    label: button ? button.firstChild.textContent : null,
    plain: turnEndButtonLabel(action, state.actions.actions),
    badges: badges.map((b) => b.textContent),
    titled: badges.every((b) => b.title === t('render.shortfall_title')),
  };
  [action.warning, action.shortfall] = saved;
  render();
  shown.after = document.querySelectorAll('.turn-end-row .shortfall-badge').length;
  return shown;
}"""
TURN_END_BADGE = {
    "ko": "계약 아이콘 1개 소멸 — 가져갈 수 있는 계약 없음",
    "en": "1 Contract icon(s) fizzle: no Contract you can take",
}


def check_turn_end_badge(page, action_id: str, language: str) -> None:
    shown = page.evaluate(TURN_END_BADGE_JS, action_id)
    check.ok(
        shown["rows"] == 1 and shown["marked"],
        f"{action_id} with a warning: one turn-end row, marked as a shortfall",
        shown,
    )
    check.ok(
        shown["badges"] == [TURN_END_BADGE[language]] and shown["titled"],
        f"{action_id} with a warning: the row carries the badge ({language})",
        shown,
    )
    check.ok(
        shown["label"] == shown["plain"],
        f"{action_id} with a warning: the label is unchanged before the badge",
        shown,
    )
    check.ok(shown["after"] == 0, f"{action_id}: no badge without a warning", shown)


def _not_a_panel_item(page, index: int) -> bool:
    return not page.evaluate(
        "[...document.querySelectorAll('#actions .action-item')]"
        f".some((n) => Number(n.dataset.index) === {index})"
    )


def check_finish_agent_turn(page, rec) -> None:
    print("[c] finish_agent_turn: the banner's turn-end row, not a panel item")
    action = page.evaluate(
        "state.actions.actions.find((a) => a.action_id === 'finish_agent_turn')"
    )
    check.ok(action is not None, "finish_agent_turn is offered")
    check.ok(
        _not_a_panel_item(page, action["index"]),
        "it is not an item in #actions",
    )
    row = page.locator(".turn-end-row button")
    check.ok(row.count() == 1, "the banner shows the turn-end row")
    check.ok(
        row.inner_text() == page.evaluate("t('render.turn_end_button')"),
        "labelled plainly",
        row.inner_text(),
    )
    check_turn_end_badge(page, "finish_agent_turn", "ko")

    posts = rec.count("POST", "/actions")
    confirms = rec.count("POST", "/confirm")
    row.click()
    assert settled(page, 20)
    check.ok(
        rec.count("POST", "/actions") == posts + 1 and rec.count("POST", "/confirm") == confirms,
        "one click posts to /actions, not /confirm",
    )
    check.ok(
        page.evaluate("state.summary.confirmation !== state.viewSeat"),
        "and never holds this seat for a second press",
    )


def _reveal_label_expects_prefix(page) -> bool:
    """The prefix follows whether the Reveal still offers buyable cards
    (isAcquire actions among the legal actions, render.js turnEndButtonLabel),
    not whether anything has already been bought."""
    return bool(
        page.evaluate(
            "state.actions.actions.some((a) => a.action_id.startsWith('acquire'))"
        )
    )


def check_finish_reveal(page, rec) -> None:
    print("[d] finish_reveal: 'Done acquiring' while cards remain buyable")
    action = page.evaluate(
        "state.actions.actions.find((a) => a.action_id === 'finish_reveal')"
    )
    check.ok(action is not None, "finish_reveal is offered")
    check.ok(
        _not_a_panel_item(page, action["index"]),
        "it is not an item in #actions",
    )
    row = page.locator(".turn-end-row button")
    check.ok(row.count() == 1, "the banner shows the turn-end row")
    expect_prefix = _reveal_label_expects_prefix(page)
    check.ok(
        (row.inner_text() == page.evaluate("t('render.turn_end_button_with_buys')"))
        == expect_prefix,
        "labelled by what remains buyable, not by purchase history",
        (row.inner_text(), expect_prefix),
    )

    lit = page.evaluate(
        "[...document.querySelectorAll('#market .vcard.legal')]"
        ".map((n) => n.dataset.instance)"
    )
    if lit:
        page.click(f"#market .vcard[data-instance='{lit[0]}']")
        assert settled(page, 20)
        expect_prefix = _reveal_label_expects_prefix(page)
        check.ok(
            (row.inner_text() == page.evaluate("t('render.turn_end_button_with_buys')"))
            == expect_prefix,
            "re-labelled after the purchase from what remains buyable",
            (row.inner_text(), expect_prefix),
        )
    else:
        print("  .. nothing affordable this Reveal; buying is untested here")

    posts = rec.count("POST", "/actions")
    row.click()
    assert settled(page, 20)
    check.ok(rec.count("POST", "/actions") == posts + 1, "one click, one request")
    check.ok(
        page.evaluate("state.summary.confirmation !== state.viewSeat"),
        "and never holds this seat for a second press",
    )


def check_pass_combat_intrigue(page, rec) -> None:
    print("[f] pass_combat_intrigue: '패스 · 턴 종료 ▶' / 'Pass · End turn ▶'")
    action = page.evaluate(
        "state.actions.actions.find((a) => a.action_id === 'pass_combat_intrigue')"
    )
    check.ok(action is not None, "pass_combat_intrigue is offered")
    check.ok(
        _not_a_panel_item(page, action["index"]),
        "it is not an item in #actions",
    )
    row = page.locator(".turn-end-row button")
    check.ok(
        row.inner_text() == page.evaluate("t('render.turn_end_button_pass')"),
        "labelled Pass · End turn",
        row.inner_text(),
    )
    check_turn_end_badge(page, "pass_combat_intrigue", "ko")

    posts = rec.count("POST", "/actions")
    row.click()
    assert settled(page, 20)
    check.ok(rec.count("POST", "/actions") == posts + 1, "one click, one request")
    check.ok(
        page.evaluate("state.summary.confirmation !== state.viewSeat"),
        "and hands over without holding this seat",
    )


def check_irreversible_end(page) -> None:
    print("[e] a turn ending in an irreversible step: the row, no undo row")
    check.ok(page.locator(".turn-end-row button").count() == 1, "the turn-end row is shown")
    check.ok(
        page.locator(".undo-row").count() == 0,
        "and no undo row, since nothing here can be taken back",
    )


def combined_scenarios(page, rec, limit: int = 700) -> None:
    """Drive one game long enough to opportunistically hit [c], [d], [e], [f].

    Each is checked the first time its condition is met; deploy_troops is
    chosen whenever legal and [f] is still pending, so the seat becomes a
    Combat Intrigue participant (only a seat with units_in_conflict > 0 gets
    a turn in it) without needing its own dedicated game.
    """

    print(
        "[2] one game: finish_agent_turn, an irreversible end, finish_reveal, "
        "pass_combat_intrigue"
    )
    done = {
        "finish_agent_turn": False,
        "irreversible_end": False,
        "finish_reveal": False,
        "pass_combat_intrigue": False,
    }
    combat_js = f"""(() => {{
      const combat = {json.dumps(COMBAT)};
      // The card pick first, then (at the next call) the space pick.
      const toCombat = placementActions().find((a) =>
        combat.includes(a.arguments.space_id));
      return toCombat ? (toCombat.pickIndex ?? toCombat.index) : 0;
    }})()"""
    for _ in range(limit):
        assert settled(page, 20)
        if page.evaluate("state.summary.finished") or all(done.values()):
            break
        if not done["irreversible_end"] and page.evaluate(
            "!(state.summary.undo || []).some((u) => u.seat === state.viewSeat && u.steps > 0)"
            " && (state.summary.confirmation === state.viewSeat"
            " || Boolean(state.actions && turnEndAction(state.actions.actions)))"
        ):
            check_irreversible_end(page)
            done["irreversible_end"] = True
        if page.evaluate("state.summary.confirmation === state.viewSeat"):
            page.click(".turn-end-row button")
            assert settled(page, 20)
            continue
        if not page.evaluate("Boolean(state.actions && state.actions.actions.length)"):
            time.sleep(0.05)
            continue
        ids = page.evaluate("state.actions.actions.map((a) => a.action_id)")
        if not done["finish_agent_turn"] and "finish_agent_turn" in ids:
            check_finish_agent_turn(page, rec)
            done["finish_agent_turn"] = True
        elif "deploy_troops" in ids and not done["pass_combat_intrigue"]:
            index = page.evaluate(
                "state.actions.actions.find((a) => a.action_id === 'deploy_troops').index"
            )
            page.evaluate(f"applyAction({index})")
        elif not done["finish_reveal"] and "finish_reveal" in ids:
            check_finish_reveal(page, rec)
            done["finish_reveal"] = True
        elif not done["pass_combat_intrigue"] and "pass_combat_intrigue" in ids:
            check_pass_combat_intrigue(page, rec)
            done["pass_combat_intrigue"] = True
        elif not done["pass_combat_intrigue"]:
            page.evaluate(f"applyAction({page.evaluate(combat_js)})")
        else:
            page.evaluate("applyAction(0)")
    for name, ok in done.items():
        check.ok(
            ok, f"{name} was reached within {limit} steps (seed {SEED} reaches it today)"
        )


def scenario_english(base, browser, seed: int) -> None:
    """The turn-end row in English, at a hold and at one of the seat's own
    explicit turn-end actions: always ends "End turn ▶", and carries no
    Hangul (lang.py covers the rest of the page)."""

    print("[3] the turn-end row in English: 'End turn ▶', no Hangul")
    context, page, rec = open_context(browser, "turn-end-english")
    create_game(page, base, humans=(0,), seed=seed)
    switch_language(page, "en")

    def check_row(what: str) -> None:
        row = page.locator(".turn-end-row button")
        check.ok(row.count() == 1, f"{what}: the turn-end row is shown")
        text = row.inner_text()
        check.ok(text.endswith("End turn ▶"), f"{what}: ends with 'End turn ▶'", text)
        check.ok(not HANGUL.search(text), f"{what}: no Hangul in the row", text)

    seen_hold = False
    seen_explicit = False
    for _ in range(700):
        assert settled(page, 20)
        if page.evaluate("state.summary.finished") or (seen_hold and seen_explicit):
            break
        if page.evaluate("state.summary.confirmation === state.viewSeat"):
            if not seen_hold:
                check_row("a hold")
                seen_hold = True
            page.click(".turn-end-row button")
            assert settled(page, 20)
            continue
        if not page.evaluate("Boolean(state.actions && state.actions.actions.length)"):
            time.sleep(0.05)
            continue
        ids = page.evaluate("state.actions.actions.map((a) => a.action_id)")
        if not seen_explicit and any(i in EXPLICIT_TURN_END_IDS for i in ids):
            check_row("an explicit-end decision")
            explicit = next(i for i in ids if i in EXPLICIT_TURN_END_IDS)
            check_turn_end_badge(page, explicit, "en")
            seen_explicit = True
            page.click(".turn-end-row button")
            assert settled(page, 20)
            continue
        page.evaluate("applyAction(0)")
    check.ok(seen_hold, "a hold was reached in English")
    check.ok(seen_explicit, "an explicit-end decision was reached in English")

    failed = [r for r in rec.requests if r[3] >= 400]
    check.ok(not failed, "no failed requests", failed[:5])
    check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
    context.close()


def find_endgame_intrigue_seed(
    base: str, *, limit: int = 20, step_cap: int = 400
) -> int | None:
    """A game_seed where, always taking the seat's own first legal action
    (confirming a hold at once), seat 0 reaches a pass_endgame_intrigue
    decision -- raw HTTP, like find_draft_seed: driving a whole base game
    through the browser for each candidate seed would be far slower, and a
    handful of seeds is enough (every seed sampled while writing this found
    one in well under 200 steps)."""

    for seed in range(limit):
        game = _api_post(
            base,
            "/games",
            {
                "seats": ["human", "heuristic", "heuristic", "heuristic"],
                "leader_draft": True,
                "game_seed": seed,
            },
        )
        game_id = game["game_id"]
        for _ in range(step_cap):
            if game["finished"]:
                break
            if game["confirmation"] == 0:
                game = _api_post(
                    base,
                    f"/games/{game_id}/confirm",
                    {
                        "seat": 0,
                        "revision": game["revision"],
                        "undo_count": game["undo_count"],
                    },
                )
                continue
            decision = game["decision"]
            if decision is None or decision["owner"] != 0:
                # The server auto-advances AI seats inline; this should not
                # happen, so stop driving this seed rather than loop dead.
                break
            actions = _api_get(base, f"/games/{game_id}/seats/0/actions")["actions"]
            if not actions:
                break
            if any(a["action_id"] == "pass_endgame_intrigue" for a in actions):
                return seed
            game = _api_post(
                base,
                f"/games/{game_id}/actions",
                {
                    "seat": 0,
                    "revision": game["revision"],
                    "undo_count": game["undo_count"],
                    "index": actions[0]["index"],
                },
            )
    return None


def check_pass_endgame_intrigue(page, rec) -> None:
    print("[g] pass_endgame_intrigue: '패스 · 턴 종료 ▶' / 'Pass · End turn ▶'")
    action = page.evaluate(
        "state.actions.actions.find((a) => a.action_id === 'pass_endgame_intrigue')"
    )
    check.ok(action is not None, "pass_endgame_intrigue is offered")
    check.ok(
        _not_a_panel_item(page, action["index"]),
        "it is not an item in #actions",
    )
    row = page.locator(".turn-end-row button")
    check.ok(
        row.inner_text() == page.evaluate("t('render.turn_end_button_pass')"),
        "labelled Pass · End turn",
        row.inner_text(),
    )

    posts = rec.count("POST", "/actions")
    row.click()
    assert settled(page, 20)
    check.ok(rec.count("POST", "/actions") == posts + 1, "one click, one request")
    check.ok(
        page.evaluate("state.summary.confirmation !== state.viewSeat"),
        "and hands over without holding this seat",
    )


def scenario_endgame_intrigue(base, browser, seed: int) -> None:
    """Replay find_endgame_intrigue_seed's identical policy (the seat's own
    first legal action every time, confirming a hold at once) through the
    browser: same seed, same deterministic engine, so it lands on the same
    pass_endgame_intrigue decision."""

    context, page, rec = open_context(browser, "endgame-intrigue")
    create_game(page, base, humans=(0,), seed=seed)
    found = False
    for _ in range(400):
        assert settled(page, 20)
        if page.evaluate("state.summary.finished"):
            break
        if page.evaluate("state.summary.confirmation === state.viewSeat"):
            page.evaluate("confirmTurn()")
            continue
        if not page.evaluate("Boolean(state.actions && state.actions.actions.length)"):
            time.sleep(0.05)
            continue
        ids = page.evaluate("state.actions.actions.map((a) => a.action_id)")
        if "pass_endgame_intrigue" in ids:
            check_pass_endgame_intrigue(page, rec)
            found = True
            break
        page.evaluate("applyAction(0)")
    check.ok(found, f"pass_endgame_intrigue was reached (seed {seed})")

    failed = [r for r in rec.requests if r[3] >= 400]
    check.ok(not failed, "no failed requests", failed[:5])
    check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
    context.close()


# The Conflict-end decline (h): two human seats, so the server never
# answers it for them (sessions.py _auto_decline_locked).
DECLINE = "decline_conflict_end_intrigue"
TWO_HUMANS = ["human", "human", "heuristic", "heuristic"]


def find_conflict_end_seed(
    base: str, *, limit: int = 20, step_cap: int = 300
) -> int | None:
    """A game_seed of an Immortality game with seats 0 and 1 human (and the
    setup screen's Leader draft) where, each human always taking its first
    legal action (confirming a hold at once), one of them reaches a
    Conflict-end window that offers only the decline -- raw HTTP, like
    find_endgame_intrigue_seed."""

    for seed in range(limit):
        game = _api_post(
            base,
            "/games",
            {
                "seats": TWO_HUMANS,
                "leader_draft": True,
                "immortality": True,
                "game_seed": seed,
            },
        )
        game_id = game["game_id"]
        for _ in range(step_cap):
            if game["finished"]:
                break
            held = game["confirmation"]
            if isinstance(held, int):
                game = _api_post(
                    base,
                    f"/games/{game_id}/confirm",
                    {
                        "seat": held,
                        "revision": game["revision"],
                        "undo_count": game["undo_count"],
                    },
                )
                continue
            decision = game["decision"]
            if decision is None or decision["owner"] not in (0, 1):
                break
            owner = decision["owner"]
            actions = _api_get(base, f"/games/{game_id}/seats/{owner}/actions")[
                "actions"
            ]
            if not actions:
                break
            if decision["kind"] == "conflict_end_trigger" and [
                a["action_id"] for a in actions
            ] == [DECLINE]:
                return seed
            game = _api_post(
                base,
                f"/games/{game_id}/actions",
                {
                    "seat": owner,
                    "revision": game["revision"],
                    "undo_count": game["undo_count"],
                    "index": actions[0]["index"],
                },
            )
    return None


def check_conflict_end_decline(page, rec) -> None:
    print("[h] a decline-only Conflict-end window: '쓰지 않음 · 턴 종료 ▶'")
    seat = page.evaluate("state.viewSeat")
    prompt = page.inner_text("#decision-info .prompt")
    check.ok(
        "쓸 수 있으면 사용, 아니면 쓰지 않음" in prompt,
        "the prompt reads for a seat with nothing to play",
        prompt,
    )
    check.ok(
        page.locator("#actions .action-item").count() == 0,
        "the decline is no item in #actions",
    )
    row = page.locator(".turn-end-row button")
    check.ok(
        row.count() == 1
        and row.inner_text() == page.evaluate("t('render.turn_end_button_decline')"),
        "labelled 쓰지 않음 · 턴 종료",
        row.inner_text() if row.count() else None,
    )
    check.ok(page.locator(".undo-row").count() == 0, "nothing to take back")
    offered = page.evaluate(
        "state.log.entries.some((entry) => (entry.events || []).some("
        "(event) => event.kind === 'conflict_end_trigger_offered'))"
    )
    check.ok(
        offered and "제안" not in page.inner_text("#action-log"),
        "the log records the offers but shows no per-seat 'offered' line",
        offered,
    )
    switch_language(page, "en")
    text = page.locator(".turn-end-row button").inner_text()
    check.ok(
        text == "Decline · End turn ▶" and not HANGUL.search(text),
        "in English: 'Decline · End turn ▶'",
        text,
    )
    switch_language(page, "ko")

    posts = rec.count("POST", "/actions")
    page.locator(".turn-end-row button").click()
    assert settled(page, 20)
    check.ok(rec.count("POST", "/actions") == posts + 1, "one click, one request")
    check.ok(
        page.evaluate(f"state.summary.confirmation !== {seat}"),
        "and hands over without holding the seat",
    )
    check.ok(
        page.evaluate(
            f"!(state.summary.decision && state.summary.decision.owner === {seat}"
            " && state.summary.decision.kind === 'conflict_end_trigger')"
        ),
        "the window does not come back",
    )


def scenario_conflict_end_decline(base, browser, seed: int) -> None:
    """Replay find_conflict_end_seed's policy through the browser (the page
    follows the deciding human seat), to the same decline-only window."""

    context, page, rec = open_context(browser, "conflict-end-decline")
    create_game(page, base, humans=(0, 1), seed=seed, options=("immortality",))
    found = False
    for _ in range(2000):
        assert settled(page, 20)
        if page.evaluate("state.summary.finished"):
            break
        if page.evaluate("state.summary.confirmation === state.viewSeat"):
            page.evaluate("confirmTurn()")
            continue
        if not page.evaluate("Boolean(state.actions && state.actions.actions.length)"):
            time.sleep(0.05)
            continue
        ids = page.evaluate("state.actions.actions.map((a) => a.action_id)")
        if (
            page.evaluate("state.summary.decision.kind") == "conflict_end_trigger"
            and ids == [DECLINE]
        ):
            check_conflict_end_decline(page, rec)
            found = True
            break
        page.evaluate("applyAction(0)")
    check.ok(found, f"a decline-only Conflict-end window was reached (seed {seed})")

    failed = [r for r in rec.requests if r[3] >= 400]
    check.ok(not failed, "no failed requests", failed[:5])
    check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
    context.close()


# The lone human's Conflict-end window (i): one human seat, so the server
# answers a decline-only window for it (sessions.py _auto_decline_locked).
# Seeds that reach one with the policy below, in the order of how few of the
# seat's requests they take (scanned 2026-10-09 over seeds 0-119, codec
# v141): 97 in round 1 after 19 requests, then 48, 49, 114, 98, 96. Stage B2
# (OQ-112) has a Conflict reward's recipient resolve it row by row, so a
# Combat the seat is rewarded in is one it sees resolved; a headless scan of
# the same policy over seeds 0-119 (2026-10-19) finds only games where the
# seat wins nothing in a Conflict much later: 118 in round 8 after 127
# requests, then 85, 8, 57 (none within 60 requests of seeds 0-159).
LONE_HUMAN = ["human", "heuristic", "heuristic", "heuristic"]
AUTO_DECLINE_SEEDS = (118, 85, 8, 57)


def _server_declined(entries: list[dict[str, Any]], last_press: int) -> int | None:
    """The log index of a decline of seat 0's after its press at
    ``last_press`` (the page never sends one under this policy, see
    scenario_auto_decline), when the Combat was resolved in between."""

    resolved = False
    for entry in entries:
        if entry["index"] <= last_press:
            continue
        kinds = {event["kind"] for event in entry.get("events") or []}
        resolved = resolved or "combat_standing" in kinds
        if (
            entry["type"] == "action"
            and entry["actor"] == 0
            and entry["action_id"] == DECLINE
        ):
            return entry["index"] if resolved else None
    return None


def find_auto_decline_seed(base: str, *, request_cap: int = 160) -> int | None:
    """The first of AUTO_DECLINE_SEEDS where seat 0, the one human seat of
    an Immortality game with the setup screen's Leader draft, always taking
    its first legal action (confirming a hold at once, never offered a
    lone decline before), has a Conflict-end window declined for it by the
    server after a Combat it did not see resolved -- raw HTTP, like
    find_endgame_intrigue_seed."""

    for seed in AUTO_DECLINE_SEEDS:
        game = _api_post(
            base,
            "/games",
            {
                "seats": LONE_HUMAN,
                "leader_draft": True,
                "immortality": True,
                "game_seed": seed,
            },
        )
        game_id = game["game_id"]
        log = f"/games/{game_id}/log?seat=0"
        last_press = -1
        for _ in range(request_cap):
            if game["finished"]:
                break
            body = {
                "seat": 0,
                "revision": game["revision"],
                "undo_count": game["undo_count"],
            }
            count = _api_get(base, log)["count"]
            if game["confirmation"] == 0:
                game = _api_post(base, f"/games/{game_id}/confirm", body)
            else:
                decision = game["decision"]
                if decision is None or decision["owner"] != 0:
                    break
                actions = _api_get(base, f"/games/{game_id}/seats/0/actions")[
                    "actions"
                ]
                if not actions or actions[0]["action_id"] == DECLINE:
                    break
                game = _api_post(
                    base,
                    f"/games/{game_id}/actions",
                    {**body, "index": actions[0]["index"]},
                )
                # The seat's own step is the first new entry (a confirm
                # adds none of its own).
                last_press = count
            entries = _api_get(base, f"{log}&after={count}")["entries"]
            if _server_declined(entries, last_press) is not None:
                return seed
    return None


# Which cards glow, worked out from the request this page last sent rather
# than from ownGlowFrom: every card holding a log entry after that press
# (`lastPress`), and none before. logGroups() only says which entries share
# a card, in the DOM's order (remote_fresh.py's GLOW_CHECK_JS does the same).
AUTO_DECLINE_GLOW_JS = """([lastPress, declined]) => {
  const groups = logGroups(state.log.entries).filter((g) => g.kind !== "undo");
  const indexes = (g) =>
    g.kind === "neutral"
      ? g.items.map((item) => item.index ?? item.chance.index)
      : g.entries.map((entry) => entry.index);
  const cards = [...document.querySelectorAll("#action-log .turn-card")].filter(
    (card) => !card.classList.contains("undo-marker")
  );
  const expected = groups.map((g) => indexes(g).some((index) => index > lastPress));
  const actual = cards.map((card) => card.classList.contains("fresh"));
  const resolved = groups.findIndex(
    (g) =>
      g.kind === "neutral" &&
      g.items.some((item) => item.event && item.event.kind === "combat_standing") &&
      indexes(g).some((index) => index > lastPress)
  );
  const declineCard = groups.findIndex((g) => indexes(g).includes(declined));
  return {
    expected, actual,
    resolvedTitle:
      resolved >= 0 ? cards[resolved].querySelector("strong").textContent : null,
    resolvedFresh: resolved >= 0 && actual[resolved],
    declineFolded: declineCard >= 0 && groups[declineCard].kind === "passes",
    declineFresh: declineCard >= 0 && actual[declineCard],
  };
}"""


def scenario_auto_decline(base, browser, seed: int) -> None:
    """Replay find_auto_decline_seed's policy through the browser up to the
    seat's first decision after the server declined for it, then read the
    log's glow: the Combat result and the AI moves the seat never saw are
    new to it although the log holds a later step of its own (panels.js
    ownGlowFrom leaves the seat's Conflict-end declines out)."""

    print("[i] a lone human's decline-only window, answered by the server")
    context, page, rec = open_context(browser, "auto-decline")
    create_game(page, base, humans=(0,), seed=seed, options=("immortality",))
    last_press = -1
    declined = None
    for _ in range(600):
        assert settled(page, 20)
        if page.evaluate("state.summary.finished"):
            break
        held = page.evaluate("state.summary.confirmation === 0")
        acting = page.evaluate(
            "Boolean(state.actions && state.actions.actions.length)"
        )
        if not held and not acting:
            time.sleep(0.05)
            continue
        entries = page.evaluate("state.log.entries")
        declined = _server_declined(entries, last_press)
        if declined is not None:
            break
        if held:
            page.evaluate("confirmTurn()")
            continue
        if page.evaluate("state.actions.actions[0].action_id") == DECLINE:
            break
        before = max((entry["index"] for entry in entries), default=-1)
        page.evaluate("applyAction(0)")
        assert settled(page, 20)
        last_press = page.evaluate(
            f"state.log.entries.find((e) => e.index > {before}"
            " && e.type === 'action' && e.actor === 0).index"
        )
    if not check.ok(
        declined is not None,
        f"the server declined a window for the lone human (seed {seed})",
    ):
        context.close()
        return
    check.ok(
        page.evaluate("state.summary.confirmation !== 0")
        and page.evaluate("state.summary.decision.owner === 0")
        and page.evaluate("state.summary.decision.kind !== 'conflict_end_trigger'"),
        "the seat's next decision is not the window",
    )
    glow = page.evaluate(AUTO_DECLINE_GLOW_JS, [last_press, declined])
    check.ok(
        glow["resolvedFresh"],
        "the Combat result, resolved after the seat's last press, is new to it",
        glow["resolvedTitle"],
    )
    check.ok(
        glow["declineFolded"] and glow["declineFresh"],
        "the server's decline is folded with the others and new to the seat",
        glow,
    )
    check.ok(
        glow["expected"] == glow["actual"],
        "exactly the cards holding entries after the seat's last press glow",
        glow,
    )

    failed = [r for r in rec.requests if r[3] >= 400]
    check.ok(not failed, "no failed requests", failed[:5])
    check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
    context.close()


def main() -> None:
    with server() as (base, server_log), chrome() as browser:
        try:
            last_seed = find_draft_seed(base, human_first=True)
            if last_seed is None:
                check.ok(False, "a seed with seat 0 as First Player was found")
            else:
                scenario_last_pick(base, browser, last_seed)
            next_seed = find_draft_seed(base, human_first=False)
            if next_seed is None:
                check.ok(False, "a seed with a non-last human pick was found")
            else:
                scenario_non_last_pick(base, browser, next_seed)

            context, page, rec = open_context(browser, "player")
            create_game(page, base, humans=(0,), seed=SEED)
            combined_scenarios(page, rec)
            failed = [r for r in rec.requests if r[3] >= 400]
            check.ok(not failed, "no failed requests", failed[:5])
            check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
            context.close()

            if next_seed is not None:
                scenario_english(base, browser, next_seed)

            endgame_seed = find_endgame_intrigue_seed(base)
            if endgame_seed is None:
                print(
                    "  .. no seed reached a pass_endgame_intrigue decision for seat 0"
                    " within the search budget; [g] left out"
                )
            else:
                scenario_endgame_intrigue(base, browser, endgame_seed)

            conflict_end_seed = find_conflict_end_seed(base)
            if conflict_end_seed is None:
                check.ok(False, "a seed reached a decline-only Conflict-end window")
            else:
                scenario_conflict_end_decline(base, browser, conflict_end_seed)

            auto_decline_seed = find_auto_decline_seed(base)
            if auto_decline_seed is None:
                check.ok(
                    False,
                    "one of AUTO_DECLINE_SEEDS reached a server decline"
                    " (rescan with that policy)",
                )
            else:
                scenario_auto_decline(base, browser, auto_decline_seed)
        finally:
            shutil.copy(server_log, SERVER_LOG_COPY)
        text = server_log.read_text()
        check.ok(
            "Traceback" not in text and "ERROR" not in text,
            f"no server errors (see {SERVER_LOG_COPY})",
        )
    check.finish()


if __name__ == "__main__":
    main()
