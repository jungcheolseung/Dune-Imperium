"""Declared differences of the composed-effects cleanup-2 (branch ``cleanup2``).

docs/composed-effects-plan.md 5, "정리-2 계획": every change a player, an agent
or a save can see on purpose, as rules for ``engine_equivalence.py check
--differences scripts/ab/differences/cleanup2.py`` against the recording of
the stage's start master (``d892cd6c``). Each rule's ``why`` names the plan's
sub-stage; a sub-stage adds its rules here with its change.
"""

import importlib.util
import json
import re
from collections import Counter
from pathlib import Path

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
        named = (_VANISHED[kind] & {source, *_box_aliases(source, kind)}) if (
            event["kind"] == event_kind
        ) else set()
        if named:
            _VANISHED[kind].discard(named.pop())
            continue
        kept.append(event)
    candidate.events = kept


def _box_aliases(source: str, kind: str) -> set[str]:
    """The base's names of a frame the candidate names after its Agent box
    (cleanup-2c-2): Control the Spice's trash ``…:agent_card_payment:<card>``,
    Stitched Horror's ``…:agent_card_payment:<n>``; and of a research
    space's window, whose opener lost a caller's extra ``:research`` in
    cleanup-2c-5 (every vanished source of that round and seat ending with
    the space)."""

    research = re.match(r"^round:(\d+):.*:research:(c\d+r\d+)$", source)
    if research is not None:
        round_number, space = research.groups()
        seat = _SOURCE_SEAT.match(source)
        return {
            vanished
            for vanished in _VANISHED[kind]
            if vanished.startswith(f"round:{round_number}:")
            and vanished.endswith(f":research:{space}")
            and (
                (named := _SOURCE_SEAT.match(vanished)) is not None
                and seat is not None
                and named.group(1) == seat.group(1)
                or named is None
                and seat is None
            )
        }

    box = re.match(
        rf"^(round:\d+:player:\d+):agent_card:({_CARD_REF})(?::(\d+))?$", source
    )
    if box is None:
        return set()
    root, card, pick = box.groups()
    return {f"{root}:agent_card_payment:{pick if pick else card}"}


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


