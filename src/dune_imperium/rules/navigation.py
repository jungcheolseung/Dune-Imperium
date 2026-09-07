"""Steersman Y'rkoon's Navigation cards [Steersman Y'rkoon card] [Bloodlines p. 12].

Plot Course: at game start the shuffled deck deals a hand of five, four of
which the owner places face down in order (``NAVIGATION_SETUP``); the rest
return to the box. Whenever the owner reaches two Influence with a Faction
the next slot's card is played: the engine opens a ``NAVIGATION_CHOICE``
frame offering the card's playable options, which then resolve through the
Intrigue choice machinery (the cards are transcribed in the effect DSL).
"""

from dataclasses import replace

from dune_imperium.content.uprising.intrigue import intrigue_card_for_instance
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.effect_interpreter import (
    applicable_sections,
    choice_slots,
    option_is_playable,
    pay_cost,
    resource_cost,
)
from dune_imperium.rules.frames import (
    FrameKind,
    context_int,
    context_str,
    owned_top_frame,
    replace_player,
)
from dune_imperium.rules.intrigue import finish_intrigue_play

NAVIGATION_HAND = 5
NAVIGATION_SLOTS = 4


def assign_navigation_deck(state: GameState) -> GameState:
    """Deal the shuffled Navigation deck to Steersman Y'rkoon's seat.

    The owner then chooses four of the top five for the slots; the frame
    pauses the game in SETUP until the choice is made.
    """

    if not state.navigation_stock:
        return state
    seat = next(
        (
            candidate
            for candidate in state.players
            if candidate.leader_id == "steersman_y_rkoon"
        ),
        None,
    )
    if seat is None:
        return state
    hand = state.navigation_stock[:NAVIGATION_HAND]
    dealt = replace(seat, navigation_box=state.navigation_stock[NAVIGATION_HAND:])
    frame = DecisionFrame(
        kind=FrameKind.NAVIGATION_SETUP,
        frame_id=f"setup:navigation:{seat.player_id}",
        decision=PlayerDecision(
            owner=seat.player_id,
            prompt="Place four Navigation cards face down, in order",
        ),
        context=(
            ("hand", ",".join(hand)),
            ("player", seat.player_id),
            ("resume_phase", state.phase.value),
        ),
    )
    return replace(
        state,
        phase=GamePhase.SETUP,
        players=replace_player(state.players, dealt),
        navigation_stock=(),
        decision_stack=(*state.decision_stack, frame),
    )


def legal_navigation_setup_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer every card still in the dealt hand for the next slot."""

    frame = owned_top_frame(state, FrameKind.NAVIGATION_SETUP, player)
    if frame is None:
        return ()
    hand = context_str(dict(frame.context), "hand", owner="Navigation setup frame")
    return tuple(
        DomainAction(
            action_id="place_navigation_card",
            actor=player,
            arguments=(("card_id", card_id),),
        )
        for card_id in hand.split(",")
        if card_id
    )


def apply_navigation_setup_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Put the chosen card in the next slot; the fifth pick closes the setup."""

    if action not in legal_navigation_setup_actions(state, action.actor):
        raise ValueError("action is not a legal Navigation setup choice")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    card_id = str(dict(action.arguments)["card_id"])
    hand = tuple(
        held
        for held in context_str(context, "hand", owner="Navigation setup frame").split(
            ","
        )
        if held and held != card_id
    )
    owner = state.players[action.actor]
    placed = replace(owner, navigation_slots=(*owner.navigation_slots, card_id))
    event = GameEvent(
        event_id=f"{frame.frame_id}:slot:{len(placed.navigation_slots)}",
        kind="navigation_card_placed",
        payload=(("player", action.actor), ("slot", len(placed.navigation_slots))),
        visible_to=(action.actor,),
    )
    if len(placed.navigation_slots) < NAVIGATION_SLOTS:
        context["hand"] = ",".join(hand)
        next_frame = replace(frame, context=tuple(sorted(context.items())))
        return RuleResult(
            state=replace(
                state,
                players=replace_player(state.players, placed),
                decision_stack=(*state.decision_stack[:-1], next_frame),
            ),
            events=(event,),
        )
    # "Return all others to the box."
    boxed = replace(placed, navigation_box=(*placed.navigation_box, *hand))
    resume = GamePhase(
        context_str(context, "resume_phase", owner="Navigation setup frame")
    )
    return RuleResult(
        state=replace(
            state,
            phase=resume,
            players=replace_player(state.players, boxed),
            decision_stack=state.decision_stack[:-1],
        ),
        events=(
            event,
            GameEvent(
                event_id=f"{frame.frame_id}:done",
                kind="navigation_setup_finished",
                payload=(("player", action.actor), ("slots", NAVIGATION_SLOTS)),
            ),
        ),
    )


def navigation_play_is_queued(state: GameState) -> bool:
    """Return whether an owed Navigation play can open now."""

    frame = state.decision_stack[-1] if state.decision_stack else None
    return bool(state.pending_navigation_plays) and (
        frame is None or not isinstance(frame.decision, ChanceDecision)
    )


