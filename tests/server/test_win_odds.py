"""A finished game's win odds, round by round (``GameSessionManager.win_odds``).

User request 2026-11-07: each player's chance of winning in the current
position, the four seats' numbers from public information only, read at
each round's opening. Ruling 2026-11-08: no number during play; a finished
game shows its course on the result screen and in its review. So the server
refuses a running game and computes nothing while it runs.

The server walks the live game for each round's opening, as the Victory
Point ledger walks it for points, and reads ``evaluation.win_odds`` there
with its search network. The oracles here are independent of the walk: an
engine replay of the logged steps, and ``round_odds`` called directly on
the state it reaches. The network is a small untrained entity network with a
value branch on the calibrated reward scale; what is tested is the plumbing
and who may read the numbers, not their quality (docs/win-odds.md).
"""

import random
from pathlib import Path

import pytest

from dune_imperium.core.state import GameState
from dune_imperium.evaluation import win_odds as evaluation
from dune_imperium.server import sessions as sessions_module
from dune_imperium.server.access import AccessMode, Credentials
from dune_imperium.server.session_log import LoggedStep
from dune_imperium.server.sessions import (
    GameSession,
    GameSessionManager,
    JsonObject,
    SeatAccessError,
    SessionError,
    UnknownGameError,
)
from dune_imperium.server.win_odds import odds_network

torch = pytest.importorskip("torch")

TABLE = ("heuristic_uprising_table",) * 4
PAYLOAD_KEYS = {"game_id", "log_count", "available", "reason", "step_count", "rounds"}
ROW_KEYS = {"round", "index", "odds"}
ADMIN_KEY = "top-secret-admin-key"


