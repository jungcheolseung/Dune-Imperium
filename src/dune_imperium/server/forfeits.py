"""What a step would make its own seat lose of the effects it has not used.

User request 2026-10-31, after a real game: seat 2 grafted Show of Strength
to Dissecting Kit at Arrakeen and took Dissecting Kit's "trash the other
grafted card" first. "You can't receive or activate an effect from a card
that is already trashed" (OQ-022, designer ruling;
``agent_effects.expire_trashed_card_effects``), so Show of Strength's
unused draw was lost, and Arrakeen's draw that followed sealed the undo.
The row did carry a mark, but a small one that named neither the card nor
what it would lose ("이번 차례에 낸 카드 · 폐기하면 에이전트 칸의 남은 효과
사라짐", from ``turn_cards``' old trash-row dry runs), and only for a fixed
list of trash rows. Now every row the seat is served says, from the dry
run it already gets (``sessions._dry_run_fields``), which of the seat's
cards it would cost an unused effect and what that effect is:

- an Agent box of the open Agent turn the step expires: the engine's
  ``agent_card_effect_expired`` / ``leader_signet_expired`` for the seat --
  the played card or its graft partner trashed by another effect (the other
  box, an Intrigue card, a board space, Research, a Tech tile), a Ghola
  copying a box, Urgent Shigawire's draw added to a box, an optional trash
  a box left waiting on the turn;
- such a box the step leaves to expire as soon as the frame it pushed
  closes (Arrakis Planetologist's trash while its Intrigue card still waits
  in the same frame, ``box_doomed``);
- a Reveal choice still pending whose card the step trashes: the choice
  then offers nothing and lapses when the Reveal ends (OQ-022, its
  2026-09-07 addition; ``reveal_turn._available_pending_choices``).

A card that leaves play by its own printed effect keeps what is left
(OQ-022: "카드가 자기 효과로 자신을 trash하는 경우 인쇄된 이득은 정상 지급"),
and the engine expires nothing then, so nothing is said either. A Row card
borrowed with Usurp is never a trash target before its turn ends (OQ-054);
what it has not used lapses with the turn's end, like every unused optional
effect (OQ-095 (2)).

Every fact here is public: the cards lie face up in play, their printed
boxes are on their faces, and the engine announces each expiry to every
seat. The forfeits ride on the acting seat's own rows only, and nothing
here reaches ``PlayerView``, the AI observation, the codec or the engine.
"""

import logging
from collections.abc import Mapping
from typing import Final

from dune_imperium.content.core.cards import PersonalCardDefinition
from dune_imperium.content.registry.card_abilities import card_agent_box
from dune_imperium.content.registry.personal_cards import personal_card_for_instance
from dune_imperium.core.actions import ActionValue
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.display.actions import (
    agent_box_texts,
    agent_card_icon_text,
    agent_card_icon_text_ko,
    personal_card_names,
    reveal_choice_text,
)
from dune_imperium.rules.effects import borrowed_agent_card, pending_boost_draws
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.reveal_turn import pending_reveal_choices
from dune_imperium.server.persistence import JsonObject, JsonValue
from dune_imperium.server.turn_cards import TURN_CARD_KEYS, trash_waits, turn_cards

_LOGGER = logging.getLogger(__name__)

# The Signet Ring box logs its own kinds (cleanup-2c-4).
EXPIRED_KINDS: Final = frozenset(
    {"agent_card_effect_expired", "leader_signet_expired"}
)

# Each box key of the effect frame and its queued icons (OQ-027).
_PENDING_ICON_KEYS: Final = {
    "card_id": "pending_agent_icons",
    "graft_card_id": "graft_pending_icons",
}

# Icons ``agent_card_icon_text`` does not word: an optional trash a box
# left waiting on the turn (cleanup-2b), named by its printed icon.
_ICON_TEXT: Final = {"trash": ("Trash", "{trash}")}

# Urgent Shigawire's draw "added to its Agent box" [Urgent Shigawire card]
# expires under its own unit name (``agent_effects._BOOST_UNIT``).
_BOOST_TEXT: Final = ("Draw 1 card", "{draw:1}")


def forfeited_effects(
    before: GameState, seat: int, outcome: RuleResult | None
) -> list[JsonValue] | None:
    """``_forfeited_effects``, or None if it fails: a warning is display
    only, and an unexpected engine state must not fail a whole listing."""

    try:
        return _forfeited_effects(before, seat, outcome)
    except Exception:
        _LOGGER.exception("could not read what a step of seat %s forfeits", seat)
        return None


