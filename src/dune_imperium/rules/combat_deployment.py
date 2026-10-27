"""Troop deployment during a Combat-space Agent turn (OQ-029).

The basic deployment of an Agent turn is adjustable until the turn ends
(project convention OQ-029, ``docs/rules/player-turns.md``): ``deploy_troops``
adds troops to this turn's deployment, ``withdraw_troops`` returns troops
deployed this turn to the garrison, and ``finish_agent_turn`` closes the turn
once every other pending effect has been resolved. The net deployment of the
turn never exceeds "every troop recruited this turn plus two garrison troops"
[Main p. 10] [FAQ p. 4], and a withdrawal may not drop the turn's deployed
unit count below a condition a played card already used (Distraction,
Coercive Negotiation). A withdrawal undoes the deployment, so it also lowers
the turn's deployment peak those cards read (``record_deployment_peak``).
A card or Leader effect that retreats or loses units from the Conflict does
not undo anything: the units it moves have used their deployment, so only a
withdrawal gives room back (OQ-029, user ruling 2026-10-04,
``reconcile_deployment_after_retreat``).

Bloodlines Sardaukar Commanders are "troops" for this purpose [Bloodlines
p. 4] (``deploy_commanders`` / ``withdraw_commanders``; the frame tracks the
Commander share separately so a withdrawal returns the right kind of unit).
Each unit recruited this turn reserves a deploy slot for its own kind: a
recruited Commander's slot is filled only by a Commander and a recruited
troop's only by a troop, and the garrison extra (normally two) is shared by
both kinds on top of those (user ruling OQ-070, ``deployment_rooms``).
"""

from collections.abc import Mapping
from copy import replace
from dataclasses import dataclass
from typing import Final

from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules import turn_rows
from dune_imperium.rules.effects import (
    agent_turn_has_other_pending_effects,
    close_agent_turn,
    current_agent_effect_context,
)
from dune_imperium.rules.frames import (
    COMMANDERS_RECRUITED_KEY,
    FrameKind,
    owes_held_draw,
    owes_track_spy,
    own_turn_frame_index,
    recruited_commander_count,
    replace_player,
    with_context,
)

# Agent-turn effect frame keys while the turn end runs its Usurp trash
# (OQ-095 (4)-(5)): the press happened, the window the turn had for Combat
# deployment, and the units recruited by then.
FINISHING_KEY: Final = "finishing"
FINISH_DEPLOYMENT_KEY: Final = "finish_deployment_window"
FINISH_RECRUITS_KEY: Final = "finish_recruited_units"

# Agent-turn effect frame keys for the Combat deployment (absent means none).
# ``combat_troops_deployed`` counts every unit the turn's basic deployment
# moved (its allowance used) and ``combat_commanders_deployed`` the
# Commander share of it; only a withdrawal lowers them. The withdrawable
# pair counts the same units still eligible for a withdrawal, in the same
# shape, and a card retreat or loss lowers it too (OQ-029, user ruling
# 2026-10-04).
DEPLOYED_UNITS_KEY: Final = "combat_troops_deployed"
DEPLOYED_COMMANDERS_KEY: Final = "combat_commanders_deployed"
WITHDRAWABLE_UNITS_KEY: Final = "combat_troops_withdrawable"
WITHDRAWABLE_COMMANDERS_KEY: Final = "combat_commanders_withdrawable"


# Harkonnen Advisor troops the supply could not give yet: the part of the
# seat's recruit shortfall (``PlayerState.ungained_troops``, OQ-030) that
# stays undeployable once the supply refills it (OQ-038, 2026-10-26).
# Kept beside ``undeployable_troops`` in the owner's turn frame; absent
# means none.
UNGAINED_UNDEPLOYABLE_KEY: Final = "undeployable_troops_ungained"


def undeployable_troops(context: dict[str, ActionValue]) -> int:
    """Return the garrison troops the turn's effects forbid deploying."""

    value = context.get("undeployable_troops", 0)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError("Agent-turn effect frame has invalid undeployable count")
    return value


def ungained_undeployable_troops(context: dict[str, ActionValue]) -> int:
    """Return the undeployable troops still waiting in the shortfall."""

    value = context.get(UNGAINED_UNDEPLOYABLE_KEY, 0)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError("turn frame has an invalid ungained undeployable count")
    return value


