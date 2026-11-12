"""The xdist controller's assert-rewrite prewrite (tests/support/rewrite_cache.py).

A worker must run exactly the code pytest would have built itself, and a run
must leave behind none of the cache files it created.
"""

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from _pytest.assertion import rewrite as _rewrite
from tests.support import rewrite_cache

_MODULE = """
def test_sample():
    values = [1, 2, 3]
    assert sum(values) == 6, "sum"
    assert {"a": values} != {"a": []}
"""


def _write_module(folder: Path, name: str) -> Path:
    path = folder / name
    path.write_text(_MODULE, encoding="utf-8")
    return path


def test_a_prewritten_module_is_the_code_pytest_would_build(tmp_path: Path) -> None:
    path = _write_module(tmp_path, "test_sample.py")

    result = rewrite_cache._prewrite_one(str(path))

    pyc = tmp_path / "__pycache__" / ("test_sample" + _rewrite.PYC_TAIL)
    assert result == (str(path), str(pyc), str(tmp_path / "__pycache__"))
    cached = _rewrite._read_pyc(path, pyc)
    assert cached is not None
    _, own = _rewrite._rewrite_test(path, cast(Any, None))
    assert cached == own


def test_removal_takes_only_what_the_prewrite_created(tmp_path: Path) -> None:
    kept = _write_module(tmp_path, "test_kept.py")
    first = rewrite_cache._prewrite_one(str(kept))
    assert first is not None and first[1] is not None
    new = _write_module(tmp_path, "test_new.py")

    again = rewrite_cache._prewrite_one(str(kept))
    created = rewrite_cache._prewrite_one(str(new))

    assert again == (str(kept), None, None)  # existed: overwritten, not owned
    assert created is not None and created[1] is not None and created[2] is None
    stash = pytest.Stash()
    stash[rewrite_cache._WRITTEN] = ([Path(created[1])], [tmp_path / "__pycache__"])
    rewrite_cache.remove(cast(pytest.Config, SimpleNamespace(stash=stash)))
    assert not Path(created[1]).exists()
    assert Path(first[1]).exists()  # the folder still holds it, so it stays
