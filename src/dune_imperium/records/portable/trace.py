"""Per-field state digests, the per-step trace codec, and per-step index keys.

Standard library only (see the package docstring): an old engine's corpus
driver loads this file by path, and the current engine imports it as
``dune_imperium.records.portable.trace``. Both must compute the same bytes.

**Fingerprint.** A state is cut into fields: every top-level ``GameState``
field except ``SKIPPED_FIELDS``, with ``players`` split into one field per
seat per ``PlayerState`` field (``players[2].hand``); 398 fields at codec
141. Each field's digest is the first ``DIGEST_SIZE`` bytes of blake2b over
the canonical JSON of its value (``canonical``). A field the state lacks
digests as ``ABSENT``. The ``UNORDERED`` player zones are hashed as sorted
multisets; the deck stays ordered.

**Trace.** One record's trace is the digest vector of the reset state, then
for each recorded step the fields whose digest changed from the state
before that step to the state after it. A trace file (``.trace.bin``) is::

    b"DICT1", u16 F                       # field count
    per record:
        u32 payload length
        u32 step count, F x 4 bytes       # the reset vector
        per step: varint n, n x (u16 field index, 4-byte digest)

(little-endian). The state before recorded step ``i`` is the reset vector
plus deltas ``0..i-1``; the final state is the vector after the last.

**Index keys.** ``step_keys`` names what one step did as flat
``"dimension:key"`` strings, and ``KeyIndex`` gathers them into a record's
index row: ``key -> [count, first_step, positions]``.
"""

import dataclasses
import enum
import hashlib
import json
import re
import struct
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from typing import Any, Final

# ``GameState`` fields left out of the fingerprint: the decision stack is the
# engine's control flow (a bridge changes it by design), and the event log
# and revision grow with every step.
SKIPPED_FIELDS: Final = frozenset({"decision_stack", "event_log", "revision"})
# ``PlayerState`` zones hashed as sorted multisets: an engine may hand a seat
# the same cards in another order (OQ-106 owed draws). A test checks every
# name against ``PlayerState``, so a misspelt zone cannot be skipped silently.
UNORDERED: Final = ("discard_pile", "hand", "hand_public", "in_play", "intrigue_cards")
DIGEST_SIZE: Final = 4
ABSENT: Final = bytes(DIGEST_SIZE)
# The canonical value of a field that a class schema names but the object
# lacks (an engine that removed or renamed a nested field).
ABSENT_VALUE: Final = "\x00absent"
TRACE_MAGIC: Final = b"DICT1"

type Schema = Mapping[str, Sequence[str]]
type Digests = tuple[bytes, ...]

_MISSING: Final = object()
_FIELD: Final = re.compile(r"^players\[(?P<seat>\d+)\]\.(?P<attr>.+)$")


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def canonical(
    value: Any,
    schema: Schema | None = None,
    seen: dict[str, list[str]] | None = None,
) -> Any:
    """``value`` as plain JSON data, independent of object identity.

    A dataclass becomes ``{field: value}``, restricted to
    ``schema[qualname]`` when ``schema`` names its class (a field the
    object lacks becomes ``ABSENT_VALUE``); an Enum its ``value``; a tuple
    or list a list; a set a sorted list; a dict one with string keys.
    ``seen`` collects every dataclass met, as ``{qualname: [field names]}``.
    """

    if value is _MISSING:
        return ABSENT_VALUE
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        qualname = type(value).__qualname__
        names = [field.name for field in dataclasses.fields(value)]
        if seen is not None:
            seen.setdefault(qualname, names)
        if schema is not None and qualname in schema:
            names = list(schema[qualname])
        return {
            name: canonical(getattr(value, name, _MISSING), schema, seen)
            for name in names
        }
    if isinstance(value, enum.Enum):
        return canonical(value.value, schema, seen)
    if isinstance(value, tuple | list):
        return [canonical(item, schema, seen) for item in value]
    if isinstance(value, set | frozenset):
        return sorted((canonical(item, schema, seen) for item in value), key=_json)
    if isinstance(value, dict):
        return {str(key): canonical(item, schema, seen) for key, item in value.items()}
    return value


def field_names(state: Any) -> tuple[str, ...]:
    """The fingerprint's field names for ``state``'s engine."""

    names: list[str] = []
    for field in dataclasses.fields(state):
        if field.name in SKIPPED_FIELDS:
            continue
        if field.name == "players":
            for seat, player in enumerate(state.players):
                names.extend(
                    f"players[{seat}].{player_field.name}"
                    for player_field in dataclasses.fields(player)
                )
        else:
            names.append(field.name)
    return tuple(names)


