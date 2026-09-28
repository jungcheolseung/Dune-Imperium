"""Identity ("slot") features of observation v20 for the ``mlp_slots`` network.

The MLP trunk reads every observation column through ``log1p``, which is
right for counts and resources but wrong for the columns that hold an
identity as ``index + 1`` (the Imperium Row, the current Conflict, the
decision kind, Agent locations, each seat's Leader, ...): as a magnitude,
card 40 is "twice" card 20 and the trunk cannot tell which card is there.
This module names those columns and maps each (column, value) pair to one
trainable embedding row, so ``MlpSlotsNetwork`` can add a one-hot path for
them next to the unchanged ``log1p`` path.

A field is one group of columns sharing a row set:

- a *value* field maps each listed observation value to its row (a shared
  multi-hot when it has several columns, e.g. the five Imperium Row slots);
- a *bitmask* field gives each set bit its own row (the granted Agent
  icons).

Every value the spec does not list -- the declared pad values such as an
empty slot's 0, and anything else -- maps to the untrained ``PAD_ROW``.
Values are clamped to ``0..VALUE_RANGE - 1`` before the lookup.

``SLOT_KEYS`` names every trainable row; a checkpoint stores it, so a file
written under another table is refused rather than read with its rows
silently meaning something else. Change the table only together with
``SLOT_VERSION`` and the golden digest in the tests.

Column positions come from the encoder's segment table; the positions
*inside* the global and seat scalar segments are the order in which
``encode_player_view`` writes them (the encoder exports no names for
those). The tests check each of those positions, and the full set of
active rows, against keys decoded independently from real views.
"""

import hashlib
from dataclasses import dataclass, replace
from functools import cache
from typing import Final

import torch

from dune_imperium.adapters.observation_encoding import (
    _AGENT_ICONS,
    _FRAME_KINDS,
    _PHASES,
    CONFLICT_IDS,
    FEYD_TRACK_IDS,
    INTRIGUE_IDS,
    LEADER_IDS,
    PERSONAL_CARD_IDS,
    RESEARCH_SPACE_IDS,
    SPACE_IDS,
    segment_slice,
)
from dune_imperium.content.bloodlines.tech import TECH_IDS
from dune_imperium.content.immortality.board import TLEILAXU_TRACK_END
from dune_imperium.content.immortality.tleilaxu import TLEILAXU_CARDS_BY_ID
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.intrigue import INTRIGUE_CARDS_BY_ID
from dune_imperium.core.state import GamePhase
from dune_imperium.rules.tactics import TACTICS_TRACK_END, TACTICS_TRACK_START

SLOT_VERSION: Final = 1
# The observation the table was written against. A new observation version
# must revisit the table (and bump SLOT_VERSION if any row changes); a test
# fails until it does.
# v22 (Arrakeen Scouts) added no identity column; its new frame kind added
# the row ``decision_kind:scouts_draw``, and checkpoints re-link their rows
# by key (``training.checkpoint``).
SLOT_OBSERVATION_VERSION: Final = 22
VALUE_RANGE: Final = 256

# Positions inside ``global_scalars`` (``encode_player_view``).
_GLOBAL_PHASE: Final = 1
_GLOBAL_FIRST_PLAYER: Final = 2
_GLOBAL_DECISION_KIND: Final = 4
_GLOBAL_TURN_OWNER: Final = 6
# Positions inside ``seat{k}_scalars`` (``_write_seat``).
_SEAT_LEADER: Final = 20
_SEAT_FEYD: Final = 22
_SEAT_AGENT_ICONS: Final = 34
_SEAT_TACTICS: Final = 37
_SEAT_RESEARCH: Final = 45
_SEAT_TLEILAXU: Final = 46

_SEATS: Final = 4
# The phase the network sees most (every Agent and Reveal turn) is the
# reference level: it gets no row, like the dropped level of a dummy code.
_REFERENCE_PHASE: Final = GamePhase.PLAYER_TURNS


@dataclass(frozen=True, slots=True)
class SlotField:
    """One group of observation columns sharing a set of embedding rows.

    ``values[i]`` selects ``keys[i]``: an observation value for a value
    field, a bit number for a bitmask field. ``pad_values`` are the values
    that are declared to carry nothing (an empty slot, a track's start);
    they, and only they, may map to the pad row in a real game.
    """

    name: str
    segments: tuple[str, ...]
    columns: tuple[int, ...]
    keys: tuple[str, ...]
    values: tuple[int, ...]
    bitmask: bool = False
    pad_values: tuple[int, ...] = (0,)


def _columns(segment: str) -> tuple[int, ...]:
    part = segment_slice(segment)
    return tuple(range(part.start, part.stop))


def _scalar(segment: str, position: int) -> tuple[int, ...]:
    return (segment_slice(segment).start + position,)


def _sub_universe(
    universe: tuple[str, ...], members: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[int, ...]]:
    """The members' ids and their ``index + 1`` encodings in ``universe``."""

    index = {identity: position for position, identity in enumerate(universe)}
    return members, tuple(index[identity] + 1 for identity in members)


