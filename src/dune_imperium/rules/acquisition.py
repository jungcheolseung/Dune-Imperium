"""Card acquisition during a Reveal turn."""

from dataclasses import replace

from dune_imperium.content.uprising.imperium import imperium_card_for_instance
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.reserve import RESERVE_STACKS_BY_ID
from dune_imperium.content.uprising.types import (
    PersonalCardAcquisitionEffect,
    PersonalCardRevealAcquisitionEffect,
)
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.influence import gain_faction_influence
from dune_imperium.rules.reveal_turn import current_reveal_context
from dune_imperium.rules.spy_placement import (
    empty_observation_post_ids,
    place_spy,
    recall_spy,
    spied_factions,
)


def legal_acquisition_spy_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return choices for a place-Spy acquisition bonus."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if (
        not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
        or "acquisition_card_id" not in context
    ):
        return ()
    owner = state.players[player]
    if context.get("acquisition_spy_recalled") is True or owner.spies_supply > 0:
        return tuple(
            DomainAction(
                action_id="place_acquisition_spy",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in empty_observation_post_ids(state)
        )
    return tuple(
        DomainAction(
            action_id="recall_spy_for_acquisition",
            actor=player,
            arguments=(("post_id", post_id),),
        )
        for post_id in owner.spy_post_ids
    )


def apply_acquisition_spy_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Recall if necessary, then place the Spy granted on acquisition."""

    if action not in legal_acquisition_spy_actions(state, action.actor):
        raise ValueError("action is not a legal acquisition Spy choice")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    card_id = context["acquisition_card_id"]
    post_id = dict(action.arguments).get("post_id")
    if not isinstance(card_id, str) or not isinstance(post_id, str):
        raise RuntimeError("acquisition Spy frame has invalid context")
    owner = state.players[action.actor]
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"acquire:{card_id}"
    )

    if action.action_id == "recall_spy_for_acquisition":
        next_owner = recall_spy(owner, post_id)
        context["acquisition_spy_recalled"] = True
        next_frame = replace(frame, context=tuple(sorted(context.items())))
        next_state = replace(
            state,
            players=_replace_player(state, next_owner),
            decision_stack=(*state.decision_stack[:-1], next_frame),
        )
        event = GameEvent(
            event_id=f"{source}:spy_recalled:{post_id}",
            kind="spy_recalled",
            payload=(
                ("player", action.actor),
                ("post_id", post_id),
                ("source", card_id),
            ),
        )
        return RuleResult(state=next_state, events=(event,))

    next_owner = place_spy(owner, post_id)
    next_state = replace(
        state,
        players=_replace_player(state, next_owner),
        decision_stack=state.decision_stack[:-1],
    )
    event = GameEvent(
        event_id=f"{source}:spy_placed:{post_id}",
        kind="spy_placed",
        payload=(
            ("card_id", card_id),
            ("player", action.actor),
            ("post_id", post_id),
        ),
    )
    return RuleResult(state=next_state, events=(event,))


def legal_reserve_acquisitions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Enumerate affordable, non-empty Reserve stacks for the revealer."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        context = current_reveal_context(state)
    except ValueError:
        return ()
    owner = context["turn_owner"]
    persuasion = context["persuasion"]
    if (
        isinstance(owner, bool)
        or not isinstance(owner, int)
        or isinstance(persuasion, bool)
        or not isinstance(persuasion, int)
    ):
        raise RuntimeError("Reveal frame has invalid acquisition context")
    if owner != player:
        return ()

    return tuple(
        DomainAction(
            action_id="acquire_reserve",
            actor=player,
            arguments=(("card_id", card_id),),
        )
        for card_id, count in state.reserve_stacks
        if count > 0
        and RESERVE_STACKS_BY_ID[card_id].acquisition_cost <= persuasion
    )


def apply_reserve_acquisition(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Spend Persuasion and put one Reserve card in the discard pile."""

    if action not in legal_reserve_acquisitions(state, action.actor):
        raise ValueError("action is not a legal Reserve acquisition")
    card_id = dict(action.arguments)["card_id"]
    if not isinstance(card_id, str):
        raise ValueError("Reserve acquisition card_id must be a string")
    definition = RESERVE_STACKS_BY_ID[card_id]
    context = current_reveal_context(state)
    persuasion = context["persuasion"]
    if isinstance(persuasion, bool) or not isinstance(persuasion, int):
        raise RuntimeError("Reveal frame has invalid Persuasion")

    stack_count = dict(state.reserve_stacks)[card_id]
    instance_id = f"reserve:{card_id}:{stack_count - 1}"
    owner = state.players[action.actor]
    next_owner = replace(
        owner,
        discard_pile=(*owner.discard_pile, instance_id),
        victory_points=owner.victory_points + definition.acquisition_vp,
    )
    players = tuple(
        next_owner if player.player_id == action.actor else player
        for player in state.players
    )
    reserve_stacks = tuple(
        (candidate_id, count - 1 if candidate_id == card_id else count)
        for candidate_id, count in state.reserve_stacks
    )
    context["persuasion"] = persuasion - definition.acquisition_cost
    frame = state.decision_stack[-1]
    next_frame = replace(frame, context=tuple(sorted(context.items())))
    next_state = replace(
        state,
        players=players,
        reserve_stacks=reserve_stacks,
        decision_stack=(*state.decision_stack[:-1], next_frame),
    )
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{action.actor}:acquire:{instance_id}"
        ),
        kind="card_acquired",
        payload=(("card_id", card_id), ("player", action.actor)),
    )
    triggered = _resolve_reveal_acquisition_triggers(
        next_state,
        action.actor,
        card_id,
    )
    return RuleResult(state=triggered.state, events=(event, *triggered.events))


