"""Own servers selected from the native menu, over a private local mailbox.

Only the launcher creates this directory (0700); Godot receives its path.
Requests/responses are atomic files, never an exposed HTTP management API.
Administrator keys exist only in this private response and authenticated POSTs.
The launcher owns every started process and stops it when the client exits.
"""

import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dune_imperium.godot_client.host_config import parse_host_config, server_origin
from dune_imperium.launcher.addresses import Discovery, best_remote_address, discover
from dune_imperium.launcher.command import LaunchPlan, build_plan, run_output
from dune_imperium.launcher.settings import LauncherSettings
from dune_imperium.launcher.supervisor import ServerProcess, StartupFailed

ServerFactory = Callable[[LaunchPlan, Path], ServerProcess]


class HostControl:
    def __init__(
        self, directory: Path, *, assets: Path | None,
        free_port: Callable[[], int], server_factory: ServerFactory,
        discover_addresses: Callable[[], Discovery] = lambda: discover(run_output),
    ) -> None:
        self.directory = directory
        self.assets = assets
        self.free_port = free_port
        self.server_factory = server_factory
        self.discover_addresses = discover_addresses
        self.server: ServerProcess | None = None
        self._settings: LauncherSettings | None = None
        self._python: str | None = None
        self._last_id = 0

    def snapshot(self) -> dict[str, Any]:
        if self.server is None or not self.server.is_alive():
            return {"running": False}
        plan = self.server.plan
        return {
            "running": True, "mode": "remote" if plan.remote else "local",
            "origin": server_origin(plan.host, plan.port),
            "room_base": plan.room_base, "port": plan.port,
        }

    def stop(self) -> None:
        if self.server is not None:
            stopped = self.server.stop()
            if not stopped.port_free and self.server.is_alive():
                raise RuntimeError(
                    "서버 포트가 아직 사용 중입니다. 잠시 후 다시 시도하세요."
                )
            self.server = None
            self._settings = None

    def dispatch(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.server is not None and not self.server.is_alive():
            self.stop()
        operation = request.get("operation")
        if operation == "inspect":
            found = self.discover_addresses()
            return {
                **self.snapshot(),
                "addresses": [{"ip": item.ip, "kind": item.kind}
                              for item in found.candidates],
                "suggested_ip": best_remote_address(found),
                "tailscale_running": bool(found.tailscale and found.tailscale.running),
            }
        if operation == "stop":
            self.stop()
            return self.snapshot()
        if operation != "start":
            raise ValueError("알 수 없는 서버 요청입니다.")
        data = request.get("preferences")
        if not isinstance(data, dict):
            raise ValueError("서버 설정을 확인해 주세요.")
        previous = self.server
        local_port = (
            previous.plan.port if previous is not None and not previous.plan.remote
            else self.free_port()
        )
        config = parse_host_config(data, assets=self.assets, local_port=local_port)
        if config.settings.mode == "remote" and not config.settings.public_url:
            raise ValueError("친구에게 보낼 서버 주소를 선택하거나 입력하세요.")
        if self._settings != config.settings or self._python != config.python:
            # Validate before shutting down the old server. Never kill another
            # process to claim a port; wait_ready reports an occupied port.
            plan = build_plan(config.settings, config.key, python=config.python)
            self.stop()
            started = self.server_factory(plan, self.directory.parent / "server")
            try:
                started.start()
                started.wait_ready()
            except BaseException:
                started.stop()
                raise
            self.server = started
            self._settings = config.settings
            self._python = config.python
        assert self.server is not None
        result = self.snapshot()
        if self.server.plan.admin_key:
            result["credentials"] = {
                "origin": result["origin"], "key": self.server.plan.admin_key,
            }
        return result

    def process_once(self) -> None:
        path = self.directory / "request.json"
        if not path.is_file():
            return
        identifier = 0
        try:
            if path.stat().st_size > 64 * 1024:
                raise ValueError("서버 요청이 너무 큽니다.")
            request = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(request, dict):
                raise ValueError("잘못된 서버 요청입니다.")
            identifier = request.get("id", 0)
            if type(identifier) is not int or identifier <= self._last_id:
                identifier = 0
                raise ValueError("이미 처리했거나 잘못된 서버 요청입니다.")
            self._last_id = identifier
            result = {"id": identifier, "ok": True, **self.dispatch(request)}
        except (OSError, ValueError, RuntimeError, StartupFailed) as error:
            result = {
                "id": identifier, "ok": False, "message": str(error),
                **self.snapshot(),
            }
        finally:
            path.unlink(missing_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
        scratch = Path(temporary)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                json.dump(result, output, ensure_ascii=False)
            scratch.replace(self.directory / "response.json")
        finally:
            scratch.unlink(missing_ok=True)
