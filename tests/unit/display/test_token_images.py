"""Tests for the pictured Combat marker filenames and their availability."""

import re
from pathlib import Path

from dune_imperium.content.uprising.board import Faction
from dune_imperium.display.token_images import (
    ALLIANCE_TOKEN_FACTIONS,
    MAKER_HOOKS_TOKEN_FILENAME,
    SHIELD_WALL_TOKEN_FILENAME,
    STRENGTH_TOKEN_COLORS,
    alliance_token_filename,
    available_alliance_tokens,
    available_seat_pieces,
    available_strength_tokens,
    strength_token_filenames,
)


def test_each_seat_has_its_own_token_colour() -> None:
    # One colour per seat of the four-player game, in seat order; the
    # browser UI's SEAT_COLORS (blue, red, green, yellow) tint the rest of
    # what a seat owns, so the two tables must agree.
    assert STRENGTH_TOKEN_COLORS == ("blue", "red", "green", "yellow")
    assert len(set(STRENGTH_TOKEN_COLORS)) == 4


def test_a_token_has_a_sword_face_and_a_plus_20_face() -> None:
    # "strength가 20을 넘으면 marker를 `+20` 면으로 뒤집고 track 처음부터
    # 초과분을 표시한다." [Main p. 12] (docs/rules/player-turns.md)
    assert strength_token_filenames("yellow") == (
        "strength_yellow.png",
        "strength_yellow_plus20.png",
    )
    names = [
        name
        for color in STRENGTH_TOKEN_COLORS
        for name in strength_token_filenames(color)
    ]
    assert len(set(names)) == 8


def test_a_seat_gets_pictures_only_with_both_faces() -> None:
    assert available_strength_tokens(frozenset()) == (None, None, None, None)

    files = frozenset(
        {
            "strength_blue.png",
            "strength_blue_plus20.png",
            # Red could show its sword but never flip: it keeps the drawn token.
            "strength_red.png",
            # Green could only ever show "+20".
            "strength_green_plus20.png",
            "unrelated.png",
        }
    )
    assert available_strength_tokens(files) == (
        ("strength_blue.png", "strength_blue_plus20.png"),
        None,
        None,
        None,
    )

    complete = frozenset(
        name
        for color in STRENGTH_TOKEN_COLORS
        for name in strength_token_filenames(color)
    )
    assert available_strength_tokens(complete) == tuple(
        strength_token_filenames(color) for color in STRENGTH_TOKEN_COLORS
    )


def test_the_shield_wall_token_has_its_own_picture() -> None:
    names = {
        name
        for color in STRENGTH_TOKEN_COLORS
        for name in strength_token_filenames(color)
    }
    assert SHIELD_WALL_TOKEN_FILENAME == "shield_wall.png"
    assert SHIELD_WALL_TOKEN_FILENAME not in names


def test_every_faction_has_an_alliance_token_picture_name() -> None:
    # One Alliance token per Faction [Main p. 4], named by the engine's
    # Faction value so the browser can look a picture up by faction key.
    assert ALLIANCE_TOKEN_FACTIONS == tuple(faction.value for faction in Faction)
    assert alliance_token_filename("bene_gesserit") == "alliance_bene_gesserit.png"
    names = {alliance_token_filename(faction) for faction in ALLIANCE_TOKEN_FACTIONS}
    assert len(names) == 4
    assert MAKER_HOOKS_TOKEN_FILENAME not in names


def test_alliance_pictures_are_offered_one_by_one() -> None:
    # A missing picture only sends that Faction's token back to the drawn
    # one; the others keep theirs.
    assert available_alliance_tokens(frozenset()) == {}
    files = frozenset({"alliance_fremen.jpg", "alliance_emperor.png", "other.jpg"})
    assert available_alliance_tokens(files) == {
        "fremen": "alliance_fremen.jpg",
        "emperor": "alliance_emperor.png",
    }
    # the app's picture wins over an older checkout's photo
    both = frozenset({"alliance_fremen.jpg", "alliance_fremen.png"})
    assert available_alliance_tokens(both) == {"fremen": "alliance_fremen.png"}


def test_seat_pieces_need_all_four_colours() -> None:
    # A kind with a missing colour stays drawn for every seat, so no seat's
    # Agent looks different from another's.
    files = frozenset(
        [f"agent_{color}.png" for color in ("blue", "red", "green", "yellow")]
        + ["spy_blue.png", "spy_red.png", "spy_green.png"]
    )
    assert available_seat_pieces(files) == {
        "agent": (
            "agent_blue.png",
            "agent_red.png",
            "agent_green.png",
            "agent_yellow.png",
        )
    }
    assert available_seat_pieces(frozenset()) == {}


def test_the_strength_faces_are_built_in_the_seat_colours() -> None:
    # scripts/dwgr/app_assets.py `strength` paints each Combat marker's tile
    # in its seat's colour; the browser tints everything else a seat owns
    # with render.js SEAT_COLORS, so the two tables must agree (the tool
    # imports UnityPy, so it is read here as text).
    repo = Path(__file__).resolve().parents[3]
    render_js = (repo / "src/dune_imperium/server/static/render.js").read_text()
    seat_colors = re.search(r"const SEAT_COLORS = \[([^\]]*)\]", render_js)
    assert seat_colors is not None
    tool = (repo / "scripts/dwgr/app_assets.py").read_text()
    table = re.search(r"STRENGTH_TILE_COLORS = \{([^}]*)\}", tool)
    assert table is not None
    tiles = dict(re.findall(r'"(\w+)": "(#[0-9a-f]{6})"', table.group(1)))
    assert tuple(tiles) == STRENGTH_TOKEN_COLORS
    assert list(tiles.values()) == re.findall(r'"(#[0-9a-f]{6})"', seat_colors.group(1))
