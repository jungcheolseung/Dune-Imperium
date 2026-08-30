"""HTTP-level tests for the FastAPI play server (needs the ``ui`` extra)."""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from dune_imperium.server.app import create_app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


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


def test_created_games_are_listed_and_summarized(client: TestClient) -> None:
    summary = _create(client)
    game_id = summary["game_id"]

    assert client.get("/games").json() == [summary]
    assert client.get(f"/games/{game_id}").json() == summary
    assert summary["finished"] is False
    decision = summary["decision"]
    assert isinstance(decision, dict)
    assert decision["owner"] == 0


def test_an_all_ai_game_returns_finished_standings(client: TestClient) -> None:
    summary = _create(client, seats=["random", "random", "random", "random"])

    assert summary["finished"] is True
    standings = summary["standings"]
    assert isinstance(standings, list)
    assert sorted(entry["rank"] for entry in standings) == [1, 2, 3, 4]


def test_views_and_actions_respect_the_seat_boundary(client: TestClient) -> None:
    summary = _create(client)
    game_id = summary["game_id"]

    view = client.get(f"/games/{game_id}/seats/0/view")
    assert view.status_code == 200
    assert view.json()["player"] == 0

    actions = client.get(f"/games/{game_id}/seats/0/actions")
    assert actions.status_code == 200
    assert actions.json()["actions"]

    assert client.get(f"/games/{game_id}/seats/1/view").status_code == 403
    assert client.get(f"/games/{game_id}/seats/1/actions").status_code == 403


def test_apply_action_advances_and_guards_revisions(client: TestClient) -> None:
    summary = _create(client)
    game_id = summary["game_id"]
    revision = summary["revision"]

    stale = client.post(
        f"/games/{game_id}/actions",
        json={"seat": 0, "revision": int(str(revision)) + 1, "index": 0},
    )
    assert stale.status_code == 409

    applied = client.post(
        f"/games/{game_id}/actions",
        json={"seat": 0, "revision": revision, "index": 0},
    )
    assert applied.status_code == 200
    assert applied.json()["revision"] != revision


def test_unknown_games_and_bad_requests_map_to_http_errors(
    client: TestClient,
) -> None:
    assert client.get("/games/absent").status_code == 404
    assert client.get("/games/absent/seats/0/view").status_code == 404
    assert client.delete("/games/absent").status_code == 404

    bad_seats = client.post("/games", json={"seats": ["human"]})
    assert bad_seats.status_code == 422
    unknown_kind = client.post(
        "/games", json={"seats": ["human", "alien", "random", "random"]}
    )
    assert unknown_kind.status_code == 400


def test_deleting_a_game_removes_it(client: TestClient) -> None:
    summary = _create(client)
    game_id = summary["game_id"]

    assert client.delete(f"/games/{game_id}").json() == {"deleted": game_id}
    assert client.get(f"/games/{game_id}").status_code == 404


def test_a_leader_draft_game_over_http_reaches_round_one(
    client: TestClient,
) -> None:
    summary = _create(
        client,
        seats=["human", "human", "human", "human"],
        leader_draft=True,
        game_seed=22,
    )
    game_id = summary["game_id"]

    picks = 0
    decision = summary["decision"]
    while isinstance(decision, dict) and decision["kind"] == "leader_draft":
        owner = decision["owner"]
        applied = client.post(
            f"/games/{game_id}/actions",
            json={"seat": owner, "revision": summary["revision"], "index": 0},
        )
        assert applied.status_code == 200, applied.text
        summary = applied.json()
        decision = summary["decision"]
        picks += 1
    assert picks == 4
    assert summary["round_number"] == 1
