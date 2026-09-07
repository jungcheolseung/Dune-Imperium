"""Troop deployment during a Combat-space Agent turn (OQ-029).

The basic deployment of an Agent turn is adjustable until the turn ends
(project convention OQ-029, ``docs/rules/player-turns.md``): ``deploy_troops``
adds troops to this turn's deployment, ``withdraw_troops`` returns troops
deployed this turn to the garrison, and ``finish_agent_turn`` closes the turn
once every other pending effect has been resolved. The net deployment of the
turn never exceeds "every troop recruited this turn plus two garrison troops"
[Main p. 10] [FAQ p. 4], and a withdrawal may not drop the turn's deployed
unit count below a condition an effect already consumed (Distraction's Spy).

Bloodlines Sardaukar Commanders are "troops" for this purpose: one recruited
this turn or in the garrison deploys under the same limit, counted together
with the troops [Bloodlines p. 4] (``deploy_commanders`` /
``withdraw_commanders``; the frame tracks the Commander share separately so a
withdrawal returns the right kind of unit).
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
from dune_imperium.rules.frames import FrameKind, replace_player


def undeployable_troops(context: dict[str, ActionValue]) -> int:
    """Return the garrison troops the turn's effects forbid deploying."""

    value = context.get("undeployable_troops", 0)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError("Agent-turn effect frame has invalid undeployable count")
    return value


def release_undeployable_troops(
    state: GameState,
    player: int,
    count: int,
) -> GameState:
    """A garrison troop lost this turn counts as the undeployable one.

    Troops are indistinguishable, so a player who must lose a garrison
    troop while Harkonnen Advisor's troop sits there gives up that troop
    first and the deployable count returns to normal (OQ-038).
    """

    if count < 1:
        return state
    frames = list(state.decision_stack)
    for index in range(len(frames) - 1, -1, -1):
        frame = frames[index]
        if frame.kind != FrameKind.AGENT_EFFECTS or not isinstance(
            frame.decision, PlayerDecision
        ):
            continue
        if frame.decision.owner != player:
            continue
        context = dict(frame.context)
        undeployable = undeployable_troops(context)
        if not undeployable:
            return state
        context["undeployable_troops"] = max(0, undeployable - count)
        frames[index] = replace(frame, context=tuple(sorted(context.items())))
        return replace(state, decision_stack=tuple(frames))
    return state


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
    context, recruited, existing_limit, deployed = found
    # Harkonnen Advisor's troop "can't be deployed to the Conflict this
    # turn": it sits in the garrison but is not available [Piter De Vries
    # card] (OQ-038).
    garrison = max(
        0, state.players[player].troops_garrison - undeployable_troops(context)
    )
    maximum = min(garrison, recruited + existing_limit - deployed)
    return tuple(
        DomainAction(
            action_id="deploy_troops",
            actor=player,
            arguments=(("count", count),),
        )
        for count in range(1, maximum + 1)
    )


