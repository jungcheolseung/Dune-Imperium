"""Epic Game Mode on the original game with Rise of Ix (stage P4e).

docs/rules/rise-of-ix.md 11 (`[Rise of Ix p. 10]`): "12점까지. Conflict I을
쓰지 않고 무작위 II 다섯 장을 III 다섯 장 위에 놓는다 — 원판 + Ix의 III은 다섯
장(원판 4 + Economic Supremacy)이라 모두 쓴다. 좌석마다 Dune, the Desert Planet
하나를 Control the Spice로 바꾸고, 모두 Intrigue 1장을 뽑고(Hundro는 모두 뽑은
뒤 Intelligence), garrison troop 5로 시작한다. Uprising 위의
구현(epic-game-mode.md)을 다시 쓴다(계획 9절 9)."

The Uprising implementation it reuses is docs/rules/epic-game-mode.md: the
Intrigue card goes out from the First Player in seat order once every Leader
is known (section 7), Control the Spice and Economic Supremacy are section 6,
and Go to 11 with Epic runs from 0 to 12 (section 5, OQ-093). The mode is
Rise of Ix's, so the original game without Rise of Ix stays refused; Go to 11
needs Immortality, which the original game takes from stage P7.
"""

from collections import Counter
from dataclasses import replace
from functools import cache

import pytest
from tests.support.pauses import answer_pause
from tests.support.reward_windows import settle_reward_window

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents import HeuristicAgent
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.uprising.starting_cards import starting_card_for_instance
from dune_imperium.content.uprising.types import ConflictTier
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    Resources,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.action_shapes import Source
from dune_imperium.rules.combat import (
    apply_combat_reward_optional_payment,
    legal_combat_reward_optional_payment_actions,
    resolve_combat_rewards,
)
from dune_imperium.rules.effect_steps import steps_for
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.leader_draft import remaining_draft_pool
from dune_imperium.rules.pauses import pause_is_pending
from dune_imperium.rules.setup import (
    SetupResult,
    conflict_setup_decisions,
    create_draft_initial_state,
    create_initial_state,
)
from dune_imperium.simulation.invariants import check_observation_privacy
from dune_imperium.simulation.sweep import run_checked_game

IX = RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True)
IX_EPIC = replace(IX, epic_game=True)
IX_EPIC_DRAFT = replace(IX_EPIC, leader_draft=True)
# No Leader here pauses the setup (no Baron, no Hundro).
LEADERS = (
    "paul_atreides",
    "duke_leto_atreides",
    "glossu_rabban",
    "count_ilban_richese",
)
HUNDRO = "viscount_hundro_moritani"
BARON = "baron_vladimir_harkonnen"
# Seed 1 makes seat 3 the First Player, so Hundro at seat 2 draws last.
HUNDRO_LEADERS = (
    "glossu_rabban",
    "count_ilban_richese",
    HUNDRO,
    "earl_memnon_thorvald",
)


@cache
def _codec(config: RulesetConfig) -> ActionCodec:
    return ActionCodec(config)


class _Engine(UprisingRulesEngine):
    """Check every offered row, the setup-time ones included (a draft pick,
    the Intelligence keep, the Baron's Factions), through ``ActionCodec``."""

    def legal_actions(self, state: GameState, player: int) -> tuple[DomainAction, ...]:
        rows = super().legal_actions(state, player)
        codec = _codec(state.config)
        for row in rows:
            assert codec.decode(codec.encode(row), player) == row
        return rows


def _settle(engine: UprisingRulesEngine, state: GameState, seed: int = 3) -> GameState:
    chance = ChanceResolver(seed=seed)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    return state


def _card_ids(instance_ids: tuple[str, ...]) -> Counter[str]:
    return Counter(
        starting_card_for_instance(instance_id).card.card_id
        for instance_id in instance_ids
    )


def _outcome_values(setup: SetupResult, decision_id: str) -> tuple[str, ...]:
    return next(
        outcome.values
        for outcome in setup.chance_outcomes
        if outcome.decision_id == decision_id
    )


def _deck(state: GameState) -> tuple[str, ...]:
    # Round 1 may already have revealed the top card.
    return (*state.current_conflict_ids, *state.conflict_deck)


