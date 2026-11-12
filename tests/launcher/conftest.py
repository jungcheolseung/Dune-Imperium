"""The launcher tests run as on a plain machine: under WSL ``listen_host``
would widen every remote bind (plan 5.13). The WSL tests ask for it."""

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _not_wsl(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr("dune_imperium.launcher.command.is_wsl", lambda: False)
    yield
