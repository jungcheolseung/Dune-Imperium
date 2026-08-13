"""Typed resolution of implemented Uprising board-space effects."""

from dataclasses import replace

from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState, Resources
from dune_imperium.core.state import GameState
from dune_imperium.rules.effects import GainResourcesEffect


def board_effects_for(
    state: GameState,
    space_id: str,
    cost_option: int,
) -> tuple[GainResourcesEffect, ...]:
    """Return implemented automatic effects for one paid board-space option."""

    match space_id, cost_option:
        case "dutiful_service", 0 if not state.config.choam_module:
            return (GainResourcesEffect(solari=2),)
        case "deliver_supplies", 0:
            return (GainResourcesEffect(water=1),)
        case "spice_refinery", 0:
            return (GainResourcesEffect(solari=2),)
        case "spice_refinery", 1:
            return (GainResourcesEffect(solari=4),)
        case _:
            raise NotImplementedError(
                f"board effect is not implemented: {space_id} option {cost_option}"
            )


def resolve_board_effect(state: GameState) -> RuleResult:
    """Resolve the board-effect group in the current Agent-turn frame."""

    frame = _current_effect_frame(state)
    context = dict(frame.context)
    if context.get("pending_board_effect") is not True:
        raise ValueError("the current Agent turn has no pending board effect")
    player = context.get("turn_owner")
    space_id = context.get("space_id")
    cost_option = context.get("cost_option")
    if (
        isinstance(player, bool)
        or not isinstance(player, int)
        or not isinstance(space_id, str)
        or isinstance(cost_option, bool)
        or not isinstance(cost_option, int)
    ):
        raise RuntimeError("Agent-turn effect frame has invalid context")

    effects = board_effects_for(state, space_id, cost_option)
    owner = state.players[player]
    next_owner = owner
    for effect in effects:
        next_owner = _gain_resources(next_owner, effect)
    players = tuple(
        next_owner if candidate.player_id == player else candidate
        for candidate in state.players
    )
    context["pending_board_effect"] = False
    next_frame = replace(frame, context=tuple(sorted(context.items())))
    next_state = replace(
        state,
        players=players,
        decision_stack=(*state.decision_stack[:-1], next_frame),
    )
    event = GameEvent(
        event_id=f"round:{state.round_number}:player:{player}:board:{space_id}",
        kind="board_effect_resolved",
        payload=(("player", player), ("space_id", space_id)),
    )
    return RuleResult(state=next_state, events=(event,))


def _current_effect_frame(state: GameState) -> DecisionFrame:
    if not state.decision_stack:
        raise ValueError("there is no pending Agent-turn effect frame")
    frame = state.decision_stack[-1]
    if not isinstance(frame.decision, PlayerDecision):
        raise ValueError("the current decision is not an Agent-turn effect")
    return frame


def _gain_resources(
    player: PlayerState,
    effect: GainResourcesEffect,
) -> PlayerState:
    return replace(
        player,
        resources=Resources(
            solari=player.resources.solari + effect.solari,
            spice=player.resources.spice + effect.spice,
            water=player.resources.water + effect.water,
        ),
    )
