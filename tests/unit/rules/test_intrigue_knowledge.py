"""The Intrigue cards a seat knows and another seat does not (OQ-149).

docs/rules/open-questions.md OQ-149, user ruling 2026-10-29 ("(가) 둘 다
기록"): a seat that looked at the Intrigue deck's top cards and put one back
on top knows that card -- Imperium Ceremony here, Viscount Hundro Moritani
from stage P4e -- until it reaches a public zone or the seat's own hand, and
a shuffle forgets the cards it shuffles (``rules.intrigue_knowledge``).
"""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.immortality.board import RESEARCH_START_ID
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
)
from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.decisions import ChanceDecision
from dune_imperium.core.observation import known_card_seats, observe_state
from dune_imperium.rules.board_effects import _secrets_steal_frame, apply_secrets_steal
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.intrigue_deck import draw_intrigue_cards
from dune_imperium.rules.intrigue_knowledge import (
    forget_intrigue_cards,
    remember_intrigue,
    settle_known_intrigue,
)
from dune_imperium.rules.intrigue_peek import (
    apply_intrigue_peek,
    begin_intrigue_peek,
    legal_intrigue_peek_actions,
)
from dune_imperium.simulation.invariants import (
    CardCensus,
    InvariantViolation,
    check_observation_privacy,
    check_state_invariants,
)

IMMORTALITY = RulesetConfig(immortality=True)
INTRIGUE = intrigue_deck_instance_ids(False, immortality=True)


def _state(**overrides: object) -> GameState:
    values: dict[str, object] = {
        "config": IMMORTALITY,
        "seed": 1,
        "phase": GamePhase.PLAYER_TURNS,
        "round_number": 1,
        "current_conflict_ids": (CONFLICTS[0].card.card_id,),
        "intrigue_deck": INTRIGUE[:6],
        "players": tuple(
            PlayerState(player_id=seat, research_space=RESEARCH_START_ID)
            for seat in range(4)
        ),
        "decision_stack": (
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    }
    values.update(overrides)
    return GameState(**values)  # type: ignore[arg-type]


def _peek(state: GameState, seat: int, keep: str) -> GameState:
    opened = begin_intrigue_peek(state, seat, source=f"test:peek:{seat}").state
    (action,) = (
        action
        for action in legal_intrigue_peek_actions(opened, seat)
        if dict(action.arguments)["instance_id"] == keep
    )
    return apply_intrigue_peek(opened, action).state


def _with_hand(state: GameState, seat: int, cards: tuple[str, ...]) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], intrigue_cards=cards)
    return replace(state, players=tuple(players))


def test_imperium_ceremony_remembers_the_card_put_back_on_top() -> None:
    """OQ-149 (가): the card not kept stays on top of the deck [Imperium
    Ceremony card] (OQ-052), and the seat that put it there knows it; no
    other seat does."""

    kept = _peek(_state(), 0, INTRIGUE[1])
    assert kept.intrigue_deck[0] == INTRIGUE[0]
    assert kept.players[0].known_intrigue_ids == (INTRIGUE[0],)
    assert all(not player.known_intrigue_ids for player in kept.players[1:])
    own = observe_state(kept, 0).private
    other = observe_state(kept, 1).private
    assert own is not None and own.known_intrigue_top == INTRIGUE[0]
    assert other is not None and other.known_intrigue_top == ""
    assert known_card_seats(kept)[INTRIGUE[0]] == frozenset({0})
    check_observation_privacy(kept)


def test_a_known_card_another_seat_draws_stays_known_in_its_hand() -> None:
    """A draw takes the deck's top card, so the seat that knew it knows who
    holds it (rise-of-ix.md 13, "such a card once another seat drew it");
    once that seat plays or discards it, the card is public and the record
    lets it go."""

    kept = _peek(_state(), 0, INTRIGUE[1])
    drawn = settle_known_intrigue(
        draw_intrigue_cards(kept, 1, 1, source="test:draw").state
    )
    assert drawn.players[1].intrigue_cards == (INTRIGUE[0],)
    assert drawn.players[0].known_intrigue_ids == (INTRIGUE[0],)
    own = observe_state(drawn, 0).private
    assert own is not None
    assert own.known_intrigue_top == ""
    assert own.known_intrigue_held == ((1, INTRIGUE[0]),)
    assert known_card_seats(drawn)[INTRIGUE[0]] == frozenset({0, 1})
    check_observation_privacy(drawn)
    played = settle_known_intrigue(
        replace(_with_hand(drawn, 1, ()), intrigue_discard=(INTRIGUE[0],))
    )
    assert played.players[0].known_intrigue_ids == ()