def _identity(
    name: str,
    segment: str,
    columns: tuple[int, ...],
    universe: tuple[str, ...],
    members: tuple[str, ...] | None = None,
    *,
    prefix: str | None = None,
) -> SlotField:
    """A value field over (a sub-universe of) an ``index + 1`` identity slot."""

    ids, values = _sub_universe(universe, universe if members is None else members)
    label = prefix if prefix is not None else name
    return SlotField(
        name=name,
        segments=(segment,),
        columns=columns,
        keys=tuple(f"{label}:{identity}" for identity in ids),
        values=values,
    )


def _relative_seat(name: str, segment: str, columns: tuple[int, ...]) -> SlotField:
    """A value field over an egocentric seat reference (1..4, 0 = nobody)."""

    return SlotField(
        name=name,
        segments=(segment,),
        columns=columns,
        keys=tuple(f"{name}:seat{seat}" for seat in range(_SEATS)),
        values=tuple(seat + 1 for seat in range(_SEATS)),
    )


def _build_fields() -> tuple[SlotField, ...]:
    imperium = tuple(IMPERIUM_CARDS_BY_ID)
    tleilaxu = tuple(TLEILAXU_CARDS_BY_ID)
    navigation = tuple(
        card_id for card_id, entry in INTRIGUE_CARDS_BY_ID.items() if entry.navigation
    )
    phase_levels = tuple(
        (index, phase)
        for index, phase in enumerate(_PHASES)
        if phase != _REFERENCE_PHASE
    )
    fields: list[SlotField] = [
        SlotField(
            name="phase",
            segments=("global_scalars",),
            columns=_scalar("global_scalars", _GLOBAL_PHASE),
            keys=tuple(f"phase:{phase.value}" for _, phase in phase_levels),
            values=tuple(index for index, _ in phase_levels),
            pad_values=(_PHASES.index(_REFERENCE_PHASE),),
        ),
        _relative_seat(
            "first_player",
            "global_scalars",
            _scalar("global_scalars", _GLOBAL_FIRST_PLAYER),
        ),
        _relative_seat(
            "turn_owner",
            "global_scalars",
            _scalar("global_scalars", _GLOBAL_TURN_OWNER),
        ),
        _identity(
            "decision_kind",
            "global_scalars",
            _scalar("global_scalars", _GLOBAL_DECISION_KIND),
            _FRAME_KINDS,
        ),
        _identity(
            "conflict",
            "current_conflict",
            _columns("current_conflict"),
            CONFLICT_IDS,
        ),
        _identity(
            "imperium_row",
            "imperium_row",
            _columns("imperium_row"),
            PERSONAL_CARD_IDS,
            imperium,
        ),
    ]
    for slot, column in enumerate(_columns("reveal_order")):
        fields.append(_relative_seat(f"reveal_order{slot}", "reveal_order", (column,)))
    fields.extend(
        (
            _identity(
                "tech_face_up", "tech_face_up", _columns("tech_face_up"), TECH_IDS
            ),
            _identity(
                "tleilaxu_row",
                "tleilaxu_row",
                _columns("tleilaxu_row"),
                PERSONAL_CARD_IDS,
                tleilaxu,
            ),
        )
    )
    for slot, column in enumerate(_columns("private_navigation_slots")):
        fields.append(
            _identity(
                f"navigation{slot}",
                "private_navigation_slots",
                (column,),
                INTRIGUE_IDS,
                navigation,
            )
        )
    fields.append(
        _identity(
            "secret_project",
            "private_secret_project",
            _columns("private_secret_project"),
            TECH_IDS,
        )
    )
    # Every seat's Agent locations summed into one shared multi-hot: the
    # same information as the seat blocks below, re-parametrised so the rows
    # learn from four times the data.
    occupancy = tuple(
        column
        for seat in range(_SEATS)
        for column in _columns(f"seat{seat}_agent_locations")
    )
    fields.append(
        replace(
            _identity("occupancy", "seat0_agent_locations", occupancy, SPACE_IDS),
            segments=tuple(f"seat{seat}_agent_locations" for seat in range(_SEATS)),
        )
    )
    for seat in range(_SEATS):
        fields.extend(_seat_fields(seat, imperium))
    return tuple(fields)


