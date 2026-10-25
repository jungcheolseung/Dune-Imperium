"""The "Player 1 starts" option in game creation, saves and the setup box.

OQ-132 project convention (user decision 2026-10-25): with
``first_player_seat_zero`` seat 0 takes the Objective with the First Player
marker and the others are dealt at random. The printed deal gives every
player a random Objective and whoever gets the marker starts [Main p. 5]
(docs/rules/setup-and-game-flow.md). The engine and the API keep the
printed deal unless asked; the play server's setup box opens checked
(``--first-player``, ``server.seating``).
"""

from pathlib import Path

from fastapi.testclient import TestClient

from dune_imperium.server.app import create_app
from dune_imperium.server.persistence import parse_save_document
from dune_imperium.server.sessions import GameSessionManager

# The game rests at the human's first decision, so its summary shows the
# First Player of round 1 (all AI seats would play the game out).
HUMAN_FIRST = ("human", "heuristic", "heuristic", "heuristic")


def test_the_option_seats_the_first_player_at_zero_in_every_game() -> None:
    manager = GameSessionManager()
    for seed in range(8):
        summary = manager.create_game(
            HUMAN_FIRST, leader_draft=True, first_player_seat_zero=True, game_seed=seed
        )
        assert summary["first_player"] == 0
        assert summary["first_player_seat_zero"] is True
    firsts = {
        manager.create_game(HUMAN_FIRST, leader_draft=True, game_seed=seed)[
            "first_player"
        ]
        for seed in range(8)
    }
    # Without it the printed deal seats the marker anywhere.
    assert len(firsts) > 1


def test_a_save_keeps_the_option_and_an_older_save_has_it_off() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(
        HUMAN_FIRST, first_player_seat_zero=True, game_seed=3
    )
    document = manager.save_document(str(summary["game_id"]))
    ruleset = document["ruleset"]
    assert isinstance(ruleset, dict)
    assert ruleset["first_player_seat_zero"] is True
    assert parse_save_document(document).replay.ruleset.first_player_seat_zero
    restored = manager.restore_game(document)
    assert restored["first_player_seat_zero"] is True
    assert restored["first_player"] == 0

    # A save written before the option existed has no such key: off, and it
    # loads with the hash it was saved with (the option at its default is
    # left out of the state hash, RulesetConfig.HASH_OMITTED_AT_DEFAULT).
    older = manager.save_document(
        str(manager.create_game(HUMAN_FIRST, game_seed=3)["game_id"])
    )
    older_ruleset = older["ruleset"]
    assert isinstance(older_ruleset, dict)
    del older_ruleset["first_player_seat_zero"]
    assert not parse_save_document(older).replay.ruleset.first_player_seat_zero
    assert manager.restore_game(older)["first_player_seat_zero"] is False


def _app(tmp_path: Path, **options: str) -> TestClient:
    return TestClient(
        create_app(
            saves_dir=tmp_path / "saves",
            card_images_dir=tmp_path / "no-images",
            icons_dir=tmp_path / "no-icons",
            tokens_dir=tmp_path / "no-tokens",
            board_image=tmp_path / "no-map.jpg",
            bene_tleilax_image=tmp_path / "no-bene-tleilax.jpg",
            **options,  # type: ignore[arg-type]
        )
    )


def test_the_server_says_how_the_setup_box_opens(tmp_path: Path) -> None:
    assert _app(tmp_path).get("/whoami").json()["first_player"] == "player1"
    printed = _app(tmp_path, default_first_player="deal")
    assert printed.get("/whoami").json()["first_player"] == "deal"
    created = printed.post(
        "/games",
        json={
            "seats": list(HUMAN_FIRST),
            "game_seed": 4,
            "first_player_seat_zero": True,
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["first_player"] == 0
