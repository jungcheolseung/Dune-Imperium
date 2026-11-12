"""Contract tiles' terms across every set, by tile id.

Uprising's standard tiles, then Bloodlines', then the Rise of Ix tiles -- the
order of ``content.registry.contracts.CONTRACTS`` (stage 4,
docs/content-core-refactor-plan.md 8.3).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.bloodlines.contract_abilities import (
    BLOODLINES_CONTRACT_ABILITIES,
)
from dune_imperium.content.core.abilities import Ability
from dune_imperium.content.rise_of_ix.contract_abilities import IX_CONTRACT_ABILITIES
from dune_imperium.content.uprising.contract_abilities import (
    UPRISING_CONTRACT_ABILITIES,
)

CONTRACT_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        **UPRISING_CONTRACT_ABILITIES,
        **BLOODLINES_CONTRACT_ABILITIES,
        **IX_CONTRACT_ABILITIES,
    }
)
