"""Declared differences of the composed-effects cleanup-2 (branch ``cleanup2``).

docs/composed-effects-plan.md 5, "정리-2 계획": every change a player, an agent
or a save can see on purpose, as rules for ``engine_equivalence.py check
--differences scripts/ab/differences/cleanup2.py`` against the recording of
the stage's start master (``d892cd6c``). Each rule's ``why`` names the plan's
sub-stage; a sub-stage adds its rules here with its change.
"""

import json
import re
from collections import Counter

from equivalence_rules import At, Rule, Step

from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.state import GamePhase
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


# Per game: the sources of in-turn refusals the candidate has no counterpart
# for (a bonus or trash that waits until the turn end lapses it), until that
# lapse is seen; the expiry events carried to a later step
# (``_expiry_at_the_trash``); and the last step index seen (a lower one starts
# another game).
_VANISHED: dict[str, set[str]] = {"research": set(), "trash": set()}
_carried_expiries: dict[str, dict[str, object]] = {}
_last_index = [-1]
_SOURCE_SEAT = re.compile(r"^round:\d+:player:(\d+):")
_TURN_FRAME_KINDS = frozenset({"turn", "agent_effects", "reveal"})


def _game_at(index: int) -> None:
    """Start a new game's bookkeeping at a lower step index; an expiry or a
    Conflict-end event the candidate moved that the base never logged is a
    difference (reported on the next game's first step, the bookkeeping
    cleared first so it is reported once)."""

    if index >= _last_index[0]:
        _last_index[0] = index
        return
    expiries = sorted(_carried_expiries)
    carried = [event["event_id"] for event in _CONFLICT_END_CARRY]
    _carried_expiries.clear()
    for sources in _VANISHED.values():
        sources.clear()
    _reset_conflict_end()
    _last_index[0] = index
    if expiries:
        raise AssertionError(f"expiry events the base never logged: {expiries}")
    if carried:
        raise AssertionError(
            "the previous game ended with Conflict-end events the base never "
            f"logged: {carried}"
        )


def _vanished(kind: str, step: Step, suffix: str) -> None:
    for event in step.events:
        if event["event_id"].endswith(suffix):
            _VANISHED[kind].add(event["event_id"].removesuffix(suffix))


def _waits_for(kind: str, seat: object) -> bool:
    """Whether a refusal of ``kind`` by ``seat`` vanished and its lapse is
    still to come."""

    return any(
        (match := _SOURCE_SEAT.match(source)) is not None
        and int(match.group(1)) == seat
        for source in _VANISHED[kind]
    )


def _lapsed(kind: str, candidate: Step, event_kind: str, suffix: str) -> None:
    """Drop the lapse events of the vanished refusals, which ends them."""

    kept = []
    for event in candidate.events:
        source = event["event_id"].removesuffix(suffix)
        if event["kind"] == event_kind and source in _VANISHED[kind]:
            _VANISHED[kind].discard(source)
            continue
        kept.append(event)
    candidate.events = kept


def _at_a_turn_frame(old: Step, candidate: Step) -> bool:
    seat = old.step[2]
    return bool(candidate.views) and (
        candidate.views[seat].get("decision_kind") in _TURN_FRAME_KINDS
    )


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

    _game_at(step.index)
    if step.step[1] == "decline_research_bonus" and _in_turn_research_window(step):
        step.vanish = True
        _vanished("research", step, ":bonus_declined")
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

    if (
        not _in_turn_research_window(old)
        or not isinstance(candidate.decision, list)
        or not _at_a_turn_frame(old, candidate)
    ):
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
        or not _waits_for("research", old.step[2])
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
    """2b-1: the turn end lapses a waiting bonus with an event (one whose
    in-turn refusal vanished)."""

    _lapsed("research", candidate, "research_bonus_lapsed", ":bonus_lapsed")


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

    _game_at(step.index)
    if step.step[1] == "decline_optional_trash" and _in_turn_trash_window(step):
        step.vanish = True
        _vanished("trash", step, ":trash_declined")
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

    if (
        not _in_turn_trash_window(old)
        or not isinstance(candidate.decision, list)
        or not _at_a_turn_frame(old, candidate)
    ):
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
        or not _waits_for("trash", old.step[2])
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