def _assert_epic_setup(state: GameState, *, intrigue_cards: int = 1) -> None:
    """Every rise-of-ix.md 11 setup item, on a state built either way."""

    deck = _deck(state)
    tiers = tuple(CONFLICTS_BY_ID[card_id].tier for card_id in deck)
    assert tiers == (ConflictTier.TWO,) * 5 + (ConflictTier.THREE,) * 5
    pool = content_for(state.config).conflict_pool
    assert set(deck[5:]) == {
        conflict.card.card_id
        for conflict in pool
        if conflict.tier is ConflictTier.THREE
    }
    assert "economic_supremacy" in deck[5:]
    assert len(state.unused_conflict_ids) == 12
    for player in state.players:
        assert (player.troops_garrison, player.troops_supply) == (5, 7)
        assert player.dreadnoughts_supply == 2
        assert player.victory_points == 1
        assert len(player.intrigue_cards) == intrigue_cards
        owned = _card_ids((*player.deck, *player.hand, *player.discard_pile))
        assert owned["control_the_spice"] == 1
        assert owned["dune_the_desert_planet"] == 1
        assert sum(owned.values()) == 10


# -- The refusal ----------------------------------------------------------------
@pytest.mark.parametrize("leader_draft", (False, True))
def test_epic_on_the_original_game_needs_rise_of_ix(leader_draft: bool) -> None:
    """rise-of-ix.md 11 places the mode in the Rise of Ix rulebook
    (`[Rise of Ix p. 10]`); only Uprising plays it alone, by user decision
    (OQ-092, epic-game-mode.md). The original game without Rise of Ix stays
    refused, by both setup paths."""

    config = RulesetConfig(
        base_game=BaseGame.IMPERIUM, epic_game=True, leader_draft=leader_draft
    )
    with pytest.raises(NotImplementedError, match="epic_game only with rise_of_ix"):
        UprisingRulesEngine().reset(config, 0)
    # The opened combination plays, and Uprising's own Epic still does.
    assert (
        UprisingRulesEngine()
        .reset(replace(config, rise_of_ix=True), 0)
        .config.epic_game
    )
    assert (
        UprisingRulesEngine()
        .reset(RulesetConfig(epic_game=True, leader_draft=leader_draft), 0)
        .config.epic_game
    )


def test_go_to_11_with_epic_waits_for_immortality_on_the_original_game() -> None:
    """Go to 11 needs Immortality [Immortality p. 12] (OQ-091), which the
    original game takes from stage P7; when it does, the game runs from 0 to
    12: "사용자 결정: 0에서 시작해 12점에 Endgame이다 (OQ-093)"
    (epic-game-mode.md 5)."""

    config = replace(IX_EPIC, immortality=True, go_to_11=True)
    assert (config.starting_victory_points, config.endgame_victory_points) == (0, 12)
    with pytest.raises(NotImplementedError, match="immortality from stage P7"):
        UprisingRulesEngine().reset(config, 0)


# -- The Conflict deck ----------------------------------------------------------
def test_the_epic_conflict_deck_uses_all_five_conflict_iii() -> None:
    """ "Conflict I을 쓰지 않고 무작위 II 다섯 장을 III 다섯 장 위에 놓는다 —
    원판 + Ix의 III은 다섯 장(원판 4 + Economic Supremacy)이라 모두 쓴다"
    (rise-of-ix.md 11): the tier decisions are five of the five III and five
    of the eleven II, and no Conflict I is drawn."""

    decisions = conflict_setup_decisions(IX_EPIC)
    assert [(d.decision_id, d.count, len(d.options)) for d in decisions] == [
        ("setup:conflict:tier:3", 5, 5),
        ("setup:conflict:tier:2", 5, 11),
    ]
    assert "economic_supremacy" in decisions[0].options


@pytest.mark.parametrize("seed", range(6))
def test_every_conflict_i_and_six_ii_stay_in_the_box(seed: int) -> None:
    """The printed I 6, II 11, III 5 (`[Rise of Ix p. 3]`, rise-of-ix.md 3
    item 3) less the five II over five III leave twelve unused: every
    Conflict I and six Conflict II, unseen."""

    state = create_initial_state(IX_EPIC, seed, LEADERS).state
    deck = _deck(state)
    pool = content_for(IX_EPIC).conflict_pool
    assert len(pool) == 22
    unused = Counter(CONFLICTS_BY_ID[card].tier for card in state.unused_conflict_ids)
    assert unused == {ConflictTier.ONE: 6, ConflictTier.TWO: 6}
    assert set(deck) | set(state.unused_conflict_ids) == {
        conflict.card.card_id for conflict in pool
    }
    assert not set(deck) & set(state.unused_conflict_ids)
    _assert_epic_setup(state)


