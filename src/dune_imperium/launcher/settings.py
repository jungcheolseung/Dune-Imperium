"""The launcher's settings: one JSON file in the checkout's ``local/``.

docs/server-launcher-plan.md 5.4. The file outlives runs, unlike ``tmp/``,
and stays out of ``saves/``, whose ``*.json`` the server lists as saves.
Paths inside the checkout are stored relative to it, so a settings file
copied between a Mac and a Windows checkout still points at the same
folders; the keys that only make sense on one machine (the bind address,
the room-link base, the last good start, the window) are reset when they
do not fit the new one.
"""

import json
import os
import re
import secrets
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Final, Literal, cast

from dune_imperium.paths import LOCAL_DIR, PROJECT_ROOT

SETTINGS_FILE: Final = LOCAL_DIR / "launcher.json"
SETTINGS_VERSION: Final = 1
DEFAULT_PORT: Final = 8000
# The server's --ai-pace choices (dune_imperium.server.pacing.AI_PACES),
# repeated so that reading the settings imports no server code.
AI_PACES: Final = ("normal", "fast", "instant")

# What an admin key may hold: the server mints URL-safe tokens, and the key
# travels in a URL fragment and a cookie.
_ADMIN_KEY: Final = re.compile(r"[A-Za-z0-9_-]{16,}")

Mode = Literal["local", "remote"]
KeyMode = Literal["fixed", "fresh"]
_MODES: Final = ("local", "remote")
_KEY_MODES: Final = ("fixed", "fresh")


@dataclass(frozen=True)
class Window:
    """Where the launcher window was, to put it back there."""

    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class LauncherSettings:
    """What the host chose; ``None`` always means "the server's default"."""

    mode: Mode = "local"
    # The remote mode's bind address; the local mode always binds 127.0.0.1,
    # so switching modes keeps the remote choice.
    host: str = ""
    port: int = DEFAULT_PORT
    public_url: str | None = None
    admin_key_mode: KeyMode = "fixed"
    # Out of repr: a settings object in an error message must not show it.
    admin_key: str | None = field(default=None, repr=False)
    saves_dir: str | None = None
    autosave: bool = True
    search_checkpoint: str | None = None
    ai_pace: str = "normal"
    assets_dir: str | None = None
    keep_awake: bool = True
    open_browser: bool = True
    window: Window | None = None
    # The settings of the last start that came up, offered back with a
    # button after a failed start (never applied by itself).
    last_good: Mapping[str, object] | None = None
    last_error: str | None = None
    # Keys a newer launcher wrote; kept so that saving does not drop them.
    unknown: Mapping[str, object] = field(default_factory=dict)
    # The file's format: a newer launcher's number is kept on saving, so it
    # never reads its own data as an older format.
    version: int = SETTINGS_VERSION


@dataclass(frozen=True)
class Loaded:
    settings: LauncherSettings
    # Things the host should hear about the file itself, in Korean.
    notes: tuple[str, ...] = ()


def new_admin_key() -> str:
    """An admin key as unguessable as the server's own (``access.new_token``)."""

    return secrets.token_urlsafe(24)


def with_admin_key(settings: LauncherSettings) -> tuple[LauncherSettings, str]:
    """Return the settings to keep and the admin key for this start.

    A fixed key is minted once and then stored, so the admin link stays the
    same from one start to the next; a fresh key is never stored.
    """

    if settings.admin_key_mode == "fresh":
        return replace(settings, admin_key=None), new_admin_key()
    if settings.admin_key:
        return settings, settings.admin_key
    key = new_admin_key()
    return replace(settings, admin_key=key), key


def stored_path(path: Path, root: Path = PROJECT_ROOT) -> str:
    """Write a path the way the settings keep it: relative inside ``root``."""

    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def resolved_path(value: str, root: Path = PROJECT_ROOT) -> Path:
    """Read a stored path back: relative values are inside ``root``."""

    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


