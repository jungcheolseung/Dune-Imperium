"""Secrets in the Desert's face-down Intrigue cards through the remote server's
seat cookies (needs the ``ui`` extra; the Codex review of stage P8b).

The original game's mission Botanical Testing - Secrets in the Desert puts the
top two Intrigue cards face down on the Research Station, and a seat that sends
an Agent there "may" take one (docs/rules/arrakeen-scouts.md 9a). The rules of
what a seat may see (docs/rules/information-visibility.md): a face-down card of
a space is known to nobody until it is taken, and a held Intrigue card is its
owner's alone. ``known_card_seats`` lists the cards on the space as known to no
seat and the taken one as known to its taker, which is all the server reads:
the log shows each other seat only that a card was drawn, a step that gave a
seat a card nobody knew cannot be taken back (the Emperor's Schemes take is the
same, ``session_log.reveals_hidden_information``), and a save keeps what is
still face down on the space hidden.

A real game reaches the visit only after the schedule has drawn the mission in
round 2 or 3 and a seat holds the two water the space costs: this test plays
one through the server's own table, four human seats and a seatless spectator,
over a plan it finds first on the engine (``_find_plan``: seeded random seats,
the Reveal preferred, the first seed whose game reaches a seat that may send an
Agent to the Research Station with both cards on it). Nothing is set outside the
rules, so the save below replays the game from its record.

The second half of the file is the original Covert Operation's Faction pick (the
Codex review of stage P8c): two of its four lines give Influence with a Faction
named when the pick is made, and "진영은 선택과 함께 숨는다"
(docs/rules/arrakeen-scouts.md 9a, the ``imperium_covert_operation`` row; 7,
secret picks; OQ-085). The pick is one action ``scouts_secret_pick(faction=...,
pick=...)``; the Faction is ``GameState.scouts_secret_factions``, shown only in
the chooser's ``PrivatePlayerView.scouts_secret_factions``
(docs/rules/information-visibility.md: only the chooser sees its pick), the log
shows the other seats only ``{"pick": "(비공개)"}``, and the reveal event
``scouts_secret_revealed`` carries the Faction. The plan (``_find_covert_game``)
is found on the engine the same way, with the four seats' picks forced when the
event is drawn.
"""

from __future__ import annotations

import copy
import json
import random
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from dune_imperium import BaseGame, RulesetConfig  # noqa: E402
from dune_imperium.agents.agent_turn_steps import apply_whole  # noqa: E402
from dune_imperium.core import ChanceDecision, ChanceResolver  # noqa: E402
from dune_imperium.core.decisions import PlayerDecision  # noqa: E402
from dune_imperium.core.observation import (  # noqa: E402
    known_card_seats,
    secret_pick_id,
)
from dune_imperium.core.state import canonical_state_hash  # noqa: E402
from dune_imperium.rules import UprisingRulesEngine  # noqa: E402
from dune_imperium.rules.frames import FrameKind  # noqa: E402
from dune_imperium.server.access import AccessMode  # noqa: E402
from dune_imperium.server.app import create_app  # noqa: E402
from dune_imperium.server.sessions import GameSessionManager  # noqa: E402

ADMIN_KEY = "scouts-original-payload-admin-key"
MISSION = "botanical_secrets_in_the_desert"
SPACE = "imperium_research_station"
CONFIG = RulesetConfig(
    base_game=BaseGame.IMPERIUM, arrakeen_scouts=True, first_player_seat_zero=True
)
# The seeds the plan search tries, the one a game of this engine reached the
# visit with first: a change of the rules may move the first that does.
_SEEDS = (47, *range(0, 60))
_STREAMS = range(6)
_MAX_STEPS = 160
_PREFER_REVEAL = 0.8
type Plan = list[tuple[int, str, dict[str, Any]]]


@cache
def _find_plan() -> tuple[int, Plan]:
    """(game seed, whole actions) of a game that stops with a seat to place an
    Agent on the Research Station while Secrets in the Desert's two cards lie
    there; found on the engine with every seat playing a seeded random move
    (the Reveal preferred, to reach the third round quickly), the way the
    server's table plays it back."""

    for seed in dict.fromkeys(_SEEDS):
        for stream in _STREAMS:
            plan = _play(seed, stream)
            if plan is not None:
                return seed, plan
    raise AssertionError("no seed reaches a visit to the Research Station")


