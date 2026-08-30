"""Versioned flat-vector encoding of ``PlayerView`` for learning adapters.

The encoder is a pure function of ``PlayerView``: every visibility decision
stays in ``core.observation`` and the encoder can only rearrange what a view
already exposes. The layout is egocentric — every seat reference is rotated
so relative seat 0 is the observer — and versioned through
``OBSERVATION_VERSION`` with a named segment table so training code never
hardcodes offsets.

Encoding rules:

- Ordered slots hold ``identity_index + 1`` with ``0`` meaning empty.
- Unordered card zones hold one count per catalog identity.
- Membership zones hold multi-hot flags; battle cards use a tri-state value
  (0 absent, 1 face up, 2 face down).
"""

from dataclasses import dataclass
from typing import Final

from dune_imperium.content.uprising.board import (
    BOARD_SPACES_BY_ID,
    OBSERVATION_POSTS,
    Faction,
)
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.contracts import (
    CONTRACTS_BY_ID,
    contract_for_instance,
)
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.intrigue import (
    INTRIGUE_CARDS_BY_ID,
    INTRIGUE_CARDS_BY_INSTANCE,
)
from dune_imperium.content.uprising.leaders import FEYD_TRACK_BY_ID, LEADERS_BY_ID
from dune_imperium.content.uprising.objectives import OBJECTIVES
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.reserve import RESERVE_STACKS
from dune_imperium.content.uprising.starting_cards import STARTING_CARDS_BY_ID
from dune_imperium.core.observation import PlayerView, PublicPlayerView
from dune_imperium.core.state import GamePhase
from dune_imperium.rules.frames import FrameKind

OBSERVATION_VERSION: Final = 2
_SEATS: Final = 4

PERSONAL_CARD_IDS: Final = (
    *STARTING_CARDS_BY_ID,
    *(stack.card.card_id for stack in RESERVE_STACKS),
    *IMPERIUM_CARDS_BY_ID,
)
INTRIGUE_IDS: Final = tuple(INTRIGUE_CARDS_BY_ID)
CONTRACT_IDS: Final = tuple(CONTRACTS_BY_ID)
CONFLICT_IDS: Final = tuple(conflict.card.card_id for conflict in CONFLICTS)
BATTLE_CARD_IDS: Final = (
    *CONFLICT_IDS,
    *(objective.objective_id for objective in OBJECTIVES),
)
LEADER_IDS: Final = tuple(LEADERS_BY_ID)
SPACE_IDS: Final = tuple(BOARD_SPACES_BY_ID)
POST_IDS: Final = tuple(post.post_id for post in OBSERVATION_POSTS)
FEYD_TRACK_IDS: Final = tuple(FEYD_TRACK_BY_ID)
FACTION_IDS: Final = tuple(faction.value for faction in Faction)
CONTROL_SPACE_IDS: Final = ("arrakeen", "spice_refinery", "imperial_basin")
MAKER_SPACE_IDS: Final = ("deep_desert", "hagga_basin", "imperial_basin")
RESERVE_STACK_IDS: Final = tuple(stack.card.card_id for stack in RESERVE_STACKS)

_PHASES: Final = tuple(GamePhase)
_FRAME_KINDS: Final = tuple(kind.value for kind in FrameKind)
_PERSONAL_INDEX: Final = {
    card_id: index for index, card_id in enumerate(PERSONAL_CARD_IDS)
}
_INTRIGUE_INDEX: Final = {
    card_id: index for index, card_id in enumerate(INTRIGUE_IDS)
}
_AGENT_LOCATION_SLOTS: Final = 3
_SET_ASIDE_SLOTS: Final = 2
_IMPERIUM_ROW_SLOTS: Final = 5
_LEADER_DRAFT_SLOTS: Final = 6


@dataclass(frozen=True, slots=True)
class ObservationSegment:
    """One named, contiguous slice of the encoded observation vector."""

    name: str
    offset: int
    length: int


