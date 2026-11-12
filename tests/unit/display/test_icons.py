"""Tests for the rulebook icon-name table and filename resolution."""

from dune_imperium import display
from dune_imperium.display.icons import (
    APP_ONLY_ICON_NAMES,
    ICON_NAMES,
    RULEBOOK_ICON_SOURCE_GROUPS,
    available_icons,
    icon_filename,
)


def test_icon_names_are_lowercase_unique_identifiers() -> None:
    assert len(ICON_NAMES) == len(set(ICON_NAMES))
    for name in ICON_NAMES:
        assert name.isidentifier()
        assert name == name.lower()


def test_rulebook_icon_sources_keys_match_icon_names_in_order() -> None:
    names = tuple(
        name
        for sources in RULEBOOK_ICON_SOURCE_GROUPS.values()
        for name in sources
    )
    assert ICON_NAMES == (*names, *APP_ONLY_ICON_NAMES)


def test_app_only_icons_are_served_but_have_no_rulebook_source() -> None:
    """Rise of Ix's card icons come from the app alone: they are served like
    every icon, yet ``extract_rulebook_icons`` (which reads the source
    groups) never makes them."""

    rulebook_names = {
        name
        for sources in RULEBOOK_ICON_SOURCE_GROUPS.values()
        for name in sources
    }

    assert APP_ONLY_ICON_NAMES == (
        "dreadnought",
        "freighter",
        "tech_negotiation",
        "acquire_tech",
        "acquire_tech_minus1",
        "acquire_tech_minus2",
        "unload",
    )
    assert not rulebook_names & set(APP_ONLY_ICON_NAMES)
    assert set(APP_ONLY_ICON_NAMES) <= set(ICON_NAMES)


def test_rulebook_icon_sources_pages_and_xrefs_are_unique_and_valid() -> None:
    triples = [
        (source_key, page, xref)
        for source_key, sources in RULEBOOK_ICON_SOURCE_GROUPS.items()
        for page, xref in sources.values()
    ]

    assert len(triples) == len(set(triples))
    assert set(RULEBOOK_ICON_SOURCE_GROUPS) == {"main", "immortality"}
    assert all(page in (9, 20) for source, page, _xref in triples if source == "main")
    assert ("immortality", 16, 203) in triples


def test_icon_filename_appends_png() -> None:
    assert icon_filename("troop") == "troop.png"


def test_available_icons_keeps_only_present_files() -> None:
    available = frozenset(
        {"troop.png", "specimen.png", "freighter.png", "unknown.png"}
    )

    assert available_icons(available) == {
        "troop": "troop.png",
        "specimen": "specimen.png",
        "freighter": "freighter.png",
    }
    assert available_icons(frozenset()) == {}


def test_display_package_reexports_icon_helpers() -> None:
    assert display.ICON_NAMES == ICON_NAMES
    assert display.icon_filename is icon_filename
    assert display.available_icons is available_icons
