"""The columns observation v35 added at the end of older segments.

Stage P2a of docs/base-game-and-ix-plan.md (15.4): the original game's three
Reserve cards in every personal-card segment and its three Reserve stacks,
two Maker spaces, Carthag's Control and a fourth Agent location per seat,
and the new ``mentat`` segment. Tests that rebuild an older layout from
today's (a migrated checkpoint, the v31 input names, the golden digests)
take these columns off.
"""

from dune_imperium.adapters.observation_encoding import (
    PERSONAL_CARD_IDS,
    ObservationSegment,
)

V35_SEGMENTS = frozenset({"mentat"})
V35_COLUMNS = 26 * 3 + 3 + 2 + 4 + 4 + 3


def v35_growth(segment: ObservationSegment) -> int:
    """How many of ``segment``'s last columns v35 added (all of a v35
    segment's)."""

    if segment.name in V35_SEGMENTS:
        return segment.length
    if segment.length == len(PERSONAL_CARD_IDS):
        return 3
    if segment.name.endswith(("_control", "_agent_locations")):
        return 1
    return {"reserve_stacks": 3, "maker_bonus_spice": 2}.get(segment.name, 0)
