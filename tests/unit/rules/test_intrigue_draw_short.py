"""An Intrigue draw the deck and its discard cannot cover is logged.

"In the rare case that you exhaust the Intrigue deck, shuffle the discarded
Intrigue cards to form a new deck" [FAQ p. 2]; with both piles empty the
draw stops short (implementation-audits/intrigue.md "Deck exhaustion",
OQ-067). Nothing is left to choose, so no window opens, but the shortfall is
logged with the public event ``intrigue_draw_short`` and the step that
causes it carries a warning before the click (user ruling 2026-10-02,
L2-Q4: "로그 + 클릭 전 경고"; the warning is tests/server/test_sessions.py).
"""

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.intrigue import (
    intrigue_deck_instance_ids,
    twisted_intrigue_instance_ids,
)
from dune_imperium.core import GamePhase, GameState, PlayerState
from dune_imperium.core.chance import ChanceOutcome, ChanceResolver
from dune_imperium.core.decisions import ChanceDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.intrigue_deck import (
    apply_intrigue_reshuffle,
    draw_intrigue_cards,
    draw_or_queue_intrigue_cards,
    resolve_pending_intrigue_draw,
)
from dune_imperium.simulation.invariants import check_event_visibility

INTRIGUE = intrigue_deck_instance_ids(False)
TWISTED = twisted_intrigue_instance_ids()


def _state(
    deck: tuple[str, ...], discard: tuple[str, ...] = ()
) -> GameState:
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=tuple(PlayerState(player_id=seat) for seat in range(4)),
        intrigue_deck=deck,
        intrigue_discard=discard,
    )


def _short(result: RuleResult) -> list[dict[str, object]]:
    return [
        dict(event.payload)
        for event in result.events
        if event.kind == "intrigue_draw_short"
    ]


def _reshuffled(result: RuleResult) -> RuleResult:
    frame = result.state.decision_stack[-1]
    assert frame.kind == FrameKind.INTRIGUE_RESHUFFLE
    decision = UprisingRulesEngine().current_decision(result.state)
    assert isinstance(decision, ChanceDecision)
    return apply_intrigue_reshuffle(
        result.state, ChanceResolver(seed=3).resolve(decision)
    )


def test_a_draw_both_piles_cannot_cover_logs_the_shortfall() -> None:
    drawn = draw_intrigue_cards(_state(INTRIGUE[:1]), 0, 2, source="probe")

    assert drawn.state.players[0].intrigue_cards == INTRIGUE[:1]
    assert drawn.state.decision_stack == ()
    assert [event.kind for event in drawn.events] == [
        "intrigue_card_drawn",
        "intrigue_draw_short",
    ]
    assert _short(drawn) == [{"drawn": 1, "player": 0, "requested": 2, "short": 1}]
    # Public, counts only: no card is named.
    short = drawn.events[-1]
    assert short.visible_to is None
    check_event_visibility(drawn.state, drawn.events)


def test_a_draw_with_both_piles_empty_logs_the_whole_draw_short() -> None:
    drawn = draw_intrigue_cards(_state(()), 2, 1, source="probe")

    assert drawn.state.players[2].intrigue_cards == ()
    assert [event.kind for event in drawn.events] == ["intrigue_draw_short"]
    assert _short(drawn) == [{"drawn": 0, "player": 2, "requested": 1, "short": 1}]


def test_a_short_reshuffle_is_logged_when_the_shuffle_is_asked_for() -> None:
    # Deck 1, discard 1, a draw of 3: one card now, the discard reshuffled
    # for the rest, and one card is missing. Both piles are public, so the
    # shortfall is certain before the shuffle and rides the drawing step.
    asked = draw_intrigue_cards(
        _state(INTRIGUE[:1], INTRIGUE[1:2]), 0, 3, source="probe"
    )

    assert _short(asked) == [{"drawn": 2, "player": 0, "requested": 3, "short": 1}]
    finished = _reshuffled(asked)

    assert [event.kind for event in finished.events] == [
        "intrigue_discard_shuffled",
        "intrigue_card_drawn",
    ]
    # What was logged is what the reshuffle then gives.
    assert finished.state.players[0].intrigue_cards == INTRIGUE[:2]
    assert finished.state.intrigue_deck == ()


def test_a_covered_draw_logs_no_shortfall() -> None:
    full = draw_intrigue_cards(_state(INTRIGUE[:2]), 0, 2, source="probe")
    assert _short(full) == []
    # The discard covers what the deck lacks.
    asked = draw_intrigue_cards(_state((), INTRIGUE[:2]), 0, 2, source="probe")
    assert _short(asked) == []
    finished = _reshuffled(asked)
    assert _short(finished) == []
    assert len(finished.state.players[0].intrigue_cards) == 2


