"""Double-click shortcuts to the launcher, made in the checkout (plan 5.10).

Both live in the project folder (user decision 2026-10-06: no project file
outside it) and are git-ignored; the host may drag them to the Dock or
pin them to the taskbar.

* macOS: ``Dune Imperium Server.app``, a bundle whose executable is a zsh
  script that finds the checkout from its own location, so moving the
  folder does not break it. Made on this Mac, it carries no quarantine
  flag, so Gatekeeper does not stop it.
* Windows: ``Dune Imperium Server.lnk`` to the ``dune-imperium-launcher``
  program uv installed (windowless), made through PowerShell's
  ``WScript.Shell``. The paths travel in environment variables and the
  script as ``-EncodedCommand``, so no quoting can break on a folder name
  with spaces, quotes or Hangul.
* WSL: the same ``.lnk``, made by the same script through
  ``powershell.exe``, to ``wslg.exe`` (no console window), which runs this
  checkout's ``.venv/bin/python -m dune_imperium.launcher`` in its
  distribution. It lies in the Linux folder; Explorer opens it there
  (under ``\\\\wsl.localhost``) and can drag it to the desktop or taskbar.
"""

import base64
import os
import plistlib
import stat
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Final

from dune_imperium.launcher.wsl import WSLG, is_wsl, wslpath
from dune_imperium.paths import PROJECT_ROOT

NAME: Final = "Dune Imperium Server"
BUNDLE_ID: Final = "local.dune-imperium.launcher"
_LAUNCH_SCRIPT: Final = r"""#!/bin/zsh
# Opens the Dune Imperium server launcher of the checkout this app sits in
# (docs/server-launcher-plan.md 5.10). Made by
# `python -m dune_imperium.launcher.cli --make-shortcut`.
cd "${0:A:h}/../../.." || exit 1
if [[ ! -x ./.venv/bin/python ]]; then
  hint="먼저 scripts/launcher/Install Launcher.command 를 실행하세요."
  /usr/bin/osascript -e "display alert \"Dune Imperium 서버\" message \"$hint\""
  exit 1
fi
exec ./.venv/bin/python -m dune_imperium.launcher
"""
# Errors go to standard output as plain UTF-8 text: redirected, PowerShell
# 5.1 writes its error stream as CLIXML in the console's code page.
_LNK_SCRIPT: Final = """\
[Console]::OutputEncoding = [Text.Encoding]::UTF8
try {
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($env:DUNE_LNK_PATH)
    $link.TargetPath = $env:DUNE_LNK_TARGET
    $link.Arguments = $env:DUNE_LNK_ARGUMENTS
    $link.WorkingDirectory = $env:DUNE_LNK_WORKDIR
    $link.Description = $env:DUNE_LNK_DESCRIPTION
    $link.Save()
} catch {
    [Console]::Out.WriteLine($_.Exception.Message)
    exit 1
}
"""

Run = Callable[[Sequence[str], float, Mapping[str, str]], tuple[int, str]]
"""Run a command with a timeout and extra environment variables; return
its exit code (-1 if it could not run or timed out) and what it said."""


class ShortcutError(Exception):
    """A shortcut could not be made; the message says why, in Korean."""


def info_plist() -> bytes:
    return plistlib.dumps(
        {
            "CFBundleExecutable": "launch",
            "CFBundleIdentifier": BUNDLE_ID,
            "CFBundleName": NAME,
            "CFBundleDisplayName": NAME,
            "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": "1.0",
            "LSMinimumSystemVersion": "11.0",
            "NSHighResolutionCapable": True,
        }
    )


def launch_script() -> str:
    return _LAUNCH_SCRIPT


def make_app_bundle(root: Path = PROJECT_ROOT) -> Path:
    """Write ``<root>/Dune Imperium Server.app``; return its path."""

    bundle = root / f"{NAME}.app"
    contents = bundle / "Contents"
    executable = contents / "MacOS" / "launch"
    try:
        executable.parent.mkdir(parents=True, exist_ok=True)
        (contents / "Info.plist").write_bytes(info_plist())
        executable.write_text(launch_script(), encoding="utf-8", newline="\n")
        mode = executable.stat().st_mode
        executable.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError as error:
        raise ShortcutError(f"앱을 만들지 못했습니다: {error}") from error
    return bundle


def windows_shortcut_target(root: Path = PROJECT_ROOT) -> tuple[Path, str]:
    """What the Windows shortcut runs: the windowless launcher program, or
    ``pythonw -m dune_imperium.launcher`` if that is missing."""

    scripts = root / ".venv" / "Scripts"
    program = scripts / "dune-imperium-launcher.exe"
    if program.exists():
        return program, ""
    return scripts / "pythonw.exe", "-m dune_imperium.launcher"


def powershell_command(program: str = "powershell") -> list[str]:
    encoded = base64.b64encode(_LNK_SCRIPT.encode("utf-16-le")).decode("ascii")
    return [
        program,
        "-NoProfile",
        "-NonInteractive",
        "-EncodedCommand",
        encoded,
    ]