def begin_navigation_play(state: GameState) -> RuleResult:
    """Open the oldest owed Navigation play, or drop it when no card is left."""

    if not state.pending_navigation_plays:
        raise ValueError("there is no pending Navigation play")
    player, faction, source = state.pending_navigation_plays[0]
    remaining = replace(
        state, pending_navigation_plays=state.pending_navigation_plays[1:]
    )
    owner = remaining.players[player]
    if not owner.navigation_slots:
        return RuleResult(
            state=remaining,
            events=(
                GameEvent(
                    event_id=f"{source}:exhausted",
                    kind="navigation_exhausted",
                    payload=(("faction", faction), ("player", player)),
                ),
            ),
        )
    card_id = owner.navigation_slots[0]
    armed = replace(
        owner,
        navigation_active_slot=len(owner.navigation_played) + 1,
        navigation_trigger_faction=faction,
    )
    working = replace(remaining, players=replace_player(remaining.players, armed))
    options = intrigue_card_for_instance(card_id).options
    if not any(option_is_playable(working, player, option) for option in options):
        # Nothing on the card can be paid or applied (OQ-039): the card is
        # still played and spent.
        fizzled = replace(
            armed,
            navigation_slots=armed.navigation_slots[1:],
            navigation_played=(*armed.navigation_played, card_id),
            navigation_active_slot=0,
            navigation_trigger_faction="",
        )
        return RuleResult(
            state=replace(working, players=replace_player(working.players, fizzled)),
            events=(
                GameEvent(
                    event_id=f"{source}:fizzled",
                    kind="navigation_card_played",
                    payload=(
                        ("card_id", card_id),
                        ("faction", faction),
                        ("fizzled", 1),
                        ("player", player),
                    ),
                ),
            ),
        )
    frame = DecisionFrame(
        kind=FrameKind.NAVIGATION_CHOICE,
        frame_id=f"{source}:choice",
        decision=PlayerDecision(owner=player, prompt="Play the Navigation card"),
        context=(("card_id", card_id), ("faction", faction), ("source", source)),
    )
    return RuleResult(state=working.push_decision(frame))


def legal_navigation_play_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer each playable printed option of the slot's card."""

    frame = owned_top_frame(state, FrameKind.NAVIGATION_CHOICE, player)
    if frame is None:
        return ()
    card_id = context_str(dict(frame.context), "card_id", owner="Navigation frame")
    options = intrigue_card_for_instance(card_id).options
    return tuple(
        DomainAction(
            action_id="play_navigation",
            actor=player,
            arguments=(("option", index),),
        )
        for index, option in enumerate(options)
        if option_is_playable(state, player, option)
    )


def apply_navigation_play(state: GameState, action: DomainAction) -> RuleResult:
    """Pay for the chosen option and resolve it like an Intrigue play."""

    if action not in legal_navigation_play_actions(state, action.actor):
        raise ValueError("action is not a legal Navigation play")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    card_id = context_str(context, "card_id", owner="Navigation frame")
    source = context_str(context, "source", owner="Navigation frame")
    option_index = context_int(
        dict(action.arguments), "option", owner="Navigation play"
    )
    player = action.actor
    owner = state.players[player]
    option = intrigue_card_for_instance(card_id).options[option_index]
    sections = applicable_sections(
        state, player, option, shield_wall_present=state.shield_wall_present
    )
    section_indexes = tuple(
        index for index, section in enumerate(option.sections) if section in sections
    )
    cost = resource_cost(sections)
    paid_owner = pay_cost(owner, cost)
    popped = replace(
        state,
        players=replace_player(state.players, paid_owner),
        decision_stack=state.decision_stack[:-1],
    )
    events: list[GameEvent] = [
        GameEvent(
            event_id=f"{source}:played",
            kind="navigation_card_played",
            payload=(
                ("card_id", card_id),
                ("faction", owner.navigation_trigger_faction),
                ("option", option_index),
                ("player", player),
                ("slot", owner.navigation_active_slot),
            ),
        )
    ]
    if choice_slots(sections, shield_wall_present=state.shield_wall_present):
        choice = DecisionFrame(
            kind=FrameKind.INTRIGUE_CHOICE,
            frame_id=f"{source}:choice_slots",
            decision=PlayerDecision(
                owner=player, prompt="Resolve the Navigation choice"
            ),
            context=(
                ("card_id", card_id),
                ("chosen_factions", ""),
                ("option", option_index),
                ("peeked_card_id", ""),
                ("sections", ",".join(str(index) for index in section_indexes)),
                ("shield_wall_at_play", state.shield_wall_present),
                ("slot", 0),
                ("source", source),
            ),
        )
        return RuleResult(state=popped.push_decision(choice), events=tuple(events))
    finished = finish_intrigue_play(popped, player, card_id, sections, source)
    return RuleResult(state=finished.state, events=(*events, *finished.events))
