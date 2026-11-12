"""Every Leader any game prints, by id.

The original game's and Rise of Ix's Leaders follow Uprising's. Moved from
``content.uprising.leaders`` (docs/content-core-refactor-plan.md 2B).
"""

from typing import Final

from dune_imperium.content.bloodlines.leaders import BLOODLINES_LEADERS
from dune_imperium.content.core.cards import LeaderDefinition
from dune_imperium.content.core.schema import GameOption
from dune_imperium.content.imperium.leaders import IMPERIUM_LEADERS
from dune_imperium.content.rise_of_ix.leaders import IX_LEADERS
from dune_imperium.content.uprising.leaders import UPRISING_LEADERS

# The Uprising-format Leaders: Uprising's, then Bloodlines' (dealt only with
# the option, ``leaders_for_choam``).
LEADERS: Final = (*UPRISING_LEADERS, *BLOODLINES_LEADERS)

LEADERS_BY_ID: Final = {
    leader.leader_id: leader
    for leader in (*LEADERS, *IMPERIUM_LEADERS, *IX_LEADERS)
}


def leaders_for_choam(
    choam_module: bool,
    *,
    bloodlines: bool = False,
    tech_module: bool = False,
) -> tuple[LeaderDefinition, ...]:
    """Return Leader cards legal for the selected setup."""

    return tuple(
        leader
        for leader in LEADERS
        if (choam_module or GameOption.CHOAM_MODULE not in leader.requires)
        and (bloodlines or GameOption.BLOODLINES not in leader.requires)
        and (tech_module or GameOption.TECH_MODULE not in leader.requires)
    )
