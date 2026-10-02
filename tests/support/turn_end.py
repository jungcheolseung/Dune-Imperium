"""Ending an Agent turn in rules tests.

Every Agent turn ends only through its owner's ``finish_agent_turn``, even
when nothing is left to resolve (user ruling OQ-095,
``docs/rules/open-questions.md``): the last effect no longer hands the turn
to the next seat. A test that used to read the next seat's turn right after
the last effect presses the end first with these helpers.

Import with the same ``sys.path`` line ``ko_text`` uses (tests/support is
not a package pytest or mypy resolve from a dotted import)::

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "support"))
    from turn_end import finish_agent_turn  # type: ignore[import-not-found]
"""

from dune_imperium.core import DomainAction, GameState, PlayerDecision
from dune_imperium.core.engine import Transition
from dune_imperium.rules.effects import current_agent_effect_context
from dune_imperium.rules.engine import UprisingRulesEngine


def finish_agent_turn_result(state: GameState) -> Transition:
    """Press the open Agent turn's end through the engine; return the result.

    The owner's Agent-turn effect frame must be on top and the end legal
    (every mandatory group resolved), exactly as a seat would press it.
    """

    frame, _ = current_agent_effect_context(state)
    if not isinstance(frame.decision, PlayerDecision):
        raise TypeError("an Agent-turn effect frame holds a player decision")
    owner = frame.decision.owner
    return UprisingRulesEngine().apply(state, DomainAction("finish_agent_turn", owner))


def finish_agent_turn(state: GameState) -> GameState:
    """Press the open Agent turn's end through the engine; return the state."""

    return finish_agent_turn_result(state).state
