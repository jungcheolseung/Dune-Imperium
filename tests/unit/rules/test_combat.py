"""Tests for official four-player Combat ranking and ties."""

import pytest

from dune_imperium.core import PlayerState
from dune_imperium.rules.combat import (
    CombatRanking,
    CombatReward,
    RewardRank,
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
