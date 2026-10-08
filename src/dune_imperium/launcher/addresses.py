"""The addresses this machine could serve the other players on.

docs/server-launcher-plan.md 5.6. There is no single right answer to "my
address": a VPN can own the default route (the UDP trick then names the
VPN, not the LAN), Tailscale may be off, a meeting place may have no
Internet. So the launcher shows a labelled list and remembers the host's
pick. The parsers are pure functions over command output; the lookups
swallow every failure and return nothing, so a missing tool only shortens
the list.
"""

import ipaddress
import json
import os
import socket
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, Protocol

Kind = Literal["tailscale", "lan", "outbound", "loopback"]

# Tailscale hands out addresses from the CGNAT range (RFC 6598).
TAILSCALE_NETWORK: Final = ipaddress.ip_network("100.64.0.0/10")
# Tailscale's own resolver address; a route to it exists only while
# Tailscale is connected, so the source address towards it is ours there.
TAILSCALE_PROBE: Final = "100.100.100.100"
OUTBOUND_PROBE: Final = "8.8.8.8"
LOOPBACK: Final = "127.0.0.1"
_LABELS: Final[Mapping[Kind, str]] = {
    "tailscale": "Tailscale",
    "lan": "같은 네트워크(LAN)",
    "outbound": "인터넷으로 나가는 주소",
    "loopback": "이 PC에서만",
}
_ORDER: Final[Mapping[Kind, int]] = {
    "tailscale": 0,
    "lan": 1,
    "outbound": 2,
    "loopback": 3,
}


@dataclass(frozen=True)
class Candidate:
    ip: str
    kind: Kind
    # Where it came from, for the diagnostics ("tailscale CLI", "ifconfig").
    source: str

    @property
    def label(self) -> str:
        return f"{_LABELS[self.kind]} — {self.ip}"


@dataclass(frozen=True)
class TailscaleStatus:
    # ``BackendState``: "Running", "Stopped", "NeedsLogin", ...
    state: str | None
    ipv4: str | None

    @property
    def running(self) -> bool:
        return self.state == "Running"


class Runner(Protocol):
    """Run a command with a timeout (and extra environment variables);
    return its standard output, or ``None`` if it could not run or failed."""

    def __call__(
        self,
        argv: Sequence[str],
        timeout: float,
        /,
        *,
        env: Mapping[str, str] | None = None,
    ) -> str | None: ...


# The App Store app's executable decides from the environment (SHLVL, TERM)
# whether it was started as the CLI; from Finder it would not be. Tailscale
# documents this variable for scripts.
_TAILSCALE_CLI_ENVIRONMENT: Final = {"TAILSCALE_BE_CLI": "1"}


def classify(ip: str) -> Kind | None:
    """The kind of a local IPv4 address, or ``None`` for one not to offer."""

    try:
        address = ipaddress.IPv4Address(ip)
    except ValueError:
        return None
    if address.is_loopback:
        return "loopback"
    if address in TAILSCALE_NETWORK:
        return "tailscale"
    if address.is_link_local or address.is_unspecified or address.is_multicast:
        return None
    if address.is_private:
        return "lan"
    return None


def parse_tailscale_status(text: str) -> TailscaleStatus:
    """Read ``tailscale status --json``; a format change means "unknown"."""

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return TailscaleStatus(None, None)
    if not isinstance(data, dict):
        return TailscaleStatus(None, None)
    state = data.get("BackendState")
    addresses: object = None
    own = data.get("Self")
    if isinstance(own, dict):
        addresses = own.get("TailscaleIPs")
    if not isinstance(addresses, list):
        addresses = data.get("TailscaleIPs")
    ipv4 = None
    if isinstance(addresses, list):
        for value in addresses:
            if isinstance(value, str) and classify(value) == "tailscale":
                ipv4 = value
                break
    return TailscaleStatus(state if isinstance(state, str) else None, ipv4)


def parse_ifconfig(text: str) -> list[tuple[str, bool]]:
    """The IPv4 addresses in macOS ``ifconfig`` output (``inet`` lines).

    Each comes with whether its interface is point-to-point: the tunnels of
    VPN clients (``utun``), whose private addresses are not the LAN.
    """

    found: list[tuple[str, bool]] = []
    point_to_point = False
    for line in text.splitlines():
        if line and not line[0].isspace():
            point_to_point = "POINTOPOINT" in line
            continue
        words = line.split()
        if len(words) >= 2 and words[0] == "inet":
            found.append((words[1], point_to_point))
    return found


def parse_get_netipaddress_json(text: str) -> list[str]:
    """The addresses in ``Get-NetIPAddress ... | ConvertTo-Json`` output.

    PowerShell writes one object for a single result and a list otherwise.
    """

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    items = data if isinstance(data, list) else [data]
    found: list[str] = []
    for item in items:
        if isinstance(item, dict):
            value = item.get("IPAddress")
            if isinstance(value, str):
                found.append(value)
    return found


