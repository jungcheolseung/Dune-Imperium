"""Arrakeen Scouts: missions (docs/rules/arrakeen-scouts.md 5).

A revealed mission places bank goods on the board (``GameState.scouts_goods``,
face-down cards in ``scouts_goods_cards``) and asks each seat in turn order
whether it takes part, parking troops on a space (``scouts_parked``, counted
by ``PlayerState.troops_parked`` in the 12-troop total). Pieces stay until
claimed [Scouts help]. An Agent visiting such a space collects what is there
for its seat as one more freely ordered effect of the visit
(``BOARD_ICON_SCOUTS``, like the Bloodlines Commander [Bloodlines p. 4]).

Goods rows are ``(mission, location, resource, amount, seat)`` (seat -1:
whoever collects first); parked rows ``(mission, seat, location, troops)``.
"""

from dataclasses import replace
from typing import Final

from dune_imperium.content.arrakeen_scouts import MISSIONS_BY_ID, Mission, MissionKind
from dune_imperium.content.uprising.board import (
    BOARD_SPACES_BY_ID,
    OBSERVATION_POSTS,
)
from dune_imperium.content.uprising.contracts import contract_for_instance
from dune_imperium.content.uprising.types import AgentIcon
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.contract_tiles import receive_contract
from dune_imperium.rules.effects import (
    advance_after_effect,
    current_agent_effect_context,
    finish_board_icon,
    pending_board_icons,
    recruit_troops,
)
from dune_imperium.rules.frames import (
    FrameKind,
    context_int,
    context_str,
    owned_top_frame,
    replace_player,
)
from dune_imperium.rules.specimens import return_specimens

BOARD_ICON_SCOUTS: Final = "scouts_mission"
_JOIN_FRAME: Final = "Mission participation frame"
TLEILAXU_OFFERING_SPACE: Final = "tleilaxu_track"
# Tleilaxu Offering's "third space of the Tleilaxu Track", counted like the
# setup spice's "fourth space" (index 4, the start space uncounted)
# [Immortality p. 4] (OQ-089 (a)).
TLEILAXU_OFFERING_TRACK_SPACE: Final = 3
# Where the goods of the missions paid off away from a visit wait.
HELIX: Final = "helix"
RECLAIMED_FORCES: Final = "reclaimed_forces"

# Participation: (troop source, troops parked) per mission kind.
_PARKING: Final = {
    MissionKind.SECURITY_DETAIL: ("supply", 1),
    MissionKind.FEDAYKIN_ASSISTANCE: ("supply", 2),
    MissionKind.WEIRDING_WARFARE: ("supply", 2),
    MissionKind.SEND_FOR_AID: ("garrison", 1),
    MissionKind.COORDINATE_WITH_THE_EMPEROR: ("specimens", 1),
    MissionKind.TLEILAXU_OFFERING: ("supply", 2),
}
# Where a mission's collected troops go when their seat visits (OQ-077).
_TO_CONFLICT: Final = frozenset(
    {
        MissionKind.SECURITY_DETAIL,
        MissionKind.WEIRDING_WARFARE,
        MissionKind.SEND_FOR_AID,
    }
)
_PARTICIPATION: Final = frozenset(
    {*_PARKING, MissionKind.PRISON_PLANET, MissionKind.CHOAM_ESCORT}
)


def mission_tasks(
    state: GameState, mission_id: str, order: tuple[int, ...]
) -> tuple[str, ...]:
    """The reveal's tasks: place the goods, then ask each seat in turn order."""

    mission = MISSIONS_BY_ID[mission_id]
    tasks = ["goods"]
    if mission.kind in _PARTICIPATION:
        tasks.extend(f"join:{seat}" for seat in order)
    return tuple(tasks)


# --- Goods -------------------------------------------------------------------------


def _posts_next_to(
    state: GameState, icon: AgentIcon | None, *, maker: bool
) -> tuple[str, ...]:
    """Empty Observation Posts connected to a City (or Maker) space."""

    occupied = {post for seat in state.players for post in seat.spy_post_ids}
    spaces = {
        space_id
        for space_id, space in BOARD_SPACES_BY_ID.items()
        if (space.maker if maker else space.agent_icon is icon)
    }
    return tuple(
        post.post_id
        for post in OBSERVATION_POSTS
        if post.post_id not in occupied and spaces & set(post.connected_space_ids)
    )


