"""Typed resolution of implemented Uprising board-space effects."""

from dataclasses import replace

from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState, Resources
from dune_imperium.core.state import GameState
from dune_imperium.rules.effects import (
    GainResourcesEffect,
    advance_after_effect,
    current_agent_effect_context,
)


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

    _, context = current_agent_effect_context(state)
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
    next_state = advance_after_effect(state, context, players)
    event = GameEvent(
        event_id=f"round:{state.round_number}:player:{player}:board:{space_id}",
        kind="board_effect_resolved",
        payload=(("player", player), ("space_id", space_id)),
    )
    return RuleResult(state=next_state, events=(event,))


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
