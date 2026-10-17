"""Liet Kynes' Arrakis Planetologist [Liet Kynes card].

"You summon no sandworms. For each one you would, instead: trash a card
(optional), 1 spice, 1 Intrigue card. (Even when the Conflict is protected
by the Shield Wall.)" Every sandworm summon site asks ``replaces_sandworms``
and pays the replacement through ``replace_sandworms``. The spice is paid at
once; the trash and the Intrigue card wait in one frame per replacement,
each its own step in either order, so the choice that summoned (a Maker
space's sandworms, Unexpected Allies' Shield Wall, ...) never draws a hidden
card itself (user ruling 2026-10-10, OQ-106).
"""

from copy import replace

from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import replace_player
from dune_imperium.rules.optional_trash import open_planetologist_replacement


def replaces_sandworms(player: PlayerState) -> bool:
    """Return whether this seat turns every sandworm into the replacement."""

    return player.leader_id == "liet_kynes"


def replace_sandworms(
    state: GameState,
    player: int,
    count: int,
    *,
    source: str,
) -> RuleResult:
    """Pay ``count`` replacements: the spice now, then one frame each for
    the optional trash and the Intrigue card (``draw_planetologist_intrigue``),
    resolved in either order (user ruling 2026-10-10, OQ-106: "그 외에는
    전부 나누자"). Inside the owner's own turn both wait on the turn as rows
    instead (cleanup-2b, ``open_planetologist_replacement``)."""

    if count < 1:
        return RuleResult(state=state)
    owner = state.players[player]
    paid = replace(
        owner,
        resources=replace(owner.resources, spice=owner.resources.spice + count),
    )
    working = replace(state, players=replace_player(state.players, paid))
    for index in range(count):
        working = open_planetologist_replacement(
            working, player, f"{source}:planetologist:{index}"
        )
    return RuleResult(
        state=working,
        events=(
            GameEvent(
                event_id=f"{source}:planetologist",
                kind="sandworms_replaced",
                payload=(("count", count), ("player", player), ("spice", count)),
            ),
        ),
    )
