"""Imperium Ceremony: look at the Intrigue deck's top two cards and keep one.

The owner sees both cards while the choice is open (``PrivatePlayerView
.peeked_intrigue_ids``); the card not kept stays on top of the deck.
With fewer than two cards face down, the discard pile is shuffled into a
new deck beneath the card(s) still on top and the peek then looks at two
(OQ-052, user ruling); only when nothing is left to shuffle does the box
take the single remaining card.
"""

from dataclasses import replace

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.observation import peeked_intrigue_ids
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import (
    FrameKind,
    context_str,
    owned_top_frame,
    replace_player,
)
from dune_imperium.rules.intrigue_deck import draw_or_queue_intrigue_cards

PEEK_COUNT = 2
_FRAME = "Intrigue peek frame"


def begin_intrigue_peek(state: GameState, player: int, *, source: str) -> RuleResult:
    """Open the keep-one choice, or draw one card when the deck is short."""

    top = state.intrigue_deck[:PEEK_COUNT]
    if len(top) < PEEK_COUNT and state.intrigue_discard:
        # OQ-052 (user ruling): the discard is shuffled into a new deck
        # beneath the remaining top card, then two cards are looked at.
        decision_id = f"{source}:intrigue_shuffle"
        frame = DecisionFrame(
            kind=FrameKind.INTRIGUE_RESHUFFLE,
            frame_id=f"{decision_id}:intrigue_reshuffle",
            decision=ChanceDecision(
                decision_id=decision_id,
                prompt="Shuffle the Intrigue discard pile into a new deck",
                options=state.intrigue_discard,
                count=len(state.intrigue_discard),
            ),
            context=(
                ("count", 0),
                ("player", player),
                ("purpose", "peek"),
                ("source", source),
            ),
        )
        return RuleResult(state=state.push_decision(frame))
    if len(top) < PEEK_COUNT:
        # Nothing left to shuffle: the single face-down card (if any) is all
        # there is to look at, so it is kept.
        if not top:
            return RuleResult(state=state)
        return draw_or_queue_intrigue_cards(state, player, 1, source=f"{source}:draw")
    frame = DecisionFrame(
        kind=FrameKind.INTRIGUE_PEEK,
        frame_id=f"{source}:intrigue_peek",
        decision=PlayerDecision(
            owner=player, prompt="Keep one of the two Intrigue cards"
        ),
        context=(
            ("peeked_intrigue_ids", ",".join(top)),
            ("player", player),
            ("source", source),
        ),
    )
    return RuleResult(
        state=state.push_decision(frame),
        events=(
            GameEvent(
                event_id=f"{source}:intrigue_peek",
                kind="intrigue_cards_peeked",
                payload=(("count", PEEK_COUNT), ("player", player)),
            ),
        ),
    )


def legal_intrigue_peek_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer each peeked card to keep."""

    if owned_top_frame(state, FrameKind.INTRIGUE_PEEK, player) is None:
        return ()
    return tuple(
        DomainAction(
            action_id="keep_peeked_intrigue",
            actor=player,
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in peeked_intrigue_ids(state, player)
    )


def apply_intrigue_peek(state: GameState, action: DomainAction) -> RuleResult:
    """Keep the chosen card; the other stays on top of the deck."""

    if action not in legal_intrigue_peek_actions(state, action.actor):
        raise ValueError("action is not a legal Intrigue peek choice")
    frame = state.decision_stack[-1]
    source = context_str(dict(frame.context), "source", owner=_FRAME)
    kept = str(dict(action.arguments)["instance_id"])
    peeked = peeked_intrigue_ids(state, action.actor)
    owner = state.players[action.actor]
    next_owner = replace(owner, intrigue_cards=(*owner.intrigue_cards, kept))
    remaining = tuple(card for card in peeked if card != kept)
    next_state = replace(
        state.pop_decision(),
        players=replace_player(state.players, next_owner),
        intrigue_deck=(*remaining, *state.intrigue_deck[len(peeked) :]),
    )
    return RuleResult(
        state=next_state,
        events=(
            GameEvent(
                event_id=f"{source}:intrigue_kept",
                kind="intrigue_card_drawn",
                payload=(("count", 1), ("player", action.actor)),
            ),
            GameEvent(
                event_id=f"{source}:intrigue_kept:card",
                kind="intrigue_card_kept",
                payload=(("card_id", kept), ("player", action.actor)),
                visible_to=(action.actor,),
            ),
        ),
    )
