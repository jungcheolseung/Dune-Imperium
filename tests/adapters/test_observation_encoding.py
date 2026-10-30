"""Tests for the versioned flat observation encoding."""

from dataclasses import replace
from typing import Any

import pytest
from tests.support.observation_growth import (
    NEW_SEGMENTS,
    NONZERO_GROWTH,
    V38_SEGMENTS,
    V38_SIZE,
    V39_NEW_SEGMENTS,
    growth_since_v34,
    v38_columns,
    v38_layout,
)

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters.observation_encoding import (
    BATTLE_CARD_IDS,
    CONFLICT_IDS,
    CONTRACT_IDS,
    CONTROL_SPACE_IDS,
    FACTION_IDS,
    INTRIGUE_IDS,
    IX_SPACE_IDS,
    LEADER_IDS,
    MAKER_SPACE_IDS,
    OBSERVATION_SEGMENTS,
    OBSERVATION_SIZE,
    OBSERVATION_VERSION,
    PERSONAL_CARD_IDS,
    RESERVE_STACK_IDS,
    SPACE_IDS,
    TECH_IDS,
    TECH_SEGMENTS,
    VOICE_BLOCK_SPACE_IDS,
    ObservationSegment,
    encode_player_view,
    segment_slice,
)
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.core.observation import (
    NEGOTIATORS_RETURNABLE_KEY,
    SHIPPING_REWARDS_KEY,
    TECH_DISCOUNT_KEY,
    TECH_PAYMENT_KEY,
    known_card_seats,
    observe_state,
)
from dune_imperium.core.state import GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.action_shapes import Source, Verb
from dune_imperium.rules.engine import LEGAL_ACTION_PROVIDERS
from dune_imperium.rules.frames import IX_FRAME_KINDS, FrameKind
from dune_imperium.simulation import run_random_game


def test_layout_is_versioned_and_contiguous() -> None:
    assert OBSERVATION_VERSION == 39
    # 66 Uprising personal-card identities plus 26 Bloodlines Imperium
    # identities, the Bloodlines promo, 25 Immortality Imperium identities,
    # Experimentation, the 19 Tleilaxu deck cards (promo included) and Epic
    # Game Mode's Control the Spice, then (v35) the original game's three
    # Reserve cards and (v37) its 43 Imperium cards and three promos; 39
    # Uprising Intrigue identities plus 18 Bloodlines, 12 Twisted, 10
    # Navigation, 11 Immortality and (v37) the original game's 34; then (v39)
    # Rise of Ix's 29 Imperium cards and Boundless Ambition, and its 17
    # Intrigue cards.
    assert len(PERSONAL_CARD_IDS) == 66 + 26 + 1 + 25 + 1 + 19 + 1 + 3 + 46 + 30
    assert PERSONAL_CARD_IDS[-80] == "control_the_spice"
    assert PERSONAL_CARD_IDS[-79:-76] == (
        "arrakis_liaison",
        "imperium_the_spice_must_flow",
        "foldspace_card",
    )
    assert PERSONAL_CARD_IDS[-76] == "arrakis_recruiter"
    assert PERSONAL_CARD_IDS[-30] == "appropriate"
    assert PERSONAL_CARD_IDS[-1] == "boundless_ambition"
    assert len(INTRIGUE_IDS) == 39 + 18 + 12 + 10 + 11 + 34 + 17
    assert INTRIGUE_IDS[-51] == "bribery"
    assert INTRIGUE_IDS[-17] == "advanced_weaponry"
    # 16 Uprising Conflicts, the two Bloodlines cards and Epic Game Mode's
    # Economic Supremacy (identity universe), then (v35) the original game's
    # 18; the battle cards add the four Objectives before Economic
    # Supremacy, so the older ones keep their columns (no original Conflict
    # is won as a card [DI p. 8]). v39: Rise of Ix's three new Conflicts
    # after the original game's (its Economic Supremacy is Uprising's Epic
    # card); like the original game's, they print no battle icon.
    assert len(CONFLICT_IDS) == 19 + 18 + 3
    assert CONFLICT_IDS[18] == "economic_supremacy"
    assert CONFLICT_IDS[-4] == "grand_vision"
    assert CONFLICT_IDS[-3:] == ("skirmish_e", "skirmish_f", "trade_monopoly")
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
    # v31: the open Agent turn's two boxes, card identity + 1 and pending
    # flag each, 4 columns (4,533 -> 4,537; docs/graft-boxes-plan.md 4.7).
    # v32: each relative seat's deck pool, one count per personal-card
    # identity, 4 x 139 columns (4,537 -> 5,093; OQ-010 ruling 6).
    # v33: the seat's own picked Agent card (one count per personal-card
    # identity) and its graft flag, 139 + 1 columns (5,093 -> 5,233; stage
    # B1, OQ-111).
    # Also v33 (stage B3a, OQ-111 (4)): the seat's own picked effect, its
    # verb (one-hot over 45), source (one-hot over 21), printed personal
    # card (139), grafted-box flag (1) and the count of targets picked so
    # far (1), 45 + 21 + 139 + 1 + 1 columns (5,233 -> 5,440).
    # Also v33 (the B3c-1 review): the targets picked so far by identity --
    # Intrigue card 90, Faction 4, post 13, Tech 18, Conflict or Objective
    # card 24, and a second picked Faction 4 (5,440 -> 5,593).
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
        + 4
        + 4 * 139
        + 139
        + 1
        + 45
        + 21
        + 139
        + 1
        + 1
        + 90
        + 4
        + 13
        + 18
        + 24
        + 4
        # v33 (the B3d-2a review): a personal card picked before the last.
        + 139
        # v34 (the base-game axis): the base-game flag.
        + 1
        # v35 (stage P2a): the original game's three Reserve cards in the 26
        # personal-card segments, its three Reserve stacks, two Maker spaces,
        # Carthag's Control per seat, a fourth Agent location per seat and
        # the Mentat segment.
        + 26 * 3
        + 3
        + 2
        + 4
        + 4
        + 3
        # v36 (stage P2b): the Masterstroke segments, four seats and four
        # Factions.
        + 4
        + 4
        # v37 (stage P3a): the original game's 46 Imperium cards in the 26
        # personal-card segments and its 34 Intrigue cards in the nine
        # Intrigue segments.
        + 26 * 46
        + 9 * 34
        # v38 (OQ-145 and the original game's public markers): the public
        # deck-top counts of four seats by personal-card identity, the
        # barred spaces of four seats, and two turn flags per seat.
        + 4 * 188
        + 4 * 42
        + 4 * 2
        # v39 (stage P4a, Rise of Ix): its 30 Imperium cards in the 30
        # personal-card segments and its 17 Intrigue cards in the nine
        # Intrigue segments; the Intrigue deck's size in ``global_scalars``;
        # then four seats' three dreadnought counts, two columns per Control
        # space, four seats' ten Shipping, Negotiator, Snooper, Ilesa and
        # Strategic Push pledge columns (the pledge joined on 2026-10-30,
        # before v39 reached master), four seats' bars on the four Ix spaces,
        # the known Intrigue
        # deck top (141), its eight bottom depths, the known Intrigue of three
        # opponents (141 each), the set-aside card (218), seven pending
        # columns and the Rise of Ix flag. Its 18 Tech tiles in the six Tech
        # segments (four seats, the trash and the effect pick); its four
        # spaces add no column (an Agent location holds a space by index).
        + 30 * 30
        + 9 * 17
        + 6 * 18
        + 1
        + 4 * 3
        + 4 * 2
        + 4 * 10
        + 4 * 4
        + 141
        + 8
        + 3 * 141
        + 218
        + 7
        + 1
    )
    assert OBSERVATION_SIZE == 10_301
    assert OBSERVATION_SEGMENTS[-1] == ObservationSegment("ix_flags", 10_300, 1)
    # v39: the Tech Module's 18 tiles, then Rise of Ix's 18; the segments
    # with a column per tile are exactly ``TECH_SEGMENTS``.
    assert len(TECH_IDS) == 18 + 18
    assert TECH_IDS[17] == "training_depot" and TECH_IDS[18] == "artillery"
    assert {
        segment.name
        for segment in OBSERVATION_SEGMENTS
        if segment.length == len(TECH_IDS)
    } == TECH_SEGMENTS

    offset = 0
    for segment in OBSERVATION_SEGMENTS:
        assert segment.offset == offset
        assert segment.length > 0
        offset += segment.length
    assert offset == OBSERVATION_SIZE

    # v39: the Intrigue deck's size is the 13th global scalar.
    assert segment_slice("global_scalars") == slice(0, 13)
    names = [segment.name for segment in OBSERVATION_SEGMENTS]
    assert "intrigue_trash" not in names
    assert names[names.index("intrigue_discard") + 1] == "imperium_removed"
    assert (
        segment_slice("intrigue_discard").stop
        == segment_slice("imperium_removed").start
    )
    seat0_in_play = segment_slice("seat0_in_play")
    assert (
        seat0_in_play.stop - seat0_in_play.start
        == 66 + 26 + 1 + 25 + 20 + 1 + 3 + 46 + 30
    )
    private_secret_project = segment_slice("private_secret_project")
    # v22 appends the Arrakeen Scouts segments after the private ones.
    assert private_secret_project.stop == segment_slice("scouts_items").start
    # v28 appends the Epic Game Mode flag after the last Scouts segment.
    assert segment_slice("scouts_calls").stop == segment_slice("epic_game").start
    assert segment_slice("epic_game").stop == segment_slice("shortfall").start
    assert segment_slice("shortfall").stop == segment_slice("track_spies_owed").start
    assert segment_slice("track_spies_owed").stop == segment_slice("agent_boxes").start
    # v32 appends the four deck pools, seat by seat, after agent_boxes.
    assert segment_slice("agent_boxes").stop == segment_slice("seat0_deck_pool").start
    for seat in range(3):
        assert (
            segment_slice(f"seat{seat}_deck_pool").stop
            == segment_slice(f"seat{seat + 1}_deck_pool").start
        )
    # v33 appends the picked Agent card and its graft flag, then (stage B3a)
    # the picked effect's verb, source, card, box and target count, last.
    assert (
        segment_slice("seat3_deck_pool").stop
        == segment_slice("private_agent_card_pick").start
    )
    assert (
        segment_slice("private_agent_card_pick").stop
        == segment_slice("private_agent_card_pick_graft").start
    )
    # The targets picked so far follow by kind (the B3c-1 review).
    pick_segments = (
        "private_agent_card_pick_graft",
        "private_effect_pick_verb",
        "private_effect_pick_source",
        "private_effect_pick_card",
        "private_effect_pick_box",
        "private_effect_pick_targets",
        "private_effect_pick_intrigue",
        "private_effect_pick_faction",
        "private_effect_pick_post",
        "private_effect_pick_tech",
        "private_effect_pick_battle",
        "private_effect_pick_second_faction",
        "private_effect_pick_personal",
    )
    for before, after in zip(pick_segments, pick_segments[1:], strict=False):
        assert segment_slice(before).stop == segment_slice(after).start
    assert (
        segment_slice("private_effect_pick_personal").stop
        == segment_slice("base_game").start
    )
    # v35 appends the Mentat after the base-game flag.
    assert segment_slice("base_game").stop == segment_slice("mentat").start
    assert segment_slice("mentat").stop == segment_slice("masterstroke_secret").start
    # v38 appends the public deck tops (seat by seat), the barred spaces and
    # the turn flags after the Masterstroke segments.
    assert (
        segment_slice("private_masterstroke").stop
        == segment_slice("seat0_deck_public_top").start
    )
    for seat in range(3):
        assert (
            segment_slice(f"seat{seat}_deck_public_top").stop
            == segment_slice(f"seat{seat + 1}_deck_public_top").start
        )
    assert (
        segment_slice("seat3_deck_public_top").stop
        == segment_slice("voice_blocks").start
    )
    assert segment_slice("voice_blocks").stop == segment_slice("card_turn_flags").start
    # v39 appends Rise of Ix's segments after the card turn flags, in order.
    ix_segments = (
        "card_turn_flags",
        *(f"seat{seat}_units" for seat in range(4)),
        "dreadnought_control",
        *(f"seat{seat}_ix" for seat in range(4)),
        "voice_blocks_ix",
        "private_intrigue_top",
        "private_intrigue_bottom",
        *(f"private_known_intrigue_seat{seat}" for seat in range(1, 4)),
        "private_set_aside",
        "ix_pending",
        "ix_flags",
    )
    for before, after in zip(ix_segments, ix_segments[1:], strict=False):
        assert segment_slice(before).stop == segment_slice(after).start
    assert set(ix_segments[1:]) == V39_NEW_SEGMENTS
    assert segment_slice("ix_flags").stop == OBSERVATION_SIZE


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


