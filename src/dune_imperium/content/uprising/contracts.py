"""Contract identities for the Uprising CHOAM Module.

The 20 standard tiles come from the Uprising box [Main p. 16]; the eight
Bloodlines tiles join them only with the ``bloodlines`` option
[Bloodlines p. 2]. The box's other ten tiles, "with contrasting backs",
are "Used only with the RISE OF IX expansion" [Main p. 16] and are not
transcribed.
"""

from dataclasses import dataclass, replace
from typing import Final

from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.uprising.abilities import Ability
from dune_imperium.content.uprising.contract_abilities import CONTRACT_ABILITIES
from dune_imperium.content.uprising.effect_dsl import (
    AcquiredCard,
    AllConditions,
    AllianceTaken,
    AtBoardSpace,
    AtMakerSpace,
    Condition,
    ContractTaken,
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    GainedSpiceThisTurn,
    GainInfluence,
    GainResources,
    PlaceSpy,
    RecallAgent,
    RecruitTroops,
    TakeContract,
    TrashIntrigueCard,
)


@dataclass(frozen=True, slots=True)
class ContractDefinition:
    """One standard Contract tile.

    Each physical tile has its own id, so two copies of one printed face are
    two definitions; ``copy_of`` names the first copy's id, whose picture,
    Korean name and record the second copy shares. ``terms`` is the tile's
    ability record (``contract_abilities``): its ``requirement`` is the
    completion condition and its one line the reward. The rules, the card
    text and the codec read it (the compiled ``ContractCondition`` /
    ``ContractReward`` copies are gone since the reward totals cleanup,
    2026-10-21).
    """

    card: CardDefinition
    terms: Ability
    bloodlines_only: bool = False
    copy_of: str | None = None

    def __post_init__(self) -> None:
        check_contract_terms(self.terms)

    @property
    def requirement(self) -> Condition:
        """The printed completion condition."""

        requirement = self.terms.requirement
        assert requirement is not None  # ``check_contract_terms``
        return requirement

    @property
    def reward_line(self) -> EffectSection:
        """The printed reward line (its cost, Bloodlines' Immediate trash)."""

        (line,) = self.terms.sections
        return line

    @property
    def board_space(self) -> str | None:
        """The board space an Agent visit completes the tile at, if any."""

        requirement = self.requirement
        return requirement.space_id if isinstance(requirement, AtBoardSpace) else None

    @property
    def harvest_spice(self) -> int:
        """The spice a Maker-space visit must gain that turn ("Harvest"), or 0
        for a tile completed otherwise."""

        match self.requirement:
            case AllConditions(
                conditions=(AtMakerSpace(), GainedSpiceThisTurn(amount=n))
            ):
                return n
        return 0

    @property
    def acquire_card(self) -> str | None:
        """The card whose acquisition completes the tile, if any."""

        requirement = self.requirement
        return requirement.card_id if isinstance(requirement, AcquiredCard) else None

    @property
    def earns_alliance(self) -> bool:
        """Whether taking an Alliance token completes the tile (Bloodlines'
        "Earn any Alliance" [Bloodlines p. 2])."""

        return isinstance(self.requirement, AllianceTaken)

    @property
    def completes_immediately(self) -> bool:
        """Return whether taking this Contract completes it immediately."""

        return isinstance(self.requirement, ContractTaken)

    @property
    def requires_intrigue_trash(self) -> bool:
        """Return whether taking this Contract costs an Intrigue card from hand
        (the Bloodlines Immediate tile [Bloodlines p. 2])."""

        return self.completes_immediately and bool(self.reward_line.costs)