def test_the_option_only_drops_the_conflict_i_decision() -> None:
    """The Epic changes add no chance step: the Intrigue deal reads the
    shuffled deck (epic-game-mode.md 7, "새 우연 결정은 없다")."""

    plain = create_initial_state(IX, 5, LEADERS)
    epic = create_initial_state(IX_EPIC, 5, LEADERS)
    assert [outcome.decision_id for outcome in epic.chance_outcomes] == [
        outcome.decision_id
        for outcome in plain.chance_outcomes
        if outcome.decision_id != "setup:conflict:tier:1"
    ]


# -- Players ----------------------------------------------------------------------
def test_each_starting_deck_swaps_one_dune_for_control_the_spice() -> None:
    """ "좌석마다 Dune, the Desert Planet 하나를 Control the Spice로 바꾸고"
    (rise-of-ix.md 11): the original starting deck holds two Dune, the Desert
    Planet among its ten [DI p. 3] (imperium-base.md 3), so the deck keeps ten
    cards with one of each; nothing starts in the discard pile."""

    plain = create_initial_state(IX, 3, LEADERS).state
    state = create_initial_state(IX_EPIC, 3, LEADERS).state

    for before, player in zip(plain.players, state.players, strict=True):
        assert len(player.deck) == 10
        assert player.discard_pile == ()
        expected = _card_ids(before.deck)
        assert expected["dune_the_desert_planet"] == 2
        expected["dune_the_desert_planet"] -= 1
        expected["control_the_spice"] += 1
        assert _card_ids(player.deck) == expected
        assert f"player:{player.player_id}:starter:control_the_spice:0" in player.deck


def test_each_garrison_starts_with_five_troops() -> None:
    """ "garrison troop 5로 시작한다" (rise-of-ix.md 11): the other seven of
    the 12 wait in the supply beside the two dreadnoughts (rise-of-ix.md 3
    item 5)."""

    plain = create_initial_state(IX, 3, LEADERS).state
    state = create_initial_state(IX_EPIC, 3, LEADERS).state
    for before, player in zip(plain.players, state.players, strict=True):
        assert (before.troops_garrison, before.troops_supply) == (3, 9)
        assert (player.troops_garrison, player.troops_supply) == (5, 7)
        assert (player.dreadnoughts_supply, player.freighter_space) == (2, 0)


def test_each_seat_draws_one_intrigue_card_from_the_first_player() -> None:
    """ "모두 Intrigue 1장을 뽑고" (rise-of-ix.md 11): the shuffled deck's top
    cards go out one each in seat order from the First Player (project
    convention, epic-game-mode.md 7)."""

    plain = create_initial_state(IX, 1, LEADERS).state
    setup = create_initial_state(IX_EPIC, 1, LEADERS)
    state = setup.state
    # A First Player other than seat 0, so dealing from seat 0 would fail.
    assert state.first_player == 3
    shuffled = _outcome_values(setup, "setup:intrigue_deck")
    for position in range(4):
        seat = (state.first_player + position) % 4
        assert state.players[seat].intrigue_cards == (shuffled[position],)
    assert state.intrigue_deck == shuffled[4:]
    assert len(state.intrigue_deck) == len(plain.intrigue_deck) - 4
    assert all(player.intrigue_cards == () for player in plain.players)


def test_the_game_plays_to_twelve_from_the_usual_start() -> None:
    """ "12점까지" (rise-of-ix.md 11): the Endgame threshold is 12, the Score
    markers still start on 1 in a four-player game (imperium-base.md 4)."""

    assert (IX_EPIC.starting_victory_points, IX_EPIC.endgame_victory_points) == (1, 12)
    assert (IX.starting_victory_points, IX.endgame_victory_points) == (1, 10)


@pytest.mark.parametrize("config", (IX_EPIC, replace(IX_EPIC, promo_cards=True)))
def test_epic_setup_replays_from_its_recorded_chance(config: RulesetConfig) -> None:
    first = create_initial_state(config, 55, LEADERS)
    repeated = create_initial_state(config, 55, LEADERS)
    replayed = create_initial_state(
        config, 999, LEADERS, recorded_outcomes=first.chance_outcomes
    )

    assert repeated == first
    assert replace(replayed.state, seed=first.state.seed) == first.state
    assert replayed.chance_outcomes == first.chance_outcomes


def test_the_engine_reset_starts_round_one_with_the_epic_setup() -> None:
    state = UprisingRulesEngine(leader_ids=LEADERS).reset(IX_EPIC, 4)

    assert state.phase is GamePhase.PLAYER_TURNS
    assert state.round_number == 1
    _assert_epic_setup(state)
    assert all(len(player.hand) == 5 for player in state.players)


