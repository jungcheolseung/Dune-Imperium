"""The ten Rise of Ix Contract tiles' terms as ability records, by tile id.

The tiles ship in the Uprising box "with contrasting backs", "Used only with
the RISE OF IX expansion" [Main p. 16]; their records moved here from
``content.uprising.contract_abilities`` (stage 4,
docs/content-core-refactor-plan.md 8.3), and ``content.registry.
contract_abilities`` merges them after Bloodlines'.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.core.abilities import (
    Ability,
    contract_terms,
    maker_harvest,
)
from dune_imperium.content.core.effects import (
    AtBoardSpace,
    GainResources,
    PlaceNegotiator,
    TakeContract,
)

IX_CONTRACT_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        # The ten tiles "with contrasting backs", "Used only with the RISE OF
        # IX expansion" [Main p. 16] (stage P7f-2): every one prints "+1
        # Contract" (the jumpstart). Read from the Steam app's attribute
        # table of the ten tiles (the space, ``SpiceCost``, ``Solari``,
        # ``TechNegotiator``) and their printed faces, checked against the
        # Dune Cards Hub faces (docs/rules/choam-module.md). The Tech
        # Negotiation icon is Rise of Ix's Negotiator ("you may take a troop
        # from your supply and place it on the Ix board" [Rise of Ix p. 4]).
        "ix_dreadnought": contract_terms(
            AtBoardSpace("dreadnought"), PlaceNegotiator(), TakeContract()
        ),
        "ix_espionage": contract_terms(
            AtBoardSpace("espionage"), GainResources(solari=1), TakeContract()
        ),
        "ix_harvest_3": contract_terms(maker_harvest(3), TakeContract()),
        "ix_harvest_4": contract_terms(
            maker_harvest(4), GainResources(solari=2), TakeContract()
        ),
        "ix_heighliner": contract_terms(
            AtBoardSpace("heighliner"), GainResources(solari=3), TakeContract()
        ),
        "ix_high_council": contract_terms(
            AtBoardSpace("high_council"), PlaceNegotiator(), TakeContract()
        ),
        "ix_interstellar_shipping": contract_terms(
            AtBoardSpace("interstellar_shipping"), PlaceNegotiator(), TakeContract()
        ),
        "ix_secrets": contract_terms(AtBoardSpace("secrets"), TakeContract()),
        "ix_smuggling": contract_terms(AtBoardSpace("smuggling"), TakeContract()),
        "ix_tech_negotiation": contract_terms(
            AtBoardSpace("tech_negotiation"), TakeContract()
        ),
    }
)