def check_contract_terms(terms: Ability) -> None:
    """Refuse a Contract record the rules and the card text cannot read.

    One reward line with no condition of its own and no cost, but the
    Intrigue card the Bloodlines Immediate tile trashes when taken. The
    requirement is an Agent visit to a board space, a Maker-space visit
    gaining spice that turn, a named card acquired, the tile taken
    (Immediate), or an Alliance taken. The reward gives Solari, water,
    troops, cards, Intrigue cards, Contracts, Spies (with or without Deep
    Cover), Agent recalls or one Faction's Influence -- each printed once
    but Spies and recalls, which may repeat -- and gives something. (The
    checks the compiled condition and reward ran until the reward totals
    cleanup, 2026-10-21.)
    """

    if len(terms.sections) != 1:
        raise ValueError("a Contract prints one reward line")
    (line,) = terms.sections
    requirement = terms.requirement
    if line.condition is not None:
        raise ValueError("a Contract's reward line has no condition of its own")
    if line.costs and not (
        isinstance(requirement, ContractTaken) and line.costs == (TrashIntrigueCard(),)
    ):
        raise ValueError(f"no Contract pays {line.costs!r}")
    match requirement:
        case AtBoardSpace(space_id=space_id) if space_id:
            pass
        case AllConditions(
            conditions=(AtMakerSpace(), GainedSpiceThisTurn(amount=n))
        ) if n >= 1:
            pass
        case AcquiredCard(card_id=card_id) if card_id:
            pass
        case ContractTaken() | AllianceTaken():
            pass
        case _:
            raise TypeError(f"{requirement!r} is not a Contract condition")
    printed: set[str] = set()
    gained = 0
    for reward in line.rewards:
        match reward:
            case GainResources(solari=solari, spice=0, water=water):
                key = "resources"
                if min(solari, water) < 0:
                    raise ValueError("Contract rewards must not be negative")
                gained += solari + water
            case RecruitTroops(count=count):
                key, gained = "troops", gained + count
            case GainInfluence(
                times=times,
                factions=(_,),
                distinct=False,
                where_opponent_leads=False,
                different_from_trigger=False,
                minimum_own=0,
            ):
                key, gained = "influence", gained + times
            case DrawIntrigueCards(count=count):
                key, gained = "intrigue_cards", gained + count
            case DrawPersonalCards(count=count):
                key, gained = "personal_cards", gained + count
            case TakeContract(count=count):
                key, gained = "contracts", gained + count
            case PlaceSpy() if reward in (PlaceSpy(), PlaceSpy(shared_post=True)):
                gained += 1
                continue
            case RecallAgent() if reward == RecallAgent():
                gained += 1
                continue
            case _:
                raise TypeError(f"{reward!r} is not a Contract reward")
        if key in printed:
            raise ValueError(f"a Contract prints {key} twice")
        printed.add(key)
    if gained <= 0:
        raise ValueError("a Contract reward must grant something")


CONTRACT_SOURCES: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (16,)),)
BLOODLINES_CONTRACT_SOURCES: Final = (
    SourceRef(SourceDocument.BLOODLINES_RULEBOOK, (2,)),
)


def _contract(catalog_id: int, slug: str, name: str) -> ContractDefinition:
    return ContractDefinition(
        card=CardDefinition(
            card_id=slug.replace("-", "_"),
            name=name,
            sources=CONTRACT_SOURCES,
            catalog_url=(
                f"https://dunecardshub.com/cards/{catalog_id}/uprising-{slug}"
            ),
        ),
        terms=CONTRACT_ABILITIES[slug.replace("-", "_")],
    )


def _second_copy(original: ContractDefinition) -> ContractDefinition:
    """The second physical tile of a printed face that has two copies."""

    first_id = original.card.card_id
    return replace(
        original,
        card=replace(original.card, card_id=f"{first_id}_copy_2"),
        copy_of=first_id,
    )


def _bloodlines_contract(slug: str, name: str) -> ContractDefinition:
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
        terms=CONTRACT_ABILITIES[f"bloodlines_{slug.replace('-', '_')}"],
        bloodlines_only=True,
    )


# The two faces with two copies each (see STANDARD_CONTRACTS).
_ESPIONAGE_I: Final = _contract(
    506,
    "espionage-i",
    "Espionage I",
)
_HARVEST_3: Final = _contract(
    508,
    "harvest-3",
    "Harvest 3+",
)

