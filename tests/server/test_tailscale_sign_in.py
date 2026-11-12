"""The host's own Tailscale devices sign in as admin without the key.

User decision 2026-11-06 (``server/tailnet.py``): a remote server bound to
its Tailscale address asks tailscaled which account a connection's device
belongs to and hands the host's devices the usual admin cookie; the
friends, who reach it by machine sharing, belong to their own accounts.
"""

import argparse
import json
import os
import socket
import stat
import subprocess
import sys
import threading
from collections.abc import Sequence
from pathlib import Path

import pytest

from dune_imperium.cli import server as server_cli
from dune_imperium.cli.server import (
    SEARCH_CHECKPOINT_ENVIRONMENT,
    _build_parser,
    main,
    resolve_tailnet_admins,
    tailnet_lines,
)
from dune_imperium.server.access import AccessMode
from dune_imperium.server.sessions import (
    AdminAccessError,
    GameSessionManager,
    SessionError,
)
from dune_imperium.server.tailnet import (
    TailscaleWhois,
    find_tailscale_cli,
    is_tailscale_address,
    login_problem,
)

ADMIN_KEY = "top-secret-admin-key"
HOST_LOGIN = "host@example.com"
FRIEND_LOGIN = "friend@example.com"
HOST_DEVICE = "100.80.0.12"
FRIEND_DEVICE = "100.99.1.2"


# --- the address ranges and login names ---------------------------------


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("100.64.0.1", True),
        ("100.100.0.50", True),
        ("100.127.255.254", True),
        ("100.63.255.255", False),
        ("100.128.0.1", False),
        ("fd7a:115c:a1e0::401:ece8", True),
        ("fd7a:115c:a1e1::1", False),
        ("127.0.0.1", False),
        ("0.0.0.0", False),
        ("192.168.0.65", False),
        ("cs-play-box", False),
        ("", False),
    ],
)
def test_only_tailscale_addresses_count(host: str, expected: bool) -> None:
    assert is_tailscale_address(host) is expected


@pytest.mark.parametrize(
    ("login", "ok"),
    [
        ("name@gmail.com", True),
        ("name@github", True),
        ("tagged-devices", False),
        ("", False),
        ("two words@example.com", False),
    ],
)
def test_a_login_name_has_an_at_sign_and_no_space(login: str, ok: bool) -> None:
    assert (login_problem(login) is None) is ok


# --- asking tailscaled ---------------------------------------------------


class FakeRunner:
    """Stands in for running ``tailscale whois --json <address>``."""

    def __init__(self, answers: dict[str, object]) -> None:
        self.answers = answers
        self.calls: list[tuple[str, ...]] = []

    def __call__(
        self, command: Sequence[str], *, timeout: float
    ) -> subprocess.CompletedProcess[bytes]:
        self.calls.append(tuple(command))
        answer = self.answers.get(command[-1])
        if isinstance(answer, BaseException):
            raise answer
        if answer is None:
            return subprocess.CompletedProcess(command, 1, b"", b"no such peer")
        body = answer if isinstance(answer, bytes) else json.dumps(answer).encode()
        return subprocess.CompletedProcess(command, 0, body, b"")


def _profile(login: str) -> dict[str, object]:
    return {"Node": {"Name": "device."}, "UserProfile": {"LoginName": login}}


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_whois_reads_the_login_name_of_the_devices_account() -> None:
    runner = FakeRunner({HOST_DEVICE: _profile(HOST_LOGIN)})
    whois = TailscaleWhois(("tailscale",), runner=runner)

    assert whois.login_of(HOST_DEVICE) == HOST_LOGIN
    assert runner.calls == [("tailscale", "whois", "--json", HOST_DEVICE)]


@pytest.mark.parametrize("address", ["127.0.0.1", "192.168.1.64", "testclient", ""])
def test_whois_never_runs_for_an_address_outside_tailscale(address: str) -> None:
    runner = FakeRunner({})
    whois = TailscaleWhois(("tailscale",), runner=runner)

    assert whois.login_of(address) is None
    assert runner.calls == []


