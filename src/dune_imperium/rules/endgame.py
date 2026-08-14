"""Final Uprising standings after Endgame effects are resolved."""

from dataclasses import dataclass, replace

from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.uprising.objectives import OBJECTIVES_BY_ID
from dune_imperium.content.uprising.types import BattleIcon
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState


@dataclass(frozen=True, slots=True)
class FinalStanding:
    """One player's final rank and the values used to break VP ties."""

    rank: int
    player: int
    victory_points: int
    spice: int
    solari: int
    water: int
    troops_garrison: int
    reveal_position: int


@dataclass(frozen=True, slots=True)
class EndgameWildMatch:
    """One currently possible wild-to-printed battle icon match."""

    player: int
    wild_card_id: str
    matching_card_id: str


def final_standings(state: GameState) -> tuple[FinalStanding, ...]:
    """Rank players by VP and the official Uprising tiebreak sequence.

    Endgame effects must already be reflected in ``state``. The last tiebreak
    uses the current round's Reveal completion order, where a greater position
    means the player Revealed more recently.
    """

    if state.phase not in (GamePhase.ENDGAME, GamePhase.FINISHED):
        raise ValueError("final standings are available only during Endgame")
    expected_players = set(range(state.config.players))
    if set(state.reveal_order) != expected_players:
        raise ValueError("final standings require every player's Reveal order")

    reveal_positions = {
        player: position for position, player in enumerate(state.reveal_order)
    }
    ranked = tuple(
        sorted(
            state.players,
            key=lambda player: _ranking_key(
                player,
                reveal_positions[player.player_id],
            ),
            reverse=True,
        )
    )
    return tuple(
        FinalStanding(
            rank=rank,
            player=player.player_id,
            victory_points=player.victory_points,
            spice=player.resources.spice,
            solari=player.resources.solari,
            water=player.resources.water,
            troops_garrison=player.troops_garrison,
            reveal_position=reveal_positions[player.player_id],
        )
        for rank, player in enumerate(ranked, start=1)
    )


def can_finish_endgame_automatically(state: GameState) -> bool:
    """Return whether no unimplemented Endgame choice can affect scoring."""

    return not any(player.intrigue_cards for player in state.players) and not (
        _endgame_wild_matches(state)
    )


def begin_endgame_wild_choice(state: GameState) -> RuleResult:
    """Open an optional wild-icon match when exactly one pair is possible."""

    if state.phase is not GamePhase.ENDGAME:
        raise ValueError("wild battle icons resolve only during Endgame")
    if state.decision_stack:
        raise ValueError("wild battle choice requires no pending decision")
    if any(player.intrigue_cards for player in state.players):
        raise ValueError("Endgame Intrigue ordering is unresolved")
    matches = _endgame_wild_matches(state)
    if len(matches) != 1:
        raise ValueError("Endgame wild choice requires exactly one possible pair")

    match = matches[0]
    frame = DecisionFrame(
        frame_id=f"round:{state.round_number}:endgame_wild:{match.player}",
        decision=PlayerDecision(
            owner=match.player,
            prompt="Match the wild battle icon for 1 Victory Point?",
        ),
        context=(
            ("matching_card_id", match.matching_card_id),
            ("turn_owner", match.player),
            ("wild_card_id", match.wild_card_id),
        ),
    )
    return RuleResult(state=state.push_decision(frame))


def legal_endgame_wild_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return decline and match actions for an open wild-icon choice."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if (
        not frame.frame_id.startswith(f"round:{state.round_number}:endgame_wild:")
        or not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
    ):
        return ()
    context = dict(frame.context)
    wild_card_id = context.get("wild_card_id")
    matching_card_id = context.get("matching_card_id")
    if not isinstance(wild_card_id, str) or not isinstance(matching_card_id, str):
        raise RuntimeError("Endgame wild frame has invalid card IDs")
    return (
        DomainAction(action_id="decline_endgame_wild_match", actor=player),
        DomainAction(
            action_id="match_endgame_wild_icon",
            actor=player,
            arguments=(
                ("matching_card_id", matching_card_id),
                ("wild_card_id", wild_card_id),
            ),
        ),
    )


