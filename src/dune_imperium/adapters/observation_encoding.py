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
from functools import cache
from typing import Final

from dune_imperium.content.bloodlines.sardaukar import (
    COMMANDER_SETUP_SPACE_IDS,
    SKILLS,
    skill_for_instance,
)
from dune_imperium.content.bloodlines.tech import TECH_IDS, TECH_STACKS
from dune_imperium.content.immortality.board import (
    RESEARCH_SPACES_BY_ID,
    TLEILAXU_ROW_SIZE,
)
from dune_imperium.content.immortality.tleilaxu import TLEILAXU_CARDS_BY_ID
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
from dune_imperium.content.uprising.types import AgentIcon
from dune_imperium.core.observation import PlayerView, PublicPlayerView
from dune_imperium.core.state import GamePhase
from dune_imperium.rules.frames import FrameKind

OBSERVATION_VERSION: Final = 20
_SEATS: Final = 4

PERSONAL_CARD_IDS: Final = (
    *STARTING_CARDS_BY_ID,
    *(stack.card.card_id for stack in RESERVE_STACKS),
    *IMPERIUM_CARDS_BY_ID,
    # Immortality: the Tleilaxu deck (its promo included) joins the
    # personal-card universe; Reclaimed Forces never enters a deck.
    *TLEILAXU_CARDS_BY_ID,
)
RESEARCH_SPACE_IDS: Final = tuple(RESEARCH_SPACES_BY_ID)
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
MAKER_SPACE_IDS: Final = ("deep_desert", "hagga_basin", "imperial_basin", "tuek_sietch")
RESERVE_STACK_IDS: Final = tuple(stack.card.card_id for stack in RESERVE_STACKS)
SKILL_IDS: Final = tuple(skill.skill_id for skill in SKILLS)
COMMANDER_SPACE_IDS: Final = COMMANDER_SETUP_SPACE_IDS

_PHASES: Final = tuple(GamePhase)
_AGENT_ICONS: Final = tuple(icon.value for icon in AgentIcon)
_FRAME_KINDS: Final = tuple(kind.value for kind in FrameKind)
_PERSONAL_INDEX: Final = {
    card_id: index for index, card_id in enumerate(PERSONAL_CARD_IDS)
}
_INTRIGUE_INDEX: Final = {card_id: index for index, card_id in enumerate(INTRIGUE_IDS)}
_AGENT_LOCATION_SLOTS: Final = 3
_SET_ASIDE_SLOTS: Final = 2
_IMPERIUM_ROW_SLOTS: Final = 5
_LEADER_DRAFT_SLOTS: Final = 6

# Precomputed identity -> index maps for every universe otherwise searched
# with ``tuple.index`` or scanned in full by a membership zone. Building
# these once at import time turns each lookup into an O(1) dict access
# instead of an O(n) linear scan repeated on every encode call.
_SPACE_INDEX: Final = {space_id: index for index, space_id in enumerate(SPACE_IDS)}
_LEADER_INDEX: Final = {leader_id: index for index, leader_id in enumerate(LEADER_IDS)}
_CONFLICT_INDEX: Final = {
    card_id: index for index, card_id in enumerate(CONFLICT_IDS)
}
_BATTLE_CARD_INDEX: Final = {
    card_id: index for index, card_id in enumerate(BATTLE_CARD_IDS)
}
_TECH_INDEX: Final = {tech_id: index for index, tech_id in enumerate(TECH_IDS)}
_RESEARCH_SPACE_INDEX: Final = {
    space_id: index for index, space_id in enumerate(RESEARCH_SPACE_IDS)
}
_FEYD_TRACK_INDEX: Final = {
    space_id: index for index, space_id in enumerate(FEYD_TRACK_IDS)
}
_POST_INDEX: Final = {post_id: index for index, post_id in enumerate(POST_IDS)}
_FACTION_INDEX: Final = {
    faction_id: index for index, faction_id in enumerate(FACTION_IDS)
}
_CONTROL_SPACE_INDEX: Final = {
    space_id: index for index, space_id in enumerate(CONTROL_SPACE_IDS)
}
_COMMANDER_SPACE_INDEX: Final = {
    space_id: index for index, space_id in enumerate(COMMANDER_SPACE_IDS)
}
_CONTRACT_INDEX: Final = {
    card_id: index for index, card_id in enumerate(CONTRACT_IDS)
}
_SKILL_INDEX: Final = {skill_id: index for index, skill_id in enumerate(SKILL_IDS)}
_RESERVE_STACK_INDEX: Final = {
    card_id: index for index, card_id in enumerate(RESERVE_STACK_IDS)
}
_MAKER_SPACE_INDEX: Final = {
    space_id: index for index, space_id in enumerate(MAKER_SPACE_IDS)
}
_PHASE_INDEX: Final = {phase: index for index, phase in enumerate(_PHASES)}
_FRAME_KIND_INDEX: Final = {kind: index for index, kind in enumerate(_FRAME_KINDS)}
_AGENT_ICON_INDEX: Final = {icon: index for index, icon in enumerate(_AGENT_ICONS)}