# -- The Leader draft path --------------------------------------------------------
def test_the_draft_deals_the_epic_intrigue_after_the_last_pick() -> None:
    """The Intrigue card is drawn once every Leader is known ("A player using
    Viscount Hundro Moritani as their Leader should wait until all players
    have drawn their Intrigue card" [Rise of Ix p. 10], epic-game-mode.md 7):
    nobody holds it during the OQ-007 draft, and the last pick's turn-end
    press deals it from the First Player, the cards the fixed setup deals."""

    setup = create_draft_initial_state(IX_EPIC_DRAFT, 1)
    state = setup.state
    assert state.phase is GamePhase.SETUP
    assert state.first_player == 3
    _assert_epic_setup(state, intrigue_cards=0)
    shuffled = _outcome_values(setup, "setup:intrigue_deck")
    assert state.intrigue_deck == shuffled

    engine = UprisingRulesEngine()
    live = engine.reset(IX_EPIC_DRAFT, 1)
    assert live == state
    while live.phase is GamePhase.SETUP and live.leader_draft_pool:
        decision = live.decision_stack[-1].decision
        assert isinstance(decision, PlayerDecision)
        assert all(player.intrigue_cards == () for player in live.players)
        pool = remaining_draft_pool(live)
        # Leaders whose setup pauses (Baron, Hundro) are left for other tests.
        picks = [
            leader
            for leader in pool
            if leader not in ("baron_vladimir_harkonnen", "viscount_hundro_moritani")
        ]
        rows = engine.legal_actions(live, decision.owner)
        finish = [row for row in rows if row.action_id == "finish_leader_draft"]
        live = engine.apply(
            live,
            finish[0]
            if finish
            else next(
                row for row in rows if dict(row.arguments)["leader_id"] == picks[0]
            ),
        ).state
        if finish:
            break
    assert live.phase is GamePhase.PLAYER_TURNS
    for position in range(4):
        seat = (state.first_player + position) % 4
        assert live.players[seat].intrigue_cards == (shuffled[position],)
    assert live.intrigue_deck == shuffled[4:]
    _assert_epic_setup(live)


# -- Viscount Hundro Moritani's Intelligence ----------------------------------------
def _keep_rows(engine: _Engine, state: GameState, seat: int) -> list[DomainAction]:
    """The keep-one choices (whole actions; the frame offers each card's step)."""

    engine.legal_actions(state, seat)
    return [
        row
        for row in engine.whole_actions(state, seat)
        if row.action_id == "keep_peeked_intrigue"
    ]


def _peeked(
    engine: UprisingRulesEngine, state: GameState, seat: int
) -> tuple[str, ...]:
    private = engine.observe(state, seat).private
    assert private is not None
    return tuple(private.peeked_intrigue_ids)


def _assert_dealt_from_the_first_player(
    state: GameState, shuffled: tuple[str, ...], *, hundro: int, kept: str = ""
) -> None:
    assert state.first_player is not None
    for position in range(4):
        seat = (state.first_player + position) % 4
        held = (shuffled[position], *((kept,) if kept and seat == hundro else ()))
        assert state.players[seat].intrigue_cards == held


def test_hundro_looks_once_every_seat_has_drawn_its_intrigue_card() -> None:
    """ "모두 Intrigue 1장을 뽑고(Hundro는 모두 뽑은 뒤 Intelligence)"
    (rise-of-ix.md 11); "Epic에서는 Hundro가 모두가 Intrigue를 뽑은 뒤 쓴다고
    룰북이 정한다 `[Rise of Ix p. 10]`" (rise-of-ix.md 3). Every seat holds its
    card, Hundro's dealt last here, and his look is at the two cards then on
    top: the shuffled deck's fifth and sixth. The kept card joins his own; the
    other goes back on top, his alone to know (rise-of-ix.md 13, OQ-149 (가))."""

    setup = create_initial_state(IX_EPIC, 1, HUNDRO_LEADERS)
    shuffled = _outcome_values(setup, "setup:intrigue_deck")
    engine = _Engine(leader_ids=HUNDRO_LEADERS)
    state = engine.reset(IX_EPIC, 1)
    assert state == setup.state
    assert state.first_player == 3
    assert state.phase is GamePhase.SETUP
    assert [frame.kind for frame in state.decision_stack] == [FrameKind.INTRIGUE_PEEK]
    _assert_dealt_from_the_first_player(state, shuffled, hundro=2)
    assert state.intrigue_deck == shuffled[4:]
    assert _peeked(engine, state, 2) == shuffled[4:6]
    for seat in (0, 1, 3):
        assert _peeked(engine, state, seat) == ()
    check_observation_privacy(state)

    rows = _keep_rows(engine, state, 2)
    assert [dict(row.arguments)["instance_id"] for row in rows] == list(shuffled[4:6])
    kept = apply_whole(engine, state, rows[1]).state
    _assert_dealt_from_the_first_player(kept, shuffled, hundro=2, kept=shuffled[5])
    assert kept.intrigue_deck == (shuffled[4], *shuffled[6:])
    assert kept.players[2].known_intrigue_ids == (shuffled[4],)
    assert all(
        not seat.known_intrigue_ids for seat in kept.players if seat.player_id != 2
    )
    check_observation_privacy(kept)

    started = _settle(engine, kept)
    assert started.phase is GamePhase.PLAYER_TURNS
    assert started.players[2].known_intrigue_ids == (shuffled[4],)
    private = engine.observe(started, 2).private
    assert private is not None and private.known_intrigue_top == shuffled[4]
    for seat in (0, 1, 3):
        other = engine.observe(started, seat).private
        assert other is not None and other.known_intrigue_top == ""
    check_observation_privacy(started)


