"""Replayable personal-deck draw and discard reshuffle transitions."""

from dataclasses import replace

from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import FrameKind


def draw_or_request_personal_cards(
    state: GameState,
    player: int,
    count: int,
    *,
    source: str,
) -> RuleResult:
    """Draw now or push a chance decision for the needed discard shuffle."""

    if not 0 <= player < state.config.players:
        raise ValueError("draw player must identify a configured seat")
    if count < 1:
        raise ValueError("personal card draw count must be positive")
    if not source:
        raise ValueError("personal card draw source must not be empty")
    owner = state.players[player]
    if len(owner.deck) < count and owner.discard_pile:
        decision_id = f"{source}:discard_shuffle"
        frame = DecisionFrame(
            kind=FrameKind.PERSONAL_DRAW_RESHUFFLE,
            frame_id=f"{decision_id}:personal_draw",
            decision=ChanceDecision(
                decision_id=decision_id,
                prompt=f"Shuffle player {player}'s discard pile",
                options=owner.discard_pile,
                count=len(owner.discard_pile),
            ),
            context=(
                ("count", count),
                ("player", player),
                ("source", source),
            ),
        )
        return RuleResult(state=state.push_decision(frame))
    return _draw_available(state, player, count, source)


def apply_personal_draw_reshuffle(
    state: GameState,
    outcome: ChanceOutcome,
) -> RuleResult:
    """Apply one recorded discard permutation and complete its pending draw."""

    if not state.decision_stack:
        raise ValueError("there is no pending personal draw reshuffle")
    frame = state.decision_stack[-1]
    if not frame.frame_id.endswith(":personal_draw") or not isinstance(
        frame.decision, ChanceDecision
    ):
        raise ValueError("the current chance decision is not a personal draw")
    context = dict(frame.context)
    player = context.get("player")
    count = context.get("count")
    source = context.get("source")
    if (
        isinstance(player, bool)
        or not isinstance(player, int)
        or isinstance(count, bool)
        or not isinstance(count, int)
        or not isinstance(source, str)
    ):
        raise RuntimeError("personal draw reshuffle has invalid context")

    owner = state.players[player]
    next_owner = replace(
        owner,
        deck=(*owner.deck, *outcome.values),
        discard_pile=(),
    )
    players = tuple(
        next_owner if candidate.player_id == player else candidate
        for candidate in state.players
    )
    shuffled = replace(state.pop_decision(), players=players)
    drawn = _draw_available(shuffled, player, count, source)
    event = GameEvent(
        event_id=f"{source}:discard_shuffled",
        kind="personal_discard_shuffled",
        payload=(("count", len(outcome.values)), ("player", player)),
        visible_to=(player,),
    )
    return RuleResult(state=drawn.state, events=(event, *drawn.events))


def personal_draw_is_pending(state: GameState) -> bool:
    """Return whether the top decision is a personal discard reshuffle."""

    return bool(
        state.decision_stack
        and state.decision_stack[-1].frame_id.endswith(":personal_draw")
    )


def _draw_available(
    state: GameState,
    player: int,
    count: int,
    source: str,
) -> RuleResult:
    owner = state.players[player]
    drawn = owner.deck[:count]
    next_owner = replace(
        owner,
        deck=owner.deck[len(drawn) :],
        hand=(*owner.hand, *drawn),
    )
    players = tuple(
        next_owner if candidate.player_id == player else candidate
        for candidate in state.players
    )
    return RuleResult(state=replace(state, players=players))
