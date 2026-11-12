"""Shared pytest setup: temporary files and torch's thread pool.

User decision (2026-10-06): nothing the project makes lives outside the
project directory, temporary files included. ``tmp_path`` and every
``tempfile`` call of a test run (and of the processes it starts, through
``TMPDIR``) land in the git-ignored ``tmp/pytest/`` of this checkout.
pytest numbers its run folders there and keeps the last three, so two runs
side by side do not clobber each other.

Every test process holds torch to one compute thread, as a tournament
worker does (``evaluation.tournament._single_threaded_worker``). torch's
default intra-op pool has one thread per CPU, so the pytest-xdist workers
oversubscribed the machine: on a 4-CPU Linux container with ``-n auto``
(2026-11-02) a search seat's test spent 70-90% of its time in the network's
``linear`` and ``log1p`` waiting on that pool. The variables are read when
torch is first imported, so they are set before any test module imports
it; a thread count the caller exported is left alone.

With bytecode writing off (the Claude desktop app sets
``PYTHONDONTWRITEBYTECODE=1``), the xdist controller rewrites the test
modules' asserts once for all workers (``tests/support/rewrite_cache.py``).
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

from dune_imperium.paths import TMP_DIR
from tests.support import rewrite_cache

_TEST_TMP = TMP_DIR / "pytest"
_TEST_TMP.mkdir(parents=True, exist_ok=True)
os.environ["TMPDIR"] = str(_TEST_TMP)
tempfile.tempdir = str(_TEST_TMP)

_THREAD_VARIABLES = ("OMP_NUM_THREADS", "MKL_NUM_THREADS")
if not any(name in os.environ for name in _THREAD_VARIABLES):
    for _name in _THREAD_VARIABLES:
        os.environ[_name] = "1"
    if "torch" in sys.modules:
        sys.modules["torch"].set_num_threads(1)


@pytest.fixture
def symlink_support(tmp_path: Path) -> None:
    """Only link-specific tests need Windows symlink permission.

    Ordinary hosts choose real files in the launcher and need neither
    administrator rights nor Developer Mode.
    """
    if os.name != "nt":
        return
    probe = tmp_path / "symlink-permission-probe"
    try:
        probe.symlink_to("missing-target")
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows account has no symlink permission")
        raise
    else:
        probe.unlink()


def pytest_sessionstart(session: pytest.Session) -> None:
    # Before xdist's own (trylast) session start launches the workers.
    rewrite_cache.prewrite(session.config)


def pytest_unconfigure(config: pytest.Config) -> None:
    rewrite_cache.remove(config)
