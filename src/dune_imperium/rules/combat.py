"""Pure four-player Combat ranking rules."""

from dataclasses import dataclass
from enum import IntEnum

from dune_imperium.core.player import PlayerState


class RewardRank(IntEnum):
    """Printed Conflict reward rows."""

    FIRST = 1
    SECOND = 2
    THIRD = 3


@dataclass(frozen=True, slots=True)
class CombatReward:
    """The reward row and multiplier earned by one player."""

    player: int
    rank: RewardRank
    multiplier: int = 1

    def __post_init__(self) -> None:
        if self.player < 0:
            raise ValueError("reward player must not be negative")
        if self.multiplier not in (1, 2):
            raise ValueError("Combat reward multiplier must be one or two")


@dataclass(frozen=True, slots=True)
class CombatRanking:
    """Complete reward assignment and the sole Conflict winner, if any."""

    rewards: tuple[CombatReward, ...]
    winner: int | None

    def __post_init__(self) -> None:
        players = tuple(reward.player for reward in self.rewards)
        if len(players) != len(set(players)):
            raise ValueError("a player cannot receive two Conflict reward rows")
        first = tuple(
            reward.player
            for reward in self.rewards
            if reward.rank is RewardRank.FIRST
        )
        if self.winner is None and first:
            raise ValueError("a first-place reward requires a winner")
        if self.winner is not None and first != (self.winner,):
            raise ValueError("winner must be the sole first-place recipient")


def rank_combat(players: tuple[PlayerState, ...]) -> CombatRanking:
    """Apply the official four-player tie and zero-strength reward rules."""

    if len(players) != 4 or tuple(player.player_id for player in players) != tuple(
        range(4)
    ):
        raise ValueError("Combat ranking requires players in seat order 0 through 3")

    groups = _positive_strength_groups(players)
    if not groups:
        return CombatRanking(rewards=(), winner=None)

    top = groups[0]
    rewards: list[CombatReward] = []
    if len(top) > 1:
        rewards.extend(_rewards(players, top, RewardRank.SECOND))
        if len(top) == 2 and len(groups) > 1 and len(groups[1]) == 1:
            rewards.extend(_rewards(players, groups[1], RewardRank.THIRD))
        return CombatRanking(rewards=tuple(rewards), winner=None)

    winner = top[0]
    rewards.extend(_rewards(players, top, RewardRank.FIRST))
    if len(groups) == 1:
        return CombatRanking(rewards=tuple(rewards), winner=winner)

    second = groups[1]
    if len(second) > 1:
        rewards.extend(_rewards(players, second, RewardRank.THIRD))
        return CombatRanking(rewards=tuple(rewards), winner=winner)

    rewards.extend(_rewards(players, second, RewardRank.SECOND))
    if len(groups) > 2 and len(groups[2]) == 1:
        rewards.extend(_rewards(players, groups[2], RewardRank.THIRD))
    return CombatRanking(rewards=tuple(rewards), winner=winner)


def _positive_strength_groups(
    players: tuple[PlayerState, ...],
) -> tuple[tuple[int, ...], ...]:
    strengths = sorted(
        {player.combat_strength for player in players if player.combat_strength > 0},
        reverse=True,
    )
    return tuple(
        tuple(
            player.player_id
            for player in players
            if player.combat_strength == strength
        )
        for strength in strengths
    )


def _rewards(
    players: tuple[PlayerState, ...],
    recipients: tuple[int, ...],
    rank: RewardRank,
) -> tuple[CombatReward, ...]:
    return tuple(
        CombatReward(
            player=player,
            rank=rank,
            multiplier=2 if players[player].sandworms_conflict > 0 else 1,
        )
        for player in recipients
    )