def _expiry_at_the_trash(old: Step, candidate: Step) -> None:
    """2b-2: trashing a card whose Agent box still waits expires the box at
    once (``agent_effects.expire_trashed_card_effects`` runs when the turn's
    effect frame is on top). The base held stacked windows over that frame
    -- two Arrakis Planetologist replacements -- so its expiry came when the
    last of them closed: the candidate's event moves to that step."""

    _game_at(old.index)
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
    """2b-2: the turn end lapses a waiting trash with an event (one whose
    in-turn refusal vanished)."""

    _lapsed("trash", candidate, "optional_trash_lapsed", ":trash_lapsed")


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


# --- 2b-4: a research space's paired icons and c7r3's rewards in order ----


# ``immortality.RESEARCH_ICON_ORDER`` and ``OWED_ORIGIN_RESEARCH`` and the
# owed-draw decks, spelled out: ``time_legal.py`` runs these rules on the base
# engine too, which has none of them.
_RESEARCH_ICON_ORDER = ("specimen", "tleilaxu", "trash", "intrigue", "cards")
_OWED_ORIGIN_RESEARCH = "research_c7r3"
_OWED_DECKS = (("intrigue", "draw_owed_intrigue"), ("card", "draw_owed_card"))


def _next_owed(owed: tuple[tuple[str, str, str], ...], deck: str) -> int | None:
    """The waiting draw a press of ``deck``'s action takes (the oldest of
    the deck; none of the c7r3 draws is immediate)."""

    return next((i for i, (d, _, _) in enumerate(owed) if d == deck), None)


def _research_icons_in_base_order(at: At) -> object:
    """2b-4: each icon of a research space's pair (and c7r3's rewards) is
    its own step now, a turn row, an owed draw or a window; the base
    resolved them inside the step that raised them, in the order
    ``RESEARCH_ICON_ORDER`` keeps."""

    if not isinstance(at.decision, PlayerDecision):
        return None
    icons = {
        dict(action.arguments)["effect"]: action
        for action in at.legal
        if action.action_id == "resolve_research_icon"
    }
    for icon in _RESEARCH_ICON_ORDER:
        if icon in icons:
            return icons[icon]
    owed = at.state.players[at.decision.owner].owed_draws
    for deck, action_id in _OWED_DECKS:
        index = _next_owed(owed, deck)
        if index is not None and owed[index][1] == _OWED_ORIGIN_RESEARCH:
            return next(
                (action for action in at.legal if action.action_id == action_id),
                None,
            )
    return None


_RESEARCH_ICON_SOURCE = re.compile(r":research:c\d+r\d+:")


def _research_icon_events_in_base_order(old: Step, candidate: Step) -> None:
    """2b-4: the icons answered after the step log their events after the
    step's own (the base logged them inside it, before its closing event):
    the same events, put back in the base's order. Only when an answered
    research icon logged one (``:research:cNrM:`` in its source) and the
    two sides hold exactly the same events."""

    if not any(_RESEARCH_ICON_SOURCE.search(e["event_id"]) for e in candidate.events):
        return
    texts = [_row_key(e) for e in candidate.events]
    base = [_row_key(e) for e in old.events]
    if texts == base or sorted(texts) != sorted(base):
        return
    by_text: dict[str, list[dict[str, object]]] = {}
    for text, event in zip(texts, candidate.events, strict=True):
        by_text.setdefault(text, []).append(event)
    candidate.events = [by_text[text].pop(0) for text in base]


# --- Conflict end (user decision 2026-10-18): the troops go back first, then
# the windows; Harvest Cells resolves as it is played -------------------------

_HARVEST_CELLS_CHOICES = frozenset(
    {
        "acquire_intrigue_reclaimed_forces",
        "acquire_intrigue_tleilaxu",
        "decline_intrigue_tleilaxu",
    }
)
# Per game: the window interval (from the base's offering step), the base
# steps answered early (Harvest Cells' acquisition) and the seats that played
# in their window, and the candidate events moved to a later base step.
_CONFLICT_END: dict[str, object] = {}
_CONFLICT_END_CARRY: list[dict[str, object]] = []


def _reset_conflict_end() -> None:
    _CONFLICT_END.clear()
    _CONFLICT_END.update(open=False, ahead=set(), played=set())
    _CONFLICT_END_CARRY.clear()


_reset_conflict_end()


def _ahead() -> set[int]:
    ahead = _CONFLICT_END["ahead"]
    assert isinstance(ahead, set)
    return ahead


