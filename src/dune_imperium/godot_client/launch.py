"""Run the Godot prototype with its own server and clean up on window close."""

import argparse
import hashlib
import os
import platform
import shutil
import socket
import subprocess
import sys
import urllib.request
import zipfile
from collections.abc import Sequence
from pathlib import Path

from dune_imperium.godot_client.ui_data import write_ui_data
from dune_imperium.launcher.command import build_plan, no_window_flags
from dune_imperium.launcher.settings import LauncherSettings
from dune_imperium.launcher.supervisor import ServerProcess, StartupFailed
from dune_imperium.paths import PROJECT_ROOT, TMP_DIR

VERSION = "4.6.3"
PROJECT = Path(__file__).resolve().parent / "project"
RUNTIME_DIR = TMP_DIR / "godot" / "runtime"
RELEASE_URL = f"https://github.com/godotengine/godot-builds/releases/download/{VERSION}-stable"
# Official SHA512-SUMS.txt, checked 2026-10-13; see the prototype guide.
RELEASES = {
    "win32": (
        "Godot_v4.6.3-stable_win64.exe.zip", "Godot_v4.6.3-stable_win64.exe",
        "d44ea7ef5bab754cacd49d581b6062836b2eea12a82e1d183aebfad9cd8c7db2bd825"
        "13337bd657d6d2d5c04d46239c0570b029faf1343e81e8a2fa7b85dd83b",
    ),
    "linux": (
        "Godot_v4.6.3-stable_linux.x86_64.zip", "Godot_v4.6.3-stable_linux.x86_64",
        "a035258da32b77f966a5376f9fa29c30a6adde826a85ba918e1605bd1fc9823eba7d8"
        "5f1dd5e748956bd2ba72827c0025ffa11bb82aec91128c407a2e723c99c",
    ),
}


def install_archive(archive: Path, destination: Path, member: str, digest: str) -> Path:
    with archive.open("rb") as handle:
        actual = hashlib.file_digest(handle, "sha512").hexdigest()
    if actual != digest:
        raise ValueError("Godot 파일 검증에 실패했습니다. 파일을 실행하지 않습니다.")
    if Path(member).name != member:
        raise ValueError("runtime member must be one file name")
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / member
    temporary = target.with_suffix(".partial")
    try:
        with zipfile.ZipFile(archive) as packed:
            info = packed.getinfo(member)
            if info.file_size > 256 * 1024**2:
                raise ValueError("Godot 실행 파일이 예상 크기를 초과했습니다.")
            with packed.open(info) as source, temporary.open("wb") as output:
                shutil.copyfileobj(source, output)
        temporary.chmod(0o755)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def ensure_godot(explicit: str | None = None) -> Path:
    chosen = explicit or os.environ.get("GODOT_EXECUTABLE")
    if chosen:
        path = Path(chosen).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"Godot 실행 파일을 찾지 못했습니다: {path}")
        return path
    if (
        sys.platform not in RELEASES
        or platform.machine().lower() not in ("amd64", "x86_64")
    ):
        raise ValueError(
            "자동 준비는 Windows/Linux x64용입니다. "
            "--godot으로 실행 파일을 지정하세요."
        )
    archive_name, member, digest = RELEASES[sys.platform]
    runtime = RUNTIME_DIR / member
    if runtime.is_file():
        return runtime
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    archive = RUNTIME_DIR / archive_name
    download = archive.with_suffix(".download")
    print(f"첫 실행 준비: 공식 Godot {VERSION}를 내려받습니다…", flush=True)
    try:
        url = f"{RELEASE_URL}/{archive_name}"
        with urllib.request.urlopen(url, timeout=60) as source:
            with download.open("wb") as output:
                downloaded = 0
                while chunk := source.read(1024 * 1024):
                    downloaded += len(chunk)
                    if downloaded > 128 * 1024**2:
                        raise ValueError("Godot 다운로드가 예상 크기를 초과했습니다.")
                    output.write(chunk)
        download.replace(archive)
        return install_archive(archive, RUNTIME_DIR, member, digest)
    finally:
        download.unlink(missing_ok=True)
        archive.unlink(missing_ok=True)


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def find_assets(root: Path = PROJECT_ROOT) -> Path | None:
    """A worktree can read the main checkout's pictures without a symlink."""
    own = root / "assets"
    if own.is_dir():
        return own
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"], cwd=root,
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode == 0 and result.stdout.strip():
        common = (root / result.stdout.strip()).resolve()
        candidate = common.parent / "assets"
        if candidate.is_dir():
            return candidate
    return None


