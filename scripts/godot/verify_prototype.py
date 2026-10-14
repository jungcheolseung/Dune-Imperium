"""Verify native controls with a real-server turn or complete basic games."""

import argparse
import json
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
    parser.add_argument(
        "--full-game", action="store_true",
        help="Complete four games through native action/finish/save/load controls",
    )
    parser.add_argument(
        "--seeds", default="11,22,33,44", help="Bounded playthrough seeds"
    )
    args = parser.parse_args()
    seeds = args.seeds.split(",")
    if not 1 <= len(seeds) <= 8 or not all(seed.isdecimal() for seed in seeds):
        parser.error("--seeds requires one to eight nonnegative integers")
    binary = ensure_godot(args.godot)
    env = dict(os.environ, PYTHONPATH=str(PROJECT_ROOT / "src"))
    checked = subprocess.run(
        [str(binary), "--headless", "--path", str(PROJECT),
         "--script", "model_test.gd"],
        cwd=PROJECT_ROOT, env=env, timeout=30, check=False,
    )
    if checked.returncode:
        return checked.returncode
    # Fail promptly on native script errors instead of waiting for a UI watchdog
    # that cannot start when the main scene does not parse.
    for script in ("board.gd", "main.gd"):
        checked = subprocess.run(
            [str(binary), "--headless", "--path", str(PROJECT),
             "--script", script, "--check-only"],
            cwd=PROJECT_ROOT, env=env, timeout=30, check=False,
        )
        if checked.returncode:
            return checked.returncode
    command = [
        sys.executable, "-m", "dune_imperium.godot_client.launch",
        "--godot", str(binary),
    ]
    if args.full_game:
        command += ["--playthrough", args.seeds]
        if args.capture:
            command += ["--capture", str(TMP_DIR / "godot" / "screenshots")]
        else:
            command += ["--headless"]
        marker = "GODOT_PLAYTHROUGH_OK"
    elif args.capture:
        command += ["--capture", str(TMP_DIR / "godot" / "screenshots")]
        marker = "GODOT_CAPTURE_OK"
    else:
        command += ["--headless", "--smoke"]
        marker = "GODOT_SMOKE_OK"
    checked = subprocess.run(
        command, cwd=PROJECT_ROOT, env=env,
        timeout=630 if args.full_game else 120, check=False,
    )
    if checked.returncode:
        return checked.returncode
    log = (TMP_DIR / "godot" / "process.log").read_text(encoding="utf-8")
    if marker not in log or "SCRIPT ERROR" in log or "ERROR:" in log:
        print(log, file=sys.stderr)
        return 1
    if args.full_game:
        payload = log.split(marker + " ", 1)[1].splitlines()[0]
        report = json.loads(payload)
        (TMP_DIR / "godot" / "playthrough-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Completed {len(report['games'])} native games; report in tmp/godot.")
    print("Native prototype verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