def _played() -> set[int]:
    played = _CONFLICT_END["played"]
    assert isinstance(played, set)
    return played


def _kinds(step: Step) -> set[str]:
    return {event["kind"] for event in step.events}


def _conflict_end_finish(step: Step) -> None:
    """The window's press after a play is ``finish_conflict_end_intrigue``
    (the base offered its decline again)."""

    _game_at(step.index)
    if "conflict_end_trigger_offered" in _kinds(step):
        _played().clear()
        _CONFLICT_END["plays"] = 0
    if step.step[0] != "a":
        return
    seat = step.step[2]
    playing = step.step[1] == "play_conflict_end_intrigue"
    if playing:
        _CONFLICT_END["plays"] = int(str(_CONFLICT_END.get("plays", 0))) + 1
    if seat not in _played() or _seat_view(step).get("decision_kind") != (
        "conflict_end_trigger"
    ):
        if playing:
            _played().add(seat)
        return
    if isinstance(step.decision, list):
        step.decision[1] = [
            {**r, "action_id": "finish_conflict_end_intrigue"}
            if r["action_id"] == "decline_conflict_end_intrigue"
            else r
            for r in step.decision[1]
        ]
    if step.step[1] == "decline_conflict_end_intrigue":
        step.step = ("a", "finish_conflict_end_intrigue", seat, step.step[3])
        step.events = [
            {
                **e,
                "kind": "conflict_end_trigger_finished",
                "event_id": e["event_id"].replace(":declined", ":finished"),
            }
            if e["kind"] == "conflict_end_trigger_declined"
            else e
            for e in step.events
        ]


def _harvest_cells_now(at: At) -> object:
    """Harvest Cells' acquisition is asked as it is played; the base asked
    it after the cleanup: answer with the base's later choice."""

    if not isinstance(at.decision, PlayerDecision):
        return None
    top = at.state.decision_stack[-1]
    source = dict(top.context).get("source")
    if (
        top.kind != FrameKind.INTRIGUE_CHOICE
        or not isinstance(source, str)
        or ":conflict_end:" not in source
    ):
        return None
    owner = at.decision.owner
    for index in range(at.index + 1, len(at.rows)):
        step = at.rows[index][0]
        if (
            step[0] == "a"
            and step[2] == owner
            and step[1] in _HARVEST_CELLS_CHOICES
            and index not in _ahead()
        ):
            _ahead().add(index)
            return next(
                (
                    action
                    for action in at.legal
                    if action.action_id == step[1]
                    and tuple(action.arguments) == tuple(map(tuple, step[3]))
                ),
                None,
            )
    return None


# Logged as the windows open (the Conflict card's award, the troops' return)
# where the base logged them at its cleanup.
_AT_THE_WINDOWS = frozenset(
    {"battle_icons_matched", "conflict_won", "tactics_token_advanced"}
)


def _carried(event: dict[str, object]) -> bool:
    event_id = str(event["event_id"])
    return (
        event["kind"] in _AT_THE_WINDOWS
        or ":conflict_end:" in event_id
        or ":tech_draw:" in event_id
    )


# One seat's two copies: the candidate resolves each as it is played, the
# base resolved them at the cleanup, the later-played copy first; the
# candidate's first acquisition takes the base's first answer.
_HARVEST_CELLS_COPY = re.compile(r"(?<=harvest_cells:)\d+")


def _harvest_cells_key(event: dict[str, object]) -> str:
    """An event's text for matching: Harvest Cells' rewards log under
    ``<source>:rewards`` when they apply on their own (as the candidate
    applies them at the play) and under ``<source>`` when the card's last
    choice applied them (as the base did when its acquisition came first),
    and either copy matches (``_HARVEST_CELLS_COPY``)."""

    event_id = str(event["event_id"]).replace(":rewards:", ":")
    return _row_key({**event, "event_id": _HARVEST_CELLS_COPY.sub("#", event_id)})