class Fingerprint:
    """Per-field digests of a state (see the module docstring).

    ``names`` fixes the field list (a corpus's ``fingerprint_fields``; by
    default the first state's own), ``schema`` restricts nested dataclasses
    to a corpus's ``class_schema``, so fields a newer engine adds are left
    out. ``class_schema`` collects every dataclass met. An identity cache
    keeps each digested object, so an object id is never reused while
    cached, and only replaced objects are digested again: make one
    ``Fingerprint`` per game.
    """

    def __init__(
        self,
        names: Sequence[str] | None = None,
        schema: Schema | None = None,
        unordered: Iterable[str] = UNORDERED,
    ) -> None:
        self.names: tuple[str, ...] | None = None if names is None else tuple(names)
        self.schema = schema
        self.unordered = frozenset(unordered)
        self.class_schema: dict[str, list[str]] = {}
        self._paths: tuple[tuple[int | None, str], ...] | None = None
        self._cache: dict[tuple[str, bool, int], tuple[object, bytes]] = {}

    def __call__(self, state: Any) -> Digests:
        if self.names is None:
            self.names = field_names(state)
        players = getattr(state, "players", ())
        if self._paths is None:
            self._paths = tuple(_path(name) for name in self.names)
            self._note_class(state)
            if players:
                self._note_class(players[0])
        digests: list[bytes] = []
        for seat, attr in self._paths:
            if seat is None:
                holder = state
            else:
                holder = players[seat] if seat < len(players) else _MISSING
            value = _MISSING if holder is _MISSING else getattr(holder, attr, _MISSING)
            if value is _MISSING:
                digests.append(ABSENT)
            else:
                unordered = seat is not None and attr in self.unordered
                digests.append(self.digest(attr, value, unordered=unordered))
        return tuple(digests)

    def digest(self, attr: str, value: object, *, unordered: bool = False) -> bytes:
        """The digest of one field value."""

        key = (attr, unordered, id(value))
        hit = self._cache.get(key)
        if hit is not None and hit[0] is value:
            return hit[1]
        form = canonical(value, self.schema, self.class_schema)
        if unordered and isinstance(form, list):
            form = sorted(form, key=_json)
        digest = hashlib.blake2b(_json(form).encode(), digest_size=DIGEST_SIZE).digest()
        self._cache[key] = (value, digest)
        return digest

    def _note_class(self, value: object) -> None:
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            self.class_schema.setdefault(
                type(value).__qualname__,
                [field.name for field in dataclasses.fields(value)],
            )


def _path(name: str) -> tuple[int | None, str]:
    match = _FIELD.match(name)
    if match is None:
        return None, name
    return int(match.group("seat")), match.group("attr")


# --- the trace codec ---------------------------------------------------------


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    value = shift = 0
    while True:
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7


def trace_header(field_count: int) -> bytes:
    """The header of a trace file of ``field_count`` fields."""

    return TRACE_MAGIC + struct.pack("<H", field_count)


class TraceWriter:
    """One record's trace, built step by step."""

    def __init__(self, reset: Sequence[bytes]) -> None:
        self._previous = tuple(reset)
        self._body = bytearray(b"".join(self._previous))
        self.steps = 0

    @property
    def field_count(self) -> int:
        return len(self._previous)

    def step(self, after: Sequence[bytes]) -> int:
        """Add the step that ends in ``after``; return how many fields changed."""

        if len(after) != len(self._previous):
            raise ValueError("a step's digest vector changed length")
        changed = [
            index
            for index, (old, new) in enumerate(zip(self._previous, after, strict=True))
            if old != new
        ]
        self._body += _varint(len(changed))
        for index in changed:
            self._body += struct.pack("<H", index) + after[index]
        self._previous = tuple(after)
        self.steps += 1
        return len(changed)

    def to_bytes(self) -> bytes:
        """The record's length-prefixed trace."""

        payload = struct.pack("<I", self.steps) + bytes(self._body)
        return struct.pack("<I", len(payload)) + payload


