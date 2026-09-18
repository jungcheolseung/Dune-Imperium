"""Player-colour token images for the markers the browser UI draws on the board.

The Combat marker is a two-sided token in each player's colour: "strength를
공개하고 Combat marker를 Combat track의 해당 칸으로 옮긴다. 20을 넘으면 marker의
`+20` 면을 사용해 track 처음부터 남은 수치를 센다." [Main p. 12]
(``docs/rules/combat-and-round-end.md``). The UI shows a picture of each
face when the owner's private assets checkout carries them under
``tokens/`` (``strength_<colour>.png`` and ``strength_<colour>_plus20.png``);
the pictures are copyrighted artwork and never live in this repository,
the same policy as the card scans in ``dune_imperium.display.images`` and
the rulebook icons in ``dune_imperium.display.icons``. Without them the UI
keeps its drawn seat token.
"""

from typing import Final

# The token colour of each seat, in seat order. The browser UI tints
# everything else a seat owns with ``SEAT_COLORS`` in ``server/static/app.js``
# (blue, red, green, yellow); keep the two tables in step.
STRENGTH_TOKEN_COLORS: Final[tuple[str, ...]] = ("blue", "red", "green", "yellow")


def strength_token_filenames(color: str) -> tuple[str, str]:
    """Return the ``(sword face, +20 face)`` filenames of one colour's token."""

    return f"strength_{color}.png", f"strength_{color}_plus20.png"


def available_strength_tokens(
    files: frozenset[str],
) -> tuple[tuple[str, str] | None, ...]:
    """Return each seat's ``(sword face, +20 face)`` filenames, or ``None``.

    ``files`` is the listing of a local token directory (e.g. the
    gitignored ``assets/tokens``). A seat gets its pictures only when both
    faces are there: a token that could show its sword but not flip would
    misreport every strength beyond 20.
    """

    result: list[tuple[str, str] | None] = []
    for color in STRENGTH_TOKEN_COLORS:
        front, plus20 = strength_token_filenames(color)
        result.append((front, plus20) if front in files and plus20 in files else None)
    return tuple(result)
