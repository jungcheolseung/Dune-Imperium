"""Automatic transitions between top-level Uprising round phases."""

from dataclasses import replace

from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.frames import FrameKind


def begin_round(state: GameState) -> RuleResult:
    """Reveal a Conflict, draw up to five cards each, and open the first turn.

    Any discard pile needed to complete the draw must already have been
    shuffled beneath the remaining draw deck by ``prepare_round_start``.
    """

    if state.phase is not GamePhase.ROUND_START:
        raise ValueError("a round can begin only during the Round Start phase")
    if state.first_player is None:
        raise ValueError("a round requires a First Player")
    if state.decision_stack:
        raise ValueError("Round Start cannot begin with a pending decision")
    if not state.conflict_deck:
        raise ValueError("a round cannot begin without a Conflict card")
    if any(len(player.deck) < 5 and player.discard_pile for player in state.players):
        raise ValueError("Round Start draw requires a discard reshuffle transition")

    round_number = state.round_number + 1
    conflict_id = state.conflict_deck[0]
    draw_counts = tuple(min(5, len(player.deck)) for player in state.players)
    players = tuple(
        replace(
            _draw_cards(player, count),
            units_deployed_turn=0,
            deploy_trigger_offered_at=0,
            spice_at_turn_start=player.resources.spice,
            spice_spent_turn=0,
        )
        for player, count in zip(state.players, draw_counts, strict=True)
    )
    opening_frame = _round_opening_frame(
        players,
        conflict_id,
        round_number,
        state.first_player,
    )
    next_state = replace(
        state,
        phase=GamePhase.PLAYER_TURNS,
        round_number=round_number,
        reveal_order=(),
        players=players,
        conflict_deck=state.conflict_deck[1:],
        current_conflict_ids=(*state.current_conflict_ids, conflict_id),
        conflict_first_place_influence_bonus=0,
        combat_intrigue_complete=False,
        combat_rewards_resolved=False,
        decision_stack=(opening_frame,),
    )
    events = (
        GameEvent(
            event_id=f"round:{round_number}:conflict",
            kind="conflict_revealed",
            payload=(("conflict_id", conflict_id), ("round", round_number)),
        ),
        *(
            # The draw count is public: zone sizes are visible at the table
            # (OQ-010) and the payload carries no card identity.
            GameEvent(
                event_id=f"round:{round_number}:player:{player.player_id}:draw",
                kind="cards_drawn",
                payload=(("count", count), ("player", player.player_id)),
            )
            for player, count in zip(players, draw_counts, strict=True)
            if count > 0
        ),
    )
    return RuleResult(state=next_state, events=events)


def prepare_round_start(state: GameState) -> RuleResult:
    """Request required discard shuffles or begin the round immediately."""

    if state.phase is not GamePhase.ROUND_START:
        raise ValueError("only Round Start can be prepared")
    if state.decision_stack:
        raise ValueError("Round Start preparation requires no pending decision")
    for player in state.players:
        if len(player.deck) >= 5 or not player.discard_pile:
            continue
        decision_id = (
            f"round:{state.round_number + 1}:player:{player.player_id}:discard_shuffle"
        )
        frame = DecisionFrame(
            kind=FrameKind.ROUND_START_RESHUFFLE,
            frame_id=f"{decision_id}:round_start",
            decision=ChanceDecision(
                decision_id=decision_id,
                prompt=f"Shuffle player {player.player_id}'s discard pile",
                options=player.discard_pile,
                count=len(player.discard_pile),
            ),
            context=(("player", player.player_id),),
        )
        return RuleResult(state=state.push_decision(frame))
    return begin_round(state)


def apply_round_start_reshuffle(
    state: GameState,
    outcome: ChanceOutcome,
) -> RuleResult:
    """Append one recorded discard permutation beneath the remaining deck."""

    if not state.decision_stack:
        raise ValueError("there is no pending Round Start reshuffle")
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.ROUND_START_RESHUFFLE or not isinstance(
        frame.decision, ChanceDecision
    ):
        raise ValueError("the current chance decision is not a Round Start reshuffle")
    player = dict(frame.context).get("player")
    if isinstance(player, bool) or not isinstance(player, int):
        raise RuntimeError("Round Start reshuffle has invalid player context")
    owner = state.players[player]
    next_owner = replace(
        owner,
        deck=(*owner.deck, *outcome.values),
        discard_pile=(),
    )
    players = tuple(
        next_owner if candidate.player_id == player else candidate
        for candidate in state.players
    )
    prepared = prepare_round_start(replace(state.pop_decision(), players=players))
    event = GameEvent(
        event_id=f"round:{state.round_number + 1}:player:{player}:discard_shuffled",
        kind="personal_discard_shuffled",
        payload=(("count", len(outcome.values)), ("player", player)),
        visible_to=(player,),
    )
    return RuleResult(state=prepared.state, events=(event, *prepared.events))