def test_a_drafted_hundro_looks_after_the_epic_draw() -> None:
    """The draft path keeps the same order: nobody holds an Intrigue card or
    looks during the OQ-007 picks; the last pick's turn-end press deals the
    cards from the First Player (epic-game-mode.md 7) and then Hundro looks
    at the deck's new top two (rise-of-ix.md 3 and 11)."""

    setup = create_draft_initial_state(IX_EPIC_DRAFT, 1)
    shuffled = _outcome_values(setup, "setup:intrigue_deck")
    assert HUNDRO in setup.state.leader_draft_pool
    engine = _Engine()
    live = engine.reset(IX_EPIC_DRAFT, 1)
    first_pick = True
    while live.decision_stack[-1].kind is FrameKind.LEADER_DRAFT:
        assert all(player.intrigue_cards == () for player in live.players)
        assert live.intrigue_deck == shuffled
        decision = live.decision_stack[-1].decision
        assert isinstance(decision, PlayerDecision)
        rows = engine.legal_actions(live, decision.owner)
        wanted = (
            HUNDRO
            if first_pick
            else next(
                leader
                for leader in remaining_draft_pool(live)
                if leader not in (HUNDRO, BARON)
            )
        )
        first_pick = False
        live = engine.apply(
            live,
            next(
                row
                for row in rows
                if row.action_id == "finish_leader_draft"
                or dict(row.arguments).get("leader_id") == wanted
            ),
        ).state

    (hundro,) = (seat.player_id for seat in live.players if seat.leader_id == HUNDRO)
    assert live.phase is GamePhase.SETUP
    assert live.decision_stack[-1].kind is FrameKind.INTRIGUE_PEEK
    _assert_dealt_from_the_first_player(live, shuffled, hundro=hundro)
    assert _peeked(engine, live, hundro) == shuffled[4:6]
    check_observation_privacy(live)
    kept = apply_whole(engine, live, _keep_rows(engine, live, hundro)[0]).state
    assert kept.players[hundro].known_intrigue_ids == (shuffled[5],)
    started = _settle(engine, kept)
    assert started.phase is GamePhase.PLAYER_TURNS
    assert [len(seat.intrigue_cards) for seat in started.players] == [
        2 if seat.player_id == hundro else 1 for seat in started.players
    ]
    check_observation_privacy(started)


def test_the_baron_and_hundro_both_follow_the_epic_draw() -> None:
    """The Baron's Factions and Hundro's look both come "모든 setup 뒤, 첫 라운드
    전" (rise-of-ix.md 3, [FAQ p. 1]), the Epic draw being a setup step: each
    seat holds its card while the Baron chooses and Hundro looks, and the
    round begins once both are done."""

    leaders = (BARON, "count_ilban_richese", HUNDRO, "earl_memnon_thorvald")
    setup = create_initial_state(IX_EPIC, 1, leaders)
    shuffled = _outcome_values(setup, "setup:intrigue_deck")
    engine = _Engine(leader_ids=leaders)
    state = engine.reset(IX_EPIC, 1)
    assert [frame.kind for frame in state.decision_stack] == [
        FrameKind.MASTERSTROKE_SETUP,
        FrameKind.INTRIGUE_PEEK,
    ]
    _assert_dealt_from_the_first_player(state, shuffled, hundro=2)
    assert _peeked(engine, state, 2) == shuffled[4:6]
    check_observation_privacy(state)
    state = apply_whole(engine, state, _keep_rows(engine, state, 2)[0]).state
    assert state.phase is GamePhase.SETUP
    for faction in ("emperor", "fremen"):
        engine.legal_actions(state, 0)
        state = engine.apply(
            state,
            DomainAction("choose_masterstroke_faction", 0, (("faction", faction),)),
        ).state
    started = _settle(engine, state)
    assert started.phase is GamePhase.PLAYER_TURNS
    check_observation_privacy(started)


