"""Shared Faction Bond checks for personal-card effects."""

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance


def has_faction_bond(
    card_ids: tuple[str, ...],
    source_card_id: str,
    faction: Faction,
) -> bool:
    """Return whether another card in play has the required affiliation.

    The printed Bond condition only counts OTHER cards of the Faction in
    play [Main p. 20], so the source card's own zone is not part of the
    check. A source trashed before its box resolves never reaches this
    check anymore: its un-activated box expires instead (OQ-022).
    """

    return any(
        candidate_id != source_card_id
        and faction in personal_card_for_instance(candidate_id).factions
        for candidate_id in card_ids
    )