def test_the_picked_agent_card_is_encoded_for_its_own_seat_only() -> None:
    # v33 (stage B1, OQ-111): the Agent turn is a card pick and then a space
    # pick, and the seat deciding the space sees the card it picked; no other
    # seat's vector holds it.
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=5)
    assert state.first_player is not None
    owner = state.first_player
    pick = next(
        action
        for action in engine.legal_actions(state, owner)
        if action.action_id == "choose_agent_card"
    )
    picked = engine.apply(state, pick).state

    card_columns = segment_slice("private_agent_card_pick")
    graft_column = segment_slice("private_agent_card_pick_graft")
    before = encode_player_view(engine.observe(state, owner))
    assert not any(before[card_columns]) and not any(before[graft_column])
    for observer in range(4):
        encoded = encode_player_view(engine.observe(picked, observer))
        if observer == owner:
            assert sum(encoded[card_columns]) == 1
            assert tuple(encoded[graft_column]) == (0,)
        else:
            assert not any(encoded[card_columns])
            assert not any(encoded[graft_column])


def test_the_picked_effect_is_encoded_for_its_own_seat_only() -> None:
    # v33 (stage B3a, OQ-111 (4)): a waiting effect is picked before its
    # target, and the seat deciding the target sees the effect it picked
    # (verb, source, printed card, box, targets so far); no other seat's
    # vector holds it.
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=5)
    assert state.first_player is not None
    owner = state.first_player
    place = DomainAction(
        "place_agent", owner, arguments=(("space_id", "desert_tactics"),)
    )
    placed = next(
        engine.apply(picked, place).state
        for picked in (
            engine.apply(state, pick).state
            for pick in engine.legal_actions(state, owner)
            if pick.action_id == "choose_agent_card"
        )
        if place in engine.legal_actions(picked, owner)
    )
    # Desert Tactics' optional trash: an effect row, then the card to trash.
    trash = next(
        action
        for action in engine.legal_actions(placed, owner)
        if action.action_id == "trash"
    )
    picked = engine.apply(placed, trash).state
    assert {row.action_id for row in engine.legal_actions(picked, owner)} == {
        "choose_personal_card"
    }

    verb = segment_slice("private_effect_pick_verb")
    source = segment_slice("private_effect_pick_source")
    card = segment_slice("private_effect_pick_card")
    box = segment_slice("private_effect_pick_box")
    targets = segment_slice("private_effect_pick_targets")
    assert verb.stop - verb.start == len(Verb)
    assert source.stop - source.start == len(Source)
    for observer in range(4):
        before = encode_player_view(engine.observe(placed, observer))
        assert not any(before[verb.start : targets.stop])
        encoded = encode_player_view(engine.observe(picked, observer))
        if observer != owner:
            assert not any(encoded[verb.start : targets.stop])
            continue
        assert encoded[verb][tuple(Verb).index(Verb.TRASH)] == 1
        assert sum(encoded[verb]) == 1
        assert encoded[source][tuple(Source).index(Source.BOARD_SPACE)] == 1
        assert sum(encoded[source]) == 1
        # A board space printed the effect: no personal card, no grafted box,
        # and no target picked yet.
        assert not any(encoded[card])
        assert tuple(encoded[box]) == (0,)
        assert tuple(encoded[targets]) == (0,)


