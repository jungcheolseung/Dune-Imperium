"""Native hosting reuses the server contract without exposing launch keys."""

import json
import stat
from pathlib import Path

import pytest

from dune_imperium.godot_client.host_config import (
    read_host_config,
    server_origin,
    write_credentials,
)
from dune_imperium.godot_client.launch import godot_command
from dune_imperium.launcher.command import build_plan


def test_absent_preferences_start_a_local_self_contained_game(tmp_path: Path) -> None:
    config = read_host_config(tmp_path / "absent", assets=tmp_path, local_port=9123)
    plan = build_plan(config.settings, config.key, environ={})
    assert not plan.remote and plan.host == "127.0.0.1" and plan.port == 9123
    assert config.key is None and plan.python
    assert "--search-checkpoint" not in plan.argv
    assert plan.env["DUNE_IMPERIUM_CARD_IMAGE_DIR"] == str(tmp_path / "cards")


def test_remote_host_uses_share_address_and_one_use_authentication(
    tmp_path: Path,
) -> None:
    prefs = tmp_path / "prefs.json"
    prefs.write_text(json.dumps({"host": {
        "mode": "remote", "bind": "0.0.0.0", "port": 8123,
        "public_url": "https://dune.example", "checkpoint": "", "python": "",
    }}))
    config = read_host_config(prefs, assets=None, local_port=9234)
    plan = build_plan(config.settings, config.key, environ={})
    assert plan.remote and plan.room_base == "https://dune.example"
    assert config.key
    assert config.key not in repr(config) and config.key not in repr(plan)
    origin = server_origin(plan.host, plan.port)
    assert origin == "http://127.0.0.1:8123"
    credential = write_credentials(tmp_path, origin, config.key)
    assert json.loads(credential.read_text()) == {"origin": origin, "key": config.key}
    assert stat.S_IMODE(credential.stat().st_mode) == 0o600
    args = godot_command(tmp_path / "Godot", origin, tmp_path / "labels.json")
    args.append(f"--host-credentials={credential}")
    assert not any(config.key in argument for argument in args)
    assert not any("#admin=" in argument for argument in args)
    credential.unlink()
    assert not credential.exists()
    assert read_host_config(prefs, assets=None, local_port=9234).key != config.key


@pytest.mark.parametrize("host", [
    {"mode": "bad"}, {"mode": "remote", "port": True},
    {"mode": "remote", "port": 65536}, {"mode": "remote", "bind": ""},
    {"public_url": "https://user:secret@example.com"},
    {"public_url": "https://example.com/#admin=secret"},
    {"public_url": "https://example.com/path"},
    {"checkpoint": "/missing-checkpoint.pt"}, {"python": "/missing-python"},
])
def test_invalid_host_settings_fail_before_starting_a_server(
    tmp_path: Path, host: dict[str, object],
) -> None:
    prefs = tmp_path / "prefs.json"
    prefs.write_text(json.dumps({"host": host}))
    with pytest.raises(ValueError):
        read_host_config(prefs, assets=None, local_port=9123)


def test_configured_search_runtime_is_passed_to_the_owned_server(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "current-model.pt"
    python = tmp_path / "trained-python.exe"
    checkpoint.touch()
    python.touch()
    prefs = tmp_path / "prefs.json"
    prefs.write_text(json.dumps({"host": {
        "checkpoint": str(checkpoint), "python": str(python),
    }}))
    config = read_host_config(prefs, assets=None, local_port=9123)
    plan = build_plan(config.settings, config.key, python=config.python, environ={})
    assert plan.python == str(python)
    assert str(checkpoint) in plan.argv and "--search-checkpoint" in plan.argv
    assert server_origin("::", 9123) == "http://[::1]:9123"
