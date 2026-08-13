"""Integrity tests for the official four-player Uprising board data."""

from collections import Counter

from dune_imperium.content.schema import SourceDocument
from dune_imperium.content.uprising.board import (
    BOARD_SPACES,
    BOARD_SPACES_BY_ID,
    OBSERVATION_POSTS,
    DynamicCost,
    Faction,
    ResourceCost,
)
from dune_imperium.content.uprising.types import AgentIcon


def ids_with(attribute: str) -> set[str]:
    return {
        space.space_id for space in BOARD_SPACES if getattr(space, attribute) is True
    }


def test_board_has_the_official_space_and_icon_counts() -> None:
    assert len(BOARD_SPACES) == 22
    assert len(BOARD_SPACES_BY_ID) == 22
    assert len({space.space_id for space in BOARD_SPACES}) == 22
    assert Counter(space.agent_icon for space in BOARD_SPACES) == {
        AgentIcon.EMPEROR: 2,
        AgentIcon.SPACING_GUILD: 2,
        AgentIcon.BENE_GESSERIT: 2,
        AgentIcon.FREMEN: 2,
        AgentIcon.LANDSRAAD: 5,
        AgentIcon.CITY: 4,
        AgentIcon.SPICE_TRADE: 5,
    }


def test_board_space_classifications_match_the_guide() -> None:
    assert ids_with("combat") == {
        "arrakeen",
        "deep_desert",
        "desert_tactics",
        "fremkit",
        "hagga_basin",
        "heighliner",
        "imperial_basin",
        "research_station",
        "sietch_tabr",
        "spice_refinery",
    }
    assert ids_with("maker") == {
        "deep_desert",
        "hagga_basin",
        "imperial_basin",
    }
    assert ids_with("critical") == {
        "arrakeen",
        "imperial_basin",
        "spice_refinery",
    }


def test_only_faction_icon_spaces_grant_automatic_faction_influence() -> None:
    assert sum(space.faction is not None for space in BOARD_SPACES) == 8
    assert BOARD_SPACES_BY_ID["sietch_tabr"].faction is None
    assert BOARD_SPACES_BY_ID["imperial_privilege"].faction is None
    assert BOARD_SPACES_BY_ID["shipping"].faction is None


def test_influence_requirements_are_not_confused_with_agent_icons() -> None:
    assert BOARD_SPACES_BY_ID["sietch_tabr"].requirement is not None
    assert BOARD_SPACES_BY_ID["sietch_tabr"].requirement.faction is Faction.FREMEN
    assert BOARD_SPACES_BY_ID["imperial_privilege"].requirement is not None
    assert (
        BOARD_SPACES_BY_ID["imperial_privilege"].requirement.faction is Faction.EMPEROR
    )
    assert BOARD_SPACES_BY_ID["shipping"].requirement is not None
    assert BOARD_SPACES_BY_ID["shipping"].requirement.faction is Faction.SPACING_GUILD


def test_choice_and_dynamic_costs_remain_distinguishable() -> None:
    assert BOARD_SPACES_BY_ID["gather_support"].cost_options == (
        ResourceCost(),
        ResourceCost(solari=2),
    )
    assert BOARD_SPACES_BY_ID["spice_refinery"].cost_options == (
        ResourceCost(),
        ResourceCost(spice=1),
    )
    assert BOARD_SPACES_BY_ID["swordmaster"].dynamic_cost is DynamicCost.SWORDMASTER


def test_observation_post_graph_matches_the_transcription() -> None:
    assert len(OBSERVATION_POSTS) == 13
    assert len({post.post_id for post in OBSERVATION_POSTS}) == 13
    assert all(
        space_id in BOARD_SPACES_BY_ID
        for post in OBSERVATION_POSTS
        for space_id in post.connected_space_ids
    )

    connections = Counter(
        space_id for post in OBSERVATION_POSTS for space_id in post.connected_space_ids
    )
    assert connections["research_station"] == 2
    assert connections["spice_refinery"] == 2
    assert connections["imperial_basin"] == 1
    assert connections["hagga_basin"] == 1
    assert connections["deep_desert"] == 1


def test_every_space_has_a_page_level_official_source() -> None:
    assert all(space.sources for space in BOARD_SPACES)
    assert BOARD_SPACES_BY_ID["dutiful_service"].sources[0].pages == (1,)
    assert BOARD_SPACES_BY_ID["sardaukar"].sources[0].pages == (2,)
    assert any(
        source.document is SourceDocument.MAIN_RULEBOOK and source.pages == (15,)
        for source in BOARD_SPACES_BY_ID["deep_desert"].sources
    )
