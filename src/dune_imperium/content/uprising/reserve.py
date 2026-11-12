"""Finite Uprising Reserve stacks."""

from typing import Final

from dune_imperium.content.core.cards import ReserveStackDefinition
from dune_imperium.content.core.icons import AgentIcon, Faction
from dune_imperium.content.core.schema import CardDefinition, SourceDocument, SourceRef

MAIN_P3_P5: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3, 4, 5)),)

RESERVE_STACKS: Final = (
    ReserveStackDefinition(
        CardDefinition(
            "prepare_the_way",
            "Prepare the Way",
            MAIN_P3_P5,
            catalog_url=("https://dunecardshub.com/cards/537/uprising-prepare-the-way"),
        ),
        copies=8,
        acquisition_cost=2,
        # Purple "BENE GESSERIT" affiliation banner under the title [card face].
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.CITY),
        reveal_persuasion=2,
    ),
    ReserveStackDefinition(
        CardDefinition(
            "the_spice_must_flow",
            "The Spice Must Flow",
            MAIN_P3_P5,
            catalog_url=(
                "https://dunecardshub.com/cards/538/uprising-the-spice-must-flow"
            ),
        ),
        copies=10,
        acquisition_cost=9,
        acquisition_vp=1,
        # Red "SPACING GUILD" affiliation banner under the title [card face].
        factions=(Faction.SPACING_GUILD,),
        # The Reveal box prints one orange spice hexagon with a "1", not a
        # sword [card face] [Main p. 20] (icon guide): the prior
        # reveal_strength=1 misread the spice hexagon as a sword.
    ),
)

