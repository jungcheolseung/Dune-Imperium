"""Setup and Endgame of Rise of Ix's Epic Game Mode (``epic_game``).

The rules are in ``docs/rules/epic-game-mode.md``: "10이 아니라 12 Victory
Point까지 한다" and the four setup changes [Rise of Ix p. 10]; Economic
Supremacy as the fifth Conflict III [Main p. 18]; Control the Spice in the
discard pile with Immortality [Immortality p. 12]; the Go to 11 combination
(OQ-093); and the Intrigue deal order (project convention, section 7).
"""

from collections import Counter
from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.conflicts import CONFLICTS, CONFLICTS_BY_ID
from dune_imperium.content.uprising.starting_cards import starting_card_for_instance
from dune_imperium.content.uprising.types import ConflictTier
from dune_imperium.core import ChanceResolver, GamePhase, GameState, PlayerDecision
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.leader_draft import remaining_draft_pool
from dune_imperium.rules.phases import resolve_recall_or_endgame
from dune_imperium.rules.setup import (
    ConflictSetup,
    SetupResult,
    build_conflict_setup,
    conflict_setup_decisions,
    create_draft_initial_state,
    create_initial_state,
)
from dune_imperium.simulation.sweep import run_checked_game

LEADERS = (
    "feyd_rautha_harkonnen",
    "gurney_halleck",
    "lady_amber_metulli",
    "lady_jessica",
)
EPIC = RulesetConfig(epic_game=True)
EPIC_IMMORTALITY = RulesetConfig(immortality=True, epic_game=True)
EPIC_GO_TO_11 = RulesetConfig(immortality=True, go_to_11=True, epic_game=True)


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


# -- The Conflict deck --------------------------------------------------------
@pytest.mark.parametrize("bloodlines", (False, True))
def test_the_epic_conflict_deck_is_five_ii_over_five_iii(bloodlines: bool) -> None:
    # "Conflict I 카드를 쓰지 않는다. 대신 무작위로 고른 Conflict II 5장을
    # Conflict III 5장 위에 놓는다" [Rise of Ix p. 10], the fifth III being
    # Economic Supremacy [Main p. 18]; Bloodlines only widens the II pool
    # [Bloodlines p. 3] (docs/rules/epic-game-mode.md section 3).
    decisions = conflict_setup_decisions(bloodlines=bloodlines, epic_game=True)
    assert [(d.decision_id, d.count) for d in decisions] == [
        ("setup:conflict:tier:3", 5),
        ("setup:conflict:tier:2", 5),
    ]
    assert "economic_supremacy" in decisions[0].options
    assert len(decisions[0].options) == 5
    assert len(decisions[1].options) == (10 if bloodlines else 9)
    resolver = ChanceResolver(seed=17)

    setup = build_conflict_setup(
        tuple(resolver.resolve(decision) for decision in decisions),
        bloodlines=bloodlines,
        epic_game=True,
    )

    tiers = tuple(CONFLICTS_BY_ID[card_id].tier for card_id in setup.deck)
    assert tiers == (ConflictTier.TWO,) * 5 + (ConflictTier.THREE,) * 5
    assert "economic_supremacy" in setup.deck[5:]
    # Every Conflict I goes back to the box unseen, with the unused IIs.
    assert len(setup.unused) == (9 if bloodlines else 7)
    tier_one = {
        conflict.card.card_id
        for conflict in CONFLICTS
        if conflict.tier is ConflictTier.ONE
        and (bloodlines or not conflict.bloodlines_only)
    }
    assert tier_one <= set(setup.unused)
    assert set(setup.deck) | set(setup.unused) == {
        conflict.card.card_id
        for conflict in CONFLICTS
        if bloodlines or not conflict.bloodlines_only
    }


def test_the_epic_tier_outcomes_do_not_build_a_standard_deck() -> None:
    resolver = ChanceResolver(seed=17)
    outcomes = tuple(
        resolver.resolve(decision)
        for decision in conflict_setup_decisions(epic_game=True)
    )
    with pytest.raises(ValueError):
        build_conflict_setup(outcomes)


def test_the_unused_conflict_count_follows_the_option() -> None:
    deck = tuple(f"deck_{index}" for index in range(10))

    def unused(count: int) -> tuple[str, ...]:
        return tuple(f"unused_{index}" for index in range(count))

    for count in (6, 8):
        ConflictSetup(deck=deck, unused=unused(count))
        with pytest.raises(ValueError, match="Epic Game Mode"):
            ConflictSetup(deck=deck, unused=unused(count), epic_game=True)
    for count in (7, 9):
        ConflictSetup(deck=deck, unused=unused(count), epic_game=True)
        with pytest.raises(ValueError, match="six"):
            ConflictSetup(deck=deck, unused=unused(count))


