"""Effects that wait on the owner's own turn as rows (composed-effects cleanup-2b).

User decision 2026-10-17 (docs/composed-effects-plan.md 5, "정한 규칙 판단" 2;
OQ-095 (2), whose exception "(d) 차례 위에 따로 열리는 창" it narrows): a
research space's bonus choice (c6r6, c7r3, c8r6) raised inside its owner's own
Agent or Reveal turn no longer opens a window of its own. It waits on the
turn's frame -- the turn frame, the Agent-turn effect frame or the Reveal
frame -- and is offered there as rows beside the turn's others, with no
refusal: "may", an arrow cost or a black trash icon is optional [FAQ p. 3],
and an optional effect "holds no turn end back and offers no refusal; the
press lapses it" (OQ-095 (2), user ruling 2026-10-14). Unused, it lapses at
the turn-end press (``finish_agent_turn``, ``finish_reveal``) with an event;
c6r6's mandatory "Influence with any Faction" holds the end back while a
Faction can rise, and waits, then lapses, like an Agent box's Influence with
every cube at the top (OQ-057 (1)). Outside the owner's turn -- Combat, the
Arrakeen Scouts step, and a Scouts line run inside the turn, which keeps the
module's own windows -- the effect still opens its window.

The waiting effects live in the turn frame's context (``PENDING_KEY``), as the
Tech tiles' acquire icons do (``TECH_ACQUIRE_PENDING_KEY``, OQ-098), and move
with the turn frame to the Agent-turn effect or Reveal frame that replaces it
(``carried``).
"""

import json
from collections.abc import Mapping
from copy import replace
from typing import Final

from dune_imperium.content.immortality.board import ResearchBonus
from dune_imperium.content.uprising.board import Faction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import (
    FrameKind,
    frame_context,
    own_turn_frame_index,
    with_context,
)
from dune_imperium.rules.influence import influence_can_rise

PENDING_KEY: Final = "pending_turn_rows"
"""The turn frame's waiting effects: a JSON list of ``[kind, source, value]``."""

RESEARCH_BONUS: Final = "research_bonus"
"""A research space's bonus choice; ``value`` is its ``ResearchBonus``."""

type Pending = tuple[str, str, str]

_TURN_KINDS: Final = (FrameKind.TURN, FrameKind.AGENT_EFFECTS, FrameKind.REVEAL)
# A Scouts line run inside the owner's turn keeps the module's own windows.
_SCOUTS_KINDS: Final = frozenset(
    kind for kind in FrameKind if kind.value.startswith("scouts_")
)


def pending(frame: DecisionFrame) -> tuple[Pending, ...]:
    """The effects waiting on ``frame``, oldest first."""

    value = dict(frame.context).get(PENDING_KEY, "")
    if not isinstance(value, str):
        raise RuntimeError("the turn's waiting effects must be a string")
    if not value:
        return ()
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


def queue(state: GameState, player: int, item: Pending) -> GameState | None:
    """Put ``item`` on ``player``'s own open turn frame, or return None
    where it opens its own window instead: outside the seat's own turn, or
    inside a Scouts line run in it."""

    index = own_turn_frame_index(state, player)
    if index is None or state.decision_stack[-1].kind in _SCOUTS_KINDS:
        return None
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


def holds_the_end(state: GameState, player: int) -> bool:
    """Whether a waiting effect still offers a mandatory row: c6r6 with a
    Faction it can raise ("획득은 의무다", OQ-060 2026-09-30 addition). Read
    from public facts only (the frame's context, the seat's Influence), so
    the server's turn-end mirror may ask it too."""

    frame = rows_frame(state, player)
    if frame is None:
        return False
    owner = state.players[player]
    return any(
        kind == RESEARCH_BONUS
        and ResearchBonus(value) is ResearchBonus.INFLUENCE_ANY
        and any(influence_can_rise(owner, faction) for faction in Faction)
        for kind, _source, value in pending(frame)
    )


def lapse(state: GameState, player: int) -> RuleResult:
    """At the turn-end press: every waiting effect lapses, with an event."""

    frame = rows_frame(state, player)
    if frame is None or not pending(frame):
        return RuleResult(state=state)
    events = tuple(
        GameEvent(
            event_id=f"{source}:bonus_lapsed",
            kind="research_bonus_lapsed",
            payload=(("bonus", value), ("player", player)),
        )
        for kind, source, value in pending(frame)
        if kind == RESEARCH_BONUS
    )
    cleared = _replace_frame(
        state, len(state.decision_stack) - 1, _with_pending(frame, ())
    )
    return RuleResult(state=cleared, events=events)


def carried(turn_context: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
    """The waiting effects a turn frame hands the Agent-turn effect or
    Reveal frame that replaces it."""

    value = turn_context.get(PENDING_KEY)
    return ((PENDING_KEY, value),) if isinstance(value, str) and value else ()