class TraceReader:
    """One record's trace, read back."""

    def __init__(self, payload: bytes, field_count: int) -> None:
        self.field_count = field_count
        (self.steps,) = struct.unpack_from("<I", payload, 0)
        offset = 4
        end = offset + field_count * DIGEST_SIZE
        self.reset: Digests = tuple(
            bytes(payload[start : start + DIGEST_SIZE])
            for start in range(offset, end, DIGEST_SIZE)
        )
        offset = end
        deltas: list[tuple[tuple[int, bytes], ...]] = []
        for _ in range(self.steps):
            count, offset = _read_varint(payload, offset)
            delta = []
            for _ in range(count):
                (index,) = struct.unpack_from("<H", payload, offset)
                if index >= field_count:
                    raise ValueError(f"trace field index {index} out of range")
                start = offset + 2
                delta.append((index, bytes(payload[start : start + DIGEST_SIZE])))
                offset = start + DIGEST_SIZE
            deltas.append(tuple(delta))
        if offset != len(payload):
            raise ValueError("a trace record has trailing bytes")
        self._deltas = tuple(deltas)
        self._cursor = 0
        self._vector = list(self.reset)

    def delta(self, index: int) -> tuple[tuple[int, bytes], ...]:
        """The fields recorded step ``index`` changed, with their new digests."""

        return self._deltas[index]

    def before(self, index: int) -> Digests:
        """The digests of the state before recorded step ``index``.

        ``before(steps)`` is the final state. Reading forward is cheap.
        """

        if not 0 <= index <= self.steps:
            raise IndexError(f"step {index} is outside 0..{self.steps}")
        if index < self._cursor:
            self._cursor, self._vector = 0, list(self.reset)
        while self._cursor < index:
            for field, digest in self._deltas[self._cursor]:
                self._vector[field] = digest
            self._cursor += 1
        return tuple(self._vector)

    def final(self) -> Digests:
        """The digests of the final state."""

        return self.before(self.steps)

    def vectors(self) -> Iterator[Digests]:
        """``before(0)``, ..., ``before(steps)``."""

        for index in range(self.steps + 1):
            yield self.before(index)


def trace_payloads(blob: bytes) -> tuple[int, list[bytes]]:
    """A trace file's field count and each record's payload, in order."""

    if blob[: len(TRACE_MAGIC)] != TRACE_MAGIC:
        raise ValueError("not a record-corpus trace file")
    offset = len(TRACE_MAGIC)
    (field_count,) = struct.unpack_from("<H", blob, offset)
    offset += 2
    payloads = []
    while offset < len(blob):
        (length,) = struct.unpack_from("<I", blob, offset)
        start = offset + 4
        offset = start + length
        if offset > len(blob):
            raise ValueError("a trace file ends inside a record")
        payloads.append(blob[start:offset])
    return field_count, payloads


def read_traces(blob: bytes) -> list[TraceReader]:
    """Every record's trace in a trace file."""

    field_count, payloads = trace_payloads(blob)
    return [TraceReader(payload, field_count) for payload in payloads]


# --- index keys --------------------------------------------------------------

# Positions are kept in full for these dimensions, and elsewhere only while a
# key's count is at most ``POSITION_LIMIT``.
FULL_POSITION_DIMENSIONS: Final = frozenset({"chance_values", "draws", "situations"})
POSITION_LIMIT: Final = 16
# Decision-frame context entries that qualify a ``frames:`` key.
FRAME_QUALIFIERS: Final = frozenset(
    {"card_id", "item_id", "mission_id", "source", "space_id"}
)
# Chance families whose drawn values are not indexed: every family whose
# last segment ends in ``SHUFFLE_SUFFIX`` (a whole pile's new order:
# ``discard_shuffle``, ``intrigue_shuffle``, ``contract_shuffle``, ...), and
# the ``SKIPPED_CHANCE_FAMILIES`` (the one fixed outcome of a pause).
SHUFFLE_SUFFIX: Final = "_shuffle"
SKIPPED_CHANCE_FAMILIES: Final = frozenset({"pause"})
# Event kinds whose ``card_id`` the census counts as a played card, as
# ``coverage.collect_game_coverage`` reads the event log: a card revealed as
# it arrives in its owner's Reveal turn, and a Graft partner.
PLAY_EVENT_KINDS: Final = frozenset({"card_grafted", "personal_card_late_revealed"})
# ``simulation.coverage``'s census dimensions, by where they come from: the
# recorded steps and the events each one reported (computed here, with
# positions; ``cards_played`` includes the ``PLAY_EVENT_KINDS`` plays) or the
# final event log (``collect_game_coverage(final_state, ())``, a count only).
CENSUS_STEP_DIMENSIONS: Final = (
    "action_ids",
    "agent_placements",
    "cards_played",
    "chance_kinds",
)
CENSUS_EVENT_DIMENSIONS: Final = (
    "cards_acquired",
    "conflicts",
    "contracts",
    "event_kinds",
    "intrigue_played",
    "leader_events",
    "skills_taken",
    "tech_acquired",
    "tleilaxu_acquired",
)
CENSUS_DIMENSIONS: Final = frozenset(CENSUS_STEP_DIMENSIONS + CENSUS_EVENT_DIMENSIONS)
# ``coverage._INTEGER_TOKEN``: chance families drop their integers.
_INTEGER_TOKEN: Final = re.compile(r":\d+")
_COPY_TOKEN: Final = re.compile(r"#\d+")


