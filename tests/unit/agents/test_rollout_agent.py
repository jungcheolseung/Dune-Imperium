"""Tests for the determinizer and the rollout search baseline (M9)."""

import random
from collections import Counter
from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents import (
    Agent,
    HeuristicAgent,
    RolloutAgent,
    StateAgent,
    determinize,
    make_agent,
)
from dune_imperium.agents.rollout_agent import player_value, position_value
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.observation import PlayerView, observe_state
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game


def _play_rounds(seed: int, rounds: int) -> GameState:
    """Advance a heuristic game until ``rounds`` have begun."""

    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed)
    chance = ChanceResolver(seed=seed)
    policy = HeuristicAgent(seed=seed)
    while state.round_number < rounds and state.phase is not GamePhase.FINISHED:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        actions = engine.legal_actions(state, decision.owner)
        action = policy.choose_action(engine.observe(state, decision.owner), actions)
        state = engine.apply(state, action).state
    return state


def _card_census(state: GameState) -> Counter[str]:
    cards: Counter[str] = Counter()
    cards.update(state.imperium_deck)
    cards.update(state.intrigue_deck)
    cards.update(state.contract_bank)
    cards.update(state.conflict_deck)
    for player in state.players:
        cards.update(player.hand)
        cards.update(player.deck)
        cards.update(player.intrigue_cards)
    return cards


def test_determinize_keeps_the_observers_view_and_every_card() -> None:
    state = _play_rounds(seed=21, rounds=4)
    # Give an opponent a publicly known hand card and some held Intrigue so
    # both special cases are exercised.
    rival = state.players[1]
    assert rival.hand, "the rival must hold cards mid-game"
    state = replace(
        state,
        players=(
            state.players[0],
            replace(rival, hand_public=(rival.hand[0],)),
            *state.players[2:],
        ),
    )
    assert any(player.intrigue_cards for player in state.players[1:])

    world = determinize(state, 0, random.Random(3))

    assert observe_state(world, 0) == observe_state(state, 0)
    assert _card_census(world) == _card_census(state)
    for original, sampled in zip(state.players, world.players, strict=True):
        assert len(sampled.hand) == len(original.hand)
        assert len(sampled.deck) == len(original.deck)
        assert len(sampled.intrigue_cards) == len(original.intrigue_cards)
    # The observer's own hand and Intrigue are knowledge, not a sample.
    assert world.players[0].hand == state.players[0].hand
    assert world.players[0].intrigue_cards == state.players[0].intrigue_cards
    assert sorted(world.players[0].deck) == sorted(state.players[0].deck)
    # The publicly known rival card stays in the rival's hand.
    assert rival.hand[0] in world.players[1].hand
    # Different RNG seeds sample different worlds.
    other = determinize(state, 0, random.Random(4))
    assert other != world


def test_determinize_rejects_an_unknown_observer() -> None:
    state = _play_rounds(seed=2, rounds=1)
    with pytest.raises(ValueError, match="observer"):
        determinize(state, 4, random.Random(0))


def test_position_value_prefers_victory_points_and_rank() -> None:
    state = _play_rounds(seed=5, rounds=2)
    own = state.players[0]
    richer = replace(state.players[0], victory_points=own.victory_points + 1)
    ahead = replace(state, players=(richer, *state.players[1:]))
    assert position_value(ahead, 0) > position_value(state, 0)
    assert player_value(richer) - player_value(own) == pytest.approx(10.0)

    finished = run_policy_game(
        UprisingRulesEngine(),
        RulesetConfig(),
        9,
        tuple(HeuristicAgent(seed=seat) for seat in range(4)),
    )
    values = [position_value(finished.state, seat) for seat in range(4)]
    winner = finished.standings[0].player
    assert values[winner] == max(values)
    assert values[winner] == 100.0


class _StateSpy:
    """Records whether the runner used the state-aware path."""

    def __init__(self) -> None:
        self.state_calls = 0
        self.view_calls = 0
        self._inner = HeuristicAgent(seed=0)

    def choose_action(
        self,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        self.view_calls += 1
        return self._inner.choose_action(observation, legal_actions)

    def choose_action_with_state(
        self,
        state: GameState,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        self.state_calls += 1
        assert state.phase is not GamePhase.FINISHED
        assert observation.player == legal_actions[0].actor
        return self._inner.choose_action(observation, legal_actions)


def test_runner_hands_the_state_to_state_agents() -> None:
    spy = _StateSpy()
    assert isinstance(spy, StateAgent)
    assert not isinstance(HeuristicAgent(seed=0), StateAgent)
    agents: tuple[Agent, ...] = (
        spy,
        *(HeuristicAgent(seed=seat) for seat in range(1, 4)),
    )

    simulation = run_policy_game(UprisingRulesEngine(), RulesetConfig(), 4, agents)

    assert simulation.state.phase is GamePhase.FINISHED
    assert spy.state_calls > 0
    assert spy.view_calls == 0


def test_rollout_agent_searches_only_when_there_is_a_choice() -> None:
    agent = RolloutAgent(seed=1, rollouts=1, candidates=3)
    assert isinstance(agent, StateAgent)
    assert isinstance(make_agent("rollout", 0), RolloutAgent)
    with pytest.raises(ValueError, match="positive"):
        RolloutAgent(seed=1, rollouts=0)

    engine = UprisingRulesEngine()
    state = _play_rounds(seed=8, rounds=3)
    decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    seat = decision.owner
    view = engine.observe(state, seat)
    legal = engine.legal_actions(state, seat)
    assert len(legal) > 1

    chosen = agent.choose_action_with_state(state, view, legal)
    assert chosen in legal
    # The same seed and inputs reproduce the same choice.
    again = RolloutAgent(seed=1, rollouts=1, candidates=3)
    assert again.choose_action_with_state(state, view, legal) == chosen
    # A single legal action needs no rollout and comes straight back.
    assert agent.choose_action_with_state(state, view, legal[:1]) == legal[0]
    # Without a state the agent still answers, like the heuristic would.
    assert agent.choose_action(view, legal) in legal
    with pytest.raises(ValueError, match="at least one"):
        agent.choose_action_with_state(state, view, ())


def test_rollout_agent_finishes_a_game_through_the_runner() -> None:
    agents: tuple[Agent, ...] = (
        RolloutAgent(seed=3, rollouts=1, candidates=2),
        *(HeuristicAgent(seed=seat) for seat in range(1, 4)),
    )
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), 12)
    chance = ChanceResolver(seed=12)
    rollout_decisions = 0
    # Fifty decisions are enough to cross an Agent turn, a Reveal turn, and
    # at least one Combat without spending seconds on a full game.
    for _ in range(50):
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        actions = engine.legal_actions(state, decision.owner)
        view = engine.observe(state, decision.owner)
        agent = agents[decision.owner]
        if isinstance(agent, StateAgent):
            action = agent.choose_action_with_state(state, view, actions)
            rollout_decisions += 1
        else:
            action = agent.choose_action(view, actions)
        assert action in actions
        state = engine.apply(state, action).state
    assert rollout_decisions > 0
    assert state.round_number >= 1
