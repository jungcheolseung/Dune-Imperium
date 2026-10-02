"""Units lost to an opponent's card effect (Holy War, Bloodlines).

"Each opponent loses one troop" does not say from where. The project
convention (OQ-036 (a), user decision) lets the losing player choose both
the zone (garrison or Conflict) and the unit, a troop or a Sardaukar
Commander, which is a troop for card effects [Bloodlines p. 4].

Every opponent is asked, even with one option or none (user ruling
2026-09-30: "선택지가 단 하나여도 어쨌든 확인을 거치는 걸로 통일하는게
깔끔해"); a seat with no unit at all confirms the loss it cannot make with
``resolve_unit_loss_without_unit``. ``unit_loss_block`` is the one judgment
of which (zone, unit) a seat can lose, read by the provider and by the
page's greyed-out rows (``display.unavailable``).
"""

from dataclasses import replace
from enum import StrEnum
from typing import Final

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.combat_deployment import release_undeployable_troops
from dune_imperium.rules.frames import (
    FrameKind,
    context_str,
    owned_top_frame,
    replace_player,
)
from dune_imperium.rules.spy_moves import opponent_seats
from dune_imperium.rules.units import retreat_units

UNIT_ZONES: tuple[str, ...] = ("garrison", "conflict")

# Every (zone, commander) a unit can be lost from, in the order the loss
# window lists them: the garrison's troop, then its Commander, then the
# Conflict's troop and Commander.
UNIT_LOSS_CANDIDATES: Final[tuple[tuple[str, bool], ...]] = (
    ("garrison", False),
    ("garrison", True),
    ("conflict", False),
    ("conflict", True),
)


class UnitLossBlock(StrEnum):
    """Why a seat cannot lose a unit of one kind from one zone now.

    ``legal_unit_loss_actions`` offers ``lose_unit(zone[, commanders])``
    exactly when ``unit_loss_block`` is None, and the page's greyed-out row
    reads the same block, so the reason shown can never disagree with the
    legal list.
    """

    NO_TROOP = "no_troop"  # no troop in that zone
    NO_COMMANDER = "no_commander"  # no Sardaukar Commander in that zone


def unit_loss_block(
    owner: PlayerState, zone: str, *, commander: bool
) -> UnitLossBlock | None:
    """Return why ``owner`` cannot lose that unit from ``zone`` now, or None.

    Reads only the seat's own unit counts, which are public.
    """

    if zone not in UNIT_ZONES:
        raise ValueError("unit loss zone must be garrison or conflict")
    if commander:
        held = (
            owner.commanders_garrison
            if zone == "garrison"
            else owner.commanders_conflict
        )
        return None if held > 0 else UnitLossBlock.NO_COMMANDER
    held = owner.troops_garrison if zone == "garrison" else owner.troops_conflict
    return None if held > 0 else UnitLossBlock.NO_TROOP


def unit_loss_options(state: GameState, player: int) -> tuple[tuple[str, bool], ...]:
    """Return the (zone, commander) pairs the player can lose a unit from."""

    owner = state.players[player]
    return tuple(
        (zone, commander)
        for zone, commander in UNIT_LOSS_CANDIDATES
        if unit_loss_block(owner, zone, commander=commander) is None
    )


def lose_unit(
    state: GameState,
    player: int,
    zone: str,
    *,
    commander: bool = False,
    source: str,
    advance_tactics: bool = True,
) -> RuleResult:
    """Return one unit of ``player`` from ``zone`` to the supply.

    ``advance_tactics=False`` is for a caller losing several units to one
    source: it advances Chani's Tactics token once for them all
    [FAQ p. 1] [Bloodlines p. 12].
    """

    if zone not in UNIT_ZONES:
        raise ValueError("unit loss zone must be garrison or conflict")
    if unit_loss_block(state.players[player], zone, commander=commander) is not None:
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
            advance_tactics=advance_tactics,
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
    if zone == "garrison" and not commander:
        # The lost troop is Harkonnen Advisor's undeployable one first.
        working = release_undeployable_troops(working, player, 1)
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
    """Push one unit-loss decision for every opponent of ``actor``.

    Every opponent is asked, clockwise from the next seat (the frames are
    pushed so that seat decides first), even with a single (zone, unit) to
    lose or none at all (user ruling 2026-09-30, OQ-036 (a)): the seat with
    nothing to lose confirms it. Nothing is lost here; each seat's own step
    makes its loss.
    """

    frames = tuple(
        DecisionFrame(
            kind=FrameKind.OPPONENT_UNIT_LOSS,
            frame_id=f"{source}:unit_loss:{seat}",
            decision=PlayerDecision(
                owner=seat,
                prompt=(
                    "Choose where to lose one unit"
                    if unit_loss_options(state, seat)
                    else "No unit to lose"
                ),
            ),
            context=(("player", seat), ("source", f"{source}:unit_loss:{seat}")),
        )
        for seat in opponent_seats(state, actor)
    )
    return RuleResult(
        state=replace(
            state, decision_stack=(*state.decision_stack, *reversed(frames))
        )
    )


def legal_unit_loss_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer every zone and unit kind the player still holds.

    With no unit at all only ``resolve_unit_loss_without_unit`` is offered:
    the window still opens, and the seat confirms that it loses nothing.
    """

    frame = owned_top_frame(state, FrameKind.OPPONENT_UNIT_LOSS, player)
    if frame is None:
        return ()
    options = unit_loss_options(state, player)
    if not options:
        return (
            DomainAction(action_id="resolve_unit_loss_without_unit", actor=player),
        )
    return tuple(
        DomainAction(
            action_id="lose_unit",
            actor=player,
            arguments=(
                *((("commanders", 1),) if commander else ()),
                ("zone", zone),
            ),
        )
        for zone, commander in options
    )


def apply_unit_loss(state: GameState, action: DomainAction) -> RuleResult:
    """Lose one unit from the chosen zone, or confirm there is none, and close
    the frame."""

    if action not in legal_unit_loss_actions(state, action.actor):
        raise ValueError("action is not a legal unit loss choice")
    frame = state.decision_stack[-1]
    source = context_str(dict(frame.context), "source", owner="Unit loss frame")
    if action.action_id == "resolve_unit_loss_without_unit":
        # Nothing to lose: the public event now comes from the seat's own
        # confirm instead of the card player's step.
        return RuleResult(
            state=state.pop_decision(),
            events=(
                GameEvent(
                    event_id=f"{source}:none",
                    kind="unit_loss_unavailable",
                    payload=(("player", action.actor),),
                ),
            ),
        )
    arguments = dict(action.arguments)
    zone = str(arguments["zone"])
    commander = arguments.get("commanders") == 1
    return lose_unit(
        state.pop_decision(), action.actor, zone, commander=commander, source=source
    )