def tailscale_cli_paths(
    platform: str = sys.platform, environ: Mapping[str, str] = os.environ
) -> list[str]:
    """Where the Tailscale CLI may be, most likely first.

    A launcher started from Finder has no shell PATH (launchd's default
    only), so the App Store app's bundled CLI is named by its full path.
    """

    paths: list[str] = []
    if platform == "darwin":
        paths += [
            "/usr/local/bin/tailscale",
            "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
        ]
    elif platform == "win32":
        program_files = environ.get("ProgramFiles", r"C:\Program Files")
        paths.append(str(Path(program_files) / "Tailscale" / "tailscale.exe"))
    else:
        paths += ["/usr/bin/tailscale", "/usr/local/bin/tailscale"]
    return paths


def route_source_address(target: str) -> str | None:
    """The local address the system would send from towards ``target``.

    A UDP ``connect`` only picks a route; no packet leaves the machine.
    """

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect((target, 9))
            address: str = probe.getsockname()[0]
            return address
    except OSError:
        return None


def hostname_addresses() -> list[str]:
    """The IPv4 addresses the machine's own name resolves to."""

    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        return []
    return [str(info[4][0]) for info in infos]


def find_tailscale_cli(
    platform: str = sys.platform, environ: Mapping[str, str] = os.environ
) -> str | None:
    """The Tailscale CLI on this machine, or ``None``."""

    import shutil

    on_path = shutil.which("tailscale")
    if on_path:
        return on_path
    for path in tailscale_cli_paths(platform, environ):
        if Path(path).exists():
            return path
    return None


def tailscale_status(run: Runner, cli: str | None) -> TailscaleStatus | None:
    """Ask the Tailscale CLI, or ``None`` when there is none or it failed."""

    if cli is None:
        return None
    output = run([cli, "status", "--json"], 3.0, env=_TAILSCALE_CLI_ENVIRONMENT)
    return None if output is None else parse_tailscale_status(output)


def interface_addresses(run: Runner, platform: str = sys.platform) -> list[str]:
    """The IPv4 addresses of the machine's interfaces, best effort.

    On macOS the point-to-point tunnels are left out unless they are
    Tailscale's; Windows reports no such flag, so all are kept.
    """

    if platform == "win32":
        output = run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-NetIPAddress -AddressFamily IPv4 | "
                "Select-Object IPAddress | ConvertTo-Json",
            ],
            10.0,
        )
        return parse_get_netipaddress_json(output) if output else []
    output = run(["/sbin/ifconfig"], 3.0)
    if not output:
        return []
    return [
        ip
        for ip, point_to_point in parse_ifconfig(output)
        if not point_to_point or classify(ip) == "tailscale"
    ]


@dataclass(frozen=True)
class Discovery:
    candidates: tuple[Candidate, ...]
    # ``None`` when no Tailscale CLI answered.
    tailscale: TailscaleStatus | None
    # False when no route leads outside: a LAN without Internet, which is
    # fine for playing.
    internet_route: bool


def discover(
    run: Runner,
    *,
    platform: str = sys.platform,
    tailscale_cli: Callable[[], str | None] = find_tailscale_cli,
    source_address: Callable[[str], str | None] = route_source_address,
    own_addresses: Callable[[], list[str]] = hostname_addresses,
) -> Discovery:
    """Collect the labelled candidates, best first, each address once."""

    found: dict[str, Candidate] = {}
    status = tailscale_status(run, tailscale_cli())
    # A tunnel can keep its address after Tailscale was switched off; when
    # the CLI says so, that address is not offered.
    tailscale_off = status is not None and not status.running

    def offer(ip: str, source: str, kind: Kind | None = None) -> None:
        kind = kind or classify(ip)
        if kind is None or ip in found or (kind == "tailscale" and tailscale_off):
            return
        found[ip] = Candidate(ip, kind, source)

    if status is not None and status.running and status.ipv4:
        offer(status.ipv4, "tailscale CLI")
    tailscale_route = source_address(TAILSCALE_PROBE)
    if tailscale_route and classify(tailscale_route) == "tailscale":
        offer(tailscale_route, "route to 100.100.100.100")
    for ip in own_addresses():
        offer(ip, "host name")
    # Before the interface list: an address that only the default route
    # names (a VPN owning it) is labelled as such, not as the LAN.
    outbound = source_address(OUTBOUND_PROBE)
    if outbound and outbound not in found:
        kind = classify(outbound)
        if kind is not None and kind != "loopback":
            found[outbound] = Candidate(outbound, "outbound", "route to 8.8.8.8")
    for ip in interface_addresses(run, platform):
        offer(ip, "interfaces")
    offer(LOOPBACK, "loopback")
    ordered = sorted(found.values(), key=lambda c: _ORDER[c.kind])
    return Discovery(tuple(ordered), status, outbound is not None)


def best_remote_address(discovery: Discovery) -> str | None:
    """The address a remote game should start on when none was chosen yet."""

    for candidate in discovery.candidates:
        if candidate.kind in ("tailscale", "lan"):
            return candidate.ip
    return None
