"""Arrakeen Scouts: the subcommittee a new High Council seat may join (no
rule imports, so the seat-taking modules can call it without an import
cycle).

Taking a High Council seat lets the seat join one still-empty subcommittee
(docs/rules/arrakeen-scouts.md 4). The app says the seat joins "when" it
takes the seat (``spice.help.body.uprising``,
``spice.subcommittees.anouncement.description``); the project widens that
to any time in the same turn, as one more effect the seat orders freely
with the others: "You may carry out all these effects in any order."
[Main p. 9] (OQ-076 alternative C, user ruling 2026-09-30, a project
convention). So a seat may take the High Council seat, buy a Tech tile at
the seat's discount ("if you have a High Council seat, each Tech tile costs
you 1 less spice" [Bloodlines p. 7]), and only then choose its
subcommittee:

- at the High Council board space it is one more pending icon of the visit
  (``BOARD_ICON_SUBCOMMITTEE``), offered as ``choose_subcommittee`` /
  ``decline_subcommittee`` beside the visit's other effects;
- through Corrinth City's Reveal choice it stays open in that Reveal turn
  (``GameState.scouts_subcommittee_offers``), which cannot finish until the
  seat joins or declines (``reveal_turn.legal_finish_reveal_actions``).
"""

from dataclasses import replace
from typing import Final

from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState

# The pseudo space of an Agent in the Conflict (Into the Fray): a recall
# target, and the ``exclude_space`` of a subcommittee line whose
# seat-taking Agent went there this turn.
CONFLICT_AGENT: Final = "conflict"

# The Agent-turn effect frame's key for the new seat's subcommittee choice:
# an effect of the visit, not a printed icon, so it joins
# ``pending_board_icons`` only and a repeat of the printed effects never
# re-arms it (like ``effects.BOARD_ICON_COMMANDER``).
BOARD_ICON_SUBCOMMITTEE: Final = "scouts_subcommittee"


def open_subcommittees(state: GameState, player: int) -> tuple[str, ...]:
    """The display's subcommittees nobody has joined; none once ``player``
    has joined one (a seat joins one subcommittee, OQ-076 (d)).

    No cost check: whether one can be joined now is
    ``scouts_effects.joinable_subcommittees``.
    """

    if not state.config.arrakeen_scouts:
        return ()
    members = state.scouts_subcommittee_members
    if any(seat == player for _, seat in members):
        return ()
    claimed = {subcommittee for subcommittee, _ in members}
    return tuple(
        subcommittee_id
        for subcommittee_id in state.scouts_subcommittees
        if subcommittee_id not in claimed
    )


def subcommittee_unavailable(player: int, *, source: str) -> GameEvent:
    """The public note that a new seat found every subcommittee taken."""

    return GameEvent(
        event_id=f"{source}:subcommittee_unavailable",
        kind="scouts_subcommittee_unavailable",
        payload=(("player", player),),
    )


def queue_reveal_subcommittee_offer(
    state: GameState, player: int, *, source: str
) -> tuple[GameState, tuple[GameEvent, ...]]:
    """Open Corrinth City's seat's subcommittee choice for the rest of its
    Reveal turn, or note that nothing is left to join.

    The entry is ``(player, source, exclude_space)``: no Agent took this
    seat, so a Recall Agent reward may recall any other Agent (``""``,
    OQ-075).
    """

    if not state.config.arrakeen_scouts:
        return state, ()
    if not open_subcommittees(state, player):
        return state, (subcommittee_unavailable(player, source=source),)
    entry = (player, source, "")
    return (
        replace(
            state,
            scouts_subcommittee_offers=(*state.scouts_subcommittee_offers, entry),
        ),
        (),
    )


def reveal_subcommittee_offer(
    state: GameState, player: int
) -> tuple[int, str, str] | None:
    """The seat's open Reveal-turn subcommittee offer, if any."""

    return next(
        (entry for entry in state.scouts_subcommittee_offers if entry[0] == player),
        None,
    )


def drop_reveal_subcommittee_offer(state: GameState, player: int) -> GameState:
    """Remove the seat's Reveal-turn offer (joined or declined)."""

    if reveal_subcommittee_offer(state, player) is None:
        return state
    return replace(
        state,
        scouts_subcommittee_offers=tuple(
            entry for entry in state.scouts_subcommittee_offers if entry[0] != player
        ),
    )
