"""The app_ai agent as a whole: registry, full games, replay, honesty."""

import copy
import random

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.determinize import determinize
from dune_imperium.agents.registry import make_agent
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.observation import PlayerView
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game


@pytest.mark.parametrize(
    ("kind", "level"), [("app_ai", 2), ("app_ai_medium", 1), ("app_ai_easy", 0)]
)
def test_registry_builds_each_level(kind: str, level: int) -> None:
    agent = make_agent(kind, 7)
    assert isinstance(agent, AppAIAgent)
    assert agent.level == level


@pytest.mark.parametrize("choam", [False, True])
def test_four_app_seats_finish_a_game_and_replay(choam: bool) -> None:
    config = RulesetConfig(choam_module=choam)
    engine = UprisingRulesEngine()

    def play() -> tuple[object, ...]:
        agents = tuple(AppAIAgent(seed=100 + seat) for seat in range(4))
        result = run_policy_game(engine, config, 11, agents)
        assert result.state.phase is GamePhase.FINISHED
        return tuple(step for step in result.replay.steps)

    # Same seeds, same game: app_ai draws only from its own seeded RNG.
    assert play() == play()


def test_choices_ignore_hidden_zones() -> None:
    """The choice must not change when every hidden zone is re-dealt.

    ``determinize`` re-deals exactly what a seat cannot see (deck orders, the
    opponents' hand/deck split, held Intrigue, the shared decks) and leaves
    the seat's view unchanged, so an honest agent answers the same.
    """

    config = RulesetConfig(choam_module=True)
    engine = UprisingRulesEngine()
    agents = [AppAIAgent(seed=200 + seat) for seat in range(4)]
    state = engine.reset(config, 5)
    chance = ChanceResolver(seed=5)
    rng = random.Random(9)
    checked = 0
    for step in range(30_000):
        if state.phase is GamePhase.FINISHED:
            break
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        seat = decision.owner
        actions = engine.legal_actions(state, seat)
        view = engine.observe(state, seat)
        if step % 3 == 0 and len(actions) > 1:
            twin = determinize(state, seat, rng)
            assert engine.observe(twin, seat) == view
            hidden = copy.deepcopy(agents[seat])
            real = copy.deepcopy(agents[seat])
            on_twin = hidden.choose_action_with_state(twin, view, actions)
            assert on_twin == real.choose_action_with_state(state, view, actions)
            checked += 1
        action = agents[seat].choose_action_with_state(state, view, actions)
        state = engine.apply(state, action, legal_actions=actions).state
    assert checked > 50


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


def test_an_unmirrored_decision_is_answered_at_random_not_by_a_heuristic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """User decision 2026-10-05: no heuristic decision is ever mixed in.

    A decision no window mirrors gets the app's ``DefaultRandomChoice`` (a
    uniformly random legal action from the agent's seeded RNG) and counts as
    a fallback.
    """

    from dune_imperium.agents.app_ai import agent as agent_module

    state, view, actions = _first_choice(RulesetConfig())
    monkeypatch.setattr(agent_module, "handler_for", lambda kind: None)
    picks = set()
    for seed in range(40):
        app = AppAIAgent(seed=seed)
        pick = app.choose_action_with_state(state, view, actions)
        assert pick in actions
        assert sum(app.fallbacks.values()) == 1
        assert sum(app.mirrored.values()) == 0
        picks.add(pick)
    assert len(picks) > 1
    assert not hasattr(AppAIAgent(seed=0), "_fallback")


@pytest.mark.parametrize(
    ("go_to_11", "epic", "offset", "trigger"),
    [
        (False, False, 0, 10),
        (True, False, 1, 11),
        (False, True, 0, 12),
        (True, True, 1, 13),
    ],
)
def test_go_to_11_reads_vp_on_the_apps_scale(
    go_to_11: bool, epic: bool, offset: int, trigger: int
) -> None:
    """The app's Go to 11 runs from 1 to 11, ours from 0 to 10 (OQ-091):
    app_ai reads every VP as ours + 1. Epic + Go to 11 (ours 0 to 12) has
    no app counterpart; the same offset gives 13 (plan §11.2)."""

    from dune_imperium.agents.app_ai.context import AppContext

    config = RulesetConfig(immortality=go_to_11, go_to_11=go_to_11, epic_game=epic)
    state, view, _ = _first_choice(config)
    ctx = AppContext(state, view.player, view)
    assert ctx.vp_offset == offset
    assert ctx.endgame_trigger_score == trigger
    player = ctx.state.players[0]
    assert ctx.vp(player) == player.victory_points + offset
    # Both games start one app VP in: 1 in the app's 4-player setup.
    assert ctx.vp(player) == 1


def test_immediate_draws_are_answered_before_any_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """User decision 2026-10-10 (OQ-106, "가 로 가자"): an immediate
    triggered draw is all its frame offers, whatever the frame. With two of
    them (CHOAM Transports' card and a Bene Gesserit Influence 4 card) the
    agent takes one at once, with no window asked and no random fallback;
    the app draws both inside their triggers.

    Seed 1 with CHOAM, Bloodlines and Tech: seat 0's first Agent at
    Arrakeen, both draws held for it by hand.
    """

    from dataclasses import replace

    from dune_imperium.agents.agent_turn_steps import apply_placement
    from dune_imperium.agents.app_ai import agent as agent_module
    from dune_imperium.rules.agent_turn import executable_placements
    from dune_imperium.rules.frames import OWED_CARD, OWED_INTRIGUE, hold_draw

    config = RulesetConfig(choam_module=True, bloodlines=True, tech_module=True)
    engine = UprisingRulesEngine()
    state = engine.reset(config, 1)
    placement = next(
        action
        for action in executable_placements(state, 0)
        if dict(action.arguments)["space_id"] == "arrakeen"
    )
    placed = apply_placement(engine, state, placement).state
    owner = hold_draw(
        hold_draw(placed.players[0], OWED_CARD, "choam_transports", "test:card"),
        OWED_INTRIGUE,
        "bene_gesserit_4",
        "test:intrigue",
    )
    state = replace(placed, players=(owner, *placed.players[1:]))
    actions = engine.legal_actions(state, 0)
    assert {action.action_id for action in actions} == {
        "draw_owed_intrigue",
        "draw_owed_card",
    }

    monkeypatch.setattr(agent_module, "handler_for", lambda kind: None)
    app = AppAIAgent(seed=0)
    pick = app.choose_action_with_state(state, engine.observe(state, 0), actions)
    assert pick in actions
    assert not app.fallbacks