def test_the_knower_drawing_its_card_lets_the_record_go() -> None:
    """A card in the seat's own hand is its own, not a known hidden card."""

    kept = _peek(_state(), 0, INTRIGUE[1])
    drawn = settle_known_intrigue(
        draw_intrigue_cards(kept, 0, 1, source="test:draw").state
    )
    assert drawn.players[0].intrigue_cards == (INTRIGUE[1], INTRIGUE[0])
    assert drawn.players[0].known_intrigue_ids == ()


def test_another_seats_peek_makes_the_first_knower_forget() -> None:
    """The table sees a card kept and one put back face down, not which:
    the seat that knew the top card no longer knows where it is, and the
    second seat knows the card it put back."""

    first = _peek(_state(), 0, INTRIGUE[1])
    second = _peek(first, 1, INTRIGUE[2])
    assert second.intrigue_deck[0] == INTRIGUE[0]
    assert second.players[0].known_intrigue_ids == ()
    assert second.players[1].known_intrigue_ids == (INTRIGUE[0],)
    check_observation_privacy(second)


def test_a_hidden_steal_makes_the_other_seats_forget_the_victims_cards() -> None:
    """Secrets: the theft is public, the stolen card is not (OQ-010 ruling
    3), so a seat that knew a card in the victim's hand cannot follow it;
    the thief and the victim still know what they know."""

    state = _with_hand(
        _state(), 1, (INTRIGUE[0], INTRIGUE[1], INTRIGUE[2], INTRIGUE[3])
    )
    players = list(state.players)
    players[0] = remember_intrigue(players[0], (INTRIGUE[0],))
    players[2] = remember_intrigue(players[2], (INTRIGUE[1],))
    state = replace(state, players=tuple(players))
    frame = _secrets_steal_frame(state, 2, 1, state.players[1].intrigue_cards)
    pushed = state.push_decision(frame)
    assert isinstance(frame.decision, ChanceDecision)
    stolen = apply_secrets_steal(
        pushed,
        ChanceOutcome(decision_id=frame.decision.decision_id, values=(INTRIGUE[3],)),
    ).state
    assert stolen.players[0].known_intrigue_ids == ()
    assert stolen.players[2].known_intrigue_ids == (INTRIGUE[1],)


def test_forgetting_and_settling_leave_an_unchanged_state_itself() -> None:
    """Both run after every transition of every game, most of which hold no
    entry: they return the very state they were given."""

    state = _state()
    assert settle_known_intrigue(state) is state
    assert forget_intrigue_cards(state, INTRIGUE[:2]) is state
    kept = _peek(state, 0, INTRIGUE[1])
    assert settle_known_intrigue(kept) is kept
    assert forget_intrigue_cards(kept, INTRIGUE[:2], keeping=(0,)) is kept


def test_only_immortality_and_rise_of_ix_games_record_known_intrigue() -> None:
    """Imperium Ceremony is Immortality's and Hundro's Intelligence Rise of
    Ix's: the sweep accepts a known deck card there and rejects one in any
    other game, so the record cannot leak into games that have neither."""

    for config, allowed in ((IMMORTALITY, True), (RulesetConfig(), False)):
        state = UprisingRulesEngine().reset(config, 3)
        census = CardCensus.from_state(state)
        players = list(state.players)
        players[0] = remember_intrigue(players[0], state.intrigue_deck[:1])
        marked = replace(state, players=tuple(players))
        if allowed:
            check_state_invariants(marked, census)
        else:
            with pytest.raises(InvariantViolation, match="without Immortality"):
                check_state_invariants(marked, census)
