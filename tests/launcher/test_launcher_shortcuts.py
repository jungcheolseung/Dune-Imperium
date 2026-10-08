"""Double-click shortcuts, first-install scripts and keep-awake (plan 5.10-11)."""

import base64
import os
import plistlib
import shutil
import stat
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from dune_imperium.launcher.cli import _build_parser
from dune_imperium.launcher.keepawake import (
    ES_CONTINUOUS,
    ES_SYSTEM_REQUIRED,
    KeepAwake,
)
from dune_imperium.launcher.shortcuts import (
    BUNDLE_ID,
    NAME,
    ShortcutError,
    info_plist,
    make_app_bundle,
    make_shortcut,
    make_windows_shortcut,
    powershell_command,
)
from dune_imperium.paths import PROJECT_ROOT

INSTALL_COMMAND = PROJECT_ROOT / "scripts" / "launcher" / "Install Launcher.command"
INSTALL_CMD = PROJECT_ROOT / "scripts" / "launcher" / "Install Launcher.cmd"


# --- macOS app ---------------------------------------------------------------


def test_the_app_bundle_names_its_executable() -> None:
    info = plistlib.loads(info_plist())
    assert info["CFBundleExecutable"] == "launch"
    assert info["CFBundlePackageType"] == "APPL"
    assert info["CFBundleIdentifier"] == BUNDLE_ID
    assert info["CFBundleName"] == NAME


@pytest.mark.skipif(not Path("/bin/zsh").exists(), reason="needs zsh")
def test_the_app_opens_the_launcher_of_the_checkout_it_sits_in(tmp_path: Path) -> None:
    # A folder name with spaces, a quote and Hangul, as a host's might be.
    root = tmp_path / "내 게임's Dune"
    python = root / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    record = tmp_path / "ran.txt"
    python.write_text(
        f'#!/bin/sh\nprintf "%s\\n" "$PWD" "$@" > "{record}"\n', encoding="utf-8"
    )
    python.chmod(0o755)

    bundle = make_app_bundle(root)

    assert bundle == root / f"{NAME}.app"
    launch = bundle / "Contents" / "MacOS" / "launch"
    assert launch.stat().st_mode & stat.S_IXUSR
    subprocess.run(["/bin/zsh", str(launch)], check=True, timeout=30)
    cwd, *arguments = record.read_text(encoding="utf-8").splitlines()
    assert Path(cwd).resolve() == root.resolve()
    assert arguments == ["-m", "dune_imperium.launcher"]


def test_the_shortcuts_stay_out_of_git() -> None:
    paths = [f"{NAME}.app/Contents/Info.plist", f"{NAME}.lnk"]
    ignored = subprocess.run(
        ["git", "check-ignore", *paths],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ignored.stdout.splitlines() == paths


# --- Windows shortcut --------------------------------------------------------


class FakePowerShell:
    def __init__(self, code: int = 0, errors: str = "") -> None:
        self.code = code
        self.errors = errors
        self.calls: list[tuple[list[str], dict[str, str]]] = []

    def __call__(
        self, argv: Sequence[str], timeout: float, env: Mapping[str, str]
    ) -> tuple[int, str]:
        self.calls.append((list(argv), dict(env)))
        if self.code == 0:
            Path(env["DUNE_LNK_PATH"]).write_bytes(b"lnk")
        return self.code, self.errors


def _windows_checkout(tmp_path: Path) -> Path:
    root = tmp_path / "Dune 'Imperium' 한글"
    scripts = root / ".venv" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "dune-imperium-launcher.exe").write_bytes(b"")
    return root


def test_the_windows_shortcut_passes_its_paths_outside_the_script(
    tmp_path: Path,
) -> None:
    root = _windows_checkout(tmp_path)
    run = FakePowerShell()
    link = make_windows_shortcut(run, root)
    assert link == root / f"{NAME}.lnk" and link.exists()
    [(argv, env)] = run.calls
    assert argv[:3] == ["powershell", "-NoProfile", "-NonInteractive"]
    script = base64.b64decode(argv[argv.index("-EncodedCommand") + 1]).decode(
        "utf-16-le"
    )
    assert "$env:DUNE_LNK_TARGET" in script and "CreateShortcut" in script
    # Nothing of the folder name is in the script: no quoting to get wrong.
    assert "Imperium" not in script
    assert env["DUNE_LNK_TARGET"] == str(
        root / ".venv" / "Scripts" / "dune-imperium-launcher.exe"
    )
    assert env["DUNE_LNK_WORKDIR"] == str(root)
    assert env["DUNE_LNK_ARGUMENTS"] == ""


def test_without_the_launcher_program_the_shortcut_runs_pythonw(
    tmp_path: Path,
) -> None:
    root = _windows_checkout(tmp_path)
    (root / ".venv" / "Scripts" / "dune-imperium-launcher.exe").unlink()
    (root / ".venv" / "Scripts" / "pythonw.exe").write_bytes(b"")
    run = FakePowerShell()
    make_windows_shortcut(run, root)
    env = run.calls[0][1]
    assert env["DUNE_LNK_TARGET"].endswith("pythonw.exe")
    assert env["DUNE_LNK_ARGUMENTS"] == "-m dune_imperium.launcher"


