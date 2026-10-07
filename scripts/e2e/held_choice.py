"""E2E of a choice outside the turns held for the press (2026-10-08).

The turn-end press is the seat's confirmation; before it the seat may change
its decision. A step of the seat's own unit outside its Agent and Reveal
turns that cannot be taken back carries ``sent_by_turn_end`` from the server
(sessions.py), and the browser does not send a click on it (turn.js
``chooseAction``): it holds it (``.held-choice``, aria-pressed, the table
object ``.picked``), shows a hint and a banner row "확정 ▶" / "Confirm ▶"
(``.held-send-row``) that sends it with one POST /actions. Another row moves
the hold, a second click on the held row or Escape lets it go, a second click
on the held table object keeps it. A step that CAN be taken back is sent at
once, and its unit end is held by the server (``summary.confirmation``) before
the chance outcome after it, with the turn-end row and the undo row.

The positions are real: ``fixtures/held_choice_saves.py`` plays seat 0 by a
seeded random policy against the pinned table heuristic and saves
- ``held-defense``: a seat-0 Control defense whose two answers are held [A];
- ``held-reward-spy``: a seat-0 Conflict reward Spy that can be taken back,
  before the next round's reshuffle [B];
- ``held-spy-post``: a seat-0 Conflict reward Spy whose posts are held, so a
  click on a board Spy post holds it too [C].
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
SPY_POST = "place_combat_reward_spy"

# What the page shows of a hold, read in one go.
HELD_JS = """() => ({
  held: [...document.querySelectorAll('.held-choice')]
    .map((n) => Number(n.dataset.index)),
  pressed: [...document.querySelectorAll('#actions .action-item > button')]
    .filter((b) => b.getAttribute('aria-pressed') === 'true')
    .map((b) => Number(b.parentElement.dataset.index)),
  hints: [...document.querySelectorAll('.held-hint')].map((n) => n.textContent),
  send: [...document.querySelectorAll('.held-send-row button')]
    .map((b) => b.textContent),
  turnEnd: document.querySelectorAll('.turn-end-row').length,
  picked: [...document.querySelectorAll('.spy-post-hotspot.picked')]
    .map((n) => n.dataset.post),
  revision: state.summary.revision,
  confirmation: state.summary.confirmation,
})"""

# The live log's last step of seat 0 that was not taken back.
LAST_SEAT0_JS = """() => {
  const own = (state.log ? state.log.entries : []).filter(
    (e) => e.type === 'action' && e.actor === 0 && !e.undone);
  const last = own[own.length - 1];
  return last ? { action_id: last.action_id, arguments: last.arguments } : null;
}"""

# The first of `posts` whose board hotspot is the element a click at its
# centre reaches (scrolled into view first), so the click is a real one.
CLICKABLE_POST_JS = """(posts) => {
  for (const post of posts) {
    const node = document.querySelector(`.spy-post-hotspot[data-post='${post}']`);
    if (!node) continue;
    node.scrollIntoView({ block: 'center', inline: 'center' });
    const r = node.getBoundingClientRect();
    if (document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2) === node) {
      return post;
    }
  }
  return null;
}"""


def record_posts(page) -> list[tuple[str, object]]:
    """Every POST the page makes to a game, as (endpoint, body), from the
    moment of the request (not its response)."""

    posts: list[tuple[str, object]] = []

    def on_request(request) -> None:
        if request.method == "POST" and "/games/" in request.url:
            posts.append((request.url.rsplit("/", 1)[-1], request.post_data_json))

    page.on("request", on_request)
    return posts


def bodies(posts, endpoint: str) -> list:
    return [body for name, body in posts if name == endpoint]


def open_save(browser, base: str, name: str, label: str):
    context, page, rec = open_context(browser, label)
    page.goto(base + "/")
    page.locator(f"#save-list li:has-text('{name}') button").first.click()
    page.wait_for_function(
        "state.view !== null && refreshFlight === null"
        " && Boolean(state.actions && state.actions.actions.length)"
    )
    assert settled(page, 20)
    return context, page, rec, record_posts(page)


def held(page) -> dict:
    return page.evaluate(HELD_JS)


def rows(page, action_id: str) -> list[dict]:
    return page.evaluate(
        "id => state.actions.actions.filter((a) => a.action_id === id)", action_id
    )


def row_button(page, index: int):
    return page.locator(f"#actions .action-item[data-index='{index}'] > button")


def click_row(page, index: int) -> None:
    row_button(page, index).click()
    assert settled(page, 20)


def finish_page(context, rec, what: str) -> None:
    failed = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
    check.ok(not failed, f"{what}: no failed requests", failed[:5])
    check.ok(not rec.js_errors, f"{what}: no JS errors", rec.js_errors[:5])
    context.close()


def scenario_defense(browser, base: str) -> None:
    print("[A] a Control defense: both answers are held for the press")
    context, page, rec, posts = open_save(browser, base, "held-defense", "defense")
    decision = page.evaluate("state.summary.decision")
    check.ok(
        decision["kind"] == "control_defense" and decision["owner"] == 0,
        "the save rests at seat 0's Control defense",
        decision,
    )
    (deploy,) = rows(page, "deploy_control_defense")
    (decline,) = rows(page, "decline_control_defense")
    check.ok(
        deploy["sent_by_turn_end"] and decline["sent_by_turn_end"],
        "both answers are marked sent_by_turn_end",
    )
    deploy_text = row_button(page, deploy["index"]).inner_text()
    decline_text = row_button(page, decline["index"]).inner_text()
    check.ok(
        "방어 배치" in deploy_text
        and "안 함" not in deploy_text
        and "방어 배치 안 함" in decline_text,
        "A1: the rows read 방어 배치 / 방어 배치 안 함",
        (deploy_text, decline_text),
    )
    check.ok(
        page.locator("#actions .irreversible-badge").count() == 0,
        "A1: neither answer carries the 되돌리기 불가 badge",
    )
    revision = page.evaluate("state.summary.revision")

    click_row(page, deploy["index"])
    shown = held(page)
    check.ok(shown["held"] == [deploy["index"]], "A1: 방어 배치 is .held-choice", shown)
    check.ok(shown["pressed"] == [deploy["index"]], "A1: aria-pressed", shown)
    check.ok(
        page.locator(".held-hint").is_visible()
        and shown["hints"] == [page.evaluate("t('render.held_choice_hint')")],
        "A1: the hint says how the choice is sent",
        shown["hints"],
    )
    check.ok(shown["send"] == ["확정 ▶"], "A1: the banner row reads 확정 ▶", shown)
    check.ok(shown["turnEnd"] == 0, "A1: and there is no turn-end row", shown)
    check.ok(not bodies(posts, "actions"), "A1: no POST /actions for the click", posts)
    check.ok(shown["revision"] == revision, "A1: the game did not move", shown)

    click_row(page, decline["index"])
    shown = held(page)
    check.ok(
        shown["held"] == [decline["index"]] and shown["pressed"] == [decline["index"]],
        "A2: a click on 방어 배치 안 함 moves the hold to it (one .held-choice)",
        shown,
    )
    click_row(page, decline["index"])
    shown = held(page)
    check.ok(
        not shown["held"] and not shown["send"] and not shown["hints"],
        "A2: a second click on the held row lets it go",
        shown,
    )
    click_row(page, decline["index"])
    check.ok(held(page)["held"] == [decline["index"]], "A2: held again")
    page.keyboard.press("Escape")
    assert settled(page, 20)
    shown = held(page)
    check.ok(
        not shown["held"] and not shown["send"] and not shown["hints"],
        "A2: Escape lets the hold go",
        shown,
    )
    check.ok(
        not posts and shown["revision"] == revision,
        "A2: nothing was sent while the hold moved",
        posts,
    )

    click_row(page, deploy["index"])
    page.locator(".held-send-row button").click()
    assert settled(page, 20)
    sent = bodies(posts, "actions")
    check.ok(
        len(sent) == 1 and sent[0]["index"] == deploy["index"],
        "A2: 확정 ▶ sends exactly one POST /actions, the held answer",
        posts,
    )
    check.ok(not bodies(posts, "confirm"), "A2: and no POST /confirm", posts)
    after = page.evaluate("state.summary")
    check.ok(
        after["decision"] is None or after["decision"]["kind"] != "control_defense",
        "A2: the game moved on past the defense",
        after["decision"],
    )
    check.ok(
        after["confirmation"] != 0,
        "A2: the seat is not held for an extra press",
        after["confirmation"],
    )
    last = page.evaluate(LAST_SEAT0_JS)
    check.ok(
        last is not None and last["action_id"] == "deploy_control_defense",
        "A2: the live log's last seat-0 action is deploy_control_defense",
        last,
    )
    finish_page(context, rec, "A")


def scenario_defense_english(browser, base: str) -> None:
    print("[A3] the same hold in English: 'Confirm ▶'")
    context, page, rec, posts = open_save(browser, base, "held-defense", "defense-en")
    switch_language(page, "en")
    (deploy,) = rows(page, "deploy_control_defense")
    click_row(page, deploy["index"])
    shown = held(page)
    check.ok(shown["held"] == [deploy["index"]], "A3: held in English", shown)
    check.ok(shown["send"] == ["Confirm ▶"], "A3: the row reads Confirm ▶", shown)
    check.ok(
        len(shown["hints"]) == 1 and not HANGUL.search(shown["hints"][0]),
        "A3: the hint is in English",
        shown["hints"],
    )
    check.ok(shown["turnEnd"] == 0, "A3: and there is no turn-end row", shown)
    check.ok(not posts, "A3: nothing was sent", posts)
    finish_page(context, rec, "A3")


def scenario_reward_spy(browser, base: str) -> None:
    print("[B] a reward Spy that can be taken back: sent, held before the reshuffle")
    context, page, rec, posts = open_save(
        browser, base, "held-reward-spy", "reward-spy"
    )
    decision = page.evaluate("state.summary.decision")
    offers = rows(page, SPY_POST)
    check.ok(
        decision["kind"] == "combat_reward_spy"
        and decision["owner"] == 0
        and len({a["arguments"]["post_id"] for a in offers}) >= 2
        and all(a["undoable"] and not a["sent_by_turn_end"] for a in offers),
        "the save rests at seat 0's reward Spy, every post undoable and sent at once",
        decision,
    )
    check.ok(
        page.locator("#actions .irreversible-badge").count() == 0,
        "B1: no post row carries the 되돌리기 불가 badge",
    )
    check.ok(
        page.locator("#actions .strength-preview").count() == 0,
        "B1: no post row carries a strength preview",
    )
    round_number = page.evaluate("state.summary.round_number")
    first = offers[0]
    click_row(page, first["index"])
    sent = bodies(posts, "actions")
    check.ok(
        len(sent) == 1 and sent[0]["index"] == first["index"],
        "B1: a click on a post row sends it at once (one POST /actions)",
        posts,
    )
    summary = page.evaluate("state.summary")
    check.ok(
        summary["confirmation"] == 0 and summary["decision"] is None,
        "B1: the unit end is held with a chance outcome pending",
        (summary["confirmation"], summary["decision"]),
    )
    row = page.locator(".turn-end-row button")
    check.ok(
        row.count() == 1 and row.inner_text() == "턴 종료 ▶",
        "B1: the turn-end row reads 턴 종료 ▶",
        row.all_inner_texts(),
    )
    check.ok(page.locator(".held-send-row").count() == 0, "B1: no 확정 ▶ row")
    info = page.inner_text("#decision-info")
    check.ok("다음:" not in info, "B1: no next-seat line", info)
    undo = [u for u in summary["undo"] if u["seat"] == 0]
    check.ok(
        undo == [{"seat": 0, "steps": 1}]
        and page.locator(".undo-row button").count() == 1,
        "B1: the undo row offers one step",
        undo,
    )

    page.locator(".undo-row button").click()
    assert settled(page, 20)
    summary = page.evaluate("state.summary")
    check.ok(
        len(bodies(posts, "undo")) == 1
        and summary["confirmation"] is None
        and summary["decision"] is not None
        and summary["decision"]["kind"] == "combat_reward_spy"
        and summary["decision"]["owner"] == 0,
        "B2: the undo is back at the reward Spy",
        (summary["confirmation"], summary["decision"]),
    )
    other = next(
        a
        for a in rows(page, SPY_POST)
        if a["arguments"]["post_id"] != first["arguments"]["post_id"]
    )
    click_row(page, other["index"])
    summary = page.evaluate("state.summary")
    check.ok(
        len(bodies(posts, "actions")) == 2 and summary["confirmation"] == 0,
        "B2: the Spy on another post is held again",
        summary["confirmation"],
    )
    check.ok(
        summary["round_number"] == round_number,
        "B2: the round has not moved before the press",
        summary["round_number"],
    )
    last = page.evaluate(LAST_SEAT0_JS)
    check.ok(
        last is not None and last["arguments"] == other["arguments"],
        "B2: the log shows the Spy on the other post",
        last,
    )
    page.locator(".turn-end-row button").click()
    assert settled(page, 20)
    summary = page.evaluate("state.summary")
    check.ok(len(bodies(posts, "confirm")) == 1, "B2: one POST /confirm", posts)
    check.ok(summary["confirmation"] != 0, "B2: the press clears the hold", summary)
    check.ok(
        summary["round_number"] > round_number,
        "B2: the next round started only after the press",
        (round_number, summary["round_number"]),
    )
    finish_page(context, rec, "B")


def scenario_spy_post(browser, base: str) -> None:
    print("[C] a reward Spy that cannot be taken back: a board post click holds it")
    context, page, rec, posts = open_save(browser, base, "held-spy-post", "spy-post")
    offers = rows(page, SPY_POST)
    check.ok(
        page.evaluate("state.summary.decision.kind") == "combat_reward_spy"
        and offers
        and all(a["sent_by_turn_end"] for a in offers),
        "the save rests at seat 0's reward Spy, every post sent by the press",
    )
    check.ok(
        page.locator("#actions .irreversible-badge").count() == 0,
        "C1: no post row carries the 되돌리기 불가 badge",
    )
    post = page.evaluate(CLICKABLE_POST_JS, [a["arguments"]["post_id"] for a in offers])
    check.ok(post is not None, "C1: a lit Spy post can be clicked on the board")
    if post is None:
        finish_page(context, rec, "C")
        return
    (offer,) = [a for a in offers if a["arguments"]["post_id"] == post]
    hotspot = page.locator(f".spy-post-hotspot[data-post='{post}']")
    hotspot.click()
    assert settled(page, 20)
    shown = held(page)
    check.ok(shown["picked"] == [post], "C1: the clicked post is .picked", shown)
    check.ok(shown["held"] == [offer["index"]], "C1: its row is .held-choice", shown)
    check.ok(shown["send"] == ["확정 ▶"], "C1: the banner row reads 확정 ▶", shown)
    check.ok(not posts, "C1: no POST for the board click", posts)
    hotspot.click()
    assert settled(page, 20)
    shown = held(page)
    check.ok(
        shown["picked"] == [post]
        and shown["held"] == [offer["index"]]
        and shown["send"] == ["확정 ▶"]
        and not posts,
        "C1: a second click on the post keeps it held",
        shown,
    )
    page.locator(".held-send-row button").click()
    assert settled(page, 20)
    sent = bodies(posts, "actions")
    check.ok(
        len(sent) == 1 and sent[0]["index"] == offer["index"],
        "C1: 확정 ▶ sends exactly one POST /actions, the held post",
        posts,
    )
    check.ok(
        page.evaluate("state.summary.confirmation") != 0,
        "C1: the seat is not held for an extra press",
    )
    last = page.evaluate(LAST_SEAT0_JS)
    check.ok(
        last is not None
        and last["action_id"] == SPY_POST
        and last["arguments"] == offer["arguments"],
        "C1: the log shows the Spy on the held post",
        last,
    )
    finish_page(context, rec, "C")


def main() -> None:
    saves = tempfile.mkdtemp(prefix="dune-held-choice-e2e-")
    found = json.loads(
        subprocess.run(
            [
                str(REPO / ".venv/bin/python"),
                str(Path(__file__).parent / "fixtures/held_choice_saves.py"),
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
            scenario_defense(browser, server.base)
            scenario_defense_english(browser, server.base)
            scenario_reward_spy(browser, server.base)
            scenario_spy_post(browser, server.base)
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
