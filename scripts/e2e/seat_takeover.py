"""E2E of a person's seat handed to the AI mid-game, and taken back.

User request 2026-11-07: "플레이하던 사람이 나가거나, 본인이 원하는 경우 ai가
대신 이어서 플레이할 수 있게 하기"; the user's choices the same day: the
seat's player (its seat card's button) or the host (``/admin``) hands it
over, its player takes it back at any time, and every table sees a badge on
the seat and a line in the log (sessions.py ``hand_to_ai``, ``take_back``).

A. Remote: two players and the host. The player's own button asks first (a
   dismissed dialog changes nothing), the AI plays the seat on while the
   other player plays, the badge and the log line reach both tables, the
   player's table offers no action for the seat, and "직접 두기" takes it
   back. Then the host hands the seat over from ``/admin``.
B. Open server: one screen, one person; handing the only person's seat over
   plays the game to its end, the log's cards of the AI's steps there carry
   the AI's badge, and the finished game's review walks every step.
"""

from __future__ import annotations

import json
import shutil
import time

from common import (
    E2E_TMP,
    LAPTOP_VIEWPORT,
    SERVER_LOG_COPY,
    Check,
    chrome,
    open_context,
    server,
)

KEY = "e2e-seat-takeover-key-01"  # 16+ characters: the server refuses shorter keys
# The taking-over AI is the app AI, so the server runs without a search
# network: a bare server would read the main checkout's default
# checkpoints/play/search.pt and hand the seat to the search AI (2026-11-08).
NO_NETWORK = ("--search-checkpoint", str(E2E_TMP / "seat-takeover-missing.pt"))
SEED = 5
check = Check()
dialogs: list[str] = []
answer = {"accept": True}


def answer_dialog(dialog) -> None:
    dialogs.append(dialog.message)
    if answer["accept"]:
        dialog.accept()
    else:
        dialog.dismiss()


def wait_js(page, predicate: str, label: str, timeout: float = 10.0, arg=None) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if page.evaluate(predicate, arg):
            return check.ok(True, label)
        time.sleep(0.05)
    return check.ok(
        False, label, page.evaluate("state.summary && state.summary.players")
    )


def summary(page, game_id: str) -> dict:
    return page.evaluate(f"fetch('/games/{game_id}').then((r) => r.json())")


SEAT_JS = """(seat) => {
  const card = document.querySelector(`#seats .seat[data-seat='${seat}']`);
  if (!card) return null;
  const button = card.querySelector('.seat-hands');
  const rect = button ? button.getBoundingClientRect() : null;
  const box = card.getBoundingClientRect();
  return {
    ai: [...card.querySelectorAll('.badge.ai')].map((b) => b.textContent),
    button: button ? {text: button.textContent, to: button.dataset.seatHands,
      inside: rect.left >= box.left - 0.5 && rect.right <= box.right + 0.5} : null,
  };
}"""

LOG_ROWS_JS = """() =>
  [...document.querySelectorAll('#turn-history .seat-change-marker')]
  .map((row) => row.textContent)"""

# The badges of one seat's turn cards in the log, before and after the log's
# first seat-change row.
CARD_BADGES_JS = """(seat) => {
  const seen = {before: [], after: []};
  let changed = false;
  for (const node of document.getElementById('turn-history').children) {
    if (node.classList.contains('seat-change-marker')) { changed = true; continue; }
    if (node.dataset.actor !== String(seat)) continue;
    const badge = node.querySelector('.turn-head .badge');
    (changed ? seen.after : seen.before).push(
      {text: badge.textContent, ai: badge.classList.contains('ai')});
  }
  return seen;
}"""


def seat(page, number: int) -> dict:
    return page.evaluate(SEAT_JS, number)


def drive_player(page, game_id: str, seat_number: int, steps: int) -> int:
    """Seat ``seat_number`` plays action 0 (or presses) whenever it must act."""
    done = 0
    for _ in range(steps * 20):
        if done >= steps:
            break
        now = summary(page, game_id)
        if now["finished"]:
            break
        owner = (
            now["confirmation"]
            if isinstance(now["confirmation"], int)
            else (now["decision"] or {}).get("owner")
        )
        if owner != seat_number or now["thinking"] is not None:
            time.sleep(0.05)
            continue
        page.wait_for_function(
            "(rev) => state.summary && state.summary.revision === rev"
            " && !state.busy && refreshFlight === null",
            arg=now["revision"],
        )
        if isinstance(now["confirmation"], int):
            page.evaluate("confirmTurn()")
        else:
            page.wait_for_function("state.actions !== null")
            page.evaluate("applyAction(0)")
        page.wait_for_function(
            "(rev) => state.summary && state.summary.revision !== rev"
            " && !state.busy && refreshFlight === null",
            arg=now["revision"],
        )
        done += 1
    return done


