"""What ``content_for`` returns for the original game with Rise of Ix.

docs/base-game-and-ix-plan.md 17.1 and 17.7 (stage P4a, the board axis): with
``rise_of_ix`` the original game's content takes the CHOAM overlay's four
spaces for four of its own (docs/rules/rise-of-ix.md 3 item 1, 8), the three
new Conflict cards and Economic Supremacy (3 item 3, 12), the six new Leaders
once their abilities are wired (3 item 4, 10; held back until stage P4e) and
the Ix cards whose play data is complete. It adds no rules itself; setup takes
the option on the original game from stage P4c-5
(``tests/unit/rules/test_ix_setup.py``) and still refuses it with Uprising
(stage P7).
"""

from dataclasses import replace
from typing import Any

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters.observation_encoding import LEADER_IDS
from dune_imperium.content import rulesets
from dune_imperium.content.imperium.board import IMPERIUM_BOARD_SPACES
from dune_imperium.content.imperium.conflicts import IMPERIUM_CONFLICTS
from dune_imperium.content.imperium.imperium import IMPERIUM_BASE_CARDS
from dune_imperium.content.imperium.intrigue import IMPERIUM_INTRIGUE_CARDS
from dune_imperium.content.rise_of_ix.board import IX_BOARD_SPACES
from dune_imperium.content.rise_of_ix.conflicts import IX_CONFLICTS
from dune_imperium.content.rise_of_ix.imperium import IX_IMPERIUM_CARDS
from dune_imperium.content.rise_of_ix.intrigue import IX_INTRIGUE_CARDS
from dune_imperium.content.rise_of_ix.leaders import IX_LEADERS
from dune_imperium.content.rulesets import (
    IMPERIUM_LEADER_IDS,
    IX_LEADER_IDS_OFFERED,
    IX_OVERLAID_SPACE_IDS,
    RulesetContent,
    content_for,
)
from dune_imperium.content.uprising.board import BOARD_SPACES
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.uprising.leaders import LEADERS_BY_ID
from dune_imperium.content.uprising.types import AgentIcon, ConflictTier
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.setup import conflict_setup_decisions

# The option combinations the original game plays with at P4a: Rise of Ix
# alone, with the promos, with the Leader draft, and with both.
_IX_OPTIONS: tuple[dict[str, bool], ...] = (
    {},
    {"promo_cards": True},
    {"leader_draft": True},
    {"promo_cards": True, "leader_draft": True},
)


def _ix(**options: Any) -> RulesetContent:
    return content_for(
        RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True, **options)
    )


def _plain(**options: Any) -> RulesetContent:
    return content_for(RulesetConfig(base_game=BaseGame.IMPERIUM, **options))


def _ids(content: RulesetContent) -> list[str]:
    return [space.space_id for space in content.board_spaces]


@pytest.mark.parametrize("options", _IX_OPTIONS, ids=lambda options: str(options))
def test_the_overlay_swaps_four_board_spaces(options: dict[str, Any]) -> None:
    """rise-of-ix.md 3 item 1, `[Rise of Ix p. 3]`: the CHOAM overlay covers
    the original Landsraad and CHOAM sections, and the app removes Hall of
    Oratory, Rally Troops, Secure Contract and Sell Melange and adds the four
    spaces of 8 (`[Rise of Ix p. 12]`): Dreadnought, Tech Negotiation,
    Interstellar Shipping and Smuggling. Mentat, Swordmaster and High Council
    stay."""

    content = _ix(**options)
    original = [space.space_id for space in IMPERIUM_BOARD_SPACES]
    assert len(original) == 22
    assert IX_OVERLAID_SPACE_IDS == (
        "hall_of_oratory",
        "rally_troops",
        "secure_contract",
        "sell_melange",
    )
    assert content.base_game is BaseGame.IMPERIUM
    # The original order with the four removed, then the overlay's four in
    # the order it prints them: 22 - 4 + 4.
    assert _ids(content) == [
        *(space_id for space_id in original if space_id not in IX_OVERLAID_SPACE_IDS),
        "dreadnought",
        "tech_negotiation",
        "interstellar_shipping",
        "smuggling",
    ]
    assert len(content.board_spaces) == 22
    assert not set(IX_OVERLAID_SPACE_IDS) & set(_ids(content))
    assert {"mentat", "imperium_swordmaster", "imperium_high_council"} <= set(
        _ids(content)
    )
    assert content.board_spaces[-4:] == IX_BOARD_SPACES
    # Every other space is the original board's own definition.
    assert content.board_spaces[:-4] == tuple(
        space
        for space in IMPERIUM_BOARD_SPACES
        if space.space_id not in IX_OVERLAID_SPACE_IDS
    )