def refill_undeployable_troops(
    state: GameState,
    player: int,
    troops: int,
    *,
    ungained: int,
) -> tuple[GameState, int]:
    """Keep a refilled Harkonnen Advisor troop undeployable (OQ-038).

    "1 troop. You can't deploy this troop to the Conflict this turn."
    [Piter De Vries card]: the troop the supply could not give at once is
    still that troop when a later supply refill gives it (user ruling
    2026-10-26, "카드 문구대로", amending OQ-030's refill). Troops are
    indistinguishable, so a partial refill gives the deployable recruits
    first, as a garrison loss gives up the undeployable troop first.
    ``ungained`` is the seat's shortfall before this refill; returns the
    state and how many of the ``troops`` stay undeployable.
    """

    index = own_turn_frame_index(state, player)
    if index is None or troops < 1:
        return state, 0
    frame = state.decision_stack[index]
    context = dict(frame.context)
    waiting = min(ungained_undeployable_troops(context), ungained)
    deployable_waiting = ungained - waiting
    kept = min(waiting, max(0, troops - deployable_waiting))
    if not kept:
        return state, 0
    if waiting - kept:
        context[UNGAINED_UNDEPLOYABLE_KEY] = waiting - kept
    else:
        context.pop(UNGAINED_UNDEPLOYABLE_KEY, None)
    context["undeployable_troops"] = undeployable_troops(context) + kept
    return (
        replace(
            state,
            decision_stack=(
                *state.decision_stack[:index],
                replace(frame, context=tuple(sorted(context.items()))),
                *state.decision_stack[index + 1 :],
            ),
        ),
        kept,
    )


def undeployable_troops_this_turn(state: GameState, player: int) -> int:
    """Troops the player's open turn forbids deploying (OQ-038).

    The count lives in the owner's turn frame: the Agent-turn effect frame,
    the turn frame before the Agent is placed, or the Reveal frame (a
    Harkonnen Advisor troop from Servo-Receivers, OQ-062). Zero outside the
    owner's turn; every deployment that reads the garrison (basic
    deployment, Reveal Combat-icon deployment, Intrigue and Navigation
    "deploy from garrison" effects) must subtract this before judging what
    is possible.
    """

    index = own_turn_frame_index(state, player)
    if index is None:
        return 0
    return undeployable_troops(dict(state.decision_stack[index].context))


def release_undeployable_troops(
    state: GameState,
    player: int,
    count: int,
) -> GameState:
    """A garrison troop lost this turn counts as the undeployable one.

    Troops are indistinguishable, so a player who must lose a garrison
    troop while Harkonnen Advisor's troop sits there gives up that troop
    first and the deployable count returns to normal (OQ-038).
    """

    if count < 1:
        return state
    index = own_turn_frame_index(state, player)
    if index is None:
        return state
    frame = state.decision_stack[index]
    context = dict(frame.context)
    undeployable = undeployable_troops(context)
    if not undeployable:
        return state
    context["undeployable_troops"] = max(0, undeployable - count)
    return replace(
        state,
        decision_stack=(
            *state.decision_stack[:index],
            replace(frame, context=tuple(sorted(context.items()))),
            *state.decision_stack[index + 1 :],
        ),
    )


def deployment_rooms(
    *,
    troops_recruited: int,
    commanders_recruited: int,
    existing_limit: int,
    troops_deployed: int,
    commanders_deployed: int,
) -> tuple[int, int]:
    """Return how many more troops and Commanders the turn may still deploy.

    "Combat space에 들어간 turn에는 그 turn에 recruit한 troop을 원하는
    수만큼 deploy하고, 그와 별도로 garrison의 troop을 최대 두 개 더
    deploy할 수 있다" [Main p. 10] (docs/rules/player-turns.md:136); a
    Commander is a "troop" worth 2 strength [Bloodlines p. 4]. User ruling
    2026-09-26 (OQ-070): "commander 소집했으면 커맨더를 배치해야지, troop이
    그 배치 몫을 차지하면 안 되지". So each unit recruited this turn
    reserves a slot for its own kind, and ``existing_limit`` more units of
    either kind may come from the garrison: a deployment is legal iff
    ``max(0, t - R_t) + max(0, c - R_c) <= existing_limit``. Each room is
    the kind's own unfilled recruit slots plus the unused garrison extra;
    availability (garrison contents, undeployable troops) is the caller's.
    """

    troop_excess = max(0, troops_deployed - troops_recruited)
    commander_excess = max(0, commanders_deployed - commanders_recruited)
    shared = max(0, existing_limit - troop_excess - commander_excess)
    return (
        max(0, troops_recruited - troops_deployed) + shared,
        max(0, commanders_recruited - commanders_deployed) + shared,
    )


@dataclass(frozen=True, slots=True)
class _Deployment:
    """The open Agent-turn deployment window's counters."""

    context: dict[str, ActionValue]
    troop_room: int
    commander_room: int
    withdrawable_troops: int
    withdrawable_commanders: int


def _unit_count(context: dict[str, ActionValue], key: str) -> int:
    """Read one of the deployment counters (absent means none)."""

    value = context.get(key, 0)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"Agent-turn effect frame has invalid {key}")
    return value


def _shares(
    context: dict[str, ActionValue], units_key: str, commanders_key: str
) -> tuple[int, int]:
    """Split a (units, Commander share) counter pair into troops and Commanders."""

    commanders = _unit_count(context, commanders_key)
    return max(0, _unit_count(context, units_key) - commanders), commanders


