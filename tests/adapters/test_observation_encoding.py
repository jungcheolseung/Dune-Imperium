"""Tests for the versioned flat observation encoding."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.adapters.observation_encoding import (
    BATTLE_CARD_IDS,
    CONFLICT_IDS,
    INTRIGUE_IDS,
    OBSERVATION_SEGMENTS,
    OBSERVATION_SIZE,
    OBSERVATION_VERSION,
    PERSONAL_CARD_IDS,
    encode_player_view,
    segment_slice,
)
from dune_imperium.core import ChanceDecision, ChanceResolver, GamePhase, PlayerDecision
from dune_imperium.core.state import GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.simulation import run_random_game


def test_layout_is_versioned_and_contiguous() -> None:
    assert OBSERVATION_VERSION == 17
    # 66 Uprising personal-card identities plus 26 Bloodlines Imperium
    # identities, the Bloodlines promo, 25 Immortality Imperium identities,
    # Experimentation and the 19 Tleilaxu deck cards (promo included); 39
    # Uprising Intrigue identities plus 18 Bloodlines, 12 Twisted, 10
    # Navigation, and 11 Immortality.
    assert len(PERSONAL_CARD_IDS) == 66 + 26 + 1 + 25 + 1 + 19
    assert len(INTRIGUE_IDS) == 39 + 18 + 12 + 10 + 11
    # 16 Uprising Conflicts plus the two Bloodlines cards (identity universe).
    assert len(CONFLICT_IDS) == 18
    assert len(BATTLE_CARD_IDS) == 23
    # v9: Tech Module segments (24 global, 21 per seat, 1 private).
    # v10: the Bloodlines promo Ruthless Leadership adds one personal-card
    # identity to every identity-count segment.
    # v11: the Immortality catalog adds 25 personal-card and 11 Intrigue
    # identities to every identity-count segment (3,166 -> 3,729).
    # v12: Experimentation and the Tleilaxu deck (20 identities), four seat
    # scalars (research space, Tleilaxu space, specimens, Family Atomics)
    # and the Tleilaxu Row/deck/track spice segments (3,729 -> 4,129).
    # v13: the round's Reveal Persuasion bonus per seat and the Combat
    # Intrigue players segment (4,129 -> 4,137).
    # v14: Imperium Ceremony's peek at the Intrigue deck's top two cards,
    # one count per Intrigue identity (4,137 -> 4,227).
    # v15: Chairdog's pending returns and Usurp's borrowed Row card per seat
    # (4,227 -> 4,235).
    # v16: Bloodlines' eight contract tokens in each of the 11 contract segments.
    assert OBSERVATION_SIZE == (
        3038 + 24 + 4 * 21 + 1 + 19 + 563 + 400 + 8 + 90 + 8 + 11 * 8
    )

    offset = 0
    for segment in OBSERVATION_SEGMENTS:
        assert segment.offset == offset
        assert segment.length > 0
        offset += segment.length
    assert offset == OBSERVATION_SIZE

    assert segment_slice("global_scalars") == slice(0, 12)
    seat0_in_play = segment_slice("seat0_in_play")
    assert seat0_in_play.stop - seat0_in_play.start == 66 + 26 + 1 + 25 + 20
    private_secret_project = segment_slice("private_secret_project")
    assert private_secret_project.stop == OBSERVATION_SIZE


def test_reset_state_encodes_the_turn_decision_for_every_observer() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=5)
    assert state.first_player is not None
    frame_kinds = tuple(kind.value for kind in FrameKind)

    for observer in range(4):
        view = engine.observe(state, observer)
        encoded = encode_player_view(view)
        assert len(encoded) == OBSERVATION_SIZE

        scalars = encoded[segment_slice("global_scalars")]
        assert scalars[1] == tuple(GamePhase).index(GamePhase.PLAYER_TURNS)
        expected_relative = ((state.first_player - observer) % 4) + 1
        assert scalars[2] == expected_relative
        assert scalars[4] == frame_kinds.index("turn") + 1
        assert scalars[5] == expected_relative

        hand = encoded[segment_slice("private_hand")]
        assert view.private is not None
        assert sum(hand) == len(view.private.hand) == 5
        seat_scalars = encoded[segment_slice("seat0_scalars")]
        assert seat_scalars[23] == 5  # own public hand size
        assert seat_scalars[24] == 5  # own public deck size


def test_seat_blocks_rotate_egocentrically() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=6)

    from_zero = encode_player_view(engine.observe(state, 0))
    from_one = encode_player_view(engine.observe(state, 1))

    # Observer 0's seat1 block and observer 1's seat0 block both describe
    # absolute player 1, so every public chunk matches.
    for segment_name in (
        "scalars",
        "alliances",
        "battle_cards",
        "in_play",
        "hand_public",
        "discard",
        "completed_contracts",
    ):
        zero_slice = from_zero[segment_slice(f"seat1_{segment_name}")]
        one_slice = from_one[segment_slice(f"seat0_{segment_name}")]
        assert zero_slice == one_slice


def test_every_seat_discard_pile_is_encoded_for_every_observer() -> None:
    # OQ-010 ruling 1: discard piles are re-checkable by everyone because
    # every card reached them face up [Main pp. 9, 12, 13, 20].
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=8)
    players = list(state.players)
    players[1] = replace(
        players[1],
        deck=players[1].deck[:-2],
        discard_pile=(*players[1].discard_pile, *players[1].deck[-2:]),
    )
    state = replace(state, players=tuple(players))

    for observer in range(4):
        encoded = encode_player_view(engine.observe(state, observer))
        relative = (1 - observer) % 4
        discard = encoded[segment_slice(f"seat{relative}_discard")]
        assert sum(discard) == 2
        assert not any(
            segment.name == "private_discard" for segment in OBSERVATION_SEGMENTS
        )


@pytest.mark.parametrize("choam_module", (False, True))
def test_every_state_of_a_full_game_encodes(choam_module: bool) -> None:
    from dune_imperium.agents import RandomAgent

    engine = UprisingRulesEngine()
    config = RulesetConfig(choam_module=choam_module)
    agents = tuple(RandomAgent(seed=9100 + player) for player in range(4))
    state = engine.reset(config, 91)
    chance = ChanceResolver(seed=91)

    steps = 0
    while state.phase is not GamePhase.FINISHED:
        for observer in range(4):
            encoded = encode_player_view(engine.observe(state, observer))
            assert len(encoded) == OBSERVATION_SIZE
            assert min(encoded) >= 0
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
        else:
            assert isinstance(decision, PlayerDecision)
            actions = engine.legal_actions(state, decision.owner)
            observation = engine.observe(state, decision.owner)
            action = agents[decision.owner].choose_action(observation, actions)
            state = engine.apply(state, action).state
        steps += 1
        assert steps < 30_000

    final = encode_player_view(engine.observe(state, 0))
    assert final[segment_slice("global_scalars")][1] == tuple(GamePhase).index(
        GamePhase.FINISHED
    )


def test_terminal_standings_state_from_runner_encodes() -> None:
    engine = UprisingRulesEngine()
    result = run_random_game(engine, RulesetConfig(), game_seed=14, policy_seed=3014)
    assert isinstance(result.state, GameState)
    for observer in range(4):
        encoded = encode_player_view(engine.observe(result.state, observer))
        assert len(encoded) == OBSERVATION_SIZE


def test_leader_draft_pool_is_encoded_for_every_observer() -> None:
    from dune_imperium.adapters.observation_encoding import LEADER_IDS

    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(leader_draft=True), 15)
    assert state.phase is GamePhase.SETUP

    expected = [
        LEADER_IDS.index(leader_id) + 1 for leader_id in state.leader_draft_pool
    ]
    for observer in range(4):
        view = engine.observe(state, observer)
        assert view.leader_draft_pool == state.leader_draft_pool
        encoded = encode_player_view(view)
        assert list(encoded[segment_slice("leader_draft_pool")]) == expected
        # The draft frame kind is visible in the global decision scalars.
        assert encoded[segment_slice("global_scalars")][4] == (
            tuple(kind.value for kind in FrameKind).index("leader_draft") + 1
        )

    fixed = engine.reset(RulesetConfig(), 15)
    fixed_encoded = encode_player_view(engine.observe(fixed, 0))
    assert list(fixed_encoded[segment_slice("leader_draft_pool")]) == [0] * 6
