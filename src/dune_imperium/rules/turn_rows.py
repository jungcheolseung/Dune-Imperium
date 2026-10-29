"""Effects that wait on the owner's own turn as rows (composed-effects cleanup-2b).

User decision 2026-10-17 (docs/composed-effects-plan.md 5, "정한 규칙 판단" 2;
OQ-095 (2), whose exception "(d) 차례 위에 따로 열리는 창" it narrows): a
research space's bonus choice (c6r6, c7r3, c8r6) and an optional "[trash a
card]" icon raised inside its owner's own Agent or Reveal turn no longer open
a window of their own. Each waits on the turn's frame -- the turn frame, the
Agent-turn effect frame or the Reveal frame -- and is offered there as rows
beside the turn's others, with no refusal: "may", an arrow cost or a black
trash icon is optional [FAQ p. 3], and an optional effect "holds no turn end
back and offers no refusal; the press lapses it" (OQ-095 (2), user ruling
2026-10-14). Unused, it lapses at the turn-end press (``finish_agent_turn``,
``finish_reveal``) with an event; c6r6's mandatory "Influence with any
Faction" holds the end back while a Faction can rise, and waits, then lapses,
like an Agent box's Influence with every cube at the top (OQ-057 (1)).
Arrakis Planetologist's Intrigue card, which shared its replacement's trash
window (OQ-106), waits beside that trash as a mandatory step of its own and
holds the end until drawn, and so does each icon of a research space's pair
(specimen and trash, specimen and Tleilaxu), resolved in the owner's order
(rule decision 5, OQ-027). Outside the owner's turn -- Combat, the Arrakeen
Scouts step, and a Scouts line run inside the turn, which keeps the module's
own windows -- the effect still opens its window. An acquired Imperium
card's acquire box of several icons, or of a chosen Faction's Influence,
waits the same way, a row per icon (``ACQUIRE_ICON``, OQ-141); outside the
turn it has no window yet (``rules.acquire_icons``).

The waiting effects live in the turn frame's context (``PENDING_KEY``), as the
Tech tiles' acquire icons do (``TECH_ACQUIRE_PENDING_KEY``, OQ-098), and move
with the turn frame to the Agent-turn effect or Reveal frame that replaces it
(``carried``).
"""

import json
from collections.abc import Mapping
from copy import replace
from functools import cache
from typing import Final

from dune_imperium.content.immortality.board import ResearchBonus
from dune_imperium.content.uprising.board import Faction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.observation import SHIPPING_REWARD_ROW, TURN_ROWS_KEY
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import (
    TECH_ACQUIRE_PENDING_KEY,
    FrameKind,
    frame_context,
    own_turn_frame_index,
    with_context,
)
from dune_imperium.rules.influence import influence_can_rise

PENDING_KEY: Final = TURN_ROWS_KEY
"""The turn frame's waiting effects: a JSON list of ``[kind, source, value]``."""

RESEARCH_BONUS: Final = "research_bonus"
"""A research space's bonus choice; ``value`` is its ``ResearchBonus``."""

OPTIONAL_TRASH: Final = "optional_trash"
"""An optional "[trash a card]" icon (``rules.optional_trash``); ``value``
is the entity that printed it (``optional_trash.trash_printer``, stage
B3c-2b)."""

PLANETOLOGIST_INTRIGUE: Final = "planetologist_intrigue"
"""Arrakis Planetologist's Intrigue card of one replaced sandworm; no value."""

RESEARCH_ICON: Final = "research_icon"
"""One icon of a research space's pair (``value``: ``specimen`` or
``tleilaxu``), each resolved on its own in the owner's order (rule decision
5, OQ-027); mandatory."""

CONTRACT_ICON: Final = "contract_icon"
"""One icon of a Contract its owner completed in its own turn (OQ-112 (4),
stage B3b): ``value`` is ``"<contract instance>|<icon>"``; a Recall Agent
icon judges what it may not take when it is taken (``rules.contracts``);
mandatory."""

