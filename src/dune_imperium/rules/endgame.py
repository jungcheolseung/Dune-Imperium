"""Final Uprising standings after Endgame effects are resolved."""

from dataclasses import dataclass

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


def _ranking_key(player: PlayerState, reveal_position: int) -> tuple[int, ...]:
    return (
        player.victory_points,
        player.resources.spice,
        player.resources.solari,
        player.resources.water,
        player.troops_garrison,
        reveal_position,
    )
