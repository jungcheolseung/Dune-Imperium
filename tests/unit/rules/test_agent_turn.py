"""Tests for Agent-turn legal action enumeration."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.starting_cards import (
    starting_card_for_instance,
    starting_deck_instance_ids,
)
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
    canonical_state_hash,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions


def _instance(player: int, card_id: str) -> str:
    return next(
        instance_id
        for instance_id in starting_deck_instance_ids(player)
        if f":{card_id}:" in instance_id
    )


def _state(*cards: str, owner: PlayerState | None = None) -> GameState:
    player = owner or PlayerState(player_id=0, hand=cards)
    players = (player, *(PlayerState(player_id=seat) for seat in range(1, 4)))
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        players=players,
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _space_ids(state: GameState) -> set[str]:
    return {
        str(dict(action.arguments)["space_id"])
        for action in legal_agent_actions(state, 0)
    }


def _action_to(
    state: GameState,
    space_id: str,
    cost_option: int | None = None,
) -> DomainAction:
    return next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == space_id
        and (
            cost_option is None
            or dict(action.arguments).get("cost_option") == cost_option
        )
    )


def test_instance_ids_resolve_to_starting_card_definitions() -> None:
    dagger = _instance(0, "dagger")

    assert starting_card_for_instance(dagger).card.card_id == "dagger"


def test_card_icons_limit_agent_destinations() -> None:
    state = _state(_instance(0, "dagger"))

    assert _space_ids(state) == {"assembly_hall", "gather_support"}


def test_costs_and_influence_requirements_filter_spaces() -> None:
    dune = _instance(0, "dune_the_desert_planet")
    state = _state(dune)

    assert _space_ids(state) == {
        "accept_contract",
        "hagga_basin",
        "imperial_basin",
    }

    funded = PlayerState(
        player_id=0,
        hand=(dune,),
        resources=Resources(spice=3, water=3),
        influence=Influence(spacing_guild=2),
    )
    assert _space_ids(_state(owner=funded)) == {
        "accept_contract",
        "deep_desert",
        "hagga_basin",
        "imperial_basin",
        "shipping",
    }


def test_occupied_spaces_and_non_agent_cards_are_excluded() -> None:
    dagger = _instance(0, "dagger")
    argument = _instance(0, "convincing_argument")
    state = _state(dagger, argument)
    opponent = replace(
        state.players[1],
        agents_available=1,
        agent_locations=("assembly_hall",),
    )
    state = replace(state, players=(state.players[0], opponent, *state.players[2:]))

    assert _space_ids(state) == {"gather_support"}


def test_only_current_decision_owner_receives_agent_actions() -> None:
    state = _state(_instance(0, "dagger"))

    assert legal_agent_actions(state, 1) == ()
    assert legal_agent_actions(replace(state, phase=GamePhase.COMBAT), 0) == ()


def test_swordmaster_uses_the_current_dynamic_cost() -> None:
    dagger = _instance(0, "dagger")
    owner = PlayerState(
        player_id=0,
        hand=(dagger,),
        resources=Resources(solari=6),
    )
    state = _state(owner=owner)

    assert "swordmaster" not in _space_ids(state)

    opponent = replace(state.players[1], swordmaster_acquired=True, agents_available=3)
    state = replace(state, players=(state.players[0], opponent, *state.players[2:]))
    assert "swordmaster" in _space_ids(state)


def test_player_who_has_swordmaster_cannot_visit_its_space_again() -> None:
    dagger = _instance(0, "dagger")
    owner = PlayerState(
        player_id=0,
        hand=(dagger,),
        resources=Resources(solari=8),
        agents_available=3,
        swordmaster_acquired=True,
    )

    assert "swordmaster" not in _space_ids(_state(owner=owner))


def test_agent_action_pays_cost_and_moves_agent_and_card() -> None:
    dune = _instance(0, "dune_the_desert_planet")
    state = _state(dune)

    result = apply_agent_action(state, _action_to(state, "hagga_basin"))
    owner = result.state.players[0]

    assert owner.resources.water == 0
    assert owner.agents_available == 1
    assert owner.agent_locations == ("hagga_basin",)
    assert owner.hand == ()
    assert owner.in_play == (dune,)
    assert result.events[0].kind == "agent_placed"
    assert result.events[0].payload == (
        ("card_id", dune),
        ("player", 0),
        ("space_id", "hagga_basin"),
    )


def test_selected_cost_option_is_paid_and_recorded_for_effect_resolution() -> None:
    dagger = _instance(0, "dagger")
    owner = PlayerState(
        player_id=0,
        hand=(dagger,),
        resources=Resources(solari=2),
    )
    state = _state(owner=owner)

    result = apply_agent_action(state, _action_to(state, "gather_support", 1))
    context = dict(result.state.decision_stack[-1].context)

    assert result.state.players[0].resources.solari == 0
    assert context["cost_option"] == 1


def test_agent_effect_frame_preserves_freely_ordered_effect_groups() -> None:
    seek_allies = _instance(0, "seek_allies")
    state = _state(seek_allies)

    result = apply_agent_action(state, _action_to(state, "dutiful_service"))
    frame = result.state.decision_stack[-1]
    context = dict(frame.context)

    assert isinstance(frame.decision, PlayerDecision)
    assert frame.decision.owner == 0
    assert context["pending_agent_effect"] is True
    assert context["pending_board_effect"] is True
    assert context["pending_faction_influence"] is True
    assert context["space_id"] == "dutiful_service"


def test_agent_action_rejects_unlisted_action_without_mutating_state() -> None:
    dagger = _instance(0, "dagger")
    state = _state(dagger)
    before = canonical_state_hash(state)
    action = _action_to(state, "assembly_hall")
    invalid = replace(
        action,
        arguments=(("card_id", dagger), ("space_id", "sardaukar")),
    )

    with pytest.raises(ValueError, match="not a legal Agent turn"):
        apply_agent_action(state, invalid)

    assert canonical_state_hash(state) == before
