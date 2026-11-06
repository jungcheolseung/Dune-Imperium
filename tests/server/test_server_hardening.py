"""The fixes of the 2026-11 security review (``server.guards``, the admin
session, the CLI's admin link). ``test_server_security_audit.py`` keeps the
review's own tests; ``test_server_connections.py`` the connection limits.
"""

import json
import os
import socket
import stat
import sys
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from dune_imperium.cli import server as server_cli  # noqa: E402
from dune_imperium.cli.server import (  # noqa: E402
    ADMIN_KEY_ENVIRONMENT,
    SEARCH_CHECKPOINT_ENVIRONMENT,
    admin_link,
    admin_link_lines,
    allowed_host_names,
    main,
)
from dune_imperium.server import connections  # noqa: E402
from dune_imperium.server.access import (  # noqa: E402
    ADMIN_SESSION_SECONDS,
    AccessMode,
    Credentials,
    admin_session_matches,
    admin_session_token,
)
from dune_imperium.server.app import ADMIN_COOKIE, create_app  # noqa: E402
from dune_imperium.server.guards import (  # noqa: E402
    MAX_REQUEST_BODY_BYTES,
    LoginThrottle,
    host_allowed,
)
from dune_imperium.server.sessions import GameSessionManager  # noqa: E402

ADMIN_KEY = "hardening-admin-key-0123456789"
TWO_HUMANS = ["human", "human", "heuristic", "heuristic"]


def _app(
    tmp_path: Path,
    *,
    key: str | None = ADMIN_KEY,
    allowed_hosts: frozenset[str] | None = None,
    machine: str | None = None,
    throttle: LoginThrottle | None = None,
) -> FastAPI:
    manager = (
        GameSessionManager(access=AccessMode.REMOTE, admin_key=key)
        if key is not None
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
        allowed_hosts=allowed_hosts,
        host_machine=machine,
        login_throttle=throttle,
    )


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    return _app(tmp_path)


def _login(client: TestClient, key: str = ADMIN_KEY) -> None:
    response = client.post("/auth/admin", json={"key": key})
    assert response.status_code == 200, response.text


# --- the admin cookie is a session, not the key (finding 3c) -----------------


def test_the_admin_cookie_is_a_session_signed_with_the_key(app: FastAPI) -> None:
    host = TestClient(app)
    response = host.post("/auth/admin", json={"key": ADMIN_KEY})

    assert response.status_code == 200
    session = host.cookies.get(ADMIN_COOKIE)
    assert session is not None
    assert ADMIN_KEY not in session
    assert ADMIN_KEY not in response.headers["set-cookie"]
    assert admin_session_matches(ADMIN_KEY, session)
    assert host.get("/whoami").json()["admin"] is True
    assert host.post("/games", json={"seats": TWO_HUMANS}).status_code == 200


def test_the_raw_key_as_a_cookie_opens_nothing(app: FastAPI) -> None:
    # Otherwise GET /whoami would answer key guesses with no attempt limit.
    guesser = TestClient(app, cookies={ADMIN_COOKIE: ADMIN_KEY})

    assert guesser.get("/whoami").json()["admin"] is False
    assert guesser.get("/games").status_code == 403
    assert guesser.post("/games", json={"seats": TWO_HUMANS}).status_code == 403


def test_a_session_outlives_a_restart_with_the_same_key_only(tmp_path: Path) -> None:
    first = TestClient(_app(tmp_path))
    _login(first)
    session = first.cookies.get(ADMIN_COOKIE)
    assert session is not None

    # The always-on server keeps its key across restarts: the host's
    # browser stays the host's. A new key revokes every session.
    restarted = TestClient(_app(tmp_path), cookies={ADMIN_COOKIE: session})
    assert restarted.get("/whoami").json()["admin"] is True
    rotated = TestClient(
        _app(tmp_path, key="another-admin-key-0123456789"),
        cookies={ADMIN_COOKIE: session},
    )
    assert rotated.get("/whoami").json()["admin"] is False


