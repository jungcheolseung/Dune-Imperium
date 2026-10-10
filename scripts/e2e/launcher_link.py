"""E2E for the server launcher (docs/server-launcher-plan.md, stage 6).

The launcher runs as the window would run it, without the window:
``python -m dune_imperium.launcher.cli --start`` on a remote server. The
admin link it hands out has to make a browser the host; the room link the
host's page shows has to start with the launcher's room-link base and let a
player take a seat; the launcher's own game listing (the window's list,
asked as the host) has to see that game; and closing the launcher's
standard input has to stop the server gracefully and free the port, with
the admin key never written to the log.

This folder's environment has only Playwright (Python 3.12) and the project
needs 3.14, so the launcher and its listing run on the project's own
``.venv`` as child processes, the way the other scripts reach engine code.
``--remote`` works on 127.0.0.1, so no E2E_HOST is needed.
"""

from __future__ import annotations

import json
import socket
import subprocess
import tempfile
import threading
from pathlib import Path

from common import HOST, REPO, Check, chrome, free_port, open_context, set_rule_options
from remote import wait_for_setup

check = Check()
PYTHON = REPO / ".venv" / "bin" / "python"


def read_line(process: subprocess.Popen[str], timeout: float) -> str:
    """One line of the launcher's output, without hanging the run."""

    box: list[str] = []
    stream = process.stdout
    assert stream is not None
    reader = threading.Thread(target=lambda: box.append(stream.readline()), daemon=True)
    reader.start()
    reader.join(timeout)
    return box[0] if box else ""


def launcher_lists(port: int, key: str, game_id: str) -> bool:
    """The launcher's own listing (command.list_games), as the window asks."""

    listed = subprocess.run(
        [
            str(PYTHON),
            "-c",
            "import json, sys\n"
            "from dune_imperium.launcher.command import list_games\n"
            "games = list_games(sys.argv[1], int(sys.argv[2]), sys.argv[3])\n"
            "print(json.dumps([g['game_id'] for g in games or []]))",
            HOST,
            str(port),
            key,
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return listed.returncode == 0 and game_id in json.loads(listed.stdout or "[]")


def port_is_free(port: int) -> bool:
    """Free the way the server binds (SO_REUSEADDR on POSIX): the browsers'
    closed connections may leave TIME_WAIT entries behind on the port."""

    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((HOST, port))
        except OSError:
            return False
    return True


def main() -> None:
    work = Path(tempfile.mkdtemp(prefix="launcher-e2e-"))
    port = free_port()
    settings = work / "launcher.json"
    settings.write_text(
        json.dumps(
            {
                "version": 1,
                "mode": "remote",
                "host": HOST,
                "port": port,
                "saves_dir": str(work / "saves"),
                "ai_pace": "instant",
                "open_browser": False,
                "keep_awake": False,
            }
        ),
        encoding="utf-8",
    )
    errors = (work / "launcher-stderr.log").open("w", encoding="utf-8")
    launcher = subprocess.Popen(
        [
            str(PYTHON),
            "-m",
            "dune_imperium.launcher.cli",
            "--start",
            "--settings",
            str(settings),
            # Keep this run's logs out of the host's tmp/launcher.
            "--log-dir",
            str(work / "logs"),
        ],
        cwd=REPO,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=errors,
        text=True,
        encoding="utf-8",
    )
    try:
        print("[1] the launcher starts a remote server and hands out its links")
        line = read_line(launcher, 90)
        if not check.ok(bool(line), "the launcher printed its links", work):
            raise SystemExit(check.finish())
        started = json.loads(line)
        admin_url = started["open_url"]
        base = started["room_base"]
        key = json.loads(settings.read_text(encoding="utf-8"))["admin_key"]
        check.ok(
            admin_url == f"http://{HOST}:{port}/#admin={key}",
            "the admin link names the chosen address, port and the stored key",
            admin_url,
        )
        check.ok(started["access"] == "remote", "the server runs in remote mode")
        check.ok(base == f"http://{HOST}:{port}", "the room-link base", base)

        with chrome() as browser:
            _, host, _ = open_context(browser, "host")
            _, guest, _ = open_context(browser, "guest")
            print("[2] the admin link makes the browser the host")
            host.goto(admin_url)
            wait_for_setup(host)
            check.ok(host.evaluate("state.server.admin") is True, "whoami says admin")
            host.select_option("#seat-selects select[data-seat='1']", "human")
            host.select_option("#seat-selects select[data-seat='2']", "heuristic")
            host.select_option("#seat-selects select[data-seat='3']", "heuristic")
            # The launcher passes no --seating: the server's default holds.
            check.ok(
                host.is_checked("#opt-shuffle-seats"),
                "the seat shuffle opens checked (the server's default)",
            )
            # The player below claims seat 2 by its number.
            host.uncheck("#opt-shuffle-seats")
            set_rule_options(host)
            host.click("#create-game")
            host.wait_for_selector("#lobby-screen:not([hidden])")
            game_id = host.evaluate("state.gameId")
            link = host.input_value("#lobby-host .room-link-value")
            check.ok(
                link == f"{base}/#game={game_id}",
                "the page's room link starts with the launcher's base",
                link,
            )
            print("[3] a player comes in through the room link")
            guest.goto(link)
            guest.wait_for_selector("#lobby-screen:not([hidden])")
            guest.fill("#lobby-name", "친구")
            guest.click("#lobby-seats li[data-seat='1'] button")
            guest.wait_for_selector("#game-screen:not([hidden])")
            check.ok(
                guest.evaluate("state.summary.players[1].claimed") is True,
                "the player holds seat 2",
            )
            check.ok(
                launcher_lists(port, key, game_id),
                "the launcher's game list (as the host) shows the game",
            )

        print("[4] closing the launcher's input stops the server")
        assert launcher.stdin is not None
        launcher.stdin.close()
        stopped_line = read_line(launcher, 30)
        stopped = json.loads(stopped_line) if stopped_line else {}
        check.ok(
            stopped.get("stopped") == "stdin" and stopped.get("port_free") is True,
            "the server stopped on its closed input and freed the port",
            stopped,
        )
        check.ok(launcher.wait(30) == 0, "the launcher ended with code 0")
        check.ok(port_is_free(port), "the port is free again")
        log = Path(started["log"]).read_text(encoding="utf-8")
        check.ok(key not in log, "the admin key is not in the server log")
        check.ok("#admin=…" in log, "the log shows the admin link masked")
        check.ok("Traceback" not in log, "no server errors", started["log"])
        check.ok(
            Path(started["log"]).parent == work / "logs",
            "the log went to the folder the run named",
        )
    finally:
        if launcher.poll() is None:
            launcher.kill()
            launcher.wait(10)
        errors.close()
    check.finish()


if __name__ == "__main__":
    main()