def _deployment_context(
    state: GameState,
    player: int,
) -> _Deployment | None:
    """Return the open deployment window's counters, or None."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return None
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return None
    if context["pending_combat_deployment"] is not True:
        return None
    recruited = context["troops_recruited"]
    if isinstance(recruited, bool) or not isinstance(recruited, int):
        raise RuntimeError("Agent-turn effect frame has invalid recruit count")
    # And the troops an Influence track bonus recruited this turn.
    recruited += state.players[player].track_troops_recruited_turn
    existing_limit = context.get("existing_troop_deployment_limit")
    if isinstance(existing_limit, bool) or not isinstance(existing_limit, int):
        raise RuntimeError("Agent-turn effect frame has invalid deployment limit")
    # The room reads the allowance used, which a card retreat or loss leaves
    # alone (OQ-029, ``reconcile_deployment_after_retreat``).
    troops, commanders = _shares(context, DEPLOYED_UNITS_KEY, DEPLOYED_COMMANDERS_KEY)
    troop_room, commander_room = deployment_rooms(
        troops_recruited=recruited,
        commanders_recruited=recruited_commander_count(
            context, COMMANDERS_RECRUITED_KEY
        ),
        existing_limit=existing_limit,
        troops_deployed=troops,
        commanders_deployed=commanders,
    )
    withdrawable_troops, withdrawable_commanders = _shares(
        context, WITHDRAWABLE_UNITS_KEY, WITHDRAWABLE_COMMANDERS_KEY
    )
    return _Deployment(
        context,
        troop_room,
        commander_room,
        withdrawable_troops,
        withdrawable_commanders,
    )


def legal_combat_deployments(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Enumerate the troop counts that may still be added to this deployment.

    A Commander recruited this turn keeps its slot for a Commander; the
    troops take their own recruit slots and the shared garrison extra
    (OQ-070, ``deployment_rooms``).
    """

    found = _deployment_context(state, player)
    if found is None:
        return ()
    # Harkonnen Advisor's troop "can't be deployed to the Conflict this
    # turn": it sits in the garrison but is not available [Piter De Vries
    # card] (OQ-038).
    garrison = max(
        0, state.players[player].troops_garrison - undeployable_troops(found.context)
    )
    maximum = min(garrison, found.troop_room)
    return tuple(
        DomainAction(
            action_id="deploy_troops",
            actor=player,
            arguments=(("count", count),),
        )
        for count in range(1, maximum + 1)
    )