def test_the_option_only_drops_the_conflict_i_decision() -> None:
    # No new chance decision: the Intrigue deal reads the shuffled deck.
    plain = create_initial_state(RulesetConfig(), seed=5, leader_ids=LEADERS)
    epic = create_initial_state(EPIC, seed=5, leader_ids=LEADERS)
    plain_ids = [outcome.decision_id for outcome in plain.chance_outcomes]
    assert [outcome.decision_id for outcome in epic.chance_outcomes] == [
        decision_id
        for decision_id in plain_ids
        if decision_id != "setup:conflict:tier:1"
    ]


# -- Players ------------------------------------------------------------------
def test_each_starting_deck_swaps_one_dune_for_control_the_spice() -> None:
    # "각 플레이어는 시작 덱에서 Dune, the Desert Planet 1장을 빼고 Control the
    # Spice 1장으로 바꾼다" [Rise of Ix p. 10]: still ten cards.
    plain = create_initial_state(RulesetConfig(), seed=3, leader_ids=LEADERS).state
    state = create_initial_state(EPIC, seed=3, leader_ids=LEADERS).state

    for before, player in zip(plain.players, state.players, strict=True):
        assert len(player.deck) == 10
        assert player.discard_pile == ()
        expected = _card_ids(before.deck)
        expected["dune_the_desert_planet"] -= 1
        expected["control_the_spice"] += 1
        assert _card_ids(player.deck) == expected
        assert _card_ids(player.deck)["dune_the_desert_planet"] == 1


@pytest.mark.parametrize("config", (EPIC_IMMORTALITY, EPIC_GO_TO_11))
def test_with_immortality_control_the_spice_starts_in_the_discard_pile(
    config: RulesetConfig,
) -> None:
    # "시작 카드 10장 중 어느 것도 Control the Spice로 바꾸지 않고, 각
    # 플레이어가 Control the Spice를 게임 시작 때 자기 discard pile에
    # 놓는다" [Immortality p. 12] (docs/rules/epic-game-mode.md section 4).
    immortality = create_initial_state(
        RulesetConfig(immortality=True), seed=3, leader_ids=LEADERS
    ).state
    state = create_initial_state(config, seed=3, leader_ids=LEADERS).state

    for before, player in zip(immortality.players, state.players, strict=True):
        assert _card_ids(player.deck) == _card_ids(before.deck)
        assert _card_ids(player.deck)["experimentation"] == 2
        assert player.discard_pile == (
            f"player:{player.player_id}:starter:control_the_spice:0",
        )


@pytest.mark.parametrize("config", (EPIC, EPIC_IMMORTALITY))
def test_each_garrison_starts_with_five_troops(config: RulesetConfig) -> None:
    # "각 플레이어는 garrison에 troop 5개(3개가 아니라)를 두고 시작한다"
    # [Rise of Ix p. 10]; the other seven of the 12 wait in the supply
    # [Main p. 5].
    state = create_initial_state(config, seed=3, leader_ids=LEADERS).state

    for player in state.players:
        assert (player.troops_garrison, player.troops_supply) == (5, 7)


def test_each_player_draws_one_intrigue_card_from_the_first_player() -> None:
    # "각 플레이어는 Intrigue 카드 1장을 뽑는다" [Rise of Ix p. 10]; the top
    # cards go out one each in seat order from the First Player (project
    # convention, docs/rules/epic-game-mode.md section 7).
    plain = create_initial_state(RulesetConfig(), seed=2, leader_ids=LEADERS).state
    setup = create_initial_state(EPIC, seed=2, leader_ids=LEADERS)
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


def test_go_to_11_with_epic_starts_every_score_marker_on_zero() -> None:
    # OQ-093: Go to 11 moves the start to 0 [Immortality p. 12]; Epic moves
    # the end to 12 [Rise of Ix p. 10].
    assert (
        EPIC_GO_TO_11.starting_victory_points,
        EPIC_GO_TO_11.endgame_victory_points,
    ) == (0, 12)
    state = create_initial_state(EPIC_GO_TO_11, seed=3, leader_ids=LEADERS).state
    assert all(player.victory_points == 0 for player in state.players)
    epic = create_initial_state(EPIC, seed=3, leader_ids=LEADERS).state
    assert all(player.victory_points == 1 for player in epic.players)


@pytest.mark.parametrize(
    "config",
    (
        EPIC,
        EPIC_GO_TO_11,
        RulesetConfig(
            choam_module=True,
            promo_cards=True,
            bloodlines=True,
            tech_module=True,
            epic_game=True,
            arrakeen_scouts=True,
        ),
    ),
)
def test_epic_setup_replays_from_its_recorded_chance(config: RulesetConfig) -> None:
    first = create_initial_state(config, seed=55, leader_ids=LEADERS)
    repeated = create_initial_state(config, seed=55, leader_ids=LEADERS)
    replayed = create_initial_state(
        config, seed=999, leader_ids=LEADERS, recorded_outcomes=first.chance_outcomes
    )

    assert repeated == first
    assert replace(replayed.state, seed=first.state.seed) == first.state
    assert replayed.chance_outcomes == first.chance_outcomes


