"""Card image lookup through the private asset manifest.

Card scans are copyrighted and never live in this repository. They are
kept in the owner's private ``Dune-Imperium-assets`` repository under
``cards/<language>/<set>/<kind>/<printed name>.<ext>`` (for example
``cards/en/uprising/imperium/Sardaukar Soldier.webp``) together with
``cards/manifest.json``, which is the only mapping between those human
file names and the engine's content IDs. The main repository mounts that
``cards`` directory (default ``assets/cards``; ``assets`` is a symlink to
the assets checkout) and reads the manifest at server start; without it the catalog
simply carries no images and the UI shows text.

Manifest entries look like::

    {"path": "uprising/imperium/Sardaukar Soldier.webp",
     "set": "uprising", "kind": "imperium", "name": "Sardaukar Soldier",
     "name_source": "engine", "content_id": "sardaukar_soldier",
     "source": {"site": "dunecardshub", "file": "...", "url": "...",
                "sha256": "..."}}

``path`` is language neutral; the language directory is chosen here so a
Korean scan at ``ko/<path>`` is preferred per file and falls back to
``en/<path>``. Only entries of the Uprising set that carry a
``content_id`` are indexed; the other sets in the manifest are archived
for future expansions. The manifest's ``starting`` and ``reserve`` kinds
both map to the catalog's ``other`` kind (starting and Reserve cards).
"""

import json
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Final

MANIFEST_FILENAME: Final = "manifest.json"
UPRISING_SET: Final = "uprising"
DEFAULT_LANGUAGES: Final[tuple[str, ...]] = ("ko", "en")

# Manifest kind -> catalog kind. Every other kind keeps its name.
_CATALOG_KIND: Final[Mapping[str, str]] = MappingProxyType(
    {"starting": "other", "reserve": "other"}
)

type ImageKey = tuple[str, str]
"""``(catalog kind, content_id)``: the key the display catalog resolves."""


def load_card_manifest(path: Path) -> Mapping[ImageKey, str]:
    """Return ``{(catalog kind, content_id): language-neutral path}``.

    Reads one ``manifest.json``; entries outside the Uprising set or
    without a ``content_id`` are ignored. A duplicate key is an error in
    the manifest, not a tie to break silently.
    """

    document = json.loads(path.read_text(encoding="utf-8"))
    index: dict[ImageKey, str] = {}
    for entry in document["entries"]:
        content_id = entry.get("content_id")
        if entry.get("set") != UPRISING_SET or not content_id:
            continue
        kind = _CATALOG_KIND.get(entry["kind"], entry["kind"])
        key = (kind, content_id)
        if key in index and index[key] != entry["path"]:
            raise ValueError(f"manifest maps {key} to two paths")
        index[key] = entry["path"]
    return MappingProxyType(index)


def resolve_card_images(
    cards_dir: Path,
    languages: tuple[str, ...] = DEFAULT_LANGUAGES,
) -> Mapping[ImageKey, str]:
    """Return ``{key: "<language>/<path>"}`` for every image file present.

    ``languages`` is tried in order per file (Korean scan first, English
    fallback), and keys whose file exists in no language are dropped so
    the catalog never links to a missing file. A missing directory or
    manifest yields an empty mapping.
    """

    manifest = cards_dir / MANIFEST_FILENAME
    if not manifest.is_file():
        return MappingProxyType({})
    resolved: dict[ImageKey, str] = {}
    for key, relative in load_card_manifest(manifest).items():
        for language in languages:
            if (cards_dir / language / relative).is_file():
                resolved[key] = f"{language}/{relative}"
                break
    return MappingProxyType(resolved)


def required_image_keys() -> tuple[ImageKey, ...]:
    """Return every ``(catalog kind, content_id)`` the catalog can show.

    This is the coverage contract for the manifest: a test against a
    checked-out assets repository asserts each key resolves to a file.
    The content manifests are imported lazily so the loader above stays
    importable without the full content package.
    """

    from dune_imperium.content.uprising.board import BOARD_SPACES
    from dune_imperium.content.uprising.conflicts import CONFLICTS
    from dune_imperium.content.uprising.contracts import CONTRACTS
    from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS
    from dune_imperium.content.uprising.intrigue import INTRIGUE_CARDS
    from dune_imperium.content.uprising.leaders import LEADERS
    from dune_imperium.content.uprising.reserve import RESERVE_STACKS
    from dune_imperium.content.uprising.starting_cards import STARTING_CARDS_BY_ID

    keys: list[ImageKey] = []
    keys += [("imperium", entry.card.card_id) for entry in IMPERIUM_CARDS]
    keys += [("intrigue", entry.card.card_id) for entry in INTRIGUE_CARDS]
    keys += [("contract", contract.card.card_id) for contract in CONTRACTS]
    keys += [("conflict", conflict.card.card_id) for conflict in CONFLICTS]
    keys += [("location", space.space_id) for space in BOARD_SPACES]
    for leader in LEADERS:
        keys.append(("leader", leader.leader_id))
        if leader.alternate_face_id is not None:
            keys.append(("leader", leader.alternate_face_id))
    keys += [("other", card_id) for card_id in STARTING_CARDS_BY_ID]
    keys += [("other", stack.card.card_id) for stack in RESERVE_STACKS]
    return tuple(dict.fromkeys(keys))
