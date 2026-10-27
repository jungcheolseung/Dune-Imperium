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

Gun Thopter's "each opponent loses one garrisoned troop" asks the same
window with the choice limited to the garrison (``GARRISON_ONLY_KEY`` in the
frame's context, ``frame_garrison_only``): an opponent with no garrisoned
troop is unaffected [FAQ p. 2] and confirms it like any seat with nothing to
lose. Double Cross's "an opponent of your choice loses one troop in the
Conflict" asks one chosen opponent, with the choice limited to the Conflict
(``CONFLICT_ONLY_KEY``, ``frame_conflict_only``).
"""

from copy import replace
from enum import StrEnum
from typing import Final

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.action_shapes import PRINTER_KEY
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

# The frame context key of a window limited to the garrison (Gun Thopter);
# absent from every other unit-loss frame.
GARRISON_ONLY_KEY: Final = "garrison_only"
# The frame context key of a window limited to the Conflict (Double Cross);
# absent from every other unit-loss frame.
CONFLICT_ONLY_KEY: Final = "conflict_only"

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


def frame_garrison_only(frame: DecisionFrame) -> bool:
    """Whether the unit-loss ``frame`` limits the loss to the garrison."""

    return dict(frame.context).get(GARRISON_ONLY_KEY) is True


def frame_conflict_only(frame: DecisionFrame) -> bool:
    """Whether the unit-loss ``frame`` limits the loss to the Conflict."""

    return dict(frame.context).get(CONFLICT_ONLY_KEY) is True


def unit_loss_candidates(
    *, garrison_only: bool = False, conflict_only: bool = False
) -> tuple[tuple[str, bool], ...]:
    """The (zone, commander) pairs a window lists, in its order."""

    return tuple(
        (zone, commander)
        for zone, commander in UNIT_LOSS_CANDIDATES
        if not (garrison_only and zone != "garrison")
        and not (conflict_only and zone != "conflict")
    )


def unit_loss_options(
    state: GameState,
    player: int,
    *,
    garrison_only: bool = False,
    conflict_only: bool = False,
) -> tuple[tuple[str, bool], ...]:
    """Return the (zone, commander) pairs the player can lose a unit from."""

    owner = state.players[player]
    return tuple(
        (zone, commander)
        for zone, commander in unit_loss_candidates(
            garrison_only=garrison_only, conflict_only=conflict_only
        )
        if unit_loss_block(owner, zone, commander=commander) is None
    )


def opponents_with_conflict_troop(state: GameState, actor: int) -> tuple[int, ...]:
    """The opponents of ``actor`` that have a troop in the Conflict, clockwise
    from the next seat: those who can lose one there (Double Cross's official
    condition, [FAQ p. 2]; a Sardaukar Commander is a troop [Bloodlines p. 4])."""

    return tuple(
        seat
        for seat in opponent_seats(state, actor)
        if unit_loss_options(state, seat, conflict_only=True)
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
    printer: str,
    garrison_only: bool = False,
    conflict_only: bool = False,
    seats: tuple[int, ...] | None = None,
) -> RuleResult:
    """Push one unit-loss decision for every opponent of ``actor``;
    ``printer`` is the card that makes them lose it
    (``action_shapes.printer_value``; stage B3d-3); ``garrison_only``
    limits each loss to the garrison (Gun Thopter), ``conflict_only`` to the
    Conflict (Double Cross) and ``seats`` to the opponents named (the one
    Double Cross's owner chose), still clockwise from the next seat.

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
                    (
                        "Choose a garrisoned unit to lose"
                        if garrison_only
                        else "Choose a unit in the Conflict to lose"
                        if conflict_only
                        else "Choose where to lose one unit"
                    )
                    if unit_loss_options(
                        state,
                        seat,
                        garrison_only=garrison_only,
                        conflict_only=conflict_only,
                    )
                    else "No unit to lose"
                ),
            ),
            # A context is sorted by name: ``conflict_only`` and
            # ``garrison_only`` come first.
            context=(
                *(((CONFLICT_ONLY_KEY, True),) if conflict_only else ()),
                *(((GARRISON_ONLY_KEY, True),) if garrison_only else ()),
                ("player", seat),
                (PRINTER_KEY, printer),
                ("source", f"{source}:unit_loss:{seat}"),
            ),
        )
        for seat in (
            opponent_seats(state, actor)
            if seats is None
            else tuple(seat for seat in opponent_seats(state, actor) if seat in seats)
        )
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
    options = unit_loss_options(
        state,
        player,
        garrison_only=frame_garrison_only(frame),
        conflict_only=frame_conflict_only(frame),
    )
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

    if state.decision_stack and (
        state.decision_stack[-1].kind == FrameKind.OPPONENT_CARD_DISCARD
    ):
        # Test of Humanity's window offers the loss of a deployed troop beside
        # the discard; the window's own handler closes it, as for a discard.
        # Read at call time: ``rules.agent_effects`` imports this module.
        from dune_imperium.rules.agent_effects import apply_opponent_card_discard

        return apply_opponent_card_discard(state, action)
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
