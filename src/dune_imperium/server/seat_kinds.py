"""Which seats a table of each base game may hold.

The one table both the server (``POST /games``, a save's restore) and the
setup screen (``GET /whoami`` ``seat_kinds``) read, so the browser never
offers a seat the server would refuse (docs/base-game-and-ix-plan.md 18.5 3).

Uprising takes every seat kind. The original game takes the human and the
two AI seats that play its cards: the heuristic and the random seat (the
P3d soak finished 5,000 original games with them, plan 16.12). The app AI
answers about 40% of an original game's decisions at random, not knowing
its cards, and the search AI's networks never trained on it (plan 18.1),
so neither sits there yet. When the app AI's port of the original game
lands (stage P6), its three kinds join the original game's row here, and
nothing else needs to change (user decision 2026-10-29, via the
coordinator).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.config import BaseGame
from dune_imperium.server.persistence import JsonObject, JsonValue

# A base game's allowed seat kinds as the setup screen names them (``search``
# for the server's own search seat, ``checkpoint`` for a file); None: every
# kind the server can seat.
TABLE_SEAT_KINDS: Final[Mapping[BaseGame, frozenset[str] | None]] = (
    MappingProxyType(
        {
            BaseGame.UPRISING: None,
            BaseGame.IMPERIUM: frozenset({"human", "heuristic", "random"}),
        }
    )
)


def seat_kind_allowed(assignment: str, base_game: BaseGame) -> bool:
    """Whether a table of ``base_game`` may seat ``assignment``.

    ``assignment`` is the seat as the server keeps it: ``human``, a
    registry kind, or ``search:<path>`` / ``checkpoint:<path>`` (named
    ``search`` / ``checkpoint`` in the table, as the setup screen offers
    them).
    """

    allowed = TABLE_SEAT_KINDS[base_game]
    if allowed is None:
        return True
    return assignment.split(":", 1)[0] in allowed


def seat_kinds_payload() -> JsonObject:
    """The table for ``GET /whoami``: base game -> sorted kinds, or null."""

    payload: JsonObject = {}
    for base_game, kinds in TABLE_SEAT_KINDS.items():
        listed: list[JsonValue] | None = None if kinds is None else [*sorted(kinds)]
        payload[base_game.value] = listed
    return payload
