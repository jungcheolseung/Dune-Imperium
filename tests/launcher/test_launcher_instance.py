"""One launcher per checkout: an exclusive lock the system drops on exit."""

import subprocess
import sys
from pathlib import Path

from dune_imperium.launcher.instance import InstanceLock


def test_a_second_launcher_finds_the_lock_taken(tmp_path: Path) -> None:
    path = tmp_path / "launcher.lock"
    first = InstanceLock(path)
    assert first.acquire()
    try:
        assert not InstanceLock(path).acquire()
    finally:
        first.release()
    again = InstanceLock(path)
    assert again.acquire()
    again.release()


def test_another_process_is_refused_while_the_lock_is_held(tmp_path: Path) -> None:
    path = tmp_path / "launcher.lock"
    held = InstanceLock(path)
    assert held.acquire()
    try:
        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; from pathlib import Path; "
                "from dune_imperium.launcher.instance import InstanceLock; "
                "print(InstanceLock(Path(sys.argv[1])).acquire())",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
    finally:
        held.release()
    assert probe.stdout.strip() == "False"


def test_a_lock_left_by_a_dead_launcher_does_not_block(tmp_path: Path) -> None:
    # The process ends without releasing: the system drops the lock.
    path = tmp_path / "launcher.lock"
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import os, sys; from pathlib import Path; "
            "from dune_imperium.launcher.instance import InstanceLock; "
            "assert InstanceLock(Path(sys.argv[1])).acquire(); os._exit(0)",
            str(path),
        ],
        check=True,
        timeout=60,
    )
    lock = InstanceLock(path)
    assert lock.acquire()
    lock.release()
