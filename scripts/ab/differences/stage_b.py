"""Declared differences of stage B against master ``e7e9ad4f`` (codec v149).

B1 below; B2 (``COMBAT_REWARD_ICONS``) after it.


docs/stage-b-plan.md 3a, OQ-111: an Agent turn is a card pick
(``choose_agent_card``) and then a space pick (``place_agent``) instead of
one ``agent_turn`` placement. Everything else -- the state after the
placement, its events, every view and every other decision -- stays the
same, checked with ``engine_equivalence.py check --differences
scripts/ab/differences/stage_b1.py``. The pick waits in the turn frame
(left out of the comparison, like the whole decision stack), so a recorded
placement compares as its two moves: the state after both is the base's.
"""

import json
import re
from typing import Any

from equivalence_rules import At, Rule, Step

from dune_imperium.content.uprising.contracts import contract_for_instance
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome, is_fixed_outcome
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.rules.agent_turn import (
    agent_card_pick_actions,
    agent_space_pick_actions,
)
from dune_imperium.rules.combat import legacy_combat_reward_icon
from dune_imperium.rules.contracts import legacy_contract_reward_icon

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


# --- B2: a Conflict reward icon by icon (OQ-112) ----------------------------
#
# The base paid a recipient's reward in one step and pushed its choice
# frames together; the candidate opens a window per recipient and resolves
# each icon on its own row, answered here in the base's fixed order
# (``combat.legacy_combat_reward_icon``). Every later recipient's window
# closes before a pause the base had only after a recipient with choices;
# the other pauses are answered here. The base's summed
# ``combat_reward_gained`` is the candidate's header event plus each icon's
# events (``combat_reward_icon_resolved``, a reward's ``resources_gained``),
# all in the same step (the automatic icons and the Contract come first in
# the base's order): the candidate's are summed back into the base's event
# and compared with it, its count of Influence choices aside (a sandworm's
# second copy is answered a recorded step later); the other events compare
# as a multiset (the rows' events come after the step's own), and the state
# after every step still compares what was paid.
_ICON_EVENT = "combat_reward_icon_resolved"
_CONTRACT_ICON_EVENT = "contract_reward_icon_resolved"
# What a waiting Contract reward still has to give a seat.
_REWARD_FIELDS = (
    "resources",
    "troops_supply",
    "troops_garrison",
    "ungained_troops",
    "influence",
    "intrigue_cards",
    "deck",
    "hand",
    "discard_pile",
    "spies_supply",
)
# The source of an icon's resources (a Contract's 2 Solari without CHOAM
# too); an optional arrow's VP keeps the base's own source.
_ICON_SOURCE = re.compile(r"round:\d+:combat_reward:\d+:\d+(?::contract)?")
_REWARD_EVENT = "combat_reward_gained"


def _reward_answer(at: At) -> Any:
    if isinstance(at.decision, PlayerDecision):
        owner = at.decision.owner
        answer = legacy_combat_reward_icon(
            at.state, owner
        ) or legacy_contract_reward_icon(at.state, owner)
        # An owed draw of the owner's own turn comes first (OQ-106).
        return answer if answer in at.legal else None
    if isinstance(at.decision, ChanceDecision) and is_fixed_outcome(at.decision):
        later = at.rows[at.index + 1 :]
        upcoming = later[0][0] if later else None
        if (
            isinstance(upcoming, (list, tuple))
            and upcoming[0] == "c"
            and upcoming[1] == at.decision.decision_id
        ):
            return None
        if ":rewards" not in at.decision.decision_id:
            return None
        return ChanceOutcome(at.decision.decision_id, at.decision.options)
    return None


def _contract_shortfall(event: dict[str, Any]) -> bool:
    """A completed Contract's troop shortfall: the base's inside the
    completing step, the candidate's with its troops icon."""

    return event["kind"] == "troops_recruit_short" and str(event["event_id"]).endswith(
        ":completed:recruit_short"
    ) and ":contract:" in str(event["event_id"])


def _drops_reward_summary(old: Step) -> None:
    """The base's summed reward events: a Conflict reward's without its
    count of Influence choices, a Contract's with only the fact of the
    completion."""

    events = []
    for event in old.events:
        if _contract_shortfall(event):
            continue
        if event["kind"] == _REWARD_EVENT:
            event = {
                **event,
                "payload": [
                    pair for pair in event["payload"] if pair[0] != "choose_influence"
                ],
            }
        if event["kind"] == "contract_completed":
            fields = dict(event["payload"])
            if fields.get("personal_cards"):
                # The base drew the reward's card in the completing step;
                # a CHOAM Transports draw owed for the completion is the
                # owner's next step and comes before the candidate's reward
                # window (OQ-106), so the candidate draws it a step later.
                seat = fields["player"]
                old.fields_unchecked |= {
                    f"players[{seat}].{name}"
                    for name in ("deck", "hand", "discard_pile")
                }
            event = {
                **event,
                "payload": [
                    ["contract_id", fields["contract_id"]],
                    ["player", fields["player"]],
                ],
            }
        events.append(event)
    old.events = events


