"""The original game's Conflict reward rows as ability records.

Eighteen cards [DI p. 3] (Conflict I 4, II 10, III 4), written like
Uprising's (``content.uprising.conflict_abilities``): one record per place,
a line per printed icon group. Amounts are the Steam app's
``ConflictAbilities.BaseSet.*`` arguments, which the blind card-face reading
of 2026-10-22 matched on every card (P0 sweep, asset
``analysis/base-ix-2026-10-22/p0-readings/sweep/conflict-leader-board.md``).
A printed "-OR-" is a ``ONE_OF`` row, a printed "Choose two:" over separate
icon groups a ``CHOOSE_TWO`` row (both named before either is paid, OQ-114);
Machinations' "Choose two:" over the four single-Faction Influence icons is
the distinct two-Faction gain Uprising's Propaganda prints. Grand Vision's
two-chevron Influence is one Faction twice [DI p. 16]. The original game
prints no battle icon [DI p. 12].
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
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    Reward,
    TakeControl,
    TakeMentat,
    TrashPersonalCard,
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


def _choose_two(*lines: EffectSection) -> Ability:
    """A printed "Choose two:" over the lines (OQ-114: two different ones)."""

    return Ability(
        timing=AbilityTiming.CONFLICT_REWARD,
        sections=lines,
        structure=AbilityStructure.CHOOSE_TWO,
    )


IMPERIUM_CONFLICT_REWARD_ABILITIES: Final[
    Mapping[str, tuple[Ability, Ability, Ability]]
] = MappingProxyType(
    {
        # Conflict I.
        "skirmish_a": (
            _row(_line(GainVictoryPoints(1))),
            _row(_line(GainResources(water=1))),
            _row(_line(GainResources(spice=1))),
        ),
        "skirmish_b": (
            _row(_line(GainVictoryPoints(1))),
            _row(_line(GainResources(solari=2), DrawIntrigueCards(1))),
            _row(_line(GainResources(solari=2))),
        ),
        "skirmish_c": (
            _row(_line(GainInfluence(), GainResources(spice=1))),
            _row(_line(GainResources(spice=2))),
            _row(_line(GainResources(spice=1))),
        ),
        "skirmish_d": (
            _row(_line(GainInfluence(), GainResources(solari=2))),
            _row(_line(GainResources(solari=3))),
            _row(_line(GainResources(solari=2))),
        ),
        # Conflict II.
        "cloak_and_dagger": (
            _row(_line(GainInfluence(), DrawIntrigueCards(2))),
            _row(_line(GainResources(spice=1), DrawIntrigueCards(1))),
            _one_of(_line(DrawIntrigueCards(1)), _line(GainResources(spice=1))),
        ),
        "desert_power_conflict": (
            _row(_line(GainVictoryPoints(1), GainResources(water=1))),
            _row(_line(GainResources(spice=1, water=1))),
            _row(_line(GainResources(spice=1))),
        ),
        "guild_bank_raid": (
            _row(_line(GainResources(solari=6))),
            _row(_line(GainResources(solari=4))),
            _row(_line(GainResources(solari=2))),
        ),
        "machinations": (
            _row(_line(GainInfluence(times=2, distinct=True))),
            _row(_line(GainResources(solari=2, water=1))),
            _row(_line(GainResources(water=1))),
        ),
        "raid_stockpiles": (
            _row(_line(GainResources(spice=3), DrawIntrigueCards(1))),
            _row(_line(GainResources(spice=2))),
            _row(_line(GainResources(spice=1))),
        ),
        "imperium_secure_imperial_basin": (
            _row(_line(GainVictoryPoints(1), TakeControl("imperial_basin"))),
            _row(_line(GainResources(water=2))),
            _row(_line(GainResources(water=1))),
        ),
        # The rulebook's worked example [DI p. 12].
        "imperium_siege_of_arrakeen": (
            _row(_line(GainVictoryPoints(1), TakeControl("arrakeen"))),
            _row(_line(GainResources(solari=4))),
            _row(_line(GainResources(solari=2))),
        ),
        "siege_of_carthag": (
            _row(_line(GainVictoryPoints(1), TakeControl("carthag"))),
            _row(_line(GainResources(spice=1), DrawIntrigueCards(1))),
            _row(_line(GainResources(spice=1))),
        ),
        # The Mentat is taken "at the start of the next round" [FAQ p. 4].
        "sort_through_the_chaos": (
            _row(_line(TakeMentat(), GainResources(solari=2), DrawIntrigueCards(1))),
            _row(_line(GainResources(solari=2), DrawIntrigueCards(1))),
            _row(_line(GainResources(solari=2))),
        ),
        # The black-X trash is optional [DI p. 16] [FAQ p. 3].
        "terrible_purpose": (
            _row(_line(GainVictoryPoints(1), TrashPersonalCard())),
            _row(_line(GainResources(spice=1, water=1))),
            _row(_line(GainResources(spice=1))),
        ),
        # Conflict III.
        "imperium_battle_for_arrakeen": (
            _row(_line(GainVictoryPoints(2), TakeControl("arrakeen"))),
            _choose_two(
                _line(DrawIntrigueCards(1)),
                _line(GainResources(spice=2)),
                _line(GainResources(solari=3)),
            ),
            _row(_line(GainResources(solari=2), DrawIntrigueCards(1))),
        ),
        "battle_for_carthag": (
            _row(_line(GainVictoryPoints(2), TakeControl("carthag"))),
            _row(_line(GainResources(spice=3), DrawIntrigueCards(1))),
            _row(_line(GainResources(spice=3))),
        ),
        "imperium_battle_for_imperial_basin": (
            _row(_line(GainVictoryPoints(2), TakeControl("imperial_basin"))),
            _row(_line(GainResources(spice=5))),
            _row(_line(GainResources(spice=3))),
        ),
        "grand_vision": (
            _row(_line(GainInfluence(times=2, one_faction=True), DrawIntrigueCards(1))),
            _row(_line(GainResources(spice=3), DrawIntrigueCards(1))),
            _row(_line(GainResources(spice=3))),
        ),
    }
)
