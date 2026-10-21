"""Declared differences of cleanup-2d against the end of cleanup-2c.

docs/composed-effects-plan.md 5, "정리-2d": the hook conversions keep every
game the same as the recording of cleanup2 ``10f99778`` (the 2c end) but
for what is declared here, checked with ``engine_equivalence.py check
--differences scripts/ab/differences/cleanup2d.py``. ``cleanup2.py`` (the
whole of cleanup-2 against ``d892cd6c``) takes the same rules.
"""

import json
from typing import Any

from equivalence_rules import At, Rule, Step

from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.types import PersonalCardAgentEffect
from dune_imperium.core.actions import DomainAction
from dune_imperium.rules.effects import (
    active_agent_card,
    current_agent_effect_context,
    pending_agent_icons,
)
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.graft_boxes import (
    box_is_pending,
    is_grafted_turn,
    state_with_active_box,
)

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

# --- 2d-5: three Agent boxes split per icon (user decision 2026-10-18) -------
#
# Clandestine Meeting, Occupation and In High Places resolved their two icons
# with one ``resolve_agent_card_effect`` (In High Places opening the shared
# Spy placement frame under its draw); each icon is now its own row in the
# owner's order (OQ-027): the base's one move plays as the candidate's icon
# moves, In High Places' Spy at the base's frame step. The rows, the box
# events (one per icon now) and the Spy's events are compared in the base's
# form.
_BOX = PersonalCardAgentEffect
_SPLIT_ICONS: dict[PersonalCardAgentEffect, tuple[str, ...]] = {
    _BOX.GAIN_BENE_GESSERIT_INFLUENCE_AND_INTRIGUE: ("influence", "intrigue"),
    _BOX.DRAW_ONE_AND_COMBAT_ICON: ("cards", "combat"),
    _BOX.DRAW_ONE_AND_PLACE_SPY_IF_BENE_GESSERIT_BOND: ("cards", "spy"),
}
_IN_HIGH_PLACES = _BOX.DRAW_ONE_AND_PLACE_SPY_IF_BENE_GESSERIT_BOND
# The candidate's moves for the base's one resolution, in the base's order.
_SPLIT_MOVES: dict[PersonalCardAgentEffect, tuple[tuple[str, dict[str, Any]], ...]] = {
    _BOX.GAIN_BENE_GESSERIT_INFLUENCE_AND_INTRIGUE: (
        ("choose_agent_card_influence", {"faction": "bene_gesserit"}),
        ("resolve_agent_card_effect", {"effect": "intrigue"}),
    ),
    _BOX.DRAW_ONE_AND_COMBAT_ICON: (
        ("take_agent_card_combat_icon", {}),
        ("resolve_agent_card_effect", {"effect": "cards"}),
    ),
    _IN_HIGH_PLACES: (("resolve_agent_card_effect", {"effect": "cards"}),),
}
# The base's shared Spy frame rows -> the box's Spy rows.
_FRAME_SPY = {
    "place_spy_on_space": "place_agent_card_spy",
    "recall_spy_for_placement": "recall_spy_for_agent_card",
    "decline_spy_placement": "decline_agent_card_spy",
}
_BOX_SPY = frozenset(_FRAME_SPY.values())
# The split boxes pending on the candidate at the step being compared, as
# (box, effect, pending icons); set by ``_split_moves`` before the step.
_now: list[tuple[int, PersonalCardAgentEffect, tuple[str, ...]]] = []
# Whether ``_split_moves`` played this step's two icons in the other order.
_reversed = False


def _split_boxes(
    state: Any,
) -> list[tuple[int, PersonalCardAgentEffect, tuple[str, ...]]]:
    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        # A chance decision on top (a draw's reshuffle): the frame below.
        frames = [
            f for f in state.decision_stack if f.kind == FrameKind.AGENT_EFFECTS
        ]
        if not frames:
            return []
        context = dict(frames[-1].context)
        effect = active_agent_card(context).agent_effect
        if (
            effect not in _SPLIT_ICONS
            or context.get("pending_agent_effect") is not True
        ):
            return []
        return [(0, effect, pending_agent_icons(context))]
    found = []
    for box in (0, 1) if is_grafted_turn(context) else (0,):
        if not box_is_pending(context, box):
            continue
        _, active = current_agent_effect_context(state_with_active_box(state, box))
        effect = active_agent_card(active).agent_effect
        if effect in _SPLIT_ICONS:
            found.append((box, effect, pending_agent_icons(active)))
    return found


