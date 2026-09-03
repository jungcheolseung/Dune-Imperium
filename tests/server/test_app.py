"""HTTP-level tests for the FastAPI play server (needs the ``ui`` extra)."""

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from dune_imperium.server.app import create_app  # noqa: E402
from dune_imperium.server.sessions import GameSessionManager  # noqa: E402


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    # The image locations are pinned to nonexistent paths so the tests
    # behave identically with or without the machine-local caches.
    return TestClient(
        create_app(
            saves_dir=tmp_path / "saves",
            card_images_dir=tmp_path / "no-images",
            icons_dir=tmp_path / "no-icons",
            board_image=tmp_path / "no-map.jpg",
        )
    )


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


def test_root_serves_the_ui_and_static_assets(client: TestClient) -> None:
    index = client.get("/")
    assert index.status_code == 200
    assert "text/html" in index.headers["content-type"]
    assert "Dune: Imperium" in index.text

    script = client.get("/static/app.js")
    assert script.status_code == 200
    style = client.get("/static/style.css")
    assert style.status_code == 200


def test_catalog_endpoint_serves_display_names(client: TestClient) -> None:
    response = client.get("/catalog")
    assert response.status_code == 200
    catalog = response.json()
    assert catalog["cards"]["sardaukar_soldier"]["name"] == "Sardaukar Soldier"
    assert catalog["leaders"]["lady_jessica"]["name"].startswith("Lady Jessica")


def test_promo_cards_option_reaches_the_ruleset(client: TestClient) -> None:
    summary = _create(client, promo_cards=True, game_seed=5)
    assert summary["promo_cards"] is True
    assert _create(client, game_seed=5)["promo_cards"] is False


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


def test_saves_roundtrip_over_http(client: TestClient) -> None:
    summary = _create(client)
    game_id = summary["game_id"]
    applied = client.post(
        f"/games/{game_id}/actions",
        json={"seat": 0, "revision": summary["revision"], "index": 0},
    )
    assert applied.status_code == 200, applied.text
    summary = applied.json()

    saved = client.post(f"/games/{game_id}/save", json={"name": "테스트"})
    assert saved.status_code == 200, saved.text
    metadata = saved.json()
    save_id = metadata["save_id"]
    assert metadata["name"] == "테스트"
    assert "steps" not in metadata
    assert metadata["step_count"] > 0

    listing = client.get("/saves")
    assert listing.status_code == 200
    assert [entry["save_id"] for entry in listing.json()] == [save_id]

    loaded = client.post(f"/saves/{save_id}/load")
    assert loaded.status_code == 200, loaded.text
    restored = loaded.json()
    assert restored["game_id"] != game_id
    assert restored["revision"] == summary["revision"]
    assert restored["decision"] == summary["decision"]

    assert client.delete(f"/saves/{save_id}").json() == {"deleted": save_id}
    assert client.delete(f"/saves/{save_id}").status_code == 404
    assert client.post(f"/saves/{save_id}/load").status_code == 404
    assert client.post("/games/absent/save", json={}).status_code == 404


def test_review_over_http(tmp_path: Path) -> None:
    manager = GameSessionManager()
    client = TestClient(create_app(manager, saves_dir=tmp_path / "saves"))
    summary = manager.create_game(
        ("human", "heuristic", "heuristic", "heuristic"), game_seed=14
    )
    game_id = str(summary["game_id"])
    for _ in range(2_000):
        if summary["finished"]:
            break
        if summary["confirmation"] == 0:
            summary = manager.confirm_turn(
                game_id, seat=0, revision=int(str(summary["revision"]))
            )
            continue
        summary = manager.apply_action(
            game_id, seat=0, revision=int(str(summary["revision"])), index=0
        )
    assert summary["finished"] is True

    review = client.get(f"/games/{game_id}/review", params={"seat": 0})
    assert review.status_code == 200, review.text
    step_count = review.json()["step_count"]
    assert step_count == len(review.json()["steps"])

    final = client.get(f"/games/{game_id}/review/{step_count}", params={"seat": 0})
    assert final.status_code == 200, final.text
    assert final.json()["phase"] == "finished"
    assert final.json()["view"]["player"] == 0

    # Post-game disclosure (OQ-010): AI seats can be reviewed too.
    assert (
        client.get(f"/games/{game_id}/review", params={"seat": 1}).status_code
        == 200
    )
    assert (
        client.get(f"/games/{game_id}/review", params={"seat": 4}).status_code
        == 403
    )
    assert "disclosure" in final.json()["view"]
    assert (
        client.get(
            f"/games/{game_id}/review/{step_count + 1}", params={"seat": 0}
        ).status_code
        == 400
    )

    unfinished = _create(client)
    assert (
        client.get(
            f"/games/{unfinished['game_id']}/review", params={"seat": 0}
        ).status_code
        == 400
    )


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