def to_json(settings: LauncherSettings) -> dict[str, object]:
    data: dict[str, object] = dict(settings.unknown)
    data.update(
        {
            "version": max(settings.version, SETTINGS_VERSION),
            "mode": settings.mode,
            "host": settings.host,
            "port": settings.port,
            "public_url": settings.public_url,
            "admin_key_mode": settings.admin_key_mode,
            "admin_key": settings.admin_key,
            "saves_dir": settings.saves_dir,
            "autosave": settings.autosave,
            "search_checkpoint": settings.search_checkpoint,
            "ai_pace": settings.ai_pace,
            "assets_dir": settings.assets_dir,
            "keep_awake": settings.keep_awake,
            "open_browser": settings.open_browser,
            "window": None
            if settings.window is None
            else {
                "x": settings.window.x,
                "y": settings.window.y,
                "w": settings.window.width,
                "h": settings.window.height,
            },
            "last_good": None
            if settings.last_good is None
            else dict(settings.last_good),
            "last_error": settings.last_error,
        }
    )
    return data


_KNOWN_KEYS: Final = frozenset(
    {
        "version",
        "mode",
        "host",
        "port",
        "public_url",
        "admin_key_mode",
        "admin_key",
        "saves_dir",
        "autosave",
        "search_checkpoint",
        "ai_pace",
        "assets_dir",
        "keep_awake",
        "open_browser",
        "window",
        "last_good",
        "last_error",
    }
)


def from_json(data: Mapping[str, object]) -> tuple[LauncherSettings, list[str]]:
    """Read settings, keeping the default for any value of the wrong kind.

    Returns the Korean notes on what was dropped, so a hand-edited file
    with a typo still opens and says what it ignored.
    """

    notes: list[str] = []
    defaults = LauncherSettings()

    def text(key: str, default: str) -> str:
        value = data.get(key, default)
        if isinstance(value, str):
            return value
        notes.append(f"설정 '{key}' 값을 읽지 못해 기본값을 씁니다")
        return default

    def optional_text(key: str) -> str | None:
        value = data.get(key)
        if value is None or isinstance(value, str):
            return value or None
        notes.append(f"설정 '{key}' 값을 읽지 못해 기본값을 씁니다")
        return None

    def flag(key: str, default: bool) -> bool:
        value = data.get(key, default)
        if isinstance(value, bool):
            return value
        notes.append(f"설정 '{key}' 값을 읽지 못해 기본값을 씁니다")
        return default

    def choice(key: str, allowed: tuple[str, ...], default: str) -> str:
        value = data.get(key, default)
        if isinstance(value, str) and value in allowed:
            return value
        notes.append(f"설정 '{key}' 값({value!r})을 몰라 기본값을 씁니다")
        return default

    port_value = data.get("port", DEFAULT_PORT)
    if (
        isinstance(port_value, int)
        and not isinstance(port_value, bool)
        and (1 <= port_value <= 65535)
    ):
        port = port_value
    else:
        notes.append(
            f"설정 'port' 값({port_value!r})이 포트 번호가 아니라 8000을 씁니다"
        )
        port = DEFAULT_PORT

    window: Window | None = None
    raw_window = data.get("window")
    if isinstance(raw_window, Mapping):
        numbers = [raw_window.get(key) for key in ("x", "y", "w", "h")]
        if all(isinstance(n, int) and not isinstance(n, bool) for n in numbers):
            x, y, width, height = cast(list[int], numbers)
            if width > 0 and height > 0:
                window = Window(x, y, width, height)

    admin_key = optional_text("admin_key")
    if admin_key is not None and not _ADMIN_KEY.fullmatch(admin_key):
        notes.append("설정의 관리자 키가 올바르지 않아 새 키를 만듭니다")
        admin_key = None

    raw_version = data.get("version", SETTINGS_VERSION)
    version = (
        raw_version
        if isinstance(raw_version, int) and not isinstance(raw_version, bool)
        else SETTINGS_VERSION
    )

    raw_last_good = data.get("last_good")
    last_good = (
        dict(cast(Mapping[str, object], raw_last_good))
        if isinstance(raw_last_good, Mapping)
        else None
    )

    settings = LauncherSettings(
        mode=cast(Mode, choice("mode", _MODES, defaults.mode)),
        host=text("host", defaults.host),
        port=port,
        public_url=optional_text("public_url"),
        admin_key_mode=cast(
            KeyMode, choice("admin_key_mode", _KEY_MODES, defaults.admin_key_mode)
        ),
        admin_key=admin_key,
        saves_dir=optional_text("saves_dir"),
        autosave=flag("autosave", defaults.autosave),
        search_checkpoint=optional_text("search_checkpoint"),
        ai_pace=choice("ai_pace", AI_PACES, defaults.ai_pace),
        assets_dir=optional_text("assets_dir"),
        keep_awake=flag("keep_awake", defaults.keep_awake),
        open_browser=flag("open_browser", defaults.open_browser),
        window=window,
        last_good=last_good,
        last_error=optional_text("last_error"),
        unknown={key: value for key, value in data.items() if key not in _KNOWN_KEYS},
        version=version,
    )
    return settings, notes


