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
    assert OBSERVATION_VERSION == 30
    # 66 Uprising personal-card identities plus 26 Bloodlines Imperium
    # identities, the Bloodlines promo, 25 Immortality Imperium identities,
    # Experimentation, the 19 Tleilaxu deck cards (promo included) and Epic
    # Game Mode's Control the Spice; 39 Uprising Intrigue identities plus 18
    # Bloodlines, 12 Twisted, 10 Navigation, and 11 Immortality.
    assert len(PERSONAL_CARD_IDS) == 66 + 26 + 1 + 25 + 1 + 19 + 1
    assert PERSONAL_CARD_IDS[-1] == "control_the_spice"
    assert len(INTRIGUE_IDS) == 39 + 18 + 12 + 10 + 11
    # 16 Uprising Conflicts, the two Bloodlines cards and Epic Game Mode's
    # Economic Supremacy (identity universe); the battle cards add the four
    # Objectives before Economic Supremacy, so the older ones keep their
    # columns.
    assert len(CONFLICT_IDS) == 19
    assert CONFLICT_IDS[-1] == "economic_supremacy"
    assert len(BATTLE_CARD_IDS) == 24
    assert BATTLE_CARD_IDS[-1] == "economic_supremacy"
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
    # v26, v27: no column (a frame kind came and went). v28: Epic Game
    # Mode: Control the Spice in the 19 personal-card segments
    # (4 x 4 seat zones, imperium_removed, private_hand, private_peeked_card),
    # Economic Supremacy in the 4 seat battle-card segments, and the
    # epic_game flag (4,587 -> 4,611). v29: each relative seat's waiting
    # recruit and specimen shortfall, 4 x 2 (4,611 -> 4,619; OQ-030, OQ-049).
    # v30: the 90-column intrigue_trash segment, counted in the 3,038 base,
    # is gone: Intrigue cards have no trash pile (4,619 -> 4,529; OQ-061);
    # each relative seat's owed Emperor track Spies are appended, 4 columns
    # (4,529 -> 4,533; user ruling 2026-10-04).
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
        + 19
        + 4
        + 1
        + 4 * 2
        - 90
        + 4
    )
    assert OBSERVATION_SIZE == 4_533

    offset = 0
    for segment in OBSERVATION_SEGMENTS:
        assert segment.offset == offset
        assert segment.length > 0
        offset += segment.length
    assert offset == OBSERVATION_SIZE

    assert segment_slice("global_scalars") == slice(0, 12)
    names = [segment.name for segment in OBSERVATION_SEGMENTS]
    assert "intrigue_trash" not in names
    assert names[names.index("intrigue_discard") + 1] == "imperium_removed"
    assert (
        segment_slice("intrigue_discard").stop
        == segment_slice("imperium_removed").start
    )
    seat0_in_play = segment_slice("seat0_in_play")
    assert seat0_in_play.stop - seat0_in_play.start == 66 + 26 + 1 + 25 + 20 + 1
    private_secret_project = segment_slice("private_secret_project")
    # v22 appends the Arrakeen Scouts segments after the private ones.
    assert private_secret_project.stop == segment_slice("scouts_items").start
    # v28 appends the Epic Game Mode flag after the last Scouts segment.
    assert segment_slice("scouts_calls").stop == segment_slice("epic_game").start
    assert segment_slice("epic_game").stop == segment_slice("shortfall").start
    assert segment_slice("shortfall").stop == segment_slice("track_spies_owed").start
    assert segment_slice("track_spies_owed").stop == OBSERVATION_SIZE


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


def test_waiting_shortfalls_use_the_appended_columns_by_relative_seat() -> None:
    # v29 (OQ-030, OQ-049): troops then specimens for each seat, the observer
    # first, in seat order after it.
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(immortality=True), seed=5)
    short = replace(state.players[1], ungained_troops=2, ungained_specimens=1)
    state = replace(state, players=(state.players[0], short, *state.players[2:]))
    columns = segment_slice("shortfall")
    assert encode_player_view(engine.observe(state, 0))[columns] == (
        0, 0, 2, 1, 0, 0, 0, 0,
    )
    assert encode_player_view(engine.observe(state, 1))[columns] == (
        2, 1, 0, 0, 0, 0, 0, 0,
    )


