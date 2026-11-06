"""Trigger ability records of Bloodlines' personal cards, by card id.

Bloodlines' acquire, trash, discard and turn-start boxes
(docs/content-core-refactor-plan.md 8.3); ``content.registry.card_abilities``
merges them after Uprising's.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.core.abilities import (
    Ability,
    AbilityMark,
    AbilityTiming,
    automatic_box,
)
from dune_imperium.content.core.effects import (
    AcquireBankCommander,
    GainInfluence,
    GainResources,
    PlaceSpy,
    RecruitTroops,
    Reward,
    TakeContract,
)
from dune_imperium.content.core.icons import Faction


def _acquire(*rewards: Reward) -> Ability:
    return automatic_box(AbilityTiming.ACQUIRE, *rewards)


def _trash(*rewards: Reward) -> Ability:
    return automatic_box(AbilityTiming.TRASH, *rewards)


def _discard(*rewards: Reward) -> Ability:
    return automatic_box(AbilityTiming.DISCARD, *rewards)


BLOODLINES_ACQUISITION_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        "intelligence_training": _acquire(PlaceSpy()),
        "mercantile_affairs": _acquire(TakeContract(1)),
        "imperial_throneship": _acquire(GainInfluence(factions=(Faction.EMPEROR,))),
        "possible_futures": _acquire(GainResources(water=1)),
    }
)

BLOODLINES_TRASH_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        "eliminate_allies": _trash(RecruitTroops(2)),
        "sardaukar_standard": _trash(AcquireBankCommander()),
    }
)

BLOODLINES_DISCARD_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        "corrupt_bureaucrat": _discard(GainResources(solari=3)),
    }
)

# Litany Against Fear: "Put this card into play -> Draw 1 card and pass your
# turn", only as the turn's first action (OQ-095 (6); ``agent_turn``); its
# flow stays code (composed A4h).
BLOODLINES_TURN_START_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        "litany_against_fear": Ability(
            timing=AbilityTiming.TURN_START,
            sections=(),
            mark=AbilityMark.OPTIONAL,
            hook="litany_against_fear",
        ),
    }
)
