"""Final Uprising standings after Endgame effects are resolved."""

from dataclasses import dataclass, replace

from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.uprising.objectives import OBJECTIVES_BY_ID
from dune_imperium.content.uprising.types import BattleIcon
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.frames import FrameKind, owned_top_frame


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
    """Return whether no Endgame choice remains that could affect scoring.

    Once every player's Endgame window has closed the game always finishes;
    the window itself is skipped when nobody holds an Intrigue card and no
    wild battle pair exists.
    """

    return state.endgame_intrigue_complete or (
        not any(player.intrigue_cards for player in state.players)
        and not _endgame_wild_matches(state)
    )


def begin_endgame_intrigue(state: GameState) -> RuleResult:
    """Open the first Endgame window, starting with the First Player.

    Each player, clockwise from the First Player, gets one window in which
    they may play any number of Endgame Intrigue cards and match wild battle
    icons in any order before the final Victory Points are compared
    [Main pp. 7, 15, 20]. Passing closes the window for good (OQ-001).
    """

    if state.phase is not GamePhase.ENDGAME:
        raise ValueError("Endgame Intrigue windows open only during Endgame")
    if state.decision_stack:
        raise ValueError("the Endgame window requires no pending decision")
    if state.endgame_intrigue_complete:
        raise ValueError("every Endgame window has already closed")
    if state.first_player is None:
        raise ValueError("the Endgame window requires a First Player")
    order = tuple(
        (state.first_player + offset) % state.config.players
        for offset in range(state.config.players)
    )
    return RuleResult(
        state=state.push_decision(_endgame_window_frame(state, order[0], order[1:]))
    )


def legal_endgame_intrigue_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return pass and this player's wild battle matches for an open window.

    Endgame Intrigue plays are provided by the shared Intrigue play provider
    on the same frame.
    """

    frame = owned_top_frame(state, FrameKind.ENDGAME_INTRIGUE, player)
    if frame is None:
        return ()
    return (
        DomainAction(action_id="pass_endgame_intrigue", actor=player),
        *(
            DomainAction(
                action_id="match_endgame_wild_icon",
                actor=player,
                arguments=(
                    ("matching_card_id", match.matching_card_id),
                    ("wild_card_id", match.wild_card_id),
                ),
            )
            for match in _endgame_wild_matches(state)
            if match.player == player
        ),
    )


def apply_endgame_intrigue_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Pass the window on, or flip a wild pair for one Victory Point."""

    if action not in legal_endgame_intrigue_actions(state, action.actor):
        raise ValueError("action is not a legal Endgame window choice")
    frame = state.decision_stack[-1]
    context = dict(frame.context)

    if action.action_id == "pass_endgame_intrigue":
        remaining = _remaining_players(context)
        event = GameEvent(
            event_id=(
                f"round:{state.round_number}:endgame_intrigue:{action.actor}:passed"
            ),
            kind="endgame_intrigue_passed",
            payload=(("player", action.actor),),
        )
        if remaining:
            next_state = replace(
                state,
                decision_stack=(
                    *state.decision_stack[:-1],
                    _endgame_window_frame(state, remaining[0], remaining[1:]),
                ),
            )
        else:
            next_state = replace(
                state.pop_decision(),
                endgame_intrigue_complete=True,
            )
        return RuleResult(state=next_state, events=(event,))

    arguments = dict(action.arguments)
    wild_card_id = str(arguments["wild_card_id"])
    matching_card_id = str(arguments["matching_card_id"])
    owner = state.players[action.actor]
    next_owner = replace(
        owner,
        victory_points=owner.victory_points + 1,
        face_down_battle_card_ids=(
            *owner.face_down_battle_card_ids,
            wild_card_id,
            matching_card_id,
        ),
    )
    players = tuple(
        next_owner if player.player_id == action.actor else player
        for player in state.players
    )
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:endgame_wild:{action.actor}:"
            f"{wild_card_id}:{matching_card_id}"
        ),
        kind="endgame_wild_matched",
        payload=(
            ("matching_card_id", matching_card_id),
            ("player", action.actor),
            ("wild_card_id", wild_card_id),
        ),
    )
    # The window stays open: further matches or Intrigue plays may follow.
    return RuleResult(state=replace(state, players=players), events=(event,))


def _endgame_window_frame(
    state: GameState,
    player: int,
    remaining: tuple[int, ...],
) -> DecisionFrame:
    return DecisionFrame(
        kind=FrameKind.ENDGAME_INTRIGUE,
        frame_id=f"round:{state.round_number}:endgame_intrigue:{player}",
        decision=PlayerDecision(
            owner=player,
            prompt="Play Endgame Intrigue, match wild icons, or pass",
        ),
        context=(
            ("remaining", ",".join(str(seat) for seat in remaining)),
            ("turn_owner", player),
        ),
    )


def _remaining_players(context: dict[str, ActionValue]) -> tuple[int, ...]:
    value = context.get("remaining")
    if not isinstance(value, str):
        raise RuntimeError("Endgame window frame has invalid remaining players")
    return tuple(int(seat) for seat in value.split(",") if seat)


def finish_endgame_without_pending_effects(state: GameState) -> RuleResult:
    """Finish an Endgame for which no unresolved scoring effect is pending.

    The game finishes once every Endgame window has closed, or at once when
    nobody holds an Intrigue card and no wild battle pair exists.
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
    for player in state.players:
        face_up_ids = (set(player.objective_ids) | set(player.won_conflict_ids)) - set(
            player.face_down_battle_card_ids
        )
        # A won Conflict carrying Pivotal Gambit's pledged wild icon pairs as
        # a wild source too (OQ-025); it cannot pair with itself.
        wild_ids = tuple(
            card_id
            for card_id in sorted(face_up_ids)
            if _battle_icon(card_id) is BattleIcon.WILD
            or card_id in state.wild_icon_conflict_ids
        )
        matching_ids = tuple(
            card_id
            for card_id in sorted(face_up_ids)
            if _battle_icon(card_id) not in (None, BattleIcon.WILD)
        )
        matches.extend(
            EndgameWildMatch(player.player_id, wild_card_id, matching_card_id)
            for wild_card_id in wild_ids
            for matching_card_id in matching_ids
            if wild_card_id != matching_card_id
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
