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
from dune_imperium.launcher.supervisor import ServerProcess, StartupFailed
from dune_imperium.paths import PROJECT_ROOT

_LEVELS = {"error": "오류", "warning": "주의", "note": "참고"}


def _write(text: str, stream: TextIO | None = None) -> None:
    target = sys.stdout if stream is None else stream
    if target is None:
        return
    try:
        target.write(text + "\n")
        target.flush()
    except OSError, ValueError:
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


def start(settings_path: Path) -> int:
    """Run the server without a window until standard input ends."""

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
    server = ServerProcess(plan)
    try:
        server.start()
        info = server.wait_ready()
    except StartupFailed as failure:
        server.stop(grace=2.0, term_grace=2.0)
        _error(f"[오류] {failure.message}")
        for line in failure.tail:
            _error(f"  {line}")
        save(replace(settings, last_error=failure.message), settings_path)
        return 1
    save(
        replace(settings, last_good=snapshot(settings), last_error=None), settings_path
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
    code = 0
    try:
        while not ended.wait(0.2):
            _drain(server)
            if not server.is_alive():
                code = 1
                break
    except KeyboardInterrupt:
        pass
    stopped = server.stop()
    _drain(server)
    if code:
        from dune_imperium.launcher.command import explain_failure

        _error(f"[오류] {explain_failure(server.tail(), stopped.exit_code)}")
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


def _drain(server: ServerProcess) -> None:
    while not server.lines.empty():
        _error(server.lines.get_nowait())


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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    if arguments.check:
        return check(arguments.settings)
    if arguments.start:
        return start(arguments.settings)
    # The window comes with stage 3 of the plan.
    _build_parser().print_help(sys.stdout)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