def legal_control_defense_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer the controller's optional one-troop defensive deployment."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    decision = frame.decision
    if (
        frame.kind != FrameKind.CONTROL_DEFENSE
        or not isinstance(decision, PlayerDecision)
        or decision.owner != player
    ):
        return ()
    return (
        DomainAction(action_id="decline_control_defense", actor=player),
        DomainAction(action_id="deploy_control_defense", actor=player),
    )


def apply_control_defense_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve the optional deployment and open the First Player's turn."""

    if action not in legal_control_defense_actions(state, action.actor):
        raise ValueError("action is not a legal Control defense choice")
    if state.first_player is None:
        raise RuntimeError("Control defense requires a First Player")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    space_id = context.get("space_id")
    if not isinstance(space_id, str):
        raise RuntimeError("Control defense frame has invalid space ID")
    deployed = action.action_id == "deploy_control_defense"
    owner = state.players[action.actor]
    if deployed and owner.troops_supply == 0:
        raise RuntimeError("Control defender has no troop in supply")
    next_owner = replace(
        owner,
        troops_supply=owner.troops_supply - int(deployed),
        troops_conflict=owner.troops_conflict + int(deployed),
    )
    players = tuple(
        next_owner if player.player_id == action.actor else player
        for player in state.players
    )
    next_state = replace(
        state,
        players=players,
        decision_stack=(
            *state.decision_stack[:-1],
            _turn_frame(state.round_number, state.first_player),
        ),
    )
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:control_defense:{space_id}:{action.actor}"
        ),
        kind=("control_defense_deployed" if deployed else "control_defense_declined"),
        payload=(
            ("player", action.actor),
            ("space_id", space_id),
            ("troops", int(deployed)),
        ),
    )
    return RuleResult(state=next_state, events=(event,))


def _draw_cards(player: PlayerState, count: int) -> PlayerState:
    return replace(
        player,
        deck=player.deck[count:],
        hand=(*player.hand, *player.deck[:count]),
    )


def _round_opening_frame(
    players: tuple[PlayerState, ...],
    conflict_id: str,
    round_number: int,
    first_player: int,
) -> DecisionFrame:
    conflict = CONFLICTS_BY_ID[conflict_id]
    control_space_id = (
        None if conflict.rewards is None else conflict.rewards[0].control_space_id
    )
    controllers = tuple(
        player
        for player in players
        if control_space_id is not None and control_space_id in player.control_space_ids
    )
    if len(controllers) > 1:
        raise RuntimeError("a critical location cannot have multiple controllers")
    if controllers and controllers[0].troops_supply > 0:
        if control_space_id is None:
            raise RuntimeError("Control defender requires a critical location")
        controller = controllers[0]
        return DecisionFrame(
            kind=FrameKind.CONTROL_DEFENSE,
            frame_id=f"round:{round_number}:control_defense",
            decision=PlayerDecision(
                owner=controller.player_id,
                prompt="Deploy one troop from supply to defend your location?",
            ),
            context=(
                ("space_id", control_space_id),
                ("turn_owner", first_player),
            ),
        )
    return _turn_frame(round_number, first_player)


def _turn_frame(round_number: int, player: int) -> DecisionFrame:
    return DecisionFrame(
        kind=FrameKind.TURN,
        frame_id=f"round:{round_number}:turn:{player}",
        decision=PlayerDecision(
            owner=player,
            prompt="Choose an Agent turn or Reveal turn",
        ),
        context=(
            ("round", round_number),
            ("turn_owner", player),
        ),
    )


def resolve_makers(state: GameState) -> RuleResult:
    """Add spice to every unoccupied Maker space and open Recall."""

    if state.phase is not GamePhase.MAKERS:
        raise ValueError("Makers can resolve only during the Makers phase")
    if state.decision_stack:
        raise ValueError("Makers cannot resolve with a pending decision")
    occupied = {
        space_id for player in state.players for space_id in player.agent_locations
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
