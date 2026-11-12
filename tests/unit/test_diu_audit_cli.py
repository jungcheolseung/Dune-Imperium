"""Tests for the DIU development audit CLI."""

from pathlib import Path

import pytest

from dune_imperium.cli.diu_audit import main


def test_missing_diu_source_returns_a_diagnostic(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main((str(tmp_path / "missing.JSON"),))

    assert result == 2
    captured = capsys.readouterr()
    assert "DIU audit failed" in captured.out
