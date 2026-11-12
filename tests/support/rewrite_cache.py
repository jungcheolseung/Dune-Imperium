"""Rewrite the test modules' asserts once per run instead of once per worker.

pytest rewrites the asserts of every test module and conftest it imports and
keeps the result in ``__pycache__/<name>.<tag>-pytest-<version>.pyc`` -- but
only when bytecode writing is on. The Claude desktop app runs every command
with ``PYTHONDONTWRITEBYTECODE=1``, so there every pytest-xdist worker
rewrote all ~460 test modules itself on every run: about 14 s of each worker's
25 s collection, eight times over at ``-n 8`` (measured 2026-11-11).

When bytecode writing is off and xdist is about to start its workers, the
controller rewrites the modules under the run's paths once, in parallel, with
pytest's own ``_rewrite_test`` on the current source, and writes them where
pytest looks. Each worker's import then goes through pytest's unchanged
cache check (Python magic number, pytest version, source mtime and size) and
runs the same code it would have built itself; a file it rejects, or one the
prewrite missed, it rewrites as before. The files are written fresh on every
run, and the ones this run created are removed when it ends, so no cache
outlives the run: a later run with bytecode off still rewrites from source,
and the mutation checks of docs/lessons.md (2026-09-26, stale ``.pyc``) are
unaffected. Nothing under ``src/`` is ever cached here.

With bytecode writing on (a plain terminal), pytest's own cache already
serves every run after the first, and this does nothing.
"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path
from typing import Any, cast

import pytest
from _pytest.assertion import rewrite as _rewrite
from _pytest.pathlib import fnmatch_ex

_WRITTEN = pytest.StashKey[tuple[list[Path], list[Path]]]()
_SKIPPED_DIRS = frozenset({"__pycache__"})


def _wanted(config: pytest.Config) -> int:
    """Workers to prewrite with, or 0 when this run should not prewrite."""
    if not sys.dont_write_bytecode or hasattr(config, "workerinput"):
        return 0
    if config.pluginmanager.getplugin("dsession") is None:
        return 0  # not an xdist controller about to start workers
    if config.getoption("assertmode") != "rewrite":
        return 0
    if config.getini("enable_assertion_pass_hook"):
        return 0  # the prewrite below rewrites without a config
    workers = config.getoption("numprocesses")
    if not isinstance(workers, int) or workers < 2:
        return 0
    return min(workers, os.cpu_count() or 1)


def _run_paths(config: pytest.Config) -> list[Path]:
    if config.args_source == pytest.Config.ArgsSource.TESTPATHS:
        base = config.rootpath
    else:
        base = config.invocation_params.dir
    return [base / arg.split("::", 1)[0] for arg in config.args]


def module_paths(config: pytest.Config) -> list[Path]:
    """Test modules and conftests under the run's paths, as pytest picks them."""
    patterns = config.getini("python_files")
    found: set[Path] = set()
    for root in _run_paths(config):
        if root.is_file():
            if root.suffix == ".py":
                found.add(root.resolve())
            continue
        for directory, subdirs, files in os.walk(root):
            subdirs[:] = [
                name
                for name in subdirs
                if name not in _SKIPPED_DIRS and not name.startswith(".")
            ]
            for name in files:
                if not name.endswith(".py"):
                    continue
                path = Path(directory, name)
                if name == "conftest.py" or any(
                    fnmatch_ex(pattern, path) for pattern in patterns
                ):
                    found.add(path.resolve())
    return sorted(found)


def _prewrite_one(source: str) -> tuple[str, str | None, str | None] | None:
    """Write one module's rewritten code; report the files and dir it created."""
    path = Path(source)
    try:
        stat, code = _rewrite._rewrite_test(path, cast(Any, None))
    except Exception:
        return None  # a worker meets the same error and reports it
    cache_dir = _rewrite.get_cache_dir(path)
    new_dir = not cache_dir.exists()
    if not _rewrite.try_makedirs(cache_dir):
        return None
    pyc = cache_dir / (path.name[:-3] + _rewrite.PYC_TAIL)
    new_file = not pyc.exists()
    partial = f"{pyc}.{os.getpid()}"
    try:
        with open(partial, "wb") as handle:
            _rewrite._write_pyc_fp(handle, stat, code)
        os.replace(partial, pyc)
    except OSError:
        return None
    return (
        source,
        str(pyc) if new_file else None,
        str(cache_dir) if new_dir else None,
    )


def prewrite(config: pytest.Config) -> None:
    """On an xdist controller with bytecode writing off, prewrite the modules."""
    workers = _wanted(config)
    if not workers:
        return
    sources = [str(path) for path in module_paths(config)]
    if not sources:
        return
    files: list[Path] = []
    dirs: set[Path] = set()
    with ProcessPoolExecutor(workers, mp_context=get_context("spawn")) as pool:
        for result in pool.map(_prewrite_one, sources, chunksize=8):
            if result is None:
                continue
            _, new_file, new_dir = result
            if new_file is not None:
                files.append(Path(new_file))
            if new_dir is not None:
                dirs.add(Path(new_dir))
    config.stash[_WRITTEN] = (files, sorted(dirs, reverse=True))


def remove(config: pytest.Config) -> None:
    """Remove the cache files and folders this run's prewrite created."""
    files, dirs = config.stash.get(_WRITTEN, ([], []))
    for path in files:
        path.unlink(missing_ok=True)
    for directory in dirs:
        try:
            directory.rmdir()
        except OSError:
            pass  # not empty: another run or tool keeps files there
