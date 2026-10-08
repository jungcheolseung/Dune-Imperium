"""The server command a start runs, and what would keep it from coming up.

docs/server-launcher-plan.md 5.2 and 5.7. The server is the launcher's own
interpreter running ``-m dune_imperium.cli.server``: no ``uv run`` and no
console-script wrapper in between, so the process the launcher holds is the
one whose standard input ends the server. Every ``DUNE_IMPERIUM_*`` variable
of the launcher's environment is dropped and only what the settings say is
passed on, so a ``None`` in the settings really means the server's default.

The messages are Korean, for the host; the command and file names in them
stay as typed.
"""

import os
import re
import socket
import subprocess
import sys
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
from typing import Final, Literal

from dune_imperium.launcher.settings import LauncherSettings, resolved_path
from dune_imperium.paths import PROJECT_ROOT, SEARCH_CHECKPOINT

SERVER_MODULE: Final = "dune_imperium.cli.server"
ENVIRONMENT_PREFIX: Final = "DUNE_IMPERIUM_"
# cli.server.ADMIN_KEY_ENVIRONMENT (a test keeps the two equal).
ADMIN_KEY_ENVIRONMENT: Final = "DUNE_IMPERIUM_ADMIN_KEY"
# The server's picture overrides (server/app.py) and where each sits in an
# assets folder laid out like the private assets checkout.
ASSET_ENVIRONMENT: Final = (
    ("DUNE_IMPERIUM_CARD_IMAGE_DIR", "cards"),
    ("DUNE_IMPERIUM_ICON_DIR", "icons"),
    ("DUNE_IMPERIUM_TOKEN_DIR", "tokens"),
    ("DUNE_IMPERIUM_BOARD_IMAGE", "board/map.jpg"),
    ("DUNE_IMPERIUM_BENE_TLEILAX_IMAGE", "board/bene_tleilax.jpg"),
)
DEFAULT_ASSETS_DIR: Final = PROJECT_ROOT / "assets"
# The sync commands the messages name: --inexact, so that a sync for the
# server never removes the rl/train packages a development checkout has.
SYNC_UI: Final = "uv sync --locked --inexact --extra ui"
SYNC_TRAIN: Final = "uv sync --locked --inexact --extra ui --extra train"
_WILDCARDS: Final = {"0.0.0.0": "127.0.0.1", "::": "::1"}
# CREATE_NO_WINDOW: a console program started without a console window. The
# literal value, so that the flag can be computed (and tested) off Windows.
CREATE_NO_WINDOW: Final = 0x08000000

Level = Literal["error", "warning", "note"]


@dataclass(frozen=True)
class Problem:
    level: Level
    text: str


@dataclass(frozen=True)
class LaunchPlan:
    """One start: the command, and the addresses that come out of it."""

    python: str
    server_args: tuple[str, ...]
    env: Mapping[str, str]
    host: str
    port: int
    remote: bool
    admin_key: str | None
    # What the host opens: the admin link, or the table of a local server.
    open_url: str
    # What the room links start with (``<base>/#game=<id>``).
    room_base: str

    @property
    def argv(self) -> tuple[str, ...]:
        return (self.python, "-u", "-m", SERVER_MODULE, *self.server_args)

    @property
    def connect_host(self) -> str:
        """Where the launcher itself reaches the server."""

        return _WILDCARDS.get(self.host, self.host)


def no_window_flags(platform: str | None = None) -> int:
    """``creationflags`` for every child the launcher starts.

    A windowless launcher (``pythonw``) has no console, so each console
    child (the server, the Tailscale CLI, PowerShell, the torch check) would
    get a console window of its own, flashing up; CPython hides it only for
    ``shell=True``.
    """

    return CREATE_NO_WINDOW if (platform or sys.platform) == "win32" else 0


def server_python(
    executable: str = sys.executable, platform: str = sys.platform
) -> str:
    """The interpreter the server runs on: the launcher's own.

    A windowless launcher on Windows runs on ``pythonw.exe``; the server is
    a console program and gets the ``python.exe`` beside it, started with
    its console window suppressed.
    """

    path = Path(executable)
    if platform == "win32" and path.name.lower() == "pythonw.exe":
        console = path.with_name("python.exe")
        if console.exists():
            return str(console)
    return executable


def bind_host(settings: LauncherSettings) -> str:
    return settings.host.strip() if settings.mode == "remote" else "127.0.0.1"


