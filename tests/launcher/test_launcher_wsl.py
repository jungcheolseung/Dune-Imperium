"""The launcher under WSL: Windows browser and Explorer, Tk with Xft (plan 5.13)."""

import sys
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from dune_imperium.cli import server as server_cli
from dune_imperium.launcher import cli, command, wsl
from dune_imperium.launcher.command import (
    build_plan,
    explain_failure,
    has_errors,
    listen_host,
    preflight,
)
from dune_imperium.launcher.settings import LauncherSettings
from dune_imperium.launcher.shortcuts import (
    NAME,
    ShortcutError,
    make_shortcut,
    make_wsl_shortcut,
    wsl_shortcut_arguments,
)
from dune_imperium.launcher.wsl import (
    WSLG,
    browser_command,
    bundles_tk86,
    find_xft_tk,
    is_wsl,
    load_xft_tk,
    xft_tk_candidates,
)
from dune_imperium.paths import PROJECT_ROOT

ADMIN_LINK = "http://127.0.0.1:8000/#admin=abc-DEF_123"


@pytest.mark.parametrize(
    ("release", "expected"),
    [
        ("6.6.87.2-microsoft-standard-WSL2", True),
        ("4.4.0-19041-Microsoft", True),
        ("6.8.0-45-generic", False),
        ("24.0.0", False),
    ],
)
def test_wsl_is_told_by_its_kernel(release: str, expected: bool) -> None:
    assert is_wsl(release) is expected


# --- where a remote server listens -------------------------------------------


@pytest.mark.parametrize(
    ("named", "wsl_listens"),
    [
        ("100.110.0.112", "0.0.0.0"),
        ("192.168.1.28", "0.0.0.0"),
        ("127.0.0.1", "127.0.0.1"),
        ("0.0.0.0", "0.0.0.0"),
        ("::1", "::1"),
        ("fd7a:115c:a1e0::1", "fd7a:115c:a1e0::1"),
        ("mac-mini.tail1234.ts.net", "mac-mini.tail1234.ts.net"),
    ],
)
def test_under_wsl_one_ipv4_address_becomes_every_address(
    named: str, wsl_listens: str
) -> None:
    # Windows cannot reach a WSL server through its own Tailscale or LAN
    # address, only through loopback (2026-10-30: the admin link timed out).
    assert listen_host(named, wsl=True) == wsl_listens
    assert listen_host(named, wsl=False) == named


def test_under_wsl_the_admin_link_is_loopback_and_room_links_the_chosen_address() -> (
    None
):
    settings = LauncherSettings(mode="remote", host="100.110.0.112", port=8000)
    plan = build_plan(settings, "KEY", python="py", environ={}, wsl=True)
    assert plan.host == "0.0.0.0"
    arguments = plan.server_args
    assert arguments[arguments.index("--host") + 1] == "0.0.0.0"
    assert arguments[arguments.index("--public-url") + 1] == (
        "http://100.110.0.112:8000"
    )
    assert plan.open_url == "http://127.0.0.1:8000/#admin=KEY"
    assert plan.open_url == server_cli.admin_link("0.0.0.0", 8000, "KEY")
    assert plan.room_base == "http://100.110.0.112:8000"


def test_under_wsl_a_chosen_room_link_base_is_kept() -> None:
    settings = LauncherSettings(
        mode="remote",
        host="100.110.0.112",
        port=8000,
        public_url="https://pc.tail1234.ts.net",
    )
    plan = build_plan(settings, "KEY", python="py", environ={}, wsl=True)
    assert plan.room_base == "https://pc.tail1234.ts.net"


def test_under_wsl_a_local_start_stays_on_loopback() -> None:
    settings = LauncherSettings(mode="local", host="100.110.0.112", port=8000)
    plan = build_plan(settings, None, python="py", environ={}, wsl=True)
    assert plan.host == "127.0.0.1"


def test_under_wsl_the_chosen_address_must_still_be_this_pcs() -> None:
    # 192.0.2.1 is TEST-NET-1: never an address of a real interface.
    settings = LauncherSettings(mode="remote", host="192.0.2.1", port=8000)
    plan = build_plan(settings, "KEY", python="py", environ={}, wsl=True)
    problems = preflight(settings, plan, check_torch=False)
    texts = [(problem.level, problem.text) for problem in problems]
    assert any(
        level == "error" and "이 PC에 192.0.2.1 주소가 없습니다" in text
        for level, text in texts
    )
    assert any(level == "note" and text.startswith("WSL:") for level, text in texts)
    # The room links name the chosen address: no wildcard warning.
    assert not any("방 링크가" in text for _, text in texts)