@dataclass(frozen=True, slots=True)
class ObservationSegment:
    """One named, contiguous slice of the encoded observation vector."""

    name: str
    offset: int
    length: int


def _seat_segment_lengths(seat: int) -> tuple[tuple[str, int], ...]:
    prefix = f"seat{seat}"
    return (
        # v12: research space (index + 1), Tleilaxu space, specimens,
        # Family Atomics (44 -> 48). v13: this round's Reveal Persuasion
        # bonus (48 -> 49). v15: Chairdog's pending returns and Usurp's
        # borrowed Row card (49 -> 51).
        (f"{prefix}_scalars", 52),
        (f"{prefix}_alliances", len(FACTION_IDS)),
        (f"{prefix}_control", len(CONTROL_SPACE_IDS)),
        (f"{prefix}_agent_locations", _AGENT_LOCATION_SLOTS),
        (f"{prefix}_spy_posts", len(POST_IDS)),
        (f"{prefix}_battle_cards", len(BATTLE_CARD_IDS)),
        (f"{prefix}_hand_public", len(PERSONAL_CARD_IDS)),
        (f"{prefix}_in_play", len(PERSONAL_CARD_IDS)),
        (f"{prefix}_discard", len(PERSONAL_CARD_IDS)),
        (f"{prefix}_trashed", len(PERSONAL_CARD_IDS)),
        (f"{prefix}_intrigue_faceup", len(INTRIGUE_IDS)),
        (f"{prefix}_imperium_set_aside", _SET_ASIDE_SLOTS),
        (f"{prefix}_active_contracts", len(CONTRACT_IDS)),
        (f"{prefix}_completed_contracts", len(CONTRACT_IDS)),
        (f"{prefix}_skills", len(SKILL_IDS)),
        # Tri-state per tile: 0 absent, 1 face up, 2 flipped this round.
        (f"{prefix}_tech", len(TECH_IDS)),
    )


