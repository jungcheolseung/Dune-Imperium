"""Assemble a Windows x64 folder ZIP; building requires uv, playing does not."""

import argparse
import hashlib
import json
import shutil
import stat
import subprocess
import tempfile
import urllib.request
import zipfile
from importlib.metadata import distributions
from pathlib import Path, PurePosixPath

from dune_imperium.godot_client.launch import RELEASE_URL, RELEASES
from dune_imperium.paths import PROJECT_ROOT, TMP_DIR

PYTHON_VERSION = "3.14.7"
PYTHON_ARCHIVE = f"python-{PYTHON_VERSION}-embed-amd64.zip"
PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/{PYTHON_ARCHIVE}"
# https://www.python.org/downloads/release/python-3147/ (2026-10-14)
PYTHON_SHA256 = "d297e5ff019966817ad8502465176139f2d3d840fa4ed84b13bed399a6ab1f15"
GODOT_NOTICES = {
    "LICENSE.txt": "b0435e3b3e4e55238f05f4b306f30524a1b2e20147810d436eaa554fa6855c80",
    "COPYRIGHT.txt": "b3330849267d56ddd3d62a513817506606c2195034411fe05859f0140bff9d8a",
}
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".godot", "bin", "Scripts")
PYTHON_PATHS = "python314.zip\n.\nsite-packages\n../../src\nimport site\n"
# The embedded runtime ignores environment encoding overrides. Configure its
# redirected streams before either the launcher or its server prints Korean.
SITE_CUSTOMIZE = '''import sys
for stream in (sys.stdout, sys.stderr):
    if stream is not None and hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")
'''
START_COMMAND = '''@echo off
cd /d "%~dp0"
if not exist "runtime\\python\\pythonw.exe" (
  echo Extract the whole ZIP before starting the game.
  pause
  exit /b 1
)
start "" "%~dp0runtime\\python\\pythonw.exe" -m dune_imperium.godot_client.portable
'''
ASSET_DIRS = ("cards", "board", "icons", "tokens")
README = """듄 임페리움: 봉기 — Windows x64 시제품

1. ZIP 전체를 쓰기 가능한 폴더에 압축 해제합니다.
2. Play Dune.cmd를 더블클릭합니다.
3. 새 게임 → 게임 시작을 누릅니다. 지도자 공개 드래프트는 선택 사항입니다.

Python, uv, Git, Godot을 따로 설치할 필요가 없습니다.
첫 실행은 포함된 글꼴을 준비하므로 잠시 기다려 주세요. 인터넷 연결은 필요하지 않습니다.
게임 창을 닫으면 이 게임이 띄운 서버도 종료합니다.

손패 → 보드 칸 → 에이전트 배치, 남은 선택은 오른쪽에서 해결한 뒤 턴 종료.
왼쪽 플레이어 / 가운데 보드·손패 / 보드 옆 공용 카드 / 오른쪽 선택·기록.
카드·선택 버튼·카드가 있는 행동 기록에 마우스를 올리면 큰 그림과 설명이 뜹니다.
오른쪽 클릭으로 상세 보기, 공용 카드의 크게 버튼으로 카드 열을 비교합니다.
테이블에서 지도자 능력·교전 보상·목표·공개 카드 더미를 살펴봅니다.
저장 / 이어하기로 판을 이어갑니다. saves 폴더는 업데이트 때 보존하세요.

새 게임에서 기본판/웹 기본 옵션, 좌석 종류·AI 난이도·확장을 선택할 수 있습니다.
메뉴에서 원격 접속·관전/다시보기·언어·연출·효과음·서버 설정을 엽니다.
손패와 책략은 드래그로 정렬하고, 열 사이를 드래그하면 너비를 저장합니다.
승점을 누르면 승점 기록, 행동 기록을 누르면 이벤트 상세를 봅니다.
이 배포본의 기본 AI는 앱 AI이며 학습 런타임은 별도로 지정합니다.
이전 배포본의 Windows 시작·플레이는 사용자 확인을 받았습니다.
이번 화면 변경의 Windows 조작감과 전체 카드/지도자 조합은 추가 확인이 필요합니다.
그림을 포함한 개인용 묶음은 소유자의 컴퓨터 사이에서만 사용하세요.
공개로 공유하지 않습니다.

문제 기록: tmp/godot/start.log, process.log, client.log, import.log, server/
실행 안내: docs/godot-windows-package.md
구성/체크섬: package-manifest.json / licenses/
"""