def seat_players(base: str, host, guest) -> str:
    """The host makes a game of two people and two app AIs; host sits at 0,
    the guest at 1."""
    host.goto(f"{base}/#admin={KEY}")
    host.wait_for_function("state.server !== null")
    made = host.evaluate(
        "async (body) => { const r = await fetch('/games', {method: 'POST',"
        " headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});"
        " return r.json(); }",
        {"seats": ["human", "human", "app_ai", "app_ai"], "game_seed": SEED},
    )
    game_id = made["game_id"]
    for page, number, name in ((host, 0, "호스트"), (guest, 1, "친구")):
        page.goto(f"{base}/#game={game_id}")
        page.wait_for_selector("#lobby-screen:not([hidden])")
        page.fill("#lobby-name", name)
        page.click(f"#lobby-seats li[data-seat='{number}'] button")
        page.wait_for_selector("#game-screen:not([hidden])")
        page.wait_for_function(
            "(seat) => state.me && state.me.seats.includes(seat)"
            " && state.view !== null && refreshFlight === null",
            arg=number,
        )
    return game_id


def scenario_remote(base: str, browser) -> None:
    print("[A] a player hands its seat to the AI and takes it back; the host too")
    _, host, _ = open_context(browser, "host", LAPTOP_VIEWPORT)
    _, guest, _ = open_context(browser, "guest", LAPTOP_VIEWPORT)
    guest.on("dialog", answer_dialog)
    game_id = seat_players(base, host, guest)

    mine = seat(guest, 1)
    check.ok(
        mine is not None
        and mine["button"] is not None
        and mine["button"]["to"] == "ai"
        and mine["button"]["text"] == "AI에게 맡기기",
        "the guest's own seat card has the hand-over button",
        mine,
    )
    check.ok(mine["button"]["inside"], "the button stays inside the seat card", mine)
    check.ok(
        seat(guest, 0)["button"] is None and seat(host, 1)["button"] is None,
        "nobody gets a button on another person's seat",
    )

    answer["accept"] = False
    guest.click("#seats .seat[data-seat='1'] .seat-hands")
    time.sleep(0.3)
    check.ok(
        len(dialogs) == 1 and "AI에게 맡길까요" in dialogs[0],
        "the hand-over asks first",
        dialogs,
    )
    check.ok(
        summary(guest, game_id)["players"][1]["ai"] is None,
        "a dismissed dialog hands nothing over",
    )

    answer["accept"] = True
    guest.click("#seats .seat[data-seat='1'] .seat-hands")
    wait_js(
        guest,
        "state.summary.players[1].ai === 'app_ai' && !state.busy",
        "the guest's table learns the AI plays seat 1",
    )
    for name, page in (("guest", guest), ("host", host)):
        wait_js(
            page,
            "(() => { const c ="
            " document.querySelector(\"#seats .seat[data-seat='1']\");"
            " return c && [...c.querySelectorAll('.badge.ai')]"
            ".some((b) => b.textContent === 'AI가 둠'); })()",
            f"the {name}'s table shows the AI badge on seat 1",
        )
        wait_js(
            page,
            "[...document.querySelectorAll('#turn-history .seat-change-marker')]"
            ".some((r) => r.textContent.includes('AI가 맡음'))",
            f"the {name}'s log shows the hand-over line",
        )
    check.ok(
        seat(guest, 1)["button"]["to"] == "human"
        and seat(guest, 1)["button"]["text"] == "직접 두기",
        "the guest's button now takes the seat back",
        seat(guest, 1),
    )

    played = drive_player(host, game_id, 0, 6)
    check.ok(played >= 3, "the host plays on while the AI answers seat 1", played)
    now = summary(host, game_id)
    check.ok(not now["finished"], "the game is still on")
    check.ok(
        guest.evaluate("state.actions === null && !isMyTurn(state.summary)"),
        "the guest's table never offers seat 1's moves",
        guest.evaluate("state.actions && state.actions.actions.length"),
    )

    guest.click("#seats .seat[data-seat='1'] .seat-hands")
    wait_js(
        guest,
        "state.summary.players[1].ai === null && !state.busy",
        "'직접 두기' takes the seat back",
    )
    wait_js(
        host,
        "[...document.querySelectorAll('#turn-history .seat-change-marker')]"
        ".some((r) => r.textContent.includes('다시 사람이 둠'))",
        "the host's log shows the take-back line",
    )
    check.ok(not seat(host, 1)["ai"], "the AI badge is gone from seat 1", seat(host, 1))
    # The guest plays seat 1 again when it comes round.
    check.ok(
        drive_player(guest, game_id, 1, 1) + drive_player(host, game_id, 0, 30) >= 1,
        "the people play on",
    )

    print("[A2] the host hands seat 1 over from /admin")
    _, admin, _ = open_context(browser, "admin")
    admin.on("dialog", answer_dialog)
    admin.goto(f"{base}/admin#admin={KEY}")
    admin.wait_for_selector("#panels:not([hidden])")
    row = f".game[data-game-id='{game_id}'] li[data-seat='1']"
    admin.wait_for_selector(f"{row} button")
    buttons = admin.locator(f"{row} button").all_text_contents()
    check.ok("AI에게 맡기기" in buttons, "the admin row offers the hand-over", buttons)
    check.ok(
        "AI에게 맡기기"
        not in admin.locator(
            f".game[data-game-id='{game_id}'] li[data-seat='2']"
        ).text_content(),
        "an AI seat has no hand-over button",
    )
    admin.locator(f"{row} button", has_text="AI에게 맡기기").click()
    admin.wait_for_selector(f"{row} .seat-ai")
    check.ok(
        admin.locator(f"{row} .seat-ai").text_content() == "AI가 둠",
        "the admin row says the AI plays it",
    )
    wait_js(
        guest,
        "state.summary.players[1].ai === 'app_ai'",
        "the guest's table learns of the host's hand-over",
    )
    check.ok(
        guest.evaluate(
            "fetch('/games/' + state.gameId + '/seats/1/human', {method: 'POST'})"
            ".then((r) => r.status)"
        )
        == 200,
        "the guest may take back what the host handed over",
    )
    check.ok(
        admin.evaluate(
            "(id) => fetch(`/games/${id}/seats/0/human`, {method: 'POST'})"
            ".then((r) => r.status)",
            game_id,
        )
        in (400, 403),
        "the host takes nobody's seat back",
    )


