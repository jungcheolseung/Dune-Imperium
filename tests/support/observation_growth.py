"""The columns observations v35 to v43 added at the end of older segments.

Stage P2a of docs/base-game-and-ix-plan.md (15.4): the original game's three
Reserve cards in every personal-card segment and its three Reserve stacks,
two Maker spaces, Carthag's Control and a fourth Agent location per seat,
and the new ``mentat`` segment; v36 (stage P2b) appended the Masterstroke
segments; v37 (stage P3a, 16.4) the original game's 46 Imperium cards in
every personal-card segment and its 34 Intrigue cards in every Intrigue
segment; v38 (OQ-145 and the original game's public markers) appended the
public deck-top depths, the Voice's barred spaces and the card turn flags,
all new segments; v39 (stage P4a, 17.8) Rise of Ix's 30 Imperium cards in
every personal-card segment, its 17 Intrigue cards in every Intrigue segment
and its 18 Tech tiles in every Tech segment (``TECH_SEGMENTS``), the Intrigue
deck's size at the end of ``global_scalars`` and its new segments (its four
board spaces join ``SPACE_IDS``, which no segment has a column per); v40
(stage P7) every board's Sardaukar Commander setup spaces after Uprising's
six in ``commander_spaces`` (P7c), Rise of Ix's two observation posts on
Uprising's board at the end of every post segment (``POST_SEGMENTS``, P7f)
and (P7f-2) the ten Rise of Ix Contracts at the end of every Contract segment
(``CONTRACT_SEGMENTS``), the new ``private_starting_contracts`` and
``private_starting_contract_pick``, and Arrakeen Scouts' three Rise of Ix
missions at the end of the Scouts item and mission segments; v41 (stage P8)
the original game's Arrakeen Scouts items at the end of the Scouts item
segment and its missions (stage P8b-2) at the end of the parked and goods
segments; v42 (OQ-166) the new ``scouts_parked_commanders`` segment, the
garrison Sardaukar Commanders parked in place of a mission's troop (mission x
relative seat); v43 three more set-aside Imperium card slots at the end of
each relative seat's ``imperium_set_aside`` (two to five).
Tests that rebuild an older layout from today's (a migrated checkpoint, the
v31 input names, the golden digests) take these columns off.
"""

from collections.abc import Sequence