def test_the_option_step_shows_the_seat_the_card_it_picked() -> None:
    # The 2026-10-20 review of stage B3c-1: after ``play`` and
    # ``choose_intrigue_card`` the option rows are ``choose_option(option)``
    # alone, so the seat's view must say which card it picked -- Detonation
    # and Market Opportunity both offer two options here.
    from tests.unit.rules.test_intrigue import _intrigue, _turn_state

    engine = UprisingRulesEngine()
    cards = (_intrigue("detonation"), _intrigue("market_opportunity"))
    owner = PlayerState(
        player_id=0,
        intrigue_cards=cards,
        resources=Resources(solari=20, spice=20, water=20),
    )
    state = _turn_state(owner)
    play = DomainAction("play", 0, (("printed", "plot"), ("source", "intrigue")))
    picked = engine.apply(state, play).state
    chose = [
        engine.apply(
            picked, DomainAction("choose_intrigue_card", 0, (("card_id", card),))
        ).state
        for card in cards
    ]
    rows = [engine.legal_actions(each, 0) for each in chose]
    assert rows[0] == rows[1] and len(rows[0]) == 2
    views = [encode_player_view(engine.observe(each, 0)) for each in chose]
    intrigue = segment_slice("private_effect_pick_intrigue")
    for view, card in zip(views, ("detonation", "market_opportunity"), strict=True):
        column = INTRIGUE_IDS.index(card)
        assert view[intrigue][column] == 1 and sum(view[intrigue]) == 1
    assert views[0] != views[1]
    # No other seat sees the pick.
    for observer in range(1, 4):
        assert encode_player_view(engine.observe(chose[0], observer)) == (
            encode_player_view(engine.observe(chose[1], observer))
        )


def test_every_target_picked_before_a_paths_last_has_a_segment() -> None:
    # A target row a path picks before its last stays in the seat's pick:
    # its kind, at its position, must be shown by identity
    # (``PICKED_TARGET_SEGMENTS``).
    # A window's own effect picks its targets with no effect row (stage
    # B3d-2a), and Long Live the Fighters' frame keeps its card to draw.
    from dune_imperium.adapters.observation_encoding import PICKED_TARGET_SEGMENTS
    from dune_imperium.rules.effect_steps import STEP_SPECS, TARGET_SPECS, Choose

    paths = (
        *(spec.targets for spec in STEP_SPECS.values()),
        *TARGET_SPECS.values(),
    )
    picked_first = {
        (kind.action_id, position)
        for targets in paths
        for position, (_name, kind) in enumerate(targets[:-1])
    }
    picked_first.add((Choose.PERSONAL_CARD.action_id, 0))
    for action_id, position in picked_first:
        assert position < len(PICKED_TARGET_SEGMENTS[action_id]), action_id
    for segments in PICKED_TARGET_SEGMENTS.values():
        for segment in segments:
            segment_slice(segment)


def test_the_recipient_step_shows_which_faction_was_lost_and_which_gained() -> None:
    # The review of the fix above: Captured Mentat's exchange picks the
    # Faction lost, then the one gained, then the Alliance's recipient; the
    # two Factions' order decides which Alliance is handed on, so the seat
    # must see it at the recipient step.
    from tests.unit.rules.test_reveal_turn import _imperium_instance, _state

    from dune_imperium.core import Influence

    engine = UprisingRulesEngine()
    owner = PlayerState(
        player_id=0,
        hand=(_imperium_instance("captured_mentat"),),
        influence=Influence(emperor=4, spacing_guild=4),
        alliance_faction_ids=("emperor", "spacing_guild"),
    )
    state = _state(owner)
    rivals = tuple(
        PlayerState(player_id=seat, influence=Influence(emperor=4, spacing_guild=4))
        for seat in (1, 2)
    )
    state = replace(state, players=(state.players[0], *rivals, state.players[3]))
    state = engine.apply(state, DomainAction("reveal_turn", 0)).state
    exchange = next(
        row
        for row in engine.legal_actions(state, 0)
        if row.action_id == "exchange_influence"
    )
    picked = engine.apply(state, exchange).state

    def recipient_step(lost: str, gained: str) -> GameState:
        at = picked
        for faction in (lost, gained):
            at = engine.apply(
                at, DomainAction("choose_faction", 0, (("faction", faction),))
            ).state
        return at

    one = recipient_step("emperor", "spacing_guild")
    other = recipient_step("spacing_guild", "emperor")
    assert engine.legal_actions(one, 0) == engine.legal_actions(other, 0)
    first = segment_slice("private_effect_pick_faction")
    second = segment_slice("private_effect_pick_second_faction")
    for at, lost, gained in (
        (one, "emperor", "spacing_guild"),
        (other, "spacing_guild", "emperor"),
    ):
        view = encode_player_view(engine.observe(at, 0))
        assert view[first] == tuple(int(f == lost) for f in FACTION_IDS)
        assert view[second] == tuple(int(f == gained) for f in FACTION_IDS)


def test_epic_game_flag_and_cards_use_the_appended_columns() -> None:
    # v28: the flag says the Endgame opens at 12 [Rise of Ix p. 10]; Control
    # the Spice and Economic Supremacy take the last column of their
    # segments, so every older identity keeps its column (v35 appends the
    # original game's three Reserve cards after Control the Spice).
    engine = UprisingRulesEngine()
    plain = engine.reset(RulesetConfig(immortality=True), seed=5)
    epic = engine.reset(RulesetConfig(immortality=True, epic_game=True), seed=5)
    flag = segment_slice("epic_game")
    control_the_spice = PERSONAL_CARD_IDS.index("control_the_spice")
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


_V38_SEGMENTS = (
    *(f"seat{seat}_deck_public_top" for seat in range(4)),
    "voice_blocks",
    "card_turn_flags",
)


def test_a_public_deck_top_is_counted_by_identity_for_its_relative_seat() -> None:
    # v38 (OQ-145): per relative seat, a personal-card identity's column counts
    # its public copies on the deck top, as ``deck_pool`` counts (independent
    # review 2026-10-28: a depth hid a second copy and weighed the top card
    # least in the entity network); the other columns, and the other seats'
    # blocks, stay 0.
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=5)
    rival = state.players[1]
    first, second, third = (
        "player:1:starter:convincing_argument:0",
        "player:1:starter:dagger:0",
        "player:1:starter:convincing_argument:1",
    )
    hidden = tuple(
        card
        for card in (*rival.hand, *rival.deck)
        if card not in (first, second, third)
    )
    crafted = replace(
        rival,
        deck=(first, second, third, *hidden[:2]),
        hand=hidden[2:],
        hand_public=(),
        deck_public_top=(first, second, third),
    )
    state = replace(state, players=(state.players[0], crafted, *state.players[2:]))

    ids = {card_id: index for index, card_id in enumerate(PERSONAL_CARD_IDS)}
    for observer in range(4):
        encoded = encode_player_view(engine.observe(state, observer))
        for block in range(4):
            column = encoded[segment_slice(f"seat{block}_deck_public_top")]
            if (observer + block) % 4 != 1:
                assert not any(column)
                continue
            assert column[ids["convincing_argument"]] == 2  # two public copies
            assert column[ids["dagger"]] == 1
            assert sum(1 for value in column if value) == 2