def _carry_key(event: dict[str, object]) -> str:
    """An event's text for carrying it between steps: its kind and payload,
    not its id (cleanup-2c renamed sources), and a Tactics advance by its
    seat and count alone (cleanup-2c-4 also moved its gain to a
    ``resources_gained``)."""

    if event["kind"] == "tactics_token_advanced":
        data = _payload(event)
        return f"tactics:{data['player']}:{data['count']}"
    return json.dumps(
        [event["kind"], event["payload"], event.get("visible_to")], sort_keys=True
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


# --- Cleanup-2c-2: the Agent box's events -----------------------------------

# A card instance (``imperium:long_reach:0``, ``player:1:starter:x:0``).
_CARD_REF = r"(?:player:\d+:starter|[a-z_]+):[a-z0-9_]+:\d+"
# ``<box>`` or ``<box>:<icon>``: an Agent box's own source.
_BOX_SOURCE = re.compile(rf"^round:\d+:player:\d+:agent_card:{_CARD_REF}(?::[a-z_]+)?$")
_BOX_KINDS = frozenset(
    {
        "agent_card_effect_resolved",
        "agent_card_effect_unavailable",
        "agent_card_effect_declined",
        "agent_card_effect_lapsed",
        "agent_card_effect_expired",
    }
)
# The refusals each answer used to name its own way.
_BASE_DECLINES = frozenset(
    {
        "agent_card_payment_declined",
        "agent_card_trash_declined",
        "agent_card_discard_declined",
        "agent_card_acquisition_declined",
        "corrinth_city_payment_declined",
        "agent_card_effect_declined",
    }
)
_GRAFT_TRASHES = frozenset(
    {"trash_grafted_card_for_influence", "trash_grafted_card_for_specimen"}
)
_SEAT_ROOT = re.compile(r"^(round:\d+:player:\d+):")


def _pairs_with(kind: str, data: dict[str, object], base: dict[str, object]) -> bool:
    """Whether the base's event ``base`` is the candidate's box event."""

    base_kind = base["kind"]
    base_data = _payload(base)
    if ":agent_card_discard:" in str(base["event_id"]):
        # Arrakis Observer's spice, a gain (``_box_gains``).
        return False
    if base_data.get("player") != data["player"]:
        return False
    if "card_id" in base_data and base_data["card_id"] != data.get("card_id"):
        return False
    if base_data.get("tech_id") != data.get("tech_id"):
        # Servo-Receivers' Signet names its tile.
        return False
    if "effect" in base_data and base_data["effect"] != data.get("effect"):
        return False
    match kind:
        case "agent_card_effect_declined":
            return base_kind in _BASE_DECLINES
    return base_kind == kind


def _box_gains(old: Step, event: dict[str, object]) -> list[dict[str, object]]:
    """A box's ``resources_gained`` as the base logged it: Arrakis
    Observer's spice under the box's kind, anything else not at all."""

    data = _payload(event)
    for base in old.events:
        if ":agent_card_discard:" not in str(base["event_id"]):
            continue
        base_data = _payload(base)
        if base_data.get("player") == data["player"] and all(
            base_data.get(key, 0) == data.get(key, 0)
            for key in ("solari", "spice", "water")
        ):
            return [base]
    return []


def _box_events_in_base_form(old: Step, candidate: Step) -> None:
    """Cleanup-2c-2 (docs/composed-effects-plan.md, "2c-2 — Agent 칸"): the
    candidate's box events read back as the base's (one per box, named
    ``<box>:<outcome>``; the base logged some, under other names, and not
    others), its box gains as the base's (none, or Arrakis Observer's), and
    every other event named after the box under the base's id when the
    base logged the same event under another source; then the base's
    order."""

    used: set[int] = set()
    out: list[dict[str, object]] = []
    graft_trash = old.step[0] == "a" and old.step[1] in _GRAFT_TRASHES
    changed = False
    for event in candidate.events:
        kind = str(event["kind"])
        if kind == "resources_gained" and _BOX_SOURCE.match(
            str(_payload(event)["source"])
        ):
            out.extend(_box_gains(old, event))
            changed = True
            continue
        if kind not in _BOX_KINDS:
            out.append(event)
            continue
        same = next(
            (
                index
                for index, base in enumerate(old.events)
                if index not in used and base == event
            ),
            None,
        )
        if same is not None:
            # Logged alike (Servo-Receivers' Signet with no ability).
            used.add(same)
            out.append(event)
            continue
        data = _payload(event)
        changed = True
        match = next(
            (
                index
                for index, base in enumerate(old.events)
                if index not in used and _pairs_with(kind, data, base)
            ),
            None,
        )
        if match is not None:
            used.add(match)
            out.append(old.events[match])
        elif kind == "agent_card_effect_expired" and not graft_trash:
            # An expiry the base logged a step later (``_expiry_at_the_trash``
            # carries it): its base id, once per box (the candidate logs one
            # per icon the box still had).
            box = agent_card_source_of(event)
            expired = _base_event(
                f"{box}:effect_expired",
                kind,
                {"card_id": data["card_id"], "player": data["player"]},
            )
            if expired not in out:
                out.append(expired)
    for index, base in enumerate(old.events):
        if index not in used and "crysknife" in _payload(base):
            # The Beast's Spoils logged its box at its gains, the candidate
            # once the Crysknife's trash is done.
            out.insert(min(index, len(out)), base)
            changed = True
    changed |= _adopt_base_ids(old, out, (":agent_card:",))
    # The base's order only where this rule translated something: an
    # undeclared reorder elsewhere still shows.
    candidate.events = _in_base_order(old, out) if changed else out


def agent_card_source_of(event: dict[str, object]) -> str:
    """The box an Agent box's event names (``<box>:...:<outcome>``)."""

    data = _payload(event)
    event_id = str(event["event_id"])
    card = str(data["card_id"])
    return event_id[: event_id.index(card) + len(card)]


def _adopt_base_ids(
    old: Step,
    out: list[dict[str, object]],
    roots: tuple[str, ...],
    *,
    any_seat: bool = False,
) -> bool:
    """Give an event the candidate names after one of ``roots`` the base's
    id, where the base logged the same event of that seat (of any seat with
    ``any_seat``: Esmar's draw was named after the visitor) under another
    name in the step (in place); whether any was renamed."""

    spare = [
        base
        for base in old.events
        if base["event_id"] not in {e["event_id"] for e in out}
        and base["kind"] not in _BOX_KINDS
    ]
    renamed = False
    for position, event in enumerate(out):
        root = _SEAT_ROOT.match(str(event["event_id"]))
        if root is None and any_seat:
            # A source with no seat (``round:R:scouts:...``).
            root = re.match(r"^(round:\d+):", str(event["event_id"]))
        if (
            root is None
            or not any(word in str(event["event_id"]) for word in roots)
            or event in old.events
        ):
            continue
        prefix = root.group(1).rsplit(":player:", 1)[0] if any_seat else root.group(1)
        for base in spare:
            if (
                base["kind"] == event["kind"]
                and str(base["event_id"]).startswith(prefix)
                and _same_payload(base, event)
            ):
                out[position] = base
                spare.remove(base)
                renamed = True
                break
    return renamed


def _in_base_order(
    old: Step, out: list[dict[str, object]]
) -> list[dict[str, object]]:
    """``out`` in the base's order when it holds the same events."""

    texts = [_row_key(e) for e in out]
    order = [_row_key(e) for e in old.events]
    if texts == order or sorted(texts) != sorted(order):
        return out
    by_text: dict[str, list[dict[str, object]]] = {}
    for text, event in zip(texts, out, strict=True):
        by_text.setdefault(text, []).append(event)
    return [by_text[text].pop(0) for text in order]


# --- Cleanup-2c-4: Leader and Tech events --------------------------------------

_SIGNET_KINDS = frozenset(
    f"leader_signet_{outcome}"
    for outcome in ("resolved", "declined", "unavailable", "lapsed", "expired")
)
# The base's events a Signet box's event stands for, by outcome.
_SIGNET_BASE: dict[str, frozenset[str]] = {
    "leader_signet_resolved": frozenset(
        {"leader_signet_resolved", "agent_card_effect_resolved"}
    ),
    "leader_signet_declined": frozenset(
        {
            "leader_signet_payment_declined",
            "leader_card_trash_declined",
            "agent_card_effect_declined",
        }
    ),
    "leader_signet_unavailable": frozenset(
        {"leader_signet_unavailable", "agent_card_effect_unavailable"}
    ),
    "leader_signet_lapsed": frozenset({"agent_card_effect_lapsed"}),
    "leader_signet_expired": frozenset({"agent_card_effect_expired"}),
}
_LEADER_SOURCE = re.compile(r"^round:\d+:player:\d+:leader:([a-z_]+)$")
_SIGNET_SOURCE = re.compile(r"^round:\d+:player:\d+:leader_signet(?::[a-z_]+)?$")


def _signet_pairs_with(event: dict[str, object], base: dict[str, object]) -> bool:
    data = _payload(event)
    base_data = _payload(base)
    if base["kind"] not in _SIGNET_BASE[str(event["kind"])]:
        return False
    if base.get("visible_to") != event.get("visible_to"):
        return False
    if base_data.get("player") != data.get("player"):
        return False
    for key in ("card_id", "tech_id"):
        if key in base_data and base_data[key] != data.get(key):
            return False
    return "effect" not in base_data or base_data["effect"] == data.get("effect")


def _staban_base(base: dict[str, object], data: dict[str, object]) -> bool:
    """Staban's Smuggle Spice as the base logged it."""

    return (
        base["kind"] == "leader_ability_spice_gained"
        and _payload(base).get("player") == data["player"]
        and _payload(base).get("spice") == data.get("spice")
    )


def _leader_and_tech_in_base_form(old: Step, candidate: Step) -> None:
    """Cleanup-2c-4 (docs/composed-effects-plan.md, "2c-4"): the Signet
    Ring box's event (``leader_signet_<outcome>``, one per box, last) reads
    back as the base's event for it -- ``leader_signet_resolved`` with its
    amounts, a refusal of its own kind, or the Agent box's kind the base
    used for its lapse, fizzle and expiry -- or as nothing; the Signet's and
    a Leader ability's gains as the base's (none, or the ability's own
    event that carried them: Staban's ``leader_ability_spice_gained``); a
    Leader ability's event, the Tactics track's, a Tech Reveal bonus and a
    Tech trash as the base's of that seat and tile; then the base's
    order."""

    used: set[int] = set()
    out: list[dict[str, object]] = []
    changed = False

    def take(event: dict[str, object], matches: object) -> bool:
        for index, base in enumerate(old.events):
            if index not in used and matches(base):  # type: ignore[operator]
                used.add(index)
                out.append(base)
                return True
        return False

    for event in candidate.events:
        kind = str(event["kind"])
        data = _payload(event)
        if kind in _SIGNET_KINDS:
            changed = True
            if event in old.events:
                take(event, lambda base, event=event: base == event)
            else:
                take(event, lambda base, event=event: _signet_pairs_with(event, base))
            continue
        if kind == "resources_gained":
            source = str(data["source"])
            leader = _LEADER_SOURCE.match(source)
            if leader is not None and leader.group(1) == "staban_tuek":
                changed = True
                take(event, lambda base, data=data: _staban_base(base, data))
                continue
            if leader is not None or _SIGNET_SOURCE.match(source):
                changed = True
                continue
        keys: tuple[str, ...] = ()
        if kind == "leader_ability_resolved":
            keys = ("player", "leader_id")
        elif kind in ("tactics_token_advanced",):
            keys = ("player", "count")
        elif kind in ("tech_reveal_bonus", "tech_trashed"):
            keys = ("player", "tech_id")
        if keys and event not in old.events:
            match = _same_event(old, used, event, keys)
            if match is not None:
                used.add(match)
                out.append(old.events[match])
                changed = True
                continue
            if data.get("leader_id") == "staban_tuek":
                # Smuggle Spice had only its gain's event.
                changed = True
                continue
        out.append(event)
    changed |= _adopt_base_ids(old, out, (":leader:",), any_seat=True)
    candidate.events = _in_base_order(old, out) if changed else out


# --- Cleanup-2c-5: research, Immortality and Scouts events ---------------------


def _scouts_and_row_in_base_form(old: Step, candidate: Step) -> None:
    """Cleanup-2c-5 (docs/composed-effects-plan.md, "2c-5"), before the
    gains rule: Offworld Operation's spice and a mission's goods are
    resource gains now (``scouts_helix_spice``, the goods' amounts on
    ``scouts_mission_goods_taken``); the Row's redeal is
    ``imperium_row_cleared`` for Family Atomics (whose own event kept the
    removed cards) and Clear the Market (``scouts_row_cleared``); a Skill's
    Reveal bonus lost its zeros and its ``:late``."""

    used: set[int] = set()
    out: list[dict[str, object]] = []
    changed = False

    def base_of(
        kind: str, data: dict[str, object], keys: tuple[str, ...]
    ) -> int | None:
        for index, base in enumerate(old.events):
            if index in used or base["kind"] != kind:
                continue
            base_data = _payload(base)
            if all(base_data.get(key) == data.get(key) for key in keys) and (
                base.get("visible_to") == event.get("visible_to")
            ):
                return index
        return None

    for event in candidate.events:
        kind = str(event["kind"])
        data = _payload(event)
        match: int | None = None
        drop = False
        if kind == "resources_gained":
            match = base_of("scouts_helix_spice", data, ("player", "spice"))
            if match is None and any(
                base["kind"] == "scouts_mission_goods_taken"
                and _payload(base).get("player") == data["player"]
                and str(data["source"]).endswith(f":{_payload(base)['mission_id']}")
                for base in old.events
            ):
                drop = True
        elif kind == "scouts_mission_goods_taken":
            match = base_of(kind, data, ("player", "mission_id"))
        elif kind == "imperium_row_cleared":
            if "player" in data:
                drop = any(base["kind"] == "family_atomics_used" for base in old.events)
            else:
                match = base_of("scouts_row_cleared", data, ("dealt", "removed"))
        elif kind == "family_atomics_used" and event not in old.events:
            match = base_of(kind, data, ("player",))
        elif kind == "skill_reveal_bonus" and event not in old.events:
            match = base_of(kind, data, ("player", "skill_id"))
        if match is not None:
            used.add(match)
            out.append(old.events[match])
            changed = True
        elif drop:
            changed = True
        else:
            out.append(event)
    candidate.events = _in_base_order(old, out) if changed else out


def _tracks_in_base_form(old: Step, candidate: Step) -> None:
    """Cleanup-2c-5, after the gains rule: the research and Tleilaxu tracks
    are named after the seat's track space whatever moved the token (the
    base named them after the caller's source, chained bonus moves under
    each other); a Tleilaxu space's spice left ``tleilaxu_advanced``;
    callers dropped their own extra words (``:research``, ``:specimen``,
    ``:research_draw``): the base's id where only that differs."""

    used: set[int] = set()
    out: list[dict[str, object]] = []
    changed = False
    for event in candidate.events:
        kind = str(event["kind"])
        tracks = ("tleilaxu_advanced", "tleilaxu_track_end")
        if event not in old.events and kind in tracks:
            keys = ("player", "space") if kind == "tleilaxu_advanced" else ("player",)
            match = _same_event(old, used, event, keys)
            if match is not None:
                used.add(match)
                out.append(old.events[match])
                changed = True
                continue
        out.append(event)
    changed |= _adopt_base_ids(
        old,
        out,
        (
            ":research",
            ":tleilaxu:",
            ":specimens",
            ":intrigue_draw:",
            ":discard_shuffled",
        ),
        any_seat=True,
    )
    candidate.events = _in_base_order(old, out) if changed else out


# --- Cleanup-2c-6: payments and refusals ---------------------------------------

_PAID_KEYS = ("solari", "spice", "water", "specimens")


def _base_paid(base: dict[str, object]) -> dict[str, int] | None:
    """What a base payment event says was paid, or None for another kind."""

    data = _payload(base)
    kind = base["kind"]

    def amount(key: str) -> int:
        return int(str(data.get(key, 0)))

    match kind:
        case "intrigue_cost_paid" | "scouts_cost_paid":
            return {key: amount(key) for key in ("solari", "spice", "water")}
        case "agent_card_payment_resolved":
            resource = str(data["resource"])
            if resource == "card":
                return None
            key = "specimens" if resource == "specimen" else resource
            return {key: amount("spent")}
        case "corrinth_city_payment_resolved" | "research_bonus_paid":
            return {"solari": amount("solari")}
        case "combat_reward_paid":
            return {str(data["resource"]): amount("cost")}
        case "reveal_spice_paid" | "leader_signet_spice_paid":
            return {"spice": amount("amount")}
        case "leader_signet_solari_paid":
            return {"solari": amount("amount")}
        case "leader_board_repeat_paid":
            return {"water": amount("water")}
        case "scouts_specimens_paid":
            return {"specimens": amount("count")}
    return None


def _same_paid(paid: dict[str, int], data: dict[str, object]) -> bool:
    return all(
        paid.get(key, 0) == int(str(data.get(key, 0))) for key in _PAID_KEYS
    )


# Base payments the candidate logs no payment for: a card paid (its trash
# says so), and a cost or a specimen payment of nothing.
def _unpaid_base(base: dict[str, object]) -> bool:
    paid = _base_paid(base)
    if base["kind"] == "agent_card_payment_resolved":
        return str(_payload(base)["resource"]) == "card"
    return paid is not None and not any(paid.values())


def _payments_in_base_form(old: Step, candidate: Step) -> None:
    """Cleanup-2c-6 (docs/composed-effects-plan.md, "2c-6"), before the
    gains rule: a ``resources_paid`` reads as the base's payment event of
    that seat and those amounts (nine kinds, four conventions), or as
    nothing (the Signet payments the base left out); what a paid Conflict
    reward bought had no event of its own; Reverend Mother's repeat had only
    its payment's event; the refused optional trashes had kinds of their
    own; the refusals lost their zero amounts."""

    used: set[int] = set()
    out: list[dict[str, object]] = []
    changed = False
    repeat = any(base["kind"] == "leader_board_repeat_paid" for base in old.events)
    for event in candidate.events:
        kind = str(event["kind"])
        data = _payload(event)
        if kind == "resources_paid":
            changed = True
            match = next(
                (
                    index
                    for index, base in enumerate(old.events)
                    if index not in used
                    and _payload(base).get("player") == data["player"]
                    and (paid := _base_paid(base)) is not None
                    and any(paid.values())
                    and _same_paid(paid, data)
                ),
                None,
            )
            if match is not None:
                used.add(match)
                out.append(old.events[match])
            continue
        if kind == "resources_gained" and ":combat_reward:optional:" in str(
            data["source"]
        ):
            changed = True
            continue
        if kind == "leader_ability_resolved" and repeat and "space_id" in data:
            changed = True
            continue
        bases: tuple[str, ...] = ()
        if kind == "optional_trash_declined" and event not in old.events:
            bases = (
                "combat_reward_trash_declined",
                "intrigue_trash_declined",
                "tech_trash_declined",
            )
        elif kind == "combat_reward_declined" and event not in old.events:
            bases = ("combat_reward_declined",)
        if bases:
            match = next(
                (
                    index
                    for index, base in enumerate(old.events)
                    if index not in used
                    and base["kind"] in bases
                    and _payload(base).get("player") == data["player"]
                ),
                None,
            )
            if match is not None:
                used.add(match)
                out.append(old.events[match])
                changed = True
                continue
        out.append(event)
    for index, base in enumerate(old.events):
        if index not in used and _unpaid_base(base):
            out.insert(min(index, len(out)), base)
            changed = True
    candidate.events = _in_base_order(old, out) if changed else out


# --- Cleanup-2c-3: board, Conflict and Contract events ------------------------

_BOARD_SOURCE = re.compile(r"^round:\d+:player:\d+:board:[a-z_]+$")
_CONTROL_SOURCE = re.compile(r"^round:(\d+):player:(\d+):control:([a-z_]+)$")
# A Conflict reward's own Intrigue cards (the cards it deals itself).
_REWARD_DEAL = re.compile(r"^round:\d+:combat_reward:\d+:\d+:intrigue_draw:\d+$")
_NAMED_SPACES = frozenset(
    {
        "hagga_basin",
        "imperial_basin",
        "deep_desert",
        "sietch_tabr",
        "tuek_sietch",
        "imperial_privilege",
    }
)


def _agrees(base: dict[str, object], event: dict[str, object]) -> bool:
    """Whether ``event`` says nothing ``base`` contradicts: the same
    visibility and, for every payload key both carry (bar the renamed
    ``source``), the same value -- what a rule checks before it puts the
    base's event in the candidate's place (2026-10-18 review)."""

    if base.get("visible_to") != event.get("visible_to"):
        return False
    base_data, data = _payload(base), _payload(event)
    return all(
        base_data[key] == data[key]
        for key in base_data.keys() & data.keys()
        if key != "source"
    )


def _same_event(
    old: Step, used: set[int], event: dict[str, object], keys: tuple[str, ...]
) -> int | None:
    """The base event of the step with ``event``'s kind and the same
    ``keys`` in its payload, not yet taken, that ``event`` agrees with."""

    data = _payload(event)
    for index, base in enumerate(old.events):
        if index in used or base["kind"] != event["kind"]:
            continue
        base_data = _payload(base)
        if all(base_data.get(key) == data.get(key) for key in keys) and _agrees(
            base, event
        ):
            return index
    return None


def _board_conflict_contract_in_base_form(old: Step, candidate: Step) -> None:
    """Cleanup-2c-3 (docs/composed-effects-plan.md, "2c-3"): the candidate's
    board, Conflict reward and Contract events read back as the base's.

    A board icon of the six spaces that had no icon key, a Conflict reward
    and a Contract completion are the base's event of that space, seat and
    icon / rank / Contract (their payloads lost their zeros and the board
    ones their spice, now a gain; the state compares the amounts); board
    and Control gains and a reward's Intrigue draw had no event (the
    Control bonus had ``control_bonus_gained``); Imperial Privilege's trade
    had no board event; the rest named after the board are renamed; then
    the base's order."""

    used: set[int] = set()
    out: list[dict[str, object]] = []
    changed = False
    for event in candidate.events:
        kind = event["kind"]
        data = _payload(event)
        if kind == "resources_gained":
            source = str(data["source"])
            control = _CONTROL_SOURCE.match(source)
            if control is not None:
                changed = True
                round_number, player, space = control.groups()
                ((resource, amount),) = (
                    (key, value)
                    for key, value in data.items()
                    if key in ("solari", "spice", "water")
                )
                out.append(
                    _base_event(
                        f"round:{round_number}:control_bonus:{space}:{player}",
                        "control_bonus_gained",
                        {
                            "amount": amount,
                            "player": int(player),
                            "resource": resource,
                            "space_id": space,
                        },
                    )
                )
                continue
            if _BOARD_SOURCE.match(source):
                changed = True
                continue
        if kind == "intrigue_card_drawn" and _REWARD_DEAL.match(str(event["event_id"])):
            changed = True
            continue
        if kind == "board_effect_resolved" and (
            data.get("effect") == "imperial_privilege_intrigue"
        ):
            changed = True
            continue
        keys: tuple[str, ...] = ()
        if kind == "board_effect_resolved" and data.get("space_id") in _NAMED_SPACES:
            keys = ("player", "space_id", "effect")
        elif kind == "combat_reward_gained":
            keys = ("player", "rank")
        elif kind == "contract_completed":
            keys = ("player", "contract_id")
        if keys:
            match = _same_event(old, used, event, keys)
            if match is not None:
                used.add(match)
                out.append(old.events[match])
                changed = True
                continue
        out.append(event)
    changed |= _adopt_base_ids(old, out, (":board:",))
    candidate.events = _in_base_order(old, out) if changed else out





def _same_payload(base: dict[str, object], event: dict[str, object]) -> bool:
    """The payloads match, but a payment's ``gained`` (Slig Farmer's Solari,
    now a ``resources_gained``) and a source named after the box (a
    Contract's ``source``)."""

    def plain(data: dict[str, object]) -> dict[str, object]:
        return {
            key: "<box>" if ":agent_card" in str(value) else value
            for key, value in data.items()
        }

    if base.get("visible_to") != event.get("visible_to"):
        return False
    base_data = _payload(base)
    if event["kind"] == "agent_card_payment_resolved":
        base_data.pop("gained", None)
    return plain(base_data) == plain(_payload(event))


# The sources cleanup-2c renamed that a waiting draw carries.
_RENAMED_SOURCES = (":agent_card:", ":research:", ":tleilaxu:", ":leader:")


def _box_owed_draws(old: Step, at: At) -> None:
    """A waiting draw is logged under its source's name when taken
    (``PlayerState.owed_draws`` and ``GameState.pending_intrigue_draws``
    hold it): while one waits under a name cleanup-2c changed, those fields
    are left out of the state comparison (the recording keeps only their
    digests). What they draw is still compared through the step's legal
    draw actions and page, and the draw's events and chance when taken."""

    for seat, player in enumerate(at.state.players):
        if any(
            word in entry[2] for entry in player.owed_draws for word in _RENAMED_SOURCES
        ):
            old.fields_unchecked.add(f"players[{seat}].owed_draws")
    if any(
        word in entry[2]
        for entry in at.state.pending_intrigue_draws
        for word in _RENAMED_SOURCES
    ):
        old.fields_unchecked.add("pending_intrigue_draws")


def _box_owed_draw_named(old: Step, candidate: Step) -> None:
    """The step a renamed source may owe a draw in (its events carry that
    name): that seat's waiting draws are left to ``_box_owed_draws``."""

    for event in candidate.events:
        event_id = str(event["event_id"])
        root = re.match(r"^round:\d+:player:(\d+):", event_id)
        if root is not None and (
            ":agent_" in event_id
            or any(word in event_id for word in _RENAMED_SOURCES)
        ):
            old.fields_unchecked.add(f"players[{root.group(1)}].owed_draws")
            old.fields_unchecked.add("pending_intrigue_draws")


# A personal discard reshuffle, named after the draw that asks it (a Scouts
# reward's names no seat; the pile tells the seat).
_BOX_SHUFFLE = re.compile(r"^round:(\d+):(?:.+:)?discard_shuffle$")


def _box_shuffle_named(old: Step, at: At) -> tuple[ChanceOutcome, ...] | None:
    """Cleanup-2c: draws are renamed by the event grammar (a box's after the
    box, a Leader ability's after the Leader, a Research draw without the
    caller's extra word), and so is the discard shuffle each asks for: the
    recorded permutation, under the candidate's name, when it is the same
    seat's shuffle of the same pile in the same round."""

    if old.step[0] != "c" or not isinstance(at.decision, ChanceDecision):
        return None
    asked = _BOX_SHUFFLE.match(at.decision.decision_id)
    recorded = _BOX_SHUFFLE.match(str(old.step[1]))
    if (
        asked is None
        or recorded is None
        or asked.groups() != recorded.groups()
        or at.decision.decision_id == old.step[1]
        or sorted(at.decision.options) != sorted(old.step[2])
    ):
        return None
    move = ChanceOutcome(decision_id=at.decision.decision_id, values=tuple(old.step[2]))
    return (move,)


def _box_shuffle_or_owed(old: Step, at: At) -> tuple[ChanceOutcome, ...] | None:
    _box_owed_draws(old, at)
    return _box_shuffle_named(old, at)


def _box_shuffle_decision(old: Step, candidate: Step) -> None:
    """The renamed shuffle's decision reads as the base's."""

    if (
        old.step[0] == "c"
        and isinstance(old.decision, list)
        and isinstance(candidate.decision, list)
        and old.decision[0] != candidate.decision[0]
        and _BOX_SHUFFLE.match(str(old.decision[0]))
        and _BOX_SHUFFLE.match(str(candidate.decision[0]))
        and old.decision[1:] == candidate.decision[1:]
    ):
        candidate.decision[0] = old.decision[0]


def _shortfall_key(event: dict[str, object]) -> tuple[object, ...] | None:
    """A ``shortfall_refilled`` by seat and amounts: the base's id counted
    the logged events (``…:shortfall_refilled:<count>:T:S``), and
    cleanup-2c-6 dropped the count and the zero amounts."""

    if event["kind"] != "shortfall_refilled":
        return None
    data = _payload(event)
    return (data["player"], data.get("troops", 0), data.get("specimens", 0))


def _shortfall_counts(old: Step, candidate: Step) -> None:
    """A ``shortfall_refilled`` reads as the base's of that seat and those
    amounts (cleanup-2c-6; the base's count also moved with the candidate's
    fewer logged events at a Conflict's end)."""

    spare = [e for e in old.events if _shortfall_key(e) is not None]
    for position, event in enumerate(candidate.events):
        key = _shortfall_key(event)
        if key is None or event in old.events:
            continue
        base = next((e for e in spare if _shortfall_key(e) == key), None)
        if base is not None:
            spare.remove(base)
            candidate.events[position] = base


def _conflict_end_events(old: Step, candidate: Step) -> None:
    """The Tactician token's advance comes with the troops' return, before
    the windows (the base logged it at the cleanup), and Harvest Cells'
    specimens and acquisition with its play: such an event moves to the base
    step that logged it, in the base's order."""

    base = Counter(_carry_key(e) for e in old.events)
    # While a base step answered early is still ahead, everything the
    # candidate went on to log after it belongs to that later step.
    deferring = any(index > old.index for index in _ahead())
    kept: list[dict[str, object]] = []
    for event in candidate.events:
        text = _carry_key(event)
        if (_carried(event) or deferring) and base[text] == 0:
            _CONFLICT_END_CARRY.append(event)
            continue
        kept.append(event)
    have = Counter(_carry_key(e) for e in kept)
    for event in list(_CONFLICT_END_CARRY):
        text = _carry_key(event)
        if base[text] > have[text]:
            # The base's own event (the candidate's may carry a source
            # cleanup-2c renamed).
            kept.append(next(e for e in old.events if _carry_key(e) == text))
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


# Cleanup-2d's rules, declared against the 2c end (``cleanup2d.py``).
_SPEC = importlib.util.spec_from_file_location(
    "cleanup2d_differences", Path(__file__).with_name("cleanup2d.py")
)
assert _SPEC is not None and _SPEC.loader is not None
_CLEANUP2D = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CLEANUP2D)

