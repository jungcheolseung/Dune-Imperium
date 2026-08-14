"""Tests for final Uprising victory and tiebreak ranking."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.core import GamePhase, GameState, PlayerState, Resources
from dune_imperium.rules.endgame import final_standings


def _state(
    *players: PlayerState, reveal_order: tuple[int, ...] = (0, 1, 2, 3)
) -> GameState:
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.ENDGAME,
        players=players or tuple(PlayerState(player_id=player) for player in range(4)),
        reveal_order=reveal_order,
    )


def _player(
    player: int,
    *,
    victory_points: int = 10,
    spice: int = 0,
    solari: int = 0,
    water: int = 1,
    troops_garrison: int = 3,
) -> PlayerState:
    return PlayerState(
        player_id=player,
        victory_points=victory_points,
        resources=Resources(solari=solari, spice=spice, water=water),
        troops_supply=12 - troops_garrison,
        troops_garrison=troops_garrison,
    )


@pytest.mark.parametrize(
    ("winner_overrides", "runner_up_overrides"),
    (
        ({"victory_points": 11}, {"victory_points": 10, "spice": 20}),
        ({"spice": 2}, {"spice": 1, "solari": 20}),
        ({"solari": 2}, {"solari": 1, "water": 20}),
        ({"water": 2}, {"water": 1, "troops_garrison": 12}),
        ({"troops_garrison": 4}, {"troops_garrison": 3}),
    ),
)
def test_final_tiebreakers_apply_in_rules_order(
    winner_overrides: dict[str, int],
    runner_up_overrides: dict[str, int],
) -> None:
    players = (
        _player(0, **winner_overrides),
        _player(1, **runner_up_overrides),
        _player(2, victory_points=8),
        _player(3, victory_points=7),
    )

    standings = final_standings(_state(*players))

    assert tuple(standing.player for standing in standings[:2]) == (0, 1)
    assert tuple(standing.rank for standing in standings) == (1, 2, 3, 4)


def test_most_recent_reveal_breaks_an_otherwise_exact_tie() -> None:
    state = _state(
        *(_player(player) for player in range(4)),
        reveal_order=(2, 0, 3, 1),
    )

    standings = final_standings(state)

    assert tuple(standing.player for standing in standings) == (1, 3, 0, 2)
    assert standings[0].reveal_position == 3


def test_final_standings_require_endgame_and_complete_reveal_order() -> None:
    state = _state()

    with pytest.raises(ValueError, match="only during Endgame"):
        final_standings(replace(state, phase=GamePhase.RECALL_OR_ENDGAME))
    with pytest.raises(ValueError, match="every player's Reveal order"):
        final_standings(replace(state, reveal_order=(0, 1, 2)))


def test_final_standings_are_pure_and_available_after_finish() -> None:
    state = _state()
    finished = replace(state, phase=GamePhase.FINISHED)

    assert final_standings(state) == final_standings(state)
    assert final_standings(finished) == final_standings(state)
    assert state.phase is GamePhase.ENDGAME
