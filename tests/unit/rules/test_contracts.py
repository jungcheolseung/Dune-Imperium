"""Tests for the CHOAM Module's public Contract market."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
    canonical_state_hash,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.acquisition import (
    apply_reserve_acquisition,
    legal_reserve_acquisitions,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.contracts import (
    apply_contract_action,
    begin_contract_gain,
    legal_contract_actions,
    legal_contract_completion_actions,
)


def _state(
    *,
    market: tuple[str, ...] = (
        "contract:arrakeen_i",
        "contract:high_council_ii",
    ),
    bank: tuple[str, ...] = ("contract:research_station_i",),
) -> GameState:
    return GameState(
        config=RulesetConfig(choam_module=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=tuple(PlayerState(player_id=seat) for seat in range(4)),
        contract_bank=bank,
        face_up_contract_ids=market,
    )


def _agent_contract_state(
    card_id: str,
    *contract_ids: str,
    resources: Resources | None = None,
    spy_post_ids: tuple[str, ...] = (),
    deck: tuple[str, ...] = (),
) -> GameState:
    owner = PlayerState(
        player_id=0,
        resources=resources or Resources(solari=10, spice=10, water=10),
        deck=deck,
        hand=(card_id,),
        spies_supply=3 - len(spy_post_ids),
        spy_post_ids=spy_post_ids,
        active_contract_ids=contract_ids,
    )
    return GameState(
        config=RulesetConfig(choam_module=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _imperium_instance(card_id: str) -> str:
    return next(
        instance_id
        for instance_id in imperium_deck_instance_ids(True)
        if f":{card_id}:" in instance_id
    )


def _place_agent(state: GameState, space_id: str) -> GameState:
    action = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == space_id
    )
    return apply_agent_action(state, action).state


def test_contract_choice_takes_selected_tile_and_refills_the_same_position() -> None:
    state = begin_contract_gain(
        _state(),
        0,
        1,
        source="round:1:test",
    ).state
    actions = legal_contract_actions(state, 0)

    assert tuple(dict(action.arguments)["instance_id"] for action in actions) == (
        "contract:arrakeen_i",
        "contract:high_council_ii",
    )

    result = apply_contract_action(state, actions[0])

    assert result.state.players[0].active_contract_ids == ("contract:arrakeen_i",)
    assert result.state.face_up_contract_ids == (
        "contract:research_station_i",
        "contract:high_council_ii",
    )
    assert result.state.contract_bank == ()
    assert result.state.decision_stack == ()
    assert result.events[0].kind == "contract_taken"


def test_contract_market_shrinks_after_the_bank_is_empty() -> None:
    state = begin_contract_gain(
        _state(bank=()),
        2,
        1,
        source="round:1:test",
    ).state
    action = legal_contract_actions(state, 2)[1]

    result = apply_contract_action(state, action)

    assert result.state.face_up_contract_ids == ("contract:arrakeen_i",)
    assert result.state.players[2].active_contract_ids == ("contract:high_council_ii",)


def test_empty_market_converts_each_contract_icon_to_two_solari() -> None:
    result = begin_contract_gain(
        _state(market=(), bank=()),
        1,
        2,
        source="round:1:test",
    )

    assert result.state.players[1].resources.solari == 4
    assert result.state.decision_stack == ()
    assert result.events[0].kind == "contract_icons_converted_to_solari"


def test_immediate_contract_completes_and_grants_two_solari_when_taken() -> None:
    state = begin_contract_gain(
        _state(market=("contract:immediate",), bank=()),
        3,
        1,
        source="round:1:test",
    ).state

    result = apply_contract_action(state, legal_contract_actions(state, 3)[0])
    owner = result.state.players[3]

    assert owner.active_contract_ids == ()
    assert owner.completed_contract_ids == ("contract:immediate",)
    assert owner.resources.solari == 2
    assert [event.kind for event in result.events] == [
        "contract_taken",
        "contract_completed",
    ]


def test_engine_converts_a_second_icon_after_the_last_contract_is_taken() -> None:
    engine = UprisingRulesEngine()
    state = begin_contract_gain(
        _state(market=("contract:arrakeen_i",), bank=()),
        0,
        2,
        source="round:1:test",
    ).state
    action = legal_contract_actions(state, 0)[0]

    transition = engine.apply(state, action)

    assert transition.state.players[0].active_contract_ids == ("contract:arrakeen_i",)
    assert transition.state.players[0].resources.solari == 2
    assert transition.state.decision_stack == ()
    assert [event.kind for event in transition.events] == [
        "contract_taken",
        "contract_icons_converted_to_solari",
    ]


def test_contract_zones_reject_duplicates_and_module_off_state() -> None:
    state = _state()
    owner = replace(
        state.players[0],
        active_contract_ids=("contract:arrakeen_i",),
    )
    with pytest.raises(ValueError, match="two zones"):
        replace(state, players=(owner, *state.players[1:]))

    with pytest.raises(ValueError, match="CHOAM Module"):
        GameState(
            config=RulesetConfig(),
            seed=1,
            face_up_contract_ids=("contract:arrakeen_i",),
        )


def test_matching_space_contracts_are_mandatory_orderable_agent_effects() -> None:
    state = _agent_contract_state(
        "reserve:prepare_the_way:7",
        "contract:arrakeen_i",
        "contract:arrakeen_ii",
    )
    placed = _place_agent(state, "arrakeen")
    engine = UprisingRulesEngine()

    legal = engine.legal_actions(placed, 0)
    completion_ids = {
        dict(action.arguments)["instance_id"]
        for action in legal
        if action.action_id == "complete_contract"
    }

    assert completion_ids == {"contract:arrakeen_i", "contract:arrakeen_ii"}
    assert any(action.action_id == "resolve_board_effect" for action in legal)

    first_action = next(
        action
        for action in legal
        if dict(action.arguments).get("instance_id") == "contract:arrakeen_i"
    )
    first = engine.apply(placed, first_action).state
    second_action = next(
        action
        for action in engine.legal_actions(first, 0)
        if dict(action.arguments).get("instance_id") == "contract:arrakeen_ii"
    )
    second = engine.apply(first, second_action).state
    owner = second.players[0]

    assert owner.active_contract_ids == ()
    assert owner.completed_contract_ids == (
        "contract:arrakeen_i",
        "contract:arrakeen_ii",
    )
    assert owner.resources.water == 11
    assert owner.troops_garrison == 4
    assert {action.action_id for action in engine.legal_actions(second, 0)} == {
        "place_contract_spy"
    }
    placed_spy = engine.apply(
        second,
        engine.legal_actions(second, 0)[0],
    ).state
    assert placed_spy.players[0].spies_supply == 2
    assert len(placed_spy.players[0].spy_post_ids) == 1


def test_gather_intelligence_window_precedes_contract_completion() -> None:
    state = _agent_contract_state(
        "reserve:prepare_the_way:7",
        "contract:arrakeen_i",
        spy_post_ids=("arrakis-spice-refinery-arrakeen",),
    )
    placed = _place_agent(state, "arrakeen")
    engine = UprisingRulesEngine()

    assert {
        action.action_id for action in engine.legal_actions(placed, 0)
    } == {"decline_gather_intelligence"}

    declined = engine.apply(
        placed,
        next(
            action
            for action in engine.legal_actions(placed, 0)
            if action.action_id == "decline_gather_intelligence"
        ),
    ).state

    assert legal_contract_completion_actions(declined, 0)


def test_harvest_contracts_sum_maker_and_agent_card_spice() -> None:
    state = _agent_contract_state(
        _imperium_instance("desert_power"),
        "contract:harvest_3",
        "contract:harvest_4",
        resources=Resources(),
    )
    placed = _place_agent(state, "hagga_basin")
    engine = UprisingRulesEngine()

    assert not legal_contract_completion_actions(placed, 0)
    card_resolved = engine.apply(
        placed,
        next(
            action
            for action in engine.legal_actions(placed, 0)
            if action.action_id == "resolve_agent_card_effect"
        ),
    ).state
    assert card_resolved.players[0].resources.spice == 2
    assert not legal_contract_completion_actions(card_resolved, 0)

    harvested = engine.apply(
        card_resolved,
        next(
            action
            for action in engine.legal_actions(card_resolved, 0)
            if action.action_id == "harvest_maker_spice"
        ),
    ).state

    assert harvested.players[0].resources.spice == 4
    assert {
        dict(action.arguments)["instance_id"]
        for action in legal_contract_completion_actions(harvested, 0)
    } == {"contract:harvest_3", "contract:harvest_4"}

    first = engine.apply(
        harvested,
        next(
            action
            for action in legal_contract_completion_actions(harvested, 0)
            if dict(action.arguments)["instance_id"] == "contract:harvest_3"
        ),
    ).state
    second = engine.apply(
        first,
        legal_contract_completion_actions(first, 0)[0],
    ).state

    assert second.players[0].resources.solari == 7


def test_harvest_total_survives_spice_spent_later_in_the_agent_turn() -> None:
    state = _agent_contract_state(
        _imperium_instance("smuggler_s_haven"),
        "contract:harvest_4",
        resources=Resources(spice=4),
    )
    state = replace(
        state,
        maker_bonus_spice=(
            ("deep_desert", 0),
            ("hagga_basin", 2),
            ("imperial_basin", 0),
        ),
    )
    placed = _place_agent(state, "hagga_basin")
    engine = UprisingRulesEngine()
    harvested = engine.apply(
        placed,
        next(
            action
            for action in engine.legal_actions(placed, 0)
            if action.action_id == "harvest_maker_spice"
        ),
    ).state
    paid = engine.apply(
        harvested,
        next(
            action
            for action in engine.legal_actions(harvested, 0)
            if action.action_id == "pay_agent_card_spice"
        ),
    ).state

    assert paid.players[0].resources.spice == 4
    assert legal_contract_completion_actions(paid, 0)


def test_acquiring_the_spice_must_flow_completes_acquire_contract() -> None:
    owner = PlayerState(
        player_id=0,
        active_contract_ids=("contract:acquire",),
    )
    state = GameState(
        config=RulesetConfig(choam_module=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        reserve_stacks=(("the_spice_must_flow", 1),),
        decision_stack=(
            DecisionFrame(
                kind="reveal",
                frame_id="round:1:player:0:reveal",
                decision=PlayerDecision(owner=0, prompt="Resolve Reveal"),
                context=(
                    ("persuasion", 9),
                    ("revealed_card_count", 0),
                    ("strength", 0),
                    ("turn_owner", 0),
                ),
            ),
        ),
    )

    result = apply_reserve_acquisition(
        state,
        legal_reserve_acquisitions(state, 0)[0],
    )
    owner = result.state.players[0]

    assert owner.active_contract_ids == ()
    assert owner.completed_contract_ids == ("contract:acquire",)
    assert owner.resources.solari == 3
    assert owner.influence.spacing_guild == 1
    assert owner.victory_points == 2
    assert [event.kind for event in result.events][-2:] == [
        "contract_completed",
        "influence_gained",
    ]


def test_contract_reward_can_take_a_new_contract_without_retroactive_completion() -> (
    None
):
    state = _agent_contract_state(
        "player:0:starter:diplomacy:0",
        "contract:espionage_ii",
    )
    state = replace(
        state,
        face_up_contract_ids=("contract:high_council_i",),
        contract_bank=("contract:deliver_supplies",),
    )
    placed = _place_agent(state, "espionage")
    engine = UprisingRulesEngine()
    completed = engine.apply(
        placed,
        legal_contract_completion_actions(placed, 0)[0],
    ).state

    assert [
        dict(action.arguments)["instance_id"]
        for action in engine.legal_actions(completed, 0)
    ] == ["contract:high_council_i"]

    taken = engine.apply(
        completed,
        engine.legal_actions(completed, 0)[0],
    ).state
    owner = taken.players[0]

    assert owner.completed_contract_ids == ("contract:espionage_ii",)
    assert owner.active_contract_ids == ("contract:high_council_i",)
    assert not legal_contract_completion_actions(taken, 0)


def test_sardaukar_contract_draws_two_personal_cards() -> None:
    deck = starting_deck_instance_ids(0)[:2]
    state = _agent_contract_state(
        _imperium_instance("truthtrance"),
        "contract:sardaukar_i",
        deck=deck,
    )
    placed = _place_agent(state, "sardaukar")
    engine = UprisingRulesEngine()
    completed = engine.apply(
        placed,
        legal_contract_completion_actions(placed, 0)[0],
    ).state

    assert completed.players[0].hand == deck
    assert completed.players[0].deck == ()


def test_sardaukar_ii_contract_recalls_another_placed_agent() -> None:
    state = _agent_contract_state(
        _imperium_instance("truthtrance"),
        "contract:sardaukar_ii",
    )
    owner = replace(
        state.players[0],
        agents_available=1,
        agent_locations=("arrakeen",),
    )
    state = replace(state, players=(owner, *state.players[1:]))
    placed = _place_agent(state, "sardaukar")
    engine = UprisingRulesEngine()
    completed = engine.apply(
        placed,
        legal_contract_completion_actions(placed, 0)[0],
    ).state

    # The printed reward recalls one of your Agents, and the just-sent Agent
    # is not a valid target [Main p. 20].
    recall_actions = engine.legal_actions(completed, 0)
    assert [action.action_id for action in recall_actions] == [
        "recall_agent_for_contract"
    ]
    assert [
        dict(action.arguments)["space_id"] for action in recall_actions
    ] == ["arrakeen"]

    recalled = engine.apply(completed, recall_actions[0]).state
    resolved = recalled.players[0]

    assert resolved.agents_available == 1
    assert resolved.agent_locations == ("sardaukar",)
    assert resolved.completed_contract_ids == ("contract:sardaukar_ii",)


def test_sardaukar_ii_recall_does_nothing_without_another_agent() -> None:
    state = _agent_contract_state(
        _imperium_instance("truthtrance"),
        "contract:sardaukar_ii",
    )
    placed = _place_agent(state, "sardaukar")
    engine = UprisingRulesEngine()
    transition = engine.apply(
        placed,
        legal_contract_completion_actions(placed, 0)[0],
    )

    assert any(
        event.kind == "contract_recall_unavailable" for event in transition.events
    )
    assert transition.state.decision_stack[-1].kind == "agent_effects"
    assert transition.state.players[0].completed_contract_ids == (
        "contract:sardaukar_ii",
    )


def test_contract_troops_increase_combat_deployment_limit() -> None:
    state = _agent_contract_state(
        _imperium_instance("truthtrance"),
        "contract:heighliner_ii",
    )
    placed = _place_agent(state, "heighliner")
    engine = UprisingRulesEngine()
    completed = engine.apply(
        placed,
        legal_contract_completion_actions(placed, 0)[0],
    ).state
    deployment_counts = {
        dict(action.arguments)["count"]
        for action in engine.legal_actions(completed, 0)
        if action.action_id == "deploy_troops"
    }

    assert completed.players[0].troops_garrison == 5
    assert deployment_counts == {0, 1, 2, 3, 4}


def test_contract_completion_actions_replay_from_the_same_state() -> None:
    initial = _agent_contract_state(
        "reserve:prepare_the_way:7",
        "contract:high_council_ii",
    )
    placement = next(
        action
        for action in legal_agent_actions(initial, 0)
        if dict(action.arguments)["space_id"] == "high_council"
    )
    steps = (
        placement,
        DomainAction(
            action_id="complete_contract",
            actor=0,
            arguments=(("instance_id", "contract:high_council_ii"),),
        ),
    )
    engine = UprisingRulesEngine()

    def play() -> GameState:
        state = initial
        for step in steps:
            state = engine.apply(state, step).state
        return state

    first = play()
    second = play()

    assert canonical_state_hash(first) == canonical_state_hash(second)
    assert first == second
