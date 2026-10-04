"""Imperium Ceremony: look at the Intrigue deck's top two cards and keep one.

The owner sees both cards while the choice is open (``PrivatePlayerView
.peeked_intrigue_ids``); the card not kept stays on top of the deck.
With fewer than two cards face down, the discard pile is shuffled into a
new deck beneath the card(s) still on top and the peek then looks at two
(OQ-052, user ruling); only when nothing is left to shuffle does the peek
look at the single remaining card, which the owner then keeps through the
same window (user ruling 2026-10-02, L2-Q3 (2)). With no card at all the
box has no effect, and the short draw is logged (``intrigue_draw_short``,
L2-Q4). The discard's Twisted cards are never shuffled in, so a discard of
Twisted cards alone counts as empty (OQ-097).
"""

from dataclasses import replace

from dune_imperium.content.bloodlines.tech import TechAbility, has_tech
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
    turn_owner_of,
)
from dune_imperium.rules.intrigue_deck import (
    intrigue_draw_short_events,
    shufflable_intrigue_discard,
)

PEEK_COUNT = 2
_FRAME = "Intrigue peek frame"


def begin_intrigue_peek(state: GameState, player: int, *, source: str) -> RuleResult:
    """Open the keep-one choice, shuffling the discard in when short."""

    top = state.intrigue_deck[:PEEK_COUNT]
    # Twisted cards stay in the discard (OQ-097, user ruling 2026-10-04,
    # "다른 사람이 twisted 카드를 뽑는 일은 없도록").
    discard = shufflable_intrigue_discard(state)
    if len(top) < PEEK_COUNT and discard:
        # OQ-052 (user ruling): the discard is shuffled into a new deck
        # beneath the remaining top card, then two cards are looked at.
        decision_id = f"{source}:intrigue_shuffle"
        frame = DecisionFrame(
            kind=FrameKind.INTRIGUE_RESHUFFLE,
            frame_id=f"{decision_id}:intrigue_reshuffle",
            decision=ChanceDecision(
                decision_id=decision_id,
                prompt="Shuffle the Intrigue discard pile into a new deck",
                options=discard,
                count=len(discard),
            ),
            context=(
                ("count", 0),
                ("player", player),
                ("purpose", "peek"),
                ("source", source),
            ),
        )
        return RuleResult(state=state.push_decision(frame))
    if not top:
        # Nothing face down and nothing to shuffle: no effect (OQ-052). The
        # keep-one draw falls short, which is logged (user ruling
        # 2026-10-02, L2-Q4: "로그 + 클릭 전 경고").
        return RuleResult(
            state=state,
            events=intrigue_draw_short_events(source, player, 1, 0),
        )
    # With one card left and no discard to shuffle, that card is all there
    # is to look at: the window still opens on it, and keeping it is the
    # only choice (user ruling 2026-10-02, L2-Q3: "①②는 확인 창" -- (2)
    # OQ-052's single card is shown before it is kept).
    frame = DecisionFrame(
        kind=FrameKind.INTRIGUE_PEEK,
        frame_id=f"{source}:intrigue_peek",
        decision=PlayerDecision(
            owner=player,
            prompt=(
                "Keep one of the two Intrigue cards"
                if len(top) == PEEK_COUNT
                else "Keep the last Intrigue card"
            ),
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
                payload=(("count", len(top)), ("player", player)),
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
    if turn_owner_of(state) == action.actor and has_tech(
        owner.tech_ids, TechAbility.INTRIGUE_DRAW_TROOP
    ):
        # "Keep one" is an Intrigue draw: Suspensor Suits owes its troop
        # (designer ruling, OQ-057), paid by the engine after the step.
        next_owner = replace(
            next_owner, suspensor_owed=next_owner.suspensor_owed + 1
        )
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