def test_the_overlay_spaces_are_those_of_the_table() -> None:
    """rise-of-ix.md 8, `[Rise of Ix p. 12]`: Dreadnought and Tech
    Negotiation print the Landsraad icon, Interstellar Shipping and Smuggling
    the Spice Trade icon; none is a Combat space and the board's Maker spaces
    stay the original's."""

    spaces = {space.space_id: space for space in _ix().board_spaces}
    assert [
        spaces[space_id].agent_icon
        for space_id in (
            "dreadnought",
            "tech_negotiation",
            "interstellar_shipping",
            "smuggling",
        )
    ] == [
        AgentIcon.LANDSRAAD,
        AgentIcon.LANDSRAAD,
        AgentIcon.SPICE_TRADE,
        AgentIcon.SPICE_TRADE,
    ]
    assert not any(
        spaces[space_id].combat
        for space_id in (
            "dreadnought",
            "tech_negotiation",
            "interstellar_shipping",
            "smuggling",
        )
    )
    assert _ix().maker_space_ids == _plain().maker_space_ids


def _printed_tiers() -> list[int]:
    """The printed composition of the Conflict cards the original game with
    Rise of Ix draws from, by tier, counted from the definitions: the
    original 18 plus Rise of Ix's table plus Economic Supremacy."""

    printed = (
        *IMPERIUM_CONFLICTS,
        *IX_CONFLICTS,
        CONFLICTS_BY_ID["economic_supremacy"],
    )
    return [sum(c.tier is tier for c in printed) for tier in ConflictTier]


def test_the_printed_conflict_cards_are_i_6_ii_11_iii_5() -> None:
    """rise-of-ix.md 3 item 3, `[Rise of Ix p. 3]`: "Add the new Conflict
    cards to those you already have", so the tiers are drawn from I 6, II 11
    and III 5: the original's I 4, II 10 and III 4 (docs/rules/imperium-base.md,
    `[DI p. 3]`) plus Rise of Ix's four, I 2, II 1 and III 1
    (rise-of-ix.md 2, `[Rise of Ix p. 2]`), the one III being Economic
    Supremacy (12)."""

    assert [
        sum(c.tier is tier for c in IMPERIUM_CONFLICTS) for tier in ConflictTier
    ] == [
        4,
        10,
        4,
    ]
    assert [sum(c.tier is tier for c in IX_CONFLICTS) for tier in ConflictTier] == [
        2,
        1,
        0,
    ]
    assert CONFLICTS_BY_ID["economic_supremacy"].tier is ConflictTier.THREE
    assert _printed_tiers() == [6, 11, 5]
    assert [conflict.card.card_id for conflict in IX_CONFLICTS] == [
        "skirmish_e",
        "skirmish_f",
        "trade_monopoly",
    ]


@pytest.mark.parametrize("options", _IX_OPTIONS, ids=lambda options: str(options))
def test_the_conflict_pool_takes_the_transcribed_ix_cards_and_economic_supremacy(
    options: dict[str, Any],
) -> None:
    """rise-of-ix.md 3 item 3 and 12, `[Rise of Ix p. 3]`: the pool is the
    original 18, the Ix Conflicts whose rewards are transcribed (they join as
    ``reward_rows`` is filled, as a deck card joins with its play data) and
    Economic Supremacy, Rise of Ix's Conflict III, Epic Game Mode or not. Tier
    by tier: the original cards, then Rise of Ix's in printed order."""

    content = _ix(**options)
    transcribed = [c for c in IX_CONFLICTS if c.reward_rows is not None]
    economic = CONFLICTS_BY_ID["economic_supremacy"]
    for tier in ConflictTier:
        assert content.conflicts_by_tier(tier) == (
            *(c for c in IMPERIUM_CONFLICTS if c.tier is tier),
            *(c for c in transcribed if c.tier is tier),
            *((economic,) if economic.tier is tier else ()),
        )
    expected = len(IMPERIUM_CONFLICTS) + len(transcribed) + 1
    assert len(content.conflict_pool) == expected
    # All of Rise of Ix's three are transcribed since stage P4d-1, so the pool
    # is the printed I 6, II 11, III 5 [Rise of Ix p. 3] (22 cards).
    assert len(transcribed) == len(IX_CONFLICTS) == 3
    assert [len(content.conflicts_by_tier(tier)) for tier in ConflictTier] == [
        6,
        11,
        5,
    ]
    # The universe is the pool: every Conflict the engine plays here.
    assert content.conflicts == content.conflict_pool
    assert len({c.card.card_id for c in content.conflicts}) == expected
    assert "economic_supremacy" in {c.card.card_id for c in content.conflicts}
    # Economic Supremacy is in the pool, Epic or not, and Epic adds nothing.
    epic = _ix(epic_game=True, **options)
    assert epic.conflict_pool == content.conflict_pool
    assert epic.conflicts_in_play() == content.conflicts_in_play() == content.conflicts
    # The original game without Rise of Ix: I 4, II 10, III 4.
    assert [len(_plain().conflicts_by_tier(tier)) for tier in ConflictTier] == [
        4,
        10,
        4,
    ]


