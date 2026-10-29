"""Tessia Vernius' Snooper reward 1 outside her turn, through the remote
server's seat cookies over a real socket (needs the ``ui`` extra).

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
never did (her hand is empty in Combat: a Reveal shows the whole hand). So
this test plays a real game up to Tessia's Combat reward (``PLAN``: original +
Rise of Ix with the leader draft, seed 4; she is seat 1 with Bene Gesserit
Influence 1 and her four tokens), gives her a hand there -- CHOAM Delegate
from the Imperium deck and her deck's top two cards, the one change made
outside the rules -- and then plays the rest through the server: she takes
the Influence reward on Bene Gesserit, reaches her first token, and the
window opens over the Combat reward frame it interrupts. Four clients each
claim one seat (one cookie each) and a fifth claims none; every request,
the event stream included, goes over a real uvicorn socket, as a browser's
would. The page draws the window as every other ``OPTIONAL_DISCARD`` window;
the browser side of those is covered by the e2e scripts.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from types import TracebackType
from typing import Any, Self

import httpx2
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")

import uvicorn  # noqa: E402
from fastapi import FastAPI  # noqa: E402

from dune_imperium.core import GameState  # noqa: E402
from dune_imperium.rules.frames import FrameKind  # noqa: E402
from dune_imperium.server.access import AccessMode  # noqa: E402
from dune_imperium.server.app import create_app  # noqa: E402
from dune_imperium.server.sessions import GameSessionManager  # noqa: E402

ADMIN_KEY = "tessia-window-admin-key"
TESSIA = 1
BODY = {
    "seats": ["human"] * 4,
    "base_game": "imperium",
    "rise_of_ix": True,
    "leader_draft": True,
    "game_seed": 4,
}
# CHOAM Delegate's Unload box gives 3 Solari (the engine's Tessia test).
DELEGATE = "imperium:choam_delegate:0"
# Her deck at the Combat reward: Convincing Argument 0, Dune, the Desert Planet
# 0, Signet Ring 0, Reconnaissance 0, Seek Allies 0. The hand she is given, and
# two twins of it that own the same cards: one hidden starter card traded for
# another of another name, and CHOAM Delegate itself traded for one.
ARGUMENT = "player:1:starter:convincing_argument:0"
DUNE = "player:1:starter:dune_the_desert_planet:0"
SIGNET = "player:1:starter:signet_ring:0"
HAND = (DELEGATE, ARGUMENT, DUNE)
TWIN_STARTER = (DELEGATE, ARGUMENT, SIGNET)
TWIN_DELEGATE = (SIGNET, ARGUMENT, DUNE)
# What differs between two games of one table whatever their hidden cards:
# the game's id and log epoch, the play clock, who is online, the doorbell's
# sequence; and an event's raw text, which is its data (compared) with those.
VOLATILE = frozenset(
    {"game_id", "epoch", "clock", "clock_age_ms", "online", "seq", "raw"}
)
_DEADLINE = 5.0

# (seat, action id, arguments), in order; the number after each is its index.
# Found on the engine as merged with P4 6c6b747e (scratch ``find8.py``: the
# draft gives one seat Tessia, who deploys every troop offered; other answers
# at random, stream 4 * 1000 + 2): it ends at her Combat reward decision.
PLAN: list[tuple[int, str, dict[str, Any]]] = [
    (1, "pick_leader", {"leader_id": "tessia_vernius"}),  # 0
    (0, "pick_leader", {"leader_id": "ilesa_ecaz"}),  # 1
    (3, "pick_leader", {"leader_id": "paul_atreides"}),  # 2
    (2, "pick_leader", {"leader_id": "viscount_hundro_moritani"}),  # 3
    (2, "finish_leader_draft", {}),  # 4
    (2, "keep_peeked_intrigue", {"instance_id": "intrigue:know_their_ways:0"}),  # 5
    (
        0,
        "set_aside_leader_card",
        {"card_id": "player:0:starter:convincing_argument:0"},
    ),  # 6
    (2, "play_intrigue", {"card_id": "intrigue:know_their_ways:0", "option": 0}),  # 7
    (2, "choose_agent_card", {"card_id": "player:2:starter:reconnaissance:0"}),  # 8
    (2, "place_agent", {"space_id": "arrakeen"}),  # 9
    (2, "deploy_troops", {"count": 1}),  # 10
    (2, "withdraw_troops", {"count": 1}),  # 11
    (2, "resolve_board_effect", {"effect": "troops"}),  # 12
    (2, "deploy_troops", {"count": 2}),  # 13
    (2, "deploy_troops", {"count": 1}),  # 14
    (2, "withdraw_troops", {"count": 2}),  # 15
    (2, "resolve_board_effect", {"effect": "cards"}),  # 16
    (2, "withdraw_troops", {"count": 1}),  # 17
    (2, "finish_agent_turn", {}),  # 18
    (3, "choose_agent_card", {"card_id": "player:3:starter:seek_allies:0"}),  # 19
    (3, "place_agent", {"space_id": "wealth"}),  # 20
    (3, "resolve_board_effect", {"effect": "resources"}),  # 21
    (3, "resolve_agent_card_effect", {}),  # 22
    (3, "resolve_faction_influence", {}),  # 23
    (3, "finish_agent_turn", {}),  # 24
    (0, "choose_agent_card", {"card_id": "player:0:starter:dagger:1"}),  # 25
    (0, "place_agent", {"space_id": "tech_negotiation"}),  # 26
    (0, "place_board_negotiator", {}),  # 27
    (0, "finish_agent_turn", {}),  # 28
    (
        1,
        "choose_agent_card",
        {"card_id": "player:1:starter:dune_the_desert_planet:1"},
    ),  # 29
    (1, "place_agent", {"space_id": "imperium_hagga_basin"}),  # 30
    (1, "deploy_troops", {"count": 2}),  # 31
    (1, "harvest_maker_spice", {"space_id": "imperium_hagga_basin"}),  # 32
    (1, "finish_agent_turn", {}),  # 33
    (
        2,
        "choose_agent_card",
        {"card_id": "player:2:starter:dune_the_desert_planet:1"},
    ),  # 34
    (2, "place_agent", {"space_id": "imperial_basin"}),  # 35
    (2, "deploy_troops", {"count": 2}),  # 36
    (2, "withdraw_troops", {"count": 1}),  # 37
    (2, "deploy_troops", {"count": 1}),  # 38
    (2, "withdraw_troops", {"count": 1}),  # 39
    (2, "deploy_troops", {"count": 1}),  # 40
    (2, "harvest_maker_spice", {"space_id": "imperial_basin"}),  # 41
    (2, "withdraw_troops", {"count": 1}),  # 42
    (2, "finish_agent_turn", {}),  # 43
    (3, "reveal_turn", {}),  # 44
    (3, "acquire_imperium", {"instance_id": "imperium:sardaukar_infantry:1"}),  # 45
    (3, "acquire_imperium", {"instance_id": "imperium:guild_administrator:1"}),  # 46
    (3, "finish_reveal", {}),  # 47
    (
        0,
        "choose_agent_card",
        {"card_id": "player:0:starter:dune_the_desert_planet:1"},
    ),  # 48
    (0, "place_agent", {"space_id": "smuggling"}),  # 49
    (0, "resolve_board_effect", {"effect": "resources"}),  # 50
    (0, "finish_agent_turn", {}),  # 51
    (1, "choose_agent_card", {"card_id": "player:1:starter:diplomacy:0"}),  # 52
    (1, "place_agent", {"space_id": "secrets"}),  # 53
    (1, "resolve_board_effect", {"effect": "intrigue"}),  # 54
    (1, "resolve_faction_influence", {}),  # 55
    (1, "finish_agent_turn", {}),  # 56
    (2, "reveal_turn", {}),  # 57
    (2, "acquire_imperium", {"instance_id": "imperium:fremen_camp:0"}),  # 58
    (2, "finish_reveal", {}),  # 59
    (0, "reveal_turn", {}),  # 60
    (0, "finish_reveal", {}),  # 61
    (1, "play_intrigue", {"card_id": "intrigue:charisma:0", "option": 0}),  # 62
    (1, "reveal_turn", {}),  # 63
    (1, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 64
    (1, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 65
    (1, "finish_reveal", {}),  # 66
    (2, "pass_combat_intrigue", {}),  # 67
    (1, "pass_combat_intrigue", {}),  # 68
]


class LiveServer:
    """One app on a real uvicorn server on a background thread (as in
    ``test_events_app``: Starlette's ``TestClient`` buffers a response's whole
    body, so it cannot read an endless event stream)."""

    def __init__(self, app: FastAPI) -> None:
        self._server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=0,
                log_level="warning",
                timeout_graceful_shutdown=1,
            )
        )
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self.base_url = ""

    def __enter__(self) -> Self:
        self._thread.start()
        deadline = time.monotonic() + 10
        while not self._server.started:
            assert time.monotonic() < deadline, "server did not start"
            time.sleep(0.01)
        port = self._server.servers[0].sockets[0].getsockname()[1]
        self.base_url = f"http://127.0.0.1:{port}"
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=10)
        assert not self._thread.is_alive(), "server did not stop"


def _next_event(lines: Iterator[str]) -> dict[str, Any]:
    """The next named event's raw text and payload, heartbeats skipped."""

    while True:
        block: list[str] = []
        for line in lines:
            if line == "":
                break
            block.append(line)
        else:
            raise AssertionError("the stream ended before an event")
        if block and not block[0].startswith(":"):
            text = "\n".join(block)
            data = next(line for line in block if line.startswith("data: "))
            return {"raw": text, "data": json.loads(data.removeprefix("data: "))}