def _free_maker_hooks(state: GameState) -> int:
    """Four Maker Hooks tokens exist [Main p. 3]; the seats hold the rest."""

    return 4 - sum(1 for seat in state.players if seat.maker_hooks)


def _is_immediate(contract_id: str) -> bool:
    """Bloodlines' Immediate Contract: taken only by trashing an Intrigue
    card [Bloodlines p. 2]."""

    return contract_for_instance(contract_id).requires_intrigue_trash


def _reshuffle_intrigue_for_goods(state: GameState, *, source: str) -> RuleResult:
    """Shuffle the Intrigue discard into a new deck, then place the goods.

    The engine's Intrigue reshuffle chance frame [FAQ p. 2]: the new deck
    forms beneath the cards still on top (``intrigue_deck
    .apply_intrigue_reshuffle``), and with a count of 0 it draws nothing.
    The ``goods`` task is queued again, so the Scouts step places the new
    top two once the frame resolves.
    """

    if state.first_player is None:
        raise ValueError("the Scouts step requires a First Player")
    decision_id = f"{source}:intrigue_shuffle"
    frame = DecisionFrame(
        kind=FrameKind.INTRIGUE_RESHUFFLE,
        frame_id=f"{decision_id}:intrigue_reshuffle",
        decision=ChanceDecision(
            decision_id=decision_id,
            prompt="Shuffle the Intrigue discard pile into a new deck",
            options=state.intrigue_discard,
            count=len(state.intrigue_discard),
        ),
        context=(
            ("count", 0),
            ("player", state.first_player),
            ("purpose", "scouts_goods"),
            ("source", source),
        ),
    )
    requeued = replace(state, scouts_tasks=("goods", *state.scouts_tasks))
    return RuleResult(state=requeued.push_decision(frame))


def place_mission_goods(
    state: GameState, mission_id: str, *, source: str
) -> RuleResult:
    """Put the mission's bank goods (and face-down cards) on the board.

    CHOAM Research takes the bank's first two Contracts other than
    Bloodlines' Immediate, which keeps its place in the bank (OQ-090, user
    ruling 2026-09-29). Emperor's Schemes shuffles the Intrigue discard into
    a new deck first when the deck holds fewer than its two cards (OQ-078,
    user ruling 2026-09-29; "shuffle the discarded Intrigue cards to form a
    new deck" [FAQ p. 2]); with both piles short it places what there is.
    """

    mission = MISSIONS_BY_ID[mission_id]
    goods: list[tuple[str, str, str, int, int]] = []
    cards: list[tuple[str, str, str]] = []
    next_state = state
    match mission.kind:
        case MissionKind.IMPERIAL_RESERVE:
            assert mission.goods is not None and mission.space_id is not None
            goods += [
                (mission_id, mission.space_id, "spice", mission.goods.spice, -1),
                (mission_id, mission.space_id, "solari", mission.goods.solari, -1),
            ]
        case MissionKind.URBAN_SURVEILLANCE | MissionKind.PLANETARY_EXPLORATION:
            assert mission.goods is not None
            urban = mission.kind is MissionKind.URBAN_SURVEILLANCE
            resource, amount = (
                ("solari", mission.goods.solari)
                if urban
                else ("spice", mission.goods.spice)
            )
            goods += [
                (mission_id, f"post:{post}", resource, amount, -1)
                for post in _posts_next_to(state, AgentIcon.CITY, maker=not urban)
            ]
        case MissionKind.CHOAM_RESEARCH:
            assert mission.space_id is not None
            taken = tuple(
                card for card in state.contract_bank if not _is_immediate(card)
            )[: mission.goods_cards]
            cards += [(mission_id, mission.space_id, card) for card in taken]
            next_state = replace(
                next_state,
                contract_bank=tuple(
                    card for card in state.contract_bank if card not in taken
                ),
            )
        case MissionKind.EMPERORS_SCHEMES:
            assert mission.space_id is not None
            if len(state.intrigue_deck) < mission.goods_cards and (
                state.intrigue_discard
            ):
                return _reshuffle_intrigue_for_goods(state, source=source)
            taken = state.intrigue_deck[: mission.goods_cards]
            cards += [(mission_id, mission.space_id, card) for card in taken]
            next_state = replace(
                next_state, intrigue_deck=state.intrigue_deck[len(taken) :]
            )
        case MissionKind.DESERT_RIDING:
            assert mission.space_id is not None
            if _free_maker_hooks(state) > 0:
                goods.append((mission_id, mission.space_id, "maker_hooks", 1, -1))
        case MissionKind.SPONSORED_RESEARCH:
            assert mission.goods is not None
            goods.append((mission_id, HELIX, "spice", mission.goods.spice, -1))
        case MissionKind.BACK_ROOM_DEAL:
            assert mission.goods is not None
            goods.append(
                (mission_id, RECLAIMED_FORCES, "solari", mission.goods.solari, -1)
            )
        case _:
            pass
    if not goods and not cards:
        return RuleResult(state=next_state)
    next_state = replace(
        next_state,
        scouts_goods=(*next_state.scouts_goods, *goods),
        scouts_goods_cards=(*next_state.scouts_goods_cards, *cards),
    )
    return RuleResult(
        state=next_state,
        events=(
            GameEvent(
                event_id=f"{source}:goods",
                kind="scouts_mission_goods_placed",
                payload=(
                    ("cards", len(cards)),
                    (
                        "locations",
                        ",".join(
                            sorted({row[1] for row in goods} | {c[1] for c in cards})
                        ),
                    ),
                    ("mission_id", mission_id),
                ),
            ),
        ),
    )


