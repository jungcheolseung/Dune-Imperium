"""Standard Contract identities for the Uprising CHOAM Module."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.uprising.board import Faction


class ContractConditionKind(StrEnum):
    """Printed ways a standard Contract can be completed."""

    BOARD_SPACE = "board_space"
    HARVEST_SPICE = "harvest_spice"
    ACQUIRE_CARD = "acquire_card"
    IMMEDIATE = "immediate"


@dataclass(frozen=True, slots=True)
class ContractCondition:
    """One printed Contract completion condition."""

    kind: ContractConditionKind
    target: str = ""
    amount: int = 0

    def __post_init__(self) -> None:
        if self.kind in (
            ContractConditionKind.BOARD_SPACE,
            ContractConditionKind.ACQUIRE_CARD,
        ):
            if not self.target or self.amount:
                raise ValueError("target Contract conditions require only a target")
        elif self.kind is ContractConditionKind.HARVEST_SPICE:
            if self.target or self.amount < 1:
                raise ValueError("Harvest Contracts require a positive Spice amount")
        elif self.target or self.amount:
            raise ValueError("Immediate Contracts have no target or amount")


@dataclass(frozen=True, slots=True)
class ContractReward:
    """One printed standard Contract reward."""

    solari: int = 0
    water: int = 0
    troops: int = 0
    personal_cards: int = 0
    contracts: int = 0
    spies: int = 0
    recall_agents: int = 0
    influence_faction: Faction | None = None
    influence: int = 0

    def __post_init__(self) -> None:
        quantities = (
            self.solari,
            self.water,
            self.troops,
            self.personal_cards,
            self.contracts,
            self.spies,
            self.recall_agents,
            self.influence,
        )
        if min(quantities) < 0:
            raise ValueError("Contract rewards must not be negative")
        if not any(quantities):
            raise ValueError("a Contract reward must grant something")
        if (self.influence_faction is None) != (self.influence == 0):
            raise ValueError("Contract Influence requires both a Faction and amount")


@dataclass(frozen=True, slots=True)
class ContractDefinition:
    """One unique standard Contract tile."""

    card: CardDefinition
    condition: ContractCondition
    reward: ContractReward

    @property
    def completes_immediately(self) -> bool:
        """Return whether taking this Contract completes it immediately."""

        return self.condition.kind is ContractConditionKind.IMMEDIATE


CONTRACT_SOURCES: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (16,)),)


def _contract(
    catalog_id: int,
    slug: str,
    name: str,
    *,
    condition: ContractCondition,
    reward: ContractReward,
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
        condition=condition,
        reward=reward,
    )


CONTRACTS: Final = (
    _contract(
        517,
        "acquire",
        "Acquire",
        condition=ContractCondition(
            ContractConditionKind.ACQUIRE_CARD,
            target="the_spice_must_flow",
        ),
        reward=ContractReward(
            solari=3,
            influence_faction=Faction.SPACING_GUILD,
            influence=1,
        ),
    ),
    _contract(
        512,
        "arrakeen-i",
        "Arrakeen I",
        condition=ContractCondition(
            ContractConditionKind.BOARD_SPACE,
            target="arrakeen",
        ),
        reward=ContractReward(water=1),
    ),
    _contract(
        511,
        "arrakeen-ii",
        "Arrakeen II",
        condition=ContractCondition(
            ContractConditionKind.BOARD_SPACE,
            target="arrakeen",
        ),
        reward=ContractReward(troops=1, spies=1),
    ),
    _contract(
        518,
        "deliver-supplies",
        "Deliver Supplies",
        condition=ContractCondition(
            ContractConditionKind.BOARD_SPACE,
            target="deliver_supplies",
        ),
        reward=ContractReward(solari=3),
    ),
    _contract(
        506,
        "espionage-i",
        "Espionage I",
        condition=ContractCondition(
            ContractConditionKind.BOARD_SPACE,
            target="espionage",
        ),
        reward=ContractReward(solari=3),
    ),
    _contract(
        496,
        "espionage-ii",
        "Espionage II",
        condition=ContractCondition(
            ContractConditionKind.BOARD_SPACE,
            target="espionage",
        ),
        reward=ContractReward(solari=1, contracts=1),
    ),
    _contract(
        508,
        "harvest-3",
        "Harvest 3+",
        condition=ContractCondition(ContractConditionKind.HARVEST_SPICE, amount=3),
        reward=ContractReward(solari=3),
    ),
    _contract(
        493,
        "harvest-3-contract",
        "Harvest 3+",
        condition=ContractCondition(ContractConditionKind.HARVEST_SPICE, amount=3),
        reward=ContractReward(contracts=1),
    ),
    _contract(
        507,
        "harvest-4",
        "Harvest 4+",
        condition=ContractCondition(ContractConditionKind.HARVEST_SPICE, amount=4),
        reward=ContractReward(solari=4),
    ),
    _contract(
        500,
        "harvest-4-contract",
        "Harvest 4+",
        condition=ContractCondition(ContractConditionKind.HARVEST_SPICE, amount=4),
        reward=ContractReward(solari=2, contracts=1),
    ),
    _contract(
        505,
        "heighliner-i",
        "Heighliner I",
        condition=ContractCondition(
            ContractConditionKind.BOARD_SPACE,
            target="heighliner",
        ),
        reward=ContractReward(water=2),
    ),
    _contract(
        504,
        "heighliner-ii",
        "Heighliner II",
        condition=ContractCondition(
            ContractConditionKind.BOARD_SPACE,
            target="heighliner",
        ),
        reward=ContractReward(troops=2),
    ),
    _contract(
        494,
        "heighliner-iii",
        "Heighliner III",
        condition=ContractCondition(
            ContractConditionKind.BOARD_SPACE,
            target="heighliner",
        ),
        reward=ContractReward(solari=3, contracts=1),
    ),
    _contract(
        516,
        "high-council-i",
        "High Council I",
        condition=ContractCondition(
            ContractConditionKind.BOARD_SPACE,
            target="high_council",
        ),
        reward=ContractReward(
            influence_faction=Faction.BENE_GESSERIT,
            influence=1,
        ),
    ),
    _contract(
        515,
        "high-council-ii",
        "High Council II",
        condition=ContractCondition(
            ContractConditionKind.BOARD_SPACE,
            target="high_council",
        ),
        reward=ContractReward(solari=3),
    ),
    _contract(
        501,
        "immediate",
        "Immediate",
        condition=ContractCondition(ContractConditionKind.IMMEDIATE),
        reward=ContractReward(solari=2),
    ),
    _contract(
        510,
        "research-station-i",
        "Research Station I",
        condition=ContractCondition(
            ContractConditionKind.BOARD_SPACE,
            target="research_station",
        ),
        reward=ContractReward(solari=2, spies=1),
    ),
    _contract(
        509,
        "research-station-ii",
        "Research Station II",
        condition=ContractCondition(
            ContractConditionKind.BOARD_SPACE,
            target="research_station",
        ),
        reward=ContractReward(solari=3),
    ),
    _contract(
        503,
        "sardaukar-i",
        "Sardaukar I",
        condition=ContractCondition(
            ContractConditionKind.BOARD_SPACE,
            target="sardaukar",
        ),
        reward=ContractReward(personal_cards=2),
    ),
    _contract(
        502,
        "sardaukar-ii",
        "Sardaukar II",
        condition=ContractCondition(
            ContractConditionKind.BOARD_SPACE,
            target="sardaukar",
        ),
        # The printed reward recalls one of the player's Agents; per the
        # general glossary the recalled Agent cannot be the one just sent
        # [Main p. 20].
        reward=ContractReward(recall_agents=1),
    ),
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