def _play(seed: int, stream: int) -> Plan | None:
    engine = UprisingRulesEngine()
    state = engine.reset(CONFIG, seed)
    chance = ChanceResolver(seed=seed)
    rng = random.Random(stream)
    plan: Plan = []
    for _ in range(_MAX_STEPS):
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = apply_whole(engine, state, chance.resolve(decision)).state
            continue
        if not isinstance(decision, PlayerDecision):
            return None
        seat = decision.owner
        actions = engine.whole_actions(state, seat)
        if not actions:
            return None
        if sum(
            row[0] == MISSION and row[1] == SPACE for row in state.scouts_goods_cards
        ) == 2 and any(
            action.action_id == "place_agent"
            and dict(action.arguments).get("space_id") == SPACE
            for action in actions
        ):
            return plan
        reveals = [action for action in actions if action.action_id == "reveal_turn"]
        action = (
            reveals[0]
            if reveals and rng.random() < _PREFER_REVEAL
            else rng.choice(actions)
        )
        plan.append((seat, action.action_id, dict(action.arguments)))
        state = apply_whole(engine, state, action).state
    return None


class _Table:
    """A remote game: four clients each claim one seat (each holds its own
    seat cookie), a fifth claims none."""

    def __init__(self, tmp_path: Path, seed: int) -> None:
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
        self.host = TestClient(self.app)
        assert self.host.post("/auth/admin", json={"key": ADMIN_KEY}).status_code == 200
        created = self.host.post(
            "/games",
            json={
                "seats": ["human"] * 4,
                "base_game": "imperium",
                "arrakeen_scouts": True,
                "first_player_seat_zero": True,
                "game_seed": seed,
            },
        )
        assert created.status_code == 200, created.text
        self.game_id = created.json()["game_id"]
        self.seats = self.claim(self.game_id)
        self.spectator = TestClient(self.app)

    def claim(self, game_id: str) -> list[TestClient]:
        clients = []
        for seat in range(4):
            client = TestClient(self.app)
            claimed = client.post(
                f"/games/{game_id}/seats/{seat}/claim", json={"name": f"P{seat}"}
            )
            assert claimed.status_code == 200, claimed.text
            clients.append(client)
        return clients

    def summary(self, game_id: str | None = None) -> dict[str, Any]:
        response = self.spectator.get(f"/games/{game_id or self.game_id}")
        assert response.status_code == 200, response.text
        return dict(response.json())

    def rows(
        self,
        seat: int,
        game_id: str | None = None,
        seats: list[TestClient] | None = None,
    ) -> list[dict[str, Any]]:
        client = (seats or self.seats)[seat]
        game = game_id or self.game_id
        response = client.get(f"/games/{game}/seats/{seat}/actions")
        assert response.status_code == 200, response.text
        return list(response.json()["actions"])

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

    def to_the_visit(self, plan: Plan) -> int:
        """Play ``plan``; the seat to move may send an Agent to the Research
        Station. Returns that seat."""

        for seat, action_id, arguments in plan:
            self.take(seat, action_id, arguments)
        owner = self.summary()["decision"]["owner"]
        assert isinstance(owner, int)
        assert {"place_agent"} <= {row["action_id"] for row in self.rows(owner)}
        return owner

    def payloads(
        self,
        seat: int | None,
        game_id: str | None = None,
        seats: list[TestClient] | None = None,
    ) -> dict[str, Any]:
        """Everything a reader fetches with its own cookie: the table's
        summary and seatless snapshot, and for a seat its view, actions,
        snapshot and log."""

        game = f"/games/{game_id or self.game_id}"
        client = self.spectator if seat is None else (seats or self.seats)[seat]
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
        return found

    def leaks(
        self,
        cards: tuple[str, ...],
        game_id: str | None = None,
        seats: list[TestClient] | None = None,
    ) -> dict[str, list[str]]:
        """The cards each reader's payloads name, by reader."""

        found: dict[str, list[str]] = {}
        for seat in (None, 0, 1, 2, 3):
            text = json.dumps(self.payloads(seat, game_id, seats), ensure_ascii=False)
            found["spectator" if seat is None else f"seat {seat}"] = [
                card for card in cards if card in text
            ]
        return found

    def state(self, game_id: str | None = None) -> Any:
        return self.manager._get(game_id or self.game_id).state

    def restored(self, save_id: str) -> _Table:
        """The same server with the game loaded from ``save_id`` as its game:
        its seats claimed again, every helper above reading and playing it."""

        loaded = self.host.post(f"/saves/{save_id}/load")
        assert loaded.status_code == 200, loaded.text
        game_id = loaded.json()["game_id"]
        assert game_id != self.game_id
        other = copy.copy(self)
        other.game_id = game_id
        other.seats = self.claim(game_id)
        return other

    def save(self) -> str:
        saved = self.host.post(f"/games/{self.game_id}/save", json={})
        assert saved.status_code == 200, saved.text
        return str(saved.json()["save_id"])


