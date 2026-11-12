"""The launcher on Linux, WSL in particular (docs/server-launcher-plan.md 5.13).

Under WSL the window comes up through WSLg, but what the host clicks
through to lives on the Windows side:

* links open in the Windows browser through ``rundll32
  url.dll,FileProtocolHandler``, which hands the whole URL over, the admin
  link's ``#admin=`` fragment included (``explorer.exe <url>`` opened
  nothing, 2026-10-30);
* folders open in Explorer;
* the double-click shortcut (``shortcuts.make_wsl_shortcut``) runs
  ``wslg.exe``, the program WSL's own Start-menu entries for Linux apps
  run: it opens no console window.

uv's Python carries a Tk built without Xft, which draws with the X
server's core fonts; WSLg's have no Hangul, so every Korean label came out
as ``\\uc11c\\ubc84``. Loading an Xft-enabled ``libtk8.6.so`` (the
system's ``libtk8.6`` package, or the copy ``scripts/launcher/install-wsl.sh``
unpacks into ``local/xft-tk``) before ``tkinter`` makes ``_tkinter`` bind
to it by its soname, and Tk then draws with fontconfig's fonts.
"""

import ctypes
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
from collections.abc import Callable, MutableMapping
from pathlib import Path
from typing import Final

from dune_imperium.paths import LOCAL_DIR

XFT_TK_DIR: Final = LOCAL_DIR / "xft-tk"
"""Where ``install-wsl.sh`` unpacks Ubuntu's ``libtk8.6`` package."""

SYSTEM_DIR: Final = Path("/")

WSLG: Final = r"C:\Program Files\WSL\wslg.exe"
_RUNDLL32: Final = r"C:\Windows\System32\rundll32.exe"
_EXPLORER: Final = r"C:\Windows\explorer.exe"

Load = Callable[[Path], object]


def is_wsl(release: str | None = None) -> bool:
    """Whether this is Linux under WSL: its kernel names Microsoft."""

    if release is None:
        if sys.platform != "linux":
            return False
        release = platform.uname().release
    return "microsoft" in release.lower()


def wslpath(path: str, *, to_windows: bool) -> str | None:
    """``path`` as the other side names it (``wslpath -w`` / ``-u``)."""

    from dune_imperium.launcher.command import run_output

    output = run_output(["wslpath", "-w" if to_windows else "-u", path], 5.0)
    if output is None or not output.strip():
        return None
    return output.strip()


def _windows_program(name: str, windows_path: str) -> str:
    """A Windows program by the PATH WSL appends, else by its usual place."""

    found = shutil.which(name)
    if found:
        return found
    return wslpath(windows_path, to_windows=False) or name


def _start(argv: list[str]) -> None:
    try:
        subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass


def browser_command(url: str) -> list[str]:
    rundll32 = _windows_program("rundll32.exe", _RUNDLL32)
    return [rundll32, "url.dll,FileProtocolHandler", url]


def open_in_windows_browser(url: str) -> None:
    """Open ``url`` in the Windows default browser."""

    _start(browser_command(url))


def reveal_in_explorer(path: Path) -> None:
    """Show a folder of this checkout in Windows Explorer."""

    folder = wslpath(str(path), to_windows=True)
    if folder is not None:
        _start([_windows_program("explorer.exe", _EXPLORER), folder])


# --- Tk with Xft -------------------------------------------------------------


def bundles_tk86(prefix: str = sys.base_prefix) -> bool:
    """Whether this Python carries its own Tk 8.6, as uv's builds do.

    A distribution's Python uses the system Tk, which has Xft already; a
    later uv build with Tk 9 must not get the 8.6 library either.
    """

    return (Path(prefix) / "lib" / "libtk8.6.so").is_file()


def xft_tk_candidates(
    local: Path = XFT_TK_DIR, system: Path = SYSTEM_DIR
) -> list[tuple[Path, Path]]:
    """(``libtk8.6.so``, its script folder) pairs, the system's first."""

    arch = sysconfig.get_config_var("MULTIARCH") or f"{platform.machine()}-linux-gnu"
    return [
        (
            base / "usr" / "lib" / arch / "libtk8.6.so",
            base / "usr" / "share" / "tcltk" / "tk8.6",
        )
        for base in (system, local)
    ]


def _present(
    candidates: list[tuple[Path, Path]] | None,
) -> list[tuple[Path, Path]]:
    pairs = xft_tk_candidates() if candidates is None else candidates
    return [
        (library, scripts)
        for library, scripts in pairs
        if library.is_file() and (scripts / "tk.tcl").is_file()
    ]


def find_xft_tk(candidates: list[tuple[Path, Path]] | None = None) -> Path | None:
    """The first Xft-enabled Tk there is, without loading it."""

    present = _present(candidates)
    return present[0][0] if present else None


def _load_global(library: Path) -> object:
    return ctypes.CDLL(str(library), mode=ctypes.RTLD_GLOBAL)


def load_xft_tk(
    candidates: list[tuple[Path, Path]] | None = None,
    *,
    load: Load = _load_global,
    environ: MutableMapping[str, str] = os.environ,
) -> Path | None:
    """Before ``tkinter`` is imported: load an Xft-enabled Tk for it.

    Returns the library loaded, or ``None`` if there is none to load (Tk
    then draws Hangul as ``\\uXXXX``). ``TK_LIBRARY`` names the package's
    own scripts, so they match the library whatever Tk version this Python
    was built with; the server the launcher starts inherits it and never
    reads it.
    """

    for library, scripts in _present(candidates):
        try:
            load(library)
        except OSError:
            continue
        environ["TK_LIBRARY"] = str(scripts)
        return library
    return None
