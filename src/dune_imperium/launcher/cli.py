"""The launcher's entry point (docs/server-launcher-plan.md 5.1).

``python -m dune_imperium.launcher`` (or the ``dune-imperium-launcher``
program) opens the window. The options are for a console:

* ``--check`` prints the diagnostics: versions, the address candidates and
  everything the start would say, with exit code 1 if it would fail.
* ``--start`` starts the server without a window, prints one JSON line
  with the links once it answers, and stops it when this program's own
  standard input ends: the browser checks (scripts/e2e) and the Windows
  verification drive it that way.

On Windows the ``dune-imperium-launcher.exe`` program runs on ``pythonw``,
which has no standard output: the console options are run through
``python -m dune_imperium.launcher.cli`` there. Nothing here uses
``print``, so a missing stream never raises.
"""

import argparse
import json
import sys
import threading
from collections.abc import Sequence
from dataclasses import replace
from importlib import metadata
from pathlib import Path
from typing import TextIO

from dune_imperium.launcher.addresses import discover
from dune_imperium.launcher.command import (
    Problem,
    build_plan,
    has_errors,
    preflight,
    run_output,
)
from dune_imperium.launcher.settings import (
    SETTINGS_FILE,
    load,
    save,
    snapshot,
    with_admin_key,
)
from dune_imperium.launcher.supervisor import (
    LOG_DIR,
    ServerProcess,
    StartupFailed,
    Stopped,
)
from dune_imperium.paths import PROJECT_ROOT

_LEVELS = {"error": "오류", "warning": "주의", "note": "참고"}


def _write(text: str, stream: TextIO | None = None) -> None:
    target = sys.stdout if stream is None else stream
    if target is None:
        return
    try:
        target.write(text + "\n")
        target.flush()
    except (OSError, ValueError):
        pass


def _error(text: str) -> None:
    _write(text, sys.stderr)


def _version(package: str) -> str:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return "없음"


def _tk_version() -> str:
    try:
        import tkinter
    except ImportError as error:
        return f"없음 ({error})"
    return str(tkinter.TkVersion)


def diagnostics() -> list[str]:
    """What a problem report needs: where, which versions, which formats."""

    lines = [
        f"프로젝트 폴더: {PROJECT_ROOT}",
        f"Python: {sys.version.split()[0]} ({sys.executable})",
        f"Tk: {_tk_version()}",
        "패키지: "
        + ", ".join(
            f"{name} {_version(name)}" for name in ("fastapi", "uvicorn", "torch")
        ),
    ]
    commit = run_output(
        ["git", "-C", str(PROJECT_ROOT), "rev-parse", "--short", "HEAD"], 5.0
    )
    lines.append(f"커밋: {commit.strip() if commit else '알 수 없음'}")
    try:
        from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
        from dune_imperium.server.persistence import SAVE_FORMAT_VERSION
    except ImportError as error:
        lines.append(f"저장 형식: 알 수 없음 ({error})")
    else:
        lines.append(
            f"저장 형식: v{SAVE_FORMAT_VERSION}, 행동 코덱 v{ACTION_CODEC_VERSION}"
        )
    return lines


def _problem_line(problem: Problem) -> str:
    return f"[{_LEVELS[problem.level]}] {problem.text}"


def check(settings_path: Path) -> int:
    loaded = load(settings_path)
    for line in diagnostics():
        _write(line)
    _write(f"설정 파일: {settings_path}")
    for note in loaded.notes:
        _write(f"[참고] {note}")
    found = discover(run_output)
    if found.tailscale is None:
        _write("Tailscale: CLI를 찾지 못했습니다")
    else:
        state = found.tailscale.state or "알 수 없음"
        _write(f"Tailscale: {state}")
    if not found.internet_route:
        _write("인터넷 경로가 없습니다(LAN에서는 그대로 플레이할 수 있습니다)")
    _write("주소 후보:")
    for candidate in found.candidates:
        _write(f"  {candidate.label}")
    settings, admin_key = with_admin_key(loaded.settings)
    plan = build_plan(settings, admin_key)
    problems = preflight(settings, plan)
    if not problems:
        _write("시작 전 검사: 문제 없음")
    for problem in problems:
        _write(_problem_line(problem))
    return 1 if has_errors(problems) else 0


