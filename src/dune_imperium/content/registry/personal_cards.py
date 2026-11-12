"""Resolution of playable cards in one player's personal deck.

A personal card is a starting card, a Reserve card, an Imperium card of any
game or a Tleilaxu card. Moved from ``content.uprising.personal_cards``
(docs/content-core-refactor-plan.md 2B).
"""

from dune_imperium.content.core.cards import (
    ImperiumCardEntry,
    PersonalCardDefinition,
)
from dune_imperium.content.core.kept import kept_by_id
from dune_imperium.content.immortality.tleilaxu import tleilaxu_card_for_instance
from dune_imperium.content.registry.card_abilities import card_standing_hook
from dune_imperium.content.registry.imperium import imperium_card_for_instance
from dune_imperium.content.registry.reserve import reserve_card_for_instance
from dune_imperium.content.uprising.starting_cards import (
    starting_card_for_instance,
)


@kept_by_id
def personal_card_for_instance(
    instance_id: str,
) -> PersonalCardDefinition:
    """Resolve a transcribed personal card without erasing its source schema."""

    if ":starter:" in instance_id:
        return starting_card_for_instance(instance_id)
    if instance_id.startswith("reserve:"):
        return reserve_card_for_instance(instance_id)
    if instance_id.startswith("imperium:"):
        definition = imperium_card_for_instance(instance_id)
        if not definition.play_data_complete:
            raise NotImplementedError(
                "Imperium-card play data is not transcribed: " + instance_id
            )
        return definition
    if instance_id.startswith("tleilaxu:"):
        # Immortality: Tleilaxu cards are Imperium-style cards bought with
        # specimens [Immortality p. 8].
        tleilaxu = tleilaxu_card_for_instance(instance_id)
        if not tleilaxu.play_data_complete:
            raise NotImplementedError(
                "Tleilaxu-card play data is not transcribed: " + instance_id
            )
        return tleilaxu
    raise ValueError("unknown personal-card instance ID")


def card_is_graft(card: PersonalCardDefinition) -> bool:
    """Return whether the card's Agent box is a Graft box [Immortality p. 10]."""

    return isinstance(card, ImperiumCardEntry) and card.graft


def card_copies_partner_box(card: PersonalCardDefinition) -> bool:
    """Whether the card "has the same Agent box as the other grafted card"
    (Ghola [Immortality p. 14]), from its standing record."""

    return (
        isinstance(card, ImperiumCardEntry)
        and card_standing_hook(card) == "ghola_copies_agent_box"
    )


def card_grafts_row_card(card: PersonalCardDefinition) -> bool:
    """Whether the card may graft with an Imperium Row card instead of a hand
    card (Usurp, OQ-054), from its standing record."""

    return (
        isinstance(card, ImperiumCardEntry)
        and card_standing_hook(card) == "usurp_grafts_row_card"
    )


def card_sends_agent_anywhere(card: PersonalCardDefinition) -> bool:
    """Kwisatz Haderach (the original game): "Send one of your Agents from
    anywhere to ANY board space (even if occupied)" [DI p. 13]."""

    return isinstance(card, ImperiumCardEntry) and card.sends_agent_anywhere
