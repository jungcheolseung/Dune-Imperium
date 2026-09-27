"""Run the browser E2E scripts several at a time (see README.md in this folder).

Every script already starts its own play server on a free port with its own
saves directory and its own headless Chrome, so the scripts share no state.
This runner only schedules them (longest first), keeps each one's output in a
log file and prints one line per script as it finishes.

    /tmp/dune-e2e-venv/bin/python run_all.py              # every script, 4 at a time
    /tmp/dune-e2e-venv/bin/python run_all.py -j 6
    /tmp/dune-e2e-venv/bin/python run_all.py lang narrow  # only these
    /tmp/dune-e2e-venv/bin/python run_all.py --list

`rehearsal.py` needs a Tailscale address (E2E_HOST) and runs only when named.
A failure is never retried here: a check that fails only under load is a
timing assumption in that check, and it should be seen.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
NOT_SCRIPTS = {"common", "run_all"}
ONLY_WHEN_NAMED = {"rehearsal"}
ARGS = {"races": ["--ab"]}
# Seconds each script took alone (-j 1, Mac mini, 2026-09-27; 230 s in all).
# Only the order uses them, so a new script without an entry just runs last.
SECONDS = {
    "leader_card": 30,
    "races": 26,
    "open_mode": 25,
    "spectate": 16,
    "turn_end": 15,
    "remote_fresh": 14,
    "recovery": 14,
    "save_delete": 11,
    "staged_turn": 8,
    "trash_zone": 7,
    "remote": 6,
    "narrow": 6,
    "log_passes": 6,
    "log_words": 5,
}


def discover() -> list[str]:
    return sorted(
        path.stem
        for path in HERE.glob("*.py")
        if path.stem not in NOT_SCRIPTS and path.stem not in ONLY_WHEN_NAMED
    )


def run_one(name: str, logs: Path, timeout: float) -> tuple[str, int | None, float]:
    log_path = logs / f"{name}.log"
    started = time.monotonic()
    with open(log_path, "w") as log:
        process = subprocess.Popen(
            [sys.executable, "-u", str(HERE / f"{name}.py"), *ARGS.get(name, [])],
            cwd=HERE,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            code: int | None = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            code = None
    return name, code, time.monotonic() - started


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("names", nargs="*", help="script names (default: all)")
    parser.add_argument("-j", "--jobs", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=600, help="seconds per script")
    parser.add_argument("--list", action="store_true")
    options = parser.parse_args()

    names = [name.removesuffix(".py") for name in options.names] or discover()
    missing = [name for name in names if not (HERE / f"{name}.py").exists()]
    if missing:
        parser.error(f"no such script: {', '.join(missing)}")
    names.sort(key=lambda name: -SECONDS.get(name, 0))
    if options.list:
        print("\n".join(names))
        return 0

    logs = Path(tempfile.mkdtemp(prefix="dune-e2e-run-"))
    print(f"{len(names)} scripts, {options.jobs} at a time; logs in {logs}", flush=True)
    started = time.monotonic()
    failed: list[str] = []
    with ThreadPoolExecutor(max_workers=options.jobs) as pool:
        futures = [pool.submit(run_one, name, logs, options.timeout) for name in names]
        for future in as_completed(futures):
            name, code, seconds = future.result()
            status = "ok  " if code == 0 else ("TIME" if code is None else "FAIL")
            if code != 0:
                failed.append(name)
            print(f"  {status} {name:18s} {seconds:6.1f}s", flush=True)

    wall = time.monotonic() - started
    print(f"\n{len(names) - len(failed)} passed, {len(failed)} failed in {wall:.0f}s")
    for name in sorted(failed):
        lines = (logs / f"{name}.log").read_text(errors="replace").splitlines()
        print(f"\n--- {name} (last 25 lines of {logs / f'{name}.log'}) ---")
        print("\n".join(lines[-25:]))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
