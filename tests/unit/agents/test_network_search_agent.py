"""Tests for the policy-guided determinized search agent (``search:<path>``)."""

from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.agents import StateAgent, make_agent  # noqa: E402
from dune_imperium.agents.network_search_agent import (  # noqa: E402
    NetworkSearchAgent,
)
from dune_imperium.agents.registry import SEARCH_PREFIX, is_agent_kind  # noqa: E402
from dune_imperium.core.chance import ChanceResolver  # noqa: E402
from dune_imperium.core.decisions import (  # noqa: E402
    ChanceDecision,
    PlayerDecision,
)
from dune_imperium.core.state import GamePhase, GameState  # noqa: E402
from dune_imperium.rules import UprisingRulesEngine  # noqa: E402
from dune_imperium.training.checkpoint import save_checkpoint  # noqa: E402
from dune_imperium.training.network import PolicyValueNetwork  # noqa: E402


def _checkpoint(tmp_path: Path, config: RulesetConfig) -> str:
    from dune_imperium.adapters.action_codec import ActionCodec

    torch.manual_seed(0)
    network = PolicyValueNetwork(ActionCodec(config).size, hidden=(32,))
    path = tmp_path / "policy.pt"
    save_checkpoint(path, network, ruleset=config.identifier, iteration=1)
    return str(path)


def _mid_game(config: RulesetConfig, seed: int, rounds: int) -> GameState:
    """Advance a heuristic game until ``rounds`` have begun."""

    engine = UprisingRulesEngine()
    state = engine.reset(config, seed)
    chance = ChanceResolver(seed=seed)
    agents = [make_agent("heuristic", index) for index in range(config.players)]
    while state.round_number < rounds and state.phase is not GamePhase.FINISHED:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        actions = engine.legal_actions(state, decision.owner)
        choice = agents[decision.owner].choose_action(
            engine.observe(state, decision.owner), actions
        )
        state = engine.apply(state, choice).state
    return state


def test_a_search_seat_enters_by_file_like_a_checkpoint(tmp_path: Path) -> None:
    config = RulesetConfig()
    kind = f"{SEARCH_PREFIX}{_checkpoint(tmp_path, config)}"

    assert is_agent_kind(kind)
    assert not is_agent_kind(SEARCH_PREFIX)
    agent = make_agent(kind, 0)
    # The runner must hand it the state, or it would only play greedily.
    assert isinstance(agent, StateAgent)
    assert isinstance(agent, NetworkSearchAgent)
    with pytest.raises(ValueError, match="must not be negative"):
        NetworkSearchAgent(_checkpoint(tmp_path, config), seed=-1)
    with pytest.raises(ValueError, match="positive"):
        NetworkSearchAgent(_checkpoint(tmp_path, config), seed=0, rollouts=0)


def test_search_picks_among_the_network_s_own_best_actions(tmp_path: Path) -> None:
    """The search never leaves the candidate set, and repeats its own choice.

    The candidates are the network's highest-logit legal actions, so a
    searched decision is the network's shortlist re-ordered by playouts --
    not a free choice over the whole legal set.
    """

    config = RulesetConfig()
    path = _checkpoint(tmp_path, config)
    engine = UprisingRulesEngine()
    state = _mid_game(config, seed=5, rounds=2)
    decision = engine.current_decision(state)
    while isinstance(decision, ChanceDecision):
        state = engine.apply(state, ChanceResolver(seed=5).resolve(decision)).state
        decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    actions = engine.legal_actions(state, decision.owner)
    view = engine.observe(state, decision.owner)
    if len(actions) < 2:  # pragma: no cover - the seed above yields a choice
        pytest.skip("need a decision with more than one legal action")

    agent = NetworkSearchAgent(path, seed=3, candidates=2, rollouts=1)
    chosen = agent.choose_action_with_state(state, view, actions)

    assert chosen in actions
    # It is one of the two the network ranks highest.
    order = (-agent._logits(view, actions)).argsort(kind="stable")
    assert chosen in [actions[index] for index in order[:2]]
    # Same seed, same state, same answer.
    twin = NetworkSearchAgent(path, seed=3, candidates=2, rollouts=1)
    assert twin.choose_action_with_state(state, view, actions) == chosen


def test_the_search_answers_a_run_of_decisions_legally(tmp_path: Path) -> None:
    """Drive a game with a search seat for a stretch of real decisions.

    The whole game at the measured knobs (four worlds, three candidates)
    costs minutes, so this drives a bounded run at one world and two
    candidates: every answer must be a legal action of that decision, and
    the engine must accept it.
    """

    config = RulesetConfig()
    agent = NetworkSearchAgent(
        _checkpoint(tmp_path, config), seed=2, rollouts=1, candidates=2
    )
    engine = UprisingRulesEngine()
    state = _mid_game(config, seed=9, rounds=2)
    chance = ChanceResolver(seed=99)
    searched = 0

    while searched < 8 and state.phase is not GamePhase.FINISHED:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        actions = engine.legal_actions(state, decision.owner)
        view = engine.observe(state, decision.owner)
        choice = agent.choose_action_with_state(state, view, actions)
        assert choice in actions
        if len(actions) > 1:
            searched += 1
        state = engine.apply(state, choice, legal_actions=actions).state

    assert searched == 8


def test_without_a_state_the_search_plays_the_network_greedily(
    tmp_path: Path,
) -> None:
    """The no-state path is the plain checkpoint agent's choice.

    Both are asked once from fresh agents: ``NetworkAgent`` keeps a cycle
    guard that deliberately answers differently the second time it meets the
    same position, so re-asking one agent is not the comparison.
    """

    config = RulesetConfig()
    path = _checkpoint(tmp_path, config)
    engine = UprisingRulesEngine()
    state = _mid_game(config, seed=5, rounds=2)
    decision = engine.current_decision(state)
    while isinstance(decision, ChanceDecision):
        state = engine.apply(state, ChanceResolver(seed=5).resolve(decision)).state
        decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    actions = engine.legal_actions(state, decision.owner)
    view = engine.observe(state, decision.owner)

    searcher = make_agent(f"{SEARCH_PREFIX}{path}", 4)
    plain = make_agent(f"checkpoint:{path}", 4)

    assert searcher.choose_action(view, actions) == plain.choose_action(view, actions)