def start(settings_path: Path, log_dir: Path = LOG_DIR) -> int:
    """Run the server without a window until standard input ends.

    Its own messages go to standard error; the server's lines go only to
    the log file named in the JSON line, so a caller that never reads
    standard error cannot stall the launcher on a full pipe.
    """

    loaded = load(settings_path)
    for note in loaded.notes:
        _error(f"[참고] {note}")
    settings, admin_key = with_admin_key(loaded.settings)
    plan = build_plan(settings, admin_key)
    problems = preflight(settings, plan, check_torch=False)
    for problem in problems:
        _error(_problem_line(problem))
    if has_errors(problems):
        return 1
    save(settings, settings_path)
    server = ServerProcess(plan, log_dir=log_dir)
    code = 0
    announced = False
    try:
        try:
            server.start()
            info = server.wait_ready()
        except StartupFailed as failure:
            _error(f"[오류] {failure.message}")
            for line in failure.tail:
                _error(f"  {line}")
            save(replace(settings, last_error=failure.message), settings_path)
            return 1
        save(
            replace(settings, last_good=snapshot(settings), last_error=None),
            settings_path,
        )
        _write(
            json.dumps(
                {
                    "open_url": plan.open_url,
                    "room_base": plan.room_base,
                    "pid": server.pid,
                    "port": plan.port,
                    "access": info.get("access"),
                    "search_ai": info.get("search_ai"),
                    "log": None if server.log_path is None else str(server.log_path),
                },
                ensure_ascii=False,
            )
        )
        announced = True
        if not _wait_for_end_of_input(server):
            code = 1
    except KeyboardInterrupt:
        pass
    finally:
        # Every way out stops the server the same way, Ctrl+C included.
        stopped = _stop_quietly(server)
    if code:
        from dune_imperium.launcher.command import explain_failure

        _error(f"[오류] {explain_failure(server.tail(), stopped.exit_code)}")
    if announced:
        _write(
            json.dumps(
                {
                    "stopped": stopped.how,
                    "seconds": round(stopped.seconds, 2),
                    "port_free": stopped.port_free,
                }
            )
        )
    return code


def _wait_for_end_of_input(server: ServerProcess) -> bool:
    """Wait until this program's standard input ends (``True``) or the
    server dies (``False``)."""

    ended = threading.Event()
    try:
        descriptor = sys.stdin.fileno() if sys.stdin is not None else None
    except (OSError, ValueError):
        descriptor = None
    if descriptor is not None:
        from dune_imperium.cli.server import stop_when_stream_ends

        # By descriptor, as the server does: a buffered read would make the
        # interpreter abort at shutdown after Ctrl+C.
        threading.Thread(
            target=stop_when_stream_ends,
            args=(descriptor, ended.set),
            name="launcher-stdin-watch",
            daemon=True,
        ).start()
    while not ended.wait(0.2):
        if not server.is_alive():
            return False
    return True


def _stop_quietly(server: ServerProcess) -> Stopped:
    """Stop the server; a second Ctrl+C during the stop is not obeyed."""

    while True:
        try:
            return server.stop()
        except KeyboardInterrupt:
            continue


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dune-imperium-launcher",
        description=(
            "Start and stop the Dune: Imperium play server from a window "
            "(docs/server-launcher-plan.md)."
        ),
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--check",
        action="store_true",
        help="print versions, address candidates and the pre-start checks",
    )
    action.add_argument(
        "--make-shortcut",
        action="store_true",
        help=(
            "make the double-click shortcut in the project folder "
            "(macOS: Dune Imperium Server.app, Windows: Dune Imperium Server.lnk)"
        ),
    )
    action.add_argument(
        "--start",
        action="store_true",
        help=(
            "start the server without a window, print one JSON line with its "
            "links, and stop it when standard input ends"
        ),
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=SETTINGS_FILE,
        help=f"settings file (default: {SETTINGS_FILE})",
    )
    # For the tests and the browser checks: keep their logs out of the
    # host's tmp/launcher.
    parser.add_argument("--log-dir", type=Path, default=LOG_DIR, help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    if arguments.check:
        return check(arguments.settings)
    if arguments.start:
        return start(arguments.settings, arguments.log_dir)
    if arguments.make_shortcut:
        from dune_imperium.launcher.shortcuts import ShortcutError, make_shortcut

        try:
            made = make_shortcut()
        except ShortcutError as error:
            _error(f"[오류] {error}")
            return 1
        _write(f"바로가기를 만들었습니다: {made}")
        return 0
    try:
        from dune_imperium.launcher.gui import main as open_window
    except ImportError as error:  # a Python built without tkinter
        _error(f"dune-imperium-launcher: no window toolkit (tkinter): {error}")
        return 1
    return open_window(arguments.settings)


if __name__ == "__main__":
    raise SystemExit(main())