# --- Participation ------------------------------------------------------------------


def _markers_out(state: GameState, player: int) -> int:
    return sum(
        1 for row in state.scouts_goods if row[2] == "marker" and row[4] == player
    )


def _parking_open(state: GameState, player: int, mission: Mission) -> bool:
    """Whether a parking mission is open to the seat but for its troops."""

    owner = state.players[player]
    if (
        mission.kind is MissionKind.TLEILAXU_OFFERING
        and owner.tleilaxu_space >= TLEILAXU_OFFERING_TRACK_SPACE
    ):
        # A token already on or past the third space never advances to it
        # again, so its troops could never become specimens (OQ-089 (a)).
        return False
    resources = owner.resources
    return all(
        getattr(cost, "spice", 0) <= resources.spice
        and getattr(cost, "solari", 0) <= resources.solari
        for cost in mission.participation_cost
    )


def join_targets(state: GameState, player: int, mission: Mission) -> tuple[str, ...]:
    """The ways ``player`` can take part now ("" = the one plain way).

    A parking mission moves its whole printed number of troops, so a seat
    with fewer cannot take part (OQ-088, the missions' English).
    """

    owner = state.players[player]
    kind = mission.kind
    if kind is MissionKind.CHOAM_ESCORT:
        return (
            *(("recruit",) if owner.troops_supply else ()),
            *owner.active_contract_ids,
        )
    if kind is MissionKind.PRISON_PLANET:
        free_marker = len(owner.control_space_ids) + _markers_out(state, player) < 3
        return ("",) if owner.troops_garrison and free_marker else ()
    if not _parking_open(state, player, mission):
        return ()
    source, count = _PARKING[kind]
    available = {
        "supply": owner.troops_supply,
        "garrison": owner.troops_garrison,
        "specimens": owner.specimens,
    }[source]
    return ("",) if available >= count else ()


def join_unavailable_reason(
    state: GameState, player: int, mission: Mission, target: str = ""
) -> tuple[str, int, int] | None:
    """Why ``target`` is not among ``join_targets``; None when it is.

    ``(what, needed, held)``: "supply", "garrison" or "specimens" (troops
    short, OQ-088), "spice" or "solari" (the participation cost), "marker"
    (all three Control markers are out), "tleilaxu_track" (the token is
    already on or past the third space, OQ-089 (a)), "contract" (not one of
    the seat's face-up Contracts) or "none" (no participation at all). For
    the display only, which shows a way in the seat cannot take beside the
    reason; it reads ``join_targets`` first, so the two never disagree.
    """

    kind = mission.kind
    if kind not in _PARTICIPATION:
        return ("none", 0, 0)
    if target in join_targets(state, player, mission):
        return None
    owner = state.players[player]
    if kind is MissionKind.CHOAM_ESCORT:
        if target == "recruit":
            return ("supply", 1, owner.troops_supply)
        return ("contract", 1, 0)
    if kind is MissionKind.PRISON_PLANET:
        if not owner.troops_garrison:
            return ("garrison", 1, 0)
        return ("marker", 1, 0)
    if (
        kind is MissionKind.TLEILAXU_OFFERING
        and owner.tleilaxu_space >= TLEILAXU_OFFERING_TRACK_SPACE
    ):
        return ("tleilaxu_track", TLEILAXU_OFFERING_TRACK_SPACE, owner.tleilaxu_space)
    for cost in mission.participation_cost:
        for resource in ("spice", "solari"):
            needed = getattr(cost, resource, 0)
            held = getattr(owner.resources, resource)
            if needed > held:
                return (resource, needed, held)
    source, count = _PARKING[kind]
    held = {
        "supply": owner.troops_supply,
        "garrison": owner.troops_garrison,
        "specimens": owner.specimens,
    }[source]
    return (source, count, held)


