"""Tessia Vernius' Snooper reward 1 outside her turn, through the remote
server's seat cookies (needs the ``ui`` extra).

docs/rules/rise-of-ix.md 10: "Tessia Vernius (4) | Careful Observation: ...
그 token에 도달할 때마다 Snooper track의 맨 위 덮이지 않은 보상을 받는다(① discard →
spice 1, ...)"; 9.3: "Tessia: 버릴 카드가 없을 때 첫 Snooper를 얻어도 token은 가져가 맨
위 칸을 덮고, spice는 못 받음"; 7: an Unload card discarded as a cost pays its box
before the arrow's reward ("비용 → 효과 줄의 왼쪽(비용)이 Unload를 일으키면 Unload를
끝까지 해결한 뒤 오른쪽으로 간다"). Outside her turn the reward is the
``OPTIONAL_DISCARD`` window over her hand (``rules.snoopers``); her hand is
hers alone (docs/rules/information-visibility.md).

``scripts/e2e/ix_screens.py`` checks the other hidden values on real tables
through browsers. This window is not reached there: a real game gets to it
only through a Plot Intrigue that draws, played in her Reveal turn, and then a
Combat Influence reaching her first token, which about 260 searched games
never did. So this test builds that moment as the engine's own Tessia tests
do (``tests/unit/rules/test_ix_leader_tessia.py``: Combat, Emperor Influence 1
to 2) and puts it into a remote game whose four seats are claimed by four
cookie-separated clients, with a fifth client that claims none. The page
draws the window as every other ``OPTIONAL_DISCARD`` window; the browser side
of those is covered by the e2e scripts.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from dune_imperium import BaseGame, RulesetConfig  # noqa: E402
from dune_imperium.content.uprising.board import Faction  # noqa: E402
from dune_imperium.core import (  # noqa: E402
    ChanceDecision,
    ChanceResolver,
    GamePhase,
    GameState,
    Influence,
    Resources,
)
from dune_imperium.rules import UprisingRulesEngine  # noqa: E402
from dune_imperium.rules.frames import FrameKind  # noqa: E402
from dune_imperium.rules.influence import gain_faction_influence  # noqa: E402
from dune_imperium.rules.snoopers import settle_snooper_discards  # noqa: E402
from dune_imperium.server.access import AccessMode  # noqa: E402
from dune_imperium.server.app import create_app  # noqa: E402
from dune_imperium.server.sessions import GameSessionManager  # noqa: E402

ADMIN_KEY = "tessia-window-admin-key"
TESSIA = "tessia_vernius"
LEADERS = (TESSIA, "glossu_rabban", "count_ilban_richese", "earl_memnon_thorvald")
CONFIG = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
# CHOAM Delegate's Unload box gives 3 Solari (the engine's Tessia test).
DELEGATE = "imperium:choam_delegate:0"
NONE = Resources(solari=0, spice=0, water=0)
# What differs between two reads of one game whatever its hidden cards: the
# play clock and who is online.
VOLATILE = frozenset({"clock", "clock_age_ms", "online"})


def _start() -> GameState:
    engine = UprisingRulesEngine(leader_ids=LEADERS)
    state = engine.reset(CONFIG, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    return state


def _window(state: GameState) -> GameState:
    """Seat 0's token 1 reached in the Combat phase (no turn [Main p. 8])."""

    combat = replace(state, phase=GamePhase.COMBAT, decision_stack=())
    gained = gain_faction_influence(
        combat, 0, Faction.EMPEROR, 1, event_prefix="test:emperor"
    )
    window = settle_snooper_discards(gained).state
    assert window.decision_stack[-1].kind == FrameKind.OPTIONAL_DISCARD
    return window