def digest(path: Path, algorithm: str = "sha256") -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, algorithm).hexdigest()


def download(url: str, target: Path, expected: str, algorithm: str) -> Path:
    if target.is_file() and digest(target, algorithm) == expected:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".download")
    try:
        with urllib.request.urlopen(url, timeout=60) as source:
            with partial.open("wb") as output:
                size = 0
                while chunk := source.read(1024**2):
                    size += len(chunk)
                    if size > 128 * 1024**2:
                        raise ValueError("runtime download exceeds 128 MiB")
                    output.write(chunk)
        if digest(partial, algorithm) != expected:
            raise ValueError("runtime checksum mismatch")
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
    return target


def unpack(archive: Path, destination: Path, members: list[str] | None = None) -> None:
    with zipfile.ZipFile(archive) as packed:
        entries = (
            [packed.getinfo(name) for name in members]
            if members else packed.infolist()
        )
        if sum(entry.file_size for entry in entries) > 256 * 1024**2:
            raise ValueError("runtime expansion exceeds 256 MiB")
        for entry in entries:
            name = PurePosixPath(entry.filename)
            if (
                name.is_absolute() or ".." in name.parts
                or "\\" in entry.filename or ":" in entry.filename
                or stat.S_ISLNK(entry.external_attr >> 16)
            ):
                raise ValueError("unsafe runtime archive path")
        packed.extractall(destination, members=[entry.filename for entry in entries])


def check_windows_dependencies(packages: Path) -> dict[str, str]:
    versions = {
        str(item.metadata["Name"]): item.version
        for item in distributions(path=[str(packages)])
    }
    required = {"fastapi", "uvicorn", "pydantic", "pydantic_core"}
    normalized = {name.lower().replace("-", "_") for name in versions}
    if not {name.replace("-", "_") for name in required} <= normalized:
        raise ValueError("missing server dependencies")
    if any(name in normalized for name in ("torch", "pip", "pytest", "numpy")):
        raise ValueError("development or training package in runtime")
    native = list(packages.rglob("*.pyd"))
    if not native or list(packages.rglob("*.so")):
        raise ValueError("not a Windows binary dependency set")
    for path in native:
        if "cp314-win_amd64" not in path.name:
            raise ValueError(f"wrong Python/Windows architecture: {path.name}")
    return versions


