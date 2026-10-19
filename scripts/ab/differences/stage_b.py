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
from collections import Counter
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
        view.pop("decision_owner", None)
        view.pop("intrigue_deck_size", None)
        for player in view.get("players") or ():
            for key in (
                "resources",
                "troops_supply",
                "troops_garrison",
                "troops_conflict",
                "combat_strength",
                "ungained_troops",
                "influence",
                "intrigue_count",
                "intrigue_card_count",
                "victory_points",
                "alliances",
            ):
                player.pop(key, None)
        private = view.get("private")
        if isinstance(private, dict):
            private.pop("intrigue_cards", None)
            # The deck's top card the seat knows, which a reward's card
            # draw moves.
            private.pop("peeked_card_id", None)
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


# What a game's earlier steps left for later ones (module state, one game at
# a time per worker): a Contract's reward events the base had where the
# candidate's rows still wait behind an immediate draw, the windows waiting,
# the CHOAM Transports cards taken before the record drew them.
_GAME: dict[str, Any] = {
    "last": -1,
    "moved": [],
    "since": -1,
    "windows": {},
    "taken": Counter(),
    "swapped": None,
}
_WAIT_STEPS = 3


def _game_step(index: int) -> None:
    """Start afresh when a new game begins (its steps count from 0 again)."""

    if index < _GAME["last"]:
        _GAME.update(moved=[], since=-1, windows={}, taken=Counter(), swapped=None)
    _GAME["last"] = index


def _event_key(event: dict[str, Any]) -> str:
    return json.dumps(event, sort_keys=True)


def _moved_rewards(
    old: Step, candidate: Step, waiting: list[str], late: set[str]
) -> None:
    """Move a waiting Contract reward's events from the base's step to the
    candidate's later one, and leave the state they moved unchecked in
    between (a few steps at most; past that a difference shows)."""

    if late:
        # The rows of a window whose completion came a step earlier (an
        # event the base has here too, such as the reshuffle a row's card
        # draw asked for, stays).
        base = Counter(map(_event_key, old.events))
        kept = []
        for event in candidate.events:
            key = _event_key(event)
            if base[key] > 0:
                base[key] -= 1
            elif any(
                str(event["event_id"]).startswith(f"{source}:reward")
                or str(event["event_id"]).startswith(f"{source}:contract_reward")
                for source in late
            ):
                continue
            kept.append(event)
        candidate.events = kept
    if _GAME["moved"] and old.index - _GAME["since"] <= _WAIT_STEPS:
        base = Counter(map(_event_key, old.events))
        kept = []
        for event in candidate.events:
            key = _event_key(event)
            if base[key] > 0:
                base[key] -= 1
            elif key in _GAME["moved"]:
                _GAME["moved"].remove(key)
                continue
            kept.append(event)
        candidate.events = kept
    elif _GAME["moved"]:
        _GAME["moved"] = []
    if waiting:
        theirs = Counter(map(_event_key, candidate.events))
        rest = []
        for event in old.events:
            key = _event_key(event)
            if theirs[key] > 0:
                theirs[key] -= 1
                rest.append(event)
            else:
                _GAME["moved"].append(key)
        old.events = rest
        _GAME["since"] = old.index
    # The step's views are those before it: a window waiting then still
    # shows its reward unpaid. Its state is after it.
    waited = bool(_GAME["windows"])
    _GAME["windows"] = {
        source: since
        for source, since in {
            **_GAME["windows"],
            **dict.fromkeys(waiting, old.index),
        }.items()
        if source not in late and old.index - since <= _WAIT_STEPS
    }
    if waited and _without_reward(candidate.views) == _without_reward(old.views):
        candidate.views_text = old.views_now()
        candidate._views = None
    if _GAME["windows"] or _GAME["moved"] or any(_GAME["taken"].values()):
        candidate.state_unchecked = True


def _shuffle_seat(decision_id: str) -> str | None:
    """The seat whose discard pile a reshuffle decision shuffles."""

    if not decision_id.endswith(":discard_shuffle") or ":player:" not in decision_id:
        return None
    return decision_id.split(":player:", 1)[1].split(":", 1)[0]


def _swapped_reshuffle(recorded: str, asked: str) -> bool:
    """A CHOAM Transports card's reshuffle against a Contract reward draw's,
    of the same seat: whichever of the two draws found the deck empty."""

    names = (recorded, asked)
    return (
        recorded != asked
        and _shuffle_seat(recorded) is not None
        and _shuffle_seat(recorded) == _shuffle_seat(asked)
        and sum(name.endswith(":tech_draw:discard_shuffle") for name in names) == 1
        and sum(
            name.endswith(":reward:personal_draw:discard_shuffle") for name in names
        )
        == 1
    )