def chance_family(decision_id: str) -> str:
    """A chance decision id without its integers (the census's ``chance_kinds``)."""

    return _INTEGER_TOKEN.sub("", decision_id)


def indexes_values(family: str) -> bool:
    """Whether a chance ``family``'s drawn values become ``chance_values`` keys."""

    last = family.rpartition(":")[2]
    return not (last.endswith(SHUFFLE_SUFFIX) or last in SKIPPED_CHANCE_FAMILIES)


def _text(value: object) -> str:
    return str(value.value) if isinstance(value, enum.Enum) else str(value)


def _length(holder: object, name: str) -> int:
    value = getattr(holder, name, ())
    return len(value) if isinstance(value, tuple | list) else 0


def _seats(before: object, after: object) -> Iterator[tuple[Any, Any]]:
    yield from zip(
        getattr(before, "players", ()), getattr(after, "players", ()), strict=False
    )


def _held(seat: object) -> int:
    # ``hand_public`` names cards of ``hand``, so it is not counted again.
    return _length(seat, "hand") + _length(seat, "in_play")


def _piles(seat: object) -> int:
    return _length(seat, "deck") + _length(seat, "discard_pile")


def _drew_cards(before: object, after: object) -> bool:
    """Whether a seat drew an Imperium card during the step.

    A seat drew when its deck shrank, or when its hand and in-play cards
    together grew while its deck and discard pile together shrank. The
    first covers a plain draw, also in a step that discards or trashes a
    hand card as well; the second covers a draw that reshuffles the discard
    pile into the deck, and a card drawn in the seat's own Reveal turn,
    which goes from the deck straight to ``in_play``
    (``card_draw._draw_available``), with or without a reshuffle. Known
    false positives: a card that leaves the deck for anywhere else
    (discarded or trashed from its top, a Leader's setup), and a card
    returned from the discard pile to the hand.
    """

    for old, new in _seats(before, after):
        if _length(new, "deck") < _length(old, "deck"):
            return True
        if _held(new) > _held(old) and _piles(new) < _piles(old):
            return True
    return False


def _drew_intrigue(before: object, after: object) -> bool:
    if _length(after, "intrigue_deck") < _length(before, "intrigue_deck"):
        return True
    if _length(after, "intrigue_discard") >= _length(before, "intrigue_discard"):
        return False
    return any(
        _length(new, "intrigue_cards") > _length(old, "intrigue_cards")
        for old, new in _seats(before, after)
    )


def _forced_bucket(count: int) -> str:
    return str(count) if count < 3 else "3+"


