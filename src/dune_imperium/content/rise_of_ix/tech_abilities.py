"""Rise of Ix's Tech tiles' acquire effects as ability records.

What a Rise of Ix tile gives when it is acquired, keyed by tile id, one line
per printed icon (as the Tech Module's, ``content.bloodlines.tech_abilities``);
moved here from that module in stage 4 of docs/content-core-refactor-plan.md.
The tiles' abilities have no record (``content.rise_of_ix.tech``).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.core.abilities import Ability
from dune_imperium.content.core.effects import (
    DrawIntrigueCards,
    DrawPersonalCards,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    RecruitTroops,
    TrashPersonalCard,
)
from dune_imperium.content.core.tech import acquire_icons

IX_TECH_ACQUIRE_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        # Rise of Ix's tiles (stage P4a, ``content.rise_of_ix.tech``): the
        # acquire effects of docs/rules/rise-of-ix.md 4's table, as the app's
        # ``AcquireEffectList`` lists them. No setup deals these tiles yet.
        # Windtraps' water and Shuttle Fleet's "Choose two" Factions (two
        # different ones named before either is paid, OQ-114, as
        # Machinations' record) are the ``water`` and ``distinct_influence``
        # keys of ``TechTile.acquire_effect_keys`` (stage P4c-2a).
        "chaumurky": acquire_icons(DrawIntrigueCards(2)),
        # The trash icon, optional as Planetary Array's.
        "disposal_facility": acquire_icons(TrashPersonalCard()),
        "flagship": acquire_icons(GainVictoryPoints(1)),
        "invasion_ships": acquire_icons(RecruitTroops(4)),
        "memocorders": acquire_icons(GainInfluence()),
        "shuttle_fleet": acquire_icons(GainInfluence(times=2, distinct=True)),
        "sonic_snoopers": acquire_icons(DrawIntrigueCards(1)),
        # Paid at once, on acquiring (docs/rules/rise-of-ix.md 9.3).
        "spaceport": acquire_icons(DrawPersonalCards(2)),
        "windtraps": acquire_icons(GainResources(water=1)),
    }
)
