"""Tests for the Arrakeen Scouts card pictures and their availability."""

import ast
import hashlib
import json
from pathlib import Path

import pytest

from dune_imperium.display.scouts_art import (
    SCOUTS_ART_DIR,
    SCOUTS_ART_KINDS,
    SCOUTS_ART_NAMES,
    available_scouts_art,
    scouts_art_filename,
)
from dune_imperium.server.catalog import build_catalog

REPO = Path(__file__).resolve().parents[3]
SCOUTS_ART = REPO / "assets" / "cards" / SCOUTS_ART_DIR
TOOL = REPO / "scripts" / "dwgr" / "dwgr_scouts_ui.py"


def _tool_table() -> dict[str, str]:
    # The tool imports UnityPy, so its table is read as source.
    for node in ast.walk(ast.parse(TOOL.read_text())):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "SCOUTS_UI_SOURCES"
        ):
            table = ast.literal_eval(node.value)
            assert isinstance(table, dict)
            return table
    raise AssertionError("SCOUTS_UI_SOURCES not found")


def test_every_item_kind_has_its_painting() -> None:
    items = build_catalog()["scouts_items"]
    assert isinstance(items, dict)
    kinds = {entry["kind"] for entry in items.values() if isinstance(entry, dict)}
    assert kinds == set(SCOUTS_ART_KINDS)
    assert len(set(SCOUTS_ART_NAMES)) == len(SCOUTS_ART_NAMES)
    assert set(SCOUTS_ART_KINDS) <= set(SCOUTS_ART_NAMES)


def test_the_tool_writes_exactly_the_named_pictures() -> None:
    assert list(_tool_table()) == list(SCOUTS_ART_NAMES)


def test_pictures_are_offered_one_by_one() -> None:
    assert scouts_art_filename("event") == "event.webp"
    assert available_scouts_art(frozenset()) == {}
    files = frozenset(
        {
            "event.webp",
            "back.webp",
            # another format, a stray file or the provenance table is no picture
            "mission.png",
            "scouts_sources.json",
            "notes.txt",
        }
    )
    assert available_scouts_art(files) == {
        "event": "app/scouts/event.webp",
        "back": "app/scouts/back.webp",
    }
    every = frozenset(scouts_art_filename(name) for name in SCOUTS_ART_NAMES)
    assert list(available_scouts_art(every)) == list(SCOUTS_ART_NAMES)


@pytest.mark.skipif(
    not (SCOUTS_ART / "scouts_sources.json").is_file(),
    reason="assets checkout without the Scouts card pictures",
)
def test_the_assets_checkout_has_every_picture_as_recorded() -> None:
    sources = json.loads((SCOUTS_ART / "scouts_sources.json").read_text())
    rows = sources["pictures"]
    assert set(rows) == set(SCOUTS_ART_NAMES)
    assert sources["build_guid"]
    table = _tool_table()
    for name, row in rows.items():
        path = SCOUTS_ART / scouts_art_filename(name)
        assert row["file"] == path.name
        assert row["sprite"] == table[name]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"], name
    files = frozenset(path.name for path in SCOUTS_ART.iterdir())
    catalog = build_catalog(scouts_art_files=files)
    art = catalog["scouts_art"]
    assert isinstance(art, dict)
    assert list(art) == list(SCOUTS_ART_NAMES)