def _seat_fields(seat: int, imperium: tuple[str, ...]) -> tuple[SlotField, ...]:
    scalars = f"seat{seat}_scalars"
    prefix = f"seat{seat}"
    feyd_nodes = FEYD_TRACK_IDS[1:]
    tactics = tuple(range(TACTICS_TRACK_START, TACTICS_TRACK_END))
    tleilaxu_spaces = tuple(range(1, TLEILAXU_TRACK_END + 1))
    return (
        _identity(
            f"{prefix}_leader",
            scalars,
            _scalar(scalars, _SEAT_LEADER),
            LEADER_IDS,
            prefix=f"{prefix}:leader",
        ),
        # The Feyd track stores the plain index; its start (0) is every
        # non-Feyd seat's value and is the pad.
        SlotField(
            name=f"{prefix}_feyd",
            segments=(scalars,),
            columns=_scalar(scalars, _SEAT_FEYD),
            keys=tuple(f"{prefix}:feyd:{node}" for node in feyd_nodes),
            values=tuple(range(1, len(FEYD_TRACK_IDS))),
        ),
        _identity(
            f"{prefix}_research",
            scalars,
            _scalar(scalars, _SEAT_RESEARCH),
            RESEARCH_SPACE_IDS,
            prefix=f"{prefix}:research",
        ),
        SlotField(
            name=f"{prefix}_agent_icons",
            segments=(scalars,),
            columns=_scalar(scalars, _SEAT_AGENT_ICONS),
            keys=tuple(f"{prefix}:agent_icon:{icon}" for icon in _AGENT_ICONS),
            values=tuple(range(len(_AGENT_ICONS))),
            bitmask=True,
        ),
        # Chani's Tactics token lives on TACTICS_TRACK_START..END-1 (it
        # resets on reaching the end); 0 is every other seat.
        SlotField(
            name=f"{prefix}_tactics",
            segments=(scalars,),
            columns=_scalar(scalars, _SEAT_TACTICS),
            keys=tuple(f"{prefix}:tactics:{space}" for space in tactics),
            values=tactics,
        ),
        SlotField(
            name=f"{prefix}_tleilaxu",
            segments=(scalars,),
            columns=_scalar(scalars, _SEAT_TLEILAXU),
            keys=tuple(f"{prefix}:tleilaxu:{space}" for space in tleilaxu_spaces),
            values=tleilaxu_spaces,
        ),
        _identity(
            f"{prefix}_agent_locations",
            f"{prefix}_agent_locations",
            _columns(f"{prefix}_agent_locations"),
            SPACE_IDS,
            prefix=f"{prefix}:agent_location",
        ),
        _identity(
            f"{prefix}_set_aside",
            f"{prefix}_imperium_set_aside",
            _columns(f"{prefix}_imperium_set_aside"),
            PERSONAL_CARD_IDS,
            imperium,
            prefix=f"{prefix}:set_aside",
        ),
    )


SLOT_FIELDS: Final = _build_fields()
SLOT_KEYS: Final = tuple(key for field in SLOT_FIELDS for key in field.keys)
PAD_ROW: Final = len(SLOT_KEYS)

if len(set(SLOT_KEYS)) != len(SLOT_KEYS):
    raise RuntimeError("slot keys must be unique")
for _field in SLOT_FIELDS:
    if len(_field.keys) != len(_field.values) or not _field.keys:
        raise RuntimeError(f"slot field {_field.name} has mismatched keys and values")
    _limit = VALUE_RANGE.bit_length() - 1 if _field.bitmask else VALUE_RANGE
    if any(not 0 <= value < _limit for value in _field.values):
        raise RuntimeError(f"slot field {_field.name} has an out-of-range value")
    if not _field.bitmask and set(_field.values) & set(_field.pad_values):
        raise RuntimeError(f"slot field {_field.name} lists a pad value as a row")


def slot_keys_digest() -> str:
    """SHA-256 of the row names in order (the tests pin it)."""

    return hashlib.sha256("\n".join(SLOT_KEYS).encode()).hexdigest()


@cache
def _lookup_lists() -> tuple[tuple[int, ...], tuple[int, ...]]:
    columns: list[int] = []
    table: list[int] = []
    base = 0
    for field in SLOT_FIELDS:
        for column in field.columns:
            if field.bitmask:
                for offset, bit in enumerate(field.values):
                    row = [PAD_ROW] * VALUE_RANGE
                    for value in range(VALUE_RANGE):
                        if (value >> bit) & 1:
                            row[value] = base + offset
                    columns.append(column)
                    table.extend(row)
            else:
                row = [PAD_ROW] * VALUE_RANGE
                for offset, value in enumerate(field.values):
                    row[value] = base + offset
                columns.append(column)
                table.extend(row)
        base += len(field.keys)
    return tuple(columns), tuple(table)


def lookup_tables() -> tuple[torch.Tensor, torch.Tensor]:
    """The gathered columns ``[C]`` and the flat row table ``[C * VALUE_RANGE]``.

    Lookup ``j`` reads observation column ``columns[j]``; its clamped value
    ``v`` selects row ``table[j * VALUE_RANGE + v]`` (``PAD_ROW`` when the
    value carries nothing). A column appears once per lookup that reads it:
    the occupancy field re-reads the seat Agent-location columns and a
    bitmask field reads its column once per bit.
    """

    columns, table = _lookup_lists()
    return (
        torch.tensor(columns, dtype=torch.long),
        torch.tensor(table, dtype=torch.long),
    )


__all__ = [
    "PAD_ROW",
    "SLOT_FIELDS",
    "SLOT_KEYS",
    "SLOT_OBSERVATION_VERSION",
    "SLOT_VERSION",
    "VALUE_RANGE",
    "SlotField",
    "lookup_tables",
    "slot_keys_digest",
]
