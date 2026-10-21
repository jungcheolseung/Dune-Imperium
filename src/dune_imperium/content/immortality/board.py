"""The Bene Tleilax board [Immortality pp. 4-7] and the revised Research Station.

The research track is a field of hexagonal spaces read off the official
board artwork printed in the rulebook [Immortality p. 3 board artwork]; the
Tleilaxu track is the strip above it [Immortality p. 7]. Column and row
coordinates are the transcription's own: columns run left to right from the
start space (column 0) to the last column (8), rows are the hexagon's
vertical slot so that a rightward step always changes the row by one.
The printed bonuses are ability records (``track_abilities.py``, composed
A7c) compiled into ``ResearchSpace.bonus`` and ``TLEILAXU_TRACK``.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from dune_imperium.content.immortality.track_abilities import (
    RESEARCH_SPACE_ABILITIES,
    TLEILAXU_SPACE_ABILITIES,
)
from dune_imperium.content.schema import SourceDocument, SourceRef
from dune_imperium.content.uprising.abilities import (
    AbilityMark,
    AbilityStructure,
    AbilityTiming,
)
from dune_imperium.content.uprising.effect_dsl import (
    AdvanceTleilaxu,
    DrawIntrigueCards,
    DrawPersonalCards,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    GenerateSpecimens,
    PayResources,
    Research,
    TakeSetupSpice,
    TrashIntrigueCard,
    TrashPersonalCard,
)

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
    # "[Trash an Intrigue card] -> draw a card, Intrigue card": an optional
    # arrow cost. The icon is the gold Intrigue card under an X ("Trash an
    # Intrigue card" [Immortality p. 16]), not the grey trash icon it was
    # first read as (re-read from the board scan on 2026-09-19 by matching
    # the rulebook icon; docs/lessons.md).
    TRASH_INTRIGUE_FOR_CARD_AND_INTRIGUE = "trash_intrigue_for_card_and_intrigue"
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


def _space(column: int, row: int) -> ResearchSpace:
    """One space, its bonus compiled from its record (composed A7c)."""

    space_id = f"c{column}r{row}"
    return ResearchSpace(space_id, column, row, _research_bonus(space_id))


def _research_bonus(space_id: str) -> ResearchBonus:
    """The bonus a research space's record prints; raises ``ValueError``
    for a record no ``ResearchBonus`` holds."""

    record = RESEARCH_SPACE_ABILITIES.get(space_id)
    if record is None:
        return ResearchBonus.NONE
    if (
        record.timing is not AbilityTiming.TRACK_SPACE
        or record.requirement is not None
        or record.trigger is not None
        or record.hook is not None
        or record.structure is AbilityStructure.ONE_OF
    ):
        raise ValueError(f"{space_id}: not a track space's bonus")
    lines = tuple(
        (line.condition, line.costs, line.rewards) for line in record.sections
    )
    automatic = record.mark is AbilityMark.AUTOMATIC
    match lines:
        case ((None, (), (GenerateSpecimens(count=1),)),) if automatic:
            return ResearchBonus.SPECIMEN
        case ((None, (), (AdvanceTleilaxu(count=1),)),) if automatic:
            return ResearchBonus.TLEILAXU
        case ((None, (), (Research(),)),) if automatic:
            return ResearchBonus.RESEARCH
        case (
            (None, (), (TrashPersonalCard() as trash,)),
            (None, (), (GenerateSpecimens(count=1),)),
        ) if automatic and trash == TrashPersonalCard():
            return ResearchBonus.TRASH_AND_SPECIMEN
        case (
            (None, (), (AdvanceTleilaxu(count=1),)),
            (None, (), (GenerateSpecimens(count=1),)),
        ) if automatic:
            return ResearchBonus.TLEILAXU_AND_SPECIMEN
        case ((None, (), (GainResources(solari=1, spice=0, water=0),)),) if automatic:
            return ResearchBonus.SOLARI_ONE
        case ((None, (), (GainResources(solari=0, spice=1, water=0),)),) if automatic:
            return ResearchBonus.SPICE_ONE
        case ((None, (), (GainResources(solari=0, spice=2, water=0),)),) if automatic:
            return ResearchBonus.SPICE_TWO
        case ((None, (), (GainInfluence() as gain,)),) if (
            record.mark is AbilityMark.MANDATORY and gain == GainInfluence()
        ):
            return ResearchBonus.INFLUENCE_ANY
        case (
            (
                None,
                (TrashIntrigueCard() as cost,),
                (DrawPersonalCards(count=1), DrawIntrigueCards(count=1)),
            ),
        ) if record.mark is AbilityMark.OPTIONAL and cost == TrashIntrigueCard():
            return ResearchBonus.TRASH_INTRIGUE_FOR_CARD_AND_INTRIGUE
        case (
            (
                None,
                (PayResources(solari=7, spice=0, water=0),),
                (AdvanceTleilaxu(count=2),),
            ),
        ) if record.mark is AbilityMark.OPTIONAL:
            return ResearchBonus.SEVEN_SOLARI_FOR_TWO_TLEILAXU
    raise ValueError(f"{space_id}: no ResearchBonus holds {lines!r}")


RESEARCH_START_ID: Final = "c0r3"
# Genetic markers sit under the fourth and the last column [Immortality p. 6]
# [Immortality p. 3 board artwork].
FIRST_GENETIC_MARKER_COLUMN: Final = 4
SECOND_GENETIC_MARKER_COLUMN: Final = 8

RESEARCH_SPACES: Final[tuple[ResearchSpace, ...]] = (
    _space(0, 3),
    _space(1, 3),
    _space(2, 2),
    _space(2, 4),
    _space(3, 1),
    _space(3, 3),
    _space(3, 5),
    _space(4, 2),
    _space(4, 4),
    _space(4, 6),
    _space(5, 1),
    _space(5, 3),
    _space(5, 5),
    _space(6, 2),
    _space(6, 4),
    _space(6, 6),
    _space(7, 1),
    _space(7, 3),
    _space(7, 5),
    _space(8, 2),
    _space(8, 4),
    _space(8, 6),
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
    """The label key of the bonus printed on one Tleilaxu track space
    [Immortality p. 7], derived from the space's record for the board's
    labels (``server.catalog``); the rules read the record itself
    (cleanup 2e)."""

    NONE = "none"
    INTRIGUE = "intrigue"
    # "Each player gains a Victory Point when they reach this space. The
    # first player to reach it takes an additional bonus: the 2 spice that
    # was placed here during setup."
    VICTORY_POINT_AND_FIRST_SPICE = "victory_point_and_first_spice"
    VICTORY_POINT = "victory_point"


# Space 0 is the start box; the token advances one space per Tleilaxu icon.
TLEILAXU_TRACK_SPACES: Final = 8


def _tleilaxu_bonus(space: int) -> TleilaxuBonus:
    """The bonus a Tleilaxu track space's record prints (composed A7c);
    raises ``ValueError`` for a record no ``TleilaxuBonus`` holds."""

    record = TLEILAXU_SPACE_ABILITIES.get(space)
    if record is None:
        return TleilaxuBonus.NONE
    if (
        record.timing is not AbilityTiming.TRACK_SPACE
        or record.mark is not AbilityMark.AUTOMATIC
        or record.requirement is not None
        or record.trigger is not None
        or record.hook is not None
        or record.structure is AbilityStructure.ONE_OF
        or any(line.condition is not None or line.costs for line in record.sections)
    ):
        raise ValueError(f"Tleilaxu space {space}: not a track space's bonus")
    match tuple(line.rewards for line in record.sections):
        case ((DrawIntrigueCards(count=1),),):
            return TleilaxuBonus.INTRIGUE
        case ((GainVictoryPoints(amount=1),), (TakeSetupSpice(),)):
            return TleilaxuBonus.VICTORY_POINT_AND_FIRST_SPICE
        case ((GainVictoryPoints(amount=1),),):
            return TleilaxuBonus.VICTORY_POINT
    raise ValueError(f"Tleilaxu space {space}: no TleilaxuBonus holds {record!r}")


TLEILAXU_TRACK: Final[tuple[TleilaxuBonus, ...]] = tuple(
    _tleilaxu_bonus(space) for space in range(TLEILAXU_TRACK_SPACES)
)
TLEILAXU_TRACK_END: Final = len(TLEILAXU_TRACK) - 1
# "Place 2 spice from the bank on the fourth space of the Tleilaxu track"
# [Immortality p. 4].
TLEILAXU_SETUP_SPICE: Final = 2
TLEILAXU_SETUP_SPICE_SPACE: Final = 4

# Reclaimed Forces plus two dealt cards [Immortality pp. 4, 9].
TLEILAXU_ROW_SIZE: Final = 2
