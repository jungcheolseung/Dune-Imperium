"""The server command and the checks before a start (plan 5.2, 5.7)."""

import os
import socket
import subprocess
import sys
from collections.abc import Sequence
from importlib.util import find_spec
from pathlib import Path
from typing import Any

import pytest

from dune_imperium.cli import server as server_cli
from dune_imperium.launcher import command
from dune_imperium.launcher.command import (
    ADMIN_KEY_ENVIRONMENT,
    ASSET_ENVIRONMENT,
    CREATE_NO_WINDOW,
    SYNC_TRAIN,
    SYNC_UI,
    LaunchPlan,
    build_plan,
    default_public_url,
    explain_failure,
    find_free_port,
    has_errors,
    no_window_flags,
    preflight,
    run_quiet,
    server_python,
)
from dune_imperium.launcher.settings import LauncherSettings
from dune_imperium.paths import PROJECT_ROOT
from dune_imperium.server.access import AccessMode

KEY = "k" * 32


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
        return port


def _parsed(plan: LaunchPlan) -> Any:
    return server_cli._build_parser().parse_args(list(plan.server_args))


def test_a_local_start_binds_this_machine_only() -> None:
    plan = build_plan(LauncherSettings(port=8123), None, python="py", environ={})
    assert plan.argv[:4] == ("py", "-u", "-m", "dune_imperium.cli.server")
    assert plan.host == "127.0.0.1" and not plan.remote
    assert "--remote" not in plan.server_args
    assert "--exit-when-stdin-closes" in plan.server_args
    assert plan.open_url == "http://127.0.0.1:8123/"
    assert ADMIN_KEY_ENVIRONMENT not in plan.env
    arguments = _parsed(plan)
    assert server_cli.resolve_access(arguments, plan.env) == (AccessMode.OPEN, None)


def test_a_remote_start_is_what_the_server_itself_accepts() -> None:
    settings = LauncherSettings(mode="remote", host="100.101.102.103", port=8001)
    plan = build_plan(settings, KEY, python="py", environ={})
    arguments = _parsed(plan)
    assert server_cli.resolve_access(arguments, plan.env) == (AccessMode.REMOTE, KEY)
    assert server_cli.resolve_public_url(arguments) == "http://100.101.102.103:8001"
    assert server_cli.resolve_autosave(arguments) is True
    assert arguments.exit_when_stdin_closes is True
    # The key travels in the environment: argv shows in ps and Task Manager.
    assert KEY not in " ".join(plan.argv)
    assert plan.open_url == server_cli.admin_link("100.101.102.103", 8001, KEY)
    assert plan.room_base == "http://100.101.102.103:8001"


def test_the_admin_key_variable_is_the_one_the_server_reads() -> None:
    assert ADMIN_KEY_ENVIRONMENT == server_cli.ADMIN_KEY_ENVIRONMENT


def test_no_autosave_and_a_chosen_room_link_base_reach_the_server() -> None:
    settings = LauncherSettings(
        mode="remote",
        host="0.0.0.0",
        public_url="http://192.168.0.5:8000/",
        autosave=False,
    )
    plan = build_plan(settings, KEY, python="py", environ={})
    arguments = _parsed(plan)
    assert server_cli.resolve_autosave(arguments) is False
    assert server_cli.resolve_public_url(arguments) == "http://192.168.0.5:8000"
    assert plan.connect_host == "127.0.0.1"
    assert plan.room_base == "http://192.168.0.5:8000"


def test_a_wildcard_bind_without_a_room_link_base_leaves_it_to_the_browser() -> None:
    plan = build_plan(
        LauncherSettings(mode="remote", host="0.0.0.0"), KEY, python="py", environ={}
    )
    assert "--public-url" not in plan.server_args
    assert default_public_url("0.0.0.0", 8000) is None
    assert default_public_url("fd7a::1", 8000) == "http://[fd7a::1]:8000"


def test_the_launchers_own_dune_variables_never_reach_the_server() -> None:
    # A launcher started from a terminal that had them set would otherwise
    # override what its settings say ("None" = the server's default).
    environ = {
        "DUNE_IMPERIUM_SEARCH_CHECKPOINT": "/elsewhere/net.pt",
        "DUNE_IMPERIUM_ADMIN_KEY": "old",
        "DUNE_IMPERIUM_CARD_IMAGE_DIR": "/elsewhere/cards",
        "PATH": "/usr/bin",
    }
    settings = LauncherSettings(mode="remote", host="127.0.0.1")
    plan = build_plan(settings, KEY, python="py", environ=environ)
    assert plan.env["PATH"] == "/usr/bin"
    assert plan.env[ADMIN_KEY_ENVIRONMENT] == KEY
    assert "DUNE_IMPERIUM_SEARCH_CHECKPOINT" not in plan.env
    assert "DUNE_IMPERIUM_CARD_IMAGE_DIR" not in plan.env
    assert plan.env["PYTHONUTF8"] == "1"


