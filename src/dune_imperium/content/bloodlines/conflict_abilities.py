"""Bloodlines' two Conflict cards' reward rows as records (composed A5b).

Moved from ``content.uprising.conflict_abilities``
(docs/content-core-refactor-plan.md 8.3, user decision 2026-11-04);
``content.registry.conflict_abilities`` merges them with every game's.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.core.abilities import Ability, AbilityTiming
from dune_imperium.content.core.effects import (
    DrawIntrigueCards,
    EffectSection,
    GainResources,
    PlaceSpy,
    Reward,
    TrashPersonalCard,
)


def _line(*rewards: Reward) -> EffectSection:
    return EffectSection(rewards=rewards)


def _row(*lines: EffectSection) -> Ability:
    return Ability(timing=AbilityTiming.CONFLICT_REWARD, sections=lines)


BLOODLINES_CONFLICT_REWARD_ABILITIES: Final[
    Mapping[str, tuple[Ability, Ability, Ability]]
] = MappingProxyType(
    {
        # Skirmish (Wild).
        "skirmish_wild": (
            _row(_line(TrashPersonalCard())),
            _row(_line(GainResources(solari=1, water=1))),
            _row(_line(GainResources(solari=2))),
        ),
        # Storms in the South. The first place prints a gold Spy behind a grey
        # one: a Spy with Deep Cover, as on Deliver Supplies [Storms in the
        # South card] [Bloodlines p. 5].
        "storms_in_the_south": (
            _row(_line(GainResources(spice=2), PlaceSpy(shared_post=True))),
            _row(_line(GainResources(solari=2), DrawIntrigueCards(2))),
            _row(_line(GainResources(solari=2), DrawIntrigueCards(1))),
        ),
    }
)
