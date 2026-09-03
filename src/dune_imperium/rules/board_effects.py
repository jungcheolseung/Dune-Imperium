"""Typed resolution of implemented Uprising board-space effects.

Every printed icon of a visited space is one independently resolved effect:
the owner orders the icons freely against each other and against the card,
Faction, and Contract groups of the same Agent turn ("You may carry out all
these effects in any order" [Main p. 9]; OQ-027). Automatic icons resolve
through ``resolve_board_effect`` carrying an ``effect`` key; icons that need
a choice (a Spy post, a card to trash, a Faction) resolve through the space's
dedicated actions further down this module.
"""

from dataclasses import replace
from typing import Final, assert_never

from dune_imperium.content.uprising.board import Faction
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState, Resources
from dune_imperium.core.state import GameState
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.contracts import begin_contract_gain
from dune_imperium.rules.effects import (
    AutomaticEffect,
    DrawImperiumCardsEffect,
    DrawIntrigueCardsEffect,
    GainResourcesEffect,
    RecruitTroopsEffect,
    advance_after_effect,
    board_icon_is_pending,
    current_agent_effect_context,
    finish_board_icon,
    pending_board_icons,
    recruit_troops,
)
from dune_imperium.rules.frames import (
    FrameKind,
    context_int,
    context_str,
    replace_player,
    top_frame_of_kind,
)
from dune_imperium.rules.influence import gain_faction_influence
from dune_imperium.rules.intrigue_deck import (
    draw_intrigue_cards,
    draw_or_queue_intrigue_cards,
)
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

_FRAME_LABEL = "Agent-turn effect frame"

# Icon keys resolved by the generic ``resolve_board_effect`` action with
# ``effect=<key>``. Kept sorted: the action codec enumerates them.
BOARD_ICON_CARDS: Final = "cards"
BOARD_ICON_CONTRACT: Final = "contract"
BOARD_ICON_HIGH_COUNCIL: Final = "high_council"
BOARD_ICON_INTRIGUE: Final = "intrigue"
BOARD_ICON_RESOURCES: Final = "resources"
BOARD_ICON_SWORDMASTER: Final = "swordmaster"
BOARD_ICON_TROOPS: Final = "troops"
AUTOMATIC_BOARD_ICONS: Final = (
    BOARD_ICON_CARDS,
    BOARD_ICON_CONTRACT,
    BOARD_ICON_HIGH_COUNCIL,
    BOARD_ICON_INTRIGUE,
    BOARD_ICON_RESOURCES,
    BOARD_ICON_SWORDMASTER,
    BOARD_ICON_TROOPS,
)

# Icon keys resolved through a space's dedicated choice actions.
BOARD_ICON_SPY: Final = "spy"  # Espionage: the optional Spy placement
BOARD_ICON_TRASH: Final = "trash"  # Desert Tactics: the optional card trash
BOARD_ICON_INFLUENCE: Final = "influence"  # Shipping: Influence with a chosen Faction
BOARD_ICON_SIETCH_TABR: Final = "sietch_tabr"  # one printed choose-one row
BOARD_ICON_MAKER: Final = "maker"  # bonus spice, then spice or sandworms
BOARD_ICON_IMPERIAL_PRIVILEGE: Final = "imperial_privilege"  # written sentences

# Board spaces with at least one icon that is resolved through a dedicated
# choice rather than the generic ``resolve_board_effect`` action.
CHOICE_DRIVEN_SPACE_IDS = frozenset(
    {
        "espionage",
        "sietch_tabr",
        "deep_desert",
        "hagga_basin",
        "imperial_basin",
        "shipping",
        "desert_tactics",
        "imperial_privilege",
    }
)