def test_a_queued_draw_logs_its_shortfall_when_it_resolves() -> None:
    # Rule modules in the middle of their own bookkeeping queue what the
    # deck lacks; the queue resolves before the next player decision, and a
    # card discarded meanwhile could still be reshuffled, so the shortfall
    # is logged only then, for what was still owed.
    queued = draw_or_queue_intrigue_cards(
        _state(INTRIGUE[:1]), 1, 2, source="probe"
    )

    assert _short(queued) == []
    pending = queued.state.pending_intrigue_draws
    assert [(seat, count) for seat, count, _ in pending] == [(1, 1)]
    resolved = resolve_pending_intrigue_draw(queued.state)

    assert _short(resolved) == [{"drawn": 0, "player": 1, "requested": 1, "short": 1}]
    assert resolved.state.players[1].intrigue_cards == INTRIGUE[:1]


# --- OQ-097: Twisted cards stay in the discard -------------------------------
# User ruling 2026-10-04: "Piter의 twisted 카드는 공용 책략 버림 더미로
# 가지만, 나중에 다시 섞을 때는 책략 더미로 가지 않고 계속 버림 더미에
# 남아있게 하자. 다른 사람이 twisted 카드를 뽑는 일은 없도록".


def test_a_reshuffle_leaves_the_twisted_cards_in_the_discard() -> None:
    discard = (INTRIGUE[0], TWISTED[0], INTRIGUE[1], TWISTED[1], INTRIGUE[2])
    asked = draw_intrigue_cards(_state((), discard), 0, 1, source="probe")

    frame = asked.state.decision_stack[-1]
    assert frame.kind == FrameKind.INTRIGUE_RESHUFFLE
    decision = frame.decision
    assert isinstance(decision, ChanceDecision)
    # Only the cards that are shuffled are the chance step's options.
    assert decision.options == INTRIGUE[:3]
    assert decision.count == 3
    assert _short(asked) == []
    order = (INTRIGUE[2], INTRIGUE[0], INTRIGUE[1])
    finished = apply_intrigue_reshuffle(
        asked.state, ChanceOutcome(decision_id=decision.decision_id, values=order)
    )

    assert finished.state.intrigue_discard == TWISTED[:2]
    assert finished.state.players[0].intrigue_cards == order[:1]
    assert finished.state.intrigue_deck == order[1:]
    shuffled = [e for e in finished.events if e.kind == "intrigue_discard_shuffled"]
    assert [dict(e.payload) for e in shuffled] == [{"count": 3}]
    check_event_visibility(finished.state, finished.events)


def test_a_reshuffle_outcome_naming_a_twisted_card_is_refused() -> None:
    asked = draw_intrigue_cards(
        _state((), (INTRIGUE[0], TWISTED[0])), 0, 1, source="probe"
    )
    decision = asked.state.decision_stack[-1].decision
    assert isinstance(decision, ChanceDecision)
    assert decision.options == INTRIGUE[:1]
    smuggled = ChanceOutcome(decision_id=decision.decision_id, values=TWISTED[:1])

    with pytest.raises(ValueError, match="unavailable"):
        UprisingRulesEngine().apply(asked.state, smuggled)
    with pytest.raises(ValueError, match="Twisted"):
        apply_intrigue_reshuffle(asked.state, smuggled)


def test_twisted_cards_do_not_cover_a_draw() -> None:
    # The Twisted cards are not shuffled, so they count for nothing: with
    # one other card a draw of three is two short, logged before the shuffle.
    discard = (TWISTED[0], INTRIGUE[0], TWISTED[1])
    asked = draw_intrigue_cards(_state((), discard), 0, 3, source="probe")

    assert _short(asked) == [{"drawn": 1, "player": 0, "requested": 3, "short": 2}]
    finished = _reshuffled(asked)
    assert finished.state.players[0].intrigue_cards == INTRIGUE[:1]
    assert finished.state.intrigue_deck == ()
    assert finished.state.intrigue_discard == (TWISTED[0], TWISTED[1])


def test_a_discard_of_only_twisted_cards_draws_nothing() -> None:
    # Nothing to shuffle: no chance step, no card, and the shortfall logged.
    drawn = draw_intrigue_cards(_state((), TWISTED[:2]), 1, 1, source="probe")

    assert drawn.state.decision_stack == ()
    assert drawn.state.players[1].intrigue_cards == ()
    assert drawn.state.intrigue_discard == TWISTED[:2]
    assert [event.kind for event in drawn.events] == ["intrigue_draw_short"]
    assert _short(drawn) == [{"drawn": 0, "player": 1, "requested": 1, "short": 1}]
    # The deck's last card is drawn; the Twisted discard is not shuffled.
    partial = draw_intrigue_cards(
        _state(INTRIGUE[:1], TWISTED[:1]), 0, 2, source="probe"
    )
    assert partial.state.decision_stack == ()
    assert partial.state.players[0].intrigue_cards == INTRIGUE[:1]
    assert _short(partial) == [{"drawn": 1, "player": 0, "requested": 2, "short": 1}]
    # A queued draw resolves the same way.
    queued = draw_or_queue_intrigue_cards(
        _state((), TWISTED[:1]), 2, 1, source="probe"
    )
    resolved = resolve_pending_intrigue_draw(queued.state)
    assert resolved.state.decision_stack == ()
    assert resolved.state.intrigue_discard == TWISTED[:1]
    assert _short(resolved) == [{"drawn": 0, "player": 2, "requested": 1, "short": 1}]
