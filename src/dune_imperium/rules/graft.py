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
    card_is_usurp,
    personal_card_for_instance,
)
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.acquisition import take_imperium_row_card
from dune_imperium.rules.agent_effects import agent_card_icons_at_placement
from dune_imperium.rules.agent_icons import (
    card_is_boosted,
    effective_agent_icons,
    is_ghola,
)
from dune_imperium.rules.agent_turn import (
    agent_effect_is_available,
    card_can_access_space,
    is_tleilaxu_infiltrator,
)
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.effects import (
    borrowed_agent_card,
    current_agent_effect_context,
)
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
    space = BOARD_SPACES_BY_ID[context_str(context, "space_id", owner=_PARTNER_LABEL)]
    opponents = tuple(seat for seat in state.players if seat.player_id != player)
    # The placement recorded whether the placed card reached this space on its
    # own; it cannot be re-derived here. Mohiam's Clandestine -- "Each card you
    # play has the Spy icon" [Gaius Helen Mohiam card] -- let an icon-less
    # starter Infiltrate into Secrets, and Infiltrate recalls the very Spy that
    # icon needed, so the access is already spent by now. Reading the empty
    # icon tuple as "it came in on the partner's icons" then demanded a partner
    # that fit Bene Gesserit; with none in hand the turn had no legal action at
    # all (2026-09-10 all-expansion A/B, game seed 499).
    placed_reaches = context.get("placed_reaches") is True
    # The same spent access on the partner's side. A Spy icon reaches every
    # space connected to a post the owner has a Spy on and "이 아이콘을
    # 사용하기 위해 Spy를 회수하지는 않는다" `[Main p. 11]`, but an Infiltrate
    # on the same placement recalls a Spy as its own cost `[Main p. 11]`
    # `[FAQ p. 4]`. A card with no icons of its own leans entirely on the
    # partner (Usurp), so when that partner's access was the Infiltrated Spy's
    # every candidate filtered out and the turn had no legal action at all
    # (2026-09-10 Immortality A/B, game seeds 70254 and 70804). Access is
    # judged with the Spy back on the post it was recalled from, which is the
    # state the placement was judged in.
    recalled = context.get("infiltrate_post_id")
    recalled_post_id = recalled if isinstance(recalled, str) and recalled else None
    # Long Reach entered on the promise of Ghola's copy (OQ-057): only Ghola
    # may then be the partner.
    needs_ghola = False
    if not placed_reaches:
        needs_ghola = card_can_access_space(
            effective_agent_icons(
                placed, owner, grafted=True, opponents=opponents, ghola_partner=True
            ),
            space,
            owner,
            any_icon=card_is_boosted(placed, owner),
            recalled_post_id=recalled_post_id,
        )
    # Only a placed card that cannot reach the space by any means of its own
    # (Usurp, which has no icons) leans on the partner for access.
    partner_must_fit = not placed_reaches and not needs_ghola
    candidates: tuple[str, ...] = (
        *(card_id for card_id in owner.hand if card_id != placed_id),
        # Usurp: "graft this card with a card from the Imperium Row".
        *(state.imperium_row if card_is_usurp(placed) else ()),
    )
    return tuple(
        DomainAction(
            action_id="choose_graft_partner",
            actor=player,
            arguments=(("card_id", card_id),),
        )
        for card_id in candidates
        if (
            card_is_graft(placed) or card_is_graft(personal_card_for_instance(card_id))
        )
        and (not needs_ghola or is_ghola(card_id))
        # An occupied space was entered on Tleilaxu Infiltrator's promise.
        and (
            not occupied
            or is_tleilaxu_infiltrator(placed_id)
            or is_tleilaxu_infiltrator(card_id)
        )
        and (
            not partner_must_fit
            or card_can_access_space(
                effective_agent_icons(
                    personal_card_for_instance(card_id),
                    owner,
                    grafted=True,
                    opponents=opponents,
                ),
                space,
                owner,
                any_icon=card_is_boosted(personal_card_for_instance(card_id), owner),
                recalled_post_id=recalled_post_id,
            )
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
    placed_id = context_str(context, "card_id", owner=_PARTNER_LABEL)
    owner = state.players[player]
    from_row = partner_id in state.imperium_row
    imperium_row, imperium_deck = (
        take_imperium_row_card(state, partner_id)
        if from_row
        else (state.imperium_row, state.imperium_deck)
    )
    next_owner = replace(
        owner,
        hand=tuple(card_id for card_id in owner.hand if card_id != partner_id),
        in_play=(*owner.in_play, partner_id),
        # Usurp: the borrowed Row card is trashed when the turn closes.
        usurped_row_card_id=partner_id if from_row else owner.usurped_row_card_id,
    )
    # Ghola borrows the other card's box, whichever side it is on.
    partner = borrowed_agent_card(personal_card_for_instance(partner_id), placed_id)
    placed = borrowed_agent_card(personal_card_for_instance(placed_id), partner_id)
    popped = replace(
        state,
        players=replace_player(state.players, next_owner),
        imperium_row=imperium_row,
        imperium_deck=imperium_deck,
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
        # was in play; the partner may provide the Bond now, and Ghola's
        # box is the partner's.
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
                    ("from_row", from_row),
                    ("placed_card_id", placed_id),
                    ("player", player),
                    ("space_id", space_id),
                ),
            ),
        ),
    )


def _agent_turn_is_open_for(state: GameState, player: int) -> bool:
    return any(
        frame.kind == FrameKind.AGENT_EFFECTS
        and isinstance(frame.decision, PlayerDecision)
        and frame.decision.owner == player
        for frame in state.decision_stack
    )


def usurp_trash_is_queued(state: GameState) -> bool:
    """Return whether a borrowed Row card's Agent turn has closed."""

    return any(
        seat.usurped_row_card_id and not _agent_turn_is_open_for(state, seat.player_id)
        for seat in state.players
    )


def resolve_usurp_trash(state: GameState) -> RuleResult:
    """Usurp: "trash that card at the end of the turn" [card face].

    The turn's close trashes the borrowed card automatically, as an ordinary
    trash: it reaches the owner's trash pile and its "when this card is
    trashed" trigger resolves (OQ-054, user ruling 2026-09-08). A card that
    already left every owned zone (trashed earlier in the turn) needs
    nothing more.
    """

    owner = next(
        seat
        for seat in state.players
        if seat.usurped_row_card_id
        and not _agent_turn_is_open_for(state, seat.player_id)
    )
    card_id = owner.usurped_row_card_id
    source = f"round:{state.round_number}:player:{owner.player_id}:usurp_trash"
    cleared = replace(
        state,
        players=replace_player(state.players, replace(owner, usurped_row_card_id="")),
    )
    event = GameEvent(
        event_id=f"{source}:{card_id}",
        kind="usurped_card_trashed",
        payload=(("card_id", card_id), ("player", owner.player_id)),
    )
    if card_id not in (*owner.hand, *owner.deck, *owner.discard_pile, *owner.in_play):
        return RuleResult(state=cleared, events=(event,))
    trashed = trash_personal_card(
        cleared, owner.player_id, card_id, source=source, allow_deck=True
    )
    return RuleResult(state=trashed.state, events=(event, *trashed.events))


def legal_graft_switch_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer resolving the other grafted card's box next.

    Available whenever the inactive partner still has a pending box and no
    atomic selection of the active box is under way.
    """

    if not state.config.immortality:
        return ()
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("graft_pending_effect") is not True:
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
