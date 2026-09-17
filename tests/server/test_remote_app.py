"""HTTP-level tests for remote multiplayer access (M14 slice 1, needs the
``ui`` extra). ``docs/multiplayer-design.md`` sections 4.2-4.4, 5, 6."""

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from dune_imperium.server.access import AccessMode  # noqa: E402
from dune_imperium.server.app import (  # noqa: E402
    ADMIN_COOKIE,
    create_app,
    seat_cookie_name,
)
from dune_imperium.server.sessions import GameSessionManager  # noqa: E402

ADMIN_KEY = "top-secret-admin-key"


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    # The image locations are pinned to nonexistent paths so the tests
    # behave identically with or without the machine-local caches.
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key=ADMIN_KEY)
    return create_app(
        manager,
        saves_dir=tmp_path / "saves",
        card_images_dir=tmp_path / "no-images",
        icons_dir=tmp_path / "no-icons",
        board_image=tmp_path / "no-map.jpg",
        bene_tleilax_image=tmp_path / "no-bene-tleilax.jpg",
    )


def _open_app(tmp_path: Path) -> FastAPI:
    return create_app(
        saves_dir=tmp_path / "saves",
        card_images_dir=tmp_path / "no-images",
        icons_dir=tmp_path / "no-icons",
        board_image=tmp_path / "no-map.jpg",
        bene_tleilax_image=tmp_path / "no-bene-tleilax.jpg",
    )


def _admin_client(app: FastAPI) -> TestClient:
    """A fresh browser logged in as the host."""

    client = TestClient(app)
    response = client.post("/auth/admin", json={"key": ADMIN_KEY})
    assert response.status_code == 200, response.text
    return client


def _create(client: TestClient, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "seats": ["human", "heuristic", "heuristic", "heuristic"],
        "game_seed": 21,
    }
    payload.update(overrides)
    response = client.post("/games", json=payload)
    assert response.status_code == 200, response.text
    summary: dict[str, object] = response.json()
    return summary


# --- /auth/admin --------------------------------------------------------


def test_admin_login_needs_the_right_key(app: FastAPI) -> None:
    client = TestClient(app)

    wrong = client.post("/auth/admin", json={"key": "not-the-key"})
    assert wrong.status_code == 403
    assert wrong.headers.get("set-cookie") is None

    right = client.post("/auth/admin", json={"key": ADMIN_KEY})
    assert right.status_code == 200
    cookie = right.headers["set-cookie"]
    lowered = cookie.lower()
    assert f"{ADMIN_COOKIE}=" in cookie
    assert "httponly" in lowered
    assert "path=/" in lowered
    assert "samesite=strict" in lowered
    assert "max-age=2592000" in lowered


def test_admin_login_is_refused_on_an_open_server(tmp_path: Path) -> None:
    response = TestClient(_open_app(tmp_path)).post(
        "/auth/admin", json={"key": "whatever"}
    )
    assert response.status_code == 400


# --- host-only endpoints --------------------------------------------------


_HOST_ONLY_REQUESTS: list[tuple[str, str, dict[str, object] | None]] = [
    (
        "POST",
        "/games",
        {"seats": ["human", "human", "heuristic", "heuristic"], "game_seed": 5},
    ),
    ("GET", "/games", None),
    ("DELETE", "/games/{game_id}", None),
    ("POST", "/games/{game_id}/save", {}),
    ("GET", "/saves", None),
    ("POST", "/saves/{save_id}/load", None),
    ("DELETE", "/saves/{save_id}", None),
]


@pytest.mark.parametrize(("method", "path_template", "body"), _HOST_ONLY_REQUESTS)
def test_host_only_endpoints_refuse_a_client_without_the_admin_cookie(
    app: FastAPI,
    method: str,
    path_template: str,
    body: dict[str, object] | None,
) -> None:
    admin = _admin_client(app)
    summary = _create(admin, seats=["human", "human", "heuristic", "heuristic"])
    game_id = summary["game_id"]
    saved = admin.post(f"/games/{game_id}/save", json={})
    assert saved.status_code == 200, saved.text
    save_id = saved.json()["save_id"]

    path = path_template.format(game_id=game_id, save_id=save_id)

    stranger_response = TestClient(app).request(method, path, json=body)
    assert stranger_response.status_code == 403, stranger_response.text

    admin_response = admin.request(method, path, json=body)
    assert admin_response.status_code == 200, admin_response.text


# --- created summary / seed hiding -----------------------------------------