def _tables() -> tuple[GameState, GameState, list[str]]:
    """Two windows: Tessia holds CHOAM Delegate and two starter cards; in the
    second one hidden starter card is traded with her deck's top card (the
    same cards she owns, so her public deck pool is the same)."""

    start = _start()
    owner = start.players[0]
    assert DELEGATE not in start.imperium_row
    hand = (DELEGATE, *owner.hand[:2])
    first = replace(
        start,
        players=(
            replace(owner, influence=Influence(emperor=1), resources=NONE, hand=hand),
            *start.players[1:],
        ),
    )
    kept, traded = hand[2], owner.deck[0]
    # Two different cards by name, not only by instance: a leak of which card
    # it is (its name, picture or kind) shows in the comparison too.
    assert kept.split(":")[-2] != traded.split(":")[-2]
    second = replace(
        first,
        players=(
            replace(
                first.players[0],
                hand=(*hand[:2], traded),
                deck=(kept, *owner.deck[1:]),
            ),
            *first.players[1:],
        ),
    )
    return _window(first), _window(second), list(hand)


def _app(tmp_path: Path, manager: GameSessionManager) -> Any:
    return create_app(
        manager,
        saves_dir=tmp_path / "saves",
        card_images_dir=tmp_path / "no-images",
        icons_dir=tmp_path / "no-icons",
        tokens_dir=tmp_path / "no-tokens",
        board_image=tmp_path / "no-map.jpg",
        bene_tleilax_image=tmp_path / "no-bene-tleilax.jpg",
    )


