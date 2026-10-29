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

``path`` is language neutral; the language directory is chosen here, per
file, in the order given: the play server resolves once for each UI
language, English first (``en/<path>``, else ``ko/<path>``) and Korean
first, and the page shows the picture of its language. Within a language
the face drawn from the Steam app's card templates
(``app/<language>/<path>`` with a ``.webp`` suffix, written by
``scripts/dwgr/app_cards.py``) comes before the scan, because it is
sharper; so the Korean order is ``app/ko``, ``ko``, ``app/en``, ``en``.
Leader faces have no app template: ``scripts/dwgr/app_leaders.py``
assembles them from the app's two layers of the printed painting and a
frame drawn to the scans' 1460x1020, so ``display.leader_layout``'s
percentages hold for either picture (Reverend Mother Jessica, with no
Korean card, has only an English face).
A picture laid on the printed board scan (a Leader's own tile such as
Tuek's Sietch, Immortality's Research Station overlay) must keep the
printed tile's shape, which the app's board-space renders do not have
(about 2.37:1 against the print's 1.84:1 and 1.77:1), so the play server
resolves those a second time with ``app_renders=False``: scans only, in
the same language order (``ko``, ``en`` for the Korean UI).
Only entries of the indexed sets (Uprising, and Bloodlines for the
``bloodlines`` option) that carry a ``content_id`` are indexed (Rise of
Ix's 80 since stage P5f; Epic Game Mode's two cards had theirs before);
the other sets in the manifest are archived for future expansions. The original game's set
(``base``) names its own prints since stage P5d of
docs/base-game-and-ix-plan.md; its starting cards and the three spaces it
shares with Uprising are Uprising's prints and keep Uprising's entries.
The manifest's ``starting`` and ``reserve`` kinds both map to the
catalog's ``other`` kind (starting and Reserve cards), and its ``promo``
kind (the promo Imperium cards) to ``imperium``.
"""

import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Final

MANIFEST_FILENAME: Final = "manifest.json"
UPRISING_SET: Final = "uprising"
# Rise of Ix's entries carry content ids since stage P5f (assets manifest;
# Epic Game Mode's two cards, Control the Spice and Economic Supremacy, had
# theirs before).
INDEXED_SETS: Final = frozenset(
    {UPRISING_SET, "base", "bloodlines", "immortality", "rise-of-ix"}
)
DEFAULT_LANGUAGES: Final[tuple[str, ...]] = ("ko", "en")
# Faces drawn from the Steam app's templates, preferred over the scans.
APP_RENDER_DIR: Final = "app"

# Manifest kind -> catalog kind. Every other kind keeps its name.
_CATALOG_KIND: Final[Mapping[str, str]] = MappingProxyType(
    {"starting": "other", "reserve": "other", "promo": "imperium"}
)

# The Tech Module's Ixian Embassy board, keyed like the other one-off
# images under the ``other`` kind.
IXIAN_EMBASSY_IMAGE_ID: Final = "ixian_embassy_board"

# Immortality's Research Station overlay tile, keyed under ``location``
# beside the printed space it covers (``research_station``).
RESEARCH_STATION_OVERLAY_IMAGE_ID: Final = "research_station_overlay"

type ImageKey = tuple[str, str]
"""``(catalog kind, content_id)``: the key the display catalog resolves."""


def load_card_manifest(path: Path) -> Mapping[ImageKey, str]:
    """Return ``{(catalog kind, content_id): language-neutral path}``.

    Reads one ``manifest.json``; entries outside the indexed sets or
    without a ``content_id`` are ignored. A duplicate key is an error in
    the manifest, not a tie to break silently.
    """

    document = json.loads(path.read_text(encoding="utf-8"))
    index: dict[ImageKey, str] = {}
    for entry in document["entries"]:
        content_id = entry.get("content_id")
        if entry.get("set") not in INDEXED_SETS or not content_id:
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
    *,
    app_renders: bool = True,
) -> Mapping[ImageKey, str]:
    """Return ``{key: "<language>/<path>"}`` for every image file present.

    ``languages`` is tried in order per file (by default the Korean
    picture first, the English one as fallback), each language's app
    render before its scan, and keys whose file
    exists in no language are dropped so
    the catalog never links to a missing file. ``app_renders=False``
    skips the ``app/`` renders and resolves the scans alone (the board
    pieces laid on the printed scan; see the module docstring). A
    missing directory or manifest yields an empty mapping.
    """

    manifest = cards_dir / MANIFEST_FILENAME
    if not manifest.is_file():
        return MappingProxyType({})
    resolved: dict[ImageKey, str] = {}
    for key, relative in load_card_manifest(manifest).items():
        rendered = PurePosixPath(relative).with_suffix(".webp").as_posix()
        for language in languages:
            candidates = [f"{language}/{relative}"]
            if app_renders:
                candidates.insert(0, f"{APP_RENDER_DIR}/{language}/{rendered}")
            found = next(
                (
                    candidate
                    for candidate in candidates
                    if (cards_dir / candidate).is_file()
                ),
                None,
            )
            if found is not None:
                resolved[key] = found
                break
    return MappingProxyType(resolved)


def required_image_keys() -> tuple[ImageKey, ...]:
    """Return every ``(catalog kind, content_id)`` the catalog can show.

    This is the coverage contract for the manifest: a test against a
    checked-out assets repository asserts each key resolves to a file.
    The content manifests are imported lazily so the loader above stays
    importable without the full content package.
    """

    from dune_imperium.content.bloodlines.sardaukar import SKILLS
    from dune_imperium.content.bloodlines.tech import TECH_TILES
    from dune_imperium.content.immortality.tleilaxu import (
        RECLAIMED_FORCES,
        TLEILAXU_CARDS,
    )
    from dune_imperium.content.imperium.board import IMPERIUM_ONLY_BOARD_SPACES
    from dune_imperium.content.imperium.conflicts import IMPERIUM_CONFLICTS
    from dune_imperium.content.imperium.imperium import IMPERIUM_BASE_CARDS
    from dune_imperium.content.imperium.intrigue import IMPERIUM_INTRIGUE_CARDS
    from dune_imperium.content.imperium.leaders import IMPERIUM_LEADERS
    from dune_imperium.content.imperium.reserve import IMPERIUM_RESERVE_STACKS
    from dune_imperium.content.uprising.board import BOARD_SPACES
    from dune_imperium.content.uprising.conflicts import CONFLICTS
    from dune_imperium.content.uprising.contracts import CONTRACTS
    from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS
    from dune_imperium.content.uprising.intrigue import INTRIGUE_CARDS
    from dune_imperium.content.uprising.leaders import LEADERS
    from dune_imperium.content.uprising.objectives import OBJECTIVES
    from dune_imperium.content.uprising.reserve import RESERVE_STACKS
    from dune_imperium.content.uprising.starting_cards import STARTING_CARDS_BY_ID

    keys: list[ImageKey] = []
    keys += [("imperium", entry.card.card_id) for entry in IMPERIUM_CARDS]
    keys += [("intrigue", entry.card.card_id) for entry in INTRIGUE_CARDS]
    # A second copy of a tile shows the first copy's face.
    keys += [
        ("contract", contract.card.card_id)
        for contract in CONTRACTS
        if contract.copy_of is None
    ]
    keys += [("conflict", conflict.card.card_id) for conflict in CONFLICTS]
    keys += [("objective", objective.objective_id) for objective in OBJECTIVES]
    keys += [("location", space.space_id) for space in BOARD_SPACES]
    for leader in LEADERS:
        keys.append(("leader", leader.leader_id))
        if leader.alternate_face_id is not None:
            keys.append(("leader", leader.alternate_face_id))
    keys += [("other", card_id) for card_id in STARTING_CARDS_BY_ID]
    keys += [("other", stack.card.card_id) for stack in RESERVE_STACKS]
    # Bloodlines: the Skill and Tech tile faces and the Ixian Embassy board.
    keys += [("skill", skill.skill_id) for skill in SKILLS]
    keys += [("tech", tile.tech_id) for tile in TECH_TILES]
    keys.append(("other", IXIAN_EMBASSY_IMAGE_ID))
    # Immortality: the Tleilaxu deck (its promo included) and Reclaimed
    # Forces; its Imperium and Intrigue cards are in the lists above.
    keys += [("tleilaxu", entry.card.card_id) for entry in TLEILAXU_CARDS]
    keys.append(("tleilaxu", RECLAIMED_FORCES.card.card_id))
    keys.append(("location", RESEARCH_STATION_OVERLAY_IMAGE_ID))
    # The original game's own prints (its promos are Imperium cards, its
    # Reserve the ``other`` kind, as Uprising's).
    keys += [("imperium", entry.card.card_id) for entry in IMPERIUM_BASE_CARDS]
    keys += [("intrigue", entry.card.card_id) for entry in IMPERIUM_INTRIGUE_CARDS]
    keys += [("conflict", conflict.card.card_id) for conflict in IMPERIUM_CONFLICTS]
    keys += [("leader", leader.leader_id) for leader in IMPERIUM_LEADERS]
    keys += [("location", space.space_id) for space in IMPERIUM_ONLY_BOARD_SPACES]
    keys += [("other", stack.card.card_id) for stack in IMPERIUM_RESERVE_STACKS]
    return tuple(dict.fromkeys(keys))