def test_an_ix_conflict_joins_the_pool_once_its_rewards_are_transcribed() -> None:
    """The pool follows ``reward_rows``: a card of Rise of Ix's table with
    transcribed rewards is in the original game's pool and universe, one
    without is not (the action codec reads every listed Conflict's rewards)."""

    pool = {c.card.card_id for c in _ix().conflict_pool}
    for conflict in IX_CONFLICTS:
        assert (conflict.card.card_id in pool) is (conflict.reward_rows is not None)
    for conflict in _ix().conflicts:
        assert conflict.reward_rows is not None


def test_the_ix_deck_keeps_the_shape_of_the_original() -> None:
    """rise-of-ix.md 3 item 3, `[Rise of Ix p. 3]`: "you should have a
    10-card deck with one Conflict I card on top, five Conflict II cards below
    it, then four Conflict III cards on the bottom"; one Conflict III remains
    and returns to the box. Epic Game Mode (11, `[Rise of Ix p. 10]`) uses
    five Conflict II over all five Conflict III."""

    config = RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True)
    content = content_for(config)
    assert [
        (decision.decision_id, decision.options, decision.count)
        for decision in conflict_setup_decisions(config)
    ] == [
        (
            f"setup:conflict:tier:{tier.value}",
            tuple(c.card.card_id for c in content.conflicts_by_tier(tier)),
            count,
        )
        for tier, count in (
            (ConflictTier.THREE, 4),
            (ConflictTier.TWO, 5),
            (ConflictTier.ONE, 1),
        )
    ]
    # Economic Supremacy is one of the five Conflict III the deck draws four of.
    (three,) = (
        decision
        for decision in conflict_setup_decisions(config)
        if decision.decision_id == "setup:conflict:tier:3"
    )
    assert len(three.options) == 5
    assert "economic_supremacy" in three.options
    epic = replace(config, epic_game=True)
    assert [
        (decision.decision_id, decision.count)
        for decision in conflict_setup_decisions(epic)
    ] == [("setup:conflict:tier:3", 5), ("setup:conflict:tier:2", 5)]
    for decision in conflict_setup_decisions(epic):
        assert len(decision.options) >= decision.count


_IX_LEADER_IDS = (
    "archduke_armand_ecaz",
    "ilesa_ecaz",
    "prince_rhombur_vernius",
    "princess_yuna_moritani",
    "tessia_vernius",
    "viscount_hundro_moritani",
)


# The Ix Leaders stage P4e has wired so far, one commit each (setup, Leader
# ability and Signet Ring with their tests): "Princess" Yuna Moritani.
_WIRED_IX_LEADER_IDS = frozenset({"princess_yuna_moritani"})


@pytest.mark.parametrize("options", _IX_OPTIONS, ids=lambda options: str(options))
def test_the_leaders_offered_hold_back_the_ix_leaders_not_yet_wired(
    options: dict[str, Any],
) -> None:
    """rise-of-ix.md 3 item 4, `[Rise of Ix p. 3]`: "Add the 6 new Leaders to
    those you already have. When taking Leaders, players may choose any
    combination of new or existing Leaders." The six (10, `[Rise of Ix p. 2]`)
    join the offer one by one as stage P4e wires each one's setup and
    abilities (``rulesets.IX_LEADER_IDS_OFFERED``, plan 17.10 "P4c-5 Codex
    리뷰" (1)): a Leader joins once its abilities are complete, as a deck card
    joins once its play data is. Until then it is held back; without Rise of
    Ix the offer is the original game's eight."""

    content = _ix(**options)
    wired = [leader for leader in _IX_LEADER_IDS if leader in _WIRED_IX_LEADER_IDS]
    assert [leader.leader_id for leader in content.leaders] == [
        *IMPERIUM_LEADER_IDS,
        *wired,
    ]
    assert len(content.leaders) == 8 + len(wired)
    held = set(_IX_LEADER_IDS) - _WIRED_IX_LEADER_IDS
    assert not held & {leader.leader_id for leader in content.leaders}
    assert [leader.leader_id for leader in _plain(**options).leaders] == list(
        IMPERIUM_LEADER_IDS
    )
    assert IX_LEADER_IDS_OFFERED == _WIRED_IX_LEADER_IDS
    # Held back from the offer only: the six stay defined, found by id and in
    # the observation's vocabulary.
    assert tuple(leader.leader_id for leader in IX_LEADERS) == _IX_LEADER_IDS
    for leader in IX_LEADERS:
        assert LEADERS_BY_ID[leader.leader_id] is leader
        assert leader.leader_id in LEADER_IDS