def mission_top_up(state: GameState, player: int, mission: Mission) -> int:
    """How many specimens the seat may return so it can take part (0: none).

    "You may return any of your specimens to your supply at any time"
    [Immortality p. 8]; a seat short of the supply troops a mission takes
    may do so first (user ruling 2026-09-29, OQ-074, OQ-088).
    """

    if not state.config.immortality:
        return 0
    owner = state.players[player]
    kind = mission.kind
    if kind is MissionKind.CHOAM_ESCORT:
        needed = 1  # the troop it recruits
    elif (
        kind in _PARKING
        and _PARKING[kind][0] == "supply"
        and _parking_open(state, player, mission)
    ):
        needed = _PARKING[kind][1]
    else:
        return 0
    short = needed - owner.troops_supply
    if short < 1 or owner.specimens < short:
        return 0
    return short


def offer_mission_join(
    state: GameState, player: int, mission_id: str, *, source: str
) -> RuleResult:
    """Ask one seat whether it takes part (OQ-088: skipped when it cannot)."""

    mission = MISSIONS_BY_ID[mission_id]
    if not join_targets(state, player, mission) and not mission_top_up(
        state, player, mission
    ):
        return RuleResult(state=state)
    frame = DecisionFrame(
        kind=FrameKind.SCOUTS_MISSION,
        frame_id=f"{source}:join",
        decision=PlayerDecision(
            owner=player, prompt="Take part in the mission or pass"
        ),
        context=(("mission_id", mission_id), ("player", player), ("source", source)),
    )
    return RuleResult(state=state.push_decision(frame))


def legal_mission_join_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    frame = owned_top_frame(state, FrameKind.SCOUTS_MISSION, player)
    if frame is None:
        return ()
    mission = MISSIONS_BY_ID[
        context_str(dict(frame.context), "mission_id", owner=_JOIN_FRAME)
    ]
    return (
        DomainAction(action_id="scouts_decline_mission", actor=player),
        *(
            DomainAction(
                action_id="scouts_join_mission",
                actor=player,
                arguments=(("target", target),),
            )
            for target in join_targets(state, player, mission)
        ),
        *(
            DomainAction(
                action_id="scouts_return_specimens",
                actor=player,
                arguments=(("count", count),),
            )
            for count in range(1, mission_top_up(state, player, mission) + 1)
        ),
    )


def apply_mission_join(state: GameState, action: DomainAction) -> RuleResult:
    if action not in legal_mission_join_actions(state, action.actor):
        raise ValueError("action is not a legal mission choice")
    context = dict(state.decision_stack[-1].context)
    mission = MISSIONS_BY_ID[context_str(context, "mission_id", owner=_JOIN_FRAME)]
    source = context_str(context, "source", owner=_JOIN_FRAME)
    player = action.actor
    if action.action_id == "scouts_return_specimens":
        # The seat is still asked; the returned troops are now its supply.
        count = dict(action.arguments)["count"]
        assert isinstance(count, int)
        return return_specimens(state, player, count, source=f"{source}:top_up")
    popped = state.pop_decision()
    if action.action_id == "scouts_decline_mission":
        return RuleResult(
            state=popped,
            events=(
                GameEvent(
                    event_id=f"{source}:declined",
                    kind="scouts_mission_declined",
                    payload=(("mission_id", mission.mission_id), ("player", player)),
                ),
            ),
        )
    target = str(dict(action.arguments)["target"])
    joined = _join(popped, player, mission, target)
    return RuleResult(
        state=joined,
        events=(
            GameEvent(
                event_id=f"{source}:joined",
                kind="scouts_mission_joined",
                payload=(
                    ("mission_id", mission.mission_id),
                    ("player", player),
                    ("target", target),
                ),
            ),
        ),
    )


