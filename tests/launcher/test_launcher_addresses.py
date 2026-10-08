"""The address candidates (docs/server-launcher-plan.md 5.6)."""

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from dune_imperium.launcher.addresses import (
    Candidate,
    best_remote_address,
    classify,
    discover,
    parse_get_netipaddress_json,
    parse_ifconfig,
    parse_tailscale_status,
    tailscale_cli_paths,
)

# Trimmed from this project's Mac mini (2026-10-08): the LAN on en0, a VPN
# tunnel owning the default route on utun5, Tailscale on utun6.
IFCONFIG = """\
lo0: flags=8049<UP,LOOPBACK,RUNNING,MULTICAST> mtu 16384
\tinet 127.0.0.1 netmask 0xff000000
en0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
\tinet 192.168.0.64 netmask 0xffffff00 broadcast 192.168.0.255
bridge0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
utun6: flags=8051<UP,POINTOPOINT,RUNNING,MULTICAST> mtu 1280
\tinet 100.87.236.12 --> 100.87.236.12 netmask 0xffffffff
utun5: flags=8051<UP,POINTOPOINT,RUNNING,MULTICAST> mtu 1500
\tinet 10.1.0.4 --> 10.1.0.4 netmask 0xffff0000
"""


def _status(state: str, ips: list[str]) -> str:
    return json.dumps(
        {"BackendState": state, "Self": {"TailscaleIPs": ips}, "TailscaleIPs": ips}
    )


@pytest.mark.parametrize(
    ("ip", "kind"),
    [
        ("127.0.0.1", "loopback"),
        ("100.87.236.12", "tailscale"),
        ("100.63.0.1", None),
        ("192.168.0.64", "lan"),
        ("10.1.0.4", "lan"),
        ("172.16.5.5", "lan"),
        ("169.254.1.1", None),
        ("8.8.8.8", None),
        ("::1", None),
        ("not an address", None),
    ],
)
def test_classify(ip: str, kind: str | None) -> None:
    assert classify(ip) == kind


def test_a_running_tailscale_names_its_ipv4_address() -> None:
    status = parse_tailscale_status(
        _status("Running", ["fd7a:115c:a1e0::1", "100.87.236.12"])
    )
    assert status.running and status.ipv4 == "100.87.236.12"


def test_a_stopped_tailscale_is_not_running() -> None:
    status = parse_tailscale_status(_status("Stopped", []))
    assert not status.running and status.ipv4 is None


def test_an_unreadable_tailscale_answer_means_unknown() -> None:
    status = parse_tailscale_status("Tailscale is stopped.")
    assert status.state is None and status.ipv4 is None


def test_ifconfig_marks_the_point_to_point_tunnels() -> None:
    assert parse_ifconfig(IFCONFIG) == [
        ("127.0.0.1", False),
        ("192.168.0.64", False),
        ("100.87.236.12", True),
        ("10.1.0.4", True),
    ]


def test_powershell_writes_one_object_or_a_list() -> None:
    one = json.dumps({"IPAddress": "192.168.1.20"})
    many = json.dumps([{"IPAddress": "192.168.1.20"}, {"IPAddress": "127.0.0.1"}])
    assert parse_get_netipaddress_json(one) == ["192.168.1.20"]
    assert parse_get_netipaddress_json(many) == ["192.168.1.20", "127.0.0.1"]
    assert parse_get_netipaddress_json("") == []


def test_the_tailscale_cli_is_looked_for_where_each_installer_puts_it() -> None:
    mac = tailscale_cli_paths("darwin", {})
    assert "/Applications/Tailscale.app/Contents/MacOS/Tailscale" in mac
    windows = tailscale_cli_paths("win32", {"ProgramFiles": r"D:\Apps"})
    assert windows == [str(Path(r"D:\Apps") / "Tailscale" / "tailscale.exe")]


class FakeRunner:
    def __init__(self, outputs: Mapping[str, str | None]) -> None:
        self.outputs = outputs
        self.calls: list[tuple[list[str], dict[str, str] | None]] = []

    def __call__(
        self,
        argv: Sequence[str],
        timeout: float,
        /,
        *,
        env: Mapping[str, str] | None = None,
    ) -> str | None:
        self.calls.append((list(argv), None if env is None else dict(env)))
        for word, output in self.outputs.items():
            if word in argv[0]:
                return output
        return None


def _routes(table: Mapping[str, str | None]) -> FakeRoutes:
    return FakeRoutes(table)


class FakeRoutes:
    def __init__(self, table: Mapping[str, str | None]) -> None:
        self.table = table

    def __call__(self, target: str) -> str | None:
        return self.table.get(target)


def test_the_vpn_that_owns_the_default_route_is_not_called_the_lan() -> None:
    run = FakeRunner(
        {
            "tailscale": _status("Running", ["100.87.236.12"]),
            "ifconfig": IFCONFIG,
        }
    )
    found = discover(
        run,
        platform="darwin",
        tailscale_cli=lambda: "/opt/tailscale",
        source_address=_routes(
            {"100.100.100.100": "100.87.236.12", "8.8.8.8": "10.1.0.4"}
        ),
        own_addresses=lambda: ["192.168.0.64"],
    )
    assert [(c.kind, c.ip) for c in found.candidates] == [
        ("tailscale", "100.87.236.12"),
        ("lan", "192.168.0.64"),
        ("outbound", "10.1.0.4"),
        ("loopback", "127.0.0.1"),
    ]
    assert found.internet_route
    assert best_remote_address(found) == "100.87.236.12"
    # Finder starts the launcher without a shell; the app's CLI is told so.
    tailscale_call = next(call for call in run.calls if "tailscale" in call[0][0])
    assert tailscale_call[1] == {"TAILSCALE_BE_CLI": "1"}


def test_with_tailscale_off_the_lan_comes_first() -> None:
    run = FakeRunner({"tailscale": _status("Stopped", []), "ifconfig": IFCONFIG})
    found = discover(
        run,
        platform="darwin",
        tailscale_cli=lambda: "/opt/tailscale",
        # Without Tailscale's routes the probe follows the default route.
        source_address=_routes(
            {"100.100.100.100": "192.168.0.64", "8.8.8.8": "192.168.0.64"}
        ),
        own_addresses=lambda: ["192.168.0.64"],
    )
    # The tunnel may keep its address after Tailscale is switched off; the
    # CLI's word wins, so the default pick is the LAN.
    assert found.tailscale is not None and not found.tailscale.running
    assert [c.kind for c in found.candidates] == ["lan", "loopback"]
    assert best_remote_address(found) == "192.168.0.64"


def test_a_lan_without_internet_still_offers_the_lan() -> None:
    run = FakeRunner({})
    found = discover(
        run,
        platform="win32",
        tailscale_cli=lambda: None,
        source_address=_routes({}),
        own_addresses=lambda: ["192.168.1.20"],
    )
    assert found.candidates == (
        Candidate("192.168.1.20", "lan", "host name"),
        Candidate("127.0.0.1", "loopback", "loopback"),
    )
    assert not found.internet_route
    assert found.tailscale is None
