"""Native prototype bootstrap boundaries: words, verified runtime, cleanup."""

import hashlib
import io
import json
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

import pytest

from dune_imperium.godot_client import launch
from dune_imperium.godot_client.ui_data import STATIC, build_ui_data, write_ui_data
from dune_imperium.launcher.command import LaunchPlan
from dune_imperium.launcher.supervisor import StartupFailed, Stopped
from dune_imperium.rules.engine import ACTION_HANDLERS


def _archive(path: Path, name: str = "Godot.exe") -> str:
    with zipfile.ZipFile(path, "w") as packed:
        packed.writestr(name, b"the verified runtime")
        packed.writestr("../unrelated.txt", b"must never be extracted")
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha512").hexdigest()


def test_native_words_cover_engine_actions_and_use_reviewed_terms() -> None:
    data = build_ui_data()
    assert set(ACTION_HANDLERS) <= set(data["ko"]["ACTION_LABELS"])
    assert data["terms"]["trash"]["ko"] == "폐기"
    assert data["terms"]["discard"]["ko"] == "버리기"
    assert data["ko"]["ACTION_LABELS"]["finish_agent_turn"]
    assert data["en"]["ACTION_LABELS"]["finish_agent_turn"]
    assert data["prompts"]["Choose an Agent turn or Reveal turn"]
    assert data["ko"]["AGENT_ICON_GROUPS"]["landsraad"] != "landsraad"
    assert data["ko"]["PAYLOAD_KEY_LABELS"]["count"] == "수"
    assert data["ko"]["PAYLOAD_KEY_LABELS"]["player"] == "플레이어"


def test_ui_data_is_unicode_json_and_written_only_to_requested_path(
    tmp_path: Path,
) -> None:
    target = tmp_path / "native" / "labels.json"
    write_ui_data(target)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["terms"]["water"]["ko"] == "물"
    assert "물" in target.read_text(encoding="utf-8")


def test_native_ui_uses_the_browser_preferences_and_localized_seat_kinds() -> None:
    data = build_ui_data()
    assert data["ui"]["clock.game_title"] == {
        "ko": "게임 시간", "en": "Game time",
    }
    assert data["ko"]["SEAT_KINDS"]["app_ai_easy"] == "앱 AI·쉬움"
    assert data["en"]["SEAT_KINDS"]["app_ai_easy"] == "App AI·Easy"
    assert data["ui"]["html.opt_tech"]["ko"]
    assert data["ui"]["html.opt_tech"]["en"]


def test_native_ui_rejects_an_incomplete_browser_translation(tmp_path: Path) -> None:
    for name in (
        "labels.js", "labels_en.js", "core.js", "prompts_ko.js", "ui_text.js",
    ):
        shutil.copyfile(STATIC / name, tmp_path / name)
    path = tmp_path / "ui_text.js"
    path.write_text(
        path.read_text(encoding="utf-8").replace(', "en": "Game time"', ""),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="incomplete UI translation"):
        build_ui_data(tmp_path)


def test_runtime_installer_extracts_only_the_verified_executable(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "runtime.zip"
    digest = _archive(archive)
    output = tmp_path / "cache"
    runtime = launch.install_archive(archive, output, "Godot.exe", digest)
    assert runtime.read_bytes() == b"the verified runtime"
    assert sorted(p.name for p in output.iterdir()) == ["Godot.exe"]
    assert not (tmp_path / "unrelated.txt").exists()


def test_bad_download_cannot_replace_an_existing_runtime(tmp_path: Path) -> None:
    archive = tmp_path / "runtime.zip"
    _archive(archive)
    output = tmp_path / "cache"
    output.mkdir()
    existing = output / "Godot.exe"
    existing.write_bytes(b"keep this runtime")
    with pytest.raises(ValueError, match="검증"):
        launch.install_archive(archive, output, "Godot.exe", "0" * 128)
    assert existing.read_bytes() == b"keep this runtime"
    assert not existing.with_suffix(".partial").exists()


def test_runtime_path_cannot_escape_its_cache(tmp_path: Path) -> None:
    archive = tmp_path / "runtime.zip"
    digest = _archive(archive)
    with pytest.raises(ValueError, match="one file name"):
        launch.install_archive(archive, tmp_path / "cache", "../Godot.exe", digest)


def test_windows_bootstrap_verifies_and_caches_the_official_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = tmp_path / "fixture.zip"
    digest = _archive(archive)
    raw = archive.read_bytes()
    monkeypatch.setattr(launch, "RUNTIME_DIR", tmp_path / "cache")
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(platform, "machine", lambda: "AMD64")
    monkeypatch.delenv("GODOT_EXECUTABLE", raising=False)
    monkeypatch.setitem(launch.RELEASES, "win32", ("runtime.zip", "Godot.exe", digest))
    fetched: list[str] = []

    def download(url: str, **kwargs: Any) -> io.BytesIO:
        fetched.append(url)
        return io.BytesIO(raw)

    monkeypatch.setattr(urllib.request, "urlopen", download)
    runtime = launch.ensure_godot()
    assert runtime.read_bytes() == b"the verified runtime"
    assert launch.ensure_godot() == runtime
    assert fetched == [launch.RELEASE_URL + "/runtime.zip"]
    assert not list(runtime.parent.glob("*.download"))
    assert not list(runtime.parent.glob("*.zip"))


def test_launch_arguments_keep_windows_paths_with_spaces_intact(
    tmp_path: Path,
) -> None:
    binary = tmp_path / "Godot with spaces.exe"
    labels = tmp_path / "path with spaces" / "labels.json"
    command = launch.godot_command(binary, "http://127.0.0.1:8123/", labels)
    assert command[0] == str(binary)
    assert command[command.index("--") + 1] == "--server=http://127.0.0.1:8123"
    assert command[-1] == f"--labels={labels}"


def test_main_checkout_assets_are_found_without_windows_symlinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    main = tmp_path / "main"
    assets = main / "assets"
    assets.mkdir(parents=True)
    worktree = tmp_path / "preview"
    worktree.mkdir()

    def git(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 0, str(main / ".git") + "\n", "")

    monkeypatch.setattr(subprocess, "run", git)
    assert launch.find_assets(worktree) == assets


def test_local_assets_take_precedence_over_main_checkout(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    assert launch.find_assets(tmp_path) == assets


def test_failed_server_start_is_stopped_before_the_launcher_returns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    binary = tmp_path / "Godot.exe"
    binary.touch()
    stopped: list[bool] = []

    class FailedServer:
        def __init__(self, plan: LaunchPlan, *, log_dir: Path) -> None:
            self.plan = plan

        def start(self) -> None:
            pass

        def wait_ready(self) -> None:
            raise StartupFailed("test startup failure", [], 1)

        def stop(self) -> Stopped:
            stopped.append(True)
            return Stopped("already", 0, 1, True)

    def imported(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess([], 0)

    monkeypatch.setattr(launch, "ServerProcess", FailedServer)
    monkeypatch.setattr(subprocess, "run", imported)
    monkeypatch.setattr(launch, "TMP_DIR", tmp_path)
    monkeypatch.setattr(launch, "free_port", lambda: 8123)
    assert launch.main(["--godot", str(binary), "--smoke"]) == 1
    assert stopped == [True]
