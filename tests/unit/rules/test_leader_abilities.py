"""Tests for implemented Leader abilities and Signet Ring resolution."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.board import OBSERVATION_POSTS, Faction
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.core.engine import RuleResult
from dune_imperium.rules.agent_effects import resolve_agent_card_effect
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import resolve_board_effect
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.influence import (
    gain_faction_influence,
    lose_faction_influence,
)
from dune_imperium.rules.leader_abilities import (
    apply_feyd_track_action,
    apply_leader_board_repeat,
    apply_leader_card_trash,
    apply_leader_placement_ability,
    apply_leader_reveal_action,
    apply_leader_signet_acquire,
    apply_leader_signet_payment,
    apply_leader_spy_action,
    grant_leader_reveal_passives,
    legal_feyd_track_actions,
    legal_leader_board_repeat_actions,
    legal_leader_placement_ability_actions,
    legal_leader_reveal_actions,
    legal_leader_signet_actions,
)
from dune_imperium.rules.reveal_turn import begin_reveal_turn
from dune_imperium.rules.setup import create_initial_state


def _signet_instance(player: int = 0) -> str:
    return f"player:{player}:starter:signet_ring:0"


def _turn_state(owner: PlayerState) -> GameState:
    return GameState(
        config=RulesetConfig(),
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


def _signet_action_to(state: GameState, space_id: str) -> DomainAction:
    return _signet_action_to_card_id(state, space_id, _signet_instance())


def _signet_action_to_card_id(
    state: GameState,
    space_id: str,
    card_id: str,
) -> DomainAction:
    return next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == space_id
        and dict(action.arguments)["card_id"] == card_id
    )


def test_warmaster_signet_recruits_one_deployable_troop() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="gurney_halleck",
        hand=(_signet_instance(),),
    )
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)
    resolved = result.state.players[0]
    context = dict(result.state.decision_stack[-1].context)

    # Warmaster recruits one troop [Gurney Halleck card]; a troop recruited on
    # a Combat-space turn may still deploy [FAQ p. 4], so it joins the frame's
    # recruit count alongside the board recruits.
    assert resolved.troops_garrison == owner.troops_garrison + 1
    assert resolved.troops_supply == owner.troops_supply - 1
    assert context["troops_recruited"] == 1
    assert context["pending_agent_effect"] is False
    assert result.events[0].kind == "leader_signet_resolved"
    assert dict(result.events[0].payload)["troops"] == 1


def test_warmaster_signet_recruits_nothing_from_an_empty_supply() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="gurney_halleck",
        hand=(_signet_instance(),),
        troops_supply=0,
        troops_garrison=12,
    )
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].troops_garrison == 12
    assert dict(result.events[0].payload)["troops"] == 0


def test_fill_coffers_signet_gains_solari_only_without_an_alliance() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="lady_amber_metulli",
        hand=(_signet_instance(),),
    )
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)
    resources = result.state.players[0].resources

    assert resources.solari == 1
    assert resources.spice == 0
    assert dict(result.events[0].payload)["spice"] == 0


def test_fill_coffers_signet_adds_spice_while_holding_an_alliance() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="lady_amber_metulli",
        hand=(_signet_instance(),),
        alliance_faction_ids=("fremen",),
    )
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)
    resources = result.state.players[0].resources

    # Fill Coffers: one Solari, and one Spice with an Alliance [Lady Amber
    # Metulli card].
    assert resources.solari == 1
    assert resources.spice == 1


def test_signet_ring_stays_withheld_for_an_unimplemented_leader() -> None:
    engine = UprisingRulesEngine()
    implemented = _turn_state(
        PlayerState(
            player_id=0,
            leader_id="gurney_halleck",
            hand=(_signet_instance(),),
        )
    )
    unimplemented = _turn_state(
        PlayerState(
            player_id=0,
            leader_id="shaddam_corrino_iv",
            hand=(_signet_instance(),),
        )
    )

    assert any(
        dict(action.arguments).get("card_id") == _signet_instance()
        for action in engine.legal_actions(implemented, 0)
    )
    assert not any(
        dict(action.arguments).get("card_id") == _signet_instance()
        for action in engine.legal_actions(unimplemented, 0)
    )


def test_unimplemented_leader_signet_resolution_is_rejected() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="shaddam_corrino_iv",
        hand=(_signet_instance(),),
    )
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to(state, "arrakeen")).state

    with pytest.raises(RuntimeError, match="not implemented"):
        resolve_agent_card_effect(placed)


def _reveal_state(owner: PlayerState) -> GameState:
    return begin_reveal_turn(
        _turn_state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state


def test_desert_scouts_retreats_one_troop_during_the_reveal_turn() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="lady_amber_metulli",
        hand=("player:0:starter:dagger:0",),
        troops_supply=7,
        troops_garrison=3,
        troops_conflict=2,
    )
    revealed = _reveal_state(owner)
    context = dict(revealed.decision_stack[-1].context)
    assert context["strength"] == 2 * 2 + 1

    (action,) = legal_leader_reveal_actions(revealed, 0)
    assert action.action_id == "retreat_leader_troop"
    result = apply_leader_reveal_action(revealed, action)
    resolved = result.state.players[0]
    next_context = dict(result.state.decision_stack[-1].context)

    # Desert Scouts retreats one troop to the garrison [Lady Amber Metulli
    # card] [Main p. 20]; with a unit still in the Conflict only that troop's
    # two strength leaves the total.
    assert resolved.troops_conflict == 1
    assert resolved.troops_garrison == 4
    assert resolved.combat_strength == 3
    assert next_context["strength"] == 3
    assert next_context["leader_reveal_ability_used"] is True
    assert legal_leader_reveal_actions(result.state, 0) == ()


def test_desert_scouts_retreating_the_last_unit_zeroes_the_strength() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="lady_amber_metulli",
        hand=("player:0:starter:dagger:0",),
        troops_supply=8,
        troops_garrison=3,
        troops_conflict=1,
    )
    revealed = _reveal_state(owner)

    (action,) = legal_leader_reveal_actions(revealed, 0)
    result = apply_leader_reveal_action(revealed, action)

    assert result.state.players[0].troops_conflict == 0
    assert result.state.players[0].combat_strength == 0
    assert dict(result.state.decision_stack[-1].context)["strength"] == 0


def test_desert_scouts_is_not_offered_without_conflict_troops() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="lady_amber_metulli",
        hand=("player:0:starter:dagger:0",),
    )
    revealed = _reveal_state(owner)

    assert legal_leader_reveal_actions(revealed, 0) == ()


def test_desert_scouts_is_not_offered_to_other_leaders() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="gurney_halleck",
        hand=("player:0:starter:dagger:0",),
        troops_supply=7,
        troops_garrison=3,
        troops_conflict=2,
    )
    revealed = _reveal_state(owner)

    assert legal_leader_reveal_actions(revealed, 0) == ()


def test_always_smiling_grants_persuasion_at_six_strength() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="gurney_halleck",
        hand=("player:0:starter:dagger:0", "player:0:starter:dagger:1"),
        troops_supply=7,
        troops_garrison=3,
        troops_conflict=2,
    )
    revealed = _reveal_state(owner)
    assert dict(revealed.decision_stack[-1].context)["strength"] == 6

    result = grant_leader_reveal_passives(RuleResult(state=revealed))
    context = dict(result.state.decision_stack[-1].context)

    # Always Smiling: six or more strength during the Reveal turn grants one
    # Persuasion in the four-player game [Gurney Halleck card].
    assert context["persuasion"] == 1
    assert context["leader_persuasion_granted"] is True
    assert result.events[-1].kind == "reveal_persuasion_gained"


def test_always_smiling_stays_quiet_below_six_strength() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="gurney_halleck",
        hand=("player:0:starter:dagger:0",),
        troops_supply=7,
        troops_garrison=3,
        troops_conflict=2,
    )
    revealed = _reveal_state(owner)
    assert dict(revealed.decision_stack[-1].context)["strength"] == 5

    result = grant_leader_reveal_passives(RuleResult(state=revealed))

    assert result.state is revealed
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 0


def test_always_smiling_does_not_grant_twice() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="gurney_halleck",
        hand=("player:0:starter:dagger:0", "player:0:starter:dagger:1"),
        troops_supply=7,
        troops_garrison=3,
        troops_conflict=2,
    )
    revealed = _reveal_state(owner)

    first = grant_leader_reveal_passives(RuleResult(state=revealed))
    second = grant_leader_reveal_passives(RuleResult(state=first.state))

    assert second.state is first.state
    assert dict(second.state.decision_stack[-1].context)["persuasion"] == 1


def test_always_smiling_is_wired_through_the_engine_reveal() -> None:
    engine = UprisingRulesEngine()
    owner = PlayerState(
        player_id=0,
        leader_id="gurney_halleck",
        hand=("player:0:starter:dagger:0", "player:0:starter:dagger:1"),
        troops_supply=7,
        troops_garrison=3,
        troops_conflict=2,
    )
    state = _turn_state(owner)

    transition = engine.apply(state, DomainAction(action_id="reveal_turn", actor=0))
    context = dict(transition.state.decision_stack[-1].context)

    assert context["persuasion"] == 1
    assert context["leader_persuasion_granted"] is True


def _feyd_effect_state(
    *,
    track_space: str = "start",
    solari: int = 0,
    spies_supply: int = 3,
    spy_post_ids: tuple[str, ...] = (),
    extra_hand: tuple[str, ...] = (),
) -> GameState:
    owner = PlayerState(
        player_id=0,
        leader_id="feyd_rautha_harkonnen",
        hand=(_signet_instance(), *extra_hand),
        resources=Resources(solari=solari),
        feyd_track_space=track_space,
        spies_supply=spies_supply,
        spy_post_ids=spy_post_ids,
    )
    state = _turn_state(owner)
    return apply_agent_action(state, _signet_action_to(state, "arrakeen")).state


def test_personal_training_offers_the_start_fork() -> None:
    placed = _feyd_effect_state()

    actions = legal_feyd_track_actions(placed, 0)

    assert {dict(action.arguments)["space_id"] for action in actions} == {
        "paid_trash",
        "first_spy",
    }
    assert all(action.action_id == "advance_feyd_track" for action in actions)


def test_personal_training_spy_space_places_a_spy() -> None:
    placed = _feyd_effect_state()
    advance = next(
        action
        for action in legal_feyd_track_actions(placed, 0)
        if dict(action.arguments)["space_id"] == "first_spy"
    )
    advanced = apply_feyd_track_action(placed, advance)
    assert advanced.state.players[0].feyd_track_space == "first_spy"
    assert advanced.events[0].kind == "feyd_token_advanced"

    stage_actions = legal_feyd_track_actions(advanced.state, 0)
    assert all(
        action.action_id == "place_leader_spy" for action in stage_actions
    )
    placement = stage_actions[0]
    result = apply_feyd_track_action(advanced.state, placement)

    assert result.state.players[0].spies_supply == 2
    assert len(result.state.players[0].spy_post_ids) == 1
    context = dict(result.state.decision_stack[-1].context)
    assert context["pending_agent_effect"] is False
    assert "feyd_track_stage" not in context


def test_personal_training_paid_trash_pays_one_solari() -> None:
    dagger = "player:0:starter:dagger:0"
    placed = _feyd_effect_state(solari=1, extra_hand=(dagger,))
    advance = next(
        action
        for action in legal_feyd_track_actions(placed, 0)
        if dict(action.arguments)["space_id"] == "paid_trash"
    )
    advanced = apply_feyd_track_action(placed, advance).state

    stage_actions = legal_feyd_track_actions(advanced, 0)
    assert stage_actions[0].action_id == "decline_leader_card_trash"
    trash = next(
        action
        for action in stage_actions
        if dict(action.arguments).get("card_id") == dagger
    )
    result = apply_feyd_track_action(advanced, trash)

    assert result.state.players[0].resources.solari == 0
    assert dagger in result.state.players[0].trashed
    assert dict(result.state.decision_stack[-1].context)[
        "pending_agent_effect"
    ] is False


def test_personal_training_paid_trash_without_solari_only_declines() -> None:
    placed = _feyd_effect_state(solari=0)
    advance = next(
        action
        for action in legal_feyd_track_actions(placed, 0)
        if dict(action.arguments)["space_id"] == "paid_trash"
    )
    advanced = apply_feyd_track_action(placed, advance).state

    actions = legal_feyd_track_actions(advanced, 0)

    # The one-Solari arrow cost cannot be paid, so only the decline remains
    # [Main pp. 9, 20].
    assert [action.action_id for action in actions] == [
        "decline_leader_card_trash"
    ]
    result = apply_feyd_track_action(advanced, actions[0])
    assert dict(result.state.decision_stack[-1].context)[
        "pending_agent_effect"
    ] is False


def test_personal_training_double_spice_space_is_automatic() -> None:
    placed = _feyd_effect_state(track_space="second_spy")

    advance = next(
        action
        for action in legal_feyd_track_actions(placed, 0)
        if dict(action.arguments)["space_id"] == "double_spice"
    )
    result = apply_feyd_track_action(placed, advance)

    assert result.state.players[0].resources.spice == 2
    context = dict(result.state.decision_stack[-1].context)
    assert context["pending_agent_effect"] is False
    assert result.events[-1].kind == "leader_signet_resolved"


def test_personal_training_final_space_recruits_and_places_a_spy() -> None:
    placed = _feyd_effect_state(track_space="late_trash")

    advance = next(
        action
        for action in legal_feyd_track_actions(placed, 0)
        if dict(action.arguments)["space_id"] == "final"
    )
    advanced = apply_feyd_track_action(placed, advance)
    assert advanced.state.players[0].troops_garrison == 4
    assert (
        dict(advanced.state.decision_stack[-1].context)["troops_recruited"] == 1
    )

    stage_actions = legal_feyd_track_actions(advanced.state, 0)
    result = apply_feyd_track_action(advanced.state, stage_actions[0])

    assert result.state.players[0].spies_supply == 2
    assert result.state.players[0].feyd_track_space == "final"


def test_personal_training_at_the_final_space_gives_no_reward() -> None:
    placed = _feyd_effect_state(track_space="final")

    # The token remains on the rightmost space [Main p. 17]; with no new
    # space to move to, Personal Training earns nothing.
    assert legal_feyd_track_actions(placed, 0) == ()
    result = resolve_agent_card_effect(placed)

    assert result.events[0].kind == "agent_card_effect_unavailable"
    assert dict(result.state.decision_stack[-1].context)[
        "pending_agent_effect"
    ] is False


def test_personal_training_spy_stage_recalls_first_without_supply() -> None:
    posts = tuple(post.post_id for post in OBSERVATION_POSTS[:3])
    placed = _feyd_effect_state(spies_supply=0, spy_post_ids=posts)
    advance = next(
        action
        for action in legal_feyd_track_actions(placed, 0)
        if dict(action.arguments)["space_id"] == "first_spy"
    )
    advanced = apply_feyd_track_action(placed, advance).state

    recall_actions = legal_feyd_track_actions(advanced, 0)
    assert all(
        action.action_id == "recall_spy_for_leader_placement"
        for action in recall_actions
    )
    recalled = apply_feyd_track_action(advanced, recall_actions[0]).state
    assert dict(recalled.decision_stack[-1].context)["feyd_spy_recalled"] is True

    placements = legal_feyd_track_actions(recalled, 0)
    assert all(action.action_id == "place_leader_spy" for action in placements)
    result = apply_feyd_track_action(recalled, placements[0])

    assert result.state.players[0].spies_supply == 0
    assert len(result.state.players[0].spy_post_ids) == 3


def test_devious_strength_recalls_a_spy_for_two_swords() -> None:
    post_id = OBSERVATION_POSTS[0].post_id
    owner = PlayerState(
        player_id=0,
        leader_id="feyd_rautha_harkonnen",
        hand=("player:0:starter:dagger:0",),
        troops_supply=8,
        troops_garrison=3,
        troops_conflict=1,
        spies_supply=2,
        spy_post_ids=(post_id,),
    )
    revealed = _reveal_state(owner)
    assert dict(revealed.decision_stack[-1].context)["strength"] == 3

    (action,) = legal_leader_reveal_actions(revealed, 0)
    assert action.action_id == "recall_spy_for_leader"
    result = apply_leader_reveal_action(revealed, action)
    resolved = result.state.players[0]
    context = dict(result.state.decision_stack[-1].context)

    assert resolved.spies_supply == 3
    assert resolved.spy_post_ids == ()
    assert resolved.combat_strength == 5
    assert context["strength"] == 5
    assert context["optional_sword_strength"] == 2
    assert context["leader_reveal_ability_used"] is True
    assert legal_leader_reveal_actions(result.state, 0) == ()


def test_devious_strength_swords_do_not_count_without_units() -> None:
    post_id = OBSERVATION_POSTS[0].post_id
    owner = PlayerState(
        player_id=0,
        leader_id="feyd_rautha_harkonnen",
        hand=("player:0:starter:dagger:0",),
        spies_supply=2,
        spy_post_ids=(post_id,),
    )
    revealed = _reveal_state(owner)

    (action,) = legal_leader_reveal_actions(revealed, 0)
    result = apply_leader_reveal_action(revealed, action)
    context = dict(result.state.decision_stack[-1].context)

    # Swords only count while units are in the Conflict [Main pp. 12-13]; the
    # chosen bonus is still recorded for later deployments.
    assert result.state.players[0].combat_strength == 0
    assert context["strength"] == 0
    assert context["optional_sword_strength"] == 2


def test_devious_strength_is_not_offered_without_placed_spies() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="feyd_rautha_harkonnen",
        hand=("player:0:starter:dagger:0",),
        troops_supply=8,
        troops_garrison=3,
        troops_conflict=1,
    )
    revealed = _reveal_state(owner)

    assert legal_leader_reveal_actions(revealed, 0) == ()


def _jessica_owner(
    *,
    face: str = "lady_jessica",
    spice: int = 0,
    water: int = 1,
    memories: int = 0,
    hand: tuple[str, ...] = (),
    deck: tuple[str, ...] = (),
) -> PlayerState:
    return PlayerState(
        player_id=0,
        leader_id="lady_jessica",
        leader_face_id=face,
        resources=Resources(spice=spice, water=water),
        troops_supply=9 - memories,
        memories=memories,
        hand=hand,
        deck=deck,
    )


def test_spice_agony_pays_for_an_intrigue_card_and_a_memory() -> None:
    owner = _jessica_owner(spice=1, hand=(_signet_instance(),))
    state = replace(_turn_state(owner), intrigue_deck=("intrigue:test",))
    placed = apply_agent_action(state, _signet_action_to(state, "arrakeen")).state

    actions = legal_leader_signet_actions(placed, 0)
    assert {action.action_id for action in actions} == {
        "decline_leader_signet_payment",
        "pay_leader_signet_spice",
    }
    pay = next(
        action for action in actions if action.action_id == "pay_leader_signet_spice"
    )
    result = apply_leader_signet_payment(placed, pay)
    resolved = result.state.players[0]
    context = dict(result.state.decision_stack[-1].context)

    # Spice Agony: one Spice buys one Intrigue card and moves a supply troop
    # to the Bene Gesserit area as a memory [Lady Jessica card].
    assert resolved.resources.spice == 0
    assert resolved.spice_spent_turn == 1
    assert context["spice_spent_after_placement"] == 1
    assert resolved.intrigue_cards == ("intrigue:test",)
    assert resolved.memories == 1
    assert resolved.troops_supply == 8
    assert context["pending_agent_effect"] is False


def test_spice_agony_without_spice_only_declines() -> None:
    owner = _jessica_owner(spice=0, hand=(_signet_instance(),))
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to(state, "arrakeen")).state

    actions = legal_leader_signet_actions(placed, 0)

    assert [action.action_id for action in actions] == [
        "decline_leader_signet_payment"
    ]
    result = apply_leader_signet_payment(placed, actions[0])
    assert result.state.players[0].memories == 0
    assert dict(result.state.decision_stack[-1].context)[
        "pending_agent_effect"
    ] is False


def test_spice_agony_with_an_empty_supply_still_draws_intrigue() -> None:
    owner = replace(
        _jessica_owner(spice=1, hand=(_signet_instance(),)),
        troops_supply=0,
        troops_garrison=12,
    )
    state = replace(_turn_state(owner), intrigue_deck=("intrigue:test",))
    placed = apply_agent_action(state, _signet_action_to(state, "arrakeen")).state

    pay = next(
        action
        for action in legal_leader_signet_actions(placed, 0)
        if action.action_id == "pay_leader_signet_spice"
    )
    result = apply_leader_signet_payment(placed, pay)

    assert result.state.players[0].intrigue_cards == ("intrigue:test",)
    assert result.state.players[0].memories == 0


def test_water_of_life_pays_one_spice_for_one_water() -> None:
    owner = _jessica_owner(
        face="reverend_mother_jessica",
        spice=1,
        water=0,
        hand=(_signet_instance(),),
    )
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to(state, "arrakeen")).state

    pay = next(
        action
        for action in legal_leader_signet_actions(placed, 0)
        if action.action_id == "pay_leader_signet_spice"
    )
    result = apply_leader_signet_payment(placed, pay)

    # Water of Life: one Spice buys one water [Reverend Mother Jessica card].
    assert result.state.players[0].resources.spice == 0
    assert result.state.players[0].resources.water == 1


def _diplomacy_instance() -> str:
    return "player:0:starter:diplomacy:0"


def _signet_action_to_card(state: GameState, space_id: str) -> DomainAction:
    return next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == space_id
        and dict(action.arguments)["card_id"] == _diplomacy_instance()
    )


def test_other_memories_flips_and_draws_per_memory() -> None:
    dagger = "player:0:starter:dagger:0"
    second = "player:0:starter:dagger:1"
    owner = _jessica_owner(
        spice=1,
        memories=2,
        hand=(_diplomacy_instance(),),
        deck=(dagger, second),
    )
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to_card(state, "espionage")).state
    assert dict(placed.decision_stack[-1].context)["pending_leader_ability"] is True

    actions = legal_leader_placement_ability_actions(placed, 0)
    assert {action.action_id for action in actions} == {
        "use_other_memories",
        "decline_other_memories",
    }
    use = next(
        action for action in actions if action.action_id == "use_other_memories"
    )
    result = apply_leader_placement_ability(placed, use)
    resolved = result.state.players[0]
    context = dict(result.state.decision_stack[-1].context)

    # Other Memories returns every memory, draws one card per memory, and
    # flips the Leader [Lady Jessica card]; the Reverend Mother ability opens
    # on this same turn [FAQ p. 3].
    assert resolved.leader_face_id == "reverend_mother_jessica"
    assert resolved.memories == 0
    assert resolved.troops_supply == 9
    assert set(resolved.hand) >= {dagger, second}
    assert context["pending_leader_ability"] is False
    assert context["pending_leader_board_repeat"] is True
    assert result.events[0].kind == "leader_flipped"


def test_other_memories_with_no_memories_still_flips() -> None:
    owner = _jessica_owner(spice=1, memories=0, hand=(_diplomacy_instance(),))
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to_card(state, "espionage")).state

    use = next(
        action
        for action in legal_leader_placement_ability_actions(placed, 0)
        if action.action_id == "use_other_memories"
    )
    result = apply_leader_placement_ability(placed, use)

    assert result.state.players[0].leader_face_id == "reverend_mother_jessica"
    assert len(result.events) == 1
    assert dict(result.events[0].payload)["memories_returned"] == 0


def test_other_memories_declining_keeps_the_lady_jessica_face() -> None:
    owner = _jessica_owner(spice=1, memories=1, hand=(_diplomacy_instance(),))
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to_card(state, "espionage")).state

    decline = next(
        action
        for action in legal_leader_placement_ability_actions(placed, 0)
        if action.action_id == "decline_other_memories"
    )
    result = apply_leader_placement_ability(placed, decline)

    assert result.state.players[0].leader_face_id == "lady_jessica"
    assert result.state.players[0].memories == 1
    assert dict(result.state.decision_stack[-1].context)[
        "pending_leader_ability"
    ] is False


def test_other_memories_is_not_pending_outside_bene_gesserit_spaces() -> None:
    owner = _jessica_owner(memories=1, hand=(_diplomacy_instance(),))
    state = _turn_state(owner)
    placed = apply_agent_action(
        state, _signet_action_to_card(state, "dutiful_service")
    ).state

    assert dict(placed.decision_stack[-1].context)["pending_leader_ability"] is False
    assert legal_leader_placement_ability_actions(placed, 0) == ()


def test_reverend_mother_repeats_a_board_space_for_one_water() -> None:
    dagger = "player:0:starter:dagger:0"
    second = "player:0:starter:dagger:1"
    owner = _jessica_owner(
        face="reverend_mother_jessica",
        water=1,
        hand=(_diplomacy_instance(),),
        deck=(dagger, second),
    )
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to_card(state, "fremkit")).state
    context = dict(placed.decision_stack[-1].context)
    assert context["pending_leader_board_repeat"] is True

    # The repeat waits for the printed effect's first resolution.
    assert legal_leader_board_repeat_actions(placed, 0) == ()
    first = resolve_board_effect(placed)
    assert first.state.players[0].hand[-1] == dagger

    actions = legal_leader_board_repeat_actions(first.state, 0)
    assert {action.action_id for action in actions} == {
        "decline_leader_board_repeat",
        "pay_leader_board_repeat",
    }
    pay = next(
        action for action in actions if action.action_id == "pay_leader_board_repeat"
    )
    paid = apply_leader_board_repeat(first.state, pay)
    paid_context = dict(paid.state.decision_stack[-1].context)

    assert paid.state.players[0].resources.water == 0
    assert paid_context["pending_board_effect"] is True
    assert paid_context["pending_leader_board_repeat"] is False

    second_pass = resolve_board_effect(paid.state)
    assert second_pass.state.players[0].hand[-1] == second
    assert legal_leader_board_repeat_actions(second_pass.state, 0) == ()


def test_reverend_mother_repeat_without_water_only_declines() -> None:
    owner = _jessica_owner(
        face="reverend_mother_jessica",
        water=0,
        hand=(_diplomacy_instance(),),
        deck=("player:0:starter:dagger:0",),
    )
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to_card(state, "fremkit")).state
    first = resolve_board_effect(placed)

    actions = legal_leader_board_repeat_actions(first.state, 0)

    assert [action.action_id for action in actions] == [
        "decline_leader_board_repeat"
    ]
    result = apply_leader_board_repeat(first.state, actions[0])
    assert dict(result.state.decision_stack[-1].context)[
        "pending_leader_board_repeat"
    ] is False


def test_lady_jessica_repeat_is_not_pending_before_the_flip() -> None:
    owner = _jessica_owner(hand=(_diplomacy_instance(),))
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to_card(state, "fremkit")).state

    assert dict(placed.decision_stack[-1].context)[
        "pending_leader_board_repeat"
    ] is False


def test_setup_assigns_the_printed_leader_faces() -> None:
    from dune_imperium import RulesetConfig as _Config

    setup = create_initial_state(
        _Config(),
        seed=5,
        leader_ids=(
            "feyd_rautha_harkonnen",
            "gurney_halleck",
            "lady_amber_metulli",
            "lady_jessica",
        ),
    )

    faces = tuple(player.leader_face_id for player in setup.state.players)

    # Lady Jessica starts on her Lady Jessica face [Main p. 17]; single-faced
    # Leaders show their identity.
    assert faces == (
        "feyd_rautha_harkonnen",
        "gurney_halleck",
        "lady_amber_metulli",
        "lady_jessica",
    )


def test_loyalty_grants_two_spice_on_reaching_two_bene_gesserit() -> None:
    owner = PlayerState(player_id=0, leader_id="lady_margot_fenring")
    state = _turn_state(owner)

    result = gain_faction_influence(
        state,
        0,
        Faction.BENE_GESSERIT,
        2,
        event_prefix="test:loyalty",
    )
    resolved = result.state.players[0]

    # Loyalty: reaching two Bene Gesserit Influence grants two Spice, and
    # passing 2 within one multi-step gain counts [Main pp. 7, 17].
    assert resolved.influence.bene_gesserit == 2
    assert resolved.resources.spice == 2
    assert any(
        event.kind == "leader_influence_bonus_gained" for event in result.events
    )


def test_loyalty_triggers_again_after_dropping_below_two() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="lady_margot_fenring",
        influence=Influence(bene_gesserit=2),
        victory_points=2,
    )
    state = _turn_state(owner)

    lost = lose_faction_influence(
        state,
        0,
        Faction.BENE_GESSERIT,
        1,
        event_prefix="test:loyalty:loss",
    )
    assert lost.state.players[0].resources.spice == 0

    regained = gain_faction_influence(
        lost.state,
        0,
        Faction.BENE_GESSERIT,
        1,
        event_prefix="test:loyalty:regain",
    )

    assert regained.state.players[0].resources.spice == 2


def test_loyalty_ignores_other_factions_and_leaders() -> None:
    margot = PlayerState(player_id=0, leader_id="lady_margot_fenring")
    state = _turn_state(margot)

    other_faction = gain_faction_influence(
        state,
        0,
        Faction.EMPEROR,
        2,
        event_prefix="test:loyalty:other",
    )
    assert other_faction.state.players[0].resources.spice == 0

    gurney_state = _turn_state(
        PlayerState(player_id=0, leader_id="gurney_halleck")
    )
    other_leader = gain_faction_influence(
        gurney_state,
        0,
        Faction.BENE_GESSERIT,
        2,
        event_prefix="test:loyalty:gurney",
    )
    assert other_leader.state.players[0].resources.spice == 0


def test_imperial_birthright_draws_an_intrigue_card_on_reaching_two() -> None:
    owner = PlayerState(player_id=0, leader_id="princess_irulan")
    state = replace(_turn_state(owner), intrigue_deck=("intrigue:test",))

    result = gain_faction_influence(
        state,
        0,
        Faction.EMPEROR,
        2,
        event_prefix="test:birthright",
    )

    assert result.state.players[0].intrigue_cards == ("intrigue:test",)
    assert result.state.intrigue_deck == ()


def test_imperial_birthright_queues_the_draw_on_an_empty_deck() -> None:
    owner = PlayerState(player_id=0, leader_id="princess_irulan")
    state = _turn_state(owner)

    result = gain_faction_influence(
        state,
        0,
        Faction.EMPEROR,
        2,
        event_prefix="test:birthright:empty",
    )

    (owed,) = result.state.pending_intrigue_draws
    assert owed[:2] == (0, 1)


def test_arrakis_informant_places_a_spy_only_next_to_city_spaces() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="lady_margot_fenring",
        hand=(_signet_instance(),),
    )
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to(state, "arrakeen")).state

    actions = legal_leader_signet_actions(placed, 0)

    # Arrakis Informant: a Spy on a post connected to a City board space
    # [Lady Margot Fenring card] [Main p. 20].
    assert {action.action_id for action in actions} == {"place_leader_spy"}
    assert {dict(action.arguments)["post_id"] for action in actions} == {
        "arrakis-research-station-spice-refinery",
        "arrakis-research-station-sietch-tabr",
        "arrakis-spice-refinery-arrakeen",
    }
    result = apply_leader_spy_action(placed, actions[0])
    assert result.state.players[0].spies_supply == 2
    assert dict(result.state.decision_stack[-1].context)[
        "pending_agent_effect"
    ] is False


def test_arrakis_informant_fizzles_when_every_city_post_is_taken() -> None:
    city_posts = (
        "arrakis-research-station-spice-refinery",
        "arrakis-research-station-sietch-tabr",
        "arrakis-spice-refinery-arrakeen",
    )
    owner = PlayerState(
        player_id=0,
        leader_id="lady_margot_fenring",
        hand=(_signet_instance(),),
    )
    state = _turn_state(owner)
    opponent = replace(
        state.players[1],
        spies_supply=0,
        spy_post_ids=city_posts,
    )
    crowded = replace(state, players=(state.players[0], opponent, *state.players[2:]))
    placed = apply_agent_action(
        crowded, _signet_action_to(crowded, "arrakeen")
    ).state

    assert legal_leader_signet_actions(placed, 0) == ()
    result = resolve_agent_card_effect(placed)

    assert result.events[0].kind == "agent_card_effect_unavailable"


def test_lead_the_way_signet_draws_one_card() -> None:
    drawn = "player:0:starter:dagger:0"
    owner = PlayerState(
        player_id=0,
        leader_id="muad_dib",
        hand=(_signet_instance(),),
        deck=(drawn,),
    )
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)

    assert drawn in result.state.players[0].hand
    assert result.events[0].kind == "leader_signet_resolved"


def test_unpredictable_foe_draws_intrigue_with_a_sandworm() -> None:
    engine = UprisingRulesEngine()
    owner = PlayerState(
        player_id=0,
        leader_id="muad_dib",
        hand=("player:0:starter:dagger:0",),
        sandworms_conflict=1,
    )
    state = replace(_turn_state(owner), intrigue_deck=("intrigue:test",))

    transition = engine.apply(state, DomainAction(action_id="reveal_turn", actor=0))
    context = dict(transition.state.decision_stack[-1].context)

    # Unpredictable Foe: one or more sandworms in the Conflict during the
    # Reveal turn draw one Intrigue card [Muad'Dib card].
    assert transition.state.players[0].intrigue_cards == ("intrigue:test",)
    assert context["leader_intrigue_granted"] is True


def test_unpredictable_foe_stays_quiet_without_sandworms() -> None:
    engine = UprisingRulesEngine()
    owner = PlayerState(
        player_id=0,
        leader_id="muad_dib",
        hand=("player:0:starter:dagger:0",),
    )
    state = replace(_turn_state(owner), intrigue_deck=("intrigue:test",))

    transition = engine.apply(state, DomainAction(action_id="reveal_turn", actor=0))

    assert transition.state.players[0].intrigue_cards == ()
    assert "leader_intrigue_granted" not in dict(
        transition.state.decision_stack[-1].context
    )


def test_limited_allies_removes_diplomacy_from_the_starting_deck() -> None:
    setup = create_initial_state(
        RulesetConfig(),
        seed=9,
        leader_ids=(
            "staban_tuek",
            "gurney_halleck",
            "lady_amber_metulli",
            "lady_jessica",
        ),
    )

    staban_zones = (
        *setup.state.players[0].deck,
        *setup.state.players[0].hand,
        *setup.state.players[0].discard_pile,
    )
    other_zones = (
        *setup.state.players[1].deck,
        *setup.state.players[1].hand,
    )

    # Limited Allies: Staban Tuek starts without Diplomacy [Staban Tuek card].
    assert not any("diplomacy" in card_id for card_id in staban_zones)
    assert len(staban_zones) == 9
    assert any("diplomacy" in card_id for card_id in other_zones)


def test_smuggle_spice_pays_staban_for_spied_maker_visits() -> None:
    staban = PlayerState(
        player_id=1,
        leader_id="staban_tuek",
        spies_supply=2,
        spy_post_ids=("arrakis-hagga-basin",),
    )
    visitor = PlayerState(
        player_id=0,
        hand=("player:0:starter:dune_the_desert_planet:0",),
    )
    state = replace(
        _turn_state(visitor),
        players=(visitor, staban, *(_turn_state(visitor).players[2:])),
    )

    result = apply_agent_action(state, _signet_action_to_card_id(
        state, "hagga_basin", "player:0:starter:dune_the_desert_planet:0"
    ))

    # Smuggle Spice: another player's Agent on a spied Maker space pays one
    # Spice [Staban Tuek card].
    assert result.state.players[1].resources.spice == 1
    assert any(
        event.kind == "leader_ability_spice_gained" for event in result.events
    )


def test_smuggle_spice_needs_a_spy_on_the_visited_maker_space() -> None:
    staban = PlayerState(
        player_id=1,
        leader_id="staban_tuek",
        spies_supply=2,
        spy_post_ids=("arrakis-deep-desert",),
    )
    visitor = PlayerState(
        player_id=0,
        hand=("player:0:starter:dune_the_desert_planet:0",),
    )
    state = replace(
        _turn_state(visitor),
        players=(visitor, staban, *(_turn_state(visitor).players[2:])),
    )

    result = apply_agent_action(state, _signet_action_to_card_id(
        state, "hagga_basin", "player:0:starter:dune_the_desert_planet:0"
    ))

    assert result.state.players[1].resources.spice == 0


def test_smuggle_spice_ignores_stabans_own_maker_visits() -> None:
    staban = PlayerState(
        player_id=0,
        leader_id="staban_tuek",
        hand=("player:0:starter:dune_the_desert_planet:0",),
        spies_supply=2,
        spy_post_ids=("arrakis-hagga-basin",),
    )
    state = _turn_state(staban)

    result = apply_agent_action(state, _signet_action_to_card_id(
        state, "hagga_basin", "player:0:starter:dune_the_desert_planet:0"
    ))

    assert result.state.players[0].resources.spice == 0


def test_unseen_network_offers_the_landsraad_bonus() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="staban_tuek",
        hand=(_signet_instance(),),
        resources=Resources(spice=1),
    )
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to(state, "arrakeen")).state

    placement = next(
        action
        for action in legal_leader_signet_actions(placed, 0)
        if dict(action.arguments)["post_id"]
        == "landsraad-assembly-hall-gather-support"
    )
    after_spy = apply_leader_spy_action(placed, placement)
    context = dict(after_spy.state.decision_stack[-1].context)
    assert context["staban_bonus_post"] == "landsraad-assembly-hall-gather-support"

    actions = legal_leader_signet_actions(after_spy.state, 0)
    assert {action.action_id for action in actions} == {
        "decline_leader_signet_payment",
        "pay_leader_signet_spice",
    }
    pay = next(
        action for action in actions if action.action_id == "pay_leader_signet_spice"
    )
    result = apply_leader_signet_payment(after_spy.state, pay)
    resolved = result.state.players[0]

    # Unseen Network next to the Landsraad: one Spice buys three Solari
    # [Staban Tuek card].
    assert resolved.resources.spice == 0
    assert resolved.resources.solari == 3
    assert dict(result.state.decision_stack[-1].context)[
        "pending_agent_effect"
    ] is False


def test_unseen_network_offers_the_faction_bonus() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="staban_tuek",
        hand=(_signet_instance(),),
        resources=Resources(solari=2),
    )
    state = replace(_turn_state(owner), intrigue_deck=("intrigue:test",))
    placed = apply_agent_action(state, _signet_action_to(state, "arrakeen")).state

    placement = next(
        action
        for action in legal_leader_signet_actions(placed, 0)
        if dict(action.arguments)["post_id"] == "emperor-sardaukar-dutiful-service"
    )
    after_spy = apply_leader_spy_action(placed, placement)

    pay = next(
        action
        for action in legal_leader_signet_actions(after_spy.state, 0)
        if action.action_id == "pay_leader_signet_solari"
    )
    result = apply_leader_signet_payment(after_spy.state, pay)
    resolved = result.state.players[0]

    # Unseen Network next to a Faction: two Solari buy one Intrigue card
    # [Staban Tuek card].
    assert resolved.resources.solari == 0
    assert resolved.intrigue_cards == ("intrigue:test",)


def test_unseen_network_has_no_bonus_on_other_posts() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="staban_tuek",
        hand=(_signet_instance(),),
        resources=Resources(spice=3, solari=3),
    )
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to(state, "arrakeen")).state

    placement = next(
        action
        for action in legal_leader_signet_actions(placed, 0)
        if dict(action.arguments)["post_id"] == "choam-shipping-accept-contract"
    )
    result = apply_leader_spy_action(placed, placement)
    context = dict(result.state.decision_stack[-1].context)

    assert "staban_bonus_post" not in context
    assert context["pending_agent_effect"] is False


def test_unseen_network_bonus_without_funds_only_declines() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="staban_tuek",
        hand=(_signet_instance(),),
    )
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to(state, "arrakeen")).state

    placement = next(
        action
        for action in legal_leader_signet_actions(placed, 0)
        if dict(action.arguments)["post_id"]
        == "landsraad-assembly-hall-gather-support"
    )
    after_spy = apply_leader_spy_action(placed, placement)

    actions = legal_leader_signet_actions(after_spy.state, 0)

    assert [action.action_id for action in actions] == [
        "decline_leader_signet_payment"
    ]
    result = apply_leader_signet_payment(after_spy.state, actions[0])
    context = dict(result.state.decision_stack[-1].context)
    assert context["pending_agent_effect"] is False
    assert "staban_bonus_post" not in context


def test_chroniclers_insight_acquires_a_one_cost_card_to_hand() -> None:
    target = "imperium:sardaukar_soldier:0"
    refill = "imperium:overthrow:0"
    owner = PlayerState(
        player_id=0,
        leader_id="princess_irulan",
        hand=(_signet_instance(),),
    )
    state = replace(
        _turn_state(owner),
        imperium_row=(target, "imperium:calculus_of_power:0"),
        imperium_deck=(refill,),
    )
    placed = apply_agent_action(state, _signet_action_to(state, "arrakeen")).state

    actions = legal_leader_signet_actions(placed, 0)
    acquire = next(
        action
        for action in actions
        if action.action_id == "acquire_leader_imperium"
    )
    assert dict(acquire.arguments)["instance_id"] == target
    result = apply_leader_signet_acquire(placed, acquire)
    resolved = result.state.players[0]

    # Chronicler's Insight: acquire a card that costs one to your hand
    # [Princess Irulan card]; the Row refills at once [Main p. 13].
    assert target in resolved.hand
    assert refill in result.state.imperium_row
    assert dict(result.state.decision_stack[-1].context)[
        "pending_agent_effect"
    ] is False


def test_chroniclers_insight_trash_pays_spice_only_for_costed_cards() -> None:
    costed = "imperium:overthrow:0"
    starter = "player:0:starter:dagger:0"
    owner = PlayerState(
        player_id=0,
        leader_id="princess_irulan",
        hand=(_signet_instance(), costed, starter),
    )
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to(state, "arrakeen")).state

    trash_costed = next(
        action
        for action in legal_leader_signet_actions(placed, 0)
        if dict(action.arguments).get("card_id") == costed
    )
    result = apply_leader_card_trash(placed, trash_costed)
    assert costed in result.state.players[0].trashed
    assert result.state.players[0].resources.spice == 2

    trash_starter = next(
        action
        for action in legal_leader_signet_actions(placed, 0)
        if dict(action.arguments).get("card_id") == starter
    )
    starter_result = apply_leader_card_trash(placed, trash_starter)
    assert starter in starter_result.state.players[0].trashed
    assert starter_result.state.players[0].resources.spice == 0


def test_chroniclers_insight_can_decline_entirely() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="princess_irulan",
        hand=(_signet_instance(),),
    )
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to(state, "arrakeen")).state

    actions = legal_leader_signet_actions(placed, 0)
    decline = next(
        action
        for action in actions
        if action.action_id == "decline_leader_signet_payment"
    )
    result = apply_leader_signet_payment(placed, decline)

    assert dict(result.state.decision_stack[-1].context)[
        "pending_agent_effect"
    ] is False