@pytest.fixture(scope="module")
def network_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A small entity network with a value branch on the graded reward."""

    from dune_imperium.adapters.action_codec import ActionCodec
    from dune_imperium.config import RulesetConfig
    from dune_imperium.training.checkpoint import save_checkpoint
    from dune_imperium.training.entity_network import (
        EntityNetwork,
        with_value_branch,
    )

    config = RulesetConfig(
        choam_module=True,
        promo_cards=True,
        bloodlines=True,
        tech_module=True,
        immortality=True,
        go_to_11=True,
        epic_game=True,
        arrakeen_scouts=True,
        leader_draft=True,
    )
    torch.manual_seed(0)
    plain = EntityNetwork(
        config, hidden=(16,), entity_width=8, seat_width=16, action_width=8
    )
    branched = with_value_branch(plain, reward_step=1 / 6)
    path = tmp_path_factory.mktemp("win-odds") / "value.pt"
    save_checkpoint(
        path,
        branched,
        ruleset=config.identifier,
        iteration=1,
        codec=ActionCodec(config),
    )
    return path


def _obj(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _int(value: object) -> int:
    assert isinstance(value, int)
    return value


def _rows(payload: JsonObject) -> list[dict[str, object]]:
    assert set(payload) == PAYLOAD_KEYS
    rounds = payload["rounds"]
    assert isinstance(rounds, list)
    rows = [_obj(row) for row in rounds]
    for row in rows:
        assert set(row) == ROW_KEYS
    return rows


def _live(session: GameSession) -> list[tuple[int, LoggedStep]]:
    return [
        (index, entry)
        for index, entry in enumerate(session.log)
        if isinstance(entry, LoggedStep) and not entry.undone
    ]


def _openings(session: GameSession) -> list[tuple[int, int, GameState]]:
    """(round, log index, state) of each round opening, by an engine replay
    of the logged steps; -1 for the game's opening state itself (a game
    without the draft opens round 1 there)."""

    engine = session.engine
    state = engine.reset(session.config, session.game_seed)
    found = []
    reached = 0
    if evaluation.opens_round(state, reached):
        reached = state.round_number
        found.append((reached, -1, state))
    for index, entry in _live(session):
        state = engine.apply(state, entry.step).state
        if evaluation.opens_round(state, reached):
            reached = state.round_number
            found.append((reached, index, state))
    return found


def _finished(network_file: Path, seed: int = 3) -> tuple[GameSessionManager, str]:
    manager = GameSessionManager(search_checkpoint=network_file)
    summary = manager.create_game(
        TABLE,
        game_seed=seed,
        choam_module=True,
        bloodlines=True,
        tech_module=True,
        immortality=True,
    )
    assert summary["finished"] is True
    return manager, str(summary["game_id"])


def test_every_round_opening_has_its_numbers(network_file: Path) -> None:
    manager, game_id = _finished(network_file)
    session = manager._get(game_id)
    payload = manager.win_odds(game_id)
    assert payload["available"] is True and payload["reason"] is None
    assert payload["log_count"] == len(session.log)
    rows = _rows(payload)
    openings = _openings(session)
    assert [(row["round"], row["index"]) for row in rows] == [
        (number, index) for number, index, _ in openings
    ]
    assert [row["round"] for row in rows] == list(
        range(1, session.state.round_number + 1)
    )
    network, _ = odds_network(network_file, session.config)
    assert network is not None
    for row, (_, _, state) in zip(rows, openings, strict=True):
        odds = row["odds"]
        assert isinstance(odds, list) and len(odds) == 4
        assert sum(odds) == pytest.approx(1.0, abs=1e-3)
        expected = evaluation.round_odds(network, state)
        assert expected is not None
        assert odds == [round(p, 4) for p in expected]


def test_the_numbers_are_computed_once_and_kept(
    network_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []
    original = evaluation.round_odds

    def counted(network: object, state: GameState) -> object:
        calls.append(state.round_number)
        return original(network, state)  # type: ignore[arg-type]

    monkeypatch.setattr(sessions_module, "round_odds", counted)
    manager, game_id = _finished(network_file)
    first = manager.win_odds(game_id)
    rounds = [row["round"] for row in _rows(first)]
    assert calls == rounds
    assert manager.win_odds(game_id) == first
    assert calls == rounds


def _step(
    manager: GameSessionManager, game_id: str, summary: JsonObject, rng: random.Random
) -> JsonObject:
    confirmation = summary["confirmation"]
    revision = _int(summary["revision"])
    if isinstance(confirmation, int):
        return manager.confirm_turn(game_id, confirmation, revision)
    owner = _int(_obj(summary["decision"])["owner"])
    actions = manager.legal_actions(game_id, owner)["actions"]
    assert isinstance(actions, list)
    return manager.apply_action(game_id, owner, revision, rng.randrange(len(actions)))


def test_a_running_game_has_no_odds_and_computes_none(
    network_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ruling 2026-11-08: not during play, to anyone, and nothing is worked
    out while the game runs; the same game answers once it has ended."""

    calls: list[int] = []
    original = evaluation.round_odds

    def counted(network: object, state: GameState) -> object:
        calls.append(state.round_number)
        return original(network, state)  # type: ignore[arg-type]

    monkeypatch.setattr(sessions_module, "round_odds", counted)
    manager = GameSessionManager(search_checkpoint=network_file)
    summary = manager.create_game(("human",) * 4, game_seed=1)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    rng = random.Random(2)
    while session.state.round_number < 2:
        summary = _step(manager, game_id, summary, rng)
        with pytest.raises(SessionError, match="after the game finishes"):
            manager.win_odds(game_id)
    assert calls == []
    for _ in range(20_000):
        if summary["finished"]:
            break
        summary = _step(manager, game_id, summary, rng)
    assert summary["finished"] is True
    rows = _rows(manager.win_odds(game_id))
    assert [(row["round"], row["index"]) for row in rows] == [
        (number, index) for number, index, _ in _openings(session)
    ]


def test_a_restored_game_gets_the_same_numbers(network_file: Path) -> None:
    manager, game_id = _finished(network_file, seed=4)
    payload = manager.win_odds(game_id)
    document = manager.save_document(game_id)
    restored = manager.restore_game(document)
    again = manager.win_odds(str(restored["game_id"]))
    assert [row["odds"] for row in _rows(again)] == [
        row["odds"] for row in _rows(payload)
    ]


def test_a_server_without_a_search_network_shows_none() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(TABLE, game_seed=3)
    payload = manager.win_odds(str(summary["game_id"]))
    assert payload["available"] is False
    assert payload["reason"] == "no_network"
    assert _rows(payload) == []


@pytest.mark.parametrize(
    ("options", "reason"),
    [
        ({"base_game": "imperium"}, "base_game"),
        ({"rise_of_ix": True}, "rise_of_ix"),
        ({"imperium_cards": True}, "imperium_cards"),
    ],
)
def test_a_game_the_network_never_learned_shows_none(
    network_file: Path, options: dict[str, object], reason: str
) -> None:
    manager = GameSessionManager(search_checkpoint=network_file)
    summary = manager.create_game(("app_ai",) * 4, game_seed=3, **options)  # type: ignore[arg-type]
    payload = manager.win_odds(str(summary["game_id"]))
    assert payload["available"] is False
    assert payload["reason"] == reason


