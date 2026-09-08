"""Integrity tests for the Immortality content catalog and board transcription."""

from collections import Counter

import pytest

from dune_imperium.content.immortality import (
    FIRST_GENETIC_MARKER_COLUMN,
    RECLAIMED_FORCES,
    RESEARCH_LAST_COLUMN,
    RESEARCH_SPACES,
    RESEARCH_SPACES_BY_ID,
    RESEARCH_START_ID,
    SECOND_GENETIC_MARKER_COLUMN,
    TLEILAXU_CARDS,
    TLEILAXU_SETUP_SPICE_SPACE,
    TLEILAXU_TRACK,
    TLEILAXU_TRACK_END,
    ResearchBonus,
    TleilaxuBonus,
    genetic_markers_reached,
    research_next_space_ids,
    tleilaxu_card_for_instance,
    tleilaxu_cards_for,
    tleilaxu_deck_instance_ids,
)
from dune_imperium.content.schema import SourceDocument


def test_research_track_matches_the_board_artwork() -> None:
    # 21 hexagons plus the start space [Immortality p. 3 board artwork].
    assert len(RESEARCH_SPACES) == 22
    assert len(RESEARCH_SPACES_BY_ID) == 22
    assert RESEARCH_SPACES_BY_ID[RESEARCH_START_ID].bonus is ResearchBonus.NONE
    assert RESEARCH_LAST_COLUMN == SECOND_GENETIC_MARKER_COLUMN == 8
    assert FIRST_GENETIC_MARKER_COLUMN == 4
    assert Counter(space.bonus for space in RESEARCH_SPACES) == {
        ResearchBonus.NONE: 1,
        ResearchBonus.SPECIMEN: 4,
        ResearchBonus.TLEILAXU: 5,
        ResearchBonus.RESEARCH: 3,
        ResearchBonus.TRASH_AND_SPECIMEN: 2,
        ResearchBonus.TLEILAXU_AND_SPECIMEN: 1,
        ResearchBonus.SOLARI_ONE: 1,
        ResearchBonus.SPICE_ONE: 1,
        ResearchBonus.SPICE_TWO: 1,
        ResearchBonus.INFLUENCE_ANY: 1,
        ResearchBonus.TRASH_FOR_CARD_AND_INTRIGUE: 1,
        ResearchBonus.SEVEN_SOLARI_FOR_TWO_TLEILAXU: 1,
    }
    # Rows alternate parity by column so that every rightward step changes
    # the row by exactly one (the start hexagon is the one exception: it
    # touches the single first-column space head-on).
    assert all(
        (space.column + space.row) % 2 == 0
        for space in RESEARCH_SPACES
        if space.space_id != RESEARCH_START_ID
    )


def test_every_research_space_advances_rightward_until_the_last_column() -> None:
    assert research_next_space_ids(RESEARCH_START_ID) == ("c1r3",)
    assert research_next_space_ids("c1r3") == ("c2r2", "c2r4")
    # The rulebook example: from a specimen space, up-right to a research
    # icon or down-right to trash-and-specimen [Immortality p. 6].
    assert research_next_space_ids("c2r2") == ("c3r1", "c3r3")
    assert RESEARCH_SPACES_BY_ID["c3r1"].bonus is ResearchBonus.RESEARCH
    assert RESEARCH_SPACES_BY_ID["c3r3"].bonus is ResearchBonus.TRASH_AND_SPECIMEN
    # Edge spaces have a single choice; the last column has none.
    assert research_next_space_ids("c3r1") == ("c4r2",)
    assert research_next_space_ids("c6r6") == ("c7r5",)
    for space in RESEARCH_SPACES:
        nexts = research_next_space_ids(space.space_id)
        if space.column == RESEARCH_LAST_COLUMN:
            assert nexts == ()
        else:
            assert 1 <= len(nexts) <= 2
            assert all(
                RESEARCH_SPACES_BY_ID[n].column == space.column + 1 for n in nexts
            )
    # Every space except the start is reachable from the start.
    reached = {RESEARCH_START_ID}
    frontier = [RESEARCH_START_ID]
    while frontier:
        reached.update(nexts := research_next_space_ids(frontier.pop()))
        frontier.extend(nexts)
    assert reached == set(RESEARCH_SPACES_BY_ID)


def test_genetic_markers_are_reached_by_column() -> None:
    assert genetic_markers_reached(RESEARCH_START_ID) == 0
    assert genetic_markers_reached("c3r5") == 0
    assert genetic_markers_reached("c4r2") == 1
    assert genetic_markers_reached("c7r3") == 1
    assert genetic_markers_reached("c8r6") == 2


def test_tleilaxu_track_bonuses_match_the_rulebook() -> None:
    # Start plus seven spaces; the fourth space carries the setup spice
    # [Immortality pp. 4, 7].
    assert TLEILAXU_TRACK_END == 7
    assert TLEILAXU_TRACK[0] is TleilaxuBonus.NONE
    assert TLEILAXU_TRACK[TLEILAXU_SETUP_SPICE_SPACE] is (
        TleilaxuBonus.VICTORY_POINT_AND_FIRST_SPICE
    )
    assert [
        index
        for index, bonus in enumerate(TLEILAXU_TRACK)
        if bonus is TleilaxuBonus.INTRIGUE
    ] == [2, 6]
    assert TLEILAXU_TRACK[7] is TleilaxuBonus.VICTORY_POINT


def test_tleilaxu_catalog_has_the_official_deck_and_reclaimed_forces() -> None:
    retail = tuple(entry for entry in TLEILAXU_CARDS if not entry.promo)
    assert len(retail) == 18
    assert sum(entry.copies for entry in retail) == 18
    assert {entry.card.card_id for entry in TLEILAXU_CARDS if entry.promo} == {
        "piter_genius_advisor"
    }
    assert all(entry.immortality_only for entry in TLEILAXU_CARDS)
    assert all(entry.acquisition_cost is None for entry in TLEILAXU_CARDS)
    assert Counter(entry.specimen_cost for entry in retail) == {1: 4, 2: 7, 3: 5, 4: 2}
    assert sum(entry.graft for entry in retail) == 12
    assert all(entry.card.catalog_url for entry in retail)
    assert RECLAIMED_FORCES.specimen_cost == 3
    assert RECLAIMED_FORCES.card.card_id not in {
        entry.card.card_id for entry in TLEILAXU_CARDS
    }
    assert {ref.document for ref in retail[0].card.sources} == {
        SourceDocument.IMMORTALITY_RULEBOOK,
        SourceDocument.CARD_FACE,
    }
    # Nothing has play data yet, so nothing joins the deck.
    assert tleilaxu_cards_for(promo_cards=True) == ()
    assert tleilaxu_deck_instance_ids(promo_cards=True) == ()


def test_tleilaxu_instance_ids_resolve_and_validate() -> None:
    assert tleilaxu_card_for_instance("tleilaxu:ghola:0").card.name == "Ghola"
    with pytest.raises(ValueError, match="copy index"):
        tleilaxu_card_for_instance("tleilaxu:ghola:1")
    with pytest.raises(ValueError, match="unknown"):
        tleilaxu_card_for_instance("tleilaxu:mentat:0")
    with pytest.raises(ValueError, match="not a Tleilaxu"):
        tleilaxu_card_for_instance("imperium:ghola:0")
