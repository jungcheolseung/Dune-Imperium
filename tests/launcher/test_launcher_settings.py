"""The launcher's settings file (docs/server-launcher-plan.md 5.4)."""

import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from dune_imperium.launcher.settings import (
    SETTINGS_FILE,
    LauncherSettings,
    Window,
    from_json,
    load,
    resolved_path,
    restore,
    save,
    snapshot,
    stored_path,
    with_admin_key,
)
from dune_imperium.paths import LOCAL_DIR, PROJECT_ROOT

KEY = "Abc-def_0123456789xyzXYZ"


def test_the_settings_live_in_an_ignored_folder_of_the_checkout() -> None:
    # User decision 2026-10-06: no project file outside the project. tmp/ is
    # for throwaway files and saves/ is listed as saves, so neither fits.
    assert LOCAL_DIR == PROJECT_ROOT / "local"
    assert SETTINGS_FILE == LOCAL_DIR / "launcher.json"
    ignored = subprocess.run(
        ["git", "check-ignore", "local/launcher.json"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ignored.stdout.split() == ["local/launcher.json"]


def test_a_missing_file_gives_the_defaults_quietly(tmp_path: Path) -> None:
    loaded = load(tmp_path / "launcher.json")
    assert loaded.settings == LauncherSettings()
    assert loaded.notes == ()


def test_settings_survive_a_save_and_a_load(tmp_path: Path) -> None:
    path = tmp_path / "local" / "launcher.json"
    settings = LauncherSettings(
        mode="remote",
        host="100.101.102.103",
        port=8001,
        public_url="http://100.101.102.103:8001",
        admin_key_mode="fixed",
        admin_key="k" * 32,
        saves_dir="saves",
        autosave=False,
        search_checkpoint="checkpoints/play/search.pt",
        ai_pace="fast",
        assets_dir="/somewhere/assets",
        keep_awake=False,
        open_browser=False,
        window=Window(10, 20, 700, 600),
        last_good={"mode": "remote", "host": "192.168.0.5", "port": 8000},
        last_error="포트가 이미 쓰이고 있습니다",
    )
    save(settings, path)
    loaded = load(path)
    assert loaded.notes == ()
    assert loaded.settings == settings


def test_keys_of_a_newer_launcher_are_kept(tmp_path: Path) -> None:
    path = tmp_path / "launcher.json"
    path.write_text(
        json.dumps({"version": 2, "port": 8002, "future_option": [1, 2]}),
        encoding="utf-8",
    )
    loaded = load(path)
    assert loaded.settings.port == 8002
    assert any("더 새 런처" in note for note in loaded.notes)
    save(loaded.settings, path)
    assert json.loads(path.read_text(encoding="utf-8"))["future_option"] == [1, 2]


def test_values_of_the_wrong_kind_fall_back_to_the_defaults() -> None:
    settings, notes = from_json(
        {
            "mode": "server",
            "port": "8000",
            "autosave": "yes",
            "ai_pace": "slow",
            "window": {"x": 1, "y": 2, "w": 0, "h": 5},
        }
    )
    assert settings == LauncherSettings()
    assert len(notes) == 4


def test_a_broken_file_is_moved_aside_not_lost(tmp_path: Path) -> None:
    path = tmp_path / "launcher.json"
    path.write_text("{not json", encoding="utf-8")
    loaded = load(path)
    assert loaded.settings == LauncherSettings()
    [aside] = list(tmp_path.glob("launcher.json.broken-*"))
    assert aside.read_text(encoding="utf-8") == "{not json"
    assert not path.exists()
    assert aside.name in loaded.notes[0]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_only_the_owner_can_read_the_file(tmp_path: Path) -> None:
    # It may hold the fixed admin key.
    path = tmp_path / "launcher.json"
    save(LauncherSettings(admin_key="secret"), path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_paths_inside_the_checkout_are_stored_relative(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    assert stored_path(root / "saves" / "x", root) == "saves/x"
    outside = tmp_path / "elsewhere"
    assert stored_path(outside, root) == str(outside)
    assert resolved_path("saves/x", root) == root / "saves" / "x"
    assert resolved_path(str(outside), root) == outside


def test_a_fixed_admin_key_is_minted_once_and_kept() -> None:
    first, key = with_admin_key(LauncherSettings(admin_key_mode="fixed"))
    assert first.admin_key == key and len(key) >= 32
    again, same = with_admin_key(first)
    assert same == key and again == first


def test_a_fresh_admin_key_is_never_stored() -> None:
    settings = LauncherSettings(admin_key_mode="fresh", admin_key="old")
    kept, key = with_admin_key(settings)
    assert kept.admin_key is None
    assert key != "old"
    assert with_admin_key(kept)[1] != key


def test_the_last_good_start_is_offered_back_without_the_key_or_window() -> None:
    good = LauncherSettings(
        mode="remote", host="192.168.0.5", port=8000, admin_key=KEY
    )
    taken = snapshot(good)
    assert "admin_key" not in taken and "window" not in taken
    later = LauncherSettings(
        mode="remote",
        host="100.1.2.3",
        port=8123,
        admin_key=KEY,
        window=Window(1, 2, 3, 4),
        last_good=taken,
        last_error="실패",
    )
    back = restore(later, taken)
    assert (back.host, back.port) == ("192.168.0.5", 8000)
    assert back.window == later.window and back.admin_key == KEY
    assert back.last_error is None and back.last_good == taken


def test_a_file_with_a_bom_is_read(tmp_path: Path) -> None:
    # Notepad writes one; moving the file aside would lose the fixed key.
    path = tmp_path / "launcher.json"
    path.write_bytes(
        b"\xef\xbb\xbf"
        + json.dumps({"mode": "remote", "admin_key": KEY}).encode("utf-8")
    )
    loaded = load(path)
    assert loaded.notes == ()
    assert loaded.settings.admin_key == KEY and loaded.settings.mode == "remote"
    assert path.exists()


def test_a_file_that_is_not_utf8_is_moved_aside(tmp_path: Path) -> None:
    path = tmp_path / "launcher.json"
    path.write_bytes('{"host": "집", "port": 8001}'.encode("cp949"))
    loaded = load(path)
    assert loaded.settings == LauncherSettings()
    assert not path.exists()
    assert len(list(tmp_path.glob("launcher.json.broken-*"))) == 1


def test_a_newer_format_number_is_kept_on_saving(tmp_path: Path) -> None:
    path = tmp_path / "launcher.json"
    path.write_text(json.dumps({"version": 2, "port": 8002}), encoding="utf-8")
    save(load(path).settings, path)
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 2


def test_a_malformed_admin_key_is_replaced() -> None:
    settings, notes = from_json({"admin_key": "has spaces in it, oops"})
    assert settings.admin_key is None and notes


def test_the_settings_do_not_show_the_admin_key() -> None:
    assert KEY not in repr(LauncherSettings(admin_key=KEY))


def test_the_ai_paces_are_the_servers() -> None:
    from dune_imperium.launcher import settings
    from dune_imperium.server.pacing import AI_PACES

    assert settings.AI_PACES == tuple(AI_PACES)