def _seat_segment_lengths(seat: int) -> tuple[tuple[str, int], ...]:
    prefix = f"seat{seat}"
    return (
        (f"{prefix}_scalars", 28),
        (f"{prefix}_alliances", len(FACTION_IDS)),
        (f"{prefix}_control", len(CONTROL_SPACE_IDS)),
        (f"{prefix}_agent_locations", _AGENT_LOCATION_SLOTS),
        (f"{prefix}_spy_posts", len(POST_IDS)),
        (f"{prefix}_battle_cards", len(BATTLE_CARD_IDS)),
        (f"{prefix}_in_play", len(PERSONAL_CARD_IDS)),
        (f"{prefix}_trashed", len(PERSONAL_CARD_IDS)),
        (f"{prefix}_intrigue_faceup", len(INTRIGUE_IDS)),
        (f"{prefix}_imperium_set_aside", _SET_ASIDE_SLOTS),
        (f"{prefix}_active_contracts", len(CONTRACT_IDS)),
    )


def _segment_lengths() -> tuple[tuple[str, int], ...]:
    lengths: list[tuple[str, int]] = [
        ("global_scalars", 11),
        ("current_conflict", 1),
        ("imperium_row", _IMPERIUM_ROW_SLOTS),
        ("reserve_stacks", len(RESERVE_STACK_IDS)),
        ("maker_bonus_spice", len(MAKER_SPACE_IDS)),
        ("contract_bank_size", 1),
        ("face_up_contracts", len(CONTRACT_IDS)),
        ("sardaukar_contracts", len(CONTRACT_IDS)),
        ("intrigue_discard", len(INTRIGUE_IDS)),
        ("intrigue_trash", len(INTRIGUE_IDS)),
        ("imperium_removed", len(PERSONAL_CARD_IDS)),
        ("reveal_order", _SEATS),
        ("leader_draft_pool", _LEADER_DRAFT_SLOTS),
    ]
    for seat in range(_SEATS):
        lengths.extend(_seat_segment_lengths(seat))
    lengths.extend(
        (
            ("private_hand", len(PERSONAL_CARD_IDS)),
            ("private_discard", len(PERSONAL_CARD_IDS)),
            ("private_intrigue", len(INTRIGUE_IDS)),
        )
    )
    return tuple(lengths)


def _build_segments() -> tuple[ObservationSegment, ...]:
    segments: list[ObservationSegment] = []
    offset = 0
    for name, length in _segment_lengths():
        segments.append(ObservationSegment(name=name, offset=offset, length=length))
        offset += length
    return tuple(segments)


OBSERVATION_SEGMENTS: Final = _build_segments()
OBSERVATION_SIZE: Final = sum(segment.length for segment in OBSERVATION_SEGMENTS)
_SEGMENTS_BY_NAME: Final = {segment.name: segment for segment in OBSERVATION_SEGMENTS}


def segment_slice(name: str) -> slice:
    """Return the vector slice of one named segment."""

    segment = _SEGMENTS_BY_NAME[name]
    return slice(segment.offset, segment.offset + segment.length)


class _Writer:
    """Append segment chunks while verifying the declared layout."""

    def __init__(self) -> None:
        self.values: list[int] = []
        self._segments = iter(OBSERVATION_SEGMENTS)

    def write(self, name: str, chunk: list[int]) -> None:
        segment = next(self._segments, None)
        if segment is None or segment.name != name or segment.length != len(chunk):
            raise RuntimeError(f"observation segment mismatch at {name}")
        self.values.extend(chunk)

    def finish(self) -> tuple[int, ...]:
        if next(self._segments, None) is not None:
            raise RuntimeError("observation encoder ended before the last segment")
        return tuple(self.values)