def _without_hands(views: list[Any]) -> list[Any]:
    """The views without the deck and hand counts an owed draw moves."""

    out = json.loads(json.dumps(views))
    for view in out:
        for player in view.get("players") or ():
            player.pop("deck_size", None)
            player.pop("hand_size", None)
        private = view.get("private")
        if isinstance(private, dict):
            for key in ("deck_size", "hand"):
                private.pop(key, None)
    return out


def _owed_draw_settled_early(old: Step, candidate: Step) -> None:
    """The pause after a reward window (before the next recipient, or the
    Conflict-end pause after the last) sees the owed card the candidate drew
    a step early (``_reward_events_in_base_form``): its views differ only in
    that seat's deck and hand."""

    if old.step[0] != "c" or not str(old.step[1]).endswith(
        (":rewards:pause", ":conflict_end:pause")
    ):
        return
    if candidate.views_now() == old.views_now():
        return
    if _without_hands(candidate.views) == _without_hands(old.views):
        candidate.views_text = old.views_now()
        candidate._views = None


def _without_frame(views: list[Any]) -> list[Any]:
    """The views without the top frame's kind and owner, and the deck and
    hand counts."""

    out = _without_hands(views)
    for view in out:
        view.pop("decision_kind", None)
        view.pop("turn_owner", None)
    return out


def _without_reward(views: list[Any]) -> list[Any]:
    """The views without the top frame and what a waiting reward window
    still has to give (resources, units, Influence, cards)."""

    out = _without_frame(views)
    for view in out:
        for player in view.get("players") or ():
            for key in (
                "resources",
                "troops_supply",
                "troops_garrison",
                "ungained_troops",
                "influence",
                "intrigue_count",
                "alliances",
            ):
                player.pop(key, None)
        private = view.get("private")
        if isinstance(private, dict):
            private.pop("intrigue_cards", None)
    return out


def _owed_draw_before_window(old: Step, candidate: Step) -> None:
    """A CHOAM Transports draw owed for a completed Contract is the owner's
    next step (OQ-106) and comes before the candidate's reward window, which
    already stands on top: the same legal draw, under another frame."""

    owed_draws = ("draw_owed_card", "draw_owed_intrigue")
    if old.step[0] != "a" or old.step[1] not in owed_draws:
        return
    if candidate.decision != old.decision:
        return
    if _without_reward(candidate.views) == _without_reward(old.views):
        candidate.views_text = old.views_now()
        candidate._views = None
        candidate.page = old.page


def _immediate_through_trigger(old: Step, candidate: Step) -> None:
    """An Immediate tile taken through Coercive Negotiation or an Arrakeen
    Scouts mission now announces its completion like one taken from the
    market (``contract_completed``); the base paid it without the event."""

    base = {
        dict(event["payload"]).get("contract_id")
        for event in old.events
        if event["kind"] == "contract_completed"
    }
    candidate.events = [
        event
        for event in candidate.events
        if event["kind"] != "contract_completed"
        or dict(event["payload"]).get("contract_id") in base
        or not contract_for_instance(
            str(dict(event["payload"])["contract_id"])
        ).completes_immediately
    ]


