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
The server passes Combat Intrigue for a human seat holding no Intrigue card
(user request 2026-11-09), a decision the walk drew over (a draw over the
one pass); ``walk_step`` makes that draw for each such pass the server made
for a human seat since its last call (the log's ``without_choice`` entries
of human seats), so again the walk is the one it was. Since a later change
the same day the server passes a seat holding specimens too (their return
waits for the seat's Conflict reward window, OQ-050), where the walk drew
over the pass and the return and sometimes returned one; a walk over
Immortality games that should keep its seeds' games leaves those seats
asked (``keep_specimen_holders_asked``). The server also passes a human
seat's Endgame Intrigue go with nothing but the pass, drawn over the same
way, and presses a sole winner's reward-window close with no Intrigue card
(user decision 2026-11-09), a reward row the walk answered without a draw.

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
from dune_imperium.agents.window_returns import without_window_specimen_return
from dune_imperium.core.actions import DomainAction
from dune_imperium.server.session_log import INTRIGUE_PASSES

type Pick = Callable[[tuple[DomainAction, ...]], DomainAction]

# How far into each game's log the walk has drawn for the server's passes.
_DRAWN: dict[str, int] = {}
# Per game whose specimen holders the walk keeps asking
# (``keep_specimen_holders_asked``): the log positions of the passes the
# server made. The walk's own pass of a seat holding specimens and no card is
# logged ``without_choice`` too, and was drawn as the walk was asked.
_SERVER_MADE: dict[str, set[int]] = {}


def draw_for_server_passes(session: Any, game_id: str, pick: Pick) -> None:
    """Draw, as the walk did when it was asked, once for each Combat
    Intrigue pass the server made since the last call (a draw over the one
    pass, which the walk always took)."""

    log = session.log
    made = _SERVER_MADE.get(game_id)
    for position in range(_DRAWN.get(game_id, 0), len(log)):
        entry = log[position]
        if (
            getattr(entry, "without_choice", False)
            and not entry.undone
            # The winner's close the server makes is a reward row, which the
            # walk answered in the engine's order without a draw.
            and getattr(entry.step, "action_id", None) in INTRIGUE_PASSES
            # An AI seat's pass was never the walk's to draw over.
            and session.seats[entry.actor] == "human"
            and (made is None or position in made)
        ):
            pick((entry.step,))
    _DRAWN[game_id] = len(log)


def keep_specimen_holders_asked(manager: Any) -> None:
    """Leave a seat holding specimens to the walk at Combat Intrigue, as the
    server did before 2026-11-09's second change
    (``sessions._auto_pass_intrigue_locked``), for every game of
    ``manager``; ``draw_for_server_passes`` then draws for the passes the
    server made only."""

    passes = manager._auto_pass_intrigue_locked

    def asked(session: Any, seat: int) -> bool:
        # The server asks this before any pass of the game is logged.
        made = _SERVER_MADE.setdefault(session.game_id, set())
        if session.state.players[seat].specimens:
            return False
        before = len(session.log)
        passed = bool(passes(session, seat))
        made.update(range(before, len(session.log)) if passed else ())
        return passed

    manager._auto_pass_intrigue_locked = asked


def ask_agents_for_server_passes(
    manager: Any, game_id: str, agents: Any, asked: int
) -> int:
    """Ask each seat's agent for the Combat Intrigue passes the server made
    for a human seat since live step ``asked`` (user request 2026-11-09), on
    the position before each, as a walk whose agents answer every decision
    asked them when the seat was asked: every agent then draws as before
    and the seed keeps its game. Returns the live step count to pass next."""

    from dune_imperium.server.session_log import live_steps
    from dune_imperium.server.sessions import _state_after

    session = manager._get(game_id)
    live = live_steps(session.log)
    for index in range(asked, len(live)):
        entry = live[index]
        if entry.without_choice and session.seats[entry.actor] == "human":
            before = _state_after(session, index)
            agents[entry.actor].choose_action_with_state(
                before,
                session.engine.observe(before, entry.actor),
                session.engine.whole_actions(before, entry.actor),
            )
    return len(live)


def walk_step(
    manager: Any, game_id: str, owner: int, summary: Any, pick: Pick
) -> tuple[Any, DomainAction]:
    """Apply ``pick``'s choice among the seat's legal actions (placements
    whole) through the session manager; return the summary after it and
    the choice (a placement as ``agent_turn``)."""

    session = manager._get(game_id)
    draw_for_server_passes(session, game_id, pick)
    actions = session.engine.whole_actions(session.state, owner)
    scripted = engine_order_answer(session.state, owner, actions)
    if scripted is not None:
        index = actions.index(scripted)
        summary = manager.apply_action(game_id, owner, summary["revision"], index)
        return summary, scripted
    # A specimen's return in a window outside its turn is offered since
    # 2026-11-09 (OQ-050, ``agents.window_returns``); the walk draws over the
    # rows it always drew over, as the AI seats do.
    kind = str(session.state.decision_stack[-1].kind)
    steps = placements_for_steps(session.state, owner, actions)
    if steps is None:
        chosen = pick(without_window_specimen_return(actions, kind))
        index = actions.index(chosen)
        return manager.apply_action(game_id, owner, summary["revision"], index), chosen
    shown, to_step = steps
    chosen = pick(without_window_specimen_return(shown, kind))
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
