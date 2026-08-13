"""Card acquisition during a Reveal turn."""

from dataclasses import replace

from dune_imperium.content.uprising.imperium import imperium_card_for_instance
from dune_imperium.content.uprising.reserve import RESERVE_STACKS_BY_ID
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.reveal_turn import current_reveal_context


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
    return RuleResult(state=next_state, events=(event,))


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
    if definition.has_acquisition_bonus:
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
    next_owner = replace(
        owner,
        discard_pile=(*owner.discard_pile, instance_id),
    )
    players = tuple(
        next_owner if player.player_id == action.actor else player
        for player in state.players
    )
    context["persuasion"] = persuasion - cost
    frame = state.decision_stack[-1]
    next_frame = replace(frame, context=tuple(sorted(context.items())))
    next_state = replace(
        state,
        players=players,
        imperium_deck=state.imperium_deck[1:],
        imperium_row=tuple(row),
        decision_stack=(*state.decision_stack[:-1], next_frame),
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
    return RuleResult(state=next_state, events=(event,))