def test_a_network_of_another_reward_scale_shows_none(tmp_path: Path) -> None:
    from dune_imperium.adapters.action_codec import ActionCodec
    from dune_imperium.config import RulesetConfig
    from dune_imperium.training.checkpoint import save_checkpoint
    from dune_imperium.training.network import PolicyValueNetwork

    base = RulesetConfig()
    codec = ActionCodec(base)
    path = tmp_path / "policy.pt"
    save_checkpoint(
        path,
        PolicyValueNetwork(codec.size, hidden=(8,)),
        ruleset=base.identifier,
        iteration=1,
        codec=codec,
    )
    manager = GameSessionManager(search_checkpoint=path)
    summary = manager.create_game(TABLE, game_seed=3)
    payload = manager.win_odds(str(summary["game_id"]))
    assert payload["available"] is False
    assert payload["reason"] == "reward_step"


def test_an_unknown_game_has_no_odds() -> None:
    with pytest.raises(UnknownGameError):
        GameSessionManager().win_odds("nope")


# --- who may read them ---------------------------------------------------


def _app(tmp_path: Path, manager: GameSessionManager) -> object:
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


def test_a_remote_game_opens_its_odds_to_the_room_link_when_it_ends(
    tmp_path: Path, network_file: Path
) -> None:
    """While the game runs nobody reads them, a seated player included (400,
    as for the review; a seatless client 403 as for any table fact); once
    it has finished the room link is enough (OQ-010 ruling 4)."""

    testclient = pytest.importorskip("fastapi.testclient")
    manager = GameSessionManager(
        access=AccessMode.REMOTE, admin_key=ADMIN_KEY, search_checkpoint=network_file
    )
    app = _app(tmp_path, manager)
    admin = testclient.TestClient(app)
    assert admin.post("/auth/admin", json={"key": ADMIN_KEY}).status_code == 200
    created = admin.post(
        "/games", json={"seats": ["human", *TABLE[1:]], "game_seed": 21}
    )
    assert created.status_code == 200, created.text
    game_id = created.json()["game_id"]
    seated = testclient.TestClient(app)
    claim = seated.post(f"/games/{game_id}/seats/0/claim", json={"name": "Ann"})
    assert claim.status_code == 200, claim.text

    mine = seated.get(f"/games/{game_id}/win-odds")
    assert mine.status_code == 400, mine.text
    stranger = testclient.TestClient(app).get(f"/games/{game_id}/win-odds")
    assert stranger.status_code == 403, stranger.text
    host = admin.get(f"/games/{game_id}/win-odds")
    assert host.status_code == 403, host.text
    assert testclient.TestClient(app).get("/games/nope/win-odds").status_code == 404

    finished = admin.post("/games", json={"seats": list(TABLE), "game_seed": 1})
    assert finished.status_code == 200, finished.text
    assert finished.json()["finished"] is True
    done = finished.json()["game_id"]
    after = testclient.TestClient(app).get(f"/games/{done}/win-odds")
    assert after.status_code == 200, after.text
    assert after.json()["available"] is True
    assert set(after.json()) == PAYLOAD_KEYS
    assert after.json() == manager.win_odds(done)


def test_a_running_remote_game_is_refused_by_the_manager(
    network_file: Path,
) -> None:
    manager = GameSessionManager(
        access=AccessMode.REMOTE, admin_key=ADMIN_KEY, search_checkpoint=network_file
    )
    summary = manager.create_game(
        ("human", *TABLE[1:]),
        game_seed=21,
        credentials=Credentials(admin_key=ADMIN_KEY),
    )
    game_id = str(summary["game_id"])
    claim = manager.claim_seat(game_id, 0, "Ann")
    seat = Credentials(seat_tokens=frozenset({claim.token}))
    with pytest.raises(SessionError, match="after the game finishes"):
        manager.win_odds(game_id, credentials=seat)
    with pytest.raises(SeatAccessError):
        manager.win_odds(game_id)
    with pytest.raises(SeatAccessError):
        manager.win_odds(game_id, credentials=Credentials(admin_key=ADMIN_KEY))
