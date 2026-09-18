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