# -- Round 1 ----------------------------------------------------------------------
ILESA = "ilesa_ecaz"
SEAT_ZERO = replace(IX_EPIC, first_player_seat_zero=True)


def test_ilesa_sets_a_hand_card_aside_in_the_first_epic_round() -> None:
    """ "Round Start에 손의 카드 하나를 따로 둔다" (rise-of-ix.md 10), after the
    five cards (OQ-122): in Epic round 1 she also holds the setup Intrigue
    card, which is no hand card -- the choice offers her five Imperium hand
    cards only, and the Intrigue card stays hers."""

    leaders = (ILESA, "glossu_rabban", "count_ilban_richese", "earl_memnon_thorvald")
    engine = _Engine(leader_ids=leaders)
    state = _settle(engine, engine.reset(SEAT_ZERO, 3))
    assert state.phase is GamePhase.PLAYER_TURNS
    assert [frame.kind for frame in state.decision_stack] == [
        FrameKind.TURN,
        FrameKind.ROUND_START_SET_ASIDE,
    ]
    owner = state.players[0]
    assert len(owner.hand) == 5 and len(owner.intrigue_cards) == 1
    engine.legal_actions(state, 0)
    rows = [
        row
        for row in engine.whole_actions(state, 0)
        if row.action_id == "set_aside_leader_card"
    ]
    assert {dict(row.arguments)["card_id"] for row in rows} == set(owner.hand)
    check_observation_privacy(state)
    aside = apply_whole(engine, state, rows[0]).state
    after = aside.players[0]
    assert after.set_aside_card_id == dict(rows[0].arguments)["card_id"]
    assert after.set_aside_card_id not in after.hand
    assert after.intrigue_cards == owner.intrigue_cards
    assert [frame.kind for frame in aside.decision_stack] == [FrameKind.TURN]
    check_observation_privacy(aside)


# -- Control the Spice on the original board ----------------------------------------
CONTROL = "player:0:starter:control_the_spice:0"


def _with_control_in_hand(state: GameState, **changes: object) -> GameState:
    """Seat 0 holds Control the Spice (swapped from its deck or discard)."""

    owner = state.players[0]
    if CONTROL not in owner.hand:
        swapped = owner.hand[0]
        owner = replace(
            owner,
            hand=(CONTROL, *owner.hand[1:]),
            deck=tuple(swapped if card == CONTROL else card for card in owner.deck),
            discard_pile=tuple(
                swapped if card == CONTROL else card for card in owner.discard_pile
            ),
        )
    owner = replace(owner, **changes)  # type: ignore[arg-type]
    return replace(state, players=(owner, *state.players[1:]))


def _whole(engine: _Engine, state: GameState, action_id: str) -> list[DomainAction]:
    engine.legal_actions(state, 0)
    return [row for row in engine.whole_actions(state, 0) if row.action_id == action_id]


def test_control_the_spice_plays_on_the_original_board() -> None:
    """epic-game-mode.md 6: "Agent 아이콘: Spice Trade(노란 삼각형) 하나 — Dune,
    the Desert Planet와 같다"; "Agent box: spice 1 → 카드 1장 trash + troop 1
    recruit. 화살표 비용이므로 내지 않아도 되고 ... trash 후보는 hand, discard
    pile, in play의 카드다 [Main p. 20](Control the Spice 자신 포함)". On the
    original board with Rise of Ix the card goes to every Spice Trade space
    (water, spice and Spacing Guild Influence given so only the icon limits
    it); paying the spice recruits a troop and offers the trash."""

    engine = _Engine(leader_ids=LEADERS)
    state = _settle(engine, engine.reset(SEAT_ZERO, 3))
    hand = state.players[0].hand
    state = _with_control_in_hand(
        state,
        resources=replace(state.players[0].resources, spice=3, water=3),
        influence=replace(state.players[0].influence, spacing_guild=2),
    )
    owner = state.players[0]
    (pick,) = [
        row
        for row in _whole(engine, state, "choose_agent_card")
        if dict(row.arguments)["card_id"] == CONTROL
    ]
    picked = apply_whole(engine, state, pick).state
    spaces = {
        dict(row.arguments)["space_id"]: row
        for row in _whole(engine, picked, "place_agent")
    }
    assert (
        set(spaces)
        == {
            space.space_id
            for space in content_for(SEAT_ZERO).board_spaces
            if space.agent_icon.value == "spice_trade"
        }
        == {
            "imperial_basin",
            "imperium_hagga_basin",
            "the_great_flat",
            "interstellar_shipping",
            "smuggling",
        }
    )
    placed = apply_whole(engine, picked, spaces["imperial_basin"]).state
    (pay,) = _whole(engine, placed, "pay_agent_card_spice")
    paid = apply_whole(engine, placed, pay).state
    seat = paid.players[0]
    # The space's own spice (Maker harvest) is still a row of the turn.
    assert seat.resources.spice == owner.resources.spice - 1
    assert (seat.troops_garrison, seat.troops_supply) == (
        owner.troops_garrison + 1,
        owner.troops_supply - 1,
    )
    offered = {
        str(dict(row.arguments)["card_id"])
        for row in _whole(engine, paid, "trash_optional_card")
    }
    assert CONTROL in offered
    assert set(hand[1:]) <= offered
    trashed = apply_whole(
        engine,
        paid,
        next(
            row
            for row in _whole(engine, paid, "trash_optional_card")
            if dict(row.arguments)["card_id"] == CONTROL
        ),
    ).state
    assert trashed.players[0].trashed == (CONTROL,)
    check_observation_privacy(trashed)


