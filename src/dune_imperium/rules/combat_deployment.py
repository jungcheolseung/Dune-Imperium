"""Troop deployment at the end of a Combat-space Agent turn."""

from dataclasses import replace

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.effects import (
    advance_after_effect,
    current_agent_effect_context,
)


def legal_combat_deployments(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Enumerate deployment counts including the explicit choice of zero."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context["pending_combat_deployment"] is not True:
        return ()
    recruited = context["troops_recruited"]
    if isinstance(recruited, bool) or not isinstance(recruited, int):
        raise RuntimeError("Agent-turn effect frame has invalid recruit count")

    garrison = state.players[player].troops_garrison
    maximum = min(garrison, recruited + 2)
    return tuple(
        DomainAction(
            action_id="deploy_troops",
            actor=player,
            arguments=(("count", count),),
        )
        for count in range(maximum + 1)
    )


def apply_combat_deployment(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Move the selected troop count from garrison to the current Conflict."""

    if action not in legal_combat_deployments(state, action.actor):
        raise ValueError("action is not a legal Combat deployment")
    count = dict(action.arguments)["count"]
    if isinstance(count, bool) or not isinstance(count, int):
        raise ValueError("deployment count must be an integer")

    _, context = current_agent_effect_context(state)
    owner = state.players[action.actor]
    next_owner = replace(
        owner,
        troops_garrison=owner.troops_garrison - count,
        troops_conflict=owner.troops_conflict + count,
    )
    players = tuple(
        next_owner if player.player_id == action.actor else player
        for player in state.players
    )
    context["pending_combat_deployment"] = False
    next_state = advance_after_effect(state, context, players)
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{action.actor}:deploy_troops"
        ),
        kind="troops_deployed",
        payload=(("count", count), ("player", action.actor)),
    )
    return RuleResult(state=next_state, events=(event,))
