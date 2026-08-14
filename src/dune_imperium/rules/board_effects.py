"""Typed resolution of implemented Uprising board-space effects."""

from dataclasses import replace

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
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
from dune_imperium.rules.shield_wall import (
    current_conflict_is_shield_wall_protected,
    destroy_shield_wall,
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
        case "arrakeen", 0:
            return (RecruitTroopsEffect(1), DrawImperiumCardsEffect(1))
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


def legal_sietch_tabr_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Sietch Tabr's supplies or water/detonation choices."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if (
        context.get("pending_board_effect") is not True
        or context.get("space_id") != "sietch_tabr"
    ):
        return ()
    actions = [
        DomainAction(action_id="take_sietch_tabr_supplies", actor=player),
        DomainAction(action_id="take_sietch_tabr_water", actor=player),
    ]
    if state.shield_wall_present:
        actions.append(
            DomainAction(
                action_id="take_sietch_tabr_water_and_destroy_wall",
                actor=player,
            )
        )
    return tuple(actions)


def apply_sietch_tabr_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve one explicit Sietch Tabr reward branch."""

    if action not in legal_sietch_tabr_actions(state, action.actor):
        raise ValueError("action is not a legal Sietch Tabr choice")
    _, context = current_agent_effect_context(state)
    owner = state.players[action.actor]
    recruited = 0
    if action.action_id == "take_sietch_tabr_supplies":
        owner, recruited = _recruit_troops(owner, 1)
        owner = replace(
            owner,
            resources=replace(owner.resources, water=owner.resources.water + 1),
            maker_hooks=True,
        )
        previous = context.get("troops_recruited")
        if isinstance(previous, bool) or not isinstance(previous, int):
            raise RuntimeError("Agent-turn effect frame has invalid recruit count")
        context["troops_recruited"] = previous + recruited
    else:
        owner = replace(
            owner,
            resources=replace(owner.resources, water=owner.resources.water + 1),
        )

    players = tuple(
        owner if candidate.player_id == action.actor else candidate
        for candidate in state.players
    )
    effect_state = replace(state, players=players)
    events: list[GameEvent] = []
    if action.action_id == "take_sietch_tabr_water_and_destroy_wall":
        destruction = destroy_shield_wall(
            effect_state,
            event_id=(
                f"round:{state.round_number}:player:{action.actor}:shield_wall:"
                "sietch_tabr"
            ),
            source="sietch_tabr",
        )
        effect_state = destruction.state
        events.extend(destruction.events)

    context["pending_board_effect"] = False
    next_state = advance_after_effect(effect_state, context, effect_state.players)
    events.append(
        GameEvent(
            event_id=(
                f"round:{state.round_number}:player:{action.actor}:board:sietch_tabr"
            ),
            kind="board_effect_resolved",
            payload=(
                ("action_id", action.action_id),
                ("player", action.actor),
                ("space_id", "sietch_tabr"),
            ),
        )
    )
    return RuleResult(state=next_state, events=tuple(events))


def legal_maker_space_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return spice and any legal sandworm choices for a Maker space."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    space_id = context.get("space_id")
    if context.get("pending_board_effect") is not True or space_id not in (
        "deep_desert",
        "hagga_basin",
        "imperial_basin",
    ):
        return ()
    actions = [
        DomainAction(
            action_id="harvest_maker_spice",
            actor=player,
            arguments=(("space_id", space_id),),
        )
    ]
    owner = state.players[player]
    if (
        space_id != "imperial_basin"
        and owner.maker_hooks
        and state.current_conflict_ids
        and not current_conflict_is_shield_wall_protected(state)
    ):
        actions.append(
            DomainAction(
                action_id="summon_maker_sandworms",
                actor=player,
                arguments=(("space_id", space_id),),
            )
        )
    return tuple(actions)


def apply_maker_space_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Collect bonus spice, then take base spice or summon sandworms."""

    if action not in legal_maker_space_actions(state, action.actor):
        raise ValueError("action is not a legal Maker-space choice")
    space_id = dict(action.arguments).get("space_id")
    if space_id not in ("deep_desert", "hagga_basin", "imperial_basin"):
        raise RuntimeError("Maker-space action has invalid space ID")
    bonus_by_space = dict(state.maker_bonus_spice)
    bonus_spice = bonus_by_space[space_id]
    owner = state.players[action.actor]
    base_spice = 0
    sandworms = 0
    if action.action_id == "harvest_maker_spice":
        base_spice = {
            "deep_desert": 4,
            "hagga_basin": 2,
            "imperial_basin": 1,
        }[space_id]
        owner = replace(
            owner,
            resources=replace(
                owner.resources,
                spice=owner.resources.spice + bonus_spice + base_spice,
            ),
        )
    else:
        sandworms = 2 if space_id == "deep_desert" else 1
        owner = replace(
            owner,
            resources=replace(
                owner.resources,
                spice=owner.resources.spice + bonus_spice,
            ),
            sandworms_conflict=owner.sandworms_conflict + sandworms,
        )

    players = tuple(
        owner if candidate.player_id == action.actor else candidate
        for candidate in state.players
    )
    maker_bonus_spice = tuple(
        (candidate, 0 if candidate == space_id else amount)
        for candidate, amount in state.maker_bonus_spice
    )
    _, context = current_agent_effect_context(state)
    context["pending_board_effect"] = False
    effect_state = replace(
        state,
        players=players,
        maker_bonus_spice=maker_bonus_spice,
    )
    next_state = advance_after_effect(effect_state, context, players)
    event = GameEvent(
        event_id=(f"round:{state.round_number}:player:{action.actor}:board:{space_id}"),
        kind="board_effect_resolved",
        payload=(
            ("action_id", action.action_id),
            ("bonus_spice", bonus_spice),
            ("player", action.actor),
            ("sandworms", sandworms),
            ("space_id", space_id),
            ("spice", bonus_spice + base_spice),
        ),
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
