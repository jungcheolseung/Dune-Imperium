"""The columns observations v35 to v37 added at the end of older segments.

Stage P2a of docs/base-game-and-ix-plan.md (15.4): the original game's three
Reserve cards in every personal-card segment and its three Reserve stacks,
two Maker spaces, Carthag's Control and a fourth Agent location per seat,
and the new ``mentat`` segment; v36 (stage P2b) appended the Masterstroke
segments; v37 (stage P3a, 16.4) the original game's 46 Imperium cards in
every personal-card segment and its 34 Intrigue cards in every Intrigue
segment. Tests that rebuild an older layout from today's (a migrated
checkpoint, the v31 input names, the golden digests) take these columns
off.
"""

from dune_imperium.adapters.observation_encoding import (
    INTRIGUE_IDS,
    OBSERVATION_SEGMENTS,
    PERSONAL_CARD_IDS,
    ObservationSegment,
)
from dune_imperium.content.imperium.imperium import IMPERIUM_BASE_CARDS
from dune_imperium.content.imperium.intrigue import IMPERIUM_INTRIGUE_CARDS

NEW_SEGMENTS = frozenset({"mentat", "masterstroke_secret", "private_masterstroke"})
_V37_PERSONAL = len(IMPERIUM_BASE_CARDS)
_V37_INTRIGUE = len(IMPERIUM_INTRIGUE_CARDS)


def growth_since_v34(segment: ObservationSegment) -> int:
    """How many of ``segment``'s last columns v35 to v37 added (all of a
    new segment's)."""

    if segment.name in NEW_SEGMENTS:
        return segment.length
    if segment.length == len(PERSONAL_CARD_IDS):
        return 3 + _V37_PERSONAL
    if segment.length == len(INTRIGUE_IDS):
        return _V37_INTRIGUE
    if segment.name.endswith(("_control", "_agent_locations")):
        return 1
    return {"reserve_stacks": 3, "maker_bonus_spice": 2}.get(segment.name, 0)


GROWN_COLUMNS = sum(growth_since_v34(segment) for segment in OBSERVATION_SEGMENTS)
