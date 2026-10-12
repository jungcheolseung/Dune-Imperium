"""Triggered draws held as the owner's own step inside its turn (OQ-106).

User ruling 2026-10-10 (project convention, not an official rule): "4번은
소환과 뽑기가 당연히 두 단계로 나눠야지. 이건 정말 기본적인 원칙인데" and
"그 외에는 전부 나누자. 특히 카드 드로우는 나눠야하는게, 드로우 하기 전에
버림더미 카드를 폐기하고 싶을 수 있잖아." A draw that another printed effect
triggers -- the Bene Gesserit Influence 4 bonus and Princess Irulan's
Imperial Birthright, a Tleilaxu track Intrigue space, Steersman Y'rkoon's
Hungry for Spice, Sardaukar Soldier's "when trashed", Overthrow's acquire
box -- is not drawn inside the step that triggered it.
During the seat's own Agent or Reveal turn it waits in
``PlayerState.owed_draws`` (``frames.draw_waits_for_owner``) and is taken
with its own action, in any order with the turn's other effects
("You may carry out all these effects in any order." [Main p. 9], OQ-027)
and before the turn ends, like the Emperor track's Spy (user ruling
2026-10-04). The public choice that triggered it stays undoable (OQ-010);
only the draw is not. The one bundle kept is Esmar Tuek's Intrigue for an
opponent's visit to Tuek's Sietch, which is another seat's and comes with the
visit like a control bonus ("오히려 에스마르 튜엑만 안 나누는게 맞는 듯?").

Some of them are immediate (user decision 2026-10-10, "가 로 가자";
``frames.draw_is_immediate``): CHOAM Transports' card, whose adopted
designer ruling says it "can't be deferred", the Bene Gesserit Influence 4
card and Imperial Birthright ("faction bonuses ... may interrupt this
flow"), and an acquire box's card ("Acquire Effects must be taken
immediately"). Each is still its own step after its trigger, so the trigger
stays undoable, but while one waits it is the owner's only action, on
whatever frame of the owner's is open (``immediate_owed_draw_actions``).
"""

from copy import replace

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.frames import (
    OWED_CARD,
    OWED_INTRIGUE,
    FrameKind,
    draw_is_immediate,
    draw_waits_for_owner,
    replace_player,
)
from dune_imperium.rules.intrigue_deck import draw_intrigue_cards

# The turn's own frames, where a waiting draw is offered (as the Emperor
# track's Spy is, ``spy_moves.legal_track_spy_actions``), and the owner's
# open "[trash a card]" icon (Oversight's, a Tech tile's, a research
# space's): an independent effect too, so the card may be drawn first and
# then trashed, or the trash made first (OQ-027, OQ-100).
_TURN_FRAME_KINDS = frozenset(
    {
        FrameKind.TURN,
        FrameKind.AGENT_EFFECTS,
        FrameKind.REVEAL,
        FrameKind.OPTIONAL_TRASH,
    }
)
_ACTION_DECKS = {
    "draw_owed_intrigue": OWED_INTRIGUE,
    "draw_owed_card": OWED_CARD,
}