def godot_command(
    binary: Path, server: str, labels: Path, extra: Sequence[str] = ()
) -> list[str]:
    return [
        str(binary), "--path", str(PROJECT),
        "--log-file", str(TMP_DIR / "godot" / "client.log"),
        *extra, "--", f"--server={server.rstrip('/')}", f"--labels={labels}",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Godot 플레이 시제품")
    parser.add_argument(
        "--godot", help="설치된 Godot 실행 파일 (없으면 공식 버전을 자동 준비)"
    )
    parser.add_argument(
        "--server", help="이미 실행 중인 로컬 서버 주소 (이 서버는 종료하지 않음)"
    )
    parser.add_argument("--headless", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--smoke", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--capture", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    server: ServerProcess | None = None
    client: subprocess.Popen[bytes] | None = None
    log_dir = TMP_DIR / "godot"
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        binary = ensure_godot(args.godot)
        labels = log_dir / "ui_labels.json"
        write_ui_data(labels)
        with (log_dir / "import.log").open("wb") as log:
            imported = subprocess.run(
                [str(binary), "--headless", "--editor", "--path",
                 str(PROJECT), "--log-file", str(log_dir / "import-engine.log"),
                 "--import"],
                stdout=log, stderr=subprocess.STDOUT, timeout=120,
                creationflags=no_window_flags(),
            )
        if imported.returncode:
            message = f"Godot 첫 실행 준비가 실패했습니다. {log_dir / 'import.log'}"
            raise ValueError(message)
        base = args.server
        if base is None:
            assets = find_assets()
            settings = LauncherSettings(
                port=free_port(), ai_pace="fast", autosave=True,
                assets_dir=str(assets) if assets is not None else None,
                open_browser=False,
            )
            server = ServerProcess(
                build_plan(settings, None), log_dir=log_dir / "server"
            )
            server.start()
            server.wait_ready()
            base = server.plan.open_url.rstrip("/")
        extra = ["--headless"] if args.headless else []
        command = godot_command(binary, base, labels, extra)
        if args.smoke:
            command.append("--smoke")
        if args.capture:
            captures = Path(args.capture).resolve()
            if not captures.is_relative_to(PROJECT_ROOT):
                raise ValueError("스크린샷은 프로젝트 폴더 안에 저장해야 합니다.")
            captures.mkdir(parents=True, exist_ok=True)
            command.append(f"--capture={captures}")
        print("게임 창을 엽니다. 창을 닫으면 시제품 서버도 종료합니다.", flush=True)
        with (log_dir / "process.log").open("wb") as log:
            client = subprocess.Popen(
                command, cwd=PROJECT_ROOT, stdout=log, stderr=subprocess.STDOUT,
                creationflags=no_window_flags(),
            )
            return client.wait()
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, StartupFailed, subprocess.TimeoutExpired) as error:
        print(f"시제품을 시작하지 못했습니다: {error}", file=sys.stderr)
        return 1
    finally:
        if client is not None and client.poll() is None:
            client.terminate()
            try:
                client.wait(timeout=5)
            except subprocess.TimeoutExpired:
                client.kill()
                client.wait(timeout=5)
        if server is not None:
            stopped = server.stop()
            if not stopped.port_free:
                print(
                    "시제품 서버의 포트가 아직 열려 있습니다. 로그를 확인하세요.",
                    file=sys.stderr,
                )


if __name__ == "__main__":
    raise SystemExit(main())
