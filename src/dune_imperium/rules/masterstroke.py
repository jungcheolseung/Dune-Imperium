"""Baron Vladimir Harkonnen's Masterstroke (the original game, stage P2b).

docs/rules/imperium-base.md 4, 12, 14 and 15, OQ-115: "At start of game,
secretly choose 2 Factions. When you deploy 4+ troops to the Conflict in a
turn, reveal your choices and gain one Influence with each." [Baron
Vladimir Harkonnen card]. The two Factions are chosen after every other
setup step, before the first round [FAQ p. 1], from four different tokens
[DI p. 13]; they are the Baron's alone until revealed (section 14). The
reveal is mandatory the first time it is due and happens once per game
(OQ-115, user ruling 2026-10-22): due when the troops deployed in his own
turn stand in the Conflict four together -- the turn's deployment peak that
Distraction and Coercive Negotiation read (OQ-016, OQ-029) -- after which a
withdrawal may not drop below four; a Faction at the top gains nothing
(OQ-060). The original game has neither sandworms nor dreadnoughts in this
stage, so the turn's unit peak is his troop count (Rise of Ix and the
combinations must count troops and Commanders apart, OQ-115).
"""

from copy import replace
from typing import Final

from dune_imperium.content.uprising.board import Faction
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.frames import (
    FrameKind,
    context_str,
    owned_top_frame,
    replace_player,
    turn_owner_of,
)
from dune_imperium.rules.influence import gain_faction_influence

BARON: Final = "baron_vladimir_harkonnen"
MASTERSTROKE_FACTIONS: Final = 2
MASTERSTROKE_TROOPS: Final = 4
CHOOSE_ACTION: Final = "choose_masterstroke_faction"


def assign_masterstroke(state: GameState) -> GameState:
    """Open the Baron's secret choice of two Factions, pausing the game in
    SETUP (like Kota Odax's Secret Project) until he has chosen."""

    seat = next(
        (
            candidate
            for candidate in state.players
            if candidate.leader_id == BARON and not candidate.masterstroke_factions
        ),
        None,
    )
    if seat is None:
        return state
    frame = DecisionFrame(
        kind=FrameKind.MASTERSTROKE_SETUP,
        frame_id=f"setup:masterstroke:{seat.player_id}",
        decision=PlayerDecision(
            owner=seat.player_id,
            prompt="Masterstroke: secretly choose two Factions",
        ),
        context=(
            ("player", seat.player_id),
            ("resume_phase", state.phase.value),
        ),
    )
    return replace(
        state, phase=GamePhase.SETUP, decision_stack=(*state.decision_stack, frame)
    )


def legal_masterstroke_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """Each Faction the Baron has not chosen yet (four tokens, so two
    different ones [DI p. 13])."""

    if owned_top_frame(state, FrameKind.MASTERSTROKE_SETUP, player) is None:
        return ()
    chosen = state.players[player].masterstroke_factions
    return tuple(
        DomainAction(
            action_id=CHOOSE_ACTION,
            actor=player,
            arguments=(("faction", faction.value),),
        )
        for faction in Faction
        if faction.value not in chosen
    )


def apply_masterstroke_choice(state: GameState, action: DomainAction) -> RuleResult:
    """Lay one chosen Faction face down on the Baron; the second closes the
    setup. Everyone sees that he chose, only he which (section 14)."""

    if action not in legal_masterstroke_actions(state, action.actor):
        raise ValueError("action is not a legal Masterstroke choice")
    frame = state.decision_stack[-1]
    faction = str(dict(action.arguments)["faction"])
    owner = state.players[action.actor]
    chosen = replace(
        owner, masterstroke_factions=(*owner.masterstroke_factions, faction)
    )
    count = len(chosen.masterstroke_factions)
    events = (
        GameEvent(
            event_id=f"{frame.frame_id}:chosen:{count}",
            kind="masterstroke_faction_chosen",
            payload=(("count", count), ("player", action.actor)),
        ),
        GameEvent(
            event_id=f"{frame.frame_id}:identity:{count}",
            kind="masterstroke_faction_identity",
            payload=(("faction", faction), ("player", action.actor)),
            visible_to=(action.actor,),
        ),
    )
    players = replace_player(state.players, chosen)
    if count < MASTERSTROKE_FACTIONS:
        return RuleResult(state=replace(state, players=players), events=events)
    resume = GamePhase(
        context_str(dict(frame.context), "resume_phase", owner="Masterstroke frame")
    )
    return RuleResult(
        state=replace(
            state,
            phase=resume,
            players=players,
            decision_stack=state.decision_stack[:-1],
        ),
        events=events,
    )


def masterstroke_is_due(state: GameState, player: int) -> bool:
    """Whether the Baron at ``player`` must reveal now: his own turn's
    deployed troops have stood four together in the Conflict."""

    seat = state.players[player]
    return (
        len(seat.masterstroke_factions) == MASTERSTROKE_FACTIONS
        and not seat.masterstroke_revealed
        and state.phase is GamePhase.PLAYER_TURNS
        and turn_owner_of(state) == player
        and max(seat.units_deployed_turn, seat.units_deployed_peak)
        >= MASTERSTROKE_TROOPS
    )


def reveal_masterstroke(result: RuleResult) -> RuleResult:
    """Reveal a due Masterstroke after a transition: both Factions face up,
    an Influence with each in the order chosen, and a withdrawal kept from
    dropping below four (OQ-029). Runs after the turn's deployment peak is
    recorded (``combat_deployment.record_deployment_peak``)."""

    state = result.state
    due = next(
        (
            seat.player_id
            for seat in state.players
            if masterstroke_is_due(state, seat.player_id)
        ),
        None,
    )
    if due is None:
        return result
    seat = state.players[due]
    revealed = replace(
        seat,
        masterstroke_revealed=True,
        units_deployed_committed=max(
            seat.units_deployed_committed, MASTERSTROKE_TROOPS
        ),
    )
    working = replace(state, players=replace_player(state.players, revealed))
    source = f"round:{state.round_number}:player:{due}:masterstroke"
    events: list[GameEvent] = [
        GameEvent(
            event_id=f"{source}:revealed",
            kind="masterstroke_revealed",
            payload=(
                ("factions", seat.masterstroke_factions),
                ("player", due),
            ),
        )
    ]
    for faction in seat.masterstroke_factions:
        gained = gain_faction_influence(
            working, due, Faction(faction), 1, event_prefix=f"{source}:{faction}"
        )
        working = gained.state
        events.extend(gained.events)
    return RuleResult(state=working, events=(*result.events, *events))
