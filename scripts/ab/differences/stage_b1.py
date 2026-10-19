"""Declared differences of stage B1 against master ``e7e9ad4f`` (codec v149).

docs/stage-b-plan.md 3a, OQ-111: an Agent turn is a card pick
(``choose_agent_card``) and then a space pick (``place_agent``) instead of
one ``agent_turn`` placement. Everything else -- the state after the
placement, its events, every view and every other decision -- stays the
same, checked with ``engine_equivalence.py check --differences
scripts/ab/differences/stage_b1.py``. The pick waits in the turn frame
(left out of the comparison, like the whole decision stack), so a recorded
placement compares as its two moves: the state after both is the base's.
"""

from typing import Any

from equivalence_rules import At, Rule, Step

from dune_imperium.core.actions import DomainAction
from dune_imperium.rules.agent_turn import (
    agent_card_pick_actions,
    agent_space_pick_actions,
)

_PLACEMENT = "agent_turn"
_CARD_PICK = "choose_agent_card"
_PICKED_EVENT = "agent_card_picked"
# The seat's own view of its picked card (``PrivatePlayerView``), empty at
# every recorded step: both moves of a placement are inside one step. Keys
# are sorted in the compared text, and the private view has later keys.
_EMPTY_PICK_TEXT = '"agent_card_pick":"","agent_card_pick_graft":false,'
_PICK_KEYS = ("agent_card_pick", "agent_card_pick_graft")
# Page parts with one entry per legal row (``engine_equivalence.PAGE_PARTS``).
_PER_ROW_PARTS = (3, 5)


def _placement(step: tuple[Any, ...]) -> DomainAction | None:
    if step[0] != "a" or step[1] != _PLACEMENT:
        return None
    arguments = tuple((str(pair[0]), pair[1]) for pair in step[3])
    return DomainAction(action_id=_PLACEMENT, actor=step[2], arguments=arguments)


def _canonical(action: DomainAction) -> dict[str, Any]:
    return {
        "action_id": action.action_id,
        "actor": action.actor,
        "arguments": [list(pair) for pair in action.arguments],
    }


def _placement_moves(old: Step, at: At) -> tuple[DomainAction, ...] | None:
    """The base's placement as the candidate's card pick and space pick."""

    placement = _placement(old.step)
    if placement is None:
        return None
    (pick,) = agent_card_pick_actions(placement.actor, (placement,))
    arguments = dict(placement.arguments)
    card = arguments["card_id"]
    assert isinstance(card, str)
    (space,) = agent_space_pick_actions(
        placement.actor, (placement,), card, arguments.get("graft") is True
    )
    return (pick, space)


def _rows_with_card_picks(rows: list[Any]) -> list[Any]:
    """The base's legal rows with its placements as the card picks they
    start (one per card and graft choice, where its first placement was)."""

    out: list[Any] = []
    seen: set[tuple[Any, bool]] = set()
    for row in rows:
        if not (isinstance(row, dict) and row.get("action_id") == _PLACEMENT):
            out.append(row)
            continue
        arguments = {str(pair[0]): pair[1] for pair in row["arguments"]}
        key = (arguments["card_id"], arguments.get("graft") is True)
        if key in seen:
            continue
        seen.add(key)
        whole = DomainAction(
            _PLACEMENT, row["actor"], tuple((k, v) for k, v in arguments.items())
        )
        (pick,) = agent_card_pick_actions(row["actor"], (whole,))
        out.append(_canonical(pick))
    return out


def _empty_pick_dropped(candidate: Step) -> None:
    if candidate._views is not None:
        for view in candidate._views:
            private = view.get("private")
            if isinstance(private, dict) and private.get("agent_card_pick") == "":
                if private.get("agent_card_pick_graft") is False:
                    for key in _PICK_KEYS:
                        del private[key]
        return
    candidate.views_text = candidate.views_text.replace(_EMPTY_PICK_TEXT, "")


def _steps_in_base_form(old: Step, candidate: Step) -> None:
    """The candidate's card picks, pick event and empty pick view in the
    base's form."""

    _empty_pick_dropped(candidate)
    candidate.events = [
        event for event in candidate.events if event["kind"] != _PICKED_EVENT
    ]
    if not (isinstance(old.decision, list) and isinstance(candidate.decision, list)):
        return
    base, rows = old.decision[1], candidate.decision[1]
    if not (isinstance(base, list) and isinstance(rows, list)):
        return
    if not any(isinstance(r, dict) and r.get("action_id") == _CARD_PICK for r in rows):
        return
    if _rows_with_card_picks(base) != rows:
        return
    candidate.decision[1] = list(base)
    page, base_page = candidate.page, old.page
    if not (isinstance(page, list) and isinstance(base_page, list)):
        return
    for part in _PER_ROW_PARTS:
        mine, theirs = page[part], base_page[part]
        if (
            isinstance(mine, list)
            and isinstance(theirs, list)
            and len(mine) == len(rows)
            and len(theirs) == len(base)
            and all(entry is None for entry in mine)
            and all(entry is None for entry in theirs)
        ):
            page[part] = list(theirs)


AGENT_TURN_STEPS = Rule(
    name="agent_turn_steps",
    why="stage B1 (docs/stage-b-plan.md 3a, OQ-111): an Agent turn is a "
    "card pick and then a space pick",
    new=_steps_in_base_form,
    moves=_placement_moves,
)

RULES: tuple[Rule, ...] = (AGENT_TURN_STEPS,)
