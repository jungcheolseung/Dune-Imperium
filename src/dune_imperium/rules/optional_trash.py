"""A generic optional card trash decision ("[trash] icon" as a reward).

Liet Kynes' Arrakis Planetologist offers one per replaced sandworm: the
owner may trash a card from hand, discard pile or play area, or decline.
Its frame also holds the replacement's Intrigue card as a step of its own
(``draw_planetologist_intrigue``), in either order with the trash; the
frame closes once both are done (user ruling 2026-10-10, OQ-106).

Inside its owner's own Agent or Reveal turn the icon opens no window: it
waits on the turn as rows with no refusal and lapses unused at the turn-end
press, and the Planetologist's Intrigue card waits beside it (user decision
2026-10-17, cleanup-2b; ``turn_rows``). Combat, the Arrakeen Scouts step and
a Scouts line keep the window.
"""

from copy import replace

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules import turn_rows
from dune_imperium.rules.card_bonds import counted_in_play
from dune_imperium.rules.card_trash import credit_trash_recruits, trash_personal_card
from dune_imperium.rules.effects import agent_card_source
from dune_imperium.rules.frames import (
    FrameKind,
    context_str,
    owned_top_frame,
    replace_top_frame,
    with_context,
)
from dune_imperium.rules.intrigue_deck import draw_or_queue_intrigue_cards

# Arrakis Planetologist's Intrigue card still waiting in the frame, and
# whether the frame's trash (or its decline) is already done.
INTRIGUE_PENDING_KEY = "intrigue_pending"
TRASH_DONE_KEY = "trash_done"


def optional_trash_frame(
    player: int, source: str, *, intrigue: bool = False
) -> DecisionFrame:
    """Return the decision frame offering one optional trash.

    With ``intrigue`` the frame also holds Arrakis Planetologist's Intrigue
    card for its own step (``draw_planetologist_intrigue``).
    """

    return DecisionFrame(
        kind=FrameKind.OPTIONAL_TRASH,
        frame_id=f"{source}:optional_trash",
        decision=PlayerDecision(owner=player, prompt="Trash a card or decline"),
        context=(
            *(((INTRIGUE_PENDING_KEY, True),) if intrigue else ()),
            ("player", player),
            ("source", source),
        ),
    )


def open_optional_trash(state: GameState, player: int, source: str) -> GameState:
    """Offer one optional trash: a row waiting on ``player``'s own turn, or
    a window of its own elsewhere (cleanup-2b, ``turn_rows.queue``)."""

    queued = turn_rows.queue(state, player, (turn_rows.OPTIONAL_TRASH, source, ""))
    if queued is not None:
        return queued
    return state.push_decision(optional_trash_frame(player, source))


def open_planetologist_replacement(
    state: GameState, player: int, source: str
) -> GameState:
    """Offer one replacement's optional trash and its Intrigue card: two rows
    waiting on ``player``'s own turn, or one window holding both elsewhere."""

    queued = turn_rows.queue(state, player, (turn_rows.OPTIONAL_TRASH, source, ""))
    if queued is None:
        return state.push_decision(optional_trash_frame(player, source, intrigue=True))
    held = turn_rows.queue(
        queued, player, (turn_rows.PLANETOLOGIST_INTRIGUE, source, "")
    )
    if held is None:
        raise RuntimeError("the turn that took the trash must take the draw")
    return held


def _waiting_kinds(state: GameState, player: int) -> frozenset[str]:
    frame = turn_rows.rows_frame(state, player)
    items = () if frame is None else turn_rows.pending(frame)
    return frozenset(kind for kind, _source, _value in items) if items else frozenset()


def _intrigue_pending(frame: DecisionFrame) -> bool:
    return dict(frame.context).get(INTRIGUE_PENDING_KEY) is True


def _trash_done(frame: DecisionFrame) -> bool:
    return dict(frame.context).get(TRASH_DONE_KEY) is True


