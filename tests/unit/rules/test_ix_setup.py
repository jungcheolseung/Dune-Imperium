"""Setup of the original game with Rise of Ix (stage P4c-5).

The rules are docs/rules/rise-of-ix.md 3 (``[Rise of Ix p. 3]``):

- item 2: "Tech tile 18장을 뒷면으로 섞어 6장씩 세 더미로 놓고, 더미마다 맨 위를
  앞면으로 뒤집는다";
- item 3: "Conflict 덱: 원판 카드에 Ix 카드 넷을 더해(I 6, II 11, III 5) 원판과 같은
  모양(I 1, II 5, III 4)으로 만든다. 이제 III 하나가 남아 상자로 간다";
- item 5: "좌석마다 dreadnought 둘을 supply에, disc 하나를 Freighter로 Shipping
  track 맨 아래 칸에 놓는다".

The engine's Conflict pool holds a card once its rewards are transcribed
(``rulesets._imperium_conflicts``); with Rise of Ix's three (stage P4d-1) it is
the printed 22 and exactly 12 stay unused. Uprising plus Rise of Ix stays
refused until stage P7, and Epic Game Mode on the original game until stage
P4e.
"""

from collections import Counter
from dataclasses import replace

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.content.rise_of_ix.tech import IX_TECH_IDS
from dune_imperium.content.rulesets import IMPERIUM_LEADER_IDS, content_for
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.uprising.types import ConflictTier
from dune_imperium.core import ChanceResolver, GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.setup import (
    ConflictSetup,
    create_draft_initial_state,
    create_initial_state,
    deal_ix_tech_stacks,
    ix_tech_tiles_decision,
    leader_draft_pool_decision,
)
from dune_imperium.simulation.sweep import run_checked_game, sweep_specs

LEADERS = (
    "paul_atreides",
    "duke_leto_atreides",
    "glossu_rabban",
    "baron_vladimir_harkonnen",
)
ORIGINAL = RulesetConfig(base_game=BaseGame.IMPERIUM)
IX = RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True)
IX_DRAFT = replace(IX, leader_draft=True)
TECH_DECISION_ID = "setup:ix_tech_tiles"


def _setup(config: RulesetConfig = IX, seed: int = 5) -> GameState:
    return create_initial_state(config, seed, LEADERS).state


def _deck(state: GameState) -> tuple[str, ...]:
    # Round 1 may already have revealed the top card.
    return (*state.current_conflict_ids, *state.conflict_deck)


def test_each_seat_starts_with_two_dreadnoughts_and_the_freighter_at_the_bottom() -> (
    None
):
    """rise-of-ix.md 3 item 5: "좌석마다 dreadnought 둘을 supply에, disc 하나를
    Freighter로 Shipping track 맨 아래 칸에 놓는다" `[Rise of Ix p. 3]`."""

    state = _setup()
    for player in state.players:
        assert player.dreadnoughts_supply == 2
        assert player.dreadnoughts_garrison == 0
        assert player.dreadnoughts_conflict == 0
        assert player.freighter_space == 0
        assert player.negotiators == 0
    assert state.dreadnought_control == ()


def test_a_game_without_rise_of_ix_has_none_of_it() -> None:
    state = _setup(ORIGINAL)
    for player in state.players:
        assert player.dreadnoughts_supply == 0
        assert player.freighter_space == 0
    assert state.tech_stacks == ()
    outcomes = create_initial_state(ORIGINAL, 5, LEADERS).chance_outcomes
    assert TECH_DECISION_ID not in {outcome.decision_id for outcome in outcomes}


@pytest.mark.parametrize("config", (IX, IX_DRAFT), ids=("fixed", "draft"))
def test_the_ix_tech_tiles_lie_in_three_stacks_of_six(config: RulesetConfig) -> None:
    """rise-of-ix.md 3 item 2: the 18 tiles are shuffled into three stacks of
    six (`[Rise of Ix p. 3]`), the top of each face up (``tech_stacks[i][0]``,
    as the Tech Module's stacks)."""

    if config.leader_draft:
        state = create_draft_initial_state(config, 5).state
        assert state.phase is GamePhase.SETUP
    else:
        state = _setup(config)
    assert tuple(len(stack) for stack in state.tech_stacks) == (6, 6, 6)
    assert sorted(tile for stack in state.tech_stacks for tile in stack) == sorted(
        IX_TECH_IDS
    )
    assert state.tech_trash == ()
    assert all(not player.tech_ids for player in state.players)
    for player in state.players:
        assert player.dreadnoughts_supply == 2


