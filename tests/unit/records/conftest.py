"""Shared fixtures of the record-corpus tests: the drivers and a tiny corpus.

The corpus drivers are scripts (``scripts/records``) run under any engine;
the tests load them by path, as ``test_tip_census.py`` loads its script. The
tiny corpus is built once per session by the real generator on this engine:
four games cut after round 1, in three (combo, mix) groups.
"""

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts" / "records"
# The commit the tiny corpus is stamped with (no git is asked).
TINY_COMMIT = "0123456789abcdef0123456789abcdef01234567"


def _load_script(name: str) -> ModuleType:
    """Import ``scripts/records/<name>.py`` under a test-only module name."""

    module_name = f"_records_script_{name}"
    loaded = sys.modules.get(module_name)
    if loaded is not None:
        return loaded
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def generator() -> ModuleType:
    """``scripts/records/corpus_generate.py``."""

    return _load_script("corpus_generate")


@pytest.fixture(scope="session")
def make_identity(generator: ModuleType) -> Callable[..., Any]:
    """A fake ``EngineIdentity`` for the tiny corpus's commit."""

    def make(*, on_master: bool = True) -> Any:
        return generator.EngineIdentity(
            commit=TINY_COMMIT,
            on_master=on_master,
            engine_trees={name: "0" * 40 for name in generator.ENGINE_TREES},
            agents_tree="1" * 40,
        )

    return make


@pytest.fixture(scope="session")
def tiny_requests(generator: ModuleType) -> list[Any]:
    return [
        generator.Request("full", "h4", 1, 2),
        generator.Request("base", "h4", 1, 1),
        generator.Request("no-tech", "rhra", 1, 1),
    ]


@pytest.fixture(scope="session")
def tiny_corpus(
    tmp_path_factory: pytest.TempPathFactory,
    generator: ModuleType,
    make_identity: Callable[..., Any],
    tiny_requests: list[Any],
) -> Path:
    """The folder of a four-game corpus, every game cut after round 1."""

    corpus: Path = generator.generate(
        tmp_path_factory.mktemp("corpus"),
        tiny_requests,
        identity=make_identity(),
        workers=1,
        rounds=1,
        log=lambda line: None,
    )
    return corpus