def legal_optional_trash_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer every owned card in hand, discard pile or play, plus a decline.

    Inside the owner's turn the waiting trashes are offered as one row per
    card with no decline, and a waiting Planetologist Intrigue card as one
    draw row (cleanup-2b); each press takes the newest waiting effect its row
    serves (``apply_optional_trash``).
    """

    owner = state.players[player]
    frame = owned_top_frame(state, FrameKind.OPTIONAL_TRASH, player)
    if frame is None:
        waiting = _waiting_kinds(state, player)
        trash = turn_rows.OPTIONAL_TRASH in waiting
        return (
            *(_trash_rows(owner, player) if trash else ()),
            *(
                (DomainAction(action_id="draw_planetologist_intrigue", actor=player),)
                if turn_rows.PLANETOLOGIST_INTRIGUE in waiting
                else ()
            ),
        )
    draw = (
        (DomainAction(action_id="draw_planetologist_intrigue", actor=player),)
        if _intrigue_pending(frame)
        else ()
    )
    if _trash_done(frame):
        return draw
    return (
        DomainAction(action_id="decline_optional_trash", actor=player),
        *_trash_rows(owner, player),
        *draw,
    )


def _trash_rows(owner: PlayerState, player: int) -> tuple[DomainAction, ...]:
    return tuple(
        DomainAction(
            action_id="trash_optional_card",
            actor=player,
            arguments=(("card_id", card_id),),
        )
        # A Row card borrowed with Usurp is not "in play" (OQ-054,
        # ``counted_in_play``), so it is no trash target.
        for card_id in (*owner.hand, *owner.discard_pile, *counted_in_play(owner))
    )


def apply_optional_trash(state: GameState, action: DomainAction) -> RuleResult:
    """Trash the chosen card, or close the frame without trashing."""

    if action not in legal_optional_trash_actions(state, action.actor):
        raise ValueError("action is not a legal optional trash choice")
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.OPTIONAL_TRASH:
        return _take_turn_row(state, action)
    source = context_str(dict(frame.context), "source", owner="Optional trash frame")
    if action.action_id == "draw_planetologist_intrigue":
        return _draw_planetologist_intrigue(state, frame, action.actor, source)
    if _intrigue_pending(frame):
        # The Intrigue card still waits: the frame stays for it.
        popped = replace_top_frame(
            state, with_context(frame, {**dict(frame.context), TRASH_DONE_KEY: True})
        )
    else:
        popped = replace(state, decision_stack=state.decision_stack[:-1])
    return _trash_or_decline(popped, action, source)


def _take_turn_row(state: GameState, action: DomainAction) -> RuleResult:
    """Take a row waiting on the owner's turn (cleanup-2b).

    A draw row takes the newest waiting Planetologist Intrigue card. A trash
    row takes the newest waiting trash -- they are the same icon, "trash a
    card" from hand, discard pile or play [Main p. 20] -- except that a
    card's own box's trash is taken when that card is the one trashed, so
    it keeps what is left of its box (OQ-022, ``_own_box_trash``), and is
    left for that card when another one is trashed while a plain trash
    waits. Newest first is the order the windows, stacked as they were
    raised, answered.
    """

    player = action.actor
    if action.action_id == "draw_planetologist_intrigue":
        taken, source = turn_rows.take_newest(
            state, player, turn_rows.PLANETOLOGIST_INTRIGUE
        )
        return draw_or_queue_intrigue_cards(taken, player, 1, source=source)
    frame = turn_rows.rows_frame(state, player)
    if frame is None:
        raise ValueError("the owner's turn frame is not on top")
    card_id = str(dict(action.arguments)["card_id"])
    own_box = agent_card_source(state.round_number, player, card_id)
    # The trashes a card in play opened with its own box: kept for that card,
    # whose self-trash only they credit.
    own_boxes = {
        agent_card_source(state.round_number, player, played)
        for played in state.players[player].in_play
    }
    trashes = [
        item
        for item in reversed(turn_rows.pending(frame))
        if item[0] == turn_rows.OPTIONAL_TRASH
    ]
    item = (
        next((item for item in trashes if item[1] == own_box), None)
        or next((item for item in trashes if item[1] not in own_boxes), None)
        or trashes[0]
    )
    return _trash_or_decline(turn_rows.take(state, player, item), action, item[1])


def _trash_or_decline(
    popped: GameState, action: DomainAction, source: str
) -> RuleResult:
    """Trash the chosen card from ``popped`` (the trash taken off its frame
    or the turn), or log the window's decline."""

    if action.action_id == "decline_optional_trash":
        return RuleResult(
            state=popped,
            events=(
                GameEvent(
                    event_id=f"{source}:trash_declined",
                    kind="optional_trash_declined",
                    payload=(("player", action.actor),),
                ),
            ),
        )
    card_id = str(dict(action.arguments)["card_id"])
    top = popped.decision_stack[-1] if popped.decision_stack else None
    credited_in_place = (
        top is not None
        and top.kind == FrameKind.AGENT_EFFECTS
        and isinstance(top.decision, PlayerDecision)
        and top.decision.owner == action.actor
    )
    if credited_in_place:
        popped = _own_box_trash(popped, action.actor, source, card_id)
    trashed = trash_personal_card(popped, action.actor, card_id, source=source)
    if not credited_in_place:
        # trash_personal_card's own crediting (card_trash._with_recruited_
        # troops) only fires when the owner's AGENT_EFFECTS frame sits
        # directly beneath the OPTIONAL_TRASH frame just popped. With more
        # than one replacement (Arrakis Planetologist, two summons at Deep
        # Desert) or a Reveal turn's Desert Power sandworm, another
        # OPTIONAL_TRASH frame, a REVEAL frame or a TURN frame sits there
        # instead, so Eliminate Allies' "When this card is trashed: 2
        # troops" [Eliminate Allies card] would otherwise reach the
        # garrison uncounted. "그 turn에 어떤 출처에서 recruit했든 새
        # troop은 Conflict에 deploy할 수 있다" [Main p. 10] [FAQ p. 4]
        # (docs/rules/player-turns.md:137); credit_trash_recruits finds the
        # owner's still-open turn frame past any such frame and is a no-op
        # outside the owner's own turn, so this never double-counts and
        # never credits a trash resolved during Combat or another seat's
        # turn.
        trashed = credit_trash_recruits(trashed, action.actor)
    return trashed