def test_a_failed_windows_shortcut_says_why(tmp_path: Path) -> None:
    root = _windows_checkout(tmp_path)
    with pytest.raises(ShortcutError, match="Access is denied"):
        make_windows_shortcut(FakePowerShell(1, "x\nAccess is denied.\n"), root)


def test_without_an_environment_there_is_nothing_to_point_at(tmp_path: Path) -> None:
    with pytest.raises(ShortcutError, match="Install Launcher.cmd"):
        make_windows_shortcut(FakePowerShell(), tmp_path)


def test_other_systems_get_no_shortcut(tmp_path: Path) -> None:
    with pytest.raises(ShortcutError):
        make_shortcut(tmp_path, platform="linux")


def test_the_encoded_script_is_what_powershell_expects() -> None:
    argv = powershell_command()
    encoded = argv[argv.index("-EncodedCommand") + 1]
    assert base64.b64decode(encoded).decode("utf-16-le").startswith("$shell")


# --- first-install scripts ---------------------------------------------------


def test_the_macos_install_script_is_executable_in_git() -> None:
    listed = subprocess.run(
        ["git", "ls-files", "-s", str(INSTALL_COMMAND.relative_to(PROJECT_ROOT))],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert listed.startswith("100755 ")


@pytest.mark.skipif(not Path("/bin/zsh").exists(), reason="needs zsh")
def test_the_macos_install_script_parses() -> None:
    subprocess.run(["/bin/zsh", "-n", str(INSTALL_COMMAND)], check=True)


def test_the_windows_install_script_is_ascii_with_crlf_in_checkouts() -> None:
    # cmd.exe reads a batch file in the console's code page.
    INSTALL_CMD.read_bytes().decode("ascii")
    attributes = subprocess.run(
        ["git", "check-attr", "eol", "--", str(INSTALL_CMD.relative_to(PROJECT_ROOT))],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert attributes.strip().endswith("eol: crlf")


@pytest.mark.parametrize("script", [INSTALL_COMMAND, INSTALL_CMD])
def test_the_install_scripts_keep_existing_packages_and_make_the_shortcut(
    script: Path,
) -> None:
    text = script.read_text(encoding="utf-8")
    assert "uv sync --locked --inexact" in text
    assert "-m dune_imperium.launcher.cli --make-shortcut" in text
    assert "uv run" not in text
    assert _build_parser().parse_args(["--make-shortcut"]).make_shortcut


# --- keep-awake --------------------------------------------------------------


class FakeProcess:
    def __init__(self, argv: list[str]) -> None:
        self.argv = argv
        self.terminated = False

    def poll(self) -> int | None:
        return 0 if self.terminated else None

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float | None = None) -> int:
        return 0

    def kill(self) -> None:
        self.terminated = True


def test_macos_watches_the_server_with_caffeinate() -> None:
    started: list[FakeProcess] = []

    def popen(argv: list[str], **options: object) -> FakeProcess:
        started.append(FakeProcess(argv))
        return started[-1]

    awake = KeepAwake(platform="darwin", popen=popen)  # type: ignore[arg-type]
    assert awake.hold(4242) is None
    assert started[0].argv == ["/usr/bin/caffeinate", "-i", "-w", "4242"]
    assert awake.holding
    awake.release()
    assert started[0].terminated and not awake.holding


def test_windows_asks_the_system_and_clears_it_again() -> None:
    calls: list[int] = []

    def state(flags: int) -> int:
        calls.append(flags)
        return 1

    awake = KeepAwake(platform="win32", set_execution_state=state)
    assert awake.hold(4242) is None and awake.holding
    awake.release()
    assert calls == [ES_CONTINUOUS | ES_SYSTEM_REQUIRED, ES_CONTINUOUS]
    assert not awake.holding


def test_a_refused_windows_request_is_reported() -> None:
    awake = KeepAwake(platform="win32", set_execution_state=lambda flags: 0)
    note = awake.hold(4242)
    assert note is not None and "SetThreadExecutionState" in note
    assert not awake.holding


def test_elsewhere_keep_awake_does_nothing() -> None:
    awake = KeepAwake(platform="linux")
    assert awake.hold(4242) is None and not awake.holding


@pytest.mark.skipif(
    sys.platform != "darwin" or not shutil.which("caffeinate"),
    reason="macOS caffeinate",
)
def test_caffeinate_ends_with_the_server_it_watches() -> None:
    server = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    awake = KeepAwake()
    try:
        assert awake.hold(server.pid) is None and awake.holding
    finally:
        server.kill()
        server.wait(10)
    caffeinate = awake._caffeinate
    assert caffeinate is not None
    # -w: it ends by itself once the server is gone.
    assert caffeinate.wait(10) == 0
    awake.release()


def test_the_launcher_never_writes_outside_the_checkout_for_shortcuts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    root = tmp_path / "checkout"
    make_app_bundle(root)
    assert list(home.iterdir()) == []
    assert os.listdir(root) == [f"{NAME}.app"]
