"""The seat panel's Victory Point ledger (``GameSessionManager.vp_ledger``).

User request 2026-10-11: clicking a seat's Victory Points shows by what
means they were scored. Most of the engine's Victory Point changes emit no
Victory Point event (an Influence track reaching 2, an Alliance passing on),
so the server compares every seat's points before and after each live step.
The oracles here are independent of that walk: the finished game's points,
a review's state at a cursor (``review_state``, which replays on its own),
and the events of the log entry a row names.

The AI seats play the rubric-priced table pinned in the registry, not
``heuristic``, which is retuned as the baseline improves; every event the
tests rely on is looked up in the log, not hard-coded.
"""

import random
from pathlib import Path

import pytest

from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.server.access import AccessMode, Credentials
from dune_imperium.server.session_log import SEALED_ACTION_IDS, LoggedStep
from dune_imperium.server.sessions import (
    GameSession,
    GameSessionManager,
    JsonObject,
    SeatAccessError,
    UnknownGameError,
)

TABLE = ("heuristic_uprising_table",) * 4
ENTRY_KEYS = {"index", "round", "seat", "delta", "total"}
PAYLOAD_KEYS = {"game_id", "log_count", "step_count", "start", "entries"}


def _obj(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _int(value: object) -> int:
    assert isinstance(value, int)
    return value


def _rows(payload: JsonObject) -> list[dict[str, int]]:
    entries = payload["entries"]
    assert isinstance(entries, list)
    rows = []
    for entry in entries:
        row = _obj(entry)
        assert set(row) == ENTRY_KEYS
        rows.append({key: _int(value) for key, value in row.items()})
    return rows


def _start(payload: JsonObject) -> list[int]:
    start = payload["start"]
    assert isinstance(start, list)
    return [_int(points) for points in start]


def _points(payload: JsonObject, *, before: int | None = None) -> list[int]:
    """Each seat's opening points plus its deltas (rows below ``before``)."""

    points = _start(payload)
    for row in _rows(payload):
        if before is None or row["index"] < before:
            points[row["seat"]] += row["delta"]
    return points


def _by_index(payload: JsonObject) -> dict[int, dict[int, int]]:
    deltas: dict[int, dict[int, int]] = {}
    for row in _rows(payload):
        deltas.setdefault(row["index"], {})[row["seat"]] = row["delta"]
    return deltas


def _live(session: GameSession) -> list[tuple[int, LoggedStep]]:
    return [
        (index, entry)
        for index, entry in enumerate(session.log)
        if isinstance(entry, LoggedStep) and not entry.undone
    ]


def _entry(session: GameSession, index: int) -> LoggedStep:
    entry = session.log[index]
    assert isinstance(entry, LoggedStep)
    return entry


def _seat_points(session: GameSession) -> list[int]:
    return [player.victory_points for player in session.state.players]


def _finished(
    seed: int = 3, *, arrakeen_scouts: bool = False
) -> tuple[GameSessionManager, str]:
    # The default seed's AI table passes an Alliance on, scores Conflict
    # rewards and Battle icons, and matches a wild Battle icon at the
    # Endgame. v146: optional Agent-turn effects offer no refusal (OQ-095
    # (2), 2026-10-14), which moved seed 1 off the Endgame wild match;
    # re-searched then, seed 3 is the first of 0-39 with all of them (4, 8,
    # 14, 19, 24, 29, 31, 32 and 34 too).
    manager = GameSessionManager()
    summary = manager.create_game(
        TABLE, game_seed=seed, arrakeen_scouts=arrakeen_scouts
    )
    assert summary["finished"] is True
    return manager, str(summary["game_id"])


def _events(session: GameSession, kind: str) -> list[tuple[int, dict[str, object]]]:
    """Every event of ``kind`` in the live game: (log index, payload)."""

    return [
        (index, dict(event.payload))
        for index, entry in _live(session)
        for event in entry.events
        if event.kind == kind
    ]


def test_a_finished_games_rows_add_up_to_every_seats_points() -> None:
    manager, game_id = _finished()
    session = manager._get(game_id)
    payload = manager.vp_ledger(game_id)
    assert set(payload) == PAYLOAD_KEYS
    assert payload["game_id"] == game_id
    assert payload["log_count"] == len(session.log)
    assert payload["step_count"] == len(session.steps)
    assert _points(payload) == _seat_points(session)
    opening = session.engine.reset(session.config, session.game_seed)
    assert _start(payload) == [player.victory_points for player in opening.players]

    rows = _rows(payload)
    assert rows
    live = {index for index, _ in _live(session)}
    running = _start(payload)
    seen: set[tuple[int, int]] = set()
    last_index = -1
    last_round = 1
    for row in rows:
        # A live step, in the log's order, one row per seat and step.
        assert row["index"] in live
        assert row["index"] >= last_index
        assert (row["index"], row["seat"]) not in seen
        seen.add((row["index"], row["seat"]))
        assert row["delta"] != 0
        running[row["seat"]] += row["delta"]
        assert row["total"] == running[row["seat"]]
        assert last_round <= row["round"] <= session.state.round_number
        last_index, last_round = row["index"], row["round"]


def test_an_alliance_passing_on_moves_one_point_between_the_two_seats() -> None:
    """An ``alliance_transferred`` step carries no Victory Point event, yet
    the holder loses the Alliance's point and the challenger gains it."""

    manager, game_id = _finished()
    session = manager._get(game_id)
    deltas = _by_index(manager.vp_ledger(game_id))
    transfers = [
        (index, payload)
        for index, payload in _events(session, "alliance_transferred")
        if _int(payload["from_player"]) >= 0 and _int(payload["to_player"]) >= 0
    ]
    assert transfers, "seed 3 passes an Alliance on"
    index, payload = transfers[0]
    assert not any(
        event.kind == "victory_points_gained"
        for event in _entry(session, index).events
    )
    assert deltas[index] == {
        _int(payload["from_player"]): -1,
        _int(payload["to_player"]): 1,
    }


def test_rewards_battle_icons_and_endgame_matches_score_in_their_step() -> None:
    manager, game_id = _finished()
    session = manager._get(game_id)
    deltas = _by_index(manager.vp_ledger(game_id))

    rewards = [
        (index, payload)
        for index, payload in _events(session, "combat_reward_gained")
        # A reward's zero amounts are left out of its payload (cleanup-2c-3).
        if _int(payload.get("victory_points", 0)) > 0
    ]
    assert rewards
    for index, payload in rewards:
        seat = _int(payload["player"])
        assert deltas[index][seat] >= _int(payload["victory_points"])

    matches = _events(session, "battle_icons_matched")
    assert matches
    for index, payload in matches:
        assert deltas[index][_int(payload["player"])] >= 1

    endgame = _events(session, "endgame_wild_matched")
    assert endgame, "seed 3 matches a wild Battle icon at the Endgame"
    for index, payload in endgame:
        assert deltas[index][_int(payload["player"])] >= 1


def test_chance_steps_count_for_the_points_they_move() -> None:
    """A chance outcome can move Victory Points (the pause before a Conflict
    reward carries the reward); its row names that chance entry."""

    manager, game_id = _finished()
    session = manager._get(game_id)
    payload = manager.vp_ledger(game_id)
    positions = {index: position for position, (index, _) in enumerate(_live(session))}
    chance_rows = [
        row
        for row in _rows(payload)
        if isinstance(_entry(session, row["index"]).step, ChanceOutcome)
    ]
    assert chance_rows
    row = chance_rows[0]
    position = positions[row["index"]]
    before = _view_points(manager, game_id, position)
    after = _view_points(manager, game_id, position + 1)
    assert after[row["seat"]] - before[row["seat"]] == row["delta"]
    assert after[row["seat"]] == row["total"]


def _view_points(manager: GameSessionManager, game_id: str, step: int) -> list[int]:
    view = _obj(manager.review_state(game_id, 0, step)["view"])
    players = view["players"]
    assert isinstance(players, list)
    return [_int(_obj(player)["victory_points"]) for player in players]


def test_a_review_cuts_the_rows_at_its_cursor() -> None:
    """The client keeps the rows below its log's end; in a review that is the
    cursor's last live entry, so the rows add up to the reviewed points."""

    manager, game_id = _finished()
    session = manager._get(game_id)
    payload = manager.vp_ledger(game_id)
    live = [index for index, _ in _live(session)]
    transfer = live.index(_events(session, "alliance_transferred")[0][0])
    for cursor in (0, 1, len(live) // 2, transfer, transfer + 1):
        end = live[cursor - 1] + 1 if cursor else 0
        assert _points(payload, before=end) == _view_points(manager, game_id, cursor)
    assert _points(payload, before=len(session.log)) == _view_points(
        manager, game_id, len(live)
    )


def _human_game(seed: int = 0) -> tuple[GameSessionManager, str, JsonObject]:
    manager = GameSessionManager()
    summary = manager.create_game(("human",) * 4, game_seed=seed)
    return manager, str(summary["game_id"]), summary


def _step(
    manager: GameSessionManager, game_id: str, summary: JsonObject, rng: random.Random
) -> tuple[JsonObject, int, int]:
    """One human decision: a turn end pressed, or a random legal action.

    Returns the summary after it, the seat that acted and the index chosen
    (-1 for a press).
    """

    confirmation = summary["confirmation"]
    revision = _int(summary["revision"])
    if isinstance(confirmation, int):
        return manager.confirm_turn(game_id, confirmation, revision), confirmation, -1
    owner = _int(_obj(summary["decision"])["owner"])
    actions = manager.legal_actions(game_id, owner)["actions"]
    assert isinstance(actions, list)
    index = rng.randrange(len(actions))
    return manager.apply_action(game_id, owner, revision, index), owner, index


def test_an_undone_step_leaves_the_ledger_and_its_log_entry_stays() -> None:
    manager, game_id, summary = _human_game()
    session = manager._get(game_id)
    rng = random.Random(0)
    for _ in range(2000):
        before = _seat_points(session)
        state_before = session.state
        summary, seat, index = _step(manager, game_id, summary, rng)
        after = _seat_points(session)
        undo = summary["undo"]
        assert isinstance(undo, list)
        if (
            index >= 0
            and after[seat] != before[seat]
            and {"seat": seat, "steps": 1} in undo
        ):
            break
    else:
        pytest.fail("no undoable step of a seat's own moved its Victory Points")
    taken = len(session.log) - 1
    gained = manager.vp_ledger(game_id)
    assert _by_index(gained)[taken][seat] == after[seat] - before[seat]
    assert _points(gained) == after

    summary = manager.undo(game_id, seat, _int(summary["revision"]))
    assert session.state == state_before
    undone = session.log[taken]
    assert isinstance(undone, LoggedStep) and undone.undone
    ledger = manager.vp_ledger(game_id)
    assert taken not in _by_index(ledger)
    assert _points(ledger) == before
    assert ledger["log_count"] == len(session.log)

    # The same choice again is a new live step, logged after the marker.
    again = manager.apply_action(game_id, seat, _int(summary["revision"]), index)
    assert again["undo_count"] == 1
    redone = manager.vp_ledger(game_id)
    assert taken not in _by_index(redone)
    assert _by_index(redone)[len(session.log) - 1][seat] == after[seat] - before[seat]
    assert _points(redone) == after


def test_the_ledger_is_cached_and_extended_only_by_new_steps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, game_id, summary = _human_game()
    session = manager._get(game_id)
    rng = random.Random(3)
    for _ in range(40):
        summary, _, _ = _step(manager, game_id, summary, rng)
    applied: list[object] = []
    original = session.engine.apply

    def counted(state: object, step: object) -> object:
        applied.append(step)
        return original(state, step)  # type: ignore[arg-type]

    monkeypatch.setattr(session.engine, "apply", counted)
    first = manager.vp_ledger(game_id)
    assert len(applied) == len(session.steps)
    applied.clear()
    assert manager.vp_ledger(game_id) == first
    assert applied == []

    # The game's next step: only the steps since are walked.
    steps = len(session.steps)
    while len(session.steps) == steps:
        summary, _, _ = _step(manager, game_id, summary, rng)
    applied.clear()
    manager.vp_ledger(game_id)
    assert applied == list(session.steps[steps:])

    # An undo takes back steps the ledger walked: it is walked again from
    # the opening state, never from a branch that is no longer played.
    for _ in range(200):
        undo = _list(summary["undo"])
        if undo:
            break
        summary, _, _ = _step(manager, game_id, summary, rng)
    else:
        pytest.fail("no seat could take a step back")
    owner = _int(_obj(undo[0])["seat"])
    manager.vp_ledger(game_id)
    summary = manager.undo(game_id, owner, _int(summary["revision"]))
    applied.clear()
    ledger = manager.vp_ledger(game_id)
    assert len(applied) == len(session.steps)
    assert _points(ledger) == _seat_points(session)


def _list(value: object) -> list[object]:
    assert isinstance(value, list)
    return value


def test_sealed_scouts_choices_never_score() -> None:
    """A secret pick or a sealed bid (``SEALED_ACTION_IDS``) has its arguments
    hidden in the log until the game ends. Neither moves Victory Points: a
    bid keeps its frame open, and a pick only records the line, which is
    revealed (and rewarded) by a later step. So no row ever points at one,
    and a row says nothing but its step's index, round, seat and points."""

    manager, game_id = _finished(seed=0, arrakeen_scouts=True)
    session = manager._get(game_id)
    sealed = {
        index: entry.step.action_id
        for index, entry in _live(session)
        if not isinstance(entry.step, ChanceOutcome)
        and entry.step.action_id in SEALED_ACTION_IDS
    }
    assert set(sealed.values()) == SEALED_ACTION_IDS, "seed 0 picks and bids"
    payload = manager.vp_ledger(game_id)
    assert set(payload) == PAYLOAD_KEYS
    assert not set(sealed) & set(_by_index(payload))
    assert _points(payload) == _seat_points(session)


def test_an_unknown_game_has_no_ledger() -> None:
    with pytest.raises(UnknownGameError):
        GameSessionManager().vp_ledger("nope")


# --- HTTP --------------------------------------------------------------


ADMIN_KEY = "top-secret-admin-key"


def _app(tmp_path: Path, manager: GameSessionManager | None = None) -> object:
    from dune_imperium.server.app import create_app

    return create_app(
        manager,
        saves_dir=tmp_path / "saves",
        card_images_dir=tmp_path / "no-images",
        icons_dir=tmp_path / "no-icons",
        tokens_dir=tmp_path / "no-tokens",
        board_image=tmp_path / "no-map.jpg",
        bene_tleilax_image=tmp_path / "no-bene-tleilax.jpg",
    )


def test_a_remote_ledger_is_for_the_seated_until_the_game_ends(
    tmp_path: Path,
) -> None:
    """On a remote server a client with only the room link gets no more than
    before while the game runs (the summary carries no Victory Points until
    the end; spectators are a non-goal, docs/multiplayer-design.md): any of
    the game's seat cookies reads the ledger, the host's admin cookie alone
    does not, and once a game has finished the room link is enough, as for
    the review (OQ-010 ruling 4)."""

    testclient = pytest.importorskip("fastapi.testclient")
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key=ADMIN_KEY)
    app = _app(tmp_path, manager)
    admin = testclient.TestClient(app)
    assert admin.post("/auth/admin", json={"key": ADMIN_KEY}).status_code == 200
    created = admin.post(
        "/games",
        json={"seats": ["human", *TABLE[1:]], "game_seed": 21},
    )
    assert created.status_code == 200, created.text
    game_id = created.json()["game_id"]
    seated = testclient.TestClient(app)
    claim = seated.post(f"/games/{game_id}/seats/0/claim", json={"name": "Ann"})
    assert claim.status_code == 200, claim.text

    mine = seated.get(f"/games/{game_id}/vp-ledger")
    assert mine.status_code == 200, mine.text
    assert set(mine.json()) == PAYLOAD_KEYS
    stranger = testclient.TestClient(app).get(f"/games/{game_id}/vp-ledger")
    assert stranger.status_code == 403, stranger.text
    host = admin.get(f"/games/{game_id}/vp-ledger")
    assert host.status_code == 403, host.text
    missing = testclient.TestClient(app).get("/games/nope/vp-ledger")
    assert missing.status_code == 404

    finished = admin.post("/games", json={"seats": list(TABLE), "game_seed": 1})
    assert finished.status_code == 200, finished.text
    assert finished.json()["finished"] is True
    done = finished.json()["game_id"]
    after = testclient.TestClient(app).get(f"/games/{done}/vp-ledger")
    assert after.status_code == 200, after.text
    assert after.json() == manager.vp_ledger(done)


def test_a_remote_games_ledger_opens_to_the_room_link_when_it_ends() -> None:
    """The same game: refused to a seatless client while it runs, served to
    it once the seat has played it to the end."""

    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key=ADMIN_KEY)
    admin = Credentials(admin_key=ADMIN_KEY)
    summary = manager.create_game(
        ("human", *TABLE[1:]), game_seed=21, credentials=admin
    )
    game_id = str(summary["game_id"])
    claim = manager.claim_seat(game_id, 0, "Ann")
    seat = Credentials(seat_tokens=frozenset({claim.token}))
    summary = claim.summary
    manager.vp_ledger(game_id, credentials=seat)
    with pytest.raises(SeatAccessError):
        manager.vp_ledger(game_id)
    for _ in range(3000):
        if summary["finished"]:
            break
        revision = _int(summary["revision"])
        if summary["confirmation"] == 0:
            summary = manager.confirm_turn(game_id, 0, revision, credentials=seat)
            continue
        summary = manager.apply_action(game_id, 0, revision, 0, credentials=seat)
    assert summary["finished"] is True
    session = manager._get(game_id)
    assert _points(manager.vp_ledger(game_id)) == _seat_points(session)


def test_an_open_server_serves_a_finished_games_ledger(tmp_path: Path) -> None:
    testclient = pytest.importorskip("fastapi.testclient")
    client = testclient.TestClient(_app(tmp_path))
    created = client.post("/games", json={"seats": list(TABLE), "game_seed": 1})
    assert created.status_code == 200, created.text
    summary = created.json()
    assert summary["finished"] is True
    response = client.get(f"/games/{summary['game_id']}/vp-ledger")
    assert response.status_code == 200, response.text
    payload = response.json()
    standings = {row["player"]: row["victory_points"] for row in summary["standings"]}
    assert _points(payload) == [standings[seat] for seat in range(4)]
