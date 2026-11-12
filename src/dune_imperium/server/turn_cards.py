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
Signet Ring box trashes the Signet Ring and so completes the box. Which
step would lose a box is read off each row's own dry run instead
(``server.forfeits``, user request 2026-10-31).
"""

import logging
from typing import Final

from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.state import GameState
from dune_imperium.rules import turn_rows
from dune_imperium.rules.action_shapes import Source, printer_parts
from dune_imperium.rules.effects import agent_card_source, pending_boost_draws
from dune_imperium.rules.frames import FrameKind

_LOGGER = logging.getLogger(__name__)

# Each card key of the effect frame, the flag of that card's own box, and
# the flag set when that card left play by its own effect (OQ-022).
TURN_CARD_KEYS: Final = (
    ("card_id", "pending_agent_effect", "agent_card_self_trashed"),
    ("graft_card_id", "graft_pending_effect", "graft_card_self_trashed"),
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
        for card_key, pending_key, _ in TURN_CARD_KEYS:
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
                or trash_waits(state, frame, owner, card_id)
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


def trash_waits(
    state: GameState, frame: DecisionFrame, owner: int, card_id: str
) -> bool:
    """Whether an optional trash ``card_id`` printed waits on the turn (its
    own box source, or a Ghola copy's numbered one), which expires when
    another effect trashes the card (``agent_effects``'s expiry hook,
    OQ-022; engine audit 2026-10-22, P1). A research space's trash its
    Research reached is the track's own and stays."""

    source = agent_card_source(state.round_number, owner, card_id)
    return any(
        kind == turn_rows.OPTIONAL_TRASH
        and printer_parts(printer)[0] is Source.AGENT_CARD
        and (item_source == source or item_source.startswith(f"{source}:"))
        for kind, item_source, printer in turn_rows.pending(frame)
    )