def _harvest_cells_steps(step: Step) -> None:
    """The base's Harvest Cells steps after the cleanup -- its acquisition,
    answered early, and its automatic rewards -- have no counterpart; their
    events are the ones the candidate logged at the play. The base's
    ``intrigue_trigger_fired`` has none either."""

    step.events = [
        e
        for e in step.events
        if e["kind"] != "intrigue_trigger_fired"
        and e["event_id"] not in _moved_shuffles()
    ]
    rewards = (
        step.step[0] == "a"
        and step.step[1] == "resolve_intrigue_rewards"
        and any(":conflict_end:" in e["event_id"] for e in step.events)
    )
    if step.index not in _ahead() and not rewards:
        return
    step.vanish = True
    left = []
    for event in step.events:
        match = next(
            (
                c
                for c in _CONFLICT_END_CARRY
                if _harvest_cells_key(c) == _harvest_cells_key(event)
            ),
            None,
        )
        if match is None:
            left.append(event)
        else:
            _CONFLICT_END_CARRY.remove(match)
    step.events = left


# What the Conflict card's award and the troops' return before the windows
# move (with the Tactician token's spice and water and a matched battle
# icon's Victory Point): each seat's state fields and view keys, and the
# board's current Conflict.
_RETURN_KEYS = (
    "troops_supply",
    "troops_conflict",
    "commanders_supply",
    "commanders_conflict",
    "tactics_track_space",
    "resources",
    "won_conflict_ids",
    "face_down_battle_card_ids",
    "victory_points",
)


def _returned_early(old: Step, candidate: Step, *, after: bool = True) -> None:
    """In the views before the step every seat's return keys and the current
    Conflict are the base's, and (``after``) those fields are left out of
    the state after it."""

    if after:
        candidate.fields_unchecked.update(
            f"players[{seat}].{key}" for seat in range(4) for key in _RETURN_KEYS
        )
        candidate.fields_unchecked.add("current_conflict_ids")
    if not (candidate.views and old.views):
        return
    for base, view in zip(old.views, candidate.views, strict=True):
        view["current_conflict_ids"] = base["current_conflict_ids"]
        for seat, players in enumerate(view["players"]):
            for key in _RETURN_KEYS:
                players[key] = base["players"][seat][key]


def _conflict_end_interval(old: Step, candidate: Step) -> None:
    """From the base's offering step to its cleanup (or the last Harvest
    Cells acquisition it answered after it), the candidate's troops are back
    in the supply: until a Harvest Cells is played only the return's fields
    differ (``_returned_early``). From a play on the candidate has also
    resolved the card: its views are the base's but for each seat's hand,
    the window's page is the base's, and the state after the step is not
    compared."""

    kinds = _kinds(old)
    if "conflict_end_trigger_offered" in kinds:
        _CONFLICT_END["open"] = True
        _returned_early(old, candidate)
        return
    if not _CONFLICT_END["open"]:
        return
    pending = [index for index in _ahead() if index > old.index]
    cleaned = "combat_cleaned_up" in kinds or _CONFLICT_END.get("cleaned") is True
    if "combat_cleaned_up" in kinds:
        _CONFLICT_END["cleaned"] = True
    closing = cleaned and not pending
    if not int(str(_CONFLICT_END.get("plays", 0))):
        _returned_early(old, candidate, after=not closing)
    else:
        if candidate.views and old.views:
            hands = [
                (
                    [players["hand_size"] for players in view["players"]],
                    view["private"]["hand"],
                )
                for view in candidate.views
            ]
            candidate._views = [json.loads(json.dumps(view)) for view in old.views]
            for view, (sizes, hand) in zip(candidate._views, hands, strict=True):
                for players, size in zip(view["players"], sizes, strict=True):
                    players["hand_size"] = size
                view["private"]["hand"] = hand
        if _seat_view(old).get("decision_kind") == "conflict_end_trigger":
            candidate.page = old.page
        if not closing:
            old.state_unchecked = True
    if closing:
        _CONFLICT_END["open"] = False
        _CONFLICT_END["cleaned"] = False
        _CONFLICT_END["closing"] = True


_PLANETARY_ARRAY = "planetary_array"
_DRAW_FIELDS = ("hand", "deck", "discard_pile", "tech_cards_owed")


def _draw_views_differ(old: Step, candidate: Step, seat: int) -> bool:
    """Whether the seat's hand, deck (its size and pool) and discard differ
    in the views, after putting the base's in the candidate's."""

    differ = False
    for base, view in zip(old.views, candidate.views, strict=True):
        pairs = [
            (view["players"][seat], base["players"][seat], key)
            for key in ("hand_size", "deck_size", "deck_pool", "discard_pile")
        ]
        if view.get("player") == seat:
            # Glowglobes shows its owner the deck's top card.
            pairs += [
                (view["private"], base["private"], key)
                for key in ("hand", "deck_size", "peeked_card_id")
            ]
        for mine, theirs, key in pairs:
            if mine[key] != theirs[key]:
                differ = True
                mine[key] = theirs[key]
    return differ


