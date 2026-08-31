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
