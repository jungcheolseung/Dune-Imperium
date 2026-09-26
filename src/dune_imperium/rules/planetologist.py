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
    turn_closed: bool = False,
) -> RuleResult:
    """Pay ``count`` replacements: spice and Intrigue now, trashes as frames.

    ``turn_closed`` marks a replacement offered after the caller's own
    ``advance_after_effect`` call already closed the owner's turn: a troop
    the pushed trash recruits (Eliminate Allies) must not join whatever
    fresh "turn" frame reopened underneath, even the same player's own
    (OQ-044 (d)) [Main p. 10] [FAQ p. 4]. Neither known caller can reach
    this today (the sandworm summon is withheld while deployment is
    blocked, and the Combat- or Maker-space deployment it triggers keeps
    the turn open until ``finish_agent_turn``), so this is passed only for
    future-proofing.
    """

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
            optional_trash_frame(
                player, f"{source}:planetologist:{index}", turn_closed=turn_closed
            )
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