def test_the_voice_and_the_card_turn_flags_are_encoded_by_relative_seat() -> None:
    # v38: the spaces each relative seat may not send its next Agent to (The
    # Voice), then per relative seat Infiltrate's turn marker and Recruitment
    # Mission's round marker.
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=5)
    barred = replace(
        state.players[2], voice_blocked_space_ids=("arrakeen", "heighliner")
    )
    flagged = replace(
        state.players[3], enemy_agents_ignored_turn=True, acquire_to_deck_top_round=True
    )
    state = replace(state, players=(*state.players[:2], barred, flagged))
    spaces = {space_id: index for index, space_id in enumerate(SPACE_IDS)}

    for observer in range(4):
        encoded = encode_player_view(engine.observe(state, observer))
        blocks = encoded[segment_slice("voice_blocks")]
        flags = encoded[segment_slice("card_turn_flags")]
        for seat in range(4):
            row = (seat - observer) % 4
            width = len(VOICE_BLOCK_SPACE_IDS)
            row_blocks = blocks[row * width : (row + 1) * width]
            expected = (
                {spaces["arrakeen"], spaces["heighliner"]} if seat == 2 else set()
            )
            assert {i for i, value in enumerate(row_blocks) if value} == expected
            assert all(value in (0, 1) for value in row_blocks)
            assert flags[row * 2 : row * 2 + 2] == ((1, 1) if seat == 3 else (0, 0))


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
            # v38: without Immortality (or the original game) no card is put
            # on a deck top, no space is barred and no turn flag is set.
            for name in _V38_SEGMENTS:
                assert not any(encoded[segment_slice(name)]), name
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
# v138 (2026-10-06 user ruling: no Intrigue play for no effect, FAQ p. 2)
# moves only promo_bloodlines_tech (2,908 -> 2,964 vectors): at decision 470
# seat 1's Insider Information option 1 ("ignore Influence requirements this
# turn") is no longer offered because no requirement is left unmet, so the
# random seat draws from a shorter list. A per-commit run of the branch
# (scratch) moves it at the gate commit 52007a8b and nowhere else; the other
# five pins hold.
# v139 (the general-rules comparison batch, 2026-10-07; observation still
# v30). A per-commit run of the batch (scratch, ``git archive`` exports,
# with the action traces compared) gives: 5654d7f8 (a Combat Intrigue pass
# right after a card play hands priority on without counting as a
# consecutive pass) moves all six games (base 3,144 -> 3,052 vectors, choam
# 2,708 -> 2,904, promo_bloodlines_tech 2,964 -> 3,004, everything 3,360 ->
# 2,988, draft 2,732 -> 2,812, scouts 3,424 -> 3,588). ec4e4db7 (a
# Reveal-turn Plot stays face up until its owner's Reveal turn ends) changes
# the vectors of base and everything with the same choices: their
# Manipulate stays face up longer. c80d719e (a lone participant's pass
# after playing ends Combat Intrigue) moves draft (2,812 -> 2,808).
# 82b9cddc (Conflict rewards paid one recipient at a time in rank order)
# changes all six: five keep every choice and legal-set size (a later
# recipient is now paid after the winner's choices, so the vectors in
# between differ), and scouts moves (3,588 -> 3,712 vectors). d70e7be2,
# aa22c8b7, 445353d5 (its deck sizes are not encoded), a73957bf, 184f923c
# and d3699046 move none of the six.
# v141 (2026-10-09; observation still v30): the Conflict-end Intrigue window
# opens on public facts (OQ-103: Immortality, at least three units in the
# Conflict, an Intrigue card held, a Harvest Cells copy not yet public), so
# a seat that can only decline gets the window too. Only "everything"
# (Immortality on) moves (2,988 -> 3,620 vectors): at decision 264, the end
# of round 4's Conflict, seat 3 gets a decline-only window and its random
# seat draws for it. With the previous window rule patched back in (open
# only for a playable card, close after a play unless another copy is
# playable) a scratch run reproduces the old pin exactly; the Earn Any
# Alliance timing of the same change moves none of the six.
# v142, second change (user ruling 2026-10-10, OQ-027 (d)): Imperial
# Privilege's card draw is its own ``resolve_board_effect(cards)`` icon, so
# the legal list right after an Imperial Privilege placement holds one more
# action and the random seat draws from it. Four games move, each at its
# first Imperial Privilege visit: choam at decision 497 (round 8, seat 1;
# 2,904 -> 2,816 vectors), draft at 556 (round 9, seat 3; 2,808 -> 2,864),
# promo_bloodlines_tech at 517 (round 8, seat 2; 3,004 -> 3,172) and scouts
# at 340 (round 5, seat 3; 3,712 -> 3,368). With the bundled recall-and-draw
# patched back in (a scratch checkout of the previous commit) all six games
# reproduce the pins above exactly; base and everything never visit Imperial
# Privilege. ``adapters/observation_encoding.py`` and ``core/observation.py``
# are unchanged.
# v142, third change (user ruling 2026-10-10, OQ-106): the draw Urgent
# Shigawire adds to a boosted Bene Gesserit card's Agent box is its own
# ``resolve_agent_card_effect(cards)`` step, so the legal list right after a
# boosted placement holds one more action. Only "everything" moves: at
# decision 631 (round 8, seat 1, after Weirding Woman's boosted placement on
# Arrakeen) the random seat draws from 6 actions instead of 5 (3,620 ->
# 3,640 vectors). With the placement drawing the card again (a scratch copy
# of the previous commit's source) all six games reproduce the pins above
# exactly.
# v142, fourth change (OQ-106): Cunning's and Insider Information's draw is
# its own ``resolve_intrigue_rewards`` step when the owner resolves the
# trash first. Only promo_bloodlines_tech moves: at decision 547 (round 8,
# seat 2, right after Insider Information's trash) the draw is the seat's
# one legal action, where the trash had drawn already and the random seat
# chose among 6 (3,172 -> 3,164 vectors). With the
# trash drawing again (a scratch copy of the previous commit's source) all
# six games reproduce the pins above exactly.
# v142, fifth change (OQ-106): a draw another printed effect triggers in
# the seat's own turn waits as its own ``draw_owed_intrigue`` step. Two
# games move: everything at decision 216 (round 4, seat 2, right after its
# research direction c3r5 moved its Tleilaxu token onto the track's
# Intrigue space), where the random seat draws the card from 4 actions
# instead of deploying (3,640 -> 3,544 vectors), and scouts at decision 812
# (round 10, seat 3, right after its Reveal bought Overthrow), where the
# draw is the seat's one legal action (3,368 -> 3,372 vectors). With the
# triggers drawing again (a scratch copy of the previous commit's source)
# all six games reproduce the pins above exactly.
# v142, sixth change (OQ-106): a draw printed after one of an Arrakeen
# Scouts line's reward choices waits as the line's own
# ``scouts_rewards_first``. Only scouts moves: at decision 384 (round 6,
# seat 2, right after its Water Discipline trash) the draw is the seat's
# one legal action, where the trash had drawn already and seat 3 chose its
# line next (3,372 -> 3,552 vectors). The pause before a later auction
# winner's reward (the commit before) moves none of the six. With the trash
# drawing again (a scratch copy of the previous commit's source) all six
# games reproduce the pins above exactly.
# v142, seventh change (user decision 2026-10-10, OQ-106 "가 로 가자"): the
# Bene Gesserit Influence 4 card, Imperial Birthright, Overthrow's acquire
# box and CHOAM Transports' card are the owner's only action right after
# their trigger. Two games move, each at a Faction icon that reached Bene
# Gesserit 4 in an Agent turn: everything at decision 697 (round 9, seat 3),
# where the random seat had flipped a Tech tile from 3 actions before the
# draw (same 3,544 vectors, other order), and scouts at decision 702 (round
# 9, seat 0), where it drew from 3 actions (3,552 -> 3,532 vectors). With
# the draws free again and CHOAM Transports drawn by the post-step hook (a
# scratch copy of this change's source) all six games reproduce the pins
# above exactly.
# Re-pinned 2026-10-12 for observation v31 and codec v143 (both grafted
# Agent boxes offered from the start, docs/graft-boxes-plan.md): the open
# Agent turn's two boxes are appended as a 4-column ``agent_boxes`` segment.
# For all six games each vector cut back to the v30 layout (its last 4
# columns dropped) reproduces the v30 digests above exactly with the same
# vector counts (base e176cf70, choam 441cc626, draft 274b33e5, everything
# 4879457a, promo_bloodlines_tech 92815f46, scouts 6bb338f6), so no
# trajectory moved. The new columns are nonzero in 1,880 (base), 1,760
# (choam), 1,748 (draft), 2,208 (everything), 2,084 (promo_bloodlines_tech)
# and 2,036 (scouts) vectors: every open Agent turn names its placed card.
# v32 (OQ-010 ruling 6): the same games with each vector cut to its first
# 4,537 columns (the four deck-pool segments dropped) reproduce the v31
# digests exactly with the same vector counts (base d96a5baa, choam 2f49afd3,
# draft e8e7e54f, everything a63b5a28, promo_bloodlines_tech 2a4e10aa, scouts
# f6b5fc5e), so no older column and no trajectory moved. The new columns are
# nonzero in every vector: every seat always holds a deck or a hand.
# v146: optional Agent-turn effects offer no refusal (OQ-095 (2),
# 2026-10-14); observation still v32. All six games move at their first
# optional effect of an Agent turn, where the random seat now draws from a
# list without the refusal row: base at decision 11 (round 1, seat 3,
# Desert Tactics' trash; 3,052 -> 2,692 vectors), choam at 30 (round 1,
# seat 2, Desert Tactics; 2,816 -> 3,440), scouts at 30 (round 1, seat 2,
# Desert Tactics; 3,532 -> 3,080), promo_bloodlines_tech at 5 (round 1,
# seat 1, Gather Support's unaffordable Sardaukar Commander and Acquire
# Tech; 3,164 -> 3,580), everything at 1 (round 1, seat 0, the same two at
# Gather Support; 3,544 -> 3,800) and draft at 70 (round 2, seat 0, a
# Signet Ring step at Hagga Basin; 2,864 -> 2,972). A scratch export of the
# previous commit's source (``git archive``) reproduces all six pins above
# exactly on the same games; ``adapters/observation_encoding.py`` and
# ``core/observation.py`` are unchanged.
# Re-pinned the same day (codec v146 still, observation v32): Lady Jessica's
# Other Memories offers no refusal either and lapses at the turn end (OQ-095
# (2), user ruling 2026-10-14 "기존대로 턴 중에 원할 때"). Five games move at
# their first Other Memories decision, where the random seat now draws from
# a list without ``decline_other_memories``: base at decision 111 (round 2,
# seat 3; 2,692 -> 2,400 vectors), choam at 137 (round 3, seat 3; 3,440 ->
# 2,880), promo_bloodlines_tech at 64 (round 2, seat 3; 3,580 -> 3,232),
# everything at 351 (round 5, seat 3; 3,800 -> 3,556) and scouts at 510
# (round 8, seat 3; 3,080 -> 2,872). Each game's decision trace (round,
# seat, offered action ids, choice) before that point equals the previous
# pins' trace exactly; draft meets no Other Memories decision and keeps its
# pin. For a while that day the engine also asked Litany Against Fear and
# Withdrawn first and alone at the turn's start, beside a refusal of its
# own, which pinned promo_bloodlines_tech at ccc02716 / 3,388; the window was
# taken out of the engine again (whether it opened told the other seats
# such a card was held). Against that pin the trace is identical through
# decision 587; at 588 (round 8, seat 3) Litany stands beside
# ``reveal_turn`` instead of the refusal and the random seat plays it
# either way, and the first different choice is at 749 (round 10, seat 3),
# where Litany comes with the turn's usual choices and the seat places an
# Agent. The other five games never met the window and keep their pins.
# Re-pinned for codec v147 (observation still v32): a Reveal choice no
# longer opens its own frame; every pending choice is a row of the Reveal
# frame beside the purchases, an optional one without its refusal (OQ-095
# (7) addition, user ruling 2026-10-14). A scratch export of the previous
# commit's source (fc8d65ba, ``git archive``) reproduces all six previous
# pins exactly on the same games, and each game's decision trace (round,
# seat, frame kind, offered action ids, choice) equals that export's up to
# its first Reveal choice, where the random seat now draws from the Reveal
# frame's list: base at decision 254 (round 4, seat 0, Spacing Guild's
# Favor; 2,400 -> 2,868 vectors), choam at 315 (round 4, seat 3, Captured
# Mentat; 2,880 -> 2,964), promo_bloodlines_tech at 521 (round 7, seat 1,
# Spy Network; 3,232 -> 3,160), everything at 369 (round 5, seat 2, Shadout
# Mapes; 3,556 -> 3,580), draft at 224 (round 4, seat 0, a plain Reveal Spy;
# 2,972 -> 2,728) and scouts at 459 (round 7, seat 3, Captured Mentat;
# 2,872 -> 3,028). ``adapters/observation_encoding.py`` and
# ``core/observation.py`` are unchanged.
# Re-pinned for codec v149 (cleanup-2b, observation still v32): a research
# space's bonus choice raised inside its owner's own turn waits on the turn's
# frame as rows instead of opening a window with a refusal (composed-effects
# plan, rule decision 2; OQ-095 (2)). A scratch export of the previous
# commit's source (93c8446b, ``git archive``) reproduces the ``everything``
# pin exactly, and its decision trace equals this one through decision 830;
# at 831 (round 10, seat 1, c6r6 after Breakthrough) the Influence rows
# stand in the Agent-turn effect frame beside the box's other effects and
# the random seat resolves a card draw first (3,580 vectors either way).
# The other five games meet no in-turn research bonus and keep their pins.
# Re-pinned again for cleanup-2b's optional trash (observation still v32):
# a "[trash a card]" icon raised in its owner's own turn waits on the turn as
# rows instead of opening a window with a refusal. An export of the previous
# commit (72d2ad95) reproduces the two pins it moves, and each trace equals
# this one until the first in-turn trash window: ``everything`` at decision
# 219 (round 4, seat 0, the random seat declined there and now resolves a
# board icon first; 3,580 -> 3,568 vectors), ``promo_bloodlines_tech`` at 545
# (round 8, seat 1, the same trash taken from the turn's list; 3,160 either
# way). The other four games meet no in-turn trash.
# Re-pinned once more for cleanup-2b's research space icons (rule decision 5,
# OQ-027): a research space's two icons, and c7r3's two rewards, are each
# their own step in the owner's order. An export of the previous commit
# (a1b692f0) reproduces the ``everything`` pin, and its trace equals this one
# through decision 331; at 332 (round 5, seat 1, c3r3 reached in the Agent
# turn) the specimen waits as a row beside the trash and the random seat
# deploys first (3,568 -> 3,484 vectors). The other five games meet no
# research space.
# Re-pinned for the Conflict-end order (user decision 2026-10-18, codec v149):
# the Conflict's troops go back to the supply before the Conflict-end
# windows. An export of the previous commit (7ae17717) reproduces the old
# ``everything`` pin, and its decision trace equals this one at every
# decision (3,484 vectors either way); only the views at its three
# Conflict-end windows (decisions 577, 648 and 649, all declines) differ, the
# troops already in the supply there. The other five games open no window.
# Re-pinned once more for OQ-108 and OQ-109 (user decision 2026-10-18): the
# winner takes the Conflict card before the troops go back. An export of the
# previous commit (02886db5) reproduces the pin just above, and the decision
# trace is again equal at every decision (3,484 vectors); the views at the
# same three windows now show the Conflict card already won.
# Re-pinned for observation v33 and codec v150 (stage B1, OQ-111): the Agent
# turn is a card pick and then a space pick, and the seat deciding the space
# sees its picked card in the appended ``private_agent_card_pick`` and
# ``..._graft`` columns. A random seat now draws its card from the picks and
# then its space from the picked card's placements, so every game's
# trajectory moves at its first Agent turn (decision 0 or 1) and no earlier
# pin can be reproduced from these games. What was checked instead: the
# columns are nonzero only in the picking seat's own vector at its space
# pick (base 65 vectors, choam 55, promo_bloodlines_tech 55, everything 62,
# draft 64, scouts 59; none in another seat's), and the encoder files differ
# from the v32 ones only by the appended segments.
# Re-pinned for stage B2 (OQ-112, codec v150, observation v33): a Conflict
# reward recipient resolves its reward icon by icon in a window, and a
# completed Contract's reward waits in one too. An export of the previous
# commit (bc0d0a7f) gives each game's per-decision trace (the four views'
# digest, the frame on top, the action taken) equal to this one up to the
# first window, round 1's first recipient (base at decision 93, choam 68,
# promo_bloodlines_tech 55, everything 79, draft 48, scouts 68), which the
# older engine paid inside the step before; there the random seat draws over
# the window's rows and the games part.
# Re-pinned for stage B3a (OQ-111, observation v33, codec v150): the
# Agent-effect frame offers a waiting effect as an effect row and then its
# target rows, and the seat picking the target sees the effect it picked in
# the appended ``private_effect_pick_*`` columns. A random seat now draws over
# the rows (fewer than the whole actions they stand for, and a targeted
# effect takes two decisions), so every game's trajectory moves at its first
# Agent-effect frame offering several effects. An export of the previous
# commit (1bea95ad, ``git archive``) reproduces the six old pins exactly
# (2,768, 2,776, 2,984, 3,796, 2,516 and 2,564 vectors). What was checked
# instead, per decision: the digest of the four views without the appended
# columns, the frame on top, the deciding seat and the number of offered
# actions equal the old export's at each of the first 18 decisions (base), 7
# (choam), 35 (promo_bloodlines_tech), 29 (everything), 11 (draft) and 7
# (scouts), where the list is shorter (base: 10 whole actions, 6 rows); and
# the appended columns are nonzero only in the picking seat's own vector
# while its pick is pending (base 2 vectors, choam 10, promo_bloodlines_tech
# 35, everything 28, draft 6, scouts 10; none in another seat's).
# Re-pinned for stage B3b-1 (OQ-112 (4), codec v150): a Contract completed in
# its owner's own turn leaves its icons as rows of that turn instead of a
# reward window. An export of the previous commit (7a29d82f) gives each
# game's per-decision trace (the four views' digest, the frame on top, the
# deciding seat, the number of offered actions) equal to this one up to the
# decision right after the first such completion (choam at decision 384,
# everything 392, scouts 300), where the older engine stood in the window and
# this one in the turn's frame with the rows beside its other effects; base,
# promo_bloodlines_tech and draft complete no Contract and stay pinned.
# Re-pinned for stage B3b-2 (OQ-111, codec v150): the Reveal frame offers its
# purchases, its revealed cards' choices and its leader, Skill and Tech rows
# effect first (one ``acquire`` row per market, then the card). An export of
# the previous commit (8d77f452) gives each game's per-decision trace equal
# to this one up to the first Reveal decision offering several purchases
# (base at decision 62, choam 59, promo_bloodlines_tech 11, everything 69,
# draft 26, scouts 59), where the random seat draws over the fewer effect
# rows and the games part.
# Re-pinned for stage B3c-1 (OQ-111, codec v150): a card is played effect
# first -- the window's ``play`` row, then the card, then its option. An
# export of the previous commit (000d5212) gives each game's per-decision trace
# equal to this one up to the first Intrigue play (base at decision 28, choam
# 39, everything 59, draft 35, scouts 39: the decision after the random seat's
# play, now the card step) or the first Agent-effect frame offering a Plot
# among several effects (promo_bloodlines_tech at 264, fewer rows).
# Re-pinned for the B3c-1 review (v33): the seat's own pick shows the targets
# picked so far, 149 columns appended. The same games: each digest over the
# first 5,440 columns of every vector is the previous pin, and the new
# columns are set only while a seat holds a picked target (12 to 18 views a
# game). Then the second picked Faction's 4 columns: each digest over the
# first 5,589 columns is the pin before them, and no game here picks two
# Factions before an exchange's recipient.
# Re-pinned for stage B3c-2b (OQ-022 2026-10-20 note): an optional trash on
# the owner's turn is its trash icon's row, then the card. An export of the
# previous commit (1e621400) gives each game's per-decision trace equal to
# this one up to the first in-turn optional trash (everything at decision
# 505, a research space's; promo_bloodlines_tech at 317, Spy Drones'), where
# the random seat draws over the fewer rows and the games part; the other
# four games offer none and stay pinned.
# Re-pinned for stage B3d-2a (D-1 (가)): a window opened for one effect
# offers its own effect by its target rows, and a recall first beside a
# window's Spy is one effect row. An export of the previous commit
# (92644b59) gives promo_bloodlines_tech's per-decision trace equal to this
# one up to decision 774, a Spy placement window with the supply empty (a
# refusal and three recalls before, a refusal and the recall's effect row
# now), where the random seat draws over the fewer rows and the game parts;
# the other five games keep every row count and stay pinned. Then Long Live
# the Fighters' picked personal card, 139 columns appended (the B3d-2a
# review): each digest over the first 5,593 columns of every vector is the
# pin before them (promo_bloodlines_tech's B3d-2a pin
# 1a462433...4430cc65), and no game here sets them.
# Re-pinned for codec v152 (OQ-131, engine audit 2026-10-22 G4): a seat that
# cannot join a Scouts mission is asked, with the pass alone. An export of the
# commit before it (10cce681) gives the scouts game's per-decision trace equal
# to this one up to decision 84, a mission window (seat 3 with two rows before,
# seat 2 with the pass alone now), where the random seats draw again and the
# game parts (88611727...bfe48af30, 3,172 then); the other five games ask no
# such seat and stay pinned. Then Political Equilibrium asks every seat (the
# same OQ-131, user decision 2026-10-25): the previous commit's trace equals
# this one up to decision 313, where seat 1 now answers the event's one-row
# window before its turn (f062b00f...aff7c8c7, 3,404 then).
# Re-pinned for codec v154 (OQ-113 (C), user ruling 2026-10-24: a cost-free
# Intrigue line is played even when it fizzles). A trace of master
# 7303f91d's game equals this one up to decision 630, round 8, where seat 3
# is now offered False Orders with no Spy to move and no post to fill (it
# played its Agent; "You may play this Intrigue card even if no opponents'
# Spies are on the space where you sent an Agent this turn." [FAQ p. 2]),
# the random seat plays it and the everything game parts; the other five
# games meet no such play and stay pinned.
_GOLDEN_DIGESTS = {
    "base": ("9ac09f6db7d71edf89ee0d4abb58e32f0a23caad428000c1308138e00863173f", 2780),
    "choam": ("d43306c8745984b856879a1cc9abc57089348efc02b7d9dde0a3bdadcc55f1dc", 2668),
    "promo_bloodlines_tech": (
        "4457098015b02adbc4401427baa9b6c52cafa4ceaa01347f34566811a71f00d5",
        3300,
    ),
    "everything": (
        "93f8a0d1562aa3d9bf0caed24013fcc90dc0f393ed6df8c77586ebd3fccc2466",
        3556,
    ),
    "draft": ("0df15d5397e3649c558e48a2787907852d0213aa1815abd65126c95bc9ca39c2", 2788),
    "scouts": (
        "c37a06f8d12e811c096afc519c67c5dd9a8c39e258ec88a695ac7bd86fe729a8",
        3136,
    ),
}
_GOLDEN_CONFIGS: dict[str, dict[str, Any]] = {
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
            hasher.update(_pinned_columns(vector))
            encoded += 1
        actions = engine.legal_actions(state, decision.owner)
        action = agents[decision.owner].choose_action(
            engine.observe(state, decision.owner), actions
        )
        state = engine.apply(state, action, legal_actions=actions).state
    for seat in range(4):
        vector = encode_player_view(engine.observe(state, seat))
        hasher.update(_pinned_columns(vector))
        encoded += 1
    return hasher.hexdigest(), encoded


def _pinned_columns(vector: tuple[int, ...]) -> bytes:
    """The v33 columns the golden digests pin. v34 appended only the
    base-game flag (the base-game axis), 0 in every Uprising game: an
    Uprising observation is the v33 one with a 0 after it. v35 (stage P2a)
    grew segments at their end (``growth_since_v34``) and appended the Mentat,
    all 0 in every Uprising game: each segment's older columns, in order,
    are the v34 vector."""

    import numpy as np

    older: list[int] = []
    for segment in OBSERVATION_SEGMENTS:
        part = vector[segment.offset : segment.offset + segment.length]
        if segment.name in ("base_game", *NEW_SEGMENTS):
            assert not any(part)
            continue
        grown = growth_since_v34(segment)
        # v39's Intrigue deck size (``global_scalars``) is public in every
        # game; every other grown column is 0 in an Uprising game.
        if segment.name not in NONZERO_GROWTH:
            assert not any(part[segment.length - grown :])
        older.extend(part[: segment.length - grown])
    assert len(older) == _V33_SIZE
    return np.asarray(older, dtype=np.int32).tobytes()


_V33_SIZE = 5_732


@pytest.mark.parametrize("name", sorted(_GOLDEN_DIGESTS))
def test_encoding_matches_the_pinned_golden_digest(name: str) -> None:
    assert (
        _encoding_digest(RulesetConfig(**_GOLDEN_CONFIGS[name]), 91)
        == (_GOLDEN_DIGESTS[name])
    )


def test_the_base_game_flag_names_the_original_game() -> None:
    # Plan 4.2 item 8: one layout for both base games, and a column that
    # tells them apart where cards and spaces do not.
    view = observe_state(UprisingRulesEngine().reset(RulesetConfig(), 4), 0)
    assert view.base_game is BaseGame.UPRISING
    flag = segment_slice("base_game")
    assert encode_player_view(view)[flag] == (0,)
    imperium = encode_player_view(replace(view, base_game=BaseGame.IMPERIUM))
    assert imperium[flag] == (1,)
    assert imperium[: flag.start] == encode_player_view(view)[: flag.start]


# -- observation v39 (stage P4a, Rise of Ix; plan 17.8) -----------------------
def _digest(rows: Any) -> str:
    import hashlib

    return hashlib.sha256("\n".join(rows).encode()).hexdigest()


# Observation v38 as the v38 encoder printed it (7b4c65be, 2026-10-29, before
# v39): SHA-256 of its segments' "name:length" rows, and of each identity
# universe's ids in order, by universe (count, digest).
_V38_LAYOUT = "6ded77400dca4b86079a8c23a1864ab4190fce01afe7c6e0da05b229a7ceb1f4"
_V38_UNIVERSES: dict[str, tuple[tuple[str, ...], int, str]] = {
    "personal": (
        PERSONAL_CARD_IDS,
        188,
        "d8ad000d1a0e5c4f9169a4fc6a55129b50687d5b458795ac66356c27fe2df9b7",
    ),
    "intrigue": (
        INTRIGUE_IDS,
        124,
        "278d9eb84028029cacbe27252ae4360b3e5002562426823f5fca3263ee549e74",
    ),
    "conflict": (
        CONFLICT_IDS,
        37,
        "fde60a5f8a62682df2830713fb1de72ee72c7f49f5bf380e15cf121a09824d07",
    ),
    "battle": (
        BATTLE_CARD_IDS,
        24,
        "dd3582d1240ffa08c801715f9ed10d23a6e5a895ac0f6272ec45f89238164917",
    ),
    "leader": (
        LEADER_IDS,
        26,
        "e96b808e3c4d40eb016f11f4f774987d1c954be4e7a769216e8d8ed81238d3b5",
    ),
    "space": (
        SPACE_IDS,
        42,
        "618425161cf05b73bd8775babf8dbd477cc17748121e8b2659d04f85eb1e9fb2",
    ),
    "control": (
        CONTROL_SPACE_IDS,
        4,
        "1a8d4a855a45b6200ace9c50b11fb9085201ee220409c81248d504696289a54e",
    ),
    "contract": (
        CONTRACT_IDS,
        28,
        "17a07122fe0dfe5dab7e58bce0c13cebe41365431ee55d46015a42919b455121",
    ),
    "reserve": (
        RESERVE_STACK_IDS,
        5,
        "7fb7993eee26e320deb2f7565f1c1cec1dd932f43e2bbd4aeb7191304cc60615",
    ),
    "maker": (
        MAKER_SPACE_IDS,
        6,
        "c8b24403a3cd04895018db6fa878f377866823cb53447b3bd6be44de756bb3dd",
    ),
    "tech": (
        TECH_IDS,
        18,
        "4217de9bdf2edebfd82ad6aa03fb4b71f236978d743f6d965f18cbdb479c6858",
    ),
}


def test_every_v38_segment_keeps_its_name_and_the_meaning_of_its_columns() -> None:
    # Plan 17.8: v39 appends Rise of Ix's ids at the end of each universe and
    # its segments at the end of the layout, so each v38 segment is in v39 by
    # name and its old columns, at the same offsets inside it, hold the same
    # identities (checkpoints migrate by (segment, offset), ``growth_in_v39``).
    layout = v38_layout()
    assert len(layout) == V38_SEGMENTS
    assert layout[-1][1] + layout[-1][2] == V38_SIZE
    assert _digest(f"{name}:{length}" for name, _, length in layout) == _V38_LAYOUT
    for name, (ids, count, pinned) in _V38_UNIVERSES.items():
        assert _digest(ids[:count]) == pinned, name
    # A segment that is a relative seat x space matrix keeps its 42 spaces
    # (review item 5); no other segment multiplies a universe that grew.
    assert len(VOICE_BLOCK_SPACE_IDS) == 42
    voice = segment_slice("voice_blocks")
    assert voice.stop - voice.start == 4 * len(VOICE_BLOCK_SPACE_IDS)
    blocks = segment_slice("voice_blocks_ix")
    assert blocks.stop - blocks.start == 4 * len(IX_SPACE_IDS)
    assert IX_SPACE_IDS == (
        "dreadnought",
        "tech_negotiation",
        "interstellar_shipping",
        "smuggling",
    )
    # v39 appends them to the space universe, after ``voice_blocks``' 42.
    assert SPACE_IDS == (*VOICE_BLOCK_SPACE_IDS, *IX_SPACE_IDS)


def _v39_games() -> dict[str, dict[str, Any]]:
    return {
        "uprising_all": {
            "choam_module": True,
            "promo_cards": True,
            "bloodlines": True,
            "tech_module": True,
            "immortality": True,
        },
        "original": {"base_game": BaseGame.IMPERIUM},
    }


# SHA-256 over the int32 v38 vectors of every observer at each of the first
# 400 player decisions of one random game (seed 13, RandomAgent seeds 7013 +
# seat), computed with the v38 encoder before v39 (7b4c65be): the v39
# encoder's v38 columns must reproduce them. A digest that moves while the
# v39 columns stay right means the engine plays the seed differently (re-pin
# after checking, as for the golden digests above).
_V38_GAME_DIGESTS = {
    "uprising_all": (
        "207cf35b6a679151723c6bdc7f64daf26f5ef7f936ac4b84d688d4ad3168f675",
        1600,
    ),
    "original": (
        "e1502318bf9b80c03f6ce18e9235e3cdfec4686149d729f8845b2b25efa8ea73",
        1600,
    ),
}


@pytest.mark.parametrize("name", sorted(_V38_GAME_DIGESTS))
def test_a_fixed_game_encodes_every_old_column_as_v38_did(name: str) -> None:
    import hashlib

    import numpy as np

    from dune_imperium.agents import RandomAgent

    engine = UprisingRulesEngine()
    agents = [RandomAgent(seed=7_000 + 13 + seat) for seat in range(4)]
    state = engine.reset(RulesetConfig(**_v39_games()[name]), 13)
    chance = ChanceResolver(seed=13)
    hasher = hashlib.sha256()
    count = decisions = 0
    deck_size = segment_slice("global_scalars").start + 12
    while state.phase is not GamePhase.FINISHED and decisions < 400:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        for seat in range(4):
            vector = encode_player_view(engine.observe(state, seat))
            hasher.update(np.asarray(v38_columns(vector), dtype=np.int32).tobytes())
            count += 1
            # Without Rise of Ix every v39 column is 0 but the public
            # Intrigue deck size.
            assert vector[deck_size] == len(state.intrigue_deck)
            for segment in OBSERVATION_SEGMENTS:
                if segment.name in V39_NEW_SEGMENTS:
                    part = vector[segment.offset : segment.offset + segment.length]
                    assert not any(part), segment.name
        actions = engine.legal_actions(state, decision.owner)
        action = agents[decision.owner].choose_action(
            engine.observe(state, decision.owner), actions
        )
        state = engine.apply(state, action, legal_actions=actions).state
        decisions += 1
    assert (hasher.hexdigest(), count) == _V38_GAME_DIGESTS[name]


def _ix_state() -> GameState:
    """An original game's first turn under the Rise of Ix option (its setup
    is a later stage's; the observation is what is checked here)."""

    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(base_game=BaseGame.IMPERIUM), 5)
    chance = ChanceResolver(seed=5)
    while state.phase is not GamePhase.PLAYER_TURNS:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        action = engine.legal_actions(state, decision.owner)[0]
        state = engine.apply(state, action).state
    return replace(state, config=replace(state.config, rise_of_ix=True))