def test_an_assets_folder_sets_every_picture_the_server_looks_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("fastapi")
    from dune_imperium.server import app

    plan = build_plan(
        LauncherSettings(assets_dir=str(tmp_path)), None, python="py", environ={}
    )
    for name, _relative in ASSET_ENVIRONMENT:
        monkeypatch.setenv(name, plan.env[name])
    assert app.default_card_images_directory() == tmp_path / "cards"
    assert app.default_icons_directory() == tmp_path / "icons"
    assert app.default_tokens_directory() == tmp_path / "tokens"
    assert app.default_board_image_path() == tmp_path / "board" / "map.jpg"
    assert (
        app.default_bene_tleilax_image_path() == tmp_path / "board" / "bene_tleilax.jpg"
    )


def test_relative_folders_are_inside_the_checkout_and_networks_are_real_files(
    tmp_path: Path,
) -> None:
    network = tmp_path / "net-v1.pt"
    network.write_bytes(b"")
    link = tmp_path / "search.pt"
    link.symlink_to(network.name)
    settings = LauncherSettings(saves_dir="saves", search_checkpoint=str(link))
    arguments = _parsed(build_plan(settings, None, python="py", environ={}))
    assert arguments.saves_dir == PROJECT_ROOT / "saves"
    # Saves record the file a link named when the server started.
    assert arguments.search_checkpoint == str(network.resolve())


def test_a_windowless_windows_launcher_starts_the_console_python(
    tmp_path: Path,
) -> None:
    (tmp_path / "python.exe").write_bytes(b"")
    windowless = str(tmp_path / "pythonw.exe")
    assert server_python(windowless, "win32") == str(tmp_path / "python.exe")
    assert server_python(windowless, "darwin") == windowless
    assert server_python("/venv/bin/python", "win32") == "/venv/bin/python"


def test_no_child_gets_a_console_window_on_windows() -> None:
    assert no_window_flags("win32") == CREATE_NO_WINDOW == 0x08000000
    assert no_window_flags("darwin") == 0


def test_helper_programs_run_without_a_window_or_an_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The Tailscale CLI, PowerShell and the torch check all go through here.
    seen: dict[str, Any] = {}

    def fake_run(
        argv: Sequence[str], **options: Any
    ) -> subprocess.CompletedProcess[str]:
        seen.update(options)
        return subprocess.CompletedProcess(list(argv), 0, "out", "")

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "run", fake_run)
    result = run_quiet(["tailscale", "status"], 3.0, env={"TAILSCALE_BE_CLI": "1"})
    assert result is not None and result.stdout == "out"
    assert seen["creationflags"] == CREATE_NO_WINDOW
    assert seen["stdin"] == subprocess.DEVNULL
    assert seen["env"]["TAILSCALE_BE_CLI"] == "1"


def test_a_program_that_cannot_run_is_no_crash() -> None:
    assert run_quiet([str(PROJECT_ROOT / "no-such-program")], 3.0) is None


def test_a_free_port_is_found_from_the_one_asked_for() -> None:
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        busy: int = taken.getsockname()[1]
        found = find_free_port("127.0.0.1", busy, 5)
    assert found != busy and found > 0


# --- preflight -------------------------------------------------------------


def _check(settings: LauncherSettings, **options: Any) -> list[str]:
    plan = build_plan(settings, KEY if settings.mode == "remote" else None)
    problems = preflight(settings, plan, check_torch=False, **options)
    return [f"{p.level}: {p.text}" for p in problems]


def test_missing_server_packages_name_the_sync_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = find_spec
    monkeypatch.setattr(
        command, "find_spec", lambda name: None if name == "uvicorn" else real(name)
    )
    [first, *_rest] = _check(LauncherSettings(port=_free_port()))
    assert first.startswith("error:") and SYNC_UI in first and "uvicorn" in first


def test_a_remote_start_needs_an_address() -> None:
    lines = _check(LauncherSettings(mode="remote", host=""))
    assert any(
        line.startswith("error:") and "주소를 고르세요" in line for line in lines
    )


def test_a_remote_start_on_loopback_is_only_a_warning() -> None:
    # The server and the host guide allow it: only this PC can come in.
    lines = _check(LauncherSettings(mode="remote", host="127.0.0.1", port=_free_port()))
    assert not any(line.startswith("error:") for line in lines)
    assert any(line.startswith("warning:") and "이 PC에서만" in line for line in lines)


def test_a_busy_port_is_an_error_before_the_start() -> None:
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port: int = taken.getsockname()[1]
        lines = _check(LauncherSettings(port=port))
    assert any(line.startswith("error:") and str(port) in line for line in lines)