def legal_imperium_acquisitions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Enumerate affordable cards currently visible in the Imperium Row."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        context = current_reveal_context(state)
    except ValueError:
        return ()
    owner = context["turn_owner"]
    persuasion = context["persuasion"]
    if (
        isinstance(owner, bool)
        or not isinstance(owner, int)
        or isinstance(persuasion, bool)
        or not isinstance(persuasion, int)
    ):
        raise RuntimeError("Reveal frame has invalid acquisition context")
    if owner != player:
        return ()

    actions: list[DomainAction] = []
    for instance_id in state.imperium_row:
        cost = imperium_card_for_instance(instance_id).acquisition_cost
        if cost is not None and cost <= persuasion:
            actions.append(
                DomainAction(
                    action_id="acquire_imperium",
                    actor=player,
                    arguments=(("instance_id", instance_id),),
                )
            )
    return tuple(actions)


def apply_imperium_acquisition(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Acquire one Row card and immediately refill its position."""

    if action not in legal_imperium_acquisitions(state, action.actor):
        raise ValueError("action is not a legal Imperium Row acquisition")
    instance_id = dict(action.arguments)["instance_id"]
    if not isinstance(instance_id, str):
        raise ValueError("Imperium acquisition instance_id must be a string")
    definition = imperium_card_for_instance(instance_id)
    if definition.has_acquisition_bonus and definition.acquisition_effect is None:
        raise NotImplementedError(
            f"acquisition bonus is not implemented: {definition.card.card_id}"
        )
    if not state.imperium_deck:
        raise NotImplementedError(
            "Imperium Row refill after deck exhaustion is unresolved"
        )
    cost = definition.acquisition_cost
    if cost is None:
        raise RuntimeError("Imperium card is missing its acquisition cost")

    context = current_reveal_context(state)
    persuasion = context["persuasion"]
    if isinstance(persuasion, bool) or not isinstance(persuasion, int):
        raise RuntimeError("Reveal frame has invalid Persuasion")
    row = list(state.imperium_row)
    row[row.index(instance_id)] = state.imperium_deck[0]
    owner = state.players[action.actor]
    intrigue_deck = state.intrigue_deck
    next_owner = replace(
        owner,
        discard_pile=(*owner.discard_pile, instance_id),
    )
    acquisition_events: tuple[GameEvent, ...] = ()
    if (
        definition.acquisition_effect
        is PersonalCardAcquisitionEffect.DRAW_INTRIGUE_CARD
    ):
        if not intrigue_deck:
            raise ValueError("the Intrigue deck does not contain enough cards")
        next_owner = replace(
            next_owner,
            intrigue_cards=(*next_owner.intrigue_cards, intrigue_deck[0]),
        )
        intrigue_deck = intrigue_deck[1:]
        acquisition_events = (
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{action.actor}:"
                    f"acquire:{instance_id}:intrigue_draw"
                ),
                kind="intrigue_card_drawn",
                payload=(("count", 1), ("player", action.actor)),
            ),
        )
    players = tuple(
        next_owner if player.player_id == action.actor else player
        for player in state.players
    )
    context["persuasion"] = persuasion - cost
    frame = state.decision_stack[-1]
    next_frame = replace(frame, context=tuple(sorted(context.items())))
    decision_stack = (*state.decision_stack[:-1], next_frame)
    if definition.acquisition_effect is PersonalCardAcquisitionEffect.PLACE_SPY:
        decision_stack = (
            *decision_stack,
            DecisionFrame(
                frame_id=(
                    f"round:{state.round_number}:player:{action.actor}:"
                    f"acquisition_spy:{instance_id}"
                ),
                decision=PlayerDecision(
                    owner=action.actor,
                    prompt="Choose an Observation Post for the acquired Spy",
                ),
                context=(
                    ("acquisition_card_id", instance_id),
                    ("turn_owner", action.actor),
                ),
            ),
        )
    next_state = replace(
        state,
        players=players,
        imperium_deck=state.imperium_deck[1:],
        imperium_row=tuple(row),
        intrigue_deck=intrigue_deck,
        decision_stack=decision_stack,
    )
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{action.actor}:acquire:{instance_id}"
        ),
        kind="card_acquired",
        payload=(
            ("card_id", definition.card.card_id),
            ("instance_id", instance_id),
            ("player", action.actor),
        ),
    )
    return RuleResult(state=next_state, events=(event, *acquisition_events))


def _replace_player(
    state: GameState,
    owner: PlayerState,
) -> tuple[PlayerState, ...]:
    return tuple(
        owner if player.player_id == owner.player_id else player
        for player in state.players
    )


def _resolve_reveal_acquisition_triggers(
    state: GameState,
    player: int,
    acquired_card_id: str,
) -> RuleResult:
    if acquired_card_id != "the_spice_must_flow":
        return RuleResult(state=state)
    trigger_cards = tuple(
        played_card_id
        for played_card_id in state.players[player].in_play
        if personal_card_for_instance(played_card_id).reveal_acquisition_effect
        is (
            PersonalCardRevealAcquisitionEffect.GAIN_INFLUENCE_FOR_EACH_SPIED_FACTION_ON_SPICE_MUST_FLOW
        )
    )
    next_state = state
    events: tuple[GameEvent, ...] = ()
    for trigger_card_id in trigger_cards:
        for faction in spied_factions(next_state.players[player]):
            gained = gain_faction_influence(
                next_state,
                player,
                faction,
                1,
                event_prefix=(
                    f"round:{state.round_number}:player:{player}:"
                    f"reveal_card:{trigger_card_id}:spice_must_flow:"
                    f"{faction.value}"
                ),
            )
            next_state = gained.state
            events = (*events, *gained.events)
    return RuleResult(state=next_state, events=events)
