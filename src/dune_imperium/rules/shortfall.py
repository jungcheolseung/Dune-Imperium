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
deployment allowance like any other recruit -- except a Harkonnen Advisor
troop, which stays undeployable however it arrives (OQ-038, 2026-10-26).
Suspensor Suits troops the supply could not cover (``ungained_conflict_troops``)
are made up after the recruit shortfall and before the specimens, and go to
the Conflict as they come (OQ-042, user re-ruling 2026-10-25), in the Steam
app's order (recruits, then deployments, then specimens).
Every seat's shortfall clears when a turn opens
(``frames.reset_turn_counters``) and whenever no player turn is open
(``drop_stale_shortfalls``): outside a turn nothing is refilled, so a
Combat reward's shortfall is simply dropped.
"""

from copy import replace

from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.combat_deployment import (
    credit_owed_recruits,
    refill_undeployable_troops,
)
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
        waiting = seat.ungained_troops or seat.ungained_conflict_troops or specimens
        if seat.troops_supply and waiting:
            return seat.player_id
    return None


def refill_shortfall(state: GameState, player: int) -> RuleResult:
    """Take ``player``'s waiting shortfall from the troops now in its supply."""

    owner = state.players[player]
    troops = min(owner.troops_supply, owner.ungained_troops)
    supply = owner.troops_supply - troops
    conflict = min(supply, owner.ungained_conflict_troops)
    supply -= conflict
    specimens = (
        min(supply, owner.ungained_specimens) if state.config.immortality else 0
    )
    if not troops and not conflict and not specimens:
        raise ValueError("there is no shortfall the supply can cover")
    # The Conflict's troops stay in the supply for
    # ``suspensor_troops_to_conflict`` below.
    next_owner = replace(
        owner,
        troops_supply=supply + conflict - specimens,
        troops_garrison=owner.troops_garrison + troops,
        specimens=owner.specimens + specimens,
        ungained_troops=owner.ungained_troops - troops,
        ungained_specimens=owner.ungained_specimens - specimens,
        ungained_conflict_troops=owner.ungained_conflict_troops - conflict,
    )
    next_state = replace(state, players=replace_player(state.players, next_owner))
    if troops and turn_owner_of(state) == player:
        # A Harkonnen Advisor troop stays undeployable however it arrives
        # (OQ-038, 2026-10-26); the rest are this turn's recruits.
        next_state, undeployable = refill_undeployable_troops(
            next_state, player, troops, ungained=owner.ungained_troops
        )
        if troops - undeployable:
            next_state = update_turn_recruits(
                next_state, troops_recruited=troops - undeployable
            )
            # Reinforcements' and Gurney Halleck's owed troops come first: in
            # the Reveal turn they may then deploy (OQ-140).
            next_state = credit_owed_recruits(
                next_state, player, troops - undeployable
            )
    placed: tuple[GameEvent, ...] = ()
    if conflict:
        # Imported here: the Tech rules import half the rules package.
        from dune_imperium.rules.tech import suspensor_troops_to_conflict

        deployed = suspensor_troops_to_conflict(
            next_state,
            player,
            conflict,
            source=f"round:{state.round_number}:player:{player}:suspensor_suits:refill",
        )
        next_state = deployed.state
        placed = deployed.events
    # Ids need not be unique: two refills of one seat share it (cleanup-2c-6;
    # it used to count the event log), and a zero is left out.
    event = GameEvent(
        event_id=f"round:{state.round_number}:player:{player}:shortfall_refilled",
        kind="shortfall_refilled",
        payload=(
            *((("conflict_troops", conflict),) if conflict else ()),
            ("player", player),
            *((("specimens", specimens),) if specimens else ()),
            *((("troops", troops),) if troops else ()),
        ),
    )
    return RuleResult(state=next_state, events=(event, *placed))


def shortfall_is_stale(state: GameState) -> bool:
    """Whether a shortfall waits although no player turn is open."""

    return turn_owner_of(state) is None and any(
        seat.ungained_troops or seat.ungained_specimens or seat.ungained_conflict_troops
        for seat in state.players
    )


def drop_stale_shortfalls(state: GameState) -> RuleResult:
    """Clear every seat's shortfall once no turn can make it up any more."""

    players = tuple(
        replace(
            seat, ungained_troops=0, ungained_specimens=0, ungained_conflict_troops=0
        )
        for seat in state.players
    )
    return RuleResult(state=replace(state, players=players))
