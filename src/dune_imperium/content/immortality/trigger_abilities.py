"""Trigger ability records of Immortality's personal cards, by card id.

The acquire and trash boxes of Immortality's Imperium cards and of the
Tleilaxu cards (docs/content-core-refactor-plan.md 8.3);
``content.registry.card_abilities`` merges them after Bloodlines'.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.core.abilities import (
    Ability,
    AbilityTiming,
    automatic_box,
)
from dune_imperium.content.core.effects import (
    AdvanceTleilaxu,
    GainResources,
    RecruitTroops,
    Research,
)

IMMORTALITY_ACQUISITION_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        "spiritual_fervor": automatic_box(AbilityTiming.ACQUIRE, Research()),
        "lisan_al_gaib": automatic_box(AbilityTiming.ACQUIRE, GainResources(spice=1)),
        "occupation": automatic_box(AbilityTiming.ACQUIRE, RecruitTroops(3)),
        "corrino_genes": automatic_box(AbilityTiming.ACQUIRE, GainResources(solari=2)),
        "subject_x_137": automatic_box(AbilityTiming.ACQUIRE, AdvanceTleilaxu(1)),
    }
)

IMMORTALITY_TRASH_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        "replacement_eyes": automatic_box(AbilityTiming.TRASH, AdvanceTleilaxu(1)),
    }
)
