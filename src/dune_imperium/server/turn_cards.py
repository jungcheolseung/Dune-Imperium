"""The cards of the open Agent turn, read off the engine's decision stack.

Display only (user feedback 2026-10-11): with two copies of one card in a
seat's play area, the page could not tell the copy played this Agent turn
from the one played on an earlier turn, and a trash choice took the wrong
one. The difference matters because "you can't receive or activate an
effect from a card that is already trashed" (OQ-022, designer ruling,
``expire_trashed_card_effects``): trashing this turn's card before its
Agent box resolves loses what is left of that box.

The Agent turn's effect frame (``FrameKind.AGENT_EFFECTS``) replaces the
turn frame at placement and stays on the stack until its owner presses
``finish_agent_turn`` (OQ-095, ``rules.effects.close_agent_turn``), so it
holds the played card and its graft partner (Immortality) for the whole
turn, even after every effect has resolved: the box being resolved in
``card_id`` and the other in ``graft_card_id``, swapped together with their
pending flags when the other box's row is taken (``rules.graft_boxes``), so
each card is read with its own flag: ``pending_agent_effect`` for
``card_id``, ``graft_pending_effect`` for ``graft_card_id``, and a boosted
card's added draw (``BOOST_DRAW_KEY``, "added to its Agent box" [Urgent
Shigawire card]; a Ghola's copy of it, OQ-107) for the card it names. A
paid arrow's optional trash waits on the turn instead, outside the box
(cleanup-2b, ``turn_rows.OPTIONAL_TRASH`` under the card's box source),
and expires with the card too (engine audit 2026-10-22, P1).

Every fact here is public: the played card and its partner lie face up in
play, and each box's resolution is announced as it happens. A Reveal turn
keeps no list of the cards it revealed, so only Agent turns are read.
Nothing here reaches ``PlayerView`` or the AI observation; the engine, the
codec and saves are untouched.

A pending box is not always lost by trashing its card: a card that trashes
itself by its own effect still pays its printed rewards (OQ-022: "카드가
자기 효과로 자신을 trash하는 경우 인쇄된 이득은 정상 지급"), as when Feyd's
Signet Ring box trashes the Signet Ring and so completes the box.
``box_losing_trash`` therefore asks the engine, row by row, which of the
decision owner's trash choices would lose a box.
"""

import logging
from typing import Final

from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.core.actions import ActionValue
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules import UprisingRulesEngine, turn_rows
from dune_imperium.rules.agent_effect_frame import route_box_action
from dune_imperium.rules.effects import agent_card_source, pending_boost_draws
from dune_imperium.rules.frames import FrameKind

_LOGGER = logging.getLogger(__name__)

# Each card key of the effect frame, the flag of that card's own box, and
# the flag set when that card left play by its own effect (OQ-022).
_CARD_KEYS = (
    ("card_id", "pending_agent_effect", "agent_card_self_trashed"),
    ("graft_card_id", "graft_pending_effect", "graft_card_self_trashed"),
)

# Every legal action that trashes a personal card its owner picks, naming it
# in ``card_id``; Dissecting Kit's names none, it always trashes the other
# grafted card.
TRASH_CARD_ACTIONS: Final = frozenset(
    {
        "scouts_trash_card",
        "trash_agent_card",
        "trash_card_for_desert_tactics",
        "trash_combat_reward_card",
        "trash_grafted_card_for_influence",
        "trash_grafted_card_for_specimen",
        "trash_intrigue_card",
        "trash_leader_card",
        "trash_optional_card",
        "trash_reveal_card",
    }
)


def turn_cards(state: GameState) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """``_turn_cards``, or nothing if it fails: these marks are display
    only, and an unexpected engine state must not fail a whole snapshot."""

    try:
        return _turn_cards(state)
    except Exception:
        _LOGGER.exception("could not read the open Agent turn's cards")
        return (), ()


