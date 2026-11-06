"""Local filename mapping for the action log's own pictures.

The Steam Dune: Imperium app's Action Log puts one icon beside each entry.
Most of them are the same artwork as the rulebook-icon set
(``dune_imperium.display.icons``), which the play UI's log reuses, and the
Alliance tokens (``display.token_images``). ``LOG_ICON_NAMES`` names the
pictures that set lacks: the Conflict's crossed blades, the Round numerals,
the reshuffle, the log's red trash cross, the Intrigue glyph and played card,
the troop deploy and retreat badges, the winner's wreath, the four Factions'
Influence-down marks, and the Tleilaxu, research, Family Atomics and tech
marks. Which event shows which picture is the client's table
(``static/log_icons.js``), checked against both name sets by
``tests/server/test_log_icon_table.py``.

``scripts/dwgr/app_log_icons.py`` writes each picture from the installed
app as ``log_<name>.png`` into the gitignored ``assets/icons`` directory,
beside the rulebook icons. They are copyrighted Dire Wolf Digital artwork
and live in the owner's private assets repository, never in this one, the
same policy as ``display.icons``. Without them the log shows text alone.
"""

from typing import Final

ROUND_LOG_ICONS: Final[int] = 10
"""The app has Round numerals 1-10; a later round keeps the text mark."""

LOG_ICON_NAMES: Final[tuple[str, ...]] = (
    "conflict",
    *(f"round_{number}" for number in range(1, ROUND_LOG_ICONS + 1)),
    "reshuffle",
    "card_trashed",
    "intrigue_played",
    "intrigue",
    "troop_deploy",
    "troop_retreat",
    "vp_winner",
    "influence_down_emperor",
    "influence_down_spacing_guild",
    "influence_down_bene_gesserit",
    "influence_down_fremen",
    "tleilaxu",
    "research",
    "family_atomics",
    "tech",
)


def log_icon_filename(name: str) -> str:
    """Return the local filename of one log picture."""

    return f"log_{name}.png"


def available_log_icons(files: frozenset[str]) -> dict[str, str]:
    """Return ``{name: filename}`` for every log picture present in ``files``.

    ``files`` is the listing of the local icon directory (the gitignored
    ``assets/icons``); names without a matching file are absent from the
    result, so a machine without the pictures shows the text-only log.
    """

    result: dict[str, str] = {}
    for name in LOG_ICON_NAMES:
        filename = log_icon_filename(name)
        if filename in files:
            result[name] = filename
    return result
