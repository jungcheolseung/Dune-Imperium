"""The admin page's server side: ``GET /admin`` and ``GET /admin/status``.

User decision 2026-11-06: the host gets one page that says how the server
and its machine are doing (``server/host_status.py``), host-only, showing
no game's hidden information and no traceback.
"""

import json
import logging
import shutil
import subprocess
from pathlib import Path

import pytest

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.server.access import AccessMode
from dune_imperium.server.host_status import (
    COLLECTED_LOGGERS,
    RecentLog,
    machine_status,
    source_commit,
    uptime_seconds,
)
from dune_imperium.server.sessions import GameSessionManager

pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from dune_imperium.server.app import create_app  # noqa: E402

ADMIN_KEY = "top-secret-admin-key"


def _app(
    tmp_path: Path,
    *,
    remote: bool = True,
    recent_log: RecentLog | None = None,
    search: Path | None = None,
    imperium_search: Path | None = None,
) -> FastAPI:
    manager = (
        GameSessionManager(
            access=AccessMode.REMOTE,
            admin_key=ADMIN_KEY,
            search_checkpoint=search,
            imperium_search_checkpoint=imperium_search,
            search_turn_extend=16 if search else 0,
        )
        if remote
        else GameSessionManager()
    )
    return create_app(
        manager,
        saves_dir=tmp_path / "saves",
        card_images_dir=tmp_path / "no-images",
        icons_dir=tmp_path / "no-icons",
        tokens_dir=tmp_path / "no-tokens",
        board_image=tmp_path / "no-map.jpg",
        bene_tleilax_image=tmp_path / "no-bene-tleilax.jpg",
        public_url="http://100.100.0.50:8000" if remote else None,
        recent_log=recent_log,
    )


def _host(app: FastAPI) -> TestClient:
    client = TestClient(app)
    assert client.post("/auth/admin", json={"key": ADMIN_KEY}).status_code == 200
    return client


def test_the_admin_page_is_served_and_revalidated(tmp_path: Path) -> None:
    response = TestClient(_app(tmp_path)).get("/admin")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-cache"
    assert "/static/admin.js" in response.text


def test_only_the_host_reads_the_status(tmp_path: Path) -> None:
    app = _app(tmp_path)

    assert TestClient(app).get("/admin/status").status_code == 403
    response = _host(app).get("/admin/status")
    assert response.status_code == 200
    # Never kept in a shared browser's cache (Codex review r1).
    assert response.headers["cache-control"] == "no-store"


def test_the_status_names_the_build_the_options_and_the_machine(
    tmp_path: Path,
) -> None:
    network = tmp_path / "checkpoints" / "selfplay-s1-e3.pt"
    network.parent.mkdir()
    network.write_bytes(b"")
    original = tmp_path / "checkpoints" / "imperium-readapt-800.pt"
    original.write_bytes(b"")
    status = (
        _host(_app(tmp_path, search=network, imperium_search=original))
        .get("/admin/status")
        .json()
    )

    server = status["server"]
    assert server["action_codec"] == ACTION_CODEC_VERSION
    assert isinstance(server["observation"], int)
    assert server["access"] == "remote"
    assert server["public_url"] == "http://100.100.0.50:8000"
    assert server["autosave"] is True
    # The network's file name, never where it lives.
    assert server["search_ai"] == "selfplay-s1-e3.pt"
    assert str(tmp_path) not in json.dumps(server["search_ai"])
    # The original game's own network, the same way (user 2026-11-08).
    assert server["search_ai_imperium"] == "imperium-readapt-800.pt"
    assert str(tmp_path) not in json.dumps(server["search_ai_imperium"])
    assert server["search_turn_extend"] == 16
    assert server["tailscale_users"] == []
    assert server["uptime_seconds"] >= 0
    machine = status["machine"]
    assert machine["cpus"] and machine["cpus"] >= 1
    assert machine["disk_free"] is not None and machine["disk_total"] is not None
    assert status["log"] is None  # no collector given


