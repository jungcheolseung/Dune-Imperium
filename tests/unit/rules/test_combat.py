"""Tests for official four-player Combat ranking and ties."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.core import (
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
)
from dune_imperium.rules.combat import (
    CombatRanking,
    CombatReward,
    RewardRank,
    apply_combat_intrigue_pass,
    apply_combat_reward_influence,
    apply_combat_reward_optional_payment,
    apply_combat_reward_spy,
    apply_combat_reward_trash,
    begin_combat_intrigue,
    finish_combat,
    legal_combat_intrigue_actions,
    legal_combat_reward_influence_actions,
    legal_combat_reward_optional_payment_actions,
    legal_combat_reward_spy_actions,
    legal_combat_reward_trash_actions,
    rank_combat,
    resolve_combat_rewards,
)


def _players(
    strengths: tuple[int, int, int, int],
    sandworm_players: tuple[int, ...] = (),
) -> tuple[PlayerState, ...]:
    return tuple(
        PlayerState(
            player_id=player,
            combat_strength=strength,
            sandworms_conflict=1 if player in sandworm_players else 0,
        )
        for player, strength in enumerate(strengths)
    )


def test_distinct_positive_strengths_receive_first_second_and_third() -> None:
    assert rank_combat(_players((8, 6, 4, 2))) == CombatRanking(
        rewards=(
            CombatReward(0, RewardRank.FIRST),
            CombatReward(1, RewardRank.SECOND),
            CombatReward(2, RewardRank.THIRD),
        ),
        winner=0,
    )


def test_zero_strength_never_receives_a_reward() -> None:
    assert rank_combat(_players((4, 2, 0, 0))) == CombatRanking(
        rewards=(
            CombatReward(0, RewardRank.FIRST),
            CombatReward(1, RewardRank.SECOND),
        ),
        winner=0,
    )
    assert rank_combat(_players((0, 0, 0, 0))) == CombatRanking((), None)


@pytest.mark.parametrize(
    ("strengths", "expected"),
    (
        (
            (8, 8, 4, 2),
            CombatRanking(
                (
                    CombatReward(0, RewardRank.SECOND),
                    CombatReward(1, RewardRank.SECOND),
                    CombatReward(2, RewardRank.THIRD),
                ),
                None,
            ),
        ),
        (
            (8, 8, 4, 4),
            CombatRanking(
                (
                    CombatReward(0, RewardRank.SECOND),
                    CombatReward(1, RewardRank.SECOND),
                ),
                None,
            ),
        ),
        (
            (8, 8, 8, 4),
            CombatRanking(
                tuple(CombatReward(player, RewardRank.SECOND) for player in range(3)),
                None,
            ),
        ),
        (
            (8, 8, 8, 8),
            CombatRanking(
                tuple(CombatReward(player, RewardRank.SECOND) for player in range(4)),
                None,
            ),
        ),
    ),
)
def test_first_place_ties_follow_four_player_reward_rules(
    strengths: tuple[int, int, int, int],
    expected: CombatRanking,
) -> None:
    assert rank_combat(_players(strengths)) == expected


def test_second_place_tie_gives_each_tied_player_third_reward() -> None:
    assert rank_combat(_players((9, 5, 5, 2))) == CombatRanking(
        (
            CombatReward(0, RewardRank.FIRST),
            CombatReward(1, RewardRank.THIRD),
            CombatReward(2, RewardRank.THIRD),
        ),
        winner=0,
    )


def test_third_place_tie_gives_no_third_reward() -> None:
    assert rank_combat(_players((9, 7, 4, 4))) == CombatRanking(
        (
            CombatReward(0, RewardRank.FIRST),
            CombatReward(1, RewardRank.SECOND),
        ),
        winner=0,
    )


def test_sandworm_doubles_only_its_owners_reward_assignment() -> None:
    ranking = rank_combat(_players((9, 7, 5, 3), sandworm_players=(1, 3)))

    assert ranking.rewards == (
        CombatReward(0, RewardRank.FIRST, multiplier=1),
        CombatReward(1, RewardRank.SECOND, multiplier=2),
        CombatReward(2, RewardRank.THIRD, multiplier=1),
    )


def test_combat_intrigue_priority_starts_at_first_eligible_clockwise_seat() -> None:
    players = _players((0, 3, 0, 5))
    players = tuple(
        replace(
            player,
            troops_supply=8 if player.player_id in (1, 3) else 9,
            troops_conflict=1 if player.player_id in (1, 3) else 0,
        )
        for player in players
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=2,
        players=players,
    )

    started = begin_combat_intrigue(state).state
    decision = started.decision_stack[-1].decision

    assert isinstance(decision, PlayerDecision)
    assert decision.owner == 3
    assert legal_combat_intrigue_actions(started, 2) == ()


def test_all_participants_must_pass_consecutively() -> None:
    players = tuple(
        PlayerState(
            player_id=player,
            troops_supply=8 if player in (0, 2, 3) else 9,
            troops_conflict=1 if player in (0, 2, 3) else 0,
        )
        for player in range(4)
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=2,
        players=players,
    )
    state = begin_combat_intrigue(state).state

    visited: list[int] = []
    for player in (2, 3, 0):
        action = legal_combat_intrigue_actions(state, player)[0]
        visited.append(action.actor)
        state = apply_combat_intrigue_pass(state, action).state

    assert visited == [2, 3, 0]
    assert state.combat_intrigue_complete is True
    assert state.decision_stack == ()


def test_no_participant_closes_combat_intrigue_immediately() -> None:
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.COMBAT,
        first_player=0,
        players=_players((0, 0, 0, 0)),
    )

    result = begin_combat_intrigue(state)

    assert result.state.combat_intrigue_complete is True
    assert result.events[0].kind == "combat_intrigue_finished"


def test_intrigue_holders_wait_for_card_type_transcription() -> None:
    player = PlayerState(
        player_id=0,
        troops_supply=8,
        troops_conflict=1,
        intrigue_cards=("intrigue:unknown",),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.COMBAT,
        first_player=0,
        players=(player, *(PlayerState(player_id=seat) for seat in range(1, 4))),
    )

    with pytest.raises(NotImplementedError, match="eligibility"):
        begin_combat_intrigue(state)


def test_unlisted_combat_intrigue_action_is_rejected() -> None:
    player = PlayerState(player_id=0, troops_supply=8, troops_conflict=1)
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.COMBAT,
        first_player=0,
        players=(player, *(PlayerState(player_id=seat) for seat in range(1, 4))),
    )
    state = begin_combat_intrigue(state).state

    with pytest.raises(ValueError, match="not a legal"):
        apply_combat_intrigue_pass(
            state,
            DomainAction(action_id="play_unknown", actor=0),
        )


def _reward_state(
    conflict_id: str,
    strengths: tuple[int, int, int, int] = (8, 6, 4, 0),
    *,
    sandworm_players: tuple[int, ...] = (),
) -> GameState:
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        players=_players(strengths, sandworm_players),
        current_conflict_ids=(conflict_id,),
        combat_intrigue_complete=True,
        intrigue_deck=("intrigue:0", "intrigue:1", "intrigue:2", "intrigue:3"),
    )


def test_desert_mouse_rewards_apply_by_rank() -> None:
    result = resolve_combat_rewards(
        _reward_state("skirmish_desert_mouse")
    )

    assert tuple(player.resources.solari for player in result.state.players) == (
        2,
        3,
        2,
        0,
    )
    assert result.state.combat_rewards_resolved is True
    assert result.state.decision_stack == ()


def test_ornithopter_rewards_draw_intrigue_in_rank_order() -> None:
    result = resolve_combat_rewards(
        _reward_state("skirmish_ornithopter")
    )

    assert result.state.players[0].intrigue_cards == ("intrigue:0",)
    assert result.state.players[1].intrigue_cards == ("intrigue:1",)
    assert result.state.players[2].intrigue_cards == ("intrigue:2",)
    assert result.state.intrigue_deck == ("intrigue:3",)


def test_sandworm_doubles_the_assigned_reward_row() -> None:
    result = resolve_combat_rewards(
        _reward_state("skirmish_ornithopter", sandworm_players=(1,))
    )

    assert result.state.players[1].resources.solari == 4
    assert result.state.players[1].intrigue_cards == (
        "intrigue:1",
        "intrigue:2",
    )
    assert result.state.players[2].intrigue_cards == ("intrigue:3",)


def test_crysknife_queues_and_applies_influence_choice() -> None:
    state = _reward_state("skirmish_crysknife")
    players = list(state.players)
    players[0] = replace(players[0], influence=Influence(emperor=1))
    state = replace(state, players=tuple(players))

    rewarded = resolve_combat_rewards(state).state
    actions = legal_combat_reward_influence_actions(rewarded, 0)

    assert rewarded.combat_rewards_resolved is False
    assert {dict(action.arguments)["faction"] for action in actions} == {
        "emperor",
        "spacing_guild",
        "bene_gesserit",
        "fremen",
    }
    emperor = next(
        action for action in actions if dict(action.arguments)["faction"] == "emperor"
    )
    resolved = apply_combat_reward_influence(rewarded, emperor).state

    assert resolved.players[0].influence.emperor == 2
    assert resolved.players[0].victory_points == 2
    assert resolved.combat_rewards_resolved is True


def test_combat_rewards_require_completed_intrigue_and_only_resolve_once() -> None:
    state = _reward_state("skirmish_desert_mouse")

    with pytest.raises(ValueError, match="Intrigue must finish"):
        resolve_combat_rewards(
            replace(state, combat_intrigue_complete=False)
        )

    resolved = resolve_combat_rewards(state).state
    with pytest.raises(ValueError, match="already resolved"):
        resolve_combat_rewards(resolved)


def test_transcribed_distinct_influence_reward_waits_for_rule_support() -> None:
    with pytest.raises(NotImplementedError, match="distinct Faction"):
        resolve_combat_rewards(_reward_state("propaganda"))


def test_tier_two_resources_troops_and_fixed_influence_resolve() -> None:
    state = _reward_state("protect_the_sietches")
    players = list(state.players)
    players[0] = replace(players[0], influence=Influence(fremen=1))
    state = replace(state, players=tuple(players))

    result = resolve_combat_rewards(state).state

    assert result.players[0].resources.water == 2
    assert result.players[0].troops_garrison == 4
    assert result.players[0].influence.fremen == 2
    assert result.players[0].victory_points == 2
    assert result.players[1].resources.spice == 3
    assert result.players[1].troops_garrison == 4
    assert result.players[2].resources.spice == 2


def test_contract_icons_become_two_solari_when_choam_is_off() -> None:
    result = resolve_combat_rewards(_reward_state("choam_security")).state

    assert result.players[0].resources.solari == 2
    assert result.players[0].influence.spacing_guild == 1
    assert result.players[1].resources.solari == 2
    assert result.players[1].resources.water == 2
    assert result.players[2].intrigue_cards == ("intrigue:0",)


def test_control_reward_replaces_an_opponents_marker() -> None:
    state = _reward_state("siege_of_arrakeen")
    players = list(state.players)
    players[1] = replace(players[1], control_space_ids=("arrakeen",))
    state = replace(state, players=tuple(players))

    result = resolve_combat_rewards(state).state

    assert result.players[0].control_space_ids == ("arrakeen",)
    assert result.players[1].control_space_ids == ()


def test_sandworm_does_not_double_control_marker() -> None:
    result = resolve_combat_rewards(
        _reward_state("siege_of_arrakeen", sandworm_players=(0,))
    ).state

    assert result.players[0].control_space_ids == ("arrakeen",)
    assert result.players[0].resources.solari == 4
    assert result.players[0].troops_garrison == 7


def test_seize_spice_refinery_skips_spy_choice_when_first_place_is_tied() -> None:
    tied = _reward_state(
        "seize_spice_refinery",
        strengths=(8, 8, 4, 0),
    )
    result = resolve_combat_rewards(tied).state

    assert result.players[0].resources.spice == 1
    assert result.players[1].resources.spice == 1
    assert result.players[2].resources.spice == 2


def test_conflict_spy_reward_lists_empty_observation_posts() -> None:
    state = _reward_state("seize_spice_refinery")
    occupied_post = "emperor-sardaukar-dutiful-service"
    opponent = replace(
        state.players[1],
        spies_supply=2,
        spy_post_ids=(occupied_post,),
    )
    state = replace(
        state,
        players=(state.players[0], opponent, *state.players[2:]),
    )

    rewarded = resolve_combat_rewards(state).state
    actions = legal_combat_reward_spy_actions(rewarded, 0)

    assert len(actions) == 12
    assert occupied_post not in {
        dict(action.arguments)["post_id"] for action in actions
    }
    placed = apply_combat_reward_spy(rewarded, actions[0]).state
    assert placed.players[0].spies_supply == 2
    assert placed.players[0].spy_post_ids == (
        dict(actions[0].arguments)["post_id"],
    )
    assert placed.players[0].resources.spice == 2
    assert placed.players[0].control_space_ids == ("spice_refinery",)
    assert placed.combat_rewards_resolved is True


def test_sandworm_repeats_spy_placement_but_not_control() -> None:
    state = resolve_combat_rewards(
        _reward_state("seize_spice_refinery", sandworm_players=(0,))
    ).state

    for _ in range(2):
        action = legal_combat_reward_spy_actions(state, 0)[0]
        state = apply_combat_reward_spy(state, action).state

    assert state.players[0].spies_supply == 1
    assert len(state.players[0].spy_post_ids) == 2
    assert len(set(state.players[0].spy_post_ids)) == 2
    assert state.players[0].resources.spice == 4
    assert state.players[0].control_space_ids == ("spice_refinery",)
    assert state.combat_rewards_resolved is True


def test_choam_contract_selection_remains_deferred() -> None:
    state = _reward_state("choam_security")
    state = replace(state, config=RulesetConfig(choam_module=True))

    with pytest.raises(NotImplementedError, match="contract selection"):
        resolve_combat_rewards(state)


def test_spice_freighters_reward_can_be_paid_after_influence_choice() -> None:
    state = _reward_state("spice_freighters")
    owner = replace(
        state.players[0],
        resources=replace(state.players[0].resources, spice=3),
    )
    state = replace(state, players=(owner, *state.players[1:]))

    rewarded = resolve_combat_rewards(state).state
    influence = legal_combat_reward_influence_actions(rewarded, 0)[0]
    rewarded = apply_combat_reward_influence(rewarded, influence).state
    actions = legal_combat_reward_optional_payment_actions(rewarded, 0)

    assert tuple(action.action_id for action in actions) == (
        "decline_combat_reward",
        "pay_combat_reward",
    )
    paid = apply_combat_reward_optional_payment(rewarded, actions[1]).state
    assert paid.players[0].resources.spice == 0
    assert paid.players[0].victory_points == 2
    assert paid.combat_rewards_resolved is True


def test_unaffordable_spice_freighters_reward_can_only_be_declined() -> None:
    state = resolve_combat_rewards(_reward_state("spice_freighters")).state
    influence = legal_combat_reward_influence_actions(state, 0)[0]
    state = apply_combat_reward_influence(state, influence).state

    actions = legal_combat_reward_optional_payment_actions(state, 0)

    assert tuple(action.action_id for action in actions) == (
        "decline_combat_reward",
    )
    declined = apply_combat_reward_optional_payment(state, actions[0])
    assert declined.state.players[0].victory_points == 1
    assert declined.state.combat_rewards_resolved is True
    assert declined.events[0].kind == "combat_reward_declined"


def test_sandworm_repeats_spice_freighters_payment_choice() -> None:
    state = _reward_state("spice_freighters", sandworm_players=(0,))
    owner = replace(
        state.players[0],
        resources=replace(state.players[0].resources, spice=6),
    )
    state = replace(state, players=(owner, *state.players[1:]))
    state = resolve_combat_rewards(state).state

    for _ in range(2):
        influence = legal_combat_reward_influence_actions(state, 0)[0]
        state = apply_combat_reward_influence(state, influence).state
        payment = legal_combat_reward_optional_payment_actions(state, 0)[1]
        state = apply_combat_reward_optional_payment(state, payment).state

    assert state.players[0].resources.spice == 0
    assert state.players[0].influence.emperor == 2
    assert state.players[0].victory_points == 4
    assert state.combat_rewards_resolved is True


def test_trade_dispute_trashes_from_hand_discard_and_in_play() -> None:
    state = _reward_state("trade_dispute")
    players = list(state.players)
    players[0] = replace(
        players[0],
        hand=("p0:hand",),
        discard_pile=("p0:discard",),
        in_play=("p0:played",),
    )
    players[1] = replace(players[1], discard_pile=("p1:discard",))
    state = replace(state, players=tuple(players))
    state = resolve_combat_rewards(state).state

    first_actions = legal_combat_reward_trash_actions(state, 0)
    assert tuple(action.action_id for action in first_actions) == (
        "decline_combat_reward_trash",
        "trash_combat_reward_card",
        "trash_combat_reward_card",
        "trash_combat_reward_card",
    )
    assert tuple(
        dict(action.arguments)["card_id"] for action in first_actions[1:]
    ) == (
        "p0:hand",
        "p0:discard",
        "p0:played",
    )
    state = apply_combat_reward_trash(state, first_actions[2]).state

    second_actions = legal_combat_reward_trash_actions(state, 1)
    state = apply_combat_reward_trash(state, second_actions[1]).state

    assert state.players[0].hand == ("p0:hand",)
    assert state.players[0].discard_pile == ()
    assert state.players[0].in_play == ("p0:played",)
    assert state.players[0].trashed == ("p0:discard",)
    assert state.players[1].discard_pile == ()
    assert state.players[1].trashed == ("p1:discard",)
    assert state.players[0].resources.solari == 2
    assert state.players[0].resources.water == 2
    assert state.combat_rewards_resolved is True


def test_trade_dispute_skips_trash_when_no_card_is_available() -> None:
    result = resolve_combat_rewards(_reward_state("trade_dispute")).state

    assert result.decision_stack == ()
    assert result.combat_rewards_resolved is True


def test_sandworm_trash_reward_is_limited_by_available_cards() -> None:
    state = _reward_state("trade_dispute", sandworm_players=(0,))
    owner = replace(state.players[0], hand=("only_card",))
    state = replace(state, players=(owner, *state.players[1:]))
    state = resolve_combat_rewards(state).state

    actions = legal_combat_reward_trash_actions(state, 0)
    state = apply_combat_reward_trash(state, actions[1]).state

    assert legal_combat_reward_trash_actions(state, 0) == (
        DomainAction(action_id="decline_combat_reward_trash", actor=0),
    )
    state = apply_combat_reward_trash(
        state,
        legal_combat_reward_trash_actions(state, 0)[0],
    ).state

    assert state.players[0].trashed == ("only_card",)
    assert state.decision_stack == ()
    assert state.combat_rewards_resolved is True


def test_trade_dispute_trash_can_be_declined_with_cards_available() -> None:
    state = _reward_state("trade_dispute")
    owner = replace(state.players[0], discard_pile=("keep_me",))
    state = replace(state, players=(owner, *state.players[1:]))
    state = resolve_combat_rewards(state).state

    declined = legal_combat_reward_trash_actions(state, 0)[0]
    result = apply_combat_reward_trash(state, declined)

    assert result.state.players[0].discard_pile == ("keep_me",)
    assert result.state.players[0].trashed == ()
    assert result.state.combat_rewards_resolved is True
    assert result.events[0].kind == "combat_reward_trash_declined"


def test_trade_dispute_returns_trashed_reserve_card_to_its_stack() -> None:
    state = _reward_state("trade_dispute")
    reserve_card = "reserve:prepare_the_way:7"
    owner = replace(state.players[0], discard_pile=(reserve_card,))
    state = replace(
        state,
        players=(owner, *state.players[1:]),
        reserve_stacks=(("prepare_the_way", 7), ("the_spice_must_flow", 10)),
    )
    state = resolve_combat_rewards(state).state
    action = legal_combat_reward_trash_actions(state, 0)[1]

    result = apply_combat_reward_trash(state, action).state

    assert result.players[0].discard_pile == ()
    assert result.players[0].trashed == ()
    assert dict(result.reserve_stacks)["prepare_the_way"] == 8


def test_tier_three_base_vp_control_and_spice_payment_resolve() -> None:
    state = _reward_state("battle_for_imperial_basin")
    owner = replace(
        state.players[0],
        resources=replace(state.players[0].resources, spice=4),
    )
    state = replace(state, players=(owner, *state.players[1:]))

    rewarded = resolve_combat_rewards(state).state

    assert rewarded.players[0].victory_points == 2
    assert rewarded.players[0].control_space_ids == ("imperial_basin",)
    assert rewarded.players[1].resources.spice == 5
    assert rewarded.players[2].resources.spice == 3
    actions = legal_combat_reward_optional_payment_actions(rewarded, 0)
    paid = apply_combat_reward_optional_payment(rewarded, actions[1]).state
    assert paid.players[0].resources.spice == 0
    assert paid.players[0].victory_points == 3


def test_tier_three_solari_payment_uses_solari_not_spice() -> None:
    state = _reward_state("battle_for_spice_refinery")
    owner = replace(
        state.players[0],
        resources=replace(state.players[0].resources, solari=6, spice=2),
    )
    state = replace(state, players=(owner, *state.players[1:]))
    rewarded = resolve_combat_rewards(state).state

    paid = apply_combat_reward_optional_payment(
        rewarded,
        legal_combat_reward_optional_payment_actions(rewarded, 0)[1],
    ).state

    assert paid.players[0].resources.solari == 0
    assert paid.players[0].resources.spice == 2
    assert paid.players[0].victory_points == 3


def test_sandworm_doubles_tier_three_vp_and_payment_opportunities() -> None:
    state = _reward_state(
        "battle_for_imperial_basin",
        sandworm_players=(0,),
    )
    owner = replace(
        state.players[0],
        resources=replace(state.players[0].resources, spice=8),
    )
    state = replace(state, players=(owner, *state.players[1:]))
    state = resolve_combat_rewards(state).state

    for _ in range(2):
        action = legal_combat_reward_optional_payment_actions(state, 0)[1]
        state = apply_combat_reward_optional_payment(state, action).state

    assert state.players[0].victory_points == 5
    assert state.players[0].resources.spice == 0
    assert state.players[0].control_space_ids == ("imperial_basin",)


def test_arrakeen_spy_recall_choice_is_explicitly_blocked() -> None:
    with pytest.raises(NotImplementedError, match="Spy recall"):
        resolve_combat_rewards(_reward_state("battle_for_arrakeen"))

    tied = _reward_state("battle_for_arrakeen", strengths=(8, 8, 4, 0))
    result = resolve_combat_rewards(tied).state
    assert result.players[0].resources.spice == 1
    assert result.players[0].resources.solari == 3


def test_combat_winner_takes_conflict_matches_icon_and_units_are_cleaned_up() -> None:
    state = _reward_state("skirmish_crysknife")
    players = list(state.players)
    players[0] = replace(
        players[0],
        objective_ids=("objective_crysknife_1",),
        troops_supply=7,
        troops_conflict=2,
        sandworms_conflict=1,
    )
    players[1] = replace(players[1], troops_supply=8, troops_conflict=1)
    state = replace(
        state,
        players=tuple(players),
        current_conflict_ids=("older_tied_conflict", "skirmish_crysknife"),
        combat_rewards_resolved=True,
    )

    result = finish_combat(state)
    winner = result.state.players[0]

    assert result.state.phase is GamePhase.MAKERS
    assert result.state.current_conflict_ids == ("older_tied_conflict",)
    assert winner.won_conflict_ids == ("skirmish_crysknife",)
    assert winner.face_down_battle_card_ids == (
        "objective_crysknife_1",
        "skirmish_crysknife",
    )
    assert winner.victory_points == 2
    assert winner.troops_supply == 9
    assert all(player.troops_conflict == 0 for player in result.state.players)
    assert all(player.sandworms_conflict == 0 for player in result.state.players)
    assert all(player.combat_strength == 0 for player in result.state.players)
    assert tuple(event.kind for event in result.events) == (
        "conflict_won",
        "battle_icons_matched",
        "combat_cleaned_up",
    )


def test_first_place_tie_leaves_conflict_on_board_during_cleanup() -> None:
    state = replace(
        _reward_state("skirmish_desert_mouse", strengths=(8, 8, 4, 0)),
        combat_rewards_resolved=True,
    )

    result = finish_combat(state)

    assert result.state.current_conflict_ids == ("skirmish_desert_mouse",)
    assert all(player.won_conflict_ids == () for player in result.state.players)
    assert tuple(event.kind for event in result.events) == ("combat_cleaned_up",)


def test_combat_cleanup_requires_resolved_rewards() -> None:
    with pytest.raises(ValueError, match="rewards must resolve"):
        finish_combat(_reward_state("skirmish_desert_mouse"))
