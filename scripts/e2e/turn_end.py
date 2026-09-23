"""E2E of the unified turn-end control (2026-09-24).

One press, EXACTLY one, ends a human seat's turn, whatever step closes it:
- a hold (server ``awaiting_confirmation``, ``summary.confirmation`` == the
  seat) renders the banner's turn-end row, its button calling
  ``confirmTurn()`` (POST /confirm);
- the seat's own explicit turn-end action (``EXPLICIT_TURN_END_IDS`` in
  render.js, mirroring ``EXPLICIT_TURN_ENDS`` in server/turn_end.py:
  ``finish_agent_turn``, ``finish_reveal``, ``pass_combat_intrigue``,
  ``pass_endgame_intrigue``) renders as that SAME row instead, its button
  applying that action directly (POST /actions) -- and never doubles as an
  item in any action list (the staged Agent turn's steps, its "or" list,
  the full-list toggle, the Reveal panel).

Both are `div.confirm-row.turn-end-row` with one button whose text ends in
"턴 종료 ▶" / "End turn ▶": this checks that the row is the one and only
turn-end control, in the one place, for every one of these steps, and that
pressing it is always a single request with no second step afterwards. It
also checks the row in English (no Hangul, "End turn ▶") at a hold and at
an explicit-end decision, and pass_endgame_intrigue's own label, once a
seed search (raw HTTP, no browser) finds one that reaches it.
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
# use it.
EXPLICIT_TURN_END_IDS = {
    "finish_agent_turn",
    "finish_reveal",
    "pass_combat_intrigue",
    "pass_endgame_intrigue",
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
    action = page.evaluate("state.actions.actions[0]")
    page.click(f"#actions .action-item[data-index='{action['index']}'] > button")
    assert settled(page, 20)

    check.ok(
        page.evaluate("state.summary.confirmation === state.viewSeat"),
        "held after the last pick",
    )
    check.ok(
        page.evaluate("state.summary.decision.owner === state.viewSeat"),
        "the pending decision is the seat's own round-1 turn",
    )
    check.ok(page.evaluate("state.actions") is None, "#actions offers nothing while held")
    check.ok(page.locator("#actions .action-item").count() == 0, "the panel is empty")
    row = page.locator(".turn-end-row button")
    check.ok(row.count() == 1, "the turn-end row is shown")
    check.ok(
        row.inner_text() == page.evaluate("t('render.turn_end_button')"),
        "labelled plainly",
        row.inner_text(),
    )

    confirms = rec.count("POST", "/confirm")
    row.click()
    assert settled(page, 20)
    check.ok(
        rec.count("POST", "/confirm") == confirms + 1,
        "pressing it posts to /confirm exactly once",
    )
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

    posts = rec.count("POST", "/actions")
    row.click()
    assert settled(page, 20)
    check.ok(rec.count("POST", "/actions") == posts + 1, "one click, one request")
    check.ok(
        page.evaluate("state.summary.confirmation !== state.viewSeat"),
        "and hands over without holding this seat",
    )


def check_irreversible_hold(page) -> None:
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
        "[2] one game: finish_agent_turn, an irreversible hold, finish_reveal, "
        "pass_combat_intrigue"
    )
    done = {
        "finish_agent_turn": False,
        "irreversible_hold": False,
        "finish_reveal": False,
        "pass_combat_intrigue": False,
    }
    combat_js = f"""(() => {{
      const A = state.actions.actions;
      const combat = {json.dumps(COMBAT)};
      const toCombat = A.find((a) => a.action_id === 'agent_turn'
        && combat.includes(a.arguments.space_id));
      return toCombat ? toCombat.index : 0;
    }})()"""
    for _ in range(limit):
        assert settled(page, 20)
        if page.evaluate("state.summary.finished") or all(done.values()):
            break
        if page.evaluate("state.summary.confirmation === state.viewSeat"):
            if not done["irreversible_hold"] and page.evaluate(
                "!(state.summary.undo || []).some("
                "(u) => u.seat === state.viewSeat && u.steps > 0)"
            ):
                check_irreversible_hold(page)
                done["irreversible_hold"] = True
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


def scenario_english(base, browser) -> None:
    """The turn-end row in English, at a hold and at one of the seat's own
    explicit turn-end actions: always ends "End turn ▶", and carries no
    Hangul (lang.py covers the rest of the page)."""

    print("[3] the turn-end row in English: 'End turn ▶', no Hangul")
    context, page, rec = open_context(browser, "turn-end-english")
    create_game(page, base, humans=(0,), seed=SEED)
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

            scenario_english(base, browser)

            endgame_seed = find_endgame_intrigue_seed(base)
            if endgame_seed is None:
                print(
                    "  .. no seed reached a pass_endgame_intrigue decision for seat 0"
                    " within the search budget; [g] left out"
                )
            else:
                scenario_endgame_intrigue(base, browser, endgame_seed)
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