def test_the_intrigue_deck_size_is_the_last_global_scalar() -> None:
    # Plan 17.8 review item 6: public, as every shared deck's count.
    state = _ix_state()
    for observer in range(4):
        scalars = encode_player_view(observe_state(state, observer))[
            segment_slice("global_scalars")
        ]
        assert scalars[12] == len(state.intrigue_deck) == 40


def test_the_rise_of_ix_seat_columns_are_public_by_relative_seat() -> None:
    state = _ix_state()
    players = list(state.players)
    one = players[1]
    players[1] = replace(
        one,
        dreadnoughts_supply=1,
        dreadnoughts_conflict=1,
        freighter_space=2,
        troops_supply=one.troops_supply - 2,
        negotiators=2,
        snooper_faction_ids=("spacing_guild", "fremen"),
        set_aside_returned_turn=True,
        turns_finished_round=1,
        strategic_push_solari=2,
    )
    two = players[2]
    pool_before = observe_state(state, 0).players[2].deck_pool
    players[2] = replace(two, hand=two.hand[1:], set_aside_card_id=two.hand[0])
    players[3] = replace(
        players[3], voice_blocked_space_ids=("arrakeen", "smuggling")
    )
    state = replace(
        state,
        players=tuple(players),
        dreadnought_control=(("carthag", 1, True), ("imperial_basin", 3, False)),
    )
    # Plan 17.8 review item 1: the face-down card stays in the public pool.
    assert observe_state(state, 0).players[2].deck_pool == pool_before

    for observer in range(4):
        encoded = encode_player_view(observe_state(state, observer))
        units = [
            encoded[segment_slice(f"seat{(player - observer) % 4}_units")]
            for player in range(4)
        ]
        ix = [
            encoded[segment_slice(f"seat{(player - observer) % 4}_ix")]
            for player in range(4)
        ]
        relative = [(player - observer) % 4 + 1 for player in range(4)]

        assert units[1] == (1, 0, 1)
        # Freighter, Negotiators, the Snooper tokens' space by Faction
        # (emperor, spacing_guild, bene_gesserit, fremen), the set-aside
        # card, its return this turn, the turns finished this round, the
        # Solari pledged with Strategic Push.
        assert ix[1] == (2, 2, 0, 2, 0, 2, 0, 1, 1, 2)
        assert ix[2] == (0, 0, 0, 0, 0, 0, 1, 0, 0, 0)
        for other in (0, 3):
            assert not any(units[other]) and not any(ix[other])
        control = encoded[segment_slice("dreadnought_control")]
        expected = [0] * 8
        expected[2 * CONTROL_SPACE_IDS.index("carthag") : 8] = [relative[1], 1]
        expected[2 * CONTROL_SPACE_IDS.index("imperial_basin")] = relative[3]
        assert control == tuple(expected)
        blocks = encoded[segment_slice("voice_blocks_ix")]
        row = (3 - observer) % 4
        assert {index for index, value in enumerate(blocks) if value} == {
            row * 4 + IX_SPACE_IDS.index("smuggling")
        }
        old = encoded[segment_slice("voice_blocks")]
        assert {index for index, value in enumerate(old) if value} == {
            row * 42 + SPACE_IDS.index("arrakeen")
        }
        assert encoded[segment_slice("ix_flags")] == (1,)
        # The set-aside card's identity is its owner's alone.
        aside = encoded[segment_slice("private_set_aside")]
        if observer == 2:
            card = personal_card_for_instance(two.hand[0]).card.card_id
            index = PERSONAL_CARD_IDS.index(card)
            assert {i for i, value in enumerate(aside) if value} == {index}
        else:
            assert not any(aside)
    plain = replace(_ix_state(), config=replace(state.config, rise_of_ix=False))
    flag = encode_player_view(observe_state(plain, 0))[segment_slice("ix_flags")]
    assert flag == (0,)


