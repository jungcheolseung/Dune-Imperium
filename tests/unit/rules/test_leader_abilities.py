"""Tests for implemented Leader abilities and Signet Ring resolution."""



import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.board import OBSERVATION_POSTS
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.core.engine import RuleResult
from dune_imperium.rules.agent_effects import resolve_agent_card_effect
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.leader_abilities import (
    apply_feyd_track_action,
    apply_leader_reveal_action,
    grant_leader_reveal_passives,
    legal_feyd_track_actions,
    legal_leader_reveal_actions,
)
from dune_imperium.rules.reveal_turn import begin_reveal_turn


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
    return next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == space_id
        and dict(action.arguments)["card_id"] == _signet_instance()
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
            leader_id="muad_dib",
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
        leader_id="muad_dib",
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
