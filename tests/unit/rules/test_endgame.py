"""Tests for final Uprising victory and tiebreak ranking."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.core import (
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules.endgame import (
    apply_endgame_intrigue_action,
    begin_endgame_intrigue,
    can_finish_endgame_automatically,
    final_standings,
    finish_endgame_without_pending_effects,
    legal_endgame_intrigue_actions,
)


def _state(
    *players: PlayerState, reveal_order: tuple[int, ...] = (0, 1, 2, 3)
) -> GameState:
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.ENDGAME,
        first_player=0,
        players=players or tuple(PlayerState(player_id=player) for player in range(4)),
        reveal_order=reveal_order,
    )


def _pass(actor: int) -> DomainAction:
    return DomainAction(action_id="pass_endgame_intrigue", actor=actor)


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


def test_endgame_without_intrigue_finishes_with_ranked_winner_event() -> None:
    state = _state(
        _player(0, victory_points=9),
        _player(1, victory_points=11),
        _player(2, victory_points=10),
        _player(3, victory_points=8),
    )

    result = finish_endgame_without_pending_effects(state)

    assert result.state.phase is GamePhase.FINISHED
    assert result.events[0].kind == "game_finished"
    assert result.events[0].payload == (("player", 1), ("victory_points", 11))


def test_held_intrigue_conservatively_blocks_automatic_endgame_finish() -> None:
    state = _state()
    holder = replace(state.players[2], intrigue_cards=("intrigue:cunning:0",))
    state = replace(state, players=(*state.players[:2], holder, state.players[3]))

    assert can_finish_endgame_automatically(state) is False
    with pytest.raises(ValueError, match="Intrigue or wild battle"):
        finish_endgame_without_pending_effects(state)


def test_face_up_wild_battle_match_blocks_automatic_finish() -> None:
    state = _state()
    holder = replace(
        state.players[0],
        objective_ids=("objective_crysknife_1",),
        won_conflict_ids=("propaganda",),
    )
    state = replace(state, players=(holder, *state.players[1:]))

    assert can_finish_endgame_automatically(state) is False

    matched = replace(
        holder,
        face_down_battle_card_ids=("objective_crysknife_1", "propaganda"),
    )
    matched_state = replace(state, players=(matched, *state.players[1:]))
    assert can_finish_endgame_automatically(matched_state) is True


def test_endgame_windows_open_clockwise_from_the_first_player() -> None:
    state = replace(_state(), first_player=2)
    holder = replace(state.players[0], intrigue_cards=("intrigue:cunning:0",))
    state = replace(state, players=(holder, *state.players[1:]))

    opened = begin_endgame_intrigue(state).state
    frame = opened.decision_stack[-1]
    assert frame.kind == "endgame_intrigue"
    assert isinstance(frame.decision, PlayerDecision)
    assert frame.decision.owner == 2
    assert dict(frame.context)["remaining"] == "3,0,1"
    # Only pass is available without matches or playable Endgame cards.
    assert legal_endgame_intrigue_actions(opened, 2) == (_pass(2),)
    assert legal_endgame_intrigue_actions(opened, 0) == ()


def test_passing_every_window_completes_the_endgame() -> None:
    from dune_imperium.rules import UprisingRulesEngine

    state = _state()
    holder = replace(state.players[1], intrigue_cards=("intrigue:cunning:0",))
    state = replace(state, players=(state.players[0], holder, *state.players[2:]))
    engine = UprisingRulesEngine()

    opened = begin_endgame_intrigue(state).state
    working = opened
    for seat in (0, 1, 2):
        working = engine.apply(working, _pass(seat)).state
        assert working.decision_stack[-1].kind == "endgame_intrigue"
    finished = engine.apply(working, _pass(3))
    # The last pass closes the sweep and the game finishes at once.
    assert finished.state.endgame_intrigue_complete is True
    assert finished.state.phase is GamePhase.FINISHED
    assert [event.kind for event in finished.events] == [
        "endgame_intrigue_passed",
        "game_finished",
    ]


def test_wild_matches_resolve_inside_the_owners_window() -> None:
    state = _state()
    holder = replace(
        state.players[0],
        objective_ids=("objective_crysknife_1",),
        won_conflict_ids=("propaganda",),
    )
    state = replace(state, players=(holder, *state.players[1:]))

    opened = begin_endgame_intrigue(state).state
    actions = legal_endgame_intrigue_actions(opened, 0)
    assert actions[0] == _pass(0)
    match = actions[1]
    assert match.action_id == "match_endgame_wild_icon"
    assert dict(match.arguments) == {
        "matching_card_id": "objective_crysknife_1",
        "wild_card_id": "propaganda",
    }

    result = apply_endgame_intrigue_action(opened, match)
    owner = result.state.players[0]
    assert owner.victory_points == 2
    assert owner.face_down_battle_card_ids == (
        "propaganda",
        "objective_crysknife_1",
    )
    # The window stays open for further plays before the owner passes.
    assert result.state.decision_stack[-1].kind == "endgame_intrigue"
    assert result.events[0].kind == "endgame_wild_matched"
    assert legal_endgame_intrigue_actions(result.state, 0) == (_pass(0),)


def test_passing_without_matching_leaves_the_pair_unused() -> None:
    from dune_imperium.rules import UprisingRulesEngine

    state = _state()
    holder = replace(
        state.players[1],
        objective_ids=("objective_crysknife_1",),
        won_conflict_ids=("propaganda",),
    )
    state = replace(state, players=(state.players[0], holder, *state.players[2:]))
    engine = UprisingRulesEngine()

    working = begin_endgame_intrigue(state).state
    for seat in (0, 1, 2):
        working = engine.apply(working, _pass(seat)).state
    finished = engine.apply(working, _pass(3)).state

    assert finished.players[1].victory_points == 1
    assert finished.players[1].face_down_battle_card_ids == ()
    assert finished.phase is GamePhase.FINISHED


def test_multiple_wild_match_candidates_are_offered_together() -> None:
    state = _state()
    holder = replace(
        state.players[0],
        objective_ids=("objective_crysknife_1", "objective_crysknife_2"),
        won_conflict_ids=("propaganda",),
    )
    state = replace(state, players=(holder, *state.players[1:]))

    opened = begin_endgame_intrigue(state).state
    matches = [
        dict(action.arguments)["matching_card_id"]
        for action in legal_endgame_intrigue_actions(opened, 0)
        if action.action_id == "match_endgame_wild_icon"
    ]
    assert matches == ["objective_crysknife_1", "objective_crysknife_2"]

    # Matching one pair consumes the wild card, so the other offer disappears.
    first = legal_endgame_intrigue_actions(opened, 0)[1]
    resolved = apply_endgame_intrigue_action(opened, first).state
    assert legal_endgame_intrigue_actions(resolved, 0) == (_pass(0),)
