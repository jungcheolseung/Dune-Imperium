"""Bloodlines' eight Contract tiles' terms as ability records, by tile id.

Moved from ``content.uprising.contract_abilities`` (stage 4,
docs/content-core-refactor-plan.md 8.3); ``content.registry.
contract_abilities`` merges them after Uprising's standard tiles.
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
    AllianceTaken,
    AtBoardSpace,
    ContractTaken,
    DrawIntrigueCards,
    DrawPersonalCards,
    GainResources,
    PlaceSpy,
    RecallAgent,
    RecruitTroops,
    TrashIntrigueCard,
)

_TAKEN = ContractTaken()

BLOODLINES_CONTRACT_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        # Deliver Supplies.
        "bloodlines_deliver_supplies": contract_terms(
            AtBoardSpace("deliver_supplies"),
            GainResources(solari=1),
            PlaceSpy(shared_post=True),
        ),
        # Earn Any Alliance.
        "bloodlines_earn_any_alliance": contract_terms(
            AllianceTaken(), GainResources(solari=2), RecruitTroops(2)
        ),
        # Harvest 3+.
        "bloodlines_harvest_3": contract_terms(
            maker_harvest(3), GainResources(solari=2), PlaceSpy()
        ),
        # Harvest 4+.
        "bloodlines_harvest_4": contract_terms(
            maker_harvest(4), GainResources(solari=3), PlaceSpy()
        ),
        # High Council (Bloodlines). Recall one of your Agents; as with Sardaukar
        # II the Agent just sent is not a valid target [Main p. 20].
        "bloodlines_high_council": contract_terms(
            AtBoardSpace("high_council"), RecallAgent()
        ),
        # Immediate.
        "bloodlines_immediate": contract_terms(
            _TAKEN,
            DrawIntrigueCards(1),
            DrawPersonalCards(1),
            costs=(TrashIntrigueCard(),),
        ),
        # Secrets.
        "bloodlines_secrets": contract_terms(
            AtBoardSpace("secrets"), GainResources(solari=2), DrawPersonalCards(1)
        ),
        # Spice Refinery.
        "bloodlines_spice_refinery": contract_terms(
            AtBoardSpace("spice_refinery"), RecruitTroops(2)
        ),
    }
)