def _forfeited_effects(
    before: GameState, seat: int, outcome: RuleResult | None
) -> list[JsonValue] | None:
    """The cards of ``seat`` whose unused effects the step loses, each as
    ``{card_id, kind, name, name_ko, effects, effects_ko}``; None when it
    loses none. ``kind`` is "agent" for an Agent box, "reveal" for a Reveal
    choice; ``effects`` are the lost effects in English and ``effects_ko``
    their Korean twins with ``{term}`` tokens (the button texts' grammar),
    one per icon a box still had queued, or the whole printed box for a box
    that resolves as one, then Urgent Shigawire's draw added to it and an
    optional trash it left waiting on the turn."""

    if outcome is None:
        return None
    lost: dict[str, list[tuple[str, str]]] = {}
    kinds: dict[str, str] = {}
    for card_id, texts in _expired_boxes(before, seat, outcome.events):
        lost.setdefault(card_id, []).extend(texts)
        kinds[card_id] = "agent"
    _, pending = turn_cards(before)
    owned = before.players[seat].in_play
    for card_id in pending:
        if card_id in lost or card_id not in owned:
            continue
        if box_doomed(outcome.state, card_id):
            lost[card_id] = _remaining_effects(before, card_id)
            kinds[card_id] = "agent"
    for card_id, texts in _lapsing_reveal_choices(before, seat, outcome.state):
        lost.setdefault(card_id, []).extend(texts)
        kinds[card_id] = "reveal"
    if not lost:
        return None
    forfeits: list[JsonValue] = []
    for card_id, texts in lost.items():
        name, name_ko = personal_card_names(card_id)
        unique = list(dict.fromkeys(texts))
        entry: JsonObject = {
            "card_id": card_id,
            "kind": kinds[card_id],
            "name": name,
            "name_ko": name_ko,
            "effects": [text for text, _ in unique],
            "effects_ko": [text_ko for _, text_ko in unique],
        }
        forfeits.append(entry)
    return forfeits


def _expired_boxes(
    before: GameState, seat: int, events: tuple[GameEvent, ...]
) -> list[tuple[str, list[tuple[str, str]]]]:
    """Each Agent box the step's own events expire for ``seat``, with what
    it still had: one event per icon it had queued, or one for a box that
    resolves as one action (``agent_effects._box_events``)."""

    found: list[tuple[str, list[tuple[str, str]]]] = []
    for event in events:
        if event.kind not in EXPIRED_KINDS:
            continue
        payload = dict(event.payload)
        card_id = payload.get("card_id")
        if payload.get("player") != seat or not isinstance(card_id, str):
            continue
        effect = payload.get("effect")
        if ":boost:" in event.event_id:
            found.append((card_id, [_BOOST_TEXT]))
        elif isinstance(effect, str) and (text := _icon_text(before, card_id, effect)):
            found.append((card_id, [text]))
        else:
            found.append((card_id, _whole_box(before, card_id)))
    return found


def _icon_text(before: GameState, card_id: str, icon: str) -> tuple[str, str] | None:
    """One queued icon of ``card_id``'s box, worded as its button is."""

    if icon in _ICON_TEXT:
        return _ICON_TEXT[icon]
    definition = _box_definition(before, card_id)
    effect = card_agent_box(definition) if definition is not None else None
    try:
        return agent_card_icon_text(effect, icon), agent_card_icon_text_ko(effect, icon)
    except KeyError:
        return None


def _whole_box(before: GameState, card_id: str) -> list[tuple[str, str]]:
    """What ``card_id``'s box still had before the step: its queued icons,
    or its whole printed box when it resolves as one action; nothing when
    the box has no words (the card is still named)."""

    context = _box_context(before, card_id)
    if context is not None:
        key = "card_id" if context.get("card_id") == card_id else "graft_card_id"
        queued = context.get(_PENDING_ICON_KEYS[key], "")
        icons = [icon for icon in str(queued).split(",") if icon]
        texts = [text for icon in icons if (text := _icon_text(before, card_id, icon))]
        if icons and len(texts) == len(icons):
            return texts
    definition = _box_definition(before, card_id)
    whole = agent_box_texts(definition) if definition is not None else None
    return [whole] if whole is not None else []


def _remaining_effects(before: GameState, card_id: str) -> list[tuple[str, str]]:
    """Everything ``card_id`` still had waiting before the step, for a box the
    step leaves to expire once the frame above closes (``box_doomed``): its
    box while it waits (``_whole_box``), Urgent Shigawire's draw "added to
    its Agent box" [Urgent Shigawire card], and an optional trash its box
    left waiting on the turn (cleanup-2b) -- the same three the expiry hook
    ends (``agent_effects.expire_trashed_card_effects``; 2026-10-31 review:
    a boosted Truthtrance, its own box done, named nothing)."""

    found = _box_frame(before, card_id)
    if found is None:
        return _whole_box(before, card_id)
    frame, context = found
    texts: list[tuple[str, str]] = []
    for card_key, pending_key, _ in TURN_CARD_KEYS:
        if context.get(card_key) == card_id and context.get(pending_key) is True:
            texts.extend(_whole_box(before, card_id))
    if card_id in pending_boost_draws(context):
        texts.append(_BOOST_TEXT)
    owner = context.get("turn_owner")
    if (
        isinstance(owner, int)
        and not isinstance(owner, bool)
        and trash_waits(before, frame, owner, card_id)
    ):
        texts.append(_ICON_TEXT["trash"])
    return texts