def url_host(host: str) -> str:
    return f"[{host}]" if ":" in host else host


def default_public_url(host: str, port: int) -> str | None:
    """The room-link base for a bind address; none for a wildcard bind."""

    if not host or host in _WILDCARDS:
        return None
    return f"http://{url_host(host)}:{port}"


def is_loopback(host: str) -> bool:
    from dune_imperium.cli.server import is_loopback_host

    return is_loopback_host(host)


def server_environment(
    settings: LauncherSettings,
    admin_key: str | None,
    environ: Mapping[str, str],
) -> dict[str, str]:
    env = {
        key: value
        for key, value in environ.items()
        if not key.upper().startswith(ENVIRONMENT_PREFIX)
    }
    env.update(
        {"PYTHONUNBUFFERED": "1", "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    )
    if settings.mode == "remote" and admin_key is not None:
        env[ADMIN_KEY_ENVIRONMENT] = admin_key
    if settings.assets_dir:
        root = resolved_path(settings.assets_dir)
        for name, relative in ASSET_ENVIRONMENT:
            env[name] = str(root / relative)
    return env


def build_plan(
    settings: LauncherSettings,
    admin_key: str | None,
    *,
    python: str | None = None,
    environ: Mapping[str, str] = os.environ,
) -> LaunchPlan:
    """The command for ``settings``; ``admin_key`` is used in remote mode."""

    from dune_imperium.cli.server import admin_link

    remote = settings.mode == "remote"
    host = bind_host(settings)
    port = settings.port
    args: list[str] = [
        "--exit-when-stdin-closes",
        "--host",
        host,
        "--port",
        str(port),
        "--ai-pace",
        settings.ai_pace,
    ]
    if settings.saves_dir:
        args += ["--saves-dir", str(resolved_path(settings.saves_dir))]
    if settings.search_checkpoint:
        # The real file: saves record the network a symlink named at start.
        args += [
            "--search-checkpoint",
            str(resolved_path(settings.search_checkpoint).resolve()),
        ]
    public_url = settings.public_url or default_public_url(host, port)
    if remote:
        args.append("--remote")
        if public_url:
            args += ["--public-url", public_url.rstrip("/")]
        if not settings.autosave:
            args.append("--no-autosave")
    reach = _WILDCARDS.get(host, host)
    if remote:
        if admin_key is None:
            raise ValueError("a remote start needs an admin key")
        open_url = admin_link(host, port, admin_key)
    else:
        open_url = f"http://{url_host(reach)}:{port}/"
    room_base = (public_url or f"http://{url_host(reach)}:{port}").rstrip("/")
    return LaunchPlan(
        python=python or server_python(),
        server_args=tuple(args),
        env=server_environment(settings, admin_key if remote else None, environ),
        host=host,
        port=port,
        remote=remote,
        admin_key=admin_key if remote else None,
        open_url=open_url,
        room_base=room_base,
    )


def find_free_port(host: str, start: int = 8000, count: int = 100) -> int:
    """The first port from ``start`` the server could listen on, else any."""

    from dune_imperium.cli.server import bind_problem

    for port in range(start, min(start + count, 65536)):
        if bind_problem(host, port) is None:
            return port
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        probe.bind((_WILDCARDS.get(host, host), 0))
        port_found: int = probe.getsockname()[1]
        return port_found


def whoami(
    host: str, port: int, admin_key: str | None = None, timeout: float = 1.0
) -> dict[str, object] | None:
    """``GET /whoami`` of a play server at ``host:port``, or ``None``.

    With the admin key the server answers as to its host (``admin: true``);
    the key travels as the admin cookie, so no login request is needed.
    """

    import json

    request = urllib.request.Request(
        f"http://{url_host(_WILDCARDS.get(host, host))}:{port}/whoami"
    )
    if admin_key is not None:
        request.add_header("Cookie", f"dune_admin={admin_key}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and "access" in data else None


def run_quiet(
    argv: Sequence[str],
    timeout: float,
    *,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str] | None:
    """Run a helper program without a console window; ``None`` if it could
    not run or timed out. ``env`` adds variables to the launcher's own."""

    try:
        return subprocess.run(
            list(argv),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            env=None if env is None else {**os.environ, **env},
            creationflags=no_window_flags(),
        )
    except (OSError, subprocess.SubprocessError):
        return None


def run_output(
    argv: Sequence[str],
    timeout: float,
    /,
    *,
    env: Mapping[str, str] | None = None,
) -> str | None:
    """The ``addresses.Runner`` the launcher uses: standard output of a
    command that succeeded."""

    result = run_quiet(argv, timeout, env=env)
    if result is None or result.returncode != 0:
        return None
    return result.stdout


def _search_checkpoint_problems(
    plan: LaunchPlan,
    settings: LauncherSettings,
    *,
    check_torch: bool,
    run: Callable[[Sequence[str], float], subprocess.CompletedProcess[str] | None],
) -> list[Problem]:
    from dune_imperium.cli.server import _build_parser, resolve_search_checkpoint

    named = (
        resolved_path(settings.search_checkpoint)
        if settings.search_checkpoint
        else SEARCH_CHECKPOINT
    )
    if named.is_symlink() and not named.exists():
        target = os.readlink(named).removeprefix("\\\\?\\")
        return [
            Problem(
                "note",
                "탐색 AI 꺼짐: 링크가 가리키는 파일이 없습니다 "
                f"({named.name} → {target})",
            )
        ]
    arguments = _build_parser().parse_args(list(plan.server_args))
    checkpoint, line = resolve_search_checkpoint(arguments, plan.env)
    if checkpoint is None:
        if "torch not installed" in line:
            return [
                Problem(
                    "note",
                    f"탐색 AI 꺼짐: torch가 없습니다 (탐색 AI를 쓰려면 `{SYNC_TRAIN}`)",
                )
            ]
        if "no file at" in line:
            return [Problem("note", f"탐색 AI 꺼짐: 고른 파일이 없습니다 ({named})")]
        return [
            Problem(
                "note",
                "탐색 AI 꺼짐: 체크포인트 파일이 없습니다 (checkpoints/play/search.pt)",
            )
        ]
    if not check_torch:
        return []
    result = run([plan.python, "-c", "import torch"], 180.0)
    if result is None or result.returncode != 0:
        detail = ""
        if result is not None:
            lines = [line for line in result.stderr.splitlines() if line.strip()]
            detail = lines[-1] if lines else ""
        windows = (
            " Windows라면 최신 Visual C++ 재배포 패키지(x64)를 설치하세요."
            if sys.platform == "win32"
            else ""
        )
        return [
            Problem(
                "warning",
                "torch를 불러오지 못해, 탐색 AI 좌석을 고르면 서버가 오류를 냅니다"
                + (f": {detail}" if detail else "")
                + f".{windows}",
            )
        ]
    return []


def _port_problems(plan: LaunchPlan) -> list[Problem]:
    from dune_imperium.cli.server import bind_problem

    problem = bind_problem(plan.host, plan.port)
    if problem is None:
        return []
    if (
        not is_loopback(plan.host)
        and plan.host not in _WILDCARDS
        and (bind_problem(plan.host, 0) is not None)
    ):
        return [
            Problem(
                "error",
                f"이 PC에 {plan.host} 주소가 없습니다. Tailscale 주소라면 Tailscale이 "
                "연결돼 있는지, LAN 주소라면 주소가 바뀌지 않았는지 보고 "
                "주소를 다시 고르세요.",
            )
        ]
    if whoami(plan.host, plan.port) is not None:
        return [
            Problem(
                "error",
                f"포트 {plan.port}에 이미 Dune 서버가 떠 있습니다. 그 서버를 끄거나 "
                "다른 포트를 고르세요.",
            )
        ]
    return [
        Problem(
            "error",
            f"포트 {plan.port}을(를) 다른 프로그램이 쓰고 있습니다. "
            "다른 포트를 고르세요.",
        )
    ]


def _asset_problems(settings: LauncherSettings) -> list[Problem]:
    root = (
        resolved_path(settings.assets_dir)
        if settings.assets_dir
        else DEFAULT_ASSETS_DIR
    )
    if not root.exists():
        if settings.assets_dir:
            return [
                Problem(
                    "warning", f"그림 폴더가 없습니다 ({root}): 그림 없이 시작합니다"
                )
            ]
        return [Problem("note", "그림 폴더(assets)가 없어 그림 없이 시작합니다")]
    missing = [
        relative
        for _name, relative in ASSET_ENVIRONMENT
        if not (root / relative).exists()
    ]
    if missing:
        return [Problem("note", "그림 폴더에 없는 것: " + ", ".join(missing))]
    return []


def preflight(
    settings: LauncherSettings,
    plan: LaunchPlan,
    *,
    check_torch: bool = True,
    run: Callable[
        [Sequence[str], float], subprocess.CompletedProcess[str] | None
    ] = run_quiet,
) -> list[Problem]:
    """Everything worth saying before the server is started, errors first.

    An error means the start would fail; a warning, that it would come up
    with something missing the host probably wanted; a note, a fact.
    Slow (the torch check imports torch in a child), so the window runs it
    off the event loop.
    """

    problems: list[Problem] = []
    missing = [name for name in ("fastapi", "uvicorn") if find_spec(name) is None]
    if missing:
        problems.append(
            Problem(
                "error",
                f"서버 의존성({', '.join(missing)})이 없습니다. 터미널에서 프로젝트 "
                f"폴더로 가서 `{SYNC_UI}`를 실행하세요.",
            )
        )
    if settings.mode == "remote":
        if not plan.host:
            problems.append(
                Problem("error", "원격 모드에서 서버를 열 주소를 고르세요.")
            )
        elif is_loopback(plan.host):
            problems.append(
                Problem(
                    "warning",
                    "이 주소로는 다른 사람이 들어올 수 없습니다(이 PC에서만 접속).",
                )
            )
        if settings.public_url and not settings.public_url.startswith(
            ("http://", "https://")
        ):
            problems.append(
                Problem("error", "공개 주소는 http:// 또는 https://로 시작해야 합니다.")
            )
    if not 1 <= settings.port <= 65535:
        problems.append(
            Problem("error", f"포트 {settings.port}은(는) 쓸 수 없는 번호입니다.")
        )
    elif plan.host:
        problems += _port_problems(plan)
    if settings.saves_dir:
        saves = resolved_path(settings.saves_dir)
        if saves.exists() and not saves.is_dir():
            problems.append(
                Problem("error", f"저장 폴더 자리에 파일이 있습니다: {saves}")
            )
        elif not saves.exists():
            problems.append(Problem("note", f"저장 폴더를 새로 만듭니다: {saves}"))
    problems += _asset_problems(settings)
    if not missing:
        problems += _search_checkpoint_problems(
            plan, settings, check_torch=check_torch, run=run
        )
    order = {"error": 0, "warning": 1, "note": 2}
    return sorted(problems, key=lambda problem: order[problem.level])


def has_errors(problems: Sequence[Problem]) -> bool:
    return any(problem.level == "error" for problem in problems)


_FAILURES: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (
        re.compile(r"cannot resolve --host (\S+)"),
        "주소 {0}을(를) 해석할 수 없습니다. 주소를 다시 고르세요.",
    ),
    (
        re.compile(r"cannot listen on (\S+?):(\d+)"),
        "{0}:{1}에서 연결을 받을 수 없습니다: 포트가 이미 쓰이고 있거나, 이 PC에 "
        "그 주소가 없습니다(Tailscale 연결과 LAN 주소를 확인하세요).",
    ),
    (
        re.compile(
            r"WinError 10048|Errno 48\b|Errno 98\b|address already in use|"
            r"error while attempting to bind",
            re.IGNORECASE,
        ),
        "포트가 이미 쓰이고 있습니다. 다른 포트를 고르세요.",
    ),
    (
        re.compile(r"No module named '([\w.]+)'"),
        "필요한 패키지({0})가 없습니다. 터미널에서 프로젝트 폴더로 가서 "
        f"`{SYNC_UI}`(탐색 AI를 쓰면 `{SYNC_TRAIN}`)를 실행하세요.",
    ),
    (
        re.compile(r"WinError 126|DLL load failed", re.IGNORECASE),
        "라이브러리(DLL)를 불러오지 못했습니다. Windows라면 최신 Visual C++ "
        "재배포 패키지(x64)를 설치하세요.",
    ),
    (
        re.compile(r"dune-imperium-server: error: (.+)"),
        "서버가 설정을 거부했습니다: {0}",
    ),
)


def explain_failure(log_tail: Sequence[str], exit_code: int | None) -> str:
    """Say in Korean why a server that should be running is not.

    Looks at the last lines first: the newest cause wins over an old
    warning.
    """

    for line in reversed(log_tail):
        for pattern, message in _FAILURES:
            match = pattern.search(line)
            if match:
                return message.format(*match.groups())
    code = "" if exit_code is None else f"(종료 코드 {exit_code})"
    return f"서버가 멈췄습니다{code}. 로그를 확인하세요."