def _transports_moves(old: Step, at: At) -> tuple[Any, ...] | None:
    """The candidate's moves where CHOAM Transports' card comes first (the
    user decision of 2026-10-19; records bridge ``transports_card_first``):
    a recorded step that waits behind the card takes the card first, the
    record's own card draw then vanishes, and a reshuffle recorded under the
    other draw's name is asked under the candidate's."""

    _game_step(old.index)
    taken: Counter[int] = _GAME["taken"]
    if old.step[0] == "c":
        if isinstance(at.decision, ChanceDecision) and _swapped_reshuffle(
            str(old.step[1]), at.decision.decision_id
        ):
            if sorted(at.decision.options) == sorted(old.step[2]):
                return (ChanceOutcome(at.decision.decision_id, tuple(old.step[2])),)
    if not isinstance(at.decision, PlayerDecision):
        return None
    owner = at.decision.owner
    draw = DomainAction(action_id="draw_owed_card", actor=owner)
    if old.step[0] == "a" and old.step[1] == "draw_owed_card":
        if taken[owner] > 0 and draw not in at.legal:
            taken[owner] -= 1
            return ()
        return None
    if at.legal != (draw,) or not any(
        entry[1] == "choam_transports" for entry in at.state.players[owner].owed_draws
    ):
        return None
    after = at.engine.apply(at.state, draw).state
    taken[owner] += 1
    if old.step[0] != "c":
        return (draw,)
    # The recorded reshuffle: the card's own (the deck was empty), or the
    # Contract's card draw's once the window's rows are answered.
    moves: list[Any] = [draw]
    for _ in range(8):
        decision = at.engine.current_decision(after)
        if isinstance(decision, ChanceDecision):
            name = decision.decision_id
            if name == old.step[1] or (
                _swapped_reshuffle(str(old.step[1]), name)
                and sorted(decision.options) == sorted(old.step[2])
            ):
                _GAME["swapped"] = (old.index, name, str(old.step[1]))
                return (*moves, ChanceOutcome(name, tuple(old.step[2])))
            break
        if not isinstance(decision, PlayerDecision):
            break
        row = legacy_contract_reward_icon(after, decision.owner)
        if row is None or row not in at.engine.legal_actions(after, decision.owner):
            break
        moves.append(row)
        after = at.engine.apply(after, row).state
    return (draw,)


def _reshuffle_in_base_form(old: Step, candidate: Step) -> None:
    """A renamed reshuffle's decision and event read as the base's; so does
    a recorded reshuffle the candidate asked behind CHOAM Transports' card,
    under the card's decision (``_transports_moves``)."""

    swapped = _GAME.get("swapped")
    if swapped is not None and swapped[0] == old.index:
        _GAME["swapped"] = None
        asked, recorded = swapped[1], swapped[2]
        candidate.decision = old.decision
        candidate.page = old.page
        if _without_reward(candidate.views) == _without_reward(old.views):
            candidate.views_text = old.views_now()
            candidate._views = None
        asked_id = asked.removesuffix("discard_shuffle") + "discard_shuffled"
        recorded_id = recorded.removesuffix("discard_shuffle") + "discard_shuffled"
        candidate.events = [
            {**event, "event_id": recorded_id}
            if event["event_id"] == asked_id
            else event
            for event in candidate.events
        ]
        return
    if old.step[0] != "c" or candidate.decision == old.decision:
        return
    if not isinstance(candidate.decision, list) or not isinstance(old.decision, list):
        return
    asked, recorded = str(candidate.decision[0]), str(old.decision[0])
    if (
        _swapped_reshuffle(recorded, asked)
        and sorted(candidate.decision[1]) == sorted(old.decision[1])
        and candidate.decision[2:] == old.decision[2:]
    ):
        candidate.decision = old.decision
        asked_id = asked.removesuffix("discard_shuffle") + "discard_shuffled"
        recorded_id = recorded.removesuffix("discard_shuffle") + "discard_shuffled"
        candidate.events = [
            {**event, "event_id": recorded_id}
            if event["event_id"] == asked_id
            else event
            for event in candidate.events
        ]


def _reward_events_in_base_form(old: Step, candidate: Step) -> None:
    _game_step(old.index)
    _reshuffle_in_base_form(old, candidate)
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
    for event in candidate.events:
        if event["kind"] != "contract_completed":
            continue
        # CHOAM Transports' card owed outside its owner's turn is drawn by
        # the engine's post-step hook, which waits while a chance decision
        # is on top: the base completed the Contract under the pause before
        # the next recipient, the candidate under its reward window, which
        # draws the card a step earlier.
        seat = dict(event["payload"])["player"]
        candidate.fields_unchecked |= {
            f"players[{seat}].{name}"
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
            # An immediate draw earned in the same step (CHOAM Transports'
            # card, OQ-106 13 and the user decision of 2026-10-19; a Bene
            # Gesserit 4 Intrigue card) comes before the reward window: the
            # base paid the reward inside the step, the candidate after that
            # draw (and the reshuffle it may ask for).
            waiting.append(str(event["event_id"]).removesuffix(":completed"))
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
    _moved_rewards(old, candidate, waiting, late)
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
    moves=_transports_moves,
    answer=_reward_answer,
)

RULES: tuple[Rule, ...] = (AGENT_TURN_STEPS, COMBAT_REWARD_ICONS)
