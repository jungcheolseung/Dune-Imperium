"""Local game-icon filename mapping extracted from the official rulebook.

``RULEBOOK_ICON_SOURCES`` records, for every named game icon, its
``(page_number, image_xref)`` location inside the pinned "Uprising Main
Rulebook" PDF (``scripts/official-rule-sources.json`` key ``main``, sha256
``0a8daa36f73c09316143d05bbd5d845183d1ae6f56ce211d93c59b360074f7db``). Page
numbers are 1-based; xrefs were read from that exact file with PyMuPDF
(``page.get_image_info(xrefs=True)``) and are only valid for that file
version — if the pinned PDF is ever updated, this table must be
re-extracted, not reused.

``scripts/extract_rulebook_icons.py`` uses this table to crop each icon out
of the rulebook and key out its background, producing one transparent PNG
per name in the gitignored ``downloads/icons`` directory. The icons are
copyrighted Dire Wolf Digital artwork; they are extracted for machine-local
UI use only and are never committed to this repository, the same policy as
the Dune Cards Hub card images in ``dune_imperium.display.images``.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

RULEBOOK_ICON_SOURCES: Final[Mapping[str, tuple[int, int]]] = MappingProxyType(
    {
        "agent": (20, 971),
        "battle_crysknife": (20, 972),
        "battle_ornithopter": (20, 973),
        "battle_desert_mouse": (20, 974),
        "battle_wild": (20, 976),
        "contract": (20, 977),
        "control": (20, 978),
        "discard": (20, 979),
        "draw": (20, 980),
        "intrigue": (20, 981),
        "influence_emperor": (20, 982),
        "influence_spacing_guild": (20, 983),
        "influence_bene_gesserit": (20, 984),
        "influence_fremen": (20, 985),
        "influence_any": (20, 986),
        "influence_any_two": (20, 987),
        "influence_lose": (20, 988),
        "maker": (20, 989),
        "maker_hooks": (20, 990),
        "arrow_right": (20, 991),
        "arrow_down": (20, 992),
        "persuasion": (20, 994),
        "recall_agent": (20, 995),
        "recall_spy": (20, 996),
        "solari": (20, 997),
        "spice": (20, 998),
        "water": (20, 999),
        "sandworm": (20, 1000),
        "shield_wall": (20, 1001),
        "signet_ring": (20, 1002),
        "spy": (20, 1003),
        "steal_intrigue": (20, 1008),
        "sword": (20, 1009),
        "trash_intrigue": (20, 1010),
        "trash": (20, 1011),
        "troop": (20, 1012),
        "victory_point": (20, 1014),
        "agent_icon_emperor": (9, 1592),
        "agent_icon_spacing_guild": (9, 1593),
        "agent_icon_bene_gesserit": (9, 1594),
        "agent_icon_fremen": (9, 1596),
        "agent_icon_landsraad": (9, 1597),
        "agent_icon_city": (9, 1598),
        "agent_icon_spice_trade": (9, 1599),
        "agent_icon_spy": (9, 1600),
    }
)

ICON_NAMES: Final[tuple[str, ...]] = tuple(RULEBOOK_ICON_SOURCES.keys())


def icon_filename(name: str) -> str:
    """Return the extracted-icon filename for one icon name."""

    return f"{name}.png"


def available_icons(files: frozenset[str]) -> dict[str, str]:
    """Return ``{name: filename}`` for every icon whose PNG is in ``files``.

    ``files`` is the listing of a local icon directory (e.g. the gitignored
    ``downloads/icons``); names without a matching file are simply absent
    from the result.
    """

    result: dict[str, str] = {}
    for name in ICON_NAMES:
        filename = icon_filename(name)
        if filename in files:
            result[name] = filename
    return result
