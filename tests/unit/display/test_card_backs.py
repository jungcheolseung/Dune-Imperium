"""Tests for the card back picture names and their availability."""

from dune_imperium.content.uprising.types import ConflictTier
from dune_imperium.display.card_backs import (
    CARD_BACK_KINDS,
    available_card_backs,
    card_back_filename,
)
from dune_imperium.display.token_images import (
    FIRST_PLAYER_TOKEN_FILENAME,
    STRENGTH_TOKEN_COLORS,
    seat_piece_filename,
    strength_token_filenames,
)


def test_every_conflict_tier_has_its_own_back() -> None:
    # "Conflict 카드를 I, II, III 뒷면별로 나눈다." [Main p. 4]
    # (docs/rules/setup-and-game-flow.md): the browser asks for the back of
    # the deck's top card by `conflict_<tier>`, the server's
    # conflict_deck_top_tier.
    assert {f"conflict_{tier.value}" for tier in ConflictTier} <= set(CARD_BACK_KINDS)
    assert {"imperium", "intrigue", "tech"} <= set(CARD_BACK_KINDS)
    assert len(set(CARD_BACK_KINDS)) == len(CARD_BACK_KINDS)


def test_back_pictures_are_named_apart_from_the_tokens() -> None:
    assert card_back_filename("conflict_2") == "back_conflict_2.webp"
    names = {card_back_filename(kind) for kind in CARD_BACK_KINDS}
    assert len(names) == len(CARD_BACK_KINDS)
    tokens = {
        FIRST_PLAYER_TOKEN_FILENAME,
        *(n for c in STRENGTH_TOKEN_COLORS for n in strength_token_filenames(c)),
        *(seat_piece_filename("troop", c) for c in STRENGTH_TOKEN_COLORS),
    }
    assert not names & tokens


def test_backs_are_offered_kind_by_kind() -> None:
    assert available_card_backs(frozenset()) == {}
    files = frozenset(
        {
            "back_imperium.webp",
            "back_conflict_3.webp",
            # another format or name is not a back
            "back_intrigue.png",
            "conflict_1.webp",
        }
    )
    assert available_card_backs(files) == {
        "imperium": "back_imperium.webp",
        "conflict_3": "back_conflict_3.webp",
    }
    every = frozenset(card_back_filename(kind) for kind in CARD_BACK_KINDS)
    assert list(available_card_backs(every)) == list(CARD_BACK_KINDS)
