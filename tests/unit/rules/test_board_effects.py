"""Tests for typed automatic board-space effects."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    ChanceDecision,
    ChanceOutcome,
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
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import (
    apply_espionage_action,
    apply_maker_space_action,
    apply_sietch_tabr_action,
    board_effects_for,
    legal_espionage_actions,
    legal_maker_space_actions,
    legal_sietch_tabr_actions,
    resolve_board_effect,
)
from dune_imperium.rules.contracts import legal_contract_actions
from dune_imperium.rules.effects import (
    DrawImperiumCardsEffect,
    DrawIntrigueCardsEffect,
    GainResourcesEffect,
    RecruitTroopsEffect,
)


def _instance(card_id: str) -> str:
    return next(
        instance_id
        for instance_id in starting_deck_instance_ids(0)
        if f":{card_id}:" in instance_id
    )


def _state(card_id: str, resources: Resources | None = None) -> GameState:
    card = _instance(card_id)
    starting_resources = resources or Resources()
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        players=(
            PlayerState(player_id=0, hand=(card,), resources=starting_resources),
            *(PlayerState(player_id=seat) for seat in range(1, 4)),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


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


def test_first_resource_board_effects_are_typed() -> None:
    state = _state("diplomacy")

    assert board_effects_for(state, "dutiful_service", 0) == (
        GainResourcesEffect(solari=2),
    )
    assert board_effects_for(state, "deliver_supplies", 0) == (
        GainResourcesEffect(water=1),
    )
    assert board_effects_for(state, "spice_refinery", 1) == (
        GainResourcesEffect(solari=4),
    )


def test_accept_contract_draws_and_opens_the_choam_market_choice() -> None:
    state = _state("dune_the_desert_planet")
    drawn = _instance("dagger")
    owner = replace(state.players[0], deck=(drawn,))
    state = replace(
        state,
        config=RulesetConfig(choam_module=True),
        players=(owner, *state.players[1:]),
        contract_bank=("contract:research_station_i",),
        face_up_contract_ids=(
            "contract:arrakeen_i",
            "contract:high_council_ii",
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "accept_contract")).state

    result = resolve_board_effect(placed)

    assert result.state.players[0].hand == (drawn,)
    assert len(legal_contract_actions(result.state, 0)) == 2
    assert result.events[-1].kind == "board_effect_resolved"


def test_dutiful_service_resolves_board_reward_and_keeps_faction_pending() -> None:
    state = _state("diplomacy")
    placed = apply_agent_action(state, _action_to(state, "dutiful_service")).state

    result = resolve_board_effect(placed)
    context = dict(result.state.decision_stack[-1].context)

    assert result.state.players[0].resources.solari == 2
    assert context["pending_board_effect"] is False
    assert context["pending_faction_influence"] is True
    assert result.events[0].kind == "board_effect_resolved"


def test_spice_refinery_reward_depends_on_already_paid_option() -> None:
    state = _state("signet_ring", Resources(spice=1))
    action = _action_to(state, "spice_refinery", cost_option=1)
    placed = apply_agent_action(state, action).state

    resolved = resolve_board_effect(placed).state

    assert resolved.players[0].resources.spice == 0
    assert resolved.players[0].resources.solari == 4


def test_unimplemented_or_already_resolved_board_effect_is_rejected() -> None:
    state = _state("diplomacy")
    placed = apply_agent_action(state, _action_to(state, "desert_tactics")).state
    before = canonical_state_hash(placed)

    with pytest.raises(NotImplementedError, match="desert_tactics"):
        resolve_board_effect(placed)
    assert canonical_state_hash(placed) == before

    dutiful = apply_agent_action(
        state,
        _action_to(state, "dutiful_service"),
    ).state
    resolved = resolve_board_effect(dutiful).state
    with pytest.raises(ValueError, match="no pending"):
        resolve_board_effect(resolved)


def test_draw_and_recruit_board_effects_are_typed() -> None:
    state = _state("diplomacy")

    assert board_effects_for(state, "fremkit", 0) == (DrawImperiumCardsEffect(1),)
    assert board_effects_for(state, "assembly_hall", 0) == (DrawIntrigueCardsEffect(1),)
    assert board_effects_for(state, "research_station", 0) == (
        RecruitTroopsEffect(2),
        DrawImperiumCardsEffect(2),
    )


def test_fremkit_draws_a_card_and_leaves_combat_deployment_pending() -> None:
    state = _state("diplomacy")
    drawn = _instance("dagger")
    owner = replace(state.players[0], deck=(drawn,))
    state = replace(state, players=(owner, *state.players[1:]))
    placed = apply_agent_action(state, _action_to(state, "fremkit")).state

    resolved = resolve_board_effect(placed).state
    context = dict(resolved.decision_stack[-1].context)

    assert resolved.players[0].hand == (drawn,)
    assert resolved.players[0].deck == ()
    assert context["pending_board_effect"] is False
    assert context["pending_combat_deployment"] is True


def test_arrakeen_recruits_a_troop_and_draws_a_card() -> None:
    state = _state("reconnaissance")
    drawn = _instance("dagger")
    owner = replace(state.players[0], deck=(drawn,))
    state = replace(state, players=(owner, *state.players[1:]))
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    resolved = resolve_board_effect(placed).state
    owner = resolved.players[0]
    context = dict(resolved.decision_stack[-1].context)

    assert owner.hand == (drawn,)
    assert owner.troops_supply == 8
    assert owner.troops_garrison == 4
    assert context["troops_recruited"] == 1
    assert context["pending_combat_deployment"] is True


def test_assembly_hall_draws_hidden_intrigue() -> None:
    state = _state("dagger")
    state = replace(state, intrigue_deck=("intrigue:first", "intrigue:second"))
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state

    resolved = resolve_board_effect(placed).state

    assert resolved.players[0].intrigue_cards == ("intrigue:first",)
    assert resolved.intrigue_deck == ("intrigue:second",)


def _espionage_state(*, spies_supply: int = 3) -> tuple[GameState, str]:
    state = _state("diplomacy", Resources(spice=1))
    drawn = _instance("dagger")
    spy_post_ids = (
        "emperor-sardaukar-dutiful-service",
        "landsraad-assembly-hall-gather-support",
        "arrakis-imperial-basin",
    )[: 3 - spies_supply]
    owner = replace(
        state.players[0],
        deck=(drawn,),
        spies_supply=spies_supply,
        spy_post_ids=spy_post_ids,
    )
    state = replace(state, players=(owner, *state.players[1:]))
    return apply_agent_action(state, _action_to(state, "espionage")).state, drawn


def test_espionage_draws_card_and_can_place_spy() -> None:
    state, drawn = _espionage_state()
    actions = legal_espionage_actions(state, 0)
    placement = next(
        action
        for action in actions
        if action.action_id == "resolve_espionage_place_spy"
    )
    post_id = dict(placement.arguments)["post_id"]

    result = apply_espionage_action(state, placement)
    owner = result.state.players[0]
    context = dict(result.state.decision_stack[-1].context)

    assert drawn in owner.hand
    assert owner.spies_supply == 2
    assert post_id in owner.spy_post_ids
    assert context["pending_board_effect"] is False
    assert context["pending_faction_influence"] is True
    assert tuple(event.kind for event in result.events) == (
        "spy_placed",
        "board_effect_resolved",
    )


def test_espionage_can_decline_spy_and_still_draw_card() -> None:
    state, drawn = _espionage_state()
    decline = next(
        action
        for action in legal_espionage_actions(state, 0)
        if action.action_id == "resolve_espionage_without_spy"
    )

    resolved = apply_espionage_action(state, decline).state

    assert drawn in resolved.players[0].hand
    assert resolved.players[0].spies_supply == 3
    assert resolved.players[0].spy_post_ids == ()


def test_espionage_reshuffles_discard_before_drawing() -> None:
    state, drawn = _espionage_state()
    owner = replace(state.players[0], deck=(), discard_pile=(drawn,))
    state = replace(state, players=(owner, *state.players[1:]))
    engine = UprisingRulesEngine()
    decline = next(
        action
        for action in engine.legal_actions(state, 0)
        if action.action_id == "resolve_espionage_without_spy"
    )

    pending = engine.apply(state, decline).state
    decision = engine.current_decision(pending)
    assert isinstance(decision, ChanceDecision)
    finished = engine.apply(
        pending,
        ChanceOutcome(decision.decision_id, (drawn,)),
    ).state

    assert finished.players[0].hand == (drawn,)
    assert finished.players[0].discard_pile == ()


def test_espionage_recall_commits_to_a_replacement_when_supply_is_empty() -> None:
    state, drawn = _espionage_state(spies_supply=0)
    recall_actions = legal_espionage_actions(state, 0)
    recalled_post = dict(recall_actions[0].arguments)["post_id"]

    recalled = apply_espionage_action(state, recall_actions[0])
    replacement_actions = legal_espionage_actions(recalled.state, 0)

    assert {action.action_id for action in recall_actions} == {
        "recall_spy_for_espionage"
    }
    assert {action.action_id for action in replacement_actions} == {
        "resolve_espionage_place_spy"
    }
    assert recalled_post not in recalled.state.players[0].spy_post_ids
    assert recalled.state.players[0].spies_supply == 1
    assert recalled.events[0].kind == "spy_recalled"

    resolved = apply_espionage_action(recalled.state, replacement_actions[0]).state
    owner = resolved.players[0]

    assert drawn in owner.hand
    assert owner.spies_supply == 0
    assert len(owner.spy_post_ids) == 3


def test_first_high_council_visit_grants_seat_without_repeat_rewards() -> None:
    state = _state("dagger", Resources(solari=5))
    placed = apply_agent_action(state, _action_to(state, "high_council")).state

    resolved = resolve_board_effect(placed).state
    owner = resolved.players[0]

    assert owner.high_council is True
    assert owner.resources.spice == 0
    assert owner.intrigue_cards == ()
    assert owner.troops_garrison == 3


def test_high_council_revisit_grants_spice_intrigue_and_troops() -> None:
    state = _state("dagger", Resources(solari=5))
    owner = replace(state.players[0], high_council=True)
    state = replace(
        state,
        players=(owner, *state.players[1:]),
        intrigue_deck=("intrigue:first",),
    )
    placed = apply_agent_action(state, _action_to(state, "high_council")).state

    resolved = resolve_board_effect(placed).state
    owner = resolved.players[0]

    assert owner.resources.spice == 2
    assert owner.intrigue_cards == ("intrigue:first",)
    assert owner.troops_supply == 6
    assert owner.troops_garrison == 6


def test_swordmaster_is_available_immediately_after_acquisition() -> None:
    state = _state("dagger", Resources(solari=8))
    placed = apply_agent_action(state, _action_to(state, "swordmaster")).state

    resolved = resolve_board_effect(placed).state
    owner = resolved.players[0]

    assert owner.swordmaster_acquired is True
    assert owner.agents_available == 2
    assert owner.agent_locations == ("swordmaster",)


def test_gather_support_recruits_available_troops_and_finishes_turn() -> None:
    state = _state("dagger")
    placed = apply_agent_action(state, _action_to(state, "gather_support", 0)).state

    resolved = resolve_board_effect(placed).state
    owner = resolved.players[0]
    decision = resolved.decision_stack[-1].decision

    assert owner.troops_supply == 7
    assert owner.troops_garrison == 5
    assert isinstance(decision, PlayerDecision)
    assert decision.owner == 1


def _sietch_tabr_state() -> GameState:
    state = _state("signet_ring")
    owner = replace(state.players[0], influence=Influence(fremen=2))
    state = replace(state, players=(owner, *state.players[1:]))
    return apply_agent_action(state, _action_to(state, "sietch_tabr")).state


def test_sietch_tabr_supplies_grant_hooks_troop_and_water() -> None:
    state = _sietch_tabr_state()
    action = next(
        candidate
        for candidate in legal_sietch_tabr_actions(state, 0)
        if candidate.action_id == "take_sietch_tabr_supplies"
    )

    resolved = apply_sietch_tabr_action(state, action).state
    owner = resolved.players[0]
    context = dict(resolved.decision_stack[-1].context)

    assert owner.maker_hooks is True
    assert owner.resources.water == 2
    assert owner.troops_supply == 8
    assert owner.troops_garrison == 4
    assert context["troops_recruited"] == 1
    assert context["pending_board_effect"] is False
    assert context["pending_combat_deployment"] is True


def test_sietch_tabr_water_can_destroy_shield_wall() -> None:
    state = _sietch_tabr_state()
    actions = legal_sietch_tabr_actions(state, 0)

    assert {action.action_id for action in actions} == {
        "take_sietch_tabr_supplies",
        "take_sietch_tabr_water",
        "take_sietch_tabr_water_and_destroy_wall",
    }
    detonate = next(
        action
        for action in actions
        if action.action_id == "take_sietch_tabr_water_and_destroy_wall"
    )
    result = apply_sietch_tabr_action(state, detonate)

    assert result.state.players[0].resources.water == 2
    assert result.state.shield_wall_present is False
    assert tuple(event.kind for event in result.events) == (
        "shield_wall_destroyed",
        "board_effect_resolved",
    )


def test_sietch_tabr_omits_detonation_after_wall_is_destroyed() -> None:
    state = replace(_sietch_tabr_state(), shield_wall_present=False)

    assert {action.action_id for action in legal_sietch_tabr_actions(state, 0)} == {
        "take_sietch_tabr_supplies",
        "take_sietch_tabr_water",
    }


def _hagga_basin_state(*, wall_present: bool) -> GameState:
    state = _state("dune_the_desert_planet")
    owner = replace(state.players[0], maker_hooks=True)
    state = replace(
        state,
        players=(owner, *state.players[1:]),
        current_conflict_ids=("siege_of_arrakeen",),
        shield_wall_present=wall_present,
        maker_bonus_spice=(
            ("deep_desert", 0),
            ("hagga_basin", 3),
            ("imperial_basin", 0),
        ),
    )
    return apply_agent_action(state, _action_to(state, "hagga_basin")).state


def test_shield_wall_removes_sandworm_choice_from_protected_conflict() -> None:
    state = _hagga_basin_state(wall_present=True)

    assert tuple(
        action.action_id for action in legal_maker_space_actions(state, 0)
    ) == ("harvest_maker_spice",)


def test_maker_space_can_summon_worm_and_collect_bonus_after_detonation() -> None:
    state = _hagga_basin_state(wall_present=False)
    actions = legal_maker_space_actions(state, 0)
    summon = next(
        action for action in actions if action.action_id == "summon_maker_sandworms"
    )

    resolved = apply_maker_space_action(state, summon).state

    assert resolved.players[0].sandworms_conflict == 1
    assert resolved.players[0].resources.spice == 3
    assert dict(resolved.maker_bonus_spice)["hagga_basin"] == 0
    assert (
        dict(resolved.decision_stack[-1].context)["pending_combat_deployment"] is True
    )


def test_maker_spice_choice_collects_base_and_accumulated_spice() -> None:
    state = _hagga_basin_state(wall_present=True)
    harvest = legal_maker_space_actions(state, 0)[0]

    resolved = apply_maker_space_action(state, harvest).state

    assert resolved.players[0].resources.spice == 5
    assert resolved.players[0].sandworms_conflict == 0
    assert dict(resolved.maker_bonus_spice)["hagga_basin"] == 0


def test_deep_desert_summons_two_sandworms() -> None:
    state = _state("dune_the_desert_planet", Resources(water=3))
    owner = replace(state.players[0], maker_hooks=True)
    state = replace(
        state,
        players=(owner, *state.players[1:]),
        current_conflict_ids=("propaganda",),
        maker_bonus_spice=(
            ("deep_desert", 2),
            ("hagga_basin", 0),
            ("imperial_basin", 0),
        ),
    )
    state = apply_agent_action(state, _action_to(state, "deep_desert")).state
    summon = next(
        action
        for action in legal_maker_space_actions(state, 0)
        if action.action_id == "summon_maker_sandworms"
    )

    resolved = apply_maker_space_action(state, summon).state

    assert resolved.players[0].sandworms_conflict == 2
    assert resolved.players[0].resources.spice == 2
    assert dict(resolved.maker_bonus_spice)["deep_desert"] == 0


def test_imperial_basin_collects_spice_without_a_sandworm_choice() -> None:
    state = _state("dune_the_desert_planet")
    owner = replace(state.players[0], maker_hooks=True)
    state = replace(
        state,
        players=(owner, *state.players[1:]),
        current_conflict_ids=("propaganda",),
        maker_bonus_spice=(
            ("deep_desert", 0),
            ("hagga_basin", 0),
            ("imperial_basin", 2),
        ),
    )
    state = apply_agent_action(state, _action_to(state, "imperial_basin")).state

    actions = legal_maker_space_actions(state, 0)
    resolved = apply_maker_space_action(state, actions[0]).state

    assert tuple(action.action_id for action in actions) == ("harvest_maker_spice",)
    assert resolved.players[0].resources.spice == 3
    assert dict(resolved.maker_bonus_spice)["imperial_basin"] == 0
    assert (
        dict(resolved.decision_stack[-1].context)["pending_combat_deployment"] is True
    )