ACQUIRE_ICON: Final = "acquire_icon"
"""One icon of an Imperium card's acquire box, taken in its owner's own turn
(OQ-141, the original game's CHOAM Directorship and Lady Jessica): ``value``
is ``"<card id>|<icon>"`` (``rules.acquire_icons``). A fixed Faction's icon is
mandatory; the chosen-Faction icon is too while a Faction can rise, and with
every cube at the top it waits and the press lapses it (OQ-060, OQ-057 (1))."""

SHIPPING_REWARD: Final = SHIPPING_REWARD_ROW
"""One reward of a Shipping track recall the owner took in its own turn (Rise
of Ix, stage P4c-3, ``rules.shipping_track``): ``value`` is the Shipping space
whose reward it is (``"1"``, ``"2:recruit"``, ``"2:influence"``, ``"3"``:
space 2 prints two rewards, each its own, OQ-148). All but space 3's are
mandatory; its Acquire Tech is "may" ([Rise of Ix p. 4]), so it holds no turn
end back and the press lapses it (OQ-095 (2))."""

CHOSEN_INFLUENCE_ICON: Final = "influence_any"
"""The acquire icon ``value`` of an Influence with a Faction of the owner's
choice."""

type Pending = tuple[str, str, str]

_TURN_KINDS: Final = (FrameKind.TURN, FrameKind.AGENT_EFFECTS, FrameKind.REVEAL)
# A Scouts line run inside the owner's turn keeps the module's own windows.
_SCOUTS_KINDS: Final = frozenset(
    kind for kind in FrameKind if kind.value.startswith("scouts_")
)


def pending(frame: DecisionFrame) -> tuple[Pending, ...]:
    """The effects waiting on ``frame``, oldest first.

    Asked by several providers at every decision of a turn, so it reads the
    context pairs without building a dict and parses each value once.
    """

    for key, value in frame.context:
        if key != PENDING_KEY:
            continue
        if not isinstance(value, str):
            raise RuntimeError("the turn's waiting effects must be a string")
        return _parsed(value) if value else ()
    return ()


@cache
def _parsed(value: str) -> tuple[Pending, ...]:
    return tuple(
        (str(kind), str(source), str(item)) for kind, source, item in json.loads(value)
    )


def _with_pending(frame: DecisionFrame, items: tuple[Pending, ...]) -> DecisionFrame:
    context = frame_context(frame)
    if items:
        context[PENDING_KEY] = json.dumps([list(item) for item in items])
    else:
        context.pop(PENDING_KEY, None)
    return with_context(frame, context)


def _replace_frame(state: GameState, index: int, frame: DecisionFrame) -> GameState:
    return replace(
        state,
        decision_stack=(
            *state.decision_stack[:index],
            frame,
            *state.decision_stack[index + 1 :],
        ),
    )


def waits_on_turn(state: GameState, player: int) -> bool:
    """Whether an effect of ``player``'s would wait on its own open turn
    frame (``queue``) rather than open its own window: inside the seat's own
    turn and not in a Scouts line run in it -- a line's frame anywhere above
    the turn frame, also under a frame the line opened (its Contract market,
    its Research direction)."""

    index = own_turn_frame_index(state, player)
    return index is not None and not any(
        frame.kind in _SCOUTS_KINDS for frame in state.decision_stack[index + 1 :]
    )


def queue(state: GameState, player: int, item: Pending) -> GameState | None:
    """Put ``item`` on ``player``'s own open turn frame, or return None
    where it opens its own window instead: outside the seat's own turn, or
    inside a Scouts line run in it."""

    if not waits_on_turn(state, player):
        return None
    index = own_turn_frame_index(state, player)
    assert index is not None
    frame = state.decision_stack[index]
    return _replace_frame(state, index, _with_pending(frame, (*pending(frame), item)))


