"""Pictures for the Arrakeen Scouts card the browser UI lays over the board.

While the Scouts step resolves an item (``docs/rules/arrakeen-scouts.md``
3절; the public ``scouts_item`` of the view), the play UI shows it as one
large card over the board, laid out like Dire Wolf Game Room's reveal page
(user request 2026-10-11): a header band with the item's kind and name, a
painting for the kind on the left and a parchment with the item's lines on
the right. The lines are this project's own paraphrase (``display.scouts``),
never the app's text.

The pictures are the app's, written by ``scripts/dwgr/dwgr_scouts_ui.py``
into the owner's private assets checkout under ``cards/app/scouts/`` and
served from the card-image mount. They are copyrighted artwork and never
live in this repository, the same policy as ``display.card_backs``. Each
stands alone: without a picture the UI draws that part in CSS.
"""

from typing import Final

# Where the pictures lie under the card-image directory (``assets/cards``).
SCOUTS_ART_DIR: Final = "app/scouts"

# The play UI's name of each picture: one painting per item kind (the kinds
# of ``catalog.scouts_items``), then the pieces every card shares.
SCOUTS_ART_KINDS: Final[tuple[str, ...]] = (
    "mission",
    "event",
    "auction",
    "sale",
    "subcommittee",
)
SCOUTS_ART_NAMES: Final[tuple[str, ...]] = (
    *SCOUTS_ART_KINDS,
    # the parchment holding the item's lines
    "back",
    # the header band: the dark strip behind the kind, the blue one behind
    # the name
    "header_upper",
    "header_lower",
    # the bar between two lines
    "or_backer",
    # the card's background
    "starfield",
)


def scouts_art_filename(name: str) -> str:
    """Return the filename of one Scouts card picture."""

    return f"{name}.webp"


def available_scouts_art(files: frozenset[str]) -> dict[str, str]:
    """Return ``{name: "app/scouts/<file>"}`` for the pictures in ``files``.

    ``files`` is the listing of the local ``cards/app/scouts`` directory;
    the paths are relative to the card-image directory, in
    ``SCOUTS_ART_NAMES`` order.
    """

    return {
        name: f"{SCOUTS_ART_DIR}/{scouts_art_filename(name)}"
        for name in SCOUTS_ART_NAMES
        if scouts_art_filename(name) in files
    }
