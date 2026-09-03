"""Tests for the rulebook icon-name table and filename resolution."""

from dune_imperium import display
from dune_imperium.display.icons import (
    ICON_NAMES,
    RULEBOOK_ICON_SOURCES,
    available_icons,
    icon_filename,
)


def test_icon_names_are_lowercase_unique_identifiers() -> None:
    assert len(ICON_NAMES) == len(set(ICON_NAMES))
    for name in ICON_NAMES:
        assert name.isidentifier()
        assert name == name.lower()


def test_rulebook_icon_sources_keys_match_icon_names_in_order() -> None:
    assert tuple(RULEBOOK_ICON_SOURCES.keys()) == ICON_NAMES
    assert set(RULEBOOK_ICON_SOURCES.keys()) == set(ICON_NAMES)


def test_rulebook_icon_sources_pages_and_xrefs_are_unique_and_valid() -> None:
    pairs = list(RULEBOOK_ICON_SOURCES.values())

    assert len(pairs) == len(set(pairs))
    for page, _xref in pairs:
        assert page in (9, 20)


def test_icon_filename_appends_png() -> None:
    assert icon_filename("troop") == "troop.png"


def test_available_icons_keeps_only_present_files() -> None:
    available = frozenset({"troop.png", "unknown.png"})

    assert available_icons(available) == {"troop": "troop.png"}
    assert available_icons(frozenset()) == {}


def test_display_package_reexports_icon_helpers() -> None:
    assert display.ICON_NAMES == ICON_NAMES
    assert display.icon_filename is icon_filename
    assert display.available_icons is available_icons