def test_the_stacks_are_a_chance_step_that_replays_exactly() -> None:
    """The shuffle goes through the chance stream, as every setup shuffle, so a
    recorded stream rebuilds the same state and another seed shuffles anew."""

    first = create_initial_state(IX, 5, LEADERS)
    outcome = next(
        outcome
        for outcome in first.chance_outcomes
        if outcome.decision_id == TECH_DECISION_ID
    )
    assert sorted(outcome.values) == sorted(IX_TECH_IDS)
    assert first.state.tech_stacks == deal_ix_tech_stacks(outcome.values)
    assert outcome == ChanceResolver(seed=0, recorded=(outcome,)).resolve(
        ix_tech_tiles_decision()
    )
    replayed = create_initial_state(
        IX, 999, LEADERS, recorded_outcomes=first.chance_outcomes
    )
    assert replace(replayed.state, seed=first.state.seed) == first.state
    other = create_initial_state(IX, 6, LEADERS).state
    assert other.tech_stacks != first.state.tech_stacks
    assert Counter(tile for stack in other.tech_stacks for tile in stack) == Counter(
        IX_TECH_IDS
    )


def test_the_other_chance_steps_keep_their_order() -> None:
    """Rise of Ix adds one shuffle (after the expansions' decisions, before the
    starting decks'), so the chance stream of the original game is this one's
    without it."""

    plain = tuple(
        outcome.decision_id
        for outcome in create_initial_state(ORIGINAL, 5, LEADERS).chance_outcomes
    )
    ix = tuple(
        outcome.decision_id
        for outcome in create_initial_state(IX, 5, LEADERS).chance_outcomes
    )
    assert ix.count(TECH_DECISION_ID) == 1
    assert (
        tuple(decision_id for decision_id in ix if decision_id != TECH_DECISION_ID)
        == plain
    )


@pytest.mark.parametrize("seed", range(6))
def test_the_conflict_deck_is_one_i_five_ii_four_iii_from_the_ix_pool(
    seed: int,
) -> None:
    """rise-of-ix.md 3 item 3: the deck keeps the original's shape (I 1, II 5,
    III 4) drawn from a pool that holds Rise of Ix's Conflicts, the rest
    unused (`[Rise of Ix p. 3]`)."""

    state = _setup(seed=seed)
    deck = _deck(state)
    tiers = tuple(CONFLICTS_BY_ID[card_id].tier for card_id in deck)
    assert tiers == (
        (ConflictTier.ONE,) + (ConflictTier.TWO,) * 5 + (ConflictTier.THREE,) * 4
    )
    pool = {conflict.card.card_id for conflict in content_for(IX).conflict_pool}
    assert "economic_supremacy" in pool
    assert set(deck) | set(state.unused_conflict_ids) == pool
    assert not set(deck) & set(state.unused_conflict_ids)
    assert len(state.unused_conflict_ids) == len(pool) - 10 == 12


def test_the_unused_conflicts_are_twelve_of_the_printed_22() -> None:
    """The printed deck is I 6, II 11, III 5 (22 cards): 12 stay in the box
    (rise-of-ix.md 3 item 3, `[Rise of Ix p. 3]`). The pool holds all 22 since
    Rise of Ix's three Conflicts are transcribed (stage P4d-1), so the check
    takes exactly 12."""

    deck = tuple(f"deck_{index}" for index in range(10))

    def unused(count: int) -> tuple[str, ...]:
        return tuple(f"unused_{index}" for index in range(count))

    ConflictSetup(deck=deck, unused=unused(12), rise_of_ix=True)
    for count in (6, 8, 9, 10, 11, 13):
        with pytest.raises(ValueError, match="twelve"):
            ConflictSetup(deck=deck, unused=unused(count), rise_of_ix=True)
    # Without Rise of Ix the original's 8 stand and 12 is refused.
    ConflictSetup(deck=deck, unused=unused(8))
    with pytest.raises(ValueError, match="six"):
        ConflictSetup(deck=deck, unused=unused(12))


