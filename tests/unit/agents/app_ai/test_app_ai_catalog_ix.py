"""The catalog of Rise of Ix on the original board (docs/app-ai-plan.md §13).

Every Ix card, Intrigue card, Conflict, Leader, Tech tile and board space maps
to the app's ``RiseOfIx`` archetype of the same name (Boundless Ambition to
the app's Ix ``Promo``), and the Ix board is the app's: the original
``BaseSet`` spaces less the four whose ``RemovedFromSetList`` holds
``RiseOfIx``, then the four Ix spaces.
"""

import re
from collections.abc import Mapping

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.catalog import (
    CARD_ARCHETYPES,
    CONFLICT_ARCHETYPES,
    INTRIGUE_ARCHETYPES,
    IX_CARD_ARCHETYPES,
    IX_CONFLICT_ARCHETYPES,
    IX_COVERED_SPACE_IDS,
    IX_INTRIGUE_ARCHETYPES,
    IX_LEADER_ARCHETYPES,
    IX_SPACE_ARCHETYPES,
    IX_TECH_ARCHETYPES,
    LEADER_ARCHETYPES,
    ORIGINAL_SPACE_ARCHETYPES,
    TECH_ARCHETYPES,
    board_space_ids,
    is_board_space,
    space_entity,
)
from dune_imperium.agents.app_ai.context import Board
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES
from dune_imperium.agents.app_ai.windows.turn import board_space_order
from dune_imperium.config import BaseGame
from dune_imperium.content.rise_of_ix.board import IX_SPACE_IDS
from dune_imperium.content.rise_of_ix.conflicts import IX_CONFLICTS
from dune_imperium.content.rise_of_ix.imperium import IX_IMPERIUM_CARDS
from dune_imperium.content.rise_of_ix.intrigue import IX_INTRIGUE_CARDS
from dune_imperium.content.rise_of_ix.leaders import IX_LEADERS
from dune_imperium.content.rise_of_ix.tech import IX_TECH_IDS
from dune_imperium.content.rulesets import content_for

IX = RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True, promo_cards=True)
BOARD = Board.of(IX)


def _set_list(attributes: Mapping[str, object], name: str) -> tuple[object, ...]:
    value = attributes.get(name)
    return value if isinstance(value, tuple) else ()


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", re.sub(r"<[^>]+>", "", text).lower())


def test_the_ix_tables_cover_our_ix_content_and_are_merged() -> None:
    assert set(IX_CARD_ARCHETYPES) == {e.card.card_id for e in IX_IMPERIUM_CARDS}
    assert set(IX_INTRIGUE_ARCHETYPES) == {e.card.card_id for e in IX_INTRIGUE_CARDS}
    assert set(IX_CONFLICT_ARCHETYPES) == {c.card.card_id for c in IX_CONFLICTS}
    assert set(IX_LEADER_ARCHETYPES) == {leader.leader_id for leader in IX_LEADERS}
    assert set(IX_TECH_ARCHETYPES) == set(IX_TECH_IDS)
    assert set(IX_SPACE_ARCHETYPES) == set(IX_SPACE_IDS)
    for table, merged in (
        (IX_CARD_ARCHETYPES, CARD_ARCHETYPES),
        (IX_INTRIGUE_ARCHETYPES, INTRIGUE_ARCHETYPES),
        (IX_CONFLICT_ARCHETYPES, CONFLICT_ARCHETYPES),
        (IX_LEADER_ARCHETYPES, LEADER_ARCHETYPES),
        (IX_TECH_ARCHETYPES, TECH_ARCHETYPES),
    ):
        assert all(merged[key] == value for key, value in table.items())


@pytest.mark.parametrize(
    ("table", "kind", "names"),
    [
        (
            IX_CARD_ARCHETYPES,
            "imperium",
            {e.card.card_id: e.card.name for e in IX_IMPERIUM_CARDS},
        ),
        (
            IX_INTRIGUE_ARCHETYPES,
            "intrigue",
            {e.card.card_id: e.card.name for e in IX_INTRIGUE_CARDS},
        ),
        (
            IX_LEADER_ARCHETYPES,
            "leader",
            {leader.leader_id: leader.name for leader in IX_LEADERS},
        ),
    ],
)
def test_every_ix_entry_is_the_apps_card_of_the_same_name(
    table: dict[str, str], kind: str, names: dict[str, str]
) -> None:
    for key, short in table.items():
        archetype = ARCHETYPES[short]
        assert archetype.kind == kind, key
        assert "RiseOfIx" in _set_list(archetype.attributes, "SetList"), key
        assert archetype.title is not None
        assert _norm(archetype.title) == _norm(names[key]), key


def test_every_ix_conflict_and_tile_is_an_app_ix_archetype() -> None:
    for conflict_id, (short, choam) in IX_CONFLICT_ARCHETYPES.items():
        assert short == choam
        assert ARCHETYPES[short].kind == "conflict", conflict_id
    for tech_id, short in IX_TECH_ARCHETYPES.items():
        assert short.startswith("TechTileArchetypes.RiseOfIx."), tech_id
        assert short in ARCHETYPES, tech_id


def test_the_ix_board_is_the_apps_base_set_board_with_rise_of_ix() -> None:
    expected = (
        *(s for s in ORIGINAL_SPACE_ARCHETYPES if s not in IX_COVERED_SPACE_IDS),
        *IX_SPACE_ARCHETYPES,
    )
    assert board_space_ids(BOARD) == expected
    assert set(board_space_order(BOARD)) == set(expected)
    assert {s.space_id for s in content_for(IX).board_spaces} == set(expected)
    for space_id in IX_COVERED_SPACE_IDS:
        removed = ARCHETYPES[ORIGINAL_SPACE_ARCHETYPES[space_id]].attributes
        assert "RiseOfIx" in _set_list(removed, "RemovedFromSetList")
    for space_id, short in IX_SPACE_ARCHETYPES.items():
        assert space_entity(space_id, BOARD).short == short
        assert is_board_space(space_id)
    # The app's typedef order puts the Ix spaces after the Uprising ones,
    # so on the original board they come after the BaseSet spaces.
    assert board_space_order(BOARD)[-4:] == (
        "dreadnought",
        "interstellar_shipping",
        "smuggling",
        "tech_negotiation",
    )