@pytest.mark.parametrize(
    "answer",
    [
        None,  # tailscaled does not know the peer (a non-zero exit)
        b"not json",
        b"[]",
        {"UserProfile": "nope"},
        {"Node": {}, "UserProfile": {"LoginName": 7}},
        {"UserProfile": {"LoginName": HOST_LOGIN}},  # no Node
        _profile("tagged-devices"),
        # A tagged device answers with its tags even beside the login of
        # whoever tagged it: its identity is the tags (Codex review r1).
        {"Node": {"Tags": ["tag:server"]}, "UserProfile": {"LoginName": HOST_LOGIN}},
        subprocess.TimeoutExpired("tailscale", 3.0),
        FileNotFoundError("tailscale"),
    ],
)
def test_whois_vouches_for_nobody_when_the_answer_is_not_an_account(
    answer: object,
) -> None:
    whois = TailscaleWhois(("tailscale",), runner=FakeRunner({HOST_DEVICE: answer}))

    assert whois.login_of(HOST_DEVICE) is None


def test_whois_keeps_an_answer_a_minute_and_a_failure_ten_seconds() -> None:
    clock = Clock()
    runner = FakeRunner({HOST_DEVICE: _profile(HOST_LOGIN), FRIEND_DEVICE: None})
    whois = TailscaleWhois(("tailscale",), runner=runner, clock=clock)

    for _ in range(3):
        assert whois.login_of(HOST_DEVICE) == HOST_LOGIN
        assert whois.login_of(FRIEND_DEVICE) is None
    assert len(runner.calls) == 2
    clock.now += 11
    whois.login_of(HOST_DEVICE)
    whois.login_of(FRIEND_DEVICE)
    assert len(runner.calls) == 3  # only the failure was asked again
    clock.now += 50
    whois.login_of(HOST_DEVICE)
    assert len(runner.calls) == 4


class BlockingRunner(FakeRunner):
    """A runner whose every run waits until the test lets it go."""

    def __init__(self, answers: dict[str, object]) -> None:
        super().__init__(answers)
        self.go = threading.Event()
        self.started = threading.Semaphore(0)

    def __call__(
        self, command: Sequence[str], *, timeout: float
    ) -> subprocess.CompletedProcess[bytes]:
        self.started.release()
        assert self.go.wait(10)
        return super().__call__(command, timeout=timeout)


def test_parallel_lookups_of_one_address_share_one_run() -> None:
    runner = BlockingRunner({FRIEND_DEVICE: _profile(FRIEND_LOGIN)})
    whois = TailscaleWhois(("tailscale",), runner=runner)
    answers: list[str | None] = []

    def ask() -> None:
        answers.append(whois.login_of(FRIEND_DEVICE))

    threads = [threading.Thread(target=ask) for _ in range(8)]
    for thread in threads:
        thread.start()
    assert runner.started.acquire(timeout=10)
    runner.go.set()
    for thread in threads:
        thread.join(10)

    assert len(runner.calls) == 1
    assert answers == [FRIEND_LOGIN] * 8


def test_at_most_four_lookups_run_at_once() -> None:
    addresses = [f"100.70.0.{n}" for n in range(1, 6)]
    runner = BlockingRunner({a: _profile(HOST_LOGIN) for a in addresses})
    whois = TailscaleWhois(("tailscale",), runner=runner)
    threads = [
        threading.Thread(target=whois.login_of, args=(a,)) for a in addresses[:4]
    ]
    for thread in threads:
        thread.start()
    for _ in threads:
        assert runner.started.acquire(timeout=10)

    # The fifth address finds four runs going and answers at once.
    assert whois.login_of(addresses[4]) is None
    runner.go.set()
    for thread in threads:
        thread.join(10)
    assert len(runner.calls) == 4
    # Not cached as an answer: asked again, it runs.
    assert whois.login_of(addresses[4]) == HOST_LOGIN


def test_whois_asks_about_one_spelling_of_an_ipv6_address() -> None:
    runner = FakeRunner({"fd7a:115c:a1e0::401:ece8": _profile(HOST_LOGIN)})
    whois = TailscaleWhois(("tailscale",), runner=runner)

    assert whois.login_of("fd7a:115c:a1e0:0::401:ECE8") == HOST_LOGIN
    assert runner.calls[0][-1] == "fd7a:115c:a1e0::401:ece8"


