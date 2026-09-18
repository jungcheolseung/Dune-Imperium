"""Keep one training run going unattended (stdlib only; lives outside git).

Runs ``dune-imperium-train`` under ``run_guard.py`` until TOTAL iterations are
recorded in ``training.jsonl``. When an attempt dies with an exception (a
learner explores states no soak has reached, so an engine error is possible),
the traceback is kept as ``crash_<n>.log`` and the run resumes from
``latest.pt`` with ``--seed`` bumped, because a resumed iteration would
otherwise replay the very game seeds that crashed. It does not restart after
a memory kill (needs a human), a manual stop, two attempts in a row without
progress, or MAX_RESTARTS.

Stop it with:  kill -TERM $(cat RUN_DIR/supervisor.pid)
usage: train_overnight.py --dir RUN_DIR --total N --repo REPO -- <train args
       without --out/--iterations/--resume/--seed>
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

MAX_RESTARTS = 8


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, required=True)
    parser.add_argument("--total", type=int, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--floor-mib", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--start-from",
        type=Path,
        default=None,
        help="checkpoint the first attempt resumes from (a run that continues "
        "another run's checkpoint in a fresh directory); --total still counts "
        "the iterations recorded in this directory",
    )
    parser.add_argument("train_args", nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    train_args = [part for part in arguments.train_args if part != "--"]
    run: Path = arguments.dir
    run.mkdir(parents=True, exist_ok=True)
    (run / "supervisor.pid").write_text(f"{os.getpid()}\n")
    log = (run / "supervisor.log").open("a", buffering=1)

    def note(message: str) -> None:
        log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")

    def done() -> int:
        path = run / "training.jsonl"
        return len(path.read_text().splitlines()) if path.exists() else 0

    state = {"stopping": False, "guard": None}

    def stop(signum: int, _frame: object) -> None:
        state["stopping"] = True
        note(f"signal {signum}: stopping after the guard ends")
        guard = state["guard"]
        if guard is not None and guard.poll() is None:
            guard.send_signal(signal.SIGTERM)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    restarts = 0
    seed = arguments.seed
    stalled = 0
    reason = "unknown"
    while True:
        completed = done()
        remaining = arguments.total - completed
        if remaining <= 0:
            reason = f"finished: {completed} iterations"
            break
        command = [
            sys.executable,
            str(Path(__file__).resolve().with_name("run_guard.py")),
            "--dir",
            str(run),
            "--min-available-mib",
            str(arguments.floor_mib),
            "--cwd",
            str(arguments.repo),
            "--",
            str(arguments.repo / ".venv" / "bin" / "dune-imperium-train"),
            "--out",
            str(run),
            "--iterations",
            str(remaining),
            "--seed",
            str(seed),
            *train_args,
        ]
        latest = run / "latest.pt"
        if completed > 0 and latest.exists():
            command += ["--resume", str(latest)]
        elif arguments.start_from is not None:
            command += ["--resume", str(arguments.start_from)]
        note(
            f"attempt {restarts + 1}: {completed}/{arguments.total} done, "
            f"seed {seed}, resume={'--resume' in command}"
        )
        guard = subprocess.Popen(
            command,
            cwd=arguments.repo,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        state["guard"] = guard
        code = guard.wait()
        state["guard"] = None
        after = done()
        if state["stopping"]:
            reason = f"stopped by signal at {after} iterations"
            break
        if code == 0 and after >= arguments.total:
            reason = f"finished: {after} iterations"
            break
        summary_path = run / "mem-summary.json"
        killed_for_memory = False
        if summary_path.exists():
            try:
                killed_for_memory = bool(
                    json.loads(summary_path.read_text()).get("killed_for_memory")
                )
            except ValueError:
                pass
        if killed_for_memory:
            reason = f"memory guard fired at {after} iterations; not restarting"
            break
        restarts += 1
        crash = run / f"crash_{restarts}.log"
        train_log = run / "train.log"
        tail = (
            train_log.read_text(errors="replace")[-6000:] if train_log.exists() else ""
        )
        crash.write_text(f"exit code {code}; iterations {after}; seed {seed}\n\n{tail}")
        note(
            f"attempt ended with exit {code} at {after} iterations; "
            f"traceback tail kept in {crash.name}"
        )
        stalled = stalled + 1 if after == completed else 0
        if stalled >= 2:
            reason = f"two attempts without progress at {after} iterations; giving up"
            break
        if restarts >= MAX_RESTARTS:
            reason = f"{MAX_RESTARTS} restarts used at {after} iterations; giving up"
            break
        seed += 1
        time.sleep(10)
    note(f"supervisor-exit: {reason}")
    log.close()
    return 0 if reason.startswith("finished") else 1


if __name__ == "__main__":
    sys.exit(main())