def test_an_address_this_machine_lacks_points_at_tailscale() -> None:
    # 192.0.2.0/24 is for documentation (RFC 5737): no interface has it,
    # which is what a Tailscale address looks like while Tailscale is off.
    lines = _check(LauncherSettings(mode="remote", host="192.0.2.1"))
    assert any(
        line.startswith("error:") and "192.0.2.1" in line and "Tailscale" in line
        for line in lines
    )


def test_a_file_in_place_of_the_saves_folder_is_an_error(tmp_path: Path) -> None:
    taken = tmp_path / "saves"
    taken.write_text("", encoding="utf-8")
    lines = _check(LauncherSettings(port=_free_port(), saves_dir=str(taken)))
    assert any(line.startswith("error:") and "저장 폴더" in line for line in lines)


def test_a_missing_pictures_folder_is_no_error(tmp_path: Path) -> None:
    lines = _check(
        LauncherSettings(port=_free_port(), assets_dir=str(tmp_path / "none"))
    )
    assert not any(line.startswith("error:") for line in lines)
    assert any("그림 없이" in line for line in lines)


def test_a_chosen_network_that_is_missing_switches_the_search_ai_off(
    tmp_path: Path,
) -> None:
    lines = _check(
        LauncherSettings(
            port=_free_port(), search_checkpoint=str(tmp_path / "missing.pt")
        )
    )
    assert any("탐색 AI 꺼짐" in line and "missing.pt" in line for line in lines)


def test_a_link_to_a_missing_network_says_where_it_points(tmp_path: Path) -> None:
    link = tmp_path / "search.pt"
    link.symlink_to("gone-v9.pt")
    lines = _check(LauncherSettings(port=_free_port(), search_checkpoint=str(link)))
    assert any("링크" in line and "gone-v9.pt" in line for line in lines)


def test_without_torch_the_search_ai_is_off_and_the_command_is_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    network = tmp_path / "net.pt"
    network.write_bytes(b"")
    real = find_spec
    monkeypatch.setattr(
        "dune_imperium.cli.server.find_spec",
        lambda name: None if name == "torch" else real(name),
    )
    lines = _check(LauncherSettings(port=_free_port(), search_checkpoint=str(network)))
    assert any("torch" in line and SYNC_TRAIN in line for line in lines)


def test_torch_that_does_not_import_is_a_warning(tmp_path: Path) -> None:
    # find_spec cannot see a broken DLL ([WinError 126]); the check imports
    # torch in a child, the way the server would.
    network = tmp_path / "net.pt"
    network.write_bytes(b"")
    settings = LauncherSettings(port=_free_port(), search_checkpoint=str(network))
    plan = build_plan(settings, None)
    calls: list[list[str]] = []

    def broken_torch(
        argv: Sequence[str], timeout: float
    ) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        return subprocess.CompletedProcess(
            list(argv), 1, "", "OSError: [WinError 126] fbgemm.dll\n"
        )

    if find_spec("torch") is None:
        pytest.skip("torch is not installed here")
    problems = preflight(settings, plan, check_torch=True, run=broken_torch)
    assert calls == [[plan.python, "-c", "import torch"]]
    assert any(p.level == "warning" and "WinError 126" in p.text for p in problems)
    assert not has_errors(problems)


# --- explain_failure -------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "words"),
    [
        (
            "dune-imperium-server: cannot listen on 100.1.2.3:8000: "
            "Can't assign requested address",
            ["100.1.2.3:8000", "Tailscale"],
        ),
        ("ERROR:    [Errno 48] error while attempting to bind", ["포트"]),
        ("OSError: [WinError 10048] Only one usage of each socket", ["포트"]),
        ("ModuleNotFoundError: No module named 'uvicorn'", ["uvicorn", SYNC_UI]),
        ("ImportError: DLL load failed while importing _C", ["Visual C++"]),
        (
            "dune-imperium-server: error: --public-url must start with http://",
            ["--public-url"],
        ),
    ],
)
def test_failures_are_explained_in_words(line: str, words: list[str]) -> None:
    message = explain_failure(["INFO: something earlier", line], 1)
    for word in words:
        assert word in message


def test_an_unknown_failure_points_at_the_log() -> None:
    assert "종료 코드 3" in explain_failure(["something odd"], 3)
    assert "로그" in explain_failure([], None)


def test_the_newest_cause_wins() -> None:
    message = explain_failure(
        ["No module named 'torch'", "cannot listen on 127.0.0.1:8000: in use"], 1
    )
    assert "127.0.0.1:8000" in message


def test_the_plan_runs_on_this_interpreter_by_default() -> None:
    plan = build_plan(LauncherSettings(), None, environ=os.environ)
    assert plan.python == server_python()
