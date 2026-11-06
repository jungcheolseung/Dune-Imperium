"""Trigger ability records of Rise of Ix's personal cards, by card id.

Rise of Ix's acquire boxes (docs/content-core-refactor-plan.md 8.3);
``content.registry.card_abilities`` merges them after the original game's.
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
    CommissionDreadnought,
    Freighter,
    GainResources,
    RecruitTroops,
    TrashPersonalCard,
)

IX_ACQUISITION_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        "negotiated_withdrawal": automatic_box(AbilityTiming.ACQUIRE, RecruitTroops(1)),
        "water_peddler": automatic_box(AbilityTiming.ACQUIRE, GainResources(water=1)),
        # Appropriate: the Freighter icon [Steam app attribute table,
        # AcquireEffectList], "you may move" [Rise of Ix p. 5] -- an optional
        # row of the turn, or outside its owner's turn the Freighter's own
        # window (``rules.acquire_icons``).
        "appropriate": automatic_box(AbilityTiming.ACQUIRE, Freighter()),
        # Full-Scale Assault: the Dreadnought icon, "you may commission" [Rise
        # of Ix p. 6] -- an optional row of the turn (``rules.acquire_icons``).
        "full_scale_assault": automatic_box(
            AbilityTiming.ACQUIRE, CommissionDreadnought()
        ),
        # Shai-Hulud: the black Trash icon, resolved when the card is acquired
        # as an optional trash (``rules.acquisition``, ``rules.optional_trash``).
        "shai_hulud": automatic_box(AbilityTiming.ACQUIRE, TrashPersonalCard()),
    }
)
