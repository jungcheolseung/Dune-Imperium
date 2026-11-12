"""Combat rules from docs/rules that had no regression test (2026-11 audit).

Each test quotes the docs/rules sentence it pins, with its citation.
"""

from tests.support.pauses import answer_pause
from tests.support.reward_windows import settle_reward_window

from dune_imperium import RulesetConfig
from dune_imperium.core import GamePhase, GameState, PlayerState
from dune_imperium.rules.combat import (
    CombatReward,
    RewardRank,
    apply_combat_reward_influence,
    legal_combat_reward_influence_actions,
    rank_combat,
    resolve_combat_rewards,
)
from dune_imperium.rules.frames import FrameKind, top_frame
from dune_imperium.rules.pauses import pause_is_pending


def _players(
    strengths: tuple[int, int, int, int], sandworms: dict[int, int]
) -> tuple[PlayerState, ...]:
    return tuple(
        PlayerState(
            player_id=player,
            combat_strength=strength,
            sandworms_conflict=sandworms.get(player, 0),
        )
        for player, strength in enumerate(strengths)
    )


def _reward_state(conflict_id: str, sandworms: dict[int, int]) -> GameState:
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        players=_players((8, 6, 4, 0), sandworms),
        current_conflict_ids=(conflict_id,),
        combat_intrigue_complete=True,
        intrigue_deck=tuple(f"intrigue:{index}" for index in range(6)),
    )


def _settle(state: GameState) -> GameState:
    """Pay every recipient in rank order, answering the windows as the
    older engine did (``tests.support.reward_windows``)."""

    for _ in range(64):
        if state.combat_rewards_resolved:
            return state
        frame = top_frame(state)
        if pause_is_pending(state):
            state = answer_pause(state).state
        elif not state.decision_stack:
            state = resolve_combat_rewards(state).state
        elif frame is not None and frame.kind == FrameKind.COMBAT_REWARD_ICONS:
            state = settle_reward_window(state)
        else:
            return state
    raise AssertionError("the rewards did not settle")


def test_two_sandworms_still_only_double_the_reward() -> None:
    """Two or more sandworms double a reward once, never more.

    docs/rules/combat-and-round-end.md: "보상을 받을 때 자신의 sandworm이
    Conflict에 하나 이상 있으면 자신이 받는 보상을 두 배로 한다. sandworm 수가
    둘 이상이어도 두 배보다 더 커지지 않는다." [Main p. 14]
    """

    ranking = rank_combat(_players((8, 6, 4, 0), {1: 2, 2: 3}))
    assert ranking.rewards == (
        CombatReward(0, RewardRank.FIRST, multiplier=1),
        CombatReward(1, RewardRank.SECOND, multiplier=2),
        CombatReward(2, RewardRank.THIRD, multiplier=2),
    )

    # Skirmish (Ornithopter): 2nd place "2 Solari + 1 Intrigue card", 3rd
    # place "1 Intrigue card" [Skirmish (Ornithopter) card].
    paid = _settle(
        resolve_combat_rewards(
            _reward_state("skirmish_ornithopter", {1: 2, 2: 3})
        ).state
    )

    assert paid.players[1].resources.solari == 4
    assert len(paid.players[1].intrigue_cards) == 2
    assert len(paid.players[2].intrigue_cards) == 2


def _doubled_crysknife_choice() -> GameState:
    # Skirmish (Crysknife)'s 1st reward is one Influence of the winner's
    # choice; the winner has a sandworm in the Conflict.
    state = resolve_combat_rewards(_reward_state("skirmish_crysknife", {0: 1})).state
    state = settle_reward_window(state)
    frame = top_frame(state)
    assert frame is not None and frame.kind == FrameKind.COMBAT_REWARD_INFLUENCE
    return state


def _choose(state: GameState, faction: str) -> GameState:
    action = next(
        candidate
        for candidate in legal_combat_reward_influence_actions(state, 0)
        if dict(candidate.arguments)["faction"] == faction
    )
    state = apply_combat_reward_influence(state, action).state
    frame = top_frame(state)
    if frame is not None and frame.kind == FrameKind.COMBAT_REWARD_ICONS:
        state = settle_reward_window(state)
    return state


def test_a_doubled_influence_reward_may_go_to_two_different_factions() -> None:
    """A doubled one-Influence reward may be split between two Factions.

    docs/rules/combat-and-round-end.md: "reward의 Influence 1을 두 배로 받는
    경우 두 번의 Influence를 같은 Faction에 주거나 서로 다른 두 Faction에
    하나씩 줄 수 있다. 이는 일반적인 `gain 2 Influence`가 한 Faction을 고르는
    규칙과 달리, reward를 두 번 받는 처리다." [Main p. 14] [Main p. 20]
    """

    state = _choose(_doubled_crysknife_choice(), "emperor")

    # The second Influence is a fresh choice that offers every Faction,
    # the one already chosen and the others alike.
    assert {
        dict(action.arguments)["faction"]
        for action in legal_combat_reward_influence_actions(state, 0)
    } == {"emperor", "spacing_guild", "bene_gesserit", "fremen"}

    state = _choose(state, "fremen")

    assert state.players[0].influence.emperor == 1
    assert state.players[0].influence.fremen == 1
    assert legal_combat_reward_influence_actions(state, 0) == ()


def test_a_doubled_influence_reward_may_go_twice_to_one_faction() -> None:
    """The same doubled reward may also give both Influence to one Faction.

    docs/rules/combat-and-round-end.md: "두 번의 Influence를 같은 Faction에
    주거나 서로 다른 두 Faction에 하나씩 줄 수 있다." [Main p. 14] [Main p. 20]
    Reaching 2 Influence scores its point ("Influence 2에 도달하면 1 VP를
    얻는다." `[Main pp. 7, 17]`, docs/rules/uprising-systems.md).
    """

    opened = _doubled_crysknife_choice()
    state = _choose(_choose(opened, "emperor"), "emperor")

    assert state.players[0].influence.emperor == 2
    assert state.players[0].victory_points == opened.players[0].victory_points + 1