@pytest.fixture
def table(tmp_path: Path) -> _Table:
    seed, _ = _find_plan()
    return _Table(tmp_path, seed)


def _cards_on_the_space(table: _Table) -> tuple[str, ...]:
    return tuple(
        card
        for mission, space, card in table.state().scouts_goods_cards
        if (mission, space) == (MISSION, SPACE)
    )


def _knowers(state: Any, card: str) -> frozenset[int]:
    """The seats that know ``card`` (``known_card_seats``): none of them for a
    face-down card, its owner for a held Intrigue card."""

    return known_card_seats(state).get(card, frozenset(range(4)))


def _visit_and_take(table: _Table) -> tuple[int, str, str]:
    """The seat to move sends an Agent to the Research Station and takes a
    card: (the seat, the card it took, the card left on the space)."""

    _, plan = _find_plan()
    visitor = table.to_the_visit(plan)
    first, second = _cards_on_the_space(table)
    table.take(visitor, "place_agent", {"space_id": SPACE})
    table.take(visitor, "scouts_collect_mission", {"choice": "take"})
    return visitor, first, second


def test_no_seat_names_a_face_down_card_before_it_is_taken(table: _Table) -> None:
    _, plan = _find_plan()
    table.to_the_visit(plan)
    first, second = _cards_on_the_space(table)
    assert known_card_seats(table.state())[first] == frozenset()
    assert known_card_seats(table.state())[second] == frozenset()
    for reader, named in table.leaks((first, second)).items():
        assert named == [], reader


def test_only_the_taking_seat_names_the_card_it_took(table: _Table) -> None:
    visitor, taken, left = _visit_and_take(table)
    state = table.state()
    # The card moved from the space to the visitor's hand; the other stays.
    assert taken in state.players[visitor].intrigue_cards
    assert _cards_on_the_space(table) == (left,)
    assert _knowers(state, taken) == frozenset({visitor})
    assert _knowers(state, left) == frozenset()

    leaks = table.leaks((taken, left))
    assert leaks[f"seat {visitor}"] == [taken]
    assert table.payloads(visitor)["view"]["private"]["intrigue_cards"] == [taken]
    for reader, named in leaks.items():
        if reader != f"seat {visitor}":
            assert named == [], reader

    # The log tells every other seat only that a card was drawn: the event's
    # payload holds a count and the seat, no card, and no row names one.
    for seat in range(4):
        log = table.seats[seat].get(f"/games/{table.game_id}/log?seat={seat}").json()
        step = next(
            entry
            for entry in reversed(log["entries"])
            if entry.get("action_id") == "scouts_collect_mission"
        )
        assert step["arguments"] == {"choice": "take"}
        assert step["events"] == [
            {"kind": "intrigue_card_drawn", "payload": {"count": 1, "player": visitor}}
        ]


def test_the_take_cannot_be_taken_back_nor_anything_before_it(table: _Table) -> None:
    """The step gave a seat a card nobody knew, so it is a reveal
    (``reveals_hidden_information``): the seat's undo window closes at it, as it
    does at an Emperor's Schemes take. Before it, the seat's card pick and
    placement could be taken back."""

    _, plan = _find_plan()
    visitor = table.to_the_visit(plan)
    table.take(visitor, "place_agent", {"space_id": SPACE})
    assert {"seat": visitor, "steps": 2} in table.summary()["undo"]

    table.take(visitor, "scouts_collect_mission", {"choice": "take"})
    summary = table.summary()
    assert all(window["seat"] != visitor for window in summary["undo"])
    refused = table.seats[visitor].post(
        f"/games/{table.game_id}/undo",
        json={
            "seat": visitor,
            "revision": summary["revision"],
            "steps": 1,
            "undo_count": summary["undo_count"],
        },
    )
    assert refused.status_code == 400, refused.text
    assert "at most 0 step" in refused.text
    # Nothing changed: the card is still the visitor's.
    assert len(table.state().players[visitor].intrigue_cards) >= 1


