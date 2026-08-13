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


def resolve_makers(state: GameState) -> RuleResult:
    """Add spice to every unoccupied Maker space and open Recall."""

    if state.phase is not GamePhase.MAKERS:
        raise ValueError("Makers can resolve only during the Makers phase")
    if state.decision_stack:
        raise ValueError("Makers cannot resolve with a pending decision")
    occupied = {
        space_id
        for player in state.players
        for space_id in player.agent_locations
    }
    maker_bonus_spice = tuple(
        (space_id, amount if space_id in occupied else amount + 1)
        for space_id, amount in state.maker_bonus_spice
    )
    next_state = replace(
        state,
        phase=GamePhase.RECALL_OR_ENDGAME,
        maker_bonus_spice=maker_bonus_spice,
    )
    events = tuple(
        GameEvent(
            event_id=f"round:{state.round_number}:maker:{space_id}",
            kind="maker_spice_added",
            payload=(("space_id", space_id),),
        )
        for space_id, _ in state.maker_bonus_spice
        if space_id not in occupied
    )
    return RuleResult(state=next_state, events=events)


def resolve_recall_or_endgame(state: GameState) -> RuleResult:
    """Enter Endgame or recall Agents and prepare the next Round Start."""

    if state.phase is not GamePhase.RECALL_OR_ENDGAME:
        raise ValueError("Recall can resolve only after Makers")
    if state.first_player is None:
        raise ValueError("Recall requires a First Player")
    if state.decision_stack:
        raise ValueError("Recall cannot resolve with a pending decision")
    if any(
        player.troops_conflict > 0
        or player.sandworms_conflict > 0
        or player.combat_strength > 0
        for player in state.players
    ):
        raise ValueError("Combat cleanup must finish before Recall")

    if not state.conflict_deck or any(
        player.victory_points >= 10 for player in state.players
    ):
        next_state = replace(state, phase=GamePhase.ENDGAME)
        event = GameEvent(
            event_id=f"round:{state.round_number}:endgame",
            kind="endgame_started",
        )
        return RuleResult(state=next_state, events=(event,))

    players = tuple(
        replace(
            player,
            agents_available=3 if player.swordmaster_acquired else 2,
            agent_locations=(),
            has_revealed=False,
        )
        for player in state.players
    )
    first_player = (state.first_player + 1) % state.config.players
    next_state = replace(
        state,
        phase=GamePhase.ROUND_START,
        first_player=first_player,
        players=players,
    )
    event = GameEvent(
        event_id=f"round:{state.round_number}:recall",
        kind="agents_recalled",
        payload=(("first_player", first_player),),
    )
    return RuleResult(state=next_state, events=(event,))
