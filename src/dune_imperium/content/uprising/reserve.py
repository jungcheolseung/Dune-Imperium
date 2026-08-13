"""Finite Uprising Reserve stacks."""

from dataclasses import dataclass
from typing import Final

from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef


@dataclass(frozen=True, slots=True)
class ReserveStackDefinition:
    """One face-up Reserve stack and its physical quantity."""

    card: CardDefinition
    copies: int
    acquisition_cost: int
    acquisition_vp: int = 0

    def __post_init__(self) -> None:
        if self.copies < 1:
            raise ValueError("reserve stack copies must be positive")
        if self.acquisition_cost < 0 or self.acquisition_vp < 0:
            raise ValueError("Reserve acquisition values must not be negative")


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
        acquisition_cost=2,
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
        acquisition_cost=9,
        acquisition_vp=1,
    ),
)

RESERVE_STACKS_BY_ID: Final = {
    stack.card.card_id: stack for stack in RESERVE_STACKS
}
