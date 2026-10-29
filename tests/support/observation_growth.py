"""The columns observations v35 to v39 added at the end of older segments.

Stage P2a of docs/base-game-and-ix-plan.md (15.4): the original game's three
Reserve cards in every personal-card segment and its three Reserve stacks,
two Maker spaces, Carthag's Control and a fourth Agent location per seat,
and the new ``mentat`` segment; v36 (stage P2b) appended the Masterstroke
segments; v37 (stage P3a, 16.4) the original game's 46 Imperium cards in
every personal-card segment and its 34 Intrigue cards in every Intrigue
segment; v38 (OQ-145 and the original game's public markers) appended the
public deck-top depths, the Voice's barred spaces and the card turn flags,
all new segments; v39 (stage P4a, 17.8) Rise of Ix's 30 Imperium cards in
every personal-card segment and its 17 Intrigue cards in every Intrigue
segment, the Intrigue deck's size at the end of ``global_scalars`` and its
new segments. Tests that rebuild an older layout from today's (a migrated
checkpoint, the v31 input names, the golden digests) take these columns
off.
"""

from collections.abc import Sequence

from dune_imperium.adapters.observation_encoding import (
    INTRIGUE_IDS,
    OBSERVATION_SEGMENTS,
    PERSONAL_CARD_IDS,
    ObservationSegment,
)
from dune_imperium.content.imperium.imperium import IMPERIUM_BASE_CARDS
from dune_imperium.content.imperium.intrigue import IMPERIUM_INTRIGUE_CARDS
from dune_imperium.content.rise_of_ix.imperium import IX_IMPERIUM_CARDS
from dune_imperium.content.rise_of_ix.intrigue import IX_INTRIGUE_CARDS

# The segments v39 appended (stage P4a, plan 17.8).
V39_NEW_SEGMENTS = frozenset(
    {
        *(f"seat{seat}_units" for seat in range(4)),
        "dreadnought_control",
        *(f"seat{seat}_ix" for seat in range(4)),
        "voice_blocks_ix",
        "private_intrigue_top",
        "private_intrigue_bottom",
        *(f"private_known_intrigue_seat{seat}" for seat in range(1, 4)),
        "private_set_aside",
        "ix_pending",
        "ix_flags",
    }
)
NEW_SEGMENTS = frozenset(
    {
        "mentat",
        "masterstroke_secret",
        "private_masterstroke",
        *(f"seat{seat}_deck_public_top" for seat in range(4)),
        "voice_blocks",
        "card_turn_flags",
        *V39_NEW_SEGMENTS,
    }
)
# Grown columns that are not 0 in an Uprising game: the Intrigue deck's size,
# the last column of ``global_scalars`` since v39 (public in every game).
NONZERO_GROWTH = frozenset({"global_scalars"})
_V37_PERSONAL = len(IMPERIUM_BASE_CARDS)
_V37_INTRIGUE = len(IMPERIUM_INTRIGUE_CARDS)
_V39_PERSONAL = len(IX_IMPERIUM_CARDS)
_V39_INTRIGUE = len(IX_INTRIGUE_CARDS)
# Observation v38's width and segment count.
V38_SIZE = 8_265
V38_SEGMENTS = 137


def growth_in_v39(segment: ObservationSegment) -> int:
    """How many of ``segment``'s last columns v39 added (all of a new
    segment's)."""

    if segment.name in V39_NEW_SEGMENTS:
        return segment.length
    if segment.length == len(PERSONAL_CARD_IDS):
        return _V39_PERSONAL
    if segment.length == len(INTRIGUE_IDS):
        return _V39_INTRIGUE
    return int(segment.name == "global_scalars")


def growth_since_v34(segment: ObservationSegment) -> int:
    """How many of ``segment``'s last columns v35 to v39 added (all of a
    new segment's)."""

    if segment.name in NEW_SEGMENTS:
        return segment.length
    if segment.length == len(PERSONAL_CARD_IDS):
        return 3 + _V37_PERSONAL + _V39_PERSONAL
    if segment.length == len(INTRIGUE_IDS):
        return _V37_INTRIGUE + _V39_INTRIGUE
    if segment.name.endswith(("_control", "_agent_locations")):
        return 1
    return {"reserve_stacks": 3, "maker_bonus_spice": 2, "global_scalars": 1}.get(
        segment.name, 0
    )


GROWN_COLUMNS = sum(growth_since_v34(segment) for segment in OBSERVATION_SEGMENTS)


def v38_layout() -> list[tuple[str, int, int]]:
    """Observation v38's layout as (segment, offset, length), rebuilt from
    today's: every v38 segment by name, without v39's columns."""

    layout: list[tuple[str, int, int]] = []
    offset = 0
    for segment in OBSERVATION_SEGMENTS:
        if segment.name in V39_NEW_SEGMENTS:
            continue
        length = segment.length - growth_in_v39(segment)
        layout.append((segment.name, offset, length))
        offset += length
    return layout


def v38_columns(vector: Sequence[int]) -> list[int]:
    """The v38 vector inside a v39 one: each v38 segment's columns, in the
    v38 order (``v38_layout``)."""

    older: list[int] = []
    for segment in OBSERVATION_SEGMENTS:
        if segment.name in V39_NEW_SEGMENTS:
            continue
        length = segment.length - growth_in_v39(segment)
        older.extend(vector[segment.offset : segment.offset + length])
    return older
