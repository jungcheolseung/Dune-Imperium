"""Tests for Reserve acquisition during Reveal turns."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
)
from dune_imperium.rules.acquisition import (
    apply_imperium_acquisition,
    apply_reserve_acquisition,
    legal_imperium_acquisitions,
    legal_reserve_acquisitions,
)
from dune_imperium.rules.reveal_turn import begin_reveal_turn, legal_reveal_actions


def _instance(card_id: str, copy: int = 0) -> str:
    return tuple(
        instance_id
        for instance_id in starting_deck_instance_ids(0)
        if f":{card_id}:" in instance_id
    )[copy]


def _reveal_state(*cards: str) -> GameState:
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(
            PlayerState(player_id=0, hand=cards),
            *(PlayerState(player_id=seat) for seat in range(1, 4)),
        ),
        reserve_stacks=(
            ("prepare_the_way", 8),
            ("the_spice_must_flow", 10),
        ),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    return begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state


def test_only_affordable_nonempty_reserve_stacks_are_legal() -> None:
    state = _reveal_state(_instance("convincing_argument"))

    actions = legal_reserve_acquisitions(state, 0)

    assert tuple(dict(action.arguments)["card_id"] for action in actions) == (
        "prepare_the_way",
    )
    assert legal_reserve_acquisitions(state, 1) == ()


def test_acquisition_spends_persuasion_decrements_stack_and_discards_card() -> None:
    state = _reveal_state(_instance("convincing_argument"))
    action = legal_reserve_acquisitions(state, 0)[0]

    result = apply_reserve_acquisition(state, action)
    context = dict(result.state.decision_stack[-1].context)

    assert context["persuasion"] == 0
    assert dict(result.state.reserve_stacks)["prepare_the_way"] == 7
    assert result.state.players[0].discard_pile == (
        "reserve:prepare_the_way:7",
    )


def test_spice_must_flow_awards_its_acquisition_vp() -> None:
    arguments = tuple(_instance("convincing_argument", copy) for copy in range(2))
    dunes = tuple(_instance("dune_the_desert_planet", copy) for copy in range(2))
    cards = (
        *arguments,
        *dunes,
        _instance("diplomacy"),
        _instance("reconnaissance"),
        _instance("signet_ring"),
    )
    state = _reveal_state(*cards)
    action = next(
        action
        for action in legal_reserve_acquisitions(state, 0)
        if dict(action.arguments)["card_id"] == "the_spice_must_flow"
    )

    result = apply_reserve_acquisition(state, action)

    assert result.state.players[0].victory_points == 2
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 0


def test_imperium_purchase_refills_same_row_position_immediately() -> None:
    state = _reveal_state(_instance("convincing_argument"))
    instances = imperium_deck_instance_ids(False)
    cheap = next(card for card in instances if ":sardaukar_soldier:" in card)
    expensive = next(card for card in instances if ":bene_gesserit_operative:" in card)
    others = tuple(card for card in instances if card not in {cheap, expensive})
    row = (expensive, cheap, *others[:3])
    replacement = others[3]
    state = replace(
        state,
        imperium_row=row,
        imperium_deck=(replacement, *others[4:]),
    )

    actions = legal_imperium_acquisitions(state, 0)
    assert tuple(dict(action.arguments)["instance_id"] for action in actions) == (
        cheap,
    )
    result = apply_imperium_acquisition(state, actions[0])

    assert result.state.players[0].discard_pile == (cheap,)
    assert result.state.imperium_row == (expensive, replacement, *others[:3])
    assert result.state.imperium_deck == others[4:]
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1


def test_acquisition_bonus_card_is_not_silently_resolved() -> None:
    cards = (
        _instance("convincing_argument", 0),
        _instance("convincing_argument", 1),
    )
    state = _reveal_state(*cards)
    instances = imperium_deck_instance_ids(False)
    guild_spy = next(card for card in instances if ":guild_spy:" in card)
    others = tuple(card for card in instances if card != guild_spy)
    state = replace(
        state,
        imperium_row=(guild_spy, *others[:4]),
        imperium_deck=others[4:],
    )
    action = next(
        action
        for action in legal_imperium_acquisitions(state, 0)
        if dict(action.arguments)["instance_id"] == guild_spy
    )

    with pytest.raises(NotImplementedError, match="guild_spy"):
        apply_imperium_acquisition(state, action)
