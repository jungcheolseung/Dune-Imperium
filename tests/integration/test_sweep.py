"""Tests for the M7 verification sweep and its invariant checks."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.cli.sweep import main as sweep_main
from dune_imperium.core import GamePhase
from dune_imperium.core.observation import observe_state
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.simulation import (
    CardCensus,
    InvariantViolation,
    check_observation_privacy,
    check_state_invariants,
    run_checked_game,
    run_sweep,
    sweep_specs,
)
from dune_imperium.simulation.invariants import _scramble_hidden_information


def test_checked_game_passes_every_invariant() -> None:
    report = run_checked_game(
        RulesetConfig(),
        game_seed=61,
        policy_seed=7061,
        privacy_interval=5,
    )

    assert report.ruleset == "uprising-4p-base"
    assert report.steps > 100
    assert report.rounds >= 1
    assert 0 <= report.winner < 4


def test_checked_heuristic_game_passes_every_invariant() -> None:
    report = run_checked_game(
        RulesetConfig(choam_module=True),
        game_seed=61,
        policy_seed=7061,
        privacy_interval=5,
        policy="heuristic",
    )

    assert report.ruleset == "uprising-4p-choam"
    assert report.steps > 100
    assert 0 <= report.winner < 4


@pytest.mark.parametrize("game_seed", [97, 901])
def test_special_mission_spy_deadlock_seeds_run_to_finished(game_seed: int) -> None:
    # These CHOAM heuristic games stranded the Special Mission PlaceSpy slot
    # before the optional decline existed [Main pp. 11, 20].
    report = run_checked_game(
        RulesetConfig(choam_module=True),
        game_seed=game_seed,
        policy_seed=700_000 + game_seed,
        privacy_interval=0,
        policy="heuristic",
    )

    assert report.rounds >= 1


def test_checked_leader_draft_game_passes_every_invariant() -> None:
    # The census is fixed after setup, so Staban's printed starting-card
    # removal during the draft cannot trip card conservation.
    report = run_checked_game(
        RulesetConfig(choam_module=True, leader_draft=True),
        game_seed=70,
        policy_seed=7070,
        privacy_interval=5,
        policy="heuristic",
    )

    assert report.ruleset == "uprising-4p-choam"
    assert report.steps > 100
    assert 0 <= report.winner < 4


def test_unknown_sweep_policy_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown sweep policy"):
        run_checked_game(RulesetConfig(), game_seed=1, policy_seed=1, policy="best")
    with pytest.raises(ValueError, match="unknown sweep policy"):
        sweep_specs(games=1, rulesets=(False,), start_seed=1, policy="best")


def test_small_sweep_covers_both_rulesets() -> None:
    specs = sweep_specs(
        games=1,
        rulesets=(False, True),
        start_seed=62,
        privacy_interval=10,
    )
    report = run_sweep(specs)

    assert report.failures == ()
    assert {game.ruleset for game in report.games} == {
        "uprising-4p-base",
        "uprising-4p-choam",
    }
    assert report.total_steps > 200


def test_census_detects_a_vanished_card() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=63)
    census = CardCensus.from_state(state)

    lightened = replace(state.players[0], hand=state.players[0].hand[1:])
    corrupted = replace(state, players=(lightened, *state.players[1:]))

    with pytest.raises(InvariantViolation, match="instances changed"):
        check_state_invariants(corrupted, census)


def test_census_detects_cross_player_duplication() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=64)
    census = CardCensus.from_state(state)
    stolen = state.players[0].hand[0]

    duplicated = replace(
        state.players[1], hand=(*state.players[1].hand, stolen)
    )
    corrupted = replace(
        state,
        players=(state.players[0], duplicated, *state.players[2:]),
    )

    with pytest.raises(InvariantViolation, match="two zones"):
        check_state_invariants(corrupted, census)


def test_privacy_scramble_changes_hidden_state_but_not_the_view() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=65)

    scrambled = _scramble_hidden_information(state, observer=0)

    # The scramble must really move hidden cards, or the check is vacuous.
    assert scrambled.intrigue_deck != state.intrigue_deck
    assert scrambled.imperium_deck != state.imperium_deck
    assert scrambled.players[1].hand != state.players[1].hand
    assert scrambled.players[0].hand == state.players[0].hand

    assert observe_state(scrambled, 0) == observe_state(state, 0)
    check_observation_privacy(state)


def test_step_limit_reports_a_failure_instead_of_raising() -> None:
    specs = sweep_specs(
        games=1,
        rulesets=(False,),
        start_seed=66,
        max_steps=5,
        privacy_interval=0,
        verify_replay=False,
    )
    report = run_sweep(specs)

    assert report.games == ()
    assert len(report.failures) == 1
    assert "exceeded the 5-step limit" in report.failures[0].error


def test_cli_returns_zero_on_success_and_one_on_failure() -> None:
    assert (
        sweep_main(
            [
                "--games",
                "1",
                "--ruleset",
                "base",
                "--start-seed",
                "67",
                "--privacy-interval",
                "0",
                "--skip-replay",
            ]
        )
        == 0
    )
    assert (
        sweep_main(
            [
                "--games",
                "1",
                "--ruleset",
                "base",
                "--start-seed",
                "68",
                "--max-steps",
                "5",
                "--privacy-interval",
                "0",
                "--skip-replay",
            ]
        )
        == 1
    )


def test_checked_game_state_reaches_finished() -> None:
    engine = UprisingRulesEngine()
    from dune_imperium.simulation import run_random_game

    baseline = run_random_game(engine, RulesetConfig(), 69, 700_069)
    checked = run_checked_game(
        RulesetConfig(),
        game_seed=69,
        policy_seed=700_069,
        privacy_interval=0,
        verify_replay=False,
    )

    # The checked loop replays the exact same seeded trajectory.
    assert baseline.state.phase is GamePhase.FINISHED
    assert checked.steps == len(baseline.replay.steps)
    assert checked.winner == baseline.standings[0].player
