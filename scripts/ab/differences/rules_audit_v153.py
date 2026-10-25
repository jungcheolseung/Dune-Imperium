"""Declared differences of codec v153 against master ``3890262f`` (codec v152).

The general rules audit's (2026-10-25) count-only events are served to every
seat: the Round Start discard reshuffle (``personal_discard_shuffled``, the
in-turn one was public already) and a Navigation card placed face down in
setup (``navigation_card_placed``, only its slot). "장수·수량만 담는 이벤트는
전원 공개다." (docs/rules/open-questions.md OQ-010 ruling 3). The batch's other
changes move play only where they apply (a lone Scouts Faction is asked,
Infiltrate stays open to other graft pairs, a refilled Harkonnen Advisor troop
stays undeployable, a Guild Spy played in an Agent turn no longer reacts), so
they are left to show as differences. Checked with ``engine_equivalence.py
check --differences scripts/ab/differences/rules_audit_v153.py``.
"""

from equivalence_rules import Rule, Step

_PUBLIC_KINDS = frozenset({"personal_discard_shuffled", "navigation_card_placed"})


def _publish_count_events(step: Step) -> bool:
    """Serve the base's count-only events to every seat; whether any was."""

    published = False
    for event in step.events:
        if event["kind"] in _PUBLIC_KINDS and event.get("visible_to") is not None:
            event["visible_to"] = None
            published = True
    return published


COUNT_EVENTS_PUBLIC = Rule(
    name="count_events_public",
    why="OQ-010 ruling 3: count-only events are public (rules audit 2026-10-25)",
    old=_publish_count_events,
)

RULES = (COUNT_EVENTS_PUBLIC,)
