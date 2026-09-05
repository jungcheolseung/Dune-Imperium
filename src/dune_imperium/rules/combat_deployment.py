"""Troop deployment during a Combat-space Agent turn (OQ-029).

The basic deployment of an Agent turn is adjustable until the turn ends
(project convention OQ-029, ``docs/rules/player-turns.md``): ``deploy_troops``
adds troops to this turn's deployment, ``withdraw_troops`` returns troops
deployed this turn to the garrison, and ``finish_agent_turn`` closes the turn
once every other pending effect has been resolved. The net deployment of the
turn never exceeds "every troop recruited this turn plus two garrison troops"
[Main p. 10] [FAQ p. 4], and a withdrawal may not drop the turn's deployed
unit count below a condition an effect already consumed (Distraction's Spy).
"""

from dataclasses import replace

from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.effects import (
    advance_after_effect,
    agent_turn_has_other_pending_effects,
    current_agent_effect_context,
)


def _deployment_context(
    state: GameState,
    player: int,
) -> tuple[dict[str, ActionValue], int, int, int] | None:
    """Return (context, recruited, existing limit, deployed so far) or None."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return None
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return None
    if context["pending_combat_deployment"] is not True:
        return None
    recruited = context["troops_recruited"]
    if isinstance(recruited, bool) or not isinstance(recruited, int):
        raise RuntimeError("Agent-turn effect frame has invalid recruit count")
    existing_limit = context.get("existing_troop_deployment_limit")
    if isinstance(existing_limit, bool) or not isinstance(existing_limit, int):
        raise RuntimeError("Agent-turn effect frame has invalid deployment limit")
    deployed = context.get("combat_troops_deployed", 0)
    if isinstance(deployed, bool) or not isinstance(deployed, int):
        raise RuntimeError("Agent-turn effect frame has invalid deployment count")
    return context, recruited, existing_limit, deployed


def legal_combat_deployments(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Enumerate the troop counts that may still be added to this deployment."""

    found = _deployment_context(state, player)
    if found is None:
        return ()
    _, recruited, existing_limit, deployed = found
    garrison = state.players[player].troops_garrison
    maximum = min(garrison, recruited + existing_limit - deployed)
    return tuple(
        DomainAction(
            action_id="deploy_troops",
            actor=player,
            arguments=(("count", count),),
        )
        for count in range(1, maximum + 1)
    )


def legal_troop_withdrawals(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Enumerate how many of this turn's deployed troops may return (OQ-029)."""

    found = _deployment_context(state, player)
    if found is None:
        return ()
    _, _, _, deployed = found
    owner = state.players[player]
    # A consumed deployment condition (Distraction) keeps its minimum deployed.
    maximum = min(deployed, owner.units_deployed_turn - owner.units_deployed_committed)
    return tuple(
        DomainAction(
            action_id="withdraw_troops",
            actor=player,
            arguments=(("count", count),),
        )
        for count in range(1, maximum + 1)
    )


def legal_agent_turn_finish_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer the explicit turn end once only the deployment stays open."""

    found = _deployment_context(state, player)
    if found is None:
        return ()
    context = found[0]
    if agent_turn_has_other_pending_effects(context, state.players):
        return ()
    return (DomainAction(action_id="finish_agent_turn", actor=player),)


def _count_argument(action: DomainAction) -> int:
    count = dict(action.arguments)["count"]
    if isinstance(count, bool) or not isinstance(count, int):
        raise ValueError("deployment count must be an integer")
    return count


def _move_troops(
    state: GameState,
    context: dict[str, ActionValue],
    player: int,
    delta: int,
) -> GameState:
    """Move ``delta`` troops garrison→Conflict (negative: back) and keep the frame."""

    owner = state.players[player]
    next_owner = replace(
        owner,
        troops_garrison=owner.troops_garrison - delta,
        troops_conflict=owner.troops_conflict + delta,
        units_deployed_turn=owner.units_deployed_turn + delta,
    )
    players = tuple(
        next_owner if seat.player_id == player else seat for seat in state.players
    )
    deployed = context.get("combat_troops_deployed", 0)
    if isinstance(deployed, bool) or not isinstance(deployed, int):
        raise RuntimeError("Agent-turn effect frame has invalid deployment count")
    context["combat_troops_deployed"] = deployed + delta
    frame = state.decision_stack[-1]
    next_frame = replace(frame, context=tuple(sorted(context.items())))
    return replace(
        state,
        players=players,
        decision_stack=(*state.decision_stack[:-1], next_frame),
    )


def apply_combat_deployment(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Add the selected troop count to this turn's Conflict deployment."""

    if action not in legal_combat_deployments(state, action.actor):
        raise ValueError("action is not a legal Combat deployment")
    count = _count_argument(action)
    _, context = current_agent_effect_context(state)
    next_state = _move_troops(state, context, action.actor, count)
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{action.actor}:deploy_troops:"
            f"{next_state.players[action.actor].units_deployed_turn}"
        ),
        kind="troops_deployed",
        payload=(("count", count), ("player", action.actor)),
    )
    return RuleResult(state=next_state, events=(event,))


def apply_troop_withdrawal(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Return troops deployed this turn from the Conflict to the garrison."""

    if action not in legal_troop_withdrawals(state, action.actor):
        raise ValueError("action is not a legal troop withdrawal")
    count = _count_argument(action)
    _, context = current_agent_effect_context(state)
    next_state = _move_troops(state, context, action.actor, -count)
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{action.actor}:withdraw_troops:"
            f"{next_state.players[action.actor].units_deployed_turn}"
        ),
        kind="troops_withdrawn",
        payload=(("count", count), ("player", action.actor)),
    )
    return RuleResult(state=next_state, events=(event,))


def apply_agent_turn_finish(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Close the deployment window and hand the turn over."""

    if action not in legal_agent_turn_finish_actions(state, action.actor):
        raise ValueError("the Agent turn cannot be finished yet")
    _, context = current_agent_effect_context(state)
    context["pending_combat_deployment"] = False
    next_state = advance_after_effect(state, context)
    event = GameEvent(
        event_id=f"round:{state.round_number}:player:{action.actor}:finish_agent_turn",
        kind="agent_turn_finished",
        payload=(("player", action.actor),),
    )
    return RuleResult(state=next_state, events=(event,))
