"""Uprising with the original game's cards and Leaders (stage P7e).

docs/rules/imperium-base.md 13.4 ([Main p. 18] "COMBINING WITH BASE DUNE:
IMPERIUM"):

- "원판 Conflict 카드는 넣지 않기를 권한다 ... — 사용자 결정(2026-10-30, 계획
  19.4 P7-3 (가)): 넣지 않는다."
- "Uprising에는 Mentat가 없으므로 Calculated Hire Intrigue를 뺀다"
- "나머지 Intrigue·Imperium 카드는 Uprising 카드와 모두 섞거나 골라 섞는다. —
  사용자 결정(2026-10-30, 계획 19.4 P7-2 (가), OQ-155): 옵션 하나로 원판
  Imperium·Intrigue 전부(Calculated Hire 빼고)를 섞고 원판 지도자 여덟도 고를 수
  있게 한다. 원판 프로모는 `promo_cards`일 때 함께."
"""

from dataclasses import replace
from typing import Any

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.content.core.cards import ImperiumCardEntry, IntrigueCardEntry
from dune_imperium.content.core.schema import GameOption
from dune_imperium.content.imperium.imperium import IMPERIUM_BASE_CARDS
from dune_imperium.content.imperium.intrigue import IMPERIUM_INTRIGUE_CARDS
from dune_imperium.content.imperium.leaders import IMPERIUM_LEADERS
from dune_imperium.content.rulesets import content_for
from dune_imperium.core.state import GamePhase, _canonicalize
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.setup import create_initial_state, leader_draft_pool_decision

MIXED = RulesetConfig(imperium_cards=True)
ORIGINAL_LEADER_IDS = tuple(leader.leader_id for leader in IMPERIUM_LEADERS)


def _instances(
    prefix: str,
    entries: tuple[ImperiumCardEntry, ...] | tuple[IntrigueCardEntry, ...],
    *,
    promo: bool,
) -> set[str]:
    return {
        f"{prefix}:{entry.card.card_id}:{copy}"
        for entry in entries
        if promo or GameOption.PROMO_CARDS not in entry.requires
        for copy in range(entry.copies)
    }


def test_the_option_names_itself_in_the_identifier_and_is_off_by_default() -> None:
    assert RulesetConfig().imperium_cards is False
    assert MIXED.identifier == "uprising-4p-base+imperium-cards"
    config = RulesetConfig(
        choam_module=True,
        imperium_cards=True,
        promo_cards=True,
        bloodlines=True,
        immortality=True,
        epic_game=True,
        arrakeen_scouts=True,
    )
    assert config.identifier == (
        "uprising-4p-choam+imperium-cards+promo+bloodlines+immortality+epic+scouts"
    )
    assert RulesetConfig.from_identifier(config.identifier) == config
    assert RulesetConfig.from_identifier(MIXED.identifier) == MIXED
    # Every identifier without it stays what it was.
    assert RulesetConfig(promo_cards=True).identifier == "uprising-4p-base+promo"


def test_the_option_is_left_out_of_the_state_hash_at_its_default() -> None:
    # Saves and records made before the option keep their hashes
    # (RulesetConfig.HASH_OMITTED_AT_DEFAULT).
    assert "imperium_cards" not in _canonicalize(RulesetConfig())
    assert _canonicalize(MIXED)["imperium_cards"] is True


def test_the_original_game_refuses_the_option() -> None:
    # The option brings the original game's cards to Uprising [Main p. 18];
    # an original game holds them already.
    config = RulesetConfig(base_game=BaseGame.IMPERIUM, imperium_cards=True)
    with pytest.raises(NotImplementedError, match="does not take imperium_cards"):
        UprisingRulesEngine().reset(config, 0)


def test_the_decks_hold_every_original_card_but_calculated_hire() -> None:
    plain = content_for(RulesetConfig())
    mixed = content_for(MIXED)
    assert mixed.original_cards and not plain.original_cards
    original_imperium = _instances("imperium", IMPERIUM_BASE_CARDS, promo=False)
    assert set(mixed.imperium_deck_instance_ids) == (
        set(plain.imperium_deck_instance_ids) | original_imperium
    )
    # 67 original cards [DI p. 3] beside Uprising's; no promo without the
    # option's promo_cards.
    assert len(original_imperium) == 67
    original_intrigue = _instances("intrigue", IMPERIUM_INTRIGUE_CARDS, promo=True)
    assert set(mixed.intrigue_deck_instance_ids) == set(
        plain.intrigue_deck_instance_ids
    ) | {card for card in original_intrigue if ":calculated_hire:" not in card}
    assert not any(":calculated_hire:" in c for c in mixed.intrigue_deck_instance_ids)
    # Uprising's board, Reserve, starting decks, Objectives and Conflicts
    # stay (P7-3 (가): no original Conflict card).
    for name in (
        "board_spaces",
        "observation_posts",
        "conflicts",
        "conflict_pool",
        "reserve_stacks",
        "objectives",
        "starting_deck_entries",
        "contract_instance_ids",
        "maker_space_ids",
        "sandworm_space_ids",
    ):
        assert getattr(mixed, name) == getattr(plain, name), name
    assert mixed.base_game is BaseGame.UPRISING