def make_windows_shortcut(run: Run, root: Path = PROJECT_ROOT) -> Path:
    """Write ``<root>/Dune Imperium Server.lnk``; return its path."""

    target, arguments = windows_shortcut_target(root)
    if not target.exists():
        raise ShortcutError(
            f"{target} 이(가) 없습니다. 먼저 "
            "scripts\\launcher\\Install Launcher.cmd 를 실행하세요."
        )
    link = root / f"{NAME}.lnk"
    _write_lnk(
        run,
        powershell_command(),
        link,
        {
            "DUNE_LNK_PATH": str(link),
            "DUNE_LNK_TARGET": str(target),
            "DUNE_LNK_ARGUMENTS": arguments,
            "DUNE_LNK_WORKDIR": str(root),
            "DUNE_LNK_DESCRIPTION": "Dune Imperium 서버",
        },
    )
    return link


def wsl_shortcut_arguments(distro: str, root: Path) -> str:
    """What the WSL shortcut passes to ``wslg.exe``: the distribution, the
    checkout as the working folder, then the launcher (as WSL's own
    Start-menu entries do: ``-d <distro> --cd <folder> -- <command>``)."""

    return subprocess.list2cmdline(
        ["-d", distro, "--cd", str(root), "--"]
        + [".venv/bin/python", "-m", "dune_imperium.launcher"]
    )


Convert = Callable[[str], str | None]


def _to_windows(path: str) -> str | None:
    return wslpath(path, to_windows=True)


def _to_linux(path: str) -> str | None:
    return wslpath(path, to_windows=False)


def make_wsl_shortcut(
    run: Run,
    root: Path = PROJECT_ROOT,
    *,
    distro: str | None = None,
    to_windows: Convert = _to_windows,
    to_linux: Convert = _to_linux,
) -> Path:
    """Write ``<root>/Dune Imperium Server.lnk`` for Windows to open this
    WSL checkout's launcher; return its path."""

    name = os.environ.get("WSL_DISTRO_NAME", "") if distro is None else distro
    if not name:
        raise ShortcutError("WSL 배포판 이름(WSL_DISTRO_NAME)을 알 수 없습니다.")
    python = root / ".venv" / "bin" / "python"
    if not python.exists():
        raise ShortcutError(
            f"{python} 이(가) 없습니다. 먼저 scripts/launcher/install-wsl.sh 를 "
            "실행하세요."
        )
    wslg = to_linux(WSLG)
    if wslg is None or not Path(wslg).exists():
        raise ShortcutError(
            f"{WSLG} 이(가) 없습니다. Windows에서 `wsl --update`로 WSL을 "
            "새로 받으세요."
        )
    link = root / f"{NAME}.lnk"
    link_windows = to_windows(str(link))
    root_windows = to_windows(str(root))
    if link_windows is None or root_windows is None:
        raise ShortcutError("프로젝트 폴더의 Windows 경로를 얻지 못했습니다(wslpath).")
    values = {
        "DUNE_LNK_PATH": link_windows,
        "DUNE_LNK_TARGET": WSLG,
        "DUNE_LNK_ARGUMENTS": wsl_shortcut_arguments(name, root),
        "DUNE_LNK_WORKDIR": root_windows,
        "DUNE_LNK_DESCRIPTION": "Dune Imperium 서버",
    }
    # A Windows program sees only the variables WSLENV names.
    shared = [os.environ.get("WSLENV", ""), *values]
    values["WSLENV"] = ":".join(part for part in shared if part)
    _write_lnk(run, powershell_command("powershell.exe"), link, values)
    return link


def _write_lnk(
    run: Run, argv: Sequence[str], link: Path, env: Mapping[str, str]
) -> None:
    code, errors = run(argv, 60.0, env)
    if code != 0 or not link.exists():
        detail = errors.strip().splitlines()[-1] if errors.strip() else f"코드 {code}"
        raise ShortcutError(f"바로가기를 만들지 못했습니다: {detail}")


def _run_quiet(
    argv: Sequence[str], timeout: float, env: Mapping[str, str]
) -> tuple[int, str]:
    from dune_imperium.launcher.command import run_quiet

    result = run_quiet(argv, timeout, env=env)
    if result is None:
        return -1, "PowerShell이 실행되지 않았거나 응답이 없습니다"
    return result.returncode, f"{result.stdout}\n{result.stderr}"


def make_shortcut(
    root: Path = PROJECT_ROOT,
    *,
    platform: str = sys.platform,
    run: Run = _run_quiet,
    wsl: bool | None = None,
) -> Path:
    """Make this machine's double-click shortcut to the launcher."""

    if platform == "darwin":
        return make_app_bundle(root)
    if platform == "win32":
        return make_windows_shortcut(run, root)
    if platform == "linux" and (is_wsl() if wsl is None else wsl):
        return make_wsl_shortcut(run, root)
    raise ShortcutError(
        "이 운영체제에서는 바로가기를 만들지 않습니다: "
        f"{os.path.join('.venv', 'bin', 'dune-imperium-launcher')} 를 실행하세요."
    )
