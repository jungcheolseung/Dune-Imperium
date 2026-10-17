"""The title menu controls only its owned server and shares no admin URL."""

import json
import stat
import subprocess
from pathlib import Path

import pytest

from dune_imperium.godot_client import launch
from dune_imperium.godot_client.host_control import HostControl
from dune_imperium.launcher.addresses import Candidate, Discovery
from dune_imperium.launcher.command import LaunchPlan
from dune_imperium.launcher.supervisor import ServerProcess, StartupFailed, Stopped


class FakeServer(ServerProcess):
    def __init__(self, plan: LaunchPlan, logs: Path) -> None:
        self.plan = plan
        self.starts = 0
        self.stops = 0
        self.fail = False

    def start(self) -> None:
        self.starts += 1

    def is_alive(self) -> bool:
        return self.starts > self.stops

    def wait_ready(
        self, timeout: float = 30.0, *, interval: float = 0.2,
    ) -> dict[str, object]:
        if self.fail:
            raise StartupFailed("이미 사용 중인 포트", [], 1)
        return {}

    def stop(self, *, grace: float = 10.0, term_grace: float = 5.0) -> Stopped:
        self.stops += 1
        return Stopped("stdin", 0, 0, True)


def control(tmp_path: Path) -> tuple[HostControl, list[FakeServer]]:
    started: list[FakeServer] = []

    def factory(plan: LaunchPlan, logs: Path) -> ServerProcess:
        server = FakeServer(plan, logs)
        started.append(server)
        return server

    mailbox = HostControl(
        tmp_path, assets=None, free_port=lambda: 9123, server_factory=factory,
        discover_addresses=lambda: Discovery((
            Candidate("192.168.1.9", "lan", "test"),
            Candidate("127.0.0.1", "loopback", "test"),
        ), None, True),
    )
    return mailbox, started


def start(mode: str = "local") -> dict[str, object]:
    host: dict[str, object] = {"mode": mode}
    if mode == "remote":
        host.update(port=8123, public_url="http://192.168.1.9:8123")
    return {"operation": "start", "preferences": {"host": host}}


def test_title_and_address_inspection_start_no_server(tmp_path: Path) -> None:
    mailbox, started = control(tmp_path)
    assert mailbox.snapshot() == {"running": False}
    found = mailbox.dispatch({"operation": "inspect"})
    assert found["suggested_ip"] == "192.168.1.9"
    assert found["addresses"][0] == {"ip": "192.168.1.9", "kind": "lan"}
    assert not found["running"] and not started
    mailbox.stop()


def test_mode_changes_stop_only_the_owned_server_and_same_mode_reuses_it(
    tmp_path: Path,
) -> None:
    mailbox, started = control(tmp_path)
    local = mailbox.dispatch(start())
    assert local["origin"] == "http://127.0.0.1:9123"
    mailbox.dispatch(start())
    assert len(started) == 1 and started[0].stops == 0
    remote = mailbox.dispatch(start("remote"))
    assert started[0].stops == 1 and len(started) == 2
    assert remote["room_base"] == "http://192.168.1.9:8123"
    key = remote["credentials"]["key"]
    assert key not in remote["room_base"]
    assert all(key not in arg for arg in started[1].plan.argv)
    assert "credentials" not in mailbox.dispatch({"operation": "inspect"})
    assert mailbox.dispatch(start("remote"))["credentials"]["key"] == key
    assert len(started) == 2
    mailbox.dispatch({"operation": "stop"})
    assert started[1].stops == 1 and mailbox.server is None
    mailbox.stop()
    assert started[1].stops == 1


@pytest.mark.parametrize("preferences", [
    {"host": {"mode": "bad"}}, {"host": {"mode": "remote"}},
    {"host": {"mode": "remote", "port": True}},
    {"host": {"public_url": "https://user:secret@example.com"}},
    {"host": {"python": "/missing-python"}},
])
def test_invalid_preferences_preserve_the_running_server(
    tmp_path: Path, preferences: dict[str, object],
) -> None:
    mailbox, started = control(tmp_path)
    mailbox.dispatch(start())
    with pytest.raises(ValueError):
        mailbox.dispatch({"operation": "start", "preferences": preferences})
    assert mailbox.server is started[0] and started[0].stops == 0