# -- The Leader draft path -----------------------------------------------------
def _assert_epic_setup(state: GameState, *, immortality: bool) -> None:
    # Round 1 may already have revealed the top card.
    deck = (*state.current_conflict_ids, *state.conflict_deck)
    tiers = tuple(CONFLICTS_BY_ID[card_id].tier for card_id in deck)
    assert tiers == (ConflictTier.TWO,) * 5 + (ConflictTier.THREE,) * 5
    assert "economic_supremacy" in deck[5:]
    assert len(state.unused_conflict_ids) == 7
    for player in state.players:
        assert (player.troops_garrison, player.troops_supply) == (5, 7)
        assert len(player.intrigue_cards) == 1
        owned = _card_ids((*player.deck, *player.hand, *player.discard_pile))
        assert owned["control_the_spice"] == 1
        assert owned["dune_the_desert_planet"] == (0 if immortality else 1)
        if immortality:
            assert _card_ids(player.discard_pile) == {"control_the_spice": 1}


@pytest.mark.parametrize("immortality", (False, True))
def test_the_draft_setup_deals_the_same_epic_setup(immortality: bool) -> None:
    config = RulesetConfig(leader_draft=True, immortality=immortality, epic_game=True)
    setup = create_draft_initial_state(config, seed=19)
    state = setup.state
    assert state.phase is GamePhase.SETUP
    # A First Player other than seat 0, so dealing from seat 0 would fail.
    assert state.first_player == 2
    _assert_epic_setup(state, immortality=immortality)
    shuffled = _outcome_values(setup, "setup:intrigue_deck")
    for position in range(4):
        seat = (state.first_player + position) % 4
        assert state.players[seat].intrigue_cards == (shuffled[position],)
    assert state.intrigue_deck == shuffled[4:]

    replayed = create_draft_initial_state(
        config, seed=999, recorded_outcomes=setup.chance_outcomes
    )
    assert replace(replayed.state, seed=state.seed) == state

    # The picks keep every seat's Intrigue card and discard pile.
    engine = UprisingRulesEngine()
    live = engine.reset(config, 19)
    assert live == state
    while live.phase is GamePhase.SETUP:
        decision = live.decision_stack[-1].decision
        assert isinstance(decision, PlayerDecision)
        pick = remaining_draft_pool(live)[0]
        live = engine.apply(
            live,
            next(
                action
                for action in engine.legal_actions(live, decision.owner)
                if dict(action.arguments)["leader_id"] == pick
            ),
        ).state
    assert live.phase is GamePhase.PLAYER_TURNS
    for before, after in zip(state.players, live.players, strict=True):
        assert after.intrigue_cards == before.intrigue_cards
        assert after.discard_pile == before.discard_pile


def test_the_engine_reset_starts_round_one_with_the_epic_setup() -> None:
    state = UprisingRulesEngine().reset(EPIC, 4)

    assert state.phase is GamePhase.PLAYER_TURNS
    assert state.round_number == 1
    _assert_epic_setup(state, immortality=False)
    assert all(len(player.hand) == 5 for player in state.players)


# -- The Endgame ----------------------------------------------------------------
@pytest.mark.parametrize("config", (EPIC, EPIC_GO_TO_11))
@pytest.mark.parametrize(("victory_points", "endgame"), ((11, False), (12, True)))
def test_the_epic_endgame_opens_at_twelve(
    config: RulesetConfig, victory_points: int, endgame: bool
) -> None:
    # "10이 아니라 12 Victory Point까지 한다" [Rise of Ix p. 10]: the round-end
    # check [Main p. 15] reads 12 instead of 10, whether the markers started
    # on 1 or, with Go to 11, on 0 (OQ-093).
    state = create_initial_state(config, seed=71, leader_ids=LEADERS).state
    leader = replace(state.players[2], victory_points=victory_points)
    state = replace(
        state,
        phase=GamePhase.RECALL_OR_ENDGAME,
        players=(*state.players[:2], leader, state.players[3]),
    )

    result = resolve_recall_or_endgame(state)

    assert (result.state.phase is GamePhase.ENDGAME) is endgame


def test_an_empty_conflict_deck_still_ends_an_epic_game() -> None:
    # The other end condition is unchanged [Main p. 15].
    state = create_initial_state(EPIC, seed=71, leader_ids=LEADERS).state
    state = replace(state, phase=GamePhase.RECALL_OR_ENDGAME, conflict_deck=())

    assert resolve_recall_or_endgame(state).state.phase is GamePhase.ENDGAME


# -- Whole games ------------------------------------------------------------------
@pytest.mark.parametrize(
    "config",
    (
        EPIC,
        EPIC_GO_TO_11,
        RulesetConfig(
            choam_module=True,
            bloodlines=True,
            tech_module=True,
            epic_game=True,
            arrakeen_scouts=True,
        ),
    ),
    ids=("epic", "epic_immortality_go11", "epic_bloodlines_tech_choam_scouts"),
)
@pytest.mark.parametrize("policy", ["random", "heuristic"])
def test_an_epic_game_finishes_under_every_invariant(
    config: RulesetConfig, policy: str
) -> None:
    report = run_checked_game(
        config, 12, 900_012, policy=policy, soundness_interval=25
    )
    assert report.winner is not None
