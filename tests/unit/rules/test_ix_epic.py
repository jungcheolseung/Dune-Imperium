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

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.uprising.starting_cards import starting_card_for_instance
from dune_imperium.content.uprising.types import ConflictTier
from dune_imperium.core import (
    GamePhase,
    GameState,
    PlayerDecision,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.leader_draft import remaining_draft_pool
from dune_imperium.rules.setup import (
    SetupResult,
    conflict_setup_decisions,
    create_draft_initial_state,
    create_initial_state,
)

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
