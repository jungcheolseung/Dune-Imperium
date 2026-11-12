"""The bytes path of the observation encoding (2026-11 engine speed, round 3).

``encode_player_view_bytes`` and ``training.policy.encoded_view`` must give
exactly what the tuple path gives: the bytes of ``encode_player_view`` when
every value fits a byte, and otherwise nothing new (the caller's fallback).
"""

from dataclasses import replace

import numpy as np
import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import observation_encoding
from dune_imperium.adapters.observation_encoding import (
    OBSERVATION_SIZE,
    encode_player_view,
    encode_player_view_bytes,
    segment_slice,
)
from dune_imperium.agents import RandomAgent
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.observation import PlayerView
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.training.policy import encoded_view

_CONFIGS = {
    "uprising-all": RulesetConfig(
        choam_module=True,
        leader_draft=True,
        promo_cards=True,
        bloodlines=True,
        tech_module=True,
        immortality=True,
        epic_game=True,
        arrakeen_scouts=True,
    ),
    "imperium-ix-all": RulesetConfig(
        base_game=BaseGame.IMPERIUM,
        rise_of_ix=True,
        promo_cards=True,
        bloodlines=True,
        tech_module=True,
        immortality=True,
        arrakeen_scouts=True,
        leader_draft=True,
    ),
}


def _states(config: RulesetConfig, seed: int, steps: int) -> list[GameState]:
    engine = UprisingRulesEngine()
    agents = tuple(RandomAgent(seed=seed * 10 + seat) for seat in range(4))
    state = engine.reset(config, seed)
    chance = ChanceResolver(seed=seed)
    states = [state]
    for _ in range(steps):
        if state.phase is GamePhase.FINISHED:
            break
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
        else:
            assert isinstance(decision, PlayerDecision)
            legal = engine.legal_actions(state, decision.owner)
            view = engine.observe(state, decision.owner)
            action = agents[decision.owner].choose_action(view, legal)
            state = engine.apply(state, action, legal_actions=legal).state
        states.append(state)
    return states


def _bytes(view: PlayerView) -> bytes:
    packed = encode_player_view_bytes(view)
    assert packed is not None
    return bytes(packed)


@pytest.mark.parametrize("name", sorted(_CONFIGS))
def test_the_bytes_are_the_tuple_s_for_every_seat_of_every_state(name: str) -> None:
    engine = UprisingRulesEngine()
    observation_encoding._SEAT_BLOCKS.clear()
    for state in _states(_CONFIGS[name], 4_100, 600):
        for seat in range(4):
            view = engine.observe(state, seat)
            values = encode_player_view(view)
            assert _bytes(view) == bytes(values)
            array = encoded_view(view)
            expected = np.asarray(values, dtype=np.int32)
            assert array.dtype == expected.dtype
            assert array.flags.writeable
            assert np.array_equal(array, expected)


def _observed() -> PlayerView:
    engine = UprisingRulesEngine()
    states = _states(_CONFIGS["uprising-all"], 4_200, 120)
    return engine.observe(states[-1], 1)


def _with_seat(view: PlayerView, seat: int, **changes: object) -> PlayerView:
    players = list(view.players)
    players[seat] = replace(players[seat], **changes)  # type: ignore[arg-type]
    return replace(view, players=tuple(players))


@pytest.mark.parametrize("victory_points", (256, 1_000, -1))
def test_a_value_outside_a_byte_takes_the_old_path(victory_points: int) -> None:
    view = _with_seat(_observed(), 2, victory_points=victory_points)

    assert encode_player_view_bytes(view) is None
    values = encode_player_view(view)
    array = encoded_view(view)
    assert array.dtype == np.int32
    assert np.array_equal(array, np.asarray(values, dtype=np.int32))
    # Seat 2 is relative seat 1 for observer 1.
    assert values[segment_slice("seat1_scalars")][0] == victory_points
    assert array[segment_slice("seat1_scalars")][0] == victory_points


def test_an_encoding_error_is_raised_by_the_old_path_as_before() -> None:
    view = replace(_observed(), private=None)

    assert encode_player_view_bytes(view) is None
    with pytest.raises(ValueError, match="requires the private view"):
        encode_player_view(view)
    with pytest.raises(ValueError, match="requires the private view"):
        encoded_view(view)


def test_a_seat_block_is_kept_per_public_view_object() -> None:
    view = _observed()
    observation_encoding._SEAT_BLOCKS.clear()
    first = _bytes(view)
    blocks = dict(observation_encoding._SEAT_BLOCKS)

    assert len(blocks) == 4
    assert {id(player) for player in view.players} == set(blocks)
    # The second encoding of the same view reads the kept blocks.
    assert _bytes(view) == first == bytes(encode_player_view(view))
    assert all(
        observation_encoding._SEAT_BLOCKS[key][1] is blocks[key][1] for key in blocks
    )

    # A changed seat is another object, with its own block.
    changed = _with_seat(view, 3, victory_points=view.players[3].victory_points + 1)
    assert _bytes(changed) == bytes(encode_player_view(changed))
    assert _bytes(changed) != first
    assert len(observation_encoding._SEAT_BLOCKS) == 5


def test_every_observer_shares_the_same_seat_blocks() -> None:
    engine = UprisingRulesEngine()
    state = _states(_CONFIGS["imperium-ix-all"], 4_300, 200)[-1]
    observation_encoding._SEAT_BLOCKS.clear()
    for seat in range(4):
        view = engine.observe(state, seat)
        assert _bytes(view) == bytes(encode_player_view(view))
    assert len(observation_encoding._SEAT_BLOCKS) == 4


def test_the_seat_block_layout_is_the_seat_segments() -> None:
    start = observation_encoding._SEAT_STARTS
    block = observation_encoding._SEAT_BLOCK
    assert block * 4 == start[3] + block - start[0]
    for seat in range(4):
        assert segment_slice(f"seat{seat}_scalars").start == start[seat]
        assert segment_slice(f"seat{seat}_tech").stop == start[seat] + block
    assert start[3] + block <= OBSERVATION_SIZE