def _turn_cards(state: GameState) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return the open Agent turn's played cards and those with a box left.

    The first tuple is the card instances the turn's owner put into play
    with this Agent turn's card play, the played card and its graft
    partner, while they are still in play, in play-area order; empty
    outside an Agent turn. The second is the ones of them whose Agent box
    is not fully resolved yet, so that trashing them now would expire the
    rest of it (OQ-022). A Row card borrowed with Usurp is never pending:
    it is not "in play" for any trash choice (OQ-054) and is trashed when
    the turn ends anyway.
    """

    played: set[str] = set()
    pending: set[str] = set()
    owners: list[int] = []
    for frame in state.decision_stack:
        if frame.kind != FrameKind.AGENT_EFFECTS or not isinstance(
            frame.decision, PlayerDecision
        ):
            continue
        context = dict(frame.context)
        owner = context.get("turn_owner")
        if isinstance(owner, bool) or not isinstance(owner, int):
            continue
        boosted = pending_boost_draws(context)
        in_play = state.players[owner].in_play
        borrowed = state.players[owner].usurped_row_card_id
        for card_key, pending_key, _ in _CARD_KEYS:
            card_id = context.get(card_key)
            if not isinstance(card_id, str) or card_id not in in_play:
                continue
            played.add(card_id)
            owners.append(owner)
            if card_id == borrowed:
                continue
            if (
                context.get(pending_key) is True
                or card_id in boosted
                or _trash_waits(state, frame, owner, card_id)
            ):
                pending.add(card_id)
    order = [
        card_id
        for owner in dict.fromkeys(owners)
        for card_id in state.players[owner].in_play
    ]
    return (
        tuple(card_id for card_id in order if card_id in played),
        tuple(card_id for card_id in order if card_id in pending),
    )


# A trash row's arguments that name the trash icon it uses (an optional
# trash waiting on the turn, stage B3c-2b): two rows of one card differ by
# them, and only one of them may lose the card's box.
ICON_ARGUMENTS: Final = ("printed", "printed_box", "source")

type LosingRow = tuple[str, str, tuple[tuple[str, ActionValue], ...]]


def box_losing_trash(
    engine: UprisingRulesEngine, state: GameState, seat: int
) -> tuple[LosingRow, ...]:
    """``_box_losing_trash``, or no rows if it fails (display only, as
    ``turn_cards``)."""

    try:
        return _box_losing_trash(engine, state, seat)
    except Exception:
        _LOGGER.exception("could not dry-run the trash rows of seat %s", seat)
        return ()


def _box_losing_trash(
    engine: UprisingRulesEngine, state: GameState, seat: int
) -> tuple[LosingRow, ...]:
    """Return the ``(action_id, card_id, icon arguments)`` trash rows that
    would lose a box (``ICON_ARGUMENTS``: the trash icon an optional trash
    row uses, none for the others).

    Only for ``seat`` while it owns the pending decision, and only its legal
    trash rows (``TRASH_CARD_ACTIONS``) naming a card of the open Agent turn
    whose box still waits (``turn_cards``). Each such row is applied to the
    state with the engine, a pure dry run that leaves every session as it
    was, and loses the box when

    - the engine expires the card's box in that step
      (``agent_card_effect_expired``: ``expire_trashed_card_effects`` after
      an optional trash, a Research bonus, Desert Tactics, an Intrigue card;
      Beguiling Pheromones or Dissecting Kit trashing the other grafted
      card; trashing the active card itself is that card's own cost and
      keeps its rewards, OQ-022);
    - or the card has left play while the effect frame still holds its box
      pending, not trashed by its own effect: the engine expires it as soon
      as the frame above closes (Arrakis Planetologist's trash while its
      Intrigue card still waits in the same frame).

    Dissecting Kit's row names no card; its row is reported with the
    partner it trashes.
    """

    decision = engine.current_decision(state)
    if not isinstance(decision, PlayerDecision) or decision.owner != seat:
        return ()
    _, pending = turn_cards(state)
    if not pending:
        return ()
    losing: list[LosingRow] = []
    # The whole actions (stage B3: a trash with the card it trashes).
    for action in engine.whole_actions(state, seat):
        if action.action_id not in TRASH_CARD_ACTIONS:
            continue
        # The row's own box is active in ``view``: a grafted turn's box 1
        # row (``box=1``) trashes "the other grafted card" of box 1.
        view, _, _ = route_box_action(state, action)
        context = _effect_context(view)
        partner = context.get("graft_card_id")
        card_id = dict(action.arguments).get(
            "card_id",
            partner if action.action_id == "trash_grafted_card_for_specimen" else None,
        )
        if not isinstance(card_id, str) or card_id not in pending:
            continue
        try:
            result = apply_whole(engine, state, action)
        except Exception:
            _LOGGER.exception("the dry run of %s failed", action.action_id)
            continue
        if _box_expired(result.events, card_id) or _box_doomed(result.state, card_id):
            icon = tuple(
                (key, value)
                for key, value in action.arguments
                if key in ICON_ARGUMENTS
            )
            losing.append((action.action_id, card_id, icon))
    return tuple(losing)


def _effect_context(state: GameState) -> dict[str, object]:
    """The context of the topmost open Agent-turn effect frame."""

    for frame in reversed(state.decision_stack):
        if frame.kind == FrameKind.AGENT_EFFECTS and isinstance(
            frame.decision, PlayerDecision
        ):
            return dict(frame.context)
    return {}


# The Signet Ring box logs its own kinds (cleanup-2c-4).
_BOX_EXPIRED_KINDS = frozenset({"agent_card_effect_expired", "leader_signet_expired"})


def _box_expired(events: tuple[GameEvent, ...], card_id: str) -> bool:
    return any(
        event.kind in _BOX_EXPIRED_KINDS
        and dict(event.payload).get("card_id") == card_id
        for event in events
    )


def _box_doomed(state: GameState, card_id: str) -> bool:
    """Whether ``card_id`` left its owner's zones with its box still
    pending and not by its own effect: the test ``expire_trashed_card_effects``
    applies once the effect frame is back on top."""

    for frame in state.decision_stack:
        if frame.kind != FrameKind.AGENT_EFFECTS:
            continue
        context = dict(frame.context)
        owner = context.get("turn_owner")
        if isinstance(owner, bool) or not isinstance(owner, int):
            continue
        player = state.players[owner]
        if card_id in (*player.hand, *player.discard_pile, *player.in_play):
            return False
        for card_key, pending_key, self_key in _CARD_KEYS:
            if context.get(card_key) != card_id or context.get(self_key) is True:
                continue
            if context.get(pending_key) is True:
                return True
            if card_id in pending_boost_draws(context):
                return True
            if _trash_waits(state, frame, owner, card_id):
                return True
    return False


def _trash_waits(
    state: GameState, frame: DecisionFrame, owner: int, card_id: str
) -> bool:
    """Whether an optional trash ``card_id``'s box left waits on the turn
    (its own box source, or a Ghola copy's numbered one), which expires
    when another effect trashes the card (``agent_effects``'s expiry hook,
    OQ-022; engine audit 2026-10-22, P1)."""

    source = agent_card_source(state.round_number, owner, card_id)
    return any(
        kind == turn_rows.OPTIONAL_TRASH
        and (item_source == source or item_source.startswith(f"{source}:"))
        for kind, item_source, _ in turn_rows.pending(frame)
    )