def test_a_save_keeps_the_card_on_the_space_hidden_and_the_game_goes_on(
    table: _Table,
) -> None:
    visitor, taken, left = _visit_and_take(table)
    saved = table.host.post(f"/games/{table.game_id}/save", json={})
    assert saved.status_code == 200, saved.text
    loaded = table.host.post(f"/saves/{saved.json()['save_id']}/load")
    assert loaded.status_code == 200, loaded.text
    game_id = loaded.json()["game_id"]
    assert game_id != table.game_id
    seats = table.claim(game_id)

    # The card is where it was and still face down: on the space, known to no
    # seat, and in no reader's payload; the taker's own card is still its own.
    state = table.state(game_id)
    assert [row[2] for row in state.scouts_goods_cards if row[1] == SPACE] == [left]
    assert _knowers(state, left) == frozenset()
    assert taken in state.players[visitor].intrigue_cards
    assert _knowers(state, taken) == frozenset({visitor})
    leaks = table.leaks((taken, left), game_id, seats)
    assert leaks[f"seat {visitor}"] == [taken]
    for reader, named in leaks.items():
        if reader != f"seat {visitor}":
            assert named == [], reader

    # The game goes on: whoever holds the decision answers it, step after step.
    revision = loaded.json()["revision"]
    for _ in range(8):
        summary = table.summary(game_id)
        owner = summary["decision"]["owner"]
        rows = table.rows(owner, game_id, seats)
        assert rows, summary["decision"]
        sent = seats[owner].post(
            f"/games/{game_id}/actions",
            json={
                "seat": owner,
                "revision": summary["revision"],
                "undo_count": summary["undo_count"],
                "index": rows[0]["index"],
            },
        )
        assert sent.status_code == 200, sent.text
    assert table.summary(game_id)["revision"] > revision
    # Whoever knows the card afterwards (a seat that took it in the meantime)
    # and nobody else names it.
    state = table.state(game_id)
    for seat in range(4):
        text = json.dumps(table.payloads(seat, game_id, seats), ensure_ascii=False)
        assert (left in text) <= (seat in _knowers(state, left)), seat


# --- The original Covert Operation's Faction pick (stage P8c) ----------------------

COVERT = "imperium_covert_operation"
# The four seats' picks, in the order the seats make them (the First Player
# first), as (line, Faction or ""): every line once, the two that name a
# Faction (1 and 3, docs/rules/arrakeen-scouts.md 9a) by seats that are not
# next to each other. The first seat's line is due the next round, the third
# seat's one round after that.
_COVERT_LINES = ((1, "fremen"), (0, ""), (3, "spacing_guild"), (2, ""))
# The Faction the first seat names first and then takes back, and, for the
# comparison games, the Faction each named one swapped for.
_FIRST_TRY = "emperor"
_SWAPPED = {"fremen": "emperor", "spacing_guild": "bene_gesserit"}
_FACTIONS = ("emperor", "spacing_guild", "bene_gesserit", "fremen")
# The seed the plan search tries first (a game of this engine whose Covert
# Operation comes in round 4): a change of the rules may move the first that
# works.
_COVERT_SEEDS = (11, *range(0, 60))
_COVERT_MAX_STEPS = 600
_NOISE = frozenset({"clock", "clock_age_ms", "revision", "undo_count", "log_count"})
# The paths where two readers' payloads of games that differ only in a named
# Faction may differ: the chooser's own Faction (the view's and the log's).
_OWN_FACTION_PATHS = frozenset(
    {
        ".view.private.scouts_secret_factions[][]",
        ".snapshot.view.private.scouts_secret_factions[][]",
        ".log.entries[].arguments.faction",
        ".snapshot.log.entries[].arguments.faction",
    }
)
_HIDDEN = "(비공개)"


def _pick_arguments(line: int, faction: str) -> dict[str, Any]:
    return {"faction": faction, "pick": line} if faction else {"pick": line}


@dataclass(frozen=True)
class _CovertGame:
    """A game on the engine up to the reveal of the first seat's pick."""

    seed: int
    # Every seat's whole actions: the game up to the first pick, the four
    # picks, and the rest up to the round the first seat's line is due, whose
    # Scouts step has revealed it and asks the first seat to pay it (after
    # the second seat's click on line 0, which comes first, OQ-164).
    plan: Plan
    start: int
    event_round: int

    @property
    def before(self) -> Plan:
        return self.plan[: self.start]

    @property
    def picks(self) -> Plan:
        return self.plan[self.start : self.start + 4]

    @property
    def after(self) -> Plan:
        return self.plan[self.start + 4 :]


