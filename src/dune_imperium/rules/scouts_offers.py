"""Arrakeen Scouts: queue a subcommittee offer (no rule imports, so the
seat-taking modules can call it without an import cycle)."""

from dataclasses import replace
from typing import Final

from dune_imperium.core.state import GameState

# The pseudo space of an Agent in the Conflict (Into the Fray): a recall
# target, and the ``exclude_space`` of an offer whose seat-taking Agent went
# there this turn.
CONFLICT_AGENT: Final = "conflict"


def queue_subcommittee_offer(
    state: GameState,
    player: int,
    *,
    source: str,
    exclude_space: str,
    turn_closed: bool,
) -> GameState:
    """Queue the seat's one subcommittee offer on taking a High Council seat.

    Taking a High Council seat lets the seat join one still-empty
    subcommittee (docs/rules/arrakeen-scouts.md 4, OQ-076).
    """

    if not state.config.arrakeen_scouts:
        return state
    entry = (player, source, exclude_space, turn_closed)
    return replace(
        state, scouts_subcommittee_offers=(*state.scouts_subcommittee_offers, entry)
    )