def _own_box_trash(
    state: GameState, player: int, source: str, card_id: str
) -> GameState:
    """Mark a box whose own trash icon trashes its own card.

    Throne Room Politics' optional trash icon may pick the card itself (or
    a Ghola copying it, Ghola). That card leaves play by its own icon, so
    what remains of its box -- Urgent Shigawire's draw "added to its Agent
    box" -- still pays out: "카드가 자기 효과로 자신을 trash하는 경우 인쇄된
    이득은 정상 지급" (OQ-022 designer ruling; the OQ-027 extension's "자기
    비용이나 자기 아이콘으로"). The box opened this frame when ``source`` is
    its own (``effects.agent_card_source``); a trash another effect opened
    (a board space, the other grafted card's box) is not the card's own.
    """

    if source != agent_card_source(state.round_number, player, card_id):
        return state
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if context.get("card_id") == card_id:
        key = "agent_card_self_trashed"
    elif context.get("graft_card_id") == card_id:
        key = "graft_card_self_trashed"
    else:
        return state
    return replace_top_frame(state, with_context(frame, {**context, key: True}))


def _draw_planetologist_intrigue(
    state: GameState, frame: DecisionFrame, player: int, source: str
) -> RuleResult:
    """Draw Arrakis Planetologist's Intrigue card of this replacement.

    "For each one you would, instead: [trash a card] [1 spice] [1 Intrigue]"
    [Liet Kynes card]: three printed icons, each its own effect (OQ-027).
    The Intrigue card is the one hidden draw, so it is a step of its own,
    in either order with the trash, and the summon or harvest choice before
    it stays undoable (OQ-010): "그 외에는 전부 나누자." (user ruling
    2026-10-10, OQ-106). The frame closes once the trash is done too; the
    frame is updated before the draw, so a reshuffle stacks above it.
    """

    if _trash_done(frame):
        working = replace(state, decision_stack=state.decision_stack[:-1])
    else:
        context = dict(frame.context)
        del context[INTRIGUE_PENDING_KEY]
        working = replace_top_frame(state, with_context(frame, context))
    return draw_or_queue_intrigue_cards(working, player, 1, source=source)
