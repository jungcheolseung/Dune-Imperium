"""Standalone package boundaries: local runtime, isolation, data and notices."""

import io
import json
import os
import stat
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

import pytest

from dune_imperium.godot_client import launch, portable
from dune_imperium.godot_client import package_windows as package


@pytest.mark.parametrize("name", ["../outside", "/outside", "a\\outside", "C:bad"])
def test_runtime_archive_cannot_write_outside_its_folder(
    tmp_path: Path, name: str,
) -> None:
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as packed:
        packed.writestr(name, "must not write")
    with pytest.raises(ValueError, match="unsafe"):
        package.unpack(archive, tmp_path / "runtime")
    assert not (tmp_path / "outside").exists()


def test_runtime_archive_rejects_symlinks(tmp_path: Path) -> None:
    archive = tmp_path / "link.zip"
    entry = zipfile.ZipInfo("link")
    entry.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as packed:
        packed.writestr(entry, "outside")
    with pytest.raises(ValueError, match="unsafe"):
        package.unpack(archive, tmp_path / "runtime")


def test_bad_download_preserves_cached_runtime_and_removes_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "runtime.zip"
    target.write_bytes(b"existing")
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *args, **kwargs: io.BytesIO(b"wrong")
    )
    with pytest.raises(ValueError, match="checksum"):
        package.download("https://example.invalid", target, "0" * 64, "sha256")
    assert target.read_bytes() == b"existing"
    assert not target.with_suffix(".download").exists()


def test_packaging_never_overwrites_an_existing_game(tmp_path: Path) -> None:
    game = tmp_path / "game"
    game.mkdir()
    saved = game / "save.json"
    saved.write_text("keep my game")
    with pytest.raises(ValueError, match="already exists"):
        package.assemble(game, tmp_path, tmp_path, tmp_path, tmp_path)
    assert saved.read_text() == "keep my game"


def test_embedded_stream_setup_handles_korean_with_ascii_parent() -> None:
    result = subprocess.run(
        [sys.executable, "-c", package.SITE_CUSTOMIZE + '\nprint("봉기 저장")'],
        env=dict(os.environ, PYTHONIOENCODING="ascii"),
        capture_output=True, check=True,
    )
    assert result.stdout.decode("utf-8").strip() == "봉기 저장"


