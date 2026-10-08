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
"""

import base64
import os
import plistlib
import stat
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Final

from dune_imperium.paths import PROJECT_ROOT

NAME: Final = "Dune Imperium Server"
BUNDLE_ID: Final = "local.dune-imperium.launcher"
_LAUNCH_SCRIPT: Final = """\
#!/bin/zsh
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
_LNK_SCRIPT: Final = """\
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($env:DUNE_LNK_PATH)
$link.TargetPath = $env:DUNE_LNK_TARGET
$link.Arguments = $env:DUNE_LNK_ARGUMENTS
$link.WorkingDirectory = $env:DUNE_LNK_WORKDIR
$link.Description = $env:DUNE_LNK_DESCRIPTION
$link.Save()
"""

Run = Callable[[Sequence[str], float, Mapping[str, str]], tuple[int, str]]
"""Run a command with a timeout and extra environment variables; return
its exit code (-1 if it could not run) and its error output."""


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


def powershell_command() -> list[str]:
    encoded = base64.b64encode(_LNK_SCRIPT.encode("utf-16-le")).decode("ascii")
    return [
        "powershell",
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
    code, errors = run(
        powershell_command(),
        60.0,
        {
            "DUNE_LNK_PATH": str(link),
            "DUNE_LNK_TARGET": str(target),
            "DUNE_LNK_ARGUMENTS": arguments,
            "DUNE_LNK_WORKDIR": str(root),
            "DUNE_LNK_DESCRIPTION": "Dune Imperium 서버",
        },
    )
    if code != 0 or not link.exists():
        detail = errors.strip().splitlines()[-1] if errors.strip() else f"코드 {code}"
        raise ShortcutError(f"바로가기를 만들지 못했습니다: {detail}")
    return link


def _run_quiet(
    argv: Sequence[str], timeout: float, env: Mapping[str, str]
) -> tuple[int, str]:
    from dune_imperium.launcher.command import run_quiet

    result = run_quiet(argv, timeout, env=env)
    if result is None:
        return -1, "PowerShell을 실행하지 못했습니다"
    return result.returncode, result.stderr


def make_shortcut(
    root: Path = PROJECT_ROOT,
    *,
    platform: str = sys.platform,
    run: Run = _run_quiet,
) -> Path:
    """Make this machine's double-click shortcut to the launcher."""

    if platform == "darwin":
        return make_app_bundle(root)
    if platform == "win32":
        return make_windows_shortcut(run, root)
    raise ShortcutError(
        "이 운영체제에서는 바로가기를 만들지 않습니다: "
        f"{os.path.join('.venv', 'bin', 'dune-imperium-launcher')} 를 실행하세요."
    )