def test_mailbox_consumes_once_and_writes_a_private_credential_response(
    tmp_path: Path,
) -> None:
    mailbox, started = control(tmp_path)
    request = tmp_path / "request.json"
    request.write_text(json.dumps({"id": 1, **start("remote")}))
    mailbox.process_once()
    response = tmp_path / "response.json"
    data = json.loads(response.read_text())
    assert data["ok"] and data["id"] == 1 and data["credentials"]["key"]
    assert stat.S_IMODE(response.stat().st_mode) == 0o600
    assert not request.exists() and not list(tmp_path.glob("*.tmp"))
    mailbox.process_once()
    assert len(started) == 1
    request.write_text(json.dumps({"id": 1, **start()}))
    mailbox.process_once()
    assert not json.loads(response.read_text())["ok"]
    assert started[0].stops == 0
    mailbox.stop()


def test_start_failure_cleans_up_and_accepts_a_retry(tmp_path: Path) -> None:
    mailbox, started = control(tmp_path)
    original = mailbox.server_factory

    def failed(plan: LaunchPlan, logs: Path) -> ServerProcess:
        result = original(plan, logs)
        assert isinstance(result, FakeServer)
        result.fail = True
        return result

    mailbox.server_factory = failed
    (tmp_path / "request.json").write_text(json.dumps({"id": 1, **start()}))
    mailbox.process_once()
    response = json.loads((tmp_path / "response.json").read_text())
    assert not response["ok"] and "포트" in response["message"]
    assert started[0].stops == 1 and mailbox.server is None
    mailbox.server_factory = original
    assert mailbox.dispatch(start())["running"]
    mailbox.stop()


@pytest.mark.parametrize("payload", [
    '[]', '{bad', '{"id": true}', '{"id": 1, "operation": "unknown"}',
])
def test_bad_request_is_reported_without_crashing_the_launcher(
    tmp_path: Path, payload: str,
) -> None:
    mailbox, started = control(tmp_path)
    (tmp_path / "request.json").write_text(payload)
    mailbox.process_once()
    assert not json.loads((tmp_path / "response.json").read_text())["ok"]
    assert not started


def test_interactive_launch_shows_the_menu_without_starting_a_saved_remote_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    binary = tmp_path / "Godot.exe"
    binary.touch()
    seen: list[str] = []

    class Client:
        def __init__(self, args: list[str], **kwargs: object) -> None:
            seen.extend(args)

        def wait(self, timeout: float = 0.1) -> int:
            return 0

        def poll(self) -> int:
            return 0

    monkeypatch.setattr(launch, "TMP_DIR", tmp_path)
    monkeypatch.setattr(launch, "find_assets", lambda: None)
    monkeypatch.setattr(subprocess, "Popen", Client)
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess([], 0),
    )
    monkeypatch.setattr(
        launch, "ServerProcess",
        lambda *a, **k: pytest.fail("server started before a mode was selected"),
    )
    assert launch.main(["--godot", str(binary)]) == 0
    assert "--server=" in seen
    assert any(arg.startswith("--host-control=") for arg in seen)
    assert not list((tmp_path / "godot").glob("host-*"))


def test_a_dead_owned_server_can_be_started_again(tmp_path: Path) -> None:
    mailbox, started = control(tmp_path)
    mailbox.dispatch(start())
    started[0].stops = 1  # The child exited independently.
    assert not mailbox.snapshot()["running"]
    assert mailbox.dispatch(start())["running"]
    assert len(started) == 2
    mailbox.stop()


def test_interactive_client_exit_stops_a_server_started_by_the_menu(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    binary = tmp_path / "Godot.exe"
    binary.touch()
    started: list[FakeServer] = []

    def server(plan: LaunchPlan, *, log_dir: Path) -> FakeServer:
        instance = FakeServer(plan, log_dir)
        started.append(instance)
        return instance

    class Client:
        def __init__(self, args: list[str], **kwargs: object) -> None:
            argument = next(arg for arg in args if arg.startswith("--host-control="))
            self.mailbox = Path(argument.split("=", 1)[1])
            (self.mailbox / "request.json").write_text(json.dumps({"id": 1, **start()}))
            self.waits = 0

        def wait(self, timeout: float = 0.1) -> int:
            self.waits += 1
            if self.waits == 1:
                raise subprocess.TimeoutExpired([], timeout)
            response = json.loads((self.mailbox / "response.json").read_text())
            assert response["ok"] and response["running"]
            return 0

        def poll(self) -> int:
            return 0

    monkeypatch.setattr(launch, "TMP_DIR", tmp_path)
    monkeypatch.setattr(launch, "find_assets", lambda: None)
    monkeypatch.setattr(launch, "free_port", lambda: 9123)
    monkeypatch.setattr(launch, "ServerProcess", server)
    monkeypatch.setattr(subprocess, "Popen", Client)
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: subprocess.CompletedProcess([], 0),
    )
    assert launch.main(["--godot", str(binary)]) == 0
    assert len(started) == 1 and started[0].starts == started[0].stops == 1
    assert not list((tmp_path / "godot").glob("host-*"))
