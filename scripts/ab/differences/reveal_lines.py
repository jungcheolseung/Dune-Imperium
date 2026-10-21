"""Declared differences of codec v151 against master ``822e7d62`` (codec v150).

The Reveal frame's state names follow the code's "Reveal line": the
``reveal_effect_granted_late`` event is ``reveal_line_granted_late`` and its
``effect_index`` payload key is ``line_index`` (user request 2026-10-21, no
other change). The frame context key ``granted_reveal_effects`` became
``granted_reveal_lines`` too; the decision stack is left out of every state
comparison, so only the event shows. Checked with ``engine_equivalence.py
check --differences scripts/ab/differences/reveal_lines.py``.
"""

from equivalence_rules import Rule, Step

_OLD_KIND = "reveal_effect_granted_late"
_NEW_KIND = "reveal_line_granted_late"
_OLD_KEY = "effect_index"
_NEW_KEY = "line_index"


def _rename_late_grant(step: Step) -> bool:
    """Rename the base's late Reveal grants in place; whether any was."""

    renamed = False
    for event in step.events:
        if event["kind"] != _OLD_KIND:
            continue
        event["kind"] = _NEW_KIND
        event["payload"] = [
            [_NEW_KEY if key == _OLD_KEY else key, value]
            for key, value in event["payload"]
        ]
        renamed = True
    return renamed


LATE_GRANT_NAME = Rule(
    name="late_grant_name",
    why="codec v151: a late Reveal grant is named after the Reveal line it pays",
    old=_rename_late_grant,
)

RULES = (LATE_GRANT_NAME,)
