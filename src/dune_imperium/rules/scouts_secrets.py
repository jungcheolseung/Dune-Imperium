"""Arrakeen Scouts: secret picks (docs/rules/arrakeen-scouts.md 7).

A secret event (Covert Operation, Offworld Operation) has each seat, in
turn order, pick one of four lines in secret (OQ-071). A pick is kept in
``GameState.scouts_secret_picks`` and is its seat's alone
(``core.observation.secret_pick_id`` in ``known_card_seats``); nobody else
sees it until it is due, one or two rounds later, at the start of that
round's Scouts step, before the round's own item (OQ-085). Then every due
pick is revealed at once and resolved in event order, line order and turn
order. A pick still waiting when the game ends is lost.

A pick is one action, ``scouts_secret_pick(pick=i)``, offered with all four
values whatever the seat holds, so neither the action id nor the mask says
anything; the server hides its argument from the other seats' log
(``server.session_log.SEALED_ACTION_IDS``).

The original game's Covert Operation (stage P8c, docs/rules/arrakeen-scouts.md
9a): two of its lines give Influence with a Faction named when the pick is
made (``SecretChoice.names_faction``). Such a pick is still one action,
``scouts_secret_pick(faction=f, pick=i)``, one per Faction, all offered
whatever the seat holds; the Faction is part of the hidden pick
(``GameState.scouts_secret_factions``, under the pick's own registry id), the
other seats' log shows the pick's ``pick`` key alone
(``server.session_log.SEALED_SHOWN_KEYS``), and the reveal names it with the
pick. At the reveal the line is the seat's to pay as any other revealed
line's (OQ-085 (c)): a seat that cannot pay its discard gets nothing (OQ-071).
"""

from copy import replace
from typing import Final

from dune_imperium.content.arrakeen_scouts import EVENTS_BY_ID
from dune_imperium.content.core.icons import Faction
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import FrameKind, context_str, owned_top_frame
from dune_imperium.rules.scouts_effects import offer_secret_reward

SECRET_ITEM: Final = "secrets"
_SECRET_FRAME: Final = "Secret pick frame"


def secret_tasks(order: tuple[int, ...]) -> tuple[str, ...]:
    """A secret event's tasks: each seat picks, in turn order (OQ-071)."""

    return tuple(f"secret:{seat}" for seat in order)


def pick_delay(event_id: str, pick: int) -> int:
    return EVENTS_BY_ID[event_id].secret_choices[pick].delay


def pick_names_faction(event_id: str, pick: int) -> bool:
    """Whether line ``pick`` of ``event_id`` names a Faction when picked."""

    return EVENTS_BY_ID[event_id].secret_choices[pick].names_faction


def pick_alternatives(
    state: GameState, row: tuple[int, str, int, int]
) -> tuple[int, ...]:
    """The picks another seat cannot tell ``row``'s from.

    Before the event's next round revealed its one-round picks, any line;
    after it, a pick still waiting is one of the two-round lines.
    """

    event_round, event_id, _, _ = row
    lines = range(len(EVENTS_BY_ID[event_id].secret_choices))
    if state.scouts_secrets_round < event_round + 1:
        return tuple(lines)
    return tuple(line for line in lines if pick_delay(event_id, line) == 2)


# --- Picking --------------------------------------------------------------------------


def offer_secret_pick(
    state: GameState, player: int, event_id: str, *, source: str
) -> RuleResult:
    frame = DecisionFrame(
        kind=FrameKind.SCOUTS_SECRET,
        frame_id=f"{source}:secret",
        decision=PlayerDecision(owner=player, prompt="Make a secret pick"),
        context=(("event_id", event_id), ("source", source)),
    )
    return RuleResult(state=state.push_decision(frame))


def legal_secret_pick_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    frame = owned_top_frame(state, FrameKind.SCOUTS_SECRET, player)
    if frame is None:
        return ()
    event_id = context_str(dict(frame.context), "event_id", owner=_SECRET_FRAME)
    actions: list[DomainAction] = []
    for pick in range(len(EVENTS_BY_ID[event_id].secret_choices)):
        if pick_names_faction(event_id, pick):
            # Every Faction, whatever the seat's Influence: the mask says
            # nothing of the pick either.
            actions.extend(
                DomainAction(
                    action_id="scouts_secret_pick",
                    actor=player,
                    arguments=(("faction", faction.value), ("pick", pick)),
                )
                for faction in Faction
            )
        else:
            actions.append(
                DomainAction(
                    action_id="scouts_secret_pick",
                    actor=player,
                    arguments=(("pick", pick),),
                )
            )
    return tuple(actions)