def test_card_images_are_served_from_a_manifest_checkout(tmp_path: Path) -> None:
    cards = tmp_path / "cards"
    relative = "uprising/imperium/Sardaukar Soldier.webp"
    (cards / "en" / "uprising" / "imperium").mkdir(parents=True)
    (cards / "en" / relative).write_bytes(b"not-really-webp")
    (cards / "manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "entries": [
                    {
                        "path": relative,
                        "set": "uprising",
                        "kind": "imperium",
                        "name": "Sardaukar Soldier",
                        "name_source": "engine",
                        "content_id": "sardaukar_soldier",
                        "source": {
                            "site": "dunecardshub",
                            "file": "x",
                            "url": "u",
                            "sha256": "0",
                        },
                    }
                ],
            }
        )
    )
    with TestClient(
        create_app(saves_dir=tmp_path / "saves", card_images_dir=cards)
    ) as image_client:
        catalog = image_client.get("/catalog").json()
        soldier = catalog["cards"]["sardaukar_soldier"]
        assert soldier["image"] == (
            "/card-images/en/uprising/imperium/Sardaukar%20Soldier.webp"
        )
        assert catalog["cards"]["dagger"]["image"] is None

        served = image_client.get(soldier["image"])
        assert served.status_code == 200
        assert served.content == b"not-really-webp"


def test_card_images_degrade_to_text_without_the_cache(
    client: TestClient,
) -> None:
    catalog = client.get("/catalog").json()
    for section in ("cards", "intrigue", "contracts", "conflicts", "spaces"):
        assert all(
            entry["image"] is None for entry in catalog[section].values()
        ), section
    missing = client.get("/card-images/en/uprising/imperium/Sardaukar%20Soldier.webp")
    assert missing.status_code == 404
    assert catalog["icons"] == {}
    assert catalog["board_image"] is None
    assert client.get("/board-image").status_code == 404
    assert client.get("/icons/troop.png").status_code == 404


def test_board_scan_and_icons_are_served_when_present(tmp_path: Path) -> None:
    icons = tmp_path / "icons"
    icons.mkdir()
    (icons / "troop.png").write_bytes(b"png-troop")
    (icons / "stray.txt").write_bytes(b"ignored")
    board = tmp_path / "board.jpg"
    board.write_bytes(b"jpeg-board")
    with TestClient(
        create_app(
            saves_dir=tmp_path / "saves",
            card_images_dir=tmp_path / "no-images",
            icons_dir=icons,
            board_image=board,
        )
    ) as image_client:
        catalog = image_client.get("/catalog").json()
        assert catalog["icons"] == {"troop": "/icons/troop.png"}
        assert catalog["board_image"] == "/board-image"
        assert image_client.get("/icons/troop.png").content == b"png-troop"
        served = image_client.get("/board-image")
        assert served.status_code == 200
        assert served.content == b"jpeg-board"


def test_undo_and_log_over_http(client: TestClient) -> None:
    summary = _create(client, game_seed=14)
    game_id = str(summary["game_id"])
    while int(str(summary["revision"])) < 10:
        response = client.post(
            f"/games/{game_id}/actions",
            json={"seat": 0, "revision": summary["revision"], "index": 0},
        )
        assert response.status_code == 200, response.text
        summary = response.json()
    assert summary["revision"] == 10
    assert summary["undo"] == [{"seat": 0, "steps": 2}]

    stale = client.post(
        f"/games/{game_id}/undo", json={"seat": 0, "revision": 9, "steps": 1}
    )
    assert stale.status_code == 409, stale.text
    too_many = client.post(
        f"/games/{game_id}/undo", json={"seat": 0, "revision": 10, "steps": 3}
    )
    assert too_many.status_code == 400, too_many.text

    undone = client.post(
        f"/games/{game_id}/undo",
        json={"seat": 0, "revision": 10, "steps": 1, "undo_count": 0},
    )
    assert undone.status_code == 200, undone.text
    assert undone.json()["revision"] == 9
    assert undone.json()["undo"] == [{"seat": 0, "steps": 1}]
    assert undone.json()["undo_count"] == 1
    # A stale client still sending undo generation 0 is refused.
    stale_generation = client.post(
        f"/games/{game_id}/actions",
        json={"seat": 0, "revision": 9, "index": 0, "undo_count": 0},
    )
    assert stale_generation.status_code == 409, stale_generation.text

    log = client.get(f"/games/{game_id}/log", params={"seat": 0})
    assert log.status_code == 200, log.text
    entries = log.json()["entries"]
    assert log.json()["count"] == len(entries) == undone.json()["log_count"]
    assert entries[-1]["type"] == "undo"
    assert entries[-2]["undone"] is True
    tail = client.get(
        f"/games/{game_id}/log", params={"seat": 0, "after": len(entries) - 1}
    )
    assert [entry["index"] for entry in tail.json()["entries"]] == [len(entries) - 1]
    assert client.get(f"/games/{game_id}/log", params={"seat": 1}).status_code == 403
