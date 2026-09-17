"""Remote E2E for M14 slice 4 (docs/multiplayer-design.md section 10).

room -> join -> claim -> a few turns -> reload -> release -> re-claim, with
two cookie-separated contexts against a --remote server.

The game is driven by whoever the *server* says must act, and after every
step every page must converge to the server's summary (and the acting page
must hold actions for that revision). A page that stops converging is the
hang the handoff describes, and its timeline is printed.
"""

from __future__ import annotations

import json
import shutil
import sys
import time

from common import (
    SERVER_LOG_COPY,
    Check,
    chrome,
    client_state,
    now,
    open_context,
    server,
)

KEY = "e2e-admin-key"
STEPS = 40  # first stretch; `python remote.py 120` plays a longer one
check = Check()

CONVERGED_JS = (
    """async (gameId) => {
  const s = await fetch(`/games/${gameId}`).then((r) => r.json());
  const mine = state.me ? state.me.seats : [];
  const local = state.summary;
  if (!local) return {ok: false, why: "no summary", server: s.revision};
  const same =
    s.revision === local.revision &&
    s.undo_count === local.undo_count &&
    s.log_count === local.log_count &&
    s.confirmation === local.confirmation &&
    s.finished === local.finished &&
    JSON.stringify(s.players) === JSON.stringify(local.players);
  const held = typeof s.confirmation === "number";
  const owner = s.decision ? s.decision.owner : null;
  const mustAct = !s.finished && !held && owner !== null && mine.includes(owner);
  const acts = state.actions && state.actions.revision === s.revision &&"""
    """ state.actions.actions.length > 0;
  const viewOk = !mine.length || (state.view !== null && mine.includes(state.viewSeat));
  const settled = !state.busy && refreshFlight === null;
  const ok = same && settled && viewOk && (mustAct ? acts && state.viewSeat === owner"""
    """ : state.actions === null);
  return {ok, same, settled, viewOk, mustAct, acts: Boolean(acts), serverRev:"""
    """ s.revision, localRev: local.revision,
          serverOwner: owner, serverConfirmation: s.confirmation, localConfirmation:"""
    """ local.confirmation};
}"""
)


def wait_until(page, predicate_js: str, timeout: float, label: str, recorders=()):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if page.evaluate(predicate_js):
            return True
        time.sleep(0.05)
    print(f"  TIMEOUT {label}: {json.dumps(client_state(page), ensure_ascii=False)}")
    for recorder in recorders:
        recorder.dump(since=now() - timeout - 1)
    return False


def converge(pages, game_id: str, label: str, timeout: float = 5.0) -> bool:
    """Every page reaches the server's state; print the laggard's timeline."""
    deadline = time.monotonic() + timeout
    verdicts = {}
    while time.monotonic() < deadline:
        verdicts = {
            name: page.evaluate(CONVERGED_JS, game_id)
            for name, (page, _) in pages.items()
        }
        if all(v["ok"] for v in verdicts.values()):
            return True
        time.sleep(0.05)
    for name, verdict in verdicts.items():
        if not verdict["ok"]:
            page, recorder = pages[name]
            print(f"  NOT CONVERGED [{label}] {name}: {json.dumps(verdict)}")
            print(f"    client: {json.dumps(client_state(page), ensure_ascii=False)}")
            recorder.dump(since=now() - timeout - 2, limit=60)
    return False


def drive(pages, seat_pages, game_id: str, steps: int, label: str) -> int:
    """Play `steps` human steps, each by the seat the server names."""
    done = 0
    any_page = next(iter(pages.values()))[0]
    for _ in range(steps):
        summary = any_page.evaluate(f"fetch('/games/{game_id}').then((r) => r.json())")
        if summary["finished"]:
            break
        if isinstance(summary["confirmation"], int):
            seat, act = summary["confirmation"], "confirmTurn()"
        else:
            seat, act = summary["decision"]["owner"], "applyAction(0)"
        if seat not in seat_pages:
            print(f"  .. seat {seat} must act but nobody in this test holds it")
            break
        started = now()
        seat_pages[seat].evaluate(act)
        if not converge(
            pages,
            game_id,
            f"{label} step {done} seat {seat} {act} rev {summary['revision']}",
        ):
            return -1
        done += 1
        if now() - started > 2.0:
            print(f"  .. slow step: {now() - started:.2f}s ({act} by seat {seat})")
    return done


