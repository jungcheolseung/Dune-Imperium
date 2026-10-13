"""Run the native model checks and a real-server turn (Godot is optional)."""

import argparse
import os
import subprocess
import sys

from dune_imperium.godot_client.launch import PROJECT, ensure_godot
from dune_imperium.paths import PROJECT_ROOT, TMP_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--godot", help="Godot executable; otherwise prepare the pinned runtime"
    )
    parser.add_argument(
        "--capture", action="store_true",
        help="Also verify clicks and capture on a display",
    )
    args = parser.parse_args()
    binary = ensure_godot(args.godot)
    env = dict(os.environ, PYTHONPATH=str(PROJECT_ROOT / "src"))
    checked = subprocess.run(
        [str(binary), "--headless", "--path", str(PROJECT),
         "--script", "model_test.gd"],
        cwd=PROJECT_ROOT, env=env, timeout=30, check=False,
    )
    if checked.returncode:
        return checked.returncode
    command = [
        sys.executable, "-m", "dune_imperium.godot_client.launch",
        "--godot", str(binary),
    ]
    if args.capture:
        command += ["--capture", str(TMP_DIR / "godot" / "screenshots")]
        marker = "GODOT_CAPTURE_OK"
    else:
        command += ["--headless", "--smoke"]
        marker = "GODOT_SMOKE_OK"
    checked = subprocess.run(
        command, cwd=PROJECT_ROOT, env=env, timeout=120, check=False
    )
    if checked.returncode:
        return checked.returncode
    log = (TMP_DIR / "godot" / "process.log").read_text(encoding="utf-8")
    if marker not in log or "SCRIPT ERROR" in log or "ERROR:" in log:
        print(log, file=sys.stderr)
        return 1
    print("Native prototype verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