def legal_commander_deployments(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Enumerate the Sardaukar Commander counts that may still deploy.

    A Commander shares the turn's unit limit with the troops: every unit
    recruited this turn plus two more from the garrison [Bloodlines p. 4]
    [Main p. 10].
    """

    found = _deployment_context(state, player)
    if found is None:
        return ()
    _, recruited, existing_limit, deployed = found
    garrison = state.players[player].commanders_garrison
    maximum = min(garrison, recruited + existing_limit - deployed)
    return tuple(
        DomainAction(
            action_id="deploy_commanders",
            actor=player,
            arguments=(("count", count),),
        )
        for count in range(1, maximum + 1)
    )


def _commanders_deployed(context: dict[str, ActionValue]) -> int:
    deployed = context.get("combat_commanders_deployed", 0)
    if isinstance(deployed, bool) or not isinstance(deployed, int):
        raise RuntimeError("Agent-turn effect frame has invalid Commander count")
    return deployed


def legal_troop_withdrawals(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Enumerate how many of this turn's deployed troops may return (OQ-029)."""

    found = _deployment_context(state, player)
    if found is None:
        return ()
    context, _, _, deployed = found
    owner = state.players[player]
    # A consumed deployment condition (Distraction) keeps its minimum deployed.
    maximum = min(
        deployed - _commanders_deployed(context),
        owner.units_deployed_turn - owner.units_deployed_committed,
    )
    return tuple(
        DomainAction(
            action_id="withdraw_troops",
            actor=player,
            arguments=(("count", count),),
        )
        for count in range(1, maximum + 1)
    )


def legal_commander_withdrawals(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Enumerate how many of this turn's deployed Commanders may return."""

    found = _deployment_context(state, player)
    if found is None:
        return ()
    context, _, _, _ = found
    owner = state.players[player]
    maximum = min(
        _commanders_deployed(context),
        owner.units_deployed_turn - owner.units_deployed_committed,
    )
    return tuple(
        DomainAction(
            action_id="withdraw_commanders",
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
    *,
    commanders: bool = False,
) -> GameState:
    """Move ``delta`` units garrison→Conflict (negative: back) and keep the frame.

    ``combat_troops_deployed`` counts every unit of the turn's basic
    deployment; ``combat_commanders_deployed`` the Commander share of it.
    """

    owner = state.players[player]
    if commanders:
        next_owner = replace(
            owner,
            commanders_garrison=owner.commanders_garrison - delta,
            commanders_conflict=owner.commanders_conflict + delta,
            units_deployed_turn=owner.units_deployed_turn + delta,
        )
        context["combat_commanders_deployed"] = _commanders_deployed(context) + delta
    else:
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


def reconcile_deployment_after_retreat(
    state: GameState,
    player: int,
    *,
    troops: int,
    commanders: int = 0,
) -> GameState:
    """Shrink the open Agent turn's deployment counters after a retreat.

    A Signet Ring or Plot Intrigue may retreat units the turn's basic
    deployment just moved (Fedaykin Maneuver); the withdrawal window keeps
    offering the counters it recorded, so they follow the retreat down.
    The per-turn deployment count also drops, never below the count a
    trigger already consumed (OQ-029).
    """

    total = troops + commanders
    if total < 1:
        return state
    owner = state.players[player]
    players = replace_player(
        state.players,
        replace(
            owner,
            units_deployed_turn=max(
                owner.units_deployed_committed, owner.units_deployed_turn - total
            ),
        ),
    )
    frames = list(state.decision_stack)
    for index in range(len(frames) - 1, -1, -1):
        frame = frames[index]
        if frame.kind != FrameKind.AGENT_EFFECTS or not isinstance(
            frame.decision, PlayerDecision
        ):
            continue
        if frame.decision.owner != player:
            continue
        context = dict(frame.context)
        deployed = context.get("combat_troops_deployed", 0)
        if isinstance(deployed, bool) or not isinstance(deployed, int):
            raise RuntimeError("Agent-turn effect frame has invalid deployment count")
        context["combat_troops_deployed"] = max(0, deployed - total)
        context["combat_commanders_deployed"] = max(
            0, _commanders_deployed(context) - commanders
        )
        frames[index] = replace(frame, context=tuple(sorted(context.items())))
        break
    return replace(state, players=players, decision_stack=tuple(frames))


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


def apply_commander_deployment(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Add the selected Sardaukar Commander count to this turn's deployment."""

    if action not in legal_commander_deployments(state, action.actor):
        raise ValueError("action is not a legal Commander deployment")
    count = _count_argument(action)
    _, context = current_agent_effect_context(state)
    next_state = _move_troops(state, context, action.actor, count, commanders=True)
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{action.actor}:deploy_commanders:"
            f"{next_state.players[action.actor].units_deployed_turn}"
        ),
        kind="commanders_deployed",
        payload=(("count", count), ("player", action.actor)),
    )
    return RuleResult(state=next_state, events=(event,))


def apply_commander_withdrawal(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Return Commanders deployed this turn from the Conflict to the garrison."""

    if action not in legal_commander_withdrawals(state, action.actor):
        raise ValueError("action is not a legal Commander withdrawal")
    count = _count_argument(action)
    _, context = current_agent_effect_context(state)
    next_state = _move_troops(state, context, action.actor, -count, commanders=True)
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{action.actor}:withdraw_commanders:"
            f"{next_state.players[action.actor].units_deployed_turn}"
        ),
        kind="commanders_withdrawn",
        payload=(("count", count), ("player", action.actor)),
    )
    return RuleResult(state=next_state, events=(event,))


def grant_combat_icon(state: GameState, player: int) -> GameState:
    """Let ``player`` deploy this turn as if at a Combat space [Bloodlines p. 5].

    Inside the owner's Agent-turn effect frame the basic deployment window
    opens (or stays open) with the garrison share capped at two whatever
    the number of icons; inside the owner's Reveal frame the Reveal-turn
    deployment opens (``reveal_turn``); before the placement the flag waits
    on the seat for the placement to read. Emperor of the Known Universe
    still blocks deployment for the turn [Main p. 17].
    """

    for index in range(len(state.decision_stack) - 1, -1, -1):
        frame = state.decision_stack[index]
        if not isinstance(frame.decision, PlayerDecision) or (
            frame.decision.owner != player
        ):
            continue
        if frame.kind == FrameKind.AGENT_EFFECTS:
            context = dict(frame.context)
            if context.get("units_deploy_blocked") is True:
                return state
            context["pending_combat_deployment"] = True
            limit = context.get("existing_troop_deployment_limit", 0)
            if isinstance(limit, bool) or not isinstance(limit, int):
                raise RuntimeError(
                    "Agent-turn effect frame has invalid deployment limit"
                )
            context["existing_troop_deployment_limit"] = max(limit, 2)
            return replace(
                state,
                decision_stack=(
                    *state.decision_stack[:index],
                    replace(frame, context=tuple(sorted(context.items()))),
                    *state.decision_stack[index + 1 :],
                ),
            )
        if frame.kind == FrameKind.REVEAL:
            context = dict(frame.context)
            context["combat_deployment"] = True
            return replace(
                state,
                decision_stack=(
                    *state.decision_stack[:index],
                    replace(frame, context=tuple(sorted(context.items()))),
                    *state.decision_stack[index + 1 :],
                ),
            )
        if frame.kind == FrameKind.TURN:
            break
    owner = state.players[player]
    return (
        replace(
            state,
            players=tuple(
                replace(seat, combat_icon_turn=True)
                if seat.player_id == player
                else seat
                for seat in state.players
            ),
        )
        if not owner.combat_icon_turn
        else state
    )


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