def seat_two_players(base: str, host, guest) -> str:
    """Host (seat 0) and guest (seat 1) at the table of a fresh remote game."""

    host.goto(f"{base}/#admin={KEY}")
    host.wait_for_selector("#setup-screen:not([hidden])")
    host.select_option("#seat-selects select[data-seat='1']", "human")
    host.click("#create-game")
    host.wait_for_selector("#lobby-screen:not([hidden])")
    game_id = host.evaluate("state.gameId")
    host.fill("#lobby-name", "호스트")
    host.click("#lobby-seats li[data-seat='0'] button")
    host.wait_for_selector("#game-screen:not([hidden])")
    guest.goto(f"{base}/#game={game_id}")
    guest.wait_for_selector("#lobby-screen:not([hidden])")
    guest.fill("#lobby-name", "친구")
    guest.click("#lobby-seats li[data-seat='1'] button")
    guest.wait_for_selector("#game-screen:not([hidden])")
    return game_id


def main() -> None:
    global STEPS
    if len(sys.argv) > 1:
        STEPS = int(sys.argv[1])
    with (
        server("--remote", "--admin-key", KEY) as (base, server_log),
        chrome() as browser,
    ):
        _, host, host_rec = open_context(browser, "host")
        _, guest, guest_rec = open_context(browser, "guest")
        pages = {"host": (host, host_rec), "guest": (guest, guest_rec)}
        try:
            scenario(base, host, host_rec, guest, guest_rec, pages)
        finally:
            shutil.copy(server_log, SERVER_LOG_COPY)
        log_text = server_log.read_text()
        bad = "Traceback" in log_text or "ERROR" in log_text
        check.ok(not bad, f"no server errors (see {SERVER_LOG_COPY})")
    check.finish()