def test_window_launcher_uses_bundled_godot_and_logs_without_a_console(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    binary = tmp_path / "runtime" / "godot" / launch.RELEASES["win32"][1]
    binary.parent.mkdir(parents=True)
    binary.touch()
    monkeypatch.setattr(portable, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(portable, "TMP_DIR", tmp_path / "tmp")
    received: list[list[str]] = []

    def start(args: list[str]) -> int:
        received.append(args)
        print("게임 창 준비")
        return 0

    monkeypatch.setattr(launch, "main", start)
    assert portable.main() == 0
    assert received == [["--godot", str(binary)]]
    assert "게임 창 준비" in (tmp_path / "tmp/godot/start.log").read_text()


def test_missing_packaged_runtime_reports_error_without_downloading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(portable, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(portable, "TMP_DIR", tmp_path / "tmp")
    reported: list[Path] = []
    monkeypatch.setattr(portable, "show_failure", reported.append)
    monkeypatch.setattr(
        launch, "main",
        lambda args: pytest.fail("must not start/download an absent runtime"),
    )
    assert portable.main() == 1
    assert reported == [tmp_path / "tmp/godot/start.log"]
    assert "실행 파일이 없습니다" in reported[0].read_text()


def _dependencies(root: Path) -> None:
    for name in ("fastapi", "uvicorn", "pydantic", "pydantic_core"):
        metadata = root / f"{name}-1.0.dist-info" / "METADATA"
        metadata.parent.mkdir(parents=True)
        metadata.write_text(f"Name: {name}\nVersion: 1.0\n")
    native = root / "pydantic_core" / "_pydantic_core.cp314-win_amd64.pyd"
    native.parent.mkdir()
    native.touch()


def test_runtime_dependencies_reject_linux_and_training_extras(tmp_path: Path) -> None:
    _dependencies(tmp_path)
    assert "fastapi" in package.check_windows_dependencies(tmp_path)
    wrong = tmp_path / "pydantic_core" / "native.so"
    wrong.touch()
    with pytest.raises(ValueError, match="Windows binary"):
        package.check_windows_dependencies(tmp_path)
    wrong.unlink()
    metadata_stat = tmp_path.stat()
    metadata = tmp_path / "torch-1.0.dist-info" / "METADATA"
    metadata.parent.mkdir()
    metadata.write_text("Name: torch\nVersion: 1.0\n")
    # Reproduce filesystems whose timestamp does not change during an install.
    os.utime(tmp_path, ns=(metadata_stat.st_atime_ns, metadata_stat.st_mtime_ns))
    with pytest.raises(ValueError, match="training"):
        package.check_windows_dependencies(tmp_path)


@pytest.mark.parametrize("personal_images", [False, True])
def test_package_contains_source_data_not_user_state_and_is_relocatable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, personal_images: bool,
) -> None:
    source = tmp_path / "source"
    module = source / "src/dune_imperium"
    module.mkdir(parents=True)
    (module / "paths.py").write_text(
        "from pathlib import Path\n"
        "PROJECT_ROOT=Path(__file__).resolve().parents[2]\n"
    )
    data = module / "server/static/labels.js"
    data.parent.mkdir(parents=True)
    data.write_text("shared labels")
    generated = module / "godot_client/project/.godot"
    generated.mkdir(parents=True)
    (generated / "machine-cache").touch()
    (source / "saves").mkdir()
    (source / "saves/secret.json").write_text("private hand order")
    (source / "docs").mkdir()
    for name in (
        "godot-prototype-guide.md", "local-images.md", "godot-windows-package.md",
        "godot-feature-parity.md",
    ):
        (source / "docs" / name).write_text("instructions")
    archives = []
    for filename, member in (("python.zip", "python.exe"), ("godot.zip", "Godot.exe")):
        archive = tmp_path / filename
        with zipfile.ZipFile(archive, "w") as packed:
            packed.writestr(member, "runtime")
        archives.append(archive)
    monkeypatch.setattr(package, "PYTHON_SHA256", package.digest(archives[0]))
    monkeypatch.setitem(
        launch.RELEASES, "win32",
        ("godot.zip", "Godot.exe", package.digest(archives[1], "sha512")),
    )
    deps = tmp_path / "deps"
    deps.mkdir()
    _dependencies(deps)
    for name in package.GODOT_NOTICES:
        path = tmp_path / ("godot-" + name)
        path.write_text("license notice")
        monkeypatch.setitem(package.GODOT_NOTICES, name, package.digest(path))
    monkeypatch.setattr(
        subprocess, "run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "abc123\n", ""),
    )
    destination = tmp_path / "한글 경로 game"
    assets = tmp_path / "private-assets"
    assets.mkdir()
    for name in package.ASSET_DIRS:
        (assets / name).mkdir()
        (assets / name / "picture.png").write_text("personal picture")
    (assets / "README.md").write_text("owner-only")
    (assets / "rulebooks").mkdir()
    (assets / "rulebooks/private.pdf").write_text("do not read or package")
    package.assemble(
        destination, archives[0], archives[1], deps, tmp_path, source=source,
        assets=assets if personal_images else None,
    )
    assert (
        destination / "src/dune_imperium/server/static/labels.js"
    ).read_text() == "shared labels"
    assert not list((destination / "saves").iterdir())
    assert not (destination / "src/dune_imperium/godot_client/project/.godot").exists()
    paths = (destination / "runtime/python/python314._pth").read_text().splitlines()
    assert (destination / "runtime/python" / paths[3]).resolve() == destination / "src"
    command = (destination / "Play Dune.cmd").read_bytes()
    assert b"\r\n" in command and b"%~dp0runtime\\python\\pythonw.exe" in command
    assert b"uv " not in command and b"git " not in command
    manifest = json.loads((destination / "package-manifest.json").read_text())
    assert manifest["personal_images"] == personal_images
    assert not (destination / "assets/rulebooks").exists()
    assert (destination / "assets/cards/picture.png").exists() == personal_images
    assert manifest["files"][
        "src/dune_imperium/server/static/labels.js"
    ] == package.digest(data)
