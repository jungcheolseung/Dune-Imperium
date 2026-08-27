"""Standard Contract identities for the Uprising CHOAM Module."""

from dataclasses import dataclass
from typing import Final

from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef


@dataclass(frozen=True, slots=True)
class ContractDefinition:
    """One unique standard Contract tile."""

    card: CardDefinition
    completes_immediately: bool = False


CONTRACT_SOURCES: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (16,)),)


def _contract(
    catalog_id: int,
    slug: str,
    name: str,
    *,
    completes_immediately: bool = False,
) -> ContractDefinition:
    return ContractDefinition(
        card=CardDefinition(
            card_id=slug.replace("-", "_"),
            name=name,
            sources=CONTRACT_SOURCES,
            catalog_url=(
                f"https://dunecardshub.com/cards/{catalog_id}/uprising-{slug}"
            ),
        ),
        completes_immediately=completes_immediately,
    )


CONTRACTS: Final = (
    _contract(517, "acquire", "Acquire"),
    _contract(512, "arrakeen-i", "Arrakeen I"),
    _contract(511, "arrakeen-ii", "Arrakeen II"),
    _contract(518, "deliver-supplies", "Deliver Supplies"),
    _contract(506, "espionage-i", "Espionage I"),
    _contract(496, "espionage-ii", "Espionage II"),
    _contract(508, "harvest-3", "Harvest 3+"),
    _contract(493, "harvest-3-contract", "Harvest 3+"),
    _contract(507, "harvest-4", "Harvest 4+"),
    _contract(500, "harvest-4-contract", "Harvest 4+"),
    _contract(505, "heighliner-i", "Heighliner I"),
    _contract(504, "heighliner-ii", "Heighliner II"),
    _contract(494, "heighliner-iii", "Heighliner III"),
    _contract(516, "high-council-i", "High Council I"),
    _contract(515, "high-council-ii", "High Council II"),
    _contract(497, "high-council-iii", "High Council III"),
    _contract(501, "immediate", "Immediate", completes_immediately=True),
    _contract(510, "research-station-i", "Research Station I"),
    _contract(509, "research-station-ii", "Research Station II"),
    _contract(503, "sardaukar-i", "Sardaukar I"),
)

CONTRACTS_BY_ID: Final = {contract.card.card_id: contract for contract in CONTRACTS}


def contract_instance_ids() -> tuple[str, ...]:
    """Return stable IDs for the 20 unique standard Contracts."""

    return tuple(f"contract:{contract.card.card_id}" for contract in CONTRACTS)


def contract_for_instance(instance_id: str) -> ContractDefinition:
    """Resolve one standard Contract instance ID."""

    prefix = "contract:"
    if not instance_id.startswith(prefix):
        raise KeyError(f"unknown Contract instance ID: {instance_id}")
    try:
        return CONTRACTS_BY_ID[instance_id.removeprefix(prefix)]
    except KeyError as error:
        raise KeyError(f"unknown Contract instance ID: {instance_id}") from error
