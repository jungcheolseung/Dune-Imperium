"""The Bene Tleilax board [Immortality pp. 4-7] and the revised Research Station.

The research track is a field of hexagonal spaces read off the official
board artwork printed in the rulebook [Immortality p. 3 board artwork]; the
Tleilaxu track is the strip above it [Immortality p. 7]. Column and row
coordinates are the transcription's own: columns run left to right from the
start space (column 0) to the last column (8), rows are the hexagon's
vertical slot so that a rightward step always changes the row by one.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from dune_imperium.content.schema import SourceDocument, SourceRef

BOARD_SOURCES: Final = (SourceRef(SourceDocument.IMMORTALITY_RULEBOOK, (3, 6, 7)),)


class ResearchBonus(StrEnum):
    """The bonus printed on one research space [Immortality p. 3 board artwork]."""

    # The start space: no bonus.
    NONE = "none"
    # Generate one specimen.
    SPECIMEN = "specimen"
    # Advance one space on the Tleilaxu track.
    TLEILAXU = "tleilaxu"
    # Another research icon: advance again at once [Immortality p. 6].
    RESEARCH = "research"
    # A black trash icon (optional [Main p. 20]) and one specimen.
    TRASH_AND_SPECIMEN = "trash_and_specimen"
    # One Tleilaxu advance and one specimen.
    TLEILAXU_AND_SPECIMEN = "tleilaxu_and_specimen"
    SOLARI_ONE = "solari_one"
    SPICE_ONE = "spice_one"
    SPICE_TWO = "spice_two"
    # One Influence of the owner's choice.
    INFLUENCE_ANY = "influence_any"
    # "[trash] -> draw a card, Intrigue card": an optional arrow cost.
    TRASH_FOR_CARD_AND_INTRIGUE = "trash_for_card_and_intrigue"
    # "7 Solari -> two Tleilaxu advances": an optional arrow cost.
    SEVEN_SOLARI_FOR_TWO_TLEILAXU = "seven_solari_for_two_tleilaxu"


@dataclass(frozen=True, slots=True)
class ResearchSpace:
    """One hexagon of the research track."""

    space_id: str
    column: int
    row: int
    bonus: ResearchBonus

    def __post_init__(self) -> None:
        if self.column < 0 or self.row < 0:
            raise ValueError("research space coordinates must not be negative")


def _space(column: int, row: int, bonus: ResearchBonus) -> ResearchSpace:
    return ResearchSpace(f"c{column}r{row}", column, row, bonus)


RESEARCH_START_ID: Final = "c0r3"
# Genetic markers sit under the fourth and the last column [Immortality p. 6]
# [Immortality p. 3 board artwork].
FIRST_GENETIC_MARKER_COLUMN: Final = 4
SECOND_GENETIC_MARKER_COLUMN: Final = 8

RESEARCH_SPACES: Final[tuple[ResearchSpace, ...]] = (
    _space(0, 3, ResearchBonus.NONE),
    _space(1, 3, ResearchBonus.SPECIMEN),
    _space(2, 2, ResearchBonus.SPECIMEN),
    _space(2, 4, ResearchBonus.TLEILAXU),
    _space(3, 1, ResearchBonus.RESEARCH),
    _space(3, 3, ResearchBonus.TRASH_AND_SPECIMEN),
    _space(3, 5, ResearchBonus.TLEILAXU_AND_SPECIMEN),
    _space(4, 2, ResearchBonus.TLEILAXU),
    _space(4, 4, ResearchBonus.SPECIMEN),
    _space(4, 6, ResearchBonus.RESEARCH),
    _space(5, 1, ResearchBonus.RESEARCH),
    _space(5, 3, ResearchBonus.SPECIMEN),
    _space(5, 5, ResearchBonus.SOLARI_ONE),
    _space(6, 2, ResearchBonus.SPICE_ONE),
    _space(6, 4, ResearchBonus.TLEILAXU),
    _space(6, 6, ResearchBonus.INFLUENCE_ANY),
    _space(7, 1, ResearchBonus.TLEILAXU),
    _space(7, 3, ResearchBonus.TRASH_FOR_CARD_AND_INTRIGUE),
    _space(7, 5, ResearchBonus.TRASH_AND_SPECIMEN),
    _space(8, 2, ResearchBonus.SPICE_TWO),
    _space(8, 4, ResearchBonus.TLEILAXU),
    _space(8, 6, ResearchBonus.SEVEN_SOLARI_FOR_TWO_TLEILAXU),
)
RESEARCH_SPACES_BY_ID: Final = {space.space_id: space for space in RESEARCH_SPACES}
RESEARCH_LAST_COLUMN: Final = max(space.column for space in RESEARCH_SPACES)


def research_next_space_ids(space_id: str) -> tuple[str, ...]:
    """Return the spaces one rightward step away, top first.

    "advance your research token one space to the right ... You may move
    to either of the two connected hexagonal spaces (in some cases, there is
    only one choice of where to advance). You may never move straight up or
    down, nor to the left" [Immortality pp. 6, 16]. The start space touches
    only the single first-column space.
    """

    current = RESEARCH_SPACES_BY_ID[space_id]
    if space_id == RESEARCH_START_ID:
        # The large start hexagon touches the whole first column.
        return tuple(space.space_id for space in RESEARCH_SPACES if space.column == 1)
    return tuple(
        space.space_id
        for space in RESEARCH_SPACES
        if space.column == current.column + 1 and abs(space.row - current.row) == 1
    )


def genetic_markers_reached(space_id: str) -> int:
    """Return how many genetic markers the token at ``space_id`` has reached.

    "When your research token reaches a column with a genetic marker at the
    bottom, for the rest of the game, any effects on cards marked with that
    icon are active for you" [Immortality p. 6].
    """

    column = RESEARCH_SPACES_BY_ID[space_id].column
    if column >= SECOND_GENETIC_MARKER_COLUMN:
        return 2
    if column >= FIRST_GENETIC_MARKER_COLUMN:
        return 1
    return 0


class TleilaxuBonus(StrEnum):
    """The bonus printed on one Tleilaxu track space [Immortality p. 7]."""

    NONE = "none"
    INTRIGUE = "intrigue"
    # "Each player gains a Victory Point when they reach this space. The
    # first player to reach it takes an additional bonus: the 2 spice that
    # was placed here during setup."
    VICTORY_POINT_AND_FIRST_SPICE = "victory_point_and_first_spice"
    VICTORY_POINT = "victory_point"


# Space 0 is the start box; the token advances one space per Tleilaxu icon.
TLEILAXU_TRACK: Final[tuple[TleilaxuBonus, ...]] = (
    TleilaxuBonus.NONE,
    TleilaxuBonus.NONE,
    TleilaxuBonus.INTRIGUE,
    TleilaxuBonus.NONE,
    TleilaxuBonus.VICTORY_POINT_AND_FIRST_SPICE,
    TleilaxuBonus.NONE,
    TleilaxuBonus.INTRIGUE,
    TleilaxuBonus.VICTORY_POINT,
)
TLEILAXU_TRACK_END: Final = len(TLEILAXU_TRACK) - 1
# "Place 2 spice from the bank on the fourth space of the Tleilaxu track"
# [Immortality p. 4].
TLEILAXU_SETUP_SPICE: Final = 2
TLEILAXU_SETUP_SPICE_SPACE: Final = 4

# Reclaimed Forces plus two dealt cards [Immortality pp. 4, 9].
TLEILAXU_ROW_SIZE: Final = 2