def apply_secret_pick(state: GameState, action: DomainAction) -> RuleResult:
    """Record the pick; the public event names the seat, never the line."""

    if action not in legal_secret_pick_actions(state, action.actor):
        raise ValueError("action is not a legal secret pick")
    context = dict(state.decision_stack[-1].context)
    event_id = context_str(context, "event_id", owner=_SECRET_FRAME)
    source = context_str(context, "source", owner=_SECRET_FRAME)
    arguments = dict(action.arguments)
    pick = arguments["pick"]
    assert isinstance(pick, int)
    row = (state.round_number, event_id, action.actor, pick)
    faction = arguments.get("faction")
    named = (
        ((state.round_number, action.actor, str(faction)),)
        if faction is not None
        else ()
    )
    return RuleResult(
        state=replace(
            state.pop_decision(),
            scouts_secret_picks=(*state.scouts_secret_picks, row),
            scouts_secret_factions=(*state.scouts_secret_factions, *named),
        ),
        events=(
            GameEvent(
                event_id=f"{source}:picked",
                kind="scouts_secret_picked",
                payload=(("item_id", event_id), ("player", action.actor)),
            ),
        ),
    )


# --- The due round -------------------------------------------------------------------


def secrets_are_due(state: GameState) -> bool:
    """Whether this round's Scouts step has yet to reveal its due picks."""

    return state.scouts_secrets_round < state.round_number


def reveal_due_secrets(state: GameState, order: tuple[int, ...]) -> RuleResult:
    """Reveal every pick due this round and queue their rewards (OQ-085 (b)).

    Order: the event revealed first, then the line's printed order, then the
    seats from the First Player.
    """

    round_number = state.round_number
    due = [
        row
        for row in state.scouts_secret_picks
        if row[0] + pick_delay(row[1], row[3]) <= round_number
    ]
    seat_rank = {seat: rank for rank, seat in enumerate(order)}
    due.sort(key=lambda row: (row[0], row[3], seat_rank[row[2]]))
    # A named Faction is revealed with its pick (``scouts_secret_factions``).
    named = {(row[0], row[1]): row[2] for row in state.scouts_secret_factions}
    due_keys = {(row[0], row[2]) for row in due}
    revealed = replace(
        state,
        scouts_secrets_round=round_number,
        scouts_secret_picks=tuple(r for r in state.scouts_secret_picks if r not in due),
        scouts_secret_factions=tuple(
            row
            for row in state.scouts_secret_factions
            if (row[0], row[1]) not in due_keys
        ),
    )
    if not due:
        return RuleResult(state=revealed)
    events = tuple(
        _revealed_event(
            round_number, row, named.get((row[0], row[2]), "")
        )
        for row in due
    )
    return RuleResult(
        state=replace(
            revealed,
            scouts_item=SECRET_ITEM,
            scouts_tasks=tuple(
                f"secret_reward:{event_round}:{event_id}:{seat}:{pick}"
                + (
                    f":{named[(event_round, seat)]}"
                    if (event_round, seat) in named
                    else ""
                )
                for event_round, event_id, seat, pick in due
            ),
        ),
        events=events,
    )


def _revealed_event(
    round_number: int, row: tuple[int, str, int, int], faction: str
) -> GameEvent:
    """A due pick's public reveal; a pick that named a Faction names it too."""

    event_round, event_id, seat, pick = row
    event_id_text = f"round:{round_number}:scouts:secrets:{event_round}:{seat}"
    if faction:
        return GameEvent(
            event_id=event_id_text,
            kind="scouts_secret_revealed",
            payload=(
                ("event_round", event_round),
                ("faction", faction),
                ("item_id", event_id),
                ("pick", pick),
                ("player", seat),
            ),
        )
    return GameEvent(
        event_id=event_id_text,
        kind="scouts_secret_revealed",
        payload=(
            ("event_round", event_round),
            ("item_id", event_id),
            ("pick", pick),
            ("player", seat),
        ),
    )


def run_secret_reward(state: GameState, task: str) -> RuleResult:
    """Resolve one revealed pick for its seat."""

    event_round, event_id, seat, pick, *named = task.removeprefix(
        "secret_reward:"
    ).split(":")
    source = f"round:{state.round_number}:scouts:secrets:{event_round}:{seat}"
    return offer_secret_reward(
        state,
        int(seat),
        event_id,
        int(pick),
        source=source,
        faction=named[0] if named else "",
    )