# -- Economic Supremacy -------------------------------------------------------------
def _combat_on_economic_supremacy(*, solari: int, spice: int) -> GameState:
    """An Epic setup's state at the Combat of round 6, Economic Supremacy
    revealed: seat 0 first (8), seat 1 second (6), seat 2 third (4), seat 3
    out."""

    state = create_initial_state(SEAT_ZERO, 3, LEADERS).state
    players = [
        replace(
            player,
            combat_strength=strength,
            resources=Resources(solari=solari, spice=spice)
            if player.player_id == 0
            else Resources(),
        )
        for player, strength in zip(state.players, (8, 6, 4, 0), strict=True)
    ]
    return replace(
        state,
        phase=GamePhase.COMBAT,
        round_number=6,
        players=tuple(players),
        current_conflict_ids=("economic_supremacy",),
        conflict_deck=tuple(
            card for card in state.conflict_deck if card != "economic_supremacy"
        ),
        combat_intrigue_complete=True,
    )


def _answer_arrow(state: GameState, *, pay: bool) -> GameState:
    frame = state.decision_stack[-1]
    assert frame.kind == FrameKind.COMBAT_REWARD_OPTIONAL
    action = DomainAction("pay_combat_reward" if pay else "decline_combat_reward", 0)
    assert action in legal_combat_reward_optional_payment_actions(state, 0)
    return settle_reward_window(
        apply_combat_reward_optional_payment(state, action).state
    )


@pytest.mark.parametrize("pay", (True, False))
def test_economic_supremacy_pays_its_rows_in_the_original_game(pay: bool) -> None:
    """Every Epic deck of the original game holds Economic Supremacy among its
    five Conflict III (rise-of-ix.md 11, 12). Its rows (epic-game-mode.md 6):
    "1위: Victory Point 1. 그리고 Solari 6 → Victory Point 1, spice 4 →
    Victory Point 1. 두 화살표는 서로 독립이라 둘 다, 하나만, 또는 하나도 안 낼
    수 있다"; "2위: Victory Point 1"; "3위: spice 2, Solari 2"; "location 없음
    (control 보상 없음)"."""

    before = _combat_on_economic_supremacy(solari=6, spice=4)
    state = settle_reward_window(resolve_combat_rewards(before).state)
    state = _answer_arrow(state, pay=pay)
    state = _answer_arrow(state, pay=pay)
    while not state.combat_rewards_resolved:
        if pause_is_pending(state):
            state = answer_pause(state).state
        elif not state.decision_stack:
            state = resolve_combat_rewards(state).state
        else:
            state = settle_reward_window(state)

    first, second, third, fourth = state.players
    gained = 3 if pay else 1
    assert first.victory_points == before.players[0].victory_points + gained
    assert (first.resources.solari, first.resources.spice) == (
        (0, 0) if pay else (6, 4)
    )
    assert second.victory_points == before.players[1].victory_points + 1
    assert (third.resources.spice, third.resources.solari) == (2, 2)
    assert fourth == before.players[3]
    assert all(player.control_space_ids == () for player in state.players)
    assert state.dreadnought_control == ()


