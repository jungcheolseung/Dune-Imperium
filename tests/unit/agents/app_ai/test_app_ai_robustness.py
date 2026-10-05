"""app_ai against odd, human-like choices: random seats at the UI defaults.

The census and the A/B tables seat app_ai against app_ai and heuristic
seats only. A human at the play UI makes choices neither makes (odd
Intrigue timing, declined optional effects, unusual targets), and each of
them reaches app_ai's windows that answer another seat's moves. Random seats
stand in for that: every app_ai decision must still be mirrored, with no
window failing (``error:<kind>``) or left unmirrored.
"""

import logging

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.app_ai.abilities import UNPORTED
from dune_imperium.agents.app_ai.windows.run import DecisionRun
from dune_imperium.agents.base import Agent
from dune_imperium.agents.random_agent import RandomAgent
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.observation import PlayerView
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game

UI_DEFAULT_OPTIONS = {
    "choam_module": True,
    "leader_draft": True,
    "promo_cards": True,
    "bloodlines": True,
    "tech_module": True,
    "immortality": True,
    "go_to_11": True,
    "epic_game": True,
}


@pytest.mark.parametrize("scouts", [False, True], ids=["ui-default", "scouts"])
@pytest.mark.parametrize("game_seed", [1, 2, 3])
def test_app_ai_answers_random_seats_without_a_fallback(
    scouts: bool, game_seed: int, caplog: pytest.LogCaptureFixture
) -> None:
    config = RulesetConfig(**UI_DEFAULT_OPTIONS, arrakeen_scouts=scouts)
    agents: list[Agent] = []
    app_seats: list[AppAIAgent] = []
    for seat in range(4):
        # Rotate the seats and levels over the seeds.
        if (seat + game_seed) % 2 == 0:
            app = AppAIAgent(seed=1000 * game_seed + seat, level=(seat + game_seed) % 3)
            app_seats.append(app)
            agents.append(app)
        else:
            agents.append(RandomAgent(seed=1000 * game_seed + seat))
    unported = dict(UNPORTED)

    with caplog.at_level(logging.WARNING, logger="dune_imperium.agents.app_ai"):
        result = run_policy_game(UprisingRulesEngine(), config, game_seed, agents)

    assert result.state.phase is GamePhase.FINISHED
    for app in app_seats:
        assert dict(app.fallbacks) == {}
        assert sum(app.mirrored.values()) > 100
    assert dict(UNPORTED) == unported
    assert caplog.records == []


# --- a window that fails --------------------------------------------------------


def _first_choice(
    config: RulesetConfig,
) -> tuple[GameState, PlayerView, tuple[DomainAction, ...]]:
    """The first player decision with more than one legal action."""

    engine = UprisingRulesEngine()
    state = engine.reset(config, 3)
    chance = ChanceResolver(seed=3)
    while True:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        actions = engine.legal_actions(state, decision.owner)
        if len(actions) > 1:
            return state, engine.observe(state, decision.owner), actions
        state = engine.apply(state, actions[0], legal_actions=actions).state


@pytest.mark.usefixtures("app_ai_errors_expected")
@pytest.mark.parametrize("failure", ["raises", "illegal"])
def test_a_failing_window_is_answered_at_random_and_logged(
    failure: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    app_ai_error_records: list[logging.LogRecord],
) -> None:
    """User decision 2026-10-05: a live game never stalls on an app_ai bug.

    The answer is the app's ``DefaultRandomChoice`` from the agent's own
    seeded RNG (no heuristic), counted under ``error:<kind>`` and logged.
    """

    from dune_imperium.agents.app_ai import agent as agent_module

    state, view, actions = _first_choice(RulesetConfig())
    kind = str(view.decision_kind)

    def broken(run: DecisionRun) -> DomainAction | None:
        if failure == "raises":
            raise KeyError("probe")
        return DomainAction("probe_not_an_action", run.ctx.seat)

    monkeypatch.setattr(agent_module, "handler_for", lambda _kind: broken)
    picks = set()
    with caplog.at_level(logging.WARNING, logger="dune_imperium.agents.app_ai"):
        for seed in range(30):
            app = AppAIAgent(seed=seed)
            pick = app.choose_action_with_state(state, view, actions)
            assert pick in actions
            assert dict(app.fallbacks) == {f"error:{kind}": 1}
            assert not app.mirrored
            # Deterministic: a fresh agent of the same seed answers the same
            # (what a save restore relies on).
            again = AppAIAgent(seed=seed).choose_action_with_state(state, view, actions)
            assert again == pick
            picks.add(pick)
    assert len(picks) > 1
    assert len(caplog.records) == 60
    for record in caplog.records:
        assert record.levelno == logging.ERROR
        assert f"{kind} decision" in record.getMessage()
        assert (record.exc_info is not None) is (failure == "raises")
    # conftest's guard sees them, and fails any test that does not opt out
    # (the game-level coverage tests count only ``fallbacks[<kind>]``).
    assert app_ai_error_records == caplog.records


def test_every_unmirrored_answer_logs_a_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from dune_imperium.agents.app_ai import agent as agent_module

    state, view, actions = _first_choice(RulesetConfig())
    kind = str(view.decision_kind)
    monkeypatch.setattr(agent_module, "handler_for", lambda _kind: None)
    app = AppAIAgent(seed=1)

    with caplog.at_level(logging.WARNING, logger="dune_imperium.agents.app_ai"):
        app.choose_action_with_state(state, view, actions)
        app.choose_action(view, actions)

    assert dict(app.fallbacks) == {kind: 1, f"view-only:{kind}": 1}
    assert [record.levelno for record in caplog.records] == [logging.WARNING] * 2
    assert all(kind in record.getMessage() for record in caplog.records)
    # A forced decision (one legal action) is no fallback and logs nothing.
    caplog.clear()
    assert app.choose_action_with_state(state, view, actions[:1]) == actions[0]
    assert caplog.records == []