@cache
def _find_covert_game() -> _CovertGame:
    """A game of seeded random seats (the Reveal preferred) in which Covert
    Operation is drawn, each seat then picks its ``_COVERT_LINES`` entry, and
    the next round's Scouts step reveals the first seat's line with its seat
    offered to pay it; found on the engine the way the server's table plays
    it back."""

    for seed in dict.fromkeys(_COVERT_SEEDS):
        for stream in _STREAMS:
            game = _play_to_the_covert_reveal(seed, stream)
            if game is not None:
                return game
    raise AssertionError("no seed draws Covert Operation and reaches its reveal")


def _play_to_the_covert_reveal(seed: int, stream: int) -> _CovertGame | None:
    engine = UprisingRulesEngine()
    state = engine.reset(CONFIG, seed)
    chance = ChanceResolver(seed=seed)
    rng = random.Random(stream)
    plan: Plan = []
    start = event_round = first = -1
    picked = 0
    for _ in range(_COVERT_MAX_STEPS):
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = apply_whole(engine, state, chance.resolve(decision)).state
            continue
        if not isinstance(decision, PlayerDecision):
            return None
        seat = decision.owner
        actions = engine.whole_actions(state, seat)
        if not actions:
            return None
        frame = state.decision_stack[-1]
        if picked == 4 and state.scouts_secrets_round > event_round:
            offered = any(row.action_id == "scouts_choose_option" for row in actions)
            if seat == first and offered:
                return _CovertGame(seed, plan, start, event_round)
            if [row.action_id for row in actions] != ["scouts_collect_reward"]:
                return None
            # Line 0 (the second seat's Solari) resolves before line 1 and
            # waits for its seat's own click (OQ-164).
            action = actions[0]
        elif (
            frame.kind == FrameKind.SCOUTS_SECRET
            and dict(frame.context).get("event_id") == COVERT
        ):
            if picked == 0:
                start, event_round, first = len(plan), state.round_number, seat
            line, faction = _COVERT_LINES[picked]
            wanted = _pick_arguments(line, faction)
            action = next(row for row in actions if dict(row.arguments) == wanted)
            picked += 1
        else:
            reveals = [row for row in actions if row.action_id == "reveal_turn"]
            action = (
                reveals[0]
                if reveals and rng.random() < _PREFER_REVEAL
                else rng.choice(actions)
            )
        plan.append((seat, action.action_id, dict(action.arguments)))
        state = apply_whole(engine, state, action).state
    return None


def _play_steps(table: _Table, steps: Plan) -> None:
    for seat, action_id, arguments in steps:
        table.take(seat, action_id, arguments)


def _live_picks(game: _CovertGame, count: int = 4) -> dict[int, tuple[int, str]]:
    """The picks of the first ``count`` seats as (line, Faction or "")."""

    return {
        seat: (arguments["pick"], arguments.get("faction", ""))
        for seat, _, arguments in game.picks[:count]
    }


def _values_of(payload: Any, key: str) -> list[Any]:
    """Every value ``key`` has anywhere in ``payload``."""

    found: list[Any] = []
    if isinstance(payload, dict):
        for name, value in payload.items():
            if name == key:
                found.append(value)
            found += _values_of(value, key)
    elif isinstance(payload, list):
        for item in payload:
            found += _values_of(item, key)
    return found


def _expect_secrets(
    table: _Table, game: _CovertGame, live: dict[int, tuple[int, str]]
) -> None:
    """``live`` (seat -> (line, Faction or "")) are the picks standing: each
    seat's payloads hold its own line and Faction and no other seat's; everyone
    sees only that those seats have picked."""

    event_round = game.event_round
    # Public, in the order the seats picked (``live`` keeps it).
    pending = [[event_round, COVERT, seat] for seat in live]
    for reader in (None, 0, 1, 2, 3):
        payloads = table.payloads(reader)
        own = live.get(reader) if reader is not None else None
        picks = [[event_round, COVERT, own[0]]] if own else []
        factions = [[event_round, COVERT, own[1]]] if own and own[1] else []
        for name, payload in payloads.items():
            for key, expected in (
                ("scouts_secret_picks", picks),
                ("scouts_secret_factions", factions),
            ):
                for value in _values_of(payload, key):
                    assert value == expected, (reader, name, key)
            if name in ("view", "snapshot") and reader is not None:
                assert _values_of(payload, "scouts_secret_pending") == [pending], (
                    reader,
                    name,
                )
        if reader is not None:
            private = payloads["view"]["private"]
            assert private["scouts_secret_picks"] == picks, reader
            assert private["scouts_secret_factions"] == factions, reader
        else:
            for payload in payloads.values():
                assert _values_of(payload, "scouts_secret_pending") == [], reader


