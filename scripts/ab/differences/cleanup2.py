"""Declared differences of the composed-effects cleanup-2 (branch ``cleanup2``).

docs/composed-effects-plan.md 5, "정리-2 계획": every change a player, an agent
or a save can see on purpose, as rules for ``engine_equivalence.py check
--differences scripts/ab/differences/cleanup2.py`` against the recording of
the stage's start master (``d892cd6c``). Each rule's ``why`` names the plan's
sub-stage; a sub-stage adds its rules here with its change.
"""

import json
import re

from equivalence_rules import At, Rule, Step

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


# --- 2b-1: research bonuses raised in the owner's turn wait on it ---------

_RESEARCH_ROWS = frozenset(
    {
        "choose_research_influence",
        "trash_intrigue_for_research_bonus",
        "pay_research_bonus",
    }
)
_IN_TURN_SOURCE = re.compile(r"^round:\d+:player:\d+:")
# The page's greyed-out rows of a waiting research bonus (display.unavailable
# ``_pending_research``).
_RESEARCH_ROW_KEY = re.compile(r"^(choice|waiting):research_(influence|bonus_)")


def _seat_view(step: Step) -> dict[str, object]:
    return step.views[step.step[2]] if step.step[0] == "a" else {}


def _in_turn_window(step: Step, kind: str) -> bool:
    """A base step answering a ``kind`` window raised in its owner's own turn
    (its events name a player's source; Combat and the Scouts step keep the
    window)."""

    if step.step[0] != "a":
        return False
    view = _seat_view(step)
    if view.get("decision_kind") != kind or view.get("phase") == "combat":
        return False
    ids = [event["event_id"] for event in step.events]
    return bool(ids) and all(_IN_TURN_SOURCE.match(i) for i in ids[:1])


def _in_turn_research_window(step: Step) -> bool:
    return _in_turn_window(step, "research_bonus")


def _research_decline_vanishes(step: Step) -> None:
    """2b-1: the in-turn decline has no counterpart (the bonus waits and the
    turn end lapses it); its event goes with it."""

    if step.step[1] == "decline_research_bonus" and _in_turn_research_window(step):
        step.vanish = True
        step.events = [e for e in step.events if e["kind"] != "research_bonus_declined"]


def _research_window_rows(step: Step) -> None:
    """2b-1: the base's window offered its decline beside the rows."""

    if _in_turn_research_window(step) and isinstance(step.decision, list):
        rows = step.decision[1]
        step.decision[1] = [
            r for r in rows if r["action_id"] != "decline_research_bonus"
        ]


def _only_research_rows(old: Step, candidate: Step) -> None:
    """2b-1: where the base answered its window, the candidate offers the
    same rows inside its turn's list: compare those, with the window's
    views and page."""

    if not _in_turn_research_window(old) or not isinstance(candidate.decision, list):
        return
    candidate.decision[1] = [
        r for r in candidate.decision[1] if r["action_id"] in _RESEARCH_ROWS
    ]
    for view, base in zip(candidate.views, old.views, strict=True):
        view["decision_kind"] = base["decision_kind"]
        view["turn_owner"] = base["turn_owner"]
    candidate.page = old.page


def _no_waiting_research(old: Step, candidate: Step) -> None:
    """2b-1: a bonus the base declined still waits in the candidate's turn
    until the turn end lapses it: its rows (and with them the page, whose
    per-row parts follow the list and whose dimmed cards spare an Intrigue
    card the trash row could take) or, offering nothing, its greyed-out row."""

    if (
        old.step[0] != "a"
        or _in_turn_research_window(old)
        or not isinstance(candidate.decision, list)
        or not isinstance(candidate.decision[1], list)
    ):
        return
    offered = (
        {r["action_id"] for r in old.decision[1]}
        if isinstance(old.decision, list) and isinstance(old.decision[1], list)
        else set()
    )
    rows = [
        r
        for r in candidate.decision[1]
        if r["action_id"] not in _RESEARCH_ROWS or r["action_id"] in offered
    ]
    if len(rows) != len(candidate.decision[1]):
        candidate.decision[1] = rows
        candidate.page = old.page
        return
    page = candidate.page
    if isinstance(page, list) and isinstance(page[1], dict):
        kept = [r for r in page[1]["rows"] if not _RESEARCH_ROW_KEY.match(r["key"])]
        if len(kept) == len(page[1]["rows"]):
            return
        if not kept and (not isinstance(old.page, list) or old.page[1] is None):
            page[1] = None
        else:
            page[1]["rows"] = kept


def _no_research_lapse(old: Step, candidate: Step) -> None:
    """2b-1: the turn end lapses a waiting bonus with an event."""

    candidate.events = [
        e for e in candidate.events if e["kind"] != "research_bonus_lapsed"
    ]


# --- 2b-2: optional trash icons raised in the owner's turn wait on it ------

# The rows a trash window offered beside its decline: the trash, the
# Planetologist's Intrigue card, and a triggered draw waiting in the turn.
_TRASH_WINDOW_ROWS = frozenset(
    {
        "trash_optional_card",
        "draw_planetologist_intrigue",
        "draw_owed_intrigue",
        "draw_owed_card",
    }
)
# The rows only a waiting trash offers in the candidate's turn.
_WAITING_TRASH_ROWS = frozenset({"trash_optional_card", "draw_planetologist_intrigue"})


