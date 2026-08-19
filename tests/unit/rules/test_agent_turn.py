"""Tests for Agent-turn legal action enumeration."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import (
    starting_card_for_instance,
    starting_deck_instance_ids,
)
from dune_imperium.content.uprising.types import AgentIcon
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
from dune_imperium.rules.agent_turn import (
    apply_agent_action,
    card_can_access_space,
    legal_agent_actions,
)


def _instance(player: int, card_id: str) -> str:
    return next(
        instance_id
        for instance_id in starting_deck_instance_ids(player)
        if f":{card_id}:" in instance_id
    )


def _imperium_instance(card_id: str) -> str:
    return next(
        instance_id
        for instance_id in imperium_deck_instance_ids(False)
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


def test_prepare_the_way_uses_its_landsraad_and_city_icons() -> None:
    owner = PlayerState(
        player_id=0,
        hand=("reserve:prepare_the_way:7",),
        resources=Resources(solari=10, spice=10, water=10),
    )
    state = _state(owner=owner)

    assert _space_ids(state) == {
        "arrakeen",
        "assembly_hall",
        "gather_support",
        "high_council",
        "research_station",
        "spice_refinery",
        "swordmaster",
    }


def test_transcribed_imperium_icons_enable_agent_destinations() -> None:
    maula = _imperium_instance("maula_pistol")
    truthtrance = _imperium_instance("truthtrance")

    maula_spaces = _space_ids(_state(maula))
    truthtrance_spaces = _space_ids(_state(truthtrance))

    assert maula_spaces == {
        "accept_contract",
        "arrakeen",
        "hagga_basin",
        "imperial_basin",
        "spice_refinery",
    }
    assert "dutiful_service" in truthtrance_spaces
    assert "deliver_supplies" in truthtrance_spaces
    assert "secrets" in truthtrance_spaces
    assert "fremkit" in truthtrance_spaces
    assert "assembly_hall" not in truthtrance_spaces


def test_sardaukar_soldier_uses_its_city_icon() -> None:
    sardaukar = _imperium_instance("sardaukar_soldier")

    assert _space_ids(_state(sardaukar)) == {"arrakeen", "spice_refinery"}


def test_hidden_missive_uses_its_landsraad_icon() -> None:
    hidden_missive = _imperium_instance("hidden_missive")

    assert _space_ids(_state(hidden_missive)) == {"assembly_hall", "gather_support"}


def test_desert_survival_uses_its_spice_trade_icon() -> None:
    desert_survival = _imperium_instance("desert_survival")

    assert _space_ids(_state(desert_survival)) == {
        "accept_contract",
        "hagga_basin",
        "imperial_basin",
    }


def test_smugglers_harvester_uses_its_spice_trade_icon() -> None:
    harvester = _imperium_instance("smuggler_s_harvester")

    assert _space_ids(_state(harvester)) == {
        "accept_contract",
        "hagga_basin",
        "imperial_basin",
    }


def test_fedaykin_stilltent_uses_its_spice_trade_icon() -> None:
    stilltent = _imperium_instance("fedaykin_stilltent")

    assert _space_ids(_state(stilltent)) == {
        "accept_contract",
        "hagga_basin",
        "imperial_basin",
    }


def test_northern_watermaster_uses_its_city_icon() -> None:
    watermaster = _imperium_instance("northern_watermaster")

    assert _space_ids(_state(watermaster)) == {"arrakeen", "spice_refinery"}


def test_spy_agent_icon_accesses_only_spaces_connected_to_an_owned_spy() -> None:
    owner = PlayerState(
        player_id=0,
        spies_supply=2,
        spy_post_ids=("arrakis-spice-refinery-arrakeen",),
    )

    assert card_can_access_space(
        (AgentIcon.SPY,), BOARD_SPACES_BY_ID["arrakeen"], owner
    )
    assert card_can_access_space(
        (AgentIcon.SPY,), BOARD_SPACES_BY_ID["spice_refinery"], owner
    )
    assert not card_can_access_space(
        (AgentIcon.SPY,), BOARD_SPACES_BY_ID["assembly_hall"], owner
    )


def test_spy_agent_icon_does_not_recall_the_spy_for_destination_access() -> None:
    owner = PlayerState(
        player_id=0,
        spies_supply=2,
        spy_post_ids=("arrakis-spice-refinery-arrakeen",),
    )

    assert (
        card_can_access_space(
            (AgentIcon.CITY, AgentIcon.SPY),
            BOARD_SPACES_BY_ID["imperial_basin"],
            owner,
        )
        is False
    )
    assert owner.spies_supply == 2
    assert owner.spy_post_ids == ("arrakis-spice-refinery-arrakeen",)


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


def test_infiltrate_adds_occupied_destination_with_connected_spy_choice() -> None:
    dagger = _instance(0, "dagger")
    owner = PlayerState(
        player_id=0,
        hand=(dagger,),
        spies_supply=2,
        spy_post_ids=("landsraad-assembly-hall-gather-support",),
    )
    state = _state(owner=owner)
    opponent = replace(
        state.players[1],
        agents_available=1,
        agent_locations=("assembly_hall",),
    )
    state = replace(state, players=(state.players[0], opponent, *state.players[2:]))

    action = _action_to(state, "assembly_hall")

    assert dict(action.arguments)["infiltrate_post_id"] == (
        "landsraad-assembly-hall-gather-support"
    )
    assert "gather_support" in _space_ids(state)


def test_infiltrate_does_not_bypass_icon_or_connection_requirements() -> None:
    dagger = _instance(0, "dagger")
    owner = PlayerState(
        player_id=0,
        hand=(dagger,),
        spies_supply=2,
        spy_post_ids=("arrakis-spice-refinery-arrakeen",),
    )
    state = _state(owner=owner)
    opponents = tuple(
        replace(
            candidate,
            agents_available=1,
            agent_locations=("assembly_hall",),
        )
        if candidate.player_id == 1
        else candidate
        for candidate in state.players
    )

    assert "assembly_hall" not in _space_ids(replace(state, players=opponents))


def test_infiltrate_defers_space_with_multiple_opposing_agents() -> None:
    dagger = _instance(0, "dagger")
    owner = PlayerState(
        player_id=0,
        hand=(dagger,),
        spies_supply=2,
        spy_post_ids=("landsraad-assembly-hall-gather-support",),
    )
    state = _state(owner=owner)
    opponents = tuple(
        replace(
            candidate,
            agents_available=1,
            agent_locations=("assembly_hall",),
        )
        if candidate.player_id in (1, 2)
        else candidate
        for candidate in state.players
    )

    assert "assembly_hall" not in _space_ids(replace(state, players=opponents))


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


def test_infiltrate_recalls_selected_spy_and_consumes_its_gather_window() -> None:
    reconnaissance = _instance(0, "reconnaissance")
    post_id = "arrakis-spice-refinery-arrakeen"
    owner = PlayerState(
        player_id=0,
        hand=(reconnaissance,),
        spies_supply=2,
        spy_post_ids=(post_id,),
    )
    state = _state(owner=owner)
    opponent = replace(
        state.players[1],
        agents_available=1,
        agent_locations=("arrakeen",),
    )
    state = replace(state, players=(state.players[0], opponent, *state.players[2:]))

    result = apply_agent_action(state, _action_to(state, "arrakeen"))
    next_owner = result.state.players[0]
    context = dict(result.state.decision_stack[-1].context)

    assert next_owner.spies_supply == 3
    assert next_owner.spy_post_ids == ()
    assert context["pending_gather_intelligence"] is False
    assert tuple(event.kind for event in result.events) == (
        "agent_placed",
        "spy_recalled_for_infiltrate",
    )
    assert result.events[1].payload == (
        ("player", 0),
        ("post_id", post_id),
        ("space_id", "arrakeen"),
    )


def test_critical_location_visit_pays_the_opposing_controller() -> None:
    reconnaissance = _instance(0, "reconnaissance")
    state = _state(reconnaissance)
    controller = replace(
        state.players[1],
        control_space_ids=("arrakeen",),
    )
    state = replace(
        state,
        players=(state.players[0], controller, *state.players[2:]),
    )

    result = apply_agent_action(state, _action_to(state, "arrakeen"))

    assert result.state.players[1].resources.solari == 1
    assert tuple(event.kind for event in result.events) == (
        "agent_placed",
        "control_bonus_gained",
    )
    assert result.events[1].payload == (
        ("amount", 1),
        ("player", 1),
        ("resource", "solari"),
        ("space_id", "arrakeen"),
    )


def test_controller_gains_bonus_when_visiting_their_own_imperial_basin() -> None:
    dune = _instance(0, "dune_the_desert_planet")
    owner = PlayerState(
        player_id=0,
        hand=(dune,),
        control_space_ids=("imperial_basin",),
    )
    state = _state(owner=owner)

    result = apply_agent_action(
        state,
        _action_to(state, "imperial_basin"),
    )

    assert result.state.players[0].resources.spice == 1


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
