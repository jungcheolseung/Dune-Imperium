"""Typed resolution of implemented Uprising board-space effects."""

from dataclasses import replace

from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState, Resources
from dune_imperium.core.state import GameState
from dune_imperium.rules.effects import (
    AutomaticEffect,
    DrawImperiumCardsEffect,
    DrawIntrigueCardsEffect,
    GainResourcesEffect,
    RecruitTroopsEffect,
    advance_after_effect,
    current_agent_effect_context,
)


def board_effects_for(
    state: GameState,
    space_id: str,
    cost_option: int,
) -> tuple[AutomaticEffect, ...]:
    """Return implemented automatic effects for one paid board-space option."""

    match space_id, cost_option:
        case "dutiful_service", 0 if not state.config.choam_module:
            return (GainResourcesEffect(solari=2),)
        case "sardaukar", 0:
            return (DrawIntrigueCardsEffect(1), RecruitTroopsEffect(4))
        case "deliver_supplies", 0:
            return (GainResourcesEffect(water=1),)
        case "heighliner", 0:
            return (RecruitTroopsEffect(5),)
        case "fremkit", 0:
            return (DrawImperiumCardsEffect(1),)
        case "assembly_hall", 0:
            return (DrawIntrigueCardsEffect(1),)
        case "gather_support", 0:
            return (RecruitTroopsEffect(2),)
        case "gather_support", 1:
            return (RecruitTroopsEffect(2), GainResourcesEffect(water=1))
        case "research_station", 0:
            return (RecruitTroopsEffect(2), DrawImperiumCardsEffect(2))
        case "spice_refinery", 0:
            return (GainResourcesEffect(solari=2),)
        case "spice_refinery", 1:
            return (GainResourcesEffect(solari=4),)
        case "accept_contract", 0 if not state.config.choam_module:
            return (DrawImperiumCardsEffect(1), GainResourcesEffect(solari=2))
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
    intrigue_deck = state.intrigue_deck
    for effect in effects:
        match effect:
            case GainResourcesEffect():
                next_owner = _gain_resources(next_owner, effect)
            case DrawImperiumCardsEffect():
                next_owner = _draw_imperium_cards(next_owner, effect.count)
            case DrawIntrigueCardsEffect():
                next_owner, intrigue_deck = _draw_intrigue_cards(
                    next_owner,
                    intrigue_deck,
                    effect.count,
                )
            case RecruitTroopsEffect():
                next_owner, recruited = _recruit_troops(next_owner, effect.count)
                previous = context.get("troops_recruited")
                if isinstance(previous, bool) or not isinstance(previous, int):
                    raise RuntimeError(
                        "Agent-turn effect frame has invalid recruit count"
                    )
                context["troops_recruited"] = previous + recruited
    players = tuple(
        next_owner if candidate.player_id == player else candidate
        for candidate in state.players
    )
    context["pending_board_effect"] = False
    effect_state = replace(state, intrigue_deck=intrigue_deck)
    next_state = advance_after_effect(effect_state, context, players)
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


def _draw_imperium_cards(player: PlayerState, count: int) -> PlayerState:
    if len(player.deck) < count:
        raise NotImplementedError("personal discard reshuffle is not implemented")
    return replace(
        player,
        deck=player.deck[count:],
        hand=(*player.hand, *player.deck[:count]),
    )


def _draw_intrigue_cards(
    player: PlayerState,
    deck: tuple[str, ...],
    count: int,
) -> tuple[PlayerState, tuple[str, ...]]:
    if len(deck) < count:
        raise ValueError("the Intrigue deck does not contain enough cards")
    return (
        replace(player, intrigue_cards=(*player.intrigue_cards, *deck[:count])),
        deck[count:],
    )


def _recruit_troops(player: PlayerState, count: int) -> tuple[PlayerState, int]:
    recruited = min(player.troops_supply, count)
    return (
        replace(
            player,
            troops_supply=player.troops_supply - recruited,
            troops_garrison=player.troops_garrison + recruited,
        ),
        recruited,
    )
