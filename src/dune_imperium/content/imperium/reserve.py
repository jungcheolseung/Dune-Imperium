"""The original game's three Reserve stacks (docs/rules/imperium-base.md 3).

Arrakis Liaison 8, The Spice Must Flow 10 and Foldspace 6 [DI p. 3]; their
values are the Steam app's ``ImperiumArchetypes.BaseSet`` attributes
(docs/base-game-and-ix-plan.md 15.3). The Spice Must Flow prints otherwise
than Uprising's (no Faction) and takes an ``imperium_`` id; Foldspace is
gained only through the Foldspace icon [DI pp. 11, 16] [FAQ p. 2] and its
card id is ``foldspace_card``, the board space being ``foldspace``.
"""

from typing import Final

from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.reserve import ReserveStackDefinition
from dune_imperium.content.uprising.types import AgentIcon, PersonalCardAgentEffect

_SOURCES: Final = (SourceRef(SourceDocument.IMPERIUM_RULEBOOK, (3, 4, 11)),)

# Typed: ``content.uprising.reserve`` reads it while both modules load.
IMPERIUM_RESERVE_STACKS: Final[tuple[ReserveStackDefinition, ...]] = (
    ReserveStackDefinition(
        CardDefinition("arrakis_liaison", "Arrakis Liaison", _SOURCES),
        copies=8,
        acquisition_cost=2,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.CITY),
        reveal_persuasion=2,
    ),
    # Its Reveal box's 1 spice is a record (``reveal_abilities``).
    ReserveStackDefinition(
        CardDefinition("imperium_the_spice_must_flow", "The Spice Must Flow", _SOURCES),
        copies=10,
        acquisition_cost=9,
        acquisition_vp=1,
    ),
    ReserveStackDefinition(
        CardDefinition("foldspace_card", "Foldspace", _SOURCES),
        copies=6,
        acquisition_cost=0,
        agent_icons=(
            AgentIcon.EMPEROR,
            AgentIcon.SPACING_GUILD,
            AgentIcon.BENE_GESSERIT,
            AgentIcon.FREMEN,
            AgentIcon.LANDSRAAD,
            AgentIcon.CITY,
            AgentIcon.SPICE_TRADE,
        ),
        agent_effect=PersonalCardAgentEffect.DRAW_ONE_AND_TRASH_SELF,
        icon_only=True,
    ),
)