def _scouts_trash_items() -> frozenset[str]:
    from dune_imperium.content.arrakeen_scouts.abilities import SCOUTS_ABILITIES
    from dune_imperium.content.uprising.effect_dsl import TrashPersonalCard

    return frozenset(
        item
        for item, ability in SCOUTS_ABILITIES.items()
        for section in ability.sections
        if any(isinstance(reward, TrashPersonalCard) for reward in section.rewards)
    )


# A Scouts line's trash icon run inside the turn (Oversight at the High
# Council) keeps its window: its source is ``<line source>:<step>``, the line
# source ending with the item id.
_SCOUTS_LINE_TRASH = re.compile(rf":(?:{'|'.join(sorted(_scouts_trash_items()))}):\d+:")


def _in_turn_trash_window(step: Step) -> bool:
    return _in_turn_window(step, "optional_trash") and not any(
        _SCOUTS_LINE_TRASH.search(event["event_id"]) for event in step.events[:1]
    )


def _row_key(row: object) -> str:
    return json.dumps(row, sort_keys=True)


def _trash_decline_vanishes(step: Step) -> None:
    """2b-2: the in-turn decline has no counterpart (the trash waits and the
    turn end lapses it); its event goes with it."""

    if step.step[1] == "decline_optional_trash" and _in_turn_trash_window(step):
        step.vanish = True
        step.events = [e for e in step.events if e["kind"] != "optional_trash_declined"]


def _trash_window_rows(step: Step) -> None:
    """2b-2: the base's window offered its decline beside the rows."""

    if _in_turn_trash_window(step) and isinstance(step.decision, list):
        step.decision[1] = [
            r for r in step.decision[1] if r["action_id"] != "decline_optional_trash"
        ]


def _only_trash_rows(old: Step, candidate: Step) -> None:
    """2b-2: where the base answered its window, the candidate offers the
    same rows inside its turn's list: compare those, in the window's order,
    with the window's views and page."""

    if not _in_turn_trash_window(old) or not isinstance(candidate.decision, list):
        return
    order = {
        _row_key(r): index
        for index, r in enumerate(
            old.decision[1] if isinstance(old.decision, list) else []
        )
    }
    offered = {r["action_id"] for r in old.decision[1]} if order else set()
    rows = [
        r
        for r in candidate.decision[1]
        if r["action_id"] in _TRASH_WINDOW_ROWS and r["action_id"] in offered
    ]
    candidate.decision[1] = sorted(
        rows, key=lambda r: order.get(_row_key(r), len(order))
    )
    for view, base in zip(candidate.views, old.views, strict=True):
        view["decision_kind"] = base["decision_kind"]
        view["turn_owner"] = base["turn_owner"]
        # A box whose card a trash took expires at once in the candidate
        # (``trash_expiry_moves``); the base showed it until its windows
        # closed.
        view["agent_boxes"] = base["agent_boxes"]
    candidate.page = old.page


def _no_waiting_trash(old: Step, candidate: Step) -> None:
    """2b-2: a trash the base declined still waits in the candidate's turn
    until the turn end lapses it: its rows go (and with them the page, whose
    per-row parts follow the list)."""

    if (
        old.step[0] != "a"
        or _in_turn_trash_window(old)
        or not isinstance(candidate.decision, list)
        or not isinstance(candidate.decision[1], list)
    ):
        return
    offered = (
        {r["action_id"] for r in old.decision[1]}
        if isinstance(old.decision, list) and isinstance(old.decision[1], list)
        else set()
    )
    rows = [
        r
        for r in candidate.decision[1]
        if r["action_id"] not in _WAITING_TRASH_ROWS or r["action_id"] in offered
    ]
    if len(rows) != len(candidate.decision[1]):
        candidate.decision[1] = rows
        candidate.page = old.page


# The expiry events the candidate made at a trash that the base made later,
# by id, and the last step index seen (a lower one starts another game).
_carried_expiries: dict[str, dict[str, object]] = {}
_last_index = [-1]


def _expiry_at_the_trash(old: Step, candidate: Step) -> None:
    """2b-2: trashing a card whose Agent box still waits expires the box at
    once (``agent_effects.expire_trashed_card_effects`` runs when the turn's
    effect frame is on top). The base held stacked windows over that frame
    -- two Arrakis Planetologist replacements -- so its expiry came when the
    last of them closed: the candidate's event moves to that step."""

    if old.index <= _last_index[0]:
        _carried_expiries.clear()
    _last_index[0] = old.index
    old_ids = [event["event_id"] for event in old.events]
    new_ids = {event["event_id"] for event in candidate.events}
    for event_id in [i for i in _carried_expiries if i in old_ids and i not in new_ids]:
        candidate.events.insert(
            min(old_ids.index(event_id), len(candidate.events)),
            _carried_expiries.pop(event_id),
        )
    if not _in_turn_trash_window(old):
        return
    for event in list(candidate.events):
        if (
            event["kind"] == "agent_card_effect_expired"
            and event["event_id"] not in old_ids
        ):
            candidate.events.remove(event)
            _carried_expiries[event["event_id"]] = event


