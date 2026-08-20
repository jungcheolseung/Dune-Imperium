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
    apply_acquisition_spy_action,
    apply_imperium_acquisition,
    apply_reserve_acquisition,
    legal_acquisition_spy_actions,
    legal_imperium_acquisitions,
    legal_reserve_acquisitions,
)
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.reveal_turn import (
    begin_reveal_turn,
    legal_reveal_actions,
)


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


def test_acquired_transcribed_card_can_be_revealed_later() -> None:
    cards = (
        _instance("convincing_argument", 0),
        _instance("convincing_argument", 1),
    )
    state = _reveal_state(*cards)
    instances = imperium_deck_instance_ids(False)
    maula = next(card for card in instances if ":maula_pistol:" in card)
    others = tuple(card for card in instances if card != maula)
    state = replace(
        state,
        imperium_row=(maula, *others[:4]),
        imperium_deck=others[4:],
    )
    action = next(
        action
        for action in legal_imperium_acquisitions(state, 0)
        if dict(action.arguments)["instance_id"] == maula
    )
    acquired = apply_imperium_acquisition(state, action).state
    owner = replace(
        acquired.players[0],
        hand=(maula,),
        discard_pile=acquired.players[0].in_play,
        in_play=(),
    )
    later = replace(
        acquired,
        players=(owner, *acquired.players[1:]),
        decision_stack=(
            DecisionFrame(
                frame_id="round:2:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )

    revealed = begin_reveal_turn(later, legal_reveal_actions(later, 0)[0]).state

    assert dict(revealed.decision_stack[-1].context)["persuasion"] == 1


def test_acquisition_bonus_card_is_not_silently_resolved() -> None:
    cards = (
        _instance("convincing_argument", 0),
        _instance("convincing_argument", 1),
        _instance("dune_the_desert_planet", 0),
        _instance("dune_the_desert_planet", 1),
    )
    state = _reveal_state(*cards)
    instances = imperium_deck_instance_ids(False)
    price = next(card for card in instances if ":price_is_no_object:" in card)
    others = tuple(card for card in instances if card != price)
    state = replace(
        state,
        imperium_row=(price, *others[:4]),
        imperium_deck=others[4:],
    )
    action = next(
        action
        for action in legal_imperium_acquisitions(state, 0)
        if dict(action.arguments)["instance_id"] == price
    )

    with pytest.raises(NotImplementedError, match="price_is_no_object"):
        apply_imperium_acquisition(state, action)


def test_overthrow_acquisition_draws_an_intrigue_card() -> None:
    arguments = tuple(_instance("convincing_argument", copy) for copy in range(2))
    dunes = tuple(_instance("dune_the_desert_planet", copy) for copy in range(2))
    state = _reveal_state(
        *arguments,
        *dunes,
        _instance("diplomacy"),
        _instance("reconnaissance"),
    )
    instances = imperium_deck_instance_ids(False)
    overthrow = next(card for card in instances if ":overthrow:" in card)
    others = tuple(card for card in instances if card != overthrow)
    state = replace(
        state,
        imperium_row=(overthrow, *others[:4]),
        imperium_deck=others[4:],
        intrigue_deck=("intrigue:test:0",),
    )
    action = next(
        action
        for action in legal_imperium_acquisitions(state, 0)
        if dict(action.arguments)["instance_id"] == overthrow
    )
    assert action in UprisingRulesEngine().legal_actions(state, 0)

    result = apply_imperium_acquisition(state, action)

    assert result.state.players[0].discard_pile == (overthrow,)
    assert result.state.players[0].intrigue_cards == ("intrigue:test:0",)
    assert result.state.intrigue_deck == ()
    assert tuple(event.kind for event in result.events) == (
        "card_acquired",
        "intrigue_card_drawn",
    )


def test_strike_fleet_acquisition_opens_and_resolves_spy_placement() -> None:
    state = _reveal_state(
        _instance("convincing_argument", 0),
        _instance("convincing_argument", 1),
        _instance("diplomacy"),
    )
    instances = imperium_deck_instance_ids(False)
    strike_fleet = next(card for card in instances if ":strike_fleet:" in card)
    others = tuple(card for card in instances if card != strike_fleet)
    state = replace(
        state,
        imperium_row=(strike_fleet, *others[:4]),
        imperium_deck=others[4:],
    )
    engine = UprisingRulesEngine()
    acquire = next(
        action
        for action in engine.legal_actions(state, 0)
        if dict(action.arguments).get("instance_id") == strike_fleet
    )

    acquired = engine.apply(state, acquire)
    choices = legal_acquisition_spy_actions(acquired.state, 0)
    placed = apply_acquisition_spy_action(acquired.state, choices[0])
    post_id = dict(choices[0].arguments)["post_id"]

    assert acquired.state.players[0].discard_pile == (strike_fleet,)
    assert {action.action_id for action in choices} == {"place_acquisition_spy"}
    assert placed.state.players[0].spies_supply == 2
    assert placed.state.players[0].spy_post_ids == (post_id,)
    assert dict(placed.state.decision_stack[-1].context)["persuasion"] == 0


def test_guild_spy_acquisition_opens_spy_placement() -> None:
    state = _reveal_state(
        _instance("convincing_argument", 0),
        _instance("diplomacy"),
    )
    instances = imperium_deck_instance_ids(False)
    guild_spy = next(card for card in instances if ":guild_spy:" in card)
    others = tuple(card for card in instances if card != guild_spy)
    state = replace(
        state,
        imperium_row=(guild_spy, *others[:4]),
        imperium_deck=others[4:],
    )
    acquire = next(
        action
        for action in UprisingRulesEngine().legal_actions(state, 0)
        if dict(action.arguments).get("instance_id") == guild_spy
    )

    acquired = UprisingRulesEngine().apply(state, acquire)

    assert acquired.state.players[0].discard_pile == (guild_spy,)
    assert {
        action.action_id
        for action in legal_acquisition_spy_actions(acquired.state, 0)
    } == {"place_acquisition_spy"}


def test_guild_spy_gains_influence_for_spied_factions_on_spice_must_flow() -> None:
    guild_spy = next(
        card for card in imperium_deck_instance_ids(False) if ":guild_spy:" in card
    )
    state = _reveal_state(
        guild_spy,
        _instance("convincing_argument", 0),
        _instance("convincing_argument", 1),
        _instance("dune_the_desert_planet", 0),
        _instance("dune_the_desert_planet", 1),
        _instance("diplomacy"),
    )
    owner = replace(
        state.players[0],
        spies_supply=1,
        spy_post_ids=(
            "emperor-sardaukar-dutiful-service",
            "spacing-guild-heighliner-deliver-supplies",
        ),
    )
    state = replace(state, players=(owner, *state.players[1:]))
    action = next(
        action
        for action in legal_reserve_acquisitions(state, 0)
        if dict(action.arguments)["card_id"] == "the_spice_must_flow"
    )

    result = apply_reserve_acquisition(state, action)
    influence = result.state.players[0].influence

    assert influence.emperor == 1
    assert influence.spacing_guild == 1
    assert influence.bene_gesserit == 0
    assert influence.fremen == 0
    assert [event.kind for event in result.events] == [
        "card_acquired",
        "influence_gained",
        "influence_gained",
    ]


def test_strike_fleet_acquisition_recalls_before_placing_with_empty_supply() -> None:
    state = _reveal_state(
        _instance("convincing_argument", 0),
        _instance("convincing_argument", 1),
        _instance("diplomacy"),
    )
    instances = imperium_deck_instance_ids(False)
    strike_fleet = next(card for card in instances if ":strike_fleet:" in card)
    others = tuple(card for card in instances if card != strike_fleet)
    posts = (
        "arrakis-hagga-basin",
        "arrakis-deep-desert",
        "bene-gesserit-espionage-secrets",
    )
    owner = replace(state.players[0], spies_supply=0, spy_post_ids=posts)
    state = replace(
        state,
        players=(owner, *state.players[1:]),
        imperium_row=(strike_fleet, *others[:4]),
        imperium_deck=others[4:],
    )
    acquire = next(
        action
        for action in UprisingRulesEngine().legal_actions(state, 0)
        if dict(action.arguments).get("instance_id") == strike_fleet
    )

    acquired = apply_imperium_acquisition(state, acquire).state
    recall = legal_acquisition_spy_actions(acquired, 0)[0]
    recalled = apply_acquisition_spy_action(acquired, recall)
    placement = next(
        action
        for action in legal_acquisition_spy_actions(recalled.state, 0)
        if dict(action.arguments)["post_id"] == dict(recall.arguments)["post_id"]
    )
    replaced = apply_acquisition_spy_action(recalled.state, placement)

    assert recalled.events[0].kind == "spy_recalled"
    assert replaced.state.players[0].spies_supply == 0
    assert set(replaced.state.players[0].spy_post_ids) == set(posts)
    assert dict(replaced.state.decision_stack[-1].context)["persuasion"] == 0
