"""What a client can make a remote play server do (2026-11 security review).

``docs/reviews/2026-11-cloud-server-security.md`` lists the findings. The
tests here pin the guarantees that review found sound, and the four that
proved findings 2, 4, 5 and 6 (``xfail(strict=True)`` until the fixes of
2026-11-03) now hold them fixed. ``test_server_hardening.py`` tests the
rest of those fixes.
"""

import json
import threading
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.routing import APIRoute  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from dune_imperium.core.state import canonical_state_hash  # noqa: E402
from dune_imperium.server.access import ANONYMOUS, AccessMode, Credentials  # noqa: E402
from dune_imperium.server.app import create_app  # noqa: E402
from dune_imperium.server.persistence import JsonObject  # noqa: E402
from dune_imperium.server.sessions import (  # noqa: E402
    GameSessionManager,
    StaleRevisionError,
    _state_after,
)

ADMIN_KEY = "test-admin-key-not-a-real-one"
HUMAN_FIRST = ("human", "heuristic", "heuristic", "heuristic")
TWO_HUMANS = ["human", "human", "heuristic", "heuristic"]


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key=ADMIN_KEY)
    return create_app(
        manager,
        saves_dir=tmp_path / "saves",
        card_images_dir=tmp_path / "no-images",
        icons_dir=tmp_path / "no-icons",
        tokens_dir=tmp_path / "no-tokens",
        board_image=tmp_path / "no-map.jpg",
        bene_tleilax_image=tmp_path / "no-bene-tleilax.jpg",
    )


def _admin_client(app: FastAPI) -> TestClient:
    client = TestClient(app)
    response = client.post("/auth/admin", json={"key": ADMIN_KEY})
    assert response.status_code == 200, response.text
    return client


def _game_with_a_claimed_seat(app: FastAPI) -> tuple[str, TestClient]:
    """A remote game of two human seats; the returned client holds seat 0."""

    admin = _admin_client(app)
    created = admin.post("/games", json={"seats": TWO_HUMANS, "game_seed": 21})
    assert created.status_code == 200, created.text
    game_id = str(created.json()["game_id"])
    player = TestClient(app)
    claimed = player.post(f"/games/{game_id}/seats/0/claim", json={"name": "P0"})
    assert claimed.status_code == 200, claimed.text
    return game_id, player


def _int(value: object) -> int:
    assert isinstance(value, int)
    return value


# --- guarantees the review found sound ---------------------------------------


def test_no_state_changing_route_answers_a_get(app: FastAPI) -> None:
    """Every POST or DELETE route refuses GET, so a link or an ``<img>`` can
    never claim, release, act, undo, save, load or delete anything."""

    admin = _admin_client(app)
    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    changing = [r for r in routes if (r.methods or set()) & {"POST", "DELETE"}]
    readers = {r.path: r.name for r in routes if "GET" in (r.methods or set())}
    assert len(changing) >= 13
    for route in changing:
        assert "GET" not in (route.methods or set()), route.path
        if route.path in readers:
            # The same path also lists or summarises: a separate read-only
            # endpoint answers its GET.
            assert readers[route.path] in {"list_games", "game_summary"}
            continue
        path = route.path.format(
            game_id="0" * 32, save_id="0" * 32, seat=0, step=0
        )
        assert admin.get(path).status_code == 405, route.path


def test_a_json_route_does_nothing_with_a_text_plain_body(app: FastAPI) -> None:
    """A page on another origin can send a "simple" cross-origin POST without
    a preflight only as ``text/plain`` (or a form). The routes read their
    bodies as JSON only from a JSON content type, so such a request claims
    nothing; a JSON content type needs a preflight, which no CORS header
    here allows."""

    admin = _admin_client(app)
    created = admin.post("/games", json={"seats": TWO_HUMANS, "game_seed": 21})
    game_id = str(created.json()["game_id"])
    stranger = TestClient(app)

    for content_type in ("text/plain", "application/x-www-form-urlencoded"):
        response = stranger.post(
            f"/games/{game_id}/seats/0/claim",
            content=json.dumps({"name": "csrf"}),
            headers={"Content-Type": content_type},
        )
        assert response.status_code == 422, response.text
        assert "set-cookie" not in response.headers

    summary = admin.get(f"/games/{game_id}").json()
    assert all(entry["claimed"] is False for entry in summary["players"])


def _remote_game_of_seat0() -> tuple[GameSessionManager, str, Credentials]:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key=ADMIN_KEY)
    summary = manager.create_game(
        HUMAN_FIRST, game_seed=8, credentials=Credentials(admin_key=ADMIN_KEY)
    )
    game_id = str(summary["game_id"])
    claim = manager.claim_seat(game_id, 0, "P0", credentials=ANONYMOUS)
    return manager, game_id, Credentials(seat_tokens=frozenset({claim.token}))


