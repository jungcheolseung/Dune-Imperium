"""The project's own files stay inside the project directory (2026-10-06)."""

import subprocess
import tempfile
from pathlib import Path

from dune_imperium.paths import PROJECT_ROOT, SAVES_DIR, SEARCH_CHECKPOINT, TMP_DIR


def test_every_default_folder_is_inside_the_checkout_and_ignored() -> None:
    assert (PROJECT_ROOT / "pyproject.toml").is_file()
    for path in (SAVES_DIR, SEARCH_CHECKPOINT, TMP_DIR):
        assert PROJECT_ROOT in path.parents
    paths = ["saves/x.json", "checkpoints/play/search.pt", "tmp/x"]
    ignored = subprocess.run(
        ["git", "check-ignore", *paths],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ignored.stdout.split() == paths


def test_a_test_runs_temporary_files_land_in_the_project_tmp(tmp_path: Path) -> None:
    assert TMP_DIR in tmp_path.resolve().parents
    assert TMP_DIR in Path(tempfile.gettempdir()).resolve().parents
    with tempfile.TemporaryDirectory() as scratch:
        assert TMP_DIR in Path(scratch).resolve().parents