def test_a_session_expires_with_its_cookie_and_cannot_be_altered() -> None:
    now = 1_800_000_000.0
    token = admin_session_token(ADMIN_KEY, now=now)

    assert admin_session_matches(ADMIN_KEY, token, now=now)
    assert admin_session_matches(ADMIN_KEY, token, now=now + ADMIN_SESSION_SECONDS)
    assert not admin_session_matches(
        ADMIN_KEY, token, now=now + ADMIN_SESSION_SECONDS + 1
    )
    assert not admin_session_matches(ADMIN_KEY, token, now=now - 120)
    version, issued, nonce, mac = token.split(".")
    later = str(int(issued) + 3600)
    for altered in (
        f"{version}.{later}.{nonce}.{mac}",
        f"{version}.{issued}.{nonce}x.{mac}",
        f"{version}.{issued}.{nonce}.{mac[:-1]}",
        f"v2.{issued}.{nonce}.{mac}",
        f"{issued}.{nonce}.{mac}",
        "",
    ):
        assert not admin_session_matches(ADMIN_KEY, altered, now=now), altered
    assert token != admin_session_token(ADMIN_KEY, now=now)  # a nonce each


@pytest.mark.parametrize("issued", ["²", "١٢", "1e3", " 12", "+12", "-12", "1" * 13])
def test_a_session_time_that_is_not_ascii_digits_is_refused(issued: str) -> None:
    # Codex review of this branch (2026-11-03): a cookie is read as Latin-1,
    # and str.isdigit takes "²" (byte 0xB2), which int refuses: a 500. (The
    # test client re-encodes such a byte, so this is checked below HTTP.)
    forged = f"v1.{issued}.nonce.mac"
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key=ADMIN_KEY)

    assert not admin_session_matches(ADMIN_KEY, forged)
    assert not manager.is_admin(Credentials(admin_session=forged))


@pytest.mark.parametrize(
    "cookie",
    [
        b"v1.1.\xe9.x",
        b"v1.99999999999999999999.n.m",
        b"v1.-5.n.m",
        b"\x7f",
        b"",
    ],
)
def test_a_forged_admin_cookie_is_refused_not_a_crash(
    app: FastAPI, cookie: bytes
) -> None:
    # Starlette reads a cookie header as Latin-1: any byte reaches the check.
    client = TestClient(app, raise_server_exceptions=False)
    headers = {b"Cookie": ADMIN_COOKIE.encode() + b"=" + cookie}
    assert client.get("/whoami", headers=headers).json()["admin"] is False
    assert client.get("/games", headers=headers).status_code == 403


# --- the login's attempt limit (finding 3b) ----------------------------------


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_an_address_that_keeps_guessing_is_held_off(tmp_path: Path) -> None:
    clock = _Clock()
    app = _app(tmp_path, throttle=LoginThrottle(failures=5, window=60, clock=clock))
    guesser = TestClient(app, client=("100.64.0.9", 50000))
    host = TestClient(app, client=("100.64.0.1", 50000))

    for _ in range(5):
        assert guesser.post("/auth/admin", json={"key": "wrong"}).status_code == 403
    held = guesser.post("/auth/admin", json={"key": ADMIN_KEY})
    assert held.status_code == 429
    assert held.headers["retry-after"] == "61"
    assert "set-cookie" not in held.headers
    # Another address is not held off, and the guesser is again once the
    # window has passed.
    _login(host)
    clock.now += 61
    _login(guesser)


def test_the_right_key_clears_an_addresss_failures() -> None:
    clock = _Clock()
    throttle = LoginThrottle(failures=3, window=60, clock=clock)

    assert throttle.attempt("a") is None
    assert throttle.attempt("a") is None
    throttle.succeeded("a")
    assert throttle.failures("a") == 0
    for _ in range(3):
        assert throttle.attempt("a") is None
    assert throttle.failures("a") == 3
    assert throttle.attempt("a") == 60  # held off, and not counted
    clock.now += 30
    assert throttle.attempt("a") == 30
    clock.now += 31
    assert throttle.attempt("a") is None
    assert throttle.failures("a") == 1  # the old ones have aged out


