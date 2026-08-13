"""Automatic transitions between top-level Uprising round phases."""

from dataclasses import replace

from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState


def begin_round(state: GameState) -> RuleResult:
    """Reveal a Conflict, draw five cards each, and open the first turn.

    This transition covers a Round Start for which every player already has at
    least five cards in their draw deck. A later chance-backed transition will
    handle reshuffling a discard pile when a draw crosses the deck boundary.
    """

    if state.phase is not GamePhase.ROUND_START:
        raise ValueError("a round can begin only during the Round Start phase")
    if state.first_player is None:
        raise ValueError("a round requires a First Player")
    if state.decision_stack:
        raise ValueError("Round Start cannot begin with a pending decision")
    if not state.conflict_deck:
        raise ValueError("a round cannot begin without a Conflict card")
    if any(len(player.deck) < 5 for player in state.players):
        raise ValueError("Round Start draw requires a discard reshuffle transition")

    round_number = state.round_number + 1
    conflict_id = state.conflict_deck[0]
    players = tuple(_draw_five(player) for player in state.players)
    first_turn = DecisionFrame(
        frame_id=f"round:{round_number}:turn:{state.first_player}",
        decision=PlayerDecision(
            owner=state.first_player,
            prompt="Choose an Agent turn or Reveal turn",
        ),
        context=(
            ("round", round_number),
            ("turn_owner", state.first_player),
        ),
    )
    next_state = replace(
        state,
        phase=GamePhase.PLAYER_TURNS,
        round_number=round_number,
        players=players,
        conflict_deck=state.conflict_deck[1:],
        current_conflict_ids=(*state.current_conflict_ids, conflict_id),
        decision_stack=(first_turn,),
    )
    events = (
        GameEvent(
            event_id=f"round:{round_number}:conflict",
            kind="conflict_revealed",
            payload=(("conflict_id", conflict_id), ("round", round_number)),
        ),
        *(
            GameEvent(
                event_id=f"round:{round_number}:player:{player.player_id}:draw",
                kind="cards_drawn",
                payload=(("count", 5), ("player", player.player_id)),
                visible_to=(player.player_id,),
            )
            for player in players
        ),
    )
    return RuleResult(state=next_state, events=events)


def _draw_five(player: PlayerState) -> PlayerState:
    return replace(
        player,
        deck=player.deck[5:],
        hand=(*player.hand, *player.deck[:5]),
    )
