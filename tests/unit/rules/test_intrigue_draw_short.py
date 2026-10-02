"""An Intrigue draw the deck and its discard cannot cover is logged.

"In the rare case that you exhaust the Intrigue deck, shuffle the discarded
Intrigue cards to form a new deck" [FAQ p. 2]; with both piles empty the
draw stops short (implementation-audits/intrigue.md "Deck exhaustion",
OQ-067). Nothing is left to choose, so no window opens, but the shortfall is
logged with the public event ``intrigue_draw_short`` and the step that
causes it carries a warning before the click (user ruling 2026-10-02,
L2-Q4: "로그 + 클릭 전 경고"; the warning is tests/server/test_sessions.py).
"""

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.core import GamePhase, GameState, PlayerState
from dune_imperium.core.chance import ChanceResolver
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
