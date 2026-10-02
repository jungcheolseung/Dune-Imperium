"""Liet Kynes' Arrakis Planetologist [Liet Kynes card].

"You summon no sandworms. For each one you would, instead: trash a card
(optional), 1 spice, 1 Intrigue card. (Even when the Conflict is protected
by the Shield Wall.)" Every sandworm summon site asks ``replaces_sandworms``
and pays the replacement through ``replace_sandworms``.
"""

from dataclasses import replace

from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import replace_player
from dune_imperium.rules.intrigue_deck import draw_or_queue_intrigue_cards
from dune_imperium.rules.optional_trash import optional_trash_frame


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
    """Pay ``count`` replacements: spice and Intrigue now, trashes as frames."""

    if count < 1:
        return RuleResult(state=state)
    owner = state.players[player]
    paid = replace(
        owner,
        resources=replace(owner.resources, spice=owner.resources.spice + count),
    )
    working = replace(state, players=replace_player(state.players, paid))
    drawn = draw_or_queue_intrigue_cards(
        working, player, count, source=f"{source}:planetologist"
    )
    working = drawn.state
    for index in range(count):
        working = working.push_decision(
            optional_trash_frame(player, f"{source}:planetologist:{index}")
        )
    return RuleResult(
        state=working,
        events=(
            GameEvent(
                event_id=f"{source}:planetologist",
                kind="sandworms_replaced",
                payload=(("count", count), ("player", player), ("spice", count)),
            ),
            *drawn.events,
        ),
    )
