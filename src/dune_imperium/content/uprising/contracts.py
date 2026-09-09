"""Contract identities for the Uprising CHOAM Module.

The 20 standard tiles come from the Uprising box [Main p. 16]; the eight
Bloodlines tiles join them only with the ``bloodlines`` option
[Bloodlines p. 2].
"""

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
    # Bloodlines: "Earn any Alliance" completes the next time the holder
    # takes an Alliance token they do not already hold [Bloodlines p. 2].
    EARN_ALLIANCE = "earn_alliance"
    # Bloodlines: the new Immediate tile costs an Intrigue card trashed from
    # hand and cannot be taken without one [Bloodlines p. 2].
    IMMEDIATE_INTRIGUE_TRASH = "immediate_intrigue_trash"


IMMEDIATE_CONDITION_KINDS: Final = frozenset(
    {
        ContractConditionKind.IMMEDIATE,
        ContractConditionKind.IMMEDIATE_INTRIGUE_TRASH,
    }
)


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
            raise ValueError("this Contract condition has no target or amount")


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
    intrigue_cards: int = 0
    deep_cover_spies: int = 0

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
            self.intrigue_cards,
            self.deep_cover_spies,
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
    bloodlines_only: bool = False

    @property
    def completes_immediately(self) -> bool:
        """Return whether taking this Contract completes it immediately."""

        return self.condition.kind in IMMEDIATE_CONDITION_KINDS

    @property
    def requires_intrigue_trash(self) -> bool:
        """Return whether taking this Contract costs an Intrigue card from hand."""

        return self.condition.kind is ContractConditionKind.IMMEDIATE_INTRIGUE_TRASH


CONTRACT_SOURCES: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (16,)),)
BLOODLINES_CONTRACT_SOURCES: Final = (
    SourceRef(SourceDocument.BLOODLINES_RULEBOOK, (2,)),
)


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


def _bloodlines_contract(
    slug: str,
    name: str,
    *,
    condition: ContractCondition,
    reward: ContractReward,
) -> ContractDefinition:
    # Dune Cards Hub renders its Bloodlines catalog client-side and its
    # sitemap stops before the expansion, so the card face image is the
    # stable reference (the same URL the private asset manifest records).
    return ContractDefinition(
        card=CardDefinition(
            card_id=f"bloodlines_{slug.replace('-', '_')}",
            name=name,
            sources=BLOODLINES_CONTRACT_SOURCES,
            catalog_url=(
                f"https://dunecardshub.com/images/bloodlines-contract-{slug}.webp"
            ),
        ),
        condition=condition,
        reward=reward,
        bloodlines_only=True,
    )


STANDARD_CONTRACTS: Final = (
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

# Bloodlines' eight contract tokens, transcribed from the printed faces
# (assets ``bloodlines/contract/*.webp``) and cross-checked against the BGG
# card inventory sheet (one copy each) [Bloodlines p. 2].
BLOODLINES_CONTRACTS: Final = (
    _bloodlines_contract(
        "deliver-supplies",
        "Deliver Supplies",
        condition=ContractCondition(
            ContractConditionKind.BOARD_SPACE,
            target="deliver_supplies",
        ),
        reward=ContractReward(solari=1, deep_cover_spies=1),
    ),
    _bloodlines_contract(
        "earn-any-alliance",
        "Earn Any Alliance",
        condition=ContractCondition(ContractConditionKind.EARN_ALLIANCE),
        reward=ContractReward(solari=2, troops=2),
    ),
    _bloodlines_contract(
        "harvest-3",
        "Harvest 3+",
        condition=ContractCondition(ContractConditionKind.HARVEST_SPICE, amount=3),
        reward=ContractReward(solari=2, spies=1),
    ),
    _bloodlines_contract(
        "harvest-4",
        "Harvest 4+",
        condition=ContractCondition(ContractConditionKind.HARVEST_SPICE, amount=4),
        reward=ContractReward(solari=3, spies=1),
    ),
    _bloodlines_contract(
        "high-council",
        "High Council",
        condition=ContractCondition(
            ContractConditionKind.BOARD_SPACE,
            target="high_council",
        ),
        # Recall one of your Agents; as with Sardaukar II the Agent just
        # sent is not a valid target [Main p. 20].
        reward=ContractReward(recall_agents=1),
    ),
    _bloodlines_contract(
        "immediate",
        "Immediate",
        # "Requires an Intrigue card": trash an Intrigue card -> draw an
        # Intrigue card and a card [card face] [Bloodlines p. 2].
        condition=ContractCondition(ContractConditionKind.IMMEDIATE_INTRIGUE_TRASH),
        reward=ContractReward(intrigue_cards=1, personal_cards=1),
    ),
    _bloodlines_contract(
        "secrets",
        "Secrets",
        condition=ContractCondition(
            ContractConditionKind.BOARD_SPACE,
            target="secrets",
        ),
        reward=ContractReward(solari=2, personal_cards=1),
    ),
    _bloodlines_contract(
        "spice-refinery",
        "Spice Refinery",
        condition=ContractCondition(
            ContractConditionKind.BOARD_SPACE,
            target="spice_refinery",
        ),
        reward=ContractReward(troops=2),
    ),
)

CONTRACTS: Final = (*STANDARD_CONTRACTS, *BLOODLINES_CONTRACTS)

CONTRACTS_BY_ID: Final = {contract.card.card_id: contract for contract in CONTRACTS}


def contracts_for(*, bloodlines: bool = False) -> tuple[ContractDefinition, ...]:
    """Return the Contract tiles a setup shuffles into the bank."""

    return CONTRACTS if bloodlines else STANDARD_CONTRACTS


def contract_instance_ids(*, bloodlines: bool = False) -> tuple[str, ...]:
    """Return stable IDs for the unique Contract tiles in play.

    The 20 standard tiles always; Bloodlines adds its eight tokens to the
    same bank when the option is on [Bloodlines p. 2].
    """

    return tuple(
        f"contract:{contract.card.card_id}"
        for contract in contracts_for(bloodlines=bloodlines)
    )


def contract_for_instance(instance_id: str) -> ContractDefinition:
    """Resolve one standard Contract instance ID."""

    prefix = "contract:"
    if not instance_id.startswith(prefix):
        raise KeyError(f"unknown Contract instance ID: {instance_id}")
    try:
        return CONTRACTS_BY_ID[instance_id.removeprefix(prefix)]
    except KeyError as error:
        raise KeyError(f"unknown Contract instance ID: {instance_id}") from error