def _join(state: GameState, player: int, mission: Mission, target: str) -> GameState:
    owner = state.players[player]
    goods = list(state.scouts_goods)
    parked = list(state.scouts_parked)
    kind = mission.kind
    mission_id = mission.mission_id
    if kind is MissionKind.CHOAM_ESCORT:
        if target == "recruit":
            recruited, _ = recruit_troops(owner, 1)
            return replace(state, players=replace_player(state.players, recruited))
        goods += [
            (mission_id, f"contract:{target}", "solari", 1, player),
            (mission_id, f"contract:{target}", "spice", 1, player),
        ]
        return replace(state, scouts_goods=tuple(goods))
    if kind is MissionKind.PRISON_PLANET:
        assert mission.space_id is not None and mission.seat_goods is not None
        owner = replace(
            owner,
            troops_garrison=owner.troops_garrison - 1,
            troops_supply=owner.troops_supply + 1,
        )
        goods += [
            (mission_id, mission.space_id, "marker", 1, player),
            (mission_id, mission.space_id, "spice", mission.seat_goods.spice, player),
        ]
        return replace(
            state,
            players=replace_player(state.players, owner),
            scouts_goods=tuple(goods),
        )
    source, count = _PARKING[kind]
    resources = owner.resources
    for cost in mission.participation_cost:
        resources = replace(
            resources,
            spice=resources.spice - getattr(cost, "spice", 0),
            solari=resources.solari - getattr(cost, "solari", 0),
        )
    moved = count  # join_targets only offers a seat that has them all
    owner = replace(
        owner,
        resources=resources,
        troops_parked=owner.troops_parked + moved,
        troops_supply=owner.troops_supply - (moved if source == "supply" else 0),
        troops_garrison=owner.troops_garrison - (moved if source == "garrison" else 0),
        specimens=owner.specimens - (moved if source == "specimens" else 0),
    )
    location = (
        mission.space_id if mission.space_id is not None else TLEILAXU_OFFERING_SPACE
    )
    parked.append((mission_id, player, location, moved))
    if mission.seat_goods is not None:
        for resource in ("solari", "spice", "water"):
            amount = getattr(mission.seat_goods, resource)
            if amount:
                goods.append((mission_id, location, resource, amount, player))
    return replace(
        state,
        players=replace_player(state.players, owner),
        scouts_goods=tuple(goods),
        scouts_parked=tuple(parked),
    )


# --- Visits ---------------------------------------------------------------------------

_VISITED: Final = frozenset(
    {
        MissionKind.SECURITY_DETAIL,
        MissionKind.IMPERIAL_RESERVE,
        MissionKind.CHOAM_RESEARCH,
        MissionKind.PRISON_PLANET,
        MissionKind.EMPERORS_SCHEMES,
        MissionKind.FEDAYKIN_ASSISTANCE,
        MissionKind.WEIRDING_WARFARE,
        MissionKind.SEND_FOR_AID,
        MissionKind.COORDINATE_WITH_THE_EMPEROR,
    }
)


def _collects(mission_id: str) -> bool:
    return MISSIONS_BY_ID[mission_id].kind in _VISITED


def _takeable_card(state: GameState, space_id: str) -> tuple[str, str, str] | None:
    """The next face-down card on ``space_id`` (one per visit, OQ-078).

    Any seat may take it: Bloodlines' Immediate Contract, the one card that
    needs an Intrigue card to trash [Bloodlines p. 2], never reaches the
    Research Station (OQ-090, ``place_mission_goods``).
    """

    return next(
        (
            row
            for row in state.scouts_goods_cards
            if row[1] == space_id and _collects(row[0])
        ),
        None,
    )


def mission_collectable(state: GameState, player: int, space_id: str) -> bool:
    """Whether a visit by ``player`` to ``space_id`` collects mission pieces."""

    if not state.config.arrakeen_scouts:
        return False
    return (
        any(
            row[1] == space_id
            and row[3] > 0
            and row[4] in (-1, player)
            and _collects(row[0])
            for row in state.scouts_goods
        )
        or _takeable_card(state, space_id) is not None
        or any(
            row[1] == player and row[2] == space_id and _collects(row[0])
            for row in state.scouts_parked
        )
    )


def _imperial_reserve_choices(state: GameState, space_id: str) -> tuple[str, ...]:
    return tuple(
        row[2]
        for row in state.scouts_goods
        if row[1] == space_id
        and MISSIONS_BY_ID[row[0]].kind is MissionKind.IMPERIAL_RESERVE
        and row[3] > 0
    )