def _expect_logged_picks(
    table: _Table, rows: list[tuple[int, dict[str, Any], bool]]
) -> None:
    """Each seat's log holds the secret-pick steps of ``rows`` as (seat,
    arguments, undone), in order: the chooser's own with its line and Faction,
    every other seat's with the line's key alone, hidden."""

    for reader in range(4):
        log = table.seats[reader].get(f"/games/{table.game_id}/log?seat={reader}")
        assert log.status_code == 200, log.text
        logged = [
            (entry["actor"], entry["arguments"], entry["undone"])
            for entry in log.json()["entries"]
            if entry.get("action_id") == "scouts_secret_pick"
        ]
        assert logged == [
            (seat, arguments if seat == reader else {"pick": _HIDDEN}, undone)
            for seat, arguments, undone in rows
        ], reader


def _without_noise(value: Any, game_id: str) -> Any:
    """``value`` without what two runs of one game differ in anyway: the
    clock, the counters of steps, and the game's id."""

    text = json.dumps(value, ensure_ascii=False).replace(game_id, "GAME")

    def strip(item: Any) -> Any:
        if isinstance(item, dict):
            return {k: strip(v) for k, v in item.items() if k not in _NOISE}
        if isinstance(item, list):
            return [strip(v) for v in item]
        return item

    return strip(json.loads(text))


def _differing_paths(first: Any, second: Any, path: str = "") -> set[str]:
    """The paths where two payloads differ, list positions left out."""

    paths: set[str] = set()
    if (
        isinstance(first, dict)
        and isinstance(second, dict)
        and first.keys() == second.keys()
    ):
        for key in first:
            paths |= _differing_paths(first[key], second[key], f"{path}.{key}")
    elif (
        isinstance(first, list)
        and isinstance(second, list)
        and len(first) == len(second)
    ):
        for one, other in zip(first, second, strict=True):
            paths |= _differing_paths(one, other, f"{path}[]")
    elif first != second:
        paths.add(path)
    return paths


def _readers_differ(first: _Table, second: _Table) -> dict[Any, set[str]]:
    """Where each reader's payloads of two tables differ (``_without_noise``)."""

    return {
        reader: _differing_paths(
            _without_noise(first.payloads(reader), first.game_id),
            _without_noise(second.payloads(reader), second.game_id),
        )
        for reader in (None, 0, 1, 2, 3)
    }


def _first_covert_pick_with(table: _Table, game: _CovertGame, faction: str) -> int:
    """The first seat makes its pick naming ``faction``; returns that seat."""

    seat, action_id, arguments = game.picks[0]
    table.take(seat, action_id, {**arguments, "faction": faction})
    return seat


def _take_back(table: _Table, seat: int) -> None:
    summary = table.summary()
    undone = table.seats[seat].post(
        f"/games/{table.game_id}/undo",
        json={
            "seat": seat,
            "revision": summary["revision"],
            "steps": 1,
            "undo_count": summary["undo_count"],
        },
    )
    assert undone.status_code == 200, undone.text


def test_only_the_chooser_sees_its_covert_operation_line_and_faction(
    tmp_path: Path,
) -> None:
    game = _find_covert_game()
    table = _Table(tmp_path / "table", game.seed)
    _play_steps(table, game.before)
    assert table.summary()["decision"]["owner"] == game.picks[0][0]

    for index, (seat, action_id, arguments) in enumerate(game.picks):
        table.take(seat, action_id, arguments)
        _expect_secrets(table, game, _live_picks(game, index + 1))
        _expect_logged_picks(
            table, [(s, a, False) for s, _, a in game.picks[: index + 1]]
        )

    # The engine keeps each Faction with its pick, known to its seat alone.
    state = table.state()
    named = {
        seat: arguments["faction"]
        for seat, _, arguments in game.picks
        if "faction" in arguments
    }
    assert sorted(state.scouts_secret_factions) == sorted(
        (game.event_round, seat, faction) for seat, faction in named.items()
    )
    assert len(named) == 2
    for seat in range(4):
        assert _knowers(state, secret_pick_id(game.event_round, seat)) == frozenset(
            {seat}
        )

    # Nothing else a reader fetches depends on a Faction: the same game with
    # both Factions another differs only in what those two seats see of their
    # own pick.
    twin = _Table(tmp_path / "twin", game.seed)
    _play_steps(twin, game.before)
    for seat, action_id, arguments in game.picks:
        twin.take(
            seat,
            action_id,
            {**arguments, "faction": _SWAPPED[arguments["faction"]]}
            if "faction" in arguments
            else arguments,
        )
    for reader, paths in _readers_differ(table, twin).items():
        if reader in named:
            assert paths and paths <= _OWN_FACTION_PATHS, (reader, paths)
        else:
            assert paths == set(), (reader, paths)


