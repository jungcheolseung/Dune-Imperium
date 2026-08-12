"""The ten-card Uprising starting deck listed in Main Rulebook p. 3."""

from dataclasses import dataclass
from typing import Final

from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef


@dataclass(frozen=True, slots=True)
class StartingCardEntry:
    """One starting-card definition and its per-player quantity."""

    card: CardDefinition
    copies: int

    def __post_init__(self) -> None:
        if self.copies < 1:
            raise ValueError("starting-card copies must be positive")


MAIN_P3: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3,)),)

STARTING_DECK: Final = (
    StartingCardEntry(
        CardDefinition(
            "convincing_argument",
            "Convincing Argument",
            MAIN_P3,
        ),
        copies=2,
    ),
    StartingCardEntry(CardDefinition("dagger", "Dagger", MAIN_P3), copies=2),
    StartingCardEntry(CardDefinition("diplomacy", "Diplomacy", MAIN_P3), copies=1),
    StartingCardEntry(
        CardDefinition(
            "dune_the_desert_planet",
            "Dune, the Desert Planet",
            MAIN_P3,
        ),
        copies=2,
    ),
    StartingCardEntry(
        CardDefinition("reconnaissance", "Reconnaissance", MAIN_P3),
        copies=1,
    ),
    StartingCardEntry(
        CardDefinition("seek_allies", "Seek Allies", MAIN_P3),
        copies=1,
    ),
    StartingCardEntry(
        CardDefinition("signet_ring", "Signet Ring", MAIN_P3),
        copies=1,
    ),
)


def starting_deck_instance_ids(player: int) -> tuple[str, ...]:
    """Create stable IDs for one player's unshuffled starting cards."""

    if player < 0:
        raise ValueError("player must not be negative")
    return tuple(
        f"player:{player}:starter:{entry.card.card_id}:{copy}"
        for entry in STARTING_DECK
        for copy in range(entry.copies)
    )