def _steady(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {k: _steady(v) for k, v in payload.items() if k not in VOLATILE}
    if isinstance(payload, list):
        return [_steady(value) for value in payload]
    return payload


def _hand(state: GameState, hand: tuple[str, ...]) -> GameState:
    """Tessia holds ``hand``: the cards come from her deck, CHOAM Delegate from
    the Imperium deck (into her deck when not in her hand), so the two twins
    below own the same cards."""

    owner = state.players[TESSIA]
    pool = [*owner.deck, DELEGATE]
    assert all(card in pool for card in hand)
    tessia = replace(
        owner, hand=hand, deck=tuple(card for card in pool if card not in hand)
    )
    players = list(state.players)
    players[TESSIA] = tessia
    return replace(
        state,
        players=tuple(players),
        imperium_deck=tuple(card for card in state.imperium_deck if card != DELEGATE),
    )


class _Table:
    """A remote game on a live server: four clients each claim one seat (each
    holds its own seat cookie) and a fifth claims none."""

    def __init__(self, tmp_path: Path) -> None:
        self.manager = GameSessionManager(access=AccessMode.REMOTE, admin_key=ADMIN_KEY)
        self.app = create_app(
            self.manager,
            saves_dir=tmp_path / "saves",
            card_images_dir=tmp_path / "no-images",
            icons_dir=tmp_path / "no-icons",
            tokens_dir=tmp_path / "no-tokens",
            board_image=tmp_path / "no-map.jpg",
            bene_tleilax_image=tmp_path / "no-bene-tleilax.jpg",
        )

    def open(self, server: LiveServer) -> None:
        def client() -> httpx2.Client:
            return httpx2.Client(
                base_url=server.base_url, timeout=httpx2.Timeout(_DEADLINE)
            )

        host = client()
        assert host.post("/auth/admin", json={"key": ADMIN_KEY}).status_code == 200
        created = host.post("/games", json=BODY)
        assert created.status_code == 200, created.text
        self.game_id = created.json()["game_id"]
        self.seats = []
        for seat in range(4):
            seat_client = client()
            claimed = seat_client.post(
                f"/games/{self.game_id}/seats/{seat}/claim", json={"name": f"P{seat}"}
            )
            assert claimed.status_code == 200, claimed.text
            self.seats.append(seat_client)
        self.spectator = client()
        host.close()

    def close(self) -> None:
        for client in [*self.seats, self.spectator]:
            client.close()

    def summary(self) -> dict[str, Any]:
        response = self.spectator.get(f"/games/{self.game_id}")
        assert response.status_code == 200, response.text
        return dict(response.json())

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
        listed = self.seats[seat].get(f"{game}/seats/{seat}/actions").json()
        rows = [
            row
            for row in listed["actions"]
            if row["action_id"] == action_id and (row["arguments"] or {}) == arguments
        ]
        assert len(rows) == 1, (seat, action_id, arguments, listed["actions"][:12])
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

    def to_the_window(self, hand: tuple[str, ...]) -> list[dict[str, Any]]:
        """Play ``PLAN``, give Tessia ``hand``, take the Influence reward on Bene
        Gesserit: her first token opens the window. Returns the other readers'
        payloads at the three moments (her hand given, the Influence chosen,
        the window open)."""

        for seat, action_id, arguments in PLAN:
            self.take(seat, action_id, arguments)
        session = self.manager._get(self.game_id)
        state = session.state
        assert [frame.kind for frame in state.decision_stack] == [
            FrameKind.COMBAT_REWARD_ICONS
        ]
        assert state.players[TESSIA].influence.bene_gesserit == 1
        assert len(state.players[TESSIA].snooper_faction_ids) == 4
        session.state = _hand(state, hand)
        moments = [self.others()]
        self.take(TESSIA, "resolve_combat_reward_icon", {"effect": "choose_influence"})
        moments.append(self.others())
        self.take(
            TESSIA, "choose_combat_reward_influence", {"faction": "bene_gesserit"}
        )
        kinds = [
            frame.kind for frame in self.manager._get(self.game_id).state.decision_stack
        ]
        assert kinds[-1] == FrameKind.OPTIONAL_DISCARD, kinds
        assert FrameKind.COMBAT_REWARD_ICONS in kinds[:-1], kinds
        moments.append(self.others())
        return moments

    def payloads(self, seat: int | None, *, ledger: bool = True) -> dict[str, Any]:
        """Everything a reader fetches with its own cookie, by name, and the
        event stream's first message. The VP ledger replays the session's steps
        from its start, which do not hold the hand given outside the rules: it
        is read up to the window, not after a discard from that hand."""

        game = f"/games/{self.game_id}"
        client = self.spectator if seat is None else self.seats[seat]
        paths = {"summary": game, "seatless": f"{game}/snapshot"}
        if ledger:
            paths["ledger"] = f"{game}/vp-ledger"
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
            # The VP ledger opens to a seat cookie (the spectator's is refused
            # until the game ends); every other read is the reader's own.
            assert response.status_code == (
                403 if seat is None and name == "ledger" else 200
            ), (
                seat,
                path,
                response.text,
            )
            found[name] = response.json()
        with client.stream("GET", f"{game}/events") as stream:
            found["events"] = _next_event(stream.iter_lines())
        return found

    def others(self, *, ledger: bool = True) -> dict[str, Any]:
        """The payloads of every reader but Tessia's seat."""

        readers: dict[str, Any] = {
            f"seat {seat}": self.payloads(seat, ledger=ledger)
            for seat in range(4)
            if seat != TESSIA
        }
        readers["spectator"] = self.payloads(None, ledger=ledger)
        return readers


def _marks(client: httpx2.Client, card: str) -> list[str]:
    """What names ``card`` besides its id: its English and Korean names and the
    paths of its pictures, from the server's own catalog. Not its base id:
    her public deck pool lists the cards she owns by base id (OQ-010 ruling
    6), and she owns it."""

    entry = client.get("/catalog").json()["cards"][card.split(":")[1]]
    return [
        mark
        for mark in (
            entry.get("name"),
            entry.get("name_ko"),
            *(str(entry.get(key) or "").split("?")[0] for key in ("image", "image_ko")),
        )
        if mark
    ]


@pytest.fixture
def table(tmp_path: Path) -> Iterator[_Table]:
    table = _Table(tmp_path)
    with LiveServer(table.app) as server:
        table.open(server)
        try:
            yield table
        finally:
            table.close()


def _leaks(
    payloads: dict[str, Any], cards: tuple[str, ...], marks: list[str]
) -> list[str]:
    text = json.dumps(payloads, ensure_ascii=False)
    return [mark for mark in (*cards, *marks) if mark in text]


def test_the_window_and_her_hand_reach_tessia_alone(table: _Table) -> None:
    others = table.to_the_window(HAND)[-1]
    own = table.payloads(TESSIA)
    assert own["summary"]["decision"] == {
        **own["summary"]["decision"],
        "kind": "optional_discard",
        "owner": TESSIA,
    }
    assert own["view"]["private"]["hand"] == list(HAND)
    rows = own["actions"]["actions"]
    discards = sorted(
        row["arguments"]["card_id"]
        for row in rows
        if row["action_id"] == "discard_snooper_card"
    )
    assert discards == sorted(HAND)
    assert any(row["action_id"] == "decline_snooper_discard" for row in rows)

    # Nothing of her hand reaches another seat or the spectator: no card id,
    # no row, and not CHOAM Delegate's names or pictures (the starter cards'
    # names are every seat's own cards' too, the twins below cover them).
    marks = _marks(table.spectator, DELEGATE)
    assert marks
    for name, payloads in others.items():
        assert not _leaks(payloads, HAND, marks), name
        assert "discard_snooper_card" not in json.dumps(payloads), name
        if name != "spectator":
            assert payloads["view"]["players"][TESSIA]["hand_size"] == len(HAND)
            assert payloads["actions"]["actions"] == [], name
    # Her own view, actions, snapshot and log are refused to everyone else.
    game = f"/games/{table.game_id}"
    for client in [*(table.seats[s] for s in range(4) if s != TESSIA), table.spectator]:
        for url in (
            f"{game}/seats/{TESSIA}/view",
            f"{game}/seats/{TESSIA}/actions",
            f"{game}/snapshot?seat={TESSIA}",
            f"{game}/log?seat={TESSIA}",
        ):
            assert client.get(url).status_code == 403, url


@pytest.mark.parametrize(
    "twin", [TWIN_STARTER, TWIN_DELEGATE], ids=["starter", "delegate"]
)
def test_another_hand_changes_nothing_another_reader_receives(
    tmp_path: Path, table: _Table, twin: tuple[str, ...]
) -> None:
    """The twin game: the same table where her hand differs in one card (a
    starter card, or CHOAM Delegate itself, traded for a card of another
    name from her deck). At her hand given, the Influence chosen and the
    window open, every other seat's and the spectator's payloads and event
    stream are the same in both games: neither which cards she holds nor
    their names, base ids, pictures or a count reaches them."""

    first = table.to_the_window(HAND)
    other = _Table(tmp_path / "twin")
    with LiveServer(other.app) as server:
        other.open(server)
        try:
            second = other.to_the_window(twin)
            own = other.payloads(TESSIA)["view"]["private"]["hand"]
            if DELEGATE in twin:
                # Both hands hold CHOAM Delegate: both discard it, and what is
                # left in her hand differs by one card of another name.
                for game in (table, other):
                    game.take(TESSIA, "discard_snooper_card", {"card_id": DELEGATE})
                first.append(table.others(ledger=False))
                second.append(other.others(ledger=False))
        finally:
            other.close()
    assert own == list(twin)
    for moment, (one, two) in enumerate(zip(first, second, strict=True)):
        assert _steady(one) == _steady(two), moment


def test_the_discard_turns_public_its_unload_first_and_combat_goes_on(
    tmp_path: Path, table: _Table
) -> None:
    table.to_the_window(HAND)
    # Every reader listens to the event stream while she discards.
    game = f"/games/{table.game_id}"
    readers = [*table.seats, table.spectator]
    streams = [client.stream("GET", f"{game}/events") for client in readers]
    opened = [stream.__enter__() for stream in streams]
    lines = [response.iter_lines() for response in opened]
    try:
        for each in lines:
            _next_event(each)
        table.take(TESSIA, "discard_snooper_card", {"card_id": DELEGATE})
        rung = [_next_event(each) for each in lines]
    finally:
        for stream in streams:
            stream.__exit__(None, None, None)
    still_hidden = tuple(card for card in HAND if card != DELEGATE)
    for seat, message in enumerate(rung):
        if seat != TESSIA:
            assert not [card for card in HAND if card in message["raw"]], seat

    for seat in range(4):
        payloads = table.payloads(seat, ledger=False)
        player = payloads["view"]["players"][TESSIA]
        assert DELEGATE in player["discard_pile"], seat
        (entry,) = (
            entry
            for entry in payloads["log"]["entries"]
            if entry["action_id"] == "discard_snooper_card"
        )
        # The step names the discarded card, public once discarded, or redacts
        # the choice of a hand card for the others; never another card. The
        # discard itself is public, in its event as in her discard pile.
        assert entry["arguments"]["card_id"] in (
            (DELEGATE,) if seat == TESSIA else (DELEGATE, "(비공개)")
        ), seat
        assert {
            "kind": "card_discarded",
            "payload": {"card_id": DELEGATE, "player": TESSIA},
        } in entry["events"], seat
        gains = [
            event["payload"]
            for event in entry["events"]
            if event["kind"] == "resources_gained"
        ]
        # CHOAM Delegate's Unload (3 Solari) before the reward's spice.
        assert [gain.get("solari", 0) for gain in gains] == [3, 0], seat
        assert [gain.get("spice", 0) for gain in gains] == [0, 1], seat
        if seat != TESSIA:
            assert not [card for card in still_hidden if card in json.dumps(payloads)]
    spectator = json.dumps(table.payloads(None, ledger=False))
    assert not [card for card in HAND if card in spectator]

    # The Combat reward frame the window interrupted goes on: her other icon.
    summary = table.summary()
    assert summary["decision"]["kind"] == "combat_reward_icons"
    assert summary["decision"]["owner"] == TESSIA
    kinds = [
        frame.kind for frame in table.manager._get(table.game_id).state.decision_stack
    ]
    assert kinds == [FrameKind.COMBAT_REWARD_ICONS], kinds
    left = table.payloads(TESSIA, ledger=False)["actions"]["actions"]
    assert {(row["action_id"], row["arguments"].get("effect")) for row in left} == {
        ("resolve_combat_reward_icon", "resources")
    }