def test_a_taken_back_covert_operation_pick_leaves_no_faction_behind(
    tmp_path: Path,
) -> None:
    """The pick is no reveal (it adds a secret only its seat knows, and takes
    none away), so the seat may take it back for as long as no other seat has
    acted: a window of its one step, closed by the next seat's pick."""

    game = _find_covert_game()
    table = _Table(tmp_path / "table", game.seed)
    _play_steps(table, game.before)
    chooser, action_id, arguments = game.picks[0]
    final = arguments["faction"]
    first_try = {**arguments, "faction": _FIRST_TRY}

    table.take(chooser, action_id, first_try)
    assert {"seat": chooser, "steps": 1} in table.summary()["undo"]
    _expect_secrets(table, game, {chooser: (1, _FIRST_TRY)})
    assert table.state().scouts_secret_factions == (
        (game.event_round, chooser, _FIRST_TRY),
    )

    _take_back(table, chooser)
    # Nothing of it is left: the seat is asked again, the engine holds no pick
    # and no Faction, and no reader's payload names either.
    decision = table.summary()["decision"]
    assert (decision["kind"], decision["owner"]) == ("scouts_secret", chooser)
    state = table.state()
    assert state.scouts_secret_picks == () and state.scouts_secret_factions == ()
    _expect_secrets(table, game, {})
    # The log keeps the taken-back step flagged undone (OQ-010): the chooser's
    # own shows its line and Faction, every other seat's only the hidden line.
    _expect_logged_picks(table, [(chooser, first_try, True)])

    # The seat picks again with the Faction it means: only that one is left.
    table.take(chooser, action_id, arguments)
    _expect_secrets(table, game, {chooser: (1, final)})
    assert table.state().scouts_secret_factions == ((game.event_round, chooser, final),)
    _expect_logged_picks(
        table, [(chooser, first_try, True), (chooser, arguments, False)]
    )

    # Whatever the readers fetch is what a game that never named the first
    # Faction shows: the views, the rows offered and the table's summary.
    direct = _Table(tmp_path / "direct", game.seed)
    _play_steps(direct, game.before)
    direct.take(chooser, action_id, arguments)
    for reader in (None, 0, 1, 2, 3):
        taken_back = table.payloads(reader)
        never = direct.payloads(reader)
        for name in ("summary", "view", "actions"):
            if name in taken_back:
                left = _without_noise(taken_back[name], table.game_id)
                right = _without_noise(never[name], direct.game_id)
                assert left == right, (reader, name)

    # The next seat's pick closes the chooser's window: its pick stands.
    seat, next_action, next_arguments = game.picks[1]
    table.take(seat, next_action, next_arguments)
    summary = table.summary()
    assert all(window["seat"] != chooser for window in summary["undo"])
    refused = table.seats[chooser].post(
        f"/games/{table.game_id}/undo",
        json={
            "seat": chooser,
            "revision": summary["revision"],
            "steps": 1,
            "undo_count": summary["undo_count"],
        },
    )
    assert refused.status_code == 400, refused.text
    assert "at most 0 step" in refused.text
    _expect_secrets(table, game, _live_picks(game, 2))


