"""Contract identities for the Uprising CHOAM Module.

The 20 standard tiles come from the Uprising box [Main p. 16]; the eight
Bloodlines tiles join them only with the ``bloodlines`` option
[Bloodlines p. 2]. The box's other ten tiles, "with contrasting backs",
are "Used only with the RISE OF IX expansion" [Main p. 16]: they never join
the bank, each player is dealt two and keeps one to begin the game with
(``IX_CONTRACTS``, ``rules.starting_contracts``, stage P7f-2).

This module holds the 20 standard tiles. Bloodlines' tiles are in
``content.bloodlines.contracts``, the Rise of Ix tiles in
``content.rise_of_ix.contracts``, and ``content.registry.contracts`` joins
them (stage 4, docs/content-core-refactor-plan.md 8.3).
"""

from dataclasses import replace
from typing import Final

from dune_imperium.content.core.cards import ContractDefinition
from dune_imperium.content.core.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.uprising.contract_abilities import (
    UPRISING_CONTRACT_ABILITIES,
)

CONTRACT_SOURCES: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (16,)),)


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
        terms=UPRISING_CONTRACT_ABILITIES[slug.replace("-", "_")],
    )


def _second_copy(original: ContractDefinition) -> ContractDefinition:
    """The second physical tile of a printed face that has two copies."""

    first_id = original.card.card_id
    return replace(
        original,
        card=replace(original.card, card_id=f"{first_id}_copy_2"),
        copy_of=first_id,
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
