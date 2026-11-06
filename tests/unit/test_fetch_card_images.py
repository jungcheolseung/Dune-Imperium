"""Local image crops are restored from assets, never fetched without a URL."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "fetch_card_images.py"


@pytest.mark.parametrize("mode", ["dry-run", "missing", "present"])
def test_local_photo_crops_do_not_trigger_a_download(tmp_path: Path, mode: str) -> None:
    relative = "uprising/objective/Objective (Crysknife).png"
    manifest = {
        "entries": [
            {
                "path": relative,
                "set": "uprising",
                "source": {"file": "owner-photo.jpg", "url": None, "sha256": "unused"},
            }
        ],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    if mode == "present":
        image = tmp_path / "en" / relative
        image.parent.mkdir(parents=True)
        image.write_bytes(b"existing crop")
    arguments = [sys.executable, str(SCRIPT), "--dest", str(tmp_path)]
    if mode == "dry-run":
        arguments.append("--dry-run")
    result = subprocess.run(arguments, capture_output=True, text=True, check=False)
    assert "Traceback" not in result.stderr
    if mode == "missing":
        assert result.returncode == 1
        assert "restore from private assets checkout" in result.stderr
        assert not (tmp_path / "en" / relative).exists()
    else:
        assert result.returncode == 0
        if mode == "dry-run":
            assert "local crop of owner-photo.jpg" in result.stdout
        else:
            assert "1 already present" in result.stdout