def _steady(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {k: _steady(v) for k, v in payload.items() if k not in VOLATILE}
    if isinstance(payload, list):
        return [_steady(value) for value in payload]
    return payload


class _Table:
    """A remote game of four human seats, each claimed by its own client (its
    own seat cookie), and a client that claims none."""

    def __init__(self, tmp_path: Path) -> None:
        self.manager = GameSessionManager(access=AccessMode.REMOTE, admin_key=ADMIN_KEY)
        app = _app(tmp_path, self.manager)
        host = TestClient(app)
        assert host.post("/auth/admin", json={"key": ADMIN_KEY}).status_code == 200
        created = host.post(
            "/games",
            json={
                "seats": ["human"] * 4,
                "base_game": "imperium",
                "rise_of_ix": True,
                "first_player_seat_zero": True,
                "game_seed": 3,
            },
        )
        assert created.status_code == 200, created.text
        self.game_id = created.json()["game_id"]
        self.seats = []
        for seat in range(4):
            client = TestClient(app)
            claimed = client.post(
                f"/games/{self.game_id}/seats/{seat}/claim", json={"name": f"P{seat}"}
            )
            assert claimed.status_code == 200, claimed.text
            self.seats.append(client)
        self.spectator = TestClient(app)

    def put(self, state: GameState) -> None:
        session = self.manager._get(self.game_id)
        assert session.state.config == state.config
        session.state = state

    def payloads(self, seat: int | None) -> dict[str, Any]:
        """Everything a reader fetches with its own cookie, by name; the event
        stream's message is the doorbell (``sessions.doorbell``), the same for
        every reader."""

        game = f"/games/{self.game_id}"
        client = self.spectator if seat is None else self.seats[seat]
        paths = {"summary": game, "seatless": f"{game}/snapshot"}
        if seat is not None:
            paths |= {
                "view": f"{game}/seats/{seat}/view",
                "actions": f"{game}/seats/{seat}/actions",
                "snapshot": f"{game}/snapshot?seat={seat}",
                "log": f"{game}/log?seat={seat}",
            }
        found: dict[str, Any] = {}
        for name, path in paths.items():
            response = client.get(path)
            assert response.status_code == 200, (seat, path, response.text)
            found[name] = response.json()
        found["events"] = self.manager.doorbell(self.game_id)
        return found

    def others(self) -> dict[str, Any]:
        """The payloads of every reader but Tessia's seat."""

        readers: dict[str, Any] = {
            f"seat {seat}": self.payloads(seat) for seat in (1, 2, 3)
        }
        readers["spectator"] = self.payloads(None)
        return readers


@pytest.fixture
def table(tmp_path: Path) -> _Table:
    return _Table(tmp_path)


def test_the_window_and_its_hand_reach_tessia_alone(table: _Table) -> None:
    window, _, hand = _tables()
    table.put(window)

    own = table.payloads(0)
    assert own["summary"]["decision"]["kind"] == "optional_discard"
    assert own["summary"]["decision"]["owner"] == 0
    assert own["view"]["private"]["hand"] == hand
    rows = own["actions"]["actions"]
    discards = [
        row["arguments"]["card_id"]
        for row in rows
        if row["action_id"] == "discard_snooper_card"
    ]
    assert sorted(discards) == sorted(hand)
    assert any(row["action_id"] == "decline_snooper_discard" for row in rows)

    for name, payloads in table.others().items():
        text = json.dumps(payloads)
        for card in hand:
            assert card not in text, (name, card)
        assert "discard_snooper_card" not in text, name
        if name != "spectator":
            assert payloads["view"]["players"][0]["hand_size"] == len(hand)
            assert payloads["actions"]["actions"] == []
    # Her own view, actions, snapshot and log are refused to everyone else.
    for client in [*table.seats[1:], table.spectator]:
        for path in ("view", "actions", "snapshot", "log"):
            url = (
                f"/games/{table.game_id}/snapshot?seat=0"
                if path == "snapshot"
                else f"/games/{table.game_id}/log?seat=0"
                if path == "log"
                else f"/games/{table.game_id}/seats/0/{path}"
            )
            assert client.get(url).status_code == 403, url


def test_another_hand_card_changes_nothing_any_other_reader_receives(
    table: _Table,
) -> None:
    """The twin: the same window with one hidden hand card traded for her
    deck's top card. Every other seat's and the spectator's payloads are the
    same, so neither the card nor its name, picture or a count reaches them;
    her own view tells the two apart."""

    first, second, _ = _tables()
    table.put(first)
    before, own_before = table.others(), table.payloads(0)
    table.put(second)
    after, own_after = table.others(), table.payloads(0)
    assert _steady(after) == _steady(before)
    assert own_after["view"]["private"]["hand"] != own_before["view"]["private"]["hand"]


def test_the_discarded_card_turns_public_and_its_unload_comes_first(
    table: _Table,
) -> None:
    window, _, hand = _tables()
    table.put(window)
    summary = table.payloads(0)["summary"]
    rows = table.payloads(0)["actions"]["actions"]
    (row,) = (
        row
        for row in rows
        if row["action_id"] == "discard_snooper_card"
        and row["arguments"]["card_id"] == DELEGATE
    )
    sent = table.seats[0].post(
        f"/games/{table.game_id}/actions",
        json={
            "seat": 0,
            "revision": summary["revision"],
            "undo_count": summary["undo_count"],
            "index": row["index"],
        },
    )
    assert sent.status_code == 200, sent.text

    still_hidden = [card for card in hand if card != DELEGATE]
    for seat in range(4):
        payloads = table.payloads(seat)
        player = payloads["view"]["players"][0]
        assert DELEGATE in player["discard_pile"], seat
        assert player["resources"]["solari"] == 3 and player["resources"]["spice"] == 1
        (entry,) = (
            entry
            for entry in payloads["log"]["entries"]
            if entry["action_id"] == "discard_snooper_card"
        )
        # The step's argument was a card hidden in her hand when she chose it:
        # the log redacts it for the others as it does every such choice; the
        # discard itself is public, in its event as in her discard pile.
        assert entry["arguments"] == {
            "card_id": DELEGATE if seat == 0 else "(비공개)"
        }, seat
        assert {
            "kind": "card_discarded",
            "payload": {"card_id": DELEGATE, "player": 0},
        } in entry["events"], seat
        gains = [
            event["payload"]
            for event in entry["events"]
            if event["kind"] == "resources_gained"
        ]
        # CHOAM Delegate's Unload (3 Solari) before the reward's spice.
        assert [gain.get("solari", 0) for gain in gains] == [3, 0], seat
        assert [gain.get("spice", 0) for gain in gains] == [0, 1], seat
        if seat != 0:
            text = json.dumps(payloads)
            for card in still_hidden:
                assert card not in text, (seat, card)
    spectator = json.dumps(table.payloads(None))
    for card in hand:
        assert card not in spectator, card
