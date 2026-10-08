"""Card back pictures for the face-down decks the browser UI draws.

A face-down deck shows the back its cards share: the Imperium deck and the
Tleilaxu deck the Imperium back, the Intrigue deck its own, and the Conflict
deck the back of its top card, which carries that card's tier: "Conflict
카드를 I, II, III 뒷면별로 나눈다." [Main p. 4]
(``docs/rules/setup-and-game-flow.md``). Kota Odax of Ix keeps a Tech tile
face down ("Place one face down here" [card face]), which shows the Tech
back.

The pictures are the Steam app's backs, written by ``scripts/dwgr/
app_assets.py backs`` into the owner's private assets checkout under
``tokens/`` (``back_<kind>.webp``). They are copyrighted artwork and never
live in this repository, the same policy as ``display.token_images``.
Without a kind's picture the UI keeps its earlier drawing for that deck.
"""

from typing import Final

CARD_BACK_KINDS: Final[tuple[str, ...]] = (
    "imperium",
    "intrigue",
    "conflict_1",
    "conflict_2",
    "conflict_3",
    "tech",
)


def card_back_filename(kind: str) -> str:
    """Return the filename of one kind of card back's picture."""

    return f"back_{kind}.webp"


def available_card_backs(files: frozenset[str]) -> dict[str, str]:
    """Return ``{kind: filename}`` for the card backs pictured in ``files``.

    ``files`` is the listing of the local token directory. Each kind stands
    alone: a missing Conflict III back only sends a tier III deck back to
    the drawn box.
    """

    return {
        kind: card_back_filename(kind)
        for kind in CARD_BACK_KINDS
        if card_back_filename(kind) in files
    }
