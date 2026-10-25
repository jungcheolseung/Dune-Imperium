"""Remote E2E: a room that draws its seats when a player starts it.

User decision 2026-10-25 (play feedback item 5): with "Random seating"
checked, a remote room shows nobody the game until every human place is
taken; then any player in the room (or the host) presses "게임 시작", the
server deals the people to the human seats at random
(sessions.py start_game) and every page goes to the table at its drawn
seat. Who sits where is a table convention, not a rule (the rules do not
seat players; the First Player comes from the Objectives [Main p. 5]).

[1] the host creates the room with the box checked: the lobby is the
    waiting room, 0 of 2 joined, no start button;
[2] the host joins and stays in the room (no game screen, no seat read);
[3] a guest joins through the link: both pages show 2 of 2 and the start
    button;
[4] the guest starts: both pages reach the table, each at a different
    human seat, with its own name on it.
"""

from __future__ import annotations

import os
import shutil
import tempfile

from common import SERVER_LOG_COPY, Check, chrome, open_context, server, set_rule_options

KEY = "e2e-room-start-key"
check = Check()
SHOTS = os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(prefix="dune-e2e-room-start-")

ROOM_JS = """() => ({
  title: el('lobby-title').textContent,
  status: el('lobby-status').textContent,
  start: Boolean(document.getElementById('lobby-start')),
  join: [...document.querySelectorAll('.waiting-room-actions button')]
    .map((b) => b.textContent),
  waiting: Boolean(state.summary && state.summary.awaiting_start),
  game: !el('game-screen').hidden,
  lobby: !el('lobby-screen').hidden,
})"""


def wait_for_setup(page) -> None:
    page.wait_for_selector("#setup-screen:not([hidden])")
    page.wait_for_function(
        "state.server !== null"
        " && document.querySelectorAll('#seat-selects select').length === 4"
    )


def join(page, name: str) -> None:
    page.fill("#lobby-name", name)
    page.click(".waiting-room-actions button")
    page.wait_for_function("state.me && state.me.seats.length === 1 && !state.busy")


def main() -> None:
    with (
        server("--remote", "--admin-key", KEY, "--seating", "random") as (
            base,
            server_log,
        ),
        chrome() as browser,
    ):
        _, host, _ = open_context(browser, "room-host")
        _, guest, _ = open_context(browser, "room-guest")
        try:
            print("[1] the host creates a room that draws its seats at the start")
            host.goto(f"{base}/#admin={KEY}")
            wait_for_setup(host)
            check.ok(host.is_checked("#opt-shuffle-seats"), "the box opens checked")
            host.select_option("#seat-selects select[data-seat='0']", "human")
            host.select_option("#seat-selects select[data-seat='1']", "human")
            host.select_option("#seat-selects select[data-seat='2']", "heuristic")
            host.select_option("#seat-selects select[data-seat='3']", "heuristic")
            set_rule_options(host)
            with host.expect_request(
                lambda r: r.method == "POST" and r.url.endswith("/games")
            ) as sent:
                host.click("#create-game")
            check.ok(
                sent.value.post_data_json.get("seats_at_start") is True,
                "POST /games asks for the seats at the start",
                sent.value.post_data_json,
            )
            host.wait_for_selector("#lobby-screen:not([hidden])")
            game_id = host.evaluate("state.gameId")
            room = host.evaluate(ROOM_JS)
            check.ok(
                room["waiting"] and room["title"] == "게임 대기실",
                "the lobby is the waiting room",
                room,
            )
            check.ok(
                "0/2" in room["status"] and not room["start"],
                "0 of 2 joined, no start button",
                room,
            )

            print("[2] the host joins and stays in the room")
            join(host, "호스트")
            room = host.evaluate(ROOM_JS)
            check.ok(
                room["lobby"] and not room["game"] and "1/2" in room["status"],
                "the host waits in the room, 1 of 2",
                room,
            )
            refused = host.evaluate(
                """async (gameId) => (await fetch(
                  `/games/${gameId}/snapshot?seat=${state.me.seats[0]}`)).status""",
                game_id,
            )
            check.ok(refused == 409, "no seat is read before the start", refused)
            quiet = host.evaluate(
                "({mine: isMyTurn(state.summary), title: document.title,"
                " base: baseTitle()})"
            )
            check.ok(
                not quiet["mine"] and quiet["title"] == quiet["base"],
                "a place in the waiting room is never 'your turn'",
                quiet,
            )

            print("[3] a guest joins through the room link, losing a join race")
            guest.goto(f"{base}/#game={game_id}")
            guest.wait_for_selector("#lobby-screen:not([hidden])")
            # As if both had pressed "join" at once: the guest asks for the
            # place the host has just taken and gets the next free one.
            taken = host.evaluate("state.me.seats[0]")
            guest.fill("#lobby-name", "친구")
            guest.evaluate("(seat) => claimSeat(seat)", taken)
            guest.wait_for_function(
                "state.me && state.me.seats.length === 1 && !state.busy"
            )
            raced = guest.evaluate(
                "({seat: state.me.seats[0],"
                " error: !document.getElementById('lobby-error').hidden})"
            )
            check.ok(
                raced["seat"] != taken and not raced["error"],
                "the join race takes the next free place without an error",
                (taken, raced),
            )
            for page, label in ((guest, "guest"), (host, "host")):
                page.wait_for_function("Boolean(document.getElementById('lobby-start'))")
                room = page.evaluate(ROOM_JS)
                check.ok(
                    "2/2" in room["status"] and room["start"] and room["waiting"],
                    f"{label}: 2 of 2 and the start button",
                    room,
                )
            guest.screenshot(path=f"{SHOTS}/waiting_room_ready.png")

            print("[4] the guest starts: both pages go to the table at drawn seats")
            guest.click("#lobby-start")
            for page in (guest, host):
                page.wait_for_selector("#game-screen:not([hidden])")
                page.wait_for_function(
                    "state.view !== null && refreshFlight === null && !state.busy"
                )
            seats = {
                label: page.evaluate("state.me.seats")
                for page, label in ((host, "host"), (guest, "guest"))
            }
            humans = host.evaluate(
                "state.summary.seats.flatMap((k, i) => (k === 'human' ? [i] : []))"
            )
            check.ok(
                sorted(seats["host"] + seats["guest"]) == sorted(humans),
                "the two players hold the two human seats",
                (seats, humans),
            )
            names = host.evaluate(
                "Object.fromEntries(state.summary.players.map((p) => [p.seat, p.name]))"
            )
            check.ok(
                names[str(seats["host"][0])] == "호스트"
                and names[str(seats["guest"][0])] == "친구",
                "each name went with its player",
                (seats, names),
            )
            check.ok(
                host.evaluate("state.summary.awaiting_start") is False,
                "the room has started",
            )
            print(f"screenshots in {SHOTS}")
        finally:
            shutil.copy(server_log, SERVER_LOG_COPY)
        log_text = server_log.read_text()
        check.ok(
            "Traceback" not in log_text and "ERROR" not in log_text,
            f"no server errors (see {SERVER_LOG_COPY})",
        )
    check.finish()


if __name__ == "__main__":
    main()