def _planetary_array_at_the_win(old: Step, candidate: Step) -> None:
    """OQ-108 (user decision 2026-10-18): the candidate draws Planetary
    Array's card as the Conflict is won, before the windows ("When you win
    a Conflict: draw a card"); the base drew it at its cleanup when a
    Harvest Cells fired there, else after the next round's hand. Until the
    base draws the same card the seat's hand, deck, discard and owed count
    are the base's in the views and left out of the state."""

    candidate.events = [
        e for e in candidate.events if e["event_id"] not in _moved_shuffles()
    ]
    ahead_until = _CONFLICT_END.get("ahead_until")
    if isinstance(ahead_until, int):
        # From the base's Round Start pause, which its shuffle then held up,
        # to that shuffle, the candidate's Round Start is a step ahead.
        if old.step[0] == "c" and str(old.step[1]).endswith(":round_start:pause"):
            _CONFLICT_END["ahead_started"] = True
        if old.index >= ahead_until:
            _CONFLICT_END.pop("ahead_until")
            _CONFLICT_END.pop("ahead_started", None)
        elif _CONFLICT_END.get("ahead_started"):
            old.state_unchecked = True
    early = _CONFLICT_END.setdefault("early_draws", {})
    assert isinstance(early, dict)
    started = set()
    for event in candidate.events:
        if event["kind"] != "conflict_won" or not old.views:
            continue
        seat = dict(event["payload"])["player"]
        if _PLANETARY_ARRAY in old.views[0]["players"][seat]["tech_ids"]:
            early[seat] = old.views[0]["round_number"]
            started.add(seat)
    for seat, won in list(early.items()):
        if seat not in started and old.views and candidate.views:
            if not _draw_views_differ(old, candidate, seat):
                del early[seat]
                continue
            if old.views[0]["round_number"] > won + 1:
                raise AssertionError(f"Planetary Array's card never came: {seat}")
        candidate.fields_unchecked.update(
            f"players[{seat}].{name}" for name in _DRAW_FIELDS
        )


def _tech_draw_now(at: At) -> object:
    """OQ-108: Planetary Array's card is drawn as the Conflict is won; a base
    that drew it at its cleanup (a Harvest Cells fired there) recorded its
    reshuffle under the same decision, which is the answer."""

    if (
        not isinstance(at.decision, ChanceDecision)
        or ":tech_draw:" not in at.decision.decision_id
        or at.state.phase is not GamePhase.COMBAT
        or not at.state.combat_end_triggers_offered
    ):
        return None
    for index in range(at.index + 1, len(at.rows)):
        step = at.rows[index][0]
        if step[0] == "c" and step[1] == at.decision.decision_id:
            _ahead().add(index)
            return ChanceOutcome(decision_id=step[1], values=tuple(step[2]))
    return None


_PERSONAL_SHUFFLE = re.compile(r"^round:\d+:player:(\d+):(?:.+:)?discard_shuffle$")
_ROUND_START_SHUFFLE = re.compile(r"^round:\d+:player:\d+:discard_shuffle$")


def _moved_shuffles() -> set[str]:
    moved = _CONFLICT_END.setdefault("moved_shuffles", set())
    assert isinstance(moved, set)
    return moved