def legal_commander_deployments(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Enumerate the Sardaukar Commander counts that may still deploy.

    A Commander is a "troop" [Bloodlines p. 4]: every Commander recruited
    this turn may deploy, and a garrison Commander may be one of the "up to
    two" garrison units [Bloodlines p. 4] [Main p. 10]. The recruit slots
    are kept per kind -- a Commander recruited this turn reserves its slot
    for a Commander and a recruited troop's slot is never a Commander's --
    while the garrison extra is shared with the troops (user ruling OQ-070,
    ``deployment_rooms``).
    """

    if not state.config.bloodlines:
        return ()
    found = _deployment_context(state, player)
    if found is None:
        return ()
    garrison = state.players[player].commanders_garrison
    maximum = min(garrison, found.commander_room)
    return tuple(
        DomainAction(
            action_id="deploy_commanders",
            actor=player,
            arguments=(("count", count),),
        )
        for count in range(1, maximum + 1)
    )


def legal_troop_withdrawals(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Enumerate how many of this turn's deployed troops may return (OQ-029).

    Only troops of the turn's basic deployment that no card retreat or loss
    has taken since (``reconcile_deployment_after_retreat``) are offered.
    """

    found = _deployment_context(state, player)
    if found is None:
        return ()
    owner = state.players[player]
    # A deployment condition a played card used (Distraction, Coercive
    # Negotiation) keeps its minimum deployed.
    # The units actually in the Conflict bound this too: a troop deployed this
    # turn can leave it again before the turn closes, and "when you lose a
    # troop, return it to your supply (not your garrison)"
    # [Dune: Imperium Rules 2020-10-26 p. 16], so the frame's deployment count
    # outruns the Conflict. A withdrawal acts on what is there when it
    # resolves, the way a recruit does (OQ-030); offering more advertised a
    # move that drove the seat's troops negative (2026-09-10 soak, seed 34).
    maximum = min(
        found.withdrawable_troops,
        owner.units_deployed_turn - owner.units_deployed_committed,
        owner.troops_conflict,
    )
    return tuple(
        DomainAction(
            action_id="withdraw_troops",
            actor=player,
            arguments=(("count", count),),
        )
        for count in range(1, maximum + 1)
    )


def legal_commander_withdrawals(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Enumerate how many of this turn's deployed Commanders may return."""

    if not state.config.bloodlines:
        return ()
    found = _deployment_context(state, player)
    if found is None:
        return ()
    owner = state.players[player]
    # Bounded by the Commanders actually in the Conflict, for the same reason
    # the troop withdrawal is: Bloodlines loses a Commander from the garrison
    # or the Conflict [Bloodlines Rules p. 8].
    maximum = min(
        found.withdrawable_commanders,
        owner.units_deployed_turn - owner.units_deployed_committed,
        owner.commanders_conflict,
    )
    return tuple(
        DomainAction(
            action_id="withdraw_commanders",
            actor=player,
            arguments=(("count", count),),
        )
        for count in range(1, maximum + 1)
    )


def agent_turn_is_finishing(context: dict[str, ActionValue]) -> bool:
    """Whether the owner already pressed the end and its own steps still run.

    Every ``finish_agent_turn`` press puts its turn in this state
    (``FINISHING_KEY``): what the press leaves behind (a Usurp trash's
    follow-ups, a Skill or Navigation choice, a reshuffle, an owed Emperor
    track Spy) resolves on top of the frame, and
    ``settle_finishing_agent_turn`` then closes or reopens it. A press that
    leaves nothing is settled in the same transition.
    """

    return context.get(FINISHING_KEY) is True


def legal_agent_turn_finish_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer the explicit turn end once no mandatory group is pending.

    Every Agent turn ends only here, whether or not anything optional is
    left (user ruling OQ-095); the Combat deployment window stays open until
    the press (OQ-029). An optional effect left unused does not hold the end
    back -- "'턴 종료'는 의무 효과가 모두 끝났을 때만 제시된다" (OQ-095 (2)), and
    "may", an arrow cost or a black trash icon is optional [FAQ p. 3] --
    and the press lapses it (user ruling 2026-10-14). The end is also offered
    when the only other pending group is a mandatory Agent box that can only
    fizzle (its condition is false and nothing else of the turn remains to
    meet it): the box waits for the turn's end rather than fizzling on
    demand (designer ruling, OQ-057). An Emperor track Spy the owner still
    owes holds the end back: it is placed in any order but before the turn
    ends (user ruling
    2026-10-04, "엄연히 agent턴 내에 순서를 정해서 할 수 있는 의무 행동").
    """

    from dune_imperium.rules.agent_effects import pending_boxes_hold_the_end

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if agent_turn_is_finishing(context):
        return ()
    if owes_track_spy(state, player) or turn_rows.tech_acquire_effects_hold_the_end(
        context, state.players[player]
    ):
        # An owed Tech acquire icon holds the end (OQ-098), but not an
        # Influence with every Faction at the top: the press lapses it
        # (cleanup-2b, ``turn_rows.lapse``).
        return ()
    if turn_rows.holds_the_end(state, player):
        # c6r6's Influence waiting on the turn, with a Faction it can raise
        # (cleanup-2b): taking it is mandatory.
        return ()
    if owes_held_draw(state, player):
        # A triggered draw waits as its own step and is taken before the
        # turn ends (user ruling 2026-10-10, OQ-106).
        return ()
    # Every Agent box still pending -- both of a graft, each judged with
    # itself active -- is optional now (the press lapses it, user ruling
    # 2026-10-14) or can only fizzle (OQ-057 (1)).
    if agent_turn_has_other_pending_effects(
        context,
        state.players,
        ignore_agent_effect=not pending_boxes_hold_the_end(state),
    ):
        return ()
    return (DomainAction(action_id="finish_agent_turn", actor=player),)


def _count_argument(action: DomainAction) -> int:
    count = dict(action.arguments)["count"]
    if isinstance(count, bool) or not isinstance(count, int):
        raise ValueError("deployment count must be an integer")
    return count


def _move_troops(
    state: GameState,
    context: dict[str, ActionValue],
    player: int,
    delta: int,
    *,
    commanders: bool = False,
) -> GameState:
    """Move ``delta`` units garrison→Conflict (negative: back) and keep the frame.

    A deployment adds to both the allowance used and the withdrawable count;
    a withdrawal undoes the deployment, so it lowers both and gives its room
    back (OQ-029; the keys are described at ``DEPLOYED_UNITS_KEY``).
    """

    owner = state.players[player]
    # A withdrawal undoes the deployment (OQ-029), so the turn's deployment
    # peak drops with it; a deployment raises the peak through
    # ``record_deployment_peak`` once the transition settles. Lowering it by
    # the withdrawn count never overstates the peak; after a retreat it can
    # understate it (withdrawing a unit deployed after the retreat), a
    # recorded project convention (OQ-016).
    peak = (
        max(owner.units_deployed_turn + delta, owner.units_deployed_peak + delta)
        if delta < 0
        else owner.units_deployed_peak
    )
    if commanders:
        next_owner = replace(
            owner,
            commanders_garrison=owner.commanders_garrison - delta,
            commanders_conflict=owner.commanders_conflict + delta,
            units_deployed_turn=owner.units_deployed_turn + delta,
            units_deployed_peak=peak,
        )
        for key in (DEPLOYED_COMMANDERS_KEY, WITHDRAWABLE_COMMANDERS_KEY):
            context[key] = _unit_count(context, key) + delta
    else:
        next_owner = replace(
            owner,
            troops_garrison=owner.troops_garrison - delta,
            troops_conflict=owner.troops_conflict + delta,
            units_deployed_turn=owner.units_deployed_turn + delta,
            units_deployed_peak=peak,
        )
    players = tuple(
        next_owner if seat.player_id == player else seat for seat in state.players
    )
    for key in (DEPLOYED_UNITS_KEY, WITHDRAWABLE_UNITS_KEY):
        context[key] = _unit_count(context, key) + delta
    frame = state.decision_stack[-1]
    next_frame = replace(frame, context=tuple(sorted(context.items())))
    return replace(
        state,
        players=players,
        decision_stack=(*state.decision_stack[:-1], next_frame),
    )


def apply_combat_deployment(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Add the selected troop count to this turn's Conflict deployment."""

    if action not in legal_combat_deployments(state, action.actor):
        raise ValueError("action is not a legal Combat deployment")
    count = _count_argument(action)
    _, context = current_agent_effect_context(state)
    next_state = _move_troops(state, context, action.actor, count)
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{action.actor}:deploy_troops:"
            f"{next_state.players[action.actor].units_deployed_turn}"
        ),
        kind="troops_deployed",
        payload=(("count", count), ("player", action.actor)),
    )
    return RuleResult(state=next_state, events=(event,))


