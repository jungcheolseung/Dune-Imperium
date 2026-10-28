"""Cards put face up on top of a deck are known to every seat (OQ-145).

docs/rules/open-questions.md OQ-145, user ruling 2026-10-28 (the project
convention that extends OQ-010 ruling 5 and ``docs/rules/information-
visibility.md``): a card acquired face up and put on top of its owner's deck
-- the original game's Bypass Protocol and Recruitment Mission
(``rules.acquisition.acquired_card_placed``) and Immortality's Tleilaxu card
(``rules.tleilaxu_row``) -- is known to every seat until it is drawn or the
deck is shuffled. Cards placed one after another stack in that order, the
last one placed on top. A drawn one stays public in the hand until it
leaves it (``PlayerState.hand_public``, OQ-010 ruling 1).

``PlayerState.deck_public_top`` records the deck's public cards, top first,
and is always a prefix of ``deck`` between transitions
(``simulation.invariants.check_state_invariants``). The draw, trash and
discard sites take cards off the deck as they always did and know nothing of
it; ``settle_public_deck_tops`` runs at the end of every engine transition
(``rules.engine``), keeps the cards still on top of the deck and moves the
ones that went to the hand into ``hand_public``. A whole-deck shuffle
(Refocus) clears the record (``rules.card_draw``); a draw's own reshuffle and
the Round Start reshuffle put the shuffled discard pile beneath the cards the
deck still holds, so the public top stays.
"""

from copy import replace

from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState


def settle_deck_top(owner: PlayerState) -> PlayerState:
    """``owner`` with ``deck_public_top`` brought in line with the deck.

    Draws, trashes and discards take cards off the top of the deck: the
    record keeps the longest suffix of itself that is still a prefix of the
    deck. A dropped card now in the hand entered it from the public top of
    the deck, so it stays public there (``hand_public``); one trashed or
    discarded is simply no longer on the deck. Returns ``owner`` itself when
    nothing changes.
    """

    record = owner.deck_public_top
    if not record:
        return owner
    deck = owner.deck
    kept = next(
        (
            length
            for length in range(len(record), 0, -1)
            if deck[:length] == record[len(record) - length :]
        ),
        0,
    )
    if kept == len(record):
        return owner
    dropped = record[: len(record) - kept]
    in_hand = frozenset(owner.hand)
    already_public = frozenset(owner.hand_public)
    drawn = tuple(
        card_id
        for card_id in dropped
        if card_id in in_hand and card_id not in already_public
    )
    return replace(
        owner,
        deck_public_top=record[len(record) - kept :],
        hand_public=(*owner.hand_public, *drawn),
    )


def place_on_deck_top(owner: PlayerState, instance_id: str) -> PlayerState:
    """``owner`` with ``instance_id`` put face up on top of the deck, public.

    The record is settled first, so a card drawn earlier in the same
    transition is already public in the hand and the new card stacks on the
    cards that really are on top.
    """

    settled = settle_deck_top(owner)
    return replace(
        settled,
        deck=(instance_id, *settled.deck),
        deck_public_top=(instance_id, *settled.deck_public_top),
    )


def clear_deck_top(owner: PlayerState) -> PlayerState:
    """``owner`` after its deck was shuffled: no card on top is known."""

    if not owner.deck_public_top:
        return owner
    return replace(owner, deck_public_top=())


def settle_public_deck_tops(state: GameState) -> GameState:
    """``state`` with every seat's ``deck_public_top`` settled.

    Returns ``state`` itself when no seat changes: most games never have a
    public top, and this runs after every transition.
    """

    players = state.players
    settled = tuple(settle_deck_top(player) for player in players)
    if all(after is before for after, before in zip(settled, players, strict=True)):
        return state
    return replace(state, players=settled)
