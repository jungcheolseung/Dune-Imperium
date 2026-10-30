"""Imperium Ceremony: look at the Intrigue deck's top two cards and keep one.

The owner sees both cards while the choice is open (``PrivatePlayerView
.peeked_intrigue_ids``); the card not kept stays on top of the deck, and
the owner knows it there until it reaches a public zone or the owner's hand
(OQ-149, user ruling 2026-10-29 "(가) 둘 다 기록";
``rules.intrigue_knowledge``). The other seats see a card kept and one put
back face down, not which, so what they knew of the two is lost.
With fewer than two cards face down, the discard pile is shuffled into a
new deck beneath the card(s) still on top and the peek then looks at two
(OQ-052, user ruling); only when nothing is left to shuffle does the peek
look at the single remaining card, which the owner then keeps through the
same window (user ruling 2026-10-02, L2-Q3 (2)). With no card at all the
box has no effect, and the short draw is logged (``intrigue_draw_short``,
L2-Q4). The discard's Twisted cards are never shuffled in, so a discard of
Twisted cards alone counts as empty (OQ-097).
"""

from copy import replace
from typing import Final

from dune_imperium.content.bloodlines.tech import TechAbility, has_tech
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.observation import peeked_intrigue_ids
from dune_imperium.core.state import GamePhase, GameState
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
from dune_imperium.rules.intrigue_knowledge import (
    forget_intrigue_cards,
    remember_intrigue,
)

PEEK_COUNT = 2
_FRAME = "Intrigue peek frame"
# A peek opened before the first round (Hundro Moritani's Intelligence)
# names the phase the game resumes once the card is kept.
RESUME_PHASE_KEY: Final = "resume_phase"
HUNDRO: Final = "viscount_hundro_moritani"


def begin_intrigue_peek(
    state: GameState,
    player: int,
    *,
    source: str,
    resume_phase: GamePhase | None = None,
) -> RuleResult:
    """Open the keep-one choice, shuffling the discard in when short.

    ``resume_phase``: the peek pauses the game in SETUP and resumes this
    phase once the card is kept (``assign_intelligence``); there is no
    discard to shuffle then, and a deck that is short is looked at as it
    is."""

    top = state.intrigue_deck[:PEEK_COUNT]
    # Twisted cards stay in the discard (OQ-097, user ruling 2026-10-04,
    # "다른 사람이 twisted 카드를 뽑는 일은 없도록").
    discard = shufflable_intrigue_discard(state)
    if len(top) < PEEK_COUNT and discard and resume_phase is None:
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
            *(
                ((RESUME_PHASE_KEY, resume_phase.value),)
                if resume_phase is not None
                else ()
            ),
            ("source", source),
        ),
    )
    opened = state.push_decision(frame)
    if resume_phase is not None:
        opened = replace(opened, phase=GamePhase.SETUP)
    return RuleResult(
        state=opened,
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
    next_owner = remember_intrigue(next_owner, remaining)
    popped = state.pop_decision()
    resume = dict(frame.context).get(RESUME_PHASE_KEY)
    if isinstance(resume, str):
        # Hundro Moritani's Intelligence: the game resumes as it was before
        # the setup pause (``assign_intelligence``).
        popped = replace(popped, phase=GamePhase(resume))
    next_state = forget_intrigue_cards(
        replace(
            popped,
            players=replace_player(state.players, next_owner),
            intrigue_deck=(*remaining, *state.intrigue_deck[len(peeked) :]),
        ),
        peeked,
        keeping=(action.actor,),
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


def assign_intelligence(state: GameState) -> GameState:
    """Viscount Hundro Moritani's Intelligence: "At the start of the game,
    look at the top two cards of the Intrigue deck. Keep one and put the
    other back on top" [Hundro Moritani card, app text].

    docs/rules/rise-of-ix.md 3: "순서: Baron(원판)의 진영 고르기와 같이 "모든
    setup 뒤, 첫 라운드 전"에 둔다 -- Epic에서는 Hundro가 모두가 Intrigue를
    뽑은 뒤 쓴다고 룰북이 정한다 `[Rise of Ix p. 10]`"; 13: the kept card is in
    his hand (hidden), the one put back is his to know (OQ-149 (가),
    ``rules.intrigue_knowledge``), a private decision not bound to the Leader
    pick (lessons 2026-10-05). The peek pauses the game in SETUP like the
    Baron's Masterstroke; the setup paths call this after dealing the setup
    Intrigue cards and the other setup steps.
    """

    seat = next(
        (candidate for candidate in state.players if candidate.leader_id == HUNDRO),
        None,
    )
    if seat is None:
        return state
    return begin_intrigue_peek(
        state,
        seat.player_id,
        source=f"setup:intelligence:{seat.player_id}",
        resume_phase=state.phase,
    ).state