def _reward_events_in_base_form(old: Step, candidate: Step) -> None:
    _owed_draw_settled_early(old, candidate)
    _owed_draw_before_window(old, candidate)
    _immediate_through_trigger(old, candidate)
    def icon_event(event: dict[str, Any]) -> bool:
        if event["kind"] in (_ICON_EVENT, _REWARD_EVENT, _CONTRACT_ICON_EVENT):
            return True
        if _contract_shortfall(event):
            return True
        payload = event["payload"]
        fields = dict(payload) if isinstance(payload, (list, dict)) else {}
        source = fields.get("source")
        return (
            event["kind"] == "resources_gained"
            and isinstance(source, str)
            and (
                _ICON_SOURCE.fullmatch(source) is not None
                or source.endswith(":contract_reward")
            )
        )

    if (
        old.step[0] == "c"
        and str(old.step[1]).endswith(":rewards:pause")
        and any(icon_event(event) for event in candidate.events)
    ):
        # A card owed after a step (CHOAM Transports, Planetary Array;
        # ``tech.draw_owed_tech_cards``) waits while a chance decision is on
        # top: the base drew it a step later, the candidate as soon as a
        # reward window stood there instead. The next step compares in full.
        candidate.fields_unchecked |= {
            f"players[{seat}].{name}"
            for seat in range(4)
            for name in ("tech_cards_owed", "deck", "hand", "discard_pile")
        }
    resolved = {
        dict(event["payload"]).get("contract_id")
        for event in candidate.events
        if event["kind"] == _CONTRACT_ICON_EVENT
    }
    waiting = []
    for event in candidate.events:
        if event["kind"] != "contract_completed":
            continue
        fields = dict(event["payload"])
        if fields["contract_id"] not in resolved:
            # An immediate draw earned in the same step (a Bene Gesserit 4
            # Intrigue card, Imperial Birthright; OQ-106) comes before the
            # reward window: the base paid the reward inside the step, the
            # candidate after that draw, so the base's reward events and the
            # fields they moved come a step later (the next step compares in
            # full).
            waiting.append(str(event["event_id"]).removesuffix(":completed"))
            candidate.fields_unchecked |= {
                f"players[{fields['player']}].{name}" for name in _REWARD_FIELDS
            }
    if waiting:
        old.events = [
            event
            for event in old.events
            if not any(
                str(event["event_id"]).startswith(f"{source}:reward")
                for source in waiting
            )
        ]
    # The rows of a window whose completion came a step earlier: their
    # events are the base's, there.
    completed_here = {
        str(event["event_id"]).removesuffix(":completed")
        for event in candidate.events
        if event["kind"] == "contract_completed"
    }
    late = {
        str(event["event_id"]).rsplit(":reward_icon:", 1)[0]
        for event in candidate.events
        if event["kind"] == _CONTRACT_ICON_EVENT
    } - completed_here
    if late:
        candidate.events = [
            event
            for event in candidate.events
            if not any(
                str(event["event_id"]).startswith(f"{source}:reward")
                or str(event["event_id"]).startswith(f"{source}:contract_reward")
                for source in late
            )
        ]
    if not any(icon_event(event) for event in candidate.events):
        return
    summaries = _summed_rewards(candidate.events)
    rest = [
        event
        for event in candidate.events
        if not icon_event(event) and event["kind"] != _REWARD_EVENT
    ]
    old_rest = [event for event in old.events if event["kind"] != _REWARD_EVENT]
    # A Contract row answered a recorded step later (a Navigation play or
    # another choice the reward's Influence opened stands above the window)
    # says its count there; the summed event here has none to compare.
    contract_rows = {
        (dict(event["payload"])["player"], dict(event["payload"])["rank"])
        for event in candidate.events
        if event["kind"] == _ICON_EVENT
        and dict(event["payload"]).get("effect") == "contract"
    }
    old_summaries = [
        event
        if (dict(event["payload"])["player"], dict(event["payload"])["rank"])
        in contract_rows
        else {
            **event,
            "payload": [pair for pair in event["payload"] if pair[0] != "contracts"],
        }
        for event in old.events
        if event["kind"] == _REWARD_EVENT
    ]
    key = lambda event: json.dumps(  # noqa: E731
        {**event, "payload": dict(event["payload"])}, sort_keys=True
    )
    # The rows come one by one after the step's other events, so a reward's
    # own events (an Intrigue draw, an Influence step, a completion) may
    # stand in another order than the base's: the rest compares as a
    # multiset, the summed rewards exactly.
    if sorted(map(key, rest)) == sorted(map(key, old_rest)) and sorted(
        map(key, summaries)
    ) == sorted(map(key, old_summaries)):
        candidate.events = list(old.events)
    else:
        candidate.events = [*rest, *summaries]


def _summed_rewards(events: list[Any]) -> list[Any]:
    """Each recipient's header with its icons' amounts summed back into the
    base's ``combat_reward_gained`` (zero amounts left out, as there)."""

    sums: dict[tuple[Any, Any], dict[str, Any]] = {}
    headers: list[Any] = []
    for event in events:
        if event["kind"] == _REWARD_EVENT:
            fields = dict(event["payload"])
            sums[(fields["player"], fields["rank"])] = dict(fields)
            headers.append(event)
    for event in events:
        fields = dict(event["payload"]) if isinstance(event["payload"], list) else {}
        if event["kind"] == _ICON_EVENT:
            total = sums.get((fields.get("player"), fields.get("rank")))
            if total is None:
                continue
            for name in ("troops", "intrigue", "victory_points", "contracts"):
                if fields.get(name):
                    total[name] = total.get(name, 0) + fields[name]
            if fields.get("effect") == "faction_influence":
                total["faction"] = fields["faction"]
                total["faction_influence"] = (
                    total.get("faction_influence", 0) + fields["influence"]
                )
            if fields.get("effect") == "control":
                total["control_space_id"] = fields["space_id"]
        elif event["kind"] == "resources_gained":
            match = _ICON_SOURCE.fullmatch(str(fields.get("source", "")))
            if match is None:
                continue
            _, player, rank = str(fields["source"]).split(":contract")[0].rsplit(":", 2)
            total = sums.get((int(player), int(rank)))
            if total is None:
                continue
            for name in ("solari", "spice", "water"):
                if fields.get(name):
                    total[name] = total.get(name, 0) + fields[name]
    return [
        {
            **header,
            "payload": sorted(
                [name, value]
                for name, value in sums[
                    (dict(header["payload"])["player"], dict(header["payload"])["rank"])
                ].items()
            ),
        }
        for header in headers
    ]




COMBAT_REWARD_ICONS = Rule(
    name="combat_reward_icons",
    why="stage B2 (OQ-112): a Conflict reward's recipient, and a completed "
    "Contract's owner, resolves its icons one row each, in any order",
    old=_drops_reward_summary,
    new=_reward_events_in_base_form,
    answer=_reward_answer,
)

RULES: tuple[Rule, ...] = (AGENT_TURN_STEPS, COMBAT_REWARD_ICONS)
