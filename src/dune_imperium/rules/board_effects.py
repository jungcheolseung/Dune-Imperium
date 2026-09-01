"""Typed resolution of implemented Uprising board-space effects."""

from dataclasses import replace

from dune_imperium.content.uprising.board import Faction
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState, Resources
from dune_imperium.core.state import GameState
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.contracts import begin_contract_gain
from dune_imperium.rules.effects import (
    AutomaticEffect,
    DrawImperiumCardsEffect,
    DrawIntrigueCardsEffect,
    GainResourcesEffect,
    RecruitTroopsEffect,
    advance_after_effect,
    current_agent_effect_context,
    recruit_troops,
)
from dune_imperium.rules.influence import gain_faction_influence
from dune_imperium.rules.intrigue_deck import draw_or_queue_intrigue_cards
from dune_imperium.rules.leader_abilities import units_deployment_blocked
from dune_imperium.rules.shield_wall import (
    current_conflict_is_shield_wall_protected,
    destroy_shield_wall,
)
from dune_imperium.rules.spy_placement import (
    empty_observation_post_ids,
    place_spy,
    recall_spy,
)

# Board spaces whose board effect is resolved through a dedicated choice rather
# than the generic ``resolve_board_effect`` action.
CHOICE_DRIVEN_SPACE_IDS = frozenset(
    {
        "espionage",
        "sietch_tabr",
        "deep_desert",
        "hagga_basin",
        "imperial_basin",
        "shipping",
    }
)


def board_effect_is_implemented(
    state: GameState,
    space_id: str,
    cost_option: int,
) -> bool:
    """Return whether an Agent may be advertised for this paid board option.

    Spaces whose printed effect still depends on unimplemented content (for
    example Intrigue-driven spaces) are withheld from legal actions so that
    every advertised action stays executable.
    """

    if space_id in CHOICE_DRIVEN_SPACE_IDS:
        return True
    try:
        board_effects_for(state, space_id, cost_option)
    except NotImplementedError:
        return False
    return True


def board_effects_for(
    state: GameState,
    space_id: str,
    cost_option: int,
) -> tuple[AutomaticEffect, ...]:
    """Return implemented automatic effects for one paid board-space option."""

    return static_board_effects(
        space_id,
        cost_option,
        choam_module=state.config.choam_module,
    )