def encode_player_view(view: PlayerView) -> tuple[int, ...]:
    """Encode one ``PlayerView`` into the versioned flat int vector."""

    if len(view.players) != _SEATS:
        raise ValueError("the observation encoding requires four seated players")
    if view.private is None:
        raise ValueError("the observation encoding requires the private view")

    observer = view.player
    writer = _Writer()

    def relative(seat: int | None) -> int:
        if seat is None:
            return 0
        return ((seat - observer) % _SEATS) + 1

    writer.write(
        "global_scalars",
        [
            view.round_number,
            _PHASES.index(view.phase),
            relative(view.first_player),
            int(view.shield_wall_present),
            0
            if view.decision_kind is None
            else _FRAME_KINDS.index(view.decision_kind) + 1,
            relative(view.decision_owner),
            relative(view.turn_owner),
            int(view.endgame_intrigue_complete),
            int(view.combat_intrigue_complete),
            int(view.combat_rewards_resolved),
            len(view.current_conflict_ids),
        ],
    )
    writer.write(
        "current_conflict",
        [
            _index_plus_one(view.current_conflict_ids[-1], CONFLICT_IDS)
            if view.current_conflict_ids
            else 0
        ],
    )
    writer.write(
        "imperium_row",
        _identity_slots(
            view.imperium_row,
            _IMPERIUM_ROW_SLOTS,
            "Imperium Row",
        ),
    )
    reserve_counts = dict(view.reserve_stacks)
    writer.write(
        "reserve_stacks",
        [reserve_counts.get(card_id, 0) for card_id in RESERVE_STACK_IDS],
    )
    maker_spice = dict(view.maker_bonus_spice)
    writer.write(
        "maker_bonus_spice",
        [maker_spice.get(space_id, 0) for space_id in MAKER_SPACE_IDS],
    )
    writer.write("contract_bank_size", [view.contract_bank_size])
    writer.write("face_up_contracts", _contract_flags(view.face_up_contract_ids))
    writer.write("sardaukar_contracts", _contract_flags(view.sardaukar_contract_ids))
    writer.write("intrigue_discard", _intrigue_counts(view.intrigue_discard))
    writer.write("intrigue_trash", _intrigue_counts(view.intrigue_trash))
    writer.write("imperium_removed", _personal_counts(view.imperium_removed))
    reveal_slots = [relative(seat) for seat in view.reveal_order]
    writer.write(
        "reveal_order", reveal_slots + [0] * (_SEATS - len(reveal_slots))
    )
    if len(view.leader_draft_pool) > _LEADER_DRAFT_SLOTS:
        raise ValueError("the Leader draft pool holds more than six Leaders")
    pool_slots = [
        _index_plus_one(leader_id, LEADER_IDS)
        for leader_id in view.leader_draft_pool
    ]
    writer.write(
        "leader_draft_pool",
        pool_slots + [0] * (_LEADER_DRAFT_SLOTS - len(pool_slots)),
    )

    for seat_offset in range(_SEATS):
        seat = (observer + seat_offset) % _SEATS
        _write_seat(writer, seat_offset, view.players[seat])

    writer.write("private_hand", _personal_counts(view.private.hand))
    writer.write("private_discard", _personal_counts(view.private.discard_pile))
    writer.write("private_intrigue", _intrigue_counts(view.private.intrigue_cards))
    return writer.finish()


