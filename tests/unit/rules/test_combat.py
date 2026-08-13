"""Tests for official four-player Combat ranking and ties."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.core import (
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
)
from dune_imperium.rules.combat import (
    CombatRanking,
    CombatReward,
    RewardRank,
    apply_combat_intrigue_pass,
    begin_combat_intrigue,
    legal_combat_intrigue_actions,
    rank_combat,
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
