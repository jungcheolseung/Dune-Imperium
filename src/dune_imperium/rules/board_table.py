"""Which board spaces are on the table.

Kept apart from ``agent_turn`` so the Agent-box rules (The Voice's "Choose any
board space") can read it without importing the placement module.
"""

from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.board import BoardSpace
from dune_imperium.core.state import GameState


def board_spaces_on_table(state: GameState) -> tuple[BoardSpace, ...]:
    """The game's board spaces in board order, less a Leader's own space when
    that Leader is not playing: Tuek's Sietch is on the table only with Esmar
    Tuek (``BoardSpace.required_leader_id``)."""

    return tuple(
        space
        for space in content_for(state.config).board_spaces
        if space.required_leader_id is None
        or any(seat.leader_id == space.required_leader_id for seat in state.players)
    )