def _write_seat(writer: _Writer, seat_offset: int, player: PublicPlayerView) -> None:
    prefix = f"seat{seat_offset}"
    leader_flipped = int(
        player.leader_face_id is not None
        and player.leader_face_id != player.leader_id
    )
    writer.write(
        f"{prefix}_scalars",
        [
            player.victory_points,
            player.resources.solari,
            player.resources.spice,
            player.resources.water,
            player.influence.emperor,
            player.influence.spacing_guild,
            player.influence.bene_gesserit,
            player.influence.fremen,
            player.agents_available,
            int(player.swordmaster_acquired),
            player.troops_supply,
            player.troops_garrison,
            player.troops_conflict,
            player.sandworms_conflict,
            player.spies_supply,
            player.combat_strength,
            int(player.has_revealed),
            int(player.high_council),
            int(player.maker_hooks),
            player.memories,
            player.completed_contract_count,
            _index_plus_one(player.leader_id, LEADER_IDS)
            if player.leader_id is not None
            else 0,
            leader_flipped,
            FEYD_TRACK_IDS.index(player.feyd_track_space),
            player.hand_size,
            player.deck_size,
            player.discard_size,
            player.intrigue_card_count,
        ],
    )
    writer.write(
        f"{prefix}_alliances", _multi_hot(player.alliance_faction_ids, FACTION_IDS)
    )
    writer.write(
        f"{prefix}_control", _multi_hot(player.control_space_ids, CONTROL_SPACE_IDS)
    )
    location_slots = [
        _index_plus_one(space_id, SPACE_IDS) for space_id in player.agent_locations
    ]
    if len(location_slots) > _AGENT_LOCATION_SLOTS:
        raise RuntimeError("a player cannot have more than three placed Agents")
    writer.write(
        f"{prefix}_agent_locations",
        location_slots + [0] * (_AGENT_LOCATION_SLOTS - len(location_slots)),
    )
    writer.write(f"{prefix}_spy_posts", _multi_hot(player.spy_post_ids, POST_IDS))
    face_down = set(player.face_down_battle_card_ids)
    held = set(player.objective_ids) | set(player.won_conflict_ids)
    writer.write(
        f"{prefix}_battle_cards",
        [
            0 if card_id not in held else (2 if card_id in face_down else 1)
            for card_id in BATTLE_CARD_IDS
        ],
    )
    writer.write(f"{prefix}_in_play", _personal_counts(player.in_play))
    writer.write(f"{prefix}_trashed", _personal_counts(player.trashed))
    writer.write(
        f"{prefix}_intrigue_faceup", _intrigue_counts(player.intrigue_faceup)
    )
    set_aside_slots = [
        _personal_identity_index(instance_id) + 1
        for instance_id in player.imperium_set_aside
    ]
    if len(set_aside_slots) > _SET_ASIDE_SLOTS:
        raise RuntimeError("more set-aside Imperium cards than encoded slots")
    writer.write(
        f"{prefix}_imperium_set_aside",
        set_aside_slots + [0] * (_SET_ASIDE_SLOTS - len(set_aside_slots)),
    )
    writer.write(
        f"{prefix}_active_contracts", _contract_flags(player.active_contract_ids)
    )


def _identity_slots(
    instance_ids: tuple[str, ...],
    slots: int,
    zone_name: str,
) -> list[int]:
    if len(instance_ids) > slots:
        raise RuntimeError(f"{zone_name} holds more cards than encoded slots")
    values = [
        _personal_identity_index(instance_id) + 1 for instance_id in instance_ids
    ]
    return values + [0] * (slots - len(values))


def _personal_identity_index(instance_id: str) -> int:
    return _PERSONAL_INDEX[personal_card_for_instance(instance_id).card.card_id]


def _personal_counts(instance_ids: tuple[str, ...]) -> list[int]:
    counts = [0] * len(PERSONAL_CARD_IDS)
    for instance_id in instance_ids:
        counts[_personal_identity_index(instance_id)] += 1
    return counts


def _intrigue_counts(instance_ids: tuple[str, ...]) -> list[int]:
    counts = [0] * len(INTRIGUE_IDS)
    for instance_id in instance_ids:
        card_id = INTRIGUE_CARDS_BY_INSTANCE[instance_id].card.card_id
        counts[_INTRIGUE_INDEX[card_id]] += 1
    return counts


def _contract_flags(instance_ids: tuple[str, ...]) -> list[int]:
    identities = tuple(
        contract_for_instance(instance_id).card.card_id
        for instance_id in instance_ids
    )
    return _multi_hot(identities, CONTRACT_IDS)


def _multi_hot(
    member_ids: tuple[str, ...],
    universe: tuple[str, ...],
) -> list[int]:
    members = set(member_ids)
    unknown = members.difference(universe)
    if unknown:
        raise RuntimeError(f"unknown identities in observation zone: {unknown}")
    return [int(identity in members) for identity in universe]


def _index_plus_one(identity: str, universe: tuple[str, ...]) -> int:
    return universe.index(identity) + 1