def reconcile_deployment_after_retreat(
    state: GameState,
    player: int,
    *,
    troops: int,
    commanders: int = 0,
) -> GameState:
    """Follow a card retreat or loss from the Conflict in the turn's counters.

    A Signet Ring, a Plot Intrigue or an Agent box may retreat or lose units
    the turn's basic deployment just moved (Fedaykin Maneuver, a Twisted
    Intrigue cost, Piter, Genius Advisor). The withdrawal window offers only
    units still there, so its counters follow the retreat down. The basic
    deployment allowance does not come back: "You may deploy any or all
    units recruited during your current turn ..., plus up to two more units
    from your garrison." [Main p. 10]; "you can't 're-recruit' troops in
    your garrison to get around the limit of deploying up to two troops from
    your garrison" [FAQ p. 4] (OQ-029, user ruling 2026-10-04, "되돌리지
    않음"). Only a withdrawal (``_move_troops``) undoes a deployment and
    frees its room. A Reveal turn's Combat-icon deployment
    (``reveal_units_deployed``) never shrinks either.

    The per-turn deployment count also drops, never below the count a
    played card already used (OQ-029); the turn's peak stays, as the
    deployment it records did happen (``record_deployment_peak``, OQ-016).

    Each kind's withdrawable share shrinks only by its own retreated units:
    a retreated troop (perhaps one deployed in an earlier turn) never takes
    a Commander out of the window (user ruling OQ-070).
    """

    total = troops + commanders
    if total < 1:
        return state
    owner = state.players[player]
    players = replace_player(
        state.players,
        replace(
            owner,
            # Floored at the count a played card used, but a retreat never
            # raises it: a card may have been played off the turn's peak with
            # fewer units left in the Conflict (OQ-016).
            units_deployed_turn=max(
                min(owner.units_deployed_committed, owner.units_deployed_turn),
                owner.units_deployed_turn - total,
            ),
        ),
    )
    frames = list(state.decision_stack)
    for index in range(len(frames) - 1, -1, -1):
        frame = frames[index]
        if frame.kind != FrameKind.AGENT_EFFECTS or not isinstance(
            frame.decision, PlayerDecision
        ):
            continue
        if frame.decision.owner != player:
            continue
        context = dict(frame.context)
        troop_share, commander_share = _shares(
            context, WITHDRAWABLE_UNITS_KEY, WITHDRAWABLE_COMMANDERS_KEY
        )
        if not troop_share and not commander_share:
            break
        next_commanders = max(0, commander_share - commanders)
        context[WITHDRAWABLE_UNITS_KEY] = (
            max(0, troop_share - troops) + next_commanders
        )
        context[WITHDRAWABLE_COMMANDERS_KEY] = next_commanders
        frames[index] = replace(frame, context=tuple(sorted(context.items())))
        break
    return replace(state, players=players, decision_stack=tuple(frames))


def apply_troop_withdrawal(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Return troops deployed this turn from the Conflict to the garrison."""

    if action not in legal_troop_withdrawals(state, action.actor):
        raise ValueError("action is not a legal troop withdrawal")
    count = _count_argument(action)
    _, context = current_agent_effect_context(state)
    next_state = _move_troops(state, context, action.actor, -count)
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{action.actor}:withdraw_troops:"
            f"{next_state.players[action.actor].units_deployed_turn}"
        ),
        kind="troops_withdrawn",
        payload=(("count", count), ("player", action.actor)),
    )
    return RuleResult(state=next_state, events=(event,))


def apply_commander_deployment(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Add the selected Sardaukar Commander count to this turn's deployment."""

    if action not in legal_commander_deployments(state, action.actor):
        raise ValueError("action is not a legal Commander deployment")
    count = _count_argument(action)
    _, context = current_agent_effect_context(state)
    next_state = _move_troops(state, context, action.actor, count, commanders=True)
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{action.actor}:deploy_commanders:"
            f"{next_state.players[action.actor].units_deployed_turn}"
        ),
        kind="commanders_deployed",
        payload=(("count", count), ("player", action.actor)),
    )
    return RuleResult(state=next_state, events=(event,))


