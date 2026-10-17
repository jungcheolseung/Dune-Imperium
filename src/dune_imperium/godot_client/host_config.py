"""Native host preferences; authentication never travels in command arguments."""

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dune_imperium.launcher.command import url_host
from dune_imperium.launcher.settings import LauncherSettings, new_admin_key


@dataclass(frozen=True)
class HostConfig:
    settings: LauncherSettings
    python: str | None = None
    key: str | None = field(default=None, repr=False)


def read_host_config(path: Path, *, assets: Path | None, local_port: int) -> HostConfig:
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    return parse_host_config(data, assets=assets, local_port=local_port)


def parse_host_config(
    data: object, *, assets: Path | None, local_port: int,
) -> HostConfig:
    """Validate the same preferences for a saved or live host request."""
    if not isinstance(data, dict) or not isinstance(data.get("host", {}), dict):
        raise ValueError("잘못된 Godot 서버 설정입니다.")
    host = data.get("host", {})
    mode = host.get("mode", "local")
    if mode not in ("local", "remote"):
        raise ValueError("서버 모드는 local 또는 remote여야 합니다.")
    port = host.get("port", 8000) if mode == "remote" else local_port
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("서버 포트는 1~65535여야 합니다.")
    bind = host.get("bind", "0.0.0.0")
    public = host.get("public_url") or None
    checkpoint = host.get("checkpoint") or None
    python = host.get("python") or None
    if not isinstance(bind, str) or not bind.strip():
        raise ValueError("서버 주소를 입력하세요.")
    if public is not None:
        if not isinstance(public, str):
            raise ValueError("방 링크 주소가 잘못되었습니다.")
        url = urlsplit(public)
        if (url.scheme not in ("http", "https") or not url.hostname
                or url.username or url.password or url.query or url.fragment
                or url.path not in ("", "/")):
            raise ValueError("방 링크에는 HTTP(S) 서버 주소만 입력하세요.")
    for value in (checkpoint, python):
        if value is not None and (
            not isinstance(value, str) or not Path(value).is_file()
        ):
            raise ValueError("설정한 서버 실행 파일 또는 학습 파일을 찾지 못했습니다.")
    pace = data.get("pace", "fast")
    if pace not in ("normal", "fast", "instant"):
        pace = "fast"
    settings = LauncherSettings(
        mode=mode, host=bind.strip(), port=port, public_url=public,
        search_checkpoint=checkpoint, ai_pace=pace,
        assets_dir=str(assets) if assets else None, autosave=True,
        open_browser=False,
    )
    return HostConfig(settings, python, new_admin_key() if mode == "remote" else None)


def server_origin(host: str, port: int) -> str:
    reach = {"0.0.0.0": "127.0.0.1", "::": "::1"}.get(host, host)
    return f"http://{url_host(reach)}:{port}"


def write_credentials(directory: Path, origin: str, key: str) -> Path:
    """One-use private file; the caller removes it even if the client fails."""
    descriptor, filename = tempfile.mkstemp(
        prefix="host-", suffix=".json", dir=directory
    )
    path = Path(filename)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"origin": origin, "key": key}, handle)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path