def step_keys(
    before: Any,
    step: Any,
    transition: Any,
    legal: Sequence[Any],
    *,
    normalize: Callable[[str], str],
) -> list[str]:
    """The index keys of one recorded step, once per occurrence.

    ``before`` is the state before ``step``, ``transition`` the engine's
    result of applying it (``.state``, ``.events``), and ``legal`` the
    actions offered at a player decision (empty at a chance decision).
    ``normalize`` is the engine's ``coverage.normalize_instance_id``.

    - census step dimensions, as ``collect_game_coverage`` counts them:
      ``action_ids``, ``agent_placements`` (space:cost_option),
      ``cards_played`` and ``chance_kinds``;
    - ``frames:<kind>`` of the decision frame a player step answered, and
      ``frames:<kind>@<context>=<value>`` for its ``FRAME_QUALIFIERS``;
    - ``offered:<action_id>`` per distinct offered id, and
      ``forced:<kind>:<1|2|3+>`` by how many actions were offered;
    - ``draws:card@<owner>`` when a seat drew an Imperium card
      (``_drew_cards``); ``draws:intrigue@<owner>`` when the Intrigue deck
      shrank, or a seat's Intrigue cards grew while the Intrigue discard
      shrank. The owner is the step's ``action_id``, or
      ``chance:<family>`` for a chance step;
    - ``events:<kind>`` per event the step reported, and
      ``cards_played:<card>`` per ``PLAY_EVENT_KINDS`` event, as the census
      counts it from the event log;
    - ``chance_values:<family>=<value>`` per drawn value, for the families
      ``indexes_values`` keeps.
    """

    keys: list[str] = []
    after = getattr(transition, "state", None)
    action_id = getattr(step, "action_id", None)
    if isinstance(action_id, str):
        owner = action_id
        keys.append(f"action_ids:{action_id}")
        if action_id in ("agent_turn", "place_agent"):
            arguments = dict(getattr(step, "arguments", ()))
            space_id = arguments.get("space_id")
            card_id = arguments.get("card_id")
            if action_id == "place_agent":
                # Stage B1: the card was picked a step earlier and waits in
                # the turn frame.
                stack = getattr(before, "decision_stack", ())
                context = dict(getattr(stack[-1], "context", ())) if stack else {}
                card_id = context.get("agent_card_pick")
            if isinstance(space_id, str):
                option = arguments.get("cost_option", 0)
                if isinstance(option, bool) or not isinstance(option, int):
                    option = 0
                keys.append(f"agent_placements:{space_id}:{option}")
            if isinstance(card_id, str):
                keys.append(f"cards_played:{normalize(card_id)}")
        stack = getattr(before, "decision_stack", ())
        if stack:
            frame = stack[-1]
            kind = _text(getattr(frame, "kind", ""))
            keys.append(f"frames:{kind}")
            for name, value in getattr(frame, "context", ()):
                if name in FRAME_QUALIFIERS and isinstance(value, str):
                    qualifier = _INTEGER_TOKEN.sub("", normalize(value))
                    keys.append(f"frames:{kind}@{name}={qualifier}")
            if legal:
                offered = {getattr(action, "action_id", "") for action in legal}
                keys.extend(f"offered:{name}" for name in sorted(offered))
                keys.append(f"forced:{kind}:{_forced_bucket(len(legal))}")
    else:
        family = chance_family(str(getattr(step, "decision_id", "")))
        owner = f"chance:{family}"
        keys.append(f"chance_kinds:{family}")
        if indexes_values(family):
            for value in getattr(step, "values", ()):
                drawn = _COPY_TOKEN.sub("", normalize(str(value)))
                keys.append(f"chance_values:{family}={drawn}")
    if after is not None:
        if _drew_cards(before, after):
            keys.append(f"draws:card@{owner}")
        if _drew_intrigue(before, after):
            keys.append(f"draws:intrigue@{owner}")
    for event in getattr(transition, "events", ()):
        kind = _text(getattr(event, "kind", ""))
        keys.append(f"events:{kind}")
        if kind in PLAY_EVENT_KINDS:
            card_id = dict(getattr(event, "payload", ())).get("card_id")
            if isinstance(card_id, str):
                keys.append(f"cards_played:{normalize(card_id)}")
    return keys


class KeyIndex:
    """A record's keys, step by step, gathered into its index row."""

    def __init__(self) -> None:
        self._hits: dict[str, list[int]] = {}

    def add(self, index: int, keys: Iterable[str]) -> None:
        """Count every key of recorded step ``index`` (steps in order)."""

        for key in keys:
            self._hits.setdefault(key, []).append(index)

    def row_keys(
        self,
        census: Mapping[str, Mapping[str, int]] | None = None,
        leaders: Iterable[str] = (),
    ) -> dict[str, list[Any]]:
        """``{key: [count, first_step, positions]}``, sorted by key.

        ``positions`` (distinct step indices) is kept for the
        ``FULL_POSITION_DIMENSIONS`` and wherever the count is at most
        ``POSITION_LIMIT``. ``census`` adds the event-derived census counts
        (``collect_game_coverage(final_state, ())``) except its
        ``CENSUS_STEP_DIMENSIONS``, which the steps already count (the
        event-derived card plays included), and ``leaders`` one
        ``leaders:<id>`` per seat; those carry a count only.
        """

        entries: dict[str, list[Any]] = {}
        for key, hits in self._hits.items():
            entry: list[Any] = [len(hits), hits[0]]
            dimension = key.partition(":")[0]
            if dimension in FULL_POSITION_DIMENSIONS or len(hits) <= POSITION_LIMIT:
                entry.append(sorted(set(hits)))
            entries[key] = entry
        for dimension, counts in (census or {}).items():
            if dimension in CENSUS_STEP_DIMENSIONS:
                continue
            for name, count in counts.items():
                entries[f"{dimension}:{name}"] = [count]
        for leader in leaders:
            key = f"leaders:{leader}"
            entries[key] = [entries.get(key, [0])[0] + 1]
        return dict(sorted(entries.items()))


def census_of(keys: Mapping[str, Sequence[Any]]) -> dict[str, dict[str, int]]:
    """An index row's census dimensions as ``{dimension: {key: count}}``.

    The shape ``simulation.coverage.merge_coverage`` sums.
    """

    census: dict[str, dict[str, int]] = {}
    for key, entry in keys.items():
        dimension, _, name = key.partition(":")
        if dimension in CENSUS_DIMENSIONS:
            census.setdefault(dimension, {})[name] = int(entry[0])
    return census