def _box_frame(
    state: GameState, card_id: str
) -> tuple[DecisionFrame, Mapping[str, ActionValue]] | None:
    """The open Agent-turn effect frame holding ``card_id``'s box, with its
    context."""

    for frame in reversed(state.decision_stack):
        if frame.kind != FrameKind.AGENT_EFFECTS or not isinstance(
            frame.decision, PlayerDecision
        ):
            continue
        context = dict(frame.context)
        if card_id in (context.get("card_id"), context.get("graft_card_id")):
            return frame, context
    return None


def _box_context(state: GameState, card_id: str) -> Mapping[str, ActionValue] | None:
    """The open Agent-turn effect frame's context holding ``card_id``'s box."""

    found = _box_frame(state, card_id)
    return found[1] if found is not None else None


def _box_definition(state: GameState, card_id: str) -> PersonalCardDefinition | None:
    """The definition whose box ``card_id`` resolves: a Ghola's borrowed one
    (``effects.borrowed_agent_card``), else the card's own."""

    context = _box_context(state, card_id)
    partner = ""
    if context is not None:
        other = (
            context.get("graft_card_id")
            if context.get("card_id") == card_id
            else context.get("card_id")
        )
        partner = other if isinstance(other, str) else ""
    try:
        return borrowed_agent_card(personal_card_for_instance(card_id), partner)
    except (KeyError, ValueError):
        return None


def box_doomed(state: GameState, card_id: str) -> bool:
    """Whether ``card_id`` left its owner's zones with its box still
    pending and not by its own effect: the test
    ``expire_trashed_card_effects`` applies once the effect frame is back
    on top."""

    for frame in state.decision_stack:
        if frame.kind != FrameKind.AGENT_EFFECTS:
            continue
        context = dict(frame.context)
        owner = context.get("turn_owner")
        if isinstance(owner, bool) or not isinstance(owner, int):
            continue
        player = state.players[owner]
        if card_id in (*player.hand, *player.discard_pile, *player.in_play):
            return False
        for card_key, pending_key, self_key in TURN_CARD_KEYS:
            if context.get(card_key) != card_id or context.get(self_key) is True:
                continue
            if context.get(pending_key) is True:
                return True
            if card_id in pending_boost_draws(context):
                return True
            if trash_waits(state, frame, owner, card_id):
                return True
    return False


def _lapsing_reveal_choices(
    before: GameState, seat: int, after: GameState
) -> list[tuple[str, list[tuple[str, str]]]]:
    """The pending Reveal choices of ``seat`` whose card the step takes out
    of play while the Reveal goes on: each then offers nothing and lapses
    at the Reveal's end (OQ-022). A card that trashes itself through its own
    choice uses that entry up as it opens, so it is no longer pending."""

    entries_before = _reveal_choices(before, seat)
    if not entries_before:
        return []
    entries_after = set(_reveal_choices(after, seat))
    in_play_before = before.players[seat].in_play
    in_play_after = after.players[seat].in_play
    lost: list[tuple[str, list[tuple[str, str]]]] = []
    for card_id, effect in entries_before:
        if (
            (card_id, effect) in entries_after
            and card_id in in_play_before
            and card_id not in in_play_after
        ):
            try:
                text = reveal_choice_text(effect)
            except ValueError:
                text = None
            lost.append((card_id, [text] if text is not None else []))
    return lost


def _reveal_choices(state: GameState, seat: int) -> tuple[tuple[str, str], ...]:
    """The pending choices of ``seat``'s Reveal frame, wherever it sits on
    the stack (a trash may push a frame of its own above it)."""

    for frame in reversed(state.decision_stack):
        if (
            frame.kind == FrameKind.REVEAL
            and isinstance(frame.decision, PlayerDecision)
            and frame.decision.owner == seat
        ):
            return pending_reveal_choices(dict(frame.context))
    return ()


# The steps whose press ends a turn and lapses what it left unused: every
# optional effect still waiting on the turn's frame "does not block the
# turn's end, has no refusal, and the press lapses it" (OQ-095 (2); the
# Reveal's choices, its 2026-10-14 addition).
LAPSING_TURN_ENDS: Final = frozenset({"finish_agent_turn", "finish_reveal"})


def lapsed_effects(seat: int, outcome: RuleResult | None) -> list[JsonValue] | None:
    """The public ``*_lapsed`` events of ``seat`` a turn end's dry run
    logs, as ``{kind, payload}`` for the page to word as its log does; None
    when nothing lapses. A Contract icon that fizzles has its own warning
    (``sessions.shortfall_warning``, OQ-059)."""

    if outcome is None:
        return None
    lapsed: list[JsonValue] = []
    for event in outcome.events:
        payload = dict(event.payload)
        if (
            event.kind.endswith("_lapsed")
            and event.visible_to is None
            and payload.get("player") == seat
        ):
            lapsed.append({"kind": event.kind, "payload": _json_payload(payload)})
    return lapsed or None


def _json_payload(payload: Mapping[str, object]) -> JsonObject:
    """An event payload's scalars, as the log serializes them."""

    return {
        key: value
        for key, value in payload.items()
        if value is None or isinstance(value, bool | int | float | str)
    }
