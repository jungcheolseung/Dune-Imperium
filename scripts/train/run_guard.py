"""Run a long training command under a memory watchdog (stdlib only).

Why: on WSL an out-of-memory run has taken the whole session down before
(docs/development-handoff.md, 2026-09-17 pre-training check), and a training
main process that dies can leave orphan workers that look like progress
(docs/lessons.md, 2026-09-06). This wrapper

- starts the command in its own session/process group, output to train.log;
- samples /proc every second into mem.csv (MemAvailable, swap used, RSS of
  the main process and of the spawn workers);
- terminates the whole group if MemAvailable stays under the floor;
- when the main process ends, reaps leftover group members and writes the
  ``exit=<code>`` sentinel to guard.log and mem-summary.json with the peaks.

Usage: python3 run_guard.py --dir RUN_DIR [--min-available-mib 1500] -- cmd...
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

PAGE = os.sysconf("SC_PAGE_SIZE")


def meminfo() -> dict[str, int]:
    values: dict[str, int] = {}
    with open("/proc/meminfo") as handle:
        for line in handle:
            key, _, rest = line.partition(":")
            values[key] = int(rest.split()[0]) // 1024  # MiB
    return values


def group_processes(pgid: int) -> list[tuple[int, int, bool]]:
    """Return (pid, rss_mib, is_worker) for every process in the group."""

    found: list[tuple[int, int, bool]] = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            stat = Path(f"/proc/{entry}/stat").read_text()
            fields = stat[stat.rindex(")") + 2 :].split()
            if int(fields[2]) != pgid:  # pgrp
                continue
            statm = Path(f"/proc/{entry}/statm").read_text().split()
            cmdline = Path(f"/proc/{entry}/cmdline").read_bytes()
        except OSError, ValueError:
            continue
        rss = int(statm[1]) * PAGE // (1024 * 1024)
        found.append((int(entry), rss, b"multiprocessing" in cmdline))
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, required=True)
    parser.add_argument("--min-available-mib", type=int, default=1500)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("command", nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    command = [part for part in arguments.command if part != "--"]
    if not command:
        parser.error("no command given")
    run_dir: Path = arguments.dir
    run_dir.mkdir(parents=True, exist_ok=True)
    guard_log = (run_dir / "guard.log").open("a", buffering=1)

    def note(message: str) -> None:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        guard_log.write(f"{stamp} {message}\n")

    train_log = (run_dir / "train.log").open("ab")
    note(f"start: {' '.join(command)}")
    child = subprocess.Popen(
        command,
        cwd=arguments.cwd,
        stdout=train_log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    pgid = child.pid
    note(f"pid={child.pid} pgid={pgid} floor={arguments.min_available_mib}MiB")

    def forward(signum: int, _frame: object) -> None:
        note(f"guard received signal {signum}; stopping the group")
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)

    peaks = {
        "min_available_mib": 10**9,
        "max_swap_used_mib": 0,
        "max_group_rss_mib": 0,
        "max_main_rss_mib": 0,
        "max_worker_rss_mib": 0,
        "max_workers": 0,
        "samples": 0,
    }
    low = 0
    killed_for_memory = False
    csv_path = run_dir / "mem.csv"
    new_file = not csv_path.exists()
    with csv_path.open("a", buffering=1) as csv:
        if new_file:
            csv.write(
                "time,available_mib,swap_used_mib,group_rss_mib,main_rss_mib,"
                "workers,worker_rss_max_mib,worker_rss_sum_mib\n"
            )
        while child.poll() is None:
            info = meminfo()
            available = info["MemAvailable"]
            swap_used = info["SwapTotal"] - info["SwapFree"]
            processes = group_processes(pgid)
            workers = [rss for _, rss, worker in processes if worker]
            mains = [rss for _, rss, worker in processes if not worker]
            group_rss = sum(rss for _, rss, _ in processes)
            csv.write(
                f"{time.strftime('%H:%M:%S')},{available},{swap_used},{group_rss},"
                f"{max(mains, default=0)},{len(workers)},{max(workers, default=0)},"
                f"{sum(workers)}\n"
            )
            peaks["min_available_mib"] = min(peaks["min_available_mib"], available)
            peaks["max_swap_used_mib"] = max(peaks["max_swap_used_mib"], swap_used)
            peaks["max_group_rss_mib"] = max(peaks["max_group_rss_mib"], group_rss)
            peaks["max_main_rss_mib"] = max(
                peaks["max_main_rss_mib"], max(mains, default=0)
            )
            peaks["max_worker_rss_mib"] = max(
                peaks["max_worker_rss_mib"], max(workers, default=0)
            )
            peaks["max_workers"] = max(peaks["max_workers"], len(workers))
            peaks["samples"] += 1
            low = low + 1 if available < arguments.min_available_mib else 0
            if low >= 2 and not killed_for_memory:
                killed_for_memory = True
                note(
                    f"LOW MEMORY: available {available} MiB < floor "
                    f"{arguments.min_available_mib} MiB; terminating the group"
                )
                os.killpg(pgid, signal.SIGTERM)
                deadline = time.monotonic() + 10
                while child.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.2)
                if child.poll() is None:
                    os.killpg(pgid, signal.SIGKILL)
            time.sleep(arguments.interval)

    code = child.returncode
    leftovers = [pid for pid, _, _ in group_processes(pgid)]
    if leftovers:
        note(f"main ended; reaping {len(leftovers)} leftover group process(es)")
        try:
            os.killpg(pgid, signal.SIGTERM)
            time.sleep(3)
            if group_processes(pgid):
                os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    peaks["exit_code"] = code
    peaks["killed_for_memory"] = killed_for_memory
    (run_dir / "mem-summary.json").write_text(json.dumps(peaks, indent=2) + "\n")
    note(f"peaks: {json.dumps(peaks)}")
    note(f"exit={code}")
    train_log.close()
    guard_log.close()
    return code if code is not None and code >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
