"""The app_ai agent as a whole: registry, full games, replay, honesty."""

import copy
import random

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.determinize import determinize
from dune_imperium.agents.registry import make_agent
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.state import GamePhase
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
            probe = copy.deepcopy(agents[seat])
            assert probe.choose_action_with_state(
                twin, view, actions
            ) == copy.deepcopy(agents[seat]).choose_action_with_state(
                state, view, actions
            )
            checked += 1
        action = agents[seat].choose_action_with_state(state, view, actions)
        state = engine.apply(state, action, legal_actions=actions).state
    assert checked > 50