def test_a_named_tailscale_command_must_exist(tmp_path: Path) -> None:
    assert find_tailscale_cli(str(tmp_path / "missing")) is None
    present = tmp_path / "tailscale"
    present.write_text("")
    assert find_tailscale_cli(str(present)) == str(present)


# --- the session layer judges ------------------------------------------


def _manager(*users: str) -> GameSessionManager:
    return GameSessionManager(
        access=AccessMode.REMOTE, admin_key=ADMIN_KEY, admin_tailnet_users=users
    )


def test_a_device_of_the_hosts_account_gets_an_admin_session() -> None:
    manager = _manager(HOST_LOGIN)

    session = manager.tailnet_admin_login(HOST_LOGIN)

    from dune_imperium.server.access import Credentials

    assert manager.is_admin(Credentials(admin_session=session))
    # Login names are compared without regard to case.
    assert manager.tailnet_admin_login("Host@Example.com")


@pytest.mark.parametrize("login", [FRIEND_LOGIN, None, "tagged-devices"])
def test_any_other_device_is_refused(login: str | None) -> None:
    with pytest.raises(AdminAccessError):
        _manager(HOST_LOGIN).tailnet_admin_login(login)


def test_a_server_without_accounts_has_no_tailscale_sign_in() -> None:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key=ADMIN_KEY)

    assert manager.tailnet_sign_in is False
    with pytest.raises(SessionError):
        manager.tailnet_admin_login(HOST_LOGIN)


def test_accounts_only_apply_to_remote_access_and_must_be_logins() -> None:
    with pytest.raises(ValueError, match="remote"):
        GameSessionManager(admin_tailnet_users=[HOST_LOGIN])
    with pytest.raises(ValueError, match="not a Tailscale login"):
        _manager("tagged-devices")


# --- over HTTP ------------------------------------------------------------

fastapi = pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from dune_imperium.server.app import ADMIN_COOKIE, create_app  # noqa: E402


class FakeIdentity:
    def __init__(self, logins: dict[str, str]) -> None:
        self.logins = logins
        self.asked: list[str] = []

    def login_of(self, address: str) -> str | None:
        self.asked.append(address)
        return self.logins.get(address)


def _app(
    tmp_path: Path, identity: FakeIdentity | None, *users: str
) -> FastAPI:
    return create_app(
        _manager(*users),
        saves_dir=tmp_path / "saves",
        card_images_dir=tmp_path / "no-images",
        icons_dir=tmp_path / "no-icons",
        tokens_dir=tmp_path / "no-tokens",
        board_image=tmp_path / "no-map.jpg",
        bene_tleilax_image=tmp_path / "no-bene-tleilax.jpg",
        tailnet_identity=identity,
    )


@pytest.fixture
def identity() -> FakeIdentity:
    return FakeIdentity({HOST_DEVICE: HOST_LOGIN, FRIEND_DEVICE: FRIEND_LOGIN})


def test_the_hosts_device_signs_in_and_becomes_the_admin(
    tmp_path: Path, identity: FakeIdentity
) -> None:
    app = _app(tmp_path, identity, HOST_LOGIN)
    client = TestClient(app, client=(HOST_DEVICE, 51000))

    before = client.get("/whoami").json()
    assert before["admin"] is False
    assert before["tailscale_sign_in"] is True
    assert client.get("/games").status_code == 403

    response = client.post("/auth/tailscale")

    assert response.status_code == 200, response.text
    assert identity.asked == [HOST_DEVICE]
    cookie = client.cookies.get(ADMIN_COOKIE)
    assert cookie and ADMIN_KEY not in cookie
    header = response.headers["set-cookie"].lower()
    assert "httponly" in header and "samesite=strict" in header
    assert client.get("/whoami").json()["admin"] is True
    assert client.get("/games").status_code == 200


def test_a_friends_shared_device_stays_a_player(
    tmp_path: Path, identity: FakeIdentity
) -> None:
    client = TestClient(_app(tmp_path, identity, HOST_LOGIN), client=(FRIEND_DEVICE, 1))

    response = client.post("/auth/tailscale")

    assert response.status_code == 403
    assert ADMIN_COOKIE not in client.cookies
    assert "set-cookie" not in response.headers
    assert client.get("/whoami").json()["admin"] is False