@pytest.mark.parametrize("taken_back", [False, True], ids=["plain", "taken-back"])
def test_a_save_before_the_reveal_restores_every_payload_with_the_factions_hidden(
    tmp_path: Path, taken_back: bool
) -> None:
    """The save keeps the log too, undone steps included (a load replays those
    branches again): a Faction named and taken back stays as hidden from the
    other seats after the load as before it."""

    game = _find_covert_game()
    table = _Table(tmp_path / "table", game.seed)
    _play_steps(table, game.before)
    chooser, _, arguments = game.picks[0]
    rows: list[tuple[int, dict[str, Any], bool]] = []
    if taken_back:
        _first_covert_pick_with(table, game, _FIRST_TRY)
        _take_back(table, chooser)
        rows.append((chooser, {**arguments, "faction": _FIRST_TRY}, True))
    _play_steps(table, game.picks)
    rows += [(seat, picked, False) for seat, _, picked in game.picks]
    live = _live_picks(game)

    # Saved right after the picks and again a few steps into the round, still
    # before the next Scouts step reveals any of them.
    played = 0
    for upto in (0, 6):
        _play_steps(table, game.after[played:upto])
        played = upto
        _expect_secrets(table, game, live)
        restored = table.restored(table.save())

        assert restored.game_id != table.game_id
        _expect_secrets(restored, game, live)
        _expect_logged_picks(restored, rows)
        # The engine's state has the Factions with their picks, as it had.
        assert restored.state().scouts_secret_factions == (
            table.state().scouts_secret_factions
        )
        assert canonical_state_hash(restored.state()) == canonical_state_hash(
            table.state()
        )
        for reader in (None, 0, 1, 2, 3):
            before = table.payloads(reader)
            after = restored.payloads(reader)
            for name in before:
                left = _without_noise(before[name], table.game_id)
                right = _without_noise(after[name], restored.game_id)
                assert _differing_paths(left, right) == set(), (upto, reader, name)


def _revealed_picks(table: _Table, reader: int) -> list[dict[str, Any]]:
    """The payloads of the ``scouts_secret_revealed`` events in ``reader``'s
    log, in order."""

    log = table.seats[reader].get(f"/games/{table.game_id}/log?seat={reader}")
    assert log.status_code == 200, log.text
    return [
        event["payload"]
        for entry in log.json()["entries"]
        for event in entry.get("events", [])
        if event["kind"] == "scouts_secret_revealed"
    ]


def test_the_reveal_discloses_the_faction_last_chosen_and_a_replay_reaches_it(
    tmp_path: Path,
) -> None:
    game = _find_covert_game()
    table = _Table(tmp_path / "table", game.seed)
    _play_steps(table, game.before)
    # The first seat names one Faction, takes the pick back and names another.
    chooser, _, arguments = game.picks[0]
    final = arguments["faction"]
    assert final != _FIRST_TRY
    _first_covert_pick_with(table, game, _FIRST_TRY)
    _take_back(table, chooser)
    _play_steps(table, game.picks)
    # The save is made before the reveal and replayed beside the game itself.
    restored = table.restored(table.save())
    assert canonical_state_hash(restored.state()) == canonical_state_hash(table.state())
    for played in (table, restored):
        _expect_secrets(played, game, _live_picks(game))
        _play_steps(played, game.after)

    line_zero_seat, two_round_seat = game.picks[1][0], game.picks[2][0]
    waiting = {
        seat: pick
        for seat, pick in _live_picks(game).items()
        if seat in (two_round_seat, game.picks[3][0])
    }
    for played in (table, restored):
        # The Scouts step of the next round reveals the one-round lines, in
        # line order. The line-1 pick discloses the Faction that was chosen
        # last; the Faction taken back is in no reveal.
        expected = [
            {
                "event_round": game.event_round,
                "item_id": COVERT,
                "pick": 0,
                "player": line_zero_seat,
            },
            {
                "event_round": game.event_round,
                "faction": final,
                "item_id": COVERT,
                "pick": 1,
                "player": chooser,
            },
        ]
        for reader in range(4):
            assert _revealed_picks(played, reader) == expected, reader
        # The two-round lines wait: the third seat's Faction is still its
        # seat's alone, and the first seat's, revealed, is in no view any more.
        _expect_secrets(played, game, waiting)
        assert played.state().scouts_secret_factions == (
            (game.event_round, two_round_seat, waiting[two_round_seat][1]),
        )

    # The first seat's line resolves with the Faction it last chose.
    for played in (table, restored):
        influence = played.state().players[chooser].influence
        before = {name: getattr(influence, name) for name in _FACTIONS}
        played.take(chooser, "scouts_choose_option", {"option": 1})
        discard = next(
            row for row in played.rows(chooser) if row["action_id"] == "scouts_discard"
        )
        played.take(chooser, "scouts_discard", discard["arguments"])
        after = played.state().players[chooser].influence
        for name, amount in before.items():
            assert getattr(after, name) == amount + (name == final), name

    # The restored game reached the same state as the one it was saved from.
    assert canonical_state_hash(restored.state()) == canonical_state_hash(table.state())