def test_the_intrigue_cards_a_seat_knows_are_its_own_columns() -> None:
    # docs/rules/rise-of-ix.md 13, plan 17.8 review items 2 and 6: seat 0
    # knows the deck's top card (Hundro), the two bottom cards it put there,
    # and one more that seat 2 has since drawn from the bottom.
    state = _ix_state()
    deck = state.intrigue_deck
    drawn = deck[-3]
    deck = (*deck[:-3], *deck[-2:])
    players = list(state.players)
    players[2] = replace(
        players[2], intrigue_cards=(*players[2].intrigue_cards, drawn)
    )
    players[0] = replace(
        players[0], known_intrigue_ids=(deck[0], deck[-1], deck[-2], drawn)
    )
    state = replace(state, players=tuple(players), intrigue_deck=deck)
    ids = {card: index for index, card in enumerate(INTRIGUE_IDS)}

    def identity(card: str) -> int:
        return ids[card.split(":")[1]]

    private = observe_state(state, 0).private
    assert private is not None
    assert private.known_intrigue_top == deck[0]
    # By depth from the bottom; the top card is the deepest.
    assert private.known_intrigue_bottom == (
        (0, deck[-1]),
        (1, deck[-2]),
        (len(deck) - 1, deck[0]),
    )
    assert private.known_intrigue_held == ((2, drawn),)
    known = known_card_seats(state)
    assert known[deck[0]] == known[deck[-1]] == frozenset({0})
    assert known[drawn] == frozenset({0, 2})
    assert known[deck[5]] == frozenset()

    for observer in range(4):
        encoded = encode_player_view(observe_state(state, observer))
        top = encoded[segment_slice("private_intrigue_top")]
        bottom = encoded[segment_slice("private_intrigue_bottom")]
        held = [
            encoded[segment_slice(f"private_known_intrigue_seat{seat}")]
            for seat in range(1, 4)
        ]
        if observer != 0:
            assert not any(top) and not any(bottom)
            assert not any(column for zone in held for column in zone)
            continue
        assert {i for i, value in enumerate(top) if value} == {identity(deck[0])}
        assert bottom == (
            identity(deck[-1]) + 1,
            identity(deck[-2]) + 1,
            *(0,) * 6,
        )
        # Seat 2 is relative seat 2 of seat 0.
        assert not any(held[0]) and not any(held[2])
        assert {i for i, value in enumerate(held[1]) if value} == {identity(drawn)}


