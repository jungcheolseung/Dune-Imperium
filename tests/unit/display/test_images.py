"""Tests for the manifest-based card image index."""

import json
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
from dune_imperium.display.images import (
    load_card_manifest,
    required_image_keys,
    resolve_card_images,
)

CARDS_DIR = Path(__file__).resolve().parents[3] / "downloads" / "cards"


def _all_content_keys() -> set[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    keys += [("imperium", entry.card.card_id) for entry in IMPERIUM_CARDS]
    keys += [("intrigue", entry.card.card_id) for entry in INTRIGUE_CARDS]
    keys += [("contract", contract.card.card_id) for contract in CONTRACTS]
    keys += [("conflict", conflict.card.card_id) for conflict in CONFLICTS]
    keys += [("location", space.space_id) for space in BOARD_SPACES]
    for leader in LEADERS:
        keys.append(("leader", leader.leader_id))
        if leader.alternate_face_id is not None:
            keys.append(("leader", leader.alternate_face_id))
    keys += [("other", entry.card.card_id) for entry in STARTING_DECK]
    keys += [("other", stack.card.card_id) for stack in RESERVE_STACKS]
    return set(keys)


def _entry(
    path: str,
    *,
    kind: str,
    content_id: str | None = None,
    set_name: str = "uprising",
) -> dict[str, object]:
    entry: dict[str, object] = {
        "path": path,
        "set": set_name,
        "kind": kind,
        "name": path.rsplit("/", 1)[-1].rsplit(".", 1)[0],
        "name_source": "engine" if content_id else "upstream-slug",
        "source": {"site": "dunecardshub", "file": "x.webp", "url": "u", "sha256": "0"},
    }
    if content_id:
        entry["content_id"] = content_id
    return entry


def _write_manifest(cards_dir: Path, entries: list[dict[str, object]]) -> Path:
    cards_dir.mkdir(parents=True, exist_ok=True)
    manifest = cards_dir / "manifest.json"
    manifest.write_text(json.dumps({"version": 1, "entries": entries}))
    return manifest


def test_manifest_indexes_uprising_entries_with_a_content_id(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [
            _entry(
                "uprising/imperium/Sardaukar Soldier.webp",
                kind="imperium",
                content_id="sardaukar_soldier",
            ),
            _entry("base/starting/Dagger.webp", kind="starting", content_id="dagger"),
            _entry(
                "uprising/reserve/The Spice Must Flow.webp",
                kind="reserve",
                content_id="the_spice_must_flow",
            ),
            _entry("uprising/six-player/Usul.webp", kind="six-player"),
            _entry(
                "base/imperium/Space Travel.webp",
                kind="imperium",
                content_id="space_travel",
                set_name="base",
            ),
        ],
    )
    index = load_card_manifest(manifest)
    assert dict(index) == {
        ("imperium", "sardaukar_soldier"): "uprising/imperium/Sardaukar Soldier.webp",
        ("other", "dagger"): "base/starting/Dagger.webp",
        ("other", "the_spice_must_flow"): "uprising/reserve/The Spice Must Flow.webp",
    }


def test_manifest_rejects_one_key_with_two_paths(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        [
            _entry("uprising/imperium/A.webp", kind="imperium", content_id="dup"),
            _entry("uprising/imperium/B.webp", kind="imperium", content_id="dup"),
        ],
    )
    with pytest.raises(ValueError, match="two paths"):
        load_card_manifest(manifest)


def test_resolve_prefers_korean_scans_and_drops_missing_files(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path,
        [
            _entry("uprising/imperium/Both.webp", kind="imperium", content_id="both"),
            _entry("uprising/imperium/English.webp", kind="imperium", content_id="en"),
            _entry(
                "uprising/imperium/Missing.webp", kind="imperium", content_id="none"
            ),
        ],
    )
    for relative in (
        "en/uprising/imperium/Both.webp",
        "ko/uprising/imperium/Both.webp",
        "en/uprising/imperium/English.webp",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"img")

    resolved = resolve_card_images(tmp_path)
    assert dict(resolved) == {
        ("imperium", "both"): "ko/uprising/imperium/Both.webp",
        ("imperium", "en"): "en/uprising/imperium/English.webp",
    }
    assert resolve_card_images(tmp_path / "nowhere") == {}


def test_required_image_keys_cover_every_displayable_content_id() -> None:
    keys = required_image_keys()
    # 54 imperium + 39 intrigue + 20 contracts + 16 conflicts + 22 spaces
    # + 10 leader faces + 7 starting + 2 reserve.
    assert len(keys) == 170
    assert len(set(keys)) == len(keys)
    assert set(keys) == _all_content_keys()


@pytest.mark.skipif(
    not (CARDS_DIR / "manifest.json").is_file(),
    reason="card-image assets checkout is not linked at downloads/cards",
)
def test_the_assets_checkout_resolves_every_content_id() -> None:
    resolved = resolve_card_images(CARDS_DIR)
    missing = [key for key in required_image_keys() if key not in resolved]
    assert not missing, missing
    for key, relative in resolved.items():
        assert (CARDS_DIR / relative).is_file(), (key, relative)
    # Every set is self-contained: the Uprising starting deck lives under
    # its own directory (copies of the base-game scans), never the
    # six-player "Commander" variants.
    for content_id in ("dagger", "signet_ring", "convincing_argument"):
        assert resolved[("other", content_id)].startswith("en/uprising/starting/")
