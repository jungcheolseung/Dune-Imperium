"""Rise of Ix's four board spaces (stage P4a; docs/rules/rise-of-ix.md 8).

docs/base-game-and-ix-plan.md 17.1 and 17.7: the CHOAM overlay covers the
original board's Landsraad and CHOAM area [Rise of Ix p. 3] and prints four
spaces [Rise of Ix p. 12]: Dreadnought and Tech Negotiation (Landsraad),
Interstellar Shipping and Smuggling (Spice Trade). Their Agent icons, costs
and Influence requirement are docs/rules/rise-of-ix.md 8's table, equal to
the app's ``SpaceArchetypes.RiseOfIx.*`` (``AgentIcon`` Pentagon is
Landsraad, Triangle Spice Trade; Dreadnought's ``SolariCost`` 3;
Interstellar Shipping's ``InfluenceRequirements`` Spacing Guild 2). The ids
are plan 17.2's; Uprising's ``shipping`` space is another space.

These are stage P4a identity entries: their effects (a dreadnought and/or
Acquire Tech; Acquire Tech with Tech Discount 1 or a Negotiator, and the
Persuasion of an Agent there; two Freighter icons; 1 Solari and a Freighter
icon) need the Freighter, dreadnought and Tech pieces of stages P4b and P4c,
so no board ability record names them yet. No ruleset content, setup or
board list holds them (``IMPERIUM_BOARD_SPACES`` keeps the original board's
22, the overlay's swap is stage P4c's), and setup still refuses Rise of Ix.
``content.uprising.board``'s ``BOARD_SPACES_BY_ID`` resolves them; the
observation lists them after every other space from v39
(``adapters.observation_encoding.SPACE_IDS``, plan 17.8). The original board
prints no observation post [DI p. 14]; the posts the overlay gets on
Uprising's board are stage P7's (plan 17.5 1).
"""

from typing import Final

from dune_imperium.content.schema import SourceDocument, SourceRef
from dune_imperium.content.uprising.board import (
    BoardSpace,
    Faction,
    InfluenceRequirement,
    ResourceCost,
)
from dune_imperium.content.uprising.types import AgentIcon

IX_P12: Final = (SourceRef(SourceDocument.RISE_OF_IX_RULEBOOK, (12,)),)

# In plan 17.2's order, which observation v39 reserved for them
# (``voice_blocks_ix``). Typed: ``content.uprising.board`` reads it while
# both modules load.
IX_BOARD_SPACES: Final[tuple[BoardSpace, ...]] = (
    BoardSpace(
        "dreadnought",
        "Dreadnought",
        AgentIcon.LANDSRAAD,
        cost_options=(ResourceCost(solari=3),),
        sources=IX_P12,
    ),
    BoardSpace(
        "tech_negotiation",
        "Tech Negotiation",
        AgentIcon.LANDSRAAD,
        sources=(SourceRef(SourceDocument.RISE_OF_IX_RULEBOOK, (4, 12)),),
    ),
    BoardSpace(
        "interstellar_shipping",
        "Interstellar Shipping",
        AgentIcon.SPICE_TRADE,
        requirement=InfluenceRequirement(Faction.SPACING_GUILD, 2),
        sources=(SourceRef(SourceDocument.RISE_OF_IX_RULEBOOK, (5, 12)),),
    ),
    BoardSpace("smuggling", "Smuggling", AgentIcon.SPICE_TRADE, sources=IX_P12),
)
IX_SPACE_IDS: Final = tuple(space.space_id for space in IX_BOARD_SPACES)