def test_an_unknown_peer_stays_a_player(tmp_path: Path, identity: FakeIdentity) -> None:
    client = TestClient(_app(tmp_path, identity, HOST_LOGIN), client=("100.70.0.9", 1))

    assert client.post("/auth/tailscale").status_code == 403
    assert client.get("/whoami").json()["admin"] is False


def test_a_proxy_header_names_nobody(tmp_path: Path, identity: FakeIdentity) -> None:
    # The app reads the connection's own client address; the command line
    # also turns uvicorn's proxy headers off (see the main() test below).
    client = TestClient(_app(tmp_path, identity, HOST_LOGIN), client=(FRIEND_DEVICE, 1))

    response = client.post(
        "/auth/tailscale", headers={"X-Forwarded-For": HOST_DEVICE}
    )

    assert response.status_code == 403
    assert identity.asked == [FRIEND_DEVICE]


def test_without_tailscale_sign_in_the_route_is_not_there(tmp_path: Path) -> None:
    client = TestClient(_app(tmp_path, None), client=(HOST_DEVICE, 1))

    assert client.get("/whoami").json()["tailscale_sign_in"] is False
    assert client.post("/auth/tailscale").status_code == 404


def test_the_accounts_and_the_whois_come_together(
    tmp_path: Path, identity: FakeIdentity
) -> None:
    with pytest.raises(ValueError, match="Tailscale sign-in"):
        _app(tmp_path, identity)
    with pytest.raises(ValueError, match="Tailscale sign-in"):
        _app(tmp_path, None, HOST_LOGIN)


def test_the_admin_link_keeps_working_beside_it(
    tmp_path: Path, identity: FakeIdentity
) -> None:
    client = TestClient(_app(tmp_path, identity, HOST_LOGIN), client=(FRIEND_DEVICE, 1))

    assert client.post("/auth/admin", json={"key": ADMIN_KEY}).status_code == 200
    assert client.get("/whoami").json()["admin"] is True


# --- the command line ----------------------------------------------------


def _arguments(*argv: str) -> argparse.Namespace:
    return _build_parser().parse_args(list(argv))