def load(path: Path = SETTINGS_FILE) -> Loaded:
    """Read the settings file; a missing one gives the defaults.

    A file that is not UTF-8 or not a JSON object is moved aside (never
    deleted) and the defaults are used, so a broken file cannot keep the
    launcher from opening.
    """

    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return Loaded(LauncherSettings())
    except OSError as error:
        return Loaded(
            LauncherSettings(),
            (f"설정 파일을 읽지 못해 기본값으로 시작합니다: {error}",),
        )
    try:
        # A BOM is allowed (Notepad writes one); saving drops it.
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        data = None
    if not isinstance(data, dict):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        aside = path.with_name(f"{path.name}.broken-{stamp}")
        try:
            os.replace(path, aside)
        except OSError:
            return Loaded(
                LauncherSettings(), ("설정 파일이 깨져 기본값으로 시작합니다",)
            )
        return Loaded(
            LauncherSettings(),
            (f"설정 파일이 깨져 {aside.name}(으)로 옮기고 기본값으로 시작합니다",),
        )
    version = data.get("version", SETTINGS_VERSION)
    settings, notes = from_json(cast(dict[str, object], data))
    if isinstance(version, int) and version > SETTINGS_VERSION:
        notes.insert(
            0,
            "더 새 런처가 쓴 설정 파일입니다: 아는 항목만 읽고 나머지는 그대로 둡니다",
        )
    return Loaded(settings, tuple(notes))


def save(settings: LauncherSettings, path: Path = SETTINGS_FILE) -> None:
    """Write the settings atomically; only the owner may read them.

    The file can hold the fixed admin key, so on POSIX it is created with
    mode 0600 (Windows keeps the inherited ACL of the user's checkout).
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(to_json(settings), ensure_ascii=False, indent=2) + "\n"
    # A scratch file of its own (mkstemp: mode 0600), so two saves at once
    # never write into the same one.
    descriptor, scratch_name = tempfile.mkstemp(
        prefix=f"{path.name}.", suffix=".tmp", dir=path.parent
    )
    scratch = Path(scratch_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        if sys.platform != "win32":
            os.chmod(scratch, 0o600)
        os.replace(scratch, path)
    except BaseException:
        scratch.unlink(missing_ok=True)
        raise


def snapshot(settings: LauncherSettings) -> dict[str, object]:
    """The part of the settings that ``last_good`` keeps: what a start used."""

    data = to_json(replace(settings, window=None, last_good=None, last_error=None))
    for key in ("version", "window", "last_good", "last_error", "admin_key"):
        data.pop(key, None)
    for key in settings.unknown:
        data.pop(key, None)
    return data


def restore(
    settings: LauncherSettings, last_good: Mapping[str, object]
) -> LauncherSettings:
    """The settings with ``last_good``'s start choices put back."""

    merged = to_json(settings)
    merged.update(last_good)
    restored, _notes = from_json(merged)
    return replace(restored, last_good=settings.last_good, last_error=None)
