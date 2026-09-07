"""Units lost to an opponent's card effect (Holy War, Bloodlines).

"Each opponent loses one troop" does not say from where. The project
convention (OQ-036, user decision) lets the losing player choose both the
zone (garrison or Conflict) and the unit, a troop or a Sardaukar Commander,
which is a troop for card effects [Bloodlines p. 4].
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


def _loss_options(state: GameState, player: int) -> tuple[tuple[str, bool], ...]:
    """Return the (zone, commander) pairs the player can lose a unit from."""

    owner = state.players[player]
    options: list[tuple[str, bool]] = []
    if owner.troops_garrison > 0:
        options.append(("garrison", False))
    if owner.commanders_garrison > 0:
        options.append(("garrison", True))
    if owner.troops_conflict > 0:
        options.append(("conflict", False))
    if owner.commanders_conflict > 0:
        options.append(("conflict", True))
    return tuple(options)


def lose_unit(
    state: GameState,
    player: int,
    zone: str,
    *,
    commander: bool = False,
    source: str,
) -> RuleResult:
    """Return one unit of ``player`` from ``zone`` to the supply."""

    if zone not in UNIT_ZONES:
        raise ValueError("unit loss zone must be garrison or conflict")
    if (zone, commander) not in _loss_options(state, player):
        raise ValueError("the player has no such unit to lose")
    owner = state.players[player]
    events: list[GameEvent] = []
    working = state
    if zone == "conflict":
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
    """Each opponent loses one unit, choosing which when more than one kind."""

    working = state
    events: list[GameEvent] = []
    frames: list[DecisionFrame] = []
    for seat in opponent_seats(state, actor):
        options = _loss_options(working, seat)
        seat_source = f"{source}:unit_loss:{seat}"
        if not options:
            events.append(
                GameEvent(
                    event_id=f"{seat_source}:none",
                    kind="unit_loss_unavailable",
                    payload=(("player", seat),),
                )
            )
        elif len(options) == 1:
            zone, commander = options[0]
            lost = lose_unit(
                working, seat, zone, commander=commander, source=seat_source
            )
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
    """Offer every zone and unit kind the player still holds."""

    frame = owned_top_frame(state, FrameKind.OPPONENT_UNIT_LOSS, player)
    if frame is None:
        return ()
    return tuple(
        DomainAction(
            action_id="lose_unit",
            actor=player,
            arguments=(
                *((("commanders", 1),) if commander else ()),
                ("zone", zone),
            ),
        )
        for zone, commander in _loss_options(state, player)
    )


def apply_unit_loss(state: GameState, action: DomainAction) -> RuleResult:
    """Lose one unit from the chosen zone and close the frame."""

    if action not in legal_unit_loss_actions(state, action.actor):
        raise ValueError("action is not a legal unit loss choice")
    frame = state.decision_stack[-1]
    source = context_str(dict(frame.context), "source", owner="Unit loss frame")
    arguments = dict(action.arguments)
    zone = str(arguments["zone"])
    commander = arguments.get("commanders") == 1
    return lose_unit(
        state.pop_decision(), action.actor, zone, commander=commander, source=source
    )
