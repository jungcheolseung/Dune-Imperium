"""Rise of Ix's three Conflict cards' reward rows as ability records (P4d-1).

docs/rules/rise-of-ix.md 12, whose amounts are the Steam app's
``ConflictAbilities.RiseOfIx.*`` arguments (docs/base-game-and-ix-plan.md 17.7):

- Skirmish (``SkirmishE``), I: 1st Freighter, troop 1 | 2nd spice 2 | 3rd spice 1.
- Skirmish (``SkirmishF``), I: 1st Freighter, spice 1 | 2nd 3 Solari | 3rd 2 Solari.
- Trade Monopoly, II: 1st Freighter 2, troop 1 | 2nd Intrigue, water | 3rd
  Intrigue -OR- water.

Written like the original game's (``content.imperium.conflict_abilities``):
one record per place, a line per printed icon group, a printed "-OR-" a
``ONE_OF`` row. "Freighter" is the DSL piece ``Freighter`` (one icon: "may"
move the Freighter up one space or recall it, [Rise of Ix p. 5]); "Freighter 2"
is two of them, as Interstellar Shipping's "Freighter 두 번" is. None of the
three takes control of a space, and like the original game's they print no
battle icon [Rise of Ix p. 2].
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.uprising.abilities import (
    Ability,
    AbilityStructure,
    AbilityTiming,
)
from dune_imperium.content.uprising.effect_dsl import (
    DrawIntrigueCards,
    EffectSection,
    Freighter,
    GainResources,
    RecruitTroops,
    Reward,
)


def _line(*rewards: Reward) -> EffectSection:
    return EffectSection(rewards=rewards)


def _row(*lines: EffectSection) -> Ability:
    return Ability(timing=AbilityTiming.CONFLICT_REWARD, sections=lines)


def _one_of(*lines: EffectSection) -> Ability:
    """A printed "-OR-" between the lines: the recipient takes one."""

    return Ability(
        timing=AbilityTiming.CONFLICT_REWARD,
        sections=lines,
        structure=AbilityStructure.ONE_OF,
    )


IX_CONFLICT_REWARD_ABILITIES: Final[Mapping[str, tuple[Ability, Ability, Ability]]] = (
    MappingProxyType(
        {
            # Skirmish (``SkirmishE``, asset ``Skirmish I.webp``).
            "skirmish_e": (
                _row(_line(Freighter(), RecruitTroops(1))),
                _row(_line(GainResources(spice=2))),
                _row(_line(GainResources(spice=1))),
            ),
            # Skirmish (``SkirmishF``, asset ``Skirmish II.webp``).
            "skirmish_f": (
                _row(_line(Freighter(), GainResources(spice=1))),
                _row(_line(GainResources(solari=3))),
                _row(_line(GainResources(solari=2))),
            ),
            "trade_monopoly": (
                _row(_line(Freighter(), Freighter(), RecruitTroops(1))),
                _row(_line(DrawIntrigueCards(1), GainResources(water=1))),
                _one_of(_line(DrawIntrigueCards(1)), _line(GainResources(water=1))),
            ),
        }
    )
)
