"""Chani's Tactics track (leaf: core and gain events) [Chani card] [Bloodlines p. 12].

The printed track has eleven spaces. A four-player game starts on the
third space; the sixth space pays one spice and the last one water, after
which the token returns to the starting space. Retreating or losing enough
troops to pass the end still only resets the token [Bloodlines p. 12].
"""

from copy import replace

from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.rules.gain_events import resources_gained_event

TACTICS_TRACK_START = 2
TACTICS_TRACK_END = 10
TACTICS_SPICE_SPACE = 5


def uses_tactics_track(player: PlayerState) -> bool:
    """Return whether this seat advances a Tactics token."""

    return player.leader_id == "chani"


def advance_tactics_token(
    player: PlayerState,
    count: int,
    *,
    round_number: int,
) -> tuple[PlayerState, tuple[GameEvent, ...]]:
    """Advance the token ``count`` spaces, paying rewards as they are reached.

    The track is the Leader's, so its events are named after the Leader
    (``round:R:player:P:leader:chani``, cleanup-2c-4): the rewards' one
    ``resources_gained``, then ``tactics_token_advanced``.
    """

    if count < 1 or not uses_tactics_track(player):
        return player, ()
    space = player.tactics_track_space
    spice = 0
    water = 0
    for _ in range(count):
        space += 1
        if space == TACTICS_SPICE_SPACE:
            spice += 1
        if space >= TACTICS_TRACK_END:
            water += 1
            space = TACTICS_TRACK_START
            # Extra troops past the end do not advance the reset token.
            break
    next_player = replace(
        player,
        tactics_track_space=space,
        resources=replace(
            player.resources,
            spice=player.resources.spice + spice,
            water=player.resources.water + water,
        ),
    )
    source = f"round:{round_number}:player:{player.player_id}:leader:{player.leader_id}"
    gains = (
        (resources_gained_event(source, player.player_id, spice=spice, water=water),)
        if spice or water
        else ()
    )
    return next_player, (
        *gains,
        GameEvent(
            event_id=f"{source}:tactics",
            kind="tactics_token_advanced",
            payload=(
                ("count", count),
                ("player", player.player_id),
                ("space", space),
            ),
        ),
    )
