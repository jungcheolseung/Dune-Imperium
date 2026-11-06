"""Disposal Facility's two trashes in one Reveal turn, through the remote
server's seat cookies (needs the ``ui`` extra).

docs/rules/rise-of-ix.md 2: "Disposal Facility | 3 | trash 1 | Reveal turn: 그
turn에 얻은 Persuasion 합계(쓴 것 포함)가 6 이상이면 in play 카드 하나를 trash할 수
있다(OQ-126)"; OQ-150 ruling (2) (2026-10-29): a tile acquired during a Reveal
turn hears that turn's Reveal abilities ("Reveal 도중 Acquire Tech로 얻은 타일도
그 Reveal turn의 Reveal 능력이 모두 듣는다"). So a seat that buys the tile in its
Reveal turn has its acquire box's trash and its Reveal ability's trash on
offer together: two rows of each card in play, which until P4 b806b3db
shared their steps and stopped the engine.

A real game reaches this only when Machine Culture's Plot buys the tile in a
Reveal turn of 6 or more Persuasion: about one in a thousand searched games
(``scripts/e2e/ix_screens.py`` pinned one, seed 246 after P4 e3cac948, and
lost the previous one whenever the decks changed). So this test plays a real
game to seat 0's first turn (original + Rise of Ix, seed 1, whose Tech stacks
open with Disposal Facility), and gives seat 0 what the path needs, the one
change made outside the rules: its own two Convincing Arguments, both Dunes
and Diplomacy in hand (7 Persuasion; the cards trade places with its deck),
Machine Culture from the Intrigue deck and 3 spice, the tile's price. The
rest goes through the server: the Reveal, Machine Culture, the tile, its
acquire box's trash; one trash, then the other. The page side of the same
rows is ``scripts/e2e/ix_screens.py``'s Disposal Facility step, which renders
``BOTH_ROWS`` and ``REVEAL_ROWS`` below.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from dune_imperium.server.access import AccessMode  # noqa: E402
from dune_imperium.server.app import create_app  # noqa: E402
from dune_imperium.server.sessions import GameSessionManager  # noqa: E402

ADMIN_KEY = "disposal-facility-admin-key"
BODY = {
    "seats": ["human"] * 4,
    "base_game": "imperium",
    "rise_of_ix": True,
    "game_seed": 1,
}
# Seat 3's Leader picks two Masterstroke factions; then seat 0 decides.
PLAN: list[tuple[int, str, dict[str, Any]]] = [
    (3, "choose_masterstroke_faction", {"faction": "emperor"}),
    (3, "choose_masterstroke_faction", {"faction": "spacing_guild"}),
]
MACHINE_CULTURE = "intrigue:machine_culture:0"
HAND = (
    "player:0:starter:convincing_argument:0",
    "player:0:starter:convincing_argument:1",
    "player:0:starter:dune_the_desert_planet:0",
    "player:0:starter:dune_the_desert_planet:1",
    "player:0:starter:diplomacy:0",
)
BOX = {"printed": "disposal_facility", "source": "tech"}
# The two trashes on offer once the acquire box's trash is chosen, in the
# server's order: the Reveal ability's row and the box's row for each card in
# play. ``ix_screens.py`` renders these rows on a page.
BOTH_ROWS: list[tuple[str, dict[str, Any]]] = [
    *(("trash_disposal_facility_card", {"card_id": card}) for card in HAND),
    *(("trash_optional_card", {"card_id": card, **BOX}) for card in HAND),
]
# After the box trashes the first Convincing Argument: the Reveal ability's
# rows for the other four cards.
REVEAL_ROWS: list[tuple[str, dict[str, Any]]] = [
    ("trash_disposal_facility_card", {"card_id": card}) for card in HAND[1:]
]
TRASHES = ("trash_disposal_facility_card", "trash_optional_card")


class _Table:
    """A remote game: four clients each claim one seat (each holds its own
    seat cookie)."""

    def __init__(self, tmp_path: Path) -> None:
        self.manager = GameSessionManager(access=AccessMode.REMOTE, admin_key=ADMIN_KEY)
        app = create_app(
            self.manager,
            saves_dir=tmp_path / "saves",
            card_images_dir=tmp_path / "no-images",
            icons_dir=tmp_path / "no-icons",
            tokens_dir=tmp_path / "no-tokens",
            board_image=tmp_path / "no-map.jpg",
            bene_tleilax_image=tmp_path / "no-bene-tleilax.jpg",
        )
        host = TestClient(app)
        assert host.post("/auth/admin", json={"key": ADMIN_KEY}).status_code == 200
        created = host.post("/games", json=BODY)
        assert created.status_code == 200, created.text
        self.game_id = created.json()["game_id"]
        self.seats: list[TestClient] = []
        for seat in range(4):
            client = TestClient(app)
            claimed = client.post(
                f"/games/{self.game_id}/seats/{seat}/claim", json={"name": f"P{seat}"}
            )
            assert claimed.status_code == 200, claimed.text
            self.seats.append(client)
        self.spectator = TestClient(app)

    def summary(self) -> dict[str, Any]:
        response = self.spectator.get(f"/games/{self.game_id}")
        assert response.status_code == 200, response.text
        return dict(response.json())

    def rows(self, seat: int) -> list[dict[str, Any]]:
        response = self.seats[seat].get(f"/games/{self.game_id}/seats/{seat}/actions")
        assert response.status_code == 200, response.text
        return list(response.json()["actions"])

    def trash_rows(self, seat: int) -> list[tuple[str, dict[str, Any]]]:
        return [
            (row["action_id"], row["arguments"])
            for row in self.rows(seat)
            if row["action_id"] in TRASHES
        ]

    def take(self, seat: int, action_id: str, arguments: dict[str, Any]) -> None:
        """Take one whole action as ``seat``, pressing any held turn end first."""

        game = f"/games/{self.game_id}"
        while isinstance(held := (summary := self.summary())["confirmation"], int):
            pressed = self.seats[held].post(
                f"{game}/confirm",
                json={
                    "seat": held,
                    "revision": summary["revision"],
                    "undo_count": summary["undo_count"],
                },
            )
            assert pressed.status_code == 200, pressed.text
        rows = [
            row
            for row in self.rows(seat)
            if row["action_id"] == action_id and (row["arguments"] or {}) == arguments
        ]
        assert len(rows) == 1, (seat, action_id, arguments)
        sent = self.seats[seat].post(
            f"{game}/actions",
            json={
                "seat": seat,
                "revision": summary["revision"],
                "undo_count": summary["undo_count"],
                "index": rows[0]["index"],
            },
        )
        assert sent.status_code == 200, sent.text

    def to_both_trashes(self) -> None:
        """Play ``PLAN``, give seat 0 the path's hand, Intrigue card and spice,
        and buy Disposal Facility with Machine Culture in its Reveal turn."""

        for seat, action_id, arguments in PLAN:
            self.take(seat, action_id, arguments)
        session = self.manager._get(self.game_id)
        state = session.state
        assert self.summary()["decision"]["owner"] == 0
        assert "disposal_facility" in [stack[0] for stack in state.tech_stacks]
        owner = state.players[0]
        pool = [*owner.hand, *owner.deck]
        assert all(card in pool for card in HAND) and not owner.discard_pile
        players = list(state.players)
        players[0] = replace(
            owner,
            hand=HAND,
            deck=tuple(card for card in pool if card not in HAND),
            intrigue_cards=(*owner.intrigue_cards, MACHINE_CULTURE),
            resources=replace(owner.resources, spice=3),
        )
        session.state = replace(
            state,
            players=tuple(players),
            intrigue_deck=tuple(
                card for card in state.intrigue_deck if card != MACHINE_CULTURE
            ),
        )
        self.take(0, "reveal_turn", {})
        self.take(0, "play_intrigue", {"card_id": MACHINE_CULTURE, "option": 0})
        self.take(0, "acquire_tech", {"tech_id": "disposal_facility"})
        self.take(
            0,
            "resolve_tech_acquire_effect",
            {"effect": "trash", "tech_id": "disposal_facility"},
        )


@pytest.fixture
def table(tmp_path: Path) -> _Table:
    return _Table(tmp_path)


def test_both_trashes_are_rows_of_their_own(table: _Table) -> None:
    table.to_both_trashes()
    rows = [row for row in table.rows(0) if row["action_id"] in TRASHES]
    assert [(row["action_id"], row["arguments"]) for row in rows] == BOTH_ROWS
    # Each row is a step of its own: no two share an index.
    assert len({row["index"] for row in rows}) == len(rows)
    for seat in (1, 2, 3):
        assert table.trash_rows(seat) == []


def test_the_box_trash_leaves_the_reveal_trash(table: _Table) -> None:
    table.to_both_trashes()
    first = HAND[0]
    table.take(0, "trash_optional_card", {"card_id": first, **BOX})
    assert table.trash_rows(0) == REVEAL_ROWS
    second = HAND[2]
    table.take(0, "trash_disposal_facility_card", {"card_id": second})
    trashed = table.manager._get(table.game_id).state.players[0].trashed
    assert first in trashed and second in trashed
    assert table.trash_rows(0) == []
