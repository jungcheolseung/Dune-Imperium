"""Scoring rules from docs/rules that had no regression test (2026-11 audit).

Each test quotes the docs/rules sentence it pins, with its citation.
"""

from dataclasses import replace

from tests.support.reward_windows import settle_reward_window

from dune_imperium import RulesetConfig
from dune_imperium.content.core.icons import Faction
from dune_imperium.core import (
    GamePhase,
    GameState,
    Influence,
    PlayerState,
)
from dune_imperium.rules.combat import (
    apply_combat_reward_trash,
    legal_combat_reward_trash_actions,
    resolve_combat_rewards,
)
from dune_imperium.rules.endgame import (
    final_standings,
    finish_endgame_without_pending_effects,
)
from dune_imperium.rules.influence import gain_faction_influence


def test_victory_points_go_past_the_printed_twelve() -> None:
    """A score is not capped at the end of the printed Score track.

    docs/rules/setup-and-game-flow.md: "Score track 그림이 12까지만 있어도
    실제 점수는 12를 넘을 수 있다." [FAQ p. 4]
    """

    leader = PlayerState(player_id=0, victory_points=12, influence=Influence(emperor=1))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.ENDGAME,
        first_player=0,
        players=(
            leader,
            replace(PlayerState(player_id=1), victory_points=12),
            *(PlayerState(player_id=seat) for seat in range(2, 4)),
        ),
        reveal_order=(0, 1, 2, 3),
    )

    # Reaching 2 Emperor Influence scores 1 VP ("Influence 2에 도달하면 1 VP를
    # 얻는다." `[Main pp. 7, 17]`, docs/rules/uprising-systems.md).
    gained = gain_faction_influence(
        state, 0, Faction.EMPEROR, 1, event_prefix="test:past-twelve"
    ).state

    assert gained.players[0].victory_points == 13
    assert final_standings(gained)[0].player == 0
    finished = finish_endgame_without_pending_effects(gained)
    assert finished.events[0].payload == (("player", 0), ("victory_points", 13))


def test_trashing_the_spice_must_flow_keeps_its_victory_point() -> None:
    """The point The Spice Must Flow scored on acquisition stays after a trash.

    docs/rules/player-turns.md: "The Spice Must Flow를 acquire하며 얻은
    Victory Point는 이후 그 카드를 trash하더라도 유지한다." [FAQ p. 4]
    A trashed Reserve card goes back to its stack (docs/rules/
    uprising-systems.md: "Reserve 카드는 해당 Reserve stack으로
    돌려보낸다." `[Main pp. 6, 20]`).
    """

    spice_must_flow = "reserve:the_spice_must_flow:9"
    owner = PlayerState(
        player_id=0,
        combat_strength=8,
        victory_points=3,
        hand=(spice_must_flow,),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        players=(
            owner,
            *(
                PlayerState(player_id=seat, combat_strength=strength)
                for seat, strength in ((1, 6), (2, 4), (3, 0))
            ),
        ),
        current_conflict_ids=("trade_dispute",),
        combat_intrigue_complete=True,
        intrigue_deck=("intrigue:0", "intrigue:1"),
        reserve_stacks=(("prepare_the_way", 8), ("the_spice_must_flow", 9)),
    )
    state = settle_reward_window(resolve_combat_rewards(state).state)
    trash = next(
        action
        for action in legal_combat_reward_trash_actions(state, 0)
        if dict(action.arguments).get("card_id") == spice_must_flow
    )
    before = state.players[0].victory_points

    trashed = apply_combat_reward_trash(state, trash).state

    assert trashed.players[0].hand == ()
    assert dict(trashed.reserve_stacks)["the_spice_must_flow"] == 10
    assert trashed.players[0].victory_points == before
