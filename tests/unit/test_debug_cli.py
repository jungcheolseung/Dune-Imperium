"""Tests for the human-readable engine debug interface."""

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.cli.debug import debug_snapshot, main, run_interactive_session
from dune_imperium.core import GamePhase, PlayerDecision
from dune_imperium.rules import UprisingRulesEngine


def test_snapshot_contains_current_players_view_and_legal_actions() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=3)
    decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)

    snapshot = debug_snapshot(engine, state, decision.owner)

    assert snapshot["decision_owner"] == decision.owner
    assert snapshot["private"] == {
        "deck_size": 5,
        "hand": state.players[decision.owner].hand,
        "discard_pile": (),
        "intrigue_cards": (),
    }
    actions = snapshot["legal_actions"]
    assert isinstance(actions, list)
    assert any(action["action_id"] == "reveal_turn" for action in actions)


def test_interactive_session_can_stop_without_mutating_the_state() -> None:
    output: list[str] = []
    engine = UprisingRulesEngine()

    state = run_interactive_session(
        engine,
        RulesetConfig(),
        seed=5,
        read=lambda _: "q",
        write=output.append,
    )

    assert state.phase is GamePhase.PLAYER_TURNS
    assert state.revision == 0
    assert output[-1] == "Session stopped without changing the current state."


def test_random_cli_mode_prints_a_round_summary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--seed", "2", "--random-policy-seed", "12"]) == 0

    output = capsys.readouterr().out
    assert '"phase": "round_start"' in output
    assert '"steps":' in output