def apply_endgame_wild_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Decline or resolve the currently unambiguous wild-icon match."""

    if action not in legal_endgame_wild_actions(state, action.actor):
        raise ValueError("action is not a legal Endgame wild choice")
    context = dict(state.decision_stack[-1].context)
    wild_card_id = str(context["wild_card_id"])
    matching_card_id = str(context["matching_card_id"])
    matched = action.action_id == "match_endgame_wild_icon"
    owner = state.players[action.actor]
    next_owner = replace(
        owner,
        victory_points=owner.victory_points + int(matched),
        face_down_battle_card_ids=(
            (*owner.face_down_battle_card_ids, wild_card_id, matching_card_id)
            if matched
            else owner.face_down_battle_card_ids
        ),
    )
    players = tuple(
        next_owner if player.player_id == action.actor else player
        for player in state.players
    )
    declined = (
        state.declined_endgame_wild_card_ids
        if matched
        else (*state.declined_endgame_wild_card_ids, wild_card_id)
    )
    next_state = replace(
        state.pop_decision(),
        players=players,
        declined_endgame_wild_card_ids=declined,
    )
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:endgame_wild:{action.actor}:"
            f"{'matched' if matched else 'declined'}"
        ),
        kind=("endgame_wild_matched" if matched else "endgame_wild_declined"),
        payload=(
            ("matching_card_id", matching_card_id),
            ("player", action.actor),
            ("wild_card_id", wild_card_id),
        ),
    )
    return RuleResult(state=next_state, events=(event,))


def finish_endgame_without_pending_effects(state: GameState) -> RuleResult:
    """Finish an Endgame for which no unresolved scoring effect is pending.

    Until Intrigue timing metadata and OQ-001 are resolved, holding any
    Intrigue card conservatively blocks this automatic path, even if that card
    will eventually be identified as a non-Endgame type. A possible wild battle
    icon match also blocks until its choice is implemented.
    """

    if state.phase is not GamePhase.ENDGAME:
        raise ValueError("only an Endgame can be finished")
    if state.decision_stack:
        raise ValueError("Endgame cannot finish with a pending decision")
    if not can_finish_endgame_automatically(state):
        raise ValueError("Endgame has unresolved Intrigue or wild battle effects")

    standings = final_standings(state)
    winner = standings[0]
    next_state = replace(state, phase=GamePhase.FINISHED)
    event = GameEvent(
        event_id=f"round:{state.round_number}:game_finished",
        kind="game_finished",
        payload=(
            ("player", winner.player),
            ("victory_points", winner.victory_points),
        ),
    )
    return RuleResult(state=next_state, events=(event,))


def _endgame_wild_matches(state: GameState) -> tuple[EndgameWildMatch, ...]:
    matches: list[EndgameWildMatch] = []
    declined = set(state.declined_endgame_wild_card_ids)
    for player in state.players:
        face_up_ids = (set(player.objective_ids) | set(player.won_conflict_ids)) - set(
            player.face_down_battle_card_ids
        )
        wild_ids = tuple(
            card_id
            for card_id in face_up_ids
            if card_id not in declined and _battle_icon(card_id) is BattleIcon.WILD
        )
        matching_ids = tuple(
            card_id
            for card_id in face_up_ids
            if _battle_icon(card_id) not in (None, BattleIcon.WILD)
        )
        matches.extend(
            EndgameWildMatch(player.player_id, wild_card_id, matching_card_id)
            for wild_card_id in wild_ids
            for matching_card_id in matching_ids
        )
    return tuple(matches)


def _battle_icon(card_id: str) -> BattleIcon | None:
    if card_id in OBJECTIVES_BY_ID:
        return OBJECTIVES_BY_ID[card_id].battle_icon
    return CONFLICTS_BY_ID[card_id].battle_icon


def _ranking_key(player: PlayerState, reveal_position: int) -> tuple[int, ...]:
    return (
        player.victory_points,
        player.resources.spice,
        player.resources.solari,
        player.resources.water,
        player.troops_garrison,
        reveal_position,
    )
