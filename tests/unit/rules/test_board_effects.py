"""Tests for typed automatic board-space effects."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.board import BOARD_SPACES, Faction
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    ChanceDecision,
    ChanceOutcome,
    ChanceResolver,
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
from dune_imperium.rules.agent_effects import resolve_faction_influence
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import (
    AUTOMATIC_BOARD_ICONS,
    CHOICE_DRIVEN_SPACE_IDS,
    apply_desert_tactics_action,
    apply_espionage_action,
    apply_imperial_privilege_action,
    apply_maker_space_action,
    apply_secrets_steal,
    apply_shipping_action,
    apply_sietch_tabr_action,
    board_effect_is_implemented,
    board_effects_for,
    board_icons_for,
    legal_board_effect_actions,
    legal_desert_tactics_actions,
    legal_espionage_actions,
    legal_imperial_privilege_actions,
    legal_maker_space_actions,
    legal_shipping_actions,
    legal_sietch_tabr_actions,
    resolve_board_effect,
    static_board_effects,
)
from dune_imperium.rules.combat_deployment import (
    apply_combat_deployment,
    legal_combat_deployments,
)
from dune_imperium.rules.contracts import apply_contract_action, legal_contract_actions
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


def _board_action(state: GameState, effect: str) -> DomainAction:
    return next(
        action
        for action in legal_board_effect_actions(state, 0)
        if dict(action.arguments)["effect"] == effect
    )


def _resolve_board(state: GameState, *effects: str) -> GameState:
    """Resolve the named icons in order, or every pending automatic icon."""

    keys = effects or tuple(
        str(dict(action.arguments)["effect"])
        for action in legal_board_effect_actions(state, 0)
    )
    for key in keys:
        state = resolve_board_effect(state, _board_action(state, key)).state
    return state


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
    assert dict(placed.decision_stack[-1].context)["board_icons"] == "cards,contract"

    # The card draw and the Contract icon are separate effects (OQ-027).
    drawn_state = resolve_board_effect(placed, _board_action(placed, "cards")).state
    assert drawn_state.players[0].hand == (drawn,)
    assert legal_contract_actions(drawn_state, 0) == ()

    result = resolve_board_effect(drawn_state, _board_action(drawn_state, "contract"))

    assert len(legal_contract_actions(result.state, 0)) == 2
    assert result.events[-1].kind == "board_effect_resolved"


def test_dutiful_service_resolves_board_reward_and_keeps_faction_pending() -> None:
    state = _state("diplomacy")
    placed = apply_agent_action(state, _action_to(state, "dutiful_service")).state

    result = resolve_board_effect(placed, _board_action(placed, "resources"))
    context = dict(result.state.decision_stack[-1].context)

    assert result.state.players[0].resources.solari == 2
    assert context["pending_board_effect"] is False
    assert context["pending_board_icons"] == ""
    assert context["pending_faction_influence"] is True
    assert result.events[0].kind == "board_effect_resolved"
    assert dict(result.events[0].payload) == {
        "effect": "resources",
        "player": 0,
        "space_id": "dutiful_service",
    }


def test_dutiful_service_choam_opens_contract_market_and_grants_influence() -> None:
    state = _state("diplomacy")
    state = replace(
        state,
        config=RulesetConfig(choam_module=True),
        contract_bank=("contract:research_station_i",),
        face_up_contract_ids=(
            "contract:arrakeen_i",
            "contract:high_council_ii",
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "dutiful_service"))

    assert placed.state.players[0].resources == state.players[0].resources
    assert dict(placed.state.decision_stack[-1].context)["board_icons"] == "contract"

    result = resolve_board_effect(
        placed.state, _board_action(placed.state, "contract")
    )

    assert result.state.players[0].resources.solari == 0
    assert len(legal_contract_actions(result.state, 0)) == 2
    assert result.events[-1].kind == "board_effect_resolved"

    taken = apply_contract_action(
        result.state, legal_contract_actions(result.state, 0)[0]
    )
    context = dict(taken.state.decision_stack[-1].context)
    assert context["pending_faction_influence"] is True
    assert taken.state.players[0].active_contract_ids == ("contract:arrakeen_i",)

    influenced = resolve_faction_influence(taken.state)

    assert influenced.state.players[0].influence.emperor == 1


def test_dutiful_service_choam_falls_back_to_solari_with_empty_market() -> None:
    state = _state("diplomacy")
    state = replace(state, config=RulesetConfig(choam_module=True))
    placed = apply_agent_action(state, _action_to(state, "dutiful_service")).state

    result = resolve_board_effect(placed, _board_action(placed, "contract"))

    assert result.state.players[0].resources.solari == 2
    assert legal_contract_actions(result.state, 0) == ()
    context = dict(result.state.decision_stack[-1].context)
    assert context["pending_board_effect"] is False
    assert context["pending_faction_influence"] is True
    assert result.events[-1].kind == "board_effect_resolved"


def test_spice_refinery_reward_depends_on_already_paid_option() -> None:
    state = _state("signet_ring", Resources(spice=1))
    action = _action_to(state, "spice_refinery", cost_option=1)
    placed = apply_agent_action(state, action).state

    resolved = _resolve_board(placed, "resources")

    assert resolved.players[0].resources.spice == 0
    assert resolved.players[0].resources.solari == 4


def test_unprinted_or_already_resolved_board_icon_is_rejected() -> None:
    state = _state("diplomacy")
    placed = apply_agent_action(state, _action_to(state, "dutiful_service")).state
    before = canonical_state_hash(placed)

    # Only the space's own pending icons are legal: Dutiful Service prints
    # no card draw, and a Spy choice icon never takes the generic action.
    for effect in ("cards", "spy"):
        with pytest.raises(ValueError, match="not a legal"):
            resolve_board_effect(
                placed,
                DomainAction(
                    action_id="resolve_board_effect",
                    actor=0,
                    arguments=(("effect", effect),),
                ),
            )
    assert canonical_state_hash(placed) == before

    solari_icon = _board_action(placed, "resources")
    resolved = resolve_board_effect(placed, solari_icon).state
    assert legal_board_effect_actions(resolved, 0) == ()
    with pytest.raises(ValueError, match="not a legal"):
        resolve_board_effect(resolved, solari_icon)


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

    resolved = _resolve_board(placed, "cards")
    context = dict(resolved.decision_stack[-1].context)

    assert resolved.players[0].hand == (drawn,)
    assert resolved.players[0].deck == ()
    assert context["pending_board_effect"] is False
    assert context["pending_combat_deployment"] is True


def test_arrakeen_troop_and_card_draw_are_independent_icons() -> None:
    # "troop 1개 recruit, card 1장 draw" [Board Guide p. 1] are two printed
    # icons, each resolved by its own action in the order the owner picks
    # ("You may carry out all these effects in any order" [Main p. 9];
    # OQ-027).
    state = _state("reconnaissance")
    drawn = _instance("dagger")
    owner = replace(state.players[0], deck=(drawn,))
    state = replace(state, players=(owner, *state.players[1:]))
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state
    context = dict(placed.decision_stack[-1].context)
    assert context["board_icons"] == "troops,cards"
    assert context["pending_board_icons"] == "troops,cards"
    assert [
        dict(action.arguments)["effect"]
        for action in legal_board_effect_actions(placed, 0)
    ] == ["troops", "cards"]

    troops_first = resolve_board_effect(placed, _board_action(placed, "troops"))
    owner = troops_first.state.players[0]
    context = dict(troops_first.state.decision_stack[-1].context)
    assert owner.troops_supply == 8
    assert owner.troops_garrison == 4
    assert owner.hand == ()
    assert context["troops_recruited"] == 1
    assert context["pending_board_icons"] == "cards"
    assert context["pending_board_effect"] is True
    assert [event.kind for event in troops_first.events] == ["board_effect_resolved"]
    assert dict(troops_first.events[0].payload) == {
        "effect": "troops",
        "player": 0,
        "space_id": "arrakeen",
    }

    both = resolve_board_effect(
        troops_first.state, _board_action(troops_first.state, "cards")
    ).state
    owner = both.players[0]
    context = dict(both.decision_stack[-1].context)
    assert owner.hand == (drawn,)
    assert owner.troops_garrison == 4
    assert context["pending_board_icons"] == ""
    assert context["pending_board_effect"] is False
    assert context["pending_combat_deployment"] is True
    assert legal_board_effect_actions(both, 0) == ()

    # The other order reaches the same state.
    cards_first = resolve_board_effect(placed, _board_action(placed, "cards")).state
    assert cards_first.players[0].hand == (drawn,)
    assert cards_first.players[0].troops_garrison == 3
    reversed_order = resolve_board_effect(
        cards_first, _board_action(cards_first, "troops")
    ).state
    assert reversed_order.players == both.players
    assert reversed_order.decision_stack == both.decision_stack


def test_gather_support_paid_option_prints_a_separate_water_icon() -> None:
    state = _state("dagger", Resources(solari=2))
    placed = apply_agent_action(state, _action_to(state, "gather_support", 1)).state
    assert dict(placed.decision_stack[-1].context)["board_icons"] == "troops,resources"

    watered = _resolve_board(placed, "resources")
    assert watered.players[0].resources.water == placed.players[0].resources.water + 1
    assert watered.players[0].troops_garrison == 3

    done = _resolve_board(watered, "troops")
    assert done.players[0].troops_garrison == 5
    # Nothing else is pending for a Dagger at Gather Support: the last icon
    # closes the effect frame and opens the clockwise player's turn.
    decision = done.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    assert decision.owner == 1


def test_assembly_hall_draws_hidden_intrigue() -> None:
    state = _state("dagger")
    state = replace(state, intrigue_deck=("intrigue:first", "intrigue:second"))
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state

    resolved = _resolve_board(placed, "intrigue")

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


def test_espionage_spy_placement_and_card_draw_are_separate_icons() -> None:
    # "card 1장 draw, Spy 1개를 배치할 수 있음" [Board Guide p. 1]: the draw
    # keeps the generic icon action while the Spy icon resolves through its
    # own choices (OQ-027).
    state, drawn = _espionage_state()
    assert dict(state.decision_stack[-1].context)["board_icons"] == "cards,spy"
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

    assert drawn not in owner.hand
    assert owner.spies_supply == 2
    assert post_id in owner.spy_post_ids
    assert context["pending_board_icons"] == "cards"
    assert context["pending_board_effect"] is True
    assert context["pending_faction_influence"] is True
    assert tuple(event.kind for event in result.events) == (
        "spy_placed",
        "board_effect_resolved",
    )
    assert dict(result.events[-1].payload) == {
        "action_id": "resolve_espionage_place_spy",
        "effect": "spy",
        "player": 0,
        "space_id": "espionage",
    }
    assert legal_espionage_actions(result.state, 0) == ()

    drawn_state = _resolve_board(result.state, "cards")
    assert drawn in drawn_state.players[0].hand
    assert dict(drawn_state.decision_stack[-1].context)["pending_board_effect"] is (
        False
    )


def test_espionage_card_draw_may_precede_the_spy_choice() -> None:
    state, drawn = _espionage_state()

    drawn_state = _resolve_board(state, "cards")

    assert drawn in drawn_state.players[0].hand
    assert dict(drawn_state.decision_stack[-1].context)["pending_board_icons"] == (
        "spy"
    )
    assert legal_board_effect_actions(drawn_state, 0) == ()
    assert {action.action_id for action in legal_espionage_actions(drawn_state, 0)} == {
        "resolve_espionage_without_spy",
        "resolve_espionage_place_spy",
    }


def test_espionage_can_decline_spy_and_still_draw_card() -> None:
    state, drawn = _espionage_state()
    decline = next(
        action
        for action in legal_espionage_actions(state, 0)
        if action.action_id == "resolve_espionage_without_spy"
    )

    declined = apply_espionage_action(state, decline).state

    assert declined.players[0].spies_supply == 3
    assert declined.players[0].spy_post_ids == ()
    assert dict(declined.decision_stack[-1].context)["pending_board_icons"] == "cards"
    resolved = _resolve_board(declined, "cards")
    assert drawn in resolved.players[0].hand


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

    declined = engine.apply(state, decline).state
    pending = engine.apply(declined, _board_action(declined, "cards")).state
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
    first_recall = next(
        action
        for action in recall_actions
        if action.action_id == "recall_spy_for_espionage"
    )
    recalled_post = dict(first_recall.arguments)["post_id"]

    recalled = apply_espionage_action(state, first_recall)
    replacement_actions = legal_espionage_actions(recalled.state, 0)

    # The printed placement stays optional before any recall [Board Guide
    # p. 1]; once the recall is chosen, placement is committed.
    assert {action.action_id for action in recall_actions} == {
        "resolve_espionage_without_spy",
        "recall_spy_for_espionage",
    }
    assert {action.action_id for action in replacement_actions} == {
        "resolve_espionage_place_spy"
    }
    assert recalled_post not in recalled.state.players[0].spy_post_ids
    assert recalled.state.players[0].spies_supply == 1
    assert recalled.events[0].kind == "spy_recalled"

    resolved = apply_espionage_action(recalled.state, replacement_actions[0]).state
    owner = resolved.players[0]

    assert owner.spies_supply == 0
    assert len(owner.spy_post_ids) == 3
    assert drawn in _resolve_board(resolved, "cards").players[0].hand


def test_espionage_with_empty_supply_may_resolve_without_moving_a_spy() -> None:
    # The printed placement is optional [Board Guide p. 1]; an empty supply
    # must not force the player to relocate a placed Spy.
    state, drawn = _espionage_state(spies_supply=0)
    decline = next(
        action
        for action in legal_espionage_actions(state, 0)
        if action.action_id == "resolve_espionage_without_spy"
    )

    result = apply_espionage_action(state, decline)
    owner = result.state.players[0]

    assert owner.spies_supply == 0
    assert len(owner.spy_post_ids) == 3
    assert dict(result.state.decision_stack[-1].context)["pending_board_icons"] == (
        "cards"
    )
    assert drawn in _resolve_board(result.state, "cards").players[0].hand


def test_espionage_reopens_recall_when_the_recalled_spy_was_consumed() -> None:
    # Placement needs a Spy in supply when it resolves [Main pp. 11, 20]; if a
    # freely ordered effect consumed the recalled Spy, the committed placement
    # reopens the recall choice instead of failing.
    state, _ = _espionage_state(spies_supply=0)
    first_recall = next(
        action
        for action in legal_espionage_actions(state, 0)
        if action.action_id == "recall_spy_for_espionage"
    )
    recalled = apply_espionage_action(state, first_recall).state

    consumed_owner = replace(
        recalled.players[0],
        spies_supply=0,
        spy_post_ids=(
            *recalled.players[0].spy_post_ids,
            "fremen-desert-tactics-fremkit",
        ),
    )
    consumed = replace(
        recalled,
        players=(consumed_owner, *recalled.players[1:]),
    )

    reopened = legal_espionage_actions(consumed, 0)
    assert {action.action_id for action in reopened} == {"recall_spy_for_espionage"}

    rerecalled = apply_espionage_action(consumed, reopened[0]).state
    placements = legal_espionage_actions(rerecalled, 0)
    assert {action.action_id for action in placements} == {
        "resolve_espionage_place_spy"
    }
    placed = apply_espionage_action(rerecalled, placements[0]).state
    assert placed.players[0].spies_supply == 0


def test_first_high_council_visit_grants_seat_without_repeat_rewards() -> None:
    state = _state("dagger", Resources(solari=5))
    placed = apply_agent_action(state, _action_to(state, "high_council")).state
    assert dict(placed.decision_stack[-1].context)["board_icons"] == "high_council"

    resolved = _resolve_board(placed, "high_council")
    owner = resolved.players[0]

    assert owner.high_council is True
    assert owner.resources.spice == 0
    assert owner.intrigue_cards == ()
    assert owner.troops_garrison == 3
    assert legal_board_effect_actions(resolved, 0) == ()


def test_high_council_revisit_grants_spice_intrigue_and_troops() -> None:
    state = _state("dagger", Resources(solari=5))
    owner = replace(state.players[0], high_council=True)
    state = replace(
        state,
        players=(owner, *state.players[1:]),
        intrigue_deck=("intrigue:first",),
    )
    placed = apply_agent_action(state, _action_to(state, "high_council")).state
    assert dict(placed.decision_stack[-1].context)["board_icons"] == (
        "resources,intrigue,troops"
    )

    resolved = _resolve_board(placed)
    owner = resolved.players[0]

    assert owner.resources.spice == 2
    assert owner.intrigue_cards == ("intrigue:first",)
    assert owner.troops_supply == 6
    assert owner.troops_garrison == 6


def test_swordmaster_is_available_immediately_after_acquisition() -> None:
    state = _state("dagger", Resources(solari=8))
    placed = apply_agent_action(state, _action_to(state, "swordmaster")).state

    resolved = _resolve_board(placed, "swordmaster")
    owner = resolved.players[0]

    assert owner.swordmaster_acquired is True
    assert owner.agents_available == 2
    assert owner.agent_locations == ("swordmaster",)


def test_gather_support_recruits_available_troops_and_finishes_turn() -> None:
    state = _state("dagger")
    placed = apply_agent_action(state, _action_to(state, "gather_support", 0)).state

    resolved = _resolve_board(placed, "troops")
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


def _shipping_state(influence: Influence) -> GameState:
    state = _state("dune_the_desert_planet", Resources(spice=3))
    owner = replace(state.players[0], influence=influence)
    state = replace(state, players=(owner, *state.players[1:]))
    return apply_agent_action(state, _action_to(state, "shipping")).state


def test_shipping_requires_guild_influence_and_pays_exact_spice_cost() -> None:
    unqualified = _state("dune_the_desert_planet", Resources(spice=3))
    unqualified = replace(
        unqualified,
        players=(
            replace(
                unqualified.players[0],
                influence=Influence(spacing_guild=1),
            ),
            *unqualified.players[1:],
        ),
    )
    assert not any(
        dict(action.arguments).get("space_id") == "shipping"
        for action in legal_agent_actions(unqualified, 0)
    )

    placed = _shipping_state(Influence(spacing_guild=2))

    assert placed.players[0].resources.spice == 0
    context = dict(placed.decision_stack[-1].context)
    assert context["pending_board_effect"] is True
    assert context["space_id"] == "shipping"


def test_shipping_offers_all_four_faction_choices() -> None:
    state = _shipping_state(Influence(spacing_guild=2))
    actions = legal_shipping_actions(state, 0)

    assert len(actions) == 4
    assert all(action.action_id == "choose_shipping_influence" for action in actions)
    assert {dict(action.arguments)["faction"] for action in actions} == {
        faction.value for faction in Faction
    }


def test_shipping_influence_choice_leaves_the_solari_icon_pending() -> None:
    # "5 Solari, 선택한 Faction 하나의 Influence 1" [Board Guide p. 2] are two
    # printed icons (OQ-027): the Influence choice resolves alone.
    state = _shipping_state(Influence(spacing_guild=2))
    assert dict(state.decision_stack[-1].context)["board_icons"] == (
        "resources,influence"
    )
    action = next(
        candidate
        for candidate in legal_shipping_actions(state, 0)
        if dict(candidate.arguments)["faction"] == Faction.EMPEROR.value
    )

    result = apply_shipping_action(state, action)
    owner = result.state.players[0]
    context = dict(result.state.decision_stack[-1].context)

    assert owner.influence.emperor == 1
    assert owner.resources.solari == 0
    assert context["pending_board_icons"] == "resources"
    assert legal_shipping_actions(result.state, 0) == ()
    assert result.events[-1].kind == "board_effect_resolved"
    assert dict(result.events[-1].payload) == {
        "action_id": "choose_shipping_influence",
        "effect": "influence",
        "player": 0,
        "space_id": "shipping",
    }

    # No other group is left pending for this hand/space combination, so
    # the Solari icon closes the Agent-turn effect frame and opens the
    # clockwise player's turn, mirroring
    # test_finishing_all_effect_groups_opens_clockwise_players_turn.
    finished = _resolve_board(result.state, "resources")
    decision = finished.decision_stack[-1].decision
    assert finished.players[0].resources.solari == 5
    assert isinstance(decision, PlayerDecision)
    assert decision.owner == 1


def test_shipping_choice_awards_the_two_influence_friendship_vp() -> None:
    state = _shipping_state(Influence(spacing_guild=2, emperor=1))
    action = next(
        candidate
        for candidate in legal_shipping_actions(state, 0)
        if dict(candidate.arguments)["faction"] == Faction.EMPEROR.value
    )

    result = apply_shipping_action(state, action)
    owner = result.state.players[0]

    assert owner.influence.emperor == 2
    assert owner.victory_points == 2
    assert any(event.kind == "influence_gained" for event in result.events)


def _desert_tactics_state() -> GameState:
    fremen_card = _instance("diplomacy")
    hand_card = _instance("dagger")
    discard_card = _instance("reconnaissance")
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        players=(
            PlayerState(
                player_id=0,
                hand=(fremen_card, hand_card),
                discard_pile=(discard_card,),
            ),
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
    return apply_agent_action(state, _action_to(state, "desert_tactics")).state


def test_desert_tactics_placement_pays_exactly_one_water() -> None:
    state = _desert_tactics_state()

    assert state.players[0].resources.water == 0
    context = dict(state.decision_stack[-1].context)
    assert context["pending_board_effect"] is True
    assert context["space_id"] == "desert_tactics"


def test_desert_tactics_offers_decline_and_every_eligible_card_trash() -> None:
    state = _desert_tactics_state()
    owner = state.players[0]
    actions = legal_desert_tactics_actions(state, 0)

    assert len(actions) == 1 + len(owner.hand) + len(owner.discard_pile) + len(
        owner.in_play
    )
    assert actions[0].action_id == "resolve_desert_tactics_without_trash"
    trash_actions = actions[1:]
    assert all(
        action.action_id == "trash_card_for_desert_tactics" for action in trash_actions
    )
    assert {dict(action.arguments)["card_id"] for action in trash_actions} == {
        *owner.hand,
        *owner.discard_pile,
        *owner.in_play,
    }


def test_desert_tactics_trash_variant_trashes_only_the_chosen_card() -> None:
    # "troop 1개 recruit, 원하면 card 1장 trash" [Board Guide p. 1]: the troop
    # is its own icon and stays pending after the trash choice (OQ-027).
    state = _desert_tactics_state()
    owner = state.players[0]
    assert dict(state.decision_stack[-1].context)["board_icons"] == "troops,trash"
    trash_target = owner.discard_pile[0]
    action = next(
        candidate
        for candidate in legal_desert_tactics_actions(state, 0)
        if candidate.action_id == "trash_card_for_desert_tactics"
        and dict(candidate.arguments)["card_id"] == trash_target
    )

    result = apply_desert_tactics_action(state, action)
    resolved = result.state
    resolved_owner = resolved.players[0]
    context = dict(resolved.decision_stack[-1].context)

    assert resolved_owner.troops_garrison == owner.troops_garrison
    assert context["troops_recruited"] == 0
    assert context["pending_board_icons"] == "troops"
    assert trash_target not in resolved_owner.hand
    assert trash_target not in resolved_owner.discard_pile
    assert trash_target not in resolved_owner.in_play
    assert trash_target in resolved_owner.trashed
    assert result.events[-1].kind == "board_effect_resolved"
    assert dict(result.events[-1].payload) == {
        "action_id": "trash_card_for_desert_tactics",
        "effect": "trash",
        "player": 0,
        "space_id": "desert_tactics",
    }
    assert legal_desert_tactics_actions(resolved, 0) == ()

    recruited = _resolve_board(resolved, "troops")
    recruited_context = dict(recruited.decision_stack[-1].context)
    assert recruited.players[0].troops_garrison == owner.troops_garrison + 1
    assert recruited_context["troops_recruited"] == 1
    assert recruited_context["pending_board_effect"] is False
    assert any(
        dict(deploy.arguments)["count"] == 3
        for deploy in legal_combat_deployments(recruited, 0)
    )


def test_desert_tactics_decline_variant_trashes_nothing() -> None:
    state = _desert_tactics_state()
    owner = state.players[0]
    decline = next(
        candidate
        for candidate in legal_desert_tactics_actions(state, 0)
        if candidate.action_id == "resolve_desert_tactics_without_trash"
    )

    result = apply_desert_tactics_action(state, decline)
    resolved_owner = result.state.players[0]

    assert resolved_owner.troops_garrison == owner.troops_garrison
    assert resolved_owner.hand == owner.hand
    assert resolved_owner.discard_pile == owner.discard_pile
    assert resolved_owner.in_play == owner.in_play
    assert resolved_owner.trashed == ()
    assert dict(result.state.decision_stack[-1].context)["pending_board_icons"] == (
        "troops"
    )
    assert result.events[-1].kind == "board_effect_resolved"
    assert dict(result.events[-1].payload) == {
        "action_id": "resolve_desert_tactics_without_trash",
        "effect": "trash",
        "player": 0,
        "space_id": "desert_tactics",
    }


def test_desert_tactics_can_trash_the_just_played_card_itself() -> None:
    state = _desert_tactics_state()
    owner = state.players[0]
    played_card = owner.in_play[-1]
    action = next(
        candidate
        for candidate in legal_desert_tactics_actions(state, 0)
        if candidate.action_id == "trash_card_for_desert_tactics"
        and dict(candidate.arguments)["card_id"] == played_card
    )

    trashed_state = apply_desert_tactics_action(state, action).state
    resolved_owner = trashed_state.players[0]

    assert played_card not in resolved_owner.in_play
    assert played_card in resolved_owner.trashed

    trashed_state = _resolve_board(trashed_state, "troops")
    deployment = next(
        candidate
        for candidate in legal_combat_deployments(trashed_state, 0)
        if dict(candidate.arguments)["count"] == 0
    )
    deployed_state = apply_combat_deployment(trashed_state, deployment).state
    # Desert Tactics' Fremen icon leaves the generic Faction Influence choice
    # pending independently of the board effect just resolved above.
    finished = resolve_faction_influence(deployed_state).state
    decision = finished.decision_stack[-1].decision

    assert isinstance(decision, PlayerDecision)
    assert decision.owner == 1


def _imperial_privilege_state(
    *,
    intrigue_cards: tuple[str, ...] = (),
    intrigue_deck: tuple[str, ...] = (),
    other_agent_space: str | None = None,
) -> GameState:
    state = _state("dagger", Resources(solari=3))
    owner = replace(
        state.players[0],
        influence=Influence(emperor=2),
        intrigue_cards=intrigue_cards,
    )
    if other_agent_space is not None:
        owner = replace(
            owner,
            agents_available=1,
            agent_locations=(other_agent_space,),
        )
    state = replace(
        state,
        players=(owner, *state.players[1:]),
        intrigue_deck=intrigue_deck,
    )
    return apply_agent_action(state, _action_to(state, "imperial_privilege")).state


def test_imperial_privilege_requires_emperor_influence_and_pays_exact_solari_cost() -> (
    None
):
    unqualified = _state("dagger", Resources(solari=3))
    unqualified = replace(
        unqualified,
        players=(
            replace(unqualified.players[0], influence=Influence(emperor=1)),
            *unqualified.players[1:],
        ),
    )
    assert not any(
        dict(action.arguments).get("space_id") == "imperial_privilege"
        for action in legal_agent_actions(unqualified, 0)
    )

    placed = _imperial_privilege_state()

    assert placed.players[0].resources.solari == 0
    context = dict(placed.decision_stack[-1].context)
    assert context["pending_board_effect"] is True
    assert context["space_id"] == "imperial_privilege"


def test_imperial_privilege_offers_decline_and_every_held_intrigue_discard() -> None:
    state = _imperial_privilege_state(
        intrigue_cards=("intrigue:one", "intrigue:two"),
    )
    actions = legal_imperial_privilege_actions(state, 0)

    assert actions[0].action_id == "decline_imperial_privilege_intrigue"
    discard_actions = actions[1:]
    assert all(
        action.action_id == "discard_intrigue_for_imperial_privilege"
        for action in discard_actions
    )
    assert {dict(action.arguments)["card_id"] for action in discard_actions} == {
        "intrigue:one",
        "intrigue:two",
    }


def test_imperial_privilege_offers_only_decline_with_no_held_intrigue() -> None:
    state = _imperial_privilege_state()

    assert tuple(
        action.action_id for action in legal_imperial_privilege_actions(state, 0)
    ) == ("decline_imperial_privilege_intrigue",)


def test_imperial_privilege_discard_swaps_intrigue_then_offers_the_other_agent() -> (
    None
):
    state = _imperial_privilege_state(
        intrigue_cards=("intrigue:held",),
        intrigue_deck=("intrigue:replacement",),
        other_agent_space="arrakeen",
    )
    action = next(
        candidate
        for candidate in legal_imperial_privilege_actions(state, 0)
        if candidate.action_id == "discard_intrigue_for_imperial_privilege"
    )

    result = apply_imperial_privilege_action(state, action)
    resolved = result.state
    owner = resolved.players[0]
    context = dict(resolved.decision_stack[-1].context)

    assert owner.intrigue_cards == ("intrigue:replacement",)
    assert resolved.intrigue_discard == ("intrigue:held",)
    assert resolved.intrigue_deck == ()
    assert context["pending_board_effect"] is True
    assert context["imperial_privilege_intrigue_resolved"] is True
    assert any(event.kind == "intrigue_card_discarded" for event in result.events)

    recall_actions = legal_imperial_privilege_actions(resolved, 0)
    assert tuple(action.action_id for action in recall_actions) == (
        "recall_agent_for_imperial_privilege",
    )
    assert dict(recall_actions[0].arguments) == {"space_id": "arrakeen"}


def test_imperial_privilege_recall_returns_agent_and_draws_a_card() -> None:
    state = _imperial_privilege_state(other_agent_space="arrakeen")
    decline = next(
        candidate
        for candidate in legal_imperial_privilege_actions(state, 0)
        if candidate.action_id == "decline_imperial_privilege_intrigue"
    )
    declined = apply_imperial_privilege_action(state, decline).state
    drawn = _instance("reconnaissance")
    declined_owner = replace(declined.players[0], deck=(drawn,))
    declined = replace(declined, players=(declined_owner, *declined.players[1:]))
    recall = next(
        candidate
        for candidate in legal_imperial_privilege_actions(declined, 0)
        if candidate.action_id == "recall_agent_for_imperial_privilege"
    )

    result = apply_imperial_privilege_action(declined, recall)
    resolved_owner = result.state.players[0]
    decision = result.state.decision_stack[-1].decision

    assert "arrakeen" not in resolved_owner.agent_locations
    assert resolved_owner.agents_available == 1
    assert resolved_owner.hand == (drawn,)
    assert isinstance(decision, PlayerDecision)
    assert decision.owner == 1
    assert result.events[-1].kind == "board_effect_resolved"
    assert dict(result.events[-1].payload) == {
        "action_id": "recall_agent_for_imperial_privilege",
        "effect": "imperial_privilege",
        "player": 0,
        "space_id": "imperial_privilege",
    }
    assert any(event.kind == "agent_recalled" for event in result.events)


def test_imperial_privilege_skips_only_the_recall_without_another_agent() -> None:
    state = _imperial_privilege_state(intrigue_cards=("intrigue:held",))
    drawn = _instance("reconnaissance")
    owner = replace(state.players[0], deck=(drawn,))
    state = replace(state, players=(owner, *state.players[1:]))
    action = next(
        candidate
        for candidate in legal_imperial_privilege_actions(state, 0)
        if candidate.action_id == "discard_intrigue_for_imperial_privilege"
    )

    result = apply_imperial_privilege_action(state, action)
    resolved = result.state
    decision = resolved.decision_stack[-1].decision

    # With no other deployed Agent only the recall is skipped; the card draw
    # is a separate printed effect and still resolves (OQ-023 decided
    # ruling, [Board Guide p. 2]).
    assert legal_imperial_privilege_actions(resolved, 0) == ()
    assert drawn in resolved.players[0].hand
    assert isinstance(decision, PlayerDecision)
    assert decision.owner == 1
    assert result.events[-1].kind == "board_effect_resolved"
    assert any(
        event.kind == "imperial_privilege_recall_skipped" for event in result.events
    )
    assert not any(event.kind == "agent_recalled" for event in result.events)


def test_imperial_privilege_discard_draw_reshuffles_an_empty_deck() -> None:
    # The slot-1 draw goes through the reshuffle-safe path [FAQ p. 2], just
    # like Assembly Hall's Intrigue draw (mirrors
    # test_owed_intrigue_draws_reshuffle_the_discard_before_the_next_decision
    # in test_intrigue.py).
    discard = ("intrigue:cunning", "intrigue:devour")
    state = _imperial_privilege_state(intrigue_cards=("intrigue:held",))
    state = replace(state, intrigue_discard=discard)
    engine = UprisingRulesEngine()
    action = next(
        candidate
        for candidate in engine.legal_actions(state, 0)
        if candidate.action_id == "discard_intrigue_for_imperial_privilege"
    )

    pending = engine.apply(state, action)
    decision = pending.next_decision

    assert isinstance(decision, ChanceDecision)
    # The just-discarded card joins the pre-existing discard pile before the
    # reshuffle is offered.
    assert decision.options == (*discard, "intrigue:held")
    assert pending.state.pending_intrigue_draws == ()

    outcome = ChanceResolver(seed=5).resolve(decision)
    resolved = engine.apply(pending.state, outcome)

    # The empty deck did not crash the draw: the reshuffle completed and the
    # owed card was delivered from the freshly shuffled deck.
    assert len(resolved.state.players[0].intrigue_cards) == 1
    assert resolved.state.intrigue_discard == ()
    assert len(resolved.state.intrigue_deck) == 2


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


def _secrets_state(
    *,
    seat1_intrigue: tuple[str, ...] = (),
    seat1_faceup: tuple[str, ...] = (),
    seat2_intrigue: tuple[str, ...] = (),
    seat3_intrigue: tuple[str, ...] = (),
    intrigue_deck: tuple[str, ...] = (),
    intrigue_discard: tuple[str, ...] = (),
) -> GameState:
    state = _state("diplomacy")
    seat1 = replace(
        state.players[1], intrigue_cards=seat1_intrigue, intrigue_faceup=seat1_faceup
    )
    seat2 = replace(state.players[2], intrigue_cards=seat2_intrigue)
    seat3 = replace(state.players[3], intrigue_cards=seat3_intrigue)
    state = replace(
        state,
        players=(state.players[0], seat1, seat2, seat3),
        intrigue_deck=intrigue_deck,
        intrigue_discard=intrigue_discard,
    )
    return apply_agent_action(state, _action_to(state, "secrets")).state


def test_secrets_no_qualifying_opponent_only_draws_intrigue() -> None:
    # With every opponent below 4 held Intrigue cards [Board Guide p. 2], the
    # Bene Gesserit Influence stays pending on the generic faction-visit path
    # and no random-steal frame is pushed.
    placed = _secrets_state(intrigue_deck=("intrigue:drawn",))
    assert dict(placed.decision_stack[-1].context)["board_icons"] == "intrigue"

    resolved = _resolve_board(placed, "intrigue")

    assert resolved.players[0].intrigue_cards == ("intrigue:drawn",)
    assert not any(frame.kind == "secrets_steal" for frame in resolved.decision_stack)
    top = resolved.decision_stack[-1]
    assert top.kind == "agent_effects"
    assert dict(top.context)["pending_faction_influence"] is True


def test_secrets_one_qualifying_opponent_pushes_a_steal_frame() -> None:
    victim_cards = ("intrigue:a", "intrigue:b", "intrigue:c", "intrigue:d")
    placed = _secrets_state(seat1_intrigue=victim_cards)

    resolved = _resolve_board(placed, "intrigue")
    top = resolved.decision_stack[-1]

    assert top.kind == "secrets_steal"
    decision = top.decision
    assert isinstance(decision, ChanceDecision)
    assert decision.options == victim_cards
    assert decision.count == 1
    assert dict(top.context) == {"thief": 0, "victim": 1}

    outcome = ChanceResolver(seed=3).resolve(decision)
    result = apply_secrets_steal(resolved, outcome)
    applied = result.state
    stolen = outcome.values[0]

    assert applied.players[1].intrigue_cards == tuple(
        card for card in victim_cards if card != stolen
    )
    assert applied.players[0].intrigue_cards == (stolen,)
    assert applied.decision_stack[-1].kind != "secrets_steal"
    # The theft is public but the stolen identity stays between thief and
    # victim: Intrigue is hidden from opponents until played [Main p. 7]
    # (OQ-010 ruling 3 for the event log).
    public, identity = result.events
    assert public.kind == "intrigue_card_stolen"
    assert public.visible_to is None
    assert dict(public.payload) == {"player": 0, "victim": 1}
    assert identity.kind == "intrigue_card_stolen_identity"
    assert identity.visible_to == (0, 1)
    assert dict(identity.payload) == {"card_id": stolen, "player": 0, "victim": 1}


def test_secrets_two_qualifying_opponents_resolve_clockwise_from_the_thief() -> None:
    seat1_cards = ("intrigue:s1a", "intrigue:s1b", "intrigue:s1c", "intrigue:s1d")
    seat2_cards = ("intrigue:s2a", "intrigue:s2b", "intrigue:s2c", "intrigue:s2d")
    placed = _secrets_state(seat1_intrigue=seat1_cards, seat2_intrigue=seat2_cards)

    resolved = _resolve_board(placed, "intrigue")
    steal_frames = [
        frame for frame in resolved.decision_stack if frame.kind == "secrets_steal"
    ]
    assert len(steal_frames) == 2

    # The seat immediately clockwise after the thief resolves first.
    top = resolved.decision_stack[-1]
    assert dict(top.context)["victim"] == 1
    assert isinstance(top.decision, ChanceDecision)
    assert top.decision.options == seat1_cards

    outcome1 = ChanceResolver(seed=1).resolve(top.decision)
    after_seat1 = apply_secrets_steal(resolved, outcome1).state
    next_top = after_seat1.decision_stack[-1]

    assert next_top.kind == "secrets_steal"
    assert dict(next_top.context)["victim"] == 2
    assert isinstance(next_top.decision, ChanceDecision)
    assert next_top.decision.options == seat2_cards

    outcome2 = ChanceResolver(seed=2).resolve(next_top.decision)
    final = apply_secrets_steal(after_seat1, outcome2).state

    assert final.players[1].intrigue_cards == tuple(
        card for card in seat1_cards if card != outcome1.values[0]
    )
    assert final.players[2].intrigue_cards == tuple(
        card for card in seat2_cards if card != outcome2.values[0]
    )
    assert final.players[0].intrigue_cards == (outcome1.values[0], outcome2.values[0])
    assert final.decision_stack[-1].kind != "secrets_steal"


def test_secrets_below_threshold_opponent_is_not_a_victim() -> None:
    placed = _secrets_state(
        seat1_intrigue=("intrigue:x", "intrigue:y", "intrigue:z"),
        seat2_intrigue=("intrigue:a", "intrigue:b", "intrigue:c", "intrigue:d"),
        seat3_intrigue=("intrigue:e", "intrigue:f", "intrigue:g", "intrigue:h"),
    )

    resolved = _resolve_board(placed, "intrigue")
    victims = {
        dict(frame.context)["victim"]
        for frame in resolved.decision_stack
        if frame.kind == "secrets_steal"
    }

    assert victims == {2, 3}


def test_secrets_faceup_intrigue_does_not_count_toward_the_threshold() -> None:
    # Face-up trigger cards sit in a separate public zone and are played, not
    # held [Main p. 7], so they never count toward the 4-card threshold.
    placed = _secrets_state(
        seat1_intrigue=("intrigue:x", "intrigue:y", "intrigue:z"),
        seat1_faceup=("intrigue:trigger_a", "intrigue:trigger_b"),
    )

    resolved = _resolve_board(placed, "intrigue")

    assert not any(frame.kind == "secrets_steal" for frame in resolved.decision_stack)


def test_secrets_reshuffle_resolves_before_the_steal_frame() -> None:
    # Secrets' generic Intrigue draw still goes through the queued
    # reshuffle-safe path [FAQ p. 2]. The printed order draws the Intrigue
    # card first, so the reshuffle chance must resolve before the random
    # steal frames (mirrors
    # test_owed_intrigue_draws_reshuffle_the_discard_before_the_next_decision
    # in test_intrigue.py).
    victim_cards = ("intrigue:a", "intrigue:b", "intrigue:c", "intrigue:d")
    state = _state("diplomacy")
    victim = replace(state.players[1], intrigue_cards=victim_cards)
    state = replace(
        state,
        players=(state.players[0], victim, *state.players[2:]),
        intrigue_discard=("intrigue:cunning", "intrigue:devour"),
    )
    engine = UprisingRulesEngine()
    to_secrets = next(
        action
        for action in engine.legal_actions(state, 0)
        if action.action_id == "agent_turn"
        and dict(action.arguments)["space_id"] == "secrets"
    )
    placed = engine.apply(state, to_secrets).state

    pending = engine.apply(placed, _board_action(placed, "intrigue"))
    decision = pending.next_decision

    assert isinstance(decision, ChanceDecision)
    assert "intrigue_shuffle" in decision.decision_id
    assert pending.state.pending_intrigue_draws == ()

    outcome = ChanceResolver(seed=7).resolve(decision)
    resolved = engine.apply(pending.state, outcome)
    next_top = resolved.state.decision_stack[-1]

    assert next_top.kind == "secrets_steal"
    assert isinstance(next_top.decision, ChanceDecision)
    assert "secrets:steal:1" in next_top.decision.decision_id
    assert next_top.decision.options == victim_cards


# The display catalog renders board-space effect text from the same static
# table the engine executes, so the full printed domain is pinned here: every
# manifest space x cost option x ruleset maps to an exact effect tuple, or to
# None where the automatic-effects channel does not cover the space (spaces
# resolved entirely through choice frames, or a not-yet-implemented effect).
# Choice-driven spaces with an automatic icon (Espionage's draw, Desert
# Tactics' troop, Shipping's Solari) list just that icon (OQ-027).
_BASE_EFFECT_TABLE: dict[str, dict[int, tuple[object, ...] | None]] = {
    "dutiful_service": {0: (GainResourcesEffect(solari=2),)},
    "sardaukar": {0: (DrawIntrigueCardsEffect(1), RecruitTroopsEffect(4))},
    "deliver_supplies": {0: (GainResourcesEffect(water=1),)},
    "heighliner": {0: (RecruitTroopsEffect(5),)},
    "espionage": {0: (DrawImperiumCardsEffect(1),)},
    "secrets": {0: (DrawIntrigueCardsEffect(1),)},
    "desert_tactics": {0: (RecruitTroopsEffect(1),)},
    "fremkit": {0: (DrawImperiumCardsEffect(1),)},
    "assembly_hall": {0: (DrawIntrigueCardsEffect(1),)},
    "gather_support": {
        0: (RecruitTroopsEffect(2),),
        1: (RecruitTroopsEffect(2), GainResourcesEffect(water=1)),
    },
    "high_council": {0: ()},
    "imperial_privilege": {0: None},
    "swordmaster": {0: (), 1: ()},
    "arrakeen": {0: (RecruitTroopsEffect(1), DrawImperiumCardsEffect(1))},
    "research_station": {0: (RecruitTroopsEffect(2), DrawImperiumCardsEffect(2))},
    "sietch_tabr": {0: None},
    "spice_refinery": {
        0: (GainResourcesEffect(solari=2),),
        1: (GainResourcesEffect(solari=4),),
    },
    "accept_contract": {0: (DrawImperiumCardsEffect(1), GainResourcesEffect(solari=2))},
    "deep_desert": {0: None},
    "hagga_basin": {0: None},
    "imperial_basin": {0: None},
    "shipping": {0: (GainResourcesEffect(solari=5),)},
}
_CHOAM_EFFECT_OVERRIDES: dict[str, dict[int, tuple[object, ...] | None]] = {
    "dutiful_service": {0: ()},
    "accept_contract": {0: (DrawImperiumCardsEffect(1),)},
}

# Every printed icon of every space option, in printed order, as the keys of
# the actions that resolve them (OQ-027): automatic keys take the generic
# ``resolve_board_effect`` action, the rest the space's dedicated choices.
_BASE_ICON_TABLE: dict[str, dict[int, str]] = {
    "dutiful_service": {0: "resources"},
    "sardaukar": {0: "intrigue,troops"},
    "deliver_supplies": {0: "resources"},
    "heighliner": {0: "troops"},
    "espionage": {0: "cards,spy"},
    "secrets": {0: "intrigue"},
    "desert_tactics": {0: "troops,trash"},
    "fremkit": {0: "cards"},
    "assembly_hall": {0: "intrigue"},
    "gather_support": {0: "troops", 1: "troops,resources"},
    "high_council": {0: "high_council"},
    "imperial_privilege": {0: "imperial_privilege"},
    "swordmaster": {0: "swordmaster", 1: "swordmaster"},
    "arrakeen": {0: "troops,cards"},
    "research_station": {0: "troops,cards"},
    "sietch_tabr": {0: "sietch_tabr"},
    "spice_refinery": {0: "resources", 1: "resources"},
    "accept_contract": {0: "cards,resources"},
    "deep_desert": {0: "maker"},
    "hagga_basin": {0: "maker"},
    "imperial_basin": {0: "maker"},
    "shipping": {0: "resources,influence"},
}
_CHOAM_ICON_OVERRIDES: dict[str, dict[int, str]] = {
    "dutiful_service": {0: "contract"},
    "accept_contract": {0: "cards,contract"},
}
_CHOICE_ICONS = frozenset(
    {"spy", "trash", "influence", "sietch_tabr", "maker", "imperial_privilege"}
)


def test_board_icons_pin_every_printed_space_option() -> None:
    manifest_domain = {
        (space.space_id, option)
        for space in BOARD_SPACES
        for option in range(max(1, len(space.cost_options)))
    }
    pinned_domain = {
        (space_id, option)
        for space_id, options in _BASE_ICON_TABLE.items()
        for option in options
    }
    assert pinned_domain == manifest_domain
    assert set(AUTOMATIC_BOARD_ICONS).isdisjoint(_CHOICE_ICONS)

    for choam_module in (False, True):
        state = GameState(
            config=RulesetConfig(choam_module=choam_module),
            seed=1,
            players=tuple(PlayerState(player_id=seat) for seat in range(4)),
        )
        for space_id, option in manifest_domain:
            expected = _BASE_ICON_TABLE[space_id][option]
            if choam_module and space_id in _CHOAM_ICON_OVERRIDES:
                expected = _CHOAM_ICON_OVERRIDES[space_id][option]
            icons = board_icons_for(state, 0, space_id, option)
            assert ",".join(icons) == expected, (space_id, option, choam_module)
            assert all(
                icon in AUTOMATIC_BOARD_ICONS or icon in _CHOICE_ICONS
                for icon in icons
            ), (space_id, option)

    # A seated Councilor turns High Council into its three revisit icons.
    member = replace(state.players[0], high_council=True)
    member_state = replace(state, players=(member, *state.players[1:]))
    assert board_icons_for(member_state, 0, "high_council", 0) == (
        "resources",
        "intrigue",
        "troops",
    )


def test_static_board_effects_pins_the_full_printed_domain() -> None:
    manifest_domain = {
        (space.space_id, option)
        for space in BOARD_SPACES
        for option in range(max(1, len(space.cost_options)))
    }
    pinned_domain = {
        (space_id, option)
        for space_id, options in _BASE_EFFECT_TABLE.items()
        for option in options
    }
    assert pinned_domain == manifest_domain

    for choam_module in (False, True):
        for space_id, option in manifest_domain:
            expected = _BASE_EFFECT_TABLE[space_id][option]
            if choam_module and space_id in _CHOAM_EFFECT_OVERRIDES:
                expected = _CHOAM_EFFECT_OVERRIDES[space_id][option]
            try:
                actual: tuple[object, ...] | None = static_board_effects(
                    space_id,
                    option,
                    choam_module=choam_module,
                )
            except NotImplementedError:
                actual = None
            assert actual == expected, (space_id, option, choam_module)


def test_unimplemented_board_spaces_are_exactly_pinned() -> None:
    base_hidden: set[str] = set()
    for choam_module, expected_hidden in (
        (False, base_hidden),
        (True, base_hidden),
    ):
        state = GameState(
            config=RulesetConfig(choam_module=choam_module),
            seed=1,
            players=tuple(PlayerState(player_id=seat) for seat in range(4)),
        )
        hidden = {
            space.space_id
            for space in BOARD_SPACES
            if not all(
                board_effect_is_implemented(state, space.space_id, option)
                for option in range(max(1, len(space.cost_options)))
            )
        }
        assert hidden == expected_hidden, choam_module
        assert not hidden & CHOICE_DRIVEN_SPACE_IDS


def test_board_effects_for_delegates_to_the_static_table() -> None:
    for choam_module in (False, True):
        state = GameState(
            config=RulesetConfig(choam_module=choam_module),
            seed=1,
            players=tuple(PlayerState(player_id=seat) for seat in range(4)),
        )
        assert board_effects_for(state, "accept_contract", 0) == static_board_effects(
            "accept_contract",
            0,
            choam_module=choam_module,
        )