@pytest.mark.parametrize("seed", range(6))
def test_a_rise_of_ix_setup_leaves_twelve_conflicts_unused(seed: int) -> None:
    """The pool is I 6, II 11, III 5 and the ten-card deck takes I 1, II 5,
    III 4 from it, so the setup returns exactly 12 to the box."""

    state = _setup(seed=seed)
    pool = content_for(IX).conflict_pool
    assert [
        sum(c.tier is tier for c in pool) for tier in ConflictTier
    ] == [6, 11, 5]
    assert len(state.unused_conflict_ids) == 12
    assert len(_deck(state)) == 10


def test_the_draft_setup_deals_the_same_ix_state() -> None:
    fixed = _setup(seed=5)
    draft = create_draft_initial_state(IX_DRAFT, 5).state
    assert len(draft.unused_conflict_ids) == len(fixed.unused_conflict_ids)
    assert tuple(len(stack) for stack in draft.tech_stacks) == (6, 6, 6)
    assert all(player.freighter_space == 0 for player in draft.players)


def test_uprising_with_rise_of_ix_is_still_refused() -> None:
    """Uprising plus Rise of Ix is stage P7 (rise-of-ix.md 1; ``[Main p. 18]``)."""

    for config in (
        RulesetConfig(rise_of_ix=True),
        RulesetConfig(rise_of_ix=True, leader_draft=True),
    ):
        with pytest.raises(NotImplementedError, match="Rise of Ix has no content"):
            UprisingRulesEngine().reset(config, 0)


def test_epic_game_mode_on_the_original_game_is_still_refused() -> None:
    config = replace(IX, epic_game=True)
    with pytest.raises(NotImplementedError, match="epic_game from stage P4"):
        UprisingRulesEngine().reset(config, 0)


@pytest.mark.parametrize("policy", ["random", "heuristic"])
@pytest.mark.parametrize("config", (IX, IX_DRAFT), ids=("fixed", "draft"))
def test_an_original_game_with_rise_of_ix_finishes_under_every_invariant(
    config: RulesetConfig, policy: str
) -> None:
    """A short engine-driven game, every seat the same scripted policy: the
    sweep checks dreadnoughts (two a seat), Negotiators among the 12 troops,
    the 18 Tech tiles conserved, the known Intrigue, the codec round trip of
    every advertised action (``soundness_interval``) and the replay."""

    report = run_checked_game(
        config,
        4,
        700_004,
        policy=policy,
        soundness_interval=25,
        collect_coverage=True,
    )
    assert report.winner is not None
    assert report.coverage is not None
    events = report.coverage["event_kinds"]
    if policy == "heuristic":
        # The scripted seat takes the Ix pieces rather than leaving them.
        for kind in ("tech_acquired", "dreadnought_commissioned", "freighter_moved"):
            assert events.get(kind, 0) > 0, kind


def test_the_ix_leaders_are_held_back_from_every_way_a_game_offers_leaders() -> None:
    """The six Ix Leaders have no setup or abilities until stage P4e (plan 17.10
    "P4c-5 Codex 리뷰" (1); ``rulesets.IX_LEADER_IDS_OFFERED``), so a game with
    Rise of Ix offers the original eight: Yuna would start with water 1 where
    docs/rules/rise-of-ix.md 3 prints 0 (`[Rise of Ix p. 3]`). A fixed roster
    naming one is refused, the draft's six face-up Leaders come from the eight,
    and a rotated roster draws from them."""

    ix_leader = "princess_yuna_moritani"
    with pytest.raises(ValueError, match="not available in this ruleset"):
        create_initial_state(IX, 5, (*LEADERS[:3], ix_leader))
    decision = leader_draft_pool_decision(IX_DRAFT)
    assert decision.options == IMPERIUM_LEADER_IDS
    for seed in range(1, 21):
        pool = next(
            outcome
            for outcome in create_draft_initial_state(IX_DRAFT, seed).chance_outcomes
            if outcome.decision_id == decision.decision_id
        )
        assert len(pool.values) == 6
        assert set(pool.values) <= set(IMPERIUM_LEADER_IDS)
    specs = sweep_specs(
        games=20,
        rulesets=(False,),
        start_seed=1,
        rotate_leaders=True,
        base_game=BaseGame.IMPERIUM,
        rise_of_ix=True,
    )
    for spec in specs:
        assert spec.leader_ids is not None
        assert set(spec.leader_ids) <= set(IMPERIUM_LEADER_IDS)
