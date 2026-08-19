"""Shared Faction Bond checks for personal-card effects."""

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance


def has_faction_bond(
    card_ids: tuple[str, ...],
    source_card_id: str,
    faction: Faction,
) -> bool:
    """Return whether another card in play has the required affiliation."""

    if source_card_id not in card_ids:
        raise ValueError("Faction Bond source card must be in play")
    return any(
        candidate_id != source_card_id
        and faction in personal_card_for_instance(candidate_id).factions
        for candidate_id in card_ids
    )