# -- Whole games ----------------------------------------------------------------------
def test_a_heuristic_game_plays_past_ten_to_the_twelve_point_end() -> None:
    """ "12점까지" (rise-of-ix.md 11): the round-end check ("Endgame 조건(10점
    이상 또는 Conflict 덱 소진)" [DI p. 13], imperium-base.md 10) reads 12, not
    10 (epic-game-mode.md 3). In this seeded heuristic game (seed 18,
    found by search) a seat stands on 10 and then 11 at round ends and the
    game goes on; a round end with 12 opens the Endgame while a Conflict card
    is still in the deck, and the game finishes there."""

    engine = UprisingRulesEngine()
    state = engine.reset(IX_EPIC, 18)
    agents = [HeuristicAgent(seed=180 + seat) for seat in range(4)]
    chance = ChanceResolver(seed=18)
    round_ends: list[tuple[int, bool, int]] = []
    while state.phase is not GamePhase.FINISHED:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            transition = engine.apply(state, chance.resolve(decision))
        else:
            assert isinstance(decision, PlayerDecision)
            rows = engine.legal_actions(state, decision.owner)
            pick = agents[decision.owner].choose_action_with_state(
                state, engine.observe(state, decision.owner), rows
            )
            transition = engine.apply(state, pick, legal_actions=rows)
        ended = any(event.kind == "endgame_started" for event in transition.events)
        if ended or transition.state.round_number > state.round_number:
            best = max(player.victory_points for player in transition.state.players)
            round_ends.append((best, ended, len(transition.state.conflict_deck)))
        state = transition.state

    *played_on, (final_best, final_ended, deck_left) = round_ends
    assert final_ended and final_best >= 12 and deck_left > 0
    assert all(not ended and best < 12 for best, ended, _ in played_on)
    assert {10, 11} <= {best for best, _, _ in played_on}
    # A Conflict card was still face down when the Endgame opened.
    assert state.conflict_deck


@pytest.mark.parametrize("policy", ["random", "heuristic"])
@pytest.mark.parametrize(
    "config",
    (IX_EPIC, IX_EPIC_DRAFT, replace(IX_EPIC, promo_cards=True)),
    ids=("fixed", "draft", "promo"),
)
def test_an_epic_game_finishes_under_every_invariant(
    config: RulesetConfig, policy: str
) -> None:
    """A short engine-driven game, every seat the same scripted policy, under
    the sweep's checks: card conservation (the Epic Intrigue cards and Control
    the Spice included), troops and dreadnoughts, observation privacy, the
    codec round trip of every advertised action (``soundness_interval``) and
    the replay."""

    report = run_checked_game(config, 12, 900_012, policy=policy, soundness_interval=25)
    assert report.winner is not None


# -- The action codec -----------------------------------------------------------------
@pytest.mark.parametrize(
    "config",
    (IX_EPIC, IX_EPIC_DRAFT, replace(IX_EPIC, promo_cards=True)),
    ids=("fixed", "draft", "promo"),
)
def test_the_epic_rows_round_trip_only_in_an_epic_catalog(
    config: RulesetConfig,
) -> None:
    """Control the Spice's rows -- the paid arrow's ``pay`` effect row, the
    optional trash's target row and its refusal naming the card -- round-trip
    through an original + Rise of Ix + Epic catalog and are in no catalog of
    the same game without Epic Game Mode; a draft pick of any offered Leader
    (the six Ix ones included) and the draft's end round-trip too. The other
    setup-time rows the engine offers (the Intelligence keep, the Baron's
    Factions, Ilesa's set-aside) are round-tripped by ``_Engine`` in the
    tests above."""

    whole_trash = DomainAction("trash_optional_card", 0, (("card_id", CONTROL),))
    (trash,) = steps_for(whole_trash, effect_row=False)
    (pay,) = steps_for(DomainAction("pay_agent_card_spice", 0), "control_the_spice")
    (decline,) = steps_for(
        DomainAction("decline_optional_trash", 0),
        "control_the_spice",
        Source.AGENT_CARD,
    )
    codec = _codec(config)
    for action in (trash, pay, decline):
        assert codec.decode(codec.encode(action), 0) == action
    plain = _codec(replace(config, epic_game=False))
    for action in (pay, decline):
        with pytest.raises(ValueError, match="not present"):
            plain.encode(action)
    assert not any(
        dict(template.arguments).get("printed") == "control_the_spice"
        for template in plain.catalog
    )
    if config.leader_draft:
        # A pick is offered as the Leader's target row (stage B3).
        for leader in content_for(config).leaders:
            pick = DomainAction("pick_leader", 2, (("leader_id", leader.leader_id),))
            for row in steps_for(pick):
                assert codec.decode(codec.encode(row), 2) == row
        finish = DomainAction("finish_leader_draft", 1)
        assert codec.decode(codec.encode(finish), 1) == finish