def test_a_leader_joins_the_offer_once_it_is_on_the_offered_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The switch P4e flips: an Ix Leader on ``IX_LEADER_IDS_OFFERED`` follows
    the original eight in printed order, with Rise of Ix only (the uncached
    builder, so the cached contents other tests share stay untouched)."""

    build = rulesets._imperium_leaders.__wrapped__
    monkeypatch.setattr(
        rulesets,
        "IX_LEADER_IDS_OFFERED",
        frozenset({"princess_yuna_moritani", "ilesa_ecaz"}),
    )
    assert [leader.leader_id for leader in build(True)] == [
        *IMPERIUM_LEADER_IDS,
        "ilesa_ecaz",
        "princess_yuna_moritani",
    ]
    assert [leader.leader_id for leader in build(False)] == list(IMPERIUM_LEADER_IDS)
    monkeypatch.setattr(rulesets, "IX_LEADER_IDS_OFFERED", frozenset(_IX_LEADER_IDS))
    assert build(True)[-6:] == IX_LEADERS
    assert len(build(True)) == 14


@pytest.mark.parametrize("options", _IX_OPTIONS, ids=lambda options: str(options))
def test_the_decks_take_the_ix_cards_whose_play_data_is_complete(
    options: dict[str, Any],
) -> None:
    """rise-of-ix.md 3 item 4, `[Rise of Ix p. 3]`: the 17 Intrigue and the 35
    Imperium cards are shuffled into their decks (the Imperium cards before
    the Row is formed); rise-of-ix.md 1 puts Boundless Ambition behind
    ``promo_cards``. The engine's decks hold only the cards whose play data is
    transcribed (plan 16.1, 17.1), so the lists follow that flag and are the
    original game's own until an Ix card is completed."""

    content = _ix(**options)
    promos = options.get("promo_cards", False)
    imperium = tuple(
        entry
        for entry in (*IMPERIUM_BASE_CARDS, *IX_IMPERIUM_CARDS)
        if entry.play_data_complete and (promos or not entry.promo)
    )
    assert content.imperium_cards == imperium
    assert content.imperium_deck_instance_ids == tuple(
        f"imperium:{entry.card.card_id}:{copy}"
        for entry in imperium
        for copy in range(entry.copies)
    )
    assert content.intrigue_deck_instance_ids == tuple(
        f"intrigue:{entry.card.card_id}:{copy}"
        for entry in (*IMPERIUM_INTRIGUE_CARDS, *IX_INTRIGUE_CARDS)
        if entry.play_data_complete
        for copy in range(entry.copies)
    )
    assert content.card_ids == _plain(**options).card_ids | {
        entry.card.card_id for entry in IX_IMPERIUM_CARDS if entry.play_data_complete
    }
    # No identity-only Ix card is dealt.
    assert all(entry.play_data_complete for entry in content.imperium_cards)
    # No Ix card is complete yet, so the decks are the original game's.
    if not any(entry.play_data_complete for entry in IX_IMPERIUM_CARDS):
        assert content.imperium_cards == _plain(**options).imperium_cards
    if not any(entry.play_data_complete for entry in IX_INTRIGUE_CARDS):
        assert (
            content.intrigue_deck_instance_ids
            == _plain(**options).intrigue_deck_instance_ids
        )


