"""Tests for automatic top-level phase transitions."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.core import (
    GamePhase,
    GameState,
    PlayerDecision,
    canonical_state_hash,
)
from dune_imperium.rules.phases import begin_round
from dune_imperium.rules.setup import create_initial_state

SELECTED_LEADERS = (
    "feyd_rautha_harkonnen",
    "gurney_halleck",
    "lady_amber_metulli",
    "lady_jessica",
)


def _setup_state(seed: int = 71) -> GameState:
    return create_initial_state(
        RulesetConfig(),
        seed=seed,
        leader_ids=SELECTED_LEADERS,
    ).state


def test_round_start_reveals_conflict_draws_five_and_opens_first_turn() -> None:
    state = _setup_state()
    first_conflict = state.conflict_deck[0]
    original_decks = tuple(player.deck for player in state.players)

    result = begin_round(state)
    started = result.state

    assert started.phase is GamePhase.PLAYER_TURNS
    assert started.round_number == 1
    assert started.current_conflict_ids == (first_conflict,)
    assert started.conflict_deck == state.conflict_deck[1:]
    for player, original_deck in zip(started.players, original_decks, strict=True):
        assert player.hand == original_deck[:5]
        assert player.deck == original_deck[5:]

    decision = started.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    assert decision.owner == state.first_player


def test_round_start_adds_five_cards_instead_of_refilling_hand_to_five() -> None:
    state = _setup_state()
    first = replace(state.players[0], hand=("retained_card",))
    state = replace(state, players=(first, *state.players[1:]))

    started = begin_round(state).state

    assert len(started.players[0].hand) == 6
    assert started.players[0].hand[0] == "retained_card"


def test_round_start_emits_public_conflict_and_private_draw_events() -> None:
    state = _setup_state()

    events = begin_round(state).events

    assert len(events) == 5
    assert events[0].kind == "conflict_revealed"
    assert events[0].visible_to is None
    assert tuple(event.visible_to for event in events[1:]) == (
        (0,),
        (1,),
        (2,),
        (3,),
    )
    assert all(event.kind == "cards_drawn" for event in events[1:])


def test_round_start_is_pure_and_rejects_wrong_phase() -> None:
    state = _setup_state()
    before = canonical_state_hash(state)

    assert begin_round(state) == begin_round(state)
    assert canonical_state_hash(state) == before
    with pytest.raises(ValueError, match="Round Start phase"):
        begin_round(replace(state, phase=GamePhase.PLAYER_TURNS))


def test_round_start_defers_draw_that_requires_reshuffling() -> None:
    state = _setup_state()
    first = replace(state.players[0], deck=state.players[0].deck[:4])
    state = replace(state, players=(first, *state.players[1:]))

    with pytest.raises(ValueError, match="reshuffle"):
        begin_round(state)
