"""Resolution of playable cards in one player's personal deck."""

from dune_imperium.content.uprising.imperium import (
    ImperiumCardEntry,
    imperium_card_for_instance,
)
from dune_imperium.content.uprising.reserve import (
    ReserveStackDefinition,
    reserve_card_for_instance,
)
from dune_imperium.content.uprising.starting_cards import (
    StartingCardEntry,
    starting_card_for_instance,
)

type PersonalCardDefinition = (
    StartingCardEntry | ReserveStackDefinition | ImperiumCardEntry
)


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
    raise ValueError("unknown personal-card instance ID")