def test_the_launcher_asks_whether_it_runs_under_wsl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Without wsl=, build_plan asks is_wsl() (tests/launcher/conftest.py
    # pins it to False for every other test).
    monkeypatch.setattr(command, "is_wsl", lambda: True)
    settings = LauncherSettings(mode="remote", host="100.110.0.112", port=8000)
    assert build_plan(settings, "KEY", python="py", environ={}).host == "0.0.0.0"
    assert listen_host("100.110.0.112") == "0.0.0.0"


def _tailnet_address_here(
    monkeypatch: pytest.MonkeyPatch, named: str, port_problem: str | None
) -> None:
    """Make ``named`` an address of this PC, and say what binding every
    address on the port gives."""

    def bind_problem(host: str, port: int) -> str | None:
        if host == named and port == 0:
            return None
        assert host == "0.0.0.0", host
        return port_problem

    monkeypatch.setattr(server_cli, "bind_problem", bind_problem)


def test_under_wsl_an_address_of_this_pc_gets_only_the_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _tailnet_address_here(monkeypatch, "100.110.0.112", None)
    monkeypatch.setattr(command, "_answers", lambda host, port: False)
    settings = LauncherSettings(mode="remote", host="100.110.0.112", port=8000)
    plan = build_plan(settings, "KEY", python="py", environ={}, wsl=True)
    problems = preflight(settings, plan, check_torch=False)
    assert not has_errors(problems), problems
    assert [p.level for p in problems if p.text.startswith("WSL:")] == ["note"]


def test_under_wsl_a_dune_server_on_the_chosen_address_is_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An earlier server holds only 100.x:8000; the wildcard bind fails and
    # loopback finds nobody, so the chosen address is asked too (review of
    # cedb0e4d: it said "another program").
    _tailnet_address_here(
        monkeypatch,
        "100.110.0.112",
        "cannot listen on 0.0.0.0:8000: Address already in use",
    )
    asked: list[str] = []

    def whoami(host: str, port: int) -> dict[str, object] | None:
        asked.append(host)
        return {"access": "remote"} if host == "100.110.0.112" else None

    monkeypatch.setattr(command, "whoami", whoami)
    settings = LauncherSettings(mode="remote", host="100.110.0.112", port=8000)
    plan = build_plan(settings, "KEY", python="py", environ={}, wsl=True)
    errors = [p.text for p in preflight(settings, plan, check_torch=False)]
    assert any("이미 Dune 서버가 떠 있습니다" in text for text in errors), errors
    assert asked == ["0.0.0.0", "100.110.0.112"]


@pytest.mark.parametrize("host", ["0.0.0.0", "::"])
def test_a_wildcard_bind_failure_blames_the_port_not_an_address(host: str) -> None:
    message = explain_failure(
        [f"dune-imperium-server: cannot listen on {host}:8000: Address in use"], 1
    )
    assert "포트 8000" in message
    assert "주소가 없습니다" not in message and host not in message


# --- Windows browser and Explorer --------------------------------------------


def test_links_go_to_rundll32_whole(monkeypatch: pytest.MonkeyPatch) -> None:
    # explorer.exe <url> opened nothing on 2026-10-30; FileProtocolHandler
    # handed the query and the #admin= fragment over unchanged.
    rundll32 = "/mnt/c/WINDOWS/system32/rundll32.exe"
    monkeypatch.setattr("shutil.which", lambda name: rundll32)
    assert browser_command(ADMIN_LINK) == [
        rundll32,
        "url.dll,FileProtocolHandler",
        ADMIN_LINK,
    ]


def test_without_windows_on_path_the_usual_place_is_asked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[tuple[str, bool]] = []

    def convert(path: str, *, to_windows: bool) -> str:
        asked.append((path, to_windows))
        return "/mnt/c/Windows/System32/rundll32.exe"

    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr(wsl, "wslpath", convert)
    assert browser_command(ADMIN_LINK)[0] == "/mnt/c/Windows/System32/rundll32.exe"
    assert asked == [(r"C:\Windows\System32\rundll32.exe", False)]


def test_explorer_gets_the_folder_by_its_windows_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    started: list[list[str]] = []
    monkeypatch.setattr("shutil.which", lambda name: f"/win/{name}")
    monkeypatch.setattr(
        wsl, "wslpath", lambda path, *, to_windows: rf"\\wsl.localhost\U{path}"
    )
    monkeypatch.setattr(wsl, "_start", started.append)
    wsl.reveal_in_explorer(tmp_path)
    assert started == [["/win/explorer.exe", rf"\\wsl.localhost\U{tmp_path}"]]


def test_the_window_opens_links_in_windows_under_wsl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("tkinter")
    from dune_imperium.launcher import gui

    opened: list[str] = []
    done = threading.Event()

    def windows(url: str) -> None:
        opened.append(url)
        done.set()

    monkeypatch.setattr(gui, "is_wsl", lambda: True)
    monkeypatch.setattr(gui, "open_in_windows_browser", windows)
    monkeypatch.setattr("webbrowser.open", lambda url: pytest.fail(url))
    gui._open_in_browser(ADMIN_LINK)
    assert done.wait(5)
    assert opened == [ADMIN_LINK]


@pytest.mark.skipif(sys.platform != "linux", reason="the Linux branch of reveal")
def test_the_window_shows_folders_in_explorer_under_wsl(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pytest.importorskip("tkinter")
    from dune_imperium.launcher import gui

    shown: list[Path] = []
    monkeypatch.setattr(gui, "is_wsl", lambda: True)
    monkeypatch.setattr(gui, "reveal_in_explorer", shown.append)
    gui.reveal(tmp_path / "logs")
    assert shown == [tmp_path / "logs"]


# --- Tk with Xft -------------------------------------------------------------


def _tk(base: Path, arch: str = "x86_64-linux-gnu") -> tuple[Path, Path]:
    library = base / "usr" / "lib" / arch / "libtk8.6.so"
    scripts = base / "usr" / "share" / "tcltk" / "tk8.6"
    library.parent.mkdir(parents=True)
    library.write_bytes(b"")
    scripts.mkdir(parents=True)
    (scripts / "tk.tcl").write_text("", encoding="utf-8")
    return library, scripts


def test_the_system_tk_comes_before_the_unpacked_copy(tmp_path: Path) -> None:
    candidates = xft_tk_candidates(tmp_path / "local", tmp_path / "system")
    assert [library.parents[3].name for library, _ in candidates] == [
        "system",
        "local",
    ]
    assert candidates[0][0].name == "libtk8.6.so"
    assert candidates[0][1].parts[-3:] == ("share", "tcltk", "tk8.6")


def test_the_install_script_unpacks_where_the_launcher_looks() -> None:
    script = (PROJECT_ROOT / "scripts" / "launcher" / "install-wsl.sh").read_text(
        encoding="utf-8"
    )
    assert f"tk_dir={wsl.XFT_TK_DIR.relative_to(PROJECT_ROOT)}" in script
    assert "apt-get download libtk8.6" in script
    assert "sudo apt-get" not in script


def test_a_library_without_its_scripts_is_passed_over(tmp_path: Path) -> None:
    lone = tmp_path / "lone" / "libtk8.6.so"
    lone.parent.mkdir()
    lone.write_bytes(b"")
    whole = _tk(tmp_path / "whole")
    assert find_xft_tk([(lone, tmp_path / "missing"), whole]) == whole[0]
    assert find_xft_tk([(lone, tmp_path / "missing")]) is None


def test_loading_points_tk_at_the_packages_own_scripts(tmp_path: Path) -> None:
    library, scripts = _tk(tmp_path / "system")
    loaded: list[Path] = []
    environ: dict[str, str] = {}
    assert load_xft_tk([(library, scripts)], load=loaded.append, environ=environ) == (
        library
    )
    assert loaded == [library]
    assert environ == {"TK_LIBRARY": str(scripts)}


def test_a_library_that_will_not_load_falls_through(tmp_path: Path) -> None:
    broken = _tk(tmp_path / "broken")
    good = _tk(tmp_path / "good")

    def load(library: Path) -> None:
        if library == broken[0]:
            raise OSError("wrong ELF class")

    environ: dict[str, str] = {}
    assert load_xft_tk([broken, good], load=load, environ=environ) == good[0]
    assert environ["TK_LIBRARY"] == str(good[1])


def test_nothing_to_load_leaves_tk_alone(tmp_path: Path) -> None:
    def load(library: Path) -> None:
        pytest.fail(f"loaded {library}")

    environ: dict[str, str] = {}
    assert load_xft_tk([], load=load, environ=environ) is None
    assert environ == {}


def test_only_a_python_with_its_own_tk86_gets_the_library(tmp_path: Path) -> None:
    assert not bundles_tk86(str(tmp_path))
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "libtk8.6.so").write_bytes(b"")
    assert bundles_tk86(str(tmp_path))


def test_the_check_names_the_missing_tk_and_the_cure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(wsl, "bundles_tk86", lambda: True)
    monkeypatch.setattr(wsl, "find_xft_tk", lambda: None)
    line = cli._xft_tk_line()
    assert line is not None and "install-wsl.sh" in line and "\\uXXXX" in line
    monkeypatch.setattr(wsl, "find_xft_tk", lambda: Path("/usr/lib/x/libtk8.6.so"))
    assert cli._xft_tk_line() == "한글 글꼴(Xft Tk): /usr/lib/x/libtk8.6.so"
    monkeypatch.setattr(sys, "platform", "darwin")
    assert cli._xft_tk_line() is None


def test_the_window_loads_the_library_only_on_linux(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(wsl, "load_xft_tk", lambda: pytest.fail("loaded"))
    assert cli._prepare_tk() is None
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(wsl, "bundles_tk86", lambda: False)
    assert cli._prepare_tk() is None
    monkeypatch.setattr(wsl, "bundles_tk86", lambda: True)
    monkeypatch.setattr(wsl, "load_xft_tk", lambda: Path("/x/libtk8.6.so"))
    assert cli._prepare_tk() == "Tk: Xft library /x/libtk8.6.so"


# --- the WSL shortcut --------------------------------------------------------


class FakePowerShell:
    def __init__(self, link: Path, code: int = 0, errors: str = "") -> None:
        self.link = link
        self.code = code
        self.errors = errors
        self.calls: list[tuple[list[str], dict[str, str]]] = []

    def __call__(
        self, argv: Sequence[str], timeout: float, env: Mapping[str, str]
    ) -> tuple[int, str]:
        self.calls.append((list(argv), dict(env)))
        if self.code == 0:
            self.link.write_bytes(b"lnk")
        return self.code, self.errors


def _wsl_checkout(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "Dune 'Imperium' 한글"
    python = root / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_bytes(b"")
    wslg = tmp_path / "wslg.exe"
    wslg.write_bytes(b"")
    return root, wslg


def _windows(path: str) -> str:
    return "W:" + path


def test_the_wsl_shortcut_runs_wslg_in_this_distribution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, wslg = _wsl_checkout(tmp_path)
    monkeypatch.setenv("WSLENV", "USERPROFILE/p")
    run = FakePowerShell(root / f"{NAME}.lnk")
    link = make_wsl_shortcut(
        run,
        root,
        distro="Ubuntu-24.04",
        to_windows=_windows,
        to_linux=lambda path: str(wslg),
    )
    assert link == root / f"{NAME}.lnk"
    [(argv, env)] = run.calls
    assert argv[0] == "powershell.exe" and "-EncodedCommand" in argv
    assert env["DUNE_LNK_PATH"] == _windows(str(link))
    assert env["DUNE_LNK_TARGET"] == WSLG
    assert env["DUNE_LNK_WORKDIR"] == _windows(str(root))
    assert env["DUNE_LNK_ARGUMENTS"] == (
        f'-d Ubuntu-24.04 --cd "{root}" -- .venv/bin/python -m dune_imperium.launcher'
    )
    # Windows programs see only what WSLENV names; the host's own entries stay.
    assert env["WSLENV"].split(":") == [
        "USERPROFILE/p",
        "DUNE_LNK_PATH",
        "DUNE_LNK_TARGET",
        "DUNE_LNK_ARGUMENTS",
        "DUNE_LNK_WORKDIR",
        "DUNE_LNK_DESCRIPTION",
    ]


def test_the_wsl_arguments_quote_a_folder_with_spaces() -> None:
    arguments = wsl_shortcut_arguments("Ubuntu", Path("/home/a b/Dune"))
    assert arguments.startswith('-d Ubuntu --cd "/home/a b/Dune" -- ')


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("no distro", "WSL_DISTRO_NAME"),
        ("no venv", "install-wsl.sh"),
        ("no wslg", "wsl --update"),
        ("powershell fails", "Access is denied"),
    ],
)
def test_a_wsl_shortcut_that_cannot_be_made_says_why(
    tmp_path: Path, change: str, message: str
) -> None:
    root, wslg = _wsl_checkout(tmp_path)
    if change == "no venv":
        (root / ".venv" / "bin" / "python").unlink()
    if change == "no wslg":
        wslg.unlink()
    run = FakePowerShell(
        root / f"{NAME}.lnk",
        *((1, "x\nAccess is denied.\n") if change == "powershell fails" else ()),
    )
    with pytest.raises(ShortcutError, match=message):
        make_wsl_shortcut(
            run,
            root,
            distro="" if change == "no distro" else "Ubuntu",
            to_windows=_windows,
            to_linux=lambda path: str(wslg),
        )


def test_linux_makes_the_wsl_shortcut_only_under_wsl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    made: list[Path] = []

    def fake(run: object, root: Path) -> Path:
        made.append(root)
        return root / f"{NAME}.lnk"

    monkeypatch.setattr("dune_imperium.launcher.shortcuts.make_wsl_shortcut", fake)
    assert make_shortcut(tmp_path, platform="linux", wsl=True) == (
        tmp_path / f"{NAME}.lnk"
    )
    assert made == [tmp_path]
    with pytest.raises(ShortcutError):
        make_shortcut(tmp_path, platform="linux", wsl=False)
