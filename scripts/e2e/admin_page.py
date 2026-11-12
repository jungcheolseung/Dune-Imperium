"""E2E for the host's admin page (``/admin``, static/admin.html).

A guest sees only the not-signed-in message; the host (admin link) sees the
server, machine, games, saves and log sections, acts on games and saves
through the page's own buttons, and switches its language. The page also has
to fit a 390 px phone, and the main page's host home links to it.
"""

from __future__ import annotations

import json
import shutil

from common import (
    SERVER_LOG_COPY,
    Check,
    chrome,
    open_context,
    server,
)

KEY = "e2e-admin-page-key-0001"  # 16+ characters: the server refuses shorter keys
check = Check()
# Every dialog the host's page opens, and whether the next one is accepted.
dialogs: list[tuple[str, str]] = []
answer = {"accept": True}


def answer_dialog(dialog) -> None:
    dialogs.append((dialog.type, dialog.message))
    if answer["accept"]:
        dialog.accept()
    else:
        dialog.dismiss()


def post_json(page, path: str, body: dict) -> dict:
    """A POST from the page's own browser context (its cookies, no markup)."""
    return page.evaluate(
        "async ([path, body]) => { const r = await fetch(path, {method: 'POST',"
        " headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});"
        " return {status: r.status, body: await r.json().catch(() => null)}; }",
        [path, body],
    )


def wait_text(page, selector: str, needle: str, label: str, timeout=8000) -> bool:
    try:
        page.wait_for_function(
            "([selector, needle]) => { const n = document.querySelector(selector);"
            " return n !== null && n.textContent.includes(needle); }",
            arg=[selector, needle],
            timeout=timeout,
        )
        return check.ok(True, label)
    except Exception as error:  # a Playwright timeout
        return check.ok(False, label, str(error)[:200])


def wait_count(page, selector: str, count: int, label: str, timeout=8000) -> bool:
    try:
        page.wait_for_function(
            "([selector, count]) =>"
            " document.querySelectorAll(selector).length === count",
            arg=[selector, count],
            timeout=timeout,
        )
        return check.ok(True, label)
    except Exception as error:
        count_now = page.evaluate(
            "(s) => document.querySelectorAll(s).length", selector
        )
        return check.ok(False, label, f"{count_now}: {str(error)[:120]}")


def sign_in_to_admin(page, base: str) -> None:
    page.goto(f"{base}/admin#admin={KEY}")
    page.wait_for_selector("#panels:not([hidden])")
    page.wait_for_selector("#server-list dt")


def main() -> None:
    with (
        server("--remote", "--admin-key", KEY) as (base, server_log),
        chrome() as browser,
    ):
        _, guest, _ = open_context(browser, "guest")
        _, host, _ = open_context(browser, "host")
        try:
            scenario(base, host, guest, browser)
        finally:
            shutil.copy(server_log, SERVER_LOG_COPY)
        check.ok(
            "Traceback" not in server_log.read_text(), "no server traceback in its log"
        )
    check.finish()