def static_board_effects(
    space_id: str,
    cost_option: int,
    *,
    choam_module: bool,
) -> tuple[AutomaticEffect, ...]:
    """Return the printed automatic effects of one paid board-space option.

    This is the state-free table behind ``board_effects_for``; the display
    catalog reads it too, so effect text shown to players always derives from
    the same table the engine executes.
    """

    match space_id, cost_option:
        case "dutiful_service", 0 if not choam_module:
            return (GainResourcesEffect(solari=2),)
        case "dutiful_service", 0:
            return ()
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
        case "high_council", 0:
            return ()
        case "swordmaster", 0 | 1:
            return ()
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
        case "accept_contract", 0 if not choam_module:
            return (DrawImperiumCardsEffect(1), GainResourcesEffect(solari=2))
        case "accept_contract", 0:
            return (DrawImperiumCardsEffect(1),)
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

    owner = state.players[player]
    next_owner = owner
    effects: tuple[AutomaticEffect, ...]
    if space_id == "high_council":
        if owner.high_council:
            effects = (
                GainResourcesEffect(spice=2),
                DrawIntrigueCardsEffect(1),
                RecruitTroopsEffect(3),
            )
        else:
            next_owner = replace(owner, high_council=True)
            effects = ()
    elif space_id == "swordmaster":
        if owner.swordmaster_acquired:
            raise RuntimeError("a player cannot acquire Swordmaster twice")
        next_owner = replace(
            owner,
            swordmaster_acquired=True,
            agents_available=owner.agents_available + 1,
        )
        effects = ()
    else:
        effects = board_effects_for(state, space_id, cost_option)
    personal_draw_count = 0
    intrigue_draw_count = 0
    for effect in effects:
        match effect:
            case GainResourcesEffect():
                next_owner = _gain_resources(next_owner, effect)
            case DrawImperiumCardsEffect():
                personal_draw_count += effect.count
            case DrawIntrigueCardsEffect():
                intrigue_draw_count += effect.count
            case RecruitTroopsEffect():
                next_owner, recruited = recruit_troops(next_owner, effect.count)
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
    effect_state = replace(state, players=players)
    intrigue_events: tuple[GameEvent, ...] = ()
    if intrigue_draw_count:
        intrigue_draw = draw_or_queue_intrigue_cards(
            effect_state,
            player,
            intrigue_draw_count,
            source=f"round:{state.round_number}:player:{player}:board:{space_id}",
        )
        effect_state = intrigue_draw.state
        intrigue_events = intrigue_draw.events
    next_state = advance_after_effect(effect_state, context)
    draw_events: tuple[GameEvent, ...] = ()
    if personal_draw_count:
        draw = draw_or_request_personal_cards(
            next_state,
            player,
            personal_draw_count,
            source=f"round:{state.round_number}:player:{player}:board:{space_id}",
        )
        next_state = draw.state
        draw_events = draw.events
    contract_events: tuple[GameEvent, ...] = ()
    if (
        space_id in ("accept_contract", "dutiful_service")
        and state.config.choam_module
    ):
        contracts = begin_contract_gain(
            next_state,
            player,
            1,
            source=(f"round:{state.round_number}:player:{player}:board:{space_id}"),
        )
        next_state = contracts.state
        contract_events = contracts.events
    event = GameEvent(
        event_id=f"round:{state.round_number}:player:{player}:board:{space_id}",
        kind="board_effect_resolved",
        payload=(("player", player), ("space_id", space_id)),
    )
    return RuleResult(
        state=next_state,
        events=(*intrigue_events, *draw_events, *contract_events, event),
    )