def test_a_created_remote_game_hides_its_seed(app: FastAPI) -> None:
    admin = _admin_client(app)
    summary = _create(admin, seats=["human", "human", "heuristic", "heuristic"])

    assert summary["game_seed"] is None
    assert summary["access"] == "remote"

    anon_view = TestClient(app).get(f"/games/{summary['game_id']}")
    assert anon_view.status_code == 200
    assert anon_view.json()["game_seed"] is None


# --- claim -----------------------------------------------------------------


def test_claiming_a_seat_sets_a_cookie_and_the_me_endpoint_sees_it(
    app: FastAPI,
) -> None:
    admin = _admin_client(app)
    summary = _create(admin, seats=["human", "human", "heuristic", "heuristic"])
    game_id = summary["game_id"]

    player = TestClient(app)
    claimed = player.post(f"/games/{game_id}/seats/0/claim", json={"name": "Alice"})
    assert claimed.status_code == 200, claimed.text
    cookie = claimed.headers["set-cookie"]
    lowered = cookie.lower()
    assert f"{seat_cookie_name(str(game_id), 0)}=" in cookie
    assert "httponly" in lowered
    assert f"path=/games/{game_id}".lower() in lowered
    assert "samesite=strict" in lowered
    assert "max-age=2592000" in lowered

    me = player.get(f"/games/{game_id}/me")
    assert me.status_code == 200
    assert me.json()["seats"] == [0]


def test_a_second_claim_of_the_same_seat_is_refused(app: FastAPI) -> None:
    admin = _admin_client(app)
    summary = _create(admin, seats=["human", "human", "heuristic", "heuristic"])
    game_id = summary["game_id"]
    TestClient(app).post(f"/games/{game_id}/seats/0/claim", json={"name": "Alice"})

    second = TestClient(app).post(
        f"/games/{game_id}/seats/0/claim", json={"name": "Bob"}
    )
    assert second.status_code == 409


def test_claiming_an_ai_seat_is_refused(app: FastAPI) -> None:
    admin = _admin_client(app)
    summary = _create(admin, seats=["human", "human", "heuristic", "heuristic"])
    game_id = summary["game_id"]

    response = TestClient(app).post(
        f"/games/{game_id}/seats/2/claim", json={"name": "x"}
    )
    assert response.status_code == 403


def test_claiming_with_an_empty_name_is_refused(app: FastAPI) -> None:
    admin = _admin_client(app)
    summary = _create(admin, seats=["human", "human", "heuristic", "heuristic"])
    game_id = summary["game_id"]

    response = TestClient(app).post(
        f"/games/{game_id}/seats/0/claim", json={"name": "   "}
    )
    assert response.status_code == 400


def test_claiming_a_seat_of_an_unknown_game_is_404(app: FastAPI) -> None:
    response = TestClient(app).post("/games/absent/seats/0/claim", json={"name": "x"})
    assert response.status_code == 404


def test_claiming_a_seat_on_an_open_server_is_refused(tmp_path: Path) -> None:
    client = TestClient(_open_app(tmp_path))
    summary = _create(client)

    response = client.post(
        f"/games/{summary['game_id']}/seats/0/claim", json={"name": "x"}
    )
    assert response.status_code == 400


# --- cross-seat isolation ----------------------------------------------


def test_cross_seat_isolation_over_http(app: FastAPI) -> None:
    admin = _admin_client(app)
    summary = _create(admin, seats=["human", "human", "heuristic", "heuristic"])
    game_id = summary["game_id"]

    player0 = TestClient(app)
    claim0 = player0.post(f"/games/{game_id}/seats/0/claim", json={"name": "P0"})
    assert claim0.status_code == 200, claim0.text
    player1 = TestClient(app)
    claim1 = player1.post(f"/games/{game_id}/seats/1/claim", json={"name": "P1"})
    assert claim1.status_code == 200, claim1.text

    assert player0.get(f"/games/{game_id}/seats/0/view").status_code == 200
    assert player0.get(f"/games/{game_id}/seats/1/view").status_code == 403
    assert player0.get(f"/games/{game_id}/seats/1/actions").status_code == 403
    assert (
        player0.get(f"/games/{game_id}/log", params={"seat": 1}).status_code == 403
    )
    assert (
        player0.post(
            f"/games/{game_id}/actions",
            json={"seat": 1, "revision": 0, "index": 0},
        ).status_code
        == 403
    )
    assert (
        player0.post(
            f"/games/{game_id}/undo", json={"seat": 1, "revision": 0}
        ).status_code
        == 403
    )
    assert (
        player0.post(
            f"/games/{game_id}/confirm", json={"seat": 1, "revision": 0}
        ).status_code
        == 403
    )

    assert player1.get(f"/games/{game_id}/seats/0/view").status_code == 403

    # Neither a cookie-less client nor the host's admin cookie opens a seat:
    # the host plays too and must not reach another hand through the API.
    for outsider in (TestClient(app), admin):
        assert outsider.get(f"/games/{game_id}/seats/0/view").status_code == 403
        assert outsider.get(f"/games/{game_id}/seats/0/actions").status_code == 403
        assert (
            outsider.get(f"/games/{game_id}/log", params={"seat": 0}).status_code
            == 403
        )
        assert (
            outsider.post(
                f"/games/{game_id}/actions",
                json={"seat": 0, "revision": summary["revision"], "index": 0},
            ).status_code
            == 403
        )