def test_ix_pending_is_the_open_decision_of_its_own_seat() -> None:
    # Plan 17.8 review item 4: the Shipping rewards still owed, the open
    # Acquire Tech's discount and payment, and the Negotiators it may return
    # -- counted from the state, not the context (Codex review of 82b2bf2e:
    # the stale 3 written here is not what the seat holds).
    state = _ix_state()
    frame = state.decision_stack[-1]
    assert isinstance(frame.decision, PlayerDecision)
    owner = frame.decision.owner
    context = tuple(
        sorted(
            (
                *frame.context,
                (SHIPPING_REWARDS_KEY, "1,3"),
                (TECH_DISCOUNT_KEY, 2),
                (TECH_PAYMENT_KEY, "solari"),
                (NEGOTIATORS_RETURNABLE_KEY, 3),
            )
        )
    )
    state = replace(
        state,
        decision_stack=(*state.decision_stack[:-1], replace(frame, context=context)),
    )
    plain = replace(state, config=replace(state.config, rise_of_ix=False))
    seats = list(state.players)
    seats[owner] = replace(
        seats[owner],
        negotiators=1,
        troops_supply=seats[owner].troops_supply - 1,
    )
    state = replace(state, players=tuple(seats), tech_stacks=(("flagship",),))
    for observer in range(4):
        pending = encode_player_view(observe_state(state, observer))[
            segment_slice("ix_pending")
        ]
        expected = (1, 0, 1, 2, 0, 1, 1) if observer == owner else (0,) * 7
        assert pending == expected
    assert not any(
        encode_player_view(observe_state(plain, owner))[segment_slice("ix_pending")]
    )