def _no_trash_lapse(old: Step, candidate: Step) -> None:
    """2b-2: the turn end lapses a waiting trash with an event."""

    candidate.events = [
        e for e in candidate.events if e["kind"] != "optional_trash_lapsed"
    ]


# --- 2b-3: no Faction at the top for Shipping and the Tech acquire Influence


def _at_the_top(step: Step, faction: object) -> bool:
    seat = step.step[2]
    influence = _seat_view(step)["players"][seat]["influence"]
    return isinstance(faction, str) and influence[faction] >= 6


# The page's parts that hold one entry per legal row (``_page``):
# ``agent_box_of_rows`` and ``reveal_choice_of_rows``.
_PER_ROW_PARTS = (3, 5)


def _tech_influence_rows(step: Step) -> None:
    """2b-3: the base offered a Tech acquire "Influence with any Faction"
    for a Faction at the top too (Glowglobes, Navigation Chamber); its rows
    go, with their entries of the page's per-row parts."""

    if step.step[0] != "a" or not isinstance(step.decision, list):
        return
    rows = step.decision[1]
    if not isinstance(rows, list):
        return
    keep = [
        not (
            r["action_id"] == "resolve_tech_acquire_effect"
            and dict(r["arguments"]).get("effect") == "influence"
            and _at_the_top(step, dict(r["arguments"]).get("faction"))
        )
        for r in rows
    ]
    if all(keep):
        return
    step.decision[1] = [r for r, kept in zip(rows, keep, strict=True) if kept]
    if isinstance(step.page, list):
        for part in _PER_ROW_PARTS:
            entries = step.page[part]
            if isinstance(entries, list) and len(entries) == len(keep):
                step.page[part] = [
                    e for e, kept in zip(entries, keep, strict=True) if kept
                ]


_TECH_INFLUENCE_ROW_KEY = re.compile(r"^(choice|waiting):tech_acquire_influence:")


def _no_greyed_tech_influence(old: Step, candidate: Step) -> None:
    """2b-3: the candidate's page greys those Factions out."""

    page = candidate.page
    if not isinstance(page, list) or not isinstance(page[1], dict):
        return
    kept = [r for r in page[1]["rows"] if not _TECH_INFLUENCE_ROW_KEY.match(r["key"])]
    if len(kept) == len(page[1]["rows"]):
        return
    if not kept and (not isinstance(old.page, list) or old.page[1] is None):
        page[1] = None
    else:
        page[1]["rows"] = kept


RULES = (
    Rule(
        "scouts_no_option_window",
        why="cleanup-2a: decision 6, OQ-071 addendum (a Scouts seat with no line "
        "is asked)",
        answer=_scouts_no_option,
    ),
    Rule(
        "research_decline_vanishes",
        why="cleanup-2b: decision 2 (OQ-095 (2)), no in-turn research refusal",
        old=_research_decline_vanishes,
    ),
    Rule(
        "research_window_rows",
        why="cleanup-2b: decision 2, the in-turn window's decline row goes",
        old=_research_window_rows,
    ),
    Rule(
        "research_rows_in_the_turn",
        why="cleanup-2b: decision 2, the window's rows are turn rows",
        new=_only_research_rows,
    ),
    Rule(
        "research_rows_wait",
        why="cleanup-2b: decision 2, an unused bonus waits until the turn end",
        new=_no_waiting_research,
    ),
    Rule(
        "research_lapse_event",
        why="cleanup-2b: decision 2, the turn end lapses it with an event",
        new=_no_research_lapse,
    ),
    Rule(
        "trash_decline_vanishes",
        why="cleanup-2b: decision 2 (OQ-095 (2)), no in-turn trash refusal",
        old=_trash_decline_vanishes,
    ),
    Rule(
        "trash_window_rows",
        why="cleanup-2b: decision 2, the in-turn window's decline row goes",
        old=_trash_window_rows,
    ),
    Rule(
        "trash_rows_in_the_turn",
        why="cleanup-2b: decision 2, the window's rows are turn rows",
        new=_only_trash_rows,
    ),
    Rule(
        "trash_rows_wait",
        why="cleanup-2b: decision 2, an unused trash waits until the turn end",
        new=_no_waiting_trash,
    ),
    Rule(
        "trash_expiry_moves",
        why="cleanup-2b: decision 2, a trashed card's waiting box expires at "
        "the trash, not when the stacked windows close",
        new=_expiry_at_the_trash,
    ),
    Rule(
        "trash_lapse_event",
        why="cleanup-2b: decision 2, the turn end lapses it with an event",
        new=_no_trash_lapse,
    ),
    Rule(
        "tech_influence_rows",
        why="cleanup-2b: decision 1 (OQ-060), no Tech acquire Influence for a "
        "Faction at the top",
        old=_tech_influence_rows,
    ),
    Rule(
        "tech_influence_greyed",
        why="cleanup-2b: decision 1, the page greys those Factions out",
        new=_no_greyed_tech_influence,
    ),
)