def scenario_open(base: str, browser) -> None:
    print("[B] one screen hands its only person's seat over: the AI plays to the end")
    _, page, _ = open_context(browser, "open")
    page.on("dialog", answer_dialog)
    page.goto(base + "/")
    page.wait_for_function(
        "state.server !== null"
        " && document.querySelectorAll('#seat-selects select').length === 4"
    )
    page.fill("#opt-seed", str(SEED))
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    button = seat(page, 0)["button"]
    check.ok(
        button is not None and button["to"] == "ai",
        "the open table's person seat has the button",
        button,
    )
    page.click("#seats .seat[data-seat='0'] .seat-hands")
    wait_js(
        page, "state.summary && state.summary.finished", "the AI plays to the end", 60
    )
    check.ok(
        seat(page, 0)["button"] is None,
        "a finished game offers no button",
        seat(page, 0),
    )
    rows = page.evaluate(LOG_ROWS_JS)
    check.ok(len(rows) == 1, "the log keeps the one hand-over line", rows)
    cards = page.evaluate(CARD_BADGES_JS, 0)
    mine_before, mine_after = cards["before"], cards["after"]
    check.ok(
        bool(mine_after)
        and all(c["ai"] and c["text"] == "AI가 둠" for c in mine_after),
        "the log's cards of the AI's steps for seat 0 carry the AI badge",
        mine_after[:3],
    )
    check.ok(
        all(not c["ai"] for c in mine_before),
        "the person's own earlier cards keep the person's badge",
        mine_before[:3],
    )

    page.click("#standings button:has-text('리플레이 검토')")
    page.wait_for_function("state.review !== null && state.review.phase !== null")
    review = page.evaluate(
        "({live: state.review.liveIndex.length, steps: state.review.meta.step_count})"
    )
    check.ok(
        review["live"] == review["steps"],
        "the review counts the seat change as no step",
        review,
    )
    page.click("#review-first")
    page.wait_for_function("state.review && state.review.cursor === 0")
    page.click("#review-last")
    page.wait_for_function(
        "state.review && state.review.cursor === state.review.meta.step_count"
    )
    check.ok(
        len(page.evaluate(LOG_ROWS_JS)) == 1,
        "the review's log at the end shows the hand-over line",
    )


def main() -> None:
    with (
        server("--remote", "--admin-key", KEY, *NO_NETWORK) as (base, server_log),
        chrome() as browser,
    ):
        try:
            scenario_remote(base, browser)
        finally:
            shutil.copy(server_log, SERVER_LOG_COPY)
        text = server_log.read_text()
        check.ok("Traceback" not in text, "no server traceback (remote)")
    with server(*NO_NETWORK) as (base, server_log), chrome() as browser:
        scenario_open(base, browser)
        check.ok(
            "Traceback" not in server_log.read_text(), "no server traceback (open)"
        )
    print(json.dumps({"dialogs": len(dialogs)}))
    check.finish()


if __name__ == "__main__":
    main()