def _reshuffle_now(at: At) -> object:
    """OQ-108: with Planetary Array's card drawn at the win, its seat
    reshuffles its discard a round earlier (at the win or the next Round
    Start) where the base shuffled the same cards for that card after the
    next round's hand. The base's permutation of those cards is the answer;
    both shuffles' events are left out (the shuffle moved)."""

    if not isinstance(at.decision, ChanceDecision):
        return None
    asked = _PERSONAL_SHUFFLE.match(at.decision.decision_id)
    if asked is None or _PLANETARY_ARRAY not in (
        at.state.players[int(asked.group(1))].tech_ids
    ):
        return None
    following = next(
        (
            at.rows[index][0]
            for index in range(at.index + 1, len(at.rows))
            if index not in _ahead()
        ),
        None,
    )
    if following is not None and following[0] == "c" and following[1] == (
        at.decision.decision_id
    ):
        return None
    cards = sorted(at.decision.options)
    for index in range(at.index + 1, min(len(at.rows), at.index + 200)):
        step = at.rows[index][0]
        if index in _ahead() or step[0] != "c":
            continue
        recorded = _PERSONAL_SHUFFLE.match(step[1])
        if (
            recorded is not None
            and recorded.group(1) == asked.group(1)
            # One side is that card's draw (``...:tech_draw:discard_shuffle``).
            and ":tech_draw:discard_shuffle" in f"{at.decision.decision_id} {step[1]}"
            and sorted(step[2]) == cards
        ):
            _ahead().add(index)
            _moved_shuffles().update((f"{step[1]}d", f"{at.decision.decision_id}d"))
            if _ROUND_START_SHUFFLE.match(step[1]):
                # The base's Round Start waited for that shuffle; the
                # candidate's ran on, a step ahead until the base's.
                _CONFLICT_END["ahead_until"] = index
            return ChanceOutcome(
                decision_id=at.decision.decision_id, values=tuple(step[2])
            )
    return None


_WINDOW_STEPS = frozenset(
    {
        "decline_conflict_end_intrigue",
        "finish_conflict_end_intrigue",
        "play_conflict_end_intrigue",
    }
)


def _conflict_end_reopened(at: At) -> object:
    """OQ-109 (user decision 2026-10-18): a played window stays open while
    its seat holds an Intrigue card, judged when it comes back on top, so a
    seat whose play emptied its hand sees it again if the card's acquisition
    drew one. The base, which drew that card at its cleanup, went on to
    another step: the candidate finishes the window."""

    if not isinstance(at.decision, PlayerDecision):
        return None
    top = at.state.decision_stack[-1]
    if (
        top.kind != FrameKind.CONFLICT_END_TRIGGER
        or dict(top.context).get("played") is not True
    ):
        return None
    owner = at.decision.owner
    following = next(
        (
            at.rows[index][0]
            for index in range(at.index + 1, len(at.rows))
            if index not in _ahead()
        ),
        None,
    )
    if (
        following is not None
        and following[0] == "a"
        and following[2] == owner
        and following[1] in _WINDOW_STEPS
    ):
        return None
    return next(
        (a for a in at.legal if a.action_id == "finish_conflict_end_intrigue"),
        None,
    )


def _harvest_cells_discard_order(old: Step, candidate: Step) -> None:
    """Each Harvest Cells goes to the Intrigue discard as it is played, in
    window order -- turn order from the First Player (OQ-002); the base
    discarded them at the cleanup, the last window's card first. With two
    played at one Conflict's end the discard holds the same cards in
    another order until it is shuffled: the base's order in the views, and
    the field left out, while the two hold the same cards."""

    if _CONFLICT_END.get("closing") and int(str(_CONFLICT_END.get("plays", 0))) > 1:
        _CONFLICT_END["discard_order"] = True
    if not _CONFLICT_END.get("discard_order"):
        return
    if old.views and candidate.views:
        same = True
        for base, view in zip(old.views, candidate.views, strict=True):
            mine, theirs = view["intrigue_discard"], base["intrigue_discard"]
            if mine != theirs:
                same = False
                if sorted(mine) == sorted(theirs):
                    view["intrigue_discard"] = list(theirs)
        if same:
            _CONFLICT_END["discard_order"] = False
            return
    candidate.fields_unchecked.add("intrigue_discard")


# --- Cleanup-2c, rule decisions 3 and 4: one resource-gain event ------------


def _payload(event: dict[str, object]) -> dict[str, object]:
    payload = event["payload"]
    assert isinstance(payload, list)
    return {str(key): value for key, value in payload}


def _base_event(
    event_id: str, kind: str, payload: dict[str, object]
) -> dict[str, object]:
    return {
        "event_id": event_id,
        "kind": kind,
        "payload": [[key, payload[key]] for key in sorted(payload)],
        "visible_to": None,
    }


