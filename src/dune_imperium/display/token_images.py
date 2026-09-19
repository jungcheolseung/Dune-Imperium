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

# The Shield Wall token's picture in the same directory: on the board until
# a player removes it, "제거된 Shield Wall은 게임이 끝날 때까지 돌아오지 않는다"
# [Main p. 10] (docs/rules/player-turns.md).
SHIELD_WALL_TOKEN_FILENAME: Final = "shield_wall.png"

# The Maker Hooks token, the same for every player: "Take a Maker Hooks token
# from the bank, if you don't already have one. Place it on your garrison"
# [Main p. 20]. The picture has the handle along its bottom edge and the hook
# at the right; ``board_layout.MAKER_HOOKS_TURNS`` turns it into each
# garrison's printed slot.
MAKER_HOOKS_TOKEN_FILENAME: Final = "maker_hooks.png"

# The four Alliance tokens, one per Faction (``Faction`` values): on the marked
# area of the Faction's Influence track until a player earns the Alliance,
# then in that player's supply [Main pp. 4, 7]. The pictures are round tokens
# on a black square; the UI cuts the circle out.
ALLIANCE_TOKEN_FACTIONS: Final[tuple[str, ...]] = (
    "emperor",
    "spacing_guild",
    "bene_gesserit",
    "fremen",
)


def alliance_token_filename(faction: str) -> str:
    """Return the filename of one Faction's Alliance token picture."""

    return f"alliance_{faction}.jpg"


def available_alliance_tokens(files: frozenset[str]) -> dict[str, str]:
    """Return ``{faction: filename}`` for the Alliance pictures in ``files``."""

    return {
        faction: alliance_token_filename(faction)
        for faction in ALLIANCE_TOKEN_FACTIONS
        if alliance_token_filename(faction) in files
    }

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
