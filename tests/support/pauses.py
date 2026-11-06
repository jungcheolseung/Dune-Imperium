"""Answer the engine's pauses in rule-level tests (rules/pauses.py).

The engine stops at a one-outcome chance decision before each Conflict
reward recipient after the first, before every Round Start after the first
and after a Control defense; a chance resolver answers it with its only
outcome. Tests that call rule functions directly answer it here, the same
way the engine does (``_resume_pause``), without the engine's automatic
advance after it.
"""

from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.engine import RuleResult, Transition
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.engine import UprisingRulesEngine, _resume_pause
from dune_imperium.rules.pauses import CONTINUE, pause_is_pending


def answer_pause(state: GameState) -> RuleResult:
    """Run the step the pause on top held back."""

    assert pause_is_pending(state), "no pause is pending"
    return _resume_pause(state)


def pause_outcome(state: GameState) -> ChanceOutcome:
    """The one outcome of the pause on top, for ``engine.apply``."""

    assert pause_is_pending(state), "no pause is pending"
    return ChanceOutcome(
        decision_id=state.decision_stack[-1].frame_id, values=(CONTINUE,)
    )


def through_pauses(engine: UprisingRulesEngine, transition: Transition) -> RuleResult:
    """Answer every pause the transition stopped at, keeping all the events.

    For tests of a whole run that now stops at a pause on the way (between
    reward recipients, before a Round Start).
    """

    state = transition.state
    events: list[GameEvent] = list(transition.events)
    while pause_is_pending(state):
        answered = engine.apply(state, pause_outcome(state))
        state = answered.state
        events.extend(answered.events)
    return RuleResult(state=state, events=tuple(events))