def _gain_in_base_form(event: dict[str, object]) -> list[dict[str, object]]:
    """A candidate ``resources_gained`` as the base's event for that source
    (none for an Intrigue or Scouts line's resources, which left none)."""

    data = _payload(event)
    source = str(data["source"])
    player = data["player"]
    amounts = {
        key: int(str(data.get(key, 0)))
        for key in ("solari", "spice", "water", "victory_points")
    }
    # A Navigation card's line (its source is the trigger's plus
    # ``:navigation:N``) is an Intrigue-shaped line, whatever triggered it.
    navigation = re.search(r":navigation:\d+$", source) is not None
    if not navigation and re.search(r":research:c\d+r\d+$", source):
        return [
            _base_event(
                f"{source}:resources",
                "research_resources_gained",
                {
                    "player": player,
                    "solari": amounts["solari"],
                    "spice": amounts["spice"],
                },
            )
        ]
    if not navigation and ":acquire:" in source:
        return [
            _base_event(
                f"{source}:{resource}",
                "acquisition_resource_gained",
                {"amount": amount, "player": player, "resource": resource},
            )
            for resource, amount in amounts.items()
            if amount and resource != "victory_points"
        ]
    if not navigation and ":reveal_gain:" in source:
        return [
            _base_event(
                source,
                "reveal_resources_gained",
                {
                    "player": player,
                    "solari": amounts["solari"],
                    "source": source.split(":reveal_gain:", 1)[1],
                    "spice": amounts["spice"],
                    "water": amounts["water"],
                },
            )
        ]
    if not navigation and ":reveal_card:" in source:
        card_id = source.split(":reveal_card:", 1)[1]
        if card_id.endswith(":contract_count_choice"):
            card_id = card_id.removesuffix(":contract_count_choice")
            return [
                _base_event(
                    f"{source}:spice",
                    "contract_reveal_spice_gained",
                    {"amount": amounts["spice"], "card_id": card_id, "player": player},
                )
            ]
        return [
            _base_event(
                f"{source}:solari",
                "reveal_solari_gained",
                {"amount": amounts["solari"], "card_id": card_id, "player": player},
            )
        ]
    if not navigation and ":endgame_tech:" in source:
        return [
            _base_event(
                source,
                "victory_points_gained",
                {
                    "amount": amounts["victory_points"],
                    "player": player,
                    "source": "tech",
                },
            )
        ]
    # An Intrigue or Scouts line: only its Victory Points left an event.
    if amounts["victory_points"]:
        return [
            _base_event(
                f"{source}:victory_points",
                "victory_points_gained",
                {"amount": amounts["victory_points"], "player": player},
            )
        ]
    return []


def _gains_in_base_form(old: Step, candidate: Step) -> None:
    """Cleanup-2c decisions 3 and 4: the candidate's ``resources_gained``
    and the amounts on ``tech_acquire_effect_resolved`` read back as the
    base's events (the state compares the amounts themselves)."""

    translated: list[dict[str, object]] = []
    for event in candidate.events:
        if event["kind"] == "resources_gained":
            translated.extend(_gain_in_base_form(event))
            continue
        if event["kind"] == "tech_acquire_effect_resolved":
            data = _payload(event)
            points = int(str(data.pop("victory_points", 0)))
            data.pop("solari", None)
            translated.append(_base_event(str(event["event_id"]), event["kind"], data))
            if points:
                translated.append(
                    _base_event(
                        f"{event['event_id']}:victory_points",
                        "victory_points_gained",
                        {"amount": points, "player": data["player"]},
                    )
                )
            continue
        translated.append(event)
    candidate.events = translated


def _shortfall_id(event: dict[str, object]) -> tuple[str, ...] | None:
    """A ``shortfall_refilled`` id without its event-log count
    (``round:R:player:P:shortfall_refilled:<count>:T:S``)."""

    parts = str(event["event_id"]).split(":")
    if event["kind"] != "shortfall_refilled" or len(parts) != 8:
        return None
    return (*parts[:5], *parts[6:], _row_key(event["payload"]))


def _shortfall_counts(old: Step, candidate: Step) -> None:
    """The ``shortfall_refilled`` ids count the logged events, and the
    candidate logs fewer at a Conflict's end (no ``intrigue_trigger_fired``,
    the Harvest Cells steps gone): the base's id where only the count
    differs."""

    base = {_shortfall_id(e): e["event_id"] for e in old.events}
    base.pop(None, None)
    have = {e["event_id"] for e in old.events}
    for event in candidate.events:
        key = _shortfall_id(event)
        if key is not None and event["event_id"] not in have and key in base:
            event["event_id"] = base[key]