def legal_mission_collect_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """The visit's mission icon: one action, or Imperial Reserve's pick."""

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if BOARD_ICON_SCOUTS not in pending_board_icons(context):
        return ()
    space_id = context_str(context, "space_id", owner="Agent effect frame")
    reserve = _imperial_reserve_choices(state, space_id)
    choices = reserve if len(reserve) > 1 else ("",)
    return tuple(
        DomainAction(
            action_id="scouts_collect_mission",
            actor=player,
            arguments=(("choice", choice),),
        )
        for choice in choices
    )


def apply_mission_collect(state: GameState, action: DomainAction) -> RuleResult:
    """Collect everything the visiting seat's missions left on this space."""

    if action not in legal_mission_collect_actions(state, action.actor):
        raise ValueError("action is not a legal mission collection")
    _, context = current_agent_effect_context(state)
    player = action.actor
    space_id = context_str(context, "space_id", owner="Agent effect frame")
    choice = str(dict(action.arguments)["choice"])
    source = f"round:{state.round_number}:player:{player}:scouts:{space_id}"
    owner = state.players[player]
    goods = list(state.scouts_goods)
    cards = list(state.scouts_goods_cards)
    parked = list(state.scouts_parked)
    events: list[GameEvent] = []
    recruited = 0
    intrigue_gained: list[str] = []
    # Parked troops (OQ-077): to the Conflict, or recruited to the garrison.
    for row in [
        r for r in parked if r[1] == player and r[2] == space_id and _collects(r[0])
    ]:
        mission_id, _, _, troops = row
        parked.remove(row)
        kind = MISSIONS_BY_ID[mission_id].kind
        to_conflict = kind in _TO_CONFLICT
        owner = replace(
            owner,
            troops_parked=owner.troops_parked - troops,
            troops_conflict=owner.troops_conflict + (troops if to_conflict else 0),
            troops_garrison=owner.troops_garrison + (0 if to_conflict else troops),
        )
        if not to_conflict:
            # Troops gained into the garrison are recruited this turn
            # (OQ-077, OQ-089 (c), user ruling 2026-09-29).
            recruited += troops
        events.append(
            GameEvent(
                event_id=f"{source}:{mission_id}:troops",
                kind="scouts_mission_troops",
                payload=(
                    ("count", troops),
                    ("mission_id", mission_id),
                    ("player", player),
                    ("to", "conflict" if to_conflict else "garrison"),
                ),
            )
        )
    # Goods on the space: the seat's own, and the anyone-goods (Imperial
    # Reserve: one of the two, OQ-078).
    reserve_taken = False
    for goods_row in [r for r in goods if r[1] == space_id and _collects(r[0])]:
        mission_id, _, resource, amount, seat = goods_row
        kind = MISSIONS_BY_ID[mission_id].kind
        if seat not in (-1, player):
            continue
        if kind is MissionKind.IMPERIAL_RESERVE:
            if reserve_taken or (choice and resource != choice):
                continue
            reserve_taken = True
        goods.remove(goods_row)
        if resource == "marker":
            events.append(
                GameEvent(
                    event_id=f"{source}:{mission_id}:marker",
                    kind="scouts_marker_returned",
                    payload=(("mission_id", mission_id), ("player", player)),
                )
            )
            continue
        owner = replace(
            owner,
            resources=replace(
                owner.resources,
                **{resource: getattr(owner.resources, resource) + amount},
            ),
        )
        events.append(
            GameEvent(
                event_id=f"{source}:{mission_id}:{resource}",
                kind="scouts_mission_goods_taken",
                payload=(
                    ("amount", amount),
                    ("mission_id", mission_id),
                    ("player", player),
                    ("resource", resource),
                ),
            )
        )
    # One face-down card per visit (OQ-078): a Contract or an Intrigue card.
    card_row = _takeable_card(state, space_id)
    if card_row is not None:
        cards.remove(card_row)
        mission_id, _, card_id = card_row
        if MISSIONS_BY_ID[mission_id].kind is MissionKind.CHOAM_RESEARCH:
            if _is_immediate(card_id):
                raise RuntimeError("the Immediate never reaches the Research Station")
            owner = receive_contract(owner, card_id)
            events.append(
                GameEvent(
                    event_id=f"{source}:{mission_id}:contract",
                    kind="contract_taken",
                    payload=(
                        ("contract_id", card_id),
                        ("player", player),
                        ("replacement_id", ""),
                        ("source", source),
                    ),
                )
            )
        else:
            owner = replace(owner, intrigue_cards=(*owner.intrigue_cards, card_id))
            intrigue_gained.append(card_id)
            events.append(
                GameEvent(
                    event_id=f"{source}:{mission_id}:intrigue",
                    kind="intrigue_card_drawn",
                    payload=(("count", 1), ("player", player)),
                    visible_to=None,
                )
            )
    finish_board_icon(context, BOARD_ICON_SCOUTS)
    if recruited:
        # Garrison-bound mission troops are this turn's recruits (OQ-077).
        context["troops_recruited"] = (
            context_int(context, "troops_recruited", owner="Agent effect frame")
            + recruited
        )
    working = replace(
        state,
        players=replace_player(state.players, owner),
        scouts_goods=tuple(goods),
        scouts_goods_cards=tuple(cards),
        scouts_parked=tuple(parked),
    )
    next_state = advance_after_effect(working, context, working.players)
    return RuleResult(state=next_state, events=tuple(events))