@pytest.mark.parametrize("options", _IX_OPTIONS, ids=lambda options: str(options))
def test_nothing_else_of_the_original_game_changes(options: dict[str, Any]) -> None:
    """Stage P4a's slice is the board, Conflicts, Leaders and decks: the
    Reserve, the Maker spaces, the Control and Influence 4 bonuses, the
    starting deck and the tables the original game prints empty (no
    observation post [DI p. 14], Objective, Contract or sandworm) are the
    original game's own. Tech stacks, dreadnought supply, Freighters and
    Snooper tokens are later stages."""

    ix = _ix(**options)
    plain = _plain(**options)
    assert replace(ix, config=plain.config) == replace(
        plain,
        board_spaces=ix.board_spaces,
        conflicts=ix.conflicts,
        conflict_pool=ix.conflict_pool,
        leaders=ix.leaders,
        card_ids=ix.card_ids,
        imperium_cards=ix.imperium_cards,
        imperium_deck_instance_ids=ix.imperium_deck_instance_ids,
        # The Ix cards shuffled in as their play data lands (stage
        # P4d); ``test_the_decks_take_the_ix_cards_whose_play_data_is_complete``
        # checks the deck itself.
        intrigue_deck_instance_ids=ix.intrigue_deck_instance_ids,
    )
    assert ix.reserve_stacks == plain.reserve_stacks
    for table in (
        ix.observation_posts,
        ix.contract_instance_ids,
        ix.objectives,
        ix.sandworm_space_ids,
    ):
        assert table == ()


@pytest.mark.parametrize("options", _IX_OPTIONS, ids=lambda options: str(options))
def test_the_original_game_without_ix_is_unchanged(options: dict[str, Any]) -> None:
    """Without ``rise_of_ix`` the original game keeps its 22 spaces (the four
    the overlay covers included) [DI pp. 17-18], its 18 Conflicts (I 4, II 10,
    III 4 [DI p. 3]) and its eight Leaders (docs/rules/imperium-base.md)."""

    plain = _plain(**options)
    assert plain.board_spaces is IMPERIUM_BOARD_SPACES
    assert len(plain.board_spaces) == 22
    assert set(IX_OVERLAID_SPACE_IDS) <= set(_ids(plain))
    assert not {space.space_id for space in IX_BOARD_SPACES} & set(_ids(plain))
    assert plain.conflicts is IMPERIUM_CONFLICTS
    assert plain.conflict_pool is IMPERIUM_CONFLICTS
    assert len(plain.conflicts) == 18
    assert [leader.leader_id for leader in plain.leaders] == list(IMPERIUM_LEADER_IDS)
    ix_ids = {c.card.card_id for c in IX_CONFLICTS} | {"economic_supremacy"}
    assert not ix_ids & {c.card.card_id for c in plain.conflicts}
    assert not {leader.leader_id for leader in IX_LEADERS} & {
        leader.leader_id for leader in plain.leaders
    }


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"choam_module": True},
        {"bloodlines": True, "tech_module": True},
        {"epic_game": True},
        {"immortality": True, "promo_cards": True},
    ],
    ids=lambda options: str(options),
)
def test_uprising_content_does_not_see_rise_of_ix(options: dict[str, Any]) -> None:
    """Uprising plus Rise of Ix is stage P7 (`[Main p. 18]`, "Adding Rise of
    Ix"; plan 17.5 item 1), so its content is Uprising's own tables whatever
    ``rise_of_ix`` says: the board, the Conflicts and the Leaders hold no Ix
    entry."""

    plain = RulesetConfig(**options)
    with_ix = RulesetConfig(rise_of_ix=True, **options)
    assert replace(content_for(with_ix), config=plain) == content_for(plain)
    content = content_for(with_ix)
    assert content.base_game is BaseGame.UPRISING
    assert content.board_spaces is BOARD_SPACES
    assert not {space.space_id for space in IX_BOARD_SPACES} & set(_ids(content))
    assert not {conflict.card.card_id for conflict in IX_CONFLICTS} & {
        conflict.card.card_id for conflict in content.conflict_pool
    }
    assert not {leader.leader_id for leader in IX_LEADERS} & {
        leader.leader_id for leader in content.leaders
    }


@pytest.mark.parametrize("options", _IX_OPTIONS, ids=lambda options: str(options))
def test_setup_takes_rise_of_ix_on_the_original_game_only(
    options: dict[str, Any],
) -> None:
    """The original game plays Rise of Ix from stage P4c-5 (plan 15.4, 17.10
    item 5); Uprising plus Rise of Ix stays refused until stage P7."""

    config = RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True, **options)
    state = UprisingRulesEngine().reset(config, 0)
    assert state.config.rise_of_ix
    with pytest.raises(NotImplementedError, match="Rise of Ix has no content"):
        UprisingRulesEngine().reset(RulesetConfig(rise_of_ix=True, **options), 0)