def test_epic_game_flag_and_cards_use_the_appended_columns() -> None:
    # v28: the flag says the Endgame opens at 12 [Rise of Ix p. 10]; Control
    # the Spice and Economic Supremacy take the last column of their
    # segments, so every older identity keeps its column.
    engine = UprisingRulesEngine()
    plain = engine.reset(RulesetConfig(immortality=True), seed=5)
    epic = engine.reset(RulesetConfig(immortality=True, epic_game=True), seed=5)
    flag = segment_slice("epic_game")
    control_the_spice = len(PERSONAL_CARD_IDS) - 1
    for observer in range(4):
        assert encode_player_view(engine.observe(plain, observer))[flag] == (0,)
        encoded = encode_player_view(engine.observe(epic, observer))
        assert encoded[flag] == (1,)
        # With Immortality every Control the Spice starts in its owner's
        # discard pile [Immortality p. 12], which every seat sees (OQ-010).
        for seat in range(4):
            discard = encoded[segment_slice(f"seat{seat}_discard")]
            assert discard[control_the_spice] == 1
            assert sum(discard) == 1

    # A won Economic Supremacy shows face up in the last battle-card column.
    winner = replace(epic.players[1], won_conflict_ids=("economic_supremacy",))
    won = replace(
        epic,
        players=(epic.players[0], winner, *epic.players[2:]),
        conflict_deck=tuple(
            card for card in epic.conflict_deck if card != "economic_supremacy"
        ),
    )
    encoded = encode_player_view(engine.observe(won, 0))
    battle_cards = encoded[segment_slice("seat1_battle_cards")]
    assert battle_cards[len(BATTLE_CARD_IDS) - 1] == 1


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
# Re-pinned on 2026-09-30 for the subcommittee join inside the turn (OQ-076
# alternative C, codec v123, observation v27 unchanged): only "scouts"
# moved. Traced against HEAD (6878111, extracted with ``git archive``): the
# first difference is decision 344, where a random seat has just taken the
# High Council seat; the old engine opened the ``scouts_subcommittee``
# frame there at once, the new one keeps the Agent-turn frame with
# ``choose_subcommittee``, and the new decision 345 (the list, opened) is
# byte for byte the old decision 344's four vectors. No encoder file
# changed.
# Re-pinned on 2026-09-30 for observation v28 (Epic Game Mode, merged from
# the epic-game-mode branch, where it was v26: Control the Spice at the end
# of every personal-card segment, Economic Supremacy at the end of every
# battle-card and Conflict segment, the epic_game flag appended last): for
# all six games, each vector cut back to the v27 layout (each v27 segment's
# first columns, the segment table taken from master 402d124 with ``git
# archive``) reproduced the v27 digests above exactly with the same vector
# counts, and all 24 new columns were 0. None of the six games turns Epic
# on, so no trajectory moved.
# Re-pinned 2026-10-01 for OQ-095 (codec v125): every Agent turn now ends
# only through its owner's finish_agent_turn, so each Agent turn gains that
# decision (and random seats take optional end-of-turn actions first), and
# all six seeds play differently. ``adapters/observation_encoding.py``,
# ``core/observation.py`` and ``rules/frames.py`` (FrameKind) are byte for
# byte the files of the previous pin (master 659cefb); only the trajectories
# moved.
# Re-pinned 2026-10-02 for L2's decision windows (same codec v125):
# ``everything`` first moved with the recall confirms (Imperial Privilege
# or a Contract's recall with no target now asks instead of skipping);
# it moved again with Holy War, whose opponents are now always asked;
# the encoder files are still byte for byte the previous pin's.
# Re-pinned 2026-10-02 for codec v127: ``everything`` moved in round 9,
# where seat 3's Battlefield Research retreats its last troop and opens its
# Tech window above the Combat Intrigue loop. Seat 3 used to be offered the
# next pass and that pass ended Combat Intrigue; now the loop drops seat 3
# and seats 0-2 pass again [Main p. 14; OQ-003]. A scratch trace of both
# versions found that round-9 play as the first difference. The encoder
# files are byte for byte the previous pin's.
# Re-pinned 2026-10-03 for codec v129 (OQ-016): Distraction and Coercive
# Negotiation are played only once three units were deployed this turn.
# ``choam`` moved at decision 691 of 709 (round 10), where seat 3 used to
# lay Distraction face up with nothing deployed; a scratch trace of master
# 9236eb5c and this branch found it as the first difference. The other
# five games never offer either card that way and keep their digests.
# ``adapters/observation_encoding.py`` and ``core/observation.py`` are byte
# for byte the previous pin's; ``rules/frames.py`` only gained a comment on
# the retired ``INTRIGUE_TRIGGER_SPY`` kind, which keeps its place.
# Re-pinned 2026-10-04 for observation v29 (OQ-030/OQ-049, each relative
# seat's waiting recruit and specimen shortfall appended last) together with
# codec v130 (OQ-021, OQ-005, OQ-050). For base, choam, draft,
# promo_bloodlines_tech and scouts, each vector cut back to the v28 layout
# (its last 8 columns dropped) reproduces the v28 digests (master 7f5c8164)
# exactly with the same vector counts, so no trajectory moved -- none of
# these games refills a shortfall, plays an Objective flip or reaches
# Shaddam's exhausted market. The new columns are nonzero in 56 (base; a
# shortfall is dropped once no turn is open), 8 (choam), 24 (draft) and 32
# (promo_bloodlines_tech) vectors. ``everything`` moved (3,624 -> 3,208
# vectors) because a specimen may now be returned at Combat Intrigue
# priority and at a supply-less Control defense (OQ-050): with those two
# windows patched shut in a scratch run, its cut vectors reproduce the v28
# digest and count exactly.
# Re-pinned 2026-10-04 (second batch) for observation v30 and codec v131:
# OQ-061 removed the 90-column intrigue_trash segment and the owed Emperor
# track Spies (OQ-057 (15)) appended a 4-column track_spies_owed segment.
# For base, choam, draft, everything and promo_bloodlines_tech, each vector
# cut back to the v29 layout (the last 4 columns dropped, the 90 columns put
# back after intrigue_discard with every trashed Intrigue card moved from
# the discard counts into them -- no reshuffle follows a trash in these
# games) reproduces the v29 digests above exactly with the same counts, so
# no trajectory moved; OQ-013, the Interstellar Trade/Stilgar change and
# OQ-012 move none of the six games. ``scouts`` moved (3,516 -> 3,424
# vectors) because an owed track Spy now waits in its owner's turn: with
# that wait patched off in a scratch run its cut vectors reproduce the v29
# digest and count exactly.
# Re-pinned 2026-10-04 (fourth batch, codec v133): base, choam and draft
# moved (2,780 -> 3,144, 2,836 -> 2,856 and 2,392 -> 2,416 vectors) because a
# separate-line Intrigue (Depart for Arrakis and the like) can no longer be
# finished before one of its lines is used (OQ-058, user ruling 2026-10-04):
# with that gate patched open in a scratch run all six games reproduce the
# pins above exactly. The OQ-029 deployment allowance, the Usurp in-play
# change and the OQ-026 prune move none of the six.
# v134 adds the final draft confirmation decision. It consumes one random
# policy choice, shifting only the draft trace. A scratch run skipping that
# decision in both encoding and policy RNG exactly reproduces the v133
# draft pin (77f0cb01..., 2416); the other five pins remain unchanged.
# v135 queues Tech acquire icons as freely ordered actions (OQ-098).
# Only the two Tech-enabled traces move; the observation layout stays v30.
# v136 adds scouts_rewards_first (OQ-100); none of the six pins moves.
# v137 (the Steam app card comparison, 2026-10-06) moves two pins, each
# because a "zero" count joins a legal list the random seats draw from:
# draft (2,808 -> 2,732 vectors) from Tactical Option's "Retreat any number
# of your troops" now allowing 0 [FAQ p. 3] (commit 8a982319), and choam
# (2,856 -> 2,708) from "Deploy up to two troops" now allowing 0 [FAQ p. 2]
# (05b285fd). A per-commit run of the batch (scratch, 2026-10-06) gave these
# exact values at those two commits. On the other branch of the batch the
# draft trace had moved too (Tread in Darkness's trash and draw as separate
# icons, 96163929, then Treacherous Maneuver's single gain of 2, 57e6c791),
# but after the merge it leaves the old path earlier, at the zero retreat, and
# no later commit of the batch moves any of the six.
_GOLDEN_DIGESTS = {
    "base": ("611b73e4bac5331e7247af075612d07830e54effd4e370377ab64e588ab6fc06", 3144),
    "choam": ("2777d9168a91b30a646404b0b7cd0276476c83fc379d7de596632d5cbbe56efe", 2708),
    "promo_bloodlines_tech": (
        "e97cb2adf5315ca8b5103b820fa8a76192ec1150810b99d6c6110639ea51af79",
        2908,
    ),
    "everything": (
        "54d4ae98a20e8653a6bd899435be3bb9a0a81899c4c4413f56c21924db7b5097",
        3360,
    ),
    "draft": ("33bdd8eee62a5cc91d3e3fea78b659c4b44f350d21069768ff6bb0c3fe35e5e1", 2732),
    "scouts": (
        "3626ddc81a3ab4b957faa18ecfae231f659a02fceeec68b0adec5a51e517f4de",
        3424,
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
