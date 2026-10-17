"""Declared differences of the composed-effects cleanup-2 (branch ``cleanup2``).

docs/composed-effects-plan.md 5, "정리-2 계획": every change a player, an agent
or a save can see on purpose, as rules for ``engine_equivalence.py check
--differences scripts/ab/differences/cleanup2.py`` against the recording of
the stage's start master (``d892cd6c``). Each rule's ``why`` names the plan's
sub-stage; a sub-stage adds its rules here with its change.
"""

from equivalence_rules import At, Rule

from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.rules.frames import FrameKind

SCOUTS_NO_OPTION = "resolve_scouts_choice_without_option"


def _scouts_no_option(at: At) -> object:
    """2a: a Scouts choice with no line to take now asks its seat, which can
    only confirm; the base skipped it (the confirm emits the same
    ``scouts_choice_skipped``)."""

    if (
        isinstance(at.decision, PlayerDecision)
        and at.state.decision_stack[-1].kind == FrameKind.SCOUTS_CHOICE
        and [action.action_id for action in at.legal] == [SCOUTS_NO_OPTION]
    ):
        return at.legal[0]
    return None


RULES = (
    Rule(
        "scouts_no_option_window",
        why="cleanup-2a: decision 6, OQ-071 addendum (a Scouts seat with no line "
        "is asked)",
        answer=_scouts_no_option,
    ),
)
