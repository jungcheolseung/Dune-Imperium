"""Tests for the action log's picture names and filename resolution."""

import importlib.util
from pathlib import Path

from dune_imperium.display.icons import ICON_NAMES, icon_filename
from dune_imperium.display.log_icons import (
    LOG_ICON_NAMES,
    ROUND_LOG_ICONS,
    available_log_icons,
    log_icon_filename,
)

_DWGR_SCRIPT = (
    Path(__file__).resolve().parents[3] / "scripts" / "dwgr" / "app_log_icons.py"
)


def test_log_icon_names_are_lowercase_unique_identifiers() -> None:
    assert len(LOG_ICON_NAMES) == len(set(LOG_ICON_NAMES))
    for name in LOG_ICON_NAMES:
        assert name.isidentifier()
        assert name == name.lower()


def test_log_icon_names_hold_the_round_numerals_and_faction_marks() -> None:
    rounds = [name for name in LOG_ICON_NAMES if name.startswith("round_")]
    assert rounds == [f"round_{n}" for n in range(1, ROUND_LOG_ICONS + 1)]
    assert ROUND_LOG_ICONS == 10
    assert {
        name for name in LOG_ICON_NAMES if name.startswith("influence_down_")
    } == {
        f"influence_down_{faction}"
        for faction in ("emperor", "spacing_guild", "bene_gesserit", "fremen")
    }


def test_log_icon_files_never_collide_with_rulebook_icon_files() -> None:
    log_files = {log_icon_filename(name) for name in LOG_ICON_NAMES}
    icon_files = {icon_filename(name) for name in ICON_NAMES}
    assert not log_files & icon_files


def test_log_icon_filename_prefixes_log_and_appends_png() -> None:
    assert log_icon_filename("conflict") == "log_conflict.png"
    assert log_icon_filename("round_10") == "log_round_10.png"


def test_available_log_icons_keeps_only_present_files() -> None:
    files = frozenset(
        {"log_conflict.png", "log_round_3.png", "troop.png", "log_unknown.png"}
    )

    assert available_log_icons(files) == {
        "conflict": "log_conflict.png",
        "round_3": "log_round_3.png",
    }
    assert available_log_icons(frozenset()) == {}


def test_extraction_script_writes_exactly_the_log_icon_names() -> None:
    """scripts/dwgr/app_log_icons.py writes one app sprite per name; the
    script imports UnityPy and Pillow only when it runs, so its table loads
    here without them."""
    spec = importlib.util.spec_from_file_location("app_log_icons", _DWGR_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    sources = module.LOG_ICON_SOURCES
    assert list(sources) == list(LOG_ICON_NAMES)
    assert all(module.filename(name) == log_icon_filename(name) for name in sources)
    assert len(set(sources.values())) == len(sources)
