"""Units lost to an opponent's card effect (Holy War, Bloodlines).

"Each opponent loses one troop" does not say from where. The project
convention (OQ-036) lets the losing player choose the zone when both the
garrison and the Conflict hold units; within a zone a troop is lost before
a Sardaukar Commander, which is a troop for card effects [Bloodlines p. 4].
"""

from dataclasses import replace

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import (
    FrameKind,
    context_str,
    owned_top_frame,
    replace_player,
)
from dune_imperium.rules.spy_moves import opponent_seats
from dune_imperium.rules.units import retreat_units

UNIT_ZONES: tuple[str, ...] = ("garrison", "conflict")


def _zones_with_units(state: GameState, player: int) -> tuple[str, ...]:
    owner = state.players[player]
    zones: list[str] = []
    if owner.troops_garrison + owner.commanders_garrison > 0:
        zones.append("garrison")
    if owner.troops_conflict + owner.commanders_conflict > 0:
        zones.append("conflict")
    return tuple(zones)


def lose_unit(
    state: GameState,
    player: int,
    zone: str,
    *,
    source: str,
) -> RuleResult:
    """Return one unit of ``player`` from ``zone`` to the supply."""

    if zone not in UNIT_ZONES:
        raise ValueError("unit loss zone must be garrison or conflict")
    owner = state.players[player]
    events: list[GameEvent] = []
    working = state
    if zone == "conflict":
        commander = owner.troops_conflict == 0
        retreated = retreat_units(
            working,
            player,
            f"{source}:loss",
            troops=0 if commander else 1,
            commanders=1 if commander else 0,
        )
        working = retreated.state
        events.extend(retreated.events)
        owner = working.players[player]
    else:
        commander = owner.troops_garrison == 0
    if commander:
        next_owner = replace(
            owner,
            commanders_garrison=owner.commanders_garrison - 1,
            commanders_supply=owner.commanders_supply + 1,
        )
    else:
        next_owner = replace(
            owner,
            troops_garrison=owner.troops_garrison - 1,
            troops_supply=owner.troops_supply + 1,
        )
    events.append(
        GameEvent(
            event_id=f"{source}:lost",
            kind="unit_lost",
            payload=(
                ("commanders", int(commander)),
                ("player", player),
                ("zone", zone),
            ),
        )
    )
    return RuleResult(
        state=replace(working, players=replace_player(working.players, next_owner)),
        events=tuple(events),
    )


def opponent_unit_loss_frames(
    state: GameState,
    actor: int,
    *,
    source: str,
) -> RuleResult:
    """Each opponent loses one unit: chosen zone when both hold units."""

    working = state
    events: list[GameEvent] = []
    frames: list[DecisionFrame] = []
    for seat in opponent_seats(state, actor):
        zones = _zones_with_units(working, seat)
        seat_source = f"{source}:unit_loss:{seat}"
        if not zones:
            events.append(
                GameEvent(
                    event_id=f"{seat_source}:none",
                    kind="unit_loss_unavailable",
                    payload=(("player", seat),),
                )
            )
        elif len(zones) == 1:
            lost = lose_unit(working, seat, zones[0], source=seat_source)
            working = lost.state
            events.extend(lost.events)
        else:
            frames.append(
                DecisionFrame(
                    kind=FrameKind.OPPONENT_UNIT_LOSS,
                    frame_id=seat_source,
                    decision=PlayerDecision(
                        owner=seat, prompt="Choose where to lose one unit"
                    ),
                    context=(("player", seat), ("source", seat_source)),
                )
            )
    next_state = replace(
        working, decision_stack=(*working.decision_stack, *reversed(frames))
    )
    return RuleResult(state=next_state, events=tuple(events))


def legal_unit_loss_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer each zone that still holds a unit."""

    frame = owned_top_frame(state, FrameKind.OPPONENT_UNIT_LOSS, player)
    if frame is None:
        return ()
    return tuple(
        DomainAction(action_id="lose_unit", actor=player, arguments=(("zone", zone),))
        for zone in _zones_with_units(state, player)
    )


def apply_unit_loss(state: GameState, action: DomainAction) -> RuleResult:
    """Lose one unit from the chosen zone and close the frame."""

    if action not in legal_unit_loss_actions(state, action.actor):
        raise ValueError("action is not a legal unit loss choice")
    frame = state.decision_stack[-1]
    source = context_str(dict(frame.context), "source", owner="Unit loss frame")
    zone = str(dict(action.arguments)["zone"])
    return lose_unit(state.pop_decision(), action.actor, zone, source=source)
