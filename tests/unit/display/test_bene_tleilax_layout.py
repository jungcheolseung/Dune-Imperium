"""Tests for the player disc geometry on the Bene Tleilax board scan."""

from dune_imperium.content.immortality.board import RESEARCH_START_ID
from dune_imperium.display.bene_tleilax_layout import bene_tleilax_layout
from dune_imperium.display.board_layout import marker_layout


def test_the_disc_is_the_size_of_the_spots_each_board_prints() -> None:
    # One common token: on the main scan it is the printed High Council
    # circle (176 px of 6012), on the Bene Tleilax scan the printed disc
    # spots (324 px of 5551). Only the scans' resolutions differ.
    layout = bene_tleilax_layout()
    assert layout["disc_size"] == 5.84
    assert round(layout["disc_size"] / 100 * 5551) == 324
    assert layout["aspect"] == 5551 / 3952
    main = marker_layout()
    assert round(main["disc_size"] / 100 * 6012) == 176


def test_every_seat_has_a_printed_spot_on_both_start_spaces() -> None:
    layout = bene_tleilax_layout()
    disc_width = layout["disc_size"]
    disc_height = disc_width * layout["aspect"]

    # The Tleilaxu track's first space: a 2x2 of spots that do not overlap
    # and lie inside the space.
    track = layout["track_start_discs"]
    assert len(track) == 4 and len({tuple(spot) for spot in track}) == 4
    start_left, start_width = layout["track_cells"][0]
    band_top, band_height = layout["track_band"]
    for x, y in track:
        assert start_left <= x - disc_width / 2
        assert x + disc_width / 2 <= start_left + start_width
        assert band_top <= y - disc_height / 2
        assert y + disc_height / 2 <= band_top + band_height
    (left, top), (right, _), (_, bottom), _ = track
    assert right - left >= disc_width and bottom - top >= disc_height

    # The research start piece: a column of four, one disc apart, around
    # the start space's point.
    research = layout["research_start_discs"]
    assert len(research) == 4
    assert len({x for x, _ in research}) == 1
    rows = [y for _, y in research]
    assert rows == sorted(rows)
    assert all(
        lower - upper >= disc_height
        for upper, lower in zip(rows, rows[1:], strict=False)
    )
    _, start_y = layout["research_points"][RESEARCH_START_ID]
    assert rows[0] < start_y < rows[-1]


def test_setup_spice_covers_the_printed_hexagon() -> None:
    # "bank의 spice 2를 Tleilaxu track의 네 번째 칸에 놓는다" [Immortality p. 4]
    # (docs/rules/immortality.md): the fourth space prints a "1st / 2"
    # hexagon, and the spice is drawn as the main board's bonus spice
    # hexagon over its white outline (310 x 270 px on the 5551x3952 scan).
    from dune_imperium.content.immortality.board import TLEILAXU_SETUP_SPICE_SPACE

    layout = bene_tleilax_layout()
    (x, y), (width, height) = layout["spice_point"], layout["spice_size"]
    assert round(width / 100 * 5551) == 310
    assert round(height / 100 * 3952) == 270
    # A regular flat-topped hexagon: height = width * sqrt(3)/2 on the scan.
    assert abs(height / (width * layout["aspect"]) - 3**0.5 / 2) < 0.01
    left, cell_width = layout["track_cells"][TLEILAXU_SETUP_SPICE_SPACE]
    band_top, band_height = layout["track_band"]
    assert left <= x - width / 2 and x + width / 2 <= left + cell_width
    assert band_top <= y - height / 2 and y + height / 2 <= band_top + band_height


def test_scouts_pieces_have_their_places_on_this_board() -> None:
    # Sponsored Research's spice lies beside the Helix (the first genetic
    # marker, OQ-089 (b)) and Tleilaxu Offering's troops on the Tleilaxu
    # track's third space (docs/rules/arrakeen-scouts.md 5).
    from dune_imperium.display.bene_tleilax_layout import (
        SCOUTS_OFFERING_BOX,
        TLEILAXU_OFFERING_TRACK_SPACE,
    )
    from dune_imperium.rules import scouts_missions

    offering_space = scouts_missions.TLEILAXU_OFFERING_TRACK_SPACE
    assert TLEILAXU_OFFERING_TRACK_SPACE == offering_space
    layout = bene_tleilax_layout()
    scouts = layout["scouts"]
    assert scouts["offering_space"] == TLEILAXU_OFFERING_TRACK_SPACE
    assert set(scouts["regions"]) == {scouts_missions.TLEILAXU_OFFERING_SPACE}
    # The box lies inside the third space and the track band.
    cell_left, cell_width = layout["track_cells"][TLEILAXU_OFFERING_TRACK_SPACE]
    band_top, band_height = layout["track_band"]
    left, top, width, height = SCOUTS_OFFERING_BOX
    assert cell_left <= left and left + width <= cell_left + cell_width
    assert band_top <= top and top + height <= band_top + band_height
    # A seat's two troops stand side by side in it at full size: the main
    # board's cube (95 px of 6012) at this scan's scale (324 / 176).
    troop_width, troop_height = scouts["sizes"]["troop"]
    assert round(troop_width / 100 * 5551) == 175
    assert abs(troop_width * 5551 - troop_height * 3952) < 5
    assert 2 * troop_width + scouts["gap"][0] <= width
    # The Helix's spice: the setup spice's hexagon, left of the Helix tile
    # (outline x 41.1-51.6, y 87.8-96.6), inside the scan.
    x, y = scouts["helix_spice_point"]
    spice_width, spice_height = layout["spice_size"]
    assert x + spice_width / 2 < 41.1 and 87.8 < y < 96.6
    assert y + spice_height / 2 < 100
