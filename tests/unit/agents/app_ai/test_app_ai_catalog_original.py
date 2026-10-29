"""The catalog of the original Dune: Imperium game (``BaseGame.IMPERIUM``).

Every original card, Intrigue card, Conflict, Leader and board space maps to
the app's ``BaseSet`` archetype of the same card (the three base-game promos to
the app's ``Promo`` ones); the original board's space lookups follow the app's
``Is…Space`` predicates. The P3d app comparison matched the same 138 items by
hand (assets ``analysis/p3d-compare-2026-10-28/dossiers``).
"""

import re

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.catalog import (
    CARD_ARCHETYPES,
    CONFLICT_ARCHETYPES,
    INTRIGUE_ARCHETYPES,
    LEADER_ARCHETYPES,
    ORIGINAL_CARD_ARCHETYPES,
    ORIGINAL_CONFLICT_ARCHETYPES,
    ORIGINAL_INTRIGUE_ARCHETYPES,
    ORIGINAL_LEADER_ARCHETYPES,
    ORIGINAL_SPACE_ARCHETYPES,
    SPACE_ARCHETYPES,
    board_space_ids,
    board_space_where,
    heighliner_space_id,
    high_council_space_id,
    is_board_space,
    space_entity,
    swordmaster_space_id,
)
from dune_imperium.agents.app_ai.context import Board
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES
from dune_imperium.agents.app_ai.windows.turn import board_space_order
from dune_imperium.config import BaseGame
from dune_imperium.content.imperium.imperium import IMPERIUM_BASE_CARDS
from dune_imperium.content.imperium.intrigue import IMPERIUM_INTRIGUE_CARDS
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.types import AgentIcon

ORIGINAL = RulesetConfig(base_game=BaseGame.IMPERIUM, promo_cards=True)
CONTENT = content_for(ORIGINAL)
BOARD = Board.of(ORIGINAL)

APP_ICONS = {
    "Emperor": AgentIcon.EMPEROR,
    "SpacingGuild": AgentIcon.SPACING_GUILD,
    "BeneGesserit": AgentIcon.BENE_GESSERIT,
    "Fremen": AgentIcon.FREMEN,
    "Pentagon": AgentIcon.LANDSRAAD,
    "Circle": AgentIcon.CITY,
    "Triangle": AgentIcon.SPICE_TRADE,
}


def _norm(text: str) -> str:
    """Tags, case and punctuation folded, as titles are compared."""

    return re.sub(r"[^a-z0-9]", "", re.sub(r"<[^>]+>", "", text).lower())


def _title(short: str) -> str:
    title = ARCHETYPES[short].title
    assert title is not None, short
    return _norm(title)


def test_the_original_tables_are_merged_into_the_lookups() -> None:
    for table, merged in (
        (ORIGINAL_CARD_ARCHETYPES, CARD_ARCHETYPES),
        (ORIGINAL_INTRIGUE_ARCHETYPES, INTRIGUE_ARCHETYPES),
        (ORIGINAL_LEADER_ARCHETYPES, LEADER_ARCHETYPES),
    ):
        assert table.items() <= merged.items()
    assert ORIGINAL_CONFLICT_ARCHETYPES.items() <= CONFLICT_ARCHETYPES.items()


def test_every_original_card_maps_to_the_apps_base_set_card() -> None:
    reserve = {stack.card.card_id: stack for stack in CONTENT.reserve_stacks}
    imperium = {entry.card.card_id: entry for entry in IMPERIUM_BASE_CARDS}
    assert set(ORIGINAL_CARD_ARCHETYPES) == set(reserve) | set(imperium)
    for card_id, short in ORIGINAL_CARD_ARCHETYPES.items():
        archetype = ARCHETYPES[short]
        entry = reserve.get(card_id) or imperium[card_id]
        assert _title(short) == _norm(entry.card.name), card_id
        assert archetype.attributes.get("CardCount", entry.copies) == entry.copies
        assert ".BaseSet." in short or (
            ".Promo." in short
            and card_id in {"duncan_loyal_blade", "jessica_of_arrakis", "thumper"}
        ), card_id
    # The starting deck is the BaseSet one the Uprising tables already hold.
    for starter in CONTENT.starting_deck_entries:
        assert CARD_ARCHETYPES[starter.card.card_id].startswith(
            "ImperiumArchetypes.BaseSet."
        )


