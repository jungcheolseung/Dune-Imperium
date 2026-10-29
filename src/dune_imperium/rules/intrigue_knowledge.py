"""Intrigue cards a seat knows and another seat does not (OQ-149).

docs/rules/open-questions.md OQ-149, user ruling 2026-10-29 ("(가) 둘 다
기록"): a seat that looked at the Intrigue deck's top cards and put one back
on top knows that card -- Immortality's Imperium Ceremony
(``rules.intrigue_peek``) and, from stage P4e, Rise of Ix's Viscount Hundro
Moritani (docs/rules/rise-of-ix.md 13) -- as a card once seen stays known to
the seat that saw it (OQ-010, user 2026-09-01). The record is
``PlayerState.known_intrigue_ids``; its places (the deck's top, the depth
from the bottom, the seat holding it) are read from the zones
(``core.observation.known_intrigue_places``).

An entry stays while its card is in the Intrigue deck or in another seat's
held Intrigue: a card drawn from the top by another seat is still known, in
that seat's hand. ``settle_known_intrigue`` runs at the end of every engine
transition (``rules.engine``) and drops the entries whose card reached a
public zone (played, discarded, trashed) or the knower's own hand. A played
Intrigue card stays in its owner's held Intrigue while its choices resolve
(``rules.intrigue``), but it is face up: it counts as public from the play
(``core.observation.resolving_intrigue_ids``, as ``known_card_seats`` has it). A hidden
move the knower cannot follow drops its entries at the move itself
(``forget_intrigue_cards``): a seat looking at the top cards and keeping one
(the others cannot tell which), Secrets' random steal and Insidious' gift
(the table sees a card change hands, only the two seats see which,
OQ-010 ruling 3).

A shuffle forgets the cards it shuffles. Every reshuffle the engine makes
forms the new deck from the discard pile beneath the cards the deck still
holds (``rules.intrigue_deck``, OQ-052), and no known card is in the
discard, so today no reshuffle moves a known card.
"""

from collections.abc import Iterable
from copy import replace

from dune_imperium.core.observation import resolving_intrigue_ids
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState


def remember_intrigue(player: PlayerState, cards: Iterable[str]) -> PlayerState:
    """``player`` knowing ``cards`` too (each once, in the order learnt)."""

    known = tuple(dict.fromkeys((*player.known_intrigue_ids, *cards)))
    if known == player.known_intrigue_ids:
        return player
    return replace(player, known_intrigue_ids=known)


def forget_intrigue_cards(
    state: GameState, cards: Iterable[str], *, keeping: Iterable[int] = ()
) -> GameState:
    """``state`` with every seat but ``keeping`` forgetting ``cards``: a
    hidden move it could not follow. Returns ``state`` itself when nothing
    changes."""

    forgotten = frozenset(cards)
    kept = frozenset(keeping)
    players = tuple(
        player
        if player.player_id in kept
        or not forgotten.intersection(player.known_intrigue_ids)
        else replace(
            player,
            known_intrigue_ids=tuple(
                card for card in player.known_intrigue_ids if card not in forgotten
            ),
        )
        for player in state.players
    )
    if all(
        after is before for after, before in zip(players, state.players, strict=True)
    ):
        return state
    return replace(state, players=players)


def settle_known_intrigue(state: GameState) -> GameState:
    """``state`` with every seat's ``known_intrigue_ids`` kept to the cards in
    the Intrigue deck or in another seat's held Intrigue.

    Returns ``state`` itself when no seat changes: most games never hold an
    entry, and this runs after every transition.
    """

    if not any(player.known_intrigue_ids for player in state.players):
        return state
    players = tuple(_settled(state, player) for player in state.players)
    if all(
        after is before for after, before in zip(players, state.players, strict=True)
    ):
        return state
    return replace(state, players=players)


def _settled(state: GameState, player: PlayerState) -> PlayerState:
    if not player.known_intrigue_ids:
        return player
    hidden_elsewhere = frozenset(state.intrigue_deck).union(
        *(
            other.intrigue_cards
            for other in state.players
            if other.player_id != player.player_id
        )
    ) - frozenset(resolving_intrigue_ids(state))
    kept = tuple(card for card in player.known_intrigue_ids if card in hidden_elsewhere)
    if kept == player.known_intrigue_ids:
        return player
    return replace(player, known_intrigue_ids=kept)
