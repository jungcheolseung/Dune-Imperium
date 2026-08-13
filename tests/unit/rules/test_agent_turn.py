"""Tests for Agent-turn legal action enumeration."""

from dataclasses import replace

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.starting_cards import (
    starting_card_for_instance,
    starting_deck_instance_ids,
)
from dune_imperium.core import (
    DecisionFrame,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules.agent_turn import legal_agent_actions


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