def _race(*calls: object) -> list[object]:
    """Run each zero-argument call on its own thread, released together."""

    barrier = threading.Barrier(len(calls))
    results: list[object] = [None] * len(calls)

    def run(index: int) -> None:
        call = calls[index]
        assert callable(call)
        barrier.wait()
        try:
            results[index] = call()
        except Exception as error:  # the loser's refusal is the result
            results[index] = error

    threads = [threading.Thread(target=run, args=(i,)) for i in range(len(calls))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


def _assert_state_matches_its_steps(manager: GameSessionManager, game_id: str) -> None:
    session = manager._get(game_id)
    with session.lock:
        replayed = _state_after(session, len(session.steps))
        assert canonical_state_hash(session.state) == canonical_state_hash(replayed)


def test_two_moves_at_the_same_revision_have_exactly_one_winner() -> None:
    """Two tabs of one seat (or a double click) send the same move at once:
    the session lock and the revision check let exactly one through."""

    manager, game_id, own = _remote_game_of_seat0()
    for _ in range(5):
        summary = manager.summary(game_id)
        if summary["confirmation"] == 0:
            manager.confirm_turn(
                game_id, 0, _int(summary["revision"]), credentials=own
            )
            continue
        revision = _int(summary["revision"])

        def move(revision: int = revision) -> JsonObject:
            return manager.apply_action(
                game_id, 0, revision, 0, credentials=own
            )

        results = _race(move, move)
        wins = [result for result in results if isinstance(result, dict)]
        losses = [r for r in results if isinstance(r, StaleRevisionError)]
        assert len(wins) == 1 and len(losses) == 1, results
        assert manager.summary(game_id)["revision"] == wins[0]["revision"]
        _assert_state_matches_its_steps(manager, game_id)


def _seat0_may_undo(windows: object) -> bool:
    assert isinstance(windows, list)
    return any(isinstance(w, dict) and w.get("seat") == 0 for w in windows)


def _undoable_decision_of_seat0(
    manager: GameSessionManager, game_id: str, own: Credentials
) -> JsonObject:
    """Play seat 0's first action until it may both undo and act again."""

    summary = manager.summary(game_id)
    for _ in range(200):
        snapshot = manager.snapshot(game_id, 0, credentials=own)
        if (
            summary["confirmation"] is None
            and snapshot["actions"] is not None
            and _seat0_may_undo(summary["undo"])
        ):
            return summary
        revision = _int(summary["revision"])
        if summary["confirmation"] == 0:
            summary = manager.confirm_turn(game_id, 0, revision, credentials=own)
        else:
            summary = manager.apply_action(game_id, 0, revision, 0, credentials=own)
    raise AssertionError("seat 0 never held an undo beside a decision of its own")


def test_an_undo_racing_a_move_of_the_same_seat_has_exactly_one_winner() -> None:
    """Undo in one tab, a move in another, both from the same revision: one
    is refused as stale and the state is exactly its recorded steps."""

    manager, game_id, own = _remote_game_of_seat0()
    summary = _undoable_decision_of_seat0(manager, game_id, own)
    revision = _int(summary["revision"])
    undo_count = _int(summary["undo_count"])
    results = _race(
        lambda: manager.undo(
            game_id, 0, revision, undo_count=undo_count, credentials=own
        ),
        lambda: manager.apply_action(
            game_id, 0, revision, 0, undo_count=undo_count, credentials=own
        ),
    )
    wins = [result for result in results if isinstance(result, dict)]
    losses = [r for r in results if isinstance(r, StaleRevisionError)]
    assert len(wins) == 1 and len(losses) == 1, results
    after = manager.summary(game_id)
    assert (after["revision"], after["undo_count"]) == (
        wins[0]["revision"],
        wins[0]["undo_count"],
    )
    _assert_state_matches_its_steps(manager, game_id)


# --- findings, fixed 2026-11-03 ---------------------------------------------


def test_an_oversized_body_is_refused_before_it_is_parsed(app: FastAPI) -> None:
    stranger = TestClient(app)
    body = json.dumps({"key": "k" * (2 * 1024 * 1024)})
    response = stranger.post(
        "/auth/admin", content=body, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413


@pytest.mark.parametrize("raw", ['{"key": Infinity}', '{"key": "\\ud800"}'])
def test_an_unrenderable_json_value_is_a_client_error(app: FastAPI, raw: str) -> None:
    stranger = TestClient(app, raise_server_exceptions=False)
    response = stranger.post(
        "/auth/admin", content=raw, headers={"Content-Type": "application/json"}
    )
    assert 400 <= response.status_code < 500


def test_a_seats_private_responses_forbid_storing(app: FastAPI) -> None:
    game_id, player = _game_with_a_claimed_seat(app)
    for path in (
        f"/games/{game_id}/snapshot?seat=0",
        f"/games/{game_id}/seats/0/view",
        f"/games/{game_id}/seats/0/actions",
        f"/games/{game_id}/log?seat=0",
    ):
        response = player.get(path)
        assert response.status_code == 200, path
        assert "no-store" in response.headers.get("cache-control", ""), path


def test_a_remote_server_serves_no_interactive_api_docs(app: FastAPI) -> None:
    stranger = TestClient(app)
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert stranger.get(path).status_code == 404, path
