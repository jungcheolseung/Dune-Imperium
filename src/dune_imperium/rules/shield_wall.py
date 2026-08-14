"""Shield Wall board state and protected-Conflict rules."""

from dataclasses import replace

from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState


def current_conflict_is_shield_wall_protected(state: GameState) -> bool:
    """Return whether the current Conflict blocks sandworm summoning."""

    if not state.shield_wall_present or not state.current_conflict_ids:
        return False
    conflict_id = state.current_conflict_ids[-1]
    try:
        conflict = CONFLICTS_BY_ID[conflict_id]
    except KeyError as error:
        raise ValueError(f"unknown current Conflict: {conflict_id}") from error
    return conflict.shield_wall_protected


def destroy_shield_wall(
    state: GameState,
    *,
    event_id: str,
    source: str,
) -> RuleResult:
    """Permanently remove the Shield Wall for a resolved detonation effect."""

    if not state.shield_wall_present:
        raise ValueError("the Shield Wall has already been destroyed")
    if not event_id or not source:
        raise ValueError("Shield Wall destruction requires event and source IDs")
    event = GameEvent(
        event_id=event_id,
        kind="shield_wall_destroyed",
        payload=(("source", source),),
    )
    return RuleResult(
        state=replace(state, shield_wall_present=False),
        events=(event,),
    )
