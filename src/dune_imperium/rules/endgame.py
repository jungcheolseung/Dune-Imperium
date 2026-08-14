"""Final Uprising standings after Endgame effects are resolved."""

from dataclasses import dataclass, replace

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


def finish_endgame_without_intrigue(state: GameState) -> RuleResult:
    """Finish an Endgame for which no Intrigue resolution can be pending.

    Until Intrigue timing metadata and OQ-001 are resolved, holding any
    Intrigue card conservatively blocks this automatic path, even if that card
    will eventually be identified as a non-Endgame type.
    """

    if state.phase is not GamePhase.ENDGAME:
        raise ValueError("only an Endgame can be finished")
    if state.decision_stack:
        raise ValueError("Endgame cannot finish with a pending decision")
    if any(player.intrigue_cards for player in state.players):
        raise ValueError("Endgame Intrigue resolution is not implemented")

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


def _ranking_key(player: PlayerState, reveal_position: int) -> tuple[int, ...]:
    return (
        player.victory_points,
        player.resources.spice,
        player.resources.solari,
        player.resources.water,
        player.troops_garrison,
        reveal_position,
    )