def scenario(base: str, host, guest, browser) -> None:
    print("[1] a guest sees only the not-signed-in message")
    host.on("dialog", answer_dialog)
    requests: list[str] = []
    guest.on("request", lambda r: requests.append(r.url.replace(base, "")))
    guest.goto(f"{base}/admin")
    guest.wait_for_selector("#signed-out:not([hidden])")
    check.ok(guest.is_hidden("#panels"), "no sections for a guest")
    check.ok(
        guest.text_content("#signed-out-how").strip() != "", "it says how to get in"
    )
    check.ok(
        not any(r.startswith("/admin/status") for r in requests),
        "a guest never asks for the status",
        requests,
    )
    check.ok(
        guest.evaluate("fetch('/admin/status').then((r) => r.status)") == 403,
        "the status is 403 for a guest",
    )

    print("[2] the admin link signs the host in and leaves the address bar")
    sign_in_to_admin(host, base)
    check.ok(
        "admin#" not in host.url and "#admin" not in host.url,
        "key left the URL",
        host.url,
    )
    status = host.evaluate("fetch('/admin/status').then((r) => r.json())")
    codec = str(status["server"]["action_codec"])
    shown = host.text_content("#server-list")
    check.ok(codec in shown, "the server section shows the codec number", codec)
    check.ok(
        status["server"]["commit"] is None or status["server"]["commit"][:7] in shown,
        "the server section shows the commit",
    )
    check.ok(
        host.locator("#machine-list dt").count() >= 7, "the machine section is filled"
    )
    check.ok(host.locator("#log .log-line").count() > 0, "the log section has lines")
    check.ok(host.is_visible("#last-refresh"), "the time of the last refresh shows")
    check.ok(
        host.locator("#games .game").count() == 0
        and "없" in host.text_content("#games"),
        "no games yet: a short none line",
    )

    print("[3] a wrong key shows up in the log as a warning")
    guest.evaluate(
        "fetch('/auth/admin', {method: 'POST', headers: {'Content-Type':"
        " 'application/json'}, body: JSON.stringify({key: 'not-the-key'})})"
    )
    host.click("#refresh")
    wait_count(
        host, "#log .log-line.level-WARNING", 1, "the wrong key is a WARNING line"
    )
    check.ok(
        "Wrong admin key" in host.text_content("#log .log-line.level-WARNING"),
        "the line names the wrong key",
    )

    print("[4] a game made through the API shows with its seats")
    made = post_json(
        host,
        "/games",
        {"seats": ["human", "human", "heuristic", "random"], "seats_at_start": False},
    )
    check.ok(made["status"] == 200, "game created", made)
    game_id = made["body"]["game_id"]
    host.click("#refresh")
    wait_count(host, "#games .game", 1, "one game block")
    block = host.locator(f"#games .game[data-game-id='{game_id}']")
    check.ok(block.count() == 1, "the block is the new game")
    check.ok(game_id[:8] in block.locator("h3").text_content(), "short id in the title")
    check.ok(block.locator(".seats li").count() == 4, "four seats listed")
    seats_text = block.locator(".seats").text_content()
    check.ok(
        seats_text.count("빈 자리") == 2
        and "휴리스틱" in seats_text
        and "랜덤" in seats_text,
        "open seats and AI kinds named",
        seats_text,
    )

    print(
        "[5] a guest claiming a seat shows with name and online dot; release frees it"
    )
    guest.goto(f"{base}/#game={game_id}")
    guest.wait_for_selector("#lobby-screen:not([hidden])")
    guest.fill("#lobby-name", "<b id=xss>친구</b>")
    guest.click("#lobby-seats li[data-seat='1'] button")
    guest.wait_for_selector("#game-screen:not([hidden])")
    host.click("#refresh")
    wait_text(
        host,
        f".game[data-game-id='{game_id}'] li[data-seat='1']",
        "<b id=xss>친구</b>",
        "the claimed seat shows the name as text",
    )
    check.ok(
        host.evaluate("document.getElementById('xss')") is None,
        "a name never becomes markup",
    )
    wait_count(
        host,
        f".game[data-game-id='{game_id}'] li[data-seat='1'] .dot.online",
        1,
        "the online dot shows",
    )
    answer["accept"] = True
    # The release button is the row's danger one; a person's seat of a
    # running game also offers "AI에게 맡기기" (seat_takeover.py), claimed
    # or not, so that one stays.
    host.click(f".game[data-game-id='{game_id}'] li[data-seat='1'] button.danger")
    wait_count(
        host,
        f".game[data-game-id='{game_id}'] li[data-seat='1'] button.danger",
        0,
        "release removed the seat's release button",
    )
    seat_one = host.text_content(f".game[data-game-id='{game_id}'] li[data-seat='1']")
    check.ok("빈 자리" in seat_one, "the seat is open again", seat_one)
    guest.goto(f"{base}/")  # leave the room: its stream would otherwise stay open

    print("[6] room link, save now, load")
    host.click(f".game[data-game-id='{game_id}'] .actions button:first-child")
    link = host.input_value(f".game[data-game-id='{game_id}'] .room-link")
    check.ok(link == f"{base}/#game={game_id}", "the room link", link)
    saves_before = len(host.evaluate("fetch('/saves').then((r) => r.json())"))
    host.click(f".game[data-game-id='{game_id}'] .actions button:nth-child(2)")
    wait_count(host, "#saves .save", saves_before + 1, "save now adds a save")
    check.ok(
        len(host.evaluate("fetch('/saves').then((r) => r.json())")) == saves_before + 1,
        "the server holds the new save",
    )
    host.click("#saves .save .actions button:first-child")
    wait_count(host, "#games .game", 2, "load made a second game")
    check.ok(
        not host.is_hidden("#status")
        and not host.evaluate(
            "document.getElementById('status').classList.contains('error')"
        ),
        "the status line says which game it became",
    )
    ids = host.evaluate(
        "[...document.querySelectorAll('#games .game')].map((g) => g.dataset.gameId)"
    )
    new_id = next(i for i in ids if i != game_id)
    check.ok(
        new_id[:8] in host.text_content("#status"), "the status names the new game"
    )

    print("[7] delete game and delete save, each after a confirm")
    answer["accept"] = True
    host.click(f".game[data-game-id='{new_id}'] .actions button.danger")
    wait_count(host, "#games .game", 1, "the loaded game is gone")
    answer["accept"] = False
    host.click(f".game[data-game-id='{game_id}'] .actions button.danger")
    check.ok(
        host.locator("#games .game").count() == 1, "a dismissed confirm deletes nothing"
    )
    answer["accept"] = True
    host.click(f".game[data-game-id='{game_id}'] .actions button.danger")
    wait_count(host, "#games .game", 0, "the first game is gone")
    answer["accept"] = True
    host.click("#saves .save .actions button.danger")
    wait_count(host, "#saves .save", saves_before, "the save is gone")

    print("[8] an error from a call shows in the status line, never an alert")
    made = post_json(
        host,
        "/games",
        {"seats": ["human", "human", "heuristic", "random"], "seats_at_start": False},
    )
    gone = made["body"]["game_id"]
    host.click("#refresh")
    wait_count(host, "#games .game", 1, "a game to delete behind the page's back")
    host.evaluate(f"fetch('/games/{gone}', {{method: 'DELETE'}})")
    host.click(f".game[data-game-id='{gone}'] .actions button:nth-child(2)")  # save now
    wait_count(host, "#status.error", 1, "a failing call shows an error line")
    check.ok(
        host.text_content("#status").strip() != "",
        "the error line has the server's text",
    )

    print("[9] the language toggle")
    heading = lambda: host.text_content("#panels section:first-child h2")  # noqa: E731
    check.ok(heading() == "서버", "Korean heading", heading())
    host.click("#language-toggle")
    check.ok(heading() == "Server", "English heading", heading())
    check.ok(
        host.evaluate("localStorage.getItem('dune.language')") == "en", "choice stored"
    )
    check.ok(host.text_content("#language-toggle") == "한국어", "toggle names Korean")
    check.ok("Games in progress" in host.text_content("#panels"), "all headings switch")
    host.click("#language-toggle")
    check.ok(heading() == "서버", "back to Korean", heading())

    print("[10] the main page links to the admin page for the host only")
    host.goto(f"{base}/")
    host.wait_for_selector("#setup-screen:not([hidden])")
    host.wait_for_selector("#open-admin:not([hidden])")
    check.ok(host.is_visible("#open-admin"), "host home shows the admin link")
    host.click("#open-admin")
    host.wait_for_selector("#panels:not([hidden])")
    check.ok(host.url.endswith("/admin"), "the link opens /admin", host.url)
    guest.goto(f"{base}/")
    guest.wait_for_selector("#landing-screen:not([hidden])")
    check.ok(not guest.is_visible("#open-admin"), "a guest has no admin link")

    print("[11] a 390 px phone does not scroll sideways")
    phone_ctx = browser.new_context(viewport={"width": 390, "height": 844})
    phone = phone_ctx.new_page()
    phone.on("pageerror", lambda e: check.ok(False, "phone page error", str(e)))
    phone.goto(f"{base}/admin#admin={KEY}")
    phone.wait_for_selector("#panels:not([hidden])")
    phone.wait_for_selector("#log .log-line")
    post_json(phone, "/games", {"seats": ["human", "human", "heuristic", "random"]})
    phone.click("#refresh")
    phone.wait_for_selector("#games .game")
    widths = phone.evaluate(
        "({scroll: document.documentElement.scrollWidth, inner: window.innerWidth})"
    )
    check.ok(
        widths["scroll"] <= widths["inner"],
        "no horizontal scroll at 390 px",
        json.dumps(widths),
    )
    phone_ctx.close()
    check.ok(
        all(kind == "confirm" for kind, _ in dialogs) and len(dialogs) == 5,
        "only the five confirms, never an alert",
        dialogs,
    )


if __name__ == "__main__":
    main()
