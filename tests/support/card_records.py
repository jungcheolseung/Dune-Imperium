"""Card records read by card id, for tests that check a card's boxes."""

from dune_imperium.content.core.effects import Reward
from dune_imperium.content.registry.card_abilities import acquisition_ability


def acquire_rewards(card_id: str) -> tuple[Reward, ...]:
    """The rewards of the card's acquire box, or () when it prints none."""

    ability = acquisition_ability(card_id)
    return () if ability is None else ability.sections[0].rewards
