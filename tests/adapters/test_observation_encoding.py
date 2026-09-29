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
    assert OBSERVATION_VERSION == 27
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
    # v20: one seat scalar for the Contract icons held to the turn's end when
    # nothing in a non-empty market could be taken (OQ-059).
    # v22: Arrakeen Scouts: 77 items (14 subcommittees, 16 missions, 32
    # events, 11 auctions, 4 sales), 4 round modifiers, 3 schedule values
    # (4,327 -> 4,411). v23: mission pieces, 16 missions x 4 parked seats
    # and x 5 goods columns (4,411 -> 4,555). v24: secret picks, 4 relative
    # seats x 2 and 3 secret events x 4 lines (4,555 -> 4,575). v25:
    # auctions, bids 4 + 1, market 3, calls 4 (4,575 -> 4,587).
    assert OBSERVATION_SIZE == (
        3038
        + 24
        + 4 * 21
        + 1
        + 19
        + 563
        + 400
        + 8
        + 90
        + 8
        + 11 * 8
        + 4
        + 77
        + 4
        + 3
        + 16 * 4
        + 16 * 5
        + 4 * 2
        + 3 * 4
        + 5
        + 3
        + 4
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
    # v22 appends the Arrakeen Scouts segments after the private ones.
    assert private_secret_project.stop == segment_slice("scouts_items").start
    assert segment_slice("scouts_calls").stop == OBSERVATION_SIZE


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


# SHA-256 over every observer's int32 encoding at every player decision (and
# the finished state) of one RandomAgent game per ruleset, game seed 91,
# computed with the encoder as it was before its 2026-09-16 speed rewrite
# (commit acdb36c). The rewrite changed how the vector is produced, not what
# it holds, and the two encoders were compared vector for vector on these
# games before the digests were pinned. A digest that moves means either the
# encoding changed -- which needs an ``OBSERVATION_VERSION`` bump -- or the
# engine now plays these seeds differently (a rules fix); tell the two apart
# by comparing the old and new encoders on the new trajectory before
# re-pinning, never by editing a digest alone. Random seats keep the games
# independent of the heuristic's tuning.
# Re-pinned on 2026-09-20 for that day's rules fixes (the printed icons of
# Branching Path, Imperial Privilege and c7r3, mandatory Spy placement, the
# printed Influence 4 bonuses): the seeds play differently, while
# ``adapters/observation_encoding.py`` and ``core/observation.py`` are byte
# for byte the files the previous digests were pinned with.
# Re-pinned on 2026-09-26 for the card-transcription audit's rules fixes
# (codec v108): ``adapters/observation_encoding.py`` is byte for byte the
# previous file, and the encoder of the previous pin (7de618d) produced the
# same vector as the current one at every one of these games' decisions
# (``core/observation.py`` only added the unencoded revealed_contract_ids
# and FrameKind gained LEADER_SIGNET at the end, keeping every old index).
# The integration review's rules fixes of the same day moved
# ``promo_bloodlines_tech`` again; the encoder of that pin (ab87327) and the
# current one agreed on every vector of all five games, and no observation
# or encoder file changed in between.
# Re-pinned the same night for OQ-070 (a recruited Commander's deploy slot
# is a Commander's): promo_bloodlines_tech first diverges at decision 371
# and everything at decision 690, both at the changed deploy_troops offer;
# master's encoder (59e7d46 line) and this one agreed on every vector of all
# five games, and no observation or encoder file changed.
# Re-pinned on 2026-09-27 for observation v21 (the four Rise of Ix Contract
# tiles out, Spice Refinery I/II and the second Espionage I and Harvest 3+
# in [Main p. 16]): only everything moved. Traced against HEAD (6d615a5) in
# a worktree, its first difference is decision 617, where the same face-up
# slot holds contract:espionage_i_copy_2 instead of contract:espionage_ii;
# the four vectors there are byte for byte the old ones (the kept tiles keep
# their index), and the game then differs by the reward. The encoder file
# changed only its version constant.
# Re-pinned on 2026-09-28 for observation v22 (the Arrakeen Scouts segments
# appended after every older one): for all five old games the vector's first
# 4,327 columns reproduced the previous digests exactly and every Scouts
# column was 0, so the games and the old columns are byte for byte what they
# were. "scouts" (CHOAM with the new option) was added then, and re-pinned
# the same day when the four round modifiers began to act (slice 3b) and
# again when subcommittees could be joined (slice 4) and when events and
# sales offered their turn-order choices (slice 5): the five other games did
# not move.
# Re-pinned for observation v23 (the mission-piece segments appended after
# v22's): the five old games' first 4,411 columns reproduced the v22
# digests exactly and every new column was 0; "scouts" moved as missions
# began to act (slice 6a).
# Re-pinned for observation v24 (the secret-pick segments appended after
# v23's): the five old games' first 4,555 columns reproduced the v23
# digests exactly and every new column was 0; "scouts" moved as secret
# events began to be played (slice 7).
# Re-pinned for observation v25 (the auction segments appended after v24's):
# the five old games' first 4,575 columns reproduced the v24 digests exactly
# and every new column was 0; "scouts" moved as auctions began (slice 8).
# Re-pinned for observation v26 (the ``scouts_top_up`` frame kind, appended
# to the frame kinds): the five old games reproduced their digests exactly;
# "scouts" moved with the 2026-09-29 rulings, which change what its game
# offers (it reveals Weirding Warfare, Moment of Revelation and a late
# auction).
# Re-pinned for observation v27 and the 2026-09-29 Round Start order
# (reveal -> optional Control defense -> draw, OQ-072): every game kept
# its vector count, so the trajectories are the same; only the vectors at
# a Control defense decision changed (phase Round Start, hands not yet
# drawn, no turn owner). "promo_bloodlines_tech" has no defense in its
# game and did not move; the Scouts rule batch left "scouts" unchanged.
_GOLDEN_DIGESTS = {
    "base": ("065fd43c904ab67a65c21d0d5b41d81338880c6d883a861132773deb646161ea", 2572),
    "choam": ("57a3a11eed5f3b0b5a9ecab205250400463fe0e2bc831dad3d8e59737f98ead8", 2972),
    "promo_bloodlines_tech": (
        "90eb2c749063dabf55630750cb65e3132739f0da7592d32bbee5967bb5f8d852",
        2772,
    ),
    "everything": (
        "b237d765c302ee775ef8f9821435465a9ff0f96fa95dfb980ca668e00f783292",
        3012,
    ),
    "draft": ("74b78ffc572d573d52b5ee711a79170f40456a932d4217f5ed3e7c4b6acd3e32", 2476),
    "scouts": (
        "bc2b5bda85477514a9a8f8c37c4774a4deb6bc266fbff2a7ac19c56af481c142",
        2912,
    ),
}
_GOLDEN_CONFIGS = {
    "base": {},
    "choam": {"choam_module": True},
    "promo_bloodlines_tech": {
        "promo_cards": True,
        "bloodlines": True,
        "tech_module": True,
    },
    "everything": {
        "choam_module": True,
        "promo_cards": True,
        "bloodlines": True,
        "tech_module": True,
        "immortality": True,
    },
    "draft": {"leader_draft": True},
    "scouts": {"choam_module": True, "arrakeen_scouts": True},
}


def _encoding_digest(config: RulesetConfig, seed: int) -> tuple[str, int]:
    import hashlib

    import numpy as np

    from dune_imperium.agents import RandomAgent

    engine = UprisingRulesEngine()
    agents = [RandomAgent(seed=9_100 + seed + s) for s in range(4)]
    state = engine.reset(config, seed)
    chance = ChanceResolver(seed=seed)
    hasher = hashlib.sha256()
    encoded = 0
    for _ in range(30_000):
        if state.phase is GamePhase.FINISHED:
            break
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        for seat in range(4):
            vector = encode_player_view(engine.observe(state, seat))
            hasher.update(np.asarray(vector, dtype=np.int32).tobytes())
            encoded += 1
        actions = engine.legal_actions(state, decision.owner)
        action = agents[decision.owner].choose_action(
            engine.observe(state, decision.owner), actions
        )
        state = engine.apply(state, action, legal_actions=actions).state
    for seat in range(4):
        vector = encode_player_view(engine.observe(state, seat))
        hasher.update(np.asarray(vector, dtype=np.int32).tobytes())
        encoded += 1
    return hasher.hexdigest(), encoded


@pytest.mark.parametrize("name", sorted(_GOLDEN_DIGESTS))
def test_encoding_matches_the_pinned_golden_digest(name: str) -> None:
    assert (
        _encoding_digest(RulesetConfig(**_GOLDEN_CONFIGS[name]), 91)
        == (_GOLDEN_DIGESTS[name])
    )