from dune_imperium.adapters.observation_encoding import (
    COMMANDER_SPACE_IDS,
    CONTRACT_SEGMENTS,
    INTRIGUE_IDS,
    OBSERVATION_SEGMENTS,
    PERSONAL_CARD_IDS,
    SCOUTS_ITEM_IDS,
    TECH_SEGMENTS,
    ObservationSegment,
)
from dune_imperium.config import BaseGame
from dune_imperium.content.arrakeen_scouts import (
    EVENTS,
    MISSIONS,
    auctions_of_base_game,
    events_of_base_game,
    missions_of_base_game,
    sales_of_base_game,
    subcommittees_of_base_game,
)
from dune_imperium.content.arrakeen_scouts.types import UPRISING_POOLS
from dune_imperium.content.bloodlines.sardaukar import COMMANDER_SETUP_SPACE_IDS
from dune_imperium.content.imperium.imperium import IMPERIUM_BASE_CARDS
from dune_imperium.content.imperium.intrigue import IMPERIUM_INTRIGUE_CARDS
from dune_imperium.content.rise_of_ix.board import IX_OBSERVATION_POSTS
from dune_imperium.content.rise_of_ix.contracts import IX_CONTRACTS
from dune_imperium.content.rise_of_ix.imperium import IX_IMPERIUM_CARDS
from dune_imperium.content.rise_of_ix.intrigue import IX_INTRIGUE_CARDS
from dune_imperium.content.rise_of_ix.tech import IX_TECH_IDS

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
# The segments v40 appended (stage P7f-2).
V40_NEW_SEGMENTS = frozenset(
    {"private_starting_contracts", "private_starting_contract_pick"}
)
# The segment v41 appended (stage P8c): the Factions the observer's own secret
# picks named (the original game's Covert Operation).
V41_NEW_SEGMENTS = frozenset({"private_scouts_secret_faction"})
# The segment v42 appended (OQ-166): the garrison Sardaukar Commanders parked
# by Send for Aid and Genetic Research (mission x relative seat).
V42_NEW_SEGMENTS = frozenset({"scouts_parked_commanders"})
# The segments v43 widened at their end: each relative seat's set-aside
# Imperium cards, from v42's two slots.
V43_SET_ASIDE_SEGMENTS = frozenset(
    f"seat{seat}_imperium_set_aside" for seat in range(4)
)
V42_SET_ASIDE_SLOTS = 2
NEW_SEGMENTS = frozenset(
    {
        *V42_NEW_SEGMENTS,
        *V41_NEW_SEGMENTS,
        *V40_NEW_SEGMENTS,
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
_V39_TECH = len(IX_TECH_IDS)
_V40_COMMANDER_SPACES = len(COMMANDER_SPACE_IDS) - len(COMMANDER_SETUP_SPACE_IDS)
# The segments with a column per observation post, which v40 (stage P7f)
# grew by Rise of Ix's two posts on Uprising's board [Main p. 18].
POST_SEGMENTS = frozenset(
    {*(f"seat{seat}_spy_posts" for seat in range(4)), "private_effect_pick_post"}
)
_V40_POST = len(IX_OBSERVATION_POSTS)
_V40_CONTRACTS = len(IX_CONTRACTS)
# Arrakeen Scouts with Rise of Ix's three missions (stage P7f-2), at the end
# of the Scouts item and mission segments.
_V40_MISSIONS = sum(1 for mission in MISSIONS if mission.rise_of_ix_only)
_V40_SCOUTS = {
    "scouts_items": _V40_MISSIONS,
    "scouts_parked": _V40_MISSIONS * 4,
    "scouts_goods": _V40_MISSIONS * 5,
}
# v41 (stage P8): the original game's own Scouts items, the ones no Uprising
# pool holds, follow every older item in ``scouts_items`` (the only segment
# with a column per item). The mission segments (``scouts_parked`` x 4 seats,
# ``scouts_goods`` x 5) grow by the original game's own missions, the ones
# appended to ``MISSIONS`` after Rise of Ix's (stage P8b-2); the secret-event
# segment grows with Covert Operation's original wording in stage P8c-1, and
# stage P8c-2's last five events and Fremen Mercenaries are six more items at
# the end of ``scouts_items`` (and of no other segment).
V41_SCOUTS_ITEMS = len(SCOUTS_ITEM_IDS) - sum(
    len(items(BaseGame.UPRISING))
    for items in (
        subcommittees_of_base_game,
        missions_of_base_game,
        events_of_base_game,
        auctions_of_base_game,
        sales_of_base_game,
    )
)
V41_MISSIONS = sum(
    1
    for mission in MISSIONS
    if not any(pool in UPRISING_POOLS for pool in mission.pools)
)
# The original game's own secret event (stage P8c): its four lines at the end
# of ``scouts_secret_own``.
V41_SECRET_EVENTS = sum(
    1
    for event in EVENTS
    if event.secret_choices
    and not any(pool in UPRISING_POOLS for pool in event.pools)
)
_V41_SCOUTS = {
    "scouts_items": V41_SCOUTS_ITEMS,
    "scouts_parked": V41_MISSIONS * 4,
    "scouts_goods": V41_MISSIONS * 5,
    "scouts_secret_own": V41_SECRET_EVENTS * 4,
}
# Observation v38's width and segment count; v39's width.
V38_SIZE = 8_265
V38_SEGMENTS = 137
V39_SIZE = 10_301


def growth_in_v43(segment: ObservationSegment) -> int:
    """How many of ``segment``'s last columns v43 added: the set-aside slots
    after v42's two in each relative seat's ``imperium_set_aside``."""

    if segment.name in V43_SET_ASIDE_SEGMENTS:
        return segment.length - V42_SET_ASIDE_SLOTS
    return 0


def growth_in_v42(segment: ObservationSegment) -> int:
    """How many of ``segment``'s last columns v42 added: all of the one new
    segment's (the parked Sardaukar Commanders of Arrakeen Scouts' Send for
    Aid and Genetic Research, OQ-166), none of any older segment's."""

    return segment.length if segment.name in V42_NEW_SEGMENTS else 0


def growth_in_v41(segment: ObservationSegment) -> int:
    """How many of ``segment``'s last columns v41 added (all of a new
    segment's): the original game's Scouts items at the end of
    ``scouts_items`` (stage P8), its missions at the end of the parked and
    goods segments (stage P8b-2), its Covert Operation's lines at the end of
    ``scouts_secret_own`` and the new segment of the observer's own picks'
    Factions (stage P8c)."""

    if segment.name in V41_NEW_SEGMENTS:
        return segment.length
    return _V41_SCOUTS.get(segment.name, 0)


def growth_in_v40(segment: ObservationSegment) -> int:
    """How many of ``segment``'s last columns v40 added (all of a new
    segment's): the original board's and Rise of Ix's Commander setup spaces
    (stage P7c), Rise of Ix's two observation posts on Uprising's board
    (stage P7f) and its ten Contracts (stage P7f-2)."""

    if segment.name in V40_NEW_SEGMENTS:
        return segment.length
    if segment.name == "commander_spaces":
        return _V40_COMMANDER_SPACES
    if segment.name in CONTRACT_SEGMENTS:
        return _V40_CONTRACTS
    if segment.name in _V40_SCOUTS:
        return _V40_SCOUTS[segment.name]
    return _V40_POST if segment.name in POST_SEGMENTS else 0


def growth_in_v39(segment: ObservationSegment) -> int:
    """How many of ``segment``'s last columns v39 added (all of a new
    segment's), read off today's segment (v40's growth taken off first)."""

    if segment.name in V39_NEW_SEGMENTS:
        return segment.length
    if segment.length == len(PERSONAL_CARD_IDS):
        return _V39_PERSONAL
    if segment.length == len(INTRIGUE_IDS):
        return _V39_INTRIGUE
    if segment.name in TECH_SEGMENTS:
        return _V39_TECH
    return int(segment.name == "global_scalars")


def growth_after_v38(segment: ObservationSegment) -> int:
    """How many of ``segment``'s last columns v39 to v43 added."""

    return (
        growth_in_v39(segment)
        + growth_in_v40(segment)
        + growth_in_v41(segment)
        + growth_in_v42(segment)
        + growth_in_v43(segment)
    )


def growth_since_v34(segment: ObservationSegment) -> int:
    """How many of ``segment``'s last columns v35 to v43 added (all of a
    new segment's)."""

    if segment.name in V43_SET_ASIDE_SEGMENTS:
        return growth_in_v43(segment)
    if segment.name in (
        "commander_spaces",
        *CONTRACT_SEGMENTS,
        *_V40_SCOUTS,
        *_V41_SCOUTS,
    ):
        return growth_in_v40(segment) + growth_in_v41(segment)
    if segment.name in NEW_SEGMENTS:
        return segment.length
    if segment.name in POST_SEGMENTS:
        return _V40_POST
    if segment.length == len(PERSONAL_CARD_IDS):
        return 3 + _V37_PERSONAL + _V39_PERSONAL
    if segment.length == len(INTRIGUE_IDS):
        return _V37_INTRIGUE + _V39_INTRIGUE
    if segment.name in TECH_SEGMENTS:
        return _V39_TECH
    if segment.name.endswith(("_control", "_agent_locations")):
        return 1
    return {"reserve_stacks": 3, "maker_bonus_spice": 2, "global_scalars": 1}.get(
        segment.name, 0
    )


GROWN_COLUMNS = sum(growth_since_v34(segment) for segment in OBSERVATION_SEGMENTS)


def v42_layout() -> list[tuple[str, int, int]]:
    """Observation v42's layout as (segment, offset, length), rebuilt from
    today's: every segment by name, each seat's ``imperium_set_aside``
    without v43's slots."""

    layout: list[tuple[str, int, int]] = []
    offset = 0
    for segment in OBSERVATION_SEGMENTS:
        length = segment.length - growth_in_v43(segment)
        layout.append((segment.name, offset, length))
        offset += length
    return layout


def v41_layout() -> list[tuple[str, int, int]]:
    """Observation v41's layout as (segment, offset, length), rebuilt from
    today's: every segment by name, without v42's one new segment (v42 grew
    no older segment) and v43's set-aside slots."""

    layout: list[tuple[str, int, int]] = []
    offset = 0
    for segment in OBSERVATION_SEGMENTS:
        if segment.name in V42_NEW_SEGMENTS:
            continue
        length = segment.length - growth_in_v43(segment)
        layout.append((segment.name, offset, length))
        offset += length
    return layout


def v40_layout() -> list[tuple[str, int, int]]:
    """Observation v40's layout as (segment, offset, length), rebuilt from
    today's: every segment by name, without v41's and v43's columns and v41's
    and v42's new segments."""

    layout: list[tuple[str, int, int]] = []
    offset = 0
    for segment in OBSERVATION_SEGMENTS:
        if segment.name in V41_NEW_SEGMENTS | V42_NEW_SEGMENTS:
            continue
        length = (
            segment.length - growth_in_v41(segment) - growth_in_v43(segment)
        )
        layout.append((segment.name, offset, length))
        offset += length
    return layout


def v39_layout() -> list[tuple[str, int, int]]:
    """Observation v39's layout as (segment, offset, length), rebuilt from
    today's: every segment by name, without v40's, v41's and v43's columns
    and the segments v40, v41 and v42 added."""

    layout: list[tuple[str, int, int]] = []
    offset = 0
    for segment in OBSERVATION_SEGMENTS:
        if segment.name in V40_NEW_SEGMENTS | V41_NEW_SEGMENTS | V42_NEW_SEGMENTS:
            continue
        length = (
            segment.length
            - growth_in_v40(segment)
            - growth_in_v41(segment)
            - growth_in_v43(segment)
        )
        layout.append((segment.name, offset, length))
        offset += length
    return layout


def v38_layout() -> list[tuple[str, int, int]]:
    """Observation v38's layout as (segment, offset, length), rebuilt from
    today's: every v38 segment by name, without v39's, v40's, v41's and
    v43's columns and the segments v39 to v42 added."""

    layout: list[tuple[str, int, int]] = []
    offset = 0
    for segment in OBSERVATION_SEGMENTS:
        if segment.name in (
            V39_NEW_SEGMENTS
            | V40_NEW_SEGMENTS
            | V41_NEW_SEGMENTS
            | V42_NEW_SEGMENTS
        ):
            continue
        length = segment.length - growth_after_v38(segment)
        layout.append((segment.name, offset, length))
        offset += length
    return layout


def v38_columns(vector: Sequence[int]) -> list[int]:
    """The v38 vector inside today's: each v38 segment's columns, in the
    v38 order (``v38_layout``)."""

    older: list[int] = []
    for segment in OBSERVATION_SEGMENTS:
        if segment.name in (
            V39_NEW_SEGMENTS
            | V40_NEW_SEGMENTS
            | V41_NEW_SEGMENTS
            | V42_NEW_SEGMENTS
        ):
            continue
        length = segment.length - growth_after_v38(segment)
        older.extend(vector[segment.offset : segment.offset + length])
    return older
