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
"""

from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.state import GameState
from dune_imperium.rules.effects import pending_boost_draw
from dune_imperium.rules.frames import FrameKind

# Each card key of the effect frame and the flag of that card's own box.
_CARD_KEYS = (
    ("card_id", "pending_agent_effect"),
    ("graft_card_id", "graft_pending_effect"),
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
        for card_key, pending_key in _CARD_KEYS:
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
