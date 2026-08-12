"""Finite Uprising Reserve stacks."""

from dataclasses import dataclass
from typing import Final

from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef


@dataclass(frozen=True, slots=True)
class ReserveStackDefinition:
    """One face-up Reserve stack and its physical quantity."""

    card: CardDefinition
    copies: int

    def __post_init__(self) -> None:
        if self.copies < 1:
            raise ValueError("reserve stack copies must be positive")


MAIN_P3_P5: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3, 4, 5)),)

RESERVE_STACKS: Final = (
    ReserveStackDefinition(
        CardDefinition(
            "prepare_the_way",
            "Prepare the Way",
            MAIN_P3_P5,
            catalog_url=("https://dunecardshub.com/cards/537/uprising-prepare-the-way"),
        ),
        copies=8,
    ),
    ReserveStackDefinition(
        CardDefinition(
            "the_spice_must_flow",
            "The Spice Must Flow",
            MAIN_P3_P5,
            catalog_url=(
                "https://dunecardshub.com/cards/538/uprising-the-spice-must-flow"
            ),
        ),
        copies=10,
    ),
)
