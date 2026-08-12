"""Pure constructors for official four-player setup state."""

from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core.player import PlayerState


def create_unshuffled_players() -> tuple[PlayerState, ...]:
    """Create four players before leader, objective, and shuffle decisions."""

    return tuple(
        PlayerState(
            player_id=player,
            deck=starting_deck_instance_ids(player),
        )
        for player in range(4)
    )