def test_v39_reserves_the_rise_of_ix_frame_kinds_after_every_other() -> None:
    # Plan 17.8: the decisions of stages P4b to P4e no older frame holds
    # (docs/rules/rise-of-ix.md 14) take their kinds now, at the end, so the
    # kind index ``global_scalars`` holds moves for no older kind and no
    # later stage needs another observation version.
    kinds = tuple(FrameKind)
    assert kinds[-len(IX_FRAME_KINDS) :] == IX_FRAME_KINDS
    assert kinds[-len(IX_FRAME_KINDS) - 1] is FrameKind.MASTERSTROKE_SETUP
    # No engine path opens them yet, but the ones a stage has opened since:
    # none else has legal-action providers. Stage P4b-1b opens the winner's
    # dreadnought choice (docs/rules/rise-of-ix.md 6, OQ-121 ruling 6 (1)); stage
    # P4c-2c opens Sonic Snoopers' pick of Intrigue cards for the deck's bottom;
    # P4c-3 opens the Freighter outside its owner's turn and a recall's rewards
    # (docs/rules/rise-of-ix.md 5); P4d opens the Unload box outside its
    # owner's turn (docs/rules/rise-of-ix.md 7); P4e opens Ilesa Ecaz's Round
    # Start set-aside and Tessia Vernius' first Snooper reward outside her
    # turn (rise-of-ix.md 10).
    opened = {
        FrameKind.DREADNOUGHT_CONTROL_CHOICE,
        FrameKind.INTRIGUE_BOTTOM_PICK,
        FrameKind.FREIGHTER_MOVE,
        FrameKind.SHIPPING_REWARD_ICONS,
        FrameKind.UNLOAD_ICONS,
        FrameKind.ROUND_START_SET_ASIDE,
        FrameKind.OPTIONAL_DISCARD,
    }
    assert not (set(IX_FRAME_KINDS) - opened) & set(LEGAL_ACTION_PROVIDERS)
    assert opened <= set(LEGAL_ACTION_PROVIDERS)
    # Each encodes as its index + 1, as every kind does.
    engine = UprisingRulesEngine()
    view = engine.observe(engine.reset(RulesetConfig(), seed=5), 0)
    for kind in IX_FRAME_KINDS:
        scalars = encode_player_view(replace(view, decision_kind=kind.value))[
            segment_slice("global_scalars")
        ]
        assert scalars[4] == kinds.index(kind) + 1
