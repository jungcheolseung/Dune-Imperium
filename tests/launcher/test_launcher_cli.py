"""The launcher's console entry point (plan 5.1): --check and --start."""

import json
import socket
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

import pytest

from dune_imperium.launcher.cli import main
from dune_imperium.launcher.settings import LauncherSettings, load, save


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
        return port


def _settings_file(tmp_path: Path, settings: LauncherSettings) -> Path:
    path = tmp_path / "launcher.json"
    save(settings, path)
    return path


def _read_line(process: subprocess.Popen[str], timeout: float = 60) -> str:
    """One line of the process's output, without hanging the test."""

    assert process.stdout is not None
    stdout = process.stdout
    box: list[str] = []
    reader = threading.Thread(target=lambda: box.append(stdout.readline()))
    reader.start()
    reader.join(timeout)
    assert box, "no line from the launcher"
    return box[0]


def _launcher(path: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "dune_imperium.launcher.cli",
            "--start",
            "--settings",
            str(path),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )


def test_check_lists_versions_addresses_and_the_checks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _settings_file(tmp_path, LauncherSettings(port=_free_port()))
    code = main(["--check", "--settings", str(path)])
    out = capsys.readouterr().out
    assert "Python: 3.14" in out
    assert "주소 후보:" in out and "127.0.0.1" in out
    assert "저장 형식:" in out
    assert code == (1 if "[오류]" in out else 0)


def test_start_runs_a_server_until_its_input_ends(tmp_path: Path) -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("uvicorn")
    port = _free_port()
    path = _settings_file(
        tmp_path, LauncherSettings(port=port, saves_dir=str(tmp_path / "saves"))
    )
    launcher = _launcher(path)
    try:
        started = json.loads(_read_line(launcher))
        assert started["open_url"] == f"http://127.0.0.1:{port}/"
        assert started["access"] == "open"
        whoami = json.load(
            urllib.request.urlopen(f"http://127.0.0.1:{port}/whoami", timeout=5)
        )
        assert whoami["access"] == "open"
        assert launcher.stdin is not None
        launcher.stdin.close()
        stopped = json.loads(_read_line(launcher))
        code = launcher.wait(timeout=20)
    finally:
        if launcher.poll() is None:
            launcher.kill()
            launcher.wait(timeout=10)
    assert code == 0
    assert stopped["stopped"] == "stdin" and stopped["port_free"] is True
    assert load(path).settings.last_good is not None


def test_a_remote_start_keeps_its_fixed_key_and_hands_out_the_admin_link(
    tmp_path: Path,
) -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("uvicorn")
    port = _free_port()
    path = _settings_file(
        tmp_path,
        LauncherSettings(
            mode="remote",
            host="127.0.0.1",
            port=port,
            saves_dir=str(tmp_path / "saves"),
        ),
    )
    launcher = _launcher(path)
    try:
        started = json.loads(_read_line(launcher))
        key = load(path).settings.admin_key
        assert key is not None
        assert started["open_url"] == f"http://127.0.0.1:{port}/#admin={key}"
        request = urllib.request.Request(f"http://127.0.0.1:{port}/whoami")
        request.add_header("Cookie", f"dune_admin={key}")
        assert json.load(urllib.request.urlopen(request, timeout=5))["admin"] is True
        assert launcher.stdin is not None
        launcher.stdin.close()
        assert launcher.wait(timeout=20) == 0
    finally:
        if launcher.poll() is None:
            launcher.kill()
            launcher.wait(timeout=10)


def test_start_refuses_a_busy_port_before_starting(tmp_path: Path) -> None:
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port: int = taken.getsockname()[1]
        path = _settings_file(tmp_path, LauncherSettings(port=port))
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "dune_imperium.launcher.cli",
                "--start",
                "--settings",
                str(path),
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            check=False,
        )
    assert result.returncode == 1
    assert "[오류]" in result.stderr and str(port) in result.stderr
    assert result.stdout == ""