def _segment_lengths() -> tuple[tuple[str, int], ...]:
    lengths: list[tuple[str, int]] = [
        ("global_scalars", 12),
        ("current_conflict", 1),
        ("imperium_row", _IMPERIUM_ROW_SLOTS),
        ("reserve_stacks", len(RESERVE_STACK_IDS)),
        ("maker_bonus_spice", len(MAKER_SPACE_IDS)),
        ("contract_bank_size", 1),
        ("face_up_contracts", len(CONTRACT_IDS)),
        ("sardaukar_contracts", len(CONTRACT_IDS)),
        ("contract_trash", len(CONTRACT_IDS)),
        ("intrigue_resolving", len(INTRIGUE_IDS)),
        ("intrigue_discard", len(INTRIGUE_IDS)),
        ("intrigue_trash", len(INTRIGUE_IDS)),
        ("imperium_removed", len(PERSONAL_CARD_IDS)),
        ("reveal_order", _SEATS),
        ("leader_draft_pool", _LEADER_DRAFT_SLOTS),
        ("commander_spaces", len(COMMANDER_SPACE_IDS)),
        ("commander_bank", 1),
        ("skill_stack_size", 1),
        ("skill_face_up", len(SKILL_IDS)),
        # Tech Module: the face-up top of each stack (identity index + 1),
        # the stack sizes and the trashed tiles.
        ("tech_face_up", TECH_STACKS),
        ("tech_stack_sizes", TECH_STACKS),
        ("tech_trash", len(TECH_IDS)),
        # Immortality: the Tleilaxu Row slots (identity index + 1), the
        # deck size and the setup spice left on the Tleilaxu track.
        ("tleilaxu_row", TLEILAXU_ROW_SIZE),
        ("tleilaxu_deck_size", 1),
        ("tleilaxu_track_spice", 1),
        # v13: seats (relative to the observer) that played a Combat
        # Intrigue card in this Conflict.
        ("combat_intrigue_players", _SEATS),
    ]
    for seat in range(_SEATS):
        lengths.extend(_seat_segment_lengths(seat))
    lengths.extend(
        (
            ("private_hand", len(PERSONAL_CARD_IDS)),
            ("private_intrigue", len(INTRIGUE_IDS)),
            ("private_peeked_card", len(PERSONAL_CARD_IDS)),
            # v14: Imperium Ceremony's peek at the Intrigue deck's top two.
            ("private_peeked_intrigue", len(INTRIGUE_IDS)),
            ("private_navigation_slots", 4),
            ("private_secret_project", 1),
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


# Precomputed name -> offset lookup, so ``encode_player_view`` writes each
# segment directly into a preallocated vector instead of appending through a
# per-call ``_Writer``. The segment layout itself is self-checked once, at
# import time, by ``_build_segments``'s cumulative offset arithmetic and by
# ``test_layout_is_versioned_and_contiguous``; nothing needs to re-verify it
# on every ``encode_player_view`` call.
_OFFSET: Final[dict[str, int]] = {
    segment.name: segment.offset for segment in OBSERVATION_SEGMENTS
}
_SEAT_SUFFIXES: Final = (
    "scalars",
    "alliances",
    "control",
    "agent_locations",
    "spy_posts",
    "battle_cards",
    "hand_public",
    "in_play",
    "discard",
    "trashed",
    "intrigue_faceup",
    "imperium_set_aside",
    "active_contracts",
    "completed_contracts",
    "skills",
    "tech",
)
_SEAT_OFFSETS: Final[tuple[dict[str, int], ...]] = tuple(
    {suffix: _OFFSET[f"seat{seat}_{suffix}"] for suffix in _SEAT_SUFFIXES}
    for seat in range(_SEATS)
)


def encode_player_view(view: PlayerView) -> tuple[int, ...]:
    """Encode one ``PlayerView`` into the versioned flat int vector."""

    if len(view.players) != _SEATS:
        raise ValueError("the observation encoding requires four seated players")
    if view.private is None:
        raise ValueError("the observation encoding requires the private view")

    observer = view.player
    values: list[int] = [0] * OBSERVATION_SIZE

    def relative(seat: int | None) -> int:
        if seat is None:
            return 0
        return ((seat - observer) % _SEATS) + 1

    offset = _OFFSET["global_scalars"]
    values[offset : offset + 12] = [
        view.round_number,
        _PHASE_INDEX[view.phase],
        relative(view.first_player),
        int(view.shield_wall_present),
        0
        if view.decision_kind is None
        else _FRAME_KIND_INDEX[view.decision_kind] + 1,
        relative(view.decision_owner),
        relative(view.turn_owner),
        int(view.endgame_intrigue_complete),
        int(view.combat_intrigue_complete),
        int(view.combat_rewards_resolved),
        len(view.current_conflict_ids),
        view.conflict_first_place_influence_bonus,
    ]
    values[_OFFSET["current_conflict"]] = (
        _CONFLICT_INDEX[view.current_conflict_ids[-1]] + 1
        if view.current_conflict_ids
        else 0
    )
    _write_identity_slots(
        values,
        _OFFSET["imperium_row"],
        _IMPERIUM_ROW_SLOTS,
        view.imperium_row,
        "Imperium Row",
    )
    offset = _OFFSET["reserve_stacks"]
    for card_id, count in view.reserve_stacks:
        slot = _RESERVE_STACK_INDEX.get(card_id)
        if slot is not None:
            values[offset + slot] = count
    offset = _OFFSET["maker_bonus_spice"]
    for space_id, spice in view.maker_bonus_spice:
        slot = _MAKER_SPACE_INDEX.get(space_id)
        if slot is not None:
            values[offset + slot] = spice
    values[_OFFSET["contract_bank_size"]] = view.contract_bank_size
    _write_contract_flags(
        values, _OFFSET["face_up_contracts"], view.face_up_contract_ids
    )
    _write_contract_flags(
        values, _OFFSET["sardaukar_contracts"], view.sardaukar_contract_ids
    )
    _write_contract_flags(values, _OFFSET["contract_trash"], view.contract_trash)
    _write_intrigue_counts(
        values, _OFFSET["intrigue_resolving"], view.intrigue_resolving
    )
    _write_intrigue_counts(values, _OFFSET["intrigue_discard"], view.intrigue_discard)
    _write_intrigue_counts(values, _OFFSET["intrigue_trash"], view.intrigue_trash)
    _write_personal_counts(values, _OFFSET["imperium_removed"], view.imperium_removed)
    reveal_slots = [relative(seat) for seat in view.reveal_order]
    _write_fixed(
        values,
        _OFFSET["reveal_order"],
        _SEATS,
        reveal_slots + [0] * (_SEATS - len(reveal_slots)),
        "reveal_order",
    )
    if len(view.leader_draft_pool) > _LEADER_DRAFT_SLOTS:
        raise ValueError("the Leader draft pool holds more than six Leaders")
    pool_slots = [
        _LEADER_INDEX[leader_id] + 1 for leader_id in view.leader_draft_pool
    ]
    offset = _OFFSET["leader_draft_pool"]
    values[offset : offset + _LEADER_DRAFT_SLOTS] = pool_slots + [0] * (
        _LEADER_DRAFT_SLOTS - len(pool_slots)
    )
    _write_multi_hot(
        values,
        _OFFSET["commander_spaces"],
        view.sardaukar_commander_space_ids,
        COMMANDER_SPACE_IDS,
        _COMMANDER_SPACE_INDEX,
    )
    values[_OFFSET["commander_bank"]] = view.sardaukar_commanders_bank
    values[_OFFSET["skill_stack_size"]] = view.skill_stack_size
    _write_skill_counts(values, _OFFSET["skill_face_up"], view.skill_face_up)
    tops = [
        _TECH_INDEX[tech_id] + 1 if tech_id else 0 for tech_id in view.tech_face_up
    ]
    _write_fixed(
        values,
        _OFFSET["tech_face_up"],
        TECH_STACKS,
        tops + [0] * (TECH_STACKS - len(tops)),
        "tech_face_up",
    )
    sizes = list(view.tech_stack_sizes)
    _write_fixed(
        values,
        _OFFSET["tech_stack_sizes"],
        TECH_STACKS,
        sizes + [0] * (TECH_STACKS - len(sizes)),
        "tech_stack_sizes",
    )
    _write_multi_hot(
        values, _OFFSET["tech_trash"], view.tech_trash, TECH_IDS, _TECH_INDEX
    )
    _write_identity_slots(
        values,
        _OFFSET["tleilaxu_row"],
        TLEILAXU_ROW_SIZE,
        view.tleilaxu_row,
        "the Tleilaxu Row",
    )
    values[_OFFSET["tleilaxu_deck_size"]] = view.tleilaxu_deck_size
    values[_OFFSET["tleilaxu_track_spice"]] = view.tleilaxu_track_spice
    offset = _OFFSET["combat_intrigue_players"]
    for seat in view.combat_intrigue_players:
        # ``relative`` is 1-based (0 marks "nobody" in the ordered slots).
        values[offset + relative(seat) - 1] = 1

    for seat_offset in range(_SEATS):
        seat = (observer + seat_offset) % _SEATS
        _write_seat(values, seat_offset, view.players[seat])

    _write_personal_counts(values, _OFFSET["private_hand"], view.private.hand)
    _write_intrigue_counts(
        values, _OFFSET["private_intrigue"], view.private.intrigue_cards
    )
    _write_personal_counts(
        values,
        _OFFSET["private_peeked_card"],
        (view.private.peeked_card_id,) if view.private.peeked_card_id else (),
    )
    _write_intrigue_counts(
        values, _OFFSET["private_peeked_intrigue"], view.private.peeked_intrigue_ids
    )
    # Face-down Navigation slots: identity index + 1 per slot, 0 when empty.
    slots = [
        _intrigue_identity_index(card_id) + 1
        for card_id in view.private.navigation_slots
    ]
    _write_fixed(
        values,
        _OFFSET["private_navigation_slots"],
        4,
        slots + [0] * (4 - len(slots)),
        "private_navigation_slots",
    )
    secret = view.private.secret_project_tech_id
    values[_OFFSET["private_secret_project"]] = (
        _TECH_INDEX[secret] + 1 if secret else 0
    )
    return tuple(values)


def _write_seat(values: list[int], seat_offset: int, player: PublicPlayerView) -> None:
    offsets = _SEAT_OFFSETS[seat_offset]
    leader_flipped = int(
        player.leader_face_id is not None and player.leader_face_id != player.leader_id
    )
    offset = offsets["scalars"]
    values[offset : offset + 52] = [
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
        _LEADER_INDEX[player.leader_id] + 1 if player.leader_id is not None else 0,
        leader_flipped,
        _FEYD_TRACK_INDEX[player.feyd_track_space],
        player.hand_size,
        player.deck_size,
        player.intrigue_card_count,
        player.commanders_supply,
        player.commanders_garrison,
        player.commanders_conflict,
        int(player.commander_recruited_turn),
        player.contracts_completed_turn,
        player.held_contract_icons,
        player.commander_discount_turn,
        int(player.ignores_influence_requirements_turn),
        # Granted Agent icons as a bit mask (Resourceful grants three).
        sum(
            1 << _AGENT_ICON_INDEX[value]
            for value in player.granted_agent_icon_turn.split(",")
            if value
        ),
        int(player.combat_icon_turn),
        int(player.bene_gesserit_boost_pending),
        player.tactics_track_space,
        player.agent_in_conflict,
        player.twisted_deck_size,
        player.navigation_remaining,
        player.reveal_persuasion_bonus,
        int(player.has_secret_project),
        player.spies_boxed,
        player.spies_recalled_turn,
        _RESEARCH_SPACE_INDEX[player.research_space] + 1
        if player.research_space
        else 0,
        player.tleilaxu_space,
        player.specimens,
        int(player.family_atomics),
        player.reveal_persuasion_round_bonus,
        len(player.chairdog_return_card_ids),
        int(bool(player.usurped_row_card_id)),
    ]
    _write_multi_hot(
        values,
        offsets["alliances"],
        player.alliance_faction_ids,
        FACTION_IDS,
        _FACTION_INDEX,
    )
    _write_multi_hot(
        values,
        offsets["control"],
        player.control_space_ids,
        CONTROL_SPACE_IDS,
        _CONTROL_SPACE_INDEX,
    )
    location_slots = [
        _SPACE_INDEX[space_id] + 1 for space_id in player.agent_locations
    ]
    if len(location_slots) > _AGENT_LOCATION_SLOTS:
        raise RuntimeError("a player cannot have more than three placed Agents")
    offset = offsets["agent_locations"]
    values[offset : offset + _AGENT_LOCATION_SLOTS] = location_slots + [0] * (
        _AGENT_LOCATION_SLOTS - len(location_slots)
    )
    _write_multi_hot(
        values, offsets["spy_posts"], player.spy_post_ids, POST_IDS, _POST_INDEX
    )
    _write_battle_cards(values, offsets["battle_cards"], player)
    _write_personal_counts(values, offsets["hand_public"], player.hand_public)
    _write_personal_counts(values, offsets["in_play"], player.in_play)
    _write_personal_counts(values, offsets["discard"], player.discard_pile)
    _write_personal_counts(values, offsets["trashed"], player.trashed)
    _write_intrigue_counts(values, offsets["intrigue_faceup"], player.intrigue_faceup)
    set_aside_slots = [
        _personal_identity_index(instance_id) + 1
        for instance_id in player.imperium_set_aside
    ]
    if len(set_aside_slots) > _SET_ASIDE_SLOTS:
        raise RuntimeError("more set-aside Imperium cards than encoded slots")
    offset = offsets["imperium_set_aside"]
    values[offset : offset + _SET_ASIDE_SLOTS] = set_aside_slots + [0] * (
        _SET_ASIDE_SLOTS - len(set_aside_slots)
    )
    _write_contract_flags(
        values, offsets["active_contracts"], player.active_contract_ids
    )
    _write_contract_flags(
        values, offsets["completed_contracts"], player.completed_contract_ids
    )
    _write_skill_counts(values, offsets["skills"], player.skill_ids)
    _write_tech_tri_state(values, offsets["tech"], player)


def _write_identity_slots(
    values: list[int],
    offset: int,
    slots: int,
    instance_ids: tuple[str, ...],
    zone_name: str,
) -> None:
    if len(instance_ids) > slots:
        raise RuntimeError(f"{zone_name} holds more cards than encoded slots")
    for position, instance_id in enumerate(instance_ids):
        values[offset + position] = _personal_identity_index(instance_id) + 1


def _write_fixed(
    values: list[int],
    offset: int,
    length: int,
    chunk: list[int],
    zone_name: str,
) -> None:
    if len(chunk) != length:
        raise RuntimeError(f"observation segment mismatch at {zone_name}")
    values[offset : offset + length] = chunk


@cache
def _personal_identity_index(instance_id: str) -> int:
    return _PERSONAL_INDEX[personal_card_for_instance(instance_id).card.card_id]


@cache
def _intrigue_identity_index(instance_id: str) -> int:
    return _INTRIGUE_INDEX[INTRIGUE_CARDS_BY_INSTANCE[instance_id].card.card_id]


@cache
def _contract_identity_index(instance_id: str) -> int:
    return _CONTRACT_INDEX[contract_for_instance(instance_id).card.card_id]


@cache
def _skill_identity_index(instance_id: str) -> int:
    return _SKILL_INDEX[skill_for_instance(instance_id).skill_id]


def _write_personal_counts(
    values: list[int], offset: int, instance_ids: tuple[str, ...]
) -> None:
    for instance_id in instance_ids:
        values[offset + _personal_identity_index(instance_id)] += 1


def _write_intrigue_counts(
    values: list[int], offset: int, instance_ids: tuple[str, ...]
) -> None:
    for instance_id in instance_ids:
        values[offset + _intrigue_identity_index(instance_id)] += 1


def _write_skill_counts(
    values: list[int], offset: int, instance_ids: tuple[str, ...]
) -> None:
    for instance_id in instance_ids:
        values[offset + _skill_identity_index(instance_id)] += 1


def _write_contract_flags(
    values: list[int], offset: int, instance_ids: tuple[str, ...]
) -> None:
    for instance_id in instance_ids:
        values[offset + _contract_identity_index(instance_id)] = 1


def _write_multi_hot(
    values: list[int],
    offset: int,
    member_ids: tuple[str, ...],
    universe: tuple[str, ...],
    index: dict[str, int],
) -> None:
    for identity in member_ids:
        slot = index.get(identity)
        if slot is None:
            unknown = set(member_ids).difference(universe)
            raise RuntimeError(f"unknown identities in observation zone: {unknown}")
        values[offset + slot] = 1


def _write_battle_cards(
    values: list[int], offset: int, player: PublicPlayerView
) -> None:
    face_down = set(player.face_down_battle_card_ids)
    for card_id in (*player.objective_ids, *player.won_conflict_ids):
        slot = _BATTLE_CARD_INDEX.get(card_id)
        if slot is not None:
            values[offset + slot] = 2 if card_id in face_down else 1


def _write_tech_tri_state(
    values: list[int], offset: int, player: PublicPlayerView
) -> None:
    flipped = set(player.tech_flipped)
    for tech_id in player.tech_ids:
        slot = _TECH_INDEX.get(tech_id)
        if slot is not None:
            values[offset + slot] = 2 if tech_id in flipped else 1