def scenario(base, host, host_rec, guest, guest_rec, pages) -> None:
    print("[1] host enters through the admin link and creates a room")
    host.goto(f"{base}/#admin={KEY}")
    host.wait_for_selector("#setup-screen:not([hidden])")
    check.ok("admin" not in host.url, "admin key left the address bar", host.url)
    check.ok(host.evaluate("state.server.access") == "remote", "whoami says remote")
    check.ok(host.evaluate("state.server.admin") is True, "whoami says admin")
    check.ok(
        not host.is_visible("#opt-seed-row"), "seed input hidden on a remote server"
    )
    host.select_option("#seat-selects select[data-seat='1']", "human")
    host.click("#create-game")
    host.wait_for_selector("#lobby-screen:not([hidden])")
    game_id = host.evaluate("state.gameId")
    check.ok(host.url.endswith(f"#game={game_id}"), "room hash set", host.url)
    check.ok(host.is_visible("#lobby-host"), "host block shown in the lobby")
    link = host.input_value("#lobby-host .room-link-value")
    check.ok(link == f"{base}/#game={game_id}", "room link", link)
    check.ok(
        host.evaluate("state.summary.game_seed") is None,
        "seed hidden from the host's summary",
    )

    print(
        "[2] a visitor without a link sees the landing page; with it, the seat picker"
    )
    guest.goto(base + "/")
    guest.wait_for_selector("#landing-screen:not([hidden])")
    check.ok(not guest.is_visible("#setup-screen"), "no setup screen for a visitor")
    guest.goto(link)
    guest.wait_for_selector("#lobby-screen:not([hidden])")
    check.ok(not guest.is_visible("#lobby-host"), "no host block for a guest")

    print("[3] claims")
    host.fill("#lobby-name", "호스트")
    host.click("#lobby-seats li[data-seat='0'] button")
    host.wait_for_selector("#game-screen:not([hidden])")
    check.ok(host.evaluate("state.me.seats") == [0], "host holds seat 0")
    ok = wait_until(
        guest,
        "state.summary.players[0].claimed === true",
        5,
        "guest's lobby hears the host's claim",
        (guest_rec,),
    )
    check.ok(ok, "the guest's seat picker shows seat 0 taken without a reload")
    taken = guest.evaluate(
        "document.querySelector(\"#lobby-seats li[data-seat='0'] button\")"
    )
    check.ok(taken is None, "no claim button on a taken seat")
    guest.click("#lobby-seats li[data-seat='1'] button")
    check.ok(
        wait_until(
            guest, "!document.getElementById('lobby-error').hidden", 3, "name required"
        ),
        "claim without a name is refused in the page",
    )
    guest.fill("#lobby-name", "<u id=xss>친구</u>")
    guest.click("#lobby-seats li[data-seat='1'] button")
    guest.wait_for_selector("#game-screen:not([hidden])")
    check.ok(guest.evaluate("state.me.seats") == [1], "guest holds seat 1")

    print("[4] cross-seat access is refused")
    status = guest.evaluate(
        f"fetch('/games/{game_id}/snapshot?seat=0').then((r) => r.status)"
    )
    check.ok(status == 403, "guest asking for seat 0 gets 403", status)
    status = guest.evaluate(
        f"fetch('/games/{game_id}/actions', "
        "{method: 'POST', headers: {'Content-Type': 'application/json'},"
        " body: JSON.stringify({seat: 0, revision: 0, undo_count: 0, index: 0})})"
        ".then((r) => r.status)"
    )
    check.ok(status == 403, "guest acting for seat 0 gets 403", status)

    print("[5] names and presence on both tables")
    check.ok(
        converge(pages, game_id, "after claims"), "both pages converge after the claims"
    )
    check.ok(
        host.evaluate("state.summary.players[1].online") is True,
        "host sees the guest online",
    )
    check.ok(
        host.evaluate("document.getElementById('xss')") is None,
        "a name never becomes markup (host)",
    )
    check.ok(
        guest.evaluate("document.getElementById('xss')") is None,
        "a name never becomes markup (guest)",
    )
    badge = host.evaluate(
        "[...document.querySelectorAll('#seats .badge')].map((b) => b.textContent)"
    )
    check.ok(
        any("친구" in text for text in badge),
        "guest's name is on the host's seat panel",
        badge,
    )
    dots = host.evaluate("document.querySelectorAll('#seats .presence.on').length")
    check.ok(dots == 2, "two presence dots lit on the host's table", dots)

    print(
        f"[6] {STEPS} steps, "
        "each by the seat the server names; every page converges after each"
    )
    seat_pages = {0: host, 1: guest}
    played = drive(pages, seat_pages, game_id, STEPS, "first stretch")
    check.ok(played == STEPS, f"played {STEPS} converging steps", played)
    if played < 0:
        return

    print("[7] banners and the turn notice")
    summary = host.evaluate("state.summary")
    held = isinstance(summary["confirmation"], int)
    actor = summary["confirmation"] if held else summary["decision"]["owner"]
    if actor in seat_pages:
        waiting = seat_pages[1 - actor]
        banner = waiting.inner_text("#decision-info")
        expected = "턴 종료 확정을 기다리는 중" if held else "결정 대기 중"
        check.ok(
            expected in banner,
            "the waiting seat's banner says who it waits for",
            banner,
        )
        check.ok(
            waiting.evaluate("state.actions") is None,
            "the waiting seat is offered no actions",
        )
        check.ok(
            seat_pages[actor].title().startswith("▶ 내 차례"),
            "the acting seat's tab title says so",
            seat_pages[actor].title(),
        )
        check.ok(
            not waiting.title().startswith("▶"),
            "the waiting seat's tab title does not",
            waiting.title(),
        )

    print("[8] reload comes back to the table with the same seat")
    guest.reload()
    guest.wait_for_selector("#game-screen:not([hidden])")
    check.ok(
        guest.evaluate("state.me.seats") == [1],
        "guest still holds seat 1 after a reload",
    )
    check.ok(
        converge(pages, game_id, "after reload"), "both pages converge after the reload"
    )
    check.ok(
        host.evaluate("state.summary.players[1].online") is True,
        "host sees the guest online again",
    )
    played = drive(pages, seat_pages, game_id, 10, "after reload")
    check.ok(played == 10, "10 more converging steps after the reload", played)

    print("[9] the host releases the guest's seat; the guest lands in the seat picker")
    host.click("#host-panel > summary")
    host.click("#host-panel-body .host-seats li:nth-child(2) button")
    ok = wait_until(
        guest,
        "!document.getElementById('lobby-screen').hidden",
        5,
        "guest sent to the lobby",
        (guest_rec, host_rec),
    )
    check.ok(ok, "guest is sent to the seat picker once its seat is released")
    check.ok(guest.evaluate("state.me.seats") == [], "guest holds nothing now")
    check.ok(
        converge(pages, game_id, "after release"),
        "both pages converge after the release",
    )
    check.ok(
        host.evaluate("state.summary.players[1].claimed") is False,
        "host sees seat 1 free",
    )

    print("[10] re-claim under a new name")
    guest.fill("#lobby-name", "돌아온 친구")
    guest.click("#lobby-seats li[data-seat='1'] button")
    guest.wait_for_selector("#game-screen:not([hidden])")
    check.ok(guest.evaluate("state.me.seats") == [1], "guest holds seat 1 again")
    check.ok(
        converge(pages, game_id, "after re-claim"),
        "both pages converge after the re-claim",
    )
    check.ok(
        host.evaluate("state.summary.players[1].name") == "돌아온 친구",
        "host sees the new name",
    )
    played = drive(pages, seat_pages, game_id, 10, "after re-claim")
    check.ok(played == 10, "10 more converging steps after the re-claim", played)

    print("[11] undo by the acting seat reaches the other page")
    summary = host.evaluate("state.summary")
    seat = (
        summary["confirmation"]
        if isinstance(summary["confirmation"], int)
        else summary["decision"]["owner"]
    )
    undo_before = summary["undo_count"]
    can_undo = seat in seat_pages and seat_pages[seat].evaluate(
        f"(state.summary.undo || []).some((u) => u.seat === {seat} && u.steps > 0)"
    )
    if can_undo:
        seat_pages[seat].evaluate(f"submitUndo({seat}, 1)")
        check.ok(
            converge(pages, game_id, "after undo"), "both pages converge after an undo"
        )
        check.ok(
            host.evaluate("state.summary.undo_count") == undo_before + 1, "undo counted"
        )
    else:
        print("  .. no undoable step at this point; skipped")

    print("[12] the guest leaves its seat by itself")
    guest.click("#open-lobby")
    guest.wait_for_selector("#lobby-screen:not([hidden])")
    guest.click("#lobby-seats li[data-seat='1'] button:has-text('자리 비우기')")
    ok = wait_until(
        guest, "state.me.seats.length === 0", 5, "guest released", (guest_rec,)
    )
    check.ok(ok, "guest released its own seat")
    check.ok(
        converge(pages, game_id, "after self-release"),
        "both pages converge after the self-release",
    )

    print(
        "[12b] a claim overtaken by leaving does not drag the table back; "
        "the landing page offers the way back"
    )
    guest.fill("#lobby-name", "마지막 친구")
    guest.evaluate("() => { claimSeat(1); leaveGame(); }")
    guest.wait_for_timeout(800)
    check.ok(
        guest.is_visible("#landing-screen") and not guest.is_visible("#game-screen"),
        "the guest stays on the landing page it left to",
    )
    check.ok("#game=" not in guest.url, "no room hash after leaving", guest.url)
    check.ok(
        guest.is_visible("#landing-resume-button"),
        "the landing page offers the last room",
    )
    guest.click("#landing-resume-button")
    guest.wait_for_selector("#game-screen:not([hidden])")
    check.ok(
        guest.evaluate("state.me.seats") == [1],
        "the way back lands at the seat the cookie holds",
    )
    check.ok(
        converge(pages, game_id, "after resume"), "both pages converge after the resume"
    )
    played = drive(pages, {0: host, 1: guest}, game_id, 6, "after resume")
    check.ok(played == 6, "6 more converging steps after the resume", played)

    print("[13] the host deletes nothing, leaves, and comes back through the game list")
    host.click("#leave-game")
    host.wait_for_selector("#setup-screen:not([hidden])")
    check.ok("#game=" not in host.url, "room hash cleared on leaving", host.url)
    host.click("#game-list button")
    host.wait_for_selector("#game-screen:not([hidden])")
    check.ok(host.evaluate("state.me.seats") == [0], "host is back at seat 0")

    print("[14] errors")
    bad_host = [r for r in host_rec.requests if r[3] >= 400]
    bad_guest = [r for r in guest_rec.requests if r[3] >= 400]
    check.ok(not bad_host, "no failed requests on the host", bad_host)
    check.ok(
        len(bad_guest) == 2 and all(r[3] == 403 for r in bad_guest),
        "only the two 403 probes failed on the guest",
        bad_guest,
    )
    page_errors = [
        e
        for e in host_rec.js_errors + guest_rec.js_errors
        if "Failed to load resource" not in e
    ]
    check.ok(not page_errors, "no JS exceptions", page_errors)
    host_posts = sum(1 for r in host_rec.requests if r[1] == "POST")
    guest_posts = sum(1 for r in guest_rec.requests if r[1] == "POST")
    print(
        f"  .. requests: host snapshot {host_rec.count('GET', '/snapshot')}, "
        f"POST {host_posts};"
        f" guest snapshot {guest_rec.count('GET', '/snapshot')}, POST {guest_posts}"
    )


if __name__ == "__main__":
    main()
