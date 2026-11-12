"""The win odds: each seat's chance of first place at a round's opening.

``evaluation.win_odds`` reads every seat's value over public worlds and turns
the four values into probabilities. These tests pin the parts that do not
need the real network: which states open a round, which games show odds,
the softmax, the guard against open private picks, and that the numbers of
two states differing only in hidden information are the same, with a fake
network whose value reads every column of a seat's view.
"""

import math
from dataclasses import replace
from functools import cache
from typing import Any

import numpy as np
import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.registry import make_agent
from dune_imperium.config import BaseGame
from dune_imperium.core.observation import observe_state
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.evaluation.win_odds import (
    BETA,
    network_unavailable_reason,
    odds_from_values,
    opens_round,
    private_choice_open,
    public_values,
    round_odds,
    unavailable_reason,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.simulation.invariants import _scramble_hidden_information
from dune_imperium.simulation.runner import run_policy_game

torch = pytest.importorskip("torch")

CONFIG = RulesetConfig(
    choam_module=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
    go_to_11=True,
    epic_game=True,
    leader_draft=True,
)


class _FakeValues:
    """A value that reads every column of the view: a fixed random weighting."""

    reward_step = 1 / 6

    def __init__(self) -> None:
        self.calls = 0

    def values(self, observations: Any) -> Any:
        self.calls += 1
        width = observations.shape[1]
        weights = torch.from_numpy(
            np.random.default_rng(7).normal(size=width).astype(np.float32) / 300.0
        )
        return torch.tanh(observations.float() @ weights)


@cache
def _game() -> tuple[tuple[GameState, ...], tuple[GameState, ...], int]:
    """A heuristic game's round openings, every 30th state, and its rounds."""

    engine = UprisingRulesEngine()
    openings: list[GameState] = []
    others: list[GameState] = []
    reached = [0]
    count = [0]

    def hook(state: GameState) -> None:
        count[0] += 1
        if opens_round(state, reached[0]):
            reached[0] = state.round_number
            openings.append(state)
        elif count[0] % 30 == 0:
            others.append(state)

    agents = [make_agent("heuristic", 300 + seat, CONFIG) for seat in range(4)]
    result = run_policy_game(engine, CONFIG, 75, agents, on_state=hook)
    return tuple(openings), tuple(others), result.state.round_number


def test_each_round_opens_once_past_its_round_start() -> None:
    openings, _, rounds = _game()
    assert [state.round_number for state in openings] == list(range(1, rounds + 1))
    for state in openings:
        assert state.phase is not GamePhase.ROUND_START
        assert state.phase is not GamePhase.FINISHED


def test_a_round_opening_holds_no_private_pick() -> None:
    openings, _, _ = _game()
    assert not any(private_choice_open(state) for state in openings)


def test_an_agent_card_picked_and_not_placed_stops_the_numbers() -> None:
    _, others, _ = _game()
    picked = [
        state
        for state in others
        if any(observe_state(state, seat).private.agent_card_pick for seat in range(4))  # type: ignore[union-attr]
    ]
    assert picked, "no state with a picked Agent card in the sample"
    assert all(private_choice_open(state) for state in picked)
    assert round_odds(_FakeValues(), picked[0]) is None  # type: ignore[arg-type]


def test_rows_picked_toward_an_effect_stop_the_numbers() -> None:
    # Stage B3 (OQ-111 (4)): the rows a seat picked toward a waiting effect
    # are seen by no other seat, and the worlds do not deal them again.
    _, others, _ = _game()
    picked = [
        state
        for state in others
        if any(observe_state(state, seat).private.effect_pick for seat in range(4))  # type: ignore[union-attr]
    ]
    assert picked, "no state with rows picked toward an effect in the sample"
    assert all(private_choice_open(state) for state in picked)


def test_a_card_an_open_frame_peeked_at_stops_the_numbers() -> None:
    # Controlled shows its owner the deck's top card while the choice is up
    # (``core.observation.peeked_card_id``); the frame's context names it.
    openings, _, _ = _game()
    state = openings[1]
    assert not private_choice_open(state)
    top = state.decision_stack[-1]
    peeking = replace(
        top, context=tuple(sorted((*top.context, ("peeked_card_id", "any_card"))))
    )
    assert private_choice_open(
        replace(state, decision_stack=(*state.decision_stack[:-1], peeking))
    )


def test_the_odds_are_a_softmax_of_the_values() -> None:
    assert odds_from_values((0.0, 0.0, 0.0, 0.0)) == (0.25, 0.25, 0.25, 0.25)
    odds = odds_from_values((0.3, -0.1, -0.1, -0.2))
    assert math.isclose(sum(odds), 1.0)
    assert odds[0] > odds[1] == odds[2] > odds[3]
    assert math.isclose(odds[0] / odds[1], math.exp(BETA * 0.4))


@pytest.mark.parametrize("observer", range(4))
def test_the_numbers_ignore_what_a_seat_alone_knows(observer: int) -> None:
    openings, _, _ = _game()
    network = _FakeValues()
    for state in openings:
        twin = _scramble_hidden_information(state, observer)
        assert public_values(network, twin, 4) == public_values(network, state, 4)  # type: ignore[arg-type]


def test_the_numbers_move_with_the_position_and_sum_to_one() -> None:
    openings, _, _ = _game()
    network = _FakeValues()
    seen = set()
    for state in openings:
        odds = round_odds(network, state, 4)  # type: ignore[arg-type]
        assert odds is not None and len(odds) == 4
        assert math.isclose(sum(odds), 1.0)
        seen.add(odds)
    assert len(seen) == len(openings)


def test_the_numbers_are_the_same_on_every_recomputation() -> None:
    openings, _, _ = _game()
    first = round_odds(_FakeValues(), openings[2], 4)  # type: ignore[arg-type]
    assert round_odds(_FakeValues(), openings[2], 4) == first  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("config", "reason"),
    [
        (CONFIG, None),
        (RulesetConfig(), None),
        (replace(CONFIG, arrakeen_scouts=True), None),
        (RulesetConfig(base_game=BaseGame.IMPERIUM), "base_game"),
        (replace(CONFIG, rise_of_ix=True), "rise_of_ix"),
        (replace(CONFIG, ix_tech_tiles=True), "rise_of_ix"),
        (replace(CONFIG, ix_tech_tiles=True, ix_leaders=True), "rise_of_ix"),
        (replace(CONFIG, imperium_cards=True), "imperium_cards"),
    ],
)
def test_only_the_networks_own_family_of_games_shows_odds(
    config: RulesetConfig, reason: str | None
) -> None:
    assert unavailable_reason(config) == reason


def test_a_network_of_another_reward_scale_shows_none() -> None:
    network = _FakeValues()
    assert network_unavailable_reason(network) is None  # type: ignore[arg-type]
    network.reward_step = 0.0
    assert network_unavailable_reason(network) == "reward_step"  # type: ignore[arg-type]
