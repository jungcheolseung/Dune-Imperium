"""Rise of Ix's Unload: a Reveal box gained when its card is discarded or trashed.

"Unload 표시가 있는 Reveal box는 Reveal turn에 공개할 때(보통처럼, Unload 표시는
무시) 말고도, 그 카드를 **discard할 때**와 **trash할 때** 얻는다. 남의 효과로
버려져도 된다" (docs/rules/rise-of-ix.md 7, [Rise of Ix p. 7]). An Imperium
card marks its Reveal box with ``ImperiumCardEntry.unload``; the box is its
Reveal gain record (``reveal_abilities.REVEAL_GAIN_ABILITIES``), whose icons
are gained again, one by one, by:

- a discard from hand (``card_discard.discard_personal_card_from_hand``),
  whoever's effect asks for it -- "discard" is a hand card unless the text
  says otherwise [FAQ p. 2]; Clean Up moving in-play cards to the discard pile
  is no discard and never comes here;
- any trash of the card (``card_trash.trash_personal_card``): "trash되는
  카드의 Unload는 trash되는 중에 일어난다" (designer ruling, rise-of-ix.md 7),
  and a revealed Unload card trashed in the same Reveal turn gives its box
  again (OQ-120).

How the icons are taken:

- Triggered by a cost: "비용 → 효과 줄의 왼쪽(비용)이 Unload를 일으키면
  Unload를 끝까지 해결한 뒤 오른쪽으로 간다" (designer ruling, rise-of-ix.md 7).
  The cost's caller passes ``at_once``: the box is paid inside the payment,
  before the line's reward (``pay_unload``).
- Triggered by an effect inside its owner's own turn: each icon waits on the
  turn's frame as a mandatory row (``turn_rows.UNLOAD_ICON``), as a Contract's
  icons do (OQ-112 (4)), and holds the turn's end until taken.
- Outside its owner's turn (an opponent's effect discards it, a Combat reward
  trashes it): the window ``FrameKind.UNLOAD_ICONS``, one row per icon, in the
  owner's order.

The transitions only announce an Unload owed by an effect (the event
``card_unloaded`` with ``pending``); the engine queues its rows or opens its
window once the action's handler is done (``settle_unloads``), because the
callers write their own frame back after the transition and would drop a
row or a window put there before.

Only Reveal boxes of plain resource gains are wired (Water Peddler, CHOAM
Delegate). A box with a condition, a choice, a cost, Persuasion or swords
belongs to its card's brief (Esmar Tuek, Freighter Fleet, Guild Accord, In The
Shadows, Ix-Guild Compact, Treachery -- whose Combat-reward case is OQ-127 --
and the promo Boundless Ambition): ``unload_icons`` refuses it.
"""

from copy import replace
from functools import cache
from typing import Final

from dune_imperium.content.uprising.effect_dsl import GainResources
from dune_imperium.content.uprising.imperium import (
    IMPERIUM_CARDS_BY_ID,
    imperium_card_for_instance,
)
from dune_imperium.content.uprising.reveal_abilities import REVEAL_GAIN_ABILITIES
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules import turn_rows
from dune_imperium.rules.frames import (
    FrameKind,
    context_str,
    owned_top_frame,
    replace_player,
    replace_top_frame,
    with_context,
)
from dune_imperium.rules.gain_events import resources_gained_event

UNLOAD_ICON_ACTION: Final = "resolve_unload_icon"
UNLOADED_EVENT: Final = "card_unloaded"
UNLOAD_ICONS_KEY: Final = "unload_icons"
"""The window's icons still owed: ``"<card instance>|<icon>"`` joined by
commas, in printed order."""
UNLOAD_PROMPT: Final = "Gain your Unload card's Reveal box"

_RESOURCES: Final = ("solari", "spice", "water")
_FRAME: Final = "Unload frame"

type UnloadIcon = tuple[str, int]
"""One icon of an Unload box: the resource it gains and how many."""


@cache
def _box_icons(definition_id: str) -> tuple[UnloadIcon, ...]:
    entry = IMPERIUM_CARDS_BY_ID[definition_id]
    if entry.reveal_persuasion or entry.reveal_strength or entry.reveal_choice_effects:
        raise NotImplementedError(
            f"{definition_id}: an Unload box with Persuasion, swords or a choice"
        )
    ability = REVEAL_GAIN_ABILITIES.get(definition_id)
    if ability is None:
        raise ValueError(f"{definition_id} is marked Unload but has no Reveal box")
    icons: list[UnloadIcon] = []
    for line in ability.sections:
        if line.condition is not None or line.costs:
            raise NotImplementedError(
                f"{definition_id}: an Unload box line with a condition or a cost"
            )
        for reward in line.rewards:
            if not isinstance(reward, GainResources):
                raise NotImplementedError(
                    f"{definition_id}: an Unload box icon {reward!r} is not wired"
                )
            icons.extend(
                (name, getattr(reward, name))
                for name in _RESOURCES
                if getattr(reward, name)
            )
    return tuple(icons)


def unload_icons(card_id: str) -> tuple[UnloadIcon, ...]:
    """The icons the personal card ``card_id`` gives when discarded or
    trashed: its Reveal box's when it is marked Unload, else none."""

    if not card_id.startswith("imperium:"):
        return ()
    entry = imperium_card_for_instance(card_id)
    if not entry.unload:
        return ()
    return _box_icons(entry.card.card_id)