def _row_args(row: Any) -> dict[str, Any]:
    if isinstance(row, DomainAction):
        return dict(row.arguments)
    if isinstance(row, dict):
        return {str(pair[0]): pair[1] for pair in row["arguments"]}
    return {str(pair[0]): pair[1] for pair in row or ()}


def _row_box(row: Any) -> int:
    box = _row_args(row).get("box", 0)
    return box if isinstance(box, int) else 0


def _split_moves(old: Step, at: At) -> tuple[DomainAction, ...] | None:
    """The base's one resolution as the candidate's icon moves; its shared
    Spy frame's move as the box's Spy move."""

    global _now, _reversed
    _now = _split_boxes(at.state)
    _reversed = False
    if old.step[0] != "a" or not _now:
        return None
    action_id, args = old.step[1], _row_args(old.step[3])
    box = _row_box(old.step[3])
    entry = next((found for found in _now if found[0] == box), None)
    if (
        action_id == "resolve_agent_card_effect"
        and "effect" not in args
        and entry is not None
        and set(entry[2]) == set(_SPLIT_ICONS[entry[1]])
    ):
        moves = []
        for wanted, wanted_args in _SPLIT_MOVES[entry[1]]:
            move = next(
                (
                    action
                    for action in at.legal
                    if action.action_id == wanted
                    and _row_box(action) == box
                    and all(
                        _row_args(action).get(k) == v for k, v in wanted_args.items()
                    )
                ),
                None,
            )
            if move is None:
                return None
            moves.append(move)
        if entry[1] is _IN_HIGH_PLACES:
            # The base pushed its Spy frame; the candidate's icon waits.
            old.state_unchecked = True
        if len(moves) == 2 and not _plays_in_order(at, moves):
            # The first icon's follow-up (an owed draw of its Influence
            # bonus) holds the second: the other order, events compared in
            # the base's (``_split_rows``).
            moves.reverse()
            _reversed = True
        return tuple(moves)
    spy = next(
        (found for found in _now if found[1] is _IN_HIGH_PLACES and "spy" in found[2]),
        None,
    )
    if spy is not None and action_id in _FRAME_SPY:
        move = next(
            (
                action
                for action in at.legal
                if action.action_id == _FRAME_SPY[action_id]
                and _row_box(action) == spy[0]
                and _row_args(action).get("post_id") == args.get("post_id")
            ),
            None,
        )
        if move is None:
            return None
        if action_id == "recall_spy_for_placement":
            old.state_unchecked = True  # the frame stays open in the base
        return (move,)
    return None


def _plays_in_order(at: At, moves: list[DomainAction]) -> bool:
    """Whether the second move is still offered after the first."""

    first = at.engine.apply(at.state, moves[0]).state
    try:
        legal = at.engine.legal_actions(first, moves[1].actor)
    except ValueError:
        return False
    return moves[1] in legal


def _split_row(row: dict[str, Any]) -> bool:
    """A candidate row of a pending split box's icons."""

    for box, effect, _ in _now:
        if _row_box(row) != box:
            continue
        action_id = row["action_id"]
        args = _row_args(row)
        if action_id == "resolve_agent_card_effect" and args.get("effect") in (
            _SPLIT_ICONS[effect]
        ):
            return True
        if effect is _BOX.GAIN_BENE_GESSERIT_INFLUENCE_AND_INTRIGUE and (
            action_id == "choose_agent_card_influence"
        ):
            return True
        if effect is _BOX.DRAW_ONE_AND_COMBAT_ICON and (
            action_id == "take_agent_card_combat_icon"
        ):
            return True
        if effect is _IN_HIGH_PLACES and action_id in _BOX_SPY:
            return True
    return False


def _split_card(event: dict[str, Any]) -> bool:
    payload = {str(key): value for key, value in event["payload"]}
    # A box's Spy recall names its card ``source``.
    card_id = payload.get("card_id", payload.get("source"))
    return (
        isinstance(card_id, str)
        and card_id.count(":") >= 1
        and _card_effect(card_id) in _SPLIT_ICONS
    )


def _card_effect(card_id: str) -> PersonalCardAgentEffect | None:
    try:
        return personal_card_for_instance(card_id).agent_effect
    except (KeyError, ValueError):
        return None


def _split_base(step: Step) -> None:
    """The base's one box event of a split box goes (the candidate logs one
    per icon, which ``_split_rows`` drops)."""

    step.events = [
        event
        for event in step.events
        if not (
            str(event["kind"]).startswith("agent_card_effect_") and _split_card(event)
        )
    ]


