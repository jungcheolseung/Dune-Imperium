"""Declared differences of cleanup-2d against the end of cleanup-2c.

docs/composed-effects-plan.md 5, "정리-2d": the hook conversions keep every
game the same as the recording of cleanup2 ``10f99778`` (the 2c end) but
for what is declared here, checked with ``engine_equivalence.py check
--differences scripts/ab/differences/cleanup2d.py``. ``cleanup2.py`` (the
whole of cleanup-2 against ``d892cd6c``) takes the same rules.
"""

import json

from equivalence_rules import Rule, Step

# The Intrigue executor's Spy pass-up (``ability_executor.piece_rows``).
_EXECUTOR_SPY_PASS = "decline_intrigue_spy"


def _same_items(old: list[object], new: list[object]) -> bool:
    key = lambda item: json.dumps(item, sort_keys=True)  # noqa: E731
    return sorted(map(key, old)) == sorted(map(key, new))


def _spy_pass_first(old: Step, candidate: Step) -> None:
    """2d-4: the executor's Spy pass-up row comes before its recalls and
    placements, as every other host's did (it came last); the same rows in
    the base's order."""

    if not (isinstance(candidate.decision, list) and isinstance(old.decision, list)):
        return
    rows, base = candidate.decision[1], old.decision[1]
    if (
        isinstance(rows, list)
        and isinstance(base, list)
        and rows != base
        and any(
            isinstance(row, dict) and row.get("action_id") == _EXECUTOR_SPY_PASS
            for row in rows
        )
        and _same_items(base, rows)
    ):
        candidate.decision[1] = list(base)
        page, base_page = candidate.page, old.page
        if (
            isinstance(page, list)
            and isinstance(base_page, list)
            and isinstance(page[1], dict)
            and isinstance(base_page[1], dict)
            and _same_items(base_page[1]["rows"], page[1]["rows"])
        ):
            page[1]["rows"] = list(base_page[1]["rows"])


SPY_PASS_FIRST = Rule(
    name="spy_pass_first",
    why="cleanup-2d-4: the Intrigue executor's Spy pass-up row comes first, "
    "as every other Spy host's",
    new=_spy_pass_first,
)

# The two retreats that moved units by hand before ``units.retreat_units``.
_RETREATS = {
    "retreat_leader_troop": 0,
    "retreat_leader_commander": 1,
    "retreat_two_troops_for_reveal": None,
}


def _arguments(step: Step) -> dict[str, object]:
    raw = step.step[3]
    if isinstance(raw, dict):
        return dict(raw)
    return {str(pair[0]): pair[1] for pair in raw or ()}


def _retreat_event(step: Step) -> None:
    """2d-4: Desert Scouts' retreat and the Reveal two-troop retreat log
    ``retreat_units``' event: id ``<source>:retreat``, and the Commander
    share in the payload (``commanders``, when not zero)."""

    if step.step[0] != "a" or step.step[1] not in _RETREATS:
        return
    commanders = _RETREATS[step.step[1]]
    if commanders is None:
        share = _arguments(step).get("commanders", 0)
        commanders = share if isinstance(share, int) else 0
    for event in step.events:
        event_id = str(event["event_id"])
        if event["kind"] == "troops_retreated" and event_id.endswith(
            ":troops_retreated"
        ):
            event["event_id"] = event_id.removesuffix("troops_retreated") + "retreat"
            payload = event["payload"]
            assert isinstance(payload, list)
            if commanders:
                event["payload"] = [["commanders", commanders], *payload]


RETREAT_EVENT = Rule(
    name="retreat_event",
    why="cleanup-2d-4: the hand-rolled retreats (Desert Scouts, the Reveal "
    "two-troop retreat) log retreat_units' event",
    old=_retreat_event,
)

RULES = (SPY_PASS_FIRST, RETREAT_EVENT)