def test_logins_sent_all_at_once_cannot_pass_the_limit_together() -> None:
    throttle = LoginThrottle(failures=5, window=60)
    barrier = threading.Barrier(40)
    passed: list[bool] = []

    def log_in() -> None:
        barrier.wait()
        passed.append(throttle.attempt("100.64.0.9") is None)

    threads = [threading.Thread(target=log_in) for _ in range(40)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert passed.count(True) == 5


def test_the_throttle_forgets_old_addresses_before_it_grows() -> None:
    clock = _Clock()
    throttle = LoginThrottle(failures=2, window=10, clock=clock, max_addresses=3)
    for address in ("a", "b", "c"):
        throttle.attempt(address)
    clock.now += 11
    for address in ("d", "e", "f", "g"):  # full of current ones: the oldest goes
        throttle.attempt(address)
    assert len(throttle._recent) == 3
    assert throttle.failures("d") == 0 and "d" not in throttle._recent


def test_an_open_server_keeps_no_count(tmp_path: Path) -> None:
    local = TestClient(_app(tmp_path, key=None))
    for _ in range(8):
        assert local.post("/auth/admin", json={"key": "anything"}).status_code == 400


# --- the request body limit (finding 2) --------------------------------------


def test_a_declared_oversized_body_is_refused_unread(app: FastAPI) -> None:
    stranger = TestClient(app)
    body = json.dumps({"name": "x" * MAX_REQUEST_BODY_BYTES})

    response = stranger.post(
        "/games/" + "0" * 32 + "/seats/0/claim",
        content=body,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.headers["connection"] == "close"
    assert response.json() == {"detail": "request body too large"}


def test_a_chunked_oversized_body_is_refused_as_it_passes_the_limit(
    app: FastAPI,
) -> None:
    sent: list[int] = []

    def chunks() -> Iterator[bytes]:
        yield b'{"key": "'
        for _ in range(64):
            sent.append(4096)
            yield b"k" * 4096
        yield b'"}'

    response = TestClient(app).post(
        "/auth/admin", content=chunks(), headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 413
    assert response.headers["connection"] == "close"
    assert response.json() == {"detail": "request body too large"}


def test_the_largest_real_body_is_far_under_the_limit(app: FastAPI) -> None:
    # The setup screen's POST /games with everything on and the longest seat
    # kinds there are: what the limit has to leave room for.
    host = TestClient(app)
    _login(host)
    body = {
        "seats": [f"checkpoint:{'/very/long/path' * 60}.pt"] * 4,
        "base_game": "uprising",
        **{
            option: True
            for option in (
                "choam_module",
                "leader_draft",
                "promo_cards",
                "bloodlines",
                "tech_module",
                "immortality",
                "go_to_11",
                "epic_game",
                "rise_of_ix",
                "imperium_cards",
                "ix_tech_tiles",
                "ix_leaders",
                "arrakeen_scouts",
                "first_player_seat_zero",
                "seats_at_start",
            )
        },
        "game_seed": 2**63,
        "policy_seed": 2**63,
        "ai_pace": "instant",
    }
    size = len(json.dumps(body))

    assert size * 10 < MAX_REQUEST_BODY_BYTES
    response = host.post(
        "/games", content=json.dumps(body), headers={"Content-Type": "application/json"}
    )
    assert response.status_code != 413


# --- invalid bodies are client errors, never 500s (finding 6) ----------------


_ODD_VALUES = ("Infinity", "-Infinity", "NaN", '"\\ud800"', '"\\udfff x"', "1e999")


def _game_with_seat0(app: FastAPI) -> tuple[TestClient, TestClient, str]:
    host = TestClient(app, raise_server_exceptions=False)
    _login(host)
    created = host.post("/games", json={"seats": TWO_HUMANS, "game_seed": 3})
    game_id = str(created.json()["game_id"])
    player = TestClient(app, raise_server_exceptions=False)
    claim = player.post(f"/games/{game_id}/seats/0/claim", json={"name": "P0"})
    assert claim.status_code == 200, claim.text
    return host, player, game_id


def test_no_body_value_makes_any_route_fail_on_the_server(app: FastAPI) -> None:
    # The review's fuzz found 93 such 500s, all from the 422 echoing its
    # input; this sends each odd JSON value in every field of every JSON
    # route, as a stranger, the seat's holder and the host.
    host, player, game_id = _game_with_seat0(app)
    stranger = TestClient(app, raise_server_exceptions=False)
    revision = int(player.get(f"/games/{game_id}").json()["revision"])
    routes: list[tuple[str, dict[str, object]]] = [
        ("/auth/admin", {"key": ADMIN_KEY}),
        ("/games", {"seats": TWO_HUMANS, "game_seed": 3, "ai_pace": "normal"}),
        (f"/games/{game_id}/ai-pace", {"pace": "fast"}),
        (
            f"/games/{game_id}/actions",
            {"seat": 0, "revision": revision, "index": 0, "undo_count": 0},
        ),
        (
            f"/games/{game_id}/undo",
            {"seat": 0, "revision": revision, "steps": 1, "undo_count": 0},
        ),
        (f"/games/{game_id}/confirm", {"seat": 0, "revision": revision}),
        (f"/games/{game_id}/seats/1/claim", {"name": "P1"}),
        (f"/games/{game_id}/save", {"name": "kept"}),
    ]
    seen = 0
    for path, body in routes:
        for name in body:
            for value in _ODD_VALUES:
                raw = json.dumps({**body, name: "__ODD__"}).replace('"__ODD__"', value)
                for client in (stranger, player, host):
                    response = client.post(
                        path,
                        content=raw,
                        headers={"Content-Type": "application/json"},
                    )
                    seen += 1
                    assert response.status_code < 500, (path, raw, response.text)
                    if response.status_code == 422:
                        assert "input" not in response.text
    assert seen > 300


def test_a_422_says_what_was_wrong_without_repeating_the_body(app: FastAPI) -> None:
    response = TestClient(app).post("/auth/admin", json={"key": "k" * 20_000})

    assert response.status_code == 422
    assert len(response.content) < 500
    (problem,) = response.json()["detail"]
    assert problem["loc"] == ["body", "key"]
    assert problem["type"] == "string_too_long"
    assert set(problem) == {"loc", "msg", "type"}


# --- per-seat answers are not stored (finding 4) -----------------------------


def test_the_hosts_and_the_seats_answers_are_not_stored(app: FastAPI) -> None:
    host, player, game_id = _game_with_seat0(app)
    private = [
        (player, f"/games/{game_id}"),
        (player, f"/games/{game_id}/me"),
        (player, f"/games/{game_id}/vp-ledger"),
        (host, "/games"),
        (host, "/saves"),
        (host, "/whoami"),
    ]
    for client, path in private:
        response = client.get(path)
        assert response.status_code == 200, (path, response.text)
        assert response.headers.get("cache-control") == "no-store", path
    login = host.post("/auth/admin", json={"key": ADMIN_KEY})
    assert login.headers["cache-control"] == "no-store"
    # The UI files keep revalidating and the catalog may be cached.
    assert host.get("/").headers["cache-control"] == "no-cache"
    assert "cache-control" not in host.get("/catalog").headers


def test_a_local_server_keeps_its_api_pages(tmp_path: Path) -> None:
    local = TestClient(_app(tmp_path, key=None))
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert local.get(path).status_code == 200, path


# --- the Host allow-list (finding 9) -----------------------------------------


@pytest.mark.parametrize(
    ("host", "allowed"),
    [
        (None, True),
        ("", True),
        ("100.112.246.50:8000", True),
        ("100.112.246.50", True),
        ("127.0.0.1:8000", True),
        ("[::1]:8000", True),
        ("[fe80::1%25en0]:8000", True),
        ("localhost:8000", True),
        ("LOCALHOST.:8000", True),
        ("beelink-01:8000", True),
        ("beelink-01.tail1a2b.ts.net:8000", True),
        ("beelink-01.local", True),
        ("play.example.org:8000", True),
        ("evil.example:8000", False),
        ("beelink-01.evil.example", False),
        ("other-pc.tail1a2b.ts.net", False),
        ("beelink-01.a.b.ts.net", False),
        ("127.0.0.1.nip.io", False),
    ],
)
def test_only_this_servers_names_and_addresses_pass(
    host: str | None, allowed: bool
) -> None:
    names, machine = allowed_host_names(
        "100.112.246.50", "http://play.example.org:8000", hostname="beelink-01"
    )
    assert host_allowed(host, names, machine) is allowed


def test_the_allowed_names_come_from_the_command_line() -> None:
    names, machine = allowed_host_names(
        "Beelink-01.lan", "https://Play.Example.org/", hostname="beelink-01.lan"
    )

    assert machine == "beelink-01"
    assert names == {
        "localhost",
        "beelink-01",
        "beelink-01.lan",
        "beelink-01.local",
        "play.example.org",
    }


def test_a_rebound_name_is_refused_before_anything_answers(tmp_path: Path) -> None:
    names, machine = allowed_host_names("100.112.246.50", None, hostname="beelink-01")
    app = _app(tmp_path, allowed_hosts=names, machine=machine)

    rebound = TestClient(app, base_url="http://attacker.example:8000")
    assert rebound.get("/whoami").status_code == 400
    assert rebound.post("/auth/admin", json={"key": ADMIN_KEY}).status_code == 400
    direct = TestClient(app, base_url="http://100.112.246.50:8000")
    assert direct.get("/whoami").status_code == 200


# --- the admin link at start (finding 3a) ------------------------------------


def test_the_whole_link_is_printed_only_to_a_terminal() -> None:
    link = admin_link("100.112.246.50", 8000, ADMIN_KEY)
    source = ADMIN_KEY_ENVIRONMENT

    assert admin_link_lines(link, source, terminal=True, link_file=None) == [
        "Remote multiplayer access is on. Host admin link (keep it private):",
        f"  {link}",
    ]
    assert admin_link_lines(link, source, terminal=False, link_file=None) == [
        "Remote multiplayer access is on. Host admin link (keep it private):",
        "  http://100.112.246.50:8000/#admin=…",
        "  (#admin= takes the key given as DUNE_IMPERIUM_ADMIN_KEY; it is printed "
        "only to a terminal)",
    ]


@dataclass
class _Started:
    """What ``main`` handed uvicorn, and the link files while it "served"."""

    configs: list[Any] = field(default_factory=list)
    link_files: list[tuple[Path, str, int]] = field(default_factory=list)


def test_a_fresh_key_with_no_file_to_hold_it_says_how_to_get_one() -> None:
    link = admin_link("127.0.0.1", 8000, "k" * 32)

    lines = admin_link_lines(link, None, terminal=False, link_file=None)

    assert "k" * 32 not in "\n".join(lines)
    assert lines[-1] == (
        "  (a fresh key for this start, printed only to a terminal: start in "
        "one, or give the key with --admin-key or DUNE_IMPERIUM_ADMIN_KEY)"
    )


def _main_without_serving(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _Started:
    uvicorn = pytest.importorskip("uvicorn")
    started = _Started()

    def keep_the_config(self: Any, *args: object, **kwargs: object) -> None:
        started.configs.append(self.config)
        for path in sorted((tmp_path / "links").glob("*")):
            text = path.read_text(encoding="utf-8")
            started.link_files.append((path, text, path.stat().st_mode))

    monkeypatch.setattr(uvicorn.Server, "run", keep_the_config)
    monkeypatch.setattr(server_cli, "ADMIN_LINK_DIR", tmp_path / "links")
    monkeypatch.delenv(SEARCH_CHECKPOINT_ENVIRONMENT, raising=False)
    monkeypatch.delenv(ADMIN_KEY_ENVIRONMENT, raising=False)
    return started


def _port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
        return port


def _saves(tmp_path: Path) -> list[str]:
    return ["--saves-dir", str(tmp_path / "saves")]


def test_a_given_key_never_reaches_a_services_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    started = _main_without_serving(monkeypatch, tmp_path)
    monkeypatch.setenv(ADMIN_KEY_ENVIRONMENT, ADMIN_KEY)
    port = _port()

    code = main(["--remote", "--port", str(port), *_saves(tmp_path)])

    output = capsys.readouterr()
    assert code == 0
    assert ADMIN_KEY not in output.out + output.err
    assert f"  http://127.0.0.1:{port}/#admin=…" in output.out.splitlines()
    assert "the key given as DUNE_IMPERIUM_ADMIN_KEY" in output.out
    assert started.link_files == []  # the host has the key it gave


def test_a_fresh_key_goes_to_a_private_file_for_the_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    started = _main_without_serving(monkeypatch, tmp_path)
    port = _port()

    code = main(["--remote", "--port", str(port), *_saves(tmp_path)])

    output = capsys.readouterr().out
    assert code == 0
    link_file = tmp_path / "links" / f"admin-link-{port}-{os.getpid()}.txt"
    ((path, text, mode),) = started.link_files
    assert path == link_file
    assert text.startswith(f"http://127.0.0.1:{port}/#admin=")
    key = text.strip().rsplit("=", 1)[1]
    assert len(key) == 32 and key not in output
    if os.name == "posix":
        assert stat.S_IMODE(mode) == 0o600
    assert f"the whole link is in {link_file}" in output
    assert not link_file.exists()  # gone with the server


def test_a_terminal_still_shows_the_whole_link(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    started = _main_without_serving(monkeypatch, tmp_path)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    port = _port()

    code = main(
        ["--remote", "--admin-key", ADMIN_KEY, "--port", str(port), *_saves(tmp_path)]
    )

    assert code == 0
    assert f"  http://127.0.0.1:{port}/#admin={ADMIN_KEY}" in capsys.readouterr().out
    assert started.link_files == []


# --- what main hands uvicorn (finding 1) -------------------------------------


def test_the_server_runs_with_the_connection_limits_and_the_host_check(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from uvicorn.protocols.http.h11_impl import H11Protocol

    started = _main_without_serving(monkeypatch, tmp_path)
    monkeypatch.setattr(connections, "raise_open_file_limit", lambda: 4096)

    code = main(
        [
            "--port",
            str(_port()),
            "--max-connections",
            "100",
            "--max-connections-per-client",
            "7",
            "--request-timeout",
            "2.5",
            *_saves(tmp_path),
        ]
    )

    assert code == 0
    (config,) = started.configs
    assert issubclass(config.http, H11Protocol)
    assert config.limit_concurrency == 101
    assert config.timeout_keep_alive == 5
    assert config.backlog == 1884  # (4096 - 128 - 2 x 100) / 2
    app = config.app
    assert (
        TestClient(app, base_url="http://evil.example").get("/whoami").status_code
        == 400
    )
    assert (
        TestClient(app, base_url="http://127.0.0.1").get("/whoami").status_code == 200
    )


def test_the_connection_cap_fits_the_open_file_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    started = _main_without_serving(monkeypatch, tmp_path)
    monkeypatch.setattr(connections, "raise_open_file_limit", lambda: 256)

    assert main(["--port", str(_port()), *_saves(tmp_path)]) == 0

    (config,) = started.configs
    assert config.limit_concurrency == 65
    assert config.backlog == 16
    assert (
        "At most 64 connections: the limit on open files is 256 (ulimit -n)"
        in capsys.readouterr().out.splitlines()
    )


@pytest.mark.parametrize(
    ("flag", "value"),
    [
        ("--max-connections", "0"),
        ("--max-connections-per-client", "-1"),
        ("--request-timeout", "0"),
        ("--request-timeout", "inf"),
        ("--request-timeout", "nan"),
    ],
)
def test_a_limit_must_be_positive(flag: str, value: str) -> None:
    with pytest.raises(SystemExit):
        main([flag, value])
