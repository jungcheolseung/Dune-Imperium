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

RULES = (SPY_PASS_FIRST,)
