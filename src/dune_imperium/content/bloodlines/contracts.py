"""Bloodlines' eight Contract tiles (``bloodlines`` option) [Bloodlines p. 2].

Moved from ``content.uprising.contracts`` (stage 4,
docs/content-core-refactor-plan.md 8.3); ``content.registry.contracts``
adds them to the bank after Uprising's standard tiles.
"""

from typing import Final

from dune_imperium.content.bloodlines.contract_abilities import (
    BLOODLINES_CONTRACT_ABILITIES,
)
from dune_imperium.content.core.cards import ContractDefinition
from dune_imperium.content.core.schema import (
    CardDefinition,
    GameOption,
    SourceDocument,
    SourceRef,
)

BLOODLINES_CONTRACT_SOURCES: Final = (
    SourceRef(SourceDocument.BLOODLINES_RULEBOOK, (2,)),
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
        terms=BLOODLINES_CONTRACT_ABILITIES[f"bloodlines_{slug.replace('-', '_')}"],
        requires=frozenset({GameOption.BLOODLINES}),
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