def test_a_seat_token_under_another_seats_cookie_name_opens_nothing(
    app: FastAPI,
) -> None:
    admin = _admin_client(app)
    summary = _create(admin, seats=["human", "human", "heuristic", "heuristic"])
    game_id = str(summary["game_id"])
    TestClient(app).post(f"/games/{game_id}/seats/0/claim", json={"name": "P0"})
    player1 = TestClient(app)
    claimed = player1.post(f"/games/{game_id}/seats/1/claim", json={"name": "P1"})
    assert claimed.status_code == 200, claimed.text
    own_token = player1.cookies.get(
        seat_cookie_name(game_id, 1), path=f"/games/{game_id}"
    )
    assert own_token

    # Tokens are judged by value, never by the cookie name they arrive under.
    forger = TestClient(app)
    forger.cookies.set(
        seat_cookie_name(game_id, 0), own_token, path=f"/games/{game_id}"
    )
    assert forger.get(f"/games/{game_id}/seats/0/view").status_code == 403
    assert forger.get(f"/games/{game_id}/me").json()["seats"] == [1]


# --- full leader-draft flow -------------------------------------------------


def test_a_remote_leader_draft_game_over_http_reaches_round_one(
    app: FastAPI,
) -> None:
    admin = _admin_client(app)
    summary = _create(
        admin,
        seats=["human", "human", "human", "human"],
        leader_draft=True,
        game_seed=22,
    )
    game_id = summary["game_id"]

    clients = [TestClient(app) for _ in range(4)]
    for seat, player in enumerate(clients):
        claimed = player.post(
            f"/games/{game_id}/seats/{seat}/claim", json={"name": f"P{seat}"}
        )
        assert claimed.status_code == 200, claimed.text

    picks = 0
    decision = summary["decision"]
    while isinstance(decision, dict) and decision["kind"] == "leader_draft":
        holder = summary["confirmation"]
        if isinstance(holder, int):
            # A remote server holds the turn until the seat that just picked
            # confirms; the next seat's browser cannot do it for them.
            early = clients[decision["owner"]].post(
                f"/games/{game_id}/actions",
                json={
                    "seat": decision["owner"],
                    "revision": summary["revision"],
                    "index": 0,
                },
            )
            assert early.status_code == 400, early.text
            confirmed = clients[holder].post(
                f"/games/{game_id}/confirm",
                json={"seat": holder, "revision": summary["revision"]},
            )
            assert confirmed.status_code == 200, confirmed.text
            summary = confirmed.json()
            decision = summary["decision"]
            continue
        owner = decision["owner"]
        other = clients[(owner + 1) % 4]
        forbidden = other.post(
            f"/games/{game_id}/actions",
            json={"seat": owner, "revision": summary["revision"], "index": 0},
        )
        assert forbidden.status_code == 403, forbidden.text

        applied = clients[owner].post(
            f"/games/{game_id}/actions",
            json={"seat": owner, "revision": summary["revision"], "index": 0},
        )
        assert applied.status_code == 200, applied.text
        summary = applied.json()
        decision = summary["decision"]
        picks += 1

    assert picks == 4
    assert summary["round_number"] == 1


# --- release -----------------------------------------------------------------


def test_a_holder_can_release_their_seat_and_someone_else_can_claim_it(
    app: FastAPI,
) -> None:
    admin = _admin_client(app)
    summary = _create(admin, seats=["human", "human", "heuristic", "heuristic"])
    game_id = summary["game_id"]

    holder = TestClient(app)
    holder.post(f"/games/{game_id}/seats/0/claim", json={"name": "P0"})

    released = holder.post(f"/games/{game_id}/seats/0/release")
    assert released.status_code == 200, released.text
    cookie = released.headers["set-cookie"].lower()
    assert "max-age=0" in cookie

    assert holder.get(f"/games/{game_id}/seats/0/view").status_code == 403

    newcomer = TestClient(app)
    reclaimed = newcomer.post(
        f"/games/{game_id}/seats/0/claim", json={"name": "P0-again"}
    )
    assert reclaimed.status_code == 200, reclaimed.text


