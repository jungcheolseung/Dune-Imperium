"""HTTP-level tests for the play server's autosave (M14 slice 5), needs the
``ui`` extra: ``docs/multiplayer-design.md`` section 4.7. ``test_autosave.py``
covers the session layer and the store directly; this module covers the
``server.app`` wiring: ``create_app(autosave=...)`` and ``GET /whoami``."""

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from dune_imperium.server.access import AccessMode  # noqa: E402
from dune_imperium.server.app import create_app  # noqa: E402
from dune_imperium.server.sessions import GameSessionManager  # noqa: E402

ADMIN_KEY = "top-secret-admin-key"


def _obj(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _rows(value: object) -> list[dict[str, object]]:
    assert isinstance(value, list)
    return [_obj(item) for item in value]


def _int(value: object) -> int:
    assert isinstance(value, int)
    return value


def _remote_app(
    tmp_path: Path, *, saves_dir: Path | None = None, autosave: bool | None = None
) -> FastAPI:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key=ADMIN_KEY)
    return create_app(
        manager,
        saves_dir=saves_dir if saves_dir is not None else tmp_path / "saves",
        card_images_dir=tmp_path / "no-images",
        icons_dir=tmp_path / "no-icons",
        tokens_dir=tmp_path / "no-tokens",
        board_image=tmp_path / "no-map.jpg",
        bene_tleilax_image=tmp_path / "no-bene-tleilax.jpg",
        autosave=autosave,
    )


