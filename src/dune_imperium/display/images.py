"""Local Dune Cards Hub image filename mapping for Uprising content.

Filenames are drawn from the gitignored ``downloads/dunecardshub/cards``
cache (populated by fetching https://dunecardshub.com/uprising per
``AGENTS.md``), named ``uprising-{kind}-{slug}.webp`` where ``slug`` is
usually the content ID with underscores replaced by hyphens. Kinds:
``imperium``, ``intrigue``, ``contract``, ``conflict``, ``location`` (board
spaces), ``leader``, and ``other`` (starting and Reserve cards).

``FILENAME_OVERRIDES`` and ``KNOWN_MISSING`` were derived empirically by
listing the cache and cross-checking it against every content ID in the
Uprising manifests; they record upstream filename typos and content that has
no published image, not a rules judgement.

``required_images`` enumerates every file the display catalog can reference;
``scripts/fetch_card_images.py`` downloads exactly that set into the local
cache on a machine that does not have it yet.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final


def default_filename(kind: str, content_id: str) -> str:
    """Return the cache filename this content ID would have with no override."""

    return f"uprising-{kind}-{content_id.replace('_', '-')}.webp"


FILENAME_OVERRIDES: Final[Mapping[tuple[str, str], str]] = MappingProxyType(
    {
        # Upstream Dune Cards Hub filename typos (verified against the cache).
        ("imperium", "junction_headquarters"): (
            "uprising-imperium-junction-headquaters.webp"
        ),
        ("imperium", "treacherous_maneuver"): (
            "uprising-imperium-theacherous-maneuver.webp"
        ),
        ("intrigue", "ornithopter"): "uprising-intrigue-ornitopter.webp",
        ("location", "high_council"): "uprising-location-hight-council.webp",
        ("location", "arrakeen"): "uprising-location-arakeen.webp",
        ("location", "deep_desert"): "uprising-location-deet-desert.webp",
        # Dune Cards Hub publishes several art variants of these shared
        # starting cards (e.g. "...-emperor.webp" and "...-muad-dib.webp");
        # the "emperor" variant is an arbitrary cosmetic pick.
        ("other", "convincing_argument"): (
            "uprising-other-convincing-argument-emperor.webp"
        ),
        ("other", "seek_allies"): "uprising-other-seek-allies-emperor.webp",
        ("other", "signet_ring"): "uprising-other-signet-ring-emperor.webp",
    }
)

KNOWN_MISSING: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("other", "dagger"),
        ("other", "diplomacy"),
        ("other", "dune_the_desert_planet"),
        ("other", "reconnaissance"),
    }
)


def image_filename(
    kind: str, content_id: str, available: frozenset[str]
) -> str | None:
    """Resolve one content ID to its cache filename, or None when absent.

    A content ID in ``KNOWN_MISSING`` always resolves to None, regardless of
    ``available``: no upstream image exists for it.
    """

    key = (kind, content_id)
    if key in KNOWN_MISSING:
        return None
    filename = FILENAME_OVERRIDES.get(key, default_filename(kind, content_id))
    return filename if filename in available else None


def required_images() -> tuple[tuple[str, str, str], ...]:
    """Return ``(kind, content_id, filename)`` for every displayable image.

    This is the exact file set the display catalog can reference: every
    Uprising content ID across all catalog sections, minus ``KNOWN_MISSING``.
    The content manifests are imported lazily so the mapping helpers above
    stay importable without pulling the full content package.
    """

    from dune_imperium.content.uprising.board import BOARD_SPACES
    from dune_imperium.content.uprising.conflicts import CONFLICTS
    from dune_imperium.content.uprising.contracts import CONTRACTS
    from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS
    from dune_imperium.content.uprising.intrigue import INTRIGUE_CARDS
    from dune_imperium.content.uprising.leaders import LEADERS
    from dune_imperium.content.uprising.reserve import RESERVE_STACKS
    from dune_imperium.content.uprising.starting_cards import STARTING_CARDS_BY_ID

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
    ids += [("other", card_id) for card_id in STARTING_CARDS_BY_ID]
    ids += [("other", stack.card.card_id) for stack in RESERVE_STACKS]

    entries: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for key in ids:
        if key in seen or key in KNOWN_MISSING:
            continue
        seen.add(key)
        kind, content_id = key
        filename = FILENAME_OVERRIDES.get(
            key, default_filename(kind, content_id)
        )
        entries.append((kind, content_id, filename))
    return tuple(entries)
