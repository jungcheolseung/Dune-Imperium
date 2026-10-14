"""E2E of a Control defense with an empty supply (OQ-050, 2026-10-04).

"When a Conflict card is revealed for a space that you already control, you
receive a defensive bonus: you may deploy one troop from your supply to the
Conflict." [Main pp. 10, 20]; "You may return any of your specimens to your
supply at any time" [Immortality p. 8]. A defender whose supply is empty but
who has a specimen is still asked: Round Start opens the Control defense and
offers ``return_specimen`` beside declining, so the specimen can become the
defending troop (rules/phases.py ``_control_defense_frame``,
rules/immortality.py ``legal_specimen_return_actions``). Only the engine unit
tests (tests/unit/rules/test_specimen_return_windows.py) and the play-server
test (tests/server/test_empty_supply_defense.py) covered it; this is the
page.

The position is real: ``fixtures/defense_specimen_saves.py`` plays an
Immortality game by the pinned table heuristic and saves it at the first
Round Start defense of a seat with no troop in its supply and a specimen.
- [A] the page offers declining and returning a specimen, and no deploy row
  while the supply is empty; returning one leaves the same defense open with
  the deploy row now offered, the answer is held for the press with both
  steps to take back, "2단계 모두 되돌리기" restores the empty-supply defense
  exactly, and the pressed answer draws the round's hand with the taken-back
  steps kept in the log flagged undone;
- [B] the same rows in English.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from common import REPO, SERVER_LOG_COPY, Check, ServerProcess, chrome, open_context
from lang import switch as switch_language
from open_mode import settled

check = Check()

HANGUL = re.compile("[가-힣]")
DECLINE = "decline_control_defense"
DEPLOY = "deploy_control_defense"
RETURN = "return_specimen"

# One entry per row of the action list, in order: its index, id, visible text
# and the alt text of every icon in it.
ROWS_JS = """() => state.actions.actions.map((a) => {
  const item = document.querySelector(
    `#actions .action-item[data-index='${a.index}']`);
  return {
    action_id: a.action_id,
    undoable: a.undoable,
    sent_by_turn_end: a.sent_by_turn_end,
    text: item ? item.innerText.trim() : null,
    alts: item ? [...item.querySelectorAll('img')].map((i) => i.alt) : [],
  };
})"""

# A seat's own numbers on the table, as the page holds them.
SEAT_JS = """(seat) => {
  const p = state.view.players[seat];
  return {
    supply: p.troops_supply,
    specimens: p.specimens,
    conflict: p.troops_conflict,
    hand: (state.view.private && state.view.private.hand || []).length,
  };
}"""

# The seat's own steps in the live log, taken-back ones included.
SEAT_STEPS_JS = """(seat) => (state.log ? state.log.entries : [])
  .filter((e) => e.type === 'action' && e.actor === seat)
  .map((e) => [e.action_id, Boolean(e.undone)])"""


def record_posts(page) -> list[tuple[str, object]]:
    """Every POST the page makes to a game, as (endpoint, body)."""

    posts: list[tuple[str, object]] = []

    def on_request(request) -> None:
        if request.method == "POST" and "/games/" in request.url:
            posts.append((request.url.rsplit("/", 1)[-1], request.post_data_json))

    page.on("request", on_request)
    return posts


def bodies(posts, endpoint: str) -> list:
    return [body for name, body in posts if name == endpoint]


def open_save(browser, base: str, label: str):
    context, page, rec = open_context(browser, label)
    page.goto(base + "/")
    page.locator("#save-list li:has-text('defense-specimen') button").first.click()
    page.wait_for_function(
        "state.view !== null && refreshFlight === null"
        " && Boolean(state.actions && state.actions.actions.length)"
    )
    assert settled(page, 20)
    return context, page, rec, record_posts(page)


def rows(page) -> list[dict]:
    return page.evaluate(ROWS_JS)


def ids(page) -> list[str]:
    return [row["action_id"] for row in rows(page)]


def row_button(page, action_id: str):
    (index,) = (
        a["index"]
        for a in page.evaluate("state.actions.actions")
        if a["action_id"] == action_id
    )
    return page.locator(
        f"#actions .action-item[data-index='{index}'] > button:not(.action-info)"
    )


def click_row(page, action_id: str) -> None:
    row_button(page, action_id).click()
    assert settled(page, 20)


def undo_buttons(page) -> list[str]:
    return page.evaluate(
        "[...document.querySelectorAll('.undo-row button')].map((b) => b.textContent)"
    )


def finish_page(context, rec, what: str) -> None:
    failed = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
    check.ok(not failed, f"{what}: no failed requests", failed[:5])
    check.ok(not rec.js_errors, f"{what}: no JS errors", rec.js_errors[:5])
    context.close()


def scenario_defense(browser, base: str, seat: int, specimens: int) -> None:
    print("[A] an empty-supply Control defense: return a specimen, deploy, take back")
    context, page, rec, posts = open_save(browser, base, "defense-specimen")
    decision = page.evaluate("state.summary.decision")
    check.ok(
        decision["kind"] == "control_defense"
        and decision["owner"] == seat
        and page.evaluate("state.viewSeat") == seat,
        "the save rests at the defender's Control defense",
        decision,
    )
    start = page.evaluate(SEAT_JS, seat)
    check.ok(
        start["supply"] == 0 and start["specimens"] == specimens and start["hand"] == 0,
        "A1: the defender has no troop in its supply, its specimens, and no hand yet",
        start,
    )
    check.ok(
        "공급처" in page.inner_text("#decision-info"),
        "A1: the prompt asks about deploying from the supply",
        page.inner_text("#decision-info"),
    )

    offered = rows(page)
    check.ok(
        [r["action_id"] for r in offered] == [DECLINE, RETURN],
        "A1: the page offers declining and returning a specimen, no deploy row",
        [r["action_id"] for r in offered],
    )
    check.ok(
        all(r["undoable"] and not r["sent_by_turn_end"] for r in offered)
        and page.locator("#actions .irreversible-badge").count() == 0,
        "A1: both rows can be taken back and are sent at once, no 되돌리기 불가 badge",
    )
    decline_row, return_row = offered
    check.ok(
        decline_row["text"] == "방어 배치 안 함"
        and "방어 배치" not in return_row["text"]
        and "공급처로 되돌리기" in return_row["text"]
        and return_row["alts"] == ["표본"],
        "A1: the rows read 방어 배치 안 함 / [표본]을 개인 공급처로 되돌리기",
        offered,
    )

    click_row(page, RETURN)
    summary = page.evaluate("state.summary")
    now_seen = page.evaluate(SEAT_JS, seat)
    check.ok(
        len(bodies(posts, "actions")) == 1
        and summary["confirmation"] is None
        and summary["decision"]["kind"] == "control_defense"
        and summary["decision"]["owner"] == seat,
        "A2: returning a specimen is sent at once and the defense stays open",
        (posts, summary["confirmation"], summary["decision"]),
    )
    check.ok(
        now_seen["supply"] == 1
        and now_seen["specimens"] == specimens - 1
        and now_seen["hand"] == 0,
        "A2: the specimen is now a troop in the supply, still no hand",
        now_seen,
    )
    offered = rows(page)
    check.ok(
        [r["action_id"] for r in offered] == [DECLINE, DEPLOY]
        and offered[1]["text"] == "방어 배치"
        and offered[1]["alts"] == ["지배"],
        "A2: the deploy row (방어 배치) is offered now, no second return",
        offered,
    )
    check.ok(
        undo_buttons(page) == ["되돌리기 (1단계)"]
        and page.locator(".turn-end-row").count() == 0,
        "A2: one undo step, and no turn-end row (nothing is held yet)",
        undo_buttons(page),
    )

    click_row(page, DEPLOY)
    summary = page.evaluate("state.summary")
    deployed = page.evaluate(SEAT_JS, seat)
    check.ok(
        len(bodies(posts, "actions")) == 2
        and summary["confirmation"] == seat
        and summary["decision"] is None,
        "A3: 방어 배치 is sent at once and held before the draw",
        (len(bodies(posts, "actions")), summary["confirmation"], summary["decision"]),
    )
    check.ok(
        deployed["supply"] == 0
        and deployed["conflict"] == start["conflict"] + 1
        and deployed["specimens"] == specimens - 1
        and deployed["hand"] == 0,
        "A3: the returned specimen defends the Conflict, still no hand",
        deployed,
    )
    turn_end = page.locator(".turn-end-row button")
    check.ok(
        turn_end.count() == 1 and turn_end.inner_text() == "턴 종료 ▶",
        "A3: the turn-end row reads 턴 종료 ▶",
        turn_end.all_inner_texts(),
    )
    check.ok(
        [u for u in summary["undo"] if u["seat"] == seat]
        == [{"seat": seat, "steps": 2}]
        and undo_buttons(page) == ["되돌리기 (1단계)", "2단계 모두 되돌리기"],
        "A3: both steps can be taken back",
        (summary["undo"], undo_buttons(page)),
    )

    page.locator(".undo-row button", has_text="2단계 모두 되돌리기").click()
    assert settled(page, 20)
    summary = page.evaluate("state.summary")
    check.ok(
        len(bodies(posts, "undo")) == 1
        and summary["confirmation"] is None
        and summary["decision"]["kind"] == "control_defense"
        and summary["decision"]["owner"] == seat,
        "A4: 2단계 모두 되돌리기 is one POST /undo, back at the defense",
        (len(bodies(posts, "undo")), summary["confirmation"], summary["decision"]),
    )
    check.ok(
        page.evaluate(SEAT_JS, seat) == start
        and ids(page) == [DECLINE, RETURN]
        and page.locator(".undo-row").count() == 0,
        "A4: the empty-supply defense is back exactly as it was, nothing to undo",
        (page.evaluate(SEAT_JS, seat), ids(page)),
    )

    click_row(page, RETURN)
    click_row(page, DEPLOY)
    check.ok(page.evaluate("state.summary.confirmation") == seat, "A5: held again")
    page.locator(".turn-end-row button").click()
    assert settled(page, 20)
    summary = page.evaluate("state.summary")
    after = page.evaluate(SEAT_JS, seat)
    check.ok(
        len(bodies(posts, "confirm")) == 1 and summary["confirmation"] != seat,
        "A5: the press is one POST /confirm and clears the hold",
        (posts, summary["confirmation"]),
    )
    check.ok(
        after["hand"] > 0
        and after["conflict"] == start["conflict"] + 1
        and after["supply"] == 0
        and after["specimens"] == specimens - 1,
        "A5: the press drew the round's hand, the defending troop stays",
        after,
    )
    steps = [
        tuple(step)
        for step in page.evaluate(SEAT_STEPS_JS, seat)
        if step[0] in (RETURN, DEPLOY)
    ]
    check.ok(
        steps == [(RETURN, True), (DEPLOY, True), (RETURN, False), (DEPLOY, False)],
        "A5: the log keeps the taken-back return and deploy flagged undone",
        steps,
    )
    finish_page(context, rec, "A")


def scenario_english(browser, base: str, seat: int) -> None:
    print("[B] the same defense in English")
    context, page, rec, posts = open_save(browser, base, "defense-specimen-en")
    switch_language(page, "en")
    offered = rows(page)
    check.ok(
        [r["action_id"] for r in offered] == [DECLINE, RETURN]
        and offered[0]["text"] == "Decline to deploy defense"
        and offered[1]["text"] == "Return a  to supply"
        and offered[1]["alts"] == ["specimen"],
        "B1: the rows read in English, the specimen icon between the words",
        offered,
    )
    shown = page.inner_text("#decision-info")
    check.ok(
        not HANGUL.search(shown)
        and not any(HANGUL.search(r["text"] or "") for r in offered),
        "B1: no Hangul in the rows or the prompt",
        shown,
    )
    click_row(page, RETURN)
    offered = rows(page)
    check.ok(
        [r["action_id"] for r in offered] == [DECLINE, DEPLOY]
        and undo_buttons(page) == ["Undo (1 step)"]
        and not any(HANGUL.search(r["text"] or "") for r in offered),
        "B2: after the return the deploy row and one English undo step show",
        (offered, undo_buttons(page)),
    )
    check.ok(len(bodies(posts, "actions")) == 1, "B2: one POST /actions", posts)
    finish_page(context, rec, "B")


def main() -> None:
    saves = tempfile.mkdtemp(prefix="dune-defense-specimen-e2e-")
    found = json.loads(
        subprocess.run(
            [
                str(REPO / ".venv/bin/python"),
                str(Path(__file__).parent / "fixtures/defense_specimen_saves.py"),
                saves,
            ],
            cwd=REPO,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    print(f"fixtures: {found}")
    server = ServerProcess(saves=saves).start()
    try:
        with chrome() as browser:
            scenario_defense(browser, server.base, found["seat"], found["specimens"])
            scenario_english(browser, server.base, found["seat"])
    finally:
        server.stop()
        shutil.copy(server.log_path, SERVER_LOG_COPY)
    text = server.log_path.read_text()
    check.ok(
        "Traceback" not in text and "ERROR" not in text,
        f"no server errors (see {SERVER_LOG_COPY})",
    )
    check.finish()


if __name__ == "__main__":
    main()