def _open_app(
    tmp_path: Path, *, saves_dir: Path | None = None, autosave: bool | None = None
) -> FastAPI:
    return create_app(
        saves_dir=saves_dir if saves_dir is not None else tmp_path / "saves",
        card_images_dir=tmp_path / "no-images",
        icons_dir=tmp_path / "no-icons",
        tokens_dir=tmp_path / "no-tokens",
        board_image=tmp_path / "no-map.jpg",
        bene_tleilax_image=tmp_path / "no-bene-tleilax.jpg",
        autosave=autosave,
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


def _claim_seat0(client: TestClient, game_id: object) -> dict[str, object]:
    response = client.post(f"/games/{game_id}/seats/0/claim", json={"name": "Host"})
    assert response.status_code == 200, response.text
    summary: dict[str, object] = response.json()
    return summary


def _play_seat0_until_confirmation(
    client: TestClient, game_id: object, summary: dict[str, object]
) -> dict[str, object]:
    for _ in range(400):
        if summary.get("confirmation") == 0:
            return summary
        response = client.post(
            f"/games/{game_id}/actions",
            json={"seat": 0, "revision": summary["revision"], "index": 0},
        )
        assert response.status_code == 200, response.text
        summary = response.json()
    raise AssertionError("seat 0 never paused for a turn-end confirmation")


def _confirm_seat0(
    client: TestClient, game_id: object, summary: dict[str, object]
) -> dict[str, object]:
    response = client.post(
        f"/games/{game_id}/confirm",
        json={"seat": 0, "revision": summary["revision"]},
    )
    assert response.status_code == 200, response.text
    result: dict[str, object] = response.json()
    return result


def _play_one_hand_over(
    client: TestClient, game_id: object, summary: dict[str, object]
) -> dict[str, object]:
    summary = _play_seat0_until_confirmation(client, game_id, summary)
    return _confirm_seat0(client, game_id, summary)


# --- one file per game, listed with autosave metadata ------------------


def test_a_confirmed_turn_leaves_exactly_one_autosave_file(tmp_path: Path) -> None:
    app = _remote_app(tmp_path)
    admin = _admin_client(app)
    summary = _create(admin, seats=["human", "heuristic", "heuristic", "heuristic"])
    game_id = summary["game_id"]
    summary = _claim_seat0(admin, game_id)

    _play_one_hand_over(admin, game_id, summary)

    files = list((tmp_path / "saves").glob("*.json"))
    assert [path.name for path in files] == [f"{game_id}.json"]

    listing = admin.get("/saves")
    assert listing.status_code == 200
    matching = [entry for entry in _rows(listing.json()) if entry["save_id"] == game_id]
    assert len(matching) == 1
    entry = matching[0]
    assert entry["autosave"] is True
    assert entry["game_seed"] is None
    assert entry["source_game_id"] == game_id

    stranger_listing = TestClient(app).get("/saves")
    assert stranger_listing.status_code == 403


def test_the_file_count_stays_one_and_step_count_never_decreases(
    tmp_path: Path,
) -> None:
    app = _remote_app(tmp_path)
    admin = _admin_client(app)
    summary = _create(admin, seats=["human", "heuristic", "heuristic", "heuristic"])
    game_id = summary["game_id"]
    summary = _claim_seat0(admin, game_id)

    step_counts: list[int] = []
    for _ in range(6):
        if summary.get("finished"):
            break
        summary = _play_one_hand_over(admin, game_id, summary)
        files = list((tmp_path / "saves").glob("*.json"))
        assert [path.name for path in files] == [f"{game_id}.json"]
        listing = _rows(admin.get("/saves").json())
        entry = next(e for e in listing if e["save_id"] == game_id)
        step_counts.append(_int(entry["step_count"]))

    assert len(step_counts) >= 2
    assert all(
        later >= earlier
        for earlier, later in zip(step_counts, step_counts[1:], strict=False)
    )


# --- loading the autosave ------------------------------------------------


def test_loading_the_autosave_creates_a_fresh_unclaimed_game(tmp_path: Path) -> None:
    app = _remote_app(tmp_path)
    admin = _admin_client(app)
    summary = _create(admin, seats=["human", "heuristic", "heuristic", "heuristic"])
    game_id = summary["game_id"]
    summary = _claim_seat0(admin, game_id)
    _play_one_hand_over(admin, game_id, summary)

    listing = _rows(admin.get("/saves").json())
    entry = next(e for e in listing if e["save_id"] == game_id)

    loaded = admin.post(f"/saves/{game_id}/load")
    assert loaded.status_code == 200, loaded.text
    restored = _obj(loaded.json())
    assert restored["game_id"] != game_id
    assert all(player["claimed"] is False for player in _rows(restored["players"]))
    assert restored["revision"] == entry["step_count"]
    assert restored["round_number"] == entry["round_number"]

    new_id = restored["game_id"]
    new_summary = _claim_seat0(admin, new_id)
    _play_one_hand_over(admin, new_id, new_summary)

    files = sorted(path.name for path in (tmp_path / "saves").glob("*.json"))
    assert files == sorted([f"{game_id}.json", f"{new_id}.json"])


# --- open server: unaffected by default ----------------------------------


def test_an_open_server_autosaves_nothing_by_default(tmp_path: Path) -> None:
    app = _open_app(tmp_path)
    client = TestClient(app)
    summary = _create(client, seats=["human", "heuristic", "heuristic", "heuristic"])
    game_id = summary["game_id"]

    _play_one_hand_over(client, game_id, summary)

    saves_dir = tmp_path / "saves"
    assert not saves_dir.exists() or list(saves_dir.glob("*.json")) == []
    whoami = client.get("/whoami")
    assert whoami.json()["autosave"] is False


# --- explicit override works both directions ------------------------------


def test_explicit_autosave_override_works_both_directions(tmp_path: Path) -> None:
    remote_off_dir = tmp_path / "remote-off"
    remote_off = _remote_app(
        remote_off_dir, saves_dir=remote_off_dir / "saves", autosave=False
    )
    admin = _admin_client(remote_off)
    summary = _create(admin, seats=["human", "heuristic", "heuristic", "heuristic"])
    game_id = summary["game_id"]
    _claim_seat0(admin, game_id)
    _play_one_hand_over(admin, game_id, summary)
    assert list((remote_off_dir / "saves").glob("*.json")) == []
    assert admin.get("/whoami").json()["autosave"] is False

    open_on_dir = tmp_path / "open-on"
    open_on = _open_app(open_on_dir, saves_dir=open_on_dir / "saves", autosave=True)
    client = TestClient(open_on)
    open_summary = _create(
        client, seats=["human", "heuristic", "heuristic", "heuristic"]
    )
    open_game_id = open_summary["game_id"]
    _play_one_hand_over(client, open_game_id, open_summary)

    files = list((open_on_dir / "saves").glob("*.json"))
    assert [path.name for path in files] == [f"{open_game_id}.json"]
    assert client.get("/whoami").json()["autosave"] is True
    listing = _rows(client.get("/saves").json())
    entry = next(e for e in listing if e["save_id"] == open_game_id)
    # An open server never hides seeds, finished or not (see save_metadata).
    assert entry["game_seed"] is not None


# --- /whoami ---------------------------------------------------------------


def test_whoami_autosave_flag_on_a_default_remote_app(tmp_path: Path) -> None:
    app = _remote_app(tmp_path)

    stranger = TestClient(app).get("/whoami")
    host = _admin_client(app).get("/whoami")

    assert stranger.json()["autosave"] is True
    assert host.json()["autosave"] is True


# --- deleting the live game keeps the autosave file -----------------------


def test_deleting_the_game_keeps_its_autosave_file(tmp_path: Path) -> None:
    app = _remote_app(tmp_path)
    admin = _admin_client(app)
    summary = _create(admin, seats=["human", "heuristic", "heuristic", "heuristic"])
    game_id = summary["game_id"]
    summary = _claim_seat0(admin, game_id)
    _play_one_hand_over(admin, game_id, summary)
    assert list((tmp_path / "saves").glob("*.json"))

    deleted = admin.delete(f"/games/{game_id}")
    assert deleted.status_code == 200, deleted.text

    files = [path.name for path in (tmp_path / "saves").glob("*.json")]
    assert files == [f"{game_id}.json"]


# --- a failing store never fails the player's own request -----------------


def test_a_failing_store_does_not_fail_the_confirm_request(tmp_path: Path) -> None:
    blocked = tmp_path / "saves-is-a-file"
    blocked.write_text("occupied", encoding="utf-8")
    app = _remote_app(tmp_path, saves_dir=blocked)
    admin = _admin_client(app)
    summary = _create(admin, seats=["human", "heuristic", "heuristic", "heuristic"])
    game_id = summary["game_id"]
    summary = _claim_seat0(admin, game_id)
    summary = _play_seat0_until_confirmation(admin, game_id, summary)

    confirmed = admin.post(
        f"/games/{game_id}/confirm",
        json={"seat": 0, "revision": summary["revision"]},
    )

    assert confirmed.status_code == 200, confirmed.text
