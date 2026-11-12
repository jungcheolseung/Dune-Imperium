"""Trigger ability records of the original game's personal cards, by card id.

The original game's acquire and trash boxes, keyed by card id
(docs/content-core-refactor-plan.md 8.3); ``content.registry.card_abilities``
merges them after Uprising's.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.core.abilities import (
    Ability,
    AbilityTiming,
    automatic_box,
)
from dune_imperium.content.core.effects import GainInfluence, GainResources
from dune_imperium.content.core.icons import Faction

IMPERIUM_ACQUISITION_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        "liet_kynes_card": automatic_box(
            AbilityTiming.ACQUIRE, GainInfluence(factions=(Faction.EMPEROR,))
        ),
        "chani_card": automatic_box(AbilityTiming.ACQUIRE, GainResources(water=1)),
        # CHOAM Directorship: four separate Influence icons, one per Faction,
        # taken one row each in the owner's order (OQ-141; ``rules.acquire_icons``).
        "choam_directorship": automatic_box(
            AbilityTiming.ACQUIRE,
            GainInfluence(factions=(Faction.EMPEROR,)),
            GainInfluence(factions=(Faction.SPACING_GUILD,)),
            GainInfluence(factions=(Faction.BENE_GESSERIT,)),
            GainInfluence(factions=(Faction.FREMEN,)),
        ),
        # Lady Jessica: one Influence with a Faction of the owner's choice, a
        # Faction at 6 not offered (OQ-141, OQ-060).
        "lady_jessica_card": automatic_box(AbilityTiming.ACQUIRE, GainInfluence()),
    }
)

IMPERIUM_TRASH_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        # Assassination Mission: 4 Solari.
        "assassination_mission": automatic_box(
            AbilityTiming.TRASH, GainResources(solari=4)
        ),
    }
)