# The box holds 30 tiles: "20 Contract tokens" and "10 Contract tokens with
# contrasting backs", the latter "Used only with the RISE OF IX expansion" to
# "jumpstart the completion of contracts" [Main p. 16]. Which is which, and
# how many copies of each face, comes from the BGG card inventory sheet
# (assets reference/bgg-card-inventory, the Contracts tab's "Rise of Ix
# -Specific?" and Count columns): the 20 standard tiles are 18 faces, with
# Espionage (3 Solari) and Harvest 3+ (3 Solari) two copies each. Every Rise
# of Ix tile prints "+1 Contract" (the jumpstart); no standard tile does.
# Dune Cards Hub lists all 28 faces as "Uprising contract", one copy each,
# which is how four Rise of Ix tiles (Espionage II, Harvest 3+ and 4+ with a
# Contract, Heighliner III) once stood in for Spice Refinery I and II and the
# two second copies (corrected 2026-09-27, docs/lessons.md). The tiles kept
# then hold their old places in this tuple and the four replacements took
# the removed tiles' places, so the observation's Contract segments (which
# follow this order) moved only there; a checkpoint from before observation
# v21 re-links those columns by identity (training/checkpoint.py).
STANDARD_CONTRACTS: Final = (
    _contract(
        517,
        "acquire",
        "Acquire",
    ),
    _contract(
        512,
        "arrakeen-i",
        "Arrakeen I",
    ),
    _contract(
        511,
        "arrakeen-ii",
        "Arrakeen II",
    ),
    _contract(
        518,
        "deliver-supplies",
        "Deliver Supplies",
    ),
    _ESPIONAGE_I,
    _second_copy(_ESPIONAGE_I),
    _HARVEST_3,
    _second_copy(_HARVEST_3),
    _contract(
        507,
        "harvest-4",
        "Harvest 4+",
    ),
    _contract(
        513,
        "spice-refinery-i",
        "Spice Refinery I",
    ),
    _contract(
        505,
        "heighliner-i",
        "Heighliner I",
    ),
    _contract(
        504,
        "heighliner-ii",
        "Heighliner II",
    ),
    _contract(
        514,
        "spice-refinery-ii",
        "Spice Refinery II",
    ),
    _contract(
        516,
        "high-council-i",
        "High Council I",
    ),
    _contract(
        515,
        "high-council-ii",
        "High Council II",
    ),
    _contract(
        501,
        "immediate",
        "Immediate",
    ),
    _contract(
        510,
        "research-station-i",
        "Research Station I",
    ),
    _contract(
        509,
        "research-station-ii",
        "Research Station II",
    ),
    _contract(
        503,
        "sardaukar-i",
        "Sardaukar I",
    ),
    _contract(
        502,
        "sardaukar-ii",
        "Sardaukar II",
    ),
)

# Bloodlines' eight contract tokens, transcribed from the printed faces
# (assets ``bloodlines/contract/*.webp``) and cross-checked against the BGG
# card inventory sheet (one copy each) [Bloodlines p. 2].
BLOODLINES_CONTRACTS: Final = (
    _bloodlines_contract(
        "deliver-supplies",
        "Deliver Supplies",
    ),
    _bloodlines_contract(
        "earn-any-alliance",
        "Earn Any Alliance",
    ),
    _bloodlines_contract(
        "harvest-3",
        "Harvest 3+",
    ),
    _bloodlines_contract(
        "harvest-4",
        "Harvest 4+",
    ),
    _bloodlines_contract(
        "high-council",
        "High Council",
    ),
    _bloodlines_contract(
        "immediate",
        "Immediate",
        # "Requires an Intrigue card": trash an Intrigue card -> draw an
        # Intrigue card and a card [card face] [Bloodlines p. 2].
    ),
    _bloodlines_contract(
        "secrets",
        "Secrets",
    ),
    _bloodlines_contract(
        "spice-refinery",
        "Spice Refinery",
    ),
)

CONTRACTS: Final = (*STANDARD_CONTRACTS, *BLOODLINES_CONTRACTS)

CONTRACTS_BY_ID: Final = {contract.card.card_id: contract for contract in CONTRACTS}


def contracts_for(*, bloodlines: bool = False) -> tuple[ContractDefinition, ...]:
    """Return the Contract tiles a setup shuffles into the bank."""

    return CONTRACTS if bloodlines else STANDARD_CONTRACTS


def contract_instance_ids(*, bloodlines: bool = False) -> tuple[str, ...]:
    """Return stable IDs for the Contract tiles in play, one per tile.

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
