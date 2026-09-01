"""Tests for the M7 verification sweep and its invariant checks."""

import json
from dataclasses import replace
from pathlib import Path

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
    merge_coverage,
    normalize_instance_id,
    run_checked_game,
    run_sweep,
    sweep_specs,
    zero_coverage,
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


def test_self_trash_board_collision_seed_runs_to_finished() -> None:
    # In this CHOAM random game Dangerous Rhetoric was played onto Desert
    # Tactics via its Spy icon and board-trashed before its self-trash
    # Agent box resolved; the OQ-022 satisfied path now covers the
    # chosen-Influence effect too (2026-09-01 sweep).
    report = run_checked_game(
        RulesetConfig(choam_module=True),
        game_seed=2735,
        policy_seed=702_735,
        privacy_interval=0,
    )

    assert report.rounds >= 8


@pytest.mark.parametrize(
    ("choam_module", "game_seed"), [(False, 2934), (True, 2590)]
)
def test_bond_source_trashed_seeds_run_to_finished(
    choam_module: bool, game_seed: int
) -> None:
    # In these random games a Bene Gesserit Bond card was trashed by a
    # freely ordered effect before its Bond box resolved; the Bond now
    # re-adjudicates over the remaining in-play cards [Main p. 20]
    # (2026-09-01 sweep).
    report = run_checked_game(
        RulesetConfig(choam_module=choam_module),
        game_seed=game_seed,
        policy_seed=700_000 + game_seed,
        privacy_interval=0,
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


@pytest.mark.parametrize("choam_module", [False, True])
def test_soundness_interval_checks_every_advertised_action(
    choam_module: bool,
) -> None:
    # Every legal action offered at a sampled decision must apply cleanly
    # and round-trip through the ActionCodec: a passing run proves every
    # advertised action in this game is both executable and
    # codec-expressible, which the sweep otherwise never exercises.
    report = run_checked_game(
        RulesetConfig(choam_module=choam_module),
        game_seed=61,
        policy_seed=7061,
        privacy_interval=0,
        soundness_interval=5,
    )

    assert report.rounds >= 1


def test_normalize_instance_id_strips_prefix_and_copy_index() -> None:
    assert (
        normalize_instance_id("imperium:dune_the_desert_planet:3")
        == "dune_the_desert_planet"
    )
    assert (
        normalize_instance_id("reserve:smuggler_s_harvester:0")
        == "smuggler_s_harvester"
    )
    assert normalize_instance_id("intrigue:cunning:1") == "cunning"
    assert normalize_instance_id("player:2:starter:signet_ring:0") == "signet_ring"
    assert normalize_instance_id("bare_identity") == "bare_identity"


def test_coverage_census_reports_normalized_identities() -> None:
    report = run_checked_game(
        RulesetConfig(),
        game_seed=61,
        policy_seed=7061,
        privacy_interval=0,
        collect_coverage=True,
    )
    coverage = report.coverage
    assert coverage is not None

    assert coverage["action_ids"]
    assert coverage["agent_placements"]
    assert coverage["event_kinds"]

    # Per-copy instance IDs normalize down to a shared identity slug: no
    # trailing copy-index suffix survives.
    for key in coverage["cards_played"]:
        assert not key.rsplit(":", 1)[-1].isdigit()
    for key in coverage["cards_acquired"]:
        assert not key.rsplit(":", 1)[-1].isdigit()

    doubled = merge_coverage(coverage, coverage)
    for dimension, counts in coverage.items():
        for key, count in counts.items():
            assert doubled[dimension][key] == count * 2

    zero = zero_coverage(coverage, choam_module=False)
    # This Conflict never gets drawn into this seeded ten-card deck.
    assert "seize_spice_refinery" in zero["conflicts"]


def test_rotate_leaders_specs_are_deterministic_with_four_distinct_ids() -> None:
    first = sweep_specs(
        games=3, rulesets=(False, True), start_seed=61, rotate_leaders=True
    )
    second = sweep_specs(
        games=3, rulesets=(False, True), start_seed=61, rotate_leaders=True
    )

    assert [spec.leader_ids for spec in first] == [spec.leader_ids for spec in second]
    for spec in first:
        assert spec.leader_ids is not None
        assert len(set(spec.leader_ids)) == 4
        if not spec.choam_module:
            assert "shaddam_corrino_iv" not in spec.leader_ids


def test_rotate_leaders_choam_roster_can_include_shaddam() -> None:
    specs = sweep_specs(games=1, rulesets=(True,), start_seed=0, rotate_leaders=True)

    assert specs[0].leader_ids is not None
    assert "shaddam_corrino_iv" in specs[0].leader_ids


def test_rotated_leaders_game_runs_to_finished_under_full_checks() -> None:
    specs = sweep_specs(
        games=1,
        rulesets=(True,),
        start_seed=500,
        privacy_interval=5,
        soundness_interval=5,
        rotate_leaders=True,
    )
    report = run_sweep(specs)

    assert report.failures == ()
    assert report.games[0].rounds >= 1


def test_rotate_leaders_rejects_leader_draft() -> None:
    with pytest.raises(ValueError, match="rotate_leaders cannot be combined"):
        sweep_specs(
            games=1,
            rulesets=(False,),
            start_seed=1,
            rotate_leaders=True,
            leader_draft=True,
        )


def test_cli_rejects_rotate_leaders_with_leader_draft() -> None:
    with pytest.raises(SystemExit) as excinfo:
        sweep_main(["--games", "1", "--rotate-leaders", "--leader-draft"])

    assert excinfo.value.code == 2


def test_cli_accepts_soundness_interval() -> None:
    assert (
        sweep_main(
            [
                "--games",
                "1",
                "--ruleset",
                "base",
                "--start-seed",
                "61",
                "--privacy-interval",
                "0",
                "--soundness-interval",
                "5",
                "--skip-replay",
            ]
        )
        == 0
    )


def test_cli_writes_coverage_json(tmp_path: Path) -> None:
    coverage_path = tmp_path / "coverage.json"

    result = sweep_main(
        [
            "--games",
            "1",
            "--ruleset",
            "base",
            "--start-seed",
            "61",
            "--privacy-interval",
            "0",
            "--skip-replay",
            "--coverage-json",
            str(coverage_path),
        ]
    )

    assert result == 0
    payload = json.loads(coverage_path.read_text())
    assert set(payload) == {"uprising-4p-base"}
    ruleset_payload = payload["uprising-4p-base"]
    assert set(ruleset_payload) == {"counts", "zero"}
    assert ruleset_payload["counts"]["action_ids"]
    assert "seize_spice_refinery" in ruleset_payload["zero"]["conflicts"]