def test_the_status_holds_no_game_seed(tmp_path: Path) -> None:
    app = _app(tmp_path)
    host = _host(app)
    game = host.post(
        "/games",
        json={
            "seats": ["human", "heuristic", "heuristic", "heuristic"],
            "game_seed": 4242,
        },
    )
    assert game.status_code == 200, game.text

    text = host.get("/admin/status").text

    assert "4242" not in text


def test_an_open_server_shows_its_status_to_its_one_user(tmp_path: Path) -> None:
    status = TestClient(_app(tmp_path, remote=False)).get("/admin/status")

    assert status.status_code == 200
    assert status.json()["server"]["access"] == "open"


def test_the_log_keeps_message_lines_never_a_traceback(tmp_path: Path) -> None:
    recent = RecentLog(capacity=3)
    logger = logging.getLogger("dune_imperium.tests.admin_status")
    logger.propagate = False
    logger.setLevel(logging.INFO)
    recent.attach([logger.name])
    try:
        logger.info("one")
        try:
            raise RuntimeError("the secret card Kwisatz Haderach")
        except RuntimeError:
            logger.exception("seat %d of game %s failed to answer", 2, "abc")
        logger.warning("two lines\nsecond line")
        logger.info("four")
    finally:
        logger.removeHandler(recent)
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
    lines = _host(_app(tmp_path, recent_log=recent)).get("/admin/status").json()["log"]

    assert [line["message"] for line in lines] == [
        "seat 2 of game abc failed to answer",
        "two lines",
        "four",
    ]
    assert [line["level"] for line in lines] == ["ERROR", "WARNING", "INFO"]
    assert "Kwisatz" not in json.dumps(lines)


def test_only_the_play_servers_own_loggers_are_collected() -> None:
    # An AI seat's logger may print the action it proposed, a card of its
    # hand among it (app_ai's "chose an illegal action %r"): never collected.
    assert COLLECTED_LOGGERS == ("uvicorn.error", "dune_imperium.server")
    recent = RecentLog()
    server = logging.getLogger("dune_imperium.server.tests_collected")
    agent = logging.getLogger("dune_imperium.agents.tests_collected")
    recent.attach(["dune_imperium.server"])
    try:
        server.warning("kept")
        agent.warning("chose an illegal action PlayIntrigue('Secret Card')")
    finally:
        parent = logging.getLogger("dune_imperium.server")
        for handler in list(parent.handlers):
            parent.removeHandler(handler)

    assert [line["message"] for line in recent.lines()] == ["kept"]


def test_attaching_keeps_the_console_line_of_a_logger_with_no_handler() -> None:
    logger = logging.getLogger("dune_imperium.tests.admin_status_fallback")
    recent = RecentLog()
    try:
        recent.attach([logger.name, logger.name])
        handlers = logger.handlers
        assert handlers.count(recent) == 1
        fallback = [h for h in handlers if h is not recent]
        # Root has no handler of its own in a bare process; under pytest it
        # may have one, and then nothing is added.
        if fallback:
            assert isinstance(fallback[0], logging.StreamHandler)
            assert fallback[0].level == logging.WARNING
    finally:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)


def test_machine_status_reads_the_disk_of_a_saves_folder_not_made_yet(
    tmp_path: Path,
) -> None:
    status = machine_status(tmp_path / "not" / "made" / "yet")

    assert status["disk_total"] is not None
    assert status["name"]


def test_source_commit_is_none_where_git_cannot_say(tmp_path: Path) -> None:
    # (tmp_path itself may sit inside this checkout, under tmp/.)
    assert source_commit(tmp_path / "missing") is None


@pytest.mark.skipif(shutil.which("git") is None, reason="no git")
def test_source_commit_reads_the_checkouts_head(tmp_path: Path) -> None:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(tmp_path), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    git("init", "-q")
    (tmp_path / "file").write_text("x")
    git("add", "file")
    git(
        "-c", "user.name=t", "-c", "user.email=t@example.com",
        "commit", "-q", "-m", "x",
    )

    assert source_commit(tmp_path) == git("rev-parse", "--short=8", "HEAD")


def test_uptime_is_whole_seconds_and_never_negative() -> None:
    assert uptime_seconds(100.0, now=165.9) == 65
    assert uptime_seconds(100.0, now=50.0) == 0
