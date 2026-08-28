"""Shared Intrigue-deck draw with a replayable discard reshuffle.

When the Intrigue deck runs out, the face-up Intrigue discard pile is shuffled
into a new deck [FAQ p. 2]. Trashed Intrigue cards live in ``intrigue_trash``
and are never reshuffled [Main p. 20].
"""

from dataclasses import replace

from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import (
    FrameKind,
    context_int,
    context_str,
    replace_player,
    top_frame_of_kind,
)


def draw_intrigue_cards(
    state: GameState,
    player: int,
    count: int,
    *,
    source: str,
) -> RuleResult:
    """Draw up to ``count`` Intrigue cards, reshuffling the discard if needed.

    Cards available on the deck are drawn immediately. If more are owed and
    the discard pile is not empty, a chance decision for the reshuffle is
    pushed and the remaining draw completes when it resolves. If neither pile
    has cards the draw simply stops short.
    """

    if not 0 <= player < state.config.players:
        raise ValueError("draw player must identify a configured seat")
    if count < 1:
        raise ValueError("Intrigue draw count must be positive")
    if not source:
        raise ValueError("Intrigue draw source must not be empty")

    drawn_now = _draw_available(state, player, count, source)
    remaining = count - len(state.intrigue_deck[:count])
    if remaining <= 0 or not drawn_now.state.intrigue_discard:
        return drawn_now
    decision_id = f"{source}:intrigue_shuffle"
    frame = DecisionFrame(
        kind=FrameKind.INTRIGUE_RESHUFFLE,
        frame_id=f"{decision_id}:intrigue_reshuffle",
        decision=ChanceDecision(
            decision_id=decision_id,
            prompt="Shuffle the Intrigue discard pile into a new deck",
            options=drawn_now.state.intrigue_discard,
            count=len(drawn_now.state.intrigue_discard),
        ),
        context=(("count", remaining), ("player", player), ("source", source)),
    )
    return RuleResult(
        state=drawn_now.state.push_decision(frame),
        events=drawn_now.events,
    )


def draw_or_queue_intrigue_cards(
    state: GameState,
    player: int,
    count: int,
    *,
    source: str,
) -> RuleResult:
    """Draw what the deck holds now and queue the rest for the dispatcher.

    Rule modules that are in the middle of their own frame bookkeeping cannot
    push the reshuffle chance frame themselves, so the shortfall is recorded
    in ``pending_intrigue_draws`` and ``resolve_pending_intrigue_draw`` runs
    it before the next player decision.
    """

    if not 0 <= player < state.config.players:
        raise ValueError("draw player must identify a configured seat")
    if count < 1:
        raise ValueError("Intrigue draw count must be positive")
    if not source:
        raise ValueError("Intrigue draw source must not be empty")
    drawn_now = _draw_available(state, player, count, source)
    shortfall = count - len(state.intrigue_deck[:count])
    if shortfall <= 0:
        return drawn_now
    queued = replace(
        drawn_now.state,
        pending_intrigue_draws=(
            *drawn_now.state.pending_intrigue_draws,
            (player, shortfall, source),
        ),
    )
    return RuleResult(state=queued, events=drawn_now.events)


def intrigue_draw_is_queued(state: GameState) -> bool:
    """Return whether an owed Intrigue draw can be resolved now."""

    frame = state.decision_stack[-1] if state.decision_stack else None
    return bool(state.pending_intrigue_draws) and (
        frame is None or not isinstance(frame.decision, ChanceDecision)
    )


def resolve_pending_intrigue_draw(state: GameState) -> RuleResult:
    """Resolve the oldest owed draw, reshuffling the discard if needed."""

    if not state.pending_intrigue_draws:
        raise ValueError("there is no pending Intrigue draw")
    player, count, source = state.pending_intrigue_draws[0]
    remaining = replace(state, pending_intrigue_draws=state.pending_intrigue_draws[1:])
    return draw_intrigue_cards(remaining, player, count, source=source)


def intrigue_reshuffle_is_pending(state: GameState) -> bool:
    """Return whether the top decision is an Intrigue discard reshuffle."""

    return top_frame_of_kind(state, FrameKind.INTRIGUE_RESHUFFLE) is not None


def apply_intrigue_reshuffle(
    state: GameState,
    outcome: ChanceOutcome,
) -> RuleResult:
    """Apply the recorded discard permutation and finish the pending draw."""

    frame = top_frame_of_kind(state, FrameKind.INTRIGUE_RESHUFFLE)
    if frame is None or not isinstance(frame.decision, ChanceDecision):
        raise ValueError("the current chance decision is not an Intrigue reshuffle")
    context = dict(frame.context)
    owner_label = "Intrigue reshuffle frame"
    player = context_int(context, "player", owner=owner_label)
    count = context_int(context, "count", owner=owner_label)
    source = context_str(context, "source", owner=owner_label)

    shuffled_ids = set(outcome.values)
    shuffled = replace(
        state.pop_decision(),
        intrigue_deck=(*state.intrigue_deck, *outcome.values),
        # Cards discarded after the shuffle was requested stay in the discard.
        intrigue_discard=tuple(
            card_id for card_id in state.intrigue_discard if card_id not in shuffled_ids
        ),
    )
    event = GameEvent(
        event_id=f"{source}:intrigue_shuffled",
        kind="intrigue_discard_shuffled",
        payload=(("count", len(outcome.values)),),
    )
    drawn = _draw_available(shuffled, player, count, source)
    return RuleResult(state=drawn.state, events=(event, *drawn.events))


def _draw_available(
    state: GameState,
    player: int,
    count: int,
    source: str,
) -> RuleResult:
    drawn = state.intrigue_deck[:count]
    if not drawn:
        return RuleResult(state=state)
    owner = state.players[player]
    next_owner = replace(owner, intrigue_cards=(*owner.intrigue_cards, *drawn))
    next_state = replace(
        state,
        players=replace_player(state.players, next_owner),
        intrigue_deck=state.intrigue_deck[len(drawn) :],
    )
    event = GameEvent(
        event_id=f"{source}:intrigue_draw:{len(state.intrigue_deck)}",
        kind="intrigue_card_drawn",
        payload=(("count", len(drawn)), ("player", player)),
    )
    return RuleResult(state=next_state, events=(event,))