def assemble(
    destination: Path, python: Path, godot: Path, packages: Path,
    licenses: Path, *, source: Path = PROJECT_ROOT, assets: Path | None = None,
) -> None:
    if destination.exists():
        raise ValueError("output already exists; keep existing games and saves")
    if digest(python) != PYTHON_SHA256:
        raise ValueError("embedded Python checksum mismatch")
    godot_name, godot_exe, godot_hash = RELEASES["win32"]
    if digest(godot, "sha512") != godot_hash:
        raise ValueError("Godot checksum mismatch")
    versions = check_windows_dependencies(packages)
    destination.mkdir(parents=True)
    runtime = destination / "runtime" / "python"
    unpack(python, runtime)
    unpack(godot, destination / "runtime" / "godot", [godot_exe])
    shutil.copytree(packages, runtime / "site-packages", ignore=IGNORE)
    (runtime / "python314._pth").write_text(PYTHON_PATHS, encoding="utf-8")
    (runtime / "sitecustomize.py").write_text(SITE_CUSTOMIZE, encoding="utf-8")
    shutil.copytree(
        source / "src" / "dune_imperium",
        destination / "src" / "dune_imperium", ignore=IGNORE,
    )
    (destination / "licenses").mkdir()
    for name in ("godot-LICENSE.txt", "godot-COPYRIGHT.txt"):
        if digest(licenses / name) != GODOT_NOTICES[name.removeprefix("godot-")]:
            raise ValueError("Godot license notice checksum mismatch")
        shutil.copyfile(licenses / name, destination / "licenses" / name)
    docs = destination / "docs"
    docs.mkdir()
    for name in (
        "godot-prototype-guide.md", "local-images.md", "godot-windows-package.md",
        "godot-feature-parity.md",
    ):
        shutil.copyfile(source / "docs" / name, docs / name)
    # These empty folders prevent invoking Git and keep all user data local.
    for folder in ("assets", "saves", "tmp/godot", "local"):
        (destination / folder).mkdir(parents=True, exist_ok=True)
    if assets is not None:
        for name in ASSET_DIRS:
            shutil.copytree(assets / name, destination / "assets" / name)
        shutil.copyfile(assets / "README.md", destination / "assets" / "README.md")
    (destination / "Play Dune.cmd").write_bytes(
        START_COMMAND.replace("\n", "\r\n").encode("ascii")
    )
    (destination / "먼저 읽어주세요.txt").write_text(README, encoding="utf-8-sig")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=source, capture_output=True,
        text=True, check=True,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=source, capture_output=True,
        text=True, check=True,
    ).stdout.strip()
    manifest = {
        "source_commit": commit, "source_tree_dirty": bool(dirty),
        "platform": "Windows x64",
        "python": PYTHON_VERSION, "godot": "4.6.3", "dependencies": versions,
        "personal_images": assets is not None,
        "runtime_archives": {PYTHON_ARCHIVE: PYTHON_SHA256, godot_name: godot_hash},
        "files": {
            str(path.relative_to(destination)).replace("\\", "/"): digest(path)
            for path in sorted(destination.rglob("*")) if path.is_file()
        },
    }
    (destination / "package-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--personal-assets", type=Path,
        help="Owner-only private images; excluded from the default build",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(PROJECT_ROOT) or output.exists():
        parser.error("choose a new output ZIP path inside this project")
    cache = TMP_DIR / "godot" / "portable-build-cache"
    cache.mkdir(parents=True, exist_ok=True)
    requirements = cache / "ui-requirements.txt"
    subprocess.run(
        ["uv", "export", "--locked", "--no-dev", "--extra", "ui",
         "--no-emit-project", "--no-header", "--no-annotate",
         "--output-file", str(requirements)],
        cwd=PROJECT_ROOT, check=True, stdout=subprocess.DEVNULL,
    )
    packages = cache / "windows-packages"
    subprocess.run(
        ["uv", "pip", "install", "--python-platform", "x86_64-pc-windows-msvc",
         "--python-version", "3.14", "--target", str(packages),
         "--no-build", "--no-deps", "--exact", "--require-hashes",
         "-r", str(requirements)],
        cwd=PROJECT_ROOT, check=True,
    )
    python = download(PYTHON_URL, cache / PYTHON_ARCHIVE, PYTHON_SHA256, "sha256")
    archive, _, sha512 = RELEASES["win32"]
    godot = download(f"{RELEASE_URL}/{archive}", cache / archive, sha512, "sha512")
    # Godot's MIT and bundled-library notices are downloaded from its exact tag.
    for name, checksum in GODOT_NOTICES.items():
        target = cache / ("godot-" + name)
        url = f"https://raw.githubusercontent.com/godotengine/godot/4.6.3-stable/{name}"
        download(url, target, checksum, "sha256")
    with tempfile.TemporaryDirectory(prefix="portable-", dir=cache) as scratch:
        folder = Path(scratch) / "Dune-Uprising-Prototype"
        assemble(folder, python, godot, packages, cache, assets=args.personal_assets)
        output.parent.mkdir(parents=True, exist_ok=True)
        partial = output.with_suffix(".partial")
        try:
            with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as packed:
                for path in sorted(folder.rglob("*")):
                    if path.is_file() or path.is_dir():
                        packed.write(path, path.relative_to(folder.parent))
            with zipfile.ZipFile(partial) as packed:
                if packed.testzip() is not None:
                    raise ValueError("output ZIP verification failed")
            partial.replace(output)
        finally:
            partial.unlink(missing_ok=True)
        print(f"ZIP: {output}\nDownload: {output.stat().st_size / 1024**2:.1f} MiB")
        size = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())
        print(f"Extracted: {size / 1024**2:.1f} MiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
