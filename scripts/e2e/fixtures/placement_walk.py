"""A seeded walk's step over the legal list as it was before stage B1.

The fixtures that look for a situation by a seeded random walk drew one of
the seat's legal actions, and an Agent placement was one of them. Stage B1
(codec v150, OQ-111) asks a placement as a card pick and then a space pick,
so drawing over the engine's list now would walk other games. ``walk_step``
draws over the list with the card picks shown as the whole placements they
lead to, in the engine's order (``agents.agent_turn_steps``), and plays a
drawn placement as its two steps: the walk is the one it was, seed for seed.
Stage B2 (OQ-112) asks a Conflict or Contract reward icon by icon; the walk
answers those rows in the engine's older fixed order without a draw, as the
AI seats do (``agents.engine_order``), so the walk stays the one it was.

Imported by the fixture scripts beside it (their directory is on
``sys.path`` when they run).
"""

from collections.abc import Callable
from typing import Any

from dune_imperium.agents.agent_turn_steps import (
    PLACEMENT_ACTION,
    placements_for_steps,
)
from dune_imperium.agents.engine_order import engine_order_answer
from dune_imperium.core.actions import DomainAction

type Pick = Callable[[tuple[DomainAction, ...]], DomainAction]


def walk_step(
    manager: Any, game_id: str, owner: int, summary: Any, pick: Pick
) -> tuple[Any, DomainAction]:
    """Apply ``pick``'s choice among the seat's legal actions (placements
    whole) through the session manager; return the summary after it and
    the choice (a placement as ``agent_turn``)."""

    session = manager._get(game_id)
    actions = session.engine.whole_actions(session.state, owner)
    scripted = engine_order_answer(session.state, owner, actions)
    if scripted is not None:
        index = actions.index(scripted)
        summary = manager.apply_action(game_id, owner, summary["revision"], index)
        return summary, scripted
    steps = placements_for_steps(session.state, owner, actions)
    if steps is None:
        chosen = pick(actions)
        index = actions.index(chosen)
        return manager.apply_action(game_id, owner, summary["revision"], index), chosen
    shown, to_step = steps
    chosen = pick(shown)
    summary = manager.apply_action(
        game_id, owner, summary["revision"], actions.index(to_step(chosen))
    )
    if chosen.action_id != PLACEMENT_ACTION:
        return summary, chosen
    later = session.engine.whole_actions(session.state, owner)
    spaces = placements_for_steps(session.state, owner, later)
    assert spaces is not None, "the card pick waits for its space pick"
    summary = manager.apply_action(
        game_id, owner, summary["revision"], later.index(spaces[1](chosen))
    )
    return summary, chosen
