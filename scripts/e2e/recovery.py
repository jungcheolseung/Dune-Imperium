"""Crash recovery E2E (M14 slice 5, docs/multiplayer-design.md section 4.7).

A remote game is played for a while, the server is killed without warning
(SIGKILL) and started again on the same port and saves directory. The host
brings the game back from its autosave through the browser; the guest, whose
page was left waiting, is told what happened and comes back by the new room
link. What may be lost is the turn in progress, nothing more.
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

from common import Check, ServerProcess, chrome, client_state, open_context
from remote import KEY, converge, drive, seat_two_players, wait_until

check = Check()


def fetch_json(page, path: str):
    return page.evaluate(f"fetch('{path}').then((r) => r.json())")


def main() -> None:
    saves = tempfile.mkdtemp(prefix="dune-e2e-recovery-")
    first = ServerProcess("--remote", "--admin-key", KEY, saves=saves).start()
    second: ServerProcess | None = None
    try:
        with chrome() as browser:
            _, host, host_rec = open_context(browser, "host")
            _, guest, guest_rec = open_context(browser, "guest")
            pages = {"host": (host, host_rec), "guest": (guest, guest_rec)}
            seat_pages = {0: host, 1: guest}

            print("[1] a remote game is played; its autosave follows the hand-overs")
            game_id = seat_two_players(first.base, host, guest)
            check.ok(
                host.evaluate("state.server.autosave") is True, "whoami: autosave on"
            )
            check.ok(converge(pages, game_id, "setup"), "both pages converge")
            played = drive(pages, seat_pages, game_id, 24, "before the crash")
            check.ok(played == 24, "24 converging steps", played)
            files = sorted(p.name for p in Path(saves).glob("*.json"))
            check.ok(files == [f"{game_id}.json"], "exactly one autosave file", files)
            document = json.loads((Path(saves) / f"{game_id}.json").read_text())
            summary = fetch_json(host, f"/games/{game_id}")
            print(
                f"  .. live revision {summary['revision']}"
                f" round {summary['round_number']};"
                f" autosave holds {len(document['steps'])} steps ({document['name']})"
            )
            check.ok(document["autosave"] is True, "the file is marked as an autosave")
            check.ok(
                len(document["steps"]) <= summary["revision"],
                "the autosave is never ahead of the game",
            )
            check.ok(
                summary["revision"] - len(document["steps"]) < 12,
                "the autosave is at most a turn behind",
                (summary["revision"], len(document["steps"])),
            )

            print("[2] the host panel shows what is on disk for this game")
            host.click("#host-panel > summary")
            ok = wait_until(
                host,
                "document.querySelectorAll("
                "'#host-panel-body .host-save-list .badge.autosave').length === 1",
                5,
                "host panel lists the autosave",
                (host_rec,),
            )
            check.ok(ok, "the host panel lists the autosave with its badge")
            heading = host.inner_text("#host-panel-body .host-saves h3")
            check.ok(
                "자동 저장" in heading and "꺼져" not in heading,
                "it says autosave is on",
                heading,
            )
            check.ok(
                guest.evaluate("document.getElementById('host-panel').hidden") is True,
                "the guest has no host panel",
            )
            status = guest.evaluate("fetch('/saves').then((r) => r.status)")
            check.ok(status == 403, "the guest cannot list saves", status)

            print("[3] the server dies (SIGKILL)")
            first.kill()
            leftovers = [p.name for p in Path(saves).glob("*.tmp")]
            check.ok(not leftovers, "no half-written file is left behind", leftovers)
            json.loads((Path(saves) / f"{game_id}.json").read_text())
            check.ok(True, "the autosave on disk is whole JSON")
            ok = wait_until(
                guest,
                "!document.getElementById('connection-note').hidden",
                20,
                "guest notices the lost connection",
                (guest_rec,),
            )
            check.ok(ok, "the waiting guest is told the connection is lost")

            print("[4] the server comes back on the same port without the game")
            second = ServerProcess(
                "--remote", "--admin-key", KEY, port=first.port, saves=saves
            ).start()
            ok = wait_until(
                guest,
                "!document.getElementById('landing-screen').hidden",
                15,
                "guest is sent to the landing page",
                (guest_rec,),
            )
            check.ok(ok, "the guest's page learns the game is gone")
            message = guest.inner_text("#landing-error")
            check.ok(
                "새 방 링크" in message,
                "and is told to wait for a new room link",
                message,
            )
            check.ok(
                not guest.is_visible("#landing-resume"),
                "the dead room is not offered as the way back",
            )

            print("[5] the host loads the autosave through the admin link")
            host.goto(f"{second.base}/#admin={KEY}")
            host.wait_for_selector("#setup-screen:not([hidden])")
            host.wait_for_selector("#save-list li")
            rows = host.evaluate(
                "[...document.querySelectorAll('#save-list li')]"
                ".map((li) => li.textContent)"
            )
            check.ok(
                len(rows) == 1
                and rows[0].startswith("자동")
                and "자동 저장" in rows[0],
                "the setup screen lists the autosave, badge first",
                rows,
            )
            check.ok(
                "seed" not in rows[0] and "시드" not in rows[0],
                "without the seed of a game in progress",
                rows,
            )
            host.click("#save-list li button:has-text('불러오기')")
            host.wait_for_selector("#lobby-screen:not([hidden])")
            new_id = host.evaluate("state.gameId")
            check.ok(new_id != game_id, "the loaded game has a new ID", new_id)
            restored = fetch_json(host, f"/games/{new_id}")
            check.ok(
                restored["revision"] == len(document["steps"]),
                "it stands exactly where the autosave was taken",
                (restored["revision"], len(document["steps"])),
            )
            check.ok(
                restored["round_number"] == document["round_number"],
                "in the same round",
            )
            check.ok(
                all(
                    not p["claimed"]
                    for p in restored["players"]
                    if p["kind"] == "human"
                ),
                "with every human seat free again",
            )
            link = host.input_value("#lobby-host .room-link-value")
            check.ok(link.endswith(f"#game={new_id}"), "and a new room link", link)

            print("[6] both come back by the new link and play on")
            host.fill("#lobby-name", "호스트")
            host.click("#lobby-seats li[data-seat='0'] button")
            host.wait_for_selector("#game-screen:not([hidden])")
            guest.goto(f"{second.base}/#game={new_id}")
            guest.wait_for_selector("#lobby-screen:not([hidden])")
            check.ok(
                guest.input_value("#lobby-name") == "친구",
                "the guest's name is remembered by its browser",
            )
            guest.click("#lobby-seats li[data-seat='1'] button")
            guest.wait_for_selector("#game-screen:not([hidden])")
            check.ok(converge(pages, new_id, "after recovery"), "both pages converge")
            log_length = host.evaluate("state.log.entries.length")
            check.ok(
                log_length == restored["log_count"],
                "the restored log is on screen",
                (log_length, restored["log_count"]),
            )
            played = drive(pages, seat_pages, new_id, 16, "after the recovery")
            check.ok(played == 16, "16 more converging steps", played)
            files = sorted(p.name for p in Path(saves).glob("*.json"))
            check.ok(
                files == sorted([f"{game_id}.json", f"{new_id}.json"]),
                "the loaded game autosaves into a slot of its own",
                files,
            )

            print("[7] errors")
            page_errors = [
                e
                for e in host_rec.js_errors + guest_rec.js_errors
                if "Failed to load resource" not in e and "ERR_" not in e
            ]
            check.ok(not page_errors, "no JS exceptions", page_errors)
            for label, process in (("first", first), ("second", second)):
                text = process.log_path.read_text()
                bad = "Traceback" in text or "ERROR" in text
                check.ok(
                    not bad,
                    f"no errors in the {label} server's log ({process.log_path})",
                )
            if check.failed:
                print(json.dumps(client_state(guest), ensure_ascii=False))
    finally:
        first.stop()
        if second is not None:
            second.stop()
    check.finish()


if __name__ == "__main__":
    started = time.monotonic()
    try:
        main()
    finally:
        print(f"({time.monotonic() - started:.1f}s)", file=sys.stderr)