RULES = (
    *_CLEANUP2D.RULES,
    Rule(
        name="agent_box_events",
        why="cleanup-2c-2: one box event per Agent box, named <box>:<outcome>; "
        "box sources, gains and refusals unified",
        new=_box_events_in_base_form,
    ),
    Rule(
        name="board_conflict_contract_events",
        why="cleanup-2c-3: board icons named <space>:<icon>, board and Control "
        "gains, zero-free Conflict and Contract payloads, source events last",
        new=_board_conflict_contract_in_base_form,
    ),
    Rule(
        name="leader_and_tech_events",
        why="cleanup-2c-4: the Signet box's own event, Leader abilities named "
        "after the Leader, their gains, zero-free Tech Reveal bonuses",
        new=_leader_and_tech_in_base_form,
    ),
    Rule(
        name="scouts_and_row_events",
        why="cleanup-2c-5: Scouts gains as resources_gained, one Row redeal "
        "event, zero-free Skill Reveal bonuses",
        new=_scouts_and_row_in_base_form,
    ),
    Rule(
        name="payment_events",
        why="cleanup-2c-6: one resources_paid for every payment, one kind for "
        "a refused optional trash, zero-free refusals",
        new=_payments_in_base_form,
    ),
    Rule(
        name="agent_box_shuffle",
        why="cleanup-2c-2: a box's draw shuffle is named after the box",
        moves=_box_shuffle_or_owed,
        new=_box_shuffle_decision,
    ),
    Rule(
        name="agent_box_owed_draw",
        why="cleanup-2c-2: a draw an Agent box owes holds the box's name",
        new=_box_owed_draw_named,
    ),
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
        "track_events",
        why="cleanup-2c-5: the research and Tleilaxu tracks named after the "
        "seat's track space; callers' extra source words dropped",
        new=_tracks_in_base_form,
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