# --- Goods paid off away from a visit -----------------------------------------------


def _give(owner: PlayerState, resource: str, amount: int) -> PlayerState:
    return replace(
        owner,
        resources=replace(
            owner.resources,
            **{resource: getattr(owner.resources, resource) + amount},
        ),
    )


def _taken_event(
    source: str, mission_id: str, player: int, resource: str, amount: int
) -> GameEvent:
    return GameEvent(
        event_id=f"{source}:{mission_id}:{resource}",
        kind="scouts_mission_goods_taken",
        payload=(
            ("amount", amount),
            ("mission_id", mission_id),
            ("player", player),
            ("resource", resource),
        ),
    )


def claim_goods_at(
    state: GameState, player: int, location: str, *, source: str
) -> RuleResult:
    """``player`` takes the bank goods waiting at ``location`` for anyone.

    Sponsored Research's spice waits beside the Helix for the next seat to
    reach it, Back Room Deal's Solari on Reclaimed Forces for the next seat to
    acquire that card (docs/rules/arrakeen-scouts.md 5, OQ-089).
    """

    rows = [row for row in state.scouts_goods if row[1] == location and row[4] < 0]
    if not rows:
        return RuleResult(state=state)
    owner = state.players[player]
    events = []
    for mission_id, _, resource, amount, _ in rows:
        owner = _give(owner, resource, amount)
        events.append(_taken_event(source, mission_id, player, resource, amount))
    return RuleResult(
        state=replace(
            state,
            players=replace_player(state.players, owner),
            scouts_goods=tuple(row for row in state.scouts_goods if row not in rows),
        ),
        events=tuple(events),
    )


def release_offering(state: GameState, player: int, *, source: str) -> RuleResult:
    """Tleilaxu Offering: the seat's parked troops become specimens.

    The troops a seat left on the Tleilaxu track's third space go into its
    Axolotl tanks as specimens once its own Tleilaxu token gets there
    (docs/rules/arrakeen-scouts.md 5, OQ-089 (a)).
    """

    rows = [
        row
        for row in state.scouts_parked
        if row[1] == player and row[2] == TLEILAXU_OFFERING_SPACE
    ]
    if not rows:
        return RuleResult(state=state)
    owner = state.players[player]
    troops = sum(row[3] for row in rows)
    owner = replace(
        owner,
        troops_parked=owner.troops_parked - troops,
        specimens=owner.specimens + troops,
    )
    return RuleResult(
        state=replace(
            state,
            players=replace_player(state.players, owner),
            scouts_parked=tuple(row for row in state.scouts_parked if row not in rows),
        ),
        events=tuple(
            GameEvent(
                event_id=f"{source}:{row[0]}:troops",
                kind="scouts_mission_troops",
                payload=(
                    ("count", row[3]),
                    ("mission_id", row[0]),
                    ("player", player),
                    ("to", "specimens"),
                ),
            )
            for row in rows
        ),
    )


def _post_occupant(state: GameState, location: str) -> int | None:
    post = location.removeprefix("post:")
    return next(
        (seat.player_id for seat in state.players if post in seat.spy_post_ids),
        None,
    )


def _escort_due(state: GameState, row: tuple[str, str, str, int, int]) -> bool:
    contract = row[1].removeprefix("contract:")
    return contract not in state.players[row[4]].active_contract_ids


def mission_goods_are_due(state: GameState) -> bool:
    """Whether a Spy or a completed Contract has earned waiting goods."""

    if not state.scouts_goods:
        return False
    for row in state.scouts_goods:
        if row[1].startswith("post:") and _post_occupant(state, row[1]) is not None:
            return True
        if row[1].startswith("contract:") and _escort_due(state, row):
            return True
    return False


