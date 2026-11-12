"""Contract tiles across every set (stage 4, docs/content-core-refactor-plan.md
8.3): Uprising's 20 standard tiles, Bloodlines' eight, the ten Rise of Ix
tiles, and the lookups the setup and the rules use.
"""

from typing import Final

from dune_imperium.content.bloodlines.contracts import BLOODLINES_CONTRACTS
from dune_imperium.content.core.cards import ContractDefinition
from dune_imperium.content.rise_of_ix.contracts import IX_CONTRACTS
from dune_imperium.content.uprising.contracts import STANDARD_CONTRACTS

# The Rise of Ix tiles end the tuple, so every older tile keeps its index in
# the observation's Contract segments (observation v40, stage P7f-2).
CONTRACTS: Final = (*STANDARD_CONTRACTS, *BLOODLINES_CONTRACTS, *IX_CONTRACTS)

CONTRACTS_BY_ID: Final = {contract.card.card_id: contract for contract in CONTRACTS}


def contracts_for(*, bloodlines: bool = False) -> tuple[ContractDefinition, ...]:
    """Return the Contract tiles a setup shuffles into the bank (never the
    Rise of Ix tiles, ``ix_contract_instance_ids``)."""

    if bloodlines:
        return (*STANDARD_CONTRACTS, *BLOODLINES_CONTRACTS)
    return STANDARD_CONTRACTS


def contract_instance_ids(*, bloodlines: bool = False) -> tuple[str, ...]:
    """Return stable IDs for the Contract tiles in play, one per tile.

    The 20 standard tiles always; Bloodlines adds its eight tokens to the
    same bank when the option is on [Bloodlines p. 2].
    """

    return tuple(
        f"contract:{contract.card.card_id}"
        for contract in contracts_for(bloodlines=bloodlines)
    )


def ix_contract_instance_ids(*, rise_of_ix: bool) -> tuple[str, ...]:
    """Return the instance IDs of the ten Rise of Ix tiles in a game with
    Rise of Ix (dealt at setup with the CHOAM Module [Main p. 16]), else ()."""

    if not rise_of_ix:
        return ()
    return tuple(f"contract:{contract.card.card_id}" for contract in IX_CONTRACTS)


def contract_for_instance(instance_id: str) -> ContractDefinition:
    """Resolve one standard Contract instance ID."""

    prefix = "contract:"
    if not instance_id.startswith(prefix):
        raise KeyError(f"unknown Contract instance ID: {instance_id}")
    try:
        return CONTRACTS_BY_ID[instance_id.removeprefix(prefix)]
    except KeyError as error:
        raise KeyError(f"unknown Contract instance ID: {instance_id}") from error