def rows_frame(state: GameState, player: int) -> DecisionFrame | None:
    """``player``'s own turn frame when it is on top, where its waiting
    effects are offered."""

    if not state.decision_stack:
        return None
    frame = state.decision_stack[-1]
    if (
        frame.kind not in _TURN_KINDS
        or not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
    ):
        return None
    return frame


def take(state: GameState, player: int, item: Pending) -> GameState:
    """Remove ``item`` from the top turn frame (its row is being taken)."""

    frame = rows_frame(state, player)
    if frame is None or item not in pending(frame):
        raise ValueError("the effect is not waiting on the owner's turn")
    items = list(pending(frame))
    items.remove(item)
    return _replace_frame(
        state, len(state.decision_stack) - 1, _with_pending(frame, tuple(items))
    )


def take_newest(state: GameState, player: int, kind: str) -> tuple[GameState, str]:
    """Remove the newest waiting effect of ``kind`` from the top turn frame
    and return its source: the one its window, stacked last, used to answer
    first."""

    frame = rows_frame(state, player)
    if frame is None:
        raise ValueError("the owner's turn frame is not on top")
    item = next((item for item in reversed(pending(frame)) if item[0] == kind), None)
    if item is None:
        raise ValueError(f"no {kind} waits on the owner's turn")
    return take(state, player, item), item[1]


def acquire_icon_blocked(value: str, owner: PlayerState) -> bool:
    """Whether an acquire icon ``value`` (``"<card id>|<icon>"``) is the
    chosen Faction's Influence with every Faction at the top, where it offers
    no row (OQ-060): it waits, greyed out, and the press lapses it."""

    _card_id, icon = value.split("|")
    return icon == CHOSEN_INFLUENCE_ICON and not any(
        influence_can_rise(owner, faction) for faction in Faction
    )


def holds_the_end(state: GameState, player: int) -> bool:
    """Whether a waiting effect still offers a mandatory row: c6r6 with a
    Faction it can raise ("획득은 의무다", OQ-060 2026-09-30 addition),
    Arrakis Planetologist's Intrigue card, a research pair's icon, a
    completed Contract's icon (OQ-112 (4)), or an acquire box's icon that
    offers a row (OQ-141). Read from public facts only (the frame's context,
    the seat's Influence), so the server's turn-end mirror may ask it too."""

    frame = rows_frame(state, player)
    if frame is None:
        return False
    owner = state.players[player]
    return any(
        kind in (PLANETOLOGIST_INTRIGUE, RESEARCH_ICON, CONTRACT_ICON)
        or (kind == SHIPPING_REWARD and value != _OPTIONAL_SHIPPING_REWARD)
        or (
            kind == RESEARCH_BONUS
            and ResearchBonus(value) is ResearchBonus.INFLUENCE_ANY
            and any(influence_can_rise(owner, faction) for faction in Faction)
        )
        or (kind == ACQUIRE_ICON and not acquire_icon_blocked(value, owner))
        for kind, _source, value in pending(frame)
    )


_OPTIONAL_SHIPPING_REWARD: Final = "3"


def _tech_acquire_keys(context: Mapping[str, object]) -> tuple[str, ...]:
    value = context.get(TECH_ACQUIRE_PENDING_KEY, "")
    if not value:
        return ()
    if not isinstance(value, str):
        raise RuntimeError("Tech acquire effects must be a string")
    return tuple(key for key in value.split(",") if key)


def tech_influence_blocked(key: str, owner: PlayerState) -> bool:
    """Whether an owed Tech acquire icon ``key`` (``<tech_id>:<effect>``) is
    an "Influence with any Faction" (Glowglobes, Navigation Chamber; Shuttle
    Fleet's two) with every Faction at the top, where it offers none (OQ-060;
    user decision 2026-10-17, composed-effects plan 5, rule decision 1)."""

    _tech_id, effect = key.split(":")
    return effect in ("influence", "distinct_influence") and not any(
        influence_can_rise(owner, faction) for faction in Faction
    )