def _spy_in_base_form(event: dict[str, Any]) -> dict[str, Any]:
    """In High Places' Spy event as the base's shared frame logged it
    (``<box>:spy_placement:placed:<post>`` and its kin, no card)."""

    event_id = str(event["event_id"])
    payload = {str(key): value for key, value in event["payload"]}
    box, _, rest = event_id.rpartition(":spy_")
    frame = f"{box}:spy_placement"
    match event["kind"]:
        case "spy_placed":
            new_id = f"{frame}:placed:{payload['post_id']}"
            data = {"player": payload["player"], "post_id": payload["post_id"]}
        case "spy_recalled":
            new_id = f"{frame}:recalled:{payload['post_id']}"
            data = {"player": payload["player"], "post_id": payload["post_id"]}
        case _:
            new_id = f"{frame}:unavailable"
            data = {"player": payload["player"]}
    del rest
    return {
        **event,
        "event_id": new_id,
        "payload": [[key, data[key]] for key in sorted(data)],
    }


def _views_in_base_form(old: Step, candidate: Step, keys: tuple[str, ...]) -> None:
    for view, base_view in zip(candidate.views, old.views, strict=True):
        for key in (*keys, "agent_boxes"):
            if key in base_view:
                view[key] = base_view[key]


def _split_rows(old: Step, candidate: Step) -> None:
    """The split boxes' rows, box events and Spy events in the base's form."""

    if any(effect is _IN_HIGH_PLACES and "spy" in icons for _, effect, icons in _now):
        # Its Spy still waits as an icon; the base's box was resolved.
        _views_in_base_form(old, candidate, ())

    events = []
    for event in candidate.events:
        kind = str(event["kind"])
        if kind.startswith("agent_card_effect_") and _split_card(event):
            continue
        if (
            kind in ("spy_placed", "spy_recalled", "spy_placement_unavailable")
            and ":agent_card:" in str(event["event_id"])
            and _split_card(event)
        ):
            event = _spy_in_base_form(event)
        events.append(event)
    if _reversed and _same_items(events, old.events):
        # The icons' order (``_split_moves``): the same events.
        events = list(old.events)
    candidate.events = events
    if old.step[0] != "a" or not _now or not isinstance(candidate.decision, list):
        return
    if not isinstance(old.decision, list):
        return
    rows, base = candidate.decision[1], old.decision[1]
    if not isinstance(rows, list) or not isinstance(base, list):
        return
    if base and all(row["action_id"] in _FRAME_SPY for row in base):
        # In High Places' Spy: the base's frame offered only its placement.
        # The candidate's turn offers its other effects beside the Spy rows,
        # never the turn's end while the Spy waits (OQ-057 (14)): a row list
        # with it stays as it is, so the comparison shows it.
        spy = [row for row in rows if row["action_id"] in _BOX_SPY]
        if any(row["action_id"] == "finish_agent_turn" for row in rows):
            return
        if len(spy) == len(base) and all(
            any(
                row["action_id"] == _FRAME_SPY[frame_row["action_id"]]
                and _row_args(row).get("post_id") == _row_args(frame_row).get("post_id")
                for row in spy
            )
            for frame_row in base
        ):
            candidate.decision[1] = list(base)
            candidate.page = old.page
            _views_in_base_form(old, candidate, ("decision_kind", "turn_owner"))
        return
    boxes = {box for box, _, _ in _now}
    kept = [row for row in rows if not _split_row(row)]
    base_kept = [
        row
        for row in base
        if not (
            row["action_id"] == "resolve_agent_card_effect"
            and "effect" not in _row_args(row)
            and _row_box(row) in boxes
        )
    ]
    if len(kept) != len(rows) and _same_items(kept, base_kept):
        candidate.decision[1] = list(base)
        candidate.page = old.page


SPLIT_BOXES = Rule(
    name="split_boxes",
    why="cleanup-2d-5: Clandestine Meeting, Occupation and In High Places "
    "resolve icon by icon (OQ-027, user decision 2026-10-18)",
    old=_split_base,
    new=_split_rows,
    moves=_split_moves,
)

# --- 2f: confirms where nothing can be done (user decision 2026-10-18) -------
#
# The 2026-09-30 principle ("결정 창 없이 자동으로 넘어가는 곳도 모두 결정 창을
# 연다"): a Signet stage left with nothing to do confirms
# (``resolve_leader_signet_without_option``) instead of its anti-jam
# refusal, and a Conflict trash reward with no card to trash opens its window
# with only ``resolve_combat_trash_without_card``.
_SIGNET_DECLINE = "decline_leader_signet_payment"
_SIGNET_NO_OPTION = "resolve_leader_signet_without_option"
_TRASH_NO_CARD = "resolve_combat_trash_without_card"


