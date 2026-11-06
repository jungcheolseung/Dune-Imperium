"""Shared fixtures of the app_ai tests."""

import logging
from collections.abc import Iterator

import pytest

from dune_imperium.agents.app_ai import agent as agent_module


class _ErrorRecords(logging.Handler):
    """Keeps the ERROR records of the agent's logger."""

    def __init__(self) -> None:
        super().__init__(logging.ERROR)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def app_ai_error_records() -> Iterator[list[logging.LogRecord]]:
    """The ERROR records ``AppAIAgent`` logged during the test: a window
    that raised or chose an illegal action."""

    handler = _ErrorRecords()
    logger = logging.getLogger(agent_module.__name__)
    logger.addHandler(handler)
    try:
        yield handler.records
    finally:
        logger.removeHandler(handler)


@pytest.fixture
def app_ai_errors_expected() -> None:
    """Request this in a test that makes an app_ai window fail on purpose,
    to opt out of ``_no_app_ai_window_errors``."""


@pytest.fixture(autouse=True)
def _no_app_ai_window_errors(
    request: pytest.FixtureRequest, app_ai_error_records: list[logging.LogRecord]
) -> Iterator[None]:
    """Fail every test in which an app_ai window raised or chose an illegal
    action.

    ``AppAIAgent`` answers such a decision at random, so a live game never
    stalls on an app_ai bug (user decision 2026-10-05), and logs an ERROR.
    Before that the exception reached the test. Most game-level coverage
    tests count only ``fallbacks[<kind>]``, never ``error:<kind>``, so
    without this guard a window that breaks mid-game would pass them.
    """

    yield
    if app_ai_error_records and "app_ai_errors_expected" not in request.fixturenames:
        formatter = logging.Formatter()
        lines = [formatter.format(record) for record in app_ai_error_records[:3]]
        pytest.fail(
            f"{len(app_ai_error_records)} app_ai window error(s), the first:\n"
            + "\n".join(lines),
            pytrace=False,
        )