def test_the_original_promos_come_with_promo_cards() -> None:
    # "원판 프로모는 promo_cards일 때 함께" (imperium-base.md 13.4).
    mixed = content_for(MIXED)
    with_promos = content_for(replace(MIXED, promo_cards=True))
    promos = {
        "imperium:duncan_loyal_blade:0",
        "imperium:jessica_of_arrakis:0",
        "imperium:thumper:0",
    }
    assert not promos & set(mixed.imperium_deck_instance_ids)
    uprising_promos = set(
        content_for(RulesetConfig(promo_cards=True)).imperium_deck_instance_ids
    ) - set(content_for(RulesetConfig()).imperium_deck_instance_ids)
    assert set(with_promos.imperium_deck_instance_ids) - set(
        mixed.imperium_deck_instance_ids
    ) == promos | uprising_promos
    # Every card the game could hold is a card id of its catalog either way.
    assert {"duncan_loyal_blade", "thumper"} <= mixed.card_ids


@pytest.mark.parametrize(
    "options",
    [{}, {"choam_module": True}, {"bloodlines": True, "tech_module": True}],
    ids=["base", "choam", "bloodlines-tech"],
)
def test_the_eight_original_leaders_join_the_offer(options: dict[str, Any]) -> None:
    plain = content_for(RulesetConfig(**options))
    mixed = content_for(RulesetConfig(imperium_cards=True, **options))
    assert mixed.leaders == (*plain.leaders, *IMPERIUM_LEADERS)
    # The draft deals six of them all (OQ-007).
    pool = leader_draft_pool_decision(replace(mixed.config, leader_draft=True))
    assert set(ORIGINAL_LEADER_IDS) <= set(pool.options)


def test_an_uprising_game_seats_original_leaders() -> None:
    # The fixed roster takes the original Leaders: the Baron's secret
    # Factions open his setup choice as in an original game [FAQ p. 1].
    leaders = (
        "baron_vladimir_harkonnen",
        "earl_memnon_thorvald",
        "muad_dib",
        "paul_atreides",
    )
    setup = create_initial_state(MIXED, 3, leaders)
    state = setup.state
    assert tuple(seat.leader_id for seat in state.players) == leaders
    assert state.phase is GamePhase.SETUP
    assert state.shield_wall_present
    deck = {*state.imperium_deck, *state.imperium_row}
    assert any(card.startswith("imperium:kwisatz_haderach:") for card in deck)
    with pytest.raises(ValueError, match="not available in this ruleset"):
        create_initial_state(RulesetConfig(), 3, leaders)


def test_the_catalog_adds_the_original_rows_and_keeps_uprisings() -> None:
    # Every Uprising row stays, and every row of the original game's catalog
    # is there but those that name what only the original board prints (its
    # spaces, Mentat, Conflicts and Reserve) and Calculated Hire's.
    for promo in (False, True):
        plain = {
            (row.action_id, row.arguments)
            for row in ActionCodec(RulesetConfig(promo_cards=promo)).catalog
        }
        mixed = {
            (row.action_id, row.arguments)
            for row in ActionCodec(replace(MIXED, promo_cards=promo)).catalog
        }
        original_config = RulesetConfig(base_game=BaseGame.IMPERIUM, promo_cards=promo)
        original = {
            (row.action_id, row.arguments)
            for row in ActionCodec(original_config).catalog
        }
        assert plain <= mixed
        missing = {
            row
            for row in original - mixed
            if not _names_the_original_board(row[1], original_config)
        }
        assert missing == {
            ("choose_intrigue_card", (("card_id", "intrigue:calculated_hire:0"),))
        }


def _names_the_original_board(
    arguments: tuple[tuple[str, object], ...], original: RulesetConfig
) -> bool:
    """Whether a row names a space, Conflict or Reserve card only the original
    game prints, or its Mentat."""

    def ids(config: RulesetConfig) -> set[str]:
        content = content_for(config)
        return (
            {space.space_id for space in content.board_spaces}
            | {conflict.card.card_id for conflict in content.conflicts}
            | {stack.card.card_id for stack in content.reserve_stacks}
        )

    board_only = {"mentat", "foldspace_card"} | (ids(original) - ids(MIXED))
    return any(
        part in board_only for _, value in arguments for part in str(value).split(":")
    )