# High Council after the Councilor is seated: "spice 2, Intrigue 1장, troop
# 3개" on every later visit [Board Guide p. 2].
HIGH_COUNCIL_REVISIT_EFFECTS: Final = (
    GainResourcesEffect(spice=2),
    DrawIntrigueCardsEffect(1),
    RecruitTroopsEffect(3),
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
    the same table the engine executes. Choice-driven spaces list only their
    automatic icons here (Espionage's card draw, Desert Tactics' troop,
    Shipping's Solari); High Council's revisit rewards depend on the visitor
    and live in ``visit_board_effects``.
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
        case "espionage", 0:
            return (DrawImperiumCardsEffect(1),)
        case "fremkit", 0:
            return (DrawImperiumCardsEffect(1),)
        case "desert_tactics", 0:
            return (RecruitTroopsEffect(1),)
        case "assembly_hall", 0:
            return (DrawIntrigueCardsEffect(1),)
        case "secrets", 0:
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
        case "shipping", 0:
            return (GainResourcesEffect(solari=5),)
        case "accept_contract", 0 if not choam_module:
            return (DrawImperiumCardsEffect(1), GainResourcesEffect(solari=2))
        case "accept_contract", 0:
            return (DrawImperiumCardsEffect(1),)
        case _:
            raise NotImplementedError(
                f"board effect is not implemented: {space_id} option {cost_option}"
            )


def visit_board_effects(
    owner: PlayerState,
    space_id: str,
    cost_option: int,
    *,
    choam_module: bool,
) -> tuple[AutomaticEffect, ...]:
    """Return the automatic icons one visit by ``owner`` resolves."""

    if space_id == "high_council":
        return HIGH_COUNCIL_REVISIT_EFFECTS if owner.high_council else ()
    return static_board_effects(space_id, cost_option, choam_module=choam_module)


def board_icon_for_effect(effect: AutomaticEffect) -> str:
    """Return the icon key one automatic effect is resolved under."""

    match effect:
        case GainResourcesEffect():
            return BOARD_ICON_RESOURCES
        case DrawImperiumCardsEffect():
            return BOARD_ICON_CARDS
        case DrawIntrigueCardsEffect():
            return BOARD_ICON_INTRIGUE
        case RecruitTroopsEffect():
            return BOARD_ICON_TROOPS
        case _:
            assert_never(effect)


def board_icons_for(
    state: GameState,
    player: int,
    space_id: str,
    cost_option: int,
) -> tuple[str, ...]:
    """Return the printed icons of one visit, in printed order.

    Each key is one independently resolved effect [Main p. 9]: automatic keys
    through ``resolve_board_effect``, the rest through the space's own choice
    actions. A printed choose-one row (Sietch Tabr, the Maker spaces' spice or
    sandworms) and Imperial Privilege's two written sentences stay single
    keys, and Secrets' random steal is text that follows its Intrigue draw
    (OQ-027).
    """

    owner = state.players[player]
    choam_module = state.config.choam_module
    match space_id:
        case "high_council" if not owner.high_council:
            return (BOARD_ICON_HIGH_COUNCIL,)
        case "swordmaster":
            return (BOARD_ICON_SWORDMASTER,)
        case "sietch_tabr":
            return (BOARD_ICON_SIETCH_TABR,)
        case "deep_desert" | "hagga_basin" | "imperial_basin":
            return (BOARD_ICON_MAKER,)
        case "imperial_privilege":
            return (BOARD_ICON_IMPERIAL_PRIVILEGE,)
    icons = [
        board_icon_for_effect(effect)
        for effect in visit_board_effects(
            owner, space_id, cost_option, choam_module=choam_module
        )
    ]
    match space_id:
        case "espionage":
            icons.append(BOARD_ICON_SPY)
        case "desert_tactics":
            icons.append(BOARD_ICON_TRASH)
        case "shipping":
            icons.append(BOARD_ICON_INFLUENCE)
        case "accept_contract" | "dutiful_service" if choam_module:
            icons.append(BOARD_ICON_CONTRACT)
    if len(set(icons)) != len(icons):
        raise RuntimeError(f"board icons of {space_id} must be distinct: {icons}")
    return tuple(icons)


def legal_board_effect_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return one ``resolve_board_effect`` action per pending automatic icon."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    return tuple(
        DomainAction(
            action_id="resolve_board_effect",
            actor=player,
            arguments=(("effect", key),),
        )
        for key in pending_board_icons(context)
        if key in AUTOMATIC_BOARD_ICONS
    )


def _icon_effect(
    effects: tuple[AutomaticEffect, ...],
    key: str,
) -> AutomaticEffect | None:
    return next(
        (effect for effect in effects if board_icon_for_effect(effect) == key),
        None,
    )


def _secrets_victims(state: GameState, thief: int) -> tuple[int, ...]:
    """Return opponents clockwise from ``thief`` holding 4+ Intrigue cards.

    Only HELD Intrigue counts [Board Guide p. 2, Main p. 7]; face-up trigger
    cards in ``intrigue_faceup`` are played, not held, and do not count.
    """
    players = state.config.players
    return tuple(
        seat
        for seat in ((thief + offset) % players for offset in range(1, players))
        if len(state.players[seat].intrigue_cards) >= 4
    )


def _secrets_steal_frame(
    state: GameState,
    thief: int,
    victim: int,
    options: tuple[str, ...],
) -> DecisionFrame:
    decision_id = (
        f"round:{state.round_number}:player:{thief}:board:secrets:steal:{victim}"
    )
    return DecisionFrame(
        kind=FrameKind.SECRETS_STEAL,
        frame_id=f"{decision_id}:secrets_steal",
        decision=ChanceDecision(
            decision_id=decision_id,
            prompt=f"Randomly steal one Intrigue card from player {victim}",
            options=options,
            count=1,
        ),
        context=(("thief", thief), ("victim", victim)),
    )


def secrets_steal_is_pending(state: GameState) -> bool:
    """Return whether the top decision is a Secrets random-steal chance."""

    frame = top_frame_of_kind(state, FrameKind.SECRETS_STEAL)
    return frame is not None and isinstance(frame.decision, ChanceDecision)


def apply_secrets_steal(state: GameState, outcome: ChanceOutcome) -> RuleResult:
    """Move the randomly chosen Intrigue card from victim to thief."""

    frame = top_frame_of_kind(state, FrameKind.SECRETS_STEAL)
    if frame is None or not isinstance(frame.decision, ChanceDecision):
        raise ValueError("the current chance decision is not a Secrets steal")
    context = dict(frame.context)
    owner_label = "Secrets steal frame"
    thief = context_int(context, "thief", owner=owner_label)
    victim = context_int(context, "victim", owner=owner_label)
    card_id = outcome.values[0]

    victim_state = state.players[victim]
    thief_state = state.players[thief]
    next_victim = replace(
        victim_state,
        intrigue_cards=tuple(c for c in victim_state.intrigue_cards if c != card_id),
    )
    next_thief = replace(
        thief_state, intrigue_cards=(*thief_state.intrigue_cards, card_id)
    )
    players = tuple(
        next_victim
        if candidate.player_id == victim
        else next_thief
        if candidate.player_id == thief
        else candidate
        for candidate in state.players
    )
    next_state = replace(state.pop_decision(), players=players)
    # The theft itself is public (both Intrigue counts change at the table),
    # but the stolen identity is not: Intrigue cards stay hidden from
    # opponents until played [Main p. 7], so only the thief and the victim
    # learn which card moved (OQ-010 ruling 3).
    events = (
        GameEvent(
            event_id=f"{frame.decision.decision_id}:stolen",
            kind="intrigue_card_stolen",
            payload=(("player", thief), ("victim", victim)),
        ),
        GameEvent(
            event_id=f"{frame.decision.decision_id}:stolen:identity",
            kind="intrigue_card_stolen_identity",
            payload=(("card_id", card_id), ("player", thief), ("victim", victim)),
            visible_to=(thief, victim),
        ),
    )
    return RuleResult(state=next_state, events=events)


def resolve_board_effect(state: GameState, action: DomainAction) -> RuleResult:
    """Resolve one printed icon of the visited space in the current Agent turn.

    The ``effect`` argument names the icon; the other icons of the space stay
    pending for their own actions, so the owner sequences them freely against
    each other and against the card, Faction, and Contract groups
    [Main p. 9] (OQ-027).
    """

    if action not in legal_board_effect_actions(state, action.actor):
        raise ValueError("action is not a legal board-effect resolution")
    _, context = current_agent_effect_context(state)
    player = action.actor
    space_id = context_str(context, "space_id", owner=_FRAME_LABEL)
    cost_option = context_int(context, "cost_option", owner=_FRAME_LABEL)
    key = str(dict(action.arguments)["effect"])
    owner = state.players[player]
    effects = visit_board_effects(
        owner, space_id, cost_option, choam_module=state.config.choam_module
    )
    source = f"round:{state.round_number}:player:{player}:board:{space_id}"
    finish_board_icon(context, key)

    next_owner = owner
    personal_draw_count = 0
    intrigue_draw_count = 0
    match _icon_effect(effects, key):
        case GainResourcesEffect() as effect:
            next_owner = _gain_resources(owner, effect)
        case DrawImperiumCardsEffect() as effect:
            personal_draw_count = effect.count
        case DrawIntrigueCardsEffect() as effect:
            intrigue_draw_count = effect.count
        case RecruitTroopsEffect() as effect:
            next_owner, recruited = recruit_troops(owner, effect.count)
            context["troops_recruited"] = (
                context_int(context, "troops_recruited", owner=_FRAME_LABEL)
                + recruited
            )
        case None if key == BOARD_ICON_HIGH_COUNCIL:
            next_owner = replace(owner, high_council=True)
        case None if key == BOARD_ICON_SWORDMASTER:
            if owner.swordmaster_acquired:
                raise RuntimeError("a player cannot acquire Swordmaster twice")
            next_owner = replace(
                owner,
                swordmaster_acquired=True,
                agents_available=owner.agents_available + 1,
            )
        case None if key == BOARD_ICON_CONTRACT:
            pass
        case _:
            raise RuntimeError(f"board icon {key} has no effect on {space_id}")

    effect_state = replace(state, players=replace_player(state.players, next_owner))
    intrigue_events: tuple[GameEvent, ...] = ()
    if intrigue_draw_count:
        intrigue_draw = draw_or_queue_intrigue_cards(
            effect_state,
            player,
            intrigue_draw_count,
            source=source,
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
            source=source,
        )
        next_state = draw.state
        draw_events = draw.events
    contract_events: tuple[GameEvent, ...] = ()
    if key == BOARD_ICON_CONTRACT:
        contracts = begin_contract_gain(next_state, player, 1, source=source)
        next_state = contracts.state
        contract_events = contracts.events
    steal_events: tuple[GameEvent, ...] = ()
    if key == BOARD_ICON_INTRIGUE and space_id == "secrets":
        # The random steal is printed text that follows the Intrigue draw
        # [Board Guide p. 2], so it rides on the draw icon (OQ-027).
        victims = _secrets_victims(next_state, player)
        for victim in reversed(victims):
            next_state = next_state.push_decision(
                _secrets_steal_frame(
                    next_state,
                    player,
                    victim,
                    next_state.players[victim].intrigue_cards,
                )
            )
        if victims and next_state.pending_intrigue_draws:
            queued_player, queued_count, queued_source = (
                next_state.pending_intrigue_draws[0]
            )
            if queued_player != player or len(next_state.pending_intrigue_draws) != 1:
                raise RuntimeError("Secrets has an unexpected queued Intrigue draw")
            reshuffle = draw_intrigue_cards(
                replace(next_state, pending_intrigue_draws=()),
                queued_player,
                queued_count,
                source=queued_source,
            )
            next_state = reshuffle.state
            steal_events = reshuffle.events
    event = GameEvent(
        event_id=f"{source}:{key}",
        kind="board_effect_resolved",
        payload=(("effect", key), ("player", player), ("space_id", space_id)),
    )
    return RuleResult(
        state=next_state,
        events=(*intrigue_events, *draw_events, *contract_events, *steal_events, event),
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
    if context.get("space_id") != "espionage" or not board_icon_is_pending(
        context, BOARD_ICON_SPY
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
    # The printed card draw is a separate icon with its own
    # ``resolve_board_effect`` action, ordered by the owner (OQ-027).
    finish_board_icon(context, BOARD_ICON_SPY)
    next_state = advance_after_effect(state, context, players)
    events.append(
        GameEvent(
            event_id=(
                f"round:{state.round_number}:player:{action.actor}:board:espionage:"
                f"{BOARD_ICON_SPY}"
            ),
            kind="board_effect_resolved",
            payload=(
                ("action_id", action.action_id),
                ("effect", BOARD_ICON_SPY),
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
    if context.get("space_id") != "sietch_tabr" or not board_icon_is_pending(
        context, BOARD_ICON_SIETCH_TABR
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

    finish_board_icon(context, BOARD_ICON_SIETCH_TABR)
    next_state = advance_after_effect(effect_state, context, effect_state.players)
    events.append(
        GameEvent(
            event_id=(
                f"round:{state.round_number}:player:{action.actor}:board:sietch_tabr"
            ),
            kind="board_effect_resolved",
            payload=(
                ("action_id", action.action_id),
                ("effect", BOARD_ICON_SIETCH_TABR),
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
    if context.get("space_id") != "shipping" or not board_icon_is_pending(
        context, BOARD_ICON_INFLUENCE
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
    """Grant Shipping's Influence with the chosen Faction."""

    if action not in legal_shipping_actions(state, action.actor):
        raise ValueError("action is not a legal Shipping choice")
    _, context = current_agent_effect_context(state)
    faction_value = dict(action.arguments).get("faction")
    if not isinstance(faction_value, str):
        raise RuntimeError("Shipping Influence choice has invalid Faction")
    faction = Faction(faction_value)

    # The printed 5 Solari are a separate icon with their own
    # ``resolve_board_effect`` action, ordered by the owner (OQ-027).
    gained = gain_faction_influence(
        state,
        action.actor,
        faction,
        1,
        event_prefix=(
            f"round:{state.round_number}:player:{action.actor}:board:shipping:"
            f"influence:{faction.value}"
        ),
    )

    finish_board_icon(context, BOARD_ICON_INFLUENCE)
    next_state = advance_after_effect(gained.state, context, gained.state.players)
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{action.actor}:board:shipping:"
            f"{BOARD_ICON_INFLUENCE}"
        ),
        kind="board_effect_resolved",
        payload=(
            ("action_id", action.action_id),
            ("effect", BOARD_ICON_INFLUENCE),
            ("player", action.actor),
            ("space_id", "shipping"),
        ),
    )
    return RuleResult(state=next_state, events=(*gained.events, event))


def legal_desert_tactics_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Desert Tactics' decline-or-trash choices for its optional trash."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("space_id") != "desert_tactics" or not board_icon_is_pending(
        context, BOARD_ICON_TRASH
    ):
        return ()
    owner = state.players[player]
    return (
        DomainAction(action_id="resolve_desert_tactics_without_trash", actor=player),
        *(
            DomainAction(
                action_id="trash_card_for_desert_tactics",
                actor=player,
                arguments=(("card_id", card_id),),
            )
            for card_id in (*owner.hand, *owner.discard_pile, *owner.in_play)
        ),
    )


def apply_desert_tactics_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve Desert Tactics' optional card trash, or decline it."""

    if action not in legal_desert_tactics_actions(state, action.actor):
        raise ValueError("action is not a legal Desert Tactics choice")
    _, context = current_agent_effect_context(state)
    # The printed troop is a separate icon with its own
    # ``resolve_board_effect`` action, ordered by the owner (OQ-027).
    effect_state = state
    events: list[GameEvent] = []
    if action.action_id == "trash_card_for_desert_tactics":
        card_value = dict(action.arguments)["card_id"]
        if not isinstance(card_value, str):
            raise RuntimeError("Desert Tactics trash choice has invalid card ID")
        trashed = trash_personal_card(
            effect_state,
            action.actor,
            card_value,
            source=(
                f"round:{state.round_number}:player:{action.actor}:board:"
                "desert_tactics"
            ),
        )
        effect_state = trashed.state
        events.extend(trashed.events)

    finish_board_icon(context, BOARD_ICON_TRASH)
    next_state = advance_after_effect(effect_state, context, effect_state.players)
    events.append(
        GameEvent(
            event_id=(
                f"round:{state.round_number}:player:{action.actor}:board:"
                f"desert_tactics:{BOARD_ICON_TRASH}"
            ),
            kind="board_effect_resolved",
            payload=(
                ("action_id", action.action_id),
                ("effect", BOARD_ICON_TRASH),
                ("player", action.actor),
                ("space_id", "desert_tactics"),
            ),
        )
    )
    return RuleResult(state=next_state, events=tuple(events))


def legal_imperial_privilege_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Imperial Privilege's optional Intrigue slot, then its recall."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("space_id") != "imperial_privilege" or not board_icon_is_pending(
        context, BOARD_ICON_IMPERIAL_PRIVILEGE
    ):
        return ()

    owner = state.players[player]
    if context.get("imperial_privilege_intrigue_resolved") is not True:
        return (
            DomainAction(
                action_id="decline_imperial_privilege_intrigue", actor=player
            ),
            *(
                DomainAction(
                    action_id="discard_intrigue_for_imperial_privilege",
                    actor=player,
                    arguments=(("card_id", card_id),),
                )
                for card_id in owner.intrigue_cards
            ),
        )
    return tuple(
        DomainAction(
            action_id="recall_agent_for_imperial_privilege",
            actor=player,
            arguments=(("space_id", space_id),),
        )
        for space_id in owner.agent_locations
        if space_id != "imperial_privilege"
    )


def apply_imperial_privilege_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve Imperial Privilege's optional Intrigue swap, then its recall."""

    if action not in legal_imperial_privilege_actions(state, action.actor):
        raise ValueError("action is not a legal Imperial Privilege choice")
    _, context = current_agent_effect_context(state)
    owner = state.players[action.actor]
    source = (
        f"round:{state.round_number}:player:{action.actor}:board:imperial_privilege"
    )

    if action.action_id == "recall_agent_for_imperial_privilege":
        space_id = dict(action.arguments).get("space_id")
        if not isinstance(space_id, str):
            raise RuntimeError("Imperial Privilege recall has invalid space ID")
        next_owner = replace(
            owner,
            agents_available=owner.agents_available + 1,
            agent_locations=tuple(
                location for location in owner.agent_locations if location != space_id
            ),
        )
        players = tuple(
            next_owner if candidate.player_id == action.actor else candidate
            for candidate in state.players
        )
        finish_board_icon(context, BOARD_ICON_IMPERIAL_PRIVILEGE)
        next_state = advance_after_effect(state, context, players)
        draw = draw_or_request_personal_cards(
            next_state, action.actor, 1, source=source
        )
        next_state = draw.state
        recall_events = (
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{action.actor}:"
                    f"agent_recalled:imperial_privilege:{space_id}"
                ),
                kind="agent_recalled",
                payload=(
                    ("player", action.actor),
                    ("source", "imperial_privilege"),
                    ("space_id", space_id),
                ),
            ),
            *draw.events,
            GameEvent(
                event_id=source,
                kind="board_effect_resolved",
                payload=(
                    ("action_id", action.action_id),
                    ("effect", BOARD_ICON_IMPERIAL_PRIVILEGE),
                    ("player", action.actor),
                    ("space_id", "imperial_privilege"),
                ),
            ),
        )
        return RuleResult(state=next_state, events=recall_events)

    effect_state = state
    events: list[GameEvent] = []
    if action.action_id == "discard_intrigue_for_imperial_privilege":
        card_id = dict(action.arguments).get("card_id")
        if not isinstance(card_id, str):
            raise RuntimeError("Imperial Privilege discard has invalid card ID")
        discarding_owner = replace(
            owner,
            intrigue_cards=tuple(
                held for held in owner.intrigue_cards if held != card_id
            ),
        )
        effect_state = replace(
            state,
            players=tuple(
                discarding_owner if candidate.player_id == action.actor else candidate
                for candidate in state.players
            ),
            intrigue_discard=(*state.intrigue_discard, card_id),
        )
        events.append(
            GameEvent(
                event_id=f"{source}:discarded:{card_id}",
                kind="intrigue_card_discarded",
                payload=(("card_id", card_id), ("player", action.actor)),
            )
        )
        drawn = draw_or_queue_intrigue_cards(
            effect_state, action.actor, 1, source=source
        )
        effect_state = drawn.state
        events.extend(drawn.events)

    context["imperial_privilege_intrigue_resolved"] = True
    other_spaces = tuple(
        location
        for location in effect_state.players[action.actor].agent_locations
        if location != "imperial_privilege"
    )
    if not other_spaces:
        # With no other deployed Agent only the recall is skipped; the card
        # draw is a separate printed effect and still resolves (OQ-023
        # decided ruling, [Board Guide p. 2]).
        finish_board_icon(context, BOARD_ICON_IMPERIAL_PRIVILEGE)
        next_state = advance_after_effect(
            effect_state, context, effect_state.players
        )
        draw = draw_or_request_personal_cards(
            next_state, action.actor, 1, source=source
        )
        next_state = draw.state
        events.append(
            GameEvent(
                event_id=f"{source}:recall_skipped",
                kind="imperial_privilege_recall_skipped",
                payload=(("player", action.actor),),
            )
        )
        events.extend(draw.events)
        events.append(
            GameEvent(
                event_id=source,
                kind="board_effect_resolved",
                payload=(
                    ("action_id", action.action_id),
                    ("effect", BOARD_ICON_IMPERIAL_PRIVILEGE),
                    ("player", action.actor),
                    ("space_id", "imperial_privilege"),
                ),
            )
        )
        return RuleResult(state=next_state, events=tuple(events))

    next_state = advance_after_effect(effect_state, context, effect_state.players)
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
    if space_id not in (
        "deep_desert",
        "hagga_basin",
        "imperial_basin",
    ) or not board_icon_is_pending(context, BOARD_ICON_MAKER):
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
    finish_board_icon(context, BOARD_ICON_MAKER)
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
            ("effect", BOARD_ICON_MAKER),
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

