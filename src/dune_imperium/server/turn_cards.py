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
holds the played card (``card_id``) and its graft partner
(``graft_card_id``, Immortality) for the whole turn, even after every
effect has resolved. ``switch_graft_card`` swaps the two keys together
with their pending flags, so each card is read with its own flag:
``pending_agent_effect`` for ``card_id``, ``graft_pending_effect`` for
``graft_card_id``, and a boosted card's added draw (``BOOST_DRAW_KEY``,
"added to its Agent box" [Urgent Shigawire card]) for the card it names.

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

from typing import Final

from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.effects import pending_boost_draw
from dune_imperium.rules.frames import FrameKind

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
# Beguiling Pheromones and Dissecting Kit clear the other grafted card's
# box themselves, with no ``agent_card_effect_expired`` event
# (``rules.agent_effects.apply_agent_card_payment``); trashing the active
# card itself is that card's own cost and keeps its rewards (OQ-022).
_GRAFT_TRASHES: Final = frozenset(
    {"trash_grafted_card_for_influence", "trash_grafted_card_for_specimen"}
)


def turn_cards(state: GameState) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return the open Agent turn's played cards and those with a box left.

    The first tuple is the card instances the turn's owner put into play
    with this Agent turn's card play, the played card and its graft
    partner, while they are still in play, in play-area order; empty
    outside an Agent turn. The second is the ones of them whose Agent box
    is not fully resolved yet, so that trashing them now would expire the
    rest of it (OQ-022).
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
        boosted = pending_boost_draw(context)
        in_play = state.players[owner].in_play
        for card_key, pending_key, _ in _CARD_KEYS:
            card_id = context.get(card_key)
            if not isinstance(card_id, str) or card_id not in in_play:
                continue
            played.add(card_id)
            owners.append(owner)
            if context.get(pending_key) is True or card_id == boosted:
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


def box_losing_trash(
    engine: UprisingRulesEngine, state: GameState, seat: int
) -> tuple[tuple[str, str], ...]:
    """Return the ``(action_id, card_id)`` trash rows that would lose a box.

    Only for ``seat`` while it owns the pending decision, and only its legal
    trash rows (``TRASH_CARD_ACTIONS``) naming a card of the open Agent turn
    whose box still waits (``turn_cards``). Each such row is applied to the
    state with the engine, a pure dry run that leaves every session as it
    was, and loses the box when

    - the engine expires the card's box in that step
      (``agent_card_effect_expired``, ``expire_trashed_card_effects``: an
      optional trash, a Research bonus, Desert Tactics, an Intrigue card);
    - or the card has left play while the effect frame still holds its box
      pending, not trashed by its own effect: the engine expires it as soon
      as the frame above closes (Arrakis Planetologist's trash while its
      Intrigue card still waits in the same frame);
    - or Beguiling Pheromones or Dissecting Kit trashes the other grafted
      card, whose box they clear themselves.

    Dissecting Kit's row names no card; its row is reported with the
    partner it trashes.
    """

    decision = engine.current_decision(state)
    if not isinstance(decision, PlayerDecision) or decision.owner != seat:
        return ()
    _, pending = turn_cards(state)
    if not pending:
        return ()
    context = _effect_context(state)
    active = context.get("card_id")
    partner = context.get("graft_card_id")
    losing: list[tuple[str, str]] = []
    for action in engine.legal_actions(state, seat):
        if action.action_id not in TRASH_CARD_ACTIONS:
            continue
        card_id = dict(action.arguments).get(
            "card_id",
            partner if action.action_id == "trash_grafted_card_for_specimen" else None,
        )
        if not isinstance(card_id, str) or card_id not in pending:
            continue
        if action.action_id in _GRAFT_TRASHES:
            if card_id != active:
                losing.append((action.action_id, card_id))
            continue
        try:
            result = engine.apply(state, action)
        except Exception:  # noqa: BLE001 - a failing dry run marks nothing
            continue
        if _box_expired(result.events, card_id) or _box_doomed(result.state, card_id):
            losing.append((action.action_id, card_id))
    return tuple(losing)


def _effect_context(state: GameState) -> dict[str, object]:
    """The context of the topmost open Agent-turn effect frame."""

    for frame in reversed(state.decision_stack):
        if frame.kind == FrameKind.AGENT_EFFECTS and isinstance(
            frame.decision, PlayerDecision
        ):
            return dict(frame.context)
    return {}


def _box_expired(events: tuple[GameEvent, ...], card_id: str) -> bool:
    return any(
        event.kind == "agent_card_effect_expired"
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
            if pending_boost_draw(context) == card_id:
                return True
    return False
