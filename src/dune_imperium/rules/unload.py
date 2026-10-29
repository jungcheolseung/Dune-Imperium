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

Wired so far: Reveal boxes of plain resource gains (Water Peddler, CHOAM
Delegate, Esmar Tuek), of a printed Faction's Influence (In The Shadows) and
of troops deployed from the supply (Treachery, also during Combat, OQ-127),
also on a line with a condition the owner's seat alone settles (Guild
Accord's "[Spacing Guild] Alliance: [3 spice]"). A conditioned
icon is gained when its condition holds as the card is discarded or trashed:
the Unload happens then ("trash되는 카드의 Unload는 trash되는 중에 일어난다"),
and the rows and the window only let the owner order what it gained. A box
with a choice, a cost, Persuasion or swords belongs to its card's brief
(Freighter Fleet, Ix-Guild Compact and the promo Boundless Ambition):
``unload_icons`` refuses it.
"""

from copy import replace
from dataclasses import dataclass
from functools import cache
from typing import Final

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    CommandReached,
    Condition,
    DeployFromSupply,
    FactionBond,
    GainInfluence,
    GainResources,
)
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
from dune_imperium.rules.conditions import owner_condition_holds
from dune_imperium.rules.frames import (
    FrameKind,
    context_str,
    owned_top_frame,
    replace_player,
    replace_top_frame,
    with_context,
)
from dune_imperium.rules.gain_events import resources_gained_event
from dune_imperium.rules.influence import gain_faction_influence

UNLOAD_ICON_ACTION: Final = "resolve_unload_icon"
UNLOADED_EVENT: Final = "card_unloaded"
UNLOAD_ICONS_KEY: Final = "unload_icons"
"""The window's icons still owed: ``"<card instance>|<icon>"`` joined by
commas, in printed order."""
UNLOAD_PROMPT: Final = "Gain your Unload card's Reveal box"

_RESOURCES: Final = ("solari", "spice", "water")
INFLUENCE_ICON_PREFIX: Final = "influence_"
"""An icon raising one printed Faction's Influence: ``influence_<faction>``
(In The Shadows' "[Bene Gesserit Influence]")."""
DEPLOY_ICON: Final = "deploy"
"""Treachery's "[troop] [troop] Deploy these troops to the Conflict.": troops
from the supply to the Conflict, one icon for the printed sentence."""
_FRAME: Final = "Unload frame"

type UnloadIcon = tuple[str, int]
"""One icon of an Unload box: the resource it gains and how many."""

_UNMET_KEY: Final = "unmet"
"""The ``card_unloaded`` payload's icons whose condition failed as the card
was discarded or trashed (comma-joined, only when there are any)."""


@dataclass(frozen=True, slots=True)
class _BoxIcon:
    """One icon of an Unload box and the condition of its printed line."""

    name: str
    amount: int
    condition: Condition | None


@cache
def _box(definition_id: str) -> tuple[_BoxIcon, ...]:
    entry = IMPERIUM_CARDS_BY_ID[definition_id]
    if entry.reveal_persuasion or entry.reveal_strength or entry.reveal_choice_effects:
        raise NotImplementedError(
            f"{definition_id}: an Unload box with Persuasion, swords or a choice"
        )
    ability = REVEAL_GAIN_ABILITIES.get(definition_id)
    if ability is None:
        raise ValueError(f"{definition_id} is marked Unload but has no Reveal box")
    icons: list[_BoxIcon] = []
    for line in ability.sections:
        if line.costs:
            raise NotImplementedError(
                f"{definition_id}: an Unload box line with a cost"
            )
        if isinstance(line.condition, FactionBond | CommandReached):
            # A Bond reads the cards in play and Command the Reveal's
            # Persuasion: neither is the owner's seat alone.
            raise NotImplementedError(
                f"{definition_id}: an Unload box condition {line.condition!r}"
            )
        for reward in line.rewards:
            if isinstance(reward, DeployFromSupply):
                icons.append(_BoxIcon(DEPLOY_ICON, reward.count, line.condition))
                continue
            if _one_faction(reward) is not None:
                assert isinstance(reward, GainInfluence) and reward.factions
                icons.append(
                    _BoxIcon(
                        f"{INFLUENCE_ICON_PREFIX}{reward.factions[0].value}",
                        reward.times,
                        line.condition,
                    )
                )
                continue
            if not isinstance(reward, GainResources):
                raise NotImplementedError(
                    f"{definition_id}: an Unload box icon {reward!r} is not wired"
                )
            icons.extend(
                _BoxIcon(name, getattr(reward, name), line.condition)
                for name in _RESOURCES
                if getattr(reward, name)
            )
    names = [icon.name for icon in icons]
    if len(set(names)) != len(names):
        raise NotImplementedError(f"{definition_id}: an Unload box icon twice")
    return tuple(icons)


def _one_faction(reward: object) -> Faction | None:
    """The one printed Faction an Influence icon raises, or None for any
    other piece (a chosen or the visited Faction's is not wired)."""

    if (
        not isinstance(reward, GainInfluence)
        or reward.requires_choice
        or reward.visited_space
        or reward.factions is None
        or len(reward.factions) != 1
    ):
        return None
    return reward.factions[0]


def _unload_box(card_id: str) -> tuple[_BoxIcon, ...]:
    if not card_id.startswith("imperium:"):
        return ()
    entry = imperium_card_for_instance(card_id)
    if not entry.unload:
        return ()
    return _box(entry.card.card_id)


def unload_icons(card_id: str) -> tuple[UnloadIcon, ...]:
    """The icons the personal card ``card_id`` may give when discarded or
    trashed: its Reveal box's when it is marked Unload, else none (each
    conditioned icon too; the catalog names a row for every one)."""

    return tuple((icon.name, icon.amount) for icon in _unload_box(card_id))


def _unmet(state: GameState, player: int, card_id: str) -> tuple[str, ...]:
    """The icons of ``card_id``'s box whose condition fails for ``player``
    now, as the card is discarded or trashed."""

    owner = state.players[player]
    unmet: list[str] = []
    for icon in _unload_box(card_id):
        if icon.condition is None:
            continue
        held = owner_condition_holds(owner, icon.condition)
        if held is None:
            raise TypeError(f"{icon.condition!r} is no Unload box condition")
        if not held:
            unmet.append(icon.name)
    return tuple(unmet)


def _gain(
    state: GameState, player: int, name: str, amount: int, *, source: str
) -> RuleResult:
    """Pay one icon of an Unload box: a resource, a printed Faction's
    Influence (gained on its track as any Influence is; at the top nothing
    is gained, OQ-060), or troops deployed from the supply. ``source`` names
    the icon's events."""

    if name == DEPLOY_ICON:
        # "Deploy these troops to the Conflict" -- also outside its owner's
        # turn: during Combat they go to the Conflict and back to the supply
        # with the others at the next step (OQ-127), and a supply short of
        # them records the rest as Double Cross's does (OQ-042 (2)).
        # Imported here: the Tech module imports the card discard and trash,
        # which import this one.
        from dune_imperium.rules.tech import deploy_troops_from_supply

        return deploy_troops_from_supply(state, player, amount, source=source)
    if name.startswith(INFLUENCE_ICON_PREFIX):
        faction = Faction(name.removeprefix(INFLUENCE_ICON_PREFIX))
        return gain_faction_influence(
            state, player, faction, amount, event_prefix=source
        )
    owner = state.players[player]
    gained = replace(
        owner,
        resources=replace(
            owner.resources,
            **{name: getattr(owner.resources, name) + amount},
        ),
    )
    return RuleResult(
        state=replace(state, players=replace_player(state.players, gained)),
        events=(resources_gained_event(source, player, **{name: amount}),),
    )


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
    unmet = _unmet(state, player, card_id)
    events = [
        GameEvent(
            event_id=unload_source,
            kind="card_unloaded",
            payload=(
                ("card_id", card_id),
                ("pending", not at_once),
                ("player", player),
                *(((_UNMET_KEY, ",".join(unmet)),) if unmet else ()),
            ),
        )
    ]
    if at_once:
        for name, amount in icons:
            if name in unmet:
                continue
            paid = _gain(state, player, name, amount, source=f"{unload_source}:{name}")
            state = paid.state
            events.extend(paid.events)
    return RuleResult(state=state, events=tuple(events))


def _value(card_id: str, name: str) -> str:
    return f"{card_id}|{name}"


def _owe(
    state: GameState,
    player: int,
    card_id: str,
    source: str,
    unmet: tuple[str, ...] = (),
) -> GameState:
    """The icons of an Unload an effect triggered, but those ``unmet``:
    rows of the owner's own turn, else a window of their own."""

    values = tuple(
        _value(card_id, name) for name, _ in unload_icons(card_id) if name not in unmet
    )
    if not values:
        return state
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
        unmet = payload.get(_UNMET_KEY, "")
        assert isinstance(player, int) and isinstance(card_id, str)
        assert isinstance(unmet, str)
        state = _owe(
            state,
            player,
            card_id,
            event.event_id,
            tuple(unmet.split(",") if unmet else ()),
        )
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
    return _gain(state, player, name, amount, source=f"{source}:{name}")
