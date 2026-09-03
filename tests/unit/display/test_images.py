"""Tests for local Dune Cards Hub image filename resolution."""

from pathlib import Path

import pytest

from dune_imperium.content.uprising.board import BOARD_SPACES
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.contracts import CONTRACTS
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS
from dune_imperium.content.uprising.intrigue import INTRIGUE_CARDS
from dune_imperium.content.uprising.leaders import LEADERS
from dune_imperium.content.uprising.reserve import RESERVE_STACKS
from dune_imperium.content.uprising.starting_cards import STARTING_DECK
from dune_imperium.display import images
from dune_imperium.display.images import (
    FILENAME_OVERRIDES,
    KNOWN_MISSING,
    default_filename,
    image_filename,
    required_images,
)

CACHE_DIR = (
    Path(__file__).resolve().parents[3] / "downloads" / "dunecardshub" / "cards"
)


def _all_content_ids() -> list[tuple[str, str]]:
    ids: list[tuple[str, str]] = []
    ids += [("imperium", entry.card.card_id) for entry in IMPERIUM_CARDS]
    ids += [("intrigue", entry.card.card_id) for entry in INTRIGUE_CARDS]
    ids += [("contract", contract.card.card_id) for contract in CONTRACTS]
    ids += [("conflict", conflict.card.card_id) for conflict in CONFLICTS]
    ids += [("location", space.space_id) for space in BOARD_SPACES]
    for leader in LEADERS:
        ids.append(("leader", leader.leader_id))
        if leader.alternate_face_id is not None:
            ids.append(("leader", leader.alternate_face_id))
    ids += [("other", entry.card.card_id) for entry in STARTING_DECK]
    ids += [("other", stack.card.card_id) for stack in RESERVE_STACKS]
    return ids


def test_default_filename_replaces_underscores_with_hyphens() -> None:
    assert default_filename("imperium", "maula_pistol") == (
        "uprising-imperium-maula-pistol.webp"
    )


def test_image_filename_resolves_the_default_when_present() -> None:
    available = frozenset({"uprising-imperium-maula-pistol.webp"})

    assert (
        image_filename("imperium", "maula_pistol", available)
        == "uprising-imperium-maula-pistol.webp"
    )


def test_image_filename_uses_a_registered_override() -> None:
    override = FILENAME_OVERRIDES[("imperium", "junction_headquarters")]
    available = frozenset({override})

    assert image_filename("imperium", "junction_headquarters", available) == override


def test_image_filename_ignores_the_default_name_when_an_override_exists() -> None:
    default = default_filename("imperium", "junction_headquarters")
    override = FILENAME_OVERRIDES[("imperium", "junction_headquarters")]
    available = frozenset({default, override})

    assert image_filename("imperium", "junction_headquarters", available) == override


def test_image_filename_returns_none_when_the_file_is_absent() -> None:
    available: frozenset[str] = frozenset()

    assert image_filename("imperium", "maula_pistol", available) is None


def test_image_filename_returns_none_for_known_missing_ids_even_if_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The set is empty today; the mechanism is exercised with a stand-in.
    assert not KNOWN_MISSING
    monkeypatch.setattr(images, "KNOWN_MISSING", frozenset({("other", "dagger")}))
    available = frozenset({FILENAME_OVERRIDES[("other", "dagger")]})

    assert image_filename("other", "dagger", available) is None


def test_base_game_starting_card_scans_stand_in_for_uprising_reprints() -> None:
    available = frozenset(
        {
            "dune-imperium-other-dagger.webp",
            "dune-imperium-other-diplomacy.webp",
            "dune-imperium-other-dune-the-desert-planet.webp",
            "dune-imperium-other-reconnaissance.webp",
        }
    )
    for content_id, filename in (
        ("dagger", "dune-imperium-other-dagger.webp"),
        ("diplomacy", "dune-imperium-other-diplomacy.webp"),
        ("dune_the_desert_planet", "dune-imperium-other-dune-the-desert-planet.webp"),
        ("reconnaissance", "dune-imperium-other-reconnaissance.webp"),
    ):
        assert image_filename("other", content_id, available) == filename


def test_known_missing_and_overrides_do_not_overlap() -> None:
    assert not KNOWN_MISSING & FILENAME_OVERRIDES.keys()


def test_required_images_cover_every_displayable_content_id() -> None:
    entries = required_images()
    keys = {(kind, content_id) for kind, content_id, _ in entries}
    filenames = [filename for _, _, filename in entries]

    # 54 imperium + 39 intrigue + 20 contracts + 16 conflicts + 22 spaces
    # + 10 leader faces + 7 starting + 2 reserve.
    assert len(entries) == 170
    assert len(set(filenames)) == len(filenames)
    assert not keys & KNOWN_MISSING
    assert keys == {
        key for key in _all_content_ids() if key not in KNOWN_MISSING
    }
    available = frozenset(filenames)
    for kind, content_id, filename in entries:
        assert image_filename(kind, content_id, available) == filename


@pytest.mark.skipif(
    not CACHE_DIR.is_dir(),
    reason="Dune Cards Hub image cache is not checked out",
)
def test_every_content_id_resolves_or_is_known_missing() -> None:
    available = frozenset(path.name for path in CACHE_DIR.iterdir())

    for kind, content_id in _all_content_ids():
        resolved = image_filename(kind, content_id, available)
        assert resolved is not None or (kind, content_id) in KNOWN_MISSING, (
            f"{kind}:{content_id} has no cache file and is not KNOWN_MISSING"
        )
    for _, _, filename in required_images():
        assert filename in available, filename