def apply_commander_withdrawal(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Return Commanders deployed this turn from the Conflict to the garrison."""

    if action not in legal_commander_withdrawals(state, action.actor):
        raise ValueError("action is not a legal Commander withdrawal")
    count = _count_argument(action)
    _, context = current_agent_effect_context(state)
    next_state = _move_troops(state, context, action.actor, -count, commanders=True)
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{action.actor}:withdraw_commanders:"
            f"{next_state.players[action.actor].units_deployed_turn}"
        ),
        kind="commanders_withdrawn",
        payload=(("count", count), ("player", action.actor)),
    )
    return RuleResult(state=next_state, events=(event,))


def open_combat_deployment(context: dict[str, ActionValue]) -> None:
    """Open an Agent turn's basic deployment as though at a Combat space,
    the garrison share capped at two whatever the number of icons
    [Bloodlines p. 5], in the owner's Agent-turn effect frame ``context``;
    nothing while Emperor of the Known Universe blocks the turn's
    deployment [Main p. 17]."""

    if context.get("units_deploy_blocked") is True:
        return
    context["pending_combat_deployment"] = True
    limit = context.get("existing_troop_deployment_limit", 0)
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise RuntimeError("Agent-turn effect frame has invalid deployment limit")
    context["existing_troop_deployment_limit"] = max(limit, 2)


RECRUITS_DEPLOYABLE_KEY = "reveal_recruits_deployable"
"""Troops a ``DeployTheseTroops`` line recruited in the owner's Reveal turn
(the original game's Gurney Halleck, Reinforcements): that many may be
deployed from the garrison (absent means none)."""


def grant_recruit_deployment(state: GameState, player: int, count: int) -> GameState:
    """Let ``player`` deploy ``count`` troops a line just recruited, "You may
    deploy these troops to the Conflict", when it is their Reveal turn; in
    their Agent turn the troops deploy by the Combat space rule [DI p. 10]
    [FAQ p. 4] and nothing opens here."""

    for index in range(len(state.decision_stack) - 1, -1, -1):
        frame = state.decision_stack[index]
        if not isinstance(frame.decision, PlayerDecision) or (
            frame.decision.owner != player
        ):
            continue
        if frame.kind == FrameKind.REVEAL:
            context = dict(frame.context)
            context[RECRUITS_DEPLOYABLE_KEY] = recruits_deployable(context) + count
            return replace(
                state,
                decision_stack=(
                    *state.decision_stack[:index],
                    replace(frame, context=tuple(sorted(context.items()))),
                    *state.decision_stack[index + 1 :],
                ),
            )
        if frame.kind in (FrameKind.TURN, FrameKind.AGENT_EFFECTS):
            break
    return state


def recruits_deployable(context: Mapping[str, object]) -> int:
    """The troops ``DeployTheseTroops`` lines opened in a Reveal frame."""

    value = context.get(RECRUITS_DEPLOYABLE_KEY, 0)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"Reveal frame has invalid {RECRUITS_DEPLOYABLE_KEY}")
    return value


def grant_combat_icon(state: GameState, player: int) -> GameState:
    """Let ``player`` deploy this turn as if at a Combat space [Bloodlines p. 5].

    Inside the owner's Agent-turn effect frame the basic deployment window
    opens (or stays open) with the garrison share capped at two whatever
    the number of icons; inside the owner's Reveal frame the Reveal-turn
    deployment opens (``reveal_turn``); before the placement the flag waits
    on the seat for the placement to read. Emperor of the Known Universe
    still blocks deployment for the turn [Main p. 17].
    """

    for index in range(len(state.decision_stack) - 1, -1, -1):
        frame = state.decision_stack[index]
        if not isinstance(frame.decision, PlayerDecision) or (
            frame.decision.owner != player
        ):
            continue
        if frame.kind == FrameKind.AGENT_EFFECTS:
            context = dict(frame.context)
            if context.get("units_deploy_blocked") is True:
                return state
            open_combat_deployment(context)
            return replace(
                state,
                decision_stack=(
                    *state.decision_stack[:index],
                    replace(frame, context=tuple(sorted(context.items()))),
                    *state.decision_stack[index + 1 :],
                ),
            )
        if frame.kind == FrameKind.REVEAL:
            context = dict(frame.context)
            context["combat_deployment"] = True
            return replace(
                state,
                decision_stack=(
                    *state.decision_stack[:index],
                    replace(frame, context=tuple(sorted(context.items()))),
                    *state.decision_stack[index + 1 :],
                ),
            )
        if frame.kind == FrameKind.TURN:
            break
    owner = state.players[player]
    return (
        replace(
            state,
            players=tuple(
                replace(seat, combat_icon_turn=True)
                if seat.player_id == player
                else seat
                for seat in state.players
            ),
        )
        if not owner.combat_icon_turn
        else state
    )


def apply_agent_turn_finish(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """End the Agent turn: the owner's one press (user ruling OQ-095).

    In order: optional effects left unused lapse (user ruling 2026-10-14),
    a mandatory Agent box that could only fizzle fizzles (OQ-057),
    a held Contract icon fizzles (OQ-059), the turn's end is announced, the
    Combat deployment window closes, and a Usurped Row card is trashed
    ("trash that card at the end of your turn.", OQ-054). The frame then waits
    as ``FINISHING_KEY``: ``settle_finishing_agent_turn`` closes the turn, or
    reopens it, once whatever the press left behind has resolved -- in the
    same transition when it left nothing.
    """

    from dune_imperium.rules.agent_effects import (
        agent_card_effect_is_unavailable,
        fizzle_pending_agent_icons,
        lapse_optional_boxes,
        resolve_agent_card_effect,
    )
    from dune_imperium.rules.board_effects import lapse_optional_board_effects
    from dune_imperium.rules.contracts import fizzle_held_contract_icons
    from dune_imperium.rules.effects import pending_agent_icons
    from dune_imperium.rules.graft import trash_usurped_card
    from dune_imperium.rules.graft_boxes import swap_boxes

    if action not in legal_agent_turn_finish_actions(state, action.actor):
        raise ValueError("the Agent turn cannot be finished yet")
    player = action.actor
    # Optional effects the owner left unused lapse with the press (user
    # ruling 2026-10-14, OQ-095 (2)): the turn's Agent boxes, then the
    # visited space's optional icons and the Leader's optional repeat.
    lapsed = lapse_optional_boxes(state)
    lapsed_board = lapse_optional_board_effects(lapsed.state, player)
    # So do the research bonuses waiting on the turn (cleanup-2b).
    lapsed_rows = turn_rows.lapse(lapsed_board.state, player)
    working = lapsed_rows.state
    events: list[GameEvent] = [
        *lapsed.events,
        *lapsed_board.events,
        *lapsed_rows.events,
    ]
    for _ in range(4):
        # Mandatory boxes that could not be met by the turn's end fizzle now
        # (OQ-057), the grafted partner's with its box made active.
        frame, context = current_agent_effect_context(working)
        if context["pending_agent_effect"] is True and (
            agent_card_effect_is_unavailable(working)
        ):
            # A box that resolves icon by icon retires every icon at once;
            # ``resolve_agent_card_effect`` only handles single-effect boxes.
            fizzled = (
                fizzle_pending_agent_icons(working)
                if pending_agent_icons(context)
                else resolve_agent_card_effect(working)
            )
            working = fizzled.state
            events.extend(fizzled.events)
            continue
        if context["pending_agent_effect"] is not True and (
            context.get("graft_pending_effect") is True
        ):
            swap_boxes(context)
            working = replace(
                working,
                decision_stack=(
                    *working.decision_stack[:-1],
                    with_context(frame, context),
                ),
            )
            continue
        break
    # A box left pending here was revived by the press itself: the first
    # grafted box's payment met the partner's condition. It is a mandatory
    # effect of this turn again (OQ-057 (1): "뒤에 뽑은 카드로 조건이 성립하면
    # box가 다시 의무가 된다"), so the settle below reopens the turn for it.
    source = f"round:{state.round_number}:player:{player}:finish_agent_turn"
    # A Contract icon that never found a token it could take fizzles with the
    # turn, without the two-Solari conversion (OQ-059).
    fizzled_contracts = fizzle_held_contract_icons(working, player, source=source)
    working = fizzled_contracts.state
    events.extend(fizzled_contracts.events)
    events.append(
        GameEvent(
            event_id=source,
            kind="agent_turn_finished",
            payload=(("player", player),),
        )
    )
    # The turn does not close here. It waits as finishing, and whatever the
    # press's own steps leave behind -- a Usurp trash's results (user ruling
    # 2026-10-01, OQ-095 (5)), the follow-ups of a box the press resolved
    # (Long Reach paying a Faction to a track bonus: an owed Emperor Spy, a
    # Skill or Navigation choice, a Friends Everywhere pick, a reshuffled
    # Intrigue draw) -- resolves on top of it, inside this turn (OQ-095 (3):
    # "마지막 효과가 남긴 Skill·Navigation 선택 ... Emperor track Influence 4의
    # Spy ... 등은 소유자의 열린 turn 위에서 풀리고"). Once the frame is back
    # on top, ``settle_finishing_agent_turn`` closes the turn or reopens it
    # (OQ-057 (15) re-ruling: "turn 종료를 누른 뒤 그 결과로 빚이 생기면
    # OQ-095 (5)처럼 turn이 다시 열린다"). A press that leaves nothing closes in
    # the same transition. Every press takes this one path, so no list of
    # follow-up kinds can fall behind the rules again (2026-10-08: the list
    # this replaced first missed the reshuffled draw).
    frame, context = current_agent_effect_context(working)
    deployment_window = context["pending_combat_deployment"] is True
    context["pending_combat_deployment"] = False
    context[FINISHING_KEY] = True
    context[FINISH_DEPLOYMENT_KEY] = deployment_window
    context[FINISH_RECRUITS_KEY] = _recruited_units(
        context, working.players[player]
    )
    working = replace(
        working,
        decision_stack=(*working.decision_stack[:-1], with_context(frame, context)),
    )
    if not working.players[player].usurped_row_card_id:
        return RuleResult(state=working, events=tuple(events))
    # Usurp: the borrowed card goes at the end of the turn, as an ordinary
    # trash whose results are still this turn's.
    trashed = trash_usurped_card(working, player)
    return RuleResult(state=trashed.state, events=(*events, *trashed.events))



def _recruited_units(context: dict[str, ActionValue], owner: PlayerState) -> int:
    troops = context["troops_recruited"]
    if isinstance(troops, bool) or not isinstance(troops, int):
        raise RuntimeError("Agent-turn effect frame has invalid recruit count")
    return (
        troops
        + owner.track_troops_recruited_turn
        + recruited_commander_count(context, COMMANDERS_RECRUITED_KEY)
    )


def settle_finishing_agent_turn(result: RuleResult) -> RuleResult:
    """Close a finishing Agent turn, or reopen it for what its end produced.

    Runs after every transition, once the press's own steps (a Usurp trash, a
    box the press resolved) and their follow-ups have resolved and the
    owner's frame is back on top -- in the press's own transition when they
    left nothing. Their results are the turn's own (user ruling 2026-10-01,
    OQ-095 (5)): when they make a
    snapshot Contract's condition true -- a Contract is always completed
    [FAQ p. 1] -- recruit units on a turn that could deploy -- "그 turn에
    recruit한 troop을 원하는 수만큼 deploy" [Main p. 10] -- or reach the
    Emperor track's Influence 4, whose Spy is a mandatory action of the turn
    (user ruling 2026-10-04), the turn reopens and the owner presses the end
    again. Otherwise the next seat's turn opens.
    """

    state = result.state
    if not state.decision_stack:
        return result
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.AGENT_EFFECTS or not isinstance(
        frame.decision, PlayerDecision
    ):
        return result
    context = dict(frame.context)
    if not agent_turn_is_finishing(context):
        return result
    owner = frame.decision.owner
    deployment_window = context.pop(FINISH_DEPLOYMENT_KEY) is True
    recruited_at_press = context.pop(FINISH_RECRUITS_KEY)
    del context[FINISHING_KEY]
    if isinstance(recruited_at_press, bool) or not isinstance(recruited_at_press, int):
        raise RuntimeError("finishing Agent-turn frame has invalid recruit count")
    # A reopened turn goes on as the same turn, so it has the deployment
    # window it had before the press (OQ-029): a unit recruited after the
    # reopen may still deploy.
    reopened = {**context, "pending_combat_deployment": deployment_window}
    reopened_state = replace(
        state,
        decision_stack=(*state.decision_stack[:-1], with_context(frame, reopened)),
    )
    recruited_more = (
        _recruited_units(context, state.players[owner]) > recruited_at_press
    )
    if (
        agent_turn_has_other_pending_effects(reopened, state.players)
        # An effect the press's own steps queued on the turn (a Contract an
        # Influence it gained completed, OQ-112 (4)) is the turn's own too,
        # never dropped unseen.
        or bool(turn_rows.pending(frame))
        or owes_track_spy(state, owner)
        or owes_held_draw(state, owner)
        or (
            recruited_more
            and (
                legal_combat_deployments(reopened_state, owner)
                or legal_commander_deployments(reopened_state, owner)
            )
        )
    ):
        return replace(
            result,
            state=reopened_state,
            events=(
                *result.events,
                GameEvent(
                    event_id=(
                        f"round:{state.round_number}:player:{owner}:agent_turn_reopened"
                    ),
                    kind="agent_turn_reopened",
                    payload=(("player", owner),),
                ),
            ),
        )
    closing = replace(
        state,
        decision_stack=(*state.decision_stack[:-1], with_context(frame, context)),
    )
    return replace(result, state=close_agent_turn(closing, owner))


def record_deployment_peak(result: RuleResult) -> RuleResult:
    """Raise each seat's turn deployment peak to its current count.

    "When you deploy three or more units to the Conflict in a single turn"
    [Distraction card; Coercive Negotiation card] is met at "a moment in
    time when there are 3 units in the conflict that were deployed to the
    conflict this turn, then that requirement becomes true" (Message from
    designer, adopted per OQ-057's rule; OQ-016). Runs after every applied
    transition, so a later retreat leaves the peak standing; the count and
    the peak both reset when the seat's next turn opens.
    """

    state = result.state
    players = tuple(
        replace(seat, units_deployed_peak=seat.units_deployed_turn)
        if seat.units_deployed_turn > seat.units_deployed_peak
        else seat
        for seat in state.players
    )
    if all(new is old for new, old in zip(players, state.players, strict=True)):
        return result
    return RuleResult(state=replace(state, players=players), events=result.events)