def test_admin_can_release_another_players_seat(app: FastAPI) -> None:
    admin = _admin_client(app)
    summary = _create(admin, seats=["human", "human", "heuristic", "heuristic"])
    game_id = summary["game_id"]

    holder = TestClient(app)
    holder.post(f"/games/{game_id}/seats/0/claim", json={"name": "P0"})

    released = admin.post(f"/games/{game_id}/seats/0/release")
    assert released.status_code == 200, released.text
    assert holder.get(f"/games/{game_id}/seats/0/view").status_code == 403


def test_a_stranger_holding_nothing_cannot_release_someone_elses_seat(
    app: FastAPI,
) -> None:
    admin = _admin_client(app)
    summary = _create(admin, seats=["human", "human", "heuristic", "heuristic"])
    game_id = summary["game_id"]
    TestClient(app).post(f"/games/{game_id}/seats/0/claim", json={"name": "P0"})

    stranger = TestClient(app)
    assert stranger.post(f"/games/{game_id}/seats/0/release").status_code == 403


# --- saves over HTTP as admin ------------------------------------------


def test_saves_hide_the_seed_and_loading_clears_claims(app: FastAPI) -> None:
    admin = _admin_client(app)
    summary = _create(admin, seats=["human", "human", "heuristic", "heuristic"])
    game_id = summary["game_id"]
    holder = TestClient(app)
    holder.post(f"/games/{game_id}/seats/0/claim", json={"name": "P0"})

    saved = admin.post(f"/games/{game_id}/save", json={"name": "sv"})
    assert saved.status_code == 200, saved.text
    metadata = saved.json()
    assert metadata["game_seed"] is None
    save_id = metadata["save_id"]

    listing = admin.get("/saves")
    assert listing.status_code == 200
    matching = [entry for entry in listing.json() if entry["save_id"] == save_id]
    assert matching and all(entry["game_seed"] is None for entry in matching)

    loaded = admin.post(f"/saves/{save_id}/load")
    assert loaded.status_code == 200, loaded.text
    restored = loaded.json()
    assert restored["game_id"] != game_id
    assert all(entry["claimed"] is False for entry in restored["players"])

    stale_seat_view = holder.get(f"/games/{restored['game_id']}/seats/0/view")
    assert stale_seat_view.status_code == 403


# --- finished game -----------------------------------------------------


def test_a_finished_remote_game_shows_its_seed_and_allows_cookieless_review(
    app: FastAPI,
) -> None:
    admin = _admin_client(app)
    summary = _create(
        admin, seats=["random", "random", "random", "random"], game_seed=99
    )
    assert summary["finished"] is True
    assert summary["game_seed"] == 99

    review = TestClient(app).get(
        f"/games/{summary['game_id']}/review", params={"seat": 0}
    )
    assert review.status_code == 200, review.text


# --- OPEN app stays permissive -----------------------------------------


def test_open_server_me_and_summary_stay_permissive(tmp_path: Path) -> None:
    client = TestClient(_open_app(tmp_path))
    summary = _create(
        client, seats=["human", "human", "heuristic", "heuristic"], game_seed=13
    )
    game_id = summary["game_id"]

    me = client.get(f"/games/{game_id}/me")
    assert me.status_code == 200
    assert me.json() == {
        "game_id": game_id,
        "access": "open",
        "seats": [0, 1],
        "admin": True,
    }
    assert summary["access"] == "open"
    assert summary["game_seed"] == 13


# --- /whoami -----------------------------------------------------------------


def test_whoami_tells_a_browser_the_access_mode_and_whether_it_is_the_host(
    tmp_path: Path,
) -> None:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key=ADMIN_KEY)
    app = create_app(
        manager,
        saves_dir=tmp_path / "saves",
        card_images_dir=tmp_path / "no-images",
        icons_dir=tmp_path / "no-icons",
        board_image=tmp_path / "no-map.jpg",
        bene_tleilax_image=tmp_path / "no-bene-tleilax.jpg",
        public_url="http://100.101.102.103:8000",
    )

    stranger = TestClient(app).get("/whoami")
    assert stranger.status_code == 200
    # The room-link base is the host's business only.
    assert stranger.json() == {"access": "remote", "admin": False, "public_url": None}

    host = _admin_client(app).get("/whoami")
    assert host.json() == {
        "access": "remote",
        "admin": True,
        "public_url": "http://100.101.102.103:8000",
    }


def test_whoami_on_an_open_server_makes_everyone_the_host(tmp_path: Path) -> None:
    response = TestClient(_open_app(tmp_path)).get("/whoami")

    assert response.json() == {"access": "open", "admin": True, "public_url": None}
