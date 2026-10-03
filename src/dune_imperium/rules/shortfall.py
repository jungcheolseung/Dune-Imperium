"""Recruit and specimen shortfalls taken once troops return to the supply.

A recruit or a specimen icon takes only what the supply holds when it
resolves; the rest is recorded on the seat (``ungained_troops``,
``ungained_specimens``; ``rules.effects.recruit_troops``,
``rules.specimens.generate_specimens``). When troops come back to that
seat's supply later in the same player turn -- a troop lost to the supply, a
specimen returned or paid, Other Memories -- the engine takes the shortfall
from them at once: troops first, then specimens (OQ-030, OQ-049; user ruling
2026-10-04, "앱 구현 방식으로 가자", following the Steam app). Refilled troops
are this turn's recruits, so on the turn owner's seat they raise the Combat
deployment allowance like any other recruit. Every seat's shortfall clears
when a turn opens (``frames.reset_turn_counters``) and whenever no player
turn is open (``drop_stale_shortfalls``): outside a turn nothing is
refilled, so a Combat reward's shortfall is simply dropped.
"""

from dataclasses import replace

from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.frames import (
    FrameKind,
    replace_player,
    turn_owner_of,
    update_turn_recruits,
)


def shortfall_refill_seat(state: GameState) -> int | None:
    """The first seat whose waiting shortfall its supply can now cover.

    Not while an Arrakeen Scouts line resolves: a line that tops the supply
    up from the tanks for its own recruit takes those troops first, and the
    shortfall is made up from what is left once the line is done.
    """

    if state.phase is not GamePhase.PLAYER_TURNS or turn_owner_of(state) is None:
        return None
    stack = state.decision_stack
    if stack and stack[-1].kind == FrameKind.SCOUTS_EFFECT:
        return None
    for seat in state.players:
        specimens = seat.ungained_specimens if state.config.immortality else 0
        if seat.troops_supply and (seat.ungained_troops or specimens):
            return seat.player_id
    return None


def refill_shortfall(state: GameState, player: int) -> RuleResult:
    """Take ``player``'s waiting shortfall from the troops now in its supply."""

    owner = state.players[player]
    troops = min(owner.troops_supply, owner.ungained_troops)
    supply = owner.troops_supply - troops
    specimens = (
        min(supply, owner.ungained_specimens) if state.config.immortality else 0
    )
    if not troops and not specimens:
        raise ValueError("there is no shortfall the supply can cover")
    next_owner = replace(
        owner,
        troops_supply=supply - specimens,
        troops_garrison=owner.troops_garrison + troops,
        specimens=owner.specimens + specimens,
        ungained_troops=owner.ungained_troops - troops,
        ungained_specimens=owner.ungained_specimens - specimens,
    )
    next_state = replace(state, players=replace_player(state.players, next_owner))
    if troops and turn_owner_of(state) == player:
        next_state = update_turn_recruits(next_state, troops_recruited=troops)
    # The step index and what is still waiting keep two refills apart, even
    # two of one seat inside one step's automatic chain.
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{player}:shortfall_refilled:"
            f"{len(state.event_log)}:{next_owner.ungained_troops}:"
            f"{next_owner.ungained_specimens}"
        ),
        kind="shortfall_refilled",
        payload=(
            ("player", player),
            ("specimens", specimens),
            ("troops", troops),
        ),
    )
    return RuleResult(state=next_state, events=(event,))


def shortfall_is_stale(state: GameState) -> bool:
    """Whether a shortfall waits although no player turn is open."""

    return turn_owner_of(state) is None and any(
        seat.ungained_troops or seat.ungained_specimens for seat in state.players
    )


def drop_stale_shortfalls(state: GameState) -> RuleResult:
    """Clear every seat's shortfall once no turn can make it up any more."""

    players = tuple(
        replace(seat, ungained_troops=0, ungained_specimens=0)
        for seat in state.players
    )
    return RuleResult(state=replace(state, players=players))
