"""Start the private Windows folder distribution with its bundled runtime."""

import ctypes
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from dune_imperium.godot_client import launch
from dune_imperium.paths import PROJECT_ROOT, TMP_DIR


def show_failure(log: Path) -> None:
    if sys.platform == "win32":
        ctypes.windll.user32.MessageBoxW(
            None,
            "게임을 시작하지 못했습니다.\n"
            "압축을 모두 풀었는지 확인해 주세요.\n\n"
            f"문제 기록: {log}",
            "듄 임페리움: 봉기", 0x10,
        )


def main() -> int:
    log = TMP_DIR / "godot" / "start.log"
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("w", encoding="utf-8", buffering=1) as output:
            with redirect_stdout(output), redirect_stderr(output):
                try:
                    binary = (
                        PROJECT_ROOT / "runtime" / "godot"
                        / launch.RELEASES["win32"][1]
                    )
                    if not binary.is_file():
                        raise ValueError("게임 실행 파일이 없습니다.")
                    # An explicit file means no download or development tools.
                    code = launch.main(["--godot", str(binary)])
                except Exception:
                    traceback.print_exc()
                    code = 1
    except OSError:
        code = 1
    if code:
        show_failure(log)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
