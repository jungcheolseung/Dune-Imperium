"""Shared Intrigue-deck draw with a replayable discard reshuffle.

When the Intrigue deck runs out, the face-up Intrigue discard pile is shuffled
into a new deck [FAQ p. 2]. Intrigue cards have no trash pile: a trashed one
joins that discard (``with_trashed_intrigue``, OQ-061) and is reshuffled with
it.
"""

from dataclasses import replace

from dune_imperium.content.bloodlines.tech import TechAbility, has_tech
from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import (
    FrameKind,
    context_int,
    context_str,
    replace_player,
    top_frame_of_kind,
    turn_owner_of,
)


def credit_suspensor_suits(
    state: GameState,
    owner: PlayerState,
    count: int,
) -> PlayerState:
    """Owe Suspensor Suits' troops for ``count`` Intrigue cards just drawn.

    "For each Intrigue card you draw or steal during your turn: [troop]
    Deploy it to the Conflict" [Suspensor Suits Tech tile]; only the owner's
    own Agent or Reveal turn counts (OQ-042 (a)). Every Intrigue draw calls
    this, the direct ones (track bonus, Leader and card effects) included;
    the engine deploys what is owed after the transition.
    """

    if (
        count < 1
        or turn_owner_of(state) != owner.player_id
        or not has_tech(owner.tech_ids, TechAbility.INTRIGUE_DRAW_TROOP)
    ):
        return owner
    return replace(owner, suspensor_owed=owner.suspensor_owed + count)


def with_trashed_intrigue(state: GameState, card_id: str) -> GameState:
    """Put an Intrigue card just trashed from a hand on the Intrigue discard.

    Every Intrigue trash lands here (OQ-061, user ruling 2026-10-04, "책략은
    따로 trash 더미가 없지", following the Steam app): the shared face-up
    discard, so the next reshuffle takes it back ("shuffle the discarded
    Intrigue cards to form a new deck" [FAQ p. 2]) and a draw that follows
    the trash may draw it again. This is a project convention, not the
    general trash rule, which removes cards "for the rest of the game"
    [Main p. 6]; the Intrigue-trash icon itself reads only "Trash an Intrigue
    card of your choice from your hand." [Main p. 20]. The caller removes the
    card from the hand and still announces it with ``intrigue_card_trashed``.
    """

    return replace(state, intrigue_discard=(*state.intrigue_discard, card_id))


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
    has cards the draw simply stops short; a shortfall is logged with
    ``intrigue_draw_short`` as soon as it is certain, which with a reshuffle
    is when the shuffle is asked for.
    """

    if not 0 <= player < state.config.players:
        raise ValueError("draw player must identify a configured seat")
    if count < 1:
        raise ValueError("Intrigue draw count must be positive")
    if not source:
        raise ValueError("Intrigue draw source must not be empty")

    drawn_now = _draw_available(state, player, count, source)
    available = len(state.intrigue_deck[:count])
    remaining = count - available
    if remaining <= 0:
        return drawn_now
    discard = drawn_now.state.intrigue_discard
    # Both piles are public, so a draw they cannot cover is known to fall
    # short before any reshuffle: logged here, the shortfall rides the step
    # that causes it, where the play server's dry run warns about it before
    # the click (user ruling 2026-10-02, L2-Q4: "로그 + 클릭 전 경고").
    short = intrigue_draw_short_events(
        source, player, count, available + min(remaining, len(discard))
    )
    if not discard:
        return RuleResult(state=drawn_now.state, events=(*drawn_now.events, *short))
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
        events=(*drawn_now.events, *short),
    )


def intrigue_draw_short_events(
    source: str, player: int, requested: int, drawn: int
) -> tuple[GameEvent, ...]:
    """Return the public event for an Intrigue draw the piles cannot cover.

    A draw the Intrigue deck and its discard pile cannot cover together
    stops short once both are exhausted (implementation-audits/intrigue.md
    "Deck exhaustion"); nothing is left to choose, so no window opens, but
    the shortfall is logged, before the shuffle when the draw needs one
    (user ruling 2026-10-02, L2-Q4: "로그 + 클릭 전 경고"). Only
    counts: the size of both piles is public, and no card is named.
    ``requested`` is what this draw asked for -- for a queued draw, what was
    still owed when the queue resolved.
    """

    if drawn >= requested:
        return ()
    return (
        GameEvent(
            event_id=f"{source}:intrigue_draw_short",
            kind="intrigue_draw_short",
            payload=(
                ("drawn", drawn),
                ("player", player),
                ("requested", requested),
                ("short", requested - drawn),
            ),
        ),
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
    """Apply the recorded discard permutation and finish the pending draw.

    A draw the new deck cannot cover was logged when the shuffle was asked
    for (``draw_intrigue_cards``): the shuffled cards are the discard of
    that moment, beneath a deck the draw had emptied.
    """

    frame = top_frame_of_kind(state, FrameKind.INTRIGUE_RESHUFFLE)
    if frame is None or not isinstance(frame.decision, ChanceDecision):
        raise ValueError("the current chance decision is not an Intrigue reshuffle")
    context = dict(frame.context)
    owner_label = "Intrigue reshuffle frame"
    player = context_int(context, "player", owner=owner_label)
    count = context_int(context, "count", owner=owner_label)
    source = context_str(context, "source", owner=owner_label)

    shuffled_ids = set(outcome.values)
    # The new deck forms beneath whatever still lay face down on top.
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
    if context.get("purpose") == "peek":
        # Imperium Ceremony asked for the shuffle to have two cards to look
        # at (OQ-052); the peek opens now. Imported here: the peek module
        # draws through this one.
        from dune_imperium.rules.intrigue_peek import begin_intrigue_peek

        peek = begin_intrigue_peek(shuffled, player, source=source)
        return RuleResult(state=peek.state, events=(event, *peek.events))
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
    next_owner = credit_suspensor_suits(
        state,
        replace(owner, intrigue_cards=(*owner.intrigue_cards, *drawn)),
        len(drawn),
    )
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