def legal_owed_draw_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer the owner's waiting triggered draws on its turn's own frames.

    One action per deck: the waiting draws of one deck are interchangeable
    (the same deck, one card each), so each press takes the oldest. Offered
    on the turn's own frame and on the owner's optional "[trash a card]"
    frame above it, never on another frame, and only inside the seat's own
    turn (``draw_waits_for_owner``); a draw waiting anywhere else is paid by
    ``pay_stale_owed_draws``. While an immediate draw waits, only its deck's
    action is offered, on any of the owner's frames
    (``immediate_owed_draw_actions``).
    """

    immediate = immediate_owed_draw_actions(state, player)
    if immediate:
        return immediate
    frame = state.decision_stack[-1] if state.decision_stack else None
    if (
        frame is None
        or frame.kind not in _TURN_FRAME_KINDS
        or not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
    ):
        return ()
    owed = state.players[player].owed_draws
    if not owed or not draw_waits_for_owner(state, player):
        return ()
    return _deck_actions(player, {deck for deck, _, _ in owed})


def immediate_owed_draw_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """The owner's only actions while an immediate triggered draw waits.

    User decision 2026-10-10 (OQ-106, "가 로 가자"): CHOAM Transports' card,
    the Bene Gesserit Influence 4 card, Imperial Birthright and an acquire
    box's card (``frames.draw_is_immediate``) are drawn as the step right
    after their trigger, so the trigger stays undoable while nothing of the
    owner's comes between: on whatever frame of the owner's is open, these
    draws are all it is offered (``UprisingRulesEngine.legal_actions``), the
    turn's other effects, a Plot, a free-timing action and the turn end
    included. Empty when no such draw waits for ``player``'s own decision.
    """

    frame = state.decision_stack[-1] if state.decision_stack else None
    if (
        frame is None
        or not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
    ):
        return ()
    owed = state.players[player].owed_draws
    decks = {deck for deck, origin, _ in owed if draw_is_immediate(origin)}
    if not decks or not draw_waits_for_owner(state, player):
        return ()
    return _deck_actions(player, decks)


def _deck_actions(player: int, decks: set[str]) -> tuple[DomainAction, ...]:
    return tuple(
        DomainAction(action_id=action_id, actor=player)
        for action_id, deck in _ACTION_DECKS.items()
        if deck in decks
    )


def apply_owed_draw(state: GameState, action: DomainAction) -> RuleResult:
    """Draw the owner's next waiting card of the action's deck."""

    if action not in legal_owed_draw_actions(state, action.actor):
        raise ValueError("action is not a legal owed draw")
    return _draw_owed(state, action.actor, _ACTION_DECKS[action.action_id])


def next_owed_draw(owner: PlayerState, deck: str) -> int | None:
    """Index of the waiting draw a press of ``deck``'s action takes.

    The oldest immediate one of the deck if any (its press is the one
    forced right after the trigger), else the deck's oldest; ``None`` when
    the deck has none.
    """

    entries = [
        (position, origin)
        for position, (entry_deck, origin, _) in enumerate(owner.owed_draws)
        if entry_deck == deck
    ]
    if not entries:
        return None
    return next(
        (position for position, origin in entries if draw_is_immediate(origin)),
        entries[0][0],
    )


def _draw_owed(state: GameState, player: int, deck: str) -> RuleResult:
    owner = state.players[player]
    index = next_owed_draw(owner, deck)
    if index is None:
        raise ValueError("no draw of that deck waits")
    source = owner.owed_draws[index][2]
    remaining = replace(
        owner,
        owed_draws=(*owner.owed_draws[:index], *owner.owed_draws[index + 1 :]),
    )
    working = replace(state, players=replace_player(state.players, remaining))
    # The draw logs what it always logged (an Intrigue card's count; a
    # personal draw nothing); the trigger was announced when it fired.
    if deck == OWED_INTRIGUE:
        return draw_intrigue_cards(working, player, 1, source=source)
    return draw_or_request_personal_cards(working, player, 1, source=source)


def pay_stale_owed_draws(result: RuleResult) -> RuleResult:
    """Draw at once what waits for a seat whose own turn is not open.

    A triggered draw only waits inside its seat's own turn, and the turn's
    end is not offered while one waits, so this pays nothing in play; it
    keeps a draw from ever being carried into another seat's turn or out of
    Player Turns. One at a time and never over a pending reshuffle, like the
    other owed draws (``tech.draw_owed_tech_cards``).
    """

    state = result.state
    if not any(seat.owed_draws for seat in state.players):
        return result
    events = list(result.events)
    for seat in state.players:
        while (
            state.players[seat.player_id].owed_draws
            and not draw_waits_for_owner(state, seat.player_id)
            and state.phase is not GamePhase.ROUND_START
            and not (
                state.decision_stack
                and isinstance(state.decision_stack[-1].decision, ChanceDecision)
            )
        ):
            deck = state.players[seat.player_id].owed_draws[0][0]
            drawn = _draw_owed(state, seat.player_id, deck)
            state = drawn.state
            events.extend(drawn.events)
    return RuleResult(state=state, events=tuple(events))