def test_every_original_intrigue_maps_to_the_apps_base_set_card() -> None:
    assert set(ORIGINAL_INTRIGUE_ARCHETYPES) == {
        card.card.card_id for card in IMPERIUM_INTRIGUE_CARDS
    }
    for card in IMPERIUM_INTRIGUE_CARDS:
        short = ORIGINAL_INTRIGUE_ARCHETYPES[card.card.card_id]
        assert short.startswith("IntrigueArchetypes.BaseSet.")
        assert _title(short) == _norm(card.card.name)
        assert ARCHETYPES[short].attributes["CardCount"] == card.copies


def test_every_original_conflict_maps_to_the_apps_card_of_its_level() -> None:
    pool = {conflict.card.card_id: conflict for conflict in CONTENT.conflict_pool}
    assert set(ORIGINAL_CONFLICT_ARCHETYPES) == set(pool)
    for conflict_id, (without, with_choam) in ORIGINAL_CONFLICT_ARCHETYPES.items():
        assert without == with_choam
        conflict = pool[conflict_id]
        assert without.startswith("ConflictArchetypes.BaseSet.")
        assert _title(without) == _norm(conflict.card.name)
        assert ARCHETYPES[without].attributes["ConflictLevel"] == conflict.tier.value
    # The four Skirmishes: A and B pay 1 VP first (the app's ``VictoryPoints``).
    for letter, vp in (("a", 1), ("b", 1), ("c", 0), ("d", 0)):
        short = ORIGINAL_CONFLICT_ARCHETYPES[f"skirmish_{letter}"][0]
        assert short.endswith(f"Skirmish{letter.upper()}")
        assert ARCHETYPES[short].attributes.get("VictoryPoints", 0) == vp


def test_every_original_leader_maps_to_the_apps_base_set_leader() -> None:
    assert set(ORIGINAL_LEADER_ARCHETYPES) == {
        leader.leader_id for leader in CONTENT.leaders
    }
    for leader in CONTENT.leaders:
        short = ORIGINAL_LEADER_ARCHETYPES[leader.leader_id]
        assert short.startswith("LeaderArchetypes.BaseSet.")
        assert _title(short) == _norm(leader.name)


def test_the_original_board_is_the_apps_base_set_board() -> None:
    assert BOARD.original
    assert not Board.of(RulesetConfig()).original
    spaces = CONTENT.board_spaces
    assert board_space_ids(BOARD) == tuple(space.space_id for space in spaces)
    assert set(ORIGINAL_SPACE_ARCHETYPES.values()) == {
        short for short in ARCHETYPES if short.startswith("SpaceArchetypes.BaseSet.")
    }
    for space in spaces:
        entity = space_entity(space.space_id, BOARD)
        assert entity.short == ORIGINAL_SPACE_ARCHETYPES[space.space_id]
        assert entity.short is not None
        assert _title(entity.short) == _norm(space.name), space.space_id
        assert APP_ICONS[str(entity.attr("AgentIcon"))] is space.agent_icon
        assert (entity.attr("CombatSpace", False) is True) is space.combat
        assert is_board_space(space.space_id)
    # The app's ``BoardSpaces`` order: the BaseSet spaces in typedef order.
    order = board_space_order(BOARD)
    assert set(order) == set(ORIGINAL_SPACE_ARCHETYPES)
    assert order[:3] == ("arrakeen", "carthag", "conspire")


def test_the_space_predicates_find_each_boards_own_space() -> None:
    uprising = Board(choam=False)
    assert swordmaster_space_id(uprising) == "swordmaster"
    assert high_council_space_id(uprising) == "high_council"
    assert heighliner_space_id(uprising) == "heighliner"
    assert swordmaster_space_id(BOARD) == "imperium_swordmaster"
    assert high_council_space_id(BOARD) == "imperium_high_council"
    assert heighliner_space_id(BOARD) == "imperium_heighliner"
    # The Uprising-only Maker spaces are not on the original board.
    hagga = frozenset({"SpaceArchetypes.Uprising.HaggaBasinUP"})
    assert board_space_where(uprising, hagga) == "hagga_basin"
    assert board_space_where(BOARD, hagga) is None
    # Shared archetypes keep one id on both boards.
    for space_id in ("secrets", "arrakeen", "imperial_basin"):
        assert SPACE_ARCHETYPES[space_id][0] == ORIGINAL_SPACE_ARCHETYPES[space_id]
