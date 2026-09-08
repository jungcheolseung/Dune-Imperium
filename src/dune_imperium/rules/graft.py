"""Graft: playing two cards on one Agent turn [Immortality pp. 10-11].

"When you play a card with Graft during an Agent turn, it can't be played
alone. You must play two cards (and only two) on that turn ... You may use
an Agent icon from either card to send your Agent ... Both played cards are
considered to have 'sent' the Agent ... You gain the effects on both cards,
in addition to the board space effects, in any order you choose."

The placement (``agent_turn`` with ``graft``) commits the first card and the
space, then a ``GRAFT_PARTNER`` frame takes the second card from the hand.
Both cards are in play; the effect frame keeps the active card in
``card_id`` and the partner in ``graft_card_id`` with its own pending box,
and ``switch_graft_card`` swaps them so either box resolves through the
ordinary Agent-box machinery in the owner's order.
"""

from dataclasses import replace

from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID
from dune_imperium.content.uprising.personal_cards import (
    card_is_graft,
    personal_card_for_instance,
)
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.agent_effects import agent_card_icons_at_placement
from dune_imperium.rules.agent_turn import (
    agent_effect_is_available,
    is_tleilaxu_infiltrator,
)
from dune_imperium.rules.effects import current_agent_effect_context
from dune_imperium.rules.frames import (
    FrameKind,
    context_str,
    frame_context,
    owned_top_frame,
    replace_player,
    with_context,
)

_PARTNER_LABEL = "Graft partner frame"


def legal_graft_partner_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer every hand card that may be grafted to the placed card."""

    frame = owned_top_frame(state, FrameKind.GRAFT_PARTNER, player)
    if frame is None:
        return ()
    context = dict(frame.context)
    placed_id = context_str(context, "card_id", owner=_PARTNER_LABEL)
    placed = personal_card_for_instance(placed_id)
    occupied = context.get("occupied") is True
    owner = state.players[player]
    return tuple(
        DomainAction(
            action_id="choose_graft_partner",
            actor=player,
            arguments=(("card_id", card_id),),
        )
        for card_id in owner.hand
        if card_id != placed_id
        and (
            card_is_graft(placed) or card_is_graft(personal_card_for_instance(card_id))
        )
        # An occupied space was entered on Tleilaxu Infiltrator's promise.
        and (
            not occupied
            or is_tleilaxu_infiltrator(placed_id)
            or is_tleilaxu_infiltrator(card_id)
        )
    )


def apply_graft_partner(state: GameState, action: DomainAction) -> RuleResult:
    """Put the partner into play and queue its Agent box on the effect frame."""

    if action not in legal_graft_partner_actions(state, action.actor):
        raise ValueError("action is not a legal Graft partner choice")
    player = action.actor
    partner_id = str(dict(action.arguments)["card_id"])
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    space_id = context_str(context, "space_id", owner=_PARTNER_LABEL)
    owner = state.players[player]
    next_owner = replace(
        owner,
        hand=tuple(card_id for card_id in owner.hand if card_id != partner_id),
        in_play=(*owner.in_play, partner_id),
    )
    partner = personal_card_for_instance(partner_id)
    popped = replace(
        state,
        players=replace_player(state.players, next_owner),
        decision_stack=state.decision_stack[:-1],
    )
    effect_frame, effect_context = current_agent_effect_context(popped)
    if not isinstance(effect_frame.decision, PlayerDecision):
        raise RuntimeError("the Graft partner needs the owner's effect frame")
    space = BOARD_SPACES_BY_ID[space_id]
    pending = agent_effect_is_available(
        partner.agent_effect, next_owner, space, partner_id
    )
    effect_context["graft_card_id"] = partner_id
    effect_context["graft_pending_effect"] = pending
    effect_context["graft_pending_icons"] = ",".join(
        agent_card_icons_at_placement(partner.agent_effect) if pending else ()
    )
    if effect_context["pending_agent_effect"] is not True:
        # The placed card's Bond-gated box was judged before the partner
        # was in play; the partner may provide the Bond now.
        placed_id = context_str(context, "card_id", owner=_PARTNER_LABEL)
        placed = personal_card_for_instance(placed_id)
        if agent_effect_is_available(placed.agent_effect, next_owner, space, placed_id):
            effect_context["pending_agent_effect"] = True
            effect_context["pending_agent_icons"] = ",".join(
                agent_card_icons_at_placement(placed.agent_effect)
            )
    next_state = replace(
        popped,
        decision_stack=(
            *popped.decision_stack[:-1],
            with_context(effect_frame, effect_context),
        ),
    )
    return RuleResult(
        state=next_state,
        events=(
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{player}:graft:{partner_id}"
                ),
                kind="card_grafted",
                payload=(
                    ("card_id", partner_id),
                    ("placed_card_id", context_str(context, "card_id")),
                    ("player", player),
                    ("space_id", space_id),
                ),
            ),
        ),
    )


def legal_graft_switch_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer resolving the other grafted card's box next.

    Available whenever the inactive partner still has a pending box and no
    atomic selection of the active box is under way.
    """

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("graft_pending_effect") is not True:
        return ()
    if context.get("long_live_fighters_selection_started") is True:
        return ()
    return (DomainAction(action_id="switch_graft_card", actor=player),)


def apply_graft_switch(state: GameState, action: DomainAction) -> RuleResult:
    """Make the other grafted card the active one of the effect frame."""

    if action not in legal_graft_switch_actions(state, action.actor):
        raise ValueError("action is not a legal Graft switch")
    frame = state.decision_stack[-1]
    context = frame_context(frame)
    active = (
        context["card_id"],
        context["pending_agent_effect"],
        context["pending_agent_icons"],
    )
    context["card_id"] = context["graft_card_id"]
    context["pending_agent_effect"] = context["graft_pending_effect"]
    context["pending_agent_icons"] = context["graft_pending_icons"]
    (
        context["graft_card_id"],
        context["graft_pending_effect"],
        context["graft_pending_icons"],
    ) = active
    # A self-trash flag belongs to the box it was set for.
    context.pop("agent_card_self_trashed", None)
    return RuleResult(
        state=replace(
            state,
            decision_stack=(*state.decision_stack[:-1], with_context(frame, context)),
        ),
        events=(
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{action.actor}:"
                    f"graft_switch:{context['card_id']}"
                ),
                kind="graft_card_switched",
                payload=(("card_id", context["card_id"]), ("player", action.actor)),
            ),
        ),
    )