def legal_espionage_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Espionage's optional Spy placement or required recall choices."""

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
        or context.get("space_id") != "espionage"
    ):
        return ()

    owner = state.players[player]
    recalled = context.get("espionage_spy_recalled") is True
    # Placement needs a Spy in supply right now [Main pp. 11, 20]; a recall
    # made for Espionage may already have been consumed by another freely
    # ordered effect, so an empty supply always reopens the recall choice.
    if owner.spies_supply > 0:
        placements = tuple(
            DomainAction(
                action_id="resolve_espionage_place_spy",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in empty_observation_post_ids(state)
        )
        if recalled:
            return placements
        return (
            DomainAction(action_id="resolve_espionage_without_spy", actor=player),
            *placements,
        )

    recalls = tuple(
        DomainAction(
            action_id="recall_spy_for_espionage",
            actor=player,
            arguments=(("post_id", post_id),),
        )
        for post_id in owner.spy_post_ids
    )
    if recalled:
        return recalls
    # The printed Spy placement is optional [Board Guide p. 1], so with an
    # empty supply the player may still resolve Espionage without recalling.
    return (
        DomainAction(action_id="resolve_espionage_without_spy", actor=player),
        *recalls,
    )


def apply_espionage_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve Espionage, including its two-step recall-then-place branch."""

    if action not in legal_espionage_actions(state, action.actor):
        raise ValueError("action is not a legal Espionage choice")
    _, context = current_agent_effect_context(state)
    owner = state.players[action.actor]
    post_id = dict(action.arguments).get("post_id")

    if action.action_id == "recall_spy_for_espionage":
        if not isinstance(post_id, str):
            raise RuntimeError("Espionage recall has invalid post ID")
        next_owner = recall_spy(owner, post_id)
        context["espionage_spy_recalled"] = True
        context["spy_recalled_this_turn"] = True
        players = tuple(
            next_owner if candidate.player_id == action.actor else candidate
            for candidate in state.players
        )
        next_state = advance_after_effect(state, context, players)
        event = GameEvent(
            event_id=(
                f"round:{state.round_number}:player:{action.actor}:spy_recalled:"
                f"espionage:{post_id}"
            ),
            kind="spy_recalled",
            payload=(
                ("player", action.actor),
                ("post_id", post_id),
                ("source", "espionage"),
            ),
        )
        return RuleResult(state=next_state, events=(event,))

    next_owner = owner
    events: list[GameEvent] = []
    if action.action_id == "resolve_espionage_place_spy":
        if not isinstance(post_id, str):
            raise RuntimeError("Espionage placement has invalid post ID")
        next_owner = place_spy(next_owner, post_id)
        events.append(
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{action.actor}:spy_placed:"
                    f"espionage:{post_id}"
                ),
                kind="spy_placed",
                payload=(
                    ("player", action.actor),
                    ("post_id", post_id),
                    ("source", "espionage"),
                ),
            )
        )

    players = tuple(
        next_owner if candidate.player_id == action.actor else candidate
        for candidate in state.players
    )
    context["pending_board_effect"] = False
    next_state = advance_after_effect(state, context, players)
    draw = draw_or_request_personal_cards(
        next_state,
        action.actor,
        1,
        source=(f"round:{state.round_number}:player:{action.actor}:board:espionage"),
    )
    next_state = draw.state
    events.extend(draw.events)
    events.append(
        GameEvent(
            event_id=(
                f"round:{state.round_number}:player:{action.actor}:board:espionage"
            ),
            kind="board_effect_resolved",
            payload=(
                ("action_id", action.action_id),
                ("player", action.actor),
                ("space_id", "espionage"),
            ),
        )
    )
    return RuleResult(state=next_state, events=tuple(events))


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
        owner, recruited = recruit_troops(owner, 1)
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


def legal_shipping_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Shipping's Faction choices for its Influence reward."""

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
        or context.get("space_id") != "shipping"
    ):
        return ()
    return tuple(
        DomainAction(
            action_id="choose_shipping_influence",
            actor=player,
            arguments=(("faction", faction.value),),
        )
        for faction in Faction
    )


def apply_shipping_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Grant Shipping's Solari and chosen Faction Influence reward."""

    if action not in legal_shipping_actions(state, action.actor):
        raise ValueError("action is not a legal Shipping choice")
    _, context = current_agent_effect_context(state)
    faction_value = dict(action.arguments).get("faction")
    if not isinstance(faction_value, str):
        raise RuntimeError("Shipping Influence choice has invalid Faction")
    faction = Faction(faction_value)

    owner = state.players[action.actor]
    owner = replace(
        owner,
        resources=replace(owner.resources, solari=owner.resources.solari + 5),
    )
    players = tuple(
        owner if candidate.player_id == action.actor else candidate
        for candidate in state.players
    )
    effect_state = replace(state, players=players)

    gained = gain_faction_influence(
        effect_state,
        action.actor,
        faction,
        1,
        event_prefix=(
            f"round:{state.round_number}:player:{action.actor}:board:shipping:"
            f"influence:{faction.value}"
        ),
    )

    context["pending_board_effect"] = False
    next_state = advance_after_effect(gained.state, context, gained.state.players)
    event = GameEvent(
        event_id=(f"round:{state.round_number}:player:{action.actor}:board:shipping"),
        kind="board_effect_resolved",
        payload=(
            ("action_id", action.action_id),
            ("player", action.actor),
            ("space_id", "shipping"),
        ),
    )
    return RuleResult(state=next_state, events=(*gained.events, event))


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
        # A summoned sandworm is immediately deployed [Main p. 20], so the
        # Emperor of the Known Universe restriction withholds it.
        and not units_deployment_blocked(state, player)
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
            units_deployed_turn=owner.units_deployed_turn + sandworms,
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

