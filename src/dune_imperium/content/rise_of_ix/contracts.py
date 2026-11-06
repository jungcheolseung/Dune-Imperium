"""The ten Rise of Ix Contract tiles.

The Uprising box's "10 Contract tokens with contrasting backs", "Used only
with the RISE OF IX expansion" [Main p. 16]: they never join the bank; each
player is dealt two and keeps one (``rules.starting_contracts``, stage
P7f-2). Moved from ``content.uprising.contracts`` (stage 4,
docs/content-core-refactor-plan.md 8.3).
"""

from typing import Final

from dune_imperium.content.core.cards import ContractDefinition
from dune_imperium.content.core.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.rise_of_ix.contract_abilities import IX_CONTRACT_ABILITIES

# Uprising's rulebook prints the tiles' rules [Main p. 16].
IX_CONTRACT_SOURCES: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (16,)),)
IX_CONTRACT_PREFIX: Final = "ix_"


def _ix_contract(key: str, slug: str, name: str) -> ContractDefinition:
    # Dune Cards Hub files these among its 28 "Uprising contract" faces; its
    # image is the stable reference (the private asset manifest's source).
    card_id = f"{IX_CONTRACT_PREFIX}{key}"
    return ContractDefinition(
        card=CardDefinition(
            card_id=card_id,
            name=name,
            sources=IX_CONTRACT_SOURCES,
            catalog_url=f"https://dunecardshub.com/images/uprising-contract-{slug}.webp",
        ),
        terms=IX_CONTRACT_ABILITIES[card_id],
        rise_of_ix_only=True,
    )


# The ten Rise of Ix tiles "with contrasting backs" [Main p. 16], one copy
# each (the BGG card inventory sheet's "Rise of Ix -Specific?" rows,
# docs/rules/choam-module.md), in printed-name order. Transcribed in stage
# P7f-2 from the Steam app's Uprising contract archetypes and card layouts,
# checked against the Dune Cards Hub faces (``IX_CONTRACT_ABILITIES``).
IX_CONTRACTS: Final = (
    _ix_contract("dreadnought", "dreadnought", "Dreadnought"),
    _ix_contract("espionage", "espionage-ii", "Espionage II"),
    _ix_contract("harvest_3", "harvest-3-contract", "Harvest 3+"),
    _ix_contract("harvest_4", "harvest-4-contract", "Harvest 4+"),
    _ix_contract("heighliner", "heighliner-iii", "Heighliner III"),
    _ix_contract("high_council", "high-council-iii", "High Council III"),
    _ix_contract(
        "interstellar_shipping", "interstellar-shipping", "Interstellar Shipping"
    ),
    _ix_contract("secrets", "secrets", "Secrets"),
    _ix_contract("smuggling", "smuggling", "Smuggling"),
    _ix_contract("tech_negotiation", "tech-negotiation", "Tech Negotiation"),
)