def _fake_cli(tmp_path: Path) -> Path:
    """An executable ``tailscale`` that answers ``whois`` like tailscaled."""

    script = tmp_path / "bin" / "tailscale"
    script.parent.mkdir()
    logins = {HOST_DEVICE: HOST_LOGIN, FRIEND_DEVICE: FRIEND_LOGIN}
    script.write_text(
        f"#!{sys.executable}\n"
        "import json, sys\n"
        f"logins = {logins!r}\n"
        "address = sys.argv[-1]\n"
        "if sys.argv[1:3] != ['whois', '--json'] or address not in logins:\n"
        "    sys.exit(1)\n"
        "print(json.dumps({'Node': {'Name': 'device.'},"
        " 'UserProfile': {'LoginName': logins[address]}}))\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def test_the_flag_needs_remote_a_tailscale_host_and_a_login(tmp_path: Path) -> None:
    cli = str(_fake_cli(tmp_path))
    base = ("--admin-tailscale-user", HOST_LOGIN, "--tailscale-cli", cli)
    with pytest.raises(ValueError, match="--remote"):
        resolve_tailnet_admins(_arguments("--host", HOST_DEVICE, *base))
    for host in ("127.0.0.1", "0.0.0.0", "192.168.0.65"):
        with pytest.raises(ValueError, match="Tailscale address"):
            resolve_tailnet_admins(_arguments("--remote", "--host", host, *base))
    with pytest.raises(ValueError, match="not a Tailscale login"):
        resolve_tailnet_admins(
            _arguments(
                "--remote", "--host", HOST_DEVICE,
                "--admin-tailscale-user", "tagged-devices", "--tailscale-cli", cli,
            )
        )
    with pytest.raises(ValueError, match="no "):
        resolve_tailnet_admins(
            _arguments(
                "--remote", "--host", HOST_DEVICE, "--admin-tailscale-user",
                HOST_LOGIN, "--tailscale-cli", str(tmp_path / "missing"),
            )
        )
    with pytest.raises(ValueError, match="--tailscale-cli only applies"):
        resolve_tailnet_admins(_arguments("--tailscale-cli", cli))


def test_the_flag_resolves_to_the_accounts_and_the_command(tmp_path: Path) -> None:
    cli = str(_fake_cli(tmp_path))
    users, command = resolve_tailnet_admins(
        _arguments(
            "--remote", "--host", HOST_DEVICE, "--tailscale-cli", cli,
            "--admin-tailscale-user", HOST_LOGIN,
            "--admin-tailscale-user", "other@example.com",
        )
    )
    assert users == {HOST_LOGIN, "other@example.com"}
    assert command == cli
    assert resolve_tailnet_admins(_arguments()) == (frozenset(), None)


def test_the_startup_lines_say_whose_devices_and_warn_when_whois_fails() -> None:
    lines = tailnet_lines(frozenset({HOST_LOGIN}), HOST_LOGIN, HOST_DEVICE)
    assert lines == [
        f"Tailscale sign-in: the devices of {HOST_LOGIN} open the page as admin."
    ]
    warned = tailnet_lines(frozenset({HOST_LOGIN}), None, HOST_DEVICE)
    assert "did not answer" in warned[1]


@pytest.mark.skipif(os.name != "posix", reason="the fake tailscale is a script")
def test_main_serves_the_sign_in_with_proxy_headers_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    uvicorn = pytest.importorskip("uvicorn")
    served: list[object] = []

    def keep_the_config(self: object, *args: object, **kwargs: object) -> None:
        served.append(self.config)  # type: ignore[attr-defined]

    monkeypatch.setattr(uvicorn.Server, "run", keep_the_config)
    # This machine need not own a Tailscale address for the test.
    monkeypatch.setattr(server_cli, "bind_problem", lambda host, port: None)
    monkeypatch.delenv(SEARCH_CHECKPOINT_ENVIRONMENT, raising=False)
    monkeypatch.setattr(
        server_cli, "DEFAULT_SEARCH_CHECKPOINT", tmp_path / "no-search.pt"
    )
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    code = main(
        [
            "--remote", "--host", HOST_DEVICE, "--port", str(port),
            "--admin-key", ADMIN_KEY, "--saves-dir", str(tmp_path / "saves"),
            "--admin-tailscale-user", HOST_LOGIN,
            "--tailscale-cli", str(_fake_cli(tmp_path)),
        ]
    )

    assert code == 0
    assert len(served) == 1
    config = served[0]
    assert config.proxy_headers is False  # type: ignore[attr-defined]
    out = capsys.readouterr().out
    assert f"Tailscale sign-in: the devices of {HOST_LOGIN}" in out
    assert "did not answer" not in out  # whois of the host's own address
    app = config.app  # type: ignore[attr-defined]
    base = f"http://{HOST_DEVICE}:{port}"
    host = TestClient(app, base_url=base, client=(HOST_DEVICE, 51000))
    friend = TestClient(app, base_url=base, client=(FRIEND_DEVICE, 51000))
    assert friend.post("/auth/tailscale").status_code == 403
    assert host.post("/auth/tailscale").status_code == 200
    assert host.get("/games").status_code == 200
    # The admin page's log collects the server's lines once uvicorn's own
    # logging is configured (server.host_status.RecentLog).
    log = host.get("/admin/status").json()["log"]
    assert [line["message"] for line in log][-1] == (
        f"Admin sign-in through Tailscale: {HOST_LOGIN} from {HOST_DEVICE}"
    )


def test_without_the_flag_proxy_headers_stay_as_uvicorn_has_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    uvicorn = pytest.importorskip("uvicorn")
    served: list[object] = []
    monkeypatch.setattr(
        uvicorn.Server, "run", lambda self, *a, **k: served.append(self.config)
    )
    monkeypatch.delenv(SEARCH_CHECKPOINT_ENVIRONMENT, raising=False)
    monkeypatch.setattr(
        server_cli, "DEFAULT_SEARCH_CHECKPOINT", tmp_path / "no-search.pt"
    )
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    assert main(["--port", str(port), "--saves-dir", str(tmp_path / "saves")]) == 0
    assert served[0].proxy_headers is True  # type: ignore[attr-defined]
