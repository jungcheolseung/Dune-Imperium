"""Run a long training command under a memory watchdog (stdlib only).

Why: on WSL an out-of-memory run has taken the whole session down before
(docs/development-handoff.md, 2026-09-17 pre-training check), and a training
main process that dies can leave orphan workers that look like progress
(docs/lessons.md, 2026-09-06). This wrapper

- starts the command in its own session/process group, output to train.log;
- samples memory every second into mem.csv (available memory, swap used, RSS
  of the main process and of the spawn workers);
- terminates the whole group when memory runs out (the rule is per platform,
  below);
- when the main process ends, reaps leftover group members and writes the
  ``exit=<code>`` sentinel to guard.log and mem-summary.json with the peaks.

Linux reads /proc and stops the run when MemAvailable stays under the floor.

macOS has no MemAvailable. ``available`` there is vm_stat's free +
file-backed + purgeable pages (what can be handed out without compressing or
swapping). It follows allocations (a job holding 1 GiB lowered it by 1 GiB),
but which level of it means trouble is not known: the 16 GB M4 Mac mini ran
full-expansion iterations at 2.5 GiB available with 3.8 GiB in the compressor
and the kernel reporting no pressure (2026-09-19). So it is logged and takes
a floor only when one is given (default 0, off), and the stop signal is the
kernel's own verdict, ``kern.memorystatus_vm_pressure_level`` (1 normal,
2 warning, 4 critical): critical on two samples in a row stops the group,
warning samples are counted and every change of level goes to guard.log. The
critical branch has not been provoked on a real machine; the stop itself is
exercised through the floor. ``ps`` supplies the group; its RSS leaves out
compressed pages, so group RSS undercounts once the compressor is busy.

Usage: python3 run_guard.py --dir RUN_DIR [--min-available-mib N] -- cmd...
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

IS_DARWIN = sys.platform == "darwin"
PAGE = os.sysconf("SC_PAGE_SIZE")
MIB = 1024 * 1024
# kern.memorystatus_vm_pressure_level
PRESSURE_WARNING = 2
PRESSURE_CRITICAL = 4
# MemAvailable floor in MiB; off on macOS (see the module docstring).
DEFAULT_FLOOR_MIB = 0 if IS_DARWIN else 1500


def meminfo() -> dict[str, int]:
    """MemAvailable, SwapTotal and SwapFree in MiB (more keys per platform)."""

    if IS_DARWIN:
        return _darwin_meminfo()
    values: dict[str, int] = {}
    with open("/proc/meminfo") as handle:
        for line in handle:
            key, _, rest = line.partition(":")
            values[key] = int(rest.split()[0]) // 1024  # MiB
    return values


# The last good macOS sample; MemAvailable starts above any floor.
_darwin_sample: dict[str, int] = {
    "MemAvailable": 10**9,
    "SwapTotal": 0,
    "SwapFree": 0,
    "Compressed": 0,
    "PressureLevel": 0,
}


def _darwin_meminfo() -> dict[str, int]:
    """The Linux keys from vm_stat and sysctl, plus Compressed and PressureLevel.

    Sampling forks, and a fork is likeliest to fail when memory is shortest.
    A guard that died there would leave the group running with nobody
    watching, so a failed sample repeats the last good one.
    """

    try:
        _darwin_sample.update(_darwin_read())
    except OSError, subprocess.SubprocessError, LookupError, ValueError:
        pass
    return dict(_darwin_sample)


def _darwin_read() -> dict[str, int]:
    report = subprocess.run(
        ["vm_stat"], capture_output=True, text=True, check=True
    ).stdout
    # "Mach Virtual Memory Statistics: (page size of 16384 bytes)"
    header, _, body = report.partition("\n")
    page = int(header.partition("page size of ")[2].split()[0])
    pages: dict[str, int] = {}
    for line in body.splitlines():
        key, _, rest = line.partition(":")
        count = rest.strip().rstrip(".")
        if count.isdigit():
            pages[key.strip('" ')] = int(count)
    # "total = 2048.00M  used = 1081.88M  free = 966.12M  (encrypted)" and "1"
    swap, level = subprocess.run(
        ["sysctl", "-n", "vm.swapusage", "kern.memorystatus_vm_pressure_level"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()[:2]
    fields = swap.split()
    sizes = {
        fields[index]: int(float(fields[index + 2].rstrip("M")))
        for index in range(0, 9, 3)
    }
    available = (
        pages["Pages free"] + pages["File-backed pages"] + pages["Pages purgeable"]
    )
    return {
        "MemAvailable": available * page // MIB,
        "SwapTotal": sizes["total"],
        "SwapFree": sizes["free"],
        "Compressed": pages["Pages occupied by compressor"] * page // MIB,
        "PressureLevel": int(level),
    }


def starvation(info: dict[str, int], floor_mib: int) -> str | None:
    """Why this sample counts as out of memory, or None."""

    available = info["MemAvailable"]
    if available < floor_mib:
        return f"available {available} MiB < floor {floor_mib} MiB"
    if info.get("PressureLevel", 0) >= PRESSURE_CRITICAL:
        return f"kernel memory pressure is critical (available {available} MiB)"
    return None


def group_processes(pgid: int) -> list[tuple[int, int, bool]]:
    """Return (pid, rss_mib, is_worker) for every process in the group."""

    if IS_DARWIN:
        return _darwin_group_processes(pgid)
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


def _darwin_group_processes(pgid: int) -> list[tuple[int, int, bool]]:
    try:
        listing = subprocess.run(
            ["ps", "-A", "-ww", "-o", "pid=,pgid=,rss=,command="],
            capture_output=True,
            text=True,
        ).stdout
    except OSError:  # a failed fork; see _darwin_meminfo
        return []
    found: list[tuple[int, int, bool]] = []
    for line in listing.splitlines():
        fields = line.split(None, 3)
        try:
            if int(fields[1]) != pgid:
                continue
            rss = int(fields[2]) // 1024  # ps reports KiB
            found.append((int(fields[0]), rss, "multiprocessing" in fields[3]))
        except IndexError, ValueError:
            continue
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, required=True)
    parser.add_argument("--min-available-mib", type=int, default=DEFAULT_FLOOR_MIB)
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
    if IS_DARWIN:
        peaks |= {
            "max_compressed_mib": 0,
            "max_pressure_level": 0,
            "pressure_warning_samples": 0,
        }
    low = 0
    pressure_seen = 0
    killed_for_memory = False
    csv_path = run_dir / "mem.csv"
    new_file = not csv_path.exists()
    with csv_path.open("a", buffering=1) as csv:
        if new_file:
            csv.write(
                "time,available_mib,swap_used_mib,group_rss_mib,main_rss_mib,"
                "workers,worker_rss_max_mib,worker_rss_sum_mib"
                + (",compressed_mib,pressure_level\n" if IS_DARWIN else "\n")
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
                f"{sum(workers)}"
            )
            if IS_DARWIN:
                pressure = info["PressureLevel"]
                csv.write(f",{info['Compressed']},{pressure}")
                peaks["max_compressed_mib"] = max(
                    peaks["max_compressed_mib"], info["Compressed"]
                )
                peaks["max_pressure_level"] = max(peaks["max_pressure_level"], pressure)
                peaks["pressure_warning_samples"] += pressure >= PRESSURE_WARNING
                if pressure != pressure_seen:
                    note(
                        f"memory pressure level {pressure} (available {available} "
                        f"MiB, swap used {swap_used} MiB, group {group_rss} MiB)"
                    )
                    pressure_seen = pressure
            csv.write("\n")
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
            starved = starvation(info, arguments.min_available_mib)
            low = low + 1 if starved else 0
            if starved and low >= 2 and not killed_for_memory:
                killed_for_memory = True
                note(f"LOW MEMORY: {starved}; terminating the group")
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