def _signet_confirm_moves(old: Step, at: At) -> tuple[DomainAction, ...] | None:
    """The base's anti-jam refusal is the candidate's confirm."""

    if old.step[0] != "a" or old.step[1] != _SIGNET_DECLINE:
        return None
    confirm = next(
        (action for action in at.legal if action.action_id == _SIGNET_NO_OPTION),
        None,
    )
    if confirm is None or any(a.action_id == _SIGNET_DECLINE for a in at.legal):
        return None
    return (confirm,)


def _signet_confirm_rows(old: Step, candidate: Step) -> None:
    """The confirm row and its event in the base's refusal form."""

    if isinstance(candidate.decision, list) and isinstance(old.decision, list):
        rows = candidate.decision[1]
        if (
            isinstance(rows, list)
            and any(
                isinstance(r, dict) and r.get("action_id") == _SIGNET_NO_OPTION
                for r in rows
            )
            and any(
                isinstance(r, dict) and r.get("action_id") == _SIGNET_DECLINE
                for r in old.decision[1]
            )
        ):
            for row in rows:
                if row.get("action_id") == _SIGNET_NO_OPTION:
                    row["action_id"] = _SIGNET_DECLINE
            if isinstance(candidate.page, list) and isinstance(old.page, list):
                candidate.page = old.page
    for event in candidate.events:
        if (
            event["kind"] == "leader_signet_unavailable"
            and old.step[1] == _SIGNET_DECLINE
        ):
            event["kind"] = "leader_signet_declined"
            event["event_id"] = str(event["event_id"]).removesuffix(
                ":unavailable"
            ) + ":declined"


SIGNET_CONFIRM = Rule(
    name="signet_confirm",
    why="cleanup-2f: a Signet stage with nothing to do confirms instead of "
    "its anti-jam refusal (the 2026-09-30 principle)",
    new=_signet_confirm_rows,
    moves=_signet_confirm_moves,
)


def _trash_confirm_answer(at: At) -> DomainAction | None:
    """The candidate's new window of a cardless Conflict trash reward."""

    if len(at.legal) == 1 and at.legal[0].action_id == _TRASH_NO_CARD:
        return at.legal[0]
    return None


def _trash_confirm_events(old: Step, candidate: Step) -> None:
    candidate.events = [
        event
        for event in candidate.events
        if event["kind"] != "combat_reward_trash_unavailable"
    ]


TRASH_CONFIRM = Rule(
    name="trash_confirm",
    why="cleanup-2f: a Conflict trash reward with no card opens its window "
    "with a confirm (the 2026-09-30 principle)",
    new=_trash_confirm_events,
    answer=_trash_confirm_answer,
)

# --- 2c-7: lists in event payloads (user decision 2026-10-18) ---------------
#
# "목록으로 바꾸자. 깔끔하게.": the id lists (and the seat and round numbers)
# an event once carried as one comma-joined string are lists. The base's
# strings in the candidate's form, for the kinds that carry them (and the
# cumulative check's older ``scouts_row_cleared``).
_LIST_KEYS: dict[str, type] = {
    "card_ids": str,
    "contract_ids": str,
    "dealt": str,
    "leader_ids": str,
    "locations": str,
    "players": int,
    "removed": str,
    "rounds": int,
    "space_ids": str,
    "subcommittee_ids": str,
}
_LIST_KINDS = frozenset(
    {
        "cards_revealed",
        "contracts_revealed",
        "imperium_row_cleared",
        "leader_draft_pool_revealed",
        "leader_draft_unused",
        "scouts_contracts_cleared",
        "scouts_maker_spice_added",
        "scouts_market_cleared",
        "scouts_market_revealed",
        "scouts_mission_goods_placed",
        "scouts_mission_layout",
        "scouts_row_cleared",
        "scouts_shield_wall_rebuilt",
        "scouts_subcommittees_revealed",
    }
)


def _payload_lists(step: Step) -> None:
    for event in step.events:
        if event["kind"] not in _LIST_KINDS:
            continue
        for pair in event["payload"]:
            kind = _LIST_KEYS.get(str(pair[0]))
            if kind is not None and isinstance(pair[1], str):
                items = [item for item in pair[1].split(",") if item]
                pair[1] = [int(item) for item in items] if kind is int else items


PAYLOAD_LISTS = Rule(
    name="payload_lists",
    why="cleanup-2c-7: an event's id or number list is a list, not one "
    "comma-joined string (user decision 2026-10-18)",
    old=_payload_lists,
)

RULES = (
    PAYLOAD_LISTS,
    SPLIT_BOXES,
    SIGNET_CONFIRM,
    TRASH_CONFIRM,
    SPY_PASS_FIRST,
    RETREAT_EVENT,
)