def claim_due_mission_goods(state: GameState) -> RuleResult:
    """Pay the goods a Spy placement or a Contract completion has earned.

    Valued Informants: the seat whose Spy lands on a post holding a good takes
    it, whatever put the Spy there (OQ-080). CHOAM Escort: the seat that loaded
    a Contract gets the Solari and spice on it when that Contract is
    completed (docs/rules/arrakeen-scouts.md 5); a Contract that left the seat's supply
    uncompleted takes them back to the bank. The claims run after every
    step, so every placement and completion path pays the same way.
    """

    players = list(state.players)
    kept = []
    events = []
    source = f"round:{state.round_number}:scouts_goods"
    for row in state.scouts_goods:
        mission_id, location, resource, amount, seat = row
        if location.startswith("post:"):
            occupant = _post_occupant(state, location)
            if occupant is None:
                kept.append(row)
                continue
            players[occupant] = _give(players[occupant], resource, amount)
            events.append(
                _taken_event(
                    f"{source}:{location}", mission_id, occupant, resource, amount
                )
            )
            continue
        if location.startswith("contract:") and _escort_due(state, row):
            contract = location.removeprefix("contract:")
            if contract in players[seat].completed_contract_ids:
                players[seat] = _give(players[seat], resource, amount)
                events.append(
                    _taken_event(
                        f"{source}:{contract}", mission_id, seat, resource, amount
                    )
                )
            continue
        kept.append(row)
    return RuleResult(
        state=replace(state, players=tuple(players), scouts_goods=tuple(kept)),
        events=tuple(events),
    )


# --- Maker Hooks (Desert Riding) -----------------------------------------------------


def desert_riding_token(state: GameState) -> tuple[str, str, str, int, int] | None:
    return next((row for row in state.scouts_goods if row[2] == "maker_hooks"), None)


def take_desert_riding_token(
    state: GameState, player: int, *, source: str
) -> RuleResult:
    """``player`` takes the Maker Hooks token Desert Riding left out.

    At Hagga Basin in place of the space's own 2 spice
    (docs/rules/arrakeen-scouts.md 5); at Sietch Tabr when it is the last of
    the four tokens (OQ-079 (e)).
    """

    row = desert_riding_token(state)
    if row is None:
        return RuleResult(state=state)
    owner = replace(state.players[player], maker_hooks=True)
    return RuleResult(
        state=replace(
            state,
            players=replace_player(state.players, owner),
            scouts_goods=tuple(r for r in state.scouts_goods if r != row),
        ),
        events=(_taken_event(source, row[0], player, "maker_hooks", 1),),
    )


def maker_hooks_left_in_bank(state: GameState) -> int:
    """The four tokens less the seats' and Desert Riding's [Main p. 3]."""

    return _free_maker_hooks(state) - (desert_riding_token(state) is not None)


def free_prison_marker(
    goods: tuple[tuple[str, str, str, int, int], ...],
    player: int,
    controlled: int,
    *,
    source: str,
) -> tuple[tuple[tuple[str, str, str, int, int], ...], tuple[GameEvent, ...]]:
    """Prison Planet: a seat gaining control with no free marker takes it back.

    Per the help (docs/rules/arrakeen-scouts.md 5), the marker is reused when
    the seat has none left for a third space, and the mission then ends with
    no spice for it: the seat's marker and spice rows leave
    the board, the spice to the bank.
    """

    rows = [
        row
        for row in goods
        if row[4] == player and MISSIONS_BY_ID[row[0]].kind is MissionKind.PRISON_PLANET
    ]
    markers = sum(1 for row in rows if row[2] == "marker")
    if not markers or controlled + markers < 3:
        return goods, ()
    remaining = tuple(row for row in goods if row not in rows)
    spice = sum(row[3] for row in rows if row[2] == "spice")
    return remaining, (
        GameEvent(
            event_id=f"{source}:prison_planet_marker:{player}",
            kind="scouts_prison_marker_taken",
            payload=(("player", player), ("spice_returned", spice)),
        ),
    )


def parked_troops_by_seat(state: GameState) -> dict[int, int]:
    counts: dict[int, int] = {}
    for _, seat, _, troops in state.scouts_parked:
        counts[seat] = counts.get(seat, 0) + troops
    return counts
