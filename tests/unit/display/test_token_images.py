"""Tests for the pictured Combat marker filenames and their availability."""

from dune_imperium.content.uprising.board import Faction
from dune_imperium.display.token_images import (
    ALLIANCE_TOKEN_FACTIONS,
    MAKER_HOOKS_TOKEN_FILENAME,
    SHIELD_WALL_TOKEN_FILENAME,
    STRENGTH_TOKEN_COLORS,
    alliance_token_filename,
    available_alliance_tokens,
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
    assert alliance_token_filename("bene_gesserit") == "alliance_bene_gesserit.jpg"
    names = {alliance_token_filename(faction) for faction in ALLIANCE_TOKEN_FACTIONS}
    assert len(names) == 4
    assert MAKER_HOOKS_TOKEN_FILENAME not in names


def test_alliance_pictures_are_offered_one_by_one() -> None:
    # A missing picture only sends that Faction's token back to the drawn
    # one; the others keep theirs.
    assert available_alliance_tokens(frozenset()) == {}
    files = frozenset({"alliance_fremen.jpg", "alliance_emperor.png", "other.jpg"})
    assert available_alliance_tokens(files) == {"fremen": "alliance_fremen.jpg"}