def _conflict_end_events(old: Step, candidate: Step) -> None:
    """The Tactician token's advance comes with the troops' return, before
    the windows (the base logged it at the cleanup), and Harvest Cells'
    specimens and acquisition with its play: such an event moves to the base
    step that logged it, in the base's order."""

    base = Counter(_row_key(e) for e in old.events)
    # While a base step answered early is still ahead, everything the
    # candidate went on to log after it belongs to that later step.
    deferring = any(index > old.index for index in _ahead())
    kept: list[dict[str, object]] = []
    for event in candidate.events:
        text = _row_key(event)
        if (_carried(event) or deferring) and base[text] == 0:
            _CONFLICT_END_CARRY.append(event)
            continue
        kept.append(event)
    have = Counter(_row_key(e) for e in kept)
    for event in list(_CONFLICT_END_CARRY):
        text = _row_key(event)
        if base[text] > have[text]:
            kept.append(event)
            have[text] += 1
            _CONFLICT_END_CARRY.remove(event)
    texts = [_row_key(e) for e in kept]
    order = [_row_key(e) for e in old.events]
    if (
        texts != order
        and sorted(texts) == sorted(order)
        and any(_carried(e) for e in kept)
    ):
        by_text: dict[str, list[dict[str, object]]] = {}
        for text, event in zip(texts, kept, strict=True):
            by_text.setdefault(text, []).append(event)
        kept = [by_text[text].pop(0) for text in order]
    candidate.events = kept
    if _CONFLICT_END.pop("closing", False) and _CONFLICT_END_CARRY:
        raise AssertionError(
            f"Conflict-end events the base never logged: {_CONFLICT_END_CARRY}"
        )


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
    Rule(
        "conflict_end_finish",
        why="user decision 2026-10-18: the Conflict-end window's press after a "
        "play is 'finish'",
        old=_conflict_end_finish,
    ),
    Rule(
        "harvest_cells_steps",
        why="user decision 2026-10-18: Harvest Cells resolves as it is played, "
        "the base's later steps have no counterpart",
        old=_harvest_cells_steps,
    ),
    Rule(
        "tech_draw_at_the_win",
        why="OQ-108: Planetary Array's reshuffle comes as the Conflict is won",
        answer=_tech_draw_now,
    ),
    Rule(
        "reshuffle_moved",
        why="OQ-108: the Planetary Array card's seat shuffles the same cards a "
        "round earlier",
        answer=_reshuffle_now,
    ),
    Rule(
        "conflict_end_reopened",
        why="OQ-109 (user decision 2026-10-18): a played window is judged when it "
        "comes back on top",
        answer=_conflict_end_reopened,
    ),
    Rule(
        "harvest_cells_now",
        why="user decision 2026-10-18: its acquisition is asked at the play",
        answer=_harvest_cells_now,
    ),
    Rule(
        "gains_in_base_form",
        why="cleanup-2c: rule decisions 3 and 4, one resources_gained event with "
        "a line's VP as a key; Tech acquire amounts on their own event",
        new=_gains_in_base_form,
    ),
    Rule(
        "shortfall_counts",
        why="user decision 2026-10-18: the Conflict's end logs fewer events, and "
        "the shortfall ids count the log",
        new=_shortfall_counts,
    ),
    Rule(
        "conflict_end_interval",
        why="user decision 2026-10-18: the troops go back before the windows "
        "[Main p. 14] [FAQ p. 1]",
        new=_conflict_end_interval,
    ),
    Rule(
        "planetary_array_at_the_win",
        why="OQ-108 (user decision 2026-10-18): the Conflict card, and Planetary "
        "Array's card, before the troops go back [Main p. 14]",
        new=_planetary_array_at_the_win,
    ),
    Rule(
        "harvest_cells_discard_order",
        why="user decision 2026-10-18: each Harvest Cells is discarded as it is "
        "played, in turn order (OQ-002)",
        new=_harvest_cells_discard_order,
    ),
    Rule(
        "conflict_end_events",
        why="user decision 2026-10-18: Tactician and Harvest Cells events come earlier",
        new=_conflict_end_events,
    ),
    Rule(
        "research_icon_events",
        why="cleanup-2b: decision 5, an answered icon's events come after the "
        "step's own",
        new=_research_icon_events_in_base_order,
    ),
    Rule(
        "research_icons_in_order",
        why="cleanup-2b: decision 5 (OQ-027), a research pair's icons and "
        "c7r3's rewards each their own step",
        answer=_research_icons_in_base_order,
    ),
)
