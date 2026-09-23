"""The collector interface shared by the tip-census modules.

A collector watches one game transition at a time and, when the game is
FINISHED, returns one column dict per seat plus one dict of game columns.
Column names are prefixed by the collector's ``name`` in the output rows
(``deck.buys``), so two collectors never collide.

Values a collector returns:

- ``int`` / ``float`` / ``bool``: averaged per agent kind in the summary.
- ``None``: "does not apply to this seat" (e.g. the round Swordmaster was
  taken when it never was); left out of that column's mean and counted in n.
- ``dict[str, int | float]``: a tally (e.g. trashed card -> count); the
  summary adds them up per kind and divides by seat-games.
- ``list``: kept in the JSONL rows only (per-event detail).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.evaluation.tournament import MatchSpec
from dune_imperium.rules.endgame import FinalStanding

Columns = dict[str, Any]


@dataclass(frozen=True, slots=True)
class Step:
    """One engine transition as the census driver saw it.

    ``owner`` is None for a chance step; ``action`` and ``legal`` are then
    None and ``()``. ``pre`` is the state the decision was taken in, ``post``
    the state after ``engine.apply``; ``events`` are that apply's events.
    """

    pre: GameState
    post: GameState
    owner: int | None
    action: DomainAction | None
    legal: tuple[DomainAction, ...]
    events: tuple[GameEvent, ...]


def payload(event: GameEvent) -> dict[str, Any]:
    """The event payload as a dict (payloads are sorted key/value tuples)."""

    return dict(event.payload)


def arguments(action: DomainAction) -> dict[str, Any]:
    """The action arguments as a dict."""

    return dict(action.arguments)


class Collector:
    """Base class: override ``step`` and ``finish``."""

    name = "base"

    def __init__(self, spec: MatchSpec, seats: int) -> None:
        self.spec = spec
        self.seats = seats

    def step(self, s: Step) -> None:
        """Observe one transition. Must not mutate anything in ``s``."""

    def finish(
        self, final: GameState, standings: tuple[FinalStanding, ...]
    ) -> tuple[list[Columns], Columns]:
        """Return (one column dict per seat, game columns)."""

        return [{} for _ in range(self.seats)], {}
