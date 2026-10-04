"""Shared in-play checks for personal-card effects: Faction Bonds and the
cards that count as in play."""

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.core.player import PlayerState


def counted_in_play(seat: PlayerState) -> tuple[str, ...]:
    """Return the cards of ``seat``'s play area that count as "in play".

    "A grafted card in the Imperium Row isn't considered to be 'in play.'"
    [Immortality p. 14]. The Row card borrowed with Usurp sits in the play
    area until the owner ends the turn and is then trashed (OQ-054), but it
    is not in play for any rule (designer ruling adopted 2026-09-09; OQ-054,
    user ruling 2026-10-04): Faction Bonds, in-play counts, the "trash a
    card from your hand, discard pile or in play" lists and returns to hand
    read this. Zone bookkeeping (playing, trashing or discarding a card,
    the observation's play area) keeps reading ``seat.in_play``, and so
    does an effect that names "this card" or "the other grafted card".
    """

    borrowed = seat.usurped_row_card_id
    if not borrowed:
        return seat.in_play
    return tuple(card_id for card_id in seat.in_play if card_id != borrowed)


def has_faction_bond(
    card_ids: tuple[str, ...],
    source_card_id: str,
    faction: Faction,
) -> bool:
    """Return whether another card in play has the required affiliation.

    The printed Bond condition only counts OTHER cards of the Faction in
    play [Main p. 20], so the source card's own zone is not part of the
    check. A source trashed before its box resolves never reaches this
    check anymore: its un-activated box expires instead (OQ-022). Callers
    pass ``counted_in_play``, so a Row card borrowed with Usurp is never
    the other card (OQ-054).
    """

    return any(
        candidate_id != source_card_id
        and faction in personal_card_for_instance(candidate_id).factions
        for candidate_id in card_ids
    )