def _gain(state: GameState, player: int, name: str, amount: int) -> GameState:
    owner = state.players[player]
    gained = replace(
        owner,
        resources=replace(
            owner.resources,
            **{name: getattr(owner.resources, name) + amount},
        ),
    )
    return replace(state, players=replace_player(state.players, gained))


def trigger_unload(
    state: GameState,
    player: int,
    card_id: str,
    *,
    source: str,
    at_once: bool = False,
) -> RuleResult:
    """Announce ``card_id``'s Unload after its discard or trash, paying the
    box at once when a cost triggered it (module docstring); a card that is
    not an Unload card changes nothing."""

    icons = unload_icons(card_id)
    if not icons:
        return RuleResult(state=state)
    unload_source = f"{source}:unload:{card_id}"
    events = [
        GameEvent(
            event_id=unload_source,
            kind="card_unloaded",
            payload=(
                ("card_id", card_id),
                ("pending", not at_once),
                ("player", player),
            ),
        )
    ]
    if at_once:
        for name, amount in icons:
            state = _gain(state, player, name, amount)
            events.append(
                resources_gained_event(
                    f"{unload_source}:{name}", player, **{name: amount}
                )
            )
    return RuleResult(state=state, events=tuple(events))


def _value(card_id: str, name: str) -> str:
    return f"{card_id}|{name}"


def _owe(state: GameState, player: int, card_id: str, source: str) -> GameState:
    """The icons of an Unload an effect triggered: rows of the owner's own
    turn, else a window of their own."""

    values = tuple(_value(card_id, name) for name, _ in unload_icons(card_id))
    if turn_rows.waits_on_turn(state, player):
        for value in values:
            queued = turn_rows.queue(
                state, player, (turn_rows.UNLOAD_ICON, source, value)
            )
            assert queued is not None
            state = queued
        return state
    return state.push_decision(
        DecisionFrame(
            kind=FrameKind.UNLOAD_ICONS,
            frame_id=f"{source}:icons",
            decision=PlayerDecision(owner=player, prompt=UNLOAD_PROMPT),
            context=tuple(
                sorted(((UNLOAD_ICONS_KEY, ",".join(values)), ("source", source)))
            ),
        )
    )


def settle_unloads(result: RuleResult) -> RuleResult:
    """Queue the rows or open the windows of the Unloads ``result``'s
    events announce as owed, once the action's handler is done."""

    owed = [
        event
        for event in result.events
        if event.kind == UNLOADED_EVENT and dict(event.payload).get("pending") is True
    ]
    if not owed:
        return result
    state = result.state
    # Windows stack: the last pushed is answered first, so the first
    # Unload announced is pushed last.
    for event in reversed(owed):
        payload = dict(event.payload)
        player, card_id = payload["player"], payload["card_id"]
        assert isinstance(player, int) and isinstance(card_id, str)
        state = _owe(state, player, card_id, event.event_id)
    return RuleResult(state=state, events=result.events)


def _row(player: int, value: str) -> DomainAction:
    card_id, name = value.split("|")
    return DomainAction(
        action_id=UNLOAD_ICON_ACTION,
        actor=player,
        arguments=(("card_id", card_id), ("effect", name)),
    )


def _window_values(frame: DecisionFrame) -> tuple[str, ...]:
    text = context_str(dict(frame.context), UNLOAD_ICONS_KEY, owner=_FRAME)
    return tuple(value for value in text.split(",") if value)


def legal_unload_window_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """A row per icon still owed in ``player``'s Unload window."""

    frame = owned_top_frame(state, FrameKind.UNLOAD_ICONS, player)
    if frame is None:
        return ()
    return tuple(_row(player, value) for value in dict.fromkeys(_window_values(frame)))


def legal_unload_row_actions(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """A row per Unload icon waiting on ``player``'s own turn."""

    frame = turn_rows.rows_frame(state, player)
    if frame is None:
        return ()
    return tuple(
        _row(player, value)
        for value in dict.fromkeys(
            value
            for kind, _source, value in turn_rows.pending(frame)
            if kind == turn_rows.UNLOAD_ICON
        )
    )


def apply_unload_icon(state: GameState, action: DomainAction) -> RuleResult:
    """Take one Unload icon: a row of its window or of its owner's turn."""

    player = action.actor
    arguments = dict(action.arguments)
    card_id, name = str(arguments["card_id"]), str(arguments["effect"])
    value = _value(card_id, name)
    frame = owned_top_frame(state, FrameKind.UNLOAD_ICONS, player)
    if frame is not None:
        if action not in legal_unload_window_actions(state, player):
            raise ValueError("action is not a legal Unload icon")
        context = dict(frame.context)
        source = context_str(context, "source", owner=_FRAME)
        remaining = list(_window_values(frame))
        remaining.remove(value)
        if remaining:
            context[UNLOAD_ICONS_KEY] = ",".join(remaining)
            state = replace_top_frame(state, with_context(frame, context))
        else:
            state = state.pop_decision()
    else:
        if action not in legal_unload_row_actions(state, player):
            raise ValueError("action is not a legal Unload icon")
        rows_frame = turn_rows.rows_frame(state, player)
        assert rows_frame is not None
        item = next(
            item
            for item in turn_rows.pending(rows_frame)
            if item[0] == turn_rows.UNLOAD_ICON and item[2] == value
        )
        source = item[1]
        state = turn_rows.take(state, player, item)
    amount = dict(unload_icons(card_id))[name]
    return RuleResult(
        state=_gain(state, player, name, amount),
        events=(resources_gained_event(f"{source}:{name}", player, **{name: amount}),),
    )
