"""Sonic Snoopers: put Intrigue cards on the Intrigue deck's bottom, then draw.

docs/rules/rise-of-ix.md 4 (the tile table), line "Sonic Snoopers":
"이 타일 trash → Intrigue 몇 장이든 덱 맨 아래로, 그만큼 뽑기(맨 아래 카드는
공개하지 않음 [Rise of Ix p. 10])". The tile prints no timing, so its owner uses
it in their own turn ("때를 적지 않은 능력은 자기 turn 가운데 쓴다 [FAQ p. 4]",
``rules.tech.legal_tech_trash_actions``); the tile is the cost, trashed first.

``FrameKind.INTRIGUE_BOTTOM_PICK`` is the effect's own pick, as
``LONG_LIVE_FIGHTERS`` is Long Live the Fighters': the seat puts one Intrigue
card of its hand at a time on the bottom, in the order it chooses (each below
the last), until it stops; then it draws as many as it put, from the top.
"Any number" includes none, so the seat may stop at once.

Knowledge (docs/rules/rise-of-ix.md 13, OQ-149 "(가) 둘 다 기록", user ruling
2026-10-29; ``rules.intrigue_knowledge``): the seat knows each card it put there
(``remember_intrigue``; the depth from the bottom is read from the zone,
``core.observation.known_intrigue_places``), and every other seat forgets the
cards it knew in this seat's hand, since it cannot tell which ones went down
(``forget_intrigue_cards`` with ``keeping``). A drawn card that is one of the
seat's own puts (a deck short enough that the draw reaches them) enters its
own hand, where ``settle_known_intrigue`` drops the record.

A Twisted Intrigue card (Piter De Vries) is never offered: it must not reach
the common deck ("다른 사람이 twisted 카드를 뽑는 일은 없도록", OQ-097, user
ruling 2026-10-04). Nothing of this opens in a game without Rise of Ix.
"""

from copy import replace
from typing import Final

from dune_imperium.content.uprising.intrigue import twisted_intrigue_instance_ids
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import (
    FrameKind,
    context_int,
    context_str,
    owned_top_frame,
    replace_player,
    replace_top_frame,
    with_context,
)
from dune_imperium.rules.intrigue_deck import draw_or_queue_intrigue_cards
from dune_imperium.rules.intrigue_knowledge import (
    forget_intrigue_cards,
    remember_intrigue,
)

PUT_ACTION: Final = "put_intrigue_on_bottom"
FINISH_ACTION: Final = "finish_intrigue_bottom"
_COUNT_KEY: Final = "count"
_FRAME: Final = "Intrigue bottom pick frame"
_TWISTED: Final = frozenset(twisted_intrigue_instance_ids())


def puttable_intrigue(state: GameState, player: int) -> tuple[str, ...]:
    """The Intrigue cards of ``player``'s hand that may go on the bottom (every
    one but a Twisted card, OQ-097)."""

    return tuple(
        card
        for card in state.players[player].intrigue_cards
        if card not in _TWISTED
    )


def begin_intrigue_bottom_pick(
    state: GameState, player: int, *, source: str
) -> GameState:
    """Open the owner's pick of cards to put on the Intrigue deck's bottom."""

    frame = DecisionFrame(
        kind=FrameKind.INTRIGUE_BOTTOM_PICK,
        frame_id=f"{source}:intrigue_bottom_pick",
        decision=PlayerDecision(
            owner=player,
            prompt="Put Intrigue cards on the bottom of the Intrigue deck, "
            "then draw as many",
        ),
        context=((_COUNT_KEY, 0), ("player", player), ("source", source)),
    )
    return state.push_decision(frame)


def legal_intrigue_bottom_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """Each hand card to put on the bottom, and the stop (the draw)."""

    if owned_top_frame(state, FrameKind.INTRIGUE_BOTTOM_PICK, player) is None:
        return ()
    return (
        *(
            DomainAction(
                action_id=PUT_ACTION, actor=player, arguments=(("card_id", card),)
            )
            for card in puttable_intrigue(state, player)
        ),
        DomainAction(action_id=FINISH_ACTION, actor=player),
    )


def apply_intrigue_bottom_action(state: GameState, action: DomainAction) -> RuleResult:
    """Put one card under the deck, or stop and draw what was put."""

    if action not in legal_intrigue_bottom_actions(state, action.actor):
        raise ValueError("action is not a legal Intrigue bottom pick")
    player = action.actor
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    source = context_str(context, "source", owner=_FRAME)
    count = context_int(context, _COUNT_KEY, owner=_FRAME)
    if action.action_id == FINISH_ACTION:
        closed = state.pop_decision()
        if count == 0:
            return RuleResult(state=closed)
        return draw_or_queue_intrigue_cards(
            closed, player, count, source=f"{source}:draw"
        )
    card = str(dict(action.arguments)["card_id"])
    owner = state.players[player]
    next_owner = remember_intrigue(
        replace(
            owner,
            intrigue_cards=tuple(held for held in owner.intrigue_cards if held != card),
        ),
        (card,),
    )
    context[_COUNT_KEY] = count + 1
    putting = replace(
        state,
        players=replace_player(state.players, next_owner),
        intrigue_deck=(*state.intrigue_deck, card),
    )
    return RuleResult(
        # Every other seat loses what it knew of this whole hand: it sees a
        # card go down, not which one, so keeping the cards still held would
        # tell it which one moved (OQ-149; Codex review of 7913f5db).
        state=forget_intrigue_cards(
            replace_top_frame(putting, with_context(frame, context)),
            owner.intrigue_cards,
            keeping=(player,),
        ),
        # The table sees a card go to the bottom, not which (rise-of-ix.md
        # 13: "공개하지 않는다" [Rise of Ix p. 10]).
        events=(
            GameEvent(
                event_id=f"{source}:intrigue_bottom:{count}",
                kind="intrigue_put_on_bottom",
                payload=(("count", 1), ("player", player)),
            ),
        ),
    )
