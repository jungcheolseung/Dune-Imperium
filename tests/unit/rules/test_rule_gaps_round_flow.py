"""Round-flow rules from docs/rules that had no regression test (2026-11 audit).

Each test quotes the docs/rules sentence it pins, with its citation.
"""

from dataclasses import replace

import pytest
from tests.unit.rules.test_reveal_turn import _state as _reveal_state

from dune_imperium import RulesetConfig
from dune_imperium.core import (
    DecisionFrame,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
)
from dune_imperium.rules.endgame import final_standings
from dune_imperium.rules.phases import resolve_recall_or_endgame
from dune_imperium.rules.reveal_turn import (
    begin_reveal_turn,
    finish_reveal_turn,
    legal_finish_reveal_actions,
    legal_reveal_actions,
)
from dune_imperium.rules.setup import create_initial_state

SELECTED_LEADERS = (
    "feyd_rautha_harkonnen",
    "gurney_halleck",
    "lady_amber_metulli",
    "lady_jessica",
)


def _round_end_state() -> GameState:
    state = create_initial_state(
        RulesetConfig(), seed=71, leader_ids=SELECTED_LEADERS
    ).state
    players = tuple(
        replace(
            player,
            agents_available=1,
            agent_locations=(f"space_{player.player_id}",),
            has_revealed=True,
        )
        for player in state.players
    )
    return replace(
        state,
        phase=GamePhase.RECALL_OR_ENDGAME,
        first_player=3,
        players=players,
        reveal_order=(3, 0, 1, 2),
    )


@pytest.mark.parametrize("reason", ("victory_points", "conflict_deck"))
def test_entering_the_endgame_skips_the_recall_and_the_first_player_pass(
    reason: str,
) -> None:
    """The Endgame starts without recalling Agents or passing the marker.

    docs/rules/combat-and-round-end.md: "Endgame 조건이 충족되면 다음 라운드를
    준비하는 Agent recall과 First Player marker 전달을 하지 않고 Endgame으로
    진행한다." [Main p. 15]
    """

    state = _round_end_state()
    if reason == "victory_points":
        scorer = replace(state.players[1], victory_points=10)
        state = replace(state, players=(state.players[0], scorer, *state.players[2:]))
    else:
        state = replace(state, conflict_deck=())

    entered = resolve_recall_or_endgame(state).state

    assert entered.phase is GamePhase.ENDGAME
    assert entered.first_player == 3
    for before, after in zip(state.players, entered.players, strict=True):
        assert after.agent_locations == before.agent_locations
        assert after.agents_available == before.agents_available
        assert after.has_revealed is True
    # The round's Reveal order survives for the last tiebreaker.
    assert entered.reveal_order == (3, 0, 1, 2)


def test_the_last_tiebreaker_reads_the_final_rounds_reveal_order() -> None:
    """An exact tie goes to the seat that revealed most recently.

    docs/rules/combat-and-round-end.md: "위 tiebreaker로도 동률이면 가장 최근에
    Reveal turn을 수행한 플레이어가 최종 승자다." [FAQ p. 2] Entering the
    Endgame keeps that round's Reveal order ("Endgame 조건이 충족되면 다음
    라운드를 준비하는 Agent recall과 First Player marker 전달을 하지 않고
    Endgame으로 진행한다." [Main p. 15]).
    """

    state = _round_end_state()
    players = tuple(
        replace(player, victory_points=10, troops_garrison=0, troops_supply=12)
        for player in state.players
    )
    state = replace(state, players=players)
    for player in state.players:
        assert player.resources == state.players[0].resources

    entered = resolve_recall_or_endgame(state).state

    # Seat 2 revealed last in (3, 0, 1, 2).
    assert final_standings(entered)[0].player == 2


def test_ten_points_mid_round_do_not_end_the_round() -> None:
    """Reaching 10 points during the Player Turns ends nothing yet.

    docs/rules/setup-and-game-flow.md: "라운드가 끝났을 때 한 명 이상이 10
    Victory Point에 도달했거나 Conflict deck이 비어 있으면 Endgame을 시작한다.
    라운드 도중 10점에 도달한 순간에 바로 끝내는 절차는 아니다." [Main p. 6]
    [Main p. 15]
    """

    state = _reveal_state(PlayerState(player_id=0, victory_points=10))
    state = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state

    after = finish_reveal_turn(state, legal_finish_reveal_actions(state, 0)[0]).state

    assert after.phase is GamePhase.PLAYER_TURNS
    decision = after.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    assert decision.owner == 1

    # The last Reveal still leads to the Combat, not to the Endgame.
    players = (
        after.players[0],
        replace(after.players[1], has_revealed=True),
        replace(after.players[2], has_revealed=True),
        after.players[3],
    )
    last = replace(
        after,
        players=players,
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:3",
                decision=PlayerDecision(owner=3, prompt="Choose a turn"),
            ),
        ),
    )
    last = begin_reveal_turn(last, legal_reveal_actions(last, 3)[0]).state
    combat = finish_reveal_turn(last, legal_finish_reveal_actions(last, 3)[0]).state

    assert combat.phase is GamePhase.COMBAT