def tech_acquire_effects_hold_the_end(
    context: Mapping[str, object], owner: PlayerState
) -> bool:
    """Whether a Tech tile's owed acquire icon still holds the turn's end
    (OQ-098): any of them that offers a row. A blocked Influence
    (``tech_influence_blocked``) waits, greyed out, and the press lapses it,
    like an Agent box's Influence with every cube at the top (OQ-057 (1))."""

    return any(
        not tech_influence_blocked(key, owner) for key in _tech_acquire_keys(context)
    )


def tech_influence_lapsed(player: int, round_number: int, key: str) -> GameEvent:
    """The event of a blocked Tech acquire Influence that lapses."""

    tech_id, effect = key.split(":")
    return GameEvent(
        event_id=(
            f"round:{round_number}:player:{player}:tech:{tech_id}:acquire:"
            f"{effect}:lapsed"
        ),
        kind="tech_acquire_effect_lapsed",
        payload=(("effect", effect), ("player", player), ("tech_id", tech_id)),
    )


def _lapsed(player: int, item: Pending) -> GameEvent:
    kind, source, value = item
    if kind == RESEARCH_BONUS:
        return GameEvent(
            event_id=f"{source}:bonus_lapsed",
            kind="research_bonus_lapsed",
            payload=(("bonus", value), ("player", player)),
        )
    if kind == OPTIONAL_TRASH:
        return GameEvent(
            event_id=f"{source}:trash_lapsed",
            kind="optional_trash_lapsed",
            payload=(("player", player),),
        )
    if kind == ACQUIRE_ICON:
        # Only the chosen Influence with every Faction at the top reaches the
        # press (``holds_the_end``).
        card_id, icon = value.split("|")
        return GameEvent(
            event_id=f"{source}:{icon}_lapsed",
            kind="acquire_icon_lapsed",
            payload=(("card_id", card_id), ("effect", icon), ("player", player)),
        )
    if kind == SHIPPING_REWARD:
        # Only space 3's Acquire Tech reaches the press (``holds_the_end``).
        return GameEvent(
            event_id=f"{source}:shipping_reward_lapsed",
            kind="shipping_reward_lapsed",
            payload=(("player", player), ("space", int(value.split(":")[0]))),
        )
    # Arrakis Planetologist's Intrigue card and a research space's icon hold
    # the end (``holds_the_end``).
    raise RuntimeError(f"a mandatory {kind} waits at the turn-end press")


def lapse(state: GameState, player: int) -> RuleResult:
    """At the turn-end press: every waiting effect lapses, with an event,
    and so does a Tech acquire Influence that could only lapse (the others
    hold the end, ``tech_acquire_effects_hold_the_end``)."""

    frame = rows_frame(state, player)
    if frame is None:
        return RuleResult(state=state)
    tech_keys = _tech_acquire_keys(dict(frame.context))
    if not pending(frame) and not tech_keys:
        return RuleResult(state=state)
    owner = state.players[player]
    if any(not tech_influence_blocked(key, owner) for key in tech_keys):
        raise RuntimeError("an owed Tech acquire icon waits at the turn-end press")
    events = (
        *(_lapsed(player, item) for item in pending(frame)),
        *(tech_influence_lapsed(player, state.round_number, key) for key in tech_keys),
    )
    context = frame_context(_with_pending(frame, ()))
    context.pop(TECH_ACQUIRE_PENDING_KEY, None)
    cleared = _replace_frame(
        state, len(state.decision_stack) - 1, with_context(frame, context)
    )
    return RuleResult(state=cleared, events=events)


def carried(turn_context: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
    """The waiting effects a turn frame hands the Agent-turn effect or
    Reveal frame that replaces it."""

    value = turn_context.get(PENDING_KEY)
    return ((PENDING_KEY, value),) if isinstance(value, str) and value else ()
